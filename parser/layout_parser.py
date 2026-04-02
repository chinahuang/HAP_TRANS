"""
解析 Android XML 布局文件，生成布局节点树。
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ANDROID_NS = "http://schemas.android.com/apk/res/android"
APP_NS = "http://schemas.android.com/apk/res-auto"
TOOLS_NS = "http://schemas.android.com/tools"


def _clean_attr_key(key: str) -> str:
    """把 {ns}name 转成 android:name / app:name / name 的形式。"""
    if key.startswith(f"{{{ANDROID_NS}}}"):
        return "android:" + key[len(f"{{{ANDROID_NS}}}"):]
    if key.startswith(f"{{{APP_NS}}}"):
        return "app:" + key[len(f"{{{APP_NS}}}"):]
    if key.startswith(f"{{{TOOLS_NS}}}"):
        return "tools:" + key[len(f"{{{TOOLS_NS}}}"):]
    return key


@dataclass
class LayoutNode:
    tag: str                              # 原始 View 标签，如 LinearLayout
    attrs: Dict[str, str] = field(default_factory=dict)
    children: List["LayoutNode"] = field(default_factory=list)

    # 便捷属性
    @property
    def android_id(self) -> str:
        return self.attrs.get("android:id", "")

    @property
    def width(self) -> str:
        return self.attrs.get("android:layout_width", "wrap_content")

    @property
    def height(self) -> str:
        return self.attrs.get("android:layout_height", "wrap_content")

    @property
    def orientation(self) -> str:
        return self.attrs.get("android:orientation", "vertical")

    def __repr__(self):
        return f"LayoutNode({self.tag}, id={self.android_id}, children={len(self.children)})"


@dataclass
class ParsedLayout:
    file_name: str       # 不含路径，如 tasks_frag.xml
    root_node: Optional[LayoutNode] = None


class LayoutParser:
    def parse_file(self, path: str) -> ParsedLayout:
        import os
        file_name = os.path.basename(path)
        tree = ET.parse(path)
        root_elem = tree.getroot()

        # DataBinding 布局：根元素是 <layout>，真正的视图是第一个非 <data> 子元素
        root_tag = root_elem.tag.split("}")[-1] if "}" in root_elem.tag else root_elem.tag
        if root_tag == "layout":
            real_root = None
            for child in root_elem:
                child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if child_tag != "data":
                    real_root = child
                    break
            root_elem = real_root if real_root is not None else root_elem

        root_node = self._parse_elem(root_elem) if root_elem is not None else None
        return ParsedLayout(file_name=file_name, root_node=root_node)

    def parse_all(self, layout_files: List[str]) -> List[ParsedLayout]:
        results = []
        for path in layout_files:
            try:
                results.append(self.parse_file(path))
            except ET.ParseError as e:
                print(f"[WARN] layout parse error {path}: {e}")
        return results

    def _parse_elem(self, elem) -> LayoutNode:
        tag = elem.tag
        if tag.startswith("{"):
            tag = tag.split("}", 1)[1]

        attrs = {_clean_attr_key(k): v for k, v in elem.attrib.items()}
        node = LayoutNode(tag=tag, attrs=attrs)
        for child in elem:
            node.children.append(self._parse_elem(child))
        return node
