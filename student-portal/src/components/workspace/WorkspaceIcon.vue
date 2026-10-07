<template><span class="workspace-icon" aria-hidden="true" v-html="art" /></template>
<script setup>
import { computed } from 'vue'
import { workspaceIcons } from '../../assets/icons/workspaceIcons'
const props = defineProps({ name: { type: String, default: 'dashboard' } })
const names = { home: 'DataBoard', schedule: 'Calendar', grades: 'Reading', departure: 'Flag', 'academic-home': 'DataBoard', 'academic-study': 'Calendar', 'academic-exam': 'Reading', 'academic-growth': 'Reading', 'academic-all': 'FolderOpened', 'academic-graduation': 'Reading', 'internship-profile': 'User', 'internship-compliance': 'Tickets', 'internship-selection': 'Suitcase', 'orientation-info': 'User', 'orientation-arrival': 'Calendar', 'orientation-materials': 'FolderOpened', 'orientation-green': 'Tickets', dashboard: 'DataBoard', work: 'DataBoard', hall: 'Search', search: 'Search', profile: 'User', academic: 'Reading', graduation: 'Reading', internship: 'Suitcase', employment: 'School', campusService: 'Tickets', leave: 'Calendar', dorm: 'House', aid: 'Tickets', funding: 'Star', activity: 'Flag', care: 'Message', talk: 'Message', psy: 'User', discipline: 'Tickets', materials: 'FolderOpened', orientation: 'Flag', messages: 'Bell', collapse: 'DArrowLeft', expand: 'DArrowRight' }
// 图形来自仓库内的官方静态图标；外部数据只经过白名单名称映射。
const art = computed(() => workspaceIcons[names[props.name] || 'FolderOpened'])
</script>
<style scoped>
.workspace-icon{display:inline-flex;width:20px;height:20px;flex:none;align-items:center;justify-content:center}.workspace-icon :deep(svg){display:block;width:100%;height:100%;fill:currentColor}
</style>
