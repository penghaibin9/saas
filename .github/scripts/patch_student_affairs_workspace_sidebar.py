from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAV = ROOT / "frontend/src/config/navPlan.js"
LAYOUT = ROOT / "frontend/src/layouts/BasePortalLayout.vue"
UNIT = ROOT / "frontend/tests/studentAffairs.v6WorkspaceNav.test.mjs"
E2E = ROOT / "e2e/specs/student-affairs-v6-a1-sidebar-deeplinks.spec.mjs"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one old block, got {count}")
    return text.replace(old, new, 1)


nav = NAV.read_text(encoding="utf-8")

nav = replace_once(
    nav,
    """function H(label, path, permissionKey, entryType, opts) {
  return { label, path, status: 'implemented', disabled: false, badge: '', hidden: true,
    ...(permissionKey ? { permissionKey } : {}), ...(entryType ? { entryType } : {}), ...(opts || {}) }
}
""",
    """function H(label, path, permissionKey, entryType, opts) {
  return { label, path, status: 'implemented', disabled: false, badge: '', hidden: true,
    ...(permissionKey ? { permissionKey } : {}), ...(entryType ? { entryType } : {}), ...(opts || {}) }
}
/** 搜索深链：不占侧栏，但可由顶部功能搜索命中；详情页仍用 H()，禁止无对象参数的假跳转。 */
function D(label, path, permissionKey, entryType, opts) {
  return {
    ...I(label, path, permissionKey, entryType, opts),
    hidden: true,
    searchable: true
  }
}
""",
    "add searchable deep-link helper",
)

nav = replace_once(
    nav,
    """const _CORRECTION_ANY = ['academicAffairs.roster.correction.view',
  'academicAffairs.roster.correction.review']

/** 二级模块：有 path=已实现入口；无独立入口但含已实现子页=可展开容器；
""",
    """const _CORRECTION_ANY = ['academicAffairs.roster.correction.view',
  'academicAffairs.roster.correction.review']
const _STU_CREATE_ANY = ['student.profile.create', 'student.profile.manage']

/** 二级模块：有 path=已实现入口；无独立入口但含已实现子页=可展开容器；
""",
    "add student create permission set",
)

nav = replace_once(
    nav,
    """function mod(key, label, path, children, permissionKey) {
  const childList = children || []
  const hasLiveChild = childList.some((child) => child.status === 'implemented' || child.status === 'partial')
  const s = path
    ? { path, status: 'implemented', disabled: false, badge: '' }
    : hasLiveChild
      ? { status: 'implemented', disabled: false, badge: '', entryType: 'CONTAINER' }
    : { status: 'planned', disabled: true, badge: '待施工' }
  return {
    key, label, ...s, children: childList,
    ...(permissionKey ? { permissionKey } : {})
  }
}
""",
    """function mod(key, label, path, children, permissionKey, opts) {
  const childList = children || []
  const hasLiveChild = childList.some((child) => child.status === 'implemented' || child.status === 'partial')
  const s = path
    ? { path, status: 'implemented', disabled: false, badge: '' }
    : hasLiveChild
      ? { status: 'implemented', disabled: false, badge: '', entryType: 'CONTAINER' }
    : { status: 'planned', disabled: true, badge: '待施工' }
  return {
    key, label, ...s, children: childList,
    ...(permissionKey ? { permissionKey } : {}),
    ...(opts || {})
  }
}
""",
    "extend module metadata",
)

