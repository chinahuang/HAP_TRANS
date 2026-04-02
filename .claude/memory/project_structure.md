---
name: hap_trans 关键文件路径与目录说明
description: 转换引擎和输出工程的关键路径，供快速定位使用
type: reference
---

## 新增静态覆盖（data 层）

| 路径 | 说明 |
|------|------|
| `c:/work/hap_trans/static_overrides/entry/src/main/ets/data/DatabaseManager.ets` | 正确 CREATE TABLE SQL，单例 RdbStore |
| `c:/work/hap_trans/static_overrides/entry/src/main/ets/data/TasksDao_dao.ets` | 类型化 DAO（Task 对象 CRUD）|

## 转换引擎（源码）

| 路径 | 说明 |
|------|------|
| `c:/work/hap_trans/main.py` | CLI 入口，7 步流水线 |
| `c:/work/hap_trans/transform/arkts_cleanup.py` | ArkTS 最终语法清理（最后一道）|
| `c:/work/hap_trans/transform/ability_generator.py` | 为 Activity 生成干净 UIAbility 骨架 |
| `c:/work/hap_trans/transform/di_transform.py` | Hilt → 手动单例，生成 AppContainer.ets |
| `c:/work/hap_trans/transform/room_transform.py` | Room → RelationalStore |
| `c:/work/hap_trans/transform/viewmodel_transform.py` | LiveData → @ObservedV2/@Trace |
| `c:/work/hap_trans/transform/navigation_transform.py` | Navigation → router |
| `c:/work/hap_trans/transform/vector_transform.py` | Vector Drawable → SVG |
| `c:/work/hap_trans/generator/project_generator.py` | 工程骨架生成，含 patch_required_resources() |
| `c:/work/hap_trans/mappings/` | 所有 JSON 映射规则文件 |

## 测试源工程

| 路径 | 说明 |
|------|------|
| `c:/work/android_sample/` | google/android-architecture-samples（views 分支）|

## 输出工程

| 路径 | 说明 |
|------|------|
| `c:/work/hap_output/` | 生成的鸿蒙工程根目录 |
| `c:/work/hap_output/entry/src/main/ets/abilities/` | UIAbility |
| `c:/work/hap_output/entry/src/main/ets/pages/` | @Entry 页面（TasksPage 等）|
| `c:/work/hap_output/entry/src/main/ets/components/` | ArkUI 布局组件 + Fragment 逻辑 |
| `c:/work/hap_output/entry/src/main/ets/viewmodels/` | @ObservedV2 ViewModel |
| `c:/work/hap_output/entry/src/main/ets/data/` | RelationalStore DAO + Entity |
| `c:/work/hap_output/entry/src/main/ets/common/` | 接口/数据类/枚举等普通源文件 |
| `c:/work/hap_output/entry/src/main/ets/di/` | AppContainer.ets |
| `c:/work/hap_output/conversion_report.md` | 转换报告（含 76 处 TODO 列表）|

## 运行方式

```bash
cd c:/work/hap_trans
C:/ProgramData/anaconda3/python.exe main.py --src c:/work/android_sample --out c:/work/hap_output
```
