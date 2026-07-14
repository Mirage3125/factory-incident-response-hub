# Factory Incident Response Hub 项目总设计文档

## 1. 项目概述

### 1.1 项目名称

- 中文名称：制造业异常处理工作流 Agent
- 英文名称：Factory Incident Response Hub
- 推荐仓库名：`factory-incident-response-hub`

### 1.2 项目定位

本项目面向制造业生产异常处理场景，用于展示以下工程能力：

- 使用 FastAPI 构建可维护的业务后端；
- 使用 n8n 编排跨系统工作流、人工审批和 SLA 升级；
- 使用大模型 Agent 对异常进行结构化辅助分析；
- 使用确定性规则引擎控制高风险决策；
- 在旧 MES 无可用 API 时，使用 Playwright RPA 完成网页工单录入；
- 使用 React 构建异常、审批、工单和自动化执行看板；
- 使用 Docker Compose 在个人电脑上完成一键部署和演示。

本项目必须形成真实可运行的业务闭环，不能只生成静态页面、流程图或占位接口。

## 2. 业务问题

制造现场出现设备报警、缺陷率升高、批次质量异常或系统接口故障后，传统流程通常需要人工完成信息收集、原因判断、工单创建、人员通知、审批和跟踪，存在响应慢、信息分散、重复工单和过程不可追溯等问题。

本系统将流程自动化为：

```text
异常事件进入系统
→ 数据校验与去重
→ 查询设备、批次和维修记录
→ Agent 生成结构化原因分析与处理建议
→ 规则引擎确认严重等级
→ n8n 编排通知、审批和工单流转
→ MES API 不可用时自动切换 RPA
→ 跟踪 SLA、状态和执行日志
→ 结案后生成异常复盘与知识案例
```

## 3. 项目目标

### 3.1 MVP 必须完成

1. 支持模拟制造业异常事件。
2. 保存异常并识别一定时间窗口内的重复报警。
3. 查询设备、生产批次和维修历史上下文。
4. 使用 Agent 输出通过 Pydantic 校验的结构化分析。
5. 无模型密钥时使用确定性的 Demo Analyzer。
6. 使用规则引擎确认 P1、P2、P3、P4 严重等级。
7. 创建并跟踪内部工单。
8. P1 异常进入人工审批流程。
9. 使用 n8n 编排异常处理、审批、工单和 SLA 升级。
10. 模拟 MES API 不可用时，调用 Playwright RPA 操作模拟旧 MES。
11. 保存 RPA 执行结果、外部工单号、日志和截图。
12. 前端展示异常、Agent 分析、审批、工单和流程时间线。
13. 通过 Docker Compose 启动主要服务。
14. 提供自动测试、Smoke Test、README 和演示说明。

### 3.2 MVP 不做

- 不接入真实 PLC、机器人或产线控制系统；
- 不执行真实停机、复位或设备控制动作；
- 不接入真实企业 MES、ERP、钉钉或企业微信；
- 不实现复杂多租户和企业级 RBAC；
- 不引入 Kubernetes、Kafka、RabbitMQ、服务注册中心；
- 不搭建复杂向量数据库或大规模 RAG；
- 不追求移动端适配和复杂动画；
- 不为展示技术而拆分过多微服务。

## 4. 设计原则

1. **完整闭环优先**：优先保证一条异常从进入系统到工单创建、审批、RPA 降级和结案可以跑通。
2. **确定性控制高风险决策**：Agent 提供建议，严重等级和关键状态转换由规则引擎确认。
3. **n8n 负责流程，后端负责业务**：n8n 不直接承担核心数据一致性和复杂领域规则。
4. **RPA 只作为降级方案**：有稳定 API 时优先使用 API，API 不可用时才启用 RPA。
5. **默认可离线演示**：没有外部模型密钥也应能运行主要流程。
6. **可验证而非文件数量**：每个阶段都必须运行测试或实际联调命令。
7. **适合 Windows 开发环境**：脚本优先兼容 PowerShell 和 Docker Desktop。

## 5. 系统架构

