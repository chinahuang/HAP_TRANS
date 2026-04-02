"""
ArkTS 最终语法清理 — 处理 KotlinTransform 之后遗留的 Kotlin 语法。

处理内容：
  1. 移除 package 语句
  2. 移除剩余 Android / Kotlin / 工程内部 import
  3. 修复类声明语法错误  class Foo extends X {) {  →  class Foo extends X {
  4. override fun / fun  →  ArkTS 方法声明
  5. private lateinit var  →  private x!: Type
  6. Kotlin 访问修饰符 / internal / open 关键字清理
  7. 去掉孤立的 Kotlin 语法关键字（companion object、init 块等）
  8. :: 方法引用清理
"""
import re
from typing import List


# Android / Kotlin 专有 import 前缀列表
_ANDROID_IMPORT_PREFIXES = (
    "android.", "androidx.", "kotlin.", "kotlinx.",
    "com.google.android.", "com.example.android.",
    "dagger.", "hilt.", "javax.inject.",
)


class ArkTSCleanup:

    def clean(self, code: str, is_ability: bool = False) -> str:
        code = self._convert_sealed_class(code)
        code = self._remove_package(code)
        code = self._remove_android_imports(code)
        code = self._convert_enum_class(code)
        code = self._convert_data_class(code)
        code = self._remove_room_annotations(code)
        code = self._convert_computed_properties(code)
        code = self._fix_class_decl(code)
        code = self._convert_fun_decls(code, is_ability)
        code = self._fix_lateinit(code)
        code = self._fix_modifiers(code)
        # Second pass for any override/suspend that _fix_modifiers exposed
        code = self._convert_fun_decls(code, is_ability)
        code = self._fix_companion_object(code)
        code = self._fix_kotlin_types(code)
        code = self._convert_primary_constructor(code)
        code = self._fix_expression_body_methods(code)
        code = self._remove_coroutine_wrappers(code)
        code = self._fix_elvis_return(code)
        code = self._fix_kotlin_idioms(code)
        code = self._fix_lambda_closings(code)
        code = self._fix_kotlin_is_checks(code)
        code = self._fix_catch_types(code)
        code = self._fix_double_await(code)
        code = self._fix_unit_literal(code)
        code = self._fix_self_method_calls(code)
        code = self._fix_interface_issues(code)
        code = self._remove_kotlin_extensions(code)
        code = self._fix_result_error_refs(code)
        code = self._add_missing_imports(code)
        code = self._add_exports(code)
        code = self._fix_string_templates(code)
        code = self._fix_missing_quote(code)
        code = self._remove_excess_blank_lines(code)
        return code

    # ------------------------------------------------------------------ #

    def _convert_sealed_class(self, code: str) -> str:
        """
        Convert Kotlin sealed class to ArkTS equivalent classes.
        sealed class Result<out R> { data class Success<out T>(...) : Result<T>() ... }
        → separate export class Result / Success / ResultError / Loading declarations.
        """
        # Match entire sealed class block
        m = re.search(
            r'\bsealed\s+class\s+(\w+)(?:<[^>]*>)?\s*\{([\s\S]*?)\n\}',
            code
        )
        if not m:
            return code

        outer_name = m.group(1)
        inner_body = m.group(2)

        # Map Kotlin types to ArkTS
        def _kt2ts(ktype: str) -> str:
            kt = ktype.strip().rstrip('?')
            mapping = {
                'Int': 'number', 'Long': 'number', 'Float': 'number', 'Double': 'number',
                'Boolean': 'boolean', 'String': 'string', 'Unit': 'void',
                'Nothing': 'Object', 'Exception': 'Error', 'Any': 'Object',
            }
            return mapping.get(kt, kt)

        classes = [f'export class {outer_name}<T = Object> {{}}']

        # data class Success<out T>(val data: T) : Result<T>()
        for inner_m in re.finditer(
            r'(?:data\s+)?class\s+(\w+)(<[^>]*>)?\s*\(([^)]*)\)\s*:\s*\w+(?:<[^>]*>)?\(\)',
            inner_body
        ):
            cname = inner_m.group(1)
            type_params_raw = inner_m.group(2) or ''  # e.g. '<out T>'
            params_str = inner_m.group(3).strip()
            # Normalize class name: Error → ResultError (to avoid ArkTS built-in collision)
            arkts_name = cname if cname != 'Error' else f'{outer_name}Error'
            # Build ArkTS type parameter: <out T> → <T = Object>
            type_params_arkts = ''
            type_param_name = 'Object'
            if type_params_raw:
                # Extract type var name: <out T> → T
                tp_m = re.search(r'<(?:out\s+|in\s+)?(\w+)>', type_params_raw)
                if tp_m:
                    type_param_name = tp_m.group(1)
                    type_params_arkts = f'<{type_param_name} = Object>'
            if params_str:
                # Parse params: "val data: T" → field + constructor
                params = [p.strip() for p in params_str.split(',') if p.strip()]
                fields = []
                ctor_params = []
                for param in params:
                    param = re.sub(r'\b(val|var)\s+', '', param)
                    if ':' in param:
                        fname, ftype = param.split(':', 1)
                        fname = fname.strip()
                        ftype = _kt2ts(ftype.strip())
                        fields.append(f'  readonly {fname}: {ftype};')
                        ctor_params.append(f'{fname}: {ftype}')
                ctor_block = (
                    f'  constructor({", ".join(ctor_params)}) {{\n'
                    f'    super();\n'
                    + ''.join(f'    this.{p.split(":")[0].strip()} = {p.split(":")[0].strip()};\n'
                               for p in ctor_params)
                    + '  }'
                )
                # extends Result<T> where T is the type param name
                extends_type = type_param_name if type_params_arkts else 'Object'
                classes.append(
                    f'export class {arkts_name}{type_params_arkts} extends {outer_name}<{extends_type}> {{\n'
                    + '\n'.join(fields) + '\n'
                    + ctor_block + '\n}'
                )
            else:
                classes.append(f'export class {arkts_name}{type_params_arkts} extends {outer_name}<Object> {{}}')

        # object Loading : Result<Nothing>()
        for obj_m in re.finditer(r'\bobject\s+(\w+)\s*:\s*\w+(?:<[^>]*>)?\(\)', inner_body):
            oname = obj_m.group(1)
            classes.append(f'export class {oname} extends {outer_name}<Object> {{}}')

        replacement = '\n\n'.join(classes)
        code = code[:m.start()] + replacement + code[m.end():]
        return code

    def _convert_enum_class(self, code: str) -> str:
        """enum class Foo { A, B } → export enum Foo { A, B }"""
        code = re.sub(r'\benum\s+class\s+(\w+)', r'export enum \1', code)
        return code

    def _convert_data_class(self, code: str) -> str:
        """
        data class Foo @JvmOverloads constructor(params) { ... }
        → export class Foo { constructor(params) }
        """
        # Remove @JvmOverloads
        code = re.sub(r'@JvmOverloads\s+', '', code)
        # data class → export class
        code = re.sub(r'\bdata\s+class\s+(\w+)', r'export class \1', code)
        # import java.util.UUID → UUID helper comment
        code = re.sub(
            r'^import java\.util\.UUID\s*\n?',
            '// UUID: use crypto.randomUUID() or Math.random().toString(36)\n',
            code, flags=re.MULTILINE
        )
        return code

    def _remove_room_annotations(self, code: str) -> str:
        """
        移除 Room 注解（Entity, ColumnInfo, PrimaryKey）及其参数。
        这些注解在 common/ 下的文件里没有意义（Room 已生成 data/ 目录下的专用文件）。
        """
        code = re.sub(r'@Entity\s*\([^)]*\)\s*\n?', '', code)
        code = re.sub(r'@ColumnInfo\s*\([^)]*\)\s*', '', code)
        code = re.sub(r'@PrimaryKey\s*', '', code)
        code = re.sub(r'@Ignore\s*', '', code)
        return code

    def _convert_computed_properties(self, code: str) -> str:
        """
        Kotlin computed property (val/var with get()) → TypeScript getter.
        val foo: Type
            get() = expr
        → get foo(): Type { return expr; }

        val foo
            get() = expr
        → get foo() { return expr; }
        """
        # val foo: Type\n    get() = expr  →  get foo(): Type { return expr; }
        code = re.sub(
            r'\bval\s+(\w+)\s*(?::\s*([\w<>?,\s]+))?\s*\n\s*get\(\)\s*=\s*([^\n]+)',
            lambda m: (
                f"get {m.group(1)}()"
                + (f": {m.group(2).strip()}" if m.group(2) else "")
                + f" {{ return {m.group(3).strip()}; }}"
            ),
            code
        )
        return code

    def _remove_package(self, code: str) -> str:
        return re.sub(r'^package [\w.]+\s*\n?', '', code, flags=re.MULTILINE)

    def _remove_android_imports(self, code: str) -> str:
        lines = code.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import "):
                module = stripped[7:]
                if any(module.startswith(p) for p in _ANDROID_IMPORT_PREFIXES):
                    continue   # drop line
            result.append(line)
        return "\n".join(result)

    def _fix_class_decl(self, code: str) -> str:
        # struct Foo {) { → struct Foo {  (Fragment 残余 Kotlin `)`)
        code = re.sub(r'(struct\s+\w+[^{]*)\{[)]\s*\{', r'\1{', code)
        # class Foo extends Bar {) { → class Foo extends Bar {
        code = re.sub(r'(class\s+\w+[^{]*)\{[)]\s*\{', r'\1{', code)
        # class Foo extends Bar() { → class Foo extends Bar {
        code = re.sub(r'(class\s+\w+\s+extends\s+\w+)\(\)', r'\1', code)
        # class Foo : Bar() { → class Foo extends Bar { (残余 Kotlin 继承语法)
        code = re.sub(
            r'\bclass\s+(\w+)\s*:\s*(\w+)\s*\(\s*\)\s*\{',
            r'class \1 extends \2 {', code
        )
        # class Foo : Interface { → class Foo implements Interface {
        # (Interface without parens — implements not extends)
        code = re.sub(
            r'\bclass\s+(\w+)\s*:\s*(\w+)\s*\{',
            lambda m: f'class {m.group(1)} implements {m.group(2)} {{' if m.group(2)[0].isupper() else m.group(0),
            code
        )
        return code

    def _convert_fun_decls(self, code: str, is_ability: bool) -> str:
        """
        将 Kotlin 函数声明转为 ArkTS 方法声明：
          override fun onCreate(...)  →  onCreate(...)
          private fun helper(...)     →  private helper(...)
          fun helper(...)             →  helper(...)
        """
        # override (suspend)? fun X( → X(
        code = re.sub(r'\boverride\s+(?:suspend\s+)?fun\s+(\w+)\s*\(', r'\1(', code)
        # private/protected/internal (suspend)? fun X( → private X(
        code = re.sub(
            r'\b(private|protected|internal)\s+(?:suspend\s+)?fun\s+(\w+)\s*\(',
            r'\1 \2(', code
        )
        # (suspend)? fun X( → X(  (top level / remaining)
        code = re.sub(r'\b(?:suspend\s+)?fun\s+(\w+)\s*\(', r'\1(', code)
        # Remove any residual standalone 'override' keyword before method/identifier
        code = re.sub(r'\boverride\s+(?=\w)', '', code)
        return code

    def _fix_lateinit(self, code: str) -> str:
        # private lateinit var x: Type → private x!: Type
        code = re.sub(
            r'\bprivate\s+lateinit\s+var\s+(\w+)\s*:\s*([\w<>?]+)',
            r'private \1!: \2', code
        )
        # lateinit var x: Type → \1!: Type
        code = re.sub(
            r'\blateunit\s+var\s+(\w+)\s*:\s*([\w<>?]+)',
            r'\1!: \2', code
        )
        code = re.sub(
            r'\blateninit\s+var\s+(\w+)\s*:\s*([\w<>?]+)',
            r'\1!: \2', code
        )
        # class field: private val x: Type → private x: Type (read-only field)
        code = re.sub(
            r'\bprivate\s+val\s+(\w+)\s*:\s*([\w<>?,\s]+)',
            r'private \1: \2', code
        )
        # private var x: Type → private x: Type
        code = re.sub(
            r'\bprivate\s+var\s+(\w+)\s*:\s*([\w<>?,\s]+)',
            r'private \1: \2', code
        )
        return code

    def _fix_modifiers(self, code: str) -> str:
        # internal class / open class → class
        code = re.sub(r'\b(internal|open|sealed|abstract)\s+class\b', r'class', code)
        # internal fun → remove 'internal'
        code = re.sub(r'\binternal\s+', '', code)
        # suspend fun / suspend keyword → remove (async is handled separately)
        code = re.sub(r'\bsuspend\s+', '', code)
        # Kotlin variance: <out T> → <T>,  <in T> → <T>
        code = re.sub(r'<(?:out|in)\s+(\w+)>', r'<\1>', code)
        # LiveData<T> → Promise<T>  (as a rough approximation)
        code = re.sub(r'\bLiveData<([^>]+)>', r'Promise<\1>', code)
        # MutableLiveData<T> → T  (already transformed by ViewModelTransform, but as fallback)
        code = re.sub(r'\bMutableLiveData<([^>]+)>', r'\1', code)
        # List<T> → Array<T> (in type positions)
        code = re.sub(r'\bList<([^>]+)>', r'Array<\1>', code)
        code = re.sub(r'\bMutableList<([^>]+)>', r'Array<\1>', code)
        return code

    def _fix_companion_object(self, code: str) -> str:
        # companion object { ... } → static block comment
        code = re.sub(
            r'\bcompanion\s+object\s*\{',
            '// companion object — convert fields to static\n  static {',
            code
        )
        return code

    def _fix_kotlin_types(self, code: str) -> str:
        # Unit return type: ): Unit { → ): void {
        code = re.sub(r'\)\s*:\s*Unit\s*\{', '): void {', code)
        # : Unit  → : void (in return type position)
        code = re.sub(r':\s*Unit\b', ': void', code)
        # Nullable types: Type? → Type | null  (in type positions only, not before .)
        code = re.sub(r'\b(\w+)\?(?=\s*[,);{=\[])', r'\1 | null', code)
        # Function param: param: Type? → param: Type | null
        code = re.sub(r'(:\s*\w+)\?(?=\s*[,)])', r'\1 | null', code)
        # Pair<A,B> → [A, B]  (rough approximation)
        code = re.sub(r'\bPair<([^,>]+),\s*([^>]+)>', r'[\1, \2]', code)

        # Kotlin primitive type names → ArkTS equivalents (in type position)
        type_map = [
            ("String", "string"), ("Boolean", "boolean"),
            ("Int", "number"), ("Long", "number"),
            ("Float", "number"), ("Double", "number"),
            ("Any", "Object"), ("Unit", "void"),
        ]
        for kt, ts in type_map:
            code = re.sub(rf':\s*{kt}\b', f': {ts}', code)
            # Also in generic params e.g. List<String> → List<string>
            code = re.sub(rf'<{kt}>', f'<{ts}>', code)

        # val x = ... → const x = ... (inside function bodies / local vars)
        code = re.sub(r'\bval\s+(\w+)\s*=', r'const \1 =', code)
        code = re.sub(r'\bvar\s+(\w+)\s*=', r'let \1 =', code)

        # top-level: const val X → export const X
        code = re.sub(r'\bconst\s+val\s+(\w+)', r'export const \1', code)

        # class field: var x: Type (residual Kotlin field modifier) → x: Type
        code = re.sub(r'\bvar\s+(\w+)\s*:', r'\1:', code)

        return code

    def _convert_primary_constructor(self, code: str) -> str:
        """
        Kotlin 主构造函数:
          export class Foo constructor(\n    var x: type = val,\n    ...\n) {
          export class Foo(params) : Interface {
          class Foo(params) {
        → export class Foo (implements Interface) {\n  private fields;\n  constructor(params) { this.x = x; }
        """
        def _split_params_smart(params_raw: str):
            """Split params by comma, respecting < > angle bracket nesting."""
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

        def rewrite(m: re.Match) -> str:
            class_prefix = m.group(1)  # e.g. 'export class Foo' or 'class Foo'
            params_raw = m.group(2)    # raw param list
            implements = m.group(3) if m.lastindex >= 3 else None  # optional: ': TasksRepository'
            # Parse params: remove private/val/var, skip default values with Android types
            fields = []
            ctor_params = []
            assignments = []
            for param in _split_params_smart(params_raw):
                param = param.strip()
                if not param:
                    continue
                # Remove Kotlin modifiers
                clean = re.sub(r'\b(?:private|public|protected|val|var)\s+', '', param)
                # Remove default values that reference Android classes (e.g. = Dispatchers.IO)
                clean = re.sub(r'\s*=\s*\w[\w.]+.*$', '', clean).strip()
                # Remove Kotlin-specific types
                clean = re.sub(r':\s*CoroutineDispatcher\b', ': Object', clean)
                if not clean or ':' not in clean:
                    continue
                pname = clean.split(':')[0].strip()
                ptype = clean.split(':', 1)[1].strip()
                # Skip Android/Kotlin-only types
                if any(t in ptype for t in ('CoroutineDispatcher', 'Dispatchers')):
                    continue
                # Use 'readonly' for public val fields, 'private' for private val/var
                is_private_field = bool(re.search(r'\bprivate\b', param))
                field_modifier = 'private' if is_private_field else 'readonly'
                fields.append(f"  {field_modifier} {pname}: {ptype};")
                ctor_params.append(f"{pname}: {ptype}")
                assignments.append(f"    this.{pname} = {pname};")
            # Build implements clause
            impl_clause = ""
            if implements:
                iface = implements.strip().lstrip(':').strip()
                if iface and not iface.endswith('()'):
                    impl_clause = f" implements {iface}"
            fields_str = ("\n" + "\n".join(fields) + "\n") if fields else "\n"
            ctor_str = ", ".join(ctor_params)
            assigns_str = "\n".join(assignments) if assignments else "    // TODO: initialize"
            return (
                f"{class_prefix}{impl_clause} {{{fields_str}\n"
                f"  constructor({ctor_str}) {{\n{assigns_str}\n  }}"
            )

        field_names: list = []

        def rewrite_and_collect(m: re.Match) -> str:
            result = rewrite(m)
            # Collect field names for later this. fixup
            params_raw = m.group(2)
            for param in _split_params_smart(params_raw):
                param = param.strip()
                clean = re.sub(r'\b(?:private|public|protected|val|var)\s+', '', param)
                clean = re.sub(r'\s*=.*$', '', clean).strip()
                if ':' in clean:
                    pname = clean.split(':')[0].strip()
                    if pname and re.match(r'^[a-z]\w*$', pname):
                        field_names.append(pname)
            return result

        # Pattern 1: export class Foo constructor(params) {
        code = re.sub(
            r'((?:export\s+)?class\s+\w+)\s+constructor\s*\((.*?)\)\s*\{',
            rewrite_and_collect,
            code,
            flags=re.DOTALL,
        )
        # Pattern 2: class Foo(params) : Interface { OR class Foo(params) {
        code = re.sub(
            r'((?:export\s+)?class\s+\w+)\s*\((.*?)\)\s*(:\s*\w+(?:\s*\(\s*\))?)?\s*\{',
            rewrite_and_collect,
            code,
            flags=re.DOTALL,
        )
        # Add this. prefix to bare field accesses (not already preceded by . or this.)
        for fname in set(field_names):
            # Match fname not preceded by '.', and not followed by ':' (type annotation)
            code = re.sub(
                rf'(?<![.\w]){re.escape(fname)}\b(?!\s*:)',
                f'this.{fname}',
                code,
            )
            # Fix double this.this. that might result
            code = code.replace(f'this.this.{fname}', f'this.{fname}')
            # Fix self-assignment in constructor: this.fname = this.fname → this.fname = fname
            code = re.sub(
                rf'(this\.{re.escape(fname)}\s*=\s*)this\.{re.escape(fname)}\b',
                rf'\g<1>{fname}',
                code,
            )
        return code

    def _remove_coroutine_wrappers(self, code: str) -> str:
        """
        移除 Kotlin 协程包装块，保留内部代码体。
        coroutineScope { body } → body
        withContext(x) { body } → body
        launch { body } → body (standalone)
        wrapEspressoIdlingResource { body } → body
        """
        import re as _re
        def inline_block(pattern, code_str):
            """Replace pattern { body } with just body (brace-aware)."""
            result = []
            i = 0
            for m in _re.finditer(pattern, code_str):
                result.append(code_str[i:m.start()])
                # Find the matching closing brace
                brace_start = m.end() - 1  # position of opening {
                depth = 0
                j = brace_start
                while j < len(code_str):
                    if code_str[j] == '{':
                        depth += 1
                    elif code_str[j] == '}':
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                # Extract inner body (strip leading/trailing whitespace)
                inner = code_str[brace_start + 1:j].strip()
                result.append(inner)
                i = j + 1
            result.append(code_str[i:])
            return "".join(result)

        code = inline_block(r'\bcoroutineScope\s*\{', code)
        code = inline_block(r'\bwithContext\s*\([^)]*\)\s*\{', code)
        code = inline_block(r'\bwrapEspressoIdlingResource\s*\{', code)
        # standalone launch { } (not viewModelScope.launch)
        code = inline_block(r'(?<!\.)\blaunch\s*\{', code)
        # return@launch → return
        code = _re.sub(r'\breturn@\w+\b', 'return', code)
        return code

    def _fix_lambda_closings(self, code: str) -> str:
        """
        After converting Kotlin lambda { x -> } to arrow function ({ x) => {,
        the closing } needs to become }) to close the enclosing forEach/map/filter call.
        Uses brace-depth tracking to find the correct closing brace.
        """
        HIGHER_ORDER_RE = re.compile(
            r'\.(forEach|map|filter|flatMap|sortedBy|sortedWith)\(\s*\(\w+\)\s*=>\s*\{'
        )
        lines = code.split('\n')
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if HIGHER_ORDER_RE.search(line):
                # Count opening { in this line vs closing } to track depth
                depth = line.count('{') - line.count('}')
                result.append(line)
                i += 1
                if depth > 0:
                    while i < len(lines):
                        current = lines[i]
                        depth += current.count('{') - current.count('}')
                        if depth == 0:
                            # This line closes the lambda — add )
                            result.append(current.rstrip() + ')')
                            i += 1
                            break
                        else:
                            result.append(current)
                            i += 1
            else:
                result.append(line)
                i += 1
        return '\n'.join(result)

    def _fix_kotlin_is_checks(self, code: str) -> str:
        """
        x is SomeType → x instanceof SomeType
        x is Result.Error → x instanceof Object (approximation)
        !(x is Y) → !(x instanceof Y)
        """
        # x is TypeName (where TypeName starts with uppercase)
        code = re.sub(r'\b(\w[\w.]*)\s+is\s+([A-Z]\w*(?:\.\w+)*)\b', r'\1 instanceof \2', code)
        # (x as? TypeName) → (x instanceof TypeName ? x as TypeName : null)
        code = re.sub(
            r'\((\w[\w.]*)\s+as\?\s+(\w+)\)',
            r'(\1 instanceof \2 ? \1 as \2 : null)',
            code
        )
        return code

    def _fix_interface_issues(self, code: str) -> str:
        """
        Fix ArkTS interface issues:
        1. Remove `this.` prefix from method signatures (added erroneously)
        2. Remove default values from parameters (not supported in ArkTS interfaces)
        3. Merge overloaded methods into single method with union type params
        4. Add return type void for methods without return type
        """
        if not re.search(r'\binterface\s+\w+\s*\{', code):
            return code

        lines = code.split('\n')
        in_interface = False
        depth = 0
        result = []
        seen_methods: dict = {}  # method_name → line index for overload detection

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if re.match(r'\binterface\s+\w+', stripped):
                in_interface = True
                seen_methods = {}
            if in_interface:
                depth += line.count('{') - line.count('}')
                if depth <= 0:
                    in_interface = False
                    depth = 0
                else:
                    # Remove `this.` prefix from method declarations in interface
                    line = re.sub(r'\bthis\.(\w+)\s*\(', r'\1(', line)
                    # Remove default values from parameter lists
                    line = re.sub(r'(\w+\s*:\s*[\w<>|,\s[\]]+)\s*=\s*[^,)]+', r'\1', line)
                    # Add ': void' return type to bare method signatures with no return type
                    line = re.sub(r'^(\s+\w+\s*\([^)]*\))\s*$', r'\1: void', line)
                    # Check for method overloading — if same method name appears twice,
                    # merge into union type signature
                    m_sig = re.match(r'\s+(\w+)\s*\(([^)]*)\)', line)
                    if m_sig:
                        mname = m_sig.group(1)
                        mparams = m_sig.group(2).strip()
                        if mname in seen_methods:
                            # Find previous line index and replace with union type
                            prev_idx = seen_methods[mname]
                            prev_line = result[prev_idx]
                            pm = re.match(r'(\s+\w+\s*\()([^)]*)(\).*)', prev_line)
                            if pm:
                                # Combine params as union: (param1: Type1 | Type2)
                                prev_params = pm.group(2).strip()
                                # Extract param names and types
                                def _extract_types(params_str: str) -> list:
                                    parts = []
                                    for p in params_str.split(','):
                                        p = p.strip()
                                        if ':' in p:
                                            parts.append(p.split(':', 1)[1].strip())
                                    return parts
                                prev_types = _extract_types(prev_params)
                                curr_types = _extract_types(mparams)
                                if prev_types and curr_types:
                                    # Use first param name from previous
                                    prev_pname = prev_params.split(':')[0].strip() if ':' in prev_params else 'param'
                                    union_type = ' | '.join(set(prev_types + curr_types))
                                    result[prev_idx] = f'{pm.group(1)}{prev_pname}OrId: {union_type}{pm.group(3)}'
                            # Skip the duplicate overload line
                            i += 1
                            continue
                        else:
                            seen_methods[mname] = len(result)
            result.append(line)
            i += 1
        return '\n'.join(result)

    def _fix_catch_types(self, code: str) -> str:
        """catch (ex: ExceptionType) → catch (ex)  (ArkTS no type annotations in catch)"""
        code = re.sub(r'\bcatch\s*\(\s*(\w+)\s*:\s*[\w.]+\s*\)', r'catch (\1)', code)
        return code

    def _fix_double_await(self, code: str) -> str:
        """await await expr → await expr"""
        code = re.sub(r'\bawait\s+await\b', 'await', code)
        return code

    def _fix_unit_literal(self, code: str) -> str:
        """
        Unit used as a value (not a type) → remove / replace.
        this.event = Unit  → this.event = null
        = Unit /* Event */ → = null /* Event */
        """
        # Unit used as RHS value
        code = re.sub(r'\b(=\s*)Unit\b', r'\1null', code)
        # Unit as function call argument
        code = re.sub(r'\bUnit\b(?!\s*\{)', 'null', code)
        return code

    def _fix_self_method_calls(self, code: str) -> str:
        """
        Add this. prefix to bare private method calls within class.
        Collects method names defined in the class and prefixes calls with this.
        Skips ViewModel files (already handled by ViewModelTransform).
        """
        # ViewModel files are already processed by ViewModelTransform._add_this_prefix
        # Interface files should not have this. prefix added to their method signatures
        # Skip ViewModel files (handled by ViewModelTransform) and interface-only files
        if '// AUTO-CONVERTED: ViewModel' in code[:300] or re.search(r'\binterface\s+\w+\s*\{', code):
            return code
        # Collect method names defined at class level (indented 2-4 spaces)
        method_names = set()
        _SKIP = frozenset((
            'constructor', 'if', 'for', 'while', 'switch', 'catch', 'get', 'set',
            'new', 'return', 'throw', 'class', 'async', 'import', 'export',
            'const', 'let', 'var', 'try', 'else', 'super',
        ))
        for m in re.finditer(r'^\s{2,4}(?:(?:private|public|async|static)\s+)*(\w+)\s*\(', code, re.MULTILINE):
            name = m.group(1)
            if name not in _SKIP:
                method_names.add(name)
        if not method_names:
            return code
        # Replace bare calls line-by-line, skipping declaration lines (those ending with '{')
        result_lines = []
        for line in code.split('\n'):
            stripped = line.lstrip()
            # Method declaration line has modifiers + name( ) with '{' at end
            is_decl = bool(re.match(
                r'(?:(?:private|public|protected|async|static|override)\s+)*\w+\s*\([^)]*\)'
                r'(?:\s*:\s*[\w<>|,\s]+)?\s*\{',
                stripped
            ))
            if not is_decl:
                for name in method_names:
                    line = re.sub(
                        rf'(?<![.\w]){re.escape(name)}\s*\(',
                        f'this.{name}(',
                        line,
                    )
                    line = line.replace(f'this.this.{name}', f'this.{name}')
            result_lines.append(line)
        return '\n'.join(result_lines)

    def _fix_expression_body_methods(self, code: str) -> str:
        """
        Method with expression body: methodName(params) = expr { → methodName(params) {
        e.g. activateTask(task: Task) = withContext<void>(ioDispatcher) {
        """
        # Remove = expr before { in method bodies
        code = re.sub(
            r'(\w+\s*\([^)]*\)\s*)=\s*\w[\w.<>]*\s*\([^)]*\)\s*\{',
            r'\1{',
            code,
        )
        return code

    def _fix_elvis_return(self, code: str) -> str:
        """
        const x = expr ?? return  →  if (expr == null) return;\n  const x = expr;
        Also: x ?? return → if (x == null) return
        """
        def replace_elvis_return(m):
            indent = m.group(1)
            decl_kw = m.group(2)   # 'const' or 'let' or None
            var_name = m.group(3)  # variable name or None
            expr = m.group(4).strip()
            if decl_kw and var_name:
                return f"{indent}if ({expr} == null) return;\n{indent}{decl_kw} {var_name} = {expr};"
            else:
                return f"{indent}if ({expr} == null) return;"
        # const x = expr ?? return  (or let x = expr ?? return)
        code = re.sub(
            r'^(\s*)(const|let)\s+(\w+)\s*=\s*(.+?)\s*\?\?\s*return\b',
            replace_elvis_return,
            code,
            flags=re.MULTILINE,
        )
        # standalone: expr ?? return
        code = re.sub(r'\b(\w[\w.]*)\s*\?\?\s*return\b', r'if (\1 == null) return', code)
        return code

    def _fix_kotlin_idioms(self, code: str) -> str:
        """常见 Kotlin 惯用法 → ArkTS 等价写法。"""
        # UUID.randomUUID().toString() → Math.random().toString(36).substring(2, 10)
        code = code.replace(
            'UUID.randomUUID().toString()',
            "Math.random().toString(36).substring(2, 10)"
        )
        # str.isNotEmpty() → str.length > 0
        code = re.sub(r'(\w+)\.isNotEmpty\(\)', r'\1.length > 0', code)
        # str.isEmpty() → str.length === 0
        code = re.sub(r'(\w+)\.isEmpty\(\)', r'\1.length === 0', code)
        # list.isNotEmpty() handled by same rule above
        # x.isNullOrEmpty() → !x || x.length === 0
        code = re.sub(r'(\w+)\.isNullOrEmpty\(\)', r'(!\1 || \1.length === 0)', code)
        # x.isNullOrBlank() → !x || x.trim().length === 0
        code = re.sub(r'(\w+)\.isNullOrBlank\(\)', r'(!\1 || \1.trim().length === 0)', code)
        # Kotlin expression if:  if (cond) a else b  (used as value) → (cond ? a : b)
        # Only handle simple single-expression form (no nested braces)
        code = re.sub(
            r'\bif\s*\(([^)]+)\)\s+([^\n{]+?)\s+else\s+([^\n{;]+)',
            r'(\1 ? \2 : \3)',
            code
        )
        # x.let { it -> body } on a single line → if (x != null) { body }
        code = re.sub(
            r'(\w[\w.]*)\?\.let\s*\{\s*(\w+)\s*->\s*([^}]+)\}',
            lambda m: f'if ({m.group(1)} != null) {{ const {m.group(2)} = {m.group(1)}; {m.group(3).strip()} }}',
            code,
        )
        # (expr as? Type)?.let { it -> body } already handled by _fix_kotlin_is_checks
        # .apply { ... } blocks — leave as-is (complex)
        # Collection operations: add { to convert Kotlin lambda to arrow function block
        code = re.sub(r'\.forEach\s*\{\s*(\w+)\s*->', r'.forEach((\1) => {', code)
        code = re.sub(r'\.map\s*\{\s*(\w+)\s*->', r'.map((\1) => {', code)
        code = re.sub(r'\.filter\s*\{\s*(\w+)\s*->', r'.filter((\1) => {', code)
        code = re.sub(r'\.flatMap\s*\{\s*(\w+)\s*->', r'.flatMap((\1) => {', code)
        # RuntimeException(...) → new Error(...)
        code = re.sub(r'\bRuntimeException\(', 'new Error(', code)
        code = re.sub(r'\bIllegalStateException\(', 'new Error(', code)
        code = re.sub(r'\bIllegalArgumentException\(', 'new Error(', code)
        code = re.sub(r'\bException\(', 'new Error(', code)
        # emptyList<T>() → []
        code = re.sub(r'\bemptyList<\w+>\(\)', r'[]', code)
        # listOf() → []
        code = re.sub(r'\blistOf\(\)', r'[]', code)
        # listOf(x, y) → [x, y]  (simple single-line)
        code = re.sub(r'\blistOf\(([^)]*)\)', r'[\1]', code)
        # ArrayList<T>() → []
        code = re.sub(r'\bArrayList<[^>]*>\(\)', r'[]', code)
        # Kotlin for-in → TypeScript for-of
        code = re.sub(r'\bfor\s*\(\s*(\w+)\s+in\s+(\w+)\s*\)', r'for (const \1 of \2)', code)
        # return if (cond) { value } else { value }
        # → if (cond) { return value; } else { return value; }
        code = re.sub(
            r'\breturn\s+if\s*\(([^)]+)\)\s*\{([^}]*)\}\s*else\s*\{([^}]*)\}',
            lambda m: (
                f'if ({m.group(1).strip()}) {{\n  return {m.group(2).strip()};\n}}'
                f' else {{\n  return {m.group(3).strip()};\n}}'
            ),
            code,
        )
        # .x?.let { it -> body }  →  if (x != null) { body }
        code = re.sub(
            r'(\w[\w.]*)\?\.let\s*\{\s*it\s*->\s*([^}]+)\}',
            lambda m: f'if ({m.group(1)} != null) {{ const it = {m.group(1)}; {m.group(2).strip()} }}',
            code,
        )
        # (expr as? Type)?.let { it -> body }  — already handled by _fix_kotlin_is_checks
        # toString() call on non-string types — leave as-is (valid in TS too)
        return code

    def _fix_string_templates(self, code: str) -> str:
        # Fix unclosed $r() strings like $r('app.color.colorPrimaryDark) → $r('app.color.colorPrimaryDark')
        code = re.sub(
            r"\$r\('(app\.\w+\.\w+)\)",
            r"$r('\1')",
            code
        )
        return code

    def _fix_missing_quote(self, code: str) -> str:
        # setStatusBarBackground($r('app.color.colorPrimaryDark) → add closing '
        code = re.sub(
            r"(\$r\('[^']*?)(\))",
            lambda m: m.group(1) + "')" if not m.group(1).endswith("'") else m.group(0),
            code
        )
        return code

    def _remove_kotlin_extensions(self, code: str) -> str:
        """
        Remove Kotlin extension property/function declarations which are invalid in ArkTS.
        val Type<*>.propName get() = ...
        fun Type.methodName(...) = ...
        """
        # val SomeType<...>.propName ... (multiline) — remove the block
        code = re.sub(r'\nval\s+\w[\w<>*., ]*\.\w+\s*\n[^\n]*\n', '\n', code)
        # Single-line: val Type.prop get() = expr
        code = re.sub(r'\nval\s+\w[\w<>*., ]*\.\w+[^\n]*\n', '\n', code)
        return code

    def _fix_result_error_refs(self, code: str) -> str:
        """
        Fix references to the Kotlin-style Result.Error / Result.Success in code bodies.
        Result.Error(ex) → new ResultError(ex)
        instanceof Result.Error → instanceof ResultError
        Result.Success(data) → new Success(data)
        """
        code = re.sub(r'\bResult\.Error\s*\(', 'new ResultError(', code)
        code = re.sub(r'\binstanceof\s+Result\.Error\b', 'instanceof ResultError', code)
        code = re.sub(r'\bResult\.Success\s*\(', 'new Success(', code)
        code = re.sub(r'\binstanceof\s+Result\.Success\b', 'instanceof Success', code)
        return code

    def _add_missing_imports(self, code: str) -> str:
        """Add import statements for commonly used types that are missing."""
        # Check what types are used but not imported
        existing_imports = set(re.findall(r"import\s*\{([^}]+)\}", code))
        already = set()
        for imp in existing_imports:
            for name in re.split(r',\s*', imp):
                already.add(name.strip())

        # Determine which types are defined in this file itself (don't self-import)
        defined_here = set(re.findall(r'export\s+(?:class|interface|enum)\s+(\w+)', code))

        to_add = []
        # Task type used but not imported and not defined here
        if 'Task' not in already and 'Task' not in defined_here and re.search(r'\bTask\b', code):
            to_add.append("import { Task } from './Task';")
        # Result types — don't add if Result is defined here
        if 'Result' not in already and 'Result' not in defined_here and re.search(r'\bResult\b', code):
            to_add.append("import { Result, Success, ResultError } from './Result';")
        # TasksRepository interface — add for files that implement it but don't import it
        if ('TasksRepository' not in already and 'TasksRepository' not in defined_here
                and re.search(r'\bimplements\s+TasksRepository\b', code)):
            to_add.append("import { TasksRepository } from './TasksRepository';")

        if to_add:
            # Insert after last import line or at the beginning of the file (after comments)
            lines = code.split('\n')
            last_import_idx = -1
            for i, line in enumerate(lines):
                if line.strip().startswith('import '):
                    last_import_idx = i
            insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
            for imp_line in reversed(to_add):
                lines.insert(insert_at, imp_line)
            code = '\n'.join(lines)
        return code

    def _add_exports(self, code: str) -> str:
        """
        对顶层 class / interface 声明添加 export（跳过 @Component struct）。
        """
        lines = code.split("\n")
        result = []
        prev_is_component = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("@Component") or stripped.startswith("@Entry"):
                prev_is_component = True
                result.append(line)
                continue
            if not prev_is_component:
                # Add export to top-level class/interface without export/abstract/open prefix
                if re.match(r'^(class|interface)\s+\w+', stripped):
                    line = "export " + line.lstrip()
            prev_is_component = False
            result.append(line)
        return "\n".join(result)

    def _remove_excess_blank_lines(self, code: str) -> str:
        return re.sub(r'\n{3,}', '\n\n', code)
