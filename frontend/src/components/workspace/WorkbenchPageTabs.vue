<template>
  <nav v-if="entries.length" class="workbench-page-tabs" aria-label="本栏目页面">
    <RouterLink v-for="item in entries" :key="item.path" :to="item.path" :class="{ selected: active === item.path }" :aria-current="active === item.path ? 'page' : undefined">{{ item.label }}</RouterLink>
  </nav>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { matchPermission } from '@/config/navPlan'
import { WORKBENCH_PAGE_TABS, workbenchSection } from '@/modules/workbench/config/workbenchNavigation'
const props = defineProps({ permissions: { type: Array, default: () => [] } })
const route = useRoute()
const entries = computed(() => WORKBENCH_PAGE_TABS.filter(item => item.section === workbenchSection(route.path) && matchPermission(props.permissions, item.permissionKey)))
const active = computed(() => entries.value.filter(item => route.path === item.path || route.path.startsWith(item.path + '/')).sort((a, b) => b.path.length - a.path.length)[0]?.path)
</script>
<style scoped>
.workbench-page-tabs{display:flex;gap:8px;overflow:auto;border-bottom:1px solid var(--line);margin-bottom:16px;padding-bottom:8px;scrollbar-width:thin}.workbench-page-tabs a{white-space:nowrap;color:var(--t3);padding:7px 12px;font-size:13px;border-radius:6px;text-decoration:none}.workbench-page-tabs a.selected{color:var(--pri);background:var(--pri-50);font-weight:600}
</style>
