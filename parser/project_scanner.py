"""
扫描 Android 工程结构，收集所有需要转换的文件路径。
支持单模块工程和多模块工程（读取 settings.gradle 获取子模块列表）。
"""
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ActivityInfo:
    name: str           # 完整类名，如 com.example.tasks.TasksActivity
    simple_name: str    # 简单类名，如 TasksActivity
    is_launcher: bool = False
    label: str = ""


@dataclass
class ProjectInfo:
    root: str                          # Android 工程根目录
    app_module: str                    # app 模块目录
    package_name: str = ""
    app_name: str = ""
    min_sdk: int = 21
    target_sdk: int = 33
    # 文件路径列表
    manifest_path: str = ""
    source_files: List[str] = field(default_factory=list)   # .kt / .java
    layout_files: List[str] = field(default_factory=list)   # res/layout/*.xml
    drawable_dirs: List[str] = field(default_factory=list)  # drawable*/ 目录
    mipmap_dirs: List[str] = field(default_factory=list)    # mipmap*/ 目录
    values_dir: str = ""                                    # res/values/
    build_gradle: str = ""                                  # build.gradle(.kts)
    # 多模块扩展
    extra_modules: List[str] = field(default_factory=list)  # 非 app 模块目录列表
    # 解析结果
    activities: List[ActivityInfo] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)


