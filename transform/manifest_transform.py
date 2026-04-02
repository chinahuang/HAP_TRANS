"""
将 AndroidManifest.xml 解析结果转换为鸿蒙的 module.json5 和 app.json5。
"""
import json
import os
from typing import Dict, Any
from parser.project_scanner import ProjectInfo
from parser.manifest_parser import ManifestParser


class ManifestTransform:
    def __init__(self, permission_map: Dict[str, str]):
        self.permission_map = permission_map  # Android权限 → 鸿蒙权限

    def transform(self, info: ProjectInfo) -> Dict[str, Any]:
        """
        返回 {
            "app.json5": {...},
            "module.json5": {...}
        }
        """
        app_json5 = self._build_app_json5(info)
        module_json5 = self._build_module_json5(info)
        return {
            "app.json5": app_json5,
            "module.json5": module_json5,
        }

    def _build_app_json5(self, info: ProjectInfo) -> Dict:
        return {
            "app": {
                "bundleName": info.package_name or "com.example.app",
                "vendor": "",
                "versionCode": 1,
                "versionName": "1.0.0",
                "icon": "$media:app_icon",
                "label": f"$string:{info.app_name}" if info.app_name else "$string:app_name",
            }
        }

    def _build_module_json5(self, info: ProjectInfo) -> Dict:
        abilities = []
        for act in info.activities:
            ability = {
                "name": act.simple_name,
                "srcEntry": f"./ets/abilities/{act.simple_name}.ets",
                "description": "$string:ability_description",
                "icon": "$media:icon",
                "label": act.label or f"$string:{act.simple_name.lower()}",
                "startWindowIcon": "$media:icon",
                "startWindowBackground": "$color:start_window_background",
                "exported": True,
            }
            if act.is_launcher:
                ability["skills"] = [
                    {
                        "entities": ["entity.system.home"],
                        "actions": ["ohos.want.action.home"],
                    }
                ]
            abilities.append(ability)

        # 权限映射
        req_permissions = []
        for perm in info.permissions:
            mapped = self.permission_map.get(perm, perm)
            req_permissions.append({"name": mapped})

        return {
            "module": {
                "name": "entry",
                "type": "entry",
                "description": "$string:module_desc",
                "mainElement": abilities[0]["name"] if abilities else "MainAbility",
                "deviceTypes": ["phone"],
                "deliveryWithInstall": True,
                "installationFree": False,
                "pages": "$profile:main_pages",
                "abilities": abilities,
                "requestPermissions": req_permissions,
            }
        }

    def write(self, output: Dict[str, Any], out_dir: str):
        """将转换结果写入文件。"""
        app_dir = os.path.join(out_dir, "AppScope")
        module_dir = os.path.join(out_dir, "entry", "src", "main")
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(module_dir, exist_ok=True)

        self._write_json5(output["app.json5"], os.path.join(app_dir, "app.json5"))
        self._write_json5(output["module.json5"], os.path.join(module_dir, "module.json5"))

    def _write_json5(self, data: Dict, path: str):
        # JSON5 与 JSON 格式兼容，这里用标准 JSON 输出（鸿蒙工具链可读）
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
