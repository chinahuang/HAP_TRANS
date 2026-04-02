"""
将 Android res/values/ 资源转换为鸿蒙 resources/base/element/ 下的 JSON 格式。
"""
import json
import os
from parser.resource_parser import ResourceSet


class ResourceTransform:
    def transform(self, res: ResourceSet) -> dict:
        """
        返回 {
            "string.json": [...],
            "color.json": [...],
            "float.json":  [...],   # dimens
        }
        """
        return {
            "string.json": self._to_json_array(res.strings),
            "color.json": self._to_json_array(res.colors),
            "float.json": self._to_json_array(self._normalize_dimens(res.dimens)),
        }

    def write(self, output: dict, out_dir: str):
        """写入 entry/src/main/resources/base/element/。"""
        element_dir = os.path.join(
            out_dir, "entry", "src", "main", "resources", "base", "element"
        )
        os.makedirs(element_dir, exist_ok=True)

        # HarmonyOS resource JSON format: {"string": [...]} / {"color": [...]} / {"float": [...]}
        TYPE_KEY = {"string.json": "string", "color.json": "color", "float.json": "float"}
        for fname, items in output.items():
            if not items:
                continue
            path = os.path.join(element_dir, fname)
            key = TYPE_KEY.get(fname, fname.replace(".json", ""))
            with open(path, "w", encoding="utf-8") as f:
                json.dump({key: items}, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    def _to_json_array(self, mapping: dict) -> list:
        """{"key": "value"} → [{"name": "key", "value": "value"}]"""
        return [{"name": k, "value": v} for k, v in mapping.items()]

    def _normalize_dimens(self, dimens: dict) -> dict:
        """把 16dp → 16vp，16sp → 16fp。"""
        result = {}
        for k, v in dimens.items():
            if v.endswith("dp"):
                result[k] = v[:-2] + "vp"
            elif v.endswith("sp"):
                result[k] = v[:-2] + "fp"
            else:
                result[k] = v
        return result
