"""
将 build.gradle 依赖映射为鸿蒙 oh-package.json5 依赖，
同时将 buildTypes / productFlavors 信息写入 build_variants_note.md。
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

    def write_build_variants_note(self, gradle_info: GradleInfo, out_dir: str) -> bool:
        """
        若源工程有 buildTypes 或 productFlavors，在输出目录写
        build_variants_note.md，说明如何在 HarmonyOS build-profile.json5 中复现。
        返回 True 表示有内容写出。
        """
        has_types = bool(gradle_info.build_types)
        has_flavors = bool(gradle_info.product_flavors)
        if not has_types and not has_flavors:
            return False

        lines = [
            "# Build Variants / Flavors → HarmonyOS build-profile.json5",
            "",
            "Android 工程包含以下构建变体，需在 `build-profile.json5` 中手动配置。",
            "",
        ]

        if has_types:
            lines += ["## buildTypes", ""]
            lines.append("| 名称 | minifyEnabled | debuggable | idSuffix | nameSuffix |")
            lines.append("|------|:---:|:---:|---|---|")
            for bt in gradle_info.build_types:
                lines.append(
                    f"| {bt.name} | {bt.minify_enabled} | {bt.debuggable} "
                    f"| {bt.application_id_suffix or '-'} | {bt.version_name_suffix or '-'} |"
                )
            lines += [
                "",
                "HarmonyOS 等价（在 `build-profile.json5` 的 `targets` 数组中添加）：",
                "```json5",
                "{",
                '  "targets": [',
            ]
            for bt in gradle_info.build_types:
                suffix = bt.application_id_suffix or ""
                lines += [
                    "    {",
                    f'      "name": "{bt.name}",',
                    f'      "applyToProducts": ["{bt.name}"]',
                    "    },",
                ]
            lines += ["  ]", "}", "```", ""]

        if has_flavors:
            lines += ["## productFlavors", ""]
            if gradle_info.flavor_dimensions:
                lines.append(f"flavorDimensions: `{', '.join(gradle_info.flavor_dimensions)}`")
                lines.append("")
            lines.append("| 名称 | dimension | applicationId | versionCode | versionName |")
            lines.append("|------|---|---|---|---|")
            for pf in gradle_info.product_flavors:
                lines.append(
                    f"| {pf.name} | {pf.dimension or '-'} | {pf.application_id or '-'} "
                    f"| {pf.version_code or '-'} | {pf.version_name or '-'} |"
                )
            lines += [
                "",
                "HarmonyOS 等价（在 `build-profile.json5` 的 `products` 数组中添加）：",
                "```json5",
                "{",
                '  "products": [',
            ]
            for pf in gradle_info.product_flavors:
                app_id = pf.application_id or (gradle_info.application_id + f".{pf.name}")
                lines += [
                    "    {",
                    f'      "name": "{pf.name}",',
                    f'      "bundleName": "{app_id}",',
                    f'      "versionCode": {pf.version_code or gradle_info.version_code},',
                    f'      "versionName": "{pf.version_name or gradle_info.version_name}"',
                    "    },",
                ]
            lines += ["  ]", "}", "```", ""]

        lines += [
            "## 参考文档",
            "",
            "- [HarmonyOS build-profile.json5 配置说明]"
            "(https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-hvigor-build-profile)",
        ]

        note_path = os.path.join(out_dir, "build_variants_note.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return True
