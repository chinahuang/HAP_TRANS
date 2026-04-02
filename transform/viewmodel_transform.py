"""
LiveData / ViewModel → ArkTS @ObservedV2 / @Trace 状态管理转换。

策略：
  - MutableLiveData<T> → @Trace field: T
  - LiveData<T>（只读）→ 只读 getter（或同样 @Trace）
  - viewModelScope.launch → async 函数
  - ViewModel 类 → 普通 class，配合 @ObservedV2
  - coroutines → async/await
"""
import re
from typing import List, Dict, Optional
from parser.kotlin_parser import SourceClass


_NESTED_TYPE = r'(?:[^<>]|<[^<>]*>)*'   # matches type with one level of nested <>

RE_MUTABLE_LIVE = re.compile(
    rf'private\s+val\s+(_\w+)\s*=\s*MutableLiveData<({_NESTED_TYPE})>\s*\(([^)]*)\)'
)
# public val (no underscore) e.g. val title = MutableLiveData<String>()
RE_PUBLIC_MUTABLE_LIVE = re.compile(
    rf'^\s+val\s+(\w+)\s*=\s*MutableLiveData<({_NESTED_TYPE})>\s*\(\s*\)',
    re.MULTILINE,
)
# private val without underscore (e.g. private val isDataLoadingError = MutableLiveData<Boolean>())
RE_MUTABLE_LIVE_NO_PFX = re.compile(
    rf'private\s+val\s+([a-z]\w+)\s*=\s*MutableLiveData<({_NESTED_TYPE})>\s*\(([^)]*)\)'
)
# private var state fields: private var isNewTask: Boolean = false
RE_PRIVATE_STATE = re.compile(
    r'private\s+var\s+(\w+)\s*(?::\s*([\w?]+))?\s*=\s*([^\n/]+)'
)
RE_LIVE_EXPOSED = re.compile(
    rf'val\s+(\w+):\s*LiveData<({_NESTED_TYPE})>\s*=\s*(_\w+)'
)
RE_LIVE_ONLY = re.compile(
    rf'private\s+val\s+(_\w+):\s*LiveData<({_NESTED_TYPE})>'
)
RE_VIEWMODEL_SCOPE = re.compile(
    r'viewModelScope\.launch\s*\{([^}]+)\}', re.DOTALL
)
RE_COROUTINE_SUSPEND = re.compile(
    r'suspend\s+fun\s+(\w+)\s*\(([^)]*)\)'
)
RE_CLASS_DECL = re.compile(
    r'class\s+(\w+)\s*\(([^)]*)\)\s*:\s*ViewModel\(\)'
)


def _default_val(kt_type: str, init: str) -> str:
    kt_type = kt_type.strip()
    init = init.strip()
    if init:
        if init.startswith("false"): return "false"
        if init.startswith("true"):  return "true"
        if re.match(r'^\d', init):   return init
        if init.startswith('"'):     return init
    if kt_type == "Boolean":    return "false"
    if kt_type in ("Int", "Long", "Double", "Float"): return "0"
    if kt_type == "String":     return "''"
    if kt_type.startswith("List"): return "[]"
    return "null"


def _kt_type_to_arkts(kt_type: str) -> str:
    kt_type = kt_type.strip().rstrip("?")
    mapping = {
        "Boolean": "boolean",
        "String": "string",
        "Int": "number",
        "Long": "number",
        "Float": "number",
        "Double": "number",
        "List": "Array",
    }
    # List<Task> → Array<Task>
    for k, v in mapping.items():
        if kt_type == k:
            return v
        kt_type = re.sub(rf'\b{k}\b', v, kt_type)
    return kt_type


