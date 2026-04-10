"""
Jetpack Compose (@Composable) → ArkUI (@Component) 转换。

策略：基于正则的轻量级转换，处理最常见的 80% 场景，
复杂模式生成 // TODO 注释供人工处理。

转换规则：
  @Composable fun Foo(params) { body }
    → @Component struct Foo { props; build() { body } }

  remember { mutableStateOf(x) }  →  @State var: type = x
  val x by flow.collectAsState()  →  @State x: type = default

  Text("hello")    → Text("hello")
  Column { ... }   → Column() { ... }
  Modifier.padding(8.dp).fillMaxWidth()
    → .padding(8).width('100%')
"""
import re
import os
from typing import Dict, List, Tuple, Optional


# ─────────────────────────────────────────────────────────────
# 常量 / 辅助
# ─────────────────────────────────────────────────────────────

_DP_RE = re.compile(r"(\d+(?:\.\d+)?)\.dp\b")
_SP_RE = re.compile(r"(\d+(?:\.\d+)?)\.sp\b")

# Kotlin lambda 箭头 "{ -> " 或 "{ param -> "
_LAMBDA_ARROW = re.compile(r"\{(\s*\w[\w\s,]*\s*->)")

# @Composable fun 签名
_COMPOSABLE_FUN = re.compile(
    r"@Composable\s+"
    r"(?:@\w+(?:\([^)]*\))?\s+)*"   # 其他注解
    r"(?:private\s+|internal\s+|public\s+)?"
    r"fun\s+(\w+)\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s*(?::\s*\w+\s*)?\{",
    re.DOTALL,
)

# remember { mutableStateOf(value) }
_REMEMBER_STATE = re.compile(
    r"(?:var|val)\s+(\w+)\s+by\s+remember\s*\{\s*mutableStateOf\s*\(([^)]*)\)\s*\}"
)
_REMEMBER_STATE_TYPED = re.compile(
    r"(?:var|val)\s+(\w+)\s*:\s*([\w<>?]+)\s+by\s+remember\s*\{\s*mutableStateOf\s*\(([^)]*)\)\s*\}"
)

# collectAsState
_COLLECT_AS_STATE = re.compile(
    r"(?:var|val)\s+(\w+)\s+(?:by|=)\s+(?:\w+\.)*(\w+)\.collectAsState\s*\((?:[^)]*)\)"
)

# Modifier chain: Modifier.xxx(...).yyy(...)
_MODIFIER_ASSIGN = re.compile(
    r"(?:val|var)\s+(\w+)\s*=\s*Modifier\b([^;\n]+)"
)

# stringResource(R.string.xxx) / painterResource(R.drawable.xxx)
_STRING_RES = re.compile(r"stringResource\(R\.string\.(\w+)\)")
_PAINTER_RES = re.compile(r"painterResource\(R\.drawable\.(\w+)\)")
_DRAWABLE_RES = re.compile(r"R\.drawable\.(\w+)")
_STRING_ONLY = re.compile(r"R\.string\.(\w+)")
_COLOR_RES = re.compile(r"colorResource\(R\.color\.(\w+)\)")
_DIMEN_RES = re.compile(r"dimensionResource\(R\.dimen\.(\w+)\)")

# Icons.Default/Filled/Outlined/Rounded/Sharp/TwoTone.IconName
_ICON_REF = re.compile(r"Icons\.(?:Default|Filled|Outlined|Rounded|Sharp|TwoTone)\.(\w+)")

# navController.navigate("route") / popBackStack
_NAV_NAVIGATE = re.compile(r"navController\.navigate\(([^)]+)\)")
_NAV_POP = re.compile(r"navController\.popBackStack\(\)")


# ─────────────────────────────────────────────────────────────
# Modifier 链转换
# ─────────────────────────────────────────────────────────────

def _convert_dp(s: str) -> str:
    s = _DP_RE.sub(lambda m: m.group(1), s)
    s = _SP_RE.sub(lambda m: m.group(1), s)
    return s


