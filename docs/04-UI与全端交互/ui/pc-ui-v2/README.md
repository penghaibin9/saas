# 高校学生全生命周期管理平台 · PC UI 定稿交付包

> **视觉母版：`00-基准-管理端v6三主题.dc.html`**（登录 / 工作台 / 学生中心 / 学生360 / 审批中心 / 6 套主题色）。
> 模块页 `10–25` 全部从母版派生，壳与 token 完全一致。
> 产品名统一：**高校学生全生命周期管理平台**（学校名走 tenantBrandConfig，禁止硬编码）。
> 本目录 HTML 为设计图纸，禁止整文件复制进 frontend/src。

## 文件清单（对接以此为准）

| 文件 | 内容 | 对应 Vue 视图 |
| --- | --- | --- |
| 00-基准-管理端v6三主题.dc.html | 登录 / 工作台 / 学生中心 / 学生360 / 审批中心 / 6 主题 | Login、AdminWorkbenchView、views/admin/student/*、approval/* |
| 10-岗位实习.dc.html | 过程监管：异常队列 / 批阅积压 / 巡访 | views/admin/internship/* |
| 11-数据中心.dc.html | 驾驶舱：KPI / 学院对比 / 风险趋势 / 生命周期漏斗 | views/admin/dataCenter/* |
| 12-系统管理.dc.html | 角色权限矩阵 / 发布卡 / 审计 | views/admin/system/*、workflow/* |
| 20-数字迎新.dc.html | 报到漏斗 / 未报到跟进 / 绿色通道 | views/admin/orientation/* |
| 21-在校服务.dc.html | 工单队列 / 资助 / 宿舍 | views/admin/campusService/* |
| 22-学业过程.dc.html | 成绩录入 / 学业预警 / 补考 | views/admin/academic/* |
| 23-毕业设计.dc.html | 节点漏斗 / 滞留名单 / 查重 | views/admin/graduation/* |
| 24-就业服务.dc.html | 冲刺看板 / 未落实分层 / 材料核验 | views/admin/employment/* |
| 25-平台运营.dc.html | 租户健康 / 同步任务 / 订单续费 | views/admin/platform/* |

## 统一壳结构（BasePortalLayout 改造目标）

1. 顶栏 56px 玻璃：品牌（tenantBrandConfig）→ ⌘K 搜索 → DEV/环境标 → 数据范围镜片 → 通知 → 角色胶囊
2. 左一级：82px 深蓝渐变图标轨（deep1→deep2），激活 = 玻璃高亮块 + 角标
3. 左二级：196px 浅色业务导航（分组标题 + 计数徽标）
4. 内容区：页头（标题+口径+主按钮）→ 玻璃 Hero（深蓝渐变 + 网格纹理 + orbit 数字站点）→ 提醒条 → 双栏（业务队列 1.62 : 洞察卡 1）

## token（并入 frontend/src/styles/tokens.css）

沿用母版 `:root`：`--pri:#2563EB`、`--ok/--warn/--err`、`--t1~--t4`、`--bg:#EDF2FA`、
`--card:rgba(255,255,255,.9)`、`--deep1:#0B2352/--deep2:#123A80`、`--r:14px`、`--s1/--s2/--s3`。
6 主题 = `.thw.th-a/b/c/d/e/f` 覆盖变量（母版内已完整定义），语义色不随主题变。
数字规则：关键计数必须带语义色（异常红 / 积压黄 / 正常蓝或墨），禁止全屏同色数字。

## Claude Code 落地顺序

tokens.css 并入 → BasePortalLayout 壳 → 工作台 → 学生主档 → 岗位实习 → 审批中心 → 数据中心 → 系统管理 → 迎新/在校/学业/毕设/就业 → 平台运营。
铁律：只改 template+style；保留 mock/api/routes/权限/currentRole/dataScope/tenantBrandConfig；页面禁白屏、禁横向滚动条；每步 `npm run lint && npm run build` 通过；不提交不 push。
详见 `07-ClaudeCode落地原则.md` 与 `页面文件对照表.md`。

## 历史探索（非定稿，仅存档）

01–06、08、09、13、14 为定稿前的探索方向，忽略即可。
