# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单、权限或后端事实源。完整机器追溯见 `prototype-manifest.json` 与 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**290**
- 独立 HTML：**283**
- 共享 HTML 路由条目：**9**
- 共享设计文件：**41**
- 首轮工作区：**53**
- 一级中心完整冻结：**0**
- 仓库截图：**0**
- 历史本地截图记录：**309**

## 工作区分布

| 中心 | 当前覆盖 | manifest | 冻结状态 |
|---|---:|---|---|
| 教务中心 | 24 工作区 | `00`–`210` | 未冻结，仍有专业分流 / 排课 / 考勤等缺口 |
| 学工中心 | 11 关键页 | `300-student-affairs-key.json` | 关键页结构完成，非全菜单覆盖 |
| 岗位实习中心 | 10 关键页覆盖12二级 | `310-internship-key.json` | 关键页结构完成，99三级待逐项复核 |
| 毕业设计中心 | 8 工作区 | `320-graduation.json` | 8工作区结构完成，浏览器回归待执行 |

## 教务中心

导航继续按生产 `navPlan.js` 的 29 个二级模块直接到达，禁止恢复第四级聚合分组。

已进入首轮追踪：成绩、成绩审核发布更正、学籍、注册、异动、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表、调停课、选课、考务、补考重修缓考免修、预警、毕业资格、教材、教学资源、教学评价、教学质量、教务归档、教务统计。

待补：专业分流、排课管理复杂工作台、课堂考勤、教务看板统一回归及其他未完成入口。

## 学工中心关键页

| 主入口 | HTML | 主要覆盖 |
|---|---|---|
| 学工总览 | `student-affairs/dashboard.html` | 范围内学生、班级、本人待办、请假、认定、奖助、处分、风险 |
| 学生360 | `student-affairs/student-360.html` | 主档入口、授权业务聚合、敏感访问边界 |
| 请假销假 | `student-affairs/leave-workbench.html` | 审批、续假、返校、销假、逾期、台账 |
| 宿舍异常 | `student-affairs/dorm-exception.html` | 楼栋 / 学生范围、夜不归宿核验、转办闭环 |
| 风险处置 | `student-affairs/risk-workbench.html` | 分派、处置、转派、升级、接管、关闭、重开 |
| 困难认定 | `student-affairs/difficulty-workbench.html` | 批次、审核、公示、异议、学生库、台账、统计 |
| 奖助发放 | `student-affairs/funding-workbench.html` | 项目、评审、公示申诉、发放、失败重试、凭证 |
| 违纪处分 | `student-affairs/discipline-workbench.html` | 调查、审批、送达、申诉、生效、解除、对账 |
| 心理危机 | `student-affairs/mental-crisis.html` | 摘要、点名授权、转介、回访、危机接管、审计 |
| 统计驾驶舱 | `student-affairs/stats-cockpit.html` | 同范围聚合、分子分母、最小样本、下钻 |
| 学生档案包 | `student-affairs/archive-packages.html` | 生成、版本、失败、下载用途、水印与审计 |

未覆盖全量：数字迎新、班级辅导员、谈心家校、活动二课与社团等。

## 岗位实习中心关键页

| 主入口 | HTML | 覆盖二级 / 主链 |
|---|---|---|
| 实习总览 | `internship/dashboard.html` | 工作台、进度、待办、风险、趋势 |
| 批次规则 | `internship/batch-rules.html` | 批次、阶段、打卡 / 周报 / 指导 / 评价 / 成绩规则 |
| 实习学生 | `internship/students.html` | 名单、资格、材料、保险、指导老师 |
| 企业岗位 | `internship/enterprise-position.html` | 企业、资质、黑名单、岗位、专业匹配 |
| 匹配协议 | `internship/match-agreement.html` | 意向、推荐、匹配冲突、申请、三方协议、调岗退岗 |
| 打卡请假 | `internship/attendance-leave.html` | 打卡、补卡、异常、请假、超期未归 |
| 周报指导 | `internship/reports-guidance.html` | 日 / 周 / 月报、批阅、指导、沟通、巡访、整改 |
| 风险处置 | `internship/risk.html` | 岗位、打卡、报告、离岗、投诉、安全、中断 |
| 评价成绩 | `internship/evaluation-score.html` | 企业 / 学生 / 指导评价、合成、审核、发布、复核 |
| 归档统计 | `internship/archive-stats.html` | 就业转化、档案包、合规证据、四类统计 |

99 个三级入口通过 `310-internship-key.json.coveredRoutes` 追踪，冻结前仍需逐项核对字段、权限、状态和 API 参数。

## 毕业设计中心

| 工作区 | HTML | 主要覆盖 |
|---|---|---|
| 毕业设计总览 | `graduation/overview.html` | 批次、资格、导师、进度、待办、风险 |
| 选题与分配 | `graduation/topic.html` | 课题、审核发布、学生选题、导师确认、最终分配 |
| 开题管理 | `graduation/proposal.html` | 要求、提交、评阅、版本、催交、统计 |
| 过程管理 | `graduation/process.html` | 任务、指导、里程碑、中期、问题、延期 |
| 成果提交 | `graduation/artifact.html` | 初稿、定稿、查重、批阅、历史、提醒 |
| 答辩管理 | `graduation/defense.html` | 组、计划、分配、回避、发布、记录、应急 |
| 成绩管理 | `graduation/grade.html` | 三类评分、计算、审核、发布、异议 |
| 归档与统计 | `graduation/archive.html` | 档案、包、审计、统计、通知、预警 |

## 统一冻结状态

新增：

- `prototype-freeze-gates.md`
- `four-window-production-migration-map.md`

当前 283 个 HTML 尚未在同一 HEAD 下完成全量浏览器回归。冻结最低要求为：

- 283 页 × 3 个分辨率 = **849 次**基础渲染
- 控制台错误 0
- 非预期根页面横向溢出 0
- 页面链接无 404
- 默认 / 加载 / 空 / 错误 / 403 / 长数据状态通过
- 抽屉和弹层键盘、焦点陷阱、Escape 与焦点归还通过
- 四中心业务红线通过

完成前：

- PR #27 保持 Draft。
- `prototype-manifest.json.status` 保持 `IN_PROGRESS_NOT_FROZEN`。
- 四条生产施工总控提示词不得启用。
- 不得同时开启四个生产修改窗口。
