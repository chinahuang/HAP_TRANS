"""
将 Android XML 布局节点树转换为 ArkUI（ArkTS）组件代码。
"""
import os
import re
from typing import Dict, List, Optional
from parser.layout_parser import LayoutNode, ParsedLayout


# --------------------------------------------------------------------------- #
# 值转换工具
# --------------------------------------------------------------------------- #

def _databinding_expr(val: str) -> Optional[str]:
    """
    DataBinding 表达式解析：
      @{viewmodel.foo}                         → this.foo
      @{context.getString(viewmodel.noTasksLabel)} → this.noTasksLabel
      @{() -> viewmodel.openTask(task.id)}     → None  (lambda，交给 _databinding_onclick)
      @{(view) -> viewmodel.completeTask(...)} → None  (lambda，交给 _databinding_onclick)
    """
    m = re.match(r"@\{(.+)\}$", val, re.DOTALL)
    if not m:
        return None
    expr = m.group(1).strip()
    # lambda 表达式（含 ->）交给 onclick 处理，返回 None 表示"不是简单属性绑定"
    if "->" in expr:
        return None
    # 简单属性引用：取最后一个 . 后的 identifier
    ident = re.split(r"[\.(]", expr)[-1].rstrip(")")
    if ident and ident.isidentifier():
        return f"this.{ident}"
    return f"/* TODO: @{{{expr}}} */"


def _databinding_onclick(val: str) -> str:
    """
    把 DataBinding lambda 转为 ArkTS onClick 表达式。
      @{() -> viewmodel.openTask(task.id)}
        → () => { this.openTask(this.taskId) }
      @{(view) -> viewmodel.completeTask(task, ((CompoundButton)view).isChecked())}
        → // TODO: complex lambda - viewmodel.completeTask(...)
    """
    m = re.match(r"@\{(?:\([^)]*\)\s*->|)\s*(.+)\}$", val, re.DOTALL)
    if not m:
        return f"() => {{ /* TODO: {val} */ }}"
    body = m.group(1).strip()
    # 简单调用：obj.method(args)
    call_m = re.match(r"(\w+)\.(\w+)\(([^)]*)\)", body)
    if call_m:
        method = call_m.group(2)
        args_raw = call_m.group(3)
        # 参数中的 task.id → this.taskId，task.xxx → this.xxx
        args = re.sub(r"\btask\.(\w+)\b", lambda x: f"this.{x.group(1)}", args_raw)
        # 去掉强转，如 ((CompoundButton)view) → 标记 TODO
        if "(" in args and "->" not in args and "isChecked" in args:
            return f"// TODO: complex lambda: {body}"
        return f"() => {{ this.{method}({args}) }}"
    return f"// TODO: lambda: {body}"


def _res_ref(val: str) -> str:
    """
    @string/foo → $r('app.string.foo')
    @color/bar  → $r('app.color.bar')
    @drawable/x → $r('app.media.x')
    @dimen/x    → $r('app.float.x')
    @+id/x      → (id 引用，不需要转 $r)
    ?android:attr/... → 主题属性，用注释标记
    """
    if val.startswith("@{"):
        db = _databinding_expr(val)
        return db if db else val
    if val.startswith("?"):
        attr = val.lstrip("?android:attr/").lstrip("?attr/")
        return f"/* theme:{attr} */ ''"
    m = re.match(r"@\+?(\w+)/(.+)", val)
    if m:
        ns, name = m.group(1), m.group(2)
        if ns in ("id",):
            return f'"{name}"'
        if ns == "drawable" or ns == "mipmap":
            return f"$r('app.media.{name}')"
        if ns == "dimen":
            return f"$r('app.float.{name}')"
        return f"$r('app.{ns}.{name}')"
    return f'"{val}"'


def _dp(val: str) -> str:
    """16dp → 16  (鸿蒙 vp 单位数字)，16sp → 16，@dimen/x → $r(...)。"""
    if val.startswith("@") or val.startswith("?"):
        return _res_ref(val)
    if val.endswith("dp"):
        return val[:-2]
    if val.endswith("sp"):
        return val[:-2]
    if val.endswith("px"):
        return val[:-2]
    return f'"{val}"'


def _size(val: str) -> Optional[str]:
    """layout_width/height 值 → ArkTS 尺寸字符串。"""
    if val == "match_parent" or val == "fill_parent":
        return "'100%'"
    if val == "wrap_content":
        return None  # 默认，不需要显式设置
    return _dp(val)


