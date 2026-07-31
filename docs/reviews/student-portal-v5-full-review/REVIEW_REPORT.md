# Student Portal V5 第一阶段真实页面复审报告

- 生成时间：2026-07-31T02:11:41.937Z
- 执行方式：real MySQL + real password login + Chromium
- 页面：0/14 通过；有问题 14；阻塞 0；未检查 0
- 三级 tab：检查 42；有问题 42
- 六套主题：检查 6；有问题 0
- 多分辨率：检查 36；有问题 36
- 控制台错误：1；失败网络请求：1

## 页面验收矩阵

| 路由 | 页面 | 模块 | 结果 | tab 数 | 主要问题 | 证据 |
|---|---|---|---|---:|---|---|
| `/home` | 首页工作台 | 公共门户 | 有问题 | 0 | 关键元素溢出 2 项 | [截图](screenshots/1920x1080--home-首页工作台.jpg) |
| `/profile` | 我的档案 | 个人档案 | 有问题 | 0 | 关键元素溢出 1 项 | [截图](screenshots/1920x1080--profile-我的档案.jpg) |
| `/academic` | 教务学业 | 教务学业 | 有问题 | 0 | 关键元素溢出 1 项 | [截图](screenshots/1920x1080--academic-教务学业.jpg) |
| `/campus-service` | 学工事务 | 学工事务 | 有问题 | 8 | 关键元素溢出 1 项；请假销假: 切换后关键元素溢出 1 项；困难认定: 切换后关键元素溢出 1 项；奖学金与助学金: 切换后关键元素溢出 1 项；我的宿舍: 切换后关键元素溢出 1 项；处分申诉: 切换后关键元素溢出 1 项；心理自评: 切换后关键元素溢出 1 项；活动与第二课堂: 切换后关键元素溢出 1 项；谈心谈话: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--campus-service-学工事务.jpg) |
| `/materials` | 材料补交 | 学工事务 | 有问题 | 3 | 关键元素溢出 1 项；待处理 3: 切换后关键元素溢出 1 项；已完成 2: 切换后关键元素溢出 1 项；全部 5: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--materials-材料补交.jpg) |
| `/internship` | 岗位实习 | 岗位实习 | 有问题 | 14 | 关键元素溢出 1 项；我的实习: 切换后关键元素溢出 1 项；三方协议: 切换后关键元素溢出 1 项；每日打卡: 切换后关键元素溢出 1 项；实习请假: 切换后关键元素溢出 1 项；补卡申请: 切换后关键元素溢出 1 项；岗位意向: 切换后关键元素溢出 1 项；正式申请: 切换后关键元素溢出 1 项；调岗退岗: 切换后关键元素溢出 1 项；企业岗位库: 切换后关键元素溢出 1 项；实习保险: 切换后关键元素溢出 1 项；实习计划: 切换后关键元素溢出 1 项；实习求助: 切换后关键元素溢出 1 项；周报/月报/总结: 切换后关键元素溢出 1 项；实习成绩/自评: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--internship-岗位实习.jpg) |
| `/internship/compliance` | 上岗合规与安全教育 | 岗位实习 | 有问题 | 0 | 关键元素溢出 1 项 | [截图](screenshots/1920x1080--internship-compliance-上岗合规与安全教育.jpg) |
| `/employment` | 就业服务 | 就业服务 | 有问题 | 4 | 关键元素溢出 1 项；我的就业: 切换后关键元素溢出 1 项；生源核对: 切换后关键元素溢出 1 项；去向登记: 切换后关键元素溢出 1 项；签约材料: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--employment-就业服务.jpg) |
| `/orientation` | 迎新报到 | 迎新报到 | 有问题 | 4 | 关键元素溢出 1 项；我的迎新: 切换后关键元素溢出 1 项；信息采集: 切换后关键元素溢出 1 项；绿色通道: 切换后关键元素溢出 1 项；离校: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--orientation-迎新报到.jpg) |
| `/messages` | 消息通知 | 消息中心 | 有问题 | 5 | 关键元素溢出 1 项；全部: 点击后未呈现选中态；全部: 切换后关键元素溢出 1 项；待办 1: 点击后未呈现选中态；待办 1: 切换后关键元素溢出 1 项；通知 1: 点击后未呈现选中态；通知 1: 切换后关键元素溢出 1 项；服务进度 1: 点击后未呈现选中态；服务进度 1: 切换后关键元素溢出 1 项；消息设置: 点击后未呈现选中态；消息设置: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--messages-消息通知.jpg) |
| `/service-hall` | 办事大厅 | 办事大厅 | 有问题 | 4 | 关键元素溢出 1 项；全部事项: 切换后关键元素溢出 1 项；教务学业类: 切换后关键元素溢出 1 项；学工事务类: 切换后关键元素溢出 1 项；毕业就业类: 切换后关键元素溢出 1 项 | [截图](screenshots/1920x1080--service-hall-办事大厅.jpg) |
| `/graduation` | 毕业设计 | 毕业设计 | 有问题 | 0 | 关键元素溢出 1 项 | [截图](screenshots/1920x1080--graduation-毕业设计.jpg) |
| `/not-enabled` | 门户未开通状态 | 公共状态页 | 有问题 | 0 | 关键元素溢出 1 项 | [截图](screenshots/1920x1080--not-enabled-门户未开通状态.jpg) |
| `/module-disabled/not-real` | 模块未开通状态 | 公共状态页 | 有问题 | 0 | 关键元素溢出 1 项 | [截图](screenshots/1920x1080--module-disabled-not-real-模块未开通状态.jpg) |