```text
┌─────────────────────────────────────┐
│ React + TypeScript Frontend         │
│ Dashboard / Incidents / Approvals   │
│ Work Orders / RPA Runs / Demo       │
└──────────────────┬──────────────────┘
                   │ HTTP
                   ▼
┌─────────────────────────────────────┐
│ FastAPI Backend                     │
│ Domain Services / REST API          │
│ Agent Adapter / Rule Engine         │
│ State Machine / Audit / Dashboard   │
└─────────────┬───────────────┬───────┘
              │               │ Internal HTTP
              ▼               ▼
       PostgreSQL         n8n Workflows
                              │
                       ┌──────┴────────┐
                       ▼               ▼
                Mock MES API      RPA Worker
                                     │
                                     ▼
                              Legacy MES Web
```

## 6. 技术栈

### 6.1 后端

- Python 3.11；
- FastAPI；
- Pydantic v2；
- SQLAlchemy 2；
- Alembic；
- PostgreSQL；
- pytest、pytest-asyncio、httpx；
- 结构化日志；
- OpenAI-compatible LLM adapter。

### 6.2 前端

- React；
- TypeScript；
- Vite；
- React Router；
- TanStack Query；
- Tailwind CSS；
- 轻量图表组件。

### 6.3 自动化

- n8n 自托管；
- Playwright Python；
- 独立的模拟旧 MES Web 服务。

### 6.4 部署

- Docker Compose；
- 前端宿主机默认端口：`3100`；
- 后端宿主机默认端口：`8100`；
- n8n 默认端口：`5678`；
- 其他端口全部通过 `.env` 配置；
- PostgreSQL 优先只在 Docker 内部网络暴露。

## 7. 服务职责边界

### 7.1 FastAPI Backend

负责：

- 异常、设备、批次、维修记录和工单的数据管理；
- 异常去重；
- 状态机和 SLA 计算；
- Agent 调用、输出校验和 fallback；
- 确定性严重等级规则；
- 审批记录和 n8n 恢复地址保护；
- 工作流事件、通知、RPA 运行记录和仪表盘指标；
- 对前端提供 REST API；
- 对 n8n 和 RPA Worker 提供受保护的内部 API。

不负责：

- 长时间等待人工审批；
- 跨系统流程编排；
- 浏览器自动化。

### 7.2 n8n

负责：

- 接收或启动异常工作流；
- 调用后端收集上下文并执行分支；
- 编排人工审批和超时升级；
- 编排 MES API 与 RPA fallback；
- 统一错误工作流；
- 记录关键工作流事件。

不负责：

- 直接维护核心领域数据一致性；
- 在 Code 节点中堆积复杂业务逻辑；
- 直接保存敏感的前端可见恢复地址。

### 7.3 Agent

负责：

- 汇总异常上下文；
- 给出可能原因及证据；
- 给出建议操作；
- 标记缺失信息；
- 给出建议等级、置信度和是否需要人工复核。

禁止：

- 直接修改数据库；
- 直接创建工单；
- 直接操作设备；
- 绕过规则引擎和人工审批。

### 7.4 RPA Worker

负责：

- 登录模拟旧 MES；
- 打开新建工单页面；
- 填写并提交表单；
- 读取外部工单号；
- 保存执行步骤、失败原因和截图。

RPA 不能直接访问 MES 数据库绕过网页流程。

## 8. 核心业务场景

### 8.1 主轴振动严重异常

- 设备：`CNC-01`；
- 异常：振动超过危险阈值；
- 规则等级：P1；
- 结果：Agent 分析、创建紧急工单、进入人工审批。

### 8.2 视觉缺陷率突增

- 设备：`VISION-01`；
- 异常：最近批次缺陷率显著上升；
- 规则等级：P2；
- 结果：查询批次和历史异常，创建质量工单。

### 8.3 重复报警

- 同一设备、异常类型和批次在去重窗口内重复上报；
- 不重复创建异常和工单；
- 增加 `occurrence_count`；
- 更新 `last_seen_at`；
- 记录重复工作流事件。

### 8.4 MES API 故障与 RPA 降级

