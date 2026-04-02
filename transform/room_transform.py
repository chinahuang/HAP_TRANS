"""
Room → HarmonyOS RelationalStore 转换。

处理三类 Room 组件：
  1. @Entity class → ArkTS interface + CREATE TABLE DDL
  2. @Dao interface  → ArkTS RdbStore 操作类
  3. @Database class → ArkTS DatabaseManager 单例
"""
import re
import os
from typing import List, Dict, Tuple, Optional
from parser.kotlin_parser import SourceClass


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #

KOTLIN_TO_ARKTS_TYPE = {
    "String": "string",
    "Int": "number",
    "Long": "number",
    "Double": "number",
    "Float": "number",
    "Boolean": "boolean",
    "ByteArray": "Uint8Array",
}

def _kt_type(t: str) -> str:
    t = t.strip().rstrip("?")
    return KOTLIN_TO_ARKTS_TYPE.get(t, t)

def _column_sql_type(t: str) -> str:
    t = t.strip().rstrip("?")
    if t in ("String",):
        return "TEXT"
    if t in ("Int", "Long"):
        return "INTEGER"
    if t in ("Double", "Float"):
        return "REAL"
    if t in ("Boolean",):
        return "INTEGER"  # 0/1
    return "TEXT"


# --------------------------------------------------------------------------- #
# @Entity 解析
# --------------------------------------------------------------------------- #

RE_ENTITY_TABLE = re.compile(r'@Entity\s*\(\s*tableName\s*=\s*"([^"]+)"', re.DOTALL)
RE_COLUMN_INFO   = re.compile(r'@ColumnInfo\s*\(\s*name\s*=\s*"([^"]+)"\s*\)', re.DOTALL)
RE_PRIMARY_KEY   = re.compile(r'@PrimaryKey')
RE_FIELD         = re.compile(
    r'(?:val|var)\s+(\w+)\s*:\s*([\w<>?,\s]+?)(?:\s*=\s*[^\n,)]+)?(?=[,\n)])',
)


class EntityInfo:
    def __init__(self):
        self.class_name: str = ""
        self.table_name: str = ""
        self.fields: List[Dict] = []  # {name, kotlin_type, column_name, is_primary}


def _parse_entity(sc: SourceClass) -> Optional[EntityInfo]:
    code = sc.raw_content
    if "@Entity" not in code:
        return None

    info = EntityInfo()
    info.class_name = sc.class_name

    m = RE_ENTITY_TABLE.search(code)
    info.table_name = m.group(1) if m else sc.class_name.lower() + "s"

    # 只解析构造函数参数内的字段（真正的 DB 列）
    # 跳过类体内的计算属性（val foo get() = ...）
    # 找构造函数参数区间：class Foo(...) { 或 class Foo @Ann constructor(...) {
    ctor_m = re.search(
        r'(?:class\s+\w+\s*(?:@\w+(?:\([^)]*\))?\s+constructor\s*)?\()(.*?)(?:\)\s*(?::\s*\w+[^{]*)?\{)',
        code,
        re.DOTALL,
    )

    if ctor_m:
        ctor_body = ctor_m.group(1)
        pending_col: Optional[str] = None
        pending_pk = False
        # 逐行解析构造函数参数
        for line in ctor_body.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            col_m = RE_COLUMN_INFO.search(stripped)
            if col_m:
                pending_col = col_m.group(1)
            if RE_PRIMARY_KEY.search(stripped):
                pending_pk = True
            field_m = re.search(r'(?:val|var)\s+(\w+)\s*:\s*([\w<>?]+)', stripped)
            if field_m:
                fname = field_m.group(1)
                ftype = field_m.group(2).rstrip("?")
                # 跳过 @Ignore 字段
                if "@Ignore" not in stripped:
                    info.fields.append({
                        "name": fname,
                        "kotlin_type": ftype,
                        "column_name": pending_col or fname,
                        "is_primary": pending_pk,
                    })
                pending_col = None
                pending_pk = False
    else:
        # fallback：旧逻辑，但跳过计算属性（含 get() 的行）
        pending_col = None
        pending_pk = False
        for line in code.split("\n"):
            stripped = line.strip()
            if "get()" in stripped or "get =" in stripped:
                pending_col = None
                pending_pk = False
                continue
            col_m = RE_COLUMN_INFO.search(stripped)
            if col_m:
                pending_col = col_m.group(1)
            if RE_PRIMARY_KEY.search(stripped):
                pending_pk = True
            field_m = re.search(r'(?:val|var)\s+(\w+)\s*:\s*([\w<>?]+)', stripped)
            if field_m:
                fname = field_m.group(1)
                ftype = field_m.group(2).rstrip("?")
                info.fields.append({
                    "name": fname,
                    "kotlin_type": ftype,
                    "column_name": pending_col or fname,
                    "is_primary": pending_pk,
                })
                pending_col = None
                pending_pk = False

    return info


