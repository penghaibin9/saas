# D5 宿舍检查、整改与复检闭环验收证据

- 基线提交：`9593881cf428d4a41f88000aea8600caded8aebf`（O4）
- 迁移：`20260901_dorm_inspection_d5`
- 上游：`20260901_orientation_qualification_o4`
- 数据库：本机独立 MySQL `127.0.0.1:33317`
- 验收日期：2026-09-01（Asia/Shanghai）

## 数据库与迁移

- Fresh MySQL 从 O4 升级 D5：通过，单一 head。
- D5 → O4 → D5 往返：通过。
- 负向预检：把存量 `check_type` 注入 `LEGACY_BAD` 后升级按预期失败；失败发生在 DDL 前，版本仍为 O4，D5 新列和整改表均未残留。
- D5 范围结构漂移：0。
- 数据策略由 Config Governance 保存并激活，配置键为 `DORM_INSPECTION_POLICY`。

## 后端闭环

命令：

```text
TEST_DATABASE_URL=mysql+pymysql://root@127.0.0.1:33317/saas_d5_test_local
FAST_TEST_SCHEMA=1
pytest tests/test_dorm_inspection_d5.py::test_d5_four_end_inspection_rectification_recheck_and_negative_gates -q --tb=short
```

结果：`1 passed, 5964 warnings in 59.30s`。

覆盖：

- 7 类检查模板：`HYGIENE / SAFETY / DISCIPLINE / NIGHT_ABSENCE / HIGH_POWER / PET / OTHER`。
- 任务创建幂等与冲突、宿管楼栋数据范围 403。
- `PENDING` 与 `INFECTED` 文件均以 `FILE_NOT_READY` 拒绝。
- 检查照片通过 `FileObject + FileBinding` 绑定 `DORM_CHECK_RECORD`，记录不保存 URL。
- 高风险异常生成整改、统一待办、消息 outbox 与风险；低风险房间卫生只生成整改，不生成风险。
- 学生开始整改、上传证据、提交复检；宿管通过复检并关闭；CAS 旧版本冲突与请求重放均被覆盖。
- 房间级卫生记录 `student_id IS NULL`，不存在 `student_id=0` 风险污染。

受影响旧用例：

```text
pytest tests/test_affairs_dorm.py::test_m5_room_abnormal_exception_no_orphan_risk tests/test_affairs_dorm.py::test_m8_student_abnormal_binds_real_risk
```

结果：`2 passed, 11484 warnings in 62.33s`。

## 前端与小程序

- 管理端目标文件 ESLint：通过。
- 学生门户目标文件 ESLint：通过。
- 管理端生产构建：通过（21 条路由预渲染完成）。
- 学生门户生产构建：通过。
- 微信小程序生产构建：`DONE Build complete`。
- 小程序角色契约：`13 passed`；新增真实宿管 `DORM_MANAGER → dorm_manager` 映射，数据范围 `DORM_BUILDING`，宿舍待办入口可达。
- 宿舍相关 PC/学生门户源码中 `window.confirm / window.alert / alert()` 扫描结果：0。

## REAL Chromium 四端矩阵

| 端 | 模式 | 数据源 | 结果 |
|---|---|---|---|
| 管理 PC | REAL | 本机 MySQL + 真实 API | 登录、入住管理、退宿待确认、宿舍检查、整改列表均通过 |
| 学生 PC | REAL | 本机 MySQL + 真实 API | 本人床位、住宿历史、高风险整改、开始整改与证据入口均通过 |
| 学生小程序 H5 | REAL | 本机 MySQL + 真实 API | 本人床位、整改卡片、调宿与历史均通过 |
| 教师小程序 H5 | REAL | 本机 MySQL + 真实 API | 宿管真实登录、负责楼栋、现场巡检、逐房表单均通过 |

禁用项：无。N/A：无。

原生弹窗专项：

- 入住管理点击“退宿”：`getJsDialog() = NONE`，显示站内表单层。
- 退宿待确认点击“核对并确认”：`getJsDialog() = NONE`，显示站内 `AppConfirmDialog`。
- 截图中的同一动作已复验，未执行最终释放床位，保留测试数据便于复查。

截图：

- `d5-real-chromium-checkout-inapp-dialog.png`
- `d5-real-chromium-checkout-final-inapp-dialog.png`
- `d5-real-chromium-admin-inspection.png`
- `d5-real-chromium-student-portal.png`
- `d5-real-chromium-mini-student.png`
- `d5-real-chromium-mini-teacher-room-form.png`

## 判定

D5 迁移、权限、文件证据、异常整改、统一待办、风险阈值、四端 REAL 链路与原生弹窗专项均通过，可独立提交并进入 D6。