student_block = r"""  /* ═══════════ 一级②：学工中心 ═══════════ */
  grp('student-affairs', '学工中心', 'studentAffairs', [
    mod('sa-workbench', '今日工作', '/admin/student-affairs/dashboard', [
      I('今日工作台', '/admin/student-affairs/dashboard', 'studentAffairs.dashboard.view', 'WORKBENCH', {
        sectionKey: 'start', sectionLabel: '开始工作'
      }),
      I('统一待办', '/admin/approval/todos', 'approval.todo.view', 'TASK_QUEUE', {
        sectionKey: 'start', sectionLabel: '开始工作'
      }),
      H('旧辅导员工作台', '/admin/student-affairs/workbench', 'studentAffairs.dashboard.view', 'COMPAT', {
        activeLabel: '今日工作台'
      })
    ], null, {
      ordinal: '01',
      description: '今天先处理什么',
      sectionKey: 'wave-1',
      sectionLabel: '第一波 · 高频主线',
      permissionAny: ['studentAffairs.dashboard.view', 'approval.todo.view']
    }),

    mod('sa-profile', '唯一学生360', '/admin/student/list', [
      I('学生主档', '/admin/student/list', null, 'WORKBENCH', {
        permissionAny: _STU_VIEW_ANY, sectionKey: 'student', sectionLabel: '学生对象'
      }),
      D('学生补录', '/admin/student/list/new', null, 'ACTION', {
        permissionAny: _STU_CREATE_ANY, activeLabel: '学生主档',
        sectionKey: 'student', sectionLabel: '学生对象'
      }),
      H('学生360详情', '/admin/student', null, 'DETAIL', {
        permissionAny: _STU_VIEW_ANY, activeLabel: '学生主档', matchPrefix: true
      }),
      H('旧学工画像入口', '/admin/student-affairs/profile', 'studentAffairs.student.view', 'COMPAT', {
        activeLabel: '学生主档'
      }),
      I('班级管理', '/admin/campus-service/classes', 'studentAffairs.class.view', 'WORKBENCH', {
        sectionKey: 'responsibility', sectionLabel: '班级与责任'
      }),
      H('班级详情', '/admin/campus-service/classes', 'studentAffairs.class.view', 'DETAIL', {
        activeLabel: '班级管理', matchPrefix: true
      }),
      I('辅导员责任台账', '/admin/student-affairs/counselor-assignments', 'studentAffairs.class.view', 'CONFIG_VIEW', {
        sectionKey: 'responsibility', sectionLabel: '班级与责任'
      }),
      I('辅导员考评', '/admin/student-affairs/counselor-eval', 'studentAffairs.counselorEval.view', 'ANALYTICS_VIEW', {
        sectionKey: 'responsibility', sectionLabel: '班级与责任'
      }),
      I('学籍异动台账', '/admin/student/status', null, 'LEDGER', {
        permissionAny: _SC_VIEW_ANY, sectionKey: 'governance', sectionLabel: '数据治理'
      }),
      I('信息更正审核', '/admin/student/corrections', null, 'TASK_QUEUE', {
        permissionAny: _CORRECTION_ANY, sectionKey: 'governance', sectionLabel: '数据治理'
      }),
      I('身份核验', '/admin/student/identity', null, 'CAPABILITY_ONLY', {
        permissionAny: _STU_VIEW_ANY, sectionKey: 'governance', sectionLabel: '数据治理'
      }),
      I('数据导入', '/admin/student/import', null, 'ACTION', {
        permissionAny: _STU_VIEW_ANY, sectionKey: 'governance', sectionLabel: '数据治理'
      }),
      I('数据导出', '/admin/student/import-export', 'student.export', 'LEDGER', {
        sectionKey: 'governance', sectionLabel: '数据治理'
      })
    ], null, {
      ordinal: '02',
      description: '围绕学生看完整背景',
      sectionKey: 'wave-1',
      sectionLabel: '第一波 · 高频主线',
      legacyKeys: ['sa-classes'],
      permissionAny: [
        ..._STU_VIEW_ANY,
        ..._SC_VIEW_ANY,
        ..._CORRECTION_ANY,
        ..._STU_CREATE_ANY,
        'studentAffairs.class.view',
        'studentAffairs.counselorEval.view',
        'student.export'
      ]
    }),

    mod('sa-risk', '风险与重点学生', '/admin/student-affairs/risk', [
      I('风险工作台', '/admin/student-affairs/risk', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        sectionKey: 'risk', sectionLabel: '风险处置'
      }),
      I('重点学生跟进', '/admin/student-affairs/talk/key-follow', 'studentAffairs.talk.view', 'TASK_QUEUE', {
        sectionKey: 'risk', sectionLabel: '风险处置'
      }),
      I('人工风险标签', '/admin/student/risk-tags', 'studentAffairs.risk.view', 'CONFIG_VIEW', {
        sectionKey: 'support', sectionLabel: '支持能力'
      }),
      H('风险处置详情', '/admin/student-affairs/risk', 'studentAffairs.risk.view', 'DETAIL', {
        activeLabel: '风险工作台', matchPrefix: true
      })
    ], null, {
      ordinal: '03',
      description: '按学生聚合多来源风险',
      sectionKey: 'wave-1',
      sectionLabel: '第一波 · 高频主线',
      permissionAny: ['studentAffairs.risk.view', 'studentAffairs.talk.view']
    }),

    mod('sa-talks', '谈心家校与回访', '/admin/student-affairs/talk', [
      I('谈心谈话', '/admin/student-affairs/talk', 'studentAffairs.talk.view', 'WORKBENCH', {
        sectionKey: 'handle', sectionLabel: '沟通与跟进'
      }),
      I('家校联系', '/admin/student-affairs/family', 'studentAffairs.homeSchool.view', 'WORKBENCH', {
        sectionKey: 'handle', sectionLabel: '沟通与跟进'
      }),
      I('家校回执', '/admin/student-affairs/family/receipts', 'studentAffairs.homeSchool.view', 'TASK_QUEUE', {
        sectionKey: 'handle', sectionLabel: '沟通与跟进'
      }),
      I('谈话台账', '/admin/student-affairs/talk/ledger', 'studentAffairs.talk.view', 'LEDGER', {
        sectionKey: 'record', sectionLabel: '台账与分析'
      }),
      I('谈话统计', '/admin/student-affairs/talk/stats', 'studentAffairs.talk.view', 'ANALYTICS_VIEW', {
        sectionKey: 'record', sectionLabel: '台账与分析'
      })
    ], null, {
      ordinal: '04',
      description: '处置后形成闭环',
      sectionKey: 'wave-1',
      sectionLabel: '第一波 · 高频主线',
      permissionAny: ['studentAffairs.talk.view', 'studentAffairs.homeSchool.view']
    }),

    mod('sa-leave', '请假与返校', '/admin/student-affairs/leave', [
      I('请假审批', '/admin/student-affairs/leave', 'studentAffairs.leave.view', 'TASK_QUEUE', {
        sectionKey: 'handle', sectionLabel: '当前办理'
      }),
      I('销假与续假', '/admin/student-affairs/leave/followup', 'studentAffairs.leave.view', 'TASK_QUEUE', {
        sectionKey: 'handle', sectionLabel: '当前办理'
      }),
      I('逾期未销假', '/admin/student-affairs/leave/ledger?status=OVERDUE', 'studentAffairs.leave.view', 'TASK_QUEUE', {
        sectionKey: 'handle', sectionLabel: '当前办理'
      }),
      I('请假台账', '/admin/student-affairs/leave/ledger', 'studentAffairs.leave.view', 'LEDGER', {
        sectionKey: 'record', sectionLabel: '台账与分析'
      }),
      I('请假统计', '/admin/student-affairs/leave/stats', 'studentAffairs.leave.view', 'ANALYTICS_VIEW', {
        sectionKey: 'record', sectionLabel: '台账与分析'
      })
    ], null, {
      ordinal: '05',
      description: '申请 → 返校 → 超期',
      sectionKey: 'wave-2',
      sectionLabel: '第二波 · 业务闭环',
      permissionAny: ['studentAffairs.leave.view']
    }),

    mod('sa-aid', '困难与资助', '/admin/student-affairs/aid', [
      I('困难认定', '/admin/student-affairs/aid', 'studentAffairs.aid.view', 'WORKBENCH', {
        sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),
      D('认定批次', '/admin/student-affairs/aid/batches', 'studentAffairs.aid.view', 'CONFIG_VIEW', {
        activeLabel: '困难认定', sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),
      I('困难学生库', '/admin/student-affairs/aid/difficult-students', 'studentAffairs.aid.view', 'LEDGER', {
        sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),
      I('困难认定公示', '/admin/student-affairs/aid/publicity', 'studentAffairs.aid.view', 'TASK_QUEUE', {
        sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),
      D('困难认定异议', '/admin/student-affairs/aid/objections', 'studentAffairs.aid.view', 'TASK_QUEUE', {
        activeLabel: '困难认定公示', sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),
      I('困难认定台账', '/admin/student-affairs/aid/ledger', 'studentAffairs.aid.view', 'LEDGER', {
        sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),
      D('困难认定统计', '/admin/student-affairs/aid/stats', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        activeLabel: '困难认定台账', sectionKey: 'difficulty', sectionLabel: '困难认定'
      }),

      I('奖助评审', '/admin/student-affairs/funding', 'studentAffairs.funding.view', 'WORKBENCH', {
        sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      I('资助项目', '/admin/student-affairs/funding/projects', 'studentAffairs.funding.view', 'CONFIG_VIEW', {
        sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      D('资助批次', '/admin/student-affairs/funding/batches', 'studentAffairs.funding.view', 'CONFIG_VIEW', {
        activeLabel: '资助项目', sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      I('资助公示', '/admin/student-affairs/funding/publicity', 'studentAffairs.funding.view', 'TASK_QUEUE', {
        sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      D('资助公示申诉', '/admin/student-affairs/funding/appeals', 'studentAffairs.funding.view', 'TASK_QUEUE', {
        activeLabel: '资助公示', sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      I('资助发放', '/admin/student-affairs/funding/disbursements', 'studentAffairs.funding.view', 'TASK_QUEUE', {
        sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      D('助学金管理', '/admin/campus-service/grants', 'studentAffairs.funding.view', 'CONFIG_VIEW', {
        activeLabel: '奖助评审', sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      I('资助台账', '/admin/student-affairs/funding/ledger', 'studentAffairs.funding.view', 'LEDGER', {
        sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),
      D('资助统计', '/admin/student-affairs/funding/stats', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        activeLabel: '资助台账', sectionKey: 'funding', sectionLabel: '奖助评审与发放'
      }),

      I('勤工助学', '/admin/student-affairs/funding/work-study', 'studentAffairs.funding.workstudy.manage', 'WORKBENCH', {
        sectionKey: 'special', sectionLabel: '专项资助'
      }),
      I('助学贷款', '/admin/student-affairs/funding/loans', 'studentAffairs.funding.loan.manage', 'WORKBENCH', {
        sectionKey: 'special', sectionLabel: '专项资助'
      }),
      I('减免与临时补助', '/admin/student-affairs/funding/fee-reductions', 'studentAffairs.funding.reduction.manage', 'WORKBENCH', {
        sectionKey: 'special', sectionLabel: '专项资助'
      })
    ], null, {
      ordinal: '06',
      description: '认定 → 资助 → 发放',
      sectionKey: 'wave-2',
      sectionLabel: '第二波 · 业务闭环',
      legacyKeys: ['sa-difficulty'],
      permissionAny: [
        'studentAffairs.aid.view',
        'studentAffairs.funding.view',
        'studentAffairs.stats.view',
        'studentAffairs.funding.workstudy.manage',
        'studentAffairs.funding.loan.manage',
        'studentAffairs.funding.reduction.manage'
      ]
    }),

    mod('sa-discipline', '违纪处分与教育', '/admin/student-affairs/discipline', [
      I('处分工作台', '/admin/student-affairs/discipline', 'studentAffairs.discipline.view', 'WORKBENCH', {
        sectionKey: 'handle', sectionLabel: '处分办理'
      }),
      I('送达与申诉复核', '/admin/student-affairs/discipline/appeals', 'studentAffairs.discipline.view', 'TASK_QUEUE', {
        sectionKey: 'handle', sectionLabel: '处分办理'
      }),
      I('违纪台账', '/admin/student-affairs/discipline/ledger', 'studentAffairs.discipline.view', 'LEDGER', {
        sectionKey: 'record', sectionLabel: '台账与分析'
      }),
      I('处分统计', '/admin/student-affairs/discipline/stats', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        sectionKey: 'record', sectionLabel: '台账与分析'
      })
    ], null, {
      ordinal: '07',
      description: '处分 → 教育 → 回访',
      sectionKey: 'wave-2',
      sectionLabel: '第二波 · 业务闭环',
      permissionAny: ['studentAffairs.discipline.view', 'studentAffairs.stats.view']
    }),

    mod('sa-dorm', '宿舍与公寓', '/admin/student-affairs/dormitory', [
      I('宿舍驾驶舱', '/admin/student-affairs/dormitory', 'studentAffairs.dorm.view', 'WORKBENCH', {
        sectionKey: 'resource', sectionLabel: '房源与入住'
      }),
      I('房源管理', '/admin/student-affairs/dorm/resource', 'studentAffairs.dorm.view', 'CONFIG_VIEW', {
        sectionKey: 'resource', sectionLabel: '房源与入住'
      }),
      I('分配计划', '/admin/student-affairs/dorm/allocation', 'studentAffairs.dorm.view', 'CONFIG_VIEW', {
        sectionKey: 'resource', sectionLabel: '房源与入住'
      }),
      I('入住管理', '/admin/student-affairs/dorm/checkin', 'studentAffairs.dorm.view', 'WORKBENCH', {
        sectionKey: 'resource', sectionLabel: '房源与入住'
      }),
      I('调宿与退宿', '/admin/student-affairs/dorm/transfer', 'studentAffairs.dorm.view', 'TASK_QUEUE', {
        sectionKey: 'operation', sectionLabel: '调整与质量'
      }),
      I('宿舍检查', '/admin/student-affairs/dorm/check', 'studentAffairs.dorm.view', 'TASK_QUEUE', {
        sectionKey: 'operation', sectionLabel: '调整与质量'
      }),
      I('宿舍异常', '/admin/student-affairs/dorm/exception', 'studentAffairs.dorm.view', 'TASK_QUEUE', {
        sectionKey: 'operation', sectionLabel: '调整与质量'
      }),
      I('宿舍统计', '/admin/student-affairs/dorm/stats', 'studentAffairs.dorm.view', 'ANALYTICS_VIEW', {
        sectionKey: 'operation', sectionLabel: '调整与质量'
      })
    ], null, {
      ordinal: '08',
      description: '房源 → 入住 → 异常',
      sectionKey: 'wave-2',
      sectionLabel: '第二波 · 业务闭环',
      permissionAny: ['studentAffairs.dorm.view']
    }),

    mod('sa-activities', '活动与成长', '/admin/student-affairs/activity', [
      I('活动运营', '/admin/student-affairs/activity', 'studentAffairs.activity.view', 'WORKBENCH', {
        sectionKey: 'activity', sectionLabel: '活动与成果'
      }),
      I('志愿服务', '/admin/student-affairs/activity/volunteer', 'studentAffairs.activity.view', 'LEDGER', {
        sectionKey: 'activity', sectionLabel: '活动与成果'
      }),
      I('第二课堂积分', '/admin/student-affairs/activity/second-class', 'studentAffairs.activity.view', 'LEDGER', {
        sectionKey: 'activity', sectionLabel: '活动与成果'
      }),
      I('积分申诉', '/admin/student-affairs/activity/credit-appeals', 'studentAffairs.activity.view', 'TASK_QUEUE', {
        sectionKey: 'activity', sectionLabel: '活动与成果'
      }),
      I('活动统计', '/admin/student-affairs/activity/stats', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        sectionKey: 'activity', sectionLabel: '活动与成果'
      }),
      I('社团管理', '/admin/student-affairs/activity/clubs', 'studentAffairs.club.view', 'WORKBENCH', {
        sectionKey: 'organization', sectionLabel: '社团与组织'
      }),
      I('学生干部与组织', '/admin/student-affairs/activity/organizations', 'studentAffairs.org.view', 'WORKBENCH', {
        sectionKey: 'organization', sectionLabel: '社团与组织'
      }),
      I('党团建设', '/admin/student-affairs/activity/party-league', 'studentAffairs.league.view', 'WORKBENCH', {
        sectionKey: 'organization', sectionLabel: '社团与组织'
      })
    ], null, {
      ordinal: '09',
      description: '活动成果沉淀成长事实',
      sectionKey: 'wave-3',
      sectionLabel: '第三波 · 生命周期 / 专项',
      permissionAny: [
        'studentAffairs.activity.view',
        'studentAffairs.stats.view',
        'studentAffairs.club.view',
        'studentAffairs.org.view',
        'studentAffairs.league.view'
      ]
    }),

    mod('sa-orientation', '数字迎新', '/admin/orientation', [
      I('迎新总览', '/admin/orientation', 'studentAffairs.orientation.view', 'WORKBENCH', {
        sectionKey: 'stage-1', sectionLabel: '阶段 1 · 总览'
      }),
      I('批次与规则', '/admin/orientation/batches', 'studentAffairs.orientation.view', 'CONFIG_VIEW', {
        sectionKey: 'stage-1', sectionLabel: '阶段 1 · 总览'
      }),
      D('报到流程配置', '/admin/orientation/flow-config', 'studentAffairs.orientation.view', 'CONFIG_VIEW', {
        activeLabel: '批次与规则', sectionKey: 'stage-1', sectionLabel: '阶段 1 · 总览'
      }),
      D('现场报到点', '/admin/orientation/checkin-points', 'studentAffairs.orientation.view', 'CONFIG_VIEW', {
        activeLabel: '批次与规则', sectionKey: 'stage-1', sectionLabel: '阶段 1 · 总览'
      }),

      I('新生底账', '/admin/orientation/students', 'studentAffairs.orientation.view', 'WORKBENCH', {
        sectionKey: 'stage-2', sectionLabel: '阶段 2 · 新生底账'
      }),
      H('新生详情', '/admin/orientation/students', 'studentAffairs.orientation.view', 'DETAIL', {
        activeLabel: '新生底账', matchPrefix: true
      }),
      D('新生数据', '/admin/orientation/data', 'studentAffairs.orientation.view', 'LEDGER', {
        activeLabel: '新生底账', sectionKey: 'stage-2', sectionLabel: '阶段 2 · 新生底账'
      }),
      D('新生信息核验', '/admin/orientation/verify', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        activeLabel: '新生底账', sectionKey: 'stage-2', sectionLabel: '阶段 2 · 新生底账'
      }),

      I('报到资格', '/admin/orientation/qualification', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        sectionKey: 'stage-3', sectionLabel: '阶段 3 · 资格闸门'
      }),

      I('报到办理', '/admin/orientation/progress', 'studentAffairs.orientation.view', 'WORKBENCH', {
        sectionKey: 'stage-4', sectionLabel: '阶段 4 · 报到办理'
      }),
      D('缴费与绿色通道', '/admin/orientation/payment', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        activeLabel: '报到办理', sectionKey: 'stage-4', sectionLabel: '阶段 4 · 报到办理'
      }),
      H('旧绿色通道入口', '/admin/orientation/green-channels', 'studentAffairs.orientation.view', 'COMPAT', {
        activeLabel: '报到办理'
      }),
      D('材料审核', '/admin/orientation/materials', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        activeLabel: '报到办理', sectionKey: 'stage-4', sectionLabel: '阶段 4 · 报到办理'
      }),
      D('宿舍预分配', '/admin/orientation/dorm-preassign', 'studentAffairs.orientation.view', 'CONFIG_VIEW', {
        activeLabel: '报到办理', sectionKey: 'stage-4', sectionLabel: '阶段 4 · 报到办理'
      }),
      D('宿舍入住', '/admin/orientation/dorm', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        activeLabel: '报到办理', sectionKey: 'stage-4', sectionLabel: '阶段 4 · 报到办理'
      }),

      I('异常闭环', '/admin/orientation/exceptions', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        sectionKey: 'stage-5', sectionLabel: '阶段 5 · 异常闭环'
      }),
      D('未报到学生', '/admin/orientation/no-show', 'studentAffairs.orientation.view', 'TASK_QUEUE', {
        activeLabel: '异常闭环', sectionKey: 'stage-5', sectionLabel: '阶段 5 · 异常闭环'
      }),
      D('迎新通知', '/admin/orientation/notices', 'studentAffairs.orientation.view', 'ACTION', {
        activeLabel: '异常闭环', sectionKey: 'stage-5', sectionLabel: '阶段 5 · 异常闭环'
      }),

      I('统计归档', '/admin/orientation/statistics', 'studentAffairs.orientation.view', 'ANALYTICS_VIEW', {
        sectionKey: 'stage-6', sectionLabel: '阶段 6 · 统计归档'
      }),
      D('迎新归档', '/admin/orientation/archive', 'studentAffairs.orientation.view', 'ARCHIVE', {
        activeLabel: '统计归档', sectionKey: 'stage-6', sectionLabel: '阶段 6 · 统计归档'
      })
    ], null, {
      ordinal: '10',
      description: '新生 → 报到 → 归档',
      sectionKey: 'wave-3',
      sectionLabel: '第三波 · 生命周期 / 专项',
      permissionAny: ['studentAffairs.orientation.view']
    }),

    mod('sa-mental', '心理专项', '/admin/student-affairs/mental/summary', [
      I('心理预警摘要', '/admin/student-affairs/mental/summary', 'studentAffairs.risk.view', 'WORKBENCH', {
        sectionKey: 'summary', sectionLabel: '必要摘要'
      }),
      I('心理关注名单', '/admin/student-affairs/mental', 'studentAffairs.risk.psyDetail.view', 'WORKBENCH', {
        sectionKey: 'specialist', sectionLabel: '专项授权'
      }),
      I('转介与回访', '/admin/student-affairs/mental/referrals', 'studentAffairs.risk.psyDetail.view', 'TASK_QUEUE', {
        sectionKey: 'specialist', sectionLabel: '专项授权'
      }),
      I('危机升级', '/admin/student-affairs/mental/crisis', 'studentAffairs.risk.psyDetail.view', 'TASK_QUEUE', {
        sectionKey: 'specialist', sectionLabel: '专项授权'
      }),
      I('心理统计', '/admin/student-affairs/mental/stats', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        sectionKey: 'specialist', sectionLabel: '专项授权'
      })
    ], null, {
      ordinal: '11',
      description: '按角色显示敏感工作区',
      sectionKey: 'wave-3',
      sectionLabel: '第三波 · 生命周期 / 专项',
      permissionAny: [
        'studentAffairs.risk.view',
        'studentAffairs.risk.psyDetail.view',
        'studentAffairs.stats.view'
      ]
    }),

    mod('sa-archive-stats', '统计与档案', '/admin/student-affairs/stats/cockpit', [
      I('统计驾驶舱', '/admin/student-affairs/stats/cockpit', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        sectionKey: 'stats', sectionLabel: '统计分析'
      }),
      I('学工统计', '/admin/student-affairs/stats', 'studentAffairs.stats.view', 'ANALYTICS_VIEW', {
        sectionKey: 'stats', sectionLabel: '统计分析'
      }),
      I('学工归档', '/admin/student-affairs/archive', 'studentAffairs.archive.view', 'ARCHIVE', {
        sectionKey: 'archive', sectionLabel: '正式归档'
      }),
      I('学生档案包', '/admin/student-affairs/archive/packages', 'studentAffairs.archive.view', 'DETAIL', {
        sectionKey: 'archive', sectionLabel: '正式归档'
      }),
      H('档案包详情', '/admin/student-affairs/archive/packages', 'studentAffairs.archive.view', 'DETAIL', {
        activeLabel: '学生档案包', matchPrefix: true
      })
    ], null, {
      ordinal: '12',
      description: '领导聚合与正式归档',
      sectionKey: 'wave-3',
      sectionLabel: '第三波 · 生命周期 / 专项',
      permissionAny: ['studentAffairs.stats.view', 'studentAffairs.archive.view']
    })
  ], {
    workspaceTitle: '学工业务工作区',
    workspaceDescription: '完整能力继续保留；日常菜单只告诉老师现在要完成什么工作。'
  }),"""