def _build_padding(attrs: Dict[str, str]) -> Optional[str]:
    """
    合并 padding / paddingTop 等到单一的 .padding({...}) 调用。
    如果只有 padding（四边相同），用 .padding(N)。
    """
    all4 = attrs.get("android:padding", "")
    top = attrs.get("android:paddingTop", "")
    bottom = attrs.get("android:paddingBottom", "")
    left = attrs.get("android:paddingLeft", attrs.get("android:paddingStart", ""))
    right = attrs.get("android:paddingRight", attrs.get("android:paddingEnd", ""))

    if all4 and not any([top, bottom, left, right]):
        return f".padding({_dp(all4)})"
    parts = {}
    if all4:
        parts = {"top": _dp(all4), "bottom": _dp(all4), "left": _dp(all4), "right": _dp(all4)}
    if top:    parts["top"] = _dp(top)
    if bottom: parts["bottom"] = _dp(bottom)
    if left:   parts["left"] = _dp(left)
    if right:  parts["right"] = _dp(right)
    if not parts:
        return None
    inner = ", ".join(f"{k}: {v}" for k, v in parts.items())
    return f".padding({{ {inner} }})"


def _build_margin(attrs: Dict[str, str]) -> Optional[str]:
    all4 = attrs.get("android:layout_margin", "")
    top = attrs.get("android:layout_marginTop", "")
    bottom = attrs.get("android:layout_marginBottom", "")
    left = attrs.get("android:layout_marginLeft", attrs.get("android:layout_marginStart", ""))
    right = attrs.get("android:layout_marginRight", attrs.get("android:layout_marginEnd", ""))

    if all4 and not any([top, bottom, left, right]):
        return f".margin({_dp(all4)})"
    parts = {}
    if all4:
        parts = {"top": _dp(all4), "bottom": _dp(all4), "left": _dp(all4), "right": _dp(all4)}
    if top:    parts["top"] = _dp(top)
    if bottom: parts["bottom"] = _dp(bottom)
    if left:   parts["left"] = _dp(left)
    if right:  parts["right"] = _dp(right)
    if not parts:
        return None
    inner = ", ".join(f"{k}: {v}" for k, v in parts.items())
    return f".margin({{ {inner} }})"


# --------------------------------------------------------------------------- #
# 主转换类
# --------------------------------------------------------------------------- #

