"""
Hilt / Koin DI → 手动单例注入。

策略：
  1. @HiltViewModel class Foo(...) : ViewModel()  → 生成 FooFactory 单例
  2. @Inject constructor(repo: XxxRepository)  → constructor 参数保留，
     生成对应的 getInstance() 工厂
  3. @AndroidEntryPoint class Foo : Fragment()  → 去掉注解，添加属性初始化注释
  4. @Module / @Provides / @Binds  → 生成等价的手动绑定文件 AppContainer.ets
"""
import re
from typing import List, Dict
from parser.kotlin_parser import SourceClass


RE_HILT_VM      = re.compile(r'@HiltViewModel\s*\n')
RE_ANDROID_EP   = re.compile(r'@AndroidEntryPoint\s*\n')
RE_INJECT_CTOR  = re.compile(r'@Inject\s+constructor\s*\(')
RE_BY_VIEWMODELS = re.compile(r'private val (\w+): (\w+) by viewModels\(\)')
RE_BY_ACTIVITY_VMS = re.compile(r'private val (\w+): (\w+) by activityViewModels\(\)')
RE_INJECT_FIELD = re.compile(r'@Inject\s+(?:lateinit var|var|val)\s+(\w+):\s+(\w+)')


class DITransform:

    def transform_source(self, code: str, class_name: str, is_fragment: bool) -> str:
        """对单个文件做 DI 注解清理和替换。"""

        # 1. @HiltViewModel → 注释
        code = RE_HILT_VM.sub('// @HiltViewModel (removed - use manual singleton)\n', code)

        # 2. @AndroidEntryPoint → 注释
        code = RE_ANDROID_EP.sub('// @AndroidEntryPoint (removed)\n', code)

        # 3. @Inject constructor → 普通 constructor
        code = RE_INJECT_CTOR.sub('constructor(', code)

        # 4. private val vm: FooViewModel by viewModels()
        #    → @State vm: FooViewModel = FooViewModel.getInstance()
        def replace_view_models(m):
            var_name = m.group(1)
            vm_type = m.group(2)
            return (
                f"@State private {var_name}: {vm_type} = {vm_type}.getInstance()"
            )
        code = RE_BY_VIEWMODELS.sub(replace_view_models, code)

        # 5. private val vm: FooViewModel by activityViewModels()
        #    → @State vm: FooViewModel = FooViewModel.getInstance()  (shared)
        def replace_activity_vms(m):
            var_name = m.group(1)
            vm_type = m.group(2)
            return (
                f"@State private {var_name}: {vm_type} = {vm_type}.getInstance()  // shared"
            )
        code = RE_BY_ACTIVITY_VMS.sub(replace_activity_vms, code)

        # 6. @Inject lateinit var repo: XxxRepository
        #    → private repo: XxxRepository = XxxRepository.getInstance()
        def replace_inject_field(m):
            field = m.group(1)
            ftype = m.group(2)
            return f"private {field}: {ftype} = {ftype}.getInstance()"
        code = RE_INJECT_FIELD.sub(replace_inject_field, code)

        # 7. import dagger/hilt → 移除
        code = re.sub(r'^import (?:dagger|hilt)\..*$\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'^import javax\.inject\..*$\n?', '', code, flags=re.MULTILINE)

        return code

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        results = {}
        for sc in classes:
            code = sc.raw_content
            if any(ann in code for ann in (
                "@HiltViewModel", "@AndroidEntryPoint",
                "@Inject", "by viewModels()", "by activityViewModels()",
            )):
                results[sc.file_path] = self.transform_source(
                    code, sc.class_name, sc.is_fragment
                )
        return results

    def generate_app_container(self, classes: List[SourceClass]) -> str:
        """
        生成 AppContainer.ets — 统一管理所有单例实例，
        替代 Hilt 的 @Module / @Provides。
        """
        viewmodels = [sc for sc in classes if sc.is_viewmodel]
        # Skip interfaces — only instantiate concrete classes
        repositories = [
            sc for sc in classes
            if "Repository" in sc.class_name
            and not sc.is_viewmodel
            and not re.search(r'\binterface\b', sc.raw_content)
        ]

        # Determine the concrete repository class name (prefer Default* implementations)
        concrete_repo = next(
            (sc.class_name for sc in repositories if sc.class_name.startswith("Default")),
            repositories[0].class_name if repositories else "DefaultTasksRepository"
        )

        vm_lines = []
        for sc in viewmodels:
            # Check if ViewModel needs savedStateHandle (second param)
            needs_state_handle = "savedStateHandle" in sc.raw_content or "SavedStateHandle" in sc.raw_content
            extra_args = ", new Map<string, Object>()" if needs_state_handle else ""
            vm_lines.append(
                f"  private static _{sc.class_name}: {sc.class_name} | null = null;\n"
                f"  static get{sc.class_name}(): {sc.class_name} {{\n"
                f"    if (!AppContainer._{sc.class_name}) {{\n"
                f"      AppContainer._{sc.class_name} = new {sc.class_name}(AppContainer.get{concrete_repo}(){extra_args});\n"
                f"    }}\n"
                f"    return AppContainer._{sc.class_name}!;\n"
                f"  }}"
            )

        repo_lines = []
        for sc in repositories:
            repo_lines.append(
                f"  private static _{sc.class_name}: {sc.class_name} | null = null;\n"
                f"  static get{sc.class_name}(): {sc.class_name} {{\n"
                f"    if (!AppContainer._{sc.class_name}) {{\n"
                f"      AppContainer._{sc.class_name} = new {sc.class_name}();\n"
                f"    }}\n"
                f"    return AppContainer._{sc.class_name}!;\n"
                f"  }}"
            )

        # 为 ViewModel 添加 getInstance 静态方法说明
        vm_imports = "\n".join(
            f"import {{ {sc.class_name} }} from '../viewmodels/{sc.class_name}';"
            for sc in viewmodels
        )
        repo_imports = "\n".join(
            f"import {{ {sc.class_name} }} from '../common/{sc.class_name}';"
            for sc in repositories
        )

        # Find interface repositories to add facade methods
        interface_repos = [
            sc for sc in classes
            if "Repository" in sc.class_name
            and not sc.is_viewmodel
            and re.search(r'\binterface\b', sc.raw_content)
        ]
        interface_imports = "\n".join(
            f"import {{ {sc.class_name} }} from '../common/{sc.class_name}';"
            for sc in interface_repos
        )
        # Add facade methods for interfaces (delegate to concrete impl)
        facade_lines = []
        for sc in interface_repos:
            facade_lines.append(
                f"  static get{sc.class_name}(): {sc.class_name} {{\n"
                f"    return AppContainer.get{concrete_repo}();\n"
                f"  }}"
            )

        all_methods = "\n\n".join(repo_lines + facade_lines + vm_lines)

        return f"""\
// AUTO-GENERATED: Replaces Hilt @Module / @Provides
// Manual DI container — call AppContainer.getXxx() instead of @Inject
{vm_imports}
{repo_imports}
{interface_imports}

export class AppContainer {{
{all_methods}
}}

// Usage in Fragment/Ability:
//   import {{ AppContainer }} from '../di/AppContainer';
//   const vm = AppContainer.getTasksViewModel();
"""
