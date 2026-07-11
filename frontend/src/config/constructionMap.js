/**
 * constructionMap.js —— 总施工图数据（供规划占位页 PlannedPlaceholderView 展示，CLAUDE.md §42）。
 * 数据源：docs/00-项目入口与总控/施工图/施工图-0X-*.html（2026-07-11 版），按一级 groupKey + 二级模块 label 索引。
 * 仅静态展示信息：施工顺序 ord、任务包 pkg、业务定位 why、推进指令 instruction；不含任何业务数据。
 * ⚠️ 施工图更新后需同步再生成本文件；不要手改 instruction 文本。
 */
export const CONSTRUCTION_MAP = {
  "workbench": {
    "我的工作台": {
      ord: "1",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对工作台·我的工作台做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "我的待办": {
      ord: "2",
      pkg: "已实现",
      why: "已实现（审批中心承接）。",
      instruction: "对工作台·我的待办做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "审批中心": {
      ord: "3",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对工作台·审批中心做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "消息通知": {
      ord: "4",
      pkg: "待施工",
      why: "统一消息中心，建议随学工 B包一起做（才有真实消息源）。",
      instruction: "开发工作台·消息通知：按统一待办/消息底座（t_unified_todo / t_unified_message）实现，要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "领导驾驶舱": {
      ord: "5",
      pkg: "已实现",
      why: "已实现（数据中心承接）。",
      instruction: "对工作台·领导驾驶舱做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "最近访问": {
      ord: "6",
      pkg: "待施工",
      why: "低优先级体验增强。",
      instruction: "开发工作台·最近访问：按统一待办/消息底座（t_unified_todo / t_unified_message）实现，要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
  },
  "student-affairs": {
    "学生画像": {
      ord: "已有",
      pkg: "已有底座",
      why: "学工自身已实现：6 菜单页+学生360（含学工摘要卡）。维护即可，各业务上线后接摘要下钻。",
      instruction: "对学工中心·学生画像做页面级回归与欠账检查：6 个菜单页+学生360 逐页点检，核对权限/脱敏/审计与历史欠账，只修缺陷不加功能，build/lint 后出报告，不 push。"
    },
    "请假销假": {
      ord: "1",
      pkg: "B包·第1步",
      why: "真实学校最高频学工业务，V1 旗舰闭环：申请→审批→销假/续假→逾期→台账。基于现有 t_cs_leave 扩展 14 态状态机，禁止建平行表。前端双栏审批工作区已就绪。",
      instruction: "开发学工中心·请假销假模块（B包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 B包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：销假与续假、请假台账、请假统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "班级与辅导员": {
      ord: "2",
      pkg: "B包·第2步",
      why: "班级与辅导员绑定是全学工的数据范围载体（辅导员能看哪些学生由它决定）。绑定须同步 t_teacher_student_scope。",
      instruction: "开发学工中心·班级与辅导员模块（B包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 B包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：班级列表、班级画像、班级材料、辅导员考评。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "宿舍与公寓": {
      ord: "3",
      pkg: "B包·第3步",
      why: "房源（楼/房/床）→入住→调宿退宿→检查→异常；夜不归宿自动进风险来源。基于 t_cs_dorm_* 扩展。",
      instruction: "开发学工中心·宿舍与公寓模块（B包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 B包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：房源管理（楼栋/房间/床位）、调宿与退宿、宿舍检查、宿舍异常（含夜不归宿）、宿舍统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "风险预警与处置": {
      ord: "4",
      pkg: "B包·第4步",
      why: "风险中枢：七类来源→分派→处置→关闭。等请假和宿舍上线才有真实数据，故排第 4。",
      instruction: "开发学工中心·风险预警与处置模块（B包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 B包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：风险看板、风险学生、风险处置。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "学工工作台": {
      ord: "5",
      pkg: "B包·第5步",
      why: "学工总览 + 辅导员工作台两张聚合看板，放 B 包最后（有数据看板才不空）。",
      instruction: "开发学工中心·学工工作台模块（B包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 B包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：学工总览、辅导员工作台。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "困难认定": {
      ord: "6",
      pkg: "C包·第6步",
      why: "批次→班评三级审→公示→困难学生库，产出困难等级（奖助上游）。家庭经济强脱敏+审计。",
      instruction: "开发学工中心·困难认定模块（C包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 C包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：认定批次、认定申请、认定审核、公示与异议、困难学生库、认定统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "奖助勤贷补": {
      ord: "7",
      pkg: "C包·第7步",
      why: "统一资助抽象（奖/助/勤/贷/减免临补一套状态机），资格校验引用困难学生库与处分状态。",
      instruction: "开发学工中心·奖助勤贷补模块（C包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 C包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：奖学金管理、勤工助学、助学贷款、减免与临时补助、名单审核与公示、发放台账、资助统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "违纪处分": {
      ord: "8",
      pkg: "C包·第8步",
      why: "登记→审批→决定送达→解除/申诉，基于 t_cs_discipline 升级流程链。独立详情页已就绪。",
      instruction: "开发学工中心·违纪处分模块（C包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 C包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：处分审批、处分决定与送达、处分解除、申诉复核、违纪台账、处分统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "谈心家校": {
      ord: "9",
      pkg: "C包·第9步",
      why: "谈话计划/记录/重点学生跟进 + 家校联系，风险处置的落地出口。",
      instruction: "开发学工中心·谈心家校模块（C包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 C包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：谈话计划、谈话记录、重点学生跟进、家校联系人、家校联系记录、谈心统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "心理关注": {
      ord: "10",
      pkg: "D包·第10步",
      why: "强敏感红线：普通角色只见「需关注」标记，明细越权 403+审计；测评属 P3 接口位。",
      instruction: "开发学工中心·心理关注模块（D包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 D包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：心理关注名单、心理预警摘要、谈话转介与回访、危机升级、心理统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "活动二课与社团": {
      ord: "11",
      pkg: "D包·第11步",
      why: "活动闭环一套底座复用给二课/社团/党团，活动三表已预留。",
      instruction: "开发学工中心·活动二课与社团模块（D包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 D包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：活动管理、活动报名与签到、第二课堂积分、志愿服务、社团管理、学生干部与组织、党团建设、活动统计。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "统计与档案": {
      ord: "12",
      pkg: "D包·第12步",
      why: "归档批次+学生档案包+统计驾驶舱，学校验收收口件。",
      instruction: "开发学工中心·统计与档案模块（D包）。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/学工中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——本任务对应索引里的 D包施工卡与四件套（状态机/API契约/表单字段/交互矩阵）。本轮只做本模块：学工统计、学工归档、学生档案包。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "在校服务与迎新": {
      ord: "承接",
      pkg: "承接入口",
      why: "在校服务 3 页+数字迎新入口；对应新模块上线时按「收编即交付」同一提交加 redirect。",
      instruction: "检查「在校服务与迎新」承接入口可达性与旧路由兼容、菜单高亮；不改迎新代码。"
    },
  },
  "academic-affairs": {
    "学年学期": {
      ord: "1",
      pkg: "第1步",
      why: "全系统时间底座，必须第 1 个做。",
      instruction: "开发教务中心·学年学期模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "校历节次": {
      ord: "2",
      pkg: "第2步",
      why: "节假日/作息/节次，排课考务前提。",
      instruction: "开发教务中心·校历节次模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "学院专业班级": {
      ord: "3",
      pkg: "第3步",
      why: "组织底座（与学工共表，教学视角投影）。",
      instruction: "开发教务中心·学院专业班级模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "学籍管理": {
      ord: "4",
      pkg: "第4步",
      why: "学生数据教务视角，已有「在籍学生」页承接。",
      instruction: "开发教务中心·学籍管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "注册管理": {
      ord: "5",
      pkg: "第5步",
      why: "学期注册与资格核验，衔接迎新缴费。",
      instruction: "开发教务中心·注册管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "学籍异动": {
      ord: "6",
      pkg: "第6步",
      why: "休学/复学/退学/转专业审批链。",
      instruction: "开发教务中心·学籍异动模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "培养方案": {
      ord: "7",
      pkg: "第7步",
      why: "课程学分主数据，毕业审核依据。",
      instruction: "开发教务中心·培养方案模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "课程库": {
      ord: "8",
      pkg: "第8步",
      why: "课程主数据。",
      instruction: "开发教务中心·课程库模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教学计划": {
      ord: "9",
      pkg: "第9步",
      why: "学期开课计划。",
      instruction: "开发教务中心·教学计划模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教学任务": {
      ord: "10",
      pkg: "第10步",
      why: "任课分配+教学班（决定教师能看哪些学生）。",
      instruction: "开发教务中心·教学任务模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "排课管理": {
      ord: "11",
      pkg: "第11步",
      why: "排课规则与冲突检测（自动排课留接口位）。",
      instruction: "开发教务中心·排课管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "课表管理": {
      ord: "12",
      pkg: "第12步",
      why: "班级/教师/学生课表输出。",
      instruction: "开发教务中心·课表管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "调停课": {
      ord: "13",
      pkg: "第13步",
      why: "调停补审批链。",
      instruction: "开发教务中心·调停课模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "选课管理": {
      ord: "14",
      pkg: "第14步",
      why: "选课批次与名额控制。",
      instruction: "开发教务中心·选课管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "考务管理": {
      ord: "15",
      pkg: "第15步",
      why: "考试/考场/监考。",
      instruction: "开发教务中心·考务管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "成绩管理": {
      ord: "16",
      pkg: "第16步",
      why: "录入→提交链（教师端核心）。",
      instruction: "开发教务中心·成绩管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "成绩审核发布更正": {
      ord: "17",
      pkg: "第17步",
      why: "审核→发布→更正审计链（SoD 分离）。",
      instruction: "开发教务中心·成绩审核发布更正模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "补考重修缓考免修": {
      ord: "18",
      pkg: "第18步",
      why: "已有「补考重修成绩」页承接。",
      instruction: "开发教务中心·补考重修缓考免修模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "学业预警": {
      ord: "19",
      pkg: "第19步",
      why: "已有「预警学生」页承接。",
      instruction: "开发教务中心·学业预警模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "毕业资格审核": {
      ord: "20",
      pkg: "第20步",
      why: "多源联动终审，商业化关键卖点。",
      instruction: "开发教务中心·毕业资格审核模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教材管理": {
      ord: "21",
      pkg: "第21步",
      why: "教材征订发放。",
      instruction: "开发教务中心·教材管理模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教学资源": {
      ord: "22",
      pkg: "第22步",
      why: "教室/实训室与预约。",
      instruction: "开发教务中心·教学资源模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教学评价": {
      ord: "23",
      pkg: "第23步",
      why: "评教。",
      instruction: "开发教务中心·教学评价模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教学质量": {
      ord: "24",
      pkg: "第24步",
      why: "督导/教学检查。",
      instruction: "开发教务中心·教学质量模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教务看板": {
      ord: "25",
      pkg: "第25步",
      why: "聚合看板，有数据再做。",
      instruction: "开发教务中心·教务看板模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教务统计": {
      ord: "26",
      pkg: "第26步",
      why: "全域统计。",
      instruction: "开发教务中心·教务统计模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "教务归档": {
      ord: "27",
      pkg: "第27步",
      why: "教务验收收口。",
      instruction: "开发教务中心·教务归档模块。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/教务中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——13B 四件套与开发阶段验收用例按索引取。本轮只做本模块三级页面。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
  },
  "graduation": {
    "毕设看板": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·毕设看板做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "毕设批次": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·毕设批次做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "毕设学生": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·毕设学生做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "题目库": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·题目库做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "选题管理": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·选题管理做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "导师管理与分配": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·导师管理与分配做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "过程指导": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·过程指导做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "开题材料": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·开题材料做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "成果检查": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·成果检查做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "答辩成绩": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·答辩成绩做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
    "预警 · 归档 · 统计": {
      ord: "✓",
      pkg: "已完成",
      why: "已全部实现并验收，只做回归与欠账收口。",
      instruction: "对毕业设计中心·预警 · 归档 · 统计做页面级回归点检（逐三级点击/权限抽查/核对 docs/06-开发施工与质量验收/施工记录/历史欠账.md 毕设欠账），只修缺陷，build/lint 后出报告。"
    },
  },
  "internship": {
    "实习工作台": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·实习工作台的待补强项：当前批次进度、我的待办、数据趋势。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "批次与规则": {
      ord: "✓",
      pkg: "已完成",
      why: "已实现，回归即可。",
      instruction: "对岗位实习中心·批次与规则做回归点检与欠账核对，只修缺陷，出报告。"
    },
    "实习学生": {
      ord: "✓",
      pkg: "已完成",
      why: "已实现，回归即可。",
      instruction: "对岗位实习中心·实习学生做回归点检与欠账核对，只修缺陷，出报告。"
    },
    "企业与岗位": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·企业与岗位的待补强项：企业黑名单。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "匹配与分配": {
      ord: "✓",
      pkg: "已完成",
      why: "已实现，回归即可。",
      instruction: "对岗位实习中心·匹配与分配做回归点检与欠账核对，只修缺陷，出报告。"
    },
    "申请与协议": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·申请与协议的待补强项：学生申请、自主实习申请、岗位申请、审核台账。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "打卡与请假": {
      ord: "✓",
      pkg: "已完成",
      why: "已实现，回归即可。",
      instruction: "对岗位实习中心·打卡与请假做回归点检与欠账核对，只修缺陷，出报告。"
    },
    "周报与任务": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·周报与任务的待补强项：实习计划、实习任务、日报提交、月报提交、周报问题。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "指导与巡访": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·指导与巡访的待补强项：指导计划、指导不足预警、巡访计划。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "风险处置": {
      ord: "✓",
      pkg: "已完成",
      why: "已实现，回归即可。",
      instruction: "对岗位实习中心·风险处置做回归点检与欠账核对，只修缺陷，出报告。"
    },
    "评价与成绩": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·评价与成绩的待补强项：学生对企业评价、学生对岗位评价。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "就业转化与归档统计": {
      ord: "补",
      pkg: "待补强收口",
      why: "主链路已实现；黄色待补强项需收口。",
      instruction: "收口岗位实习中心·就业转化与归档统计的待补强项：实习归档、实习档案包、实习统计、企业统计、学生成绩统计。按 docs/README.md 六步阅读顺序执行（禁止跳步、禁止用旧 docs/modules 路径）：① CLAUDE.md → ② docs/README.md → ③ docs/00-项目入口与总控/00-文档总导航.md → ④ docs/03-业务模块设计/岗位实习中心/README.md → ⑤ 同目录 文档关联索引.md 的【任务路由表】按本任务取必读文档 → ⑥ 只读当前任务相关章节——按设计补强与升级总册和施工与验收归档补齐真实接口与页面能力（不 mock 冒充）。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
  },
  "system": {
    "管理看板": {
      ord: "1",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·管理看板做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "用户账号": {
      ord: "2",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·用户账号做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "角色权限": {
      ord: "3",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·角色权限做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "菜单权限": {
      ord: "4",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·菜单权限做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "按钮权限": {
      ord: "5",
      pkg: "待施工",
      why: "按钮级权限配置。",
      instruction: "开发系统管理·按钮权限：必读 docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md（权限最高约束），任何改动不得扩大任何角色权限。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "数据范围": {
      ord: "6",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·数据范围做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "组织结构": {
      ord: "7",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·组织结构做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "学校参数": {
      ord: "8",
      pkg: "待施工",
      why: "学校参数/业务开关/编号规则（各业务配置统一落点）。",
      instruction: "开发系统管理·学校参数：必读 docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md（权限最高约束），任何改动不得扩大任何角色权限。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "系统与品牌": {
      ord: "9",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·系统与品牌做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "流程配置": {
      ord: "10",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·流程配置做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "审批模板": {
      ord: "11",
      pkg: "待施工",
      why: "审批节点与通知模板。",
      instruction: "开发系统管理·审批模板：必读 docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md（权限最高约束），任何改动不得扩大任何角色权限。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "日志中心": {
      ord: "12",
      pkg: "已实现",
      why: "已实现。",
      instruction: "对系统管理·日志中心做页面级回归与欠账检查：逐页点检现有功能，核对权限/数据范围/脱敏/审计与 docs/06-开发施工与质量验收/施工记录/历史欠账.md 中本模块欠账，只修缺陷不加功能，cd frontend && npm run build && npm run lint 通过后输出报告，不提交、不 push。"
    },
    "安全审计": {
      ord: "13",
      pkg: "待施工",
      why: "敏感操作/登录/导出专项审计。",
      instruction: "开发系统管理·安全审计：必读 docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md（权限最高约束），任何改动不得扩大任何角色权限。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "第三方接口": {
      ord: "14",
      pkg: "待施工",
      why: "API/Webhook/同步任务。",
      instruction: "开发系统管理·第三方接口：必读 docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md（权限最高约束），任何改动不得扩大任何角色权限。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
    "租户配置": {
      ord: "15",
      pkg: "待施工",
      why: "模块授权与套餐（对接平台运营端）。",
      instruction: "开发系统管理·租户配置：必读 docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md（权限最高约束），任何改动不得扩大任何角色权限。要求：前端按已冻结交互形态基准（连续处理=列表+详情双栏、复杂详情=独立页、确认弹窗、复用公共组件、planned 不建空页面）+ 后端接口 + MySQL（Alembic 迁移、utf8mb4、tenant_id）+ 权限与数据范围（不扩大任何角色权限）+ 敏感字段脱敏与审计 + pytest。完成后 cd frontend && npm run build && npm run lint、后端 pytest，更新 docs/06-开发施工与质量验收/施工记录/（新增本模块施工记录）与 docs/06-开发施工与质量验收/施工记录/历史欠账.md，精确暂存本模块文件提交 1 个 commit（禁止 git add -A），不 push、不 tag，输出验收报告。"
    },
  },
}

/** 取某个二级模块的施工卡信息；不存在时返回 null */
export function getConstructionInfo(groupKey, modLabel) {
  const g = CONSTRUCTION_MAP[groupKey]
  return (g && g[modLabel]) || null
}