class ProjectScanner:
    """扫描 Android 工程，返回 ProjectInfo。支持多模块工程。"""

    def scan(self, root: str) -> ProjectInfo:
        root = os.path.abspath(root)
        app_module = self._find_app_module(root)
        info = ProjectInfo(root=root, app_module=app_module)

        src_main = os.path.join(app_module, "src", "main")

        info.manifest_path = self._find_file(src_main, "AndroidManifest.xml")
        info.build_gradle = self._find_build_gradle(app_module)
        info.source_files = self._collect_source_files(src_main)
        info.layout_files = self._collect_layout_files(src_main)
        info.drawable_dirs = self._collect_res_dirs(src_main, "drawable")
        info.mipmap_dirs = self._collect_res_dirs(src_main, "mipmap")
        info.values_dir = os.path.join(src_main, "res", "values")

        # ── 多模块支持 ──────────────────────────────────────────────
        extra_modules = self._find_extra_modules(root, app_module)
        info.extra_modules = extra_modules
        for mod_dir in extra_modules:
            mod_src_main = os.path.join(mod_dir, "src", "main")
            if not os.path.isdir(mod_src_main):
                continue
            info.source_files.extend(self._collect_source_files(mod_src_main))
            info.layout_files.extend(self._collect_layout_files(mod_src_main))
            info.drawable_dirs.extend(self._collect_res_dirs(mod_src_main, "drawable"))
            info.mipmap_dirs.extend(self._collect_res_dirs(mod_src_main, "mipmap"))
            # 合并 values 资源（字符串/颜色等）
            mod_values = os.path.join(mod_src_main, "res", "values")
            if not info.values_dir and os.path.isdir(mod_values):
                info.values_dir = mod_values

        # 去重（同一文件可能被多路径收集到）
        info.source_files = list(dict.fromkeys(info.source_files))
        info.layout_files = list(dict.fromkeys(info.layout_files))
        info.drawable_dirs = list(dict.fromkeys(info.drawable_dirs))
        info.mipmap_dirs = list(dict.fromkeys(info.mipmap_dirs))

        return info

    # ------------------------------------------------------------------
    def _find_extra_modules(self, root: str, app_module: str) -> List[str]:
        """
        读取 settings.gradle(.kts)，返回除 app 模块外的所有库/特性模块目录。
        支持 Groovy 和 Kotlin DSL 两种写法：
          include ':core:data', ':feature:tasks'  (Groovy)
          include(":core:data", ":feature:tasks")  (KTS)
        """
        settings_paths = [
            os.path.join(root, "settings.gradle.kts"),
            os.path.join(root, "settings.gradle"),
        ]
        settings_content = ""
        for p in settings_paths:
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8", errors="replace") as f:
                        settings_content = f.read()
                except OSError:
                    pass
                break

        if not settings_content:
            return []

        # 从 include 语句中提取模块路径
        # 匹配 include ':core:data', ':feature:tasks' 或 include(":core:data")
        module_re = re.compile(r'["\']:([a-zA-Z0-9_:/.-]+)["\']')
        modules = []
        for line in settings_content.splitlines():
            line = line.strip()
            if not line.startswith("include"):
                continue
            for m in module_re.finditer(line):
                module_path = m.group(1).replace(":", os.sep)
                module_dir = os.path.join(root, module_path)
                if (os.path.isdir(module_dir)
                        and os.path.abspath(module_dir) != os.path.abspath(app_module)):
                    modules.append(module_dir)

        return modules

    def _find_app_module(self, root: str) -> str:
        """找 app 模块目录（含 AndroidManifest.xml 的子目录）。"""
        for name in ("app", "application"):
            candidate = os.path.join(root, name)
            manifest = os.path.join(candidate, "src", "main", "AndroidManifest.xml")
            if os.path.isfile(manifest):
                return candidate
        # fallback: 在子目录中搜索
        for entry in os.scandir(root):
            if entry.is_dir():
                manifest = os.path.join(entry.path, "src", "main", "AndroidManifest.xml")
                if os.path.isfile(manifest):
                    return entry.path
        return root

    def _find_file(self, base: str, name: str) -> str:
        for dirpath, _, files in os.walk(base):
            if name in files:
                return os.path.join(dirpath, name)
        return ""

    def _find_build_gradle(self, app_module: str) -> str:
        for name in ("build.gradle.kts", "build.gradle"):
            path = os.path.join(app_module, name)
            if os.path.isfile(path):
                return path
        return ""

    # 跳过测试目录（src/test/ 和 src/androidTest/）
    _TEST_DIR_NAMES = frozenset({"test", "androidTest", "testDebug", "testRelease"})

    def _collect_source_files(self, src_main: str) -> List[str]:
        """收集 src/main 下的 .kt/.java 文件，跳过 test 目录。"""
        result = []
        # src_main == .../src/main — 直接搜索 java/ kotlin/ 子树
        java_root = os.path.join(src_main, "java")
        kotlin_root = os.path.join(src_main, "kotlin")
        for base in (java_root, kotlin_root):
            if not os.path.isdir(base):
                continue
            for dirpath, dirs, files in os.walk(base):
                # Prune test sub-directories (in-place) so os.walk skips them
                dirs[:] = [d for d in dirs if d not in self._TEST_DIR_NAMES]
                for f in files:
                    if f.endswith((".kt", ".java")):
                        result.append(os.path.join(dirpath, f))

        # Also explicitly skip if caller accidentally passes src/ instead of src/main/
        # by checking sibling test directories
        src_root = os.path.dirname(src_main)
        for test_dir_name in self._TEST_DIR_NAMES:
            test_dir = os.path.join(src_root, test_dir_name)
            if os.path.isdir(test_dir):
                # Remove any accidentally included test files
                result = [p for p in result if not p.startswith(test_dir)]

        return result

    def _collect_layout_files(self, src_main: str) -> List[str]:
        result = []
        layout_root = os.path.join(src_main, "res")
        if not os.path.isdir(layout_root):
            return result
        for entry in os.scandir(layout_root):
            if entry.is_dir() and entry.name.startswith("layout"):
                for dirpath, _, files in os.walk(entry.path):
                    for f in files:
                        if f.endswith(".xml"):
                            result.append(os.path.join(dirpath, f))
        return result

    def _collect_res_dirs(self, src_main: str, prefix: str) -> List[str]:
        result = []
        res_root = os.path.join(src_main, "res")
        if not os.path.isdir(res_root):
            return result
        for entry in os.scandir(res_root):
            if entry.is_dir() and entry.name.startswith(prefix):
                result.append(entry.path)
        return result
