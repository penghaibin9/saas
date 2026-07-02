<template>
  <BasePortalLayout
    :title="title"
    :subtitle="subtitle"
    :menus="menus"
    :active-key="activeKey"
    @menu-select="$emit('menu-select', $event)"
  >
    <template #logo><slot name="logo" /></template>
    <template #header-right><slot name="header-right" /></template>
    <template #user><slot name="user" /></template>

    <div v-if="showScopeNotice" class="epl-scope-notice">
      仅展示企业授权学生。不展示学生家庭信息、学业敏感信息与学校内部审批意见；未经学校授权不可导出学生名单。
    </div>
    <slot />

    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from './BasePortalLayout.vue'

/**
 * EnterprisePortalLayout 企业导师 PC 轻门户壳（雏形，基于 BasePortalLayout 复用，V2.1 §6）
 * - 禁止复制布局壳改名，禁止使用 09A 管理端布局
 * - 默认内置授权范围提示（V2.1 §6.4），可通过 showScopeNotice 关闭
 * Props: title / subtitle / menus / activeKey / showScopeNotice
 * Emits: menu-select
 */
const ENTERPRISE_MENUS = [
  { key: 'home', label: '首页', icon: '⌂' },
  { key: 'students', label: '我的实习生', icon: '◫' },
  { key: 'weekly-reports', label: '周报查看', icon: '▤' },
  { key: 'evaluations', label: '企业评价', icon: '☆' },
  { key: 'employment-intentions', label: '录用意向', icon: '✓' },
  { key: 'profile', label: '企业信息', icon: '◎' }
]

export default {
  name: 'EnterprisePortalLayout',
  components: { BasePortalLayout },
  props: {
    title: { type: String, default: '企业导师门户' },
    subtitle: { type: String, default: '' },
    menus: { type: Array, default: () => ENTERPRISE_MENUS },
    activeKey: { type: String, default: 'home' },
    showScopeNotice: { type: Boolean, default: true }
  },
  emits: ['menu-select']
}
</script>

<style scoped>
.epl-scope-notice {
  background: var(--info-50);
  border: 1px solid var(--info-100);
  color: var(--info-700);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-4);
  line-height: var(--line-height-base);
}
</style>