- n8n 调用模拟 MES API；
- API 返回 503 或超时；
- 工作流进入 RPA 分支；
- Playwright 登录模拟旧 MES 并创建工单；
- 返回外部工单号、步骤、截图和错误信息；
- 内部工单记录 `creation_method=RPA`。

## 9. 严重等级和 SLA

| 等级 | 定义 | 默认 SLA |
|---|---|---:|
| P1 | 安全、设备损坏或停线风险 | 15 分钟 |
| P2 | 明显影响质量或生产效率 | 60 分钟 |
| P3 | 普通异常，需要计划处理 | 4 小时 |
| P4 | 提示类异常，记录观察 | 24 小时 |

SLA 必须集中配置，不能散落在路由和工作流代码中。

## 10. 状态机

### 10.1 异常状态

```text
RECEIVED
→ ANALYZING
→ AWAITING_APPROVAL
→ WORK_ORDER_CREATED
→ IN_PROGRESS
→ RESOLVED
→ CLOSED
```

特殊状态：

```text
DUPLICATE
REJECTED
WORKFLOW_FAILED
```

非法状态转换必须被拒绝并记录明确错误。

### 10.2 工单状态

```text
OPEN
→ ASSIGNED
→ IN_PROGRESS
→ WAITING_PARTS
→ RESOLVED
→ CLOSED
```

## 11. 异常去重

`dedupe_key` 至少由以下内容稳定生成：

- `equipment_id`；
- `incident_type`；
- `production_batch`，没有批次时使用明确占位值；
- 配置化时间窗口。

重复事件处理规则：

- 不创建第二张工单；
- `occurrence_count + 1`；
- 更新 `last_seen_at`；
- 保留新事件的必要原始信息；
- 返回 `duplicate=true` 和原异常 ID；
- 记录 `INCIDENT_DUPLICATED` 工作流事件。

## 12. 核心数据模型

### 12.1 主要实体

- `equipment`：设备基础信息；
- `maintenance_records`：设备维修记录；
- `production_batches`：生产批次；
- `incidents`：异常主记录；
- `incident_analysis_runs`：Agent 分析记录；
- `work_orders`：内部和外部工单映射；
- `approvals`：人工审批；
- `workflow_events`：工作流审计时间线；
- `notifications`：系统通知；
- `rpa_runs`：RPA 运行记录；
- `knowledge_cases`：结案知识案例。

### 12.2 关键约束

- `incident_no`、`work_order_no` 唯一；
- `dedupe_key` 建立查询索引，但是否重复还需结合时间窗口判断；
- `resume_url` 不能通过普通 API 返回前端；
- Agent 输入输出使用 JSONB 保存；
- 工单 `creation_method` 支持 `API`、`RPA`、`MANUAL`；
- 所有时间统一保存为带时区时间。

## 13. Agent 输出契约

```json
{
  "summary": "CNC-01 主轴振动异常",
  "probable_causes": [
    {
      "cause": "主轴轴承磨损",
      "evidence": "振动趋势持续升高且已接近维护周期"
    }
  ],
  "recommended_actions": [
    "检查主轴轴承温度",
    "检查润滑状态",
    "执行空载振动测试"
  ],
  "missing_information": [
    "当前轴承温度"
  ],
  "risk_level": "P1",
  "confidence": 0.83,
  "requires_human_approval": true
}
```

要求：

- 输出必须经过 Pydantic 校验；
- 无效输出最多自动重试一次；
- 重试失败使用 Demo Analyzer；
- Demo Analyzer 根据异常类型返回稳定结果，不能纯随机；
- 保存模型、供应商、Prompt 版本、耗时和 fallback 状态；
- Agent 建议不能降低明确命中 P1 规则的事件等级；
- 低置信度结果自动要求人工复核。

## 14. 确定性规则引擎

至少实现：

- 振动超过危险阈值：P1；
- 温度超过危险阈值：P1；
- 缺陷率超过阈值：P2；
- 同类异常短时间高频出现：提高一个等级，最高到 P1；
- Agent 置信度低于阈值：要求人工复核；
- P1 必须审批；
- 规则命中的 P1 不允许被 Agent 降级。

规则配置与执行代码必须独立于 API 路由。

## 15. n8n 工作流

