"""
Kotlin/Java → ArkTS 转换引擎（规则驱动 + 注释标记）。

当前策略：
  1. import 替换（android.util.Log → @ohos/hilog 等）
  2. API 调用替换（Log.d → hilog.debug 等）
  3. 生命周期方法签名适配
  4. 类声明骨架转换（Activity/Fragment → UIAbility/CustomComponent）
  5. 无法自动转换的代码用 TODO 注释标记，供人工处理

这是一个渐进式引擎，不追求100%正确，而是尽量减少人工工作量。
"""
import re
from typing import Dict, List
from parser.kotlin_parser import SourceClass


class KotlinTransform:
    def __init__(self, api_map: Dict[str, str], lifecycle_map: Dict[str, str]):
        self.api_map = api_map          # "Log.d" → "hilog.debug"
        self.lifecycle_map = lifecycle_map  # "onResume" → "onForeground"

    def transform(self, sc: SourceClass) -> str:
        code = sc.raw_content

        # 1. 替换 import
        code = self._transform_imports(code)

        # 2. 替换 API 调用
        code = self._transform_api_calls(code)

        # 3. 替换生命周期方法名
        code = self._transform_lifecycle(code)

        # 4. 替换类声明骨架
        code = self._transform_class_decl(sc, code)

        # 5. Intent → Want / router
        code = self._transform_intent(code)

        # 6. SharedPreferences → @ohos/preferences
        code = self._transform_shared_preferences(code)

        # 7. Runtime permissions → abilityAccessCtrl
        code = self._transform_permissions(code)

        # 8. 添加文件头注释
        header = self._build_header(sc)
        return header + code

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        """返回 {原文件路径 → 转换后的 ArkTS 代码}。"""
        results = {}
        for sc in classes:
            results[sc.file_path] = self.transform(sc)
        return results

    # ------------------------------------------------------------------
    def _transform_imports(self, code: str) -> str:
        import_replacements = {
            r"^import android\.util\.Log$": "import hilog from '@ohos.hilog'",
            r"^import android\.content\.Intent$": "import Want from '@ohos.app.ability.Want'",
            r"^import android\.content\.SharedPreferences.*$": "import preferences from '@ohos.data.preferences'",
            r"^import android\.widget\.Toast$": "import promptAction from '@ohos.promptAction'",
            r"^import androidx\.lifecycle\.LiveData.*$": "// TODO: LiveData → @State / @Prop",
            r"^import androidx\.lifecycle\.ViewModel.*$": "// TODO: ViewModel → ArkTS state management",
            r"^import kotlinx\.coroutines\.flow\.StateFlow.*$": "// StateFlow → @Trace (see ViewModelTransform)",
            r"^import kotlinx\.coroutines\.flow\.MutableStateFlow.*$": "// MutableStateFlow → @Trace",
            r"^import kotlinx\.coroutines\.flow\.SharedFlow.*$": "// SharedFlow → @Trace (event bus)",
            r"^import kotlinx\.coroutines\.flow\.MutableSharedFlow.*$": "// MutableSharedFlow → @Trace",
            r"^import kotlinx\.coroutines\.flow\.Flow.*$": "// Flow → async / TaskPool",
            r"^import kotlinx\.coroutines\.flow\..*$": "// coroutines-flow → TODO",
            r"^import androidx\.room\..*$": "// TODO: Room → @ohos/relationalStore",
            r"^import androidx\.navigation\..*$": "// TODO: Navigation → Router",
            r"^import dagger\.hilt\..*$": "// TODO: Hilt DI → manual injection",
            r"^import kotlinx\.coroutines\..*$": "// TODO: Coroutines → async/await or TaskPool",
        }
        lines = code.split("\n")
        new_lines = []
        for line in lines:
            stripped = line.strip()
            replaced = False
            for pattern, replacement in import_replacements.items():
                if re.match(pattern, stripped):
                    new_lines.append(replacement)
                    replaced = True
                    break
            if not replaced:
                new_lines.append(line)
        return "\n".join(new_lines)

    def _transform_api_calls(self, code: str) -> str:
        for android_api, ohos_api in self.api_map.items():
            escaped = re.escape(android_api)
            code = re.sub(escaped, ohos_api, code)
        code = self._transform_rid(code)
        return code

    def _transform_rid(self, code: str) -> str:
        """
        R.id / R.layout / R.menu 等 View ID 引用在 ArkUI 中没有对应概念。

        策略：
          - inflater.inflate(R.layout.foo_frag, ...) → 整个 inflate 调用删除，
            因为 Fragment.onCreateView 在 ArkUI 中用 build() 替代
          - findViewById(R.id.foo) → 标注 TODO，保留 id 名供参考
          - R.layout.xxx → 注释掉
          - R.id.xxx     → 字符串 "xxx"（用作标识）
          - R.menu.xxx   → 注释掉
        """
        # inflater.inflate(R.layout.xxx, ...) → // removed: inflate(R.layout.xxx)
        code = re.sub(
            r'inflater\.inflate\s*\(\s*R\.layout\.(\w+)[^)]*\)',
            r'// ArkUI: build() replaces inflate(R.layout.\1)',
            code,
        )
        # setContentView(R.layout.xxx) → // ArkUI: build() replaces setContentView
        code = re.sub(
            r'setContentView\s*\(\s*R\.layout\.(\w+)\s*\)',
            r'// ArkUI: build() replaces setContentView(R.layout.\1)',
            code,
        )
        # findViewById<Type>(R.id.foo) → // TODO: ArkUI has no findViewById; use @State binding
        code = re.sub(
            r'(?:activity\?\.)?findViewById\s*(?:<[^>]+>)?\s*\(\s*R\.id\.(\w+)\s*\)',
            r'/* TODO: no findViewById in ArkUI; bind "\1" via @State */(null as any)',
            code,
        )
        # requireView().findViewById<Type>(R.id.foo)
        code = re.sub(
            r'requireView\(\)\.findViewById\s*(?:<[^>]+>)?\s*\(\s*R\.id\.(\w+)\s*\)',
            r'/* TODO: no findViewById in ArkUI; bind "\1" via @State */(null as any)',
            code,
        )
        # R.id.xxx (残余) → "\1" 字符串
        code = re.sub(r'\bR\.id\.(\w+)\b', r'"\1"', code)
        # R.layout.xxx → 注释
        code = re.sub(r'\bR\.layout\.(\w+)\b', r'/* R.layout.\1 */', code)
        # R.menu.xxx → 注释
        code = re.sub(r'\bR\.menu\.(\w+)\b', r'/* R.menu.\1 */', code)
        return code

    def _transform_lifecycle(self, code: str) -> str:
        for android_method, ohos_method in self.lifecycle_map.items():
            if android_method == ohos_method:
                continue
            # override fun onResume() → override fun onForeground()
            pattern = rf"\b(override\s+fun\s+){android_method}\b"
            replacement = rf"\g<1>{ohos_method}"
            code = re.sub(pattern, replacement, code)
        return code

    def _transform_class_decl(self, sc: SourceClass, code: str) -> str:
        if sc.is_activity:
            code = re.sub(
                r"\bclass\s+(\w+)\s*:\s*\w*Activity\w*\(",
                r"// TODO: UIAbility\nclass \1 extends UIAbility {",
                code,
            )
        elif sc.is_fragment:
            code = re.sub(
                r"\bclass\s+(\w+)\s*:\s*\w*Fragment\w*\(",
                r"// TODO: @Component\n@Component\nstruct \1 {",
                code,
            )
        elif sc.is_viewmodel:
            code = re.sub(
                r"\bclass\s+(\w+)\s*:\s*\w*ViewModel\w*\(",
                r"// TODO: ArkTS state management\nclass \1 {",
                code,
            )
        return code

    def _transform_intent(self, code: str) -> str:
        """Android Intent → HarmonyOS Want / router."""
        # Intent(context, SomeActivity::class.java) → Want object literal
        code = re.sub(
            r'Intent\s*\(\s*\w+\s*,\s*(\w+)::class\.java\s*\)',
            lambda m: (
                f'{{bundleName: "com.example.app", '
                f'abilityName: "{m.group(1).replace("Activity", "Ability")}"}} as Want'
            ),
            code,
        )
        # intent.putExtra("key", value) → want.parameters["key"] = value
        code = re.sub(
            r'(\w+)\.putExtra\s*\(\s*("[\w.]+")\s*,\s*([^)]+)\)',
            r'\1.parameters[\2] = \3',
            code,
        )
        # intent.getStringExtra / getIntExtra / getBooleanExtra → parameters lookup
        code = re.sub(
            r'(?:getIntent\(\)|intent)\.get(?:String|Int|Boolean|Long|Float|Double)Extra\s*\(\s*("[\w.]+")\s*(?:,\s*[^)]+)?\)',
            r'(router.getParams() as Record<string, Object>)[\1]',
            code,
        )
        # startActivity(intent) → this.context.startAbility(want)
        code = re.sub(
            r'\bstartActivity\s*\(\s*(\w+)\s*\)',
            r'this.context.startAbility(\1)',
            code,
        )
        # startActivityForResult(intent, REQUEST_CODE) → TODO
        code = re.sub(
            r'\bstartActivityForResult\s*\([^)]+\)',
            r'// TODO: startAbilityForResult() — see UIAbility.startAbilityForResult()',
            code,
        )
        # finish() → this.context.terminateSelf()
        code = re.sub(
            r'\bfinish\s*\(\s*\)',
            r'this.context.terminateSelf()',
            code,
        )
        return code

    def _transform_shared_preferences(self, code: str) -> str:
        """SharedPreferences → @ohos/preferences."""
        # getSharedPreferences("name", MODE_PRIVATE) → preferences.getPreferences(context, "name")
        code = re.sub(
            r'\bgetSharedPreferences\s*\(\s*("[\w.]+")\s*,\s*\w+\s*\)',
            r'preferences.getPreferences(this.context, \1)',
            code,
        )
        # prefs.getString("key", default) → prefs.getSync("key", default) as string
        for kt_type, ts_type in [
            ('String', 'string'), ('Int', 'number'), ('Boolean', 'boolean'),
            ('Long', 'number'), ('Float', 'number'),
        ]:
            code = re.sub(
                rf'\b(\w+)\.get{kt_type}\s*\(\s*("[\w."]+")\s*,\s*([^)]+)\)',
                rf'(\1.getSync(\2, \3) as {ts_type})',
                code,
            )
        # prefs.edit().putString("key", val).apply() / .commit()
        code = re.sub(
            r'(\w+)\.edit\(\)\s*(?:\.put(?:String|Int|Boolean|Long|Float)\s*\(\s*("[\w.]+")\s*,\s*([^)]+)\)\s*)+\.(?:apply|commit)\(\)',
            lambda m: (
                f'await {m.group(1)}.put({m.group(2)}, {m.group(3)});\n'
                f'    await {m.group(1)}.flush()'
            ),
            code,
        )
        # Simpler single-call: prefs.edit().putXxx("k", v).apply()
        code = re.sub(
            r'(\w+)\.edit\(\)\.put(?:String|Int|Boolean|Long|Float)\s*\(\s*("[\w.]+")\s*,\s*([^)]+)\)\.(?:apply|commit)\(\)',
            r'await \1.put(\2, \3); await \1.flush()',
            code,
        )
        return code

    def _transform_permissions(self, code: str) -> str:
        """Android runtime permissions → abilityAccessCtrl.requestPermissionsFromUser."""
        # ActivityCompat.requestPermissions(activity, arrayOf("android.permission.X"), CODE)
        code = re.sub(
            r'ActivityCompat\.requestPermissions\s*\([^,]+,\s*(arrayOf\([^)]+\))\s*,\s*(\d+)\s*\)',
            r'// TODO: atManager.requestPermissionsFromUser(this.context, \1)\n'
            r'    //   replace android.permission.X with ohos.permission.X',
            code,
        )
        # ContextCompat.checkSelfPermission(ctx, "android.permission.X")
        code = re.sub(
            r'ContextCompat\.checkSelfPermission\s*\([^,]+,\s*("[\w."]+")\s*\)',
            r'/* TODO: atManager.checkAccessToken(tokenId, \1) */(PackageManager.PERMISSION_DENIED)',
            code,
        )
        # shouldShowRequestPermissionRationale → TODO
        code = re.sub(
            r'\bshouldShowRequestPermissionRationale\s*\([^)]+\)',
            r'/* TODO: no direct equivalent — skip or implement custom UI */ false',
            code,
        )
        # onRequestPermissionsResult → TODO comment
        code = re.sub(
            r'\boverride\s+fun\s+onRequestPermissionsResult\b',
            r'// TODO: onRequestPermissionsResult → atManager callback\n    fun onRequestPermissionsResult_UNUSED',
            code,
        )
        return code

    def _build_header(self, sc: SourceClass) -> str:
        kind = (
            "UIAbility (Activity)" if sc.is_activity else
            "@Component (Fragment)" if sc.is_fragment else
            "State Management (ViewModel)" if sc.is_viewmodel else
            "ArkTS"
        )
        return (
            f"// AUTO-CONVERTED from Android: {sc.file_path}\n"
            f"// Target: {kind}\n"
            f"// WARNING: This file requires manual review.\n"
            f"// Search for TODO comments to find unconverted sections.\n\n"
        )
