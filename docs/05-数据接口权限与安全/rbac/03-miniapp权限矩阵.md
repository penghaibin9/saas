# 03-miniapp权限矩阵

- **文档性质**：miniapp（uni-app + Vue3）角色 × 页面权限矩阵
- **适用端**：miniapp 学生端 + 教师端（H5 dev 端口 5188，`build:h5` / `build:mp-weixin` 均通过，`ENV.useMock=true`）
- **依据**：
  - `miniapp/.../config/roles.config.js`（角色定义、`teacherIdentities`、`permissionActions`）
  - 共享底稿第 2 节（miniapp 页面结构、mock 用户）
  - `miniapp/.../services/teacherApi.js`、`studentApi.js`
- **当前阶段声明**：miniapp 当前纯 mock，可运行/可构建/可演示，未接真实后端；`mockLatency=260ms`。矩阵中的可见性依据 `roles.config.js` 静态配置的角色-数据范围-按钮键推导，教师端 6 身份共用同一套页面组件，页面内部按角色再做按钮级过滤。
- **生成日期**：2026-07-04

---

## 一、matrix 读法说明

- **学生端页面（14 页）**：login、home、profile、orientation、campus-service、academic、internship、graduation、employment、my-applications、service-apply（表单）、weekly-report（表单）、messages、me。
- **教师端页面（11 页）**：workbench、todos、approval、risk-students、student-detail（360）、internship-review、graduation-guide、employment-follow、messages、me、role-switch（身份切换）。
- **角色行**：学生 `STUDENT` + 6 类教师身份（`COUNSELOR`/`MENTOR`/`INTERN_MENTOR`/`EMPLOYMENT`/`ACADEMIC`/`COLLEGE_ADMIN`）。
- **取值**：可见（页面可进入，含只读浏览）/ 可见并操作（页面可进入且含至少一个操作按钮）/ 不可见（页面不在该角色导航范围内）。

---

## 二、学生端页面 × 学生角色 矩阵

| 页面 | 学生 `STUDENT` 可见性 | 说明 |
|---|---|---|
| login | 可见 | 登录页，全角色通用入口，不区分权限 |
| home | 可见并操作 | 学生首页汇总，含待办/通知入口 |
| profile | 可见并操作 | 本人主档查看 + 信息纠错提交（`profile.correct`） |
| orientation | 可见并操作 | 数字迎新，材料提交（`material.submit`） |
| campus-service | 可见并操作 | 在校服务，服务申请（`service.apply`） |
| academic | 可见 | 本人学业过程查看（`SELF` 范围） |
| internship | 可见并操作 | 实习打卡（`internship.checkin`）、周报提交（`internship.weekly.submit`） |
| graduation | 可见 | 本人毕设进度查看 |
| employment | 可见并操作 | 就业信息填报（`employment.report`） |
| my-applications | 可见并操作 | 本人所有申请（迎新材料/服务申请/请假/周报等）汇总查看 |
| service-apply（表单） | 可见并操作 | 服务申请表单提交（`service.apply`） |
| weekly-report（表单） | 可见并操作 | 实习周报表单提交（`internship.weekly.submit`） |
| messages | 可见 | 消息中心 |
| me | 可见并操作 | 个人中心，含请假申请（`leave.apply`） |

**学生角色 `permissionActions` 按钮键全集**：`service.apply`、`material.submit`、`internship.checkin`、`internship.weekly.submit`、`leave.apply`、`employment.report`、`profile.correct`（共 7 个）。

---

## 三、教师端页面 × 6 类教师身份 矩阵

