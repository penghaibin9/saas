<template>
  <div class="priority-layout" :aria-busy="loading">
    <div class="priority-main">
      <section class="priority-brief">
        <h2>今日工作摘要</h2>
        <div class="priority-brief-counts">
          <button type="button" @click="go('/admin/approval/todos')">
            <strong>{{ pending ?? '—' }}</strong
            ><span>待我审批</span>
          </button>
          <button
            v-if="can('studentAffairs.leave.view')"
            type="button"
            @click="go('/admin/student-affairs/leave')"
          >
            <strong>{{ metric('pendingLeave') }}</strong
            ><span>待审请假</span>
          </button>
          <button
            v-if="can('studentAffairs.risk.view')"
            type="button"
            @click="go('/admin/student-affairs/risk?status=OPEN')"
          >
            <strong>{{ risk('openStudentCount') }}</strong
            ><span>风险学生</span>
          </button>
        </div>
      </section>
      <section class="priority-panel priority-main-panel">
        <header class="priority-heading">
          <h2>优先处理</h2>
          <div class="priority-filters">
            <select v-model="sort" aria-label="事项排序">
              <option value="priority">优先级</option>
              <option value="count">数量优先</option>
            </select>
            <select v-model="filter" aria-label="筛选业务">
              <option value="all">全部业务</option>
              <option value="pending">有待处理</option>
              <option v-for="row in rows" :key="row.key" :value="row.key">{{ row.label }}</option>
            </select>
          </div>
        </header>
        <p v-if="error" class="priority-empty" role="alert">
          {{ error }} <button type="button" @click="load">重试</button>
        </p>
        <p v-else-if="loading" class="priority-empty" role="status">正在读取业务事项…</p>
        <p v-else-if="!visibleRows.length" class="priority-empty">
          {{ filter === 'pending' ? '暂无待处理事项' : '当前没有可用业务入口' }}
        </p>
        <ul v-else class="priority-rows">
          <li
            v-for="row in visibleRows"
            :key="row.key"
            :class="{ urgent: row.value > 0 && row.urgent }"
          >
            <div class="priority-copy">
              <div>
                <h3>{{ row.label }}</h3>
                <span v-if="row.value > 0" class="priority-status">{{ row.status }}</span>
              </div>
              <p>{{ row.hint }}</p>
            </div>
            <div class="priority-count">
              <strong>{{ row.value ?? '—' }}</strong>
            </div>
            <button type="button" class="priority-action" @click="go(row.path)">
              {{ row.action }}
            </button>
          </li>
        </ul>
      </section>
    </div>
    <aside class="priority-side">
      <section class="priority-panel">
        <header class="priority-heading"><h2>当前工作范围</h2></header>
        <dl class="priority-scope-list">
          <div>
            <dt>管理班级</dt>
            <dd>{{ metric('classTotal') }} 个班级</dd>
          </div>
          <div>
            <dt>范围学生</dt>
            <dd>{{ metric('studentTotal') }} 位学生</dd>
          </div>
          <div>
            <dt>当前身份</dt>
            <dd>{{ identityLabel }}</dd>
          </div>
          <div>
            <dt>数据范围</dt>
            <dd>{{ scopeLabel }}</dd>
          </div>
        </dl>
        <div
          v-if="
            can('studentAffairs.risk.view') &&
            riskLevel &&
            dashboard.riskSummary?.openStudentCount > 0
          "
          class="priority-risk-foot"
        >
          <span>危急 {{ risk('criticalCount') }} 人 · 高风险 {{ risk('highCount') }} 人</span
          ><button type="button" @click="go('/admin/student-affairs/risk?status=OPEN')">
            查看风险
          </button>
        </div>
      </section>
      <section v-if="crossLinks.length" class="priority-panel">
        <header class="priority-heading">
          <h2>常用入口</h2>
          <button
            type="button"
            class="priority-text"
            @click="go('/admin/help?topic=doc-workbench')"
          >
            帮助
          </button>
        </header>
        <div class="priority-links">
          <button v-for="link in crossLinks" :key="link.path" type="button" @click="go(link.path)">
            <span>{{ link.label }}</span
            ><small>进入</small>
          </button>
        </div>
      </section>
    </aside>
  </div>