class LayoutTransform:
    def __init__(self, layout_map: Dict):
        self.tag_map: Dict[str, str] = layout_map.get("tag_map", {})

    def transform(self, parsed: ParsedLayout) -> str:
        struct_name = self._layout_name_to_struct(parsed.file_name)
        if parsed.root_node is None:
            body = "    Text('empty layout')"
        else:
            body = self._node_to_arkts(parsed.root_node, indent=4)
        return (
            f"@Component\n"
            f"struct {struct_name} {{\n"
            f"  build() {{\n"
            f"{body}\n"
            f"  }}\n"
            f"}}\n"
        )

    def transform_all(self, layouts: List[ParsedLayout]) -> Dict[str, str]:
        return {
            os.path.splitext(l.file_name)[0]: self.transform(l)
            for l in layouts
        }

    # ---------------------------------------------------------------------- #

    def _layout_name_to_struct(self, file_name: str) -> str:
        name = os.path.splitext(file_name)[0]
        return "".join(w.capitalize() for w in re.split(r"[_\-]", name))

    def _map_tag(self, node: LayoutNode) -> str:
        tag = node.tag
        short = tag.rsplit(".", 1)[-1]
        if short == "LinearLayout":
            return "Row" if node.orientation == "horizontal" else "Column"
        mapped = self.tag_map.get(short) or self.tag_map.get(tag)
        if mapped:
            return mapped
        # 自定义 View：取简单类名，加 TODO 注释
        return f"Column /* TODO: {short} */"

    def _is_container(self, tag: str) -> bool:
        containers = {
            "Column", "Row", "Stack", "RelativeContainer", "Scroll",
            "Flex", "List", "Grid", "Swiper", "Tabs",
            "Refresh",
        }
        return tag.split(" ")[0] in containers or "TODO" in tag

    def _node_to_arkts(self, node: LayoutNode, indent: int) -> str:
        pad = " " * indent
        arkui_tag = self._map_tag(node)
        attr_lines = self._map_attrs(node)

        has_children = bool(node.children)
        is_container = self._is_container(arkui_tag) or has_children

        if is_container:
            children_code = "\n".join(
                self._node_to_arkts(c, indent + 2) for c in node.children
            )
            open_line = f"{pad}{arkui_tag}() {{"
            close_line = f"{pad}}}"
            if attr_lines:
                close_line = f"{pad}}}\n{pad}" + f"\n{pad}".join(attr_lines)
            if children_code:
                return f"{open_line}\n{children_code}\n{close_line}"
            return f"{open_line}\n{close_line}"
        else:
            content = self._leaf_content(node)
            call = f"{pad}{arkui_tag}({content})"
            if attr_lines:
                call += "\n" + "\n".join(f"{pad}  {a}" for a in attr_lines)
            return call

    def _leaf_content(self, node: LayoutNode) -> str:
        a = node.attrs
        tag = node.tag.rsplit(".", 1)[-1]

        if tag in ("TextView",):
            text = a.get("android:text", "")
            return _res_ref(text) if text else "''"

        if tag in ("EditText", "AutoCompleteTextView", "TextInputEditText"):
            hint = a.get("android:hint", "")
            text = a.get("android:text", "")
            if hint:
                return f"{{ placeholder: {{ text: {_res_ref(hint)} }} }}"
            return _res_ref(text) if text else "''"

        if tag in ("Button", "ImageButton", "FloatingActionButton",
                   "ExtendedFloatingActionButton", "MaterialButton"):
            text = a.get("android:text", "")
            src = a.get("android:src", a.get("app:srcCompat", ""))
            if text:
                return _res_ref(text)
            if src:
                return f"{{ icon: {_res_ref(src)} }}"
            return "''"

        if tag in ("ImageView",):
            src = a.get("android:src", a.get("app:srcCompat", ""))
            return _res_ref(src) if src else "''"

        if tag in ("CheckBox",):
            text = a.get("android:text", "")
            return _res_ref(text) if text else "''"

        if tag in ("RadioButton",):
            text = a.get("android:text", "")
            return _res_ref(text) if text else "''"

        if tag in ("WebView",):
            url = a.get("android:url", a.get("app:url", ""))
            return f"{{ src: {_res_ref(url)} }}" if url else "{ src: '' }"

        return ""

    def _map_attrs(self, node: LayoutNode) -> List[str]:
        parts = []
        a = node.attrs

        # 尺寸
        w = _size(a.get("android:layout_width", ""))
        h = _size(a.get("android:layout_height", ""))
        if w:
            parts.append(f".width({w})")
        if h:
            parts.append(f".height({h})")

        # padding / margin（合并版）
        pad = _build_padding(a)
        if pad:
            parts.append(pad)
        mar = _build_margin(a)
        if mar:
            parts.append(mar)

        # 文字颜色 / 大小 / 粗细
        if "android:textColor" in a:
            parts.append(f".fontColor({_res_ref(a['android:textColor'])})")
        if "android:textSize" in a:
            parts.append(f".fontSize({_dp(a['android:textSize'])})")
        if "android:textStyle" in a:
            style = a["android:textStyle"]
            if "bold" in style:
                parts.append(".fontWeight(FontWeight.Bold)")
            if "italic" in style:
                parts.append(".fontStyle(FontStyle.Italic)")

        # 背景
        if "android:background" in a:
            val = a["android:background"]
            # DataBinding 表达式
            db = _databinding_expr(val)
            if db:
                parts.append(f".backgroundColor({db})")
            else:
                parts.append(f".backgroundColor({_res_ref(val)})")

        # 对齐（gravity）
        gravity = a.get("android:gravity", "")
        if "center" in gravity:
            parts.append(".justifyContent(FlexAlign.Center)")
            parts.append(".alignItems(HorizontalAlign.Center)")
        elif "center_horizontal" in gravity:
            parts.append(".alignItems(HorizontalAlign.Center)")
        elif "center_vertical" in gravity:
            parts.append(".justifyContent(FlexAlign.Center)")

        # visibility（DataBinding 表达式跳过，标记 TODO）
        vis = a.get("android:visibility", "")
        if vis:
            if vis.startswith("@{"):
                parts.append(f"// TODO: .visibility() bound to {vis}")
            elif vis == "gone":
                parts.append(".visibility(Visibility.None)")
            elif vis == "invisible":
                parts.append(".visibility(Visibility.Hidden)")

        # onClick
        onclick = a.get("android:onClick", "")
        if onclick:
            if onclick.startswith("@{"):
                handler = _databinding_onclick(onclick)
                if handler.startswith("//"):
                    parts.append(handler)
                else:
                    parts.append(f".onClick({handler})")
            else:
                parts.append(f".onClick(() => {{ this.{onclick}() }})")

        # app:onRefreshListener（SwipeRefreshLayout）
        refresh_listener = a.get("app:onRefreshListener", "")
        if refresh_listener:
            db = _databinding_expr(refresh_listener) if refresh_listener.startswith("@{") else None
            method = db.replace("this.", "") if db else "onRefresh"
            parts.append(f".onRefresh(() => {{ this.{method}() }})")

        # contentDescription → accessibilityText
        desc = a.get("android:contentDescription", "")
        if desc:
            parts.append(f".accessibilityText({_res_ref(desc)})")

        # maxLines
        if "android:maxLines" in a:
            parts.append(f".maxLines({a['android:maxLines']})")

        # ellipsize
        ellipsize = a.get("android:ellipsize", "")
        if ellipsize == "end":
            parts.append(".textOverflow({ overflow: TextOverflow.Ellipsis })")

        # scaleType for ImageView
        scale = a.get("android:scaleType", "")
        scale_map = {
            "centerCrop": "ImageFit.Cover",
            "fitCenter": "ImageFit.Contain",
            "fitXY": "ImageFit.Fill",
            "center": "ImageFit.None",
        }
        if scale in scale_map:
            parts.append(f".objectFit({scale_map[scale]})")

        return parts