## 三级 tab 检查

### 学工事务（/campus-service）
- ❌ 请假销假 · [截图](screenshots/1920x1080--campus-service-tab-请假销假.jpg) · 切换后关键元素溢出 1 项
- ❌ 困难认定 · [截图](screenshots/1920x1080--campus-service-tab-困难认定.jpg) · 切换后关键元素溢出 1 项
- ❌ 奖学金与助学金 · [截图](screenshots/1920x1080--campus-service-tab-奖学金与助学金.jpg) · 切换后关键元素溢出 1 项
- ❌ 我的宿舍 · [截图](screenshots/1920x1080--campus-service-tab-我的宿舍.jpg) · 切换后关键元素溢出 1 项
- ❌ 处分申诉 · [截图](screenshots/1920x1080--campus-service-tab-处分申诉.jpg) · 切换后关键元素溢出 1 项
- ❌ 心理自评 · [截图](screenshots/1920x1080--campus-service-tab-心理自评.jpg) · 切换后关键元素溢出 1 项
- ❌ 活动与第二课堂 · [截图](screenshots/1920x1080--campus-service-tab-活动与第二课堂.jpg) · 切换后关键元素溢出 1 项
- ❌ 谈心谈话 · [截图](screenshots/1920x1080--campus-service-tab-谈心谈话.jpg) · 切换后关键元素溢出 1 项

### 材料补交（/materials）
- ❌ 待处理 3 · [截图](screenshots/1920x1080--materials-tab-待处理-3.jpg) · 切换后关键元素溢出 1 项
- ❌ 已完成 2 · [截图](screenshots/1920x1080--materials-tab-已完成-2.jpg) · 切换后关键元素溢出 1 项
- ❌ 全部 5 · [截图](screenshots/1920x1080--materials-tab-全部-5.jpg) · 切换后关键元素溢出 1 项

### 岗位实习（/internship）
- ❌ 我的实习 · [截图](screenshots/1920x1080--internship-tab-我的实习.jpg) · 切换后关键元素溢出 1 项
- ❌ 三方协议 · [截图](screenshots/1920x1080--internship-tab-三方协议.jpg) · 切换后关键元素溢出 1 项
- ❌ 每日打卡 · [截图](screenshots/1920x1080--internship-tab-每日打卡.jpg) · 切换后关键元素溢出 1 项
- ❌ 实习请假 · [截图](screenshots/1920x1080--internship-tab-实习请假.jpg) · 切换后关键元素溢出 1 项
- ❌ 补卡申请 · [截图](screenshots/1920x1080--internship-tab-补卡申请.jpg) · 切换后关键元素溢出 1 项
- ❌ 岗位意向 · [截图](screenshots/1920x1080--internship-tab-岗位意向.jpg) · 切换后关键元素溢出 1 项
- ❌ 正式申请 · [截图](screenshots/1920x1080--internship-tab-正式申请.jpg) · 切换后关键元素溢出 1 项
- ❌ 调岗退岗 · [截图](screenshots/1920x1080--internship-tab-调岗退岗.jpg) · 切换后关键元素溢出 1 项
- ❌ 企业岗位库 · [截图](screenshots/1920x1080--internship-tab-企业岗位库.jpg) · 切换后关键元素溢出 1 项
- ❌ 实习保险 · [截图](screenshots/1920x1080--internship-tab-实习保险.jpg) · 切换后关键元素溢出 1 项
- ❌ 实习计划 · [截图](screenshots/1920x1080--internship-tab-实习计划.jpg) · 切换后关键元素溢出 1 项
- ❌ 实习求助 · [截图](screenshots/1920x1080--internship-tab-实习求助.jpg) · 切换后关键元素溢出 1 项
- ❌ 周报/月报/总结 · [截图](screenshots/1920x1080--internship-tab-周报-月报-总结.jpg) · 切换后关键元素溢出 1 项
- ❌ 实习成绩/自评 · [截图](screenshots/1920x1080--internship-tab-实习成绩-自评.jpg) · 切换后关键元素溢出 1 项

