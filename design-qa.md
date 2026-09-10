# 学校用户入口弹窗 Design QA

- Source visual truth path: `C:\Users\10850\AppData\Local\Temp\codex-clipboard-a96f1c2a-cc83-4f3d-bfe3-0833bb0e15f4.png`
- Implementation screenshot reference: Codex in-app Browser inline capture，tab 12，`http://127.0.0.1:5173/#login`，2026-09-10（Asia/Shanghai）
- Viewport: source image 1090 × 965 px；implementation browser 1280 × 720 CSS px，devicePixelRatio 1.425
- Dialog measurements: source approximately 1018 × 660 px；implementation exactly 900 × 676.8 CSS px
- State: 学校用户入口打开；小程序码配置为空，按真实未配置状态显示

## Full-view comparison evidence

源图与应用内浏览器实现均已实际打开检查。实现保留源图的白色弹窗、深蓝正文、浅蓝卡片、细边框、圆角和深色遮罩，同时把原先三条纵向入口改为三段清晰结构：电脑端三列、手机 H5 两列、微信小程序两列。新增内容没有改变官网主导航和底层登录权限。

1280 × 720 视口下，弹窗位于页面中央，宽 900px；内容区高度 521px、内容高度 593px，可正常纵向滚动，底部说明固定可见。较高视口会一次展示完整内容；窄屏按单列布局并在弹窗内部滚动。

## Focused region comparison evidence

重点检查了标题区、电脑端三卡、H5 双卡、小程序未配置状态和底部边界说明。实现中的两条 H5 地址分别为教师与学生登录深链；应用内浏览器实际打开后页面标题分别为“教师登录”和“学生登录”。小程序未配置真实码时没有伪造二维码或虚假跳转。

## Findings

- 未发现仍需修复的 P0/P1/P2 问题。
- Fonts and typography：沿用官网 `PingFang SC / Microsoft YaHei` 字体体系；标题、分组标题、卡片标题、说明和动作文本层级清楚，未出现异常换行。
- Spacing and layout rhythm：900px 弹窗在桌面端保持三列/两列节奏；720px 高度下仅需 72px 内部滚动，关闭按钮和底部边界说明始终可见。
- Colors and visual tokens：继续使用官网深海军蓝、品牌蓝、教师浅蓝、学生浅绿和浅灰边框；焦点环可见。
- Image quality and asset fidelity：本轮不需要新增装饰图片；微信小程序二维码仅接受运营配置的真实图片，缺失时显示文本状态，不使用占位图或代码伪造。
- Copy and content：电脑端、H5、微信小程序及教师/学生身份均明确区分；“无需安装”“按学校实际开通范围使用”等文案避免误导。
- Interaction and accessibility：两个 H5 深链已实际打开；弹窗语义包含分组标题、链接名称、关闭按钮与可滚动内容；应用内浏览器控制台仅有 Vite 连接调试信息，无 warning/error。

## Comparison history

1. 第一轮实现发现 P1：dotenv 中未加引号的 `#` 被当作注释，两个 H5 地址只到首页，未进入指定身份。
2. 修复：本地开发配置与部署示例中的 H5 地址使用引号包裹，保留完整 hash 路由。
3. 第二轮实测：教师地址进入 `#/pages/login/teacher/index`，学生地址进入 `#/pages/login/student/index`；两页角色标题和登录字段均正确。

## Implementation checklist

- [x] 保留教师/管理人员、学生门户、企业端三个电脑入口
- [x] 新增教师 H5 与学生 H5 独立深链
- [x] 新增教师端与学生端微信小程序展示位
- [x] 未配置小程序码时明确降级，不展示伪造二维码
- [x] 桌面端紧凑分区、窄屏单列、弹窗内部滚动
- [x] 入口配置统一经过 URL 安全校验
- [x] 浏览器实测与控制台检查

## Follow-up polish

- P3：正式教师端、学生端小程序码尚未提供；拿到微信后台生成的两张真实码后，只需配置两个环境变量即可显示，无需再改页面结构。

final result: passed
