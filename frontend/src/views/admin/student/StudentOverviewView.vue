<template>
  <ModulePageShell
    title="学生中心看板"
    subtitle="学生主档 · 学籍身份 · 风险跟进的统一入口"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生中心看板"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.platformDisplayName + ' · 学生中心'"
        :subtitle="'指标按「' + ctx.dataScope.scopeName + '」实时统计，不同角色可见指标不同'"
        :chips="heroChips"
        :stats="summary.stats"
        :flow="summary.flow"
      />

      <div class="mp-grid-cards">
        <button
          v-for="t in summary.todos"
          :key="t.key"
          type="button"
          class="ov-todo"
          :class="'is-' + t.tone"
          @click="$router.push(t.route)"
        >
          <span class="ov-todo__count">{{ t.count }}</span>
          <span class="ov-todo__label">{{ t.label }}</span>
          <span class="ov-todo__hint">{{ t.hint }}</span>
          <span class="ov-todo__go">去处理 ›</span>
        </button>
      </div>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">最近学籍异动</span>
            <button class="mp-link" @click="$router.push('/admin/student/status')">全部记录 ›</button>
          </div>
          <div class="mp-card__body">
            <EmptyState
              v-if="!summary.recentChanges.length"
              title="暂无学籍异动"
              description="当前数据范围内近期没有状态变更记录"
            />
            <ul v-else class="mp-timeline">
              <li v-for="r in summary.recentChanges" :key="r.id" class="mp-timeline__item">
                <div class="mp-timeline__title">
                  {{ r.studentName }}（{{ r.className }}）：{{ statusLabel(r.fromStatus) }} →
                  {{ statusLabel(r.toStatus) }}
                </div>
                <div class="mp-timeline__desc">{{ r.reason }}</div>
                <div class="mp-timeline__time">{{ r.operatedAt }} · {{ r.operator }}（{{ r.roleName }}）</div>
              </li>
            </ul>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">最近操作留痕</span>
            <span class="mp-note">全部管理动作可审计追溯</span>
          </div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作人</th>
                  <th>动作</th>
                  <th>对象</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="a in summary.recentAudits" :key="a.id">
                  <td>{{ a.time }}</td>
                  <td class="is-who">{{ a.operator }}（{{ a.roleName }}）</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.targetName }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">快捷入口</span>
          <span class="mp-note">按钮随当前角色权限自动裁剪</span>
        </div>
        <div class="mp-card__body">
          <ModuleToolbar :actions="quickActions" @action="onQuickAction" />
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学生中心首页 / 管理看板（/admin/student）：角色差异化指标 + 待办 + 异动 + 审计。 */
import {
  ModulePageShell,
  ModuleHero,
  ModuleToolbar,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { studentApi } from '@/modules/student/api/student.api'

export default {
  name: 'StudentOverviewView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      summary: { stats: [], flow: [], todos: [], recentChanges: [], recentAudits: [] }
    }
  },
  computed: {
    heroChips() {
      return [
        this.ctx.currentRole.roleName,
        '数据范围：' + this.ctx.dataScope.scopeName,
        '敏感字段默认脱敏'
      ]
    },
    quickActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'list', label: '学生主档列表', variant: 'primary', perm: 'viewList' },
        { key: 'create', label: '新增学生', perm: 'createStudent' },
        { key: 'import', label: '批量导入', perm: 'importStudents' },
        { key: 'export', label: '导出台账', perm: 'exportStudents' },
        { key: 'status', label: '学籍状态管理', perm: 'changeStatus' },
        { key: 'risk', label: '风险标签', perm: 'viewList' }
      ]
        .filter((a) => pa[a.perm] && pa[a.perm].visible)
        .map((a) => ({ ...a, disabled: !pa[a.perm].allowed, disabledReason: pa[a.perm].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(v) {
      const hit = this.ctx.statusOptions.studentStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    onQuickAction(key) {
      const routeMap = {
        list: '/admin/student/list',
        create: '/admin/student/list?action=create',
        import: '/admin/student/import-export',
        export: '/admin/student/import-export',
        status: '/admin/student/status',
        risk: '/admin/student/risk-tags'
      }
      if (routeMap[key]) this.$router.push(routeMap[key])
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentApi.getDashboardSummary()
      if (res.code === 0) this.summary = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

/* 待办卡片 */
.ov-todo {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--motion-fast) var(--ease-standard);
}
.ov-todo:hover {
  border-color: var(--primary-100);
}
.ov-todo__count {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: var(--font-numeric);
}
.ov-todo.is-warning .ov-todo__count {
  color: var(--warning-600);
}
.ov-todo.is-danger .ov-todo__count {
  color: var(--danger-600);
}
.ov-todo__label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
.ov-todo__hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ov-todo__go {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-link);
  font-weight: var(--font-weight-medium);
}
</style>
