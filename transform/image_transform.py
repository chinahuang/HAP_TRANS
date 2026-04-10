"""
将 Android drawable/ 和 mipmap/ 图片资源复制到鸿蒙 resources/base/media/。
对于 Vector Drawable（XML），由 VectorTransform 处理；
对于 selector/color 等状态选择器 XML，静默跳过（HarmonyOS 用 ArkTS 样式替代）。
"""
import os
import shutil
import xml.etree.ElementTree as ET
from typing import List, Tuple


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".9.png"}
VECTOR_SUFFIX = ".xml"

# 这些根元素类型由引擎其他部分处理或在 HarmonyOS 中无需对应文件
_SILENT_SKIP_TAGS = {"selector", "color", "shape", "layer-list", "transition",
                     "animated-selector", "ripple", "inset", "rotate", "scale",
                     "animation-list", "level-list"}


def _xml_root_tag(path: str) -> str:
    """返回 XML 文件的根元素标签名（不含命名空间），解析失败返回空字符串。"""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        return tag
    except ET.ParseError:
        return ""


class ImageTransform:
    def __init__(self):
        self.warnings: List[str] = []

    def transform(
        self,
        drawable_dirs: List[str],
        mipmap_dirs: List[str],
        out_dir: str,
    ) -> Tuple[int, int]:
        """
        将图片资源复制到 entry/src/main/resources/base/media/。
        返回 (copied_count, skipped_count)。
        """
        media_dir = os.path.join(
            out_dir, "entry", "src", "main", "resources", "base", "media"
        )
        os.makedirs(media_dir, exist_ok=True)

        copied = 0
        skipped = 0
        seen = set()

        for src_dir in drawable_dirs + mipmap_dirs:
            if not os.path.isdir(src_dir):
                continue
            for fname in os.listdir(src_dir):
                src_path = os.path.join(src_dir, fname)
                if not os.path.isfile(src_path):
                    continue

                # XML 文件：按根元素类型决定处理方式
                if fname.lower().endswith(VECTOR_SUFFIX):
                    if fname not in seen:
                        root_tag = _xml_root_tag(src_path)
                        if root_tag == "vector":
                            # 由 VectorTransform 处理，这里只计跳过数
                            pass
                        elif root_tag in _SILENT_SKIP_TAGS:
                            # selector/shape 等：HarmonyOS 用 ArkTS 样式替代，静默跳过
                            pass
                        elif root_tag:
                            # 未知 XML 类型才报 warning
                            self.warnings.append(
                                f"Unknown drawable XML (root=<{root_tag}>), needs manual conversion: {src_path}"
                            )
                        seen.add(fname)
                    skipped += 1
                    continue

                # 普通图片 → 复制（去重，使用 xxhdpi 优先级）
                ext = ""
                for e in IMAGE_EXTS:
                    if fname.lower().endswith(e):
                        ext = e
                        break
                if not ext:
                    continue

                dest_path = os.path.join(media_dir, fname)
                # 优先保留 xxhdpi 版本（目录名包含 xxhdpi）
                dir_name = os.path.basename(src_dir)
                priority = "xxhdpi" in dir_name or "xxxhdpi" in dir_name
                if fname not in seen or priority:
                    shutil.copy2(src_path, dest_path)
                    seen.add(fname)
                    copied += 1

        return copied, skipped
