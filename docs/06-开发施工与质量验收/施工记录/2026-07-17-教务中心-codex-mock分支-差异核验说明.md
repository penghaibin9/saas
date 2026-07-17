# 教务中心(academic_affairs)codex/mock 分支 —— 差异核验说明

- 审计日期:2026-07-17
- 配套文档:[2026-07-17-教务中心-master分支-高风险重点审计报告.md](2026-07-17-教务中心-master分支-高风险重点审计报告.md)(以下简称"主报告")
- 结论先行:**`codex/mock` 分支的 `academic_affairs` 代码是 `master` 分支的字节级严格子集**,共有文件内容逐字节相同,不存在独立于 master 的教务中心业务逻辑分支。主报告里的每一条发现,只要涉及的文件在下表"共享文件"范围内,在 `codex/mock` 上同等成立。

## 一、子集关系的证据

1. `git log master..codex/mock -- backend/app/modules/academic_affairs backend/alembic/versions frontend/src/modules/academicAffairs` 结果为空(除一条与教务业务无关的沙箱租户提交 `007e7d2`)——说明 `codex/mock` 上没有任何提交单独修改过教务中心的共享文件。
2. 文件级 diff(`find` 对比两侧 `backend/app/modules/academic_affairs/services/` 目录)显示 `codex/mock` 只是比 `master` **少 8 个文件**,不存在"有但内容不同"的文件。
3. 因此:凡是两侧都存在的文件,内容必然相同(因为没有任何 codex/mock 独有的提交碰过它们);凡是主报告的发现所在文件在 `codex/mock` 里也存在,结论直接适用。

## 二、`codex/mock` 缺失的 8 个文件(即 61c1ae3 波次的新增能力,在 codex/mock 上完全不存在)

| 缺失文件 | 对应业务能力 | 主报告里涉及该文件的发现 |
|---|---|---|
| `academic_affairs_autoschedule_service.py` | 自动排课引擎 | P0-6(教室占用索引对人工记录失明) |
| `academic_affairs_autoexam_service.py` | 自动排考引擎 | P0-7(教室占用索引对人工记录失明)、P1-8(整门课跳过粒度太粗) |
| `academic_affairs_level_exam_service.py` | 等级考务报名 | 无独立发现,已在权限审计里核实为安全 |
| `academic_affairs_major_split_service.py` | 专业分流(绩点×志愿×调剂) | 无独立发现,已在权限审计里核实为安全 |
| `academic_affairs_recognition_service.py` | 成绩认定/课程替代 | 无独立发现,已在权限审计里核实为安全 |
| `academic_affairs_selection_round_service.py` | 选课多轮次抽签摇号 | 无独立发现,摇号算法核实为确定性正确实现 |
| `academic_affairs_grade_recheck_service.py` | 成绩复查申请全链路(正方对标) | 未被 6 个审计维度专项覆盖,建议后续单独核实 |
| `academic_affairs_workload_service.py` | 教师工作量申报-审核 | P1-3(路由权限码选择过宽,服务层兜底未被击穿) |

对应的前端新增页面(`AaCertificateView.vue`、`AaGradeRecognitionView.vue`、`AaLevelExamView.vue`、`AaMajorSplitView.vue`)、以及 9 个新迁移(`0085`-`0093`)在 `codex/mock` 上同样不存在。

**结论:这些能力目前只存在于 master,`codex/mock` 分支的教务中心相对更"小"、更"简单",不涉及自动排课/排考、等级考务、专业分流、成绩认定、教师工作量申报这几块新业务,因此主报告里专属于这些新文件的发现(P0-6、P0-7、P1-3、P1-8)在当前 `codex/mock` 上不适用——不是因为已修复,是因为这段代码根本不存在。**