def _convert_modifier_chain(chain: str, modifier_map: Dict[str, str]) -> str:
    """
    将 Modifier.padding(8.dp).fillMaxWidth() 之类的链
    转换为 .padding(8).width('100%')。
    """
    chain = chain.strip()
    # 去掉开头的 Modifier
    chain = re.sub(r"^\s*Modifier\b\.?", "", chain)
    if not chain.strip():
        return ""

    result_parts = []
    # 逐个匹配 .methodName(args)
    pattern = re.compile(r"\.(\w+)\s*(\([^)]*(?:\([^)]*\)[^)]*)*\))?")
    for m in pattern.finditer(chain):
        method = m.group(1)
        args_raw = m.group(2) or "()"
        args = args_raw[1:-1].strip()  # 去掉外层括号
        args = _convert_dp(args)

        if method not in modifier_map:
            result_parts.append(f"/* TODO Modifier.{method}({args}) */")
            continue

        template = modifier_map[method]
        if not template:
            continue  # 空字符串 = 无对应，静默跳过

        # 替换模板变量
        out = template.replace("${args}", args)
        # offset 特殊处理 x/y
        if "${x}" in out or "${y}" in out:
            xy = [a.strip() for a in args.split(",")]
            out = out.replace("${x}", xy[0] if len(xy) > 0 else "0")
            out = out.replace("${y}", xy[1] if len(xy) > 1 else "0")

        result_parts.append(out)

    return "".join(result_parts)


# ─────────────────────────────────────────────────────────────
# 资源引用转换
# ─────────────────────────────────────────────────────────────

def _convert_resource_refs(code: str) -> str:
    code = _STRING_RES.sub(lambda m: f"$r('app.string.{m.group(1)}')", code)
    code = _PAINTER_RES.sub(lambda m: f"$r('app.media.{m.group(1)}')", code)
    code = _COLOR_RES.sub(lambda m: f"$r('app.color.{m.group(1)}')", code)
    code = _DIMEN_RES.sub(lambda m: f"$r('app.float.{m.group(1)}')", code)
    code = _DRAWABLE_RES.sub(lambda m: f"$r('app.media.{m.group(1)}')", code)
    code = _STRING_ONLY.sub(lambda m: f"$r('app.string.{m.group(1)}')", code)
    # Icons → media ref
    code = _ICON_REF.sub(
        lambda m: f"$r('app.media.ic_{_camel_to_snake(m.group(1))}')", code
    )
    return code


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ─────────────────────────────────────────────────────────────
# 导航转换
# ─────────────────────────────────────────────────────────────

def _convert_navigation(code: str) -> str:
    code = _NAV_NAVIGATE.sub(
        lambda m: f"router.pushUrl({{ url: {m.group(1)} }})", code
    )
    code = _NAV_POP.sub("router.back()", code)
    return code


# ─────────────────────────────────────────────────────────────
# 参数类型推断
# ─────────────────────────────────────────────────────────────

_TYPE_MAP = {
    "String": "string", "Int": "number", "Long": "number",
    "Float": "number", "Double": "number", "Boolean": "boolean",
    "Unit": "void", "List": "Array", "Map": "Map",
    "MutableList": "Array", "MutableMap": "Map",
    "MutableState": "any", "State": "any",
    "Flow": "any", "StateFlow": "any", "SharedFlow": "any",
}

_FUNC_TYPE_RE = re.compile(r"\(([^)]*)\)\s*->\s*(\w+)")


def _kt_type_to_ts(kt_type: str) -> str:
    kt_type = kt_type.strip()
    if not kt_type:
        return "any"
    m = _FUNC_TYPE_RE.match(kt_type)
    if m:
        params = m.group(1)
        ret = _kt_type_to_ts(m.group(2))
        if params.strip():
            p_types = ", ".join(_kt_type_to_ts(p.strip()) for p in params.split(","))
            return f"({p_types}) => {ret}"
        return f"() => {ret}"
    # 泛型
    generic_m = re.match(r"(\w+)<(.+)>", kt_type)
    if generic_m:
        outer = _TYPE_MAP.get(generic_m.group(1), generic_m.group(1))
        inner = _kt_type_to_ts(generic_m.group(2))
        return f"{outer}<{inner}>"
    # nullable
    if kt_type.endswith("?"):
        return _kt_type_to_ts(kt_type[:-1]) + " | null"
    return _TYPE_MAP.get(kt_type, kt_type)


def _default_for_type(ts_type: str) -> str:
    defaults = {
        "string": "''", "number": "0", "boolean": "false",
        "void": "undefined",
    }
    if ts_type in defaults:
        return defaults[ts_type]
    if ts_type.startswith("("):
        return "() => {}"
    if ts_type.startswith("Array"):
        return "[]"
    return f"new {ts_type}()"


