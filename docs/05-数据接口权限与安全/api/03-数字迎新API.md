# 03 · 数字迎新 API

> 迎新季试点模块（P2 起）。学生小程序为主入口（扫码/预报到），PC 管理端配置批次与看板。
> 通用规则见 [00 总册](00-API契约冻结总册.md)。前缀：管理端 `/api/v1/admin/onboarding`；学生 `/api/v1/student-mini/onboarding` 与 `/api/v1/student-pc/onboarding`。
> DB 依据：DB 冻结册 §4.10（t_onboarding_*、t_green_channel_application）。

---

## 模块一览

| # | 接口 | 方法 | 路径 | 端 | 一期 |
|---|---|---|---|---|---|
| 3.1 | 录取激活 | POST | /student-mini/onboarding/activate | 学生 | P2 |
| 3.2 | 迎新批次列表 | GET | /admin/onboarding/batches | PC | P2 |
| 3.3 | 报到清单（管理） | GET | /admin/onboarding/checkins | PC | P2 |
| 3.4 | 我的迎新进度 | GET | /student-mini/onboarding/progress | 学生 | P2 |
| 3.5 | 预报到信息提交 | POST | /student-mini/onboarding/pre-register | 学生 | P2 |
| 3.6 | 身份核验 | POST | /student-mini/onboarding/verify | 学生 | P2 |
| 3.7 | 缴费状态 | GET | /student-mini/onboarding/payment | 学生 | P2 |
| 3.8 | 绿色通道申请 | POST | /student-mini/onboarding/green-channel | 学生 | P2 |
| 3.9 | 报到码 | GET | /student-mini/onboarding/checkin-code | 学生 | P2 |
| 3.10 | 现场扫码核销 | POST | /admin/onboarding/scan | PC/现场 | P2 |
| 3.11 | 未报到跟进 | GET | /admin/onboarding/not-arrived | PC | P2 |
| 3.12 | 未报到-记录联系 | POST | /admin/onboarding/students/{id}/contact | PC | P2 |
| 3.13 | 迎新看板 | GET | /admin/onboarding/dashboard | PC | P4 |

---

### 3.1 录取激活
- **方法/路径**：`POST /api/v1/student-mini/onboarding/activate`
- **用途**：新生用录取信息激活账号（录取号/考生号/身份证后四位匹配）。
- **使用页面**：学生端 P8 录取激活。
- **请求体**：`{ admissionNo, candidateNo?, idTail, name }`。
- **响应字段**：`{ activated:true, studentId, currentStage:"PRE_STUDENT_VERIFIED" }`。
- **权限**：公开（激活前）。**审计**：是。**依赖微信**：是（绑定 openid）。**mock**：是。**表**：t_student_profile、t_student_user_link、t_wechat_binding、t_student_stage_event。**一期**：P2。
- **备注**：匹配失败 `DATA_NOT_FOUND`；重复激活幂等返回已激活。

### 3.2 迎新批次列表
- `GET /api/v1/admin/onboarding/batches?enrollYear=&status=`。响应 `items[] { batchId, batchName, enrollYear, scope, status, arrivedCount, totalCount }`。权限 `onboarding:batch:view`。分页 是。表 t_onboarding_batch、t_onboarding_batch_scope。一期 P2。

### 3.3 报到清单（管理）
- **方法/路径**：`GET /api/v1/admin/onboarding/checkins`
- **用途**：管理端查看学生报到进度清单。
- **请求参数**：`batchId, collegeId, classId, progressStatus, keyword, page`。
- **响应字段**：`items[] { studentId, realName, className, progressStatus, checkinAt, paymentStatus, dormAssigned, greenChannel }`。
- **权限**：`onboarding:checkin:view`。**数据范围**：按身份。**分页**：是。**mock**：是。**表**：t_onboarding_student_progress、t_onboarding_checkin_record、t_onboarding_payment_status。**一期**：P2。