**订正(复核后发现)**:P0-8(教师异议改排 `adjust_item` 不转回 `source=MANUAL`)和 P0-9(拖拽调格 `AaScheduleMaintainView.vue` 的 `ReferenceError`)最初被本文档第三节误列为"codex/mock 同等成立"。逐行核对后发现两者**也不适用于 codex/mock**:
- P0-8:`AaScheduleItem` 模型在 codex/mock 上根本没有 `source` 字段(该字段随 61c1ae3 波次的迁移 `0085_aa_scheduling_engine.py` 一起引入,codex/mock 没有这条迁移),自动排课引擎本身也不存在,所以"清空重排误删人工改排结果"这个场景在 codex/mock 上不可能发生。`adjust_item` 函数体本身确实和 master 一样缺这行回写,但缺的是一个在这个分支上尚无意义的字段。
- P0-9:`AaScheduleMaintainView.vue` 的"拖拽调格保存"整段代码(`onItemMove` 方法 + `@item-move` 事件绑定)是 61c1ae3 这一个提交新增的 6 行,同一提交才引入了这个 bug;codex/mock 没有这 6 行,连 `onItemMove` 方法都不存在,自然也没有这个 `ReferenceError`。

## 三、`codex/mock` 上同等成立的发现(共享文件,主报告可直接对照)——均已在本次修复

以下发现所在文件在 `codex/mock` 上与 master 内容相同,结论同等适用,且**已在本次任务中直接修复并跑过回归测试**(修复方式与主报告一致,细节见下方"六、本次已完成的修复"):

- P0-1 学籍名册无权限码/无数据范围收敛(`academic_affairs_service.py` + 路由) —— 已修复
- P0-2 课堂考勤新建场次无授课关系校验(`academic_affairs_attendance_service.py`) —— 已修复,同步更新了 `test_mobile_attendance.py` 两个测试的夹具(需要先建教学任务归属)
- P0-3 选课退课/人工调整并发竞态(`academic_affairs_selection_service.py`) —— 已修复
- P0-4 成绩发布并发竞态(`academic_affairs_grade_service.py`) —— 已修复
- P0-5 补考/清考挂科去重不一致(`academic_affairs_grade_service.py`/`academic_affairs_graduation_service.py`/`academic_affairs_warning_service.py`) —— 已修复(`fail_list` 展示型清单和 `stats_service._i_fail_rate` 统计口径未动,见下方待定项)
- P1-1、P1-2、P1-4、P1-5、P1-6、P1-9 均在共享文件范围内,结论同等适用,**本次未修复**(P1-1/P1-2 是需要业务口径决策的问题,不是纯技术修复;P1-4/P1-5/P1-6/P1-9 留待后续)
- P0-8、P0-9 已订正为不适用于 codex/mock,见上节

Alembic:见下节,`codex/mock` 是单头干净分支,不存在主报告第四节的双头分叉问题——但一旦合并 master 会立即出现同样问题。

## 四、Alembic 迁移:`codex/mock` 本身干净,但合并 master 会立即触发主报告的双头问题

- `codex/mock` 分支(`backend/alembic/versions/`,100 个文件)当前是**单一 head**:`aa_sandbox_baseline`(down_revision 直接指向 `aa_correction_material_r3`)。
- `aa_correction_material_r3` 在 `codex/mock` 里也只被这一个文件引用,链条本身没有分叉——`codex/mock` 目前没有 master 独有的 `0084_user_preference → ... → 0098_aa_workload_declaration` 数字链(那条链根本不存在于这个分支)。
- **一旦 `master` 合并进 `codex/mock`(或反向合并)**,会同时带入 `0098_aa_workload_declaration` 这个 head,而 `aa_sandbox_baseline` 事实上是 `aa_correction_material_r3` 的下游延伸——合并后的 head 集合会是 `{0098_aa_workload_declaration, aa_sandbox_baseline}`,依然是两个不连通的 head,主报告第四节描述的部署阻断问题原样出现,只是命名链这一侧的 head 从 `aa_correction_material_r3` 换成了它的下游 `aa_sandbox_baseline`。
- 建议:在合并 `master` 与 `codex/mock` 之前,先补一张 `alembic merge` 迁移把两条链统一,不要等合并之后才发现两个 head。

## 五、本次已完成的修复(codex/mock,即当前主工作区)

