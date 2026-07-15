<template>
  <ModulePageShell
    :title="capability.label"
    :subtitle="capability.groupLabel + ' · ' + capability.description"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ModuleHero
        :title="capability.label"
        :subtitle="capability.groupDescription"
        :stats="heroStats"
      />

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">学校侧职责与边界</span></header>
        <div class="mp-card__body scv-boundary">
          <div><b>学校可以做</b><p>{{ schoolCanDo }}</p></div>
          <div><b>学校不能做</b><p>{{ schoolCannotDo }}</p></div>
          <div><b>安全要求</b><p>{{ securityRule }}</p></div>
        </div>
      </section>

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">受控操作权限</span><span class="mp-note">高风险操作须二次确认、填写原因并写入审计</span></header>
        <div class="mp-card__body scv-actions">
          <div v-for="item in capability.actions" :key="item.key" class="scv-action">
            <code>{{ item.key }}</code>
            <span>{{ item.label }}</span>
            <StatusTag :type="item.risk === 'HIGH' ? 'warning' : 'info'" :label="item.risk === 'HIGH' ? '高风险' : '常规'" />
          </div>
        </div>
      </section>

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">落地约束</span></header>
        <div class="mp-card__body">
          <ul class="scv-list">
            <li v-for="rule in implementationRules" :key="rule">{{ rule }}</li>
          </ul>
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学校级系统管理的通用承载页。
 * 它只展示已冻结的治理边界和权限动作，不伪造尚未接入后端的业务数据或写接口；
 * 后续接入真实 API 时按 capability.key 扩展，而不再新增一套菜单/权限定义。
 */
import { ModulePageShell, ModuleHero, StatusTag } from '@/components/business'
import { SYSTEM_MANAGEMENT_ITEM_MAP } from '@/modules/system/systemManagementCatalog'

const FALLBACK = {
  key: 'unknown', label: '系统管理能力', groupLabel: '系统管理',
  description: '学校级系统治理能力。', groupDescription: '统一由权限目录、路由和后端权限码共同约束。', actions: []
}

export default {
  name: 'SystemCapabilityView',
  components: { ModulePageShell, ModuleHero, StatusTag },
  props: { ctx: { type: Object, required: true } },
  computed: {
    capability() {
      return SYSTEM_MANAGEMENT_ITEM_MAP[this.$route.meta.systemCapabilityKey] || FALLBACK
    },
    heroStats() {
      return [
        { label: '权限码', value: this.capability.permissionKey || '—', tone: 'info' },
        { label: '操作点', value: String(this.capability.actions.length), tone: 'primary' },
        { label: '数据边界', value: '本校租户', tone: 'success' }
      ]
    },
    schoolCanDo() {
      const key = this.capability.key
      if (key === 'sys-module-entitlements') return '查看本校已开通能力，并在平台授权范围内调整允许学校自主管理的业务开关。'
      if (key.includes('audit')) return '只读查询和受控导出本校审计记录；可按人员、时间、对象和风险等级追溯。'
      if (key.includes('integration') || key === 'sys-sync-jobs') return '维护本校已授权的接口连接、查看同步结果并对失败任务进行受控重试。'
      return '在本校租户范围内完成配置、查看和授权；所有高风险变更保留原因、前后值和操作人。'
    },
    schoolCannotDo() {
      const key = this.capability.key
      if (key === 'sys-module-entitlements') return '不能开通未购买模块、修改套餐、到期时间或其他学校的授权状态。'
      if (key.includes('audit')) return '不能修改或删除审计记录，不能查看其他学校的数据。'
      if (key.includes('integration') || key === 'sys-sync-jobs') return '不能读取明文密钥，不能配置平台级通用连接或绕过接口审计。'
      return '不能跨租户管理数据，不能绕过平台发布的菜单、权限目录、业务状态机和敏感字段控制。'
    },
    securityRule() {
      if (this.capability.key === 'sys-delegations') return '临时授权必须设置生效与到期时间；到期自动回收，提前撤销和所有使用记录均须审计。'
      if (this.capability.key === 'sys-dictionaries-fields') return '扩展字段采用受控元数据，不允许学校直接创建数据库列或改变核心字段语义。'
      if (this.capability.key === 'sys-numbering-rules') return '规则变更必须先预览和冲突校验；已经生成的历史编号不可重写。'
      return '权限判断由后端执行：模块授权、角色、菜单、操作、数据范围、业务关系和敏感字段均需同时通过。'
    },
    implementationRules() {
      return [
        '前端菜单只负责导航体验，后端接口必须使用同一权限码进行最终校验。',
        '涉及账号、权限、范围、导出、流程干预和接口凭证的变更必须记录操作原因与前后值。',
        '本页面后续接入真实服务时，只能扩展该能力的 API，不得新增绕过统一权限目录的独立入口。'
      ]
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.scv-boundary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }
.scv-boundary > div { padding: var(--space-4); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-page); }
.scv-boundary b { color: var(--text-primary); }
.scv-boundary p { margin: var(--space-2) 0 0; color: var(--text-secondary); line-height: 1.65; font-size: var(--font-size-sm); }
.scv-actions { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.scv-action { display: inline-flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.scv-action code { color: var(--primary-700); font-size: var(--font-size-xs); }
.scv-list { margin: 0; padding-left: 1.2em; color: var(--text-secondary); line-height: 1.9; font-size: var(--font-size-sm); }
@media (max-width: 900px) { .scv-boundary { grid-template-columns: 1fr; } }
</style>