### 15.1 01 Incident Intake and Analysis

```text
Webhook/内部触发
→ 认证和字段校验
→ 标准化数据
→ 调用后端创建或去重异常
→ 重复则记录事件并结束
→ 获取设备、批次和维修上下文
→ 调用 Agent 分析
→ 调用规则引擎确认等级
→ 更新异常
→ 按等级路由
→ 创建工单或审批
→ 创建通知
```

### 15.2 02 Critical Incident Human Approval

```text
创建待审批记录
→ 后端保存本次执行的恢复地址
→ Wait 暂停
→ 前端通过后端批准或驳回
→ 后端代理恢复 n8n 执行
→ 更新状态和事件
→ 超时则自动升级
```

### 15.3 03 Work Order API with RPA Fallback

```text
调用模拟 MES API
→ 成功：保存外部工单号
→ 5xx/超时：调用 RPA Worker
→ RPA 网页创建工单
→ 保存运行记录和截图
→ 更新内部工单创建方式
```

业务校验失败不能无条件进入 RPA；只有系统不可用、超时或明确支持的技术故障才允许降级。

### 15.4 04 SLA Escalation Monitor

定时查询超时工单，更新升级级别、创建通知和工作流事件。重复执行必须幂等，不能每次扫描都重复创建同级通知。

### 15.5 05 Incident Closure and Knowledge Case

工单完成后加载异常、分析和处理记录，生成结构化复盘，保存知识案例并更新异常状态。无模型密钥时使用固定模板。

### 15.6 99 Global Error Handler

统一接收工作流错误，脱敏后写入后端，生成管理员通知，并在适当情况下标记 `WORKFLOW_FAILED`。

## 16. 后端 API 范围

### 16.1 公共业务 API

```text
GET  /health
GET  /ready

GET  /api/equipment
GET  /api/equipment/{id}
GET  /api/equipment/{id}/maintenance-records

POST /api/incidents
GET  /api/incidents
GET  /api/incidents/{id}
GET  /api/incidents/{id}/timeline
POST /api/incidents/{id}/analyze
PATCH /api/incidents/{id}/status

GET  /api/work-orders
GET  /api/work-orders/{id}
POST /api/work-orders
PATCH /api/work-orders/{id}/status
POST /api/work-orders/{id}/assign
POST /api/work-orders/{id}/resolve

GET  /api/approvals/pending
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject

GET  /api/demo/scenarios
POST /api/demo/scenarios/{scenario_code}/trigger

GET  /api/dashboard/summary
GET  /api/dashboard/severity-distribution
GET  /api/dashboard/recent-incidents
GET  /api/dashboard/sla-metrics
```

### 16.2 内部 API

```text
POST /api/internal/agent/analyze
POST /api/internal/agent/close-case
POST /api/internal/workflow-events
POST /api/internal/notifications
POST /api/internal/work-orders/create
POST /api/internal/approvals/register
POST /api/internal/rpa-runs
POST /api/internal/errors
```

内部 API 使用共享 Header Token 或等价的简单服务认证。

## 17. 模拟旧 MES

模拟旧 MES 至少包含：

- 登录页；
- 工单列表；
- 新建工单页；
- 工单详情页；
- 可切换正常或返回 503 的模拟 API。

新建工单字段：

- `incident_no`；
- `equipment_code`；
- `title`；
- `priority`；
- `description`；
- `assigned_team`。

工单号格式示例：

```text
MES-WO-20260714-0001
```

Demo 账号只通过环境变量配置。

## 18. RPA Worker

RPA Worker 提供受保护的内部接口：

```text
GET  /health
GET  /ready
POST /internal/rpa/work-orders
```

统一响应：

```json
{
  "success": true,
  "external_id": "MES-WO-20260714-0001",
  "screenshot_path": "/artifacts/rpa/...png",
  "steps": [],
  "error_code": null,
  "error_message": null
}
```

要求：

- 优先使用 label、role、test id 定位；
- 每次执行创建独立 browser context；
- 默认 headless，可通过环境变量切换；
- 所有请求设置超时；
- 失败时保存截图；
- 日志不记录密码；
- 测试成功、登录失败、页面字段缺失和站点不可达。

