"""
生成鸿蒙工程骨架目录结构，并写入各类转换结果。
"""
import json
import os
import shutil
from typing import Dict, List
from parser.project_scanner import ProjectInfo
from parser.kotlin_parser import SourceClass


# 鸿蒙工程顶层目录结构
OHOS_PROJECT_STRUCTURE = [
    "AppScope/resources/base/element",
    "AppScope/resources/base/media",
    "entry/src/main/ets/abilities",
    "entry/src/main/ets/pages",
    "entry/src/main/ets/components",
    "entry/src/main/ets/viewmodels",
    "entry/src/main/ets/data",
    "entry/src/main/ets/common",
    "entry/src/main/resources/base/element",
    "entry/src/main/resources/base/media",
    "entry/src/main/resources/base/profile",
]


class ProjectGenerator:
    def __init__(self, out_dir: str, project_info: ProjectInfo):
        self.out_dir = os.path.abspath(out_dir)
        self.info = project_info

    def create_skeleton(self):
        """创建鸿蒙工程目录骨架（先清理 ets/ 和 resources/ 旧内容）。"""
        # 清理上次生成的代码目录（避免遗留旧文件）
        ets_dir = os.path.join(self.out_dir, "entry", "src", "main", "ets")
        if os.path.exists(ets_dir):
            shutil.rmtree(ets_dir)

        for rel_path in OHOS_PROJECT_STRUCTURE:
            os.makedirs(os.path.join(self.out_dir, rel_path), exist_ok=True)

        self._write_build_profile()
        self._write_hvigor_config()
        self._write_root_oh_package()
        self._write_appscope_string()

    def write_converted_layouts(self, layouts: Dict[str, str]):
        """将转换后的 ArkTS 布局写入 ets/pages/ 或 ets/components/。"""
        for name, code in layouts.items():
            # 以 _frag / _item 结尾的放 components，其余放 pages
            if name.endswith(("_frag", "_item", "_header")):
                dest_dir = os.path.join(self.out_dir, "entry", "src", "main", "ets", "components")
            else:
                dest_dir = os.path.join(self.out_dir, "entry", "src", "main", "ets", "pages")
            fname = self._snake_to_pascal(name) + ".ets"
            path = os.path.join(dest_dir, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)

    def write_converted_sources(self, sources: Dict[str, str], classes: List[SourceClass]):
        """将转换后的 ArkTS 源文件写入对应目录。"""
        class_map = {sc.file_path: sc for sc in classes}
        for orig_path, code in sources.items():
            sc = class_map.get(orig_path)
            dest_dir = self._classify_source(sc)
            fname = os.path.splitext(os.path.basename(orig_path))[0] + ".ets"
            path = os.path.join(dest_dir, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)

    # ------------------------------------------------------------------
    def _classify_source(self, sc: SourceClass) -> str:
        base = os.path.join(self.out_dir, "entry", "src", "main", "ets")
        if sc is None:
            return os.path.join(base, "common")
        if sc.is_activity:
            return os.path.join(base, "abilities")
        if sc.is_fragment:
            return os.path.join(base, "components")
        if sc.is_viewmodel:
            return os.path.join(base, "viewmodels")
        if sc.is_adapter:
            return os.path.join(base, "components")
        return os.path.join(base, "common")

    def _snake_to_pascal(self, name: str) -> str:
        import re
        return "".join(w.capitalize() for w in re.split(r"[_\-]", name))

    # SDK 默认调试签名路径（DevEco Studio 自带）
    _SDK_TOOLCHAIN = (
        "C:/software/devstudio/DevEco Studio/sdk/default/openharmony/toolchains"
    )
    _SDK_P12 = _SDK_TOOLCHAIN + "/lib/OpenHarmony.p12"
    _SDK_SIGN_JAR = _SDK_TOOLCHAIN + "/lib/hap-sign-tool.jar"

    def _write_build_profile(self):
        data = {
            "app": {
                "signingConfigs": [],
                "products": [
                    {
                        "name": "default",
                        "compatibleSdkVersion": "6.0.2(22)",
                        "runtimeOS": "HarmonyOS",
                    }
                ],
                "buildModeSet": [
                    {"name": "debug"},
                    {"name": "release"},
                ],
            },
            "modules": [
                {
                    "name": "entry",
                    "srcPath": "./entry",
                    "targets": [{"name": "default", "applyToProducts": ["default"]}],
                }
            ],
        }
        path = os.path.join(self.out_dir, "build-profile.json5")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def generate_sign_script(self, bundle_name: str = "com.example.app") -> str:
        """
        生成 sign_hap.sh — 解决 9568404 "profile cert ≠ signing cert" 问题。

        根本原因：用 hap-sign-tool.jar 签名时，.p7b provision profile 内嵌的证书
        必须与实际签名用的 app cert 由同一 CA 签发，否则设备/模拟器验证失败（错误 9568404）。

        脚本流程：
          1. 用 SDK 的 OpenHarmony.p12（根 CA）颁发一个本地调试 app cert（app_debug.cer）
          2. 用同一 CA 生成一个本地调试 profile（app_debug.p7b），内嵌同一 cert
          3. 用 app cert + p12 对 .hap 文件签名

        所有证书均使用 SDK 自带 OpenHarmony.p12（密码 123456）作为 CA。
        """
        sign_jar = self._SDK_SIGN_JAR
        p12 = self._SDK_P12
        p12_pwd = "123456"
        key_alias = "OpenHarmony Application Release"

        script = f"""\
#!/usr/bin/env bash
# sign_hap.sh — 修复 9568404 profile cert ≠ signing cert 问题
# 用法: bash sign_hap.sh <path/to/unsigned.hap> [<output/signed.hap>]
# 依赖: Java (JRE 11+)，DevEco Studio SDK

set -e

UNSIGNED="${{1:?Usage: $0 unsigned.hap [signed.hap]}}"
SIGNED="${{2:-${{UNSIGNED%.hap}}_signed.hap}}"

SIGN_JAR="{sign_jar}"
P12="{p12}"
P12_PWD="{p12_pwd}"
KEY_ALIAS="{key_alias}"
BUNDLE="{bundle_name}"

WORK_DIR="$(mktemp -d)"
trap "rm -rf $WORK_DIR" EXIT

echo "[1/4] 生成调试 app cert CSR..."
java -jar "$SIGN_JAR" generate-csr \\
  -keyAlias "$KEY_ALIAS" \\
  -keyPwd "$P12_PWD" \\
  -keystoreFile "$P12" \\
  -keystorePwd "$P12_PWD" \\
  -subject "C=CN,O=OpenHarmony,OU=OpenHarmony Community,CN=$BUNDLE" \\
  -signAlg "SHA256withECDSA" \\
  -outFile "$WORK_DIR/app_debug.csr"

echo "[2/4] CA 签发调试 app cert..."
java -jar "$SIGN_JAR" sign-cert \\
  -keyAlias "$KEY_ALIAS" \\
  -keyPwd "$P12_PWD" \\
  -keystoreFile "$P12" \\
  -keystorePwd "$P12_PWD" \\
  -issuer "C=CN,O=OpenHarmony,OU=OpenHarmony Community,CN=Application Signature Service CA" \\
  -issuerKeyAlias "$KEY_ALIAS" \\
  -issuerKeyPwd "$P12_PWD" \\
  -subject "C=CN,O=OpenHarmony,OU=OpenHarmony Community,CN=$BUNDLE Debug" \\
  -validity 365 \\
  -signAlg "SHA256withECDSA" \\
  -basicConstraintsPathLen -1 \\
  -inFile "$WORK_DIR/app_debug.csr" \\
  -outFile "$WORK_DIR/app_debug.cer"

echo "[3/4] 生成调试 provision profile (.p7b)..."
java -jar "$SIGN_JAR" sign-profile \\
  -keyAlias "$KEY_ALIAS" \\
  -keyPwd "$P12_PWD" \\
  -keystoreFile "$P12" \\
  -keystorePwd "$P12_PWD" \\
  -mode "debug" \\
  -bundleName "$BUNDLE" \\
  -developmentCertificate "$WORK_DIR/app_debug.cer" \\
  -distroType "app_gallery" \\
  -signAlg "SHA256withECDSA" \\
  -outFile "$WORK_DIR/app_debug.p7b"

echo "[4/4] 签名 HAP..."
java -jar "$SIGN_JAR" sign-app \\
  -keyAlias "$KEY_ALIAS" \\
  -keyPwd "$P12_PWD" \\
  -keystoreFile "$P12" \\
  -keystorePwd "$P12_PWD" \\
  -appCertFile "$WORK_DIR/app_debug.cer" \\
  -profileFile "$WORK_DIR/app_debug.p7b" \\
  -inFile "$UNSIGNED" \\
  -outFile "$SIGNED" \\
  -signAlg "SHA256withECDSA" \\
  -compatibleVersion 9

echo "✓ 签名完成: $SIGNED"
echo "  安装到设备: hdc install \\"$SIGNED\\""
"""
        sign_path = os.path.join(self.out_dir, "sign_hap.sh")
        with open(sign_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(script)
        return sign_path

    def _write_hvigor_config(self):
        hvigor = {
            "modelVersion": "6.0.2",
            "dependencies": {
                "@ohos/hvigor-ohos-plugin": "6.22.3",
            },
        }
        path = os.path.join(self.out_dir, "hvigorconfig.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hvigor, f, indent=2)

        # hvigor/hvigor-config.json5 — required by HvigorConfigLoader for modelVersionCheck
        # Schema only allows: modelVersion, dependencies, execution, logging, debugging,
        # nodeOptions, javaOptions, parameterFile, properties
        # dependencies must be empty — listing the plugin name triggers pnpm install
        hvigor_config = {
            "modelVersion": "6.0.2",
            "dependencies": {},
            "execution": {},
            "logging": {"level": "info"},
            "debugging": {},
        }
        config_path = os.path.join(self.out_dir, "hvigor", "hvigor-config.json5")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(hvigor_config, f, indent=2)

        wrapper = {
            "hvigorVersion": "6.22.3",
            "dependencies": {
                "@ohos/hvigor-ohos-plugin": "6.22.3",
            },
        }
        path2 = os.path.join(self.out_dir, "hvigor", "hvigor-wrapper.json5")
        with open(path2, "w", encoding="utf-8") as f:
            json.dump(wrapper, f, indent=2)

    def _write_root_oh_package(self):
        data = {
            "modelVersion": "6.0.2",
            "packages": "",
            "name": self.info.package_name or "com.example.app",
            "version": "1.0.0",
            "license": "",
            "dependencies": {},
            "devDependencies": {
                "@ohos/hypium": "1.0.16",
            },
        }
        path = os.path.join(self.out_dir, "oh-package.json5")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_main_pages_profile(self):
        """生成 resources/base/profile/main_pages.json (在 write_fragment_pages 后调用)。"""
        # 由 write_fragment_pages 动态设置
        pass

    def write_fragment_pages(self, fragments: list):
        """
        为每个 Fragment 生成 @Entry @Component Page 文件，并更新 main_pages.json。

        fragments: List[SourceClass]，is_fragment=True 的类列表。
        """
        import re as _re
        pages_dir = os.path.join(self.out_dir, "entry", "src", "main", "ets", "pages")
        os.makedirs(pages_dir, exist_ok=True)

        page_routes = []
        for sc in fragments:
            # TasksFragment → TasksPage
            page_name = _re.sub(r"Fragment$", "Page", sc.class_name)
            vm_name = sc.class_name.replace("Fragment", "ViewModel")
            # 对应的 ArkUI 布局组件名
            layout_component = sc.class_name.replace("Fragment", "Frag")

            code = f"""\
// AUTO-GENERATED: Page wrapper for {sc.class_name}
// This is the @Entry page loaded by router.pushUrl({{ url: 'pages/{page_name}' }})
import {{ AppContainer }} from '../di/AppContainer';

@Entry
@Component
struct {page_name} {{
  // TODO: connect ViewModel via AppContainer
  // private vm = AppContainer.get{vm_name}();

  build() {{
    // TODO: Replace with {layout_component} component when props are wired
    Column() {{
      Text('{page_name}')
        .fontSize(24)
        .width('100%')
        .textAlign(TextAlign.Center)
        .margin({{ top: 20 }})
      // TODO: Add {layout_component}() here after integrating ViewModel state
    }}
    .width('100%')
    .height('100%')
  }}
}}
"""
            page_path = os.path.join(pages_dir, page_name + ".ets")
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(code)
            page_routes.append(f"pages/{page_name}")

        # 写 main_pages.json
        data = {"src": page_routes if page_routes else ["pages/Index"]}
        profile_path = os.path.join(
            self.out_dir, "entry", "src", "main",
            "resources", "base", "profile", "main_pages.json"
        )
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _write_appscope_string(self):
        """AppScope/resources/base/element/string.json。"""
        items = [
            {"name": "app_name", "value": self.info.app_name or "App"},
            {"name": "ability_description", "value": "Auto-converted from Android"},
        ]
        path = os.path.join(
            self.out_dir, "AppScope", "resources", "base", "element", "string.json"
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"string": items}, f, indent=2, ensure_ascii=False)

    def patch_required_resources(self):
        """
        在 ResourceTransform.write() 之后调用，补充 DevEco 必要的内置资源引用。
        若目标 JSON 中已有该名字则不重复添加。
        """
        res_base = os.path.join(
            self.out_dir, "entry", "src", "main", "resources", "base", "element"
        )

        def _load_items(path, key):
            """Load {"key": [...]} format, return inner list."""
            if not os.path.exists(path):
                return []
            data = json.load(open(path, encoding="utf-8"))
            return data.get(key, data) if isinstance(data, dict) else data

        def _save_items(path, key, items):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({key: items}, f, indent=2, ensure_ascii=False)

        # ── string.json: 补充 module_desc、ability_description、<activity_name> ──
        str_path = os.path.join(res_base, "string.json")
        existing = _load_items(str_path, "string")
        existing_names = {e["name"] for e in existing}
        required_strings = [
            {"name": "module_desc", "value": "Entry module"},
            {"name": "ability_description", "value": "Auto-converted from Android"},
        ]
        for act in self.info.activities:
            required_strings.append({"name": act.simple_name.lower(), "value": act.simple_name})
        for s in required_strings:
            if s["name"] not in existing_names:
                existing.append(s)
        _save_items(str_path, "string", existing)

        # ── color.json: 补充 start_window_background ──
        clr_path = os.path.join(res_base, "color.json")
        existing_c = _load_items(clr_path, "color")
        if not any(c["name"] == "start_window_background" for c in existing_c):
            existing_c.append({"name": "start_window_background", "value": "#FFFFFF"})
        _save_items(clr_path, "color", existing_c)

        # ── media: copy ic_launcher → app_icon.png and icon.png ──
        media_src = os.path.join(
            self.out_dir, "entry", "src", "main", "resources", "base", "media"
        )
        app_media = os.path.join(self.out_dir, "AppScope", "resources", "base", "media")
        os.makedirs(app_media, exist_ok=True)
        launcher_src = os.path.join(media_src, "ic_launcher.png")
        if os.path.exists(launcher_src):
            for icon_name in ("app_icon.png", "icon.png"):
                dest = os.path.join(app_media, icon_name)
                if not os.path.exists(dest):
                    shutil.copy2(launcher_src, dest)
            icon_entry = os.path.join(media_src, "icon.png")
            if not os.path.exists(icon_entry):
                shutil.copy2(launcher_src, icon_entry)