pattern = re.compile(
    r"  /\* ═══════════ 一级②：学工中心 ═══════════ \*/.*?\n\n  /\* ═══════════ 一级③：教务中心 ═══════════ \*/",
    re.S,
)
if student_block not in nav:
    matches = list(pattern.finditer(nav))
    if len(matches) != 1:
        raise SystemExit(f"student affairs block: expected one match, got {len(matches)}")
    nav = nav[: matches[0].start()] + student_block + "\n\n  /* ═══════════ 一级③：教务中心 ═══════════ */" + nav[matches[0].end():]

nav = replace_once(
    nav,
    """        hidden: false
      })
      mod2.children.forEach((leaf, i) => {
""",
    """        hidden: false,
        searchable: false,
        permissionKey: mod2.permissionKey || null,
        permissionAny: mod2.permissionAny || null,
        children: mod2.children
      })
      mod2.children.forEach((leaf, i) => {
""",
    "extend flat module index",
)

nav = replace_once(
    nav,
    """          hidden: !!leaf.hidden,
          permissionKey: leaf.permissionKey || null
        })
""",
    """          hidden: !!leaf.hidden,
          searchable: !!leaf.searchable,
          activeLabel: leaf.activeLabel || '',
          matchPrefix: !!leaf.matchPrefix,
          permissionKey: leaf.permissionKey || null,
          permissionAny: leaf.permissionAny || null,
          source: leaf
        })
""",
    "extend flat leaf index",
)