class ViewModelTransform:

    def transform(self, sc: SourceClass) -> str:
        code = sc.raw_content

        # 1. 收集 MutableLiveData 字段，建立 private→public 映射
        private_to_public: Dict[str, str] = {}
        field_types: Dict[str, str] = {}
        trace_fields: List[str] = []
        seen_field_names: set = set()

        def _add_trace_field(name: str, ktype: str, init: str = ''):
            if name in seen_field_names:
                return
            seen_field_names.add(name)
            # Strip Event<T> wrapper → string | null (events are one-time triggers)
            if re.search(r'\bEvent\b', ktype):
                trace_fields.append(f"  @Trace {name}: string | null = null;")
                return
            # Handle nullable Kotlin types: Type?
            nullable = ktype.endswith('?')
            ktype_clean = ktype.rstrip('?')
            atype = _kt_type_to_arkts(ktype_clean)
            # Map Unit → use Object | null
            if atype in ('Unit', 'void'):
                trace_fields.append(f"  @Trace {name}: Object | null = null;")
                return
            dval = _default_val(ktype_clean, init)
            # If type is nullable or default is null, mark the type as nullable
            if nullable or init.strip() == 'null' or dval == 'null':
                if '| null' not in atype:
                    atype += ' | null'
                dval = 'null'
            field_types[name] = atype
            trace_fields.append(f"  @Trace {name}: {atype} = {dval};")

        # private val _xxx = MutableLiveData<Type>(init)  — standard pattern
        for m in RE_MUTABLE_LIVE.finditer(code):
            priv = m.group(1)       # _items
            pub_name = priv.lstrip('_')
            ktype = m.group(2)
            init = m.group(3)
            _add_trace_field(pub_name, ktype, init)

        # private val xxx = MutableLiveData<Type>(init)  — no underscore prefix
        for m in RE_MUTABLE_LIVE_NO_PFX.finditer(code):
            name = m.group(1)
            ktype = m.group(2)
            init = m.group(3) if m.lastindex >= 3 else ''
            _add_trace_field(name, ktype, init)

        # val xxx = MutableLiveData<Type>()  — public directly-exposed
        for m in RE_PUBLIC_MUTABLE_LIVE.finditer(code):
            name = m.group(1)
            ktype = m.group(2)
            _add_trace_field(name, ktype, '')

        # private var xxx: Type = init  — simple state fields
        for m in RE_PRIVATE_STATE.finditer(code):
            name = m.group(1)
            ktype = m.group(2) or ''
            init = m.group(3).strip().rstrip(';')
            # Skip Android-specific types or constructor-related things
            if any(t in (ktype or init) for t in ('Repository', 'Handle', 'Dispatcher')):
                continue
            if not ktype:
                # Infer type from init value
                if init in ('true', 'false'):
                    ktype = 'Boolean'
                elif re.match(r'^-?\d+$', init):
                    ktype = 'Int'
                elif init.startswith('"'):
                    ktype = 'String'
                else:
                    ktype = 'Object'
            _add_trace_field(name, ktype, init)

        for m in RE_LIVE_EXPOSED.finditer(code):
            pub = m.group(1)    # items
            priv = m.group(3)   # _items
            private_to_public[priv] = pub

        # 2. 类名和构造参数
        class_m = RE_CLASS_DECL.search(code)
        class_name = sc.class_name
        ctor_params = ""
        if class_m:
            # 清理 private/val/var 修饰符，简化构造参数
            params_raw = class_m.group(2)
            params_raw = re.sub(r'private\s+val\s+', '', params_raw)
            params_raw = re.sub(r'private\s+var\s+', '', params_raw)
            params_raw = re.sub(r'SavedStateHandle', 'Map<string, Object>', params_raw)
            ctor_params = params_raw.strip()

        # 3. 转换方法体
        body = self._transform_body(code)

        fields_code = "\n".join(trace_fields) or "  // No LiveData fields detected"

        # Generate private field declarations and constructor body for ctor params
        ctor_field_decls = []
        ctor_assignments = []
        ctor_param_names: list = []
        if ctor_params:
            for param in self._split_params(ctor_params):
                param = param.strip()
                if not param:
                    continue
                m_param = re.match(r'(\w+)\s*:\s*(.+)', param)
                if m_param:
                    pname, ptype = m_param.group(1).strip(), m_param.group(2).strip()
                    ctor_field_decls.append(f"  private {pname}: {ptype};")
                    ctor_assignments.append(f"    this.{pname} = {pname};")
                    ctor_param_names.append(pname)

        ctor_fields_str = ("\n" + "\n".join(ctor_field_decls) + "\n") if ctor_field_decls else ""
        ctor_body = "\n".join(ctor_assignments) if ctor_assignments else "    // TODO: initialize"

        result = f"""\
// AUTO-CONVERTED: ViewModel → ArkTS @ObservedV2 class
// TODO: Inject dependencies manually (no Hilt in HarmonyOS)
import {{ TasksRepository }} from '../common/TasksRepository';
import {{ Task }} from '../common/Task';
import {{ Result, Success, ResultError }} from '../common/Result';

@ObservedV2
export class {class_name} {{{ctor_fields_str}
{fields_code}

  constructor({ctor_params}) {{
{ctor_body}
  }}

{body}
}}
"""
        # Post-process: add this. prefix to field/method references
        # Use re.search (not match) since trace_fields strings have leading spaces
        trace_names = []
        for f in trace_fields:
            _m = re.search(r'@Trace\s+(\w+)\s*:', f)
            if _m:
                trace_names.append(_m.group(1))
        all_field_names = set(ctor_param_names) | set(trace_names)
        # Also collect method names (from async method( declarations)
        _SKIP_METHODS = frozenset(('constructor', 'if', 'for', 'while', 'switch', 'catch',
                                   'get', 'set', 'new', 'return', 'throw', 'class'))
        method_names = set()
        for mm in re.finditer(r'^\s+async\s+(\w+)\s*\(', result, re.MULTILINE):
            nm = mm.group(1)
            if nm not in _SKIP_METHODS:
                method_names.add(nm)
        result = self._add_this_prefix(result, all_field_names, method_names)
        return result

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        return {
            sc.file_path: self.transform(sc)
            for sc in classes if sc.is_viewmodel
        }

    def _split_params(self, params_raw: str) -> list:
        """Split param list by comma, respecting < > angle bracket nesting."""
        params = []
        depth = 0
        current = []
        for ch in params_raw:
            if ch in '<(':
                depth += 1
            elif ch in '>)':
                depth -= 1
            if ch == ',' and depth == 0:
                params.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            params.append(''.join(current).strip())
        return params

    def _add_this_prefix(self, code: str, field_names: set, method_names: set = None) -> str:
        """Add this. prefix to bare field accesses and method calls in generated ViewModel code."""
        # Fix field references (skip declaration and constructor param lines)
        for fname in field_names:
            result_lines = []
            for line in code.split('\n'):
                stripped = line.lstrip()
                is_field_decl = bool(re.match(
                    rf'(?:private|public|protected|@\w+)\s+{re.escape(fname)}\s*:',
                    stripped
                ))
                is_ctor_param = bool(re.search(
                    rf'\bconstructor\s*\([^)]*{re.escape(fname)}\s*:', line
                ))
                # Skip local const/let/var declarations that shadow field names
                is_local_decl = bool(re.match(
                    rf'\s*(?:const|let|var)\s+{re.escape(fname)}\s*[=:]',
                    line,
                ))
                if not is_field_decl and not is_ctor_param and not is_local_decl:
                    line = re.sub(
                        rf'(?<![.\w]){re.escape(fname)}\b(?!\s*:)',
                        f'this.{fname}',
                        line,
                    )
                    line = line.replace(f'this.this.{fname}', f'this.{fname}')
                result_lines.append(line)
            code = '\n'.join(result_lines)
            # Fix self-assignment: this.fname = this.fname → this.fname = fname
            code = re.sub(
                rf'(this\.{re.escape(fname)}\s*=\s*)this\.{re.escape(fname)}\b',
                rf'\g<1>{fname}',
                code,
            )
        # Fix method calls (use lookbehind to skip 'async name(' declaration lines)
        if method_names:
            for mname in method_names:
                # Skip if preceded by 'async ' (declaration line)
                code = re.sub(
                    rf'(?<![.\w])(?<!async ){re.escape(mname)}\s*\(',
                    f'this.{mname}(',
                    code,
                )
                code = code.replace(f'this.this.{mname}', f'this.{mname}')
        return code

    # ---------------------------------------------------------------------- #

    def _transform_body(self, code: str) -> str:
        """预处理整个文件代码，再提取方法。"""
        body = code

        # LiveData value 赋值：_items.value = x → this.items = x
        body = re.sub(r'_(\w+)\.value\s*=', lambda m: f"this.{m.group(1)} =", body)
        body = re.sub(r'_(\w+)\.postValue\(', lambda m: f"this.{m.group(1)} = (", body)
        # Public MutableLiveData: title.value = x → title = x (underscore-free fields)
        body = re.sub(r'\b(\w+)\.value\s*=', r'\1 =', body)
        # Reading .value: title.value → title
        body = re.sub(r'\b(\w+)\.value\b', r'\1', body)
        # Strip _ prefix from private LiveData references: _task → task, _taskId → taskId
        body = re.sub(r'(?<![.\w])_(\w+)\b', r'\1', body)

        # CRITICAL: handle expression-body functions BEFORE IIFE replacement
        # 表达式体函数：fun foo(...) = viewModelScope.launch { ... }
        body = re.sub(
            r'\bfun\s+(\w+)\s*(\([^)]*\))\s*=\s*viewModelScope\.launch\s*\{',
            r'fun \1\2 {',
            body,
        )
        # 通用表达式体：fun foo() = expr  →  fun foo() { return expr }
        # （仅处理单行，不含 { 的情况）
        body = re.sub(
            r'\bfun\s+(\w+\s*\([^)]*\)[^{=\n]*)\s*=\s*(?!\s*\{)([^\n]+)',
            r'fun \1 { return \2 }',
            body,
        )

        # viewModelScope.launch { ... } → inline body (methods are already async)
        def replace_launch(m):
            inner = m.group(1).strip()
            # Add await to repository method calls in the captured body
            inner = re.sub(r'\b(\w+Repository\.\w+)\(', r'await \1(', inner)
            return inner  # No IIFE wrapper — calling method is already async
        body = RE_VIEWMODEL_SCOPE.sub(replace_launch, body)

        # suspend fun → async fun
        body = re.sub(r'\bsuspend\s+fun\b', 'async fun', body)

        # withContext → 去掉
        body = re.sub(r'withContext\(Dispatchers\.\w+\)\s*\{', '{', body)

        # observe → TODO
        body = re.sub(r'\.observe\(viewLifecycleOwner,\s*\{', '// TODO: @Watch\n      // {', body)

        methods = self._extract_methods(body)
        if not methods:
            return "  // TODO: manually migrate methods from original ViewModel"
        return "\n\n".join(f"  {m}" for m in methods)

    def _extract_methods(self, code: str) -> List[str]:
        results = []
        for m in re.finditer(r'\bfun\s+(\w+)\s*\(([^)]*)\)[^{]*\{', code):
            start = m.start()
            depth = 0
            end = start
            for i in range(m.end() - 1, len(code)):
                if code[i] == '{': depth += 1
                elif code[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            func_code = code[start:end].strip()
            func_code = self._clean_method(func_code)
            results.append(func_code)
        return results

    def _clean_method(self, code: str) -> str:
        """对单个方法体做 Kotlin → ArkTS 语法清理。"""
        # 1. 去掉方法级注解行（@StringRes、@DrawableRes 等）
        code = re.sub(r'^\s*@\w+(?:\([^)]*\))?\s*$', '', code, flags=re.MULTILINE)

        # 2. 参数列表里的注解：@StringRes x: Int → x: number
        code = re.sub(r'@\w+\s+(\w+\s*:)', r'\1', code)

        # 3. 类型映射（参数和变量声明）
        for kt, ts in [("Int", "number"), ("Long", "number"), ("Float", "number"),
                       ("Double", "number"), ("Boolean", "boolean"), ("String", "string"),
                       ("Unit", "void"), ("Any", "Object")]:
            code = re.sub(rf':\s*{kt}\b', f': {ts}', code)

        # 4. override fun → async
        code = re.sub(r'\boverride\s+', '', code)
        code = re.sub(r'\bfun\s+', 'async ', code)

        # return@label → return
        code = re.sub(r'\breturn@\w+\b', 'return', code)

        # Add await to repository method calls (this.tasksRepository.x() etc.)
        code = re.sub(r'\b(this\.\w*[Rr]epository\.\w+)\(', r'await \1(', code)
        code = re.sub(r'\b(\w+Repository\.\w+)\(', r'await \1(', code)

        # x?.let { body } → if (x != null) { const it = x; body }
        # Simple single-line form: x?.let { expr }
        code = re.sub(
            r'(\w[\w.]*)\?\.let\s*\{\s*([^}]+)\}',
            lambda m: f"if ({m.group(1)} != null) {{ const it = {m.group(1)}; {m.group(2).strip()} }}",
            code,
        )
        # x.let { y -> body } (without ?)
        code = re.sub(
            r'(\w[\w.]*?)\.let\s*\{\s*(\w+)\s*->\s*([^}]+)\}',
            lambda m: f"{{ const {m.group(2)} = {m.group(1)}; {m.group(3).strip()} }}",
            code,
        )

        # 5. when (x) { A -> { ... } B -> { ... } } → switch
        code = self._convert_when(code)

        # 6. R.string.xxx → $r('app.string.xxx')
        code = re.sub(r'\bR\.string\.(\w+)\b', r"$r('app.string.\1')", code)
        code = re.sub(r'\bR\.drawable\.(\w+)\b', r"$r('app.media.\1')", code)
        code = re.sub(r'\bR\.color\.(\w+)\b', r"$r('app.color.\1')", code)
        code = re.sub(r'\bR\.dimen\.(\w+)\b', r"$r('app.float.\1')", code)

        # 7. MutableLiveData<T>() → 合适的默认值
        code = re.sub(r'MutableLiveData<List<\w+>>\(\)', '[]', code)
        code = re.sub(r'MutableLiveData<(\w+)>\((.*?)\)', lambda m:
            m.group(2) if m.group(2) else 'null', code)

        # 8. val/var 声明 → let/let
        code = re.sub(r'\bval\s+', 'const ', code)
        code = re.sub(r'\bvar\s+', 'let ', code)

        # 9. viewModelScope.launch 残余 (shouldn't reach here, but clean up if present)
        code = re.sub(r'viewModelScope\.launch\s*\{', '{', code)

        # 10. .value 读取：_items.value → this.items
        code = re.sub(r'_(\w+)\.value\b', lambda m: f"this.{m.group(1)}", code)

        # 11. ?: → ??
        code = code.replace("?:", "??")

        # 12. 字符串模板 ${} 保留（ArkTS 支持）
        # 13. Unit → void（返回类型）
        code = re.sub(r':\s*Unit\s*\{', ': void {', code)

        # 14. 去掉 Kotlin 特有 it. 在简单 lambda 中
        # 保留，不做替换避免误改

        # 15. savedStateHandle.get<T>(key) → savedStateHandle.get(key) as T (Map API)
        code = re.sub(
            r'savedStateHandle\.get<(\w+)>\(([^)]+)\)',
            r'(savedStateHandle.get(\2) as \1)',
            code
        )
        code = re.sub(
            r'savedStateHandle\.set\(([^,]+),\s*([^)]+)\)',
            r'savedStateHandle.set(\1, \2)',
            code
        )

        # 16. Event(x) → 'event' string trigger (HarmonyOS uses @State)
        # Event(Unit) / Event(null) → 'event'  |  Event(someValue) → someValue
        code = re.sub(r'\bEvent\((Unit|null)\)', "'event'", code)
        code = re.sub(r'\bEvent\(([^)]+)\)', r'\1', code)

        # Add `new` keyword for constructor calls that are missing it
        # Task(x, y) → new Task(x, y)  (only when not already preceded by 'new')
        code = re.sub(r'(?<!new )(?<![.\w])\b(Task)\s*\(', r'new \1(', code)

        # Fix Result.Error(ex) → new ResultError(ex) and isinstance checks
        code = re.sub(r'\bResult\.Error\s*\(', 'new ResultError(', code)
        code = re.sub(r'\binstanceof\s+Result\.Error\b', 'instanceof ResultError', code)

        # const this.fieldName = ... → this.fieldName = ... (invalid syntax from Kotlin val _field = )
        code = re.sub(r'\bconst\s+this\.(\w+)\b', r'this.\1', code)

        # emptyList() → []
        code = re.sub(r'\bemptyList(?:<[^>]+>)?\(\)', r'[]', code)

        # tasksToShow.add(item) → tasksToShow.push(item)
        code = re.sub(r'\.add\s*\(', '.push(', code)

        # 17. 去掉多余空行
        code = re.sub(r'\n{3,}', '\n\n', code)

        # 18. Dedup double await
        code = re.sub(r'\bawait\s+await\b', 'await', code)

        # 19. Unit literal → null (Unit used as value, not type)
        code = re.sub(r'\b(=\s*)Unit\b', r'\1null', code)

        return code

    def _convert_when(self, code: str) -> str:
        """
        Kotlin when → TypeScript switch。
        when (x) {
            A -> { body }
            B -> expr
            else -> { body }
        }
        →
        switch (x) {
            case A: { body } break;
            case B: expr; break;
            default: { body }
        }
        """
        def replace_when(m):
            subject = m.group(1).strip()
            body = m.group(2)
            cases = []
            # 每个 arm：pattern -> { ... } 或 pattern -> expr
            arm_re = re.compile(
                r'(\w+(?:\.\w+)*|else)\s*->\s*(\{[^}]*\}|[^\n]+)',
                re.DOTALL
            )
            for arm in arm_re.finditer(body):
                pat = arm.group(1).strip()
                act = arm.group(2).strip()
                kw = "default" if pat == "else" else f"case {pat}"
                if act.startswith("{"):
                    inner = act[1:-1].strip()
                    cases.append(f"  {kw}: {{\n    {inner}\n    break;\n  }}")
                else:
                    cases.append(f"  {kw}: {act}; break;")
            if not cases:
                return m.group(0)  # 无法解析，保留原样
            return f"switch ({subject}) {{\n" + "\n".join(cases) + "\n}"

        return re.sub(
            r'\bwhen\s*\(([^)]+)\)\s*\{((?:[^{}]|\{[^{}]*\})*)\}',
            replace_when,
            code,
            flags=re.DOTALL,
        )
