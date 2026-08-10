"""Deterministic zh-CN copy for Stage D academic DecisionTrace.

This module contains explanation text only. It never decides eligibility, graduation
status, numeric thresholds or remediation routes. Business code owns those facts and
passes any allowed resolution explicitly in ``availableResolutions``.
"""

SELECTION_RULE_MESSAGES = {
    "STUDENT_STATUS_NOT_ELIGIBLE": "当前学籍状态不满足本次选课资格。",
    "BATCH_NOT_OPEN": "当前不在该选课批次允许办理的时间范围内。",
    "OUT_OF_COLLEGE_SCOPE": "该课程不在当前学生所属学院的开放范围内。",
    "OUT_OF_MAJOR_SCOPE": "该课程不在当前学生所属专业的开放范围内。",
    "OUT_OF_GRADE_SCOPE": "该课程不在当前学生年级的开放范围内。",
    "ALREADY_SELECTED": "当前课程已存在有效选课记录，不能重复选课。",
    "COURSE_ALREADY_PASSED": "该课程已有通过的正式成绩，当前规则不允许重复选择。",
    "PREREQUISITE_NOT_MET": "该课程要求的先修课程尚未满足。",
    "MAX_CREDITS_EXCEEDED": "本次选课后将超过该批次允许的学分上限。",
    "TIME_CONFLICT": "该课程与当前已选课程存在上课时间冲突。",
    "COURSE_FULL": "该课程当前可用容量已满。",
    "COURSE_MASTER_MISSING": "选课供给无法关联到有效课程主档，系统已拒绝继续办理。",
    "COURSE_RULE_BROKEN": "该课程的正式选课规则数据不完整或已损坏，系统已拒绝继续办理。",
    "TERM_ARCHIVED": "该学期已经归档，普通选课写入已关闭。",
    "SELECTION_LOCKED": "当前选课供给或批次处于锁定状态，暂不能办理。",
    "LOTTERY_PENDING": "该课程仍处于抽签或结果待确认阶段，当前不能直接形成选课结果。",
}

GRADUATION_RULE_MESSAGES = {
    "PROGRAM_UNRESOLVED": "当前培养方案未能唯一确定，系统不能据此形成毕业资格结论。",
    "TOTAL_CREDITS_INSUFFICIENT": "当前已获得总学分尚未达到培养方案要求。",
    "REQUIRED_COURSE_FAILED": "仍有培养方案要求的必修课程未达到通过条件。",
    "ELECTIVE_CREDITS_INSUFFICIENT": "当前选修课程学分尚未达到培养方案要求。",
    "PRACTICE_CREDITS_INSUFFICIENT": "当前实践类学分尚未达到培养方案要求。",
    "INTERNSHIP_INCOMPLETE": "岗位实习的正式完成事实尚未满足毕业资格要求。",
    "GRADUATION_DESIGN_INCOMPLETE": "毕业设计的正式完成事实尚未满足毕业资格要求。",
    "DISCIPLINE_BLOCK": "当前存在会阻断毕业资格结论的纪律处分事实。",
    "ACADEMIC_DATA_UNKNOWN": "关键学业事实缺失、未知或存在歧义，系统不能把未知状态当作通过。",
    "GRADUATION_ALREADY_FINAL": "该学生已经形成正式毕业结论，不能按普通预审流程重复形成结论。",
}

RULE_MESSAGES = {**SELECTION_RULE_MESSAGES, **GRADUATION_RULE_MESSAGES}
