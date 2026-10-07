"""sandbox-school 跨表/跨模块业务关系闭包审计。

旧的 standard-20k 验收主要回答“每张表有多少行”。这不足以证明数据能沿真实
业务链流动：子表可能有行、页面可能有数字，但任务、版本、正式事实和下游投影并
没有指向同一个来源。

本模块只读，不修数据。它同时检查：
1. 数据库是否真正声明关系；
2. 核心业务外键式引用是否存在且同租户；
3. 关键快照是否仍与 authoritative source 一致；
4. 已发布事实是否满足上游数量/版本闭包。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text


@dataclass(frozen=True)
class RelationshipCheck:
    code: str
    domain: str
    severity: str
    title: str
    sql: str
    repair_hint: str


def _orphan(child: str, child_key: str, parent: str, *, parent_key: str = "id",
            child_filter: str = "", required: bool = True) -> str:
    null_clause = f"c.{child_key} IS NULL OR " if required else ""
    extra = f" AND {child_filter}" if child_filter else ""
    return f"""
        SELECT COUNT(*)
          FROM {child} c
          LEFT JOIN {parent} p
            ON p.{parent_key}=c.{child_key}
           AND p.tenant_id=c.tenant_id
           AND p.is_deleted=0
         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0{extra}
           AND ({null_clause}p.{parent_key} IS NULL)
    """


CHECKS = (
    # 主数据与账号
    RelationshipCheck("MASTER_STUDENT_CLASS", "master", "P0", "学生必须归属有效班级",
                      _orphan("t_student_profile", "class_id", "t_class"), "重建学生→班级关系"),
    RelationshipCheck("MASTER_STUDENT_MAJOR", "master", "P0", "学生必须归属有效专业",
                      _orphan("t_student_profile", "major_id", "t_major"), "重建学生→专业关系"),
    RelationshipCheck("MASTER_STUDENT_COLLEGE", "master", "P0", "学生必须归属有效学院",
                      _orphan("t_student_profile", "college_id", "t_college"), "重建学生→学院关系"),
    RelationshipCheck("MASTER_ACCOUNT_LINK", "master", "P0", "学生账号必须同时回链学生和用户",
                      """SELECT COUNT(*) FROM t_student_account_link l
                          LEFT JOIN t_student_profile s ON s.id=l.student_id AND s.tenant_id=l.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_user u ON u.id=l.user_id AND u.tenant_id=l.tenant_id AND u.is_deleted=0
                         WHERE l.tenant_id=:tenant_id AND l.is_deleted=0 AND (s.id IS NULL OR u.id IS NULL)""",
                      "按 student_id/user_id 重新建立唯一 ACTIVE 账号绑定"),
    RelationshipCheck("MASTER_ROLE_SCOPE_ASSIGNMENT", "master", "P0", "角色范围必须回链同一用户的有效角色关系",
                      """SELECT COUNT(*) FROM t_role_assignment_scope s
                          LEFT JOIN t_user_role ur ON ur.id=s.user_role_id AND ur.tenant_id=s.tenant_id
                           AND ur.user_id=s.user_id AND ur.status='ACTIVE' AND ur.is_deleted=0
                          LEFT JOIN t_role r ON r.id=ur.role_id AND r.tenant_id=s.tenant_id
                           AND r.role_code=s.role_code AND r.status='ACTIVE' AND r.is_deleted=0
                          LEFT JOIN t_user u ON u.id=s.user_id AND u.tenant_id=s.tenant_id
                           AND u.status='ACTIVE' AND u.is_deleted=0
                         WHERE s.tenant_id=:tenant_id AND s.status='ACTIVE' AND s.is_deleted=0
                           AND (ur.id IS NULL OR r.id IS NULL OR u.id IS NULL)""",
                      "从有效 user-role 关系重新投影稳定范围主键"),
    RelationshipCheck("MASTER_ROLE_SCOPE_RESOURCE", "master", "P0", "角色范围节点必须指向有效组织或学生主档",
                      """SELECT COUNT(*) FROM t_role_assignment_scope s
                          LEFT JOIN t_college c ON s.scope_type='COLLEGE' AND c.id=s.scope_id
                           AND c.tenant_id=s.tenant_id AND c.status='ACTIVE' AND c.is_deleted=0
                          LEFT JOIN t_major m ON s.scope_type='MAJOR' AND m.id=s.scope_id
                           AND m.tenant_id=s.tenant_id AND m.status='ACTIVE' AND m.is_deleted=0
                          LEFT JOIN t_class cl ON s.scope_type='CLASS' AND cl.id=s.scope_id
                           AND cl.tenant_id=s.tenant_id AND cl.status='ACTIVE' AND cl.is_deleted=0
                          LEFT JOIN t_student_profile st ON s.scope_type='STUDENT' AND st.id=s.scope_id
                           AND st.tenant_id=s.tenant_id AND st.status='ACTIVE' AND st.is_deleted=0
                         WHERE s.tenant_id=:tenant_id AND s.status='ACTIVE' AND s.is_deleted=0
                           AND NOT ((s.scope_type='SCHOOL' AND s.scope_id=0)
                                OR (s.scope_type='COLLEGE' AND c.id IS NOT NULL)
                                OR (s.scope_type='MAJOR' AND m.id IS NOT NULL)
                                OR (s.scope_type='CLASS' AND cl.id IS NOT NULL)
                                OR (s.scope_type='STUDENT' AND st.id IS NOT NULL))""",
                      "按范围类型重新解析学院、专业、班级或学生稳定主键"),
    RelationshipCheck("MASTER_MANUAL_ROLE_SCOPE_COVERAGE", "master", "P0", "需节点授权的演示角色必须至少配置一个有效范围",
                      """SELECT COUNT(*) FROM t_user_role ur
                          JOIN t_user u ON u.id=ur.user_id AND u.tenant_id=ur.tenant_id
                           AND u.status='ACTIVE' AND u.is_deleted=0
                          JOIN t_role r ON r.id=ur.role_id AND r.tenant_id=ur.tenant_id
                           AND r.status='ACTIVE' AND r.is_deleted=0
                         WHERE ur.tenant_id=:tenant_id AND ur.status='ACTIVE' AND ur.is_deleted=0
                           AND r.role_code IN ('COLLEGE_ADMIN','STUDENT_AFFAIRS','COUNSELOR',
                               'PSYCHOLOGY_TEACHER','GD_COLLEGE_ADMIN','GD_MAJOR_ADMIN','EMPLOYMENT_TEACHER')
                           AND NOT EXISTS (
                               SELECT 1 FROM t_role_assignment_scope s
                                WHERE s.tenant_id=ur.tenant_id AND s.user_role_id=ur.id
                                  AND s.user_id=ur.user_id AND s.role_code=r.role_code
                                  AND s.status='ACTIVE' AND s.is_deleted=0
                           )""",
                      "从旧范围、组织任职或真实业务分配投影新版角色范围"),
    RelationshipCheck("MASTER_PSY_SCOPE_COMPATIBILITY", "master", "P0", "心理老师逐生授权必须同步敏感域范围消费者",
                      """SELECT COUNT(*) FROM t_role_assignment_scope s
                          JOIN t_user u ON u.id=s.user_id AND u.tenant_id=s.tenant_id AND u.is_deleted=0
                          JOIN t_student_profile st ON st.id=s.scope_id AND st.tenant_id=s.tenant_id AND st.is_deleted=0
                          LEFT JOIN t_teacher_student_scope legacy
                            ON legacy.tenant_id=s.tenant_id AND legacy.teacher_key=u.login_name
                           AND legacy.role_code='PSYCHOLOGY_TEACHER' AND legacy.scope_type='PSY_STUDENT'
                           AND legacy.ref_value=st.student_no AND legacy.status='ACTIVE' AND legacy.is_deleted=0
                         WHERE s.tenant_id=:tenant_id AND s.role_code='PSYCHOLOGY_TEACHER'
                           AND s.scope_type='STUDENT' AND s.status='ACTIVE' AND s.is_deleted=0
                           AND legacy.id IS NULL""",
                      "心理逐生授权需同时写入新版范围和 TeacherStudentScope 兼容投影"),

    # 迎新
    RelationshipCheck("ORI_STUDENT_PROFILE", "orientation", "P0", "迎新学生必须来自学生主档",
                      _orphan("t_orientation_student", "student_id", "t_student_profile"), "从主档生成迎新投影"),
    RelationshipCheck("ORI_MATERIAL_PARENT", "orientation", "P0", "迎新材料必须属于迎新学生",
                      _orphan("t_orientation_material", "ori_student_id", "t_orientation_student"), "按迎新学生重建材料"),
    RelationshipCheck("ORI_GREEN_PARENT", "orientation", "P0", "绿色通道申请必须属于迎新学生",
                      _orphan("t_green_channel_application", "ori_student_id", "t_orientation_student"), "按迎新学生重建申请"),
    RelationshipCheck("ORI_EXCEPTION_PARENT", "orientation", "P0", "迎新异常必须属于迎新学生",
                      _orphan("t_orientation_exception", "ori_student_id", "t_orientation_student"), "按迎新学生重建异常"),
    RelationshipCheck("ORI_FOLLOWUP_PARENT", "orientation", "P0", "异常跟进必须属于真实异常",
                      _orphan("t_orientation_exception_followup", "exception_id", "t_orientation_exception"), "按异常单重建跟进"),

    # 学业与校园服务
    RelationshipCheck("ACAD_STUDENT_PROFILE", "academic", "P0", "学业学生必须来自学生主档",
                      _orphan("t_acad_student", "student_id", "t_student_profile"), "从学生主档生成学业投影"),
    RelationshipCheck("ACAD_GRADE_STUDENT", "academic", "P0", "成绩必须属于学业学生",
                      _orphan("t_acad_grade", "acad_student_id", "t_acad_student"), "修复成绩→学业学生回链"),
    RelationshipCheck("ACAD_GRADE_TERM", "academic", "P0", "成绩学期必须回链正式学期字典",
                      """SELECT COUNT(*) FROM t_acad_grade g
                          LEFT JOIN t_aa_term term
                            ON CONCAT(term.year_code,'-',term.term_no)=g.term
                           AND term.tenant_id=g.tenant_id AND term.is_deleted=0
                         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND term.id IS NULL""",
                      "先建立完整学期字典，再导入或发布成绩"),
    RelationshipCheck("ACAD_WARNING_STUDENT", "academic", "P0", "学业预警必须属于学业学生",
                      _orphan("t_acad_warning", "acad_student_id", "t_acad_student"), "从正式成绩扫描生成预警"),
    RelationshipCheck("ACAD_WARNING_GRADE_EVIDENCE", "academic", "P0", "挂科预警必须有足量当前正式成绩证据",
                      """SELECT COUNT(*) FROM t_acad_warning w
                          LEFT JOIN (
                              SELECT acad_student_id,COUNT(*) fail_count
                                FROM t_acad_grade
                               WHERE tenant_id=:tenant_id AND is_deleted=0 AND record_status='ACTIVE'
                                 AND pass_status IN ('FAIL','FAILED')
                               GROUP BY acad_student_id
                          ) g ON g.acad_student_id=w.acad_student_id
                         WHERE w.tenant_id=:tenant_id AND w.is_deleted=0 AND w.source_code='EXAM_FAIL'
                           AND COALESCE(g.fail_count,0)<2""",
                      "FAIL_2_PLUS 只能由同一学业学生至少两门 ACTIVE 不及格正式成绩触发"),
    RelationshipCheck("ACAD_STUDENT_GRADE_WARNING_AGGREGATES", "academic", "P0", "学业学生挂科数和预警数必须与正式明细回写一致",
                      """SELECT COUNT(*) FROM t_acad_student a
                          LEFT JOIN (
                              SELECT acad_student_id,COUNT(*) fails FROM t_acad_grade
                               WHERE tenant_id=:tenant_id AND is_deleted=0 AND record_status='ACTIVE'
                                 AND pass_status IN ('FAIL','FAILED') GROUP BY acad_student_id
                          ) g ON g.acad_student_id=a.id
                          LEFT JOIN (
                              SELECT acad_student_id,COUNT(*) warnings FROM t_acad_warning
                               WHERE tenant_id=:tenant_id AND is_deleted=0 AND record_status='ACTIVE'
                               GROUP BY acad_student_id
                          ) w ON w.acad_student_id=a.id
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
                           AND (a.failed_count<>COALESCE(g.fails,0)
                                OR a.warning_count<>COALESCE(w.warnings,0))""",
                      "成绩发布/更正和预警扫描必须同事务刷新 AcademicStudent 聚合"),
    RelationshipCheck("ACAD_INTERVENTION_WARNING", "academic", "P0", "干预记录必须属于预警",
                      _orphan("t_acad_intervention", "warning_id", "t_acad_warning"), "按预警生成干预记录"),
    RelationshipCheck("ACAD_GRADE_COURSE", "academic", "P1", "历史成绩必须回链课程库",
                      """SELECT COUNT(*) FROM t_acad_grade g
                          LEFT JOIN t_aa_course c ON c.id=g.course_id AND c.tenant_id=g.tenant_id AND c.is_deleted=0
                         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND (g.course_id IS NULL OR c.id IS NULL)""",
                      "在课程库形成后按课程代码/专业/版本回填 course_id"),
    RelationshipCheck("ACAD_GRADE_PROVENANCE", "academic", "P1", "已发布成绩必须有来源凭证",
                      """SELECT COUNT(*) FROM t_acad_grade g
                          LEFT JOIN t_aa_grade_task gt
                            ON gt.id=g.grade_task_id AND gt.tenant_id=g.tenant_id AND gt.is_deleted=0
                          LEFT JOIN t_aa_effective_grade_policy_snapshot snap
                            ON snap.id=g.source_biz_id AND snap.tenant_id=g.tenant_id
                           AND snap.academic_grade_id=g.id AND snap.is_deleted=0
                         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND g.source='PUBLISH'
                           AND gt.id IS NULL
                           AND NOT (g.source_biz_type='EFFECTIVE_GRADE_POLICY_SNAPSHOT' AND snap.id IS NOT NULL)""",
                      "正常发布回链 GradeTask；历史导入回链不可变策略与课程身份快照"),
    RelationshipCheck("CAMPUS_STUDENT_PROFILE", "campus", "P0", "校园服务学生必须来自学生主档",
                      _orphan("t_cs_service_student", "student_id", "t_student_profile"), "从主档生成校园服务投影"),
    RelationshipCheck("CAMPUS_DORM_STUDENT", "campus", "P0", "住宿记录必须属于校园服务学生",
                      _orphan("t_cs_dorm_record", "cs_student_id", "t_cs_service_student"), "按校园服务学生生成住宿事实"),

    # 学生工作：困难认定、资助、处分、风险、二课、社团与辅导员责任链
    RelationshipCheck("AFFAIRS_AID_APPLY", "student_affairs", "P0", "困难认定申请必须回链批次和学生",
                      """SELECT COUNT(*) FROM t_affairs_aid_apply a
                          LEFT JOIN t_affairs_aid_batch b ON b.id=a.batch_id AND b.tenant_id=a.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=a.student_id AND s.tenant_id=a.tenant_id AND s.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND (b.id IS NULL OR s.id IS NULL)""",
                      "困难认定申请只能从有效批次和学生主档生成"),
    RelationshipCheck("AFFAIRS_AID_FAMILY", "student_affairs", "P0", "家庭经济信息必须与申请和学生一致",
                      """SELECT COUNT(*) FROM t_affairs_aid_family_economy f
                          LEFT JOIN t_affairs_aid_apply a ON a.id=f.apply_id AND a.tenant_id=f.tenant_id AND a.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=f.student_id AND s.tenant_id=f.tenant_id AND s.is_deleted=0
                         WHERE f.tenant_id=:tenant_id AND f.is_deleted=0
                           AND (a.id IS NULL OR s.id IS NULL OR a.student_id<>f.student_id)""",
                      "家庭经济隔离表必须复用申请单 student_id"),
    RelationshipCheck("AFFAIRS_AID_APPROVED_HISTORY", "student_affairs", "P1", "已认定困难等级必须进入追加式历史",
                      """SELECT COUNT(*) FROM t_affairs_aid_apply a
                          LEFT JOIN t_affairs_aid_level_history h ON h.apply_id=a.id AND h.tenant_id=a.tenant_id
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND a.status='APPROVED' AND h.id IS NULL""",
                      "APPROVED 与等级历史必须在同一事务写入"),
    RelationshipCheck("AFFAIRS_FUNDING_BATCH", "student_affairs", "P0", "资助批次必须属于资助项目",
                      _orphan("t_affairs_funding_batch", "project_id", "t_affairs_funding_project"),
                      "先建项目，再开放年度批次"),
    RelationshipCheck("AFFAIRS_FUNDING_APPLICATION", "student_affairs", "P0", "资助申请必须回链批次和学生",
                      """SELECT COUNT(*) FROM t_affairs_funding_application a
                          LEFT JOIN t_affairs_funding_batch b ON b.id=a.batch_id AND b.tenant_id=a.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=a.student_id AND s.tenant_id=a.tenant_id AND s.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND (b.id IS NULL OR s.id IS NULL)""",
                      "资助申请只能从有效批次和学生主档生成"),
    RelationshipCheck("AFFAIRS_FUNDING_DISBURSEMENT", "student_affairs", "P0", "发放台账必须与批准申请的批次、学生和金额一致",
                      """SELECT COUNT(*) FROM t_affairs_funding_disbursement d
                          LEFT JOIN t_affairs_funding_application a
                            ON a.id=d.application_id AND a.tenant_id=d.tenant_id AND a.is_deleted=0
                         WHERE d.tenant_id=:tenant_id AND d.is_deleted=0
                           AND (a.id IS NULL OR a.batch_id<>d.batch_id OR a.student_id<>d.student_id
                                OR COALESCE(a.approved_amount,-1)<>COALESCE(d.approved_amount_snapshot,-1))""",
                      "批准与发放台账必须在同一来源链冻结快照"),
    RelationshipCheck("AFFAIRS_FUNDING_GRANTED_LEDGER", "student_affairs", "P1", "已批准资助必须生成发放台账",
                      """SELECT COUNT(*) FROM t_affairs_funding_application a
                          LEFT JOIN t_affairs_funding_disbursement d
                            ON d.application_id=a.id AND d.tenant_id=a.tenant_id AND d.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND a.status='GRANTED' AND d.id IS NULL""",
                      "GRANTED 与待发放台账必须原子生成"),
    RelationshipCheck("AFFAIRS_DISCIPLINE_STUDENT", "student_affairs", "P0", "处分主案必须属于学生主档",
                      _orphan("t_affairs_discipline_case", "student_id", "t_student_profile"),
                      "处分立案只接受有效 student_id"),
    RelationshipCheck("AFFAIRS_DISCIPLINE_PROJECTION", "student_affairs", "P1", "生效处分必须回链校园服务投影",
                      """SELECT COUNT(*) FROM t_affairs_discipline_case c
                          LEFT JOIN t_cs_discipline d
                            ON d.id=c.cs_discipline_id AND d.source_case_id=c.id
                           AND d.tenant_id=c.tenant_id AND d.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND c.status='EFFECTIVE' AND d.id IS NULL""",
                      "EFFECTIVE 主案与校园服务投影必须同事务写入"),
    RelationshipCheck("AFFAIRS_DISCIPLINE_VERSION", "student_affairs", "P1", "生效处分必须有追加式决定版本",
                      """SELECT COUNT(*) FROM t_affairs_discipline_case c
                          LEFT JOIN t_affairs_discipline_decision_version v
                            ON v.case_id=c.id AND v.tenant_id=c.tenant_id
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND c.status='EFFECTIVE' AND v.id IS NULL""",
                      "处分决定禁止只改主表状态，必须追加决定版本"),
    RelationshipCheck("AFFAIRS_RISK_STUDENT", "student_affairs", "P0", "风险记录必须属于学生主档",
                      _orphan("t_affairs_risk_record", "student_id", "t_student_profile"),
                      "风险中枢统一使用学生主档 id"),
    RelationshipCheck("AFFAIRS_RISK_HANDLE", "student_affairs", "P0", "风险处置必须属于风险记录",
                      _orphan("t_affairs_risk_handle_record", "risk_id", "t_affairs_risk_record"),
                      "所有处置动作追加到同一风险单"),
    RelationshipCheck("AFFAIRS_ACTIVITY_SIGNUP", "student_affairs", "P0", "活动报名必须回链活动和学生",
                      """SELECT COUNT(*) FROM t_affairs_activity_signup x
                          LEFT JOIN t_affairs_activity a ON a.id=x.activity_id AND a.tenant_id=x.tenant_id AND a.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=x.student_id AND s.tenant_id=x.tenant_id AND s.is_deleted=0
                         WHERE x.tenant_id=:tenant_id AND x.is_deleted=0 AND (a.id IS NULL OR s.id IS NULL)""",
                      "二课报名只接受有效活动和学生"),
    RelationshipCheck("AFFAIRS_ACTIVITY_CREDIT", "student_affairs", "P0", "二课积分必须回链学生及其来源活动",
                      """SELECT COUNT(*) FROM t_affairs_activity_credit c
                          LEFT JOIN t_student_profile s ON s.id=c.student_id AND s.tenant_id=c.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_affairs_activity a ON a.id=c.activity_id AND a.tenant_id=c.tenant_id AND a.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND (s.id IS NULL OR (c.activity_id IS NOT NULL AND a.id IS NULL))""",
                      "积分流水必须保留活动来源；手工调整才允许 activity_id 为空"),
    RelationshipCheck("AFFAIRS_COUNSELOR_ASSIGNMENT", "student_affairs", "P0", "辅导员责任关系必须回链班级和用户",
                      """SELECT COUNT(*) FROM t_affairs_counselor_assignment a
                          LEFT JOIN t_class c ON c.id=a.class_id AND c.tenant_id=a.tenant_id AND c.is_deleted=0
                          LEFT JOIN t_user u ON u.id=a.user_id AND u.tenant_id=a.tenant_id AND u.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND (c.id IS NULL OR u.id IS NULL)""",
                      "班级责任关系统一写 assignment，不只写显示名"),
    RelationshipCheck("AFFAIRS_CLUB_MEMBER", "student_affairs", "P0", "社团成员必须回链社团和学生",
                      """SELECT COUNT(*) FROM t_affairs_club_member m
                          LEFT JOIN t_affairs_club c ON c.id=m.club_id AND c.tenant_id=m.tenant_id AND c.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=m.student_id AND s.tenant_id=m.tenant_id AND s.is_deleted=0
                         WHERE m.tenant_id=:tenant_id AND m.is_deleted=0 AND (c.id IS NULL OR s.id IS NULL)""",
                      "社团成员只引用学生主档"),
    RelationshipCheck("AFFAIRS_CLUB_COUNT", "student_affairs", "P1", "社团成员数快照必须等于有效成员数",
                      """SELECT COUNT(*) FROM (
                          SELECT c.id FROM t_affairs_club c
                          LEFT JOIN t_affairs_club_member m ON m.club_id=c.id AND m.tenant_id=c.tenant_id
                           AND m.is_deleted=0 AND m.status='ACTIVE'
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
                         GROUP BY c.id,c.member_count HAVING COALESCE(c.member_count,0)<>COUNT(m.id)
                      ) broken""",
                      "成员增退与 member_count 必须同事务更新"),

    # 实习、毕业、就业
    RelationshipCheck("INTERN_STUDENT_PROFILE", "internship", "P0", "实习记录必须属于学生主档",
                      _orphan("t_internship_record", "student_id", "t_student_profile"), "按学生资格形成实习记录"),
    RelationshipCheck("INTERN_REPORT_PARENT", "internship", "P0", "实习周报必须属于实习记录",
                      _orphan("t_weekly_report", "internship_id", "t_internship_record"), "按实习记录生成周报"),
    RelationshipCheck("INTERN_CHECKIN_PARENT", "internship", "P0", "实习打卡必须属于实习记录",
                      _orphan("t_internship_checkin", "internship_id", "t_internship_record"), "按实习记录生成打卡"),
    RelationshipCheck("INTERN_EXCEPTION_PARENT", "internship", "P0", "实习考勤异常必须属于实习记录",
                      _orphan("t_attendance_exception", "internship_id", "t_internship_record"), "从打卡异常生成异常单"),
    RelationshipCheck("INTERN_RISK_PARENT", "internship", "P0", "实习风险必须属于实习记录",
                      _orphan("t_risk_record", "internship_id", "t_internship_record"), "从过程事实生成风险"),
    RelationshipCheck("INTERN_RECORD_SCOPE", "internship", "P0", "实习记录必须回链批次、企业和岗位",
                      """SELECT COUNT(*) FROM t_internship_record r
                          LEFT JOIN t_internship_batch b ON b.id=r.batch_id AND b.tenant_id=r.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_emp_company c ON c.id=r.enterprise_id AND c.tenant_id=r.tenant_id AND c.is_deleted=0
                          LEFT JOIN t_internship_position p ON p.id=r.position_id AND p.tenant_id=r.tenant_id AND p.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0
                           AND (b.id IS NULL OR (r.enterprise_id IS NOT NULL AND c.id IS NULL)
                                OR (r.position_id IS NOT NULL AND p.id IS NULL))""",
                      "实习安置必须复用批次、企业和岗位主键"),
    RelationshipCheck("INTERN_POSITION_SCOPE", "internship", "P0", "实习岗位必须回链批次和企业",
                      """SELECT COUNT(*) FROM t_internship_position p
                          LEFT JOIN t_internship_batch b ON b.id=p.batch_id AND b.tenant_id=p.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_emp_company c ON c.id=p.company_id AND c.tenant_id=p.tenant_id AND c.is_deleted=0
                         WHERE p.tenant_id=:tenant_id AND p.is_deleted=0 AND (b.id IS NULL OR c.id IS NULL)""",
                      "岗位必须挂到学校实习批次和统一企业库"),
    RelationshipCheck("INTERN_APPLICATION_SCOPE", "internship", "P0", "实习申请必须回链记录、学生、批次和岗位",
                      """SELECT COUNT(*) FROM t_internship_application a
                          LEFT JOIN t_internship_record r ON r.id=COALESCE(a.record_id,a.campaign_record_id)
                           AND r.tenant_id=a.tenant_id AND r.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=a.student_id AND s.tenant_id=a.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_internship_batch b ON b.id=a.batch_id AND b.tenant_id=a.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_internship_position p ON p.id=a.position_id AND p.tenant_id=a.tenant_id AND p.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
                           AND (r.id IS NULL OR s.id IS NULL OR b.id IS NULL OR (a.position_id IS NOT NULL AND p.id IS NULL))""",
                      "申请必须从该生批次记录与岗位选择器生成"),
    RelationshipCheck("INTERN_MATCH_SCOPE", "internship", "P0", "实习匹配必须回链记录、学生、岗位和企业",
                      """SELECT COUNT(*) FROM t_internship_match m
                          LEFT JOIN t_internship_record r ON r.id=m.record_id AND r.tenant_id=m.tenant_id AND r.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=m.student_id AND s.tenant_id=m.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_internship_position p ON p.id=m.position_id AND p.tenant_id=m.tenant_id AND p.is_deleted=0
                          LEFT JOIN t_emp_company c ON c.id=m.company_id AND c.tenant_id=m.tenant_id AND c.is_deleted=0
                         WHERE m.tenant_id=:tenant_id AND m.is_deleted=0
                           AND (r.id IS NULL OR s.id IS NULL OR p.id IS NULL OR c.id IS NULL)""",
                      "匹配确认不得仅保存名称快照"),
    RelationshipCheck("INTERN_AGREEMENT_SCOPE", "internship", "P0", "实习协议必须与实习记录、学生和批次一致",
                      """SELECT COUNT(*) FROM t_internship_agreement a
                          LEFT JOIN t_internship_record r ON r.id=a.internship_id AND r.tenant_id=a.tenant_id AND r.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
                           AND (r.id IS NULL OR r.student_id<>a.student_id OR r.batch_id<>a.batch_id)""",
                      "协议从实习安置事实冻结学生、批次与岗位快照"),
    RelationshipCheck("INTERN_FINAL_SCORE_SCOPE", "internship", "P0", "实习总评必须与实习记录、学生和批次一致",
                      """SELECT COUNT(*) FROM t_internship_final_score f
                          LEFT JOIN t_internship_record r ON r.id=f.internship_id AND r.tenant_id=f.tenant_id AND r.is_deleted=0
                         WHERE f.tenant_id=:tenant_id AND f.is_deleted=0
                           AND (r.id IS NULL OR r.student_id<>f.student_id OR r.batch_id<>f.batch_id)""",
                      "总评必须从同一实习记录的过程分项汇总"),
    RelationshipCheck("INTERN_ARCHIVE_SCOPE", "internship", "P0", "实习归档必须与实习记录、学生和批次一致",
                      """SELECT COUNT(*) FROM t_internship_archive a
                          LEFT JOIN t_internship_record r ON r.id=a.internship_id AND r.tenant_id=a.tenant_id AND r.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
                           AND (r.id IS NULL OR r.student_id<>a.student_id OR r.batch_id<>a.batch_id)""",
                      "归档包只能由该生实习记录生成"),
    RelationshipCheck("INTERN_PARTICIPANT_SCOPE", "internship", "P0", "实习批次参与人必须回链批次、学生和实习记录",
                      """SELECT COUNT(*) FROM t_internship_batch_participant p
                          LEFT JOIN t_internship_batch b ON b.id=p.batch_id AND b.tenant_id=p.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=p.student_id AND s.tenant_id=p.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_internship_record r ON r.id=p.internship_id AND r.tenant_id=p.tenant_id AND r.is_deleted=0
                         WHERE p.tenant_id=:tenant_id AND p.is_deleted=0
                           AND (b.id IS NULL OR s.id IS NULL OR (p.internship_id IS NOT NULL AND r.id IS NULL))""",
                      "参与人名单是批次范围与个人实习记录之间的桥梁"),
    RelationshipCheck("INTERN_COMPLIANCE_SCOPE", "internship", "P0", "实习合规凭证必须回链同一学生的实习记录",
                      """SELECT COUNT(*) FROM (
                          SELECT internship_id,student_id,tenant_id FROM t_internship_insurance WHERE tenant_id=:tenant_id AND is_deleted=0
                          UNION ALL SELECT internship_id,student_id,tenant_id FROM t_internship_consent WHERE tenant_id=:tenant_id AND is_deleted=0
                          UNION ALL SELECT internship_id,student_id,tenant_id FROM t_internship_safety_completion WHERE tenant_id=:tenant_id AND is_deleted=0
                      ) x LEFT JOIN t_internship_record r ON r.id=x.internship_id AND r.student_id=x.student_id
                       AND r.tenant_id=x.tenant_id AND r.is_deleted=0 WHERE r.id IS NULL""",
                      "保险、知情同意和安全培训统一引用个人实习记录"),
    RelationshipCheck("GRAD_STUDENT_PROFILE", "graduation", "P0", "毕设学生必须来自学生主档",
                      _orphan("t_gd_student", "student_id", "t_student_profile"), "从毕业资格名单生成毕设学生"),
    RelationshipCheck("GRAD_STUDENT_BATCH", "graduation", "P0", "毕设学生必须属于毕设批次",
                      _orphan("t_gd_student", "batch_id", "t_gd_batch"), "按批次形成学生名单"),
    RelationshipCheck("GRAD_STUDENT_TOPIC", "graduation", "P0", "已选课题必须指向真实课题",
                      _orphan("t_gd_student", "topic_id", "t_gd_topic", child_filter="c.topic_id IS NOT NULL", required=False),
                      "从选题结果写入 topic_id"),
    RelationshipCheck("GRAD_STUDENT_MENTOR", "graduation", "P0", "已分配导师必须指向导师库",
                      _orphan("t_gd_student", "mentor_id", "t_gd_mentor", child_filter="c.mentor_id IS NOT NULL", required=False),
                      "从导师分配单写入 mentor_id"),
    RelationshipCheck("GRAD_ASSIGNMENT_PARENT", "graduation", "P0", "导师分配必须同时回链学生和导师",
                      """SELECT COUNT(*) FROM t_gd_mentor_assignment a
                          LEFT JOIN t_gd_student s ON s.id=a.gd_student_id AND s.tenant_id=a.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_gd_mentor m ON m.id=a.mentor_id AND m.tenant_id=a.tenant_id AND m.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND (s.id IS NULL OR m.id IS NULL)""",
                      "从正式导师分配流程生成关系"),
    RelationshipCheck("GRAD_TOPIC_CHOICE", "graduation", "P0", "毕设志愿必须回链轮次、学生和课题",
                      """SELECT COUNT(*) FROM t_gd_topic_choice c
                          LEFT JOIN t_gd_topic_round r ON r.id=c.round_id AND r.tenant_id=c.tenant_id AND r.is_deleted=0
                          LEFT JOIN t_gd_student s ON s.id=c.gd_student_id AND s.tenant_id=c.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_gd_topic t ON t.id=c.topic_id AND t.tenant_id=c.tenant_id AND t.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND (r.id IS NULL OR s.id IS NULL OR t.id IS NULL)""",
                      "选题结果必须由轮次内志愿生成"),
    RelationshipCheck("GRAD_TASK_BOOK", "graduation", "P0", "任务书必须回链毕设学生和导师",
                      """SELECT COUNT(*) FROM t_gd_task_book b
                          LEFT JOIN t_gd_student s ON s.id=b.gd_student_id AND s.tenant_id=b.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_gd_mentor m ON m.id=b.mentor_id AND m.tenant_id=b.tenant_id AND m.is_deleted=0
                         WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND (s.id IS NULL OR m.id IS NULL)""",
                      "任务书由正式导师分配关系发起"),
    RelationshipCheck("GRAD_GUIDANCE", "graduation", "P0", "指导记录必须回链毕设学生和导师",
                      """SELECT COUNT(*) FROM t_gd_guidance g
                          LEFT JOIN t_gd_student s ON s.id=g.gd_student_id AND s.tenant_id=g.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_gd_mentor m ON m.id=g.mentor_id AND m.tenant_id=g.tenant_id AND m.is_deleted=0
                         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0 AND (s.id IS NULL OR m.id IS NULL)""",
                      "指导记录必须沿该生导师关系追加"),
    RelationshipCheck("GRAD_PROCESS_STUDENT", "graduation", "P0", "开题、中期、终稿、成绩和归档必须属于毕设学生",
                      """SELECT COUNT(*) FROM (
                          SELECT gd_student_id,tenant_id FROM t_gd_proposal WHERE tenant_id=:tenant_id AND is_deleted=0
                          UNION ALL SELECT gd_student_id,tenant_id FROM t_gd_midterm WHERE tenant_id=:tenant_id AND is_deleted=0
                          UNION ALL SELECT gd_student_id,tenant_id FROM t_gd_final WHERE tenant_id=:tenant_id AND is_deleted=0
                          UNION ALL SELECT gd_student_id,tenant_id FROM t_gd_grade WHERE tenant_id=:tenant_id AND is_deleted=0
                          UNION ALL SELECT gd_student_id,tenant_id FROM t_gd_archive_record WHERE tenant_id=:tenant_id AND is_deleted=0
                      ) x LEFT JOIN t_gd_student s ON s.id=x.gd_student_id AND s.tenant_id=x.tenant_id AND s.is_deleted=0
                     WHERE s.id IS NULL""",
                      "毕设过程事实统一引用 gd_student_id"),
    RelationshipCheck("GRAD_DEFENSE_GROUP", "graduation", "P0", "答辩组必须属于批次并引用导师库",
                      """SELECT COUNT(*) FROM t_gd_defense_group g
                          LEFT JOIN t_gd_batch b ON b.id=g.batch_id AND b.tenant_id=g.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_gd_mentor c ON c.id=g.chair_mentor_id AND c.tenant_id=g.tenant_id AND c.is_deleted=0
                          LEFT JOIN t_gd_mentor s ON s.id=g.secretary_mentor_id AND s.tenant_id=g.tenant_id AND s.is_deleted=0
                         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0
                           AND (b.id IS NULL OR (g.chair_mentor_id IS NOT NULL AND c.id IS NULL)
                                OR (g.secretary_mentor_id IS NOT NULL AND s.id IS NULL))""",
                      "答辩分组必须从批次与导师资格库生成"),
    RelationshipCheck("GRAD_DEFENSE_SCORE", "graduation", "P0", "答辩评分必须回链学生和答辩组",
                      """SELECT COUNT(*) FROM t_gd_defense_score d
                          LEFT JOIN t_gd_student s ON s.id=d.gd_student_id AND s.tenant_id=d.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_gd_defense_group g ON g.id=d.defense_group_id AND g.tenant_id=d.tenant_id AND g.is_deleted=0
                         WHERE d.tenant_id=:tenant_id AND d.is_deleted=0 AND (s.id IS NULL OR g.id IS NULL)""",
                      "评分必须来自正式答辩分组"),
    RelationshipCheck("EMP_STUDENT_PROFILE", "employment", "P0", "就业学生必须来自学生主档",
                      _orphan("t_emp_student", "student_id", "t_student_profile"), "复用毕业届学生主档"),
    RelationshipCheck("EMP_MATERIAL_PARENT", "employment", "P0", "就业材料必须属于就业学生",
                      _orphan("t_emp_material", "emp_student_id", "t_emp_student"), "按就业学生生成材料"),
    RelationshipCheck("EMP_FOLLOWUP_PARENT", "employment", "P0", "就业跟进必须属于就业学生",
                      _orphan("t_emp_followup", "emp_student_id", "t_emp_student"), "按就业学生生成跟进"),
    RelationshipCheck("EMP_JOB_COMPANY", "employment", "P0", "就业岗位必须属于企业库",
                      _orphan("t_emp_job", "company_id", "t_emp_company"), "岗位统一引用企业主键"),
    RelationshipCheck("EMP_INTERNSHIP_HANDOFF", "employment", "P1", "实习转就业必须能回到该生实习事实",
                      """SELECT COUNT(*) FROM t_emp_student e
                          LEFT JOIN t_internship_record i ON i.student_id=e.student_id AND i.tenant_id=e.tenant_id AND i.is_deleted=0
                         WHERE e.tenant_id=:tenant_id AND e.is_deleted=0 AND e.from_internship=1 AND i.id IS NULL""",
                      "从实习终态投影就业去向并保留来源标识"),
    RelationshipCheck("EMP_DESTINATION_SUBMISSION", "employment", "P0", "就业去向申报必须回链就业学生和学生主档",
                      """SELECT COUNT(*) FROM t_emp_destination_submission d
                          LEFT JOIN t_emp_student e ON e.id=d.emp_student_id AND e.tenant_id=d.tenant_id AND e.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=d.student_id AND s.tenant_id=d.tenant_id AND s.is_deleted=0
                         WHERE d.tenant_id=:tenant_id AND d.is_deleted=0
                           AND (e.id IS NULL OR s.id IS NULL OR e.student_id<>d.student_id)""",
                      "学生申报必须落到本人就业档案"),
    RelationshipCheck("EMP_RECOMMENDATION", "employment", "P0", "岗位推荐必须回链就业学生、学生主档、岗位和教师",
                      """SELECT COUNT(*) FROM t_emp_recommendation r
                          LEFT JOIN t_emp_student e ON e.id=r.emp_student_id AND e.tenant_id=r.tenant_id AND e.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=r.student_profile_id AND s.tenant_id=r.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_emp_job j ON j.id=r.job_id AND j.tenant_id=r.tenant_id AND j.is_deleted=0
                          LEFT JOIN t_user u ON u.id=r.teacher_user_id AND u.tenant_id=r.tenant_id AND u.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0
                           AND (e.id IS NULL OR s.id IS NULL OR j.id IS NULL OR u.id IS NULL
                                OR e.student_id<>r.student_profile_id)""",
                      "岗位推荐从就业档案和统一岗位库生成"),

    # 教务 authoritative chain
    RelationshipCheck("AA_TASK_PARENTS", "academic_affairs", "P0", "教学任务必须回链批次、课程和行政班",
                      """SELECT COUNT(*) FROM t_aa_teaching_task t
                          LEFT JOIN t_aa_teaching_task_batch b ON b.id=t.batch_id AND b.tenant_id=t.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_course c ON c.id=t.course_id AND c.tenant_id=t.tenant_id AND c.is_deleted=0
                          LEFT JOIN t_class k ON k.id=t.class_id AND k.tenant_id=t.tenant_id AND k.is_deleted=0
                         WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND (b.id IS NULL OR c.id IS NULL OR k.id IS NULL)""",
                      "只从有效开课计划生成教学任务"),
    RelationshipCheck("AA_TASK_TEACHER", "academic_affairs", "P0", "教学任务教师必须指向有效用户",
                      """SELECT COUNT(*) FROM t_aa_teaching_task t
                          LEFT JOIN t_user u ON u.login_name=t.teacher_key AND u.tenant_id=t.tenant_id AND u.is_deleted=0
                         WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND (t.teacher_key IS NULL OR u.id IS NULL)""",
                      "从教师分配事实写入 teacher_id/teacher_key"),
    RelationshipCheck("AA_SCHEDULE_PARENTS", "academic_affairs", "P0", "课位必须回链课表批次、教学任务和教室",
                      """SELECT COUNT(*) FROM t_aa_schedule_item i
                          LEFT JOIN t_aa_schedule_batch b ON b.id=i.batch_id AND b.tenant_id=i.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_teaching_task t ON t.id=i.task_id AND t.tenant_id=i.tenant_id AND t.is_deleted=0
                          LEFT JOIN t_aa_classroom r ON r.id=i.classroom_id AND r.tenant_id=i.tenant_id AND r.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0
                           AND (b.id IS NULL OR t.id IS NULL OR (i.classroom_id IS NOT NULL AND r.id IS NULL))""",
                      "课位只能从 READY 教学任务写入"),
    RelationshipCheck("AA_SCHEDULE_SNAPSHOT", "academic_affairs", "P0", "课位快照必须与教学任务一致",
                      """SELECT COUNT(*) FROM t_aa_schedule_item i
                          JOIN t_aa_teaching_task t ON t.id=i.task_id AND t.tenant_id=i.tenant_id AND t.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0
                           AND (i.course_id<>t.course_id OR i.course_name<>t.course_name
                                OR COALESCE(i.class_id,0)<>COALESCE(t.class_id,0)
                                OR COALESCE(i.teacher_key,'')<>COALESCE(t.teacher_key,''))""",
                      "从教学任务重建课位快照"),
    RelationshipCheck("AA_PUBLISHED_SCHEDULE_COMPLETE", "academic_affairs", "P0", "已发布课表必须完成全部应排节次",
                      """WITH RECURSIVE weeks(week_no) AS (
                              SELECT 1 UNION ALL SELECT week_no+1 FROM weeks WHERE week_no<60
                          )
                          SELECT COUNT(*) FROM (
                              SELECT h.active_batch_id,t.id task_id,w.week_no,t.weekly_hours,COUNT(i.id) actual
                                FROM t_aa_schedule_scope_head h
                                JOIN t_aa_schedule_batch b ON b.id=h.active_batch_id AND b.tenant_id=h.tenant_id
                                 AND b.term_id=h.term_id AND b.status='PUBLISHED' AND b.is_deleted=0
                                JOIN t_aa_term term ON term.id=b.term_id AND term.tenant_id=b.tenant_id AND term.is_deleted=0
                                JOIN t_aa_teaching_task_batch tb ON tb.term_id=b.term_id
                                 AND tb.tenant_id=b.tenant_id AND tb.is_deleted=0
                                JOIN t_aa_teaching_task t ON t.batch_id=tb.id AND t.status='READY' AND t.is_deleted=0
                                JOIN weeks w ON w.week_no BETWEEN t.start_week AND LEAST(t.end_week,term.teaching_weeks)
                                LEFT JOIN t_aa_schedule_item i ON i.batch_id=b.id AND i.task_id=t.id
                                 AND i.tenant_id=b.tenant_id AND i.status='EFFECTIVE' AND i.is_deleted=0
                                 AND w.week_no BETWEEN i.start_week AND i.end_week
                                 AND (i.week_parity='ALL' OR (i.week_parity='ODD' AND MOD(w.week_no,2)=1)
                                      OR (i.week_parity='EVEN' AND MOD(w.week_no,2)=0))
                               WHERE h.tenant_id=:tenant_id AND h.is_deleted=0
                               GROUP BY h.active_batch_id,t.id,w.week_no,t.weekly_hours
                              HAVING COUNT(i.id)<>t.weekly_hours
                          ) broken""",
                      "按每个教学周逐任务验证 weekly_hours；部分调课必须生成原课位残余周次，不能整段丢课"),
    RelationshipCheck("AA_SCOPE_HEAD_ACTIVE", "academic_affairs", "P0", "正式课表范围头必须指向同学期已发布批次",
                      """SELECT COUNT(*) FROM t_aa_schedule_scope_head h
                          LEFT JOIN t_aa_schedule_batch b ON b.id=h.active_batch_id AND b.tenant_id=h.tenant_id
                           AND b.term_id=h.term_id AND b.status='PUBLISHED' AND b.is_deleted=0
                         WHERE h.tenant_id=:tenant_id AND h.is_deleted=0 AND b.id IS NULL""",
                      "通过 promote_to_active 原子切换正式版本头"),
    RelationshipCheck("AA_TEACHING_CLASS_TASK", "academic_affairs", "P0", "教学班必须来自教学任务",
                      _orphan("t_aa_teaching_class", "teaching_task_id", "t_aa_teaching_task"), "从教学任务形成教学班"),
    RelationshipCheck("AA_ROSTER_HEAD", "academic_affairs", "P0", "教学班必须指向锁定名单版本",
                      """SELECT COUNT(*) FROM t_aa_teaching_class c
                          LEFT JOIN t_aa_teaching_class_roster_version v
                            ON v.id=c.current_roster_version_id AND v.teaching_class_id=c.id
                           AND v.tenant_id=c.tenant_id AND v.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND (c.current_roster_version_id IS NULL OR v.id IS NULL)""",
                      "先锁 roster version，再更新 teaching class head"),
    RelationshipCheck("AA_ROSTER_MEMBER", "academic_affairs", "P0", "名单成员必须同时属于教学班、版本和学生",
                      """SELECT COUNT(*) FROM t_aa_teaching_class_member m
                          LEFT JOIN t_aa_teaching_class c ON c.id=m.teaching_class_id AND c.tenant_id=m.tenant_id AND c.is_deleted=0
                          LEFT JOIN t_aa_teaching_class_roster_version v ON v.id=m.roster_version_id AND v.teaching_class_id=m.teaching_class_id AND v.tenant_id=m.tenant_id AND v.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=m.student_id AND s.tenant_id=m.tenant_id AND s.is_deleted=0
                         WHERE m.tenant_id=:tenant_id AND m.is_deleted=0 AND (c.id IS NULL OR v.id IS NULL OR s.id IS NULL)""",
                      "名单成员只由 roster projection 生成"),
    RelationshipCheck("AA_ROSTER_COUNT", "academic_affairs", "P0", "名单版本人数必须等于有效成员数",
                      """SELECT COUNT(*) FROM (
                          SELECT v.id FROM t_aa_teaching_class_roster_version v
                          LEFT JOIN t_aa_teaching_class_member m ON m.roster_version_id=v.id AND m.tenant_id=v.tenant_id AND m.is_deleted=0 AND m.status='ACTIVE'
                         WHERE v.tenant_id=:tenant_id AND v.is_deleted=0
                         GROUP BY v.id,v.member_count HAVING v.member_count<>COUNT(m.id)
                      ) broken""",
                      "以成员主键集合重算人数和 roster_hash"),
    RelationshipCheck("AA_GRADE_TASK", "academic_affairs", "P0", "成绩任务必须来自教学任务",
                      _orphan("t_aa_grade_task", "teaching_task_id", "t_aa_teaching_task"), "从正式教学班/任务选择器生成成绩任务"),
    RelationshipCheck("AA_GRADE_RECORD", "academic_affairs", "P0", "成绩明细必须属于成绩任务和学生",
                      """SELECT COUNT(*) FROM t_aa_grade_record r
                          LEFT JOIN t_aa_grade_task g ON g.id=r.task_id AND g.tenant_id=r.tenant_id AND g.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=r.student_id AND s.tenant_id=r.tenant_id AND s.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND (g.id IS NULL OR s.id IS NULL)""",
                      "只从锁定名单生成成绩明细"),
    RelationshipCheck("AA_EXAM_COURSE", "academic_affairs", "P0", "考试课程必须回链考试批次和教学任务",
                      """SELECT COUNT(*) FROM t_aa_exam_course e
                          LEFT JOIN t_aa_exam_batch b ON b.id=e.batch_id AND b.tenant_id=e.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_teaching_task t ON t.id=e.teaching_task_id AND t.tenant_id=e.tenant_id AND t.is_deleted=0
                         WHERE e.tenant_id=:tenant_id AND e.is_deleted=0 AND (b.id IS NULL OR t.id IS NULL)""",
                      "考试课程从正式教学任务生成"),
    RelationshipCheck("AA_EXAM_SEAT", "academic_affairs", "P0", "座位必须同时回链考场、考试课程和学生",
                      """SELECT COUNT(*) FROM t_aa_exam_room_student s
                          LEFT JOIN t_aa_exam_room r ON r.id=s.exam_room_id AND r.tenant_id=s.tenant_id AND r.is_deleted=0
                          LEFT JOIN t_aa_exam_course e ON e.id=s.exam_course_id AND e.tenant_id=s.tenant_id AND e.is_deleted=0
                          LEFT JOIN t_student_profile p ON p.id=s.student_id AND p.tenant_id=s.tenant_id AND p.is_deleted=0
                         WHERE s.tenant_id=:tenant_id AND s.is_deleted=0
                           AND (r.id IS NULL OR e.id IS NULL OR p.id IS NULL OR r.exam_course_id<>s.exam_course_id)""",
                      "从锁定考试名单分配座位"),
    RelationshipCheck("AA_EXAM_GRADE_CANDIDATE", "academic_affairs", "P0", "已结束考试的应考名单必须进入同一教学任务成绩册",
                      """SELECT COUNT(*) FROM t_aa_exam_room_student s
                          JOIN t_aa_exam_course ec ON ec.id=s.exam_course_id AND ec.tenant_id=s.tenant_id AND ec.is_deleted=0
                          JOIN t_aa_exam_batch eb ON eb.id=ec.batch_id AND eb.tenant_id=ec.tenant_id AND eb.is_deleted=0
                          LEFT JOIN t_aa_grade_task gt ON gt.teaching_task_id=ec.teaching_task_id
                           AND gt.tenant_id=ec.tenant_id AND gt.is_deleted=0 AND gt.status='PUBLISHED'
                          LEFT JOIN t_aa_grade_record gr ON gr.task_id=gt.id AND gr.student_id=s.student_id
                           AND gr.tenant_id=s.tenant_id AND gr.is_deleted=0
                         WHERE s.tenant_id=:tenant_id AND s.is_deleted=0 AND eb.status='FINISHED'
                           AND (gt.id IS NULL OR gr.id IS NULL)""",
                      "考试候选人、成绩任务和成绩明细必须复用 teaching_task_id + student_id"),
    RelationshipCheck("AA_GRAD_AUDIT_RESULT", "academic_affairs", "P0", "毕业审核结果必须回链批次和学生主档",
                      """SELECT COUNT(*) FROM t_aa_graduation_audit_result r
                          LEFT JOIN t_aa_graduation_audit_batch b ON b.id=r.batch_id
                           AND b.tenant_id=r.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=r.student_id
                           AND s.tenant_id=r.tenant_id AND s.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND (b.id IS NULL OR s.id IS NULL)""",
                      "毕业审核名单只能从批次范围内学生主档生成"),
    RelationshipCheck("AA_GRAD_ACADEMIC_STUDENT", "academic_affairs", "P0", "毕业审核学生必须具有同一主档来源的学业台账",
                      """SELECT COUNT(*) FROM t_aa_graduation_audit_result r
                          LEFT JOIN t_acad_student a ON a.student_id=r.student_id
                           AND a.tenant_id=r.tenant_id AND a.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND a.id IS NULL""",
                      "毕业规则的成绩、学分和预警取数必须沿 StudentProfile→AcademicStudent 关联"),
    RelationshipCheck("AA_GRAD_EVALUATION_RUN", "academic_affairs", "P0", "毕业预审结果必须回链一致的不可变评估 Run",
                      """SELECT COUNT(*) FROM t_aa_graduation_evaluation_run run
                          LEFT JOIN t_aa_graduation_audit_result r ON r.id=run.result_id
                           AND r.batch_id=run.batch_id AND r.student_id=run.student_id
                           AND r.tenant_id=run.tenant_id AND r.is_deleted=0
                         WHERE run.tenant_id=:tenant_id AND r.id IS NULL""",
                      "每次预审追加 Run，并冻结 batch/result/student 三元身份与输入快照"),
    RelationshipCheck("AA_GRAD_DECISION_RUN", "academic_affairs", "P0", "毕业终审决定必须引用同一结果的正式评估 Run",
                      """SELECT COUNT(*) FROM t_aa_graduation_decision_fact d
                          LEFT JOIN t_aa_graduation_audit_result r ON r.id=d.result_id
                           AND r.batch_id=d.batch_id AND r.student_id=d.student_id
                           AND r.tenant_id=d.tenant_id AND r.is_deleted=0
                          LEFT JOIN t_aa_graduation_evaluation_run run ON run.id=d.evaluation_run_id
                           AND run.result_id=d.result_id AND run.tenant_id=d.tenant_id
                         WHERE d.tenant_id=:tenant_id AND (r.id IS NULL OR run.id IS NULL)""",
                      "终审只引用当前正式 Run，不允许按可变投影直接写毕业结论"),
    RelationshipCheck("AA_GRAD_DECISION_WRITEBACK", "academic_affairs", "P0", "毕业决定必须回写审核结果并同步学生终态",
                      """SELECT COUNT(*) FROM t_aa_graduation_decision_fact d
                          JOIN t_aa_graduation_audit_result r ON r.id=d.result_id
                           AND r.tenant_id=d.tenant_id AND r.is_deleted=0
                          JOIN t_student_profile s ON s.id=d.student_id
                           AND s.tenant_id=d.tenant_id AND s.is_deleted=0
                         WHERE d.tenant_id=:tenant_id
                           AND (r.conclusion<>d.conclusion OR r.status<>d.conclusion
                                OR (d.conclusion='GRADUATED' AND s.student_status<>'GRADUATED')
                                OR (d.conclusion='COMPLETED' AND s.student_status<>'COMPLETED'))""",
                      "终审决定、审核结果和学生主档终态必须在同一事务提交；DELAYED 不伪改主档"),
    RelationshipCheck("AA_EXAM_INCIDENT_PARENTS", "academic_affairs", "P0", "考场异常必须回链考试课程、学生和有效考场",
                      """SELECT COUNT(*) FROM t_aa_exam_incident i
                          LEFT JOIN t_aa_exam_course e ON e.id=i.exam_course_id AND e.tenant_id=i.tenant_id AND e.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=i.student_id AND s.tenant_id=i.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_aa_exam_room r ON r.id=i.exam_room_id AND r.tenant_id=i.tenant_id AND r.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0
                           AND (e.id IS NULL OR s.id IS NULL
                                OR (i.exam_room_id IS NOT NULL AND (r.id IS NULL OR r.exam_course_id<>i.exam_course_id)))""",
                      "考场重排必须先解除旧 room_id，再按 exam_course 回链新考场"),
    RelationshipCheck("AA_EXAM_INCIDENT_DISCIPLINE", "academic_affairs", "P0", "考试违纪必须回链同一学生的学工处分案件",
                      """SELECT COUNT(*) FROM t_aa_exam_incident i
                          LEFT JOIN t_affairs_discipline_case d
                            ON d.id=CAST(SUBSTRING_INDEX(i.discipline_case_ref,':',-1) AS UNSIGNED)
                           AND d.tenant_id=i.tenant_id AND d.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0 AND i.status='ACTIVE'
                           AND i.incident_type<>'ABSENT'
                           AND (i.incident_type<>'DISCIPLINE_VIOLATION'
                                OR i.discipline_case_ref NOT LIKE 'DISCIPLINE_CASE:%'
                                OR d.id IS NULL OR d.student_id<>i.student_id)""",
                      "违纪记录通过 DISCIPLINE_CASE:<id> 连到同一学生的处分闭环"),
    RelationshipCheck("AA_MAKEUP_BATCH_TERMINAL", "academic_affairs", "P0", "补考批次终态必须与补考成绩明细一致",
                      """SELECT COUNT(*) FROM t_aa_makeup_batch b
                          LEFT JOIN (
                              SELECT batch_id,COUNT(*) total,
                                     SUM(CASE WHEN status='FINISHED' AND final_score IS NOT NULL THEN 1 ELSE 0 END) finished
                                FROM t_acad_makeup
                               WHERE tenant_id=:tenant_id AND is_deleted=0 AND batch_id IS NOT NULL
                               GROUP BY batch_id
                          ) r ON r.batch_id=b.id
                         WHERE b.tenant_id=:tenant_id AND b.is_deleted=0
                           AND ((b.status='FINISHED' AND (COALESCE(r.total,0)=0 OR r.finished<>r.total))
                                OR (b.status<>'FINISHED' AND COALESCE(r.total,0)>0 AND r.finished=r.total))""",
                      "成绩全部发布后原子推进补考批次 FINISHED，禁止明细终态与批次脱节"),
    RelationshipCheck("AA_ATTENDANCE_TASK", "academic_affairs", "P1", "课堂考勤必须直接回链教学任务",
                      """SELECT COUNT(*) FROM t_aa_attendance_session a
                          LEFT JOIN t_aa_teaching_task t ON t.id=a.teaching_task_id AND t.tenant_id=a.tenant_id AND t.is_deleted=0
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND (a.teaching_task_id IS NULL OR t.id IS NULL)""",
                      "考勤场次写入 teaching_task_id、occurrence_identity 和来源证据"),
    RelationshipCheck("AA_ATTENDANCE_SOURCE_TYPE", "academic_affairs", "P0", "正式课堂考勤必须使用统一 FORMAL_TEACHING 来源语义",
                      """SELECT COUNT(*) FROM t_aa_attendance_session a
                         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
                           AND ((a.teaching_task_id IS NOT NULL AND COALESCE(a.source_type,'')<>'FORMAL_TEACHING')
                                OR (a.source_type='FORMAL_TEACHING'
                                    AND (a.teaching_task_id IS NULL OR a.occurrence_identity IS NULL
                                         OR COALESCE(a.source_evidence,'')='')))""",
                      "正式课堂统一写 FORMAL_TEACHING；ScopeHead/课位证据冻结在 occurrence_identity/source_evidence"),
    RelationshipCheck("AA_SCHEDULE_PUBLISH_LEDGER", "academic_affairs", "P1", "已发布课表必须有发布流水",
                      """SELECT COUNT(*) FROM t_aa_schedule_batch b
                          LEFT JOIN t_aa_schedule_publish p
                            ON p.batch_id=b.id AND p.tenant_id=b.tenant_id AND p.is_deleted=0
                         WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status='PUBLISHED' AND p.id IS NULL""",
                      "发布必须经 service 写状态、范围头、发布流水与通知，不允许 seed 直接改终态"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_SOURCE", "academic_affairs", "P0", "调停课单必须回链正式课位、批次和教学任务",
                      """SELECT COUNT(*) FROM t_aa_schedule_change c
                          LEFT JOIN t_aa_schedule_batch b ON b.id=c.batch_id AND b.tenant_id=c.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_schedule_item i ON i.id=c.origin_item_id AND i.batch_id=c.batch_id
                           AND i.tenant_id=c.tenant_id AND i.is_deleted=0
                          LEFT JOIN t_aa_teaching_task t ON t.id=c.task_id AND t.tenant_id=c.tenant_id AND t.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND (b.id IS NULL OR i.id IS NULL OR t.id IS NULL)""",
                      "教师只能从正式课表项发起调停课"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_ACTIVE_SCOPE", "academic_affairs", "P0", "在途调停课必须指向当前 ScopeHead 正式课表",
                      """SELECT COUNT(*) FROM t_aa_schedule_change c
                          JOIN t_aa_schedule_batch b ON b.id=c.batch_id AND b.tenant_id=c.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_schedule_scope_head h
                            ON h.tenant_id=c.tenant_id AND h.term_id=c.term_id AND h.is_deleted=0
                           AND h.scope_type=CASE WHEN b.college_id IS NULL THEN 'SCHOOL' ELSE 'COLLEGE' END
                           AND h.scope_id=COALESCE(b.college_id,0)
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
                           AND c.status IN ('SUBMITTED','COLLEGE_REVIEW','ACADEMIC_REVIEW')
                           AND (b.status<>'PUBLISHED' OR h.id IS NULL OR h.active_batch_id<>c.batch_id)""",
                      "在途申请仅可改写当前 ScopeHead；换版后的旧申请必须无歧义重绑或人工取消"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_WORKFLOW", "academic_affairs", "P0", "在途调停课必须回链状态一致的审批实例",
                      """SELECT COUNT(*) FROM t_aa_schedule_change c
                          LEFT JOIN t_workflow_instance w
                            ON w.id=c.workflow_instance_id AND w.tenant_id=c.tenant_id AND w.is_deleted=0
                           AND w.source_module='academic-affairs' AND w.source_biz_type='AA_SCHEDULE_CHANGE'
                           AND w.source_biz_id=c.id
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
                           AND c.status IN ('SUBMITTED','COLLEGE_REVIEW','ACADEMIC_REVIEW')
                           AND (w.id IS NULL OR w.status<>'RUNNING' OR w.current_node<>c.current_node
                                OR (c.status='SUBMITTED' AND c.current_node<>'COLLEGE_REVIEW')
                                OR (c.status IN ('COLLEGE_REVIEW','ACADEMIC_REVIEW')
                                    AND c.current_node<>'ACADEMIC_REVIEW'))""",
                      "按单据状态补建审批实例并收敛 current_node，不允许只在业务表里伪造待审状态"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_TASK", "academic_affairs", "P0", "在途调停课当前节点必须有唯一真实审批任务",
                      """SELECT COUNT(*) FROM t_aa_schedule_change c
                          LEFT JOIN (
                              SELECT instance_id,node_code,COUNT(*) pending_count,
                                     MIN(assignee_id) min_assignee,MAX(assignee_id) max_assignee
                                FROM t_workflow_task
                               WHERE tenant_id=:tenant_id AND is_deleted=0 AND status='PENDING'
                               GROUP BY instance_id,node_code
                          ) t ON t.instance_id=c.workflow_instance_id AND t.node_code=c.current_node
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
                           AND c.status IN ('SUBMITTED','COLLEGE_REVIEW','ACADEMIC_REVIEW')
                           AND (COALESCE(t.pending_count,0)<>1 OR COALESCE(t.min_assignee,0)<=0
                                OR t.min_assignee<>t.max_assignee)""",
                      "当前节点必须生成一条指向真实账号的 PENDING WorkflowTask"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_TODO", "academic_affairs", "P0", "调停课审批任务必须同步进入同一受理人的统一待办",
                      """SELECT COUNT(*) FROM t_aa_schedule_change c
                          LEFT JOIN t_workflow_task t
                            ON t.instance_id=c.workflow_instance_id AND t.node_code=c.current_node
                           AND t.tenant_id=c.tenant_id AND t.status='PENDING' AND t.is_deleted=0
                          LEFT JOIN t_unified_todo d
                            ON d.tenant_id=c.tenant_id AND d.source_module='academic-affairs'
                           AND d.source_biz_type='AA_SCHEDULE_CHANGE' AND d.source_biz_id=c.id
                           AND d.todo_type='AA_SCHEDULE_CHANGE_APPROVAL' AND d.status='PENDING'
                           AND d.assignee_id=t.assignee_id AND d.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
                           AND c.status IN ('SUBMITTED','COLLEGE_REVIEW','ACADEMIC_REVIEW')
                           AND d.id IS NULL""",
                      "WorkflowTask 与 UnifiedTodo 必须在同一事务写入同一 assignee_id"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_APPLIED", "academic_affairs", "P0", "已生效调停课必须形成一致的新旧课位",
                      """SELECT COUNT(*) FROM t_aa_schedule_change c
                          LEFT JOIN t_aa_schedule_item o ON o.id=c.origin_item_id AND o.tenant_id=c.tenant_id AND o.is_deleted=0
                          LEFT JOIN t_aa_schedule_item n ON n.id=c.new_item_id AND n.change_id=c.id
                           AND n.tenant_id=c.tenant_id AND n.is_deleted=0
                         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0 AND c.status='APPLIED'
                           AND (o.id IS NULL
                                OR (c.change_type IN ('ADJUST','STOP') AND o.status<>'CHANGED')
                                OR (c.change_type IN ('ADJUST','MAKEUP') AND n.id IS NULL)
                                OR (c.change_type='STOP' AND c.new_item_id IS NOT NULL))""",
                      "审批终审、课位改写和 new_item 回链必须在同一事务完成"),
    RelationshipCheck("AA_SCHEDULE_CHANGE_TARGET_LINK", "academic_affairs", "P0", "调停课 change_id 只能标识单据声明的新课位",
                      """SELECT COUNT(*) FROM t_aa_schedule_item i
                          JOIN t_aa_schedule_change c ON c.id=i.change_id
                           AND c.tenant_id=i.tenant_id AND c.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0
                           AND i.status='EFFECTIVE' AND i.id<>COALESCE(c.new_item_id,0)""",
                      "部分调课残余周次保留为普通 EFFECTIVE 课位；只有目标新课位回链 change_id"),

    # 教材、评教、质量与归档：从教学任务出发形成下游事实
    RelationshipCheck("AA_TEXTBOOK_SELECTION", "academic_support", "P0", "教材选用必须回链教学任务和教材目录",
                      """SELECT COUNT(*) FROM t_aa_textbook_selection s
                          LEFT JOIN t_aa_teaching_task t ON t.id=s.task_id AND t.tenant_id=s.tenant_id AND t.is_deleted=0
                          LEFT JOIN t_aa_textbook b ON b.id=s.textbook_id AND b.tenant_id=s.tenant_id AND b.is_deleted=0
                         WHERE s.tenant_id=:tenant_id AND s.is_deleted=0 AND (t.id IS NULL OR b.id IS NULL)""",
                      "教材选用必须从有效教学任务选择器进入"),
    RelationshipCheck("AA_TEXTBOOK_REVIEW", "academic_support", "P0", "教材审核明细必须回链审核批次和选用单",
                      """SELECT COUNT(*) FROM t_aa_textbook_review_batch_item i
                          LEFT JOIN t_aa_textbook_review_batch b ON b.id=i.batch_id AND b.tenant_id=i.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_textbook_selection s ON s.id=i.selection_id AND s.tenant_id=i.tenant_id AND s.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0 AND (b.id IS NULL OR s.id IS NULL)""",
                      "审核批次只能纳入已提交的选用单"),
    RelationshipCheck("AA_TEXTBOOK_ORDER", "academic_support", "P0", "教材征订明细必须回链征订批次和教材目录",
                      """SELECT COUNT(*) FROM t_aa_textbook_order_item i
                          LEFT JOIN t_aa_textbook_order_batch b ON b.id=i.order_batch_id AND b.tenant_id=i.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_textbook t ON t.id=i.textbook_id AND t.tenant_id=i.tenant_id AND t.is_deleted=0
                         WHERE i.tenant_id=:tenant_id AND i.is_deleted=0 AND (b.id IS NULL OR t.id IS NULL)""",
                      "征订明细由审核通过的教材选用聚合生成"),
    RelationshipCheck("AA_TEXTBOOK_DISTRIBUTION", "academic_support", "P0", "教材发放明细必须回链发放批次、学生和教材",
                      """SELECT COUNT(*) FROM t_aa_textbook_distribution_record r
                          LEFT JOIN t_aa_textbook_distribution_batch b ON b.id=r.batch_id AND b.tenant_id=r.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_student_profile s ON s.id=r.student_id AND s.tenant_id=r.tenant_id AND s.is_deleted=0
                          LEFT JOIN t_aa_textbook t ON t.id=r.textbook_id AND t.tenant_id=r.tenant_id AND t.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND (b.id IS NULL OR s.id IS NULL OR t.id IS NULL)""",
                      "发放名单必须来自班级学生与已到货教材"),
    RelationshipCheck("AA_TEXTBOOK_FEE", "academic_support", "P0", "教材费用台账必须回链签收记录和同一学生",
                      """SELECT COUNT(*) FROM t_aa_textbook_fee_ledger f
                          LEFT JOIN t_aa_textbook_distribution_record r
                            ON r.id=f.distribution_record_id AND r.tenant_id=f.tenant_id AND r.is_deleted=0
                         WHERE f.tenant_id=:tenant_id AND f.is_deleted=0 AND (r.id IS NULL OR r.student_id<>f.student_id)""",
                      "签收后按 distribution_record 原子生成应收"),
    RelationshipCheck("AA_EVALUATION_TASK", "academic_support", "P0", "评教任务必须回链批次和教学任务",
                      """SELECT COUNT(*) FROM t_aa_evaluation_task e
                          LEFT JOIN t_aa_evaluation_batch b ON b.id=e.batch_id AND b.tenant_id=e.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_teaching_task t ON t.id=e.teaching_task_id AND t.tenant_id=e.tenant_id AND t.is_deleted=0
                         WHERE e.tenant_id=:tenant_id AND e.is_deleted=0 AND (b.id IS NULL OR t.id IS NULL)""",
                      "评教范围必须从已结束学期的正式教学任务生成"),
    RelationshipCheck("AA_EVALUATION_RECORD", "academic_support", "P0", "评价答卷必须属于同一批次的评教任务",
                      """SELECT COUNT(*) FROM t_aa_evaluation_record r
                          LEFT JOIN t_aa_evaluation_task t ON t.id=r.task_id AND t.batch_id=r.batch_id
                           AND t.tenant_id=r.tenant_id AND t.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND t.id IS NULL""",
                      "匿名只去除评价人身份，不得去除批次与任务来源"),
    RelationshipCheck("AA_EVALUATION_RESULT", "academic_support", "P0", "评教结果必须回链批次和教学任务",
                      """SELECT COUNT(*) FROM t_aa_evaluation_result r
                          LEFT JOIN t_aa_evaluation_batch b ON b.id=r.batch_id AND b.tenant_id=r.tenant_id AND b.is_deleted=0
                          LEFT JOIN t_aa_teaching_task t ON t.id=r.teaching_task_id AND t.tenant_id=r.tenant_id AND t.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND (b.id IS NULL OR t.id IS NULL)""",
                      "结果只能由该批次答卷聚合生成"),
    RelationshipCheck("AA_EVALUATION_COUNT", "academic_support", "P1", "评教任务提交数必须等于答卷数",
                      """SELECT COUNT(*) FROM (
                          SELECT t.id FROM t_aa_evaluation_task t
                          LEFT JOIN t_aa_evaluation_record r ON r.task_id=t.id AND r.tenant_id=t.tenant_id AND r.is_deleted=0
                         WHERE t.tenant_id=:tenant_id AND t.is_deleted=0
                         GROUP BY t.id,t.submitted_count HAVING t.submitted_count<>COUNT(r.id)
                      ) broken""",
                      "提交答卷与 submitted_count 必须同事务更新"),
    RelationshipCheck("AA_QUALITY_RECTIFICATION", "academic_support", "P0", "质量整改必须回链问题记录",
                      """SELECT COUNT(*) FROM t_aa_quality_rectification x
                          LEFT JOIN t_aa_quality_record r ON r.id=x.source_record_id AND r.tenant_id=x.tenant_id AND r.is_deleted=0
                         WHERE x.tenant_id=:tenant_id AND x.is_deleted=0
                           AND x.source_record_id IS NOT NULL AND r.id IS NULL""",
                      "质量整改必须保留 source_record_id"),
    RelationshipCheck("AA_QUALITY_REQUIRED_RECTIFICATION", "academic_support", "P1", "需整改问题必须生成整改任务",
                      """SELECT COUNT(*) FROM t_aa_quality_record r
                          LEFT JOIN t_aa_quality_rectification x ON x.source_record_id=r.id
                           AND x.tenant_id=r.tenant_id AND x.is_deleted=0
                         WHERE r.tenant_id=:tenant_id AND r.is_deleted=0 AND r.need_rectify=1 AND x.id IS NULL""",
                      "确认需整改时原子生成整改任务"),
    RelationshipCheck("AA_ARCHIVE_ITEM", "academic_support", "P0", "教务归档物料必须属于归档批次",
                      _orphan("t_aa_archive_item", "batch_id", "t_aa_archive_batch"),
                      "完整性扫描结果必须写入对应学期归档批次"),
    RelationshipCheck("AA_ARCHIVE_TERMINAL", "academic_support", "P0", "已归档批次必须零缺失且全部物料存在",
                      """SELECT COUNT(*) FROM t_aa_archive_batch b
                          LEFT JOIN t_aa_term t ON t.id=b.term_id AND t.tenant_id=b.tenant_id AND t.is_deleted=0
                          LEFT JOIN (
                              SELECT batch_id,COUNT(*) item_count,
                                     SUM(CASE
                                           WHEN JSON_VALID(remark)=0 THEN 1
                                           WHEN JSON_UNQUOTE(JSON_EXTRACT(remark,'$.r'))='PASS' AND present=1 THEN 0
                                           WHEN JSON_UNQUOTE(JSON_EXTRACT(remark,'$.r'))='NOT_APPLICABLE' AND present=0 THEN 0
                                           ELSE 1
                                         END) invalid_count
                                FROM t_aa_archive_item WHERE tenant_id=:tenant_id AND is_deleted=0 GROUP BY batch_id
                          ) i ON i.batch_id=b.id
                         WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status='ARCHIVED'
                           AND (t.id IS NULL OR t.status<>'ARCHIVED' OR b.missing_count<>0
                                OR COALESCE(i.item_count,0)<>13 OR COALESCE(i.invalid_count,0)<>0)""",
                      "归档终态必须由完整性门禁和学期封存共同提交"),
    RelationshipCheck("AA_ARCHIVE_MANIFEST", "academic_support", "P0", "已归档批次必须有完整不可变清单链",
                      """SELECT COUNT(*) FROM t_aa_archive_batch b
                          LEFT JOIN (
                              SELECT m.* FROM t_aa_archive_manifest m
                              JOIN (
                                  SELECT archive_batch_id,MAX(version_no) version_no
                                    FROM t_aa_archive_manifest WHERE tenant_id=:tenant_id GROUP BY archive_batch_id
                              ) latest ON latest.archive_batch_id=m.archive_batch_id AND latest.version_no=m.version_no
                              WHERE m.tenant_id=:tenant_id
                          ) x ON x.archive_batch_id=b.id AND x.term_id=b.term_id
                         WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status='ARCHIVED'
                           AND (x.id IS NULL OR JSON_VALID(x.domain_counts_json)=0
                                OR JSON_LENGTH(x.domain_counts_json)<>13
                                OR JSON_VALID(x.domain_hashes_json)=0 OR JSON_LENGTH(x.domain_hashes_json)<>13)""",
                      "正式归档必须经 confirm_archive 生成十三域 Manifest，后续纠错只追加版本"),

    # 消息/待办至少必须能找到接收人；source_biz 的多态闭包由各域继续扩展。
    RelationshipCheck("MESSAGE_RECEIVER", "communication", "P0", "消息接收人必须是有效用户",
                      """SELECT COUNT(*) FROM t_unified_message m
                          LEFT JOIN t_user u ON u.id=COALESCE(m.receiver_user_id,m.receiver_id) AND u.tenant_id=m.tenant_id AND u.is_deleted=0
                         WHERE m.tenant_id=:tenant_id AND m.is_deleted=0 AND u.id IS NULL""",
                      "消息必须从账号绑定解析 receiver_user_id"),
    RelationshipCheck("TODO_ASSIGNEE", "communication", "P0", "待办处理人必须是有效用户",
                      """SELECT COUNT(*) FROM t_unified_todo t
                          LEFT JOIN t_user u ON u.id=t.assignee_id AND u.tenant_id=t.tenant_id AND u.is_deleted=0
                         WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND t.assignee_id IS NOT NULL AND u.id IS NULL""",
                      "从角色/账号关系生成 assignee_id"),
    RelationshipCheck("TODO_STUDENT", "communication", "P0", "学生待办必须回链学生主档",
                      """SELECT COUNT(*) FROM t_unified_todo t
                          LEFT JOIN t_student_profile s ON s.id=t.student_id AND s.tenant_id=t.tenant_id AND s.is_deleted=0
                         WHERE t.tenant_id=:tenant_id AND t.is_deleted=0 AND t.student_id IS NOT NULL AND s.id IS NULL""",
                      "从业务来源解析 student_id"),
)


def _schema_metrics(db, tenant_id: int) -> dict:
    schema = db.execute(text("SELECT DATABASE()" )).scalar()
    tenant_tables = [row[0] for row in db.execute(text("""
        SELECT TABLE_NAME FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA=:schema AND COLUMN_NAME='tenant_id'
         ORDER BY TABLE_NAME
    """), {"schema": schema})]
    schema_fk_count = int(db.execute(text("""
        SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
         WHERE TABLE_SCHEMA=:schema AND REFERENCED_TABLE_NAME IS NOT NULL
    """), {"schema": schema}).scalar() or 0)
    populated = 0
    for table_name in tenant_tables:
        # table_name 来自 information_schema，不接受外部输入。
        count = int(db.execute(
            text(f"SELECT COUNT(*) FROM {table_name} WHERE tenant_id=:tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar() or 0)
        populated += int(count > 0)
    return {
        "schema": schema,
        "tenantTables": len(tenant_tables),
        "populatedTenantTables": populated,
        "declaredForeignKeys": schema_fk_count,
        "relationshipEnforcement": "APPLICATION_LEVEL" if schema_fk_count < populated else "DATABASE_LEVEL",
    }


def _failure_diagnostics(db, tenant_id: int) -> dict:
    """把失败计数展开成可施工证据，避免只给一串红色数字。"""
    schedules = [dict(row) for row in db.execute(text("""
        WITH RECURSIVE weeks(week_no) AS (
            SELECT 1 UNION ALL SELECT week_no+1 FROM weeks WHERE week_no<60
        ), coverage AS (
            SELECT b.id batch_id,b.batch_name,CONCAT(term.year_code,'-',term.term_no) term_code,
                   t.id task_id,w.week_no,t.weekly_hours expected,COUNT(i.id) actual
              FROM t_aa_schedule_scope_head h
              JOIN t_aa_schedule_batch b ON b.id=h.active_batch_id AND b.tenant_id=h.tenant_id
               AND b.term_id=h.term_id AND b.status='PUBLISHED' AND b.is_deleted=0
              JOIN t_aa_term term ON term.id=b.term_id AND term.tenant_id=b.tenant_id AND term.is_deleted=0
              JOIN t_aa_teaching_task_batch tb ON tb.term_id=b.term_id
               AND tb.tenant_id=b.tenant_id AND tb.is_deleted=0
              JOIN t_aa_teaching_task t ON t.batch_id=tb.id AND t.status='READY' AND t.is_deleted=0
              JOIN weeks w ON w.week_no BETWEEN t.start_week AND LEAST(t.end_week,term.teaching_weeks)
              LEFT JOIN t_aa_schedule_item i ON i.batch_id=b.id AND i.task_id=t.id
               AND i.tenant_id=b.tenant_id AND i.status='EFFECTIVE' AND i.is_deleted=0
               AND w.week_no BETWEEN i.start_week AND i.end_week
               AND (i.week_parity='ALL' OR (i.week_parity='ODD' AND MOD(w.week_no,2)=1)
                    OR (i.week_parity='EVEN' AND MOD(w.week_no,2)=0))
             WHERE h.tenant_id=:tenant_id AND h.is_deleted=0
             GROUP BY b.id,b.batch_name,term.year_code,term.term_no,t.id,w.week_no,t.weekly_hours
        )
        SELECT batch_id,batch_name,term_code,SUM(expected) expected_sessions,SUM(actual) actual_sessions,
               SUM(GREATEST(expected-actual,0)) missing_sessions
          FROM coverage GROUP BY batch_id,batch_name,term_code
        HAVING expected_sessions<>actual_sessions ORDER BY term_code
    """), {"tenant_id": tenant_id}).mappings()]

    grade_course = db.execute(text("""
        SELECT SUM(candidate_count=1) resolvable_rows,
               SUM(candidate_count>1) ambiguous_rows,
               SUM(candidate_count=0) unmatched_rows,
               COUNT(*) broken_rows
          FROM (
              SELECT g.id,COUNT(c.id) candidate_count
                FROM t_acad_grade g
                LEFT JOIN t_acad_student a ON a.id=g.acad_student_id AND a.tenant_id=g.tenant_id AND a.is_deleted=0
                LEFT JOIN t_major m ON m.major_name=a.major_name AND m.tenant_id=g.tenant_id AND m.is_deleted=0
                LEFT JOIN t_aa_course c ON c.course_name=g.course_name AND c.tenant_id=g.tenant_id AND c.is_deleted=0
                 AND (c.is_all_major=1 OR c.course_code LIKE CONCAT(m.code,'-%'))
                LEFT JOIN t_aa_course current_course ON current_course.id=g.course_id
                 AND current_course.tenant_id=g.tenant_id AND current_course.is_deleted=0
               WHERE g.tenant_id=:tenant_id AND g.is_deleted=0
                 AND (g.course_id IS NULL OR current_course.id IS NULL)
               GROUP BY g.id
          ) x
    """), {"tenant_id": tenant_id}).mappings().one()
    unmatched_names = [dict(row) for row in db.execute(text("""
        SELECT g.course_name,COUNT(*) rows_count
          FROM t_acad_grade g
          LEFT JOIN (
              SELECT DISTINCT tenant_id,course_name FROM t_aa_course WHERE tenant_id=:tenant_id AND is_deleted=0
          ) c ON c.tenant_id=g.tenant_id AND c.course_name=g.course_name
         WHERE g.tenant_id=:tenant_id AND g.is_deleted=0
           AND c.course_name IS NULL
         GROUP BY g.course_name ORDER BY rows_count DESC LIMIT 20
    """), {"tenant_id": tenant_id}).mappings()]
    provenance = [dict(row) for row in db.execute(text("""
        SELECT term,COUNT(*) rows_count
          FROM t_acad_grade
         WHERE tenant_id=:tenant_id AND is_deleted=0 AND source='PUBLISH'
           AND grade_task_id IS NULL AND source_biz_id IS NULL
         GROUP BY term ORDER BY term
    """), {"tenant_id": tenant_id}).mappings()]
    manifests = [dict(row) for row in db.execute(text("""
        SELECT m.archive_batch_id,m.version_no,
               JSON_LENGTH(m.domain_counts_json) domain_count,
               JSON_LENGTH(m.domain_hashes_json) hash_count,
               m.supersedes_id
          FROM t_aa_archive_manifest m
          JOIN (
              SELECT archive_batch_id,MAX(version_no) version_no
                FROM t_aa_archive_manifest WHERE tenant_id=:tenant_id GROUP BY archive_batch_id
          ) latest ON latest.archive_batch_id=m.archive_batch_id AND latest.version_no=m.version_no
         WHERE m.tenant_id=:tenant_id
    """), {"tenant_id": tenant_id}).mappings()]
    return {
        "brokenPublishedSchedules": schedules,
        "gradeCourseResolution": {
            "brokenRows": int(grade_course["broken_rows"] or 0),
            "resolvableRows": int(grade_course["resolvable_rows"] or 0),
            "ambiguousRows": int(grade_course["ambiguous_rows"] or 0),
            "unmatchedRows": int(grade_course["unmatched_rows"] or 0),
            "unmatchedCourseNames": unmatched_names,
        },
        "gradeProvenanceByTerm": provenance,
        "latestArchiveManifests": manifests,
    }


def audit_sandbox_relationship_closure(db, tenant_id: int) -> dict:
    """运行只读闭包检查；count 表示未闭合行数/批次数。"""
    results = []
    for spec in CHECKS:
        count = int(db.execute(text(spec.sql), {"tenant_id": tenant_id}).scalar() or 0)
        results.append({
            "code": spec.code,
            "domain": spec.domain,
            "severity": spec.severity,
            "title": spec.title,
            "count": count,
            "passed": count == 0,
            "repairHint": spec.repair_hint,
        })
    failed = [row for row in results if not row["passed"]]
    p0 = [row for row in failed if row["severity"] == "P0"]
    p1 = [row for row in failed if row["severity"] == "P1"]
    domains = {}
    for row in results:
        item = domains.setdefault(row["domain"], {"checks": 0, "failed": 0, "brokenRows": 0})
        item["checks"] += 1
        item["failed"] += int(not row["passed"])
        item["brokenRows"] += int(row["count"])
    return {
        "tenantId": str(tenant_id),
        "schema": _schema_metrics(db, tenant_id),
        "summary": {
            "checks": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "p0Failed": len(p0),
            "p1Failed": len(p1),
            "p0Passed": not p0,
            "fullClosurePassed": not failed,
        },
        "domains": domains,
        "failures": failed,
        "diagnostics": _failure_diagnostics(db, tenant_id),
        "checks": results,
    }


def require_sandbox_relationship_closure(db, tenant_id: int) -> dict:
    """重建门禁：先阻断会让核心流程走不动的 P0，P1 继续在报告中显式保留。"""
    report = audit_sandbox_relationship_closure(db, tenant_id)
    if not report["summary"]["p0Passed"]:
        failures = [
            f"{row['code']}={row['count']}"
            for row in report["failures"]
            if row["severity"] == "P0"
        ]
        raise RuntimeError("sandbox-school 业务关系闭包失败: " + ", ".join(failures))
    return report
