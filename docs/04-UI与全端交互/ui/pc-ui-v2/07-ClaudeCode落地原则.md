# PC 管理端 UI v2 · Claude Code 落地原则

> 配套设计稿：`docs/04-UI与全端交互/ui/pc-ui-v2/00–06`。本文只讲原则，不含代码。
> 目标：只换 UI 表现层，业务零回归。

## 一、铁律（违反任何一条即停止）

1. **不改业务**：`modules/**/api`、`mocks/**`、`router/index.js` 与各 `*.routes.js`、`stores/`、`security/**`、`utils/`、`main.js`、`backend/` 一律不动。
2. **只动表现**：每个 `.vue` 只允许改 `<template>` 结构与 `<style>`；`<script>` 中 data/methods/computed/api 调用、v-if/v-for 逻辑、事件名一律保留。
3. **接口冻结**：所有组件的 props / emits / slots 名称不变。可以加可选 prop，不可删改已有。
4. **品牌与角色**：学校名/Logo/主色一律来自 `ctx.tenantBrandConfig`；可见性一律来自 `ctx.currentRole` / `permissionActions` / `getVisibleAdminMenu(ctx)`。禁止硬编码学校名与角色名。
5. **趋势色**：只看接口 `trendQuality`，禁止按数字正负推断（V2.1 §3.3）。
6. **设计稿是图纸不是代码**：禁止把 `docs/04-UI与全端交互/ui/**` 的 HTML 复制进 `frontend/src`。
7. 不提交 git，不 push；每一步保持可运行（`npm run dev` 无报错、`npm run lint` 通过）。

## 二、改造顺序（严格串行，一层验一层）

1. **tokens.css 改值**：只改变量值、新增少量变量（侧栏底色、主题 class），不删不改名。全站观感先统一。
2. **App.vue 全局基线**：背景、选区色、滚动条。
3. **BasePortalLayout 壳**：52px 顶部信息区（品牌/⌘K/范围镜片/通知/角色切换器）+ 224px 三段式左栏（锚点 → 角色过滤模块分组手风琴 → 主题）。菜单数据消费 `config/adminMenu.js` 的 `getVisibleAdminMenu(ctx)`，布局组件本身仍不写死任何业务菜单。
4. **ui 基础组件**：AppButton / AppCard / AppBadge / AppDrawer 按 06 规范调样式。
5. **common/business 组件**：AppMetricCard（加可选 targetLine）、AppStatusTag / AppRiskTag（语义映射表全局唯一）、DataTable（行高两档+hover 快捷动作）、AdvancedFilter（chip 化）、四态组件。
6. **样板页**：`views/admin/student/StudentListView.vue` 按设计稿 02 改造。
7. **样板页验收通过后**，按顺序扩展：student 其余页 → approval/workflow（设计稿 04）→ internship（设计稿 03）→ orientation / campusService / academic / graduation / employment → dataCenter → system（设计稿 05）→ platform。工作台（设计稿 01）在壳稳定后做。
8. 每个模块完成后跑该模块全部路由，人工过一遍四态与角色切换。

## 三、样板页验收清单（通过才许扩展）

- [ ] 顶栏出现品牌/范围镜片/角色切换器，切角色后列表数据范围变化
- [ ] 左栏为分组菜单，当前模块手风琴展开，徽标计数正确
- [ ] 筛选、状态 chips、密度切换、保存视图可用（mock 数据驱动）
- [ ] 勾选出现批量条，Esc 退出
- [ ] 点行打开 360 抽屉，列表不刷新
- [ ] 空/加载/异常/无权限四态可被 mock 触发
- [ ] 手机号默认脱敏，导出按钮按权限隐藏
- [ ] 六主题切换全部正常（只靠变量，无写死色值）
- [ ] `npm run lint` 通过，控制台无错误
- [ ] 与设计稿 02 逐区块对照，偏差记录后统一裁决，不擅自发挥

## 四、禁止事项

- 禁止引入任何 UI 框架 / 组件库 / CSS 框架（Element、Tailwind 等）。
- 禁止新增全局样式类污染（新类名一律带模块前缀或 scoped）。
- 禁止渐变横幅、玻璃拟态、大面积状态色铺底。
- 禁止一次性全站替换；禁止跨层级"顺手"改动。
- 禁止在组件里写死色值/字号/间距——一律 `var(--*)`。

## 五、主题机制

- 默认学院蓝；`th-b 商务蓝 / th-d 护眼绿 / th-c 雅灰 / th-e 皓白极简 / th-f 墨白极简` 六套，与 v7 原型命名保持一致。
- 实现 = 根节点主题 class 覆盖 tokens 变量；主题偏好存储沿用现有 themePreference 约定；tenantBrandColor 覆盖 `--primary-*` 系。

## 六、出问题怎么办

- 任何一步页面白屏/报错：立即回退该文件，缩小改动半径重来。
- 设计稿与现有 props 冲突：以现有接口为准，在 `docs/04-UI与全端交互/ui/pc-ui-v2/偏差记录.md` 登记，等设计侧裁决。
- 不确定的视觉细节：查 06 规范；规范没写的，参考 01–05 最近似的页面，不自创。
