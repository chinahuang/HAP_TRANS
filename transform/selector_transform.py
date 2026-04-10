"""
Android <selector> XML → ArkTS 状态样式转换。

支持两类 selector：
  1. 颜色 selector（item 含 android:color）
     → 导出函数 getXxxColor(state: boolean): ResourceColor
  2. Drawable selector（item 含 android:drawable）
     → 导出常量 xxxStyle: StateStyles

ArkTS StateStyles 支持的状态：
  pressed / focused / normal / disabled / selected
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Optional

ANDROID_NS = "http://schemas.android.com/apk/res/android"


def _a(elem, name: str, default: str = "") -> str:
    return elem.get(f"{{{ANDROID_NS}}}{name}", elem.get(name, default))


def _to_camel(name: str) -> str:
    """snake_case / kebab-case → camelCase"""
    parts = re.split(r"[_\-]", name)
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _res_ref(val: str) -> str:
    """
    @color/foo  → $r('app.color.foo')
    @drawable/foo → $r('app.media.foo')
    其他值直接返回。
    """
    m = re.match(r"@(color|drawable|mipmap)/(\w+)", val)
    if not m:
        return f"'{val}'"
    kind, name = m.group(1), m.group(2)
    ns = "color" if kind == "color" else "media"
    return f"$r('app.{ns}.{name}')"


# Android state 属性 → ArkTS StateStyles key
_STATE_MAP: Dict[str, str] = {
    "state_pressed":  "pressed",
    "state_focused":  "focused",
    "state_selected": "selected",
    "state_enabled":  "disabled",   # state_enabled=false → disabled
    "state_checked":  None,         # 无内置对应，用函数参数
    "state_activated": "selected",
}


def _parse_items(root) -> List[Dict]:
    """
    解析 <selector> 下的 <item> 列表。
    返回 [{"states": {...}, "color": ..., "drawable": ...}, ...]
    """
    items = []
    for item in root:
        tag = item.tag.split("}")[-1] if "}" in item.tag else item.tag
        if tag != "item":
            continue

        entry: Dict = {"states": {}, "color": "", "drawable": ""}

        # 收集状态属性
        for attr_key in _STATE_MAP:
            val = _a(item, attr_key)
            if val:
                entry["states"][attr_key] = val.lower() == "true"

        # 收集资源引用
        entry["color"] = _a(item, "color")
        entry["drawable"] = _a(item, "drawable")

        items.append(entry)
    return items


class SelectorTransform:

    def convert_file(self, src_path: str) -> Tuple[str, bool]:
        """
        将 <selector> XML 转换为 ArkTS 代码。
        返回 (ets_content, success)；非 selector 文件返回 ("", False)。
        """
        try:
            tree = ET.parse(src_path)
            root = tree.getroot()
        except ET.ParseError:
            return "", False

        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag != "selector":
            return "", False

        items = _parse_items(root)
        if not items:
            return "", False

        # 判断类型：颜色 selector 还是 drawable selector
        has_color = any(i["color"] for i in items)
        has_drawable = any(i["drawable"] for i in items)

        if has_color and not has_drawable:
            return self._gen_color_selector(src_path, items)
        elif has_drawable:
            return self._gen_drawable_selector(src_path, items)
        else:
            return "", False

    def convert_all(
        self,
        drawable_dirs: List[str],
        out_styles_dir: str,
    ) -> Tuple[int, int]:
        """
        扫描 drawable 目录，转换所有 <selector> XML 为 ArkTS。
        返回 (converted, failed)。
        """
        os.makedirs(out_styles_dir, exist_ok=True)
        converted = 0
        failed = 0
        seen: set = set()

        for src_dir in drawable_dirs:
            if not os.path.isdir(src_dir):
                continue
            for fname in os.listdir(src_dir):
                if not fname.lower().endswith(".xml"):
                    continue
                if fname in seen:
                    continue
                seen.add(fname)

                src_path = os.path.join(src_dir, fname)
                ets_content, ok = self.convert_file(src_path)
                if ok:
                    base = os.path.splitext(fname)[0]
                    dest_name = f"{_to_camel(base)}Style.ets"
                    dest_path = os.path.join(out_styles_dir, dest_name)
                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(ets_content)
                    converted += 1
                # 非 selector 或转换失败不计入 failed（由 VectorTransform 统计）

        return converted, failed

    # ------------------------------------------------------------------ #

    def _gen_color_selector(self, src_path: str, items: List[Dict]) -> Tuple[str, bool]:
        """
        颜色 selector → 带状态参数的函数。
        示例：
          export function getDrawerItemColor(isChecked: boolean): ResourceColor {
            if (isChecked) { return $r('app.color.colorAccent') }
            return $r('app.color.colorGrey')
          }
        """
        base = os.path.splitext(os.path.basename(src_path))[0]
        camel = _to_camel(base)
        func_name = f"get{camel[0].upper()}{camel[1:]}"

        # 分析用了哪些状态参数
        state_params = self._collect_state_params(items)

        lines = [f"// Auto-converted from {os.path.basename(src_path)} (Android color selector)"]

        if not state_params:
            # 只有默认项
            default_item = next((i for i in items if not i["states"]), items[-1])
            ref = _res_ref(default_item["color"])
            lines.append(f"export function {func_name}(): ResourceColor {{")
            lines.append(f"  return {ref}")
            lines.append("}")
        else:
            param_sig = ", ".join(f"{p}: boolean" for p in state_params)
            lines.append(f"export function {func_name}({param_sig}): ResourceColor {{")

            # 先输出有"true"条件的项，将只含"false"条件或无条件的项作为默认返回
            default_ref: Optional[str] = None
            for item in items:
                if not item["color"]:
                    continue
                ref = _res_ref(item["color"])
                # 只有 "state_x=true" 才生成 if 条件；
                # 全为 false 状态或无状态的项视为默认项
                true_conditions = self._build_conditions(
                    {k: v for k, v in item["states"].items() if v}, state_params
                )
                if true_conditions:
                    lines.append(f"  if ({true_conditions}) {{")
                    lines.append(f"    return {ref}")
                    lines.append("  }")
                else:
                    default_ref = ref  # 无 true 条件 = 默认项
            if default_ref:
                lines.append(f"  return {default_ref}")
            else:
                lines.append("  return ''")  # fallback，保证函数有返回值

            lines.append("}")

        return "\n".join(lines) + "\n", True

    def _gen_drawable_selector(self, src_path: str, items: List[Dict]) -> Tuple[str, bool]:
        """
        Drawable selector → StateStyles 常量。
        示例：
          export const touchFeedbackStyle: StateStyles = {
            pressed: { backgroundImage: $r('app.media.touchFeedback') },
            normal:  { backgroundImage: $r('app.media.completedTaskBackground') }
          }
        """
        base = os.path.splitext(os.path.basename(src_path))[0]
        const_name = f"{_to_camel(base)}Style"

        lines = [f"// Auto-converted from {os.path.basename(src_path)} (Android drawable selector)"]
        lines.append(f"export const {const_name}: StateStyles = {{")

        default_ref: Optional[str] = None

        for item in items:
            if not item["drawable"]:
                continue
            ref = _res_ref(item["drawable"])
            states = item["states"]

            if not states:
                # 默认项 → normal
                default_ref = ref
                continue

            # 映射 state → ArkTS key
            ark_state = self._primary_ark_state(states)
            if ark_state:
                lines.append(f"  {ark_state}: {{ backgroundImage: {ref} }},")

        if default_ref:
            lines.append(f"  normal: {{ backgroundImage: {default_ref} }},")

        lines.append("}")

        return "\n".join(lines) + "\n", True

    # ------------------------------------------------------------------ #

    def _collect_state_params(self, items: List[Dict]) -> List[str]:
        """收集颜色 selector 中的 boolean 参数名（去重保序）。"""
        seen = set()
        params = []
        for item in items:
            for state_key, val in item["states"].items():
                # state_checked → isChecked
                param = "is" + state_key.replace("state_", "").title().replace("_", "")
                if param not in seen:
                    seen.add(param)
                    params.append(param)
        return params

    def _build_conditions(self, states: Dict[str, bool], params: List[str]) -> str:
        """将 states dict 转换为 ArkTS if 条件字符串。"""
        conditions = []
        for state_key, is_true in states.items():
            param = "is" + state_key.replace("state_", "").title().replace("_", "")
            if param in params:
                conditions.append(param if is_true else f"!{param}")
        return " && ".join(conditions)

    def _primary_ark_state(self, states: Dict[str, bool]) -> Optional[str]:
        """从 states dict 取出主要的 ArkTS 状态名。"""
        for state_key, is_true in states.items():
            ark = _STATE_MAP.get(state_key)
            if ark and is_true:
                return ark
            # state_enabled=false → disabled
            if state_key == "state_enabled" and not is_true:
                return "disabled"
        return None
