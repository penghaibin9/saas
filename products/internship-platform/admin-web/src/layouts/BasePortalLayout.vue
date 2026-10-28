<template>
  <div class="base-portal-layout bpl-workspace" :style="workspaceColors">
    <header class="bpl-topbar">
      <div class="bpl-brand"><span class="bpl-logo"><img v-if="logoUrl" :src="logoUrl" alt="学校校徽"/><OfficeBuilding v-else aria-hidden="true" /></span><strong class="bpl-brand__nm">{{ title }}</strong></div>
      <div class="bpl-search"><div class="bpl-cmdk"><Search class="bpl-ic" aria-hidden="true" /><input v-model.trim="query" type="search" aria-label="搜索功能" placeholder="搜索功能" @keydown.enter.prevent="selectFirst" @keydown.esc="query = ''" /><div v-if="query" class="bpl-cmdk__panel" role="region" aria-label="功能搜索结果"><button v-for="item in results" :key="item.id" type="button" @click="select(item)"><span>{{ item.title }}</span><small>{{ item.trail }}</small></button><p v-if="!results.length">未找到有权限访问的相关功能</p></div></div></div>
      <div class="bpl-top-r"><WorkspaceDeskUtilities /><details class="bpl-service"><summary>学校服务</summary><div><p>{{ service.reminderText || '请及时处理岗位实习待办。' }}</p><p>咨询电话：{{ service.contactPhone || '学校尚未配置' }}</p><p v-if="service.supervisionPhone">监督电话：{{ service.supervisionPhone }}</p><p v-if="service.responsibleName">服务承办人：{{ service.responsibleName }}</p><details v-for="item in service.faq || []" :key="item.question"><summary>{{ item.question }}</summary><p>{{ item.answer }}</p></details><p v-if="!service.faq?.length">学校尚未配置常见问题。</p></div></details><button class="bpl-control" type="button" @click="workspaceFrame?.openAppearance()">外观设置</button><select v-if="contexts.length > 1" class="bpl-control" :value="activeContext" :disabled="switching" aria-label="切换工作身份" @change="changeRole($event.target.value)"><option v-for="item in contexts" :key="item.contextId" :value="item.contextId">{{ displayRole(item.roleName, item.roleCode) }}</option></select><span v-else>{{ roleLabel }}</span><button class="bpl-control" type="button" @click="logout">退出</button></div>
    </header>
    <TeacherWorkspaceFrame v-if="ctx" ref="workspaceFrame" :key="ctx.ctxKey" :modules="modules" :workspace-modules="workspaceModules" :centers="centers" :active-center="activeCenter" :active-module="activeModule" :identity-key="identityKey" :scope-name="ctx.dataScope?.scopeName || ''" :resolve-destination="workspaceNavigate" @center-unavailable="openCenter" @tokens="workspaceColors = $event"><slot /></TeacherWorkspaceFrame>
    <ElDialog :model-value="!!pendingCenter" :title="`进入${pendingCenter?.label || ''}`" :show-close="false" width="min(560px, 94vw)" @update:model-value="value => { if (!value) pendingCenter = null }">
      <p>当前工作身份：{{ roleLabel }}</p>
      <p v-if="contextsLoading" role="status">正在核对已授权工作身份……</p>
      <div v-else-if="contextsError" role="alert"><p>{{ contextsError }}</p><button class="bpl-control" @click="loadContexts">重新核对工作身份</button></div>
      <template v-else-if="centerContexts.length"><p>请选择已授权工作身份继续，切换前请保存当前未提交内容。</p><p v-for="item in centerContexts" :key="item.contextId"><button class="bpl-control" :disabled="switching" @click="changeRole(item.contextId, pendingCenter.key)">以{{ displayRole(item.roleName, item.roleCode) }}进入</button></p></template>
      <template v-else><p>当前账号没有此区域的工作身份，请联系学校管理员配置相应职责。</p><p v-if="roleManagementPath"><button class="bpl-control" @click="pendingCenter = null; router.push(roleManagementPath)">配置负责人身份</button></p></template>
      <template #footer><button class="bpl-control" @click="pendingCenter = null">返回当前工作</button></template>
    </ElDialog>
    <main v-if="!ctx" class="bpl-workspace-pending" aria-label="工作区加载状态"><slot /></main>
    <footer v-if="$slots.footer"><slot name="footer" /></footer>
  </div>
