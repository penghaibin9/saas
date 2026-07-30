# PROGRESS

## 当前状态

- 状态：**IN PROGRESS**
- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 共享设计系统：`teacher-pc-v2 / 1.1.0`
- 生产代码修改：**否**
- 允许目录外修改：**0**
- 当前最新完成首轮结构工作区：**教学质量**
- 下一候选工作区：**教务归档**

## 本轮重新统计结论

此前 README、PROGRESS、PR 描述和总 manifest 长期停留在：

- 175 个 manifest 条目
- 169 个独立 HTML
- 17 个共享文件
- 15 个首轮工作区

真实原因不是后续原型不存在，而是 `prototype-manifest.json` 的 `aggregation.parts` 只加载到 `120-exam.json`，遗漏已落盘的：

- `130-makeup.json`
- `140-warning.json`
- `150-graduation.json`
- `160-textbook.json`
- `170-resource.json`
- `180-evaluation.json`

本轮补入上述部分，并新增 `190-quality.json`。当前统一口径为：

- manifest 条目：**241**
- 独立 HTML：**235**
- 共享 HTML 路由条目：**8**
- shared 文件：**31**
- 仓库截图：**0**
- 已记录本地历史渲染截图：**309**
- 已完成首轮工作区：**22**
- 完成一级中心：**0**

## 教学评价核验

教学评价结构已完整落盘：

- 8 个真实入口 HTML
- `academic-affairs/evaluation/README.md`
- `academic-affairs/evaluation/regression-report.md`
- `manifest-parts/180-evaluation.json`
- `shared/v2-evaluation-workbench.css`
- `shared/v2-evaluation-workbench.js`

覆盖评教批次、申诉审核、学生评教、教师自评、同行评价、督导评价、评价统计与评价归档。匿名最小样本、身份隔离、回避、结果版本、追加式申诉复核和归档不可覆盖均已进入设计追踪。

## 教学质量补齐

此前最新 HEAD 只有：

- `shared/v2-quality-workbench.css`
- `shared/v2-quality-workbench.js`

缺少可直接打开的页面、模块 manifest、开发还原契约和回归记录。本轮已补齐：

1. `quality-monitor.html`
2. `quality-supervision.html`
3. `quality-patrol.html`
4. `quality-inspection.html`
5. `quality-incident.html`
6. `quality-rectify.html`
7. `quality-followup.html`
8. `quality-archive.html`
9. `academic-affairs/quality/README.md`
10. `academic-affairs/quality/regression-report.md`
11. `manifest-parts/190-quality.json`

路由与权限按生产 `frontend/src/config/navPlan.js` 对齐：

- 看板：`academicAffairs.quality.dashboard.view`
- 督导 / 巡课 / 检查 / 事故：`academicAffairs.quality.record.view`
- 整改 / 跟进：`academicAffairs.quality.rectification.view`
- 归档：`academicAffairs.quality.archive.view`

### 教学质量业务边界

1. 监控信号和评价趋势只是线索，不直接定责。
2. 观察事实、专业判断和最终定性必须分离。
3. 检查标准与抽样规则启动后冻结并保留版本。
4. 教学事故先保护证据、听取说明和执行回避，再按学校制度定性。
5. 质量页面不得替代处分、成绩处理或申诉流程。
6. 整改绑定来源问题、责任、期限、证据和验收标准。
7. 上传材料不等于整改有效；复查需要验证问题消除、副作用与复发。
8. 归档原件与结论版本不可覆盖，下载记录用途和操作人。

## 已完成首轮工作区

1. 成绩管理
2. 成绩审核发布更正
3. 学籍管理
4. 注册管理
5. 学籍异动办理
6. 学院专业班级
7. 学年学期
8. 校历节次
9. 课程库
10. 培养方案
11. 教学任务
12. 课表管理
13. 调停课
14. 选课管理
15. 考务管理
16. 补考重修缓考免修
17. 学业预警
18. 毕业资格审核
19. 教材管理
20. 教学资源
21. 教学评价
22. 教学质量

“首轮完成”只表示重要页面、业务切面、权限候选、状态和高风险边界已经进入设计追踪，不等于生产施工或最终回归完成。

## 导航与公共复用冻结

- 教务中心按 `navPlan.js` 保持 **29 个真实二级模块直接到达**。
- 禁止恢复 8 个原型聚合分组或形成第四级菜单。
- 导航层级固定为：顶部一级中心 → 左侧真实二级模块 → 内容区三级功能。
- 权限与数据范围继续由生产 `navPlan → adminMenu → BasePortalLayout` 和后端裁决。
- 原型还原优先复用生产现有公共组件，不把共享 HTML 渲染脚本带入生产。

## 验证现状

### 已确认

- PR 仍为 Open / Draft / 未合并。
- 当前变更仍仅位于 `docs/ui/teacher-pc-v2-html/`。
- 教学评价 8 页结构、说明、manifest 和共享资源存在。
- 教学质量 8 页、说明、回归清单和 manifest 已落盘。
- 教学质量 URL 与权限已静态对齐 `navPlan.js`。
- 总 manifest 已加载 `00` 至 `190` 的全部现有部分。

### 尚未确认

- 当前 **235 个独立 HTML** 尚未在同一最新 HEAD 下完成一次全量真实浏览器回归。
- 教学质量 8 页当前浏览器渲染次数：**0**。
- 教学质量控制台错误、横向溢出、键盘操作、焦点陷阱和三档分辨率：**待验证**。
- 截图和打印 PDF 未提交仓库。
- 教务中心、教师 PC 和四个重点一级中心尚未整体冻结。

未执行的验证不得描述为通过。

## 下一批精确起点

继续按生产 `navPlan.js` 顺序进入 **教务归档**：

1. 核对 `/admin/academic-affairs/archive`、`/archive/precheck`、`?entry=batch`、`/archive/export` 的真实 Vue、API、权限和状态。
2. 区分归档批次工作台、9 数据域完整性预检、批量归档与导出下载面板。
3. 覆盖预检失败、缺失提醒、只读封存、重复归档、部分失败、下载用途和审计。
4. 判断哪些切面复用列表 / 详情 / 导出母版，哪些必须保留独立高保真 HTML。
5. 教务归档完成后进入教务统计，再回补专业分流、排课管理、课堂考勤等仍缺工作区。

## Git 纪律

- 保持 Draft PR #27
- 不合并 `main`
- 不创建新 PR
- 每批只修改 `docs/ui/teacher-pc-v2-html/`
- 生产代码只读
