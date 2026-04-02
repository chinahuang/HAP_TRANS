"""
生成转换报告：统计各模块转换情况、覆盖率、警告和 TODO 项。
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


@dataclass
class ConversionStats:
    # 布局
    layouts_total: int = 0
    layouts_converted: int = 0
    # 源文件
    sources_total: int = 0
    sources_converted: int = 0
    sources_activity: int = 0
    sources_fragment: int = 0
    sources_viewmodel: int = 0
    # 资源
    strings_total: int = 0
    colors_total: int = 0
    dimens_total: int = 0
    images_copied: int = 0
    images_skipped: int = 0
    # 依赖
    deps_total: int = 0
    deps_mapped: int = 0
    deps_unmapped: int = 0
    # 警告 & TODO
    warnings: List[str] = field(default_factory=list)
    todos: List[Tuple[str, int, str]] = field(default_factory=list)  # (file, line, text)


class ReportGenerator:
    def collect_todos(self, out_dir: str) -> List[Tuple[str, int, str]]:
        """扫描输出目录中所有 .ets 文件，收集 TODO 注释。"""
        todos = []
        for dirpath, _, files in os.walk(out_dir):
            for fname in files:
                if not fname.endswith(".ets"):
                    continue
                path = os.path.join(dirpath, fname)
                rel = os.path.relpath(path, out_dir)
                try:
                    with open(path, encoding="utf-8") as f:
                        for lineno, line in enumerate(f, 1):
                            if "// TODO" in line:
                                todos.append((rel, lineno, line.strip()))
                except OSError:
                    pass
        return todos

    def generate(self, stats: ConversionStats, out_dir: str) -> str:
        """生成 Markdown 格式报告，写入 out_dir/conversion_report.md，同时返回内容。"""
        stats.todos = self.collect_todos(out_dir)

        lines = [
            "# Android → HarmonyOS 转换报告\n",
            "## 概览\n",
            f"| 模块 | 总计 | 已转换 | 覆盖率 |",
            f"|------|------|--------|--------|",
        ]

        def pct(a, b):
            return f"{a/b*100:.1f}%" if b else "N/A"

        lines += [
            f"| 布局文件 | {stats.layouts_total} | {stats.layouts_converted} | {pct(stats.layouts_converted, stats.layouts_total)} |",
            f"| 源文件   | {stats.sources_total} | {stats.sources_converted} | {pct(stats.sources_converted, stats.sources_total)} |",
            f"| 依赖     | {stats.deps_total} | {stats.deps_mapped} | {pct(stats.deps_mapped, stats.deps_total)} |",
            "",
            "## 源文件分类",
            f"- Activity → UIAbility: **{stats.sources_activity}**",
            f"- Fragment → @Component: **{stats.sources_fragment}**",
            f"- ViewModel: **{stats.sources_viewmodel}**",
            "",
            "## 资源转换",
            f"- 字符串: {stats.strings_total} 条",
            f"- 颜色: {stats.colors_total} 条",
            f"- 尺寸: {stats.dimens_total} 条",
            f"- 图片复制: {stats.images_copied} 个，跳过(Vector): {stats.images_skipped} 个",
            "",
        ]

        if stats.warnings:
            lines.append("## 警告")
            for w in stats.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if stats.todos:
            lines.append(f"## 需人工处理的 TODO ({len(stats.todos)} 处)\n")
            lines.append("| 文件 | 行 | 内容 |")
            lines.append("|------|----|------|")
            for fpath, lineno, text in stats.todos[:100]:  # 最多显示100条
                text_escaped = text.replace("|", "\\|")
                lines.append(f"| {fpath} | {lineno} | {text_escaped} |")
            if len(stats.todos) > 100:
                lines.append(f"\n*... 还有 {len(stats.todos)-100} 处，请查看源文件。*")
            lines.append("")

        lines.append("## 下一步建议")
        lines.append("1. 搜索所有 `// TODO` 注释并逐一处理")
        lines.append("2. 替换 Vector Drawable 为鸿蒙矢量图")
        lines.append("3. 验证 Room → RelationalStore 数据模型")
        lines.append("4. 调整 Navigation → Router 页面跳转逻辑")
        lines.append("5. 用 DevEco Studio 打开工程，修复编译错误")

        content = "\n".join(lines)
        report_path = os.path.join(out_dir, "conversion_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        return content