### 就业服务（/employment）
- ❌ 我的就业 · [截图](screenshots/1920x1080--employment-tab-我的就业.jpg) · 切换后关键元素溢出 1 项
- ❌ 生源核对 · [截图](screenshots/1920x1080--employment-tab-生源核对.jpg) · 切换后关键元素溢出 1 项
- ❌ 去向登记 · [截图](screenshots/1920x1080--employment-tab-去向登记.jpg) · 切换后关键元素溢出 1 项
- ❌ 签约材料 · [截图](screenshots/1920x1080--employment-tab-签约材料.jpg) · 切换后关键元素溢出 1 项

### 迎新报到（/orientation）
- ❌ 我的迎新 · [截图](screenshots/1920x1080--orientation-tab-我的迎新.jpg) · 切换后关键元素溢出 1 项
- ❌ 信息采集 · [截图](screenshots/1920x1080--orientation-tab-信息采集.jpg) · 切换后关键元素溢出 1 项
- ❌ 绿色通道 · [截图](screenshots/1920x1080--orientation-tab-绿色通道.jpg) · 切换后关键元素溢出 1 项
- ❌ 离校 · [截图](screenshots/1920x1080--orientation-tab-离校.jpg) · 切换后关键元素溢出 1 项

### 消息通知（/messages）
- ❌ 全部 · [截图](screenshots/1920x1080--messages-tab-全部.jpg) · 点击后未呈现选中态；切换后关键元素溢出 1 项
- ❌ 待办 1 · [截图](screenshots/1920x1080--messages-tab-待办-1.jpg) · 点击后未呈现选中态；切换后关键元素溢出 1 项
- ❌ 通知 1 · [截图](screenshots/1920x1080--messages-tab-通知-1.jpg) · 点击后未呈现选中态；切换后关键元素溢出 1 项
- ❌ 服务进度 1 · [截图](screenshots/1920x1080--messages-tab-服务进度-1.jpg) · 点击后未呈现选中态；切换后关键元素溢出 1 项
- ❌ 消息设置 · [截图](screenshots/1920x1080--messages-tab-消息设置.jpg) · 点击后未呈现选中态；切换后关键元素溢出 1 项

### 办事大厅（/service-hall）
- ❌ 全部事项 · [截图](screenshots/1920x1080--service-hall-tab-全部事项.jpg) · 切换后关键元素溢出 1 项
- ❌ 教务学业类 · [截图](screenshots/1920x1080--service-hall-tab-教务学业类.jpg) · 切换后关键元素溢出 1 项
- ❌ 学工事务类 · [截图](screenshots/1920x1080--service-hall-tab-学工事务类.jpg) · 切换后关键元素溢出 1 项
- ❌ 毕业就业类 · [截图](screenshots/1920x1080--service-hall-tab-毕业就业类.jpg) · 切换后关键元素溢出 1 项

## 六套主题代表证据

- ✅ 学院蓝 · /home · [截图](screenshots/theme-blue--home.jpg)
- ✅ 科技紫 · /academic · [截图](screenshots/theme-purple--academic.jpg)
- ✅ 薄荷绿 · /internship · [截图](screenshots/theme-green--internship.jpg)
- ✅ 活力橙 · /campus-service · [截图](screenshots/theme-orange--campus-service.jpg)
- ✅ 樱花粉 · /graduation · [截图](screenshots/theme-pink--graduation.jpg)
- ✅ 深邃黑 · /service-hall · [截图](screenshots/theme-dark--service-hall.jpg)

## 多分辨率