nav = replace_once(
    nav,
    """      if (prefixOnly) {
        // 父路径（如 /admin/internship）不可抢占子路由高亮
        score = cand.path.length - 500
""",
    """      if (prefixOnly) {
        // 普通父路径不可抢占子路由；显式 matchPrefix 的隐藏详情归属可映射到可见工作区。
        score = row.matchPrefix ? cand.path.length - 0.5 : cand.path.length - 500
""",
    "explicit detail prefix ownership",
)

nav = replace_once(
    nav,
    """    if (score > best.score) {
      best = { groupKey: row.groupKey, modKey: row.modKey, leafKey: row.isLeaf ? row.label : '', score }
    }
""",
    """    if (score > best.score || (score === best.score && row.isLeaf && !best.leafKey)) {
      best = {
        groupKey: row.groupKey,
        modKey: row.modKey,
        leafKey: row.isLeaf ? (row.activeLabel || row.label) : '',
        score
      }
    }
""",
    "prefer exact leaf and map deep links to visible stage",
)

nav = replace_once(
    nav,
    """    if (applyPerm && mod2.permissionKey && !matchPermission(permissionPatterns, mod2.permissionKey)) {
      return false
    }
""",
    """    if (applyPerm && mod2.permissionKey && !matchPermission(permissionPatterns, mod2.permissionKey)) {
      return false
    }
    if (applyPerm && Array.isArray(mod2.permissionAny) && mod2.permissionAny.length
        && !mod2.permissionAny.some((key) => matchPermission(permissionPatterns, key))) {
      return false
    }
""",
    "filter workspace permissionAny",
)

