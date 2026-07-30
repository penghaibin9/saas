# 教师/学校管理 PC 端 V2 高保真 HTML 原型库

本目录是 `penghaibin9/saas` 教师/学校管理 PC 端的**设计交付物**，不是生产菜单、生产路由或运行时代码。

## 基线

- 生产基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 原型分支：`codex/teacher-pc-v2-html-library`
- 范围：`/workbench` 与教师/学校管理人员可到达的 `/admin/**`
- 排除：学生 PC、小程序、`/admin/platform/**`、纯开发预览和 redirect-only 页面

## 约束

- 所有新增文件只在 `docs/ui/teacher-pc-v2-html/`
- 不修改生产路由、权限、API、状态机、数据库、菜单配置、生产 tokens 或测试
- `prototype-manifest.json` 是设计交付映射，不是第二份生产菜单事实源
- 原型按钮不执行真实写操作
- “— / 学生A / 课程A”属于明确标注的中性 placeholder，不代表生产数据

## 当前已生成

- 共享 V2 tokens、壳、组件、交互脚本和 SVG 图标体系
- 教师/管理工作台
- 教务工作台
- 成绩分析
- 成绩录入（固定三段 + 动态成绩项）
- 挂科清单（含正常、空、加载和错误状态切换）

打开任意 HTML 即可预览。建议从：

- `workbench/my-workbench/index.html`
- `academic-affairs/dashboard/index.html`
- `academic-affairs/grades/grade-overview.html`

开始。

## 交付索引

- `prototype-manifest.json`：路由 → 组件 → API/字段 → HTML
- `route-coverage.md`：覆盖与缺口
- `PROGRESS.md`：可无损续工状态
- `design-system.md`：视觉和母版规范
