"""
对 Kotlin/Java 源文件做轻量级静态分析（基于正则，非完整 AST）。
提取：类名、父类、implements、import、生命周期方法、关键注解。
"""
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SourceClass:
    file_path: str
    class_name: str
    super_class: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    annotations: List[str] = field(default_factory=list)
    lifecycle_methods: List[str] = field(default_factory=list)
    is_activity: bool = False
    is_fragment: bool = False
    is_viewmodel: bool = False
    is_adapter: bool = False
    raw_content: str = ""


LIFECYCLE_METHODS = [
    "onCreate", "onStart", "onResume", "onPause",
    "onStop", "onDestroy", "onCreateView", "onViewCreated",
    "onActivityCreated", "onDestroyView",
]

_RE_CLASS = re.compile(
    r"(?:^|\n)\s*(?:(?:open|abstract|data|sealed|inner|enum)\s+)*"
    r"(?:class|object|interface)\s+(\w+)"
    r"(?:\s*@\w+(?:\([^)]*\))?\s+constructor\s*)?"  # @JvmOverloads constructor
    r"(?:\s*[<(][^{]*)?"
    r"(?:\s*:\s*([^{]+))?"
    r"\s*\{",
    re.MULTILINE,
)
_RE_IMPORT = re.compile(r"^import\s+([\w.]+)", re.MULTILINE)
_RE_ANNOTATION = re.compile(r"@(\w+)", re.MULTILINE)
_RE_LIFECYCLE = re.compile(
    r"(?:override\s+fun|@Override\s+(?:public\s+)?void)\s+(" +
    "|".join(LIFECYCLE_METHODS) + r")\s*\(",
)


class KotlinParser:
    def parse_file(self, path: str) -> Optional[SourceClass]:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return None

        m = _RE_CLASS.search(content)
        if not m:
            return None

        class_name = m.group(1)
        parent_raw = m.group(2) or ""
        parents = [p.strip().split("(")[0].split("<")[0].strip() for p in parent_raw.split(",") if p.strip()]

        imports = _RE_IMPORT.findall(content)
        annotations = list(set(_RE_ANNOTATION.findall(content)))
        lifecycle = list(set(_RE_LIFECYCLE.findall(content)))

        sc = SourceClass(
            file_path=path,
            class_name=class_name,
            imports=imports,
            annotations=annotations,
            lifecycle_methods=lifecycle,
            raw_content=content,
        )

        if parents:
            sc.super_class = parents[0]
            sc.interfaces = parents[1:]

        sc.is_activity = self._inherits(parents, imports, ("Activity", "AppCompatActivity", "ComponentActivity"))
        sc.is_fragment = self._inherits(parents, imports, ("Fragment", "DialogFragment", "BottomSheetDialogFragment"))
        sc.is_viewmodel = self._inherits(parents, imports, ("ViewModel", "AndroidViewModel"))
        sc.is_adapter = self._inherits(parents, imports, ("RecyclerView.Adapter", "ListAdapter", "BaseAdapter"))

        return sc

    def parse_all(self, source_files: List[str]) -> List[SourceClass]:
        results = []
        for path in source_files:
            sc = self.parse_file(path)
            if sc:
                results.append(sc)
        return results

    def _inherits(self, parents: List[str], imports: List[str], targets) -> bool:
        for p in parents:
            for t in targets:
                if p == t or p.endswith(t):
                    return True
        for imp in imports:
            for t in targets:
                if imp.endswith(t):
                    return True
        return False