## 19. 前端范围

### 页面

1. Dashboard；
2. Incident List；
3. Incident Detail；
4. Approval Center；
5. Work Orders；
6. RPA Runs；
7. Demo Scenarios。

### 关键展示

- 异常等级和状态；
- Agent 原因、证据、建议、置信度；
- 审批状态和意见；
- 工单 SLA、负责人和创建方式；
- n8n 工作流时间线；
- RPA 操作步骤、错误和截图；
- 场景触发后的异常编号与处理进度。

前端所有按钮必须接入真实后端接口，不允许假按钮。

## 20. 演示数据

至少生成：

- 5 台设备：`CNC-01`、`CNC-02`、`VISION-01`、`PRESS-01`、`ROBOT-01`；
- 2 条产线；
- 5 个生产批次；
- 每台设备至少 2 条维修记录；
- 10 条历史异常；
- 5 个历史工单；
- 2 个知识案例。

种子脚本必须幂等。

## 21. 安全与可靠性

- Webhook 和内部 API 使用 Token；
- Pydantic 校验请求；
- 限制输入文本长度；
- 日志对密码、Token、恢复地址和模型密钥脱敏；
- `resume_url` 不通过前端 API 返回；
- HTTP 客户端设置 timeout；
- 区分可重试和不可重试错误；
- 不允许无限重试；
- 关键创建接口支持幂等；
- Agent 不得直接执行设备动作；
- P1 必须人工审批；
- `.env` 不进入 Git。

## 22. 测试策略

### 后端单元测试

- 去重键和重复报警；
- 状态转换；
- SLA；
- 规则引擎；
- Agent Schema 和 fallback；
- 工单编号；
- 重复审批保护。

### 后端集成测试

- 创建异常；
- Agent 分析；
- 创建工单；
- 审批；
- 工单完成和结案；
- Dashboard 指标。

### RPA 测试

- 成功创建工单；
- 登录失败；
- 页面元素缺失；
- MES 不可达。

### 前端测试

- 关键页面渲染；
- 审批操作；
- Demo 场景触发；
- API 错误反馈。

### Smoke Test

至少验证：

- 主要容器健康；
- 后端和前端可访问；
- n8n 和旧 MES 可访问；
- 能触发异常；
- 能查询分析和工单；
- MES API 失败场景产生 RPA 运行记录。

## 23. 推荐目录结构

```text
factory-incident-response-hub/
├─ AGENTS.md
├─ backend/
├─ frontend/
├─ rpa-worker/
├─ legacy-mes/
├─ n8n/
│  ├─ workflows/
│  └─ README.md
├─ scripts/
├─ docs/
│  ├─ project-spec.md
│  ├─ architecture.md
│  ├─ workflow-design.md
│  ├─ demo-guide.md
│  ├─ interview-guide.md
│  └─ implementation-status.md
├─ docker-compose.yml
├─ .env.example
├─ .gitignore
└─ README.md
```

具体子目录由各阶段在有实际代码需求时创建，禁止提前生成大量无内容目录和占位文件。

## 24. 分阶段实施

### 24.0 连续执行与阶段硬门禁协议

每个阶段均采用“进入门禁 + 自动修复循环 + 当前阶段实施 + 退出门禁 + 下一阶段放行”：

1. **进入门禁**：重新运行前一阶段的关键验证，不得只读取状态文档或相信历史报告。
2. **自动修复循环**：进入门禁失败时先修复根因并重跑；通过后在同一次任务中继续当前阶段，不要求重新下发提示词。
3. **当前阶段实施**：缺少当前阶段代码是预期状态，不是阻塞。
4. **退出门禁**：运行当前阶段规定的测试、构建、迁移、接口或端到端验证。
5. **放行结论**：只有当前阶段全部退出门禁通过，才允许标记为 `PASS + GO`。

阶段结果必须使用以下固定格式：

```text
CURRENT_STAGE_RESULT: PASS | FAIL | BLOCKED
NEXT_STAGE_GATE: GO | NO-GO
```

门禁规则：

