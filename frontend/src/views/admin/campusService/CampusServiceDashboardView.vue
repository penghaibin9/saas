<template>
  <ModulePageShell
    title="在校服务中心"
    :subtitle="hero.termName + '（' + hero.termRange + '）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 在校服务总览'"
        :subtitle="'指标按当前数据范围实时计算 · 更新于 ' + hero.updateTime"
        :chips="heroChips"
        :stats="hero.kpis"
        :flow="hero.flow"
      />

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">我的待办</span>
            <button class="mp-link" @click="$router.push('/admin/campus-service/students')">学生服务 →</button>
          </div>
          <div class="mp-card__body mp-stack">
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv">
              <span class="mp-kv__k">
                <StatusTag type="warning" :label="String(t.value)" dot />
                <span class="csd-todo-label">{{ t.label }}</span>
              </span>
              <button class="mp-link" @click="goLink(t.link)">去处理</button>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">逾期与风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/campus-service/work-orders')">服务工单 →</button>
          </div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.title }}
                  <RiskTag :level="r.level" />
                </div>
                <div class="mp-timeline__desc">
                  <button class="mp-link" @click="goLink(r.link)">查看 →</button>
                </div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">热门服务排行（近30天）</span>
        </div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead><tr><th>服务事项</th><th>办理量</th><th>趋势</th></tr></thead>
            <tbody>
              <tr v-for="h in hero.hotServices" :key="h.name">
                <td class="is-who">{{ h.name }}</td>
                <td>{{ h.count }}</td>
                <td>{{ h.trend }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <p class="mp-note">
        家庭经济困难材料与心理关怀记录为敏感数据：仅授权角色可见，查看与导出均写入审计日志。本页所有操作留痕，指标口径与数据驾驶舱同源。
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 在校服务中心 · 服务工作台（/admin/campus-service）。指标按角色数据范围动态计算，数据全部来自 campusService.api。 */
import { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { getCampusServiceDashboard, createExport } from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

export default {
  name: 'CampusServiceDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      hero: { kpis: [], flow: [], todos: [], riskAlerts: [], hotServices: [], termName: '', termRange: '', updateTime: '' }
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createOrder', permission: 'campus.workorder.create', label: '＋ 新建服务工单', variant: 'primary' },
        { key: 'export', permission: 'campus.record.export', label: '导出服务台账' },
        { key: 'audit', permission: 'campus.audit.view', label: '操作留痕', variant: 'ghost' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    heroChips() {
      return ['当前角色：' + this.ctx.currentRole.roleName, '数据范围：' + this.ctx.dataScope.name]
    }
  },
  created() {
    this.load()
  },
  methods: {
    goLink(link) {
      const map = {
        leave: '/admin/campus-service/leave',
        grants: '/admin/campus-service/grants',
        dorm: '/admin/campus-service/dormitory',
        workorders: '/admin/campus-service/work-orders'
      }
      this.$router.push(map[link] || '/admin/campus-service/students')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getCampusServiceDashboard()
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'createOrder') {
        this.$router.push('/admin/campus-service/work-orders?create=1')
      } else if (key === 'export') {
        const res = await createExport('serviceList', { scope: 'SCOPE_ALL', fieldGroups: ['base', 'service'], mask: true, auditConfirmed: true })
        if (res.code === 0) toast.success('服务台账导出任务已创建（脱敏 + 水印），已写入审计日志')
        else toast.error(res.message)
      } else if (key === 'audit') {
        this.$router.push('/admin/campus-service/students?tab=audit')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.csd-todo-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  margin: 0 var(--space-1);
}
</style>