- ❌ 1440x900 /home：关键元素溢出 2 项 · [截图](screenshots/1440x900--home-responsive.jpg)
- ❌ 1440x900 /profile：关键元素溢出 1 项
- ❌ 1440x900 /academic：关键元素溢出 1 项 · [截图](screenshots/1440x900--academic-responsive.jpg)
- ❌ 1440x900 /campus-service：关键元素溢出 1 项 · [截图](screenshots/1440x900--campus-service-responsive.jpg)
- ❌ 1440x900 /materials：关键元素溢出 1 项
- ❌ 1440x900 /internship：关键元素溢出 1 项 · [截图](screenshots/1440x900--internship-responsive.jpg)
- ❌ 1440x900 /internship/compliance：关键元素溢出 1 项
- ❌ 1440x900 /employment：关键元素溢出 1 项
- ❌ 1440x900 /orientation：关键元素溢出 1 项
- ❌ 1440x900 /messages：关键元素溢出 1 项
- ❌ 1440x900 /service-hall：关键元素溢出 1 项
- ❌ 1440x900 /graduation：关键元素溢出 1 项 · [截图](screenshots/1440x900--graduation-responsive.jpg)
- ❌ 1366x768 /home：关键元素溢出 2 项 · [截图](screenshots/1366x768--home-responsive.jpg)
- ❌ 1366x768 /profile：关键元素溢出 1 项
- ❌ 1366x768 /academic：关键元素溢出 1 项 · [截图](screenshots/1366x768--academic-responsive.jpg)
- ❌ 1366x768 /campus-service：关键元素溢出 1 项 · [截图](screenshots/1366x768--campus-service-responsive.jpg)
- ❌ 1366x768 /materials：关键元素溢出 1 项
- ❌ 1366x768 /internship：关键元素溢出 1 项 · [截图](screenshots/1366x768--internship-responsive.jpg)
- ❌ 1366x768 /internship/compliance：关键元素溢出 1 项
- ❌ 1366x768 /employment：关键元素溢出 1 项
- ❌ 1366x768 /orientation：关键元素溢出 1 项
- ❌ 1366x768 /messages：关键元素溢出 1 项
- ❌ 1366x768 /service-hall：关键元素溢出 1 项
- ❌ 1366x768 /graduation：关键元素溢出 1 项 · [截图](screenshots/1366x768--graduation-responsive.jpg)
- ❌ 1024x768 /home：关键元素溢出 2 项 · [截图](screenshots/1024x768--home-responsive.jpg)
- ❌ 1024x768 /profile：关键元素溢出 1 项
- ❌ 1024x768 /academic：关键元素溢出 1 项 · [截图](screenshots/1024x768--academic-responsive.jpg)
- ❌ 1024x768 /campus-service：关键元素溢出 1 项 · [截图](screenshots/1024x768--campus-service-responsive.jpg)
- ❌ 1024x768 /materials：关键元素溢出 1 项
- ❌ 1024x768 /internship：关键元素溢出 1 项 · [截图](screenshots/1024x768--internship-responsive.jpg)
- ❌ 1024x768 /internship/compliance：关键元素溢出 1 项
- ❌ 1024x768 /employment：关键元素溢出 1 项
- ❌ 1024x768 /orientation：关键元素溢出 1 项
- ❌ 1024x768 /messages：关键元素溢出 1 项
- ❌ 1024x768 /service-hall：关键元素溢出 1 项
- ❌ 1024x768 /graduation：关键元素溢出 1 项 · [截图](screenshots/1024x768--graduation-responsive.jpg)

## 登录、权限与刷新

- ✅ unauthenticated direct route redirects to login · http://127.0.0.1:5199/login?redirect=/academic
- ✅ student real password login · http://127.0.0.1:5199/home

## 控制台与网络错误

- console · route:/campus-service · Failed to load resource: the server responded with a status of 403 (Forbidden)
- network · route:/campus-service · GET 403 http://127.0.0.1:8000/api/v1/mobile/affairs/dorm/transfers/my

## 判定边界

- 本报告使用真实数据库、真实账号密码和真实接口，不调用 `/auth/mock-login`。
- 自动化能够证明页面可达、tab 可切换、刷新不丢失、主题生效以及常见溢出问题。
- 自动化不会因为公共 CSS 已命中就判定“逐页设计完成”；还必须对截图进行人工视觉复审并形成 P0–P3 问题清单。