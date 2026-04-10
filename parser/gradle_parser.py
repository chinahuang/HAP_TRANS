"""
解析 build.gradle / build.gradle.kts，提取 SDK 版本和依赖列表。
"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class BuildType:
    name: str
    minify_enabled: bool = False
    debuggable: bool = False
    application_id_suffix: str = ""
    version_name_suffix: str = ""


@dataclass
class ProductFlavor:
    name: str
    dimension: str = ""
    application_id: str = ""
    version_code: int = 0
    version_name: str = ""


@dataclass
class GradleInfo:
    min_sdk: int = 21
    target_sdk: int = 33
    compile_sdk: int = 33
    application_id: str = ""
    version_code: int = 1
    version_name: str = "1.0"
    # (group, artifact, version)
    dependencies: List[Tuple[str, str, str]] = field(default_factory=list)
    build_types: List[BuildType] = field(default_factory=list)
    product_flavors: List[ProductFlavor] = field(default_factory=list)
    flavor_dimensions: List[str] = field(default_factory=list)


_RE_SDK = re.compile(r"(minSdk|targetSdk|compileSdk)\s*[=:]\s*(\d+)")
_RE_APP_ID = re.compile(r'applicationId\s*[=:]\s*["\']([^"\']+)["\']')
_RE_VERSION_CODE = re.compile(r'versionCode\s*[=:]\s*(\d+)')
_RE_VERSION_NAME = re.compile(r'versionName\s*[=:]\s*["\']([^"\']+)["\']')
_RE_DEP = re.compile(
    r'(?:implementation|api|compileOnly|runtimeOnly)\s*["\']'
    r'([^:]+):([^:]+):([^"\']+)["\']'
)
_RE_DEP_KTS = re.compile(
    r'(?:implementation|api|compileOnly|runtimeOnly)\s*\('
    r'"([^:]+):([^:]+):([^"]+)"'
    r'\)'
)
_RE_FLAVOR_DIMENSIONS = re.compile(
    r'flavorDimensions\s*[=(]\s*([^)\n]+)'
)
_RE_MINIFY = re.compile(r'minifyEnabled\s+(\w+)')
_RE_DEBUGGABLE = re.compile(r'debuggable\s+(\w+)')
_RE_APP_ID_SUFFIX = re.compile(r'applicationIdSuffix\s*[=:]\s*["\']([^"\']+)["\']')
_RE_VERSION_NAME_SUFFIX = re.compile(r'versionNameSuffix\s*[=:]\s*["\']([^"\']+)["\']')


def _extract_named_blocks(content: str, outer_keyword: str) -> List[Tuple[str, str]]:
    """
    提取 `outer_keyword { name1 { ... } name2 { ... } }` 中的命名子块。
    返回 [(name, body), ...]。
    """
    results = []
    # Find the outer block
    outer_re = re.compile(rf'\b{re.escape(outer_keyword)}\s*\{{')
    m = outer_re.search(content)
    if not m:
        return results
    start = m.end()
    depth = 1
    i = start
    outer_end = start
    while i < len(content) and depth > 0:
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                outer_end = i
        i += 1
    outer_body = content[start:outer_end]

    # Now find named sub-blocks inside
    sub_re = re.compile(r'(\w+)\s*\{')
    pos = 0
    while pos < len(outer_body):
        sm = sub_re.search(outer_body, pos)
        if not sm:
            break
        name = sm.group(1)
        # Skip Groovy/KTS keywords that are not variant names
        if name in ('getByName', 'create', 'register', 'if', 'else', 'when'):
            pos = sm.end()
            continue
        bstart = sm.end()
        bdepth = 1
        bi = bstart
        bend = bstart
        while bi < len(outer_body) and bdepth > 0:
            if outer_body[bi] == '{':
                bdepth += 1
            elif outer_body[bi] == '}':
                bdepth -= 1
                if bdepth == 0:
                    bend = bi
            bi += 1
        body = outer_body[bstart:bend]
        results.append((name, body))
        pos = bi

    return results


def _parse_version_catalog(toml_path: str) -> Dict[str, Tuple[str, str]]:
    """
    解析 gradle/libs.versions.toml，返回 {alias → (group, artifact)}。
    alias 格式：连字符转点号，例如 "androidx-room-ktx" → key "androidx.room.ktx"。
    """
    try:
        with open(toml_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return {}

    catalog: Dict[str, Tuple[str, str]] = {}
    in_libraries = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith('['):
            in_libraries = stripped.startswith('[libraries]')
            continue
        if not in_libraries or stripped.startswith('#') or not stripped:
            continue
        # alias = { module = "group:artifact", version.ref = "..." }
        m = re.match(r'(\S+)\s*=\s*\{([^}]+)\}', stripped)
        if m:
            alias = m.group(1).replace('-', '.')
            body = m.group(2)
            mod_m = re.search(r'module\s*=\s*"([^:]+):([^"]+)"', body)
            if mod_m:
                catalog[alias] = (mod_m.group(1), mod_m.group(2))
            continue
        # alias = "group:artifact:version"  (shorthand)
        m = re.match(r'(\S+)\s*=\s*"([^:]+):([^:]+):([^"]+)"', stripped)
        if m:
            alias = m.group(1).replace('-', '.')
            catalog[alias] = (m.group(2), m.group(3))
    return catalog


# libs.xxx.yyy  →  dots-separated alias reference
_RE_CATALOG_DEP = re.compile(
    r'(?:implementation|api|compileOnly|runtimeOnly)\s*\(\s*libs\.([a-zA-Z0-9_.]+)\s*\)'
)

# 从变量版本占位符中提取真实 group:artifact（丢弃版本变量）
_RE_DEP_DOLLAR = re.compile(
    r'(?:implementation|api|compileOnly|runtimeOnly)\s*["\']'
    r'([^:]+):([^:]+):\$[\w.]+["\']'
)


class GradleParser:
    def parse(self, path: str) -> GradleInfo:
        info = GradleInfo()
        if not path:
            return info
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return info

        # ── Gradle Version Catalog (libs.versions.toml) ──────────────────
        project_root = os.path.dirname(os.path.dirname(path))  # app/../
        catalog: Dict[str, Tuple[str, str]] = {}
        for toml_candidate in (
            os.path.join(project_root, "gradle", "libs.versions.toml"),
            os.path.join(os.path.dirname(path), "..", "gradle", "libs.versions.toml"),
        ):
            if os.path.isfile(toml_candidate):
                catalog = _parse_version_catalog(toml_candidate)
                # Also resolve SDK versions from [versions] section if referenced via libs
                self._resolve_sdk_from_catalog(toml_candidate, info)
                break

        for m in _RE_SDK.finditer(content):
            key, val_str = m.group(1), m.group(2)
            try:
                val = int(val_str)
                if key == "minSdk":
                    info.min_sdk = val
                elif key == "targetSdk":
                    info.target_sdk = val
                elif key == "compileSdk":
                    info.compile_sdk = val
            except ValueError:
                pass  # libs.versions.compileSdk.get().toInt() — already resolved above

        m = _RE_APP_ID.search(content)
        if m:
            info.application_id = m.group(1)

        m = _RE_VERSION_CODE.search(content)
        if m:
            info.version_code = int(m.group(1))

        m = _RE_VERSION_NAME.search(content)
        if m:
            info.version_name = m.group(1)

        # Standard string-literal deps (group:artifact:version)
        for pattern in (_RE_DEP, _RE_DEP_KTS):
            for m in pattern.finditer(content):
                dep = (m.group(1), m.group(2), m.group(3))
                if dep not in info.dependencies:
                    info.dependencies.append(dep)

        # Deps with $variable version (strip version placeholder)
        for m in _RE_DEP_DOLLAR.finditer(content):
            dep = (m.group(1), m.group(2), "*")
            if dep not in info.dependencies:
                info.dependencies.append(dep)

        # Version catalog: implementation(libs.androidx.room.ktx)
        for m in _RE_CATALOG_DEP.finditer(content):
            alias = m.group(1)
            if alias in catalog:
                group, artifact = catalog[alias]
                dep = (group, artifact, "*")
                if dep not in info.dependencies:
                    info.dependencies.append(dep)

        # flavorDimensions
        m = _RE_FLAVOR_DIMENSIONS.search(content)
        if m:
            dims_raw = m.group(1)
            info.flavor_dimensions = [
                d.strip().strip('"\'') for d in dims_raw.split(',') if d.strip().strip('"\'')
            ]

        # buildTypes { release { ... } debug { ... } }
        for name, body in _extract_named_blocks(content, "buildTypes"):
            bt = BuildType(name=name)
            mm = _RE_MINIFY.search(body)
            if mm:
                bt.minify_enabled = mm.group(1).lower() == 'true'
            mm = _RE_DEBUGGABLE.search(body)
            if mm:
                bt.debuggable = mm.group(1).lower() == 'true'
            mm = _RE_APP_ID_SUFFIX.search(body)
            if mm:
                bt.application_id_suffix = mm.group(1)
            mm = _RE_VERSION_NAME_SUFFIX.search(body)
            if mm:
                bt.version_name_suffix = mm.group(1)
            info.build_types.append(bt)

        # productFlavors { free { ... } paid { ... } }
        for name, body in _extract_named_blocks(content, "productFlavors"):
            pf = ProductFlavor(name=name)
            mm = re.search(r'dimension\s*[=:]\s*["\']([^"\']+)["\']', body)
            if mm:
                pf.dimension = mm.group(1)
            mm = _RE_APP_ID.search(body)
            if mm:
                pf.application_id = mm.group(1)
            mm = _RE_VERSION_CODE.search(body)
            if mm:
                pf.version_code = int(mm.group(1))
            mm = _RE_VERSION_NAME.search(body)
            if mm:
                pf.version_name = mm.group(1)
            info.product_flavors.append(pf)

        return info

    def _resolve_sdk_from_catalog(self, toml_path: str, info: GradleInfo) -> None:
        """从 libs.versions.toml 的 [versions] 节读取 compileSdk/minSdk/targetSdk。"""
        try:
            with open(toml_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return
        in_versions = False
        sdk_map: Dict[str, int] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('['):
                in_versions = stripped.startswith('[versions]')
                continue
            if not in_versions or stripped.startswith('#') or not stripped:
                continue
            m = re.match(r'(\w+)\s*=\s*"(\d+)"', stripped)
            if m:
                key, val = m.group(1).lower(), int(m.group(2))
                sdk_map[key] = val
        for key, attr in [
            ('compilesdk', 'compile_sdk'),
            ('minsdk', 'min_sdk'),
            ('targetsdk', 'target_sdk'),
        ]:
            if key in sdk_map:
                setattr(info, attr, sdk_map[key])
