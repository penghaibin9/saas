"""学生服务目录：有限导航元数据，不查询业务记录，不代表办理资格。

首页 quickServices 按阶段推荐；大厅按学校模块授权展示完整目录。
每个办理页仍执行原有本人范围、开放时间、状态机与写权限校验。
"""
from app.core.context import current_tenant_id
from app.core.exceptions import no_permission
from app.core.security import require_mobile_student
from app.services.module_access_service import module_access_state
from app.services.mobile_student_home_projection import _service_entry_action


# 路径均对应 pages.json 正式入口；毕设过程材料统一进入既有过程工作区。
DIRECTORY = (
    ("studentAffairs", "学工中心", "/pages/student/affairs/index", (
        ("入学与住宿", "迎新报到", "/pages/student/orientation/index"),
        ("入学与住宿", "我的宿舍", "/pages/student/affairs/dorm"),
        ("日常事务", "我的请假", "/pages/student/affairs/leave"),
        ("日常事务", "谈心谈话", "/pages/student/affairs/talk"),
        ("日常事务", "活动与二课", "/pages/student/affairs/activity"),
        ("日常事务", "违纪申诉", "/pages/student/affairs/discipline"),
        ("日常事务", "服务申请", "/pages/student/service-apply/index"),
        ("奖助与帮扶", "困难认定", "/pages/student/affairs/aid"),
        ("奖助与帮扶", "奖助申请", "/pages/student/affairs/funding"),
        ("奖助与帮扶", "勤工助学", "/pages/student/affairs/work-study"),
        ("奖助与帮扶", "助学贷款", "/pages/student/affairs/loan"),
        ("奖助与帮扶", "减免与临时补助", "/pages/student/affairs/reduction"),
    )),
    ("academicAffairs", "教务中心", "/pages/student/academic-affairs/index", (
        ("课表与考试", "我的课表", "/pages/student/academic-affairs/schedule"),
        ("课表与考试", "考试与缓考", "/pages/student/academic-affairs/exam"),
        ("课表与考试", "补考重修", "/pages/student/academic-affairs/makeup"),
        ("课表与考试", "等级考试", "/pages/student/academic-affairs/level-exam"),
        ("成绩与学业", "我的成绩", "/pages/student/academic-affairs/transcript"),
        ("成绩与学业", "学分修读", "/pages/student/academic-affairs/credits"),
        ("成绩与学业", "学业预警", "/pages/student/academic-affairs/warning"),
        ("成绩与学业", "成绩认定", "/pages/student/academic-affairs/recognition"),
        ("成绩与学业", "成绩复查", "/pages/student/academic-affairs/recheck"),
        ("成绩与学业", "毕业进度", "/pages/student/academic-affairs/graduation"),
        ("成绩与学业", "清考结果", "/pages/student/academic-affairs/clearance"),
        ("学习事务", "网上选课", "/pages/student/academic-affairs/selection"),
        ("学习事务", "学期注册", "/pages/student/academic-affairs/registration"),
        ("学习事务", "学籍与异动", "/pages/student/academic-affairs/status"),
        ("学习事务", "专业分流", "/pages/student/academic-affairs/major-split"),
        ("学习事务", "我的教材", "/pages/student/academic-affairs/textbook"),
        ("学习事务", "我的考勤", "/pages/student/academic-affairs/attendance"),
        ("学习事务", "校历", "/pages/student/academic-affairs/calendar"),
        ("学习事务", "学生评教", "/pages/student/academic-affairs/evaluation"),
    )),
    ("internship", "岗位实习", "/pages/student-internship/index", (
        ("日常与结果", "周报与过程报告", "/pages/student-internship/index"),
        ("准备与申请", "实习意向", "/pages/student-internship/intention/index"),
        ("准备与申请", "企业岗位", "/pages/student-internship/enterprises/index"),
        ("准备与申请", "实习申请", "/pages/student-internship/application/index"),
        ("准备与申请", "志愿结果", "/pages/student-internship/volunteer-result/index"),
        ("上岗准备", "知情确认", "/pages/student-internship/consent/index"),
        ("上岗准备", "安全教育", "/pages/student-internship/safety/index"),
        ("上岗准备", "三方协议", "/pages/student-internship/agreement/index"),
        ("上岗准备", "实习保险", "/pages/student-internship/insurance/index"),
        ("日常与结果", "实习计划", "/pages/student-internship/plan/index"),
        ("日常与结果", "实习打卡", "/pages/student-internship/checkin/index"),
        ("日常与结果", "实习请假", "/pages/student-internship/leave/index"),
        ("日常与结果", "补卡申请", "/pages/student-internship/makeup/index"),
        ("日常与结果", "调岗退岗", "/pages/student-internship/change/index"),
        ("日常与结果", "实习求助", "/pages/student-internship/help/index"),
        ("日常与结果", "实习鉴定", "/pages/student-internship/self-eval/index"),
    )),
    ("graduation", "毕业设计", "/pages/student/graduation/index", (
        ("课题与任务", "毕设选题", "/pages/student/graduation/topics/index"),
        ("课题与任务", "任务书", "/pages/student/graduation/taskbook/index"),
        ("过程与结果", "开题、中期与成果", "/pages/student/graduation/index"),
        ("过程与结果", "答辩安排", "/pages/student/graduation/defense/index"),
    )),
)


def service_directory(user: dict) -> dict:
    require_mobile_student(user)
    tenant_id = current_tenant_id()
    if not tenant_id:
        raise no_permission("学校上下文失效，请重新登录")
    categories, items = [], []
    for key, label, path, services in DIRECTORY:
        state = module_access_state(int(tenant_id), key)
        allowed = state.get("allowed") is True
        reason = ""
        if not allowed:
            reason = {
                "NOT_ENTITLED": "学校尚未开通此模块",
                "SCHOOL_DISABLED": "学校已暂停此模块",
            }.get(state.get("reasonCode"), "此模块暂不可用，请联系学校确认开放状态")
        entry = {"key": key, "label": label, "path": path}
        action = _service_entry_action(entry)
        if not allowed:
            action.update(target=None, allowedActions=[], disabledReason=reason)
        categories.append({"key": key, "label": label, "action": action, "reason": reason})
        # 保留四个分类及未开放原因，但不下发未授权模块的子菜单。
        if not allowed:
            continue
        for group, name, route in services:
            identity = f"{key}:{route}"
            items.append({"id": identity, "name": name, "cat": key, "group": group,
                          "desc": f"{label} · {group}", "dept": "",
                          "action": _service_entry_action({"key": identity, "label": name, "path": route})})
    return {"categories": categories, "items": items}
