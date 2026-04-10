"""
Retrofit / OkHttp / Ktor → HarmonyOS @ohos/axios / rcp 网络层转换。

主要场景：
  1. Retrofit interface + @GET/@POST/@PUT/@DELETE/@PATCH 注解
     → ArkTS 网络服务类（使用 axios）
  2. OkHttpClient / Request / Response → axios 等效写法
  3. Gson/Moshi/kotlinx.serialization → JSON.parse / JSON.stringify
  4. suspend fun apiCall(): Response<T> → async function returning T
  5. Call<T> / Deferred<T> → Promise<T>
  6. 拦截器 → axios 拦截器 TODO

策略：
  - 识别 Retrofit service interface，生成对应 ArkTS 网络服务类
  - 识别 Repository 中的网络调用模式，生成轻量包装
  - 无法自动转换的生成 // TODO 注释
"""
import re
import os
from typing import Dict, List, Tuple, Optional
from parser.kotlin_parser import SourceClass


# ─────────────────────────────────────────────────────────────────────────────
# 检测
# ─────────────────────────────────────────────────────────────────────────────

_RETROFIT_ANNOTATIONS = frozenset({
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
    "FormUrlEncoded", "Multipart", "Streaming", "HTTP",
})

_RETROFIT_IMPORTS = (
    "retrofit2", "com.squareup.retrofit2",
    "okhttp3", "com.squareup.okhttp3",
    "io.ktor",
)

_HTTP_METHOD_MAP = {
    "GET": "get",
    "POST": "post",
    "PUT": "put",
    "DELETE": "delete",
    "PATCH": "patch",
    "HEAD": "head",
}


def is_retrofit_file(sc: SourceClass) -> bool:
    return (
        any(imp.startswith(prefix) for imp in sc.imports for prefix in _RETROFIT_IMPORTS)
        or any(a in _RETROFIT_ANNOTATIONS for a in sc.annotations)
        or "interface" in sc.raw_content and "@GET" in sc.raw_content
    )


# ─────────────────────────────────────────────────────────────────────────────
# Retrofit Interface 解析
# ─────────────────────────────────────────────────────────────────────────────

# @GET("users/{id}") / @POST("tasks")
_ENDPOINT_RE = re.compile(
    r'@(GET|POST|PUT|DELETE|PATCH|HEAD)\s*\(\s*"([^"]*)"\s*\)\s*'
    r'(?:@\w+(?:\([^)]*\))?\s*)*'                    # 其他注解
    r'suspend\s+fun\s+(\w+)\s*'
    r'\(((?:[^)(]|\([^)]*\))*)\)'                    # 参数（支持嵌套括号）
    r'(?:\s*:\s*([\w<>?,\s]+))?',                    # 返回类型
    re.MULTILINE,
)

# @Path("id") / @Query("sort") / @Body task: T / @Field / @Header
# Key part is optional: @Body has no ("key"), but @Path/@Query do.
_PARAM_ANNO_RE = re.compile(
    r'@(Path|Query|Body|Field|Header|QueryMap)\s*(?:\("?(\w+)"?\))?\s+(\w+)\s*:\s*([\w<>?]+)'
)
_PARAM_SIMPLE_RE = re.compile(r'(\w+)\s*:\s*([\w<>?,\s]+)')

_KT_TYPE_MAP = {
    "String": "string", "Int": "number", "Long": "number",
    "Float": "number", "Double": "number", "Boolean": "boolean",
    "Unit": "void", "Any": "object",
    "Response": "AxiosResponse",
}


def _kt_type_to_ts(t: str) -> str:
    t = t.strip().rstrip("?")
    for k, v in _KT_TYPE_MAP.items():
        t = re.sub(rf'\b{k}\b', v, t)
    # List<T> → T[]
    t = re.sub(r'\bList<(\w+)>\?', r'\1[]', t)
    t = re.sub(r'\bList<(\w+)>', r'\1[]', t)
    # Response<T> → T
    t = re.sub(r'\bResponse<(.+)>', r'\1', t)
    # Call<T> → Promise<T> (shouldn't reach here but just in case)
    t = re.sub(r'\bCall<(.+)>', r'Promise<\1>', t)
    return t