def _entity_to_arkts(info: EntityInfo) -> str:
    """生成 ArkTS interface + CREATE TABLE SQL 常量。"""
    # interface
    iface_fields = "\n".join(
        f"  {f['name']}: {_kt_type(f['kotlin_type'])};"
        for f in info.fields
    )
    # CREATE TABLE
    col_defs = []
    for f in info.fields:
        col = f["column_name"]
        sql_t = _column_sql_type(f["kotlin_type"])
        pk = " PRIMARY KEY" if f["is_primary"] else ""
        col_defs.append(f"  {col} {sql_t}{pk}")
    create_sql = (
        f"CREATE TABLE IF NOT EXISTS {info.table_name} (\n"
        + ",\n".join(col_defs)
        + "\n)"
    )
    return f"""\
// AUTO-CONVERTED: Room @Entity → RelationalStore
import relationalStore from '@ohos.data.relationalStore';

export interface {info.class_name} {{
{iface_fields}
}}

export const {info.table_name.upper()}_CREATE_SQL = `{create_sql}`;

export const {info.table_name.upper()}_TABLE = '{info.table_name}';
"""


# --------------------------------------------------------------------------- #
# @Dao 解析
# --------------------------------------------------------------------------- #

RE_QUERY    = re.compile(r'@Query\s*\(\s*"([^"]+)"\s*\)', re.DOTALL)
RE_INSERT   = re.compile(r'@Insert(?:\([^)]*\))?')
RE_UPDATE   = re.compile(r'@Update(?:\([^)]*\))?')
RE_DELETE   = re.compile(r'@Delete(?:\([^)]*\))?')
RE_FUN_SIG  = re.compile(
    r'(?:suspend\s+)?fun\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*([\w<>?,\s]+?))?(?:\s*\{|$)',
    re.MULTILINE,
)


def _parse_dao_methods(code: str) -> List[Dict]:
    """提取 DAO 方法列表，带注解类型和 SQL。"""
    methods = []
    lines = code.split("\n")
    pending_ann = None
    pending_sql = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        q = RE_QUERY.search(stripped)
        if q:
            pending_ann = "query"
            pending_sql = q.group(1).strip()
            continue
        if RE_INSERT.search(stripped):
            pending_ann = "insert"
            continue
        if RE_UPDATE.search(stripped):
            pending_ann = "update"
            continue
        if RE_DELETE.search(stripped):
            pending_ann = "delete"
            continue

        fm = RE_FUN_SIG.search(stripped)
        if fm and pending_ann:
            methods.append({
                "name": fm.group(1),
                "params_raw": fm.group(2) or "",
                "return_raw": (fm.group(3) or "").strip(),
                "ann": pending_ann,
                "sql": pending_sql,
            })
            pending_ann = None
            pending_sql = None

    return methods


def _parse_params(params_raw: str) -> List[Tuple[str, str]]:
    """'taskId: String, completed: Boolean' → [('taskId','String'), ...]"""
    result = []
    for part in params_raw.split(","):
        part = part.strip()
        if ":" in part:
            name, typ = part.split(":", 1)
            result.append((name.strip(), typ.strip().rstrip("?")))
    return result


def _return_is_list(ret: str) -> bool:
    return "List" in ret or "list" in ret


def _sql_named_to_positional(sql: str, params: List[Tuple[str, str]]) -> Tuple[str, str]:
    """
    把 Room 风格命名参数 :taskId 转换为 RelationalStore 的位置参数 ?，
    同时生成对应的 bindArgs 数组（按出现顺序）。
    返回 (converted_sql, bind_args_expr)。
    """
    bind_order = []

    def replace_param(m):
        pname = m.group(1)
        bind_order.append(pname)
        return "?"

    converted = re.sub(r':(\w+)', replace_param, sql)
    # bind_order 里的名称对应 params 里的参数变量名
    param_map = {p: p for p, _ in params}
    bind_args = ", ".join(param_map.get(n, n) for n in bind_order)
    return converted, f"[{bind_args}]"


