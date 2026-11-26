# 维链工坊 · 维度建模与缓慢变化维加工平台

面向维度注册、缓慢变化维拉链、一致性维度核对、事实表装配、代理键生成、维度退化、迟到事实回补、汇总层派生、指标口径绑定与维度快照发布的数仓维度建模加工平台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/WorkbenchView.vue|tsx  全部模块共享工作台
│   ├── src/data/modules.ts              18个业务模块配置
│   ├── src/api/              统一请求封装
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/resource.py  通用查询/导出/登记/动作接口
│   ├── app/services/<key>.py    每个模块独立领域逻辑
│   ├── app/services/base.py     共享服务骨架
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8003/api/health`

### 前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认监听 `http://127.0.0.1:5176/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8003`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 维度建档 | `dim_entry` | 维度条目 | 维度编号、维度名称、业务主键 |
| 拉链加工 | `scd_chain` | 拉链记录 | 拉链编号、所属维度、代理键 |
| 代理键生成 | `surrogate_key` | 代理键段 | 键段编号、所属维度、键段起点 |
| 一致性核对 | `conform_check` | 核对条目 | 核对编号、基准维度、对照维度 |
| 事实装配 | `fact_assemble` | 事实批次 | 批次编号、所属事实表、度量列集合 |
| 退化维度 | `degenerate_dim` | 退化维条目 | 条目编号、所属事实表、退化字段 |
| 迟到事实 | `late_fact` | 迟到记录 | 记录编号、所属事实表、业务发生日 |
| 汇总层派生 | `summary_layer` | 汇总条目 | 汇总编号、来源事实表、汇总粒度 |
| 粒度声明 | `grain_declare` | 粒度声明 | 声明编号、所属事实表、一行代表 |
| 度量目录 | `measure_catalog` | 度量条目 | 度量编号、度量名称、计算表达式 |
| 指标绑定 | `metric_bind` | 绑定关系 | 绑定编号、指标名称、引用度量 |
| 维度快照 | `dim_snapshot` | 快照版本 | 快照编号、所属维度、快照日期 |
| 层级路径 | `hier_path` | 层级路径 | 路径编号、所属维度、层级名称 |
| 多值桥接 | `bridge_link` | 桥接条目 | 桥接编号、所属事实表、关联维度 |
| 属性失效 | `attr_decay` | 失效条目 | 失效编号、所属维度、属性名称 |
| 装载窗口 | `load_window` | 装载窗口 | 窗口编号、所属事实表、窗口起点 |
| 重跑任务 | `reprocess_task` | 重跑任务 | 重跑编号、触发原因、影响事实表 |
| 装配质量闸 | `quality_gate` | 质量闸条目 | 闸口编号、所属事实表、校验项 |
| 血缘关系 | `lineage_edge` | 血缘边 | 血缘编号、上游对象、下游对象 |
| 维度发布 | `dim_publish` | 发布版本 | 发布编号、所属维度、发布版本 |
| 建模审计 | `model_audit` | 审计条目 | 条目编号、操作类型、操作对象 |
| 源端抽取 | `src_extract` | 抽取批次 | 抽取编号、来源系统、抽取范围 |

## 约定

- 全部模块共享`frontend/src/views/WorkbenchView.vue|tsx`和一套资源路由。
- 每个模块仍保留独立`backend/app/services/<模块>.py`；纯前端保留
  `frontend/src/domain/<模块>.ts`，用于承载真实业务差异并维持36题位容量。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

## 快照双人签核 → 维度发布开单

新增业务模块 `snapshot_signoff`（侧栏「快照签核单」，路由 `/snapshot_signoff`，
另有 `/signoff`、`/snapshot_approval` 等别名），把维度快照的双人签核交给维度发布：

1. 维度快照页每行有「发起快照签核 / 发起签核」入口，跳转到签核页并打开制单弹窗。
2. 制单人提交后单据为 `待签核`；必须由**另一位操作员**在确认弹窗填写本人标识，
   制单人与签核人相同时后端拒绝受理（`拒绝受理…同一人`）。
3. 签核单绑定快照的 `修订号 + 快照摘要值`。快照执行「补改内容」（或「重建快照」）
   产生新修订后，旧修订的未结签核单自动置为 `已失效`，必须按本次修订重新签核。
4. 签核通过（`已签核`）后即生成「维度发布待办」：维度发布页顶部待办条与
   `GET /api/dim_publish/todos`、`GET /api/snapshot_signoff/todos` 都能取到。
5. 发布人在维度发布页选择有效签核单、填写说明后「提交并创建发布申请」，
   实际写入一条 `dim_publish` 申请（状态 `待发布`、回写 `签核单编号/签核修订号/申请说明`），
   同时签核单置为 `已使用`。
6. 签核单可在 `待签核/已签核` 状态撤回（`已撤回`）。发布开单与签核撤回共用
   `store.FLOW_LOCK`，在锁内完成「校验有效 → 写申请/撤回 → 占用单据」，
   因此并发时同一张签核单只有一个结果：要么 `已使用`（已写入一笔发布申请，
   撤回返回 409 冲突），要么 `已撤回`（开单返回 409 冲突，不写申请）。
7. 列表/详情会附带 `usable / usability_code / usability_reason / next_step`，
   签核页与发布页据此说明「这张单是否还可使用」以及此人下一步能做什么；
   所有状态都在后端，刷新或重开两个页面后自动恢复一致。

主要接口：

```text
POST /api/snapshot_signoff/submit            制单提交
POST /api/snapshot_signoff/{id}/confirm      另一位操作员确认签核
POST /api/snapshot_signoff/{id}/withdraw     撤回（与开单竞争，冲突返回 409）
GET  /api/snapshot_signoff/{id}/usability    可用性/修订匹配/下一步
POST /api/dim_publish/apply                  凭有效签核单原子创建发布申请
GET  /api/dim_publish/todos                  签核通过且仍有效的发布待办
POST /api/reset                              恢复种子数据
```

操作人可放在请求体 `operator/制单人/签核人/撤回人/发布人`，或用 `X-Operator` 头；
前端顶栏的「当前操作员」保存在 localStorage。

## 领域

数据工程 · 子方向：数仓与数据湖