nav = replace_once(
    nav,
    """      .filter(keepMod)
      .map((mod2) => ({ ...mod2, children: mod2.children.filter(keepLeaf) }))
  })).filter((group) => group.children.length > 0)
""",
    """      .filter(keepMod)
      .map((mod2) => {
        const children = mod2.children.filter(keepLeaf)
        const primaryVisible = children.some((leaf) => leaf.path === mod2.path)
        const fallbackPath = children.find((leaf) => leaf.path)?.path || null
        return {
          ...mod2,
          path: applyPerm && mod2.path && !primaryVisible ? fallbackPath : mod2.path,
          children
        }
      })
  })).filter((group) => group.children.length > 0)
""",
    "project a permitted workspace landing path",
)

nav = replace_once(
    nav,
    """    if (row.hidden) continue  // 隐藏的兼容入口不进搜索
    if (applyPerm && row.permissionKey && !matchPermission(permissionPatterns, row.permissionKey)) continue  // 无权限页面不进搜索
    if (!row.label.toLowerCase().includes(q)) continue
    out.push({
      label: row.label,
      path: row.path,
""",
    """    if (row.hidden && !row.searchable) continue  // 兼容/详情不进搜索；D() 搜索深链保留
    if (applyPerm && row.permissionKey && !matchPermission(permissionPatterns, row.permissionKey)) continue
    if (applyPerm && Array.isArray(row.permissionAny) && row.permissionAny.length
        && !row.permissionAny.some((key) => matchPermission(permissionPatterns, key))) continue
    if (!row.label.toLowerCase().includes(q)) continue
    let resolvedPath = row.path
    if (!row.isLeaf && applyPerm) {
      const visibleChildren = (row.children || []).filter((leaf) => {
        if (leaf.hidden && !leaf.searchable) return false
        if (leaf.permissionKey && !matchPermission(permissionPatterns, leaf.permissionKey)) return false
        if (Array.isArray(leaf.permissionAny) && leaf.permissionAny.length
            && !leaf.permissionAny.some((key) => matchPermission(permissionPatterns, key))) return false
        return !!leaf.path
      })
      const primary = visibleChildren.find((leaf) => leaf.path === row.path)
      resolvedPath = (primary || visibleChildren[0] || {}).path || null
      if (!resolvedPath) continue
    }
    out.push({
      label: row.label,
      path: resolvedPath,
""",
    "permission-safe menu and deep-link search",
)

NAV.write_text(nav, encoding="utf-8")

layout = LAYOUT.read_text(encoding="utf-8")

layout = replace_once(
    layout,
    """      <aside class="bpl-aside" :class="{ 'is-hidden': hideAside, 'bpl-aside--subnav': !!ctx }">
""",
    """      <aside
        class="bpl-aside"
        :class="{
          'is-hidden': hideAside,
          'bpl-aside--subnav': !!ctx,
          'bpl-aside--workspace': !!(planGroup && planGroup.workspaceTitle)
        }"
      >
""",
    "workspace aside class",
)

old_tree = """        <nav v-if="ctx && !$slots.menu" class="bpl-tree">
          <div class="bpl-submods__label">{{ planGroupLabel }}</div>
          <template v-for="m in planMods" :key="m.key">
            <!-- 二级模块（有 children 显示展开箭头） -->
            <a
              class="bpl-submods__item bpl-tree__mod"
              :class="{ 'is-active': m.key === planActiveModKey, 'is-disabled': m.disabled && !m.children.length }"
              href="javascript:void(0)"
              @click="onTreeMod(m)"
            >
              <span
                v-if="m.children.length"
                class="bpl-tree__caret"
                :class="{ 'is-open': isExpanded(m.key) }"
              >▸</span>
              <span v-else class="bpl-tree__caret bpl-tree__caret--sp" />
              <span class="bpl-submods__lb" :title="m.label">{{ m.label }}</span>
              <span v-if="m.badge && m.status !== 'planned'" class="bpl-planbadge" :class="'bpl-planbadge--' + m.status">{{ m.badge }}</span>
            </a>
            <!-- 三级页面（展开时缩进显示） -->
            <div v-if="m.children.length && isExpanded(m.key)" class="bpl-tree__leaves">
              <a
                v-for="leaf in m.children"
                :key="leafKey(m, leaf)"
                class="bpl-menu__item bpl-tree__leaf"
                :class="{ 'is-active': isLeafActive(m, leaf), 'is-disabled': leaf.disabled }"
                href="javascript:void(0)"
                @click="onPlanLeaf(leaf, m)"
              >
                <span class="bpl-menu__label" :title="leaf.label">{{ leaf.label }}</span>
                <span v-if="leaf.badge && leaf.status !== 'planned'" class="bpl-planbadge" :class="'bpl-planbadge--' + leaf.status">{{ leaf.badge }}</span>
              </a>
            </div>
          </template>
        </nav>
"""
new_tree = """        <nav v-if="ctx && !$slots.menu" class="bpl-tree" :aria-label="planGroupTitle">
          <div class="bpl-tree__workspace-head">
            <strong>{{ planGroupTitle }}</strong>
            <span v-if="planGroupDescription">{{ planGroupDescription }}</span>
          </div>
          <template v-for="section in planSections" :key="section.key">
            <div v-if="section.label" class="bpl-tree__section">
              <span>{{ section.label }}</span>
              <small>{{ section.mods.length }}</small>
            </div>
            <template v-for="m in section.mods" :key="m.key">
              <!-- 二级工作区：编号 + 业务名称 + 一句话用途；点击进入主页面并展开三级。 -->
              <button
                type="button"
                class="bpl-submods__item bpl-tree__mod"
                :class="{ 'is-active': m.key === planActiveModKey, 'is-disabled': m.disabled && !m.children.length }"
                :data-workspace="m.key"
                :aria-expanded="m.children.length ? String(isExpanded(m.key)) : undefined"
                :aria-current="m.key === planActiveModKey ? 'page' : undefined"
                @click="onTreeMod(m)"
              >
                <span v-if="m.ordinal" class="bpl-tree__num" aria-hidden="true">{{ m.ordinal }}</span>
                <span
                  v-else-if="m.children.length"
                  class="bpl-tree__caret"
                  :class="{ 'is-open': isExpanded(m.key) }"
                >▸</span>
                <span v-else class="bpl-tree__caret bpl-tree__caret--sp" />
                <span class="bpl-tree__mod-copy">
                  <span class="bpl-submods__lb" :title="m.label">{{ m.label }}</span>
                  <small v-if="m.description" :title="m.description">{{ m.description }}</small>
                </span>
                <span v-if="m.badge && m.status !== 'planned'" class="bpl-planbadge" :class="'bpl-planbadge--' + m.status">{{ m.badge }}</span>
                <span
                  v-if="m.ordinal && m.children.length"
                  class="bpl-tree__caret bpl-tree__caret--tail"
                  :class="{ 'is-open': isExpanded(m.key) }"
                  aria-hidden="true"
                >▸</span>
              </button>
              <!-- 三级页面：按业务阶段分组；低频 D() 深链由顶部搜索进入，不占侧栏。 -->
              <div v-if="m.children.length && isExpanded(m.key)" class="bpl-tree__leaves">
                <template v-for="leafSection in leafSections(m)" :key="`${m.key}/${leafSection.key}`">
                  <div v-if="leafSection.label" class="bpl-tree__leaf-section">{{ leafSection.label }}</div>
                  <button
                    v-for="leaf in leafSection.leaves"
                    :key="leafKey(m, leaf)"
                    type="button"
                    class="bpl-menu__item bpl-tree__leaf"
                    :class="{ 'is-active': isLeafActive(m, leaf), 'is-disabled': leaf.disabled }"
                    :data-leaf="leaf.label"
                    :data-nav-path="leaf.path || ''"
                    :aria-current="isLeafActive(m, leaf) ? 'page' : undefined"
                    :aria-disabled="leaf.disabled ? 'true' : undefined"
                    :title="[leaf.label, leaf.description].filter(Boolean).join(' · ')"
                    @click="onPlanLeaf(leaf, m)"
                  >
                    <span class="bpl-menu__label">{{ leaf.label }}</span>
                    <span v-if="leaf.badge && leaf.status !== 'planned'" class="bpl-planbadge" :class="'bpl-planbadge--' + leaf.status">{{ leaf.badge }}</span>
                  </button>
                </template>
              </div>
            </template>
          </template>
        </nav>
"""
layout = replace_once(layout, old_tree, new_tree, "replace workspace tree")