def _dao_method_to_arkts(m: Dict) -> str:
    name = m["name"]
    params = _parse_params(m["params_raw"])
    ann = m["ann"]
    sql = m.get("sql", "")
    ret = m["return_raw"]

    param_decl = ", ".join(f"{p}: {_kt_type(t)}" for p, t in params)
    is_list = _return_is_list(ret)

    # 判断 SQL 类型：SELECT 用 querySql，INSERT/UPDATE/DELETE 用 executeSql
    sql = sql or ""
    sql_upper = sql.strip().upper()
    is_write_sql = sql_upper.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP"))

    # 转换命名参数
    sql_positional, bind_args_expr = _sql_named_to_positional(sql, params)

    if ann == "query":
        if is_write_sql:
            return (
                f"  async {name}({param_decl}): Promise<void> {{\n"
                f"    const rdb = await DatabaseManager.getInstance();\n"
                f"    await rdb.executeSql(`{sql_positional}`, {bind_args_expr});\n"
                f"  }}"
            )
        ret_type = "Array<relationalStore.ValuesBucket>" if is_list else "relationalStore.ValuesBucket | null"
        if is_list:
            return_stmt = (
                f"    const result: Array<relationalStore.ValuesBucket> = [];\n"
                f"    const resultSet = await rdb.querySql(`{sql_positional}`, {bind_args_expr});\n"
                f"    while (resultSet.goToNextRow()) {{\n"
                f"      result.push(resultSet.getRow());\n"
                f"    }}\n"
                f"    resultSet.close();\n"
                f"    return result;"
            )
        else:
            return_stmt = (
                f"    const resultSet = await rdb.querySql(`{sql_positional}`, {bind_args_expr});\n"
                f"    if (resultSet.goToNextRow()) {{\n"
                f"      const row = resultSet.getRow();\n"
                f"      resultSet.close();\n"
                f"      return row;\n"
                f"    }}\n"
                f"    resultSet.close();\n"
                f"    return null;"
            )
        return (
            f"  async {name}({param_decl}): Promise<{ret_type}> {{\n"
            f"    const rdb = await DatabaseManager.getInstance();\n"
            f"{return_stmt}\n"
            f"  }}"
        )

    if ann == "insert":
        entity_param = params[0][0] if params else "entity"
        return (
            f"  async {name}({param_decl}): Promise<void> {{\n"
            f"    const rdb = await DatabaseManager.getInstance();\n"
            f"    await rdb.insert(TABLE_NAME, {entity_param} as relationalStore.ValuesBucket);\n"
            f"  }}"
        )

    if ann == "update":
        entity_param = params[0][0] if params else "entity"
        return (
            f"  async {name}({param_decl}): Promise<void> {{\n"
            f"    const rdb = await DatabaseManager.getInstance();\n"
            f"    const predicates = new relationalStore.RdbPredicates(TABLE_NAME);\n"
            f"    // TODO: set predicates for primary key\n"
            f"    await rdb.update({entity_param} as relationalStore.ValuesBucket, predicates);\n"
            f"  }}"
        )

    if ann == "delete":
        if sql:
            where = re.sub(r"DELETE FROM \w+ WHERE (.+)", r"\1", sql, flags=re.IGNORECASE)
            cols = re.findall(r"(\w+)\s*=\s*:\w+", where)
            pred_lines = "\n".join(
                f"    predicates.equalTo('{c}', {params[i][0]});"
                for i, c in enumerate(cols) if i < len(params)
            )
            return (
                f"  async {name}({param_decl}): Promise<number> {{\n"
                f"    const rdb = await DatabaseManager.getInstance();\n"
                f"    const predicates = new relationalStore.RdbPredicates(TABLE_NAME);\n"
                f"{pred_lines}\n"
                f"    return await rdb.delete(predicates);\n"
                f"  }}"
            )
        return (
            f"  async {name}({param_decl}): Promise<void> {{\n"
            f"    const rdb = await DatabaseManager.getInstance();\n"
            f"    const predicates = new relationalStore.RdbPredicates(TABLE_NAME);\n"
            f"    await rdb.delete(predicates);\n"
            f"  }}"
        )

    return f"  async {name}({param_decl}): Promise<void> {{ /* TODO */ }}"


def _dao_to_arkts(sc: SourceClass, entity_table: str = "tasks") -> str:
    methods = _parse_dao_methods(sc.raw_content)
    methods_code = "\n\n".join(_dao_method_to_arkts(m) for m in methods)
    return f"""\
// AUTO-CONVERTED: Room @Dao → RelationalStore
import relationalStore from '@ohos.data.relationalStore';
import {{ DatabaseManager }} from './DatabaseManager';

const TABLE_NAME = '{entity_table}';

export class {sc.class_name} {{
{methods_code}
}}
"""


