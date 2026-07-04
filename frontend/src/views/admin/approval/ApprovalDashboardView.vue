<template>
  <ModulePageShell
    title="待办看板"
    subtitle="待办、超时预警与业务分布实时联动审批队列"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <ModuleHero
        title="审批工作台"
        :subtitle="'覆盖 ' + summary.byBizType.length + ' 类业务 · 统计口径：当前数据范围内在办待办'"
        :stats="heroStats"
        :flow="heroFlow"
      />

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">按业务类型分组</span>
          <span class="mp-note">点击卡片进入对应待办列表</span>
        </div>
        <div class="mp-card__body">
          <EmptyState
            v-if="!summary.total"
            title="当前没有在办待办"
            description="新的审批申请提交后将实时进入待办队列"
          />
          <div v-else class="mp-grid-cards">
            <button
              v-for="g in summary.byBizType"
              :key="g.bizType"
              type="button"
              class="ad-group"
              :class="{ 'is-empty': !g.count }"
              @click="goTodos(g.bizType)"
            >
              <div class="ad-group__top">
                <span class="ad-group__label">{{ g.label }}</span>
                <StatusTag v-if="g.overdue" type="danger" :label="'超时 ' + g.overdue" />
              </div>
              <div class="ad-group__count">{{ g.count }}<span class="ad-group__unit">条待办</span></div>
              <div class="ad-group__sub">
                {{ g.count ? '最早提交：' + g.earliest : '暂无待办，保持清零' }}
              </div>
            </button>
          </div>
        </div>
      </section>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">超时预警</span>
            <StatusTag v-if="summary.overdue" type="danger" :label="'待处置 ' + summary.overdue + ' 条'" />
          </div>
          <div class="mp-card__body">
            <p v-if="!summary.overdueList.length" class="mp-note">当前没有超时任务，办理时效良好</p>
            <ul v-else class="ad-alerts">
              <li v-for="t in summary.overdueList" :key="t.taskId" class="ad-alert">
                <div>
                  <div class="mp-cell-main">{{ t.title }}</div>
                  <div class="mp-cell-sub">
                    {{ t.bizTypeLabel }} · {{ t.applicantName }}（{{ t.className }}）· 截止 {{ t.deadline }}
                  </div>
                </div>
                <button class="mp-link" @click="goDetail(t.taskId)">去办理</button>
              </li>
            </ul>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">快捷入口</span></div>
          <div class="mp-card__body ad-quick">
            <button
              v-for="q in quickLinks"
              :key="q.path"
              type="button"
              class="ad-quick__item"
              @click="$router.push(q.path)"
            >
              <span class="ad-quick__icon">{{ q.icon }}</span>
              <span class="ad-quick__text">
                <span class="mp-cell-main">{{ q.label }}</span>
                <span class="mp-cell-sub">{{ q.desc }}</span>
              </span>
              <span class="ad-quick__arrow">›</span>
            </button>
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 待办看板（/admin/approval）：概览统计 + 业务类型分组卡 + 超时预警 + 快捷入口。
 * 统计由 approvalApi.getTodoSummary() 按当前角色数据范围实时计算，审批动作后数字联动。
 */
import {
  ModulePageShell,
  ModuleHero,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { approvalApi } from '@/modules/approval/api/approval.api'

export default {
  name: 'ApprovalDashboardView',
  components: { ModulePageShell, ModuleHero, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      summary: null,
      quickLinks: [
        { icon: '☰', label: '我的待办', desc: '筛选、批量办理与导出', path: '/admin/approval/todos' },
        { icon: '✓', label: '已办 · 抄送', desc: '回看经手记录与抄送件', path: '/admin/approval/done' },
        { icon: '↩', label: '退回记录', desc: '跟踪退回原因与整改进度', path: '/admin/approval/returned' },
        { icon: '⚙', label: '审批模板', desc: '节点流转与时限配置', path: '/admin/approval/templates' }
      ]
    }
  },
  computed: {
    heroStats() {
      const s = this.summary
      return [
        { label: '待办总数', value: String(s.total), trend: '', trendQuality: 'neutral' },
        {
          label: '今日新增',
          value: String(s.todayNew),
          trend: s.todayNew ? '较昨日持平' : '',
          trendQuality: 'neutral'
        },
        {
          label: '临期任务',
          value: String(s.nearDeadline),
          trend: s.nearDeadline ? '需 48 小时内办结' : '',
          trendQuality: s.nearDeadline ? 'bad' : 'neutral'
        },
        {
          label: '已超时',
          value: String(s.overdue),
          trend: s.overdue ? '已提醒经办人' : '保持清零',
          trendQuality: s.overdue ? 'bad' : 'good'
        }
      ]
    },
    heroFlow() {
      const max = Math.max(...this.summary.byBizType.map((g) => g.count), 0)
      return this.summary.byBizType.map((g) => ({
        label: g.label,
        value: g.count,
        active: max > 0 && g.count === max
      }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await approvalApi.getTodoSummary()
      if (res.code === 0) this.summary = res.data
      else this.error = res.message
      this.loading = false
    },
    goTodos(bizType) {
      this.$router.push({ path: '/admin/approval/todos', query: bizType ? { bizType } : {} })
    },
    goDetail(taskId) {
      this.$router.push('/admin/approval/todos/' + taskId)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.ad-group {
  text-align: left;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  padding: var(--space-4);
  cursor: pointer;
  box-shadow: var(--shadow-card);
  transition:
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}
.ad-group:hover {
  border-color: var(--primary-500);
  box-shadow: var(--shadow-card-hover);
}
.ad-group.is-empty {
  background: var(--bg-section);
}
.ad-group__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.ad-group__label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
}
.ad-group__count {
  margin-top: var(--space-2);
  font-size: var(--font-size-metric-sm);
  font-weight: var(--font-weight-bold);
  font-variant-numeric: var(--font-numeric);
  color: var(--text-primary);
}
.ad-group__unit {
  margin-left: var(--space-1);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-normal);
  color: var(--text-tertiary);
}
.ad-group__sub {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ad-alerts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.ad-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px dashed var(--border-light);
}
.ad-alert:last-child {
  border-bottom: none;
}
.ad-quick {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.ad-quick__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--motion-fast) var(--ease-standard);
}
.ad-quick__item:hover {
  border-color: var(--primary-500);
  background: var(--primary-25);
}
.ad-quick__icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-600);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ad-quick__text {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.ad-quick__arrow {
  color: var(--text-disabled);
  font-size: var(--font-size-lg);
}
</style>
