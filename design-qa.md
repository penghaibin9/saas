# 新闻与资讯页面 Design QA

- Source visual truth path: `C:\Users\10850\AppData\Local\Temp\codex-clipboard-4f425a2a-c1ac-4710-8e35-8d6f47f7d244.png`
- Implementation screenshot reference: Codex Computer Use inline capture，Edge 用户页签 `479169339`，`http://127.0.0.1:5173/news`，2026-09-10 09:40（Asia/Shanghai）
- Viewport: source 1440 × 1024；implementation 1340 × 550 CSS px
- Pixel dimensions / density: source 1440 × 1024 PNG；implementation 1340 × 550 PNG；二者均按 1× CSS 像素目测对照，未做拉伸或密度换算
- State: 桌面端、全部资讯、8 篇内容均由后台发布完成；无登录态依赖

## Full-view comparison evidence

同一次浏览器验收结果中先显示源设计、再显示实现截图。实现保留了源设计的核心信息架构和视觉层级：深海军蓝官网导航、浅色标题与搜索区、横向分类、左侧大图头条、右侧今日关注、最新资讯、专题与订阅区。实现使用真实已发布新闻和项目原创位图，不用占位图、CSS 绘图或外链图片。最终截图控制台 warning/error 为 0。

## Focused region comparison evidence

重点放大检查了页头、标题/搜索、分类、头条和今日关注首屏区域；这些区域包含本轮最关键的字体层级、水平留白、栅格比例、颜色、图片裁切和交互入口。详情正文另在真实文章页检查了标题、正文段落、AI 辅助说明、来源日期与教育部外链。由于源设计的下半屏延续同一列表和侧栏规范，没有额外做重复裁切。

## Findings

- 未发现仍需修复的 P0/P1/P2 问题。
- 字体与排版：沿用官网现有 `PingFang SC / Microsoft YaHei / Noto Sans CJK SC / system-ui` 字体栈；标题、栏目标题、正文和小字层级与源设计一致，中文长标题可换行。
- 间距与布局：最终内容区采用最大 1300px、桌面端 56px 安全边距；主次栏比例、区块间距和分隔线接近源设计，未见重叠和裁切。
- 颜色与视觉 token：沿用官网深海军蓝、品牌蓝、浅灰蓝和细分隔线；对比度、焦点环和状态色可辨。
- 图片质量：4 组原创 JPEG 均由内容发布系统托管并按卡片比例裁切；主题、清晰度和暖色校园氛围符合源设计。
- 文案与内容：栏目文案独立可读；文章为基于权威来源的原创摘要，详情页明确 AI 辅助整理并保留原文链接和来源日期。
- 响应式与可访问性：在 Edge 390 × 844 临时视口验证了手机端语义树、导航收敛、搜索、横向分类、单栏头条/关注/列表/专题顺序；移动截图抓取超时，但页面结构与全部交互节点正常，随后已恢复用户默认视口。

## Comparison history

1. 第一轮发现 P2：桌面端左右边距仅 24px，比源设计拥挤；标题区缺少右侧校园影像，首屏品牌感偏弱。
2. 修复：统一页头、标题区、分类和正文为 1300px 最大宽度及 56px 桌面安全边距；从已发布内容中选取真实校园配图作为低透明度标题区背景，手机端隐藏该装饰图。
3. 第二轮对照：水平节奏、首屏密度和右侧校园氛围已与源设计收敛；控制台无 warning/error，未留下 P0/P1/P2。

## Implementation checklist

- [x] 首屏专业新闻结构
- [x] 分类与关键词搜索
- [x] 头条、今日关注、最新资讯和专题中心
- [x] 新闻详情、来源日期、外部原文链接
- [x] RSS 与 sitemap
- [x] 390px 响应式结构
- [x] 后台发布状态作为唯一公开条件
- [x] 浏览器控制台检查

## Follow-up polish

- P3：正式品牌图形标识尚无仓库内可复用的原始资产，因此本轮保留文字字标，未擅自伪造企业 Logo；获得正式矢量/透明 PNG 后可无风险替换。

final result: passed