- 一次命令失败是中间状态，必须先定位、修复、重跑，不能立即结束。
- 实际命令是事实来源；状态文档过期时更新状态文档后继续。
- 测试失败、迁移错误、容器不健康、代码缺失、依赖或配置问题默认属于可修复问题。
- 只有必须依赖用户提供的外部资源、无法获得的系统权限、无法恢复的网络/磁盘问题或可能破坏用户数据的操作，才允许最终 `BLOCKED + NO-GO`。
- 在宣布阻塞前必须说明根因证据、已尝试修复和无法继续的理由。
- 最终仍有关键命令未执行或失败时为 `NO-GO`。
- 不允许伪造数据、跳过关键测试、使用假按钮或把“后续再验证”当成通过。

阶段 0 不只是“完成环境报告”。进入阶段 1 前至少必须满足：

- 当前目录是有效 Git 仓库；
- Docker Desktop daemon 可连接；
- Docker Compose 可用；
- Python 3.11 可通过宿主机环境或 Docker 镜像实际运行；
- 关键端口可用或已在 `.env` 中明确改用其他端口；
- `AGENTS.md`、`docs/project-spec.md` 和 `docs/implementation-status.md` 均存在。

若上述条件任一不满足，阶段 0 必须标记为 `BLOCKED + NO-GO`，不得提示提交阶段 1。


### 阶段 0：设计落盘与风险检查

- 创建本设计文档、`AGENTS.md` 和状态文档；
- 检查现有目录和环境；
- 确认范围、端口、技术边界和阶段计划；
- 不实现业务代码。

### 阶段 1：基础设施和后端骨架

- Docker Compose 基础服务；
- FastAPI 项目；
- 配置、日志、health/ready；
- PostgreSQL、Alembic 和测试框架；
- 验证后端与数据库连通。

### 阶段 2：领域模型和核心业务 API

- 数据库模型和迁移；
- 状态机、去重、SLA 和编号生成；
- 异常、设备、工单、审批和 Dashboard API；
- Seed 数据；
- 单元和集成测试。

### 阶段 3：Agent 与规则引擎

- OpenAI-compatible adapter；
- Demo Analyzer；
- 输出 Schema、重试、fallback 和审计；
- 确定性等级规则；
- 测试。

### 阶段 4：n8n 工作流

- 工作流服务配置；
- 六个工作流 JSON；
- 导入说明或脚本；
- 后端内部 API 联调；
- 审批恢复地址保护；
- 工作流验证。

### 阶段 5：模拟 MES 与 RPA

- 旧 MES Web 和模拟 API；
- 503 故障开关；
- RPA Worker；
- API 到 RPA fallback；
- 截图和测试。

### 阶段 6：前端看板

- 主要页面；
- API 客户端和查询状态；
- 审批和场景触发；
- 时间线与 RPA 展示；
- 前端测试和 build。

### 阶段 7：端到端闭环与可靠性

- 联调完整主流程；
- 重复报警、审批、SLA、API 故障和 RPA；
- PowerShell Smoke Test；
- 修复跨服务问题。

### 阶段 8：文档、CI 与最终验收

- README、架构、工作流、Demo 和面试文档；
- 密钥扫描和仓库清理；
- GitHub Actions 基础 CI；
- 最终验收报告；
- 不自动 push 或发布。

## 25. 最终验收标准

只有满足以下条件才能称为完成：

- `docker compose up -d --build` 成功；
- 后端迁移和种子数据成功；
- 主要服务健康；
- Swagger、前端、n8n 和旧 MES 可访问；
- n8n 工作流可导入并执行；
- 异常可以入库和去重；
- Agent 或 Demo Analyzer 可以生成有效分析；
- 规则引擎可以确认等级；
- P1 可以完成人工审批；
- 工单可以创建和更新；
- MES API 故障时 RPA 能创建外部工单；
- RPA 返回外部编号、日志和截图；
- SLA 升级具有幂等性；
- 错误工作流能记录失败；
- 后端、RPA 和前端关键测试通过；
- 前端 build 通过；
- Smoke Test 通过；
- 文档完整；
- 仓库中没有真实密钥；
- 核心功能不存在 TODO、假按钮和空实现。