layout = replace_once(
    layout,
    """    planGroupLabel() {
      return this.planGroup ? this.planGroup.label : ''
    },
    planMods() {
""",
    """    planGroupLabel() {
      return this.planGroup ? this.planGroup.label : ''
    },
    planGroupTitle() {
      return this.planGroup?.workspaceTitle || this.planGroupLabel
    },
    planGroupDescription() {
      return this.planGroup?.workspaceDescription || ''
    },
    planMods() {
""",
    "workspace title computed",
)

layout = replace_once(
    layout,
    """    planActiveModKey() {
      return this.planActive.modKey || (this.planMods[0] && this.planMods[0].key) || ''
    },
    /* 按当前路由定位应高亮的唯一三级叶子（复用 findActiveInPlan 拍平索引，避免遍历 planMods 全部叶子） */
""",
    """    planActiveModKey() {
      return this.planActive.modKey || (this.planMods[0] && this.planMods[0].key) || ''
    },
    planSections() {
      const sections = []
      for (const mod2 of this.planMods) {
        const key = mod2.sectionKey || '__default'
        let section = sections[sections.length - 1]
        if (!section || section.key !== key) {
          section = { key, label: mod2.sectionLabel || '', mods: [] }
          sections.push(section)
        }
        section.mods.push(mod2)
      }
      return sections
    },
    /* 按当前路由定位应高亮的唯一三级叶子（复用 findActiveInPlan 拍平索引，避免遍历 planMods 全部叶子） */
""",
    "workspace section computed",
)

layout = replace_once(
    layout,
    """    /* 二级模块是否展开：未手动记录时，默认展开「当前路由所属二级」 */
    isExpanded(key) {
""",
    """    leafSections(mod2) {
      const sections = []
      for (const leaf of (mod2?.children || [])) {
        const key = leaf.sectionKey || '__default'
        let section = sections[sections.length - 1]
        if (!section || section.key !== key) {
          section = { key, label: leaf.sectionLabel || '', leaves: [] }
          sections.push(section)
        }
        section.leaves.push(leaf)
      }
      return sections
    },
    /* 二级模块是否展开：未手动记录时，默认展开「当前路由所属二级」 */
    isExpanded(key) {
""",
    "leaf section method",
)

workspace_css = r"""
/* ══ 学工 V6 工作区侧栏：三波 / 12 工作区 / 分阶段三级深链 ══ */
.bpl-aside--workspace {
  width: 228px;
  padding: 12px 10px;
}
.bpl-tree__workspace-head {
  position: sticky;
  top: -12px;
  z-index: 3;
  margin: -2px -2px 8px;
  padding: 10px 10px 11px;
  border-bottom: 1px solid var(--dv);
  background: color-mix(in srgb, var(--bg-sidebar) 94%, transparent);
  backdrop-filter: blur(10px);
}
.bpl-tree__workspace-head strong {
  display: block;
  color: var(--t1);
  font-size: 16px;
  line-height: 24px;
  font-weight: var(--font-weight-bold);
}
.bpl-tree__workspace-head span {
  display: block;
  margin-top: 3px;
  color: var(--t3);
  font-size: 12px;
  line-height: 18px;
}
.bpl-tree__section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 6px 4px;
  color: var(--t3);
  font-size: 12px;
  line-height: 18px;
  font-weight: var(--font-weight-semibold);
}
.bpl-tree__section::after {
  flex: 1;
  height: 1px;
  background: var(--dv);
  content: '';
}
.bpl-tree__section small {
  order: 3;
  min-width: 18px;
  color: var(--t3);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.bpl-tree .bpl-tree__mod {
  width: 100%;
  min-height: 48px;
  margin-top: 2px;
  padding: 6px 7px;
  appearance: none;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  font: inherit;
}
.bpl-tree .bpl-tree__mod:hover {
  border-color: color-mix(in srgb, var(--pri) 18%, var(--card-b));
}
.bpl-tree .bpl-tree__mod.is-active {
  border-color: color-mix(in srgb, var(--pri) 22%, var(--card-b));
  background: var(--pri-bg);
}
.bpl-tree__num {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 8px;
  background: var(--primary-100, var(--pri-100));
  color: var(--pri);
  font-size: 12px;
  line-height: 1;
  font-weight: var(--font-weight-bold);
  font-variant-numeric: tabular-nums;
}
.bpl-tree__mod-copy {
  min-width: 0;
  flex: 1;
}
.bpl-tree__mod-copy .bpl-submods__lb {
  display: block;
  color: inherit;
  font-size: 13px;
  line-height: 18px;
  font-weight: var(--font-weight-semibold);
}
.bpl-tree__mod-copy > small {
  display: block;
  margin-top: 1px;
  overflow: hidden;
  color: var(--t3);
  font-size: 12px;
  line-height: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bpl-tree__caret--tail {
  margin-left: 1px;
}
.bpl-tree__leaves {
  margin: 2px 0 8px 22px;
}
.bpl-tree__leaf-section {
  margin: 6px 8px 2px 17px;
  color: var(--t3);
  font-size: 12px;
  line-height: 18px;
  font-weight: var(--font-weight-semibold);
}
.bpl-tree .bpl-tree__leaf {
  width: 100%;
  min-height: 34px;
  padding: 6px 8px 6px 30px;
  appearance: none;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--t2);
  text-align: left;
  font: inherit;
  font-size: 13px;
  line-height: 20px;
}
.bpl-tree .bpl-tree__leaf:hover {
  background: color-mix(in srgb, var(--pri-bg) 72%, transparent);
}
.bpl-tree .bpl-tree__leaf.is-active {
  background: var(--pri-bg);
  color: var(--pri);
  font-weight: var(--font-weight-semibold);
}
.bpl-tree .bpl-tree__leaf:focus-visible,
.bpl-tree .bpl-tree__mod:focus-visible {
  outline: 2px solid var(--pri);
  outline-offset: 1px;
}
.bpl-tree .bpl-tree__leaf .bpl-menu__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 1450px) {
  .bpl-aside--workspace {
    width: 218px;
  }
}
"""