def _parse_endpoint_params(params_raw: str) -> Tuple[List[dict], bool]:
    """
    解析参数列表，返回 (params_info, has_body)。
    params_info: [{'anno': 'Query'|'Path'|'Body'|'Field', 'key': str, 'name': str, 'ts_type': str}]
    """
    params = []
    has_body = False
    for m in _PARAM_ANNO_RE.finditer(params_raw):
        anno = m.group(1)
        key = m.group(2)
        name = m.group(3)
        ts_type = _kt_type_to_ts(m.group(4))
        params.append({"anno": anno, "key": key, "name": name, "ts_type": ts_type})
        if anno in ("Body", "Field"):
            has_body = True
    # 如果没有注解，尝试简单匹配（挂载 @Query 的参数）
    if not params:
        for m in _PARAM_SIMPLE_RE.finditer(params_raw):
            name = m.group(1)
            ts_type = _kt_type_to_ts(m.group(2))
            if name not in ("continuation",):  # 跳过 Kotlin coroutine 参数
                params.append({"anno": "Query", "key": name, "name": name, "ts_type": ts_type})
    return params, has_body


def _generate_axios_method(http_method: str, path: str, fn_name: str,
                            params: List[dict], return_type: str) -> str:
    """生成单个 axios 方法。"""
    ts_return = _kt_type_to_ts(return_type) if return_type else "any"

    # 构建参数签名
    ts_params = ", ".join(f"{p['name']}: {p['ts_type']}" for p in params)

    # 路径参数替换
    path_vars = [p for p in params if p["anno"] == "Path"]
    for pv in path_vars:
        path = path.replace(f"{{{pv['key']}}}", f"${{{pv['name']}}}")
    # 如果路径含变量就变成模板字符串
    url_expr = f"`${{this.baseUrl}}/{path}`" if "{" in path else f"`${{this.baseUrl}}/{path}`"

    # Query 参数
    query_params = [p for p in params if p["anno"] in ("Query", "QueryMap")]
    body_param = next((p for p in params if p["anno"] in ("Body", "Field")), None)

    # 构建 axios 调用
    if http_method in ("get", "delete", "head"):
        if query_params:
            params_obj = "{ " + ", ".join(f"{p['key'] or p['name']}: {p['name']}" for p in query_params) + " }"
            call = f"axios.{http_method}({url_expr}, {{ params: {params_obj} }})"
        else:
            call = f"axios.{http_method}({url_expr})"
    else:
        # Body / Field → pass as request body
        body_arg = body_param["name"] if body_param else "{}"
        if query_params:
            params_obj = "{ " + ", ".join(f"{p['key'] or p['name']}: {p['name']}" for p in query_params) + " }"
            call = f"axios.{http_method}({url_expr}, {body_arg}, {{ params: {params_obj} }})"
        else:
            call = f"axios.{http_method}({url_expr}, {body_arg})"

    return f"""\
  async {fn_name}({ts_params}): Promise<{ts_return}> {{
    const response = await {call};
    return response.data as {ts_return};
  }}"""


# ─────────────────────────────────────────────────────────────────────────────
# 主转换
# ─────────────────────────────────────────────────────────────────────────────

