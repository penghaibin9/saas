from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        if text.count(old) != 1:
            raise SystemExit(f"{label}: expected one old block, got {text.count(old)}")
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise SystemExit(f"{label}: audited block not found")


layout_path = Path('frontend/src/layouts/BasePortalLayout.vue')
layout = layout_path.read_text(encoding='utf-8')
layout = replace_once(
    layout,
    "import { getVisibleNavPlan, findActiveInPlan, searchNavPlan, navRefMatches, navRefExactMatch } from '@/config/navPlan'\n",
    "import { getVisibleNavPlan, findActiveInPlan, searchNavPlan, navRefMatches, navRefExactMatch } from '@/config/navPlan'\n"
    "import { projectStudentAffairsWorkspaceDeepLinks } from '@/config/studentAffairsWorkspaceDeepLinks'\n",
    'BasePortal import'
)
layout = replace_once(
    layout,
    ":class=\"{ 'is-active': isLeafActive(m, leaf), 'is-disabled': leaf.disabled }\"\n                    :data-leaf=\"leaf.label\"\n                    :data-nav-path=\"leaf.path || ''\"",
    ":class=\"{\n                      'is-active': isLeafActive(m, leaf),\n                      'is-disabled': leaf.disabled,\n                      'is-contextual': leaf.contextualDeepLink\n                    }\"\n                    :data-leaf=\"leaf.label\"\n                    :data-nav-path=\"leaf.path || ''\"\n                    :data-deep-link=\"leaf.contextualDeepLink ? 'true' : undefined\"\n                    :data-entry-type=\"leaf.entryType || ''\"",
    'BasePortal leaf metadata'
)
old_plan_group = """    planGroup() {
      const gk = this.railActiveKey
      // 日常视角按当前身份权限集投影；planner(校管/平台)看完整能力目录。ctxKey 保证切身份/改权后缓存失效。
      return getVisibleNavPlan({
        includePlanned: this.isPlannerView,
        permissionPatterns: (this.ctx && this.ctx.permissionPatterns) || null,
        ctxKey: (this.ctx && this.ctx.ctxKey) || ''
      }).find((g) => g.key === gk) || null
    },"""
new_plan_group = """    planGroup() {
      const gk = this.railActiveKey
      const permissionPatterns = (this.ctx && this.ctx.permissionPatterns) || null
      // 日常视角按当前身份权限集投影；planner(校管/平台)看完整能力目录。ctxKey 保证切身份/改权后缓存失效。
      const group = getVisibleNavPlan({
        includePlanned: this.isPlannerView,
        permissionPatterns,
        ctxKey: (this.ctx && this.ctx.ctxKey) || ''
      }).find((g) => g.key === gk) || null
      // 学工 V6：高频三级保持原排序；D() 真实低频页只补进当前展开工作区，H() 对象详情仍不铺菜单。
      return projectStudentAffairsWorkspaceDeepLinks(group, permissionPatterns)
    },"""
layout = replace_once(layout, old_plan_group, new_plan_group, 'BasePortal planGroup')
old_aside = """.bpl-aside--subnav {
  width: 196px;
  background: var(--bg-sidebar);
  padding: 16px 12px;
}"""
new_aside = """.bpl-aside--subnav {
  width: 196px;
  background: var(--bg-sidebar);
  padding: 16px 12px;
}
/* 学工 V6 只在带 workspaceTitle 的投影中收紧一级轨并给三级标签足够宽度。 */
.bpl-aside--workspace {
  width: 214px;
  padding: 12px 9px 14px;
}
.base-portal-layout:has(.bpl-aside--workspace) .bpl-rail {
  width: 68px;
}
.base-portal-layout:has(.bpl-aside--workspace) .bpl-rail__item {
  width: 56px;
  padding-block: 8px 6px;
  border-radius: 11px;
}"""
layout = replace_once(layout, old_aside, new_aside, 'BasePortal workspace dimensions')
old_active = """.bpl-tree .bpl-tree__leaf.is-active::before {
  background: var(--pri);
}"""
new_active = """.bpl-tree .bpl-tree__leaf.is-active::before {
  background: var(--pri);
}
/* D() 低频页面在当前工作区中可见，但用轻量类型标识与主工作台区分。 */
.bpl-tree .bpl-tree__leaf.is-contextual {
  color: var(--t2);
  background: color-mix(in srgb, var(--bg-card) 72%, var(--pri-bg));
}
.bpl-tree .bpl-tree__leaf.is-contextual:hover,
.bpl-tree .bpl-tree__leaf.is-contextual.is-active {
  color: var(--pri);
  background: var(--pri-bg);
}
.bpl-tree .bpl-tree__leaf .bpl-planbadge--implemented {
  color: var(--t3);
  background: var(--bg-section);
  border: 1px solid var(--border-light);
}
.bpl-tree .bpl-tree__leaf.is-contextual.is-active .bpl-planbadge--implemented {
  color: var(--pri);
  border-color: var(--pri-100);
  background: var(--bg-card);
}"""
layout = replace_once(layout, old_active, new_active, 'BasePortal contextual styles')
layout_path.write_text(layout, encoding='utf-8')

