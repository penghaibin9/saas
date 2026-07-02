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
    <slot />
    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from './BasePortalLayout.vue'

/**
 * StudentPortalLayout 学生 PC 门户壳（雏形，基于 BasePortalLayout 复用，V2.1 §5/§6.2）
 * - 默认菜单为 V2.1 §5.3 允许的学生轻菜单，可由 props 覆盖
 * - 硬约束：学生所有业务页必须渲染在本壳内，禁止使用管理端布局
 * - 禁止出现系统管理、审计日志、权限管理等后台菜单
 * Props: title / subtitle / menus / activeKey
 * Emits: menu-select
 */
const STUDENT_MENUS = [
  { key: 'home', label: '首页', icon: '⌂' },
  { key: 'todos', label: '我的待办', icon: '☑' },
  { key: 'messages', label: '我的消息', icon: '✉' },
  { key: 'materials', label: '我的材料', icon: '▤' },
  { key: 'graduation-design', label: '毕业设计', icon: '◧' },
  { key: 'internship', label: '岗位实习', icon: '◨' },
  { key: 'employment', label: '毕业就业', icon: '◩' },
  { key: 'profile', label: '个人中心', icon: '◎' }
]

export default {
  name: 'StudentPortalLayout',
  components: { BasePortalLayout },
  props: {
    title: { type: String, default: '学生门户' },
    subtitle: { type: String, default: '' },
    menus: { type: Array, default: () => STUDENT_MENUS },
    activeKey: { type: String, default: 'home' }
  },
  emits: ['menu-select']
}
</script>
