"""
Android Navigation Component → HarmonyOS Router 转换。

从 kotlin_transform 的 import/API 替换扩展，生成：
  1. 页面跳转方法骨架（router.pushUrl）
  2. NavGraph 对应的 RouterConfig 常量文件
"""
import re
from typing import Dict, List
from parser.kotlin_parser import SourceClass


# Navigation 导航 Action 模式：
#   findNavController().navigate(R.id.action_tasks_to_addTask)  → router.pushUrl
#   findNavController().navigate(TasksFragmentDirections.actionTasksToAddTask())
#   findNavController().navigateUp()  → router.back()

RE_NAVIGATE_ID = re.compile(
    r'findNavController\(\)\.navigate\(R\.id\.(\w+)\)'
)
RE_NAVIGATE_DIRECTIONS = re.compile(
    r'findNavController\(\)\.navigate\(\w+Directions\.(\w+)\(([^)]*)\)\)'
)
RE_NAVIGATE_UP = re.compile(
    r'findNavController\(\)\.navigateUp\(\)'
)
RE_NAVIGATE_ACTION = re.compile(
    r'findNavController\(\)\.navigate\((\w+)\)'
)
RE_NAV_ARG = re.compile(
    r'navArgs<(\w+)>\(\)'
)


# action 名 → 页面路径的简单推断
def _action_to_page(action_name: str) -> str:
    """
    actionTasksToAddTask → pages/AddTaskPage
    actionTasksFragmentDestToTaskDetailFragmentDest → pages/TaskDetailPage
    """
    # 取 "To" 后面的部分
    m = re.search(r'[Tt]o([A-Z]\w+)', action_name)
    if m:
        dest = m.group(1)
        # 去掉常见后缀
        dest = re.sub(r'(Fragment|Activity|Dest)$', '', dest)
        return f"pages/{dest}Page"
    return f"pages/UnknownPage  // TODO: map '{action_name}'"


class NavigationTransform:

    def transform_source(self, code: str) -> str:
        """对单个文件的代码做 Navigation → Router 替换。"""

        # findNavController().navigate(R.id.xxx) → router.pushUrl
        def replace_navigate_id(m):
            action = m.group(1)
            page = _action_to_page(action)
            return f"router.pushUrl({{ url: '{page}' }})"
        code = RE_NAVIGATE_ID.sub(replace_navigate_id, code)

        # findNavController().navigate(XxxDirections.actionXxxToYyy(args))
        def replace_navigate_dir(m):
            action = m.group(1)
            args_raw = m.group(2).strip()
            page = _action_to_page(action)
            if args_raw:
                params = ", ".join(
                    f"{a.split('=')[0].strip()}: {a.split('=')[-1].strip()}"
                    for a in args_raw.split(",") if a.strip()
                )
                return f"router.pushUrl({{ url: '{page}', params: {{ {params} }} }})"
            return f"router.pushUrl({{ url: '{page}' }})"
        code = RE_NAVIGATE_DIRECTIONS.sub(replace_navigate_dir, code)

        # findNavController().navigateUp() → router.back()
        code = RE_NAVIGATE_UP.sub("router.back()", code)

        # navArgs<XxxArgs>() → router.getParams() as XxxArgs
        def replace_nav_args(m):
            args_type = m.group(1)
            return f"router.getParams() as {args_type}"
        code = RE_NAV_ARG.sub(replace_nav_args, code)

        # import androidx.navigation → import router
        code = re.sub(
            r'^import androidx\.navigation\..*$',
            "import router from '@ohos.router';",
            code,
            flags=re.MULTILINE,
        )
        # 去重 router import
        if code.count("import router from '@ohos.router';") > 1:
            lines = code.split("\n")
            seen_router = False
            new_lines = []
            for line in lines:
                if "import router from '@ohos.router';" in line:
                    if not seen_router:
                        new_lines.append(line)
                        seen_router = True
                else:
                    new_lines.append(line)
            code = "\n".join(new_lines)

        return code

    def transform_all(self, classes: List[SourceClass]) -> Dict[str, str]:
        return {
            sc.file_path: self.transform_source(sc.raw_content)
            for sc in classes
            if "findNavController" in sc.raw_content
            or "navArgs<" in sc.raw_content
            or "androidx.navigation" in sc.raw_content
        }

    def generate_router_config(self, classes: List[SourceClass]) -> str:
        """
        根据 Fragment 类名生成 RouterConfig 常量文件（去重）。
        """
        seen_keys: set = set()
        pages = []
        for sc in classes:
            if sc.is_fragment:
                name = re.sub(r'Fragment$', '', sc.class_name)
            elif sc.is_activity:
                name = re.sub(r'Activity$', '', sc.class_name)
            else:
                continue
            key = name.upper()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            pages.append((key, f"pages/{name}Page"))

        entries = "\n".join(
            f"  {key}: '{path}',"
            for key, path in pages
        )
        return f"""\
// AUTO-GENERATED: Router page constants
// Replace Navigation NavGraph with these router URLs
import router from '@ohos.router';

export const Routes = {{
{entries}
}};

// Usage:
//   router.pushUrl({{ url: Routes.TASKS }})
//   router.pushUrl({{ url: Routes.TASK_DETAIL, params: {{ taskId: id }} }})
//   router.back()
//   const params = router.getParams() as TaskDetailParams;
"""
