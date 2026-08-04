# 教学质量：开发还原契约

> 本目录是教师 PC V2 高保真 HTML 原型。生产权限、状态、接口、数据范围和审批裁决仍以真实代码与后端为准；原型不新增业务事实。

## 8 个真实入口

| 生产入口 | HTML | 权限 | 核心任务 |
|---|---|---|---|
| 运行质量看板 + 质量报告导出 | `quality-monitor.html` | `academicAffairs.quality.dashboard.view` | 汇总督导、巡课、检查、评价与异常信号，形成风险和待办 |
| 督导听课 | `quality-supervision.html` | `academicAffairs.quality.record.view` | 计划、任务、观察事实、证据、反馈与问题转办 |
| 巡课记录 | `quality-patrol.html` | `academicAffairs.quality.record.view` | 按课表记录现场事实，异常转核验、报修或质量线索 |
| 教学检查 | `quality-inspection.html` | `academicAffairs.quality.record.view` | 冻结标准与抽样规则，执行专项检查并形成可追溯结论 |
| 教学事故 | `quality-incident.html` | `academicAffairs.quality.record.view` | 线索登记、证据保护、调查、说明、定性与申诉衔接 |
| 质量整改 | `quality-rectify.html` | `academicAffairs.quality.rectification.view` | 将确认问题转为责任、措施、期限、证据和验收标准 |
| 整改跟进 | `quality-followup.html` | `academicAffairs.quality.rectification.view` | 独立复查整改有效性，处理无效、重开与复发 |
| 质量归档 | `quality-archive.html` | `academicAffairs.quality.archive.view` | 只读封存计划、检查、证据、结论、整改、复查和下载审计 |

入口名称、URL 与权限已对齐生产 `frontend/src/config/navPlan.js`。生产施工时仍要再次核对真实 Vue 页面、API、状态枚举、按钮级写权限和数据范围。

## 治理主链

```text
质量信号 / 检查计划
→ 记录观察事实与原始证据
→ 事实核验与问题分级
→ 责任确认
→ 生成整改任务
→ 责任单位提交措施与证据
→ 独立复查有效性
→ 关闭、重开或标记复发
→ 只读归档与下载审计
```

## 关键边界

1. 数据异常、评价趋势和投诉只作为线索，不能直接形成责任结论。
2. 督导、巡课和教学检查必须区分观察事实、专业判断和最终定性。
3. 检查标准、抽样方式和清单版本在任务开始后不得静默替换。
4. 教学事故要先保护证据、听取当事人说明并执行回避，再按学校制度定性。
5. 人员处分、学生处分、成绩处理和申诉不能被教学质量页面越权替代。
6. 整改任务必须绑定来源问题、责任人、期限、措施、证据和可验证的验收标准。
7. 上传材料不等于整改有效；复查要验证问题是否真正消除、是否产生副作用、是否复发。
8. 复查人应与整改责任人保持必要独立性；无效整改应重开并保留原历史。
9. 归档记录、原始附件、结论版本和操作审计只读，不允许覆盖式修改。
10. 质量报告导出必须遵守权限、数据范围、脱敏和用途审计。

## 页面状态

每个原型至少声明并可由共享工作台切换：

- 正常态
- 加载态
- 空态
- 错误态
- 403 / 只读态
- 长数据态

业务页还通过页面注释登记草稿、执行中、待核验、逾期、待复查、无效整改、重开、复发、归档锁定等状态。真实枚举仍以后端返回为准。

## 开发 AI 读取顺序

1. 阅读本目录 8 个 HTML `<head>` 中的 route、permission、roles、states 和 boundary。
2. 阅读 `manifest-parts/190-quality.json` 获取机器可读路由、字段和业务边界。
3. 阅读 `shared/v2-quality-workbench.js` 获取信息结构、交互和中性占位数据。
4. 阅读 `shared/v2-quality-workbench.css` 获取风险分层、治理链、证据链和响应式规则。
5. 回到生产 `navPlan.js`、真实路由、Vue 页面、API、服务、模型和权限代码逐项核对。
6. 生产还原只复用设计，不复制原型中的 placeholder 数据、候选枚举或前端权限判断。

## 当前验证口径

- 8 个 HTML、共享 CSS、共享 JS、开发契约和 manifest 已落盘。
- 路由与权限已按 `navPlan.js` 静态核对。
- 当前连接环境未执行本批真实浏览器渲染，因此不能宣称控制台、溢出、焦点或三档分辨率回归已通过。
- 浏览器验证清单见 `regression-report.md`，在原型冻结前必须补齐。
