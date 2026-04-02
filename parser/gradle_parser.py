"""
解析 build.gradle / build.gradle.kts，提取 SDK 版本和依赖列表。
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class GradleInfo:
    min_sdk: int = 21
    target_sdk: int = 33
    compile_sdk: int = 33
    application_id: str = ""
    # (group, artifact, version)
    dependencies: List[Tuple[str, str, str]] = field(default_factory=list)


_RE_SDK = re.compile(r"(minSdk|targetSdk|compileSdk)\s*[=:]\s*(\d+)")
_RE_APP_ID = re.compile(r'applicationId\s*[=:]\s*["\']([^"\']+)["\']')
_RE_DEP = re.compile(
    r'(?:implementation|api|compileOnly|runtimeOnly)\s*["\']'
    r'([^:]+):([^:]+):([^"\']+)["\']'
)
_RE_DEP_KTS = re.compile(
    r'(?:implementation|api|compileOnly|runtimeOnly)\s*\('
    r'"([^:]+):([^:]+):([^"]+)"'
    r'\)'
)


class GradleParser:
    def parse(self, path: str) -> GradleInfo:
        info = GradleInfo()
        if not path:
            return info
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return info

        for m in _RE_SDK.finditer(content):
            key, val = m.group(1), int(m.group(2))
            if key == "minSdk":
                info.min_sdk = val
            elif key == "targetSdk":
                info.target_sdk = val
            elif key == "compileSdk":
                info.compile_sdk = val

        m = _RE_APP_ID.search(content)
        if m:
            info.application_id = m.group(1)

        for pattern in (_RE_DEP, _RE_DEP_KTS):
            for m in pattern.finditer(content):
                info.dependencies.append((m.group(1), m.group(2), m.group(3)))

        return info
