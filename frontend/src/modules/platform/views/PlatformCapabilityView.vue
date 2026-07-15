<template>
  <ModulePageShell
    :title="capability.label"
    :subtitle="capability.groupLabel + ' · ' + capability.description"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="SaaS 平台运营"
  >
    <div class="mp-stack">
      <ModuleHero :title="capability.label" :subtitle="capability.groupDescription" :stats="heroStats" />

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">平台职责与跨租户边界</span></header>
        <div class="mp-card__body pcv-boundary">
          <div><b>平台可以做</b><p>{{ platformCanDo }}</p></div>
          <div><b>平台不能做</b><p>{{ platformCannotDo }}</p></div>
          <div><b>强制留痕</b><p>{{ auditRule }}</p></div>
        </div>
      </section>

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">受控操作权限</span><span class="mp-note">高风险动作需二次确认、原因和审计</span></header>
        <div class="mp-card__body pcv-actions">
          <div v-for="item in capability.actions" :key="item.key" class="pcv-action">
            <code>{{ item.key }}</code><span>{{ item.label }}</span>
            <StatusTag :type="item.risk === 'HIGH' ? 'warning' : 'info'" :label="item.risk === 'HIGH' ? '高风险' : '常规'" />
          </div>
        </div>
      </section>

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">实现约束</span></header>
        <div class="mp-card__body"><ul class="pcv-list"><li v-for="rule in rules" :key="rule">{{ rule }}</li></ul></div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
/** 平台控制面通用承载页：先固化租户边界与权限契约，真实服务按能力码接入。 */
import { ModulePageShell, ModuleHero, StatusTag } from '@/components/business'
import { PLATFORM_MANAGEMENT_ITEM_MAP } from '@/modules/platform/platformManagementCatalog'

const FALLBACK = { key: 'unknown', label: '平台运营能力', groupLabel: '平台运营', description: '跨租户控制面能力。', groupDescription: '平台仅管理控制面，不直接处理学校业务数据。', actions: [] }

export default {
  name: 'PlatformCapabilityView',
  components: { ModulePageShell, ModuleHero, StatusTag },
  props: { ctx: { type: Object, required: true } },
  computed: {
    capability() { return PLATFORM_MANAGEMENT_ITEM_MAP[this.$route.meta.platformCapabilityKey] || FALLBACK },
    heroStats() {
      return [
        { label: '权限码', value: this.capability.permissionKey || '—', tone: 'info' },
        { label: '操作点', value: String(this.capability.actions.length), tone: 'primary' },
        { label: '访问边界', value: '控制面', tone: 'success' }
      ]
    },
    platformCanDo() {
      if (this.capability.key === 'plt-support-sessions') return '在学校主动授权的用途、时间和范围内，以只读优先方式协助排障。'
      if (this.capability.key.includes('tenant') || this.capability.key.includes('provision')) return '管理租户元数据、授权、开通任务和上线检查，不直接操作学校业务记录。'
      return '在平台职责与当前权限范围内管理跨租户配置、运行状态和受控自动化任务。'
    },
    platformCannotDo() {
      if (this.capability.key === 'plt-support-sessions') return '不能绕过学校授权长期访问，不能默认读取学生敏感明细，授权到期必须自动回收。'
      return '不能通过控制面绕过学校数据范围、业务状态机或敏感字段规则；不得直接连接或修改学校业务数据库。'
    },
    auditRule() {
      if (this.capability.key.includes('release')) return '每次灰度范围、版本、回滚原因和结果均需保留，以便按租户回溯。'
      if (this.capability.key.includes('entitlement') || this.capability.key.includes('orders')) return '授权授予、回收、配额和订单开通必须记录前后值、订单依据和操作人。'
      return '跨租户查看、配置变更、密钥轮换、任务重试和高风险生命周期动作均必须记录用途、原因、时间和结果。'
    },
    rules() {
      return [
        '平台能力只能由平台角色进入，学校角色不可见；学校业务菜单也不会向平台角色开放。',
        '订单确认 → 授权生效 → 自动开通 → 学校初始化检查为唯一交付链路，禁止人工绕过任一步。',
        '本页后续接入真实 API 时必须复用 capability key、权限码和不可篡改审计，不得另建旁路入口。'
      ]
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pcv-boundary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }
.pcv-boundary > div { padding: var(--space-4); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-page); }
.pcv-boundary p { margin: var(--space-2) 0 0; color: var(--text-secondary); line-height: 1.65; font-size: var(--font-size-sm); }
.pcv-actions { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.pcv-action { display: inline-flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.pcv-action code { color: var(--primary-700); font-size: var(--font-size-xs); }
.pcv-list { margin: 0; padding-left: 1.2em; color: var(--text-secondary); line-height: 1.9; font-size: var(--font-size-sm); }
@media (max-width: 900px) { .pcv-boundary { grid-template-columns: 1fr; } }
</style>