if workspace_css.strip() not in layout:
    closing = layout.rfind("</style>")
    if closing == -1:
        raise SystemExit("BasePortalLayout style closing tag not found")
    layout = layout[:closing] + workspace_css + "\n" + layout[closing:]

LAYOUT.write_text(layout, encoding="utf-8")

UNIT.write_text(r"""import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import {
  NAV_PLAN,
  findActiveInPlan,
  getVisibleNavPlan,
  searchNavPlan
} from '../src/config/navPlan.js'

const group = NAV_PLAN.find((item) => item.key === 'student-affairs')
assert.ok(group, 'student-affairs group must exist')

const expectedWorkspaces = [
  ['01', 'sa-workbench', '今日工作', '今天先处理什么'],
  ['02', 'sa-profile', '唯一学生360', '围绕学生看完整背景'],
  ['03', 'sa-risk', '风险与重点学生', '按学生聚合多来源风险'],
  ['04', 'sa-talks', '谈心家校与回访', '处置后形成闭环'],
  ['05', 'sa-leave', '请假与返校', '申请 → 返校 → 超期'],
  ['06', 'sa-aid', '困难与资助', '认定 → 资助 → 发放'],
  ['07', 'sa-discipline', '违纪处分与教育', '处分 → 教育 → 回访'],
  ['08', 'sa-dorm', '宿舍与公寓', '房源 → 入住 → 异常'],
  ['09', 'sa-activities', '活动与成长', '活动成果沉淀成长事实'],
  ['10', 'sa-orientation', '数字迎新', '新生 → 报到 → 归档'],
  ['11', 'sa-mental', '心理专项', '按角色显示敏感工作区'],
  ['12', 'sa-archive-stats', '统计与档案', '领导聚合与正式归档']
]

const externalRoutes = new Set([
  '/workbench',
  '/admin/approval/todos',
  '/admin/campus-service/classes',
  '/admin/campus-service/grants'
])
const sources = {
  '/admin/student-affairs': fs.readFileSync(new URL('../src/modules/studentAffairs/studentAffairs.routes.js', import.meta.url), 'utf8'),
  '/admin/orientation': fs.readFileSync(new URL('../src/modules/orientation/orientation.routes.js', import.meta.url), 'utf8'),
  '/admin/student': fs.readFileSync(new URL('../src/modules/student/student.routes.js', import.meta.url), 'utf8')
}

function routeExists(navPath) {
  const path = navPath.split('?')[0]
  if (externalRoutes.has(path)) return true
  for (const [prefix, source] of Object.entries(sources)) {
    if (path === prefix) return source.includes(`path: '${prefix}'`)
    if (!path.startsWith(`${prefix}/`)) continue
    const relative = path.slice(prefix.length + 1)
    if (source.includes(`path: '${relative}'`)) return true
    if (!relative && source.includes(`path: '${prefix}'`)) return true
  }
  return false
}

test('student affairs sidebar is exactly three waves and twelve ordered workspaces', () => {
  assert.equal(group.workspaceTitle, '学工业务工作区')
  assert.equal(group.children.length, 12)
  assert.deepEqual(
    group.children.map((item) => [item.ordinal, item.key, item.label, item.description]),
    expectedWorkspaces
  )
  assert.deepEqual(
    [...new Set(group.children.map((item) => item.sectionKey))],
    ['wave-1', 'wave-2', 'wave-3']
  )
  for (const wave of ['wave-1', 'wave-2', 'wave-3']) {
    assert.equal(group.children.filter((item) => item.sectionKey === wave).length, 4)
  }
})

test('every configured leaf points to a registered real route or an audited external route', () => {
  const broken = []
  for (const workspace of group.children) {
    for (const leaf of workspace.children) {
      if (!leaf.path || !routeExists(leaf.path)) {
        broken.push(`${workspace.key}/${leaf.label} -> ${leaf.path || '(missing)'}`)
      }
    }
  }
  assert.deepEqual(broken, [])
})

test('visible third-level menu is curated while low-frequency routes remain searchable deep links', () => {
  const visible = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'v6-workspace-test'
  }).find((item) => item.key === 'student-affairs')
  assert.ok(visible)
  assert.equal(visible.children.length, 12)
  const orientation = visible.children.find((item) => item.key === 'sa-orientation')
  assert.deepEqual(
    orientation.children.map((item) => item.label),
    ['迎新总览', '批次与规则', '新生底账', '报到资格', '报到办理', '异常闭环', '统计归档']
  )
  assert.equal(orientation.children.some((item) => item.label === '报到流程配置'), false)
  const search = searchNavPlan('报到流程配置', ['studentAffairs.orientation.view'])
  assert.equal(search.length, 1)
  assert.equal(search[0].path, '/admin/orientation/flow-config')
  assert.equal(search[0].trail, '学工中心 / 数字迎新 / 报到流程配置')
})

test('permissions project each workspace to a permitted landing page and search result', () => {
  const visible = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['studentAffairs.funding.view'],
    ctxKey: 'funding-only'
  }).find((item) => item.key === 'student-affairs')
  assert.ok(visible)
  assert.deepEqual(visible.children.map((item) => item.key), ['sa-aid'])
  assert.equal(visible.children[0].path, '/admin/student-affairs/funding')
  assert.equal(visible.children[0].children[0].label, '奖助评审')

  assert.equal(searchNavPlan('学生主档', ['studentAffairs.student.view'])[0].path, '/admin/student/list')
  assert.equal(searchNavPlan('学生主档', ['unrelated.permission']).length, 0)
})

test('deep routes highlight their visible workspace and semantic third-level stage', () => {
  const cases = [
    ['/admin/student/42', '/admin/student/42', 'sa-profile', '学生主档'],
    ['/admin/student-affairs/risk/R-18', '/admin/student-affairs/risk/R-18', 'sa-risk', '风险工作台'],
    ['/admin/student-affairs/leave/ledger', '/admin/student-affairs/leave/ledger?status=OVERDUE', 'sa-leave', '逾期未销假'],
    ['/admin/orientation/materials', '/admin/orientation/materials', 'sa-orientation', '报到办理'],
    ['/admin/orientation/archive', '/admin/orientation/archive', 'sa-orientation', '统计归档']
  ]
  for (const [path, fullPath, modKey, leafKey] of cases) {
    const active = findActiveInPlan(path, fullPath)
    assert.equal(active.groupKey, 'student-affairs', fullPath)
    assert.equal(active.modKey, modKey, fullPath)
    assert.equal(active.leafKey, leafKey, fullPath)
  }
})

test('visible labels and paths are unique inside each workspace and dorm allocation is no longer missing', () => {
  const visible = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'uniqueness'
  }).find((item) => item.key === 'student-affairs')
  for (const workspace of visible.children) {
    const labels = workspace.children.map((leaf) => leaf.label)
    const paths = workspace.children.map((leaf) => leaf.path)
    assert.equal(new Set(labels).size, labels.length, `${workspace.key} duplicate label`)
    assert.equal(new Set(paths).size, paths.length, `${workspace.key} duplicate path`)
  }
  const dorm = visible.children.find((item) => item.key === 'sa-dorm')
  assert.ok(dorm.children.some((item) => item.path === '/admin/student-affairs/dorm/allocation'))
})
""", encoding="utf-8")

