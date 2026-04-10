"""
将 build.gradle 依赖映射为鸿蒙 oh-package.json5 依赖。
"""
import json
import os
from typing import Dict, List, Tuple
from parser.gradle_parser import GradleInfo


class GradleTransform:
    def __init__(self, dependency_map: Dict[str, str]):
        # "androidx.room:room-runtime" → "@ohos/relationalStore"
        self.dependency_map = dependency_map

    def transform(self, gradle_info: GradleInfo) -> Dict:
        """返回 oh-package.json5 内容（dict）。"""
        deps = {}
        unmapped: List[Tuple[str, str, str]] = []

        for group, artifact, version in gradle_info.dependencies:
            key = f"{group}:{artifact}"
            if key in self.dependency_map:
                ohos_pkg = self.dependency_map[key]
                if ohos_pkg == "builtin":
                    pass  # HarmonyOS 内置支持，无需额外包，计为已映射
                elif ohos_pkg:
                    deps[ohos_pkg] = "*"
                # 空字符串：无对应包，计为未映射
                else:
                    unmapped.append((group, artifact, version))
            else:
                unmapped.append((group, artifact, version))

        result = {
            "name": "entry",
            "version": "1.0.0",
            "description": "Auto-converted from Android",
            "main": "index.ets",
            "author": "",
            "license": "",
            "dependencies": deps,
        }
        if unmapped:
            result["_unmapped_android_deps"] = [
                f"{g}:{a}:{v}" for g, a, v in unmapped
            ]
        return result

    def write(self, output: Dict, out_dir: str):
        entry_dir = os.path.join(out_dir, "entry")
        os.makedirs(entry_dir, exist_ok=True)
        path = os.path.join(entry_dir, "oh-package.json5")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
