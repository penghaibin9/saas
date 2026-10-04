<template>
  <div class="base-portal-layout bpl-workspace" :style="workspaceColors">
    <header class="bpl-topbar">
      <div class="bpl-brand"><span class="bpl-logo"><OfficeBuilding aria-hidden="true" /></span><strong class="bpl-brand__nm">{{ title }}</strong></div>
      <div class="bpl-search"><div class="bpl-cmdk"><Search class="bpl-ic" aria-hidden="true" /><input v-model.trim="query" type="search" aria-label="搜索实习功能" placeholder="搜索实习功能" @keydown.enter.prevent="selectFirst" @keydown.esc="query = ''" /><div v-if="query" class="bpl-cmdk__panel" role="region" aria-label="实习功能搜索结果"><button v-for="item in results" :key="item.id" type="button" @click="select(item)"><span>{{ item.title }}</span><small>{{ item.trail }}</small></button><p v-if="!results.length">未找到有权限访问的相关功能</p></div></div></div>
      <div class="bpl-top-r"><WorkspaceDeskUtilities /><button class="bpl-control" type="button" @click="workspaceFrame?.openAppearance()">外观设置</button><span>{{ roleLabel }}</span><button class="bpl-control" type="button" @click="logout">退出</button></div>
    </header>
    <TeacherWorkspaceFrame v-if="ctx" ref="workspaceFrame" :key="ctx.ctxKey" :modules="modules" :centers="centers" active-center="internship" :active-module="activeModule" :identity-key="identityKey" :scope-name="ctx.dataScope?.scopeName || ''" :resolve-destination="workspaceNavigate" @tokens="workspaceColors = $event"><slot /></TeacherWorkspaceFrame>
    <main v-else class="bpl-workspace-pending" aria-label="工作区加载状态"><slot /></main>
    <footer v-if="$slots.footer"><slot name="footer" /></footer>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { OfficeBuilding, Search } from '@element-plus/icons-vue'
import TeacherWorkspaceFrame from '@/components/workspace/TeacherWorkspaceFrame.vue'
import WorkspaceDeskUtilities from '@/components/workspace/WorkspaceDeskUtilities.vue'
import { workspacePages, workspaceTokens } from '@/components/workspace/teacherWorkspace'
import { activeWorkspacePage } from '@/components/workspace/workspaceRouting'
import { getVisibleNavPlan } from '@/config/navPlan'
import { currentUserFromToken, logoutRemote } from '@/services/http/client'
const props = defineProps({ title: { type: String, required: true }, subtitle: { type: String, default: '' }, menus: { type: Array, default: () => [] }, activeKey: { type: String, default: '' }, hideAside: Boolean, workspace: Boolean, hideGlobalWorkbench: Boolean, workspaceNavigate: { type: Function, default: path => path }, ctx: { type: Object, default: null } })
const emit = defineEmits(['menu-select', 'menu-disabled'])
const route = useRoute(), router = useRouter(), workspaceFrame = ref(null)
const workspaceColors = ref(workspaceTokens('blue')), query = ref('')
const roleLabel = computed(() => { const role = props.ctx?.currentRole; const labels = { SCHOOL_ADMIN: '学校管理员', INTERN_MENTOR: '实习指导教师', TEACHER: '教师', COLLEGE_ADMIN: '院系管理员' }; const name = role?.roleName || ''; return /^[A-Z_]+$/.test(name) ? labels[name] || '学校用户' : name || labels[role?.roleCode] || '学校用户' })
const modules = computed(() => getVisibleNavPlan({ permissionPatterns: props.ctx?.permissionPatterns || [], ctxKey: props.ctx?.ctxKey || '' }).find(group => group.key === 'internship')?.children || [])
const pages = computed(() => workspacePages(modules.value))
const activeModule = computed(() => activeWorkspacePage(pages.value, route)?.moduleKey || modules.value[0]?.key || '')
const centers = computed(() => modules.value.length ? [{ key: 'internship', label: '岗位实习中心', path: modules.value[0].path }] : [])
const identityKey = computed(() => { const claims = currentUserFromToken(); return 'internship-shell:' + (claims?.tenantId != null && claims?.userId != null ? JSON.stringify([String(claims.tenantId), String(claims.userId), claims.currentRoleCode || '', claims.activeContextId || '']) : props.ctx?.ctxKey || '') })
const results = computed(() => pages.value.filter(item => !item.hidden && !item.workspaceHidden && item.title.includes(query.value)).slice(0, 30))
watch(identityKey, () => { query.value = '' })
watch(() => route.fullPath, () => { query.value = '' })
function select(item) { emit('menu-select', item); const destination = props.workspaceNavigate(item.destination || item.path); if (destination) router.push(destination); query.value = '' }
function selectFirst() { if (results.value.length) select(results.value[0]) }
async function logout() { await logoutRemote(); await router.replace('/login') }
</script>
<style scoped>
.base-portal-layout{height:100vh;display:flex;flex-direction:column;overflow:hidden;background:var(--bg);color:var(--t1)}
.bpl-topbar{height:60px;flex-shrink:0;display:flex;align-items:center;gap:10px;padding:0 20px;background:var(--surface-2);border-bottom:1px solid var(--line);position:relative;z-index:30}
.bpl-brand{display:flex;align-items:center;gap:12px;flex-shrink:0}.bpl-logo{width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;background:var(--pri);color:var(--pri-on)}.bpl-logo svg{width:25px;height:25px}.bpl-brand__nm{font-size:17px;color:var(--t1)}
.bpl-search{flex:1;min-width:0;display:flex;margin:0 10px;max-width:600px}.bpl-cmdk{position:relative;width:100%;height:36px;display:flex;align-items:center;gap:8px;padding:0 12px;border:1px solid var(--line);border-radius:9px;background:var(--surface)}.bpl-ic{width:16px;height:16px;flex-shrink:0}.bpl-cmdk input{width:100%;border:0;background:transparent;outline:0;color:var(--t1)}.bpl-cmdk__panel{position:absolute;top:42px;left:0;right:0;padding:8px;max-height:360px;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:9px;box-shadow:0 8px 24px #10203020}.bpl-cmdk__panel button{width:100%;display:flex;justify-content:space-between;gap:12px;padding:10px;border:0;border-radius:6px;background:transparent;color:var(--t1);cursor:pointer}.bpl-cmdk__panel button:hover{background:var(--pri-50)}.bpl-cmdk__panel small,.bpl-cmdk__panel p{color:var(--t3)}
.bpl-top-r{display:flex;align-items:center;gap:14px;margin-left:auto;white-space:nowrap;font-size:13px}.bpl-control{padding:6px 10px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--t1);cursor:pointer}.bpl-workspace-pending{flex:1;min-height:0;overflow:auto;padding:24px}
@media(max-width:1250px){.bpl-brand__nm{font-size:14px}.bpl-search{margin:0 2px}}@media(max-width:900px){.bpl-topbar{padding:0 10px}.bpl-brand__nm{display:none}.bpl-top-r{gap:6px}}
</style>