### 3.4 我的迎新进度
- `GET /api/v1/student-mini/onboarding/progress`。用途：学生阶段首页（迎新）。响应 `{ steps:[{ stepCode, title, status }], nextAction }`。权限 SELF。表 t_onboarding_student_progress、t_onboarding_task_config。一期 P2。

### 3.5 预报到信息提交
- `POST /api/v1/student-mini/onboarding/pre-register`，体 `{ formData, requestId }`。用途：学生 D3 预报到长表单（可 PC 端 student-pc）。审计：否。表 t_onboarding_profile_collection。一期 P2。

### 3.6 身份核验
- `POST /api/v1/student-mini/onboarding/verify`，体 `{ idMaterialFileId }`。审计：是。表 t_student_document、t_student_stage_event。一期 P2。

### 3.7 缴费状态
- `GET /api/v1/student-mini/onboarding/payment`。用途：学生查看缴费订单状态（**本系统不做支付主体，只读状态**）。响应 `{ items:[{ feeType, amount, status }] }`。金额 DECIMAL 字符串。表 t_onboarding_payment_status、t_order。一期 P2。

### 3.8 绿色通道申请
- `POST /api/v1/student-mini/onboarding/green-channel`，体 `{ reason, proofFileId, requestId }`。用途：家庭困难缓缴申请。审计：是。表 t_green_channel_application。一期 P2。状态 APPLIED/APPROVED/REJECTED。

### 3.9 报到码
- **方法/路径**：`GET /api/v1/student-mini/onboarding/checkin-code`
- **用途**：生成学生报到二维码（现场扫码核销用）。
- **使用页面**：学生端 P7 报到码。
- **响应字段**：`{ codeToken, expireAt, qrPayload }`（短期有效，防截图复用）。
- **权限**：SELF。**依赖微信**：否。**审计**：否。**mock**：是。**表**：t_onboarding_checkin_code。**一期**：P2。

### 3.10 现场扫码核销
- **方法/路径**：`POST /api/v1/admin/onboarding/scan`
- **用途**：现场工作人员扫学生报到码，完成某报到点核销。
- **请求体**：`{ codeToken, pointId, requestId }`。
- **响应字段**：`{ studentId, realName, pointName, checkinAt }`。
- **权限**：`onboarding:checkin:scan`。**审计**：是。**幂等**：requestId（防重复核销）。**表**：t_onboarding_checkin_record、t_onboarding_checkin_point、t_student_stage_event（可能触发 REGISTERED_PENDING_ENROLLMENT）。**一期**：P2。
- **备注**：码过期/已核销返回 DATA_CONFLICT。

### 3.11 未报到跟进
- **方法/路径**：`GET /api/v1/admin/onboarding/not-arrived`
- **用途**：辅导员/招生查看未报到学生名单，逐一跟进。
- **使用页面**：教师端 T11 迎新未报到、PC 迎新中心。
- **响应字段**：`items[] { studentId, realName, className, phoneMasked, lastContactAt, contactCount }`。
- **权限**：`onboarding:not-arrived:view`。**数据范围**：按身份。**分页**：是。**表**：t_onboarding_student_progress、t_onboarding_contact_record。**一期**：P2。

### 3.12 未报到-记录联系
- `POST /api/v1/admin/onboarding/students/{id}/contact`，体 `{ contactResult, summary, requestId }`。审计：是。表 t_onboarding_contact_record、t_student_timeline_event。一期 P2。

### 3.13 迎新看板
- `GET /api/v1/admin/onboarding/dashboard?batchId=`。响应指标（报到率/绿通数/未报到数，带 trendType/trendQuality）。权限 `onboarding:dashboard:view`。表 各 t_onboarding_*（聚合，禁硬编码）。一期 P4。

---

## 一期范围小结（本文档）
P2：3.1–3.12（迎新试点主流程）。P4：3.13 看板。迎新是 P2 独立试点，可在实习/毕设（P3）之前或并行按招生季窗口启动。
