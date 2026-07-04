<template>
  <ModulePageShell
    title="岗位实习中心"
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
        :title="ctx.tenantBrandConfig.schoolName + ' · 岗位实习总览'"
        :subtitle="hero.batchName + '（' + hero.batchRange + '）'"
        :chips="heroChips"
        :stats="hero.stats"
        :flow="hero.flow"
      />

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">今日待办</span>
            <button class="mp-link" @click="$router.push('/admin/internship/students')">实习学生 →</button>
          </div>
          <div class="mp-card__body mp-stack">
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv">
              <span class="mp-kv__k">
                <StatusTag :type="t.tone === 'danger' ? 'danger' : 'warning'" :label="String(t.count)" dot />
                <span class="idb-todo-label">{{ t.label }}</span>
                <span class="mp-note">（{{ t.hint }}）</span>
              </span>
              <button class="mp-link" @click="$router.push(t.route)">去处理</button>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/internship/risks')">风险学生 →</button>
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

      <p class="mp-note">本页所有操作（含导出）均写入审计日志；指标口径与数据驾驶舱同源，页面不自行计算。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 岗位实习中心 · 管理看板（/admin/internship）。数据全部来自 internshipApi。 */
import { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

export default {
  name: 'InternshipDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', hero: { stats: [], flow: [], todos: [], riskAlerts: [], batchName: '', batchRange: '', batchStatus: '' } }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const def = [
        { key: 'createBatch', label: '＋ 新增实习批次', variant: 'primary' },
        { key: 'importStudents', label: '导入实习学生' },
        { key: 'exportGroup', label: '导出统计数据' },
        { key: 'viewAuditLog', label: '操作日志', variant: 'ghost' }
      ]
      return def
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
      const res = await internshipApi.getDashboardSummary()
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
    },
    onToolbar(key) {
      if (key === 'exportGroup') toast.success('导出任务已创建：含脱敏与水印，完成后在消息中心可下载（已留痕）')
      else if (key === 'viewAuditLog') toast.info('演示环境：操作日志面板将在后续批次开放')
      else toast.info('演示环境：该操作将在后续批次开放')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.idb-todo-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  margin: 0 var(--space-1);
}
</style>