nav_path = Path('frontend/src/config/navPlan.js')
nav = nav_path.read_text(encoding='utf-8')
old_risk = """      I('风险工作台', '/admin/student-affairs/risk', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        sectionKey: 'risk', sectionLabel: '风险处置'
      }),
      I('重点学生跟进', '/admin/student-affairs/talk/key-follow', 'studentAffairs.talk.view', 'TASK_QUEUE', {"""
new_risk = """      I('风险工作台', '/admin/student-affairs/risk', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        sectionKey: 'risk', sectionLabel: '风险处置'
      }),
      D('高危 / 危急', '/admin/student-affairs/risk?priority=HIGH_CRITICAL', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        activeLabel: '风险工作台', sectionKey: 'risk', sectionLabel: '风险快捷队列'
      }),
      D('超时待跟进', '/admin/student-affairs/risk?overdueOnly=true', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        activeLabel: '风险工作台', sectionKey: 'risk', sectionLabel: '风险快捷队列'
      }),
      D('待分派风险', '/admin/student-affairs/risk?unassignedOnly=true', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        activeLabel: '风险工作台', sectionKey: 'risk', sectionLabel: '风险快捷队列'
      }),
      D('我负责的风险', '/admin/student-affairs/risk?ownerId=me', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        activeLabel: '风险工作台', sectionKey: 'risk', sectionLabel: '风险快捷队列'
      }),
      D('持续跟进风险', '/admin/student-affairs/risk?status=FOLLOWING', 'studentAffairs.risk.view', 'TASK_QUEUE', {
        activeLabel: '风险工作台', sectionKey: 'risk', sectionLabel: '风险快捷队列'
      }),
      I('重点学生跟进', '/admin/student-affairs/talk/key-follow', 'studentAffairs.talk.view', 'TASK_QUEUE', {"""
nav = replace_once(nav, old_risk, new_risk, 'navPlan risk deep links')
nav_path.write_text(nav, encoding='utf-8')

risk_path = Path('frontend/src/modules/studentAffairs/views/StudentAffairsRiskListView.vue')
risk = risk_path.read_text(encoding='utf-8')
old_apply = """    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      this.filters.studentId = this.studentFilter.studentId || ''
      this.filters.source = q.source ? String(q.source) : this.filters.source
      this.filters.riskLevel = q.riskLevel ? String(q.riskLevel) : this.filters.riskLevel
      if (q.status != null && q.status !== '') {
        const resolved = resolveTodoStatus('risk', q.status)
        // PENDING/OPEN/DONE/OVERDUE 等公共语义：下拉用 activeKey；后端 OPEN/PENDING 已识别
        this.filters.status = resolved.activeKey === 'CLOSED' ? 'CLOSED'
          : (resolved.activeKey === 'ESCALATED' ? 'ESCALATED'
            : (['PENDING', 'OPEN'].includes(resolved.activeKey) ? resolved.activeKey
              : (resolved.matchStatuses && resolved.matchStatuses.length === 1 ? resolved.matchStatuses[0] : String(q.status))))
      }
    },"""
new_apply = """    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      this.filters.studentId = this.studentFilter.studentId || ''
      this.filters.source = q.source ? String(q.source) : this.filters.source
      this.filters.riskLevel = q.riskLevel ? String(q.riskLevel) : this.filters.riskLevel
      // V6 侧栏快捷队列只投影既有服务端过滤参数；不在浏览器本地筛选或扩大 allowedActions。
      this.activeQueue = String(q.priority || '') === 'HIGH_CRITICAL' ? 'HIGH'
        : String(q.overdueOnly || '').toLowerCase() === 'true' ? 'OVERDUE'
          : String(q.unassignedOnly || '').toLowerCase() === 'true' ? 'UNASSIGNED'
            : String(q.ownerId || '') === 'me' ? 'MINE'
              : String(q.status || '').toUpperCase() === 'FOLLOWING' ? 'FOLLOWING'
                : 'ALL'
      if (q.status != null && q.status !== '') {
        const resolved = resolveTodoStatus('risk', q.status)
        // PENDING/OPEN/DONE/OVERDUE 等公共语义：下拉用 activeKey；后端 OPEN/PENDING 已识别
        this.filters.status = resolved.activeKey === 'CLOSED' ? 'CLOSED'
          : (resolved.activeKey === 'ESCALATED' ? 'ESCALATED'
            : (['PENDING', 'OPEN'].includes(resolved.activeKey) ? resolved.activeKey
              : (resolved.matchStatuses && resolved.matchStatuses.length === 1 ? resolved.matchStatuses[0] : String(q.status))))
      }
    },"""
risk = replace_once(risk, old_apply, new_apply, 'risk route queue intent')
risk_path.write_text(risk, encoding='utf-8')