E2E.write_text(r"""import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const DASHBOARD = '/admin/student-affairs/dashboard'
const expectedWorkspaces = [
  ['sa-workbench', '01'],
  ['sa-profile', '02'],
  ['sa-risk', '03'],
  ['sa-talks', '04'],
  ['sa-leave', '05'],
  ['sa-aid', '06'],
  ['sa-discipline', '07'],
  ['sa-dorm', '08'],
  ['sa-activities', '09'],
  ['sa-orientation', '10'],
  ['sa-mental', '11'],
  ['sa-archive-stats', '12']
]

async function openDashboard(page) {
  await page.setViewportSize({ width: 1366, height: 768 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}${DASHBOARD}`)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
    }
  }
}

async function ensureWorkspaceOpen(page, key) {
  const button = page.locator(`[data-workspace="${key}"]`)
  await expect(button).toBeVisible()
  if ((await button.getAttribute('aria-expanded')) !== 'true') await button.click()
  await expect(button).toHaveAttribute('aria-expanded', 'true')
  return button
}

async function expectDestination(page, navPath) {
  const expected = new URL(navPath, config.staffBaseUrl)
  await expect.poll(() => new URL(page.url()).pathname).toBe(expected.pathname)
  for (const [key, value] of expected.searchParams.entries()) {
    await expect.poll(() => new URL(page.url()).searchParams.get(key)).toBe(value)
  }
  expect(new URL(page.url()).pathname).not.toBe('/security/403')
  await expect(page.locator('.bpl-main')).not.toBeEmpty()
}

async function returnToDashboard(page) {
  for (let step = 0; step < 4 && new URL(page.url()).pathname !== DASHBOARD; step++) {
    await page.goBack()
  }
  await expect.poll(() => new URL(page.url()).pathname).toBe(DASHBOARD)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
}

test('V6 student-affairs sidebar renders three waves and twelve workspaces at 1366', async ({ page }, testInfo) => {
  await openDashboard(page)
  await expect(page.locator('.bpl-tree__workspace-head strong')).toHaveText('学工业务工作区')
  await expect(page.locator('.bpl-tree__section')).toHaveCount(3)
  await expect(page.locator('.bpl-tree__section').nth(0)).toContainText('第一波 · 高频主线')
  await expect(page.locator('.bpl-tree__section').nth(1)).toContainText('第二波 · 业务闭环')
  await expect(page.locator('.bpl-tree__section').nth(2)).toContainText('第三波 · 生命周期 / 专项')
  await expect(page.locator('[data-workspace]')).toHaveCount(12)

  for (const [key, ordinal] of expectedWorkspaces) {
    const workspace = page.locator(`[data-workspace="${key}"]`)
    await expect(workspace).toBeVisible()
    await expect(workspace.locator('.bpl-tree__num')).toHaveText(ordinal)
  }

  const geometry = await page.evaluate(() => {
    const aside = document.querySelector('.bpl-aside--workspace')
    const main = document.querySelector('.bpl-main')
    return {
      asideWidth: aside.getBoundingClientRect().width,
      asideOverflowX: aside.scrollWidth - aside.clientWidth,
      mainWidth: main.getBoundingClientRect().width,
      bodyOverflowX: document.documentElement.scrollWidth - innerWidth
    }
  })
  expect(geometry.asideWidth).toBeGreaterThanOrEqual(210)
  expect(geometry.asideOverflowX).toBeLessThanOrEqual(1)
  expect(geometry.mainWidth).toBeGreaterThan(700)
  expect(geometry.bodyOverflowX).toBeLessThanOrEqual(1)

  const file = testInfo.outputPath('v6-student-affairs-sidebar-12-workspaces-1366.png')
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach('v6-student-affairs-sidebar-12-workspaces-1366', { path: file, contentType: 'image/png' })
})

for (const [key, ordinal] of expectedWorkspaces) {
  test(`V6 workspace ${ordinal} exposes real-clickable third-level routes`, async ({ page }, testInfo) => {
    test.setTimeout(180_000)
    await openDashboard(page)
    const workspace = await ensureWorkspaceOpen(page, key)
    const section = workspace.locator('xpath=following-sibling::*[1][contains(@class,"bpl-tree__leaves")]')
    await expect(section).toBeVisible()
    const leaves = await section.locator('button[data-leaf]').evaluateAll((buttons) => buttons.map((button) => ({
      label: button.dataset.leaf,
      path: button.dataset.navPath
    })))
    expect(leaves.length, `${key} must expose at least one visible third-level route`).toBeGreaterThan(0)

    const expanded = testInfo.outputPath(`v6-workspace-${ordinal}-expanded.png`)
    await page.screenshot({ path: expanded, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach(`v6-workspace-${ordinal}-expanded`, { path: expanded, contentType: 'image/png' })

    const visited = []
    for (let index = 0; index < leaves.length; index++) {
      const leaf = leaves[index]
      expect(leaf.path).toMatch(/^\//)
      await ensureWorkspaceOpen(page, key)
      const button = page.locator(`[data-workspace="${key}"] + .bpl-tree__leaves button[data-leaf="${leaf.label}"]`)
      await expect(button, `${key}/${leaf.label} must be visible and enabled`).toBeVisible()
      await expect(button).not.toHaveAttribute('aria-disabled', 'true')
      await button.click()
      await expectDestination(page, leaf.path)
      visited.push({ ...leaf, actual: page.url() })

      const destination = testInfo.outputPath(`v6-workspace-${ordinal}-leaf-${String(index + 1).padStart(2, '0')}.png`)
      await page.screenshot({ path: destination, fullPage: false, animations: 'disabled', caret: 'hide' })
      await testInfo.attach(`v6-workspace-${ordinal}-${leaf.label}`, { path: destination, contentType: 'image/png' })
      await returnToDashboard(page)
    }

    await testInfo.attach(`v6-workspace-${ordinal}-visited-routes`, {
      body: JSON.stringify(visited, null, 2),
      contentType: 'application/json'
    })
  })
}

test('V6 search-only deep links stay out of the sidebar but remain reachable through real function search', async ({ page }, testInfo) => {
  await openDashboard(page)
  const cases = [
    ['报到流程配置', '/admin/orientation/flow-config'],
    ['新生信息核验', '/admin/orientation/verify'],
    ['缴费与绿色通道', '/admin/orientation/payment'],
    ['迎新归档', '/admin/orientation/archive'],
    ['资助批次', '/admin/student-affairs/funding/batches'],
    ['困难认定异议', '/admin/student-affairs/aid/objections']
  ]
  const visited = []
  for (const [label, path] of cases) {
    await expect(page.locator(`button[data-leaf="${label}"]`)).toHaveCount(0)
    const input = page.locator('.bpl-cmdk--fn input')
    await input.fill(label)
    const result = page.locator('.bpl-cmdk--fn .bpl-cmdk__opt').filter({
      has: page.locator('.bpl-cmdk__opt-lb', { hasText: new RegExp(`^${label}$`) })
    }).first()
    await expect(result).toBeVisible()
    await result.click()
    await expectDestination(page, path)
    visited.push({ label, path, actual: page.url() })
    await returnToDashboard(page)
  }
  await testInfo.attach('v6-search-deep-links', {
    body: JSON.stringify(visited, null, 2),
    contentType: 'application/json'
  })
})
""", encoding="utf-8")

print("student-affairs V6 workspace sidebar patch applied")