| 页面 | 辅导员 `COUNSELOR` | 指导教师(毕设) `MENTOR` | 实习指导教师 `INTERN_MENTOR` | 就业老师 `EMPLOYMENT` | 教务老师 `ACADEMIC` | 学院管理员 `COLLEGE_ADMIN` |
|---|---|---|---|---|---|---|
| workbench | 可见并操作（待办/风险学生汇总入口） | 可见（毕设指导任务汇总） | 可见（实习指导任务汇总） | 可见（就业跟进任务汇总） | 可见（学业预警/学籍处理任务汇总） | 可见并操作（`college.overview` 学院全局概览） |
| todos | 可见并操作（`approval.handle`） | 可见（毕设相关待办） | 可见（实习相关待办） | 可见（就业相关待办） | 可见并操作（`status.handle`） | 可见并操作（`approval.handle`） |
| approval | 可见并操作（`approval.handle`） | 不可见（毕设审阅走 `graduation-guide` 专页，非通用审批页，待后端确认是否复用 approval 页） | 不可见（实习审批走 `internship-review` 专页） | 不可见（待后端确认） | 可见并操作（`approval.handle`） | 可见并操作（`approval.handle`） |
| risk-students | 可见并操作（`risk.handle`、`student.contact`、`care.create`） | 不可见 | 不可见 | 不可见 | 可见并操作（`academic.warning.handle`） | 可见并操作（`risk.handle`） |
| student-detail（360） | 可见并操作（`student360.view`） | 可见并操作（`student360.view`） | 可见（底稿未明确列出 `INTERN_MENTOR` 的 `student360.view`，待后端确认是否具备） | 可见并操作（`student360.view`） | 可见（底稿未明确列出 `ACADEMIC` 的 `student360.view`，待后端确认） | 可见（底稿未明确列出 `COLLEGE_ADMIN` 的 `student360.view`，待后端确认） |
| internship-review | 不可见（辅导员在实习流程中为抄送角色，非批阅角色） | 不可见 | 可见并操作（`intern.weekly.review`、`intern.leave.approve`、`intern.checkin.handle`） | 不可见 | 不可见 | 可见（学院管理员概览视角，具体操作待后端确认） |
| graduation-guide | 不可见 | 可见并操作（`gd.review`、`gd.return`、`gd.guidelog`） | 不可见 | 不可见 | 不可见 | 可见（学院管理员概览视角，待后端确认） |
| employment-follow | 不可见 | 不可见 | 不可见 | 可见并操作（`employment.follow`、`employment.verify`、`job.recommend`） | 不可见 | 可见（学院管理员概览视角，待后端确认） |
| messages | 可见 | 可见 | 可见 | 可见 | 可见 | 可见 |
| me | 可见并操作（含身份信息、设置） | 可见并操作 | 可见并操作 | 可见并操作 | 可见并操作 | 可见并操作 |
| role-switch（身份切换） | 可见并操作（若该教师工号绑定多个身份） | 可见并操作（同左） | 可见并操作（同左） | 可见并操作（同左） | 可见并操作（同左） | 可见并操作（同左） |

> 说明：`urge.send`（学院管理员催办按钮）未与特定页面一一对应，属于跨页面通用操作按钮（如在 workbench / risk-students / approval 页内均可能出现催办入口），具体挂载页面待后端/前端页面细化确认。

---

## 四、各角色 permissionActions 按钮键汇总表

| 角色码 | 中文名 | permissionActions 按钮键列表 |
|---|---|---|
| `STUDENT` | 学生 | `service.apply`、`material.submit`、`internship.checkin`、`internship.weekly.submit`、`leave.apply`、`employment.report`、`profile.correct` |
| `COUNSELOR` | 辅导员/班主任 | `approval.handle`、`risk.handle`、`student.contact`、`care.create`、`student360.view` |
| `MENTOR` | 指导教师(毕设) | `gd.review`、`gd.return`、`gd.guidelog`、`student360.view` |
| `INTERN_MENTOR` | 实习指导教师 | `intern.weekly.review`、`intern.leave.approve`、`intern.checkin.handle`、`visit.create` |
| `EMPLOYMENT` | 就业老师 | `employment.follow`、`employment.verify`、`job.recommend`、`student360.view` |
| `ACADEMIC` | 教务老师 | `academic.warning.handle`、`status.handle`、`approval.handle` |
| `COLLEGE_ADMIN` | 学院管理员 | `college.overview`、`risk.handle`、`approval.handle`、`urge.send` |

---

## 五、mock 用户身份示例（用于演示/测试核对）

| 身份 | 姓名 | 学号/工号 | 说明 |
|---|---|---|---|
| 学生 | 林可欣 | 2024010612 | 单一角色 `STUDENT` |
| 教师 | 张明远 | T20190087 | 多身份，可在 `role-switch` 页在 6 类教师身份间切换（具体绑定了几类身份以 `mock/teacher/*` 实际数据为准，待细查 mock 数据文件确认全部绑定身份，本文档不编造具体绑定清单） |

## 六、与 PC 端角色码的映射关系（交叉参考）

详见 `01-角色体系说明.md` 第四节"角色码 PC 端 ↔ miniapp 端 对照小结"，此处不重复列出，避免多处维护口径不一致。
