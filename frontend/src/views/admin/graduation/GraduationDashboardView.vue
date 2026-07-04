<template>
  <ModulePageShell
    title="毕业设计中心"
    :subtitle="hero.batchName + ' · ' + hero.batchStatus"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 毕业设计总览'"
        :subtitle="hero.batchName + '（' + hero.batchRange + '）'"
        :chips="heroChips"
        :stats="hero.stats"
        :flow="hero.flow"
      />

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">今日待办</span>
            <button class="mp-link" @click="$router.push('/admin/graduation/students')">毕设学生 →</button>
          </div>
          <div class="mp-card__body mp-stack">
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv">
              <span class="mp-kv__k">
                <StatusTag :type="t.tone === 'danger' ? 'danger' : 'warning'" :label="String(t.count)" dot />
                <span class="gdb-todo-label">{{ t.label }}</span>
                <span class="mp-note">（{{ t.hint }}）</span>
              </span>
              <button class="mp-link" @click="$router.push(t.route)">去处理</button>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">滞后与风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/graduation/students')">滞后学生 →</button>
          </div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.code }} · {{ r.title }}
                  <RiskTag :level="r.level" />
                </div>
                <div class="mp-timeline__desc">{{ r.detail }}</div>
                <div class="mp-timeline__time">{{ r.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <p class="mp-note">进度洞察可下钻：滞后学生 → 毕设学生列表（按风险筛选）；批量提醒 / 导出均写入审计日志。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕业设计中心 · 管理看板（/admin/graduation）。 */
import { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', hero: { stats: [], flow: [], todos: [], riskAlerts: [], batchName: '', batchRange: '', batchStatus: '' } }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createBatch', label: '＋ 新增毕设批次', variant: 'primary' },
        { key: 'importStudents', label: '导入学生名单' },
        { key: 'exportStats', label: '导出进度统计' },
        { key: 'viewAuditLog', label: '操作日志', variant: 'ghost' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    heroChips() {
      return ['当前角色：' + this.ctx.currentRole.roleName, '数据范围：' + this.ctx.dataScope.scopeName]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getDashboardSummary()
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
    },
    onToolbar(key) {
      if (key === 'exportStats') toast.success('进度统计导出任务已创建（脱敏 + 水印），已写入审计日志')
      else if (key === 'viewAuditLog') toast.info('演示环境：操作日志面板将在后续批次开放')
      else toast.info('演示环境：该操作将在后续批次开放')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gdb-todo-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  margin: 0 var(--space-1);
}
</style>