class RetrofitTransform:

    def transform(self, sc: SourceClass) -> Optional[str]:
        if not is_retrofit_file(sc):
            return None

        content = sc.raw_content

        # 检测 Retrofit interface 模式
        if self._is_api_interface(content):
            return self._convert_api_interface(sc)

        # Repository 中的 Retrofit 使用
        if self._has_retrofit_calls(content):
            return self._convert_repository(sc)

        # OkHttp 直接使用
        if "OkHttpClient" in content or "Request.Builder" in content:
            return self._convert_okhttp(sc)

        return None

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for sc in classes:
            code = self.transform(sc)
            if code is not None:
                result[sc.file_path] = code
        return result

    # ------------------------------------------------------------------ #

    def _is_api_interface(self, content: str) -> bool:
        return bool(re.search(r'@(GET|POST|PUT|DELETE|PATCH)\s*\(', content))

    def _has_retrofit_calls(self, content: str) -> bool:
        return bool(re.search(r'\b\w+Api\s*\.\w+\s*\(|apiService\.\w+\s*\(', content))

    # ------------------------------------------------------------------ #

    def _convert_api_interface(self, sc: SourceClass) -> str:
        name = sc.class_name
        content = sc.raw_content

        # 尝试提取 baseUrl (通常在 companion object 或 Retrofit.Builder 调用里)
        base_url_m = re.search(r'BASE_URL\s*=\s*"([^"]+)"', content)
        base_url = base_url_m.group(1).rstrip('/') if base_url_m else "https://api.example.com"

        methods = []
        for m in _ENDPOINT_RE.finditer(content):
            http_anno = m.group(1)
            path = m.group(2)
            fn_name = m.group(3)
            params_raw = m.group(4) or ""
            return_type = (m.group(5) or "Any").strip()

            http_method = _HTTP_METHOD_MAP.get(http_anno, "get")
            params, _ = _parse_endpoint_params(params_raw)
            method_code = _generate_axios_method(http_method, path, fn_name, params, return_type)
            methods.append(method_code)

        if not methods:
            methods_code = "  // TODO: No endpoints detected — add manually"
        else:
            methods_code = "\n\n".join(methods)

        # Companion object factory
        factory = f"""\
  static create(baseUrl: string = '{base_url}'): {name} {{
    return new {name}(baseUrl);
  }}"""

        return f"""\
// AUTO-CONVERTED: Retrofit interface → ArkTS axios service
// TODO: Install @ohos/axios: ohpm install @ohos/axios
import axios, {{ AxiosResponse }} from '@ohos/axios';

export class {name} {{
  private baseUrl: string;

  constructor(baseUrl: string = '{base_url}') {{
    this.baseUrl = baseUrl.replace(/\\/$/, '');
  }}

{factory}

{methods_code}
}}
"""

    def _convert_repository(self, sc: SourceClass) -> str:
        """保留 Repository 结构，仅替换 Retrofit/suspend 相关语法。"""
        name = sc.class_name
        content = sc.raw_content

        # 替换 service 调用模式：apiService.foo(bar) → await this.apiService.foo(bar)
        content = re.sub(
            r'\b(\w+(?:Api|Service|Client))\s*\.\s*(\w+)\s*\(',
            r'await this.\1.\2(',
            content,
        )
        # suspend fun → async
        content = re.sub(r'\bsuspend\s+fun\b', 'async fun', content)
        # fun → async fun (for non-suspend public methods in Repository)
        content = re.sub(r'\boverride\s+fun\b', 'async override fun', content)
        # Result.success(x) → { success: true, data: x }
        content = re.sub(
            r'\bResult\.success\s*\(([^)]+)\)',
            r'{ success: true, data: \1 }',
            content,
        )
        # Result.failure(e) → { success: false, error: e }
        content = re.sub(
            r'\bResult\.failure\s*\(([^)]+)\)',
            r'{ success: false, error: \1 }',
            content,
        )
        # try { ... } catch (e: IOException) { ... }
        content = re.sub(r'catch\s*\((\w+):\s*\w+\)', r'catch (\1: Error)', content)
        # val/var → const/let
        content = re.sub(r'\bval\s+', 'const ', content)
        content = re.sub(r'\bvar\s+', 'let ', content)

        return (
            f"// AUTO-CONVERTED: Repository network layer\n"
            f"// TODO: Replace Retrofit service injection with axios-based service\n"
            f"import axios from '@ohos/axios';\n\n"
            + content
        )

    def _convert_okhttp(self, sc: SourceClass) -> str:
        name = sc.class_name
        content = sc.raw_content

        # OkHttpClient → axios 等效
        content = re.sub(r'OkHttpClient\.Builder\(\)', 'axios.create()', content)
        content = re.sub(r'Request\.Builder\(\)', '{ url: \'\', method: \'GET\', headers: {} }', content)
        content = re.sub(r'\.url\s*\(([^)]+)\)', r'.url = \1', content)
        content = re.sub(r'\.method\s*\("([^"]+)"\s*,\s*', r'.method = "\1"; .body = ', content)
        content = re.sub(r'client\.newCall\(request\)\.execute\(\)', 'await axios.request(request)', content)
        content = re.sub(r'response\.body\?\.string\(\)', 'response.data', content)
        content = re.sub(r'response\.isSuccessful', 'response.status >= 200 && response.status < 300', content)

        return (
            f"// AUTO-CONVERTED: OkHttp → ArkTS axios\n"
            f"// TODO: Manually review OkHttp interceptors and custom TLS config\n"
            f"import axios from '@ohos/axios';\n\n"
            + content
        )