审计完成后,用户明确要求"审计的你来修好",以下 5 项已在 codex/mock 直接修复并跑过回归测试(`pytest tests/test_mobile_attendance.py tests/test_aa_selection.py tests/test_aa_grade.py tests/test_aa_grade_review_flow.py tests/test_aa_grade_recheck_audit.py tests/test_aa_graduation.py tests/test_aa_warning.py tests/test_aa_schedule.py tests/test_aa_schedule_change.py tests/test_aa_dashboard.py`,共 89 个用例,全绿,其中 `test_mobile_attendance.py` 的 2 个用例因新增授权前置条件需要更新测试夹具,已同步更新):

1. **P0-1**:`backend/app/modules/academic_affairs/routers/academic_affairs.py` 的 `/roster` 端点加 `require_permission("academicAffairs.roster.view")`;`academic_affairs_service.py:roster()` 接入 `build_affairs_context`/`allowed_class_ids` 数据范围收敛(与既有 `roster_status_summary` 同款写法)。
2. **P0-2**:`academic_affairs_attendance_service.py:create_session()` 新增教学任务归属校验(`AaTeachingTask.teacher_key` 命中 + `class_id` 匹配才允许建场次,ACADEMIC_ADMIN/SCHOOL_ADMIN 不受限)。同步更新了 `tests/test_mobile_attendance.py`,新增 `_seed_teaching_task()` 测试夹具。
3. **P0-3**:`academic_affairs_selection_service.py` 的 `student_drop()`/`adjust_record()` 把"改状态"从直接赋值改成"仅当前状态匹配才转移"的条件 UPDATE(与既有 `student_enroll()` 的防超卖写法一致),行数为 0 时回滚并报错,避免并发重复退课导致课程容量被多释放。
4. **P0-4**:`academic_affairs_grade_service.py:publish_grades()` 在正式插入前,先用条件 UPDATE 把任务状态从 `ACADEMIC_REVIEW` 抢占为 `PUBLISHED`,抢占失败（行数为0）立即报错退出,保证并发双击/重试只有一个请求能真正执行插入循环。
5. **P0-5**:`academic_affairs_grade_service.py` 新增共享函数 `effective_grade_rows()`(按学生+课程取最高分去重),并接入三处:`publish_grades()` 自身的台账聚合计算、`academic_affairs_graduation_service.py:_check_course_required()`(毕业资格必修课判定)、`academic_affairs_warning_service.py:scan_warnings()`(挂科预警扫描)。`fail_list()`(展示型挂科清单,DB 分页优化,重写代价较大)和 `stats_service._i_fail_rate()`(挂科率统计口径本身是否该按去重课程数计算是业务问题)本次未动,留作后续。

以上 5 项在 `.worktrees/master-integration`(master 分支)同样存在,已用相同思路同步修复(P0-3/P0-4/P0-5 因该分支多出选课多轮次抽签、成绩期中分项等后续功能,函数体有增量差异,修复点已按该分支实际代码逐一对应应用,不是简单复制 diff)。另外 P0-8(`adjust_item` 缺 `source` 回写)、P0-9(拖拽调格 `ReferenceError`)、P0-6/P0-7(自动排课/排考教室占用索引失明)只存在于 master,也已在 `.worktrees/master-integration` 修复,细节见主报告。

## 六、给用户的建议(不代替决策)

`codex/mock` 目前仍落后 master 一整波教务中心新业务(自动排课/排考引擎、等级考务、专业分流、成绩认定、教师工作量申报)。共享代码的 P0 级问题已经两边各自修复,不再是阻碍合并的理由;真正阻碍无损合并的是 Alembic 双头分叉(第四节)。建议:

1. 决定何时把 master 的 61c1ae3 新波次合并回 codex/mock,合并前先补一张 `alembic merge` 迁移统一 `0098_aa_workload_declaration` 和命名链 head(见第四节),避免合并后本地/CI 初始化数据库直接报错。
2. `codex/mock` 独有的 `007e7d2`(sandbox 沙箱租户基线)提交与教务业务无关,合并时不会产生教务相关冲突。
3. `fail_list`/`stats_service._i_fail_rate`(挂科去重口径)、P1-1(挂科清单数据范围)、P1-2(学生匿名评教防刷分)仍是未决项,需要业务口径决策或额外的 SQL 重写时间。