# --------------------------------------------------------------------------- #
# @Database 解析 → DatabaseManager 单例
# --------------------------------------------------------------------------- #

RE_DB_ENTITIES  = re.compile(r'entities\s*=\s*\[([^\]]+)\]')
RE_DB_VERSION   = re.compile(r'version\s*=\s*(\d+)')


def _database_to_arkts(sc: SourceClass, create_sqls: List[str]) -> str:
    code = sc.raw_content
    version_m = RE_DB_VERSION.search(code)
    version = int(version_m.group(1)) if version_m else 1

    create_block = "\n".join(
        f"    await rdb.executeSql(`{sql}`, []);"
        for sql in create_sqls
    )
    return f"""\
// AUTO-CONVERTED: Room @Database → RelationalStore DatabaseManager
import relationalStore from '@ohos.data.relationalStore';
import common from '@ohos.app.ability.common';

const DB_NAME = 'app_database.db';
const DB_VERSION = {version};

const DB_CONFIG: relationalStore.StoreConfig = {{
  name: DB_NAME,
  securityLevel: relationalStore.SecurityLevel.S1,
}};

export class DatabaseManager {{
  private static instance: relationalStore.RdbStore | null = null;

  static async getInstance(context?: common.BaseContext): Promise<relationalStore.RdbStore> {{
    if (!DatabaseManager.instance) {{
      const ctx = context ?? getContext() as common.BaseContext;
      const rdb = await relationalStore.getRdbStore(ctx, DB_CONFIG);
{create_block}
      DatabaseManager.instance = rdb;
    }}
    return DatabaseManager.instance!;
  }}

  static async close(): Promise<void> {{
    if (DatabaseManager.instance) {{
      await DatabaseManager.instance.close();
      DatabaseManager.instance = null;
    }}
  }}
}}
"""


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #

class RoomTransform:
    """
    检测 Kotlin 源文件中的 Room 注解，生成对应的 RelationalStore ArkTS 代码。
    返回额外生成的文件（原文件路径 → ArkTS代码），以及需要覆盖原转换的文件集合。
    """

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        """
        返回 { 虚拟文件路径 → ArkTS代码 }
        """
        results: Dict[str, str] = {}
        entity_infos: List[EntityInfo] = []
        dao_classes: List[SourceClass] = []
        db_classes: List[SourceClass] = []

        for sc in classes:
            code = sc.raw_content
            if "@Entity" in code:
                info = _parse_entity(sc)
                if info:
                    entity_infos.append(info)
                    key = sc.file_path.replace(".kt", "_entity.ets").replace(".java", "_entity.ets")
                    results[key] = _entity_to_arkts(info)
            elif "@Dao" in code:
                dao_classes.append(sc)
            elif "@Database" in code:
                db_classes.append(sc)

        # DAO 转换（需要知道表名）
        table_name = entity_infos[0].table_name if entity_infos else "data"
        for sc in dao_classes:
            key = sc.file_path.replace(".kt", "_dao.ets").replace(".java", "_dao.ets")
            results[key] = _dao_to_arkts(sc, table_name)

        # Database → DatabaseManager（使用真实 CREATE TABLE SQL）
        def _build_create_sqls(entities):
            sqls = []
            for e in entities:
                cols = ", ".join(
                    f"{f['column_name']} {_column_sql_type(f['kotlin_type'])}"
                    + (" PRIMARY KEY" if f["is_primary"] else "")
                    for f in e.fields
                )
                sqls.append(f"CREATE TABLE IF NOT EXISTS {e.table_name} ({cols})")
            return sqls

        create_sqls = _build_create_sqls(entity_infos)
        for sc in db_classes:
            key = sc.file_path.replace(".kt", "_db.ets").replace(".java", "_db.ets")
            results[key] = _database_to_arkts(sc, create_sqls)

        # 统一输出 DatabaseManager.ets（DAO 统一从 ./DatabaseManager 导入）
        if entity_infos:
            class _FakeSC:
                class_name = "DatabaseManager"
                raw_content = "@Database(version = 1)"

            dm_path = os.path.join("generated", "DatabaseManager.ets")
            results[dm_path] = _database_to_arkts(_FakeSC(), create_sqls)

        return results
