"""
Android Service / BroadcastReceiver / ContentProvider → HarmonyOS 鸿蒙 Ability 存根生成。

策略：
  - Service (started)     → ServiceExtensionAbility
  - Service (bound)       → ConnectServiceAbility pattern
  - BroadcastReceiver     → CommonEventSubscriber
  - ContentProvider       → DataShareExtensionAbility (存根 + TODO)
  - JobService / Worker   → taskpool.Task (TODO 注释)
"""
import re
import os
from typing import List, Dict, Tuple, Optional
from parser.kotlin_parser import SourceClass


# ─────────────────────────────────────────────────────────────────────────────
# 检测助手
# ─────────────────────────────────────────────────────────────────────────────

_SERVICE_BASES = frozenset({
    "Service", "IntentService", "LifecycleService",
    "JobService", "JobIntentService",
})
_RECEIVER_BASES = frozenset({
    "BroadcastReceiver",
})
_PROVIDER_BASES = frozenset({
    "ContentProvider",
})
_WORKER_BASES = frozenset({
    "Worker", "CoroutineWorker", "ListenableWorker",
})


def _detect_kind(sc: SourceClass) -> Optional[str]:
    parents = [sc.super_class] + sc.interfaces if sc.super_class else sc.interfaces
    for p in parents:
        if p in _SERVICE_BASES:
            return "service"
        if p in _RECEIVER_BASES:
            return "receiver"
        if p in _PROVIDER_BASES:
            return "provider"
        if p in _WORKER_BASES:
            return "worker"
    # Fallback: check raw_content for known patterns
    content = sc.raw_content
    if "extends Service" in content or "extends IntentService" in content:
        return "service"
    if "extends BroadcastReceiver" in content:
        return "receiver"
    if "extends ContentProvider" in content:
        return "provider"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 模板生成
# ─────────────────────────────────────────────────────────────────────────────

def _is_bound_service(content: str) -> bool:
    """判断是否是 bound service（有 onBind 方法返回 IBinder）。"""
    return bool(re.search(r'\bonBind\s*\(', content))


def _extract_action_filters(content: str) -> List[str]:
    """从 BroadcastReceiver 中提取 action 字符串常量。"""
    actions = re.findall(r'"([a-zA-Z0-9_.]+\.(?:ACTION|action)_[A-Z0-9_]+)"', content)
    return list(set(actions))


def _generate_service_ability(sc: SourceClass) -> str:
    name = sc.class_name
    is_bound = _is_bound_service(sc.raw_content)
    ability_type = "ServiceExtensionAbility"

    # 提取 onCreate / onStartCommand / onDestroy 方法体（做轻量转换）
    methods = _extract_methods_simple(sc.raw_content)
    on_create = methods.get("onCreate", "// TODO: initialize service")
    on_start = methods.get("onStartCommand", "// TODO: handle start command\n    return StartAbilityResult.SUCCESS")
    on_destroy = methods.get("onDestroy", "// TODO: cleanup service")

    bound_section = ""
    if is_bound:
        bound_section = """
  // Bound service: ConnectServiceAbility pattern
  // TODO: Replace with IPC using rpc.RemoteObject
  onConnect(want: Want): rpc.RemoteObject {
    // TODO: return your IPC stub
    return null as unknown as rpc.RemoteObject;
  }

  onDisconnect(want: Want): void {
    // TODO: handle disconnect
  }
"""

    return f"""\
// AUTO-CONVERTED: Android Service → HarmonyOS ServiceExtensionAbility
// TODO: Register in module.json5 under "extensionAbilities"
import ServiceExtensionAbility from '@ohos.app.ability.ServiceExtensionAbility';
import Want from '@ohos.app.ability.Want';
import rpc from '@ohos.rpc';

export default class {name} extends {ability_type} {{
  onCreate(want: Want): void {{
    {on_create}
  }}

  onRequest(want: Want, startId: number): void {{
    {on_start}
  }}

  onDestroy(): void {{
    {on_destroy}
  }}{bound_section}}}
"""


def _generate_receiver_stub(sc: SourceClass) -> str:
    name = sc.class_name
    actions = _extract_action_filters(sc.raw_content)

    actions_comment = ""
    subscriber_init = "// TODO: add subscribeInfo events"
    if actions:
        action_list = ", ".join(f"'{a}'" for a in actions)
        subscriber_init = f"subscribeInfo.addEvent({action_list.split(',')[0].strip()});"
        actions_comment = "\n  // Detected actions: " + ", ".join(actions)

    on_receive = _extract_methods_simple(sc.raw_content).get("onReceive", "// TODO: handle broadcast")

    return f"""\
// AUTO-CONVERTED: Android BroadcastReceiver → HarmonyOS CommonEventSubscriber
// TODO: Call register{name}() during component initialization
import commonEventManager from '@ohos.commonEventManager';

class {name} extends commonEventManager.CommonEventSubscriber {{
  constructor(subscribeInfo: commonEventManager.CommonEventSubscribeInfo) {{
    super(subscribeInfo);
  }}

  onReceiveEvent(event: commonEventManager.CommonEventData): void {{
    const action = event.event;{actions_comment}
    {on_receive}
  }}
}}

export async function register{name}(): Promise<commonEventManager.CommonEventSubscriber> {{
  const subscribeInfo: commonEventManager.CommonEventSubscribeInfo = {{
    events: [],  // TODO: add event names
  }};
  {subscriber_init}
  const subscriber = await commonEventManager.createSubscriber(subscribeInfo);
  await commonEventManager.subscribe(subscriber, (err, data) => {{
    if (!err) {{
      subscriber.onReceiveEvent(data);
    }}
  }});
  return subscriber;
}}
"""


