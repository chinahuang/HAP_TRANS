"""
将 Android drawable/ 和 mipmap/ 图片资源复制到鸿蒙 resources/base/media/。
对于 Vector Drawable（XML），记录为待手动处理的 warning。
"""
import os
import shutil
from typing import List, Tuple


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".9.png"}
VECTOR_SUFFIX = ".xml"


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

                # 向量图（XML）→ 跳过并记录 warning
                if fname.lower().endswith(VECTOR_SUFFIX):
                    if fname not in seen:
                        self.warnings.append(
                            f"Vector drawable needs manual conversion: {src_path}"
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
