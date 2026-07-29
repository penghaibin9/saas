# 微信小程序分包候选清单（阶段A仅审计，不施工）

当前学生端与教师端共用一个 uni-app 工程。公共文件中心正在新增页面、组件和SDK，
因此本阶段禁止大规模改动 `pages.json`，只冻结后续候选：

- 主包：登录、角色切换、学生首页、教师工作台、消息、个人中心、公共错误页。
- 学生学工分包：`pages/student/affairs/**`
- 学生教务分包：`pages/student/academic-affairs/**`
- 学生实习分包：学生 internship 相关页面。
- 学生毕设分包：学生 graduation 相关页面。
- 教师学工分包：`pages/teacher/affairs/**` 及高频审批页面。
- 教师教务分包：`pages/teacher/academic-affairs/**`、`academic-task/**`
- 教师实习分包：教师 internship 相关页面。
- 教师毕设分包：教师 graduation 相关页面。
- 公共文件中心分包：等待文件中心客户端目录稳定后由该工程统一裁决。

实施前必须重新生成页面依赖图，确认 tabBar 页面、跨分包组件、分包预下载和文件中心页面，
不得仅按目录机械拆分。
