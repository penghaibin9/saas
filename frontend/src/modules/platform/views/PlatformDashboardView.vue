<template>
  <ModulePageShell
    title="SaaS 运营看板"
    :subtitle="ctx.tenantBrandConfig.platformDisplayName + ' · 租户 / 授权 / 集成健康总览'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="平台运营看板"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <ModuleHero
          :title="ctx.tenantBrandConfig.platformDisplayName + ' · 运营总览'"
          :subtitle="'当前角色 ' + ctx.currentRole.roleName + ' · 数据范围 ' + ctx.dataScope.scopeName + ' · 指标按数据范围过滤'"
          :stats="summary.stats"
        />

        <div class="mp-grid-2">
          <section class="mp-card">
            <header class="mp-card__head">
              <span class="mp-card__title">续费与到期提醒</span>
              <button class="mp-link" @click="$router.push('/admin/platform/orders')">订单授权 →</button>
            </header>
            <div class="mp-card__body" style="padding-top: 0">
              <table class="mp-audit">
                <thead><tr><th>租户</th><th>套餐</th><th>到期</th><th>跟进</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="r in summary.renewals" :key="r.id">
                    <td class="is-who">{{ r.tenantName }}</td>
                    <td>{{ r.packageName }}</td>
                    <td><StatusTag :type="r.remainDays <= 30 ? 'danger' : 'warning'" :label="r.expireAt + '（' + r.remainDays + ' 天）'" /></td>
                    <td>{{ r.csOwnerName }}{{ r.hasPendingOrder ? ' · 已建续费单' : '' }}</td>
                    <td><button class="mp-link" @click="$router.push('/admin/platform/tenants/' + r.tenantId)">详情</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="mp-card">
            <header class="mp-card__head">
              <span class="mp-card__title">集成健康告警</span>
              <button class="mp-link" @click="$router.push('/admin/platform/sync')">同步与日志 →</button>
            </header>
            <div class="mp-card__body">
              <ul class="mp-timeline">
                <li
                  v-for="a in summary.integrationAlerts"
                  :key="a.id"
                  class="mp-timeline__item"
                  :class="a.level === 'HIGH' ? 'is-danger' : 'is-warning'"
                >
                  <div class="mp-timeline__title">{{ a.title }} <RiskTag :level="a.level" /></div>
                  <div class="mp-timeline__desc">{{ a.detail }}</div>
                  <div class="mp-timeline__time">{{ a.time }}</div>
                </li>
              </ul>
            </div>
          </section>
        </div>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">最近平台操作（审计摘要）</span>
            <span class="mp-note">平台审计日志不可删除，仅支持只读查看与受控导出</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th style="width: 220px">操作人</th><th>动作</th><th style="width: 130px">时间</th></tr></thead>
              <tbody>
                <tr v-for="r in summary.recentOps" :key="r.id">
                  <td class="is-who">{{ r.who }}</td><td>{{ r.action }}</td><td>{{ r.time }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 平台运营首页（/admin/platform）：SaaS 指标 + 续费提醒 + 集成健康 + 审计摘要。 */
import { ModulePageShell, ModuleToolbar, ModuleHero, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { platformApi } from '@/modules/platform/api/platform.api'

export default {
  name: 'PlatformDashboardView',
  components: { ModulePageShell, ModuleToolbar, ModuleHero, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', summary: null }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createTenant', label: '＋ 新增租户', variant: 'primary' },
        { key: 'createOrder', label: '＋ 新增订单' },
        { key: 'viewPlatformLogs', label: '≡ 平台日志' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    onToolbar(key) {
      if (key === 'createTenant') this.$router.push('/admin/platform/tenants?action=create')
      if (key === 'createOrder') this.$router.push('/admin/platform/orders?action=create')
      if (key === 'viewPlatformLogs') this.$router.push('/admin/platform/sync?tab=logs')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformApi.getDashboardSummary()
      if (res.code === 0) this.summary = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
