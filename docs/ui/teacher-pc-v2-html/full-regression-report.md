# Teacher PC V2 全量视觉与交互回归台账

> PR：#27  
> 分支：`codex/teacher-pc-v2-html-library`  
> 执行源 HEAD：`8344fbf496d14d0cd4e40a119e1de8a1dac72b45`  
> 状态：**全量机器回归通过，但仍保持 Draft / NOT FROZEN**。

## 1. 全量浏览器结果

原型库共有 **290 个独立 HTML**，使用三档桌面视口执行：

- `1280 × 900`
- `1440 × 1000`
- `1920 × 1080`

最低完整回归量：

```text
290 × 3 = 870 次渲染
```

最终执行结果：

```text
870 / 870 PASS
290 / 290 页 PASS
0 次失败
0 页待执行
```

该结果替代此前的历史累计 `546 / 870`。历史分批结果仅用于追溯，不再作为当前冻结口径。

## 2. 同一执行源 HEAD 的页面族结果

- 学工中心全部 15 页：**45 / 45 PASS**；
- 其中学工 11 个关键工作台：**33 / 33 PASS**；
- 毕业设计现行 8 工作区：**24 / 24 PASS**；
- 全库其他页面：已包含在 **870 / 870 PASS** 中。

## 3. 同一执行源 HEAD 的机器审计

### 3.1 总一致性

`tools/check-prototype-consistency.mjs`：**PASS**。

核对范围包括 Manifest 聚合、HTML 存在性、相对 CSS / JavaScript / SVG、相对 HTML 目标、重复 ID、孤儿 HTML、共享资源和 owner 约束。

### 3.2 学工运行增强层

`tools/check-student-affairs-runtime-audit.mjs`：**PASS**。

```text
Manifest：11
关键 HTML：11
增强层正确接入：11 / 11
生产入口：14 / 14
errors：0
```

### 3.3 岗位实习路由投影

`tools/check-internship-route-audit.mjs`：**PASS**。

```text
二级模块：12 / 12
三级叶子：101 / 101
唯一 URL：99 / 99
共享 URL：2 / 2
唯一 owner：99 / 99
errors：0
```

### 3.4 毕业设计工作区投影

`tools/check-graduation-workspace-audit.mjs`：**PASS**。

```text
工作区：8 / 8
三级叶子：50 / 50
唯一 URL：48 / 48
共享 URL：2 / 2
HTML owner：8 / 8
errors：0
```

## 4. 浏览器自动检查范围

每次渲染至少检查：

- 页面脚本完成并生成标题、主标题和业务工作区；
- 控制台 error、`pageerror`、未处理 Promise；
- CSS、JavaScript、SVG 和页面引用可加载；
- 重复 ID 和页面根级横向溢出；
- 默认、加载、空、错误、403 / 无范围、只读和长数据状态；
- 抽屉 / 模态框基础打开与关闭；
- 二级模块、三级页签、面包屑和页面配置基本一致性。

## 5. 仍未完成的冻结验收

870 / 870 证明全库自动浏览器基线通过，**不等于已经达到最终 Freeze**。以下项目仍需真实人工验收：

1. A4 打印、分页、页眉页脚和打印溢出；
2. 复杂宽表、超长中文、超长英文、空数据和超大数据；
3. 连续键盘 Tab / Shift+Tab、Enter、Space、Escape；
4. 多层弹层焦点陷阱、关闭后的焦点归还和视觉焦点；
5. 学生主档、家庭联系人、心理危机、处分、困难认定等敏感业务红线；
6. Windows Chrome 与 Edge 的人工视觉复核。

## 6. 生产权限阻断

原型没有静默伪造以下两个生产事实为一致：

1. 数字迎新：菜单权限 `studentAffairs.orientation.view`，真实路由守卫 `orientation.student.view`；
2. 班级管理：菜单权限 `studentAffairs.class.view`，真实主路由守卫 `campus.record.view`。

这两个问题属于生产权限契约裁决，不在 PR #27 的 HTML 原型范围内修改。

## 7. 当前结论

- 全库浏览器基线：**870 / 870 PASS**；
- 全库独立页面：**290 / 290 PASS**；
- 四项机器审计：**全部 PASS / 0 error**；
- PR 文件范围：仅 `docs/ui/teacher-pc-v2-html/`；
- PR：继续保持 **Open / Draft / 未合并**；
- Manifest：继续保持 `IN_PROGRESS_NOT_FROZEN`；
- 在人工专项和两个生产权限冲突完成裁决前，不记录冻结 HEAD、不转 Ready、不合并 main。

本报告提交后产生的新 HEAD 只包含报告与台账更新。仍需在该报告提交后的最新 HEAD 上重新执行一致性检查，确认报告更新没有造成 Manifest 或文件引用口径漂移。