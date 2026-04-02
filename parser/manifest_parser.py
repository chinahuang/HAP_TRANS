"""
解析 AndroidManifest.xml，提取 package、Activity、权限等信息。
"""
import xml.etree.ElementTree as ET
from typing import List
from .project_scanner import ProjectInfo, ActivityInfo

ANDROID_NS = "http://schemas.android.com/apk/res/android"


def _attr(elem, name: str, default: str = "") -> str:
    return elem.get(f"{{{ANDROID_NS}}}{name}", elem.get(name, default))


class ManifestParser:
    def parse(self, info: ProjectInfo) -> ProjectInfo:
        if not info.manifest_path:
            return info
        tree = ET.parse(info.manifest_path)
        root = tree.getroot()

        info.package_name = root.get("package", "")
        app_elem = root.find("application")
        if app_elem is not None:
            label = _attr(app_elem, "label", "")
            info.app_name = label.lstrip("@string/")

        # 权限
        info.permissions = [
            _attr(p, "name")
            for p in root.findall("uses-permission")
            if _attr(p, "name")
        ]

        # Activity
        if app_elem is not None:
            for act in app_elem.findall("activity"):
                name = _attr(act, "name", "")
                if not name:
                    continue
                # 补全包名
                if name.startswith("."):
                    name = info.package_name + name
                simple_name = name.rsplit(".", 1)[-1]
                is_launcher = self._is_launcher(act)
                label = _attr(act, "label", "")
                info.activities.append(
                    ActivityInfo(
                        name=name,
                        simple_name=simple_name,
                        is_launcher=is_launcher,
                        label=label,
                    )
                )
        return info

    def _is_launcher(self, act_elem) -> bool:
        for intent_filter in act_elem.findall("intent-filter"):
            for action in intent_filter.findall("action"):
                if _attr(action, "name") == "android.intent.action.MAIN":
                    return True
        return False