def _generate_provider_stub(sc: SourceClass) -> str:
    name = sc.class_name

    return f"""\
// AUTO-CONVERTED: Android ContentProvider → HarmonyOS DataShareExtensionAbility
// TODO: Register in module.json5 under "extensionAbilities" with type "dataShare"
// TODO: Implement actual data sharing logic
import Extension from '@ohos.application.DataShareExtensionAbility';
import dataShare from '@ohos.data.dataShare';
import relationalStore from '@ohos.data.relationalStore';

export default class {name} extends Extension {{
  private rdbStore?: relationalStore.RdbStore;

  onCreate(want: object, callback: Function): void {{
    // TODO: initialize RDB store
    callback();
  }}

  query(uri: string, predicates: dataShare.DataSharePredicates,
        columns: Array<string>, callback: Function): void {{
    // TODO: implement query
    callback(null, null);
  }}

  insert(uri: string, value: dataShare.ValuesBucket, callback: Function): void {{
    // TODO: implement insert
    callback(null, -1);
  }}

  update(uri: string, predicates: dataShare.DataSharePredicates,
         value: dataShare.ValuesBucket, callback: Function): void {{
    // TODO: implement update
    callback(null, 0);
  }}

  delete(uri: string, predicates: dataShare.DataSharePredicates,
         callback: Function): void {{
    // TODO: implement delete
    callback(null, 0);
  }}
}}
"""


def _generate_worker_stub(sc: SourceClass) -> str:
    name = sc.class_name
    do_work = _extract_methods_simple(sc.raw_content).get("doWork", "// TODO: implement background work")

    return f"""\
// AUTO-CONVERTED: Android WorkManager Worker → HarmonyOS taskpool.Task
// TODO: Schedule with taskpool.execute() from your entry code
import taskpool from '@ohos.taskpool';

@Concurrent
async function {name}Task(inputData: object): Promise<void> {{
  // Converted from {name}.doWork()
  {do_work}
}}

// To execute: taskpool.execute(new taskpool.Task({name}Task, inputData))
export {{ {name}Task }};
"""


# ─────────────────────────────────────────────────────────────────────────────
# 轻量方法提取
# ─────────────────────────────────────────────────────────────────────────────

def _extract_methods_simple(content: str) -> Dict[str, str]:
    """提取关键方法（onCreate/onReceive/doWork 等）的内部代码，做基础清洗。"""
    result: Dict[str, str] = {}
    pattern = re.compile(
        r'(?:override\s+)?fun\s+(\w+)\s*\([^)]*\)[^{]*\{',
    )
    for m in pattern.finditer(content):
        name = m.group(1)
        start = m.end()  # right after '{'
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            i += 1
        body = content[start:i-1].strip()
        body = _clean_method_body(body)
        result[name] = body
    return result


def _clean_method_body(body: str) -> str:
    """基础 Kotlin → ArkTS 语法清洗。"""
    # 去掉 super.xxx() 调用
    body = re.sub(r'\bsuper\.\w+\([^)]*\)', '// super call removed', body)
    # val/var → const/let
    body = re.sub(r'\bval\s+', 'const ', body)
    body = re.sub(r'\bvar\s+', 'let ', body)
    # Kotlin intent extras → TODO
    body = re.sub(r'intent\??\.\w+\([^)]*\)', '// TODO: get from want.parameters', body)
    body = re.sub(r'intent\??\.getStringExtra\("(\w+)"\)', r"want.parameters?.'\1'", body)
    # Log → hilog
    body = re.sub(r'\bLog\.(d|i|w|e)\s*\(', 'hilog.debug(0x0, ', body)
    # Toast → promptAction
    body = re.sub(
        r'Toast\.makeText\([^,]+,\s*([^,]+),\s*[^)]+\)\.show\(\)',
        r"promptAction.showToast({ message: \1 })",
        body,
    )
    # 截断超长方法体（避免生成过大文件）
    lines = body.split('\n')
    if len(lines) > 30:
        lines = lines[:30] + ['    // ... (truncated — see original source)']
    return '\n    '.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 主转换器
# ─────────────────────────────────────────────────────────────────────────────

class ServiceTransform:

    def transform(self, sc: SourceClass) -> Optional[str]:
        """
        转换单个 Android 组件到 HarmonyOS 对应 Ability。
        返回转换后代码，或 None（不是支持的类型）。
        """
        kind = _detect_kind(sc)
        if kind is None:
            return None
        if kind == "service":
            return _generate_service_ability(sc)
        if kind == "receiver":
            return _generate_receiver_stub(sc)
        if kind == "provider":
            return _generate_provider_stub(sc)
        if kind == "worker":
            return _generate_worker_stub(sc)
        return None

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        """批量转换，返回 {file_path → converted_code}。"""
        result: Dict[str, str] = {}
        for sc in classes:
            code = self.transform(sc)
            if code is not None:
                result[sc.file_path] = code
        return result

    def is_supported(self, sc: SourceClass) -> bool:
        return _detect_kind(sc) is not None