</template>
<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { OfficeBuilding, Search } from '@element-plus/icons-vue'
import TeacherWorkspaceFrame from '@/components/workspace/TeacherWorkspaceFrame.vue'
import WorkspaceDeskUtilities from '@/components/workspace/WorkspaceDeskUtilities.vue'
import { workspacePages, workspaceTokens } from '@/components/workspace/teacherWorkspace'
import { activeWorkspacePage } from '@/components/workspace/workspaceRouting'
import { getVisibleNavPlan } from '@/config/navPlan'
import { currentUserFromToken, logoutRemote, fetchMyAuthContexts, switchAuthContext, request } from '@/services/http/client'
import { clearPermissionPatterns } from '@/security/permissionGate'
import { ElDialog, ElMessageBox, ElMessage } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/message/style/css'
import { fileSdk } from '@/services/file/fileSdk'
const props = defineProps({ title: { type: String, required: true }, subtitle: { type: String, default: '' }, menus: { type: Array, default: () => [] }, activeKey: { type: String, default: '' }, hideAside: Boolean, workspace: Boolean, hideGlobalWorkbench: Boolean, workspaceNavigate: { type: Function, default: path => path }, ctx: { type: Object, default: null } })
const service=computed(()=>props.ctx?.service || {})
const logoUrl=ref('');let logoRun=0
function clearLogo(){if(logoUrl.value)URL.revokeObjectURL(logoUrl.value);logoUrl.value=''}
watch(()=>[props.ctx?.ctxKey,props.ctx?.brand?.logoFileId || props.ctx?.tenantBrandConfig?.logoFileId],async([_,id])=>{const run=++logoRun;clearLogo();if(!id)return;try{const blob=await fileSdk.blob(id);if(run===logoRun)logoUrl.value=URL.createObjectURL(blob)}catch{/* 校徽读取失败保留学校文字，不显示旧身份图片。 */}},{immediate:true})
onBeforeUnmount(()=>{++logoRun;clearLogo()})
const emit = defineEmits(['menu-select', 'menu-disabled'])
const route = useRoute(), router = useRouter(), workspaceFrame = ref(null)
const workspaceColors = ref(workspaceTokens('blue')), query = ref('')
const roleLabel = computed(() => { const role = props.ctx?.currentRole; const labels = { SCHOOL_ADMIN: '学校管理员', INTERN_MENTOR: '实习指导教师', TEACHER: '教师', COLLEGE_ADMIN: '院系管理员' }; const name = role?.roleName || ''; return /^[A-Z_]+$/.test(name) ? labels[name] || '学校用户' : name || labels[role?.roleCode] || '学校用户' })
const activeCenter = computed(() => route.path.startsWith('/admin/system') ? 'system' : 'internship')
const visiblePlan = computed(() => getVisibleNavPlan({ permissionPatterns: props.ctx?.permissionPatterns || [], currentRole: props.ctx?.currentRole, ctxKey: props.ctx?.ctxKey || '' }))
const modules = computed(() => visiblePlan.value.find(group => group.key === activeCenter.value)?.children || [])
const workspaceModules = computed(() => visiblePlan.value.flatMap(group => group.children))
const pages = computed(() => workspacePages(workspaceModules.value))
const activeModule = computed(() => activeWorkspacePage(pages.value, route)?.moduleKey || modules.value[0]?.key || '')
const centers = computed(() => [{key:'internship',label:'岗位实习中心'},{key:'system',label:'系统管理'}].map(center => {
  const group = visiblePlan.value.find(group => group.key === center.key)
  return {...center, path: group?.children[0]?.children[0]?.path || group?.children[0]?.path || ''}
}))
const identityKey = computed(() => { const claims = currentUserFromToken(); return 'internship-shell:' + (claims?.tenantId != null && claims?.userId != null ? JSON.stringify([String(claims.tenantId), String(claims.userId), claims.currentRoleCode || '', claims.activeContextId || '']) : props.ctx?.ctxKey || '') })
const results = computed(() => pages.value.filter(item => !item.hidden && !item.workspaceHidden && item.title.includes(query.value)).slice(0, 30))
watch(identityKey, () => { query.value = '' })
watch(() => route.fullPath, () => { query.value = '' })
function select(item) { emit('menu-select', item); const destination = props.workspaceNavigate(item.destination || item.path); if (destination) router.push(destination); query.value = '' }
function selectFirst() { if (results.value.length) select(results.value[0]) }
async function logout() { await logoutRemote(); await router.replace('/login') }
const contexts = ref([]), activeContext = ref(''), switching = ref(false)
const pendingCenter = ref(null), contextsLoading = ref(false), contextsError = ref('')
const centerContexts = computed(() => contexts.value.filter(item => item.enabled && item.contextId !== activeContext.value && getVisibleNavPlan({permissionPatterns:item.permissionPatterns || [],currentRole:item}).some(group => group.key === pendingCenter.value?.key)))
const roleManagementPath = computed(() => pages.value.find(page => page.path === '/admin/system/roles')?.path || '')
let contextRequest = 0
async function loadContexts() {
  const run = ++contextRequest
  contextsLoading.value = true; contextsError.value = ''; contexts.value = []
  try { const me = await fetchMyAuthContexts(); if (run === contextRequest) { contexts.value = me.contexts; activeContext.value = me.activeContextId } }
  catch (e) { if (run === contextRequest) contextsError.value = e.message || '暂时无法核对工作身份，请重试' }
  finally { if (run === contextRequest) contextsLoading.value = false }
}
function openCenter(center) { pendingCenter.value = center; loadContexts() }
onBeforeUnmount(() => { ++contextRequest })
function displayRole(name, code) { return /^[A-Z_]+$/.test(name || '') ? ({ SCHOOL_ADMIN: '校级实习管理员', SYSTEM_ADMIN: '学校系统管理员', COLLEGE_ADMIN: '院系管理员', INTERN_MENTOR: '实习指导教师', COUNSELOR: '班主任／辅导员', STUDENT: '学生' }[code] || '学校工作身份') : name }
onMounted(loadContexts)
async function changeRole(target, centerKey = '') {
  if (switching.value || target === activeContext.value) return
  let roleChanged = false
  try {
    await ElMessageBox.confirm('切换身份会关闭当前工作区，请先保存未提交内容。', '切换工作身份', { confirmButtonText: '切换身份', cancelButtonText: '继续当前工作', showClose: false })
    switching.value = true
    await switchAuthContext(target); roleChanged = true; clearPermissionPatterns()
    const plan = getVisibleNavPlan(await request('/rbac/current-context'))
    const group = centerKey ? plan.find(group => group.key === centerKey) : plan[0]
    const destination = group?.children?.[0]?.children?.[0]?.path || group?.children?.[0]?.path || '/security/403'
    window.location.assign(destination)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e.message || '身份切换失败，请重试')
      if (roleChanged) window.location.assign('/security/500')
    }
  }
  finally { switching.value = false }
}
</script>
<style scoped>
.base-portal-layout{height:100vh;display:flex;flex-direction:column;overflow:hidden;background:var(--bg);color:var(--t1)}
.bpl-topbar{height:60px;flex-shrink:0;display:flex;align-items:center;gap:10px;padding:0 20px;background:var(--surface-2);border-bottom:1px solid var(--line);position:relative;z-index:30}
.bpl-brand{display:flex;align-items:center;gap:12px;flex-shrink:0}.bpl-logo{width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;background:var(--pri);color:var(--pri-on)}.bpl-logo svg{width:25px;height:25px}.bpl-logo img{width:36px;height:36px;object-fit:contain}.bpl-service{position:relative}.bpl-service>summary{cursor:pointer}.bpl-service>div{position:absolute;right:0;top:32px;width:min(360px,80vw);white-space:normal;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:0 8px 30px #0002;max-height:65vh;overflow:auto}.bpl-service p{line-height:1.7}.bpl-brand__nm{font-size:17px;color:var(--t1)}
.bpl-search{flex:1;min-width:0;display:flex;margin:0 10px;max-width:600px}.bpl-cmdk{position:relative;width:100%;height:36px;display:flex;align-items:center;gap:8px;padding:0 12px;border:1px solid var(--line);border-radius:9px;background:var(--surface)}.bpl-ic{width:16px;height:16px;flex-shrink:0}.bpl-cmdk input{width:100%;border:0;background:transparent;outline:0;color:var(--t1)}.bpl-cmdk__panel{position:absolute;top:42px;left:0;right:0;padding:8px;max-height:360px;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:9px;box-shadow:0 8px 24px #10203020}.bpl-cmdk__panel button{width:100%;display:flex;justify-content:space-between;gap:12px;padding:10px;border:0;border-radius:6px;background:transparent;color:var(--t1);cursor:pointer}.bpl-cmdk__panel button:hover{background:var(--pri-50)}.bpl-cmdk__panel small,.bpl-cmdk__panel p{color:var(--t3)}
.bpl-top-r{display:flex;align-items:center;gap:14px;margin-left:auto;white-space:nowrap;font-size:13px}.bpl-control{padding:6px 10px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--t1);cursor:pointer}.bpl-workspace-pending{flex:1;min-height:0;overflow:auto;padding:24px}
@media(max-width:1250px){.bpl-brand__nm{font-size:14px}.bpl-search{margin:0 2px}}@media(max-width:900px){.bpl-topbar{padding:0 10px}.bpl-brand__nm{display:none}.bpl-top-r{gap:6px}}
</style>