def _split_params(params_str: str) -> List[str]:
    """
    按顶层逗号切分参数列表。
    只追踪圆括号深度（`()`），忽略尖括号——避免 '->' 中的 '>'
    被错误计为闭括号。
    泛型参数（如 List<String>）中的逗号不应出现在顶层，实践中可行。
    """
    parts = []
    depth = 0
    current = []
    i = 0
    s = params_str
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _parse_params(params_str: str) -> List[Tuple[str, str, str]]:
    """
    解析 Kotlin 参数列表，返回 [(name, ts_type, default_val), ...]。
    跳过 modifier: Modifier、navController 等辅助参数。
    """
    SKIP_NAMES = {"modifier", "navController", "viewModel", "scope", "context"}
    SKIP_TYPES = {"Modifier", "NavController", "NavHostController",
                  "CoroutineScope", "Context", "LifecycleOwner"}
    result = []
    for param in _split_params(params_str):
        param = param.strip()
        if not param:
            continue
        # 去掉注解
        param = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", param).strip()

        # name: Type = default
        m = re.match(r"(\w+)\s*:\s*(.+)", param, re.DOTALL)
        if not m:
            continue
        name = m.group(1).strip()
        rest = m.group(2).strip()

        # 找到 "= defaultValue" —— 在类型之外（深度为0）的 "="
        type_part, default_val = _split_type_default(rest)

        if name in SKIP_NAMES:
            continue
        base_type = type_part.rstrip("?").strip()
        # 跳过 Modifier 等工具类型（只匹配最外层类名）
        outer_type = base_type.split("<")[0].strip()
        if outer_type in SKIP_TYPES:
            continue

        ts_type = _kt_type_to_ts(type_part.strip())
        if not default_val:
            default_val = _default_for_type(ts_type)

        result.append((name, ts_type, default_val))
    return result


def _split_type_default(rest: str) -> Tuple[str, str]:
    """从 'TypeName = defaultValue' 中分离类型和默认值。"""
    depth = 0
    for i, ch in enumerate(rest):
        if ch in "(<":
            depth += 1
        elif ch in ")>":
            depth -= 1
        elif ch == "=" and depth == 0:
            return rest[:i].strip(), rest[i+1:].strip()
    return rest.strip(), ""


# ─────────────────────────────────────────────────────────────
# 组件体转换
# ─────────────────────────────────────────────────────────────

_SCAFFOLD_NAMED_PARAMS = {
    "topBar", "bottomBar", "floatingActionButton", "drawerContent",
    "snackbarHost", "navigationIcon", "actions",
}