</template>
<script>
import { matchPermission } from '@/config/navPlan'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const BUSINESSES = [
  {
    key: 'riskStudents',
    label: '风险与重点学生',
    permission: 'studentAffairs.risk.view',
    icon: 'risk',
    status: '需关注',
    hint: '跟进未关闭风险与重点学生',
    action: '进入风险',
    urgent: true
  },
  {
    key: 'overdueLeave',
    label: '逾期返校核查',
    permission: 'studentAffairs.leave.view',
    icon: 'records',
    status: '已逾期',
    hint: '核实返校、销假与联系情况',
    action: '核查返校',
    urgent: true
  },
  {
    key: 'pendingLeave',
    label: '请假审批',
    permission: 'studentAffairs.leave.view',
    icon: 'workbench',
    status: '待审批',
    hint: '查看申请与审批进度',
    action: '进入审批'
  },
  {
    key: 'pendingAid',
    label: '困难认定',
    permission: 'studentAffairs.aid.view',
    icon: 'students',
    status: '待审核',
    hint: '审核认定材料与申请',
    action: '审核认定'
  },
  {
    key: 'pendingFunding',
    label: '奖助评审',
    permission: 'studentAffairs.funding.view',
    icon: 'kpi',
    status: '待评审',
    hint: '处理奖助申请与评审',
    action: '进入评审'
  },
  {
    key: 'pendingDiscipline',
    label: '处分审批与教育',
    permission: 'studentAffairs.discipline.view',
    icon: 'reports',
    status: '待处理',
    hint: '处理处分审批与后续教育',
    action: '处理处分'
  }
]
export default {
  name: 'StudentAffairsPriorityPanel',
  props: { ctx: { type: Object, required: true }, pending: { type: Number, default: null } },
  data: () => ({ loading: false, error: '', dashboard: {}, sort: 'priority', filter: 'all' }),
  computed: {
    identityLabel() {
      return this.ctx.currentRole?.roleName || '当前身份'
    },
    scopeLabel() {
      return this.dashboard.scopeLabel || this.ctx.dataScope?.scopeName || '按授权范围'
    },
    rows() {
      const approval = this.can('approval.todo.view')
        ? [
            {
              key: 'approval',
              label: '我的待办',
              status: '待审批',
              hint: '处理分配给我的审批事项',
              action: '查看待办',
              index: -1,
              value: this.pending,
              unit: '件',
              path: '/admin/approval/todos'
            }
          ]
        : []
      return [
        ...approval,
        ...BUSINESSES.filter((item) => this.can(item.permission))
          .map((item, index) => {
            const card = (this.dashboard.summaryCards || []).find((card) => card.key === item.key)
            return {
              ...item,
              index,
              value: typeof card?.value === 'number' ? card.value : null,
              unit: card?.unit || '件',
              path: card?.drillPath || ''
            }
          })
          .filter((item) => item.path)
      ]
    },
    visibleRows() {
      return this.rows
        .filter(
          (row) =>
            this.filter === 'all' ||
            (this.filter === 'pending' ? row.value > 0 : row.key === this.filter)
        )
        .sort((a, b) => {
          if (this.sort === 'count') return (b.value ?? -1) - (a.value ?? -1) || a.index - b.index
          const rank = (row) => (row.value > 0 ? (row.urgent ? row.index : 2) : 3)
          return rank(a) - rank(b) || a.index - b.index
        })
    },
    riskLevel() {
      if (this.loading || this.error) return ''
      return (
        {
          CRITICAL: '最高危急',
          HIGH: '最高高风险',
          MEDIUM: '最高中风险',
          LOW: '最高低风险',
          NONE: '暂无未关闭风险'
        }[this.dashboard.riskSummary?.topRiskLevel] || ''
      )
    },
    crossLinks() {
      return [
        {
          label: '请假审批',
          path: '/admin/student-affairs/leave',
          permission: 'studentAffairs.leave.view'
        },
        {
          label: '学生列表',
          path: '/admin/student/list',
          permission: 'studentAffairs.student.view'
        },
        {
          label: '住宿管理',
          path: '/admin/student-affairs/dorm',
          permission: 'studentAffairs.dorm.view'
        },
        {
          label: '谈心谈话',
          path: '/admin/student-affairs/talk',
          permission: 'studentAffairs.talk.view'
        },
        { label: '数字迎新', path: '/admin/orientation', permission: 'orientation.dashboard.view' },
        { label: '学工统计', path: '/admin/student-affairs/stats', permission: 'studentAffairs.stats.view' },
        { label: '学工归档', path: '/admin/student-affairs/archive', permission: 'studentAffairs.archive.view' }
      ].filter((link) => this.can(link.permission))
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    can(permission) {
      return matchPermission(this.ctx.permissionPatterns || [], permission)
    },
    metric(key) {
      if (this.loading || this.error) return '—'
      const value = (this.dashboard.summaryCards || []).find((item) => item.key === key)?.value
      return typeof value === 'number' ? value.toLocaleString('zh-CN') : '—'
    },
    risk(key) {
      const value = this.dashboard.riskSummary?.[key]
      return !this.loading && !this.error && typeof value === 'number' ? value : '—'
    },
    go(path) {
      if (path) this.$router.push(path)
    },
    async load() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      try {
        const result = await studentAffairsApi.getDashboard()
        if (result.code !== 0 || !result.data) throw new Error(result.message || '学工事项暂不可用')
        this.dashboard = result.data
      } catch (error) {
        this.error = error.message || '学工事项暂不可用'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>
<style scoped>
.priority-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 18px;
  color: var(--t1, #243650);
  font-size: 14px;
  align-items: start;
}
.priority-main {
  min-width: 0;
}
.priority-panel {
  padding: 18px;
  border: 1px solid var(--line, #dde4ee);
  border-radius: 8px;
  background: var(--surface, #fff);
  min-width: 0;
}
.priority-main-panel {
  padding: 0;
  overflow: hidden;
}
.priority-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 0 12px;
}
.priority-main-panel > .priority-heading {
  padding: 16px 20px;
  margin: 0;
  border-bottom: 1px solid var(--line, #dde4ee);
}
.priority-layout h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
}
.priority-layout h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.priority-layout button,
.priority-layout select {
  font: inherit;
  border: 1px solid var(--line, #dde4ee);
  border-radius: 5px;
  background: var(--surface-2, #f6f8fb);
  color: var(--pri, #285dc0);
  cursor: pointer;
  padding: 7px 10px;
}
.priority-layout button:hover {
  background: var(--pri-50, #edf3fc);
}
.priority-layout button:focus-visible,
.priority-layout select:focus-visible {
  outline: 2px solid var(--pri, #285dc0);
  outline-offset: 3px;
}
.priority-brief {
  padding: 16px 20px;
  margin-bottom: 16px;
  background: var(--pri-50, #edf3fc);
  border: 1px solid var(--line, #dde4ee);
  border-radius: 8px;
}
.priority-brief h2 {
  font-size: 13px;
  font-weight: 500;
  color: var(--t3, #65758b);
}
.priority-brief-counts {
  display: flex;
  gap: 30px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.priority-brief-counts button {
  display: flex;
  align-items: baseline;
  gap: 10px;
  border: 0;
  background: transparent;
  padding: 0;
}
.priority-brief-counts strong {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.3;
}
.priority-brief-counts span {
  font-size: 12px;
  color: var(--t3, #65758b);
}
.priority-filters {
  display: flex;
  gap: 8px;
}
.priority-filters select {
  font-size: 12px;
  max-width: 125px;
  color: var(--t3, #65758b);
  padding: 6px;
}
.priority-rows {
  padding: 0;
  margin: 0;
  list-style: none;
}
.priority-rows li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 54px 90px;
  align-items: center;
  gap: 20px;
  border-bottom: 1px solid var(--line, #dde4ee);
  padding: 16px 20px;
  min-height: 82px;
  box-sizing: border-box;
}
.priority-rows li:last-child {
  border-bottom: 0;
}
.priority-rows li:hover {
  background: var(--surface-2, #f6f8fb);
}
.priority-copy > div {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
}
.priority-copy p {
  margin: 5px 0 0;
  color: var(--t3, #65758b);
  font-size: 12px;
  line-height: 1.5;
}
.priority-status {
  font-size: 11px;
  color: var(--pri, #285dc0);
  white-space: nowrap;
}
.urgent .priority-status {
  color: var(--danger, #c9444c);
}
.priority-count {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.priority-count strong {
  font-size: 24px;
  line-height: 1.2;
  font-weight: 500;
  color: var(--pri, #285dc0);
}
.priority-layout .priority-action {
  font-size: 12px;
  padding: 8px;
  white-space: nowrap;
  background: var(--pri-50, #edf3fc);
}
.priority-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.priority-scope-list {
  margin: 0;
  font-size: 12px;
}
.priority-scope-list > div {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 11px 0;
  border-bottom: 1px solid var(--line, #dde4ee);
}
.priority-scope-list > div:last-child {
  border-bottom: 0;
}
.priority-scope-list dt {
  color: var(--t3, #65758b);
  flex: none;
}
.priority-scope-list dd {
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
}
.priority-risk-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--t3, #65758b);
}
.priority-layout .priority-risk-foot button,
.priority-layout .priority-text {
  background: transparent;
  border: 0;
  padding: 0;
  font-size: 12px;
}
.priority-links {
  display: flex;
  flex-direction: column;
}
.priority-layout .priority-links button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  text-align: left;
  font-size: 13px;
  padding: 14px 0;
  background: transparent;
  border: 0;
  border-radius: 0;
  border-bottom: 1px solid var(--line, #dde4ee);
}
.priority-links button:last-child {
  border-bottom: 0;
}
.priority-links small {
  font-size: 12px;
  color: var(--t3, #65758b);
}
.priority-empty {
  padding: 30px 15px;
  color: var(--t3, #65758b);
  text-align: center;
}
@media (max-width: 1000px) {
  .priority-layout {
    grid-template-columns: minmax(0, 1fr) 240px;
    gap: 12px;
  }
  .priority-rows li {
    padding: 14px;
    gap: 10px;
    grid-template-columns: minmax(0, 1fr) 35px 80px;
  }
  .priority-panel {
    padding: 14px;
  }
  .priority-main-panel {
    padding: 0;
  }
}
@media (max-width: 800px) {
  .priority-layout {
    grid-template-columns: 1fr;
  }
  .priority-side {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 550px) {
  .priority-side {
    grid-template-columns: 1fr;
  }
  .priority-rows li {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .priority-action {
    grid-column: 1/-1;
    justify-self: end;
  }
  .priority-brief-counts {
    gap: 18px;
  }
  .priority-brief-counts strong {
    font-size: 24px;
  }
}
</style>
