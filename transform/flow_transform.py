"""
Flow / StateFlow / SharedFlow → ArkTS @State / @Watch 转换。

作用范围：Activity / Fragment 等 UI 层文件（ViewModel 由 ViewModelTransform 处理）。

主要模式：
  viewLifecycleOwner.lifecycleScope.launch {
      viewModel.uiState.collect { state -> ... }
  }
  → // TODO: observe uiState with @Watch or @State binding

  val xxx by viewModel.xxx.collectAsState() → @State xxx: T (ComposeTransform 处理)

  repeatOnLifecycle / launchWhenStarted → 简化为直接 async block
"""
import re
from typing import List


# lifecycleScope.launch { ... .collect { ... } }
_LIFECYCLE_COLLECT = re.compile(
    r'(?:viewLifecycleOwner\.)?lifecycleScope\.launch\s*\{([^}]*'
    r'(?:\{[^}]*\}[^}]*)*)\}',
    re.DOTALL,
)

# repeatOnLifecycle(Lifecycle.State.X) { ... }
_REPEAT_LIFECYCLE = re.compile(
    r'repeatOnLifecycle\s*\([^)]+\)\s*\{',
    re.DOTALL,
)

# launchWhenStarted { } / launchWhenResumed { }
_LAUNCH_WHEN = re.compile(
    r'(?:lifecycleScope\.)?launchWhen\w+\s*\{',
)

# xxx.collect { state -> ... }
_COLLECT_BLOCK = re.compile(
    r'(\w+(?:\.\w+)*)\.collect(?:Latest)?\s*\{\s*(?:(\w+)\s*->\s*)?',
)

# xxx.collectIn(scope) { ... }  (collectIn extension)
_COLLECT_IN = re.compile(
    r'(\w+(?:\.\w+)*)\.collect(?:In|WithLifecycle)\s*\([^)]*\)\s*\{[^}]*\}',
)

# Kotlin flow: observe(viewLifecycleOwner) { ... } (LiveData)
_OBSERVE_LD = re.compile(
    r'(\w+)\.observe\s*\(\s*(?:this|viewLifecycleOwner)\s*\)\s*\{',
)


class FlowTransform:
    """对 UI 层（Activity / Fragment）文件中的 Flow 订阅模式做轻量转换。"""

    def transform(self, code: str) -> str:
        # 1. repeatOnLifecycle { ... } → 去掉包装，保留内部代码
        code = self._strip_repeat_on_lifecycle(code)

        # 2. launchWhenStarted/Resumed/Created → 去掉包装
        code = _LAUNCH_WHEN.sub('/* launchWhen removed */ {', code)

        # 3. lifecycleScope.launch { ... } → // TODO: setup observation
        code = _LIFECYCLE_COLLECT.sub(self._replace_lifecycle_launch, code)

        # 4. 直接 xxx.collect { state -> ... } → @Watch TODO
        code = _COLLECT_BLOCK.sub(self._replace_collect, code)

        # 5. collectIn / collectWithLifecycle → TODO
        code = _COLLECT_IN.sub(
            lambda m: f"// TODO: observe {m.group(1)} — use @Watch or AppStorage",
            code,
        )

        # 6. LiveData observe → TODO (if not already converted by KotlinTransform)
        code = _OBSERVE_LD.sub(
            lambda m: f"// TODO: observe {m.group(1)} — use @Watch\n      // {{",
            code,
        )

        # 7. flowOf(...) / emptyFlow() → 移除残余
        code = re.sub(r'\bflowOf\b', '/* flowOf */', code)
        code = re.sub(r'\bemptyFlow\s*<[^>]+>\s*\(\)', '[]', code)

        # 8. 去掉 Dispatchers.X 参数
        code = re.sub(r',?\s*Dispatchers\.\w+', '', code)

        return code

    def transform_all(self, sources: dict) -> dict:
        return {path: self.transform(code) for path, code in sources.items()}

    # ------------------------------------------------------------------ #

    def _strip_repeat_on_lifecycle(self, code: str) -> str:
        """repeatOnLifecycle(...) { body } → body (remove wrapper)."""
        result = []
        i = 0
        n = len(code)
        for m in _REPEAT_LIFECYCLE.finditer(code):
            result.append(code[i:m.start()])
            result.append('/* repeatOnLifecycle */ {')
            i = m.end()
        result.append(code[i:])
        return ''.join(result)

    def _replace_lifecycle_launch(self, m: re.Match) -> str:
        inner = m.group(1).strip()
        # Check if it contains .collect call
        if '.collect' in inner:
            # Extract what is being collected
            cm = _COLLECT_BLOCK.search(inner)
            if cm:
                flow_name = cm.group(1)
                param = cm.group(2) or 'state'
                return (
                    f"// TODO: observe {flow_name} changes\n"
                    f"      // Replace with @Watch or AppStorage subscription\n"
                    f"      // Original: {flow_name}.collect {{ {param} -> ... }}"
                )
        # Generic launch block without collect
        return '// TODO: migrate lifecycleScope.launch block\n' + inner

    def _replace_collect(self, m: re.Match) -> str:
        flow_expr = m.group(1)
        param = m.group(2) or 'value'
        return (
            f"// TODO: @Watch {flow_expr} — observe changes\n"
            f"      // Original: {flow_expr}.collect {{ {param} -> {{"
        )
