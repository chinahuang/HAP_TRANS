"""
UIAbility 骨架生成器 — 为 Android Activity 生成可编译的 HarmonyOS UIAbility。

Android Activity 通常负责：
  1. 设置根布局 (setContentView)
  2. 设置 ActionBar / Toolbar
  3. 设置 Navigation (NavController / DrawerLayout)

HarmonyOS 对应：
  1. UIAbility 负责生命周期，实际 UI 在 @Entry @Component 的 Page 里
  2. 导航用 router.pushUrl() 跳转 Page
  3. 侧边栏用 SideBarContainer 组件
"""
import re
from parser.kotlin_parser import SourceClass


def generate_ability(sc: SourceClass, router_page: str = "pages/TasksPage") -> str:
    """生成一个最小可编译的 UIAbility，将原 Activity 代码保留为注释供参考。"""
    class_name = sc.class_name

    # 提取顶层常量定义 (const val X = Y)，跳过引用 Android 类的常量
    constants = re.findall(
        r'(?:^|\n)\s*(?:const\s+)?val\s+(\w+)\s*=\s*(.+)',
        sc.raw_content
    )
    const_lines = "\n".join(
        f"export const {name} = {val.strip()};"
        for name, val in constants
        if name.isupper() and not re.search(r'[A-Z][a-z].*\.', val)  # 跳过引用 Android 类的常量
    )

    return f"""\
// AUTO-GENERATED: UIAbility skeleton for {class_name}
// Original Android Activity code has been moved to manual-review comment below.
// TODO: Implement navigation/drawer using HarmonyOS SideBarContainer + router.

import UIAbility from '@ohos.app.ability.UIAbility';
import window from '@ohos.window';
import router from '@ohos.router';
import Want from '@ohos.app.ability.Want';
import AbilityConstant from '@ohos.app.ability.AbilityConstant';

{const_lines}

export default class {class_name} extends UIAbility {{

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {{
    // TODO: Initialize app state here
    console.info('{class_name} onCreate');
  }}

  onWindowStageCreate(windowStage: window.WindowStage): void {{
    windowStage.loadContent('{router_page}', (err) => {{
      if (err.code !== 0) {{
        console.error('{class_name} loadContent error:', JSON.stringify(err));
      }}
    }});
  }}

  onForeground(): void {{
    console.info('{class_name} onForeground');
  }}

  onBackground(): void {{
    console.info('{class_name} onBackground');
  }}

  onDestroy(): void {{
    console.info('{class_name} onDestroy');
  }}
}}

/*
 * ── Original Android Activity (reference only) ──────────────────────────────
 * The following is kept for reference during manual migration.
 * Do NOT uncomment — it contains Android-specific APIs.
 *
{_block_comment(sc.raw_content)}
 * ─────────────────────────────────────────────────────────────────────────────
 */
"""


def _block_comment(code: str) -> str:
    """Indent each line with ' * ' for use inside a block comment.
    Escapes nested block comment markers to avoid premature comment termination."""
    lines = code.split("\n")
    result = []
    for line in lines:
        # Escape */ to prevent premature comment end
        safe = line.replace("*/", "* /").replace("/*", "/ *")
        result.append(f" * {safe}")
    return "\n".join(result)
