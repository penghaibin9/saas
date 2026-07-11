# 04 · 待办 · 审批 · 消息 API

> 全平台横切公共能力（P1 底座）。所有业务模块不自建，统一走这里。
> 通用规则见 [00 总册](00-API契约冻结总册.md)。前缀：`/api/v1/{admin|student-pc|student-mini|teacher-mobile}/todos|approvals|messages`（同一套后端，按端裁剪）。
> DB 依据：DB 冻结册 §4.14（t_unified_todo / t_workflow_* / t_unified_message）+ 11 权限流程 §11.13–11.20。

---

## 模块一览

| # | 接口 | 方法 | 路径 | 一期 |
|---|---|---|---|---|
| 4.1 | 待办列表 | GET | /{端}/todos | P1 |
| 4.2 | 待办数量 | GET | /{端}/todos/count | P1 |
| 4.3 | 待办详情 | GET | /{端}/todos/{id} | P1 |
| 4.4 | 待办-提交材料 | POST | /{端}/todos/{id}/submit | P1 |
| 4.5 | 待办-完成 | POST | /{端}/todos/{id}/complete | P1 |
| 4.6 | 待办-转 PC | POST | /teacher-mobile/todos/{id}/transfer-to-pc | P1 |
| 4.7 | 审批列表 | GET | /{端}/approvals | P1 |
| 4.8 | 审批详情 | GET | /{端}/approvals/{taskId} | P1 |
| 4.9 | 审批-同意 | POST | /{端}/approvals/{taskId}/approve | P1 |
| 4.10 | 审批-退回 | POST | /{端}/approvals/{taskId}/return | P1 |
| 4.11 | 审批-驳回 | POST | /{端}/approvals/{taskId}/reject | P1 |
| 4.12 | 审批留痕 | GET | /{端}/approvals/{instanceId}/logs | P1 |
| 4.13 | 消息列表 | GET | /{端}/messages | P1 |
| 4.14 | 消息数量 | GET | /{端}/messages/count | P1 |
| 4.15 | 消息详情 | GET | /{端}/messages/{id} | P1 |
| 4.16 | 消息-已读 | POST | /{端}/messages/{id}/read | P1 |
| 4.17 | 消息-回执 | POST | /{端}/messages/{id}/receipt | P1 |

---

### 4.1 待办列表
- **方法/路径**：`GET /api/v1/{端}/todos`
- **用途**：当前身份的待办（必须处理的任务），学生端/教师端/PC 共用一张表。
- **使用页面**：学生 S2 待办、教师 T3 待办中心、PC 工作台。
- **请求参数**：`todoType, sourceModule, status(default PENDING), priority, page/cursor`。
- **响应字段**：`items[] { todoId, todoTitle, todoType, sourceModule, sourceBizType, sourceBizId, studentId, studentName, priority, status, dueTime, actionUrl, overdue }`。
- **权限**：`{端}:todo:view`。**数据范围**：按 assignee 本人 + active_context。**审计**：否。**分页**：是。**mock**：是。**表**：t_unified_todo（教师端聚合 t_teacher_mobile_todo）。**一期**：P1。
- **备注**：`actionUrl` 指向处理页；待办按 active_context 过滤（切身份看到对应待办）。

### 4.2 待办数量
- `GET /api/v1/{端}/todos/count` → `{ total, byType:{ APPROVAL:3, REVIEW:5, RISK:1 } }`。用途：红点角标。一期 P1。

### 4.3 待办详情
- `GET /api/v1/{端}/todos/{id}` → 待办 + 关联业务摘要 + 可执行动作。用途：S3/T4 详情。表 t_unified_todo + 业务表。一期 P1。

### 4.4 待办-提交材料
- **方法/路径**：`POST /api/v1/{端}/todos/{id}/submit`
- **用途**：学生对"材料补交"类待办提交材料（S4 提交材料）。
- **请求体**：`{ fileIds:[...], formData, requestId }`。
- **权限**：`{端}:todo:submit`。**审计**：是。**幂等**：requestId。**表**：t_unified_todo、对应业务表、t_file_object。**一期**：P1。

### 4.5 待办-完成
- `POST /api/v1/{端}/todos/{id}/complete`，体 `{ comment?, requestId }`。用途：确认类待办完成。幂等 是。表 t_unified_todo。一期 P1。已完成再调返回 `DATA_CONFLICT`（TODO_ALREADY_COMPLETED）。

### 4.6 待办-转 PC
- `POST /api/v1/teacher-mobile/todos/{id}/transfer-to-pc`。用途：移动端复杂任务标记转 PC 处理。审计 是。一期 P1。

