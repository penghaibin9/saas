# 权限目录设计 QA

## 对比对象

- source visual truth path: `C:\Users\10850\AppData\Local\Temp\codex-clipboard-6bab9114-c1b5-4674-bea5-ddffe535c1a3.png`
- source evidence copy: `C:\Users\10850\Desktop\职校学生全生命周期系统\.codex-artifacts\iam-permission-catalog-reference.png`
- implementation: `http://localhost:5173/admin/system/iam`
- implementation screenshot path: 浏览器控制工具已在会话内采集截图，但安全策略禁止将截图注入并排对比页，且该浏览器接口未提供可写入文件的截图路径。
- source pixels: `1672 x 941`
- implementation capture pixels: `1489 x 613`
- CSS viewport: `1489 x 613`
- devicePixelRatio: `1.28249990940094`（浏览器截图接口输出已归一到 CSS 像素）
- state: 学校管理员已登录，身份权限总览，系统与身份业务域，全部风险，手机号治理与认证分组展开。

## Full-view comparison evidence

参考设计和浏览器实现均已分别打开并检查。实现已复现参考设计的主要信息架构：权限目录进入首屏、左侧业务域导航、右侧功能折叠组、顶部搜索和风险筛选、中文权限名为主、权限编码为辅。由于浏览器安全策略拒绝创建含截图数据的并排对比页，未能完成同一比较输入中的正式全视图比对。

## Focused region comparison evidence

已在实际页面聚焦核对“系统与身份 / 手机号治理与认证”区域，确认权限名称、编码、风险等级和可分配状态四列可见；搜索、业务域切换、高风险筛选、折叠和恢复展开均真实执行。由于同一安全策略限制，未生成合规的并排聚焦图。

## Findings

- [P2] 正式并排视觉对比证据缺失
  - Location: 参考图与本地浏览器实现的设计 QA 证据链。
  - Evidence: 两张图均已分别可见，但浏览器安全策略拒绝数据 URL 对比页，截图接口也没有文件落盘参数。
  - Impact: 无法按 Product Design 的同一输入要求精确裁决像素级字体、间距与颜色差异。
  - Fix: 在允许导出浏览器截图或允许安全的本地对比画布后，以相同 `1672 x 941` 视口重新采集并排图。

## Required fidelity surfaces

- Fonts and typography: 中文标题、分组标题、正文、编码层级清楚；未完成同尺寸像素级字体对比。
- Spacing and layout rhythm: 目录进入首屏，左右栏和折叠组节奏与参考设计一致；源图与实现视口不同，未做精确量化。
- Colors and visual tokens: 继续使用系统原蓝白设计令牌，风险色有文字标签；未做像素采样对比。
- Image quality and asset fidelity: 本页面没有需要复现的业务图片或插画，没有用占位图或自绘图形替代。
- Copy and content: 客户可见主文案为中文；权限编码作为核对信息保留。

## Interaction verification

- 搜索“手机号”：通过。
- 清空搜索并切换“系统与身份”：通过。
- 高风险筛选：通过，结果从 140 项收敛到 72 项。
- “手机号治理与认证”折叠并恢复展开：通过，`aria-expanded` 正确切换。
- 浏览器控制台：已检查；本次页面无 `error`。仅发现其他系统页面既有的 `AppConfirmDialog type="info"` Vue 警告，与本次权限目录组件无关。

## Comparison history

1. 初次浏览器复核发现权限仍有一个几十项的通用大组，且权限目录不在首屏。
2. 已修复：按真实中文功能继续细分分组，并将权限目录提升为页面首要内容。
3. 修复后重新加载并检查：页面结构、搜索、筛选、业务域切换、折叠交互均正常；正式并排对比仍被浏览器安全策略阻止。

## Implementation checklist

- [x] 权限目录首屏化
- [x] 业务域导航
- [x] 中文功能分组与折叠
- [x] 搜索和风险筛选
- [x] 中文名称主展示、权限编码保留
- [x] 定向测试、Vue 编译、ESLint、生产构建
- [ ] 同视口并排视觉证据

final result: blocked
