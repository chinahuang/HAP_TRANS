"""
Android Vector Drawable (XML) → SVG 转换。

Android Vector Drawable 是 SVG 的子集，主要差异：
  - 根元素 <vector> → <svg>
  - android:pathData → <path d="...">
  - android:fillColor → fill
  - android:strokeColor → stroke
  - android:strokeWidth → stroke-width
  - android:width / android:height → viewBox + width/height
  - <group> → <g transform="...">
  - <clip-path> → <clipPath>
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple

ANDROID_NS = "http://schemas.android.com/apk/res/android"


def _a(elem, name: str, default: str = "") -> str:
    return elem.get(f"{{{ANDROID_NS}}}{name}", elem.get(name, default))


def _color(val: str) -> str:
    """#AARRGGBB → #RRGGBBAA 或保持 #RRGGBB。"""
    if not val or val == "none":
        return "none"
    val = val.strip()
    if re.match(r'^#[0-9a-fA-F]{8}$', val):
        # #AARRGGBB → rgba
        a = int(val[1:3], 16) / 255
        r, g, b = val[3:5], val[5:7], val[7:9]
        return f"rgba({int(r,16)},{int(g,16)},{int(b,16)},{a:.2f})"
    return val


def _dp_to_num(val: str) -> str:
    return val.replace("dp", "").replace("px", "").strip()


class VectorTransform:

    def convert_file(self, src_path: str) -> Tuple[str, bool]:
        """
        将 Vector Drawable XML 转为 SVG 字符串。
        返回 (svg_content, success)。
        非 vector drawable 返回 ("", False)。
        """
        try:
            tree = ET.parse(src_path)
            root = tree.getroot()
        except ET.ParseError:
            return "", False

        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag != "vector":
            return "", False

        width = _dp_to_num(_a(root, "width", "24"))
        height = _dp_to_num(_a(root, "height", "24"))
        vp_width = _a(root, "viewportWidth", width)
        vp_height = _a(root, "viewportHeight", height)
        tint = _a(root, "tint", "")

        inner = self._convert_children(root)

        tint_filter = ""
        if tint:
            tint_filter = f'\n  <filter id="tint"><feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0"/></filter>'

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {vp_width} {vp_height}">'
            f'{tint_filter}'
            f'{inner}'
            f'</svg>'
        )
        return svg, True

    def convert_all(
        self,
        drawable_dirs: List[str],
        out_media_dir: str,
    ) -> Tuple[int, int]:
        """
        扫描 drawable 目录，将 vector XML 转换为 SVG，写入 out_media_dir。
        返回 (converted, failed)。
        """
        os.makedirs(out_media_dir, exist_ok=True)
        converted = 0
        failed = 0

        seen = set()
        for src_dir in drawable_dirs:
            if not os.path.isdir(src_dir):
                continue
            for fname in os.listdir(src_dir):
                if not fname.lower().endswith(".xml"):
                    continue
                if fname in seen:
                    continue
                seen.add(fname)

                src_path = os.path.join(src_dir, fname)
                svg_content, ok = self.convert_file(src_path)
                if ok:
                    dest_name = fname.replace(".xml", ".svg")
                    dest_path = os.path.join(out_media_dir, dest_name)
                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(svg_content)
                    converted += 1
                else:
                    failed += 1

        return converted, failed

    # ---------------------------------------------------------------------- #

    def _convert_children(self, parent) -> str:
        result = ""
        for child in parent:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "path":
                result += self._convert_path(child)
            elif tag == "group":
                result += self._convert_group(child)
            elif tag == "clip-path":
                result += self._convert_clip_path(child)
        return result

    def _convert_path(self, elem) -> str:
        d = _a(elem, "pathData", "")
        fill = _color(_a(elem, "fillColor", "black"))
        stroke = _color(_a(elem, "strokeColor", "none"))
        stroke_w = _a(elem, "strokeWidth", "")
        fill_type = _a(elem, "fillType", "")
        alpha = _a(elem, "fillAlpha", "")

        attrs = f'd="{d}" fill="{fill}"'
        if stroke != "none":
            attrs += f' stroke="{stroke}"'
        if stroke_w:
            attrs += f' stroke-width="{stroke_w}"'
        if fill_type == "evenOdd":
            attrs += ' fill-rule="evenodd"'
        if alpha:
            attrs += f' fill-opacity="{alpha}"'
        return f'<path {attrs}/>'

    def _convert_group(self, elem) -> str:
        rotate = _a(elem, "rotation", "")
        pivot_x = _a(elem, "pivotX", "")
        pivot_y = _a(elem, "pivotY", "")
        translate_x = _a(elem, "translateX", "")
        translate_y = _a(elem, "translateY", "")
        scale_x = _a(elem, "scaleX", "")
        scale_y = _a(elem, "scaleY", "")

        transforms = []
        if translate_x or translate_y:
            transforms.append(f"translate({translate_x or 0},{translate_y or 0})")
        if rotate:
            if pivot_x or pivot_y:
                transforms.append(f"rotate({rotate},{pivot_x or 0},{pivot_y or 0})")
            else:
                transforms.append(f"rotate({rotate})")
        if scale_x or scale_y:
            transforms.append(f"scale({scale_x or 1},{scale_y or 1})")

        inner = self._convert_children(elem)
        if transforms:
            return f'<g transform="{" ".join(transforms)}">{inner}</g>'
        return f'<g>{inner}</g>'

    def _convert_clip_path(self, elem) -> str:
        clip_id = _a(elem, "name", "clip0")
        path_data = _a(elem, "pathData", "")
        inner = self._convert_children(elem)
        return f'<clipPath id="{clip_id}"><path d="{path_data}"/>{inner}</clipPath>'
