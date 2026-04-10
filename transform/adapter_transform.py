"""
RecyclerView.Adapter / ListAdapter → ArkUI @Component with ForEach。

支持：
  - RecyclerView.Adapter<VH> 子类 → @Component struct with ForEach
  - ListAdapter<Item, VH> 子类 → 同上，自动推断 Item 类型
  - ViewHolder 内部类 → 删除（ArkUI 不需要）
  - onCreateViewHolder / onBindViewHolder / getItemCount → 转换为 build()
  - DiffUtil.ItemCallback → 删除
"""
import re
from typing import Optional


# ── 正则 ──────────────────────────────────────────────────────────────────────

_ADAPTER_CLASS_RE = re.compile(
    r'class\s+(\w+)\s*(?::\s*(?:RecyclerView\.Adapter|ListAdapter)\s*<([^>]*)>)?'
    r'\s*(?:\([^)]*\))?\s*\{',
)

_VIEWHOLDER_RE = re.compile(
    r'(?:inner\s+)?class\s+\w+ViewHolder\b.*?^\s*\}',
    re.MULTILINE | re.DOTALL,
)

_DIFF_CALLBACK_RE = re.compile(
    r'(?:companion\s+object\s*\{[^}]*DiffUtil[^}]*\}|'
    r'val\s+\w+\s*=\s*object\s*:\s*DiffUtil\.ItemCallback[^}]*\}[^}]*\})',
    re.DOTALL,
)

_ON_CREATE_VH_RE = re.compile(
    r'override\s+fun\s+onCreateViewHolder\s*\([^)]*\)\s*:\s*\w+\s*\{[^}]*\}',
    re.DOTALL,
)

_ON_BIND_VH_RE = re.compile(
    r'override\s+fun\s+onBindViewHolder\s*\(\s*(\w+)\s*:\s*\w+\s*,\s*(\w+)\s*:\s*Int\s*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
    re.DOTALL,
)

_GET_COUNT_RE = re.compile(
    r'override\s+fun\s+getItemCount\s*\(\s*\)\s*(?::\s*Int\s*)?\{[^}]*\}',
    re.DOTALL,
)

_SUBMIT_LIST_RE = re.compile(r'\b(\w+)\.submitList\s*\(([^)]+)\)')
_NOTIFY_RE = re.compile(r'\b\w+\.notify(?:DataSetChanged|ItemInserted|ItemRemoved|ItemChanged|ItemRangeChanged)\s*\([^)]*\)')


class AdapterTransform:

    def can_transform(self, code: str) -> bool:
        return bool(re.search(r'(?:RecyclerView\.Adapter|ListAdapter)\s*<', code))

    def transform(self, code: str) -> str:
        if not self.can_transform(code):
            return code

        m = _ADAPTER_CLASS_RE.search(code)
        class_name = m.group(1) if m else "UnknownAdapter"

        # Infer item type from generic param (ListAdapter<Item, VH> or Adapter<VH>)
        item_type = "Object"
        if m and m.group(2):
            parts = [p.strip() for p in m.group(2).split(",")]
            if len(parts) >= 2:
                item_type = parts[0]   # ListAdapter<Item, VH>
            # Adapter<VH> — can't infer item type from signature alone

        # Extract bind body for ArkUI build hint
        bind_body = ""
        bm = _ON_BIND_VH_RE.search(code)
        if bm:
            bind_body = bm.group(3).strip()
            # holder.textView.text = item.xxx → Text(item.xxx)
            bind_body = re.sub(
                r'\w+\.(\w+)\.text\s*=\s*(\w+\.\w+)',
                r'// Text(\2)  // TODO: place in build()',
                bind_body,
            )

        # submitList / notifyDataSetChanged → state update TODO
        code = _SUBMIT_LIST_RE.sub(
            lambda mm: f'this.{mm.group(1)}Items = {mm.group(2)}  // submitList',
            code,
        )
        code = _NOTIFY_RE.sub(
            '// TODO: ArkUI auto-updates via @State — remove manual notify calls',
            code,
        )

        # Remove boilerplate
        code = _VIEWHOLDER_RE.sub('', code)
        code = _DIFF_CALLBACK_RE.sub('', code)
        code = _ON_CREATE_VH_RE.sub('', code)
        code = _ON_BIND_VH_RE.sub('', code)
        code = _GET_COUNT_RE.sub('', code)

        # Replace class declaration
        comp_struct = (
            f'@Component\n'
            f'struct {class_name} {{\n'
            f'  @State private items: {item_type}[] = [];\n\n'
            f'  build() {{\n'
            f'    List() {{\n'
            f'      ForEach(this.items, (item: {item_type}) => {{\n'
            f'        ListItem() {{\n'
            f'          // TODO: render item — original onBindViewHolder body:\n'
        )
        if bind_body:
            for line in bind_body.splitlines():
                comp_struct += f'          // {line}\n'
        comp_struct += (
            f'        }}\n'
            f'      }}, (item: {item_type}) => JSON.stringify(item))\n'
            f'    }}\n'
            f'  }}\n'
            f'}}\n'
        )

        # Replace old class block with new @Component struct
        code = _ADAPTER_CLASS_RE.sub(comp_struct, code, count=1)

        # Add header comment
        header = (
            f'// AUTO-CONVERTED: RecyclerView.Adapter → ArkUI @Component\n'
            f'// Review ForEach key function and item rendering.\n\n'
        )
        return header + code