### 4.7 审批列表
- **方法/路径**：`GET /api/v1/{端}/approvals`
- **用途**：当前身份待审批任务（审批 = 有工作流的待办子集）。
- **使用页面**：教师 T3、PC 权限与审批中心。
- **请求参数**：`bizType, status, keyword, page`。
- **响应字段**：`items[] { taskId, instanceId, bizType, bizTitle, studentName, applicantName, currentNode, status, dueTime }`。
- **权限**：`workflow:task:view`。**数据范围**：按身份。**分页**：是。**表**：t_workflow_task、t_workflow_instance。**一期**：P1。

### 4.8 审批详情
- **方法/路径**：`GET /api/v1/{端}/approvals/{taskId}`
- **用途**：审批详情（申请内容、原值/新值、材料、流程记录）。
- **使用页面**：教师 T4 审批详情、PC 审批页。
- **响应字段**：`{ task, bizDetail:{ fields, oldNew:[{field,old,new}], attachments:[{fileId,name,previewUrl}] }, flowLogs:[...], version }`。
- **权限**：`workflow:task:view`。**审计**：查看敏感是。**表**：t_workflow_task/instance/action_log + 业务表。**一期**：P1。

### 4.9 审批-同意
- **方法/路径**：`POST /api/v1/{端}/approvals/{taskId}/approve`
- **请求体**：`{ comment?, version, requestId }`。
- **响应字段**：`{ nextNode, instanceStatus }`。
- **权限**：对应业务 approve 权限码（如 `intern:leave-request:approve`）。**数据范围**：按身份。**审计**：是。**乐观锁**：version（冲突 `APPROVAL_VERSION_CONFLICT`）。**幂等**：requestId。**SoD**：申请人≠审批人等（`SOD_VIOLATION`）。**表**：t_workflow_task/instance/action_log + 回写业务表 + 生成下一 todo/message。**一期**：P1。

### 4.10 审批-退回（可重新提交）
- **方法/路径**：`POST /api/v1/{端}/approvals/{taskId}/return`
- **请求体**：`{ rejectReason, version, requestId }`。
- **权限**：对应 return 权限。**审计**：是。**校验**：`rejectReason` 必填 ≥5 字，否则 `REJECT_REASON_REQUIRED`。**表**：同 4.9；生成学生待办+消息（带原因）。**一期**：P1。

### 4.11 审批-驳回（不可再提交/需重发起）
- `POST /api/v1/{端}/approvals/{taskId}/reject`，体 `{ rejectReason, version, requestId }`。语义：永久驳回。校验 rejectReason 必填。审计 是。一期 P1。
- **备注**：退回(4.10)≠驳回(4.11)，颜色/语义按 UI V2.1（退回 Warning 可重交、驳回 Danger 需重新发起）。

### 4.12 审批留痕
- `GET /api/v1/{端}/approvals/{instanceId}/logs` → `items[] { actorName, actionCode, actionResult, comment, occurredAt }`。用途：T5/审批历史。表 t_workflow_action_log（append-only）。一期 P1。

### 4.13 消息列表
- **方法/路径**：`GET /api/v1/{端}/messages`
- **用途**：站内消息（需要知道，非必须处理）。
- **使用页面**：学生 S9、教师端消息、PC 顶栏消息。
- **请求参数**：`messageType, readStatus, page/cursor`。
- **响应字段**：`items[] { messageId, title, messageType, sourceModule, readStatus, urgent, actionUrl, createdAt }`。
- **权限**：`{端}:message:view`。**分页**：是。**mock**：是。**表**：t_unified_message（教师端 t_teacher_mobile_message）。**一期**：P1。

### 4.14 消息数量
- `GET /api/v1/{端}/messages/count` → `{ unread }`。一期 P1。

### 4.15 消息详情
- `GET /api/v1/{端}/messages/{id}` → 全文 + actionUrl。进入即标已读（或单独 4.16）。表 t_unified_message。一期 P1。

### 4.16 消息-已读
- `POST /api/v1/{端}/messages/{id}/read`。表 t_unified_message.read_status。一期 P1。

### 4.17 消息-回执
- `POST /api/v1/{端}/messages/{id}/receipt`（需回执的消息）。表 t_unified_message.receipt_status、t_message_channel_log。一期 P1。

---

## 通用约定（本域强约束）
- **待办 vs 消息**：待办必须处理、进 todos；消息只需知道、进 messages。业务模块两者都可能生成，但不混用。
- **去重**：待办去重键 `sourceModule + sourceBizType + sourceBizId + todoType + assigneeId`。
- **多端同步**：PC/学生小程序/教师小程序读同一逻辑表，处理后状态实时同步。
- 审批四态语义严格：approve / return(可重交) / reject(永久) / transfer；退回驳回必带原因。

## 一期范围小结（本文档）
全部 P1。这是 P1 学生/教师主界面闭环的核心横切能力，先于 P3 三大业务落地。
