---
name: 转换引擎开发方式偏好
description: 用户在 hap_trans 项目中对工作方式的偏好和确认过的决策
type: feedback
---

用户始终说"继续按你的计划来"，将所有执行决策委托给助手。

**Why:** 用户信任助手的技术判断，不需要逐步确认。

**How to apply:** 遇到技术决策（比如是否生成骨架、如何组织目录）直接执行，不要问"要不要这样做？"。完成后简要汇报结果即可。

---

测试目标源工程选用 google/android-architecture-samples（views 分支，传统 XML 布局，非 Compose）。

**Why:** 覆盖 XML 布局 → ArkUI 的转换场景，比 Compose 分支更贴合转换引擎设计目标。

**How to apply:** 后续测试或演示时继续使用这个工程，不要切换到 main 分支（Compose）。