def _strip_scaffold_named_params_one(body: str, param: str) -> str:
    """替换 body 中第一个 'param = { ... }' 具名 lambda 为 TODO 注释。"""
    pat = re.compile(rf"\b{param}\s*=\s*\{{")
    m = pat.search(body)
    if not m:
        return body
    start = m.end() - 1  # '{' 位置
    depth = 0
    i = start
    while i < len(body):
        c = body[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                # 跳过尾随逗号
                j = end
                while j < len(body) and body[j] in ' \t':
                    j += 1
                if j < len(body) and body[j] == ',':
                    end = j + 1
                return (body[:m.start()]
                        + f"// TODO: {param} slot — add manually\n"
                        + body[end:])
        i += 1
    return body


def _strip_scaffold_named_params(body: str) -> str:
    """
    将 Scaffold / TopAppBar 等组件的具名 lambda 参数（topBar = { ... }）
    替换为 TODO 注释，因为 ArkUI 没有直接对应槽位。
    """
    for param in _SCAFFOLD_NAMED_PARAMS:
        for _ in range(20):  # 最多处理同一文件内 20 个同名槽位
            new_body = _strip_scaffold_named_params_one(body, param)
            if new_body == body:
                break
            body = new_body
    return body


def _convert_body(body: str, composable_map: Dict[str, str],
                  modifier_map: Dict[str, str]) -> str:
    """对函数体做逐行/逐模式转换。"""
    # 0. 合并多行 Modifier 链
    body = _join_multiline_modifiers(body)

    # 1. dp/sp 单位
    body = _convert_dp(body)

    # 2. 资源引用
    body = _convert_resource_refs(body)

    # 3. 导航
    body = _convert_navigation(body)

    # 4. remember { mutableStateOf() }
    body = _REMEMBER_STATE_TYPED.sub(
        lambda m: f"@State {m.group(1)}: {_kt_type_to_ts(m.group(2))} = {m.group(3)}",
        body,
    )
    body = _REMEMBER_STATE.sub(
        lambda m: f"@State {m.group(1)}: any = {m.group(2)}", body
    )

    # 5. collectAsState
    body = _COLLECT_AS_STATE.sub(
        lambda m: f"@State {m.group(1)}: any = null /* observe {m.group(2)} */",
        body,
    )

    # 6. Modifier 赋值变量
    body = _MODIFIER_ASSIGN.sub(
        lambda m: f"// modifier {m.group(1)}: {_convert_modifier_chain(m.group(2), modifier_map)}",
        body,
    )

    # 7. Modifier 内联参数（composable 调用里的 modifier = Modifier.xxx）
    # 使用支持一层嵌套括号的正则，避免 fillMaxSize() 中的 ')' 截断捕获
    def _inline_modifier(m):
        chain = m.group(1)
        converted = _convert_modifier_chain(chain, modifier_map)
        return f"/* modifier: {converted} */"

    body = re.sub(
        r"modifier\s*=\s*(Modifier\b(?:[^,)\n(]|\([^)]*\))+)",
        _inline_modifier,
        body,
    )

    # 8. 内联 Modifier 链（不带 "modifier =" 前缀的裸 Modifier.xxx）
    def _replace_inline_modifier(m):
        chain = m.group(0)
        converted = _convert_modifier_chain(chain, modifier_map)
        return converted if converted else "/* Modifier */"

    body = re.sub(
        r"\bModifier\b(?:\.\w+\s*(?:\([^)]*(?:\([^)]*\)[^)]*)*\))?)+",
        _replace_inline_modifier,
        body,
    )

    # 8b. Scaffold 具名参数提取（topBar / floatingActionButton 等 → TODO 注释）
    body = _strip_scaffold_named_params(body)

    # 9. Composable 调用 → ArkUI 组件（行级替换）
    for kt_name, ark_name in composable_map.items():
        # 替换独立出现的函数名（后跟括号或大括号）
        body = re.sub(
            rf"\b{re.escape(kt_name)}\s*(?=\(|\{{)",
            ark_name + " ",
            body,
        )

    # 10a. LazyColumn items/itemsIndexed → ForEach（必须在 lambda 箭头清理之前，以捕获参数名）
    body = re.sub(
        r"items\s*\(\s*([\w.]+)\s*\)\s*\{\s*(?:(\w+)\s*->\s*)?",
        lambda m: f"ForEach({m.group(1)}, ({m.group(2) or 'item'}) => {{",
        body,
    )
    body = re.sub(
        r"itemsIndexed\s*\(\s*([\w.]+)\s*\)\s*\{\s*(?:(?:index\s*,\s*)?(\w+)\s*->\s*)?",
        lambda m: f"ForEach({m.group(1)}, ({m.group(2) or 'item'}, index) => {{",
        body,
    )

    # 10b. Kotlin lambda 箭头清理：{ param -> body } → { body }
    body = re.sub(r"\{\s*\w+\s*->\s*", "{ ", body)
    body = re.sub(r"\{\s*\w+\s*,\s*\w+\s*->\s*", "{ ", body)

    # 10c. onClick = { block } → .onClick(() => { block })
    body = re.sub(
        r"onClick\s*=\s*\{([^}]*)\}",
        lambda m: f".onClick(() => {{{m.group(1)}}})",
        body,
    )
    # onValueChange = { v -> handler }（仅适用于 TextInput 等原生组件）
    body = re.sub(
        r"onValueChange\s*=\s*\{([^}]*)\}",
        lambda m: f".onChange((value: string) => {{{m.group(1)}}})",
        body,
    )
    # onCheckedChange = { v -> handler }
    # 原生 Checkbox/Switch：转为 .onChange；自定义组件传参：保留为回调属性
    body = re.sub(
        r"onCheckedChange\s*=\s*\{([^}]*)\}",
        lambda m: f".onChange((isOn: boolean) => {{{m.group(1)}}})",
        body,
    )

    # 11. text = "..." / text = variable → 保留为第一个参数（简化处理）
    body = re.sub(r"text\s*=\s*\"([^\"]*)\"", r'"\1"', body)

    # 12. if (condition) { ... } else { ... } → 保持（ArkTS 支持）

    # 14. Color 常量
    body = re.sub(r"\bColor\.(\w+)\b", lambda m: _COLOR_CONST.get(m.group(1), f"'#{m.group(1)}'"), body)

    # 15. fontWeight = FontWeight.Bold → fontWeight: FontWeight.Bold
    body = re.sub(r"fontWeight\s*=\s*FontWeight\.Bold", "fontWeight: FontWeight.Bold", body)
    body = re.sub(r"fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp", r"fontSize: \1", body)
    body = re.sub(r"fontSize\s*=\s*(\d+(?:\.\d+)?)", r"fontSize: \1", body)

    # 16. Alignment / Arrangement
    body = body.replace("Arrangement.Center", "FlexAlign.Center")
    body = body.replace("Arrangement.Start", "FlexAlign.Start")
    body = body.replace("Arrangement.End", "FlexAlign.End")
    body = body.replace("Arrangement.SpaceBetween", "FlexAlign.SpaceBetween")
    body = body.replace("Arrangement.SpaceAround", "FlexAlign.SpaceAround")
    body = body.replace("Arrangement.SpaceEvenly", "FlexAlign.SpaceEvenly")
    body = body.replace("Alignment.CenterHorizontally", "HorizontalAlign.Center")
    body = body.replace("Alignment.CenterVertically", "VerticalAlign.Center")
    body = body.replace("Alignment.Center", "Alignment.Center")
    body = body.replace("Alignment.Start", "HorizontalAlign.Start")
    body = body.replace("Alignment.End", "HorizontalAlign.End")
    body = body.replace("Alignment.Top", "VerticalAlign.Top")
    body = body.replace("Alignment.Bottom", "VerticalAlign.Bottom")

    # 17. ContentScale
    body = body.replace("ContentScale.Crop", "ImageFit.Cover")
    body = body.replace("ContentScale.Fit", "ImageFit.Contain")
    body = body.replace("ContentScale.FillBounds", "ImageFit.Fill")

    return body


_COLOR_CONST = {
    "Red": "#FF0000", "Green": "#00FF00", "Blue": "#0000FF",
    "White": "#FFFFFF", "Black": "#000000", "Gray": "#888888",
    "Grey": "#888888", "Yellow": "#FFFF00", "Cyan": "#00FFFF",
    "Magenta": "#FF00FF", "Transparent": "#00000000",
}


def _join_multiline_modifiers(body: str) -> str:
    """
    将多行 Modifier 链合并为单行，例如：
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    → modifier = Modifier.fillMaxWidth().padding(16.dp)
    """
    lines = body.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 只要当前行含有 Modifier 且下一行以 '.' 开头，就合并
        while (i + 1 < len(lines)
               and 'Modifier' in line
               and re.match(r'\s*\.\w+', lines[i + 1])):
            line = line.rstrip() + lines[i + 1].strip()
            i += 1
        result.append(line)
        i += 1
    return '\n'.join(result)


def _extract_state_declarations(body: str) -> Tuple[List[str], str]:
    """
    从 body 中提取 @State xxx 行，返回 (state_lines, remaining_body)。
    """
    state_lines = []
    remaining = []
    for line in body.splitlines():
        if line.strip().startswith("@State "):
            state_lines.append(line.strip())
        else:
            remaining.append(line)
    return state_lines, "\n".join(remaining)


# ─────────────────────────────────────────────────────────────
# 主转换器
# ─────────────────────────────────────────────────────────────

class ComposeTransform:

    def __init__(self, compose_map: Dict):
        self.composable_map: Dict[str, str] = compose_map.get("composables", {})
        self.modifier_map: Dict[str, str] = compose_map.get("modifiers", {})

    def is_compose_file(self, content: str) -> bool:
        """判断文件是否使用 Jetpack Compose。"""
        return (
            "androidx.compose" in content
            or "@Composable" in content
            or "import androidx.compose" in content
        )

    def transform_file(self, content: str, file_name: str = "") -> str:
        """
        转换单个 Compose 文件为 ArkTS。
        返回转换后的 ArkTS 代码。
        """
        if not self.is_compose_file(content):
            return content

        lines = [
            f"// Auto-converted from Compose: {file_name}",
            "// TODO: Review this file — Compose → ArkUI conversion is approximate",
            "",
        ]

        # 收集 import（用于推断依赖）
        imports = re.findall(r"^import\s+([\w.]+)", content, re.MULTILINE)

        # 生成 ArkTS imports
        lines += self._gen_imports(imports)
        lines.append("")

        # 提取并转换所有 @Composable 函数
        converted_fns = self._extract_and_convert_composables(content)

        if not converted_fns:
            lines.append("// TODO: No @Composable functions detected — manual conversion needed")
        else:
            for fn_code in converted_fns:
                lines.append(fn_code)
                lines.append("")

        return "\n".join(lines)

    def transform_all(self, sources: Dict[str, str]) -> Dict[str, str]:
        """
        批量转换。sources: {file_path: content}
        返回 {file_path: converted_content}（只处理 Compose 文件）。
        """
        result = {}
        for path, content in sources.items():
            if self.is_compose_file(content):
                fname = os.path.basename(path)
                result[path] = self.transform_file(content, fname)
        return result

    # ------------------------------------------------------------------ #

    def _gen_imports(self, kotlin_imports: List[str]) -> List[str]:
        lines = []
        if any("navigation" in i for i in kotlin_imports):
            lines.append("import router from '@ohos.router'")
        if any("viewmodel" in i.lower() for i in kotlin_imports):
            lines.append("// ViewModel imports handled by ViewModelTransform")
        return lines

    def _extract_and_convert_composables(self, content: str) -> List[str]:
        """提取所有 @Composable 函数并转换为 @Component struct。"""
        results = []

        for m in _COMPOSABLE_FUN.finditer(content):
            fn_name = m.group(1)
            params_str = m.group(2)
            start = m.start()
            body_start = m.end()

            # 找到对应的闭合大括号
            body_end = self._find_closing_brace(content, body_start - 1)
            if body_end < 0:
                continue

            body = content[body_start:body_end].strip()

            # 跳过 NavHost / Navigation composable（由 NavigationTransform 处理）
            if fn_name in ("NavHost", "AppNavigation", "Navigation"):
                results.append(f"// TODO: NavHost '{fn_name}' → RouterConfig.ets (see NavigationTransform)")
                continue

            params = _parse_params(params_str)
            struct_code = self._gen_struct(fn_name, params, body)
            results.append(struct_code)

        return results

    def _gen_struct(self, name: str, params: List[Tuple[str, str, str]], body: str) -> str:
        """生成 @Component struct。"""
        lines = []

        # 判断是否是顶层 Screen（是否需要 @Entry）
        is_screen = name.endswith("Screen") or name.endswith("Page") or name.endswith("View")
        if is_screen:
            lines.append("@Entry")
        lines.append("@Component")
        lines.append(f"struct {name} {{")

        # 属性声明（来自函数参数）
        for pname, ptype, pdefault in params:
            lines.append(f"  {pname}: {ptype} = {pdefault}")

        # 转换 body（先做语义转换）
        converted_body = _convert_body(body, self.composable_map, self.modifier_map)

        # 从 body 中提取 @State 声明，移到 struct 属性区
        state_lines, build_body = _extract_state_declarations(converted_body)
        for sl in state_lines:
            lines.append(f"  {sl}")

        lines.append("")
        lines.append("  build() {")

        # 缩进 build body
        for line in build_body.splitlines():
            if line.strip():
                lines.append(f"    {line}")
            else:
                lines.append("")

        lines.append("  }")
        lines.append("}")

        return "\n".join(lines)

    def _find_closing_brace(self, content: str, open_pos: int) -> int:
        """从 open_pos（'{'的位置）找到匹配的 '}'，返回其位置。"""
        depth = 0
        in_string = False
        string_char = ""
        i = open_pos
        while i < len(content):
            c = content[i]
            if in_string:
                if c == "\\" and i + 1 < len(content):
                    i += 2
                    continue
                if c == string_char:
                    in_string = False
            else:
                if c in ('"', "'"):
                    in_string = True
                    string_char = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return i
            i += 1
        return -1
