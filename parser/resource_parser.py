"""
解析 res/values/ 下的资源文件：strings.xml、colors.xml、dimens.xml 等。
"""
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ResourceSet:
    strings: Dict[str, str] = field(default_factory=dict)
    colors: Dict[str, str] = field(default_factory=dict)
    dimens: Dict[str, str] = field(default_factory=dict)
    string_arrays: Dict[str, List[str]] = field(default_factory=dict)
    drawables: Dict[str, str] = field(default_factory=dict)  # color drawables


class ResourceParser:
    def parse(self, values_dir: str) -> ResourceSet:
        res = ResourceSet()
        if not values_dir or not os.path.isdir(values_dir):
            return res

        for fname in os.listdir(values_dir):
            if not fname.endswith(".xml"):
                continue
            path = os.path.join(values_dir, fname)
            try:
                self._parse_file(path, res)
            except ET.ParseError as e:
                print(f"[WARN] resource parse error {path}: {e}")
        return res

    def _parse_file(self, path: str, res: ResourceSet):
        tree = ET.parse(path)
        root = tree.getroot()
        for elem in root:
            name = elem.get("name", "")
            if not name:
                continue
            tag = elem.tag
            if tag == "string":
                res.strings[name] = (elem.text or "").strip()
            elif tag == "color":
                res.colors[name] = (elem.text or "").strip()
            elif tag == "dimen":
                res.dimens[name] = (elem.text or "").strip()
            elif tag == "string-array":
                items = [item.text or "" for item in elem.findall("item")]
                res.string_arrays[name] = items
            elif tag == "drawable":
                res.drawables[name] = (elem.text or "").strip()
