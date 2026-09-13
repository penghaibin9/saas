<template>
  <div class="tw-frame" :class="{ focused, 'mobile-open': mobileOpen }" :style="tokens">
    <div class="tw-centers"><nav aria-label="一级菜单"><button v-for="center in centers" :key="center.key" :class="{ selected: center.key === activeCenter }" @click="navigate(center.path)">{{ center.label }}</button></nav><WorkspaceDeskUtilities scope-mode :scope-name="scopeName" :identity-key="identityKey" /></div>
    <div class="tw-body">
      <div class="tw-rails">
        <aside v-for="level in railLevels" :key="level.key" class="tw-rail" :class="[prefs[level.key], { tertiary: level.key === 'third' }]" :aria-label="level.title">
          <div class="tw-rail-body">
            <button class="tw-expand" :aria-label="`${prefs[level.key] === 'full' ? '收窄' : '展开'}${level.title}`" @click="prefs[level.key] = prefs[level.key] === 'full' ? 'compact' : 'full'"><span aria-hidden="true">{{ prefs[level.key] === 'full' ? '«' : '»' }}</span><strong class="full-label">{{ level.heading }}</strong></button>
            <div v-if="level.key === 'third' && hasSecondaryMenu" class="tw-directory-controls">
              <button type="button" :aria-expanded="expandedMenu" @click="expandedMenu = !expandedMenu; menuQuery = ''">{{ expandedMenu ? '收起完整目录' : '全部业务与设置' }}</button>
              <input v-if="expandedMenu" v-model="menuQuery" type="search" aria-label="搜索本模块业务" placeholder="搜索本模块业务" />
            </div>
            <nav :aria-label="level.title"><template v-for="(item, index) in level.items" :key="item.id || item.key"><p v-if="level.key === 'third' && expandedMenu && item.menuSection && item.menuSection !== level.items[index - 1]?.menuSection" class="tw-directory-section">{{ item.menuSection }}</p><button :title="item.disabled ? `${item.label} · ${item.badge || '暂不可用'}` : item.label" :disabled="item.disabled || (level.key === 'third' && !item.path)" :aria-label="item.disabled ? `${item.label} · ${item.badge || '暂不可用'}` : item.label" :class="{ selected: level.active === (item.id || item.key) }" :aria-current="level.active === (item.id || item.key) ? 'page' : undefined" @click="selectItem(level.key, item)"><component v-if="level.key === 'second'" :is="menuIcon(item)" class="tw-menu-icon" :class="{ 'tw-menu-icon--configured': MENU_ICONS[item.menuIcon] }" aria-hidden="true" /><span class="short-label">{{ workspaceShort(item) }}</span><span class="full-label">{{ item.label }}</span></button></template><p v-if="menuQuery && !level.items.length" class="tw-directory-section">未找到相关业务</p></nav>
          </div>
          <button class="tw-pin" :aria-label="`${prefs[level.key] === 'auto' ? '固定' : '取消固定'}${level.title}`" :aria-pressed="prefs[level.key] !== 'auto'" @click="prefs[level.key] = prefs[level.key] === 'auto' ? 'compact' : 'auto'">{{ prefs[level.key] === 'auto' ? '固定' : '已固定' }}</button>
        </aside>
      </div>
      <div class="tw-working">
        <div class="tw-tabbar"><button class="tw-menu-toggle" @click="mobileOpen = !mobileOpen">目录</button><div class="tw-tabs" role="tablist" aria-label="已打开页面" @keydown="tabKeydown"><div v-for="item in openPages" :key="item.id" class="tw-tab" :class="{ selected: item.id === currentPage?.id }"><button role="tab" :aria-selected="item.id === currentPage?.id" :tabindex="item.id === currentPage?.id ? 0 : -1" :title="`${item.trail} / ${item.title}`" @click="navigate(item.id)"><component :is="menuIcon(item)" class="tw-tab-icon" /><span>{{ item.title }}</span></button><button :aria-label="`关闭${item.title}`" @click="closePage(item)"><Close class="tw-tab-icon" /></button></div></div><div class="tw-tab-actions"><button :disabled="!closedId" title="恢复最近关闭的页签" aria-label="恢复最近关闭的页签" @click="reopen"><RefreshLeft /></button><button :disabled="!currentPage" :aria-pressed="prefs.shortcuts.includes(currentPage?.id)" :aria-label="prefs.shortcuts.includes(currentPage?.id) ? '取消收藏' : '收藏当前页面'" title="收藏当前页面" @click="toggleShortcut"><Star /></button><button :aria-pressed="focused" :aria-label="focused ? '退出专注' : '专注模式'" title="专注模式" @click="focused = !focused"><FullScreen /></button></div></div>
        <nav v-if="horizontalLevel" class="tw-module-tabs" :aria-label="horizontalLevel.heading">
          <button v-for="item in horizontalLevel.items" :key="item.id" :disabled="item.disabled || !item.path" :aria-current="horizontalLevel.active === item.id ? 'page' : undefined" :title="item.disabled ? item.badge : undefined" @click="selectItem('third', item)">{{ item.label }}</button>
        </nav>
        <main ref="mainElement" class="tw-main" tabindex="-1" @scroll="rememberScroll">
          <section v-if="route.path === '/workbench' && route.query.view === 'recent'" class="tw-recent"><header><h1>最近访问</h1><button @click="prefs.recent = []">清空记录</button></header><p v-if="!prefs.recent.length">暂无访问记录</p><button v-for="id in prefs.recent" :key="id" class="tw-recent-row" @click="navigate(id)"><span>{{ pages.find(page => page.id === id)?.title }}</span><small>{{ pages.find(page => page.id === id)?.trail }}</small></button></section>
          <slot v-else />
        </main>
        <div class="tw-dock-wrap"><button v-if="prefs.collapsed" class="tw-pill" @click="prefs.collapsed = false">我的常用<span aria-hidden="true">⌃</span></button><nav v-else class="tw-dock" aria-label="快捷操作"><span class="tw-dock-title">我的<br />常用</span><button v-for="item in shortcuts" :key="item.id" :title="`${item.trail} / ${item.title}`" @click="navigate(item.id)"><span class="tw-shortcut-icon" :style="{ background: WORKSPACE_TONES[shortcutAppearance(item, prefs.appearance).color].value }"><component :is="SHORTCUT_ICONS[shortcutAppearance(item, prefs.appearance).icon]" /></span><span>{{ prefs.appearance[item.id]?.label || item.title }}</span></button><div class="tw-dock-tools"><button aria-label="编辑快捷栏" @click="shortcutsDialog.open()">编辑</button><button aria-label="收起快捷栏" @click="prefs.collapsed = true">收起</button></div></nav></div>
      </div>
    </div>
    <dialog ref="appearance" class="tw-dialog"><form method="dialog" class="tw-dialog-head"><h2>外观设置</h2><button aria-label="关闭外观设置">×</button></form><div class="tw-themes"><button v-for="theme in WORKSPACE_THEMES" :key="theme.key" :aria-pressed="prefs.theme === theme.key" @click="prefs.theme = theme.key"><span><i v-for="color in [theme.bg, theme.surface, theme.soft, theme.accent]" :key="color" :style="{ background: color }" /></span><strong>{{ theme.label }}</strong></button></div><p>菜单宽度、配色与常用入口保存在当前浏览器。</p><button class="tw-text-button" @click="reset">恢复默认设置</button></dialog>
    <WorkspaceShortcutEditor ref="shortcutsDialog" :pages="pages" :prefs="prefs" :identity-key="identityKey" @save="saveShortcuts" />
  </div>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import WorkspaceShortcutEditor from './WorkspaceShortcutEditor.vue'
import { SHORTCUT_ICONS } from './shortcutIcons'
import { activeWorkspacePage } from './workspaceRouting'
import WorkspaceDeskUtilities from './WorkspaceDeskUtilities.vue'
import { RefreshLeft, Star, FullScreen, Close, Monitor, User, Calendar, House, Bell, ChatDotRound, Sunny, Help, Coin, DocumentChecked, Collection, DataAnalysis, School, Flag, DataBoard, SetUp, Reading, List, Select, Clock, Tickets, TrendCharts, Medal, Notebook, OfficeBuilding, CircleCheck, FolderChecked } from '@element-plus/icons-vue'
import { WORKSPACE_THEMES, WORKSPACE_TONES, restoreWorkspace, shortcutAppearance, workspacePages, workspaceMenuItems, workspaceShort, workspaceTokens } from './teacherWorkspace'
import { systemConfirm } from '@/services/systemDialog'
const props = defineProps({ horizontalModule: { type: String, default: '' }, modules: { type: Array, default: () => [] }, centers: { type: Array, default: () => [] }, activeCenter: { type: String, default: '' }, activeModule: { type: String, default: '' }, identityKey: { type: String, required: true }, legacyIdentityKey: { type: String, default: '' }, scopeName: { type: String, default: '' } })
const emit = defineEmits(['tokens', 'theme-label'])
const route = useRoute(), router = useRouter()
const pages = computed(() => workspacePages(props.modules))
const storageKey = computed(() => `teacher-workspace-v1:${props.identityKey}${props.activeCenter === 'academic-affairs' ? ':academic-affairs' : ''}`)
const prefs = ref(restoreWorkspace({}, []))
const focused = ref(false), mobileOpen = ref(false), closedId = ref(''), selectedModule = ref('')
const appearance = ref(null), shortcutsDialog = ref(null), mainElement = ref(null)
const MENU_ICONS = { DataBoard, Monitor, SetUp, User, Reading, List, Calendar, Select, Clock, Tickets, TrendCharts, Medal, Notebook, OfficeBuilding, CircleCheck, DataAnalysis, FolderChecked }
function menuIcon(item) {
  if (MENU_ICONS[item.menuIcon]) return MENU_ICONS[item.menuIcon]
  const label = item.label || item.title || ''
  if (/看板|总览|工作台/.test(label)) return Monitor
  if (/学生|主档/.test(label)) return User
  if (/请假|销假/.test(label)) return Calendar
  if (/宿舍|公寓/.test(label)) return House
  if (/风险|预警/.test(label)) return Bell
  if (/谈|家校/.test(label)) return ChatDotRound
  if (/心理/.test(label)) return Sunny
  if (/困难|认定/.test(label)) return Help
  if (/奖|助|贷|减免|补助|发放|勤工/.test(label)) return Coin
  if (/处分|违纪/.test(label)) return DocumentChecked
  if (/班级|辅导员/.test(label)) return School
  if (/迎新/.test(label)) return Flag
  if (/统计/.test(label)) return DataAnalysis
  return Collection
}
function openAppearance() { appearance.value?.showModal() }
defineExpose({ openAppearance })
watch(() => prefs.value.theme, key => emit('theme-label', WORKSPACE_THEMES.find(theme => theme.key === key)?.label || ''), { immediate: true })
const destinations = new Map(), scrollPositions = new Map()
const tokens = computed(() => workspaceTokens(prefs.value.theme))
const currentPage = computed(() => activeWorkspacePage(pages.value, route, props.activeModule))
const currentMenuId = computed(() => pages.value.find(page => page.moduleKey === currentPage.value?.moduleKey && page.path === currentPage.value?.menuParentPath)?.id || currentPage.value?.id)
const expandedMenu = ref(false), menuQuery = ref('')
watch(() => selectedModule.value || props.activeModule, () => { expandedMenu.value = false; menuQuery.value = '' })
const hasSecondaryMenu = computed(() => pages.value.some(item => item.moduleKey === selected.value?.key && item.menuSecondary && !item.workspaceHidden))
const selected = computed(() => props.modules.find(item => item.key === (selectedModule.value || props.activeModule)) || props.modules[0])
const levels = computed(() => [{ key: 'second', title: '二级菜单', heading: props.centers.find(center => center.key === props.activeCenter)?.label || '业务中心', items: props.modules, active: selected.value?.key }, { key: 'third', title: '三级菜单', heading: selected.value?.label, items: workspaceMenuItems(pages.value, selected.value?.key, currentMenuId.value, expandedMenu.value, menuQuery.value), active: expandedMenu.value ? currentPage.value?.id : currentMenuId.value }])
const horizontalLevel = computed(() => props.horizontalModule && selected.value?.key === props.horizontalModule ? levels.value[1] : null)
const railLevels = computed(() => horizontalLevel.value ? levels.value.slice(0, 1) : levels.value)
const openPages = computed(() => prefs.value.tabs.map(id => pages.value.find(item => item.id === id)).filter(Boolean))
const shortcuts = computed(() => prefs.value.shortcuts.map(id => pages.value.find(item => item.id === id)).filter(Boolean))
async function confirmUnsubmitted(to, from) {
  if (to.path === from.path) return true
  if (window.__SAAS_DIRTY_FORM_GUARD__?.handlesRoute?.(from)) return true
  const editing = [...document.querySelectorAll('textarea')].some(field => !field.readOnly && !field.disabled && field.value.trim() && field.getClientRects().length)
  return !editing || await systemConfirm({ title:'确认离开当前工作区', message:'当前表单还有填写内容，继续离开会丢失未提交的内容。', confirmText:'放弃内容并离开', type:'danger' })
}
onBeforeRouteLeave(confirmUnsubmitted)
onBeforeRouteUpdate(confirmUnsubmitted)
watch([storageKey, pages], () => {
  let saved = null
  try { const current = localStorage.getItem(storageKey.value); const legacy = !current && props.legacyIdentityKey ? localStorage.getItem(`teacher-workspace-v1:${props.legacyIdentityKey}`) : null; saved = JSON.parse(current || legacy || 'null') } catch { /* Invalid preferences reset safely. */ }
  prefs.value = restoreWorkspace(saved, pages.value)
  closedId.value = ''; selectedModule.value = ''
  rememberCurrent()
}, { immediate: true })
watch(prefs, value => { try { localStorage.setItem(storageKey.value, JSON.stringify(value)) } catch { /* Browsing works without storage. */ } }, { deep: true })
const originalBodyTokens = new Map()
let mounted = false
function applyBodyTokens(value) {
  for (const [name, color] of Object.entries(value)) {
    if (!originalBodyTokens.has(name)) originalBodyTokens.set(name, document.body.style.getPropertyValue(name))
    document.body.style.setProperty(name, color)
  }
}
watch(tokens, value => { emit('tokens', value); if (mounted) applyBodyTokens(value) }, { immediate: true })
onMounted(() => { mounted = true; applyBodyTokens(tokens.value) })
onBeforeUnmount(() => { mounted = false; for (const [name, value] of originalBodyTokens) { if (value) document.body.style.setProperty(name, value); else document.body.style.removeProperty(name) } })
watch(() => route.fullPath, async path => { selectedModule.value = ''; mobileOpen.value = false; rememberCurrent(); await nextTick(); if (path === route.fullPath && mainElement.value) mainElement.value.scrollTop = scrollPositions.get(currentPage.value?.id) || 0 }, { flush: 'post' })
function rememberScroll() { if (currentPage.value) scrollPositions.set(currentPage.value.id, mainElement.value?.scrollTop || 0) }
function rememberCurrent() { const id = currentPage.value?.id; if (id && !currentPage.value.disabled && id !== '/workbench?view=recent') prefs.value.recent = [id, ...prefs.value.recent.filter(key => key !== id)].slice(0, 30); if (id && new URL(currentPage.value.path, window.location.origin).pathname === route.path) destinations.set(id, route.fullPath); if (id && !currentPage.value.disabled && !prefs.value.tabs.includes(id)) prefs.value.tabs = [...prefs.value.tabs, id].slice(-20) }
async function navigate(path) { const page = pages.value.find(item => item.id === path); const destination = destinations.get(path) || page?.destination || page?.path || path; if (destination && destination !== route.fullPath) await router.push(destination); mobileOpen.value = false }
function selectItem(level, item) {
  if (level === 'second') {
    selectedModule.value = item.key
    const first = pages.value.find(page => page.moduleKey === item.key && !page.workspaceHidden && !page.disabled && page.path)
    if (first && currentPage.value?.moduleKey !== item.key) navigate(first.id)
  } else if (!item.disabled && item.path) navigate(item.id)
}
async function closePage(item) {
  const remaining = prefs.value.tabs.filter(id => id !== item.id)
  if (item.id === currentPage.value?.id) {
    const next = remaining.at(-1) || pages.value.find(page => page.id !== item.id)?.id
    if (!next) return
    await navigate(next)
    if (currentPage.value?.id === item.id) return
  }
  const active = currentPage.value?.id
  prefs.value.tabs = active && !remaining.includes(active) ? [...remaining, active] : remaining
  closedId.value = item.id
}
function reopen() { const id = closedId.value; closedId.value = ''; if (pages.value.some(item => item.id === id)) { prefs.value.tabs = [...new Set([...prefs.value.tabs, id])].slice(-20); navigate(id) } }
function toggleShortcut() { const id = currentPage.value?.id; if (!id) return; if (prefs.value.shortcuts.includes(id)) prefs.value.shortcuts = prefs.value.shortcuts.filter(key => key !== id); else if (prefs.value.shortcuts.length < 8) prefs.value.shortcuts.push(id); else shortcutsDialog.value.open() }
function saveShortcuts(value) { prefs.value.appearance = value.appearance; prefs.value.shortcuts = value.shortcuts; prefs.value.collapsed = false }
function reset() { prefs.value = restoreWorkspace({}, pages.value); rememberCurrent() }
function tabKeydown(event) { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || event.target.getAttribute('role') !== 'tab') return; event.preventDefault(); const tabs = [...event.currentTarget.querySelectorAll('[role="tab"]')]; const index = tabs.indexOf(event.target); const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length; tabs[next]?.focus(); tabs[next]?.click() }
</script>
<style scoped>
.tw-directory-controls { padding: 4px 8px 8px; display: grid; gap: 8px; }
.tw-directory-controls button { min-height: 34px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--pri); cursor: pointer; font-size: 12px; }
.tw-directory-controls input { box-sizing: border-box; width: 100%; min-width: 0; height: 36px; padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--t1); }
.tw-directory-section { margin: 12px 10px 4px; color: var(--t3); font-size: 11px; font-weight: 600; }
.tw-rail.compact .tw-directory-controls, .tw-rail.compact .tw-directory-section { display: none; }
.tw-rail.auto .tw-directory-controls, .tw-rail.auto .tw-directory-section { display: none; }
.tw-rail.auto .tw-rail-body:is(:hover, :focus-within) :is(.tw-directory-controls, .tw-directory-section) { display: grid; }

.tw-frame{display:flex;flex-direction:column;flex:1;min-height:0;background:var(--bg);color:var(--t1);font-size:13px}.tw-frame button{font:inherit;cursor:pointer;color:inherit}.tw-frame button:disabled{opacity:.45;cursor:default}.tw-frame button:focus-visible,.tw-frame input:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.tw-centers{height:44px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid var(--line);background:var(--surface-2)}.tw-centers nav{display:flex;gap:8px;overflow:auto}.tw-centers button{background:transparent;border:0;border-radius:6px;padding:9px 16px;white-space:nowrap}.tw-centers .selected{background:var(--pri-50);color:var(--pri);font-weight:650}.tw-appearance{display:flex;gap:6px;align-items:center}
.tw-body{display:flex;min-height:0;flex:1}.tw-rails{display:flex;min-height:0;flex:none}.tw-rail{width:88px;flex:none;position:relative;z-index:12;border-right:1px solid var(--line);background:var(--surface-2);display:flex;flex-direction:column}.tw-rail.tertiary{width:68px;z-index:11}.tw-rail.full{width:204px}.tw-rail-body{display:flex;flex-direction:column;min-height:0;flex:1;background:var(--surface-2)}.tw-expand{display:flex;align-items:center;gap:12px;height:40px;flex:none;border:0;background:transparent;padding:0 21px;color:var(--t3)}.tw-expand>span{font-size:23px}.tw-expand strong{font-size:13px;white-space:nowrap}.tw-rail nav{min-height:0;flex:1;overflow:auto;overflow-x:hidden;padding:4px 6px;scrollbar-width:thin;scrollbar-color:var(--line) transparent}.tw-rail nav button{width:100%;min-height:42px;display:flex;align-items:center;gap:7px;margin:2px 0;padding:0 9px;white-space:nowrap;background:transparent;border:0;border-radius:6px;text-align:left;color:var(--t3)}.tw-rail nav button.selected{background:var(--pri-50);color:var(--pri);box-shadow:inset 2px 0 var(--pri);font-weight:650}.tw-rail nav button:hover{background:var(--pri-50)}.full-label{display:none}.full .full-label{display:inline}.full .short-label{display:none}.tw-rail.tertiary nav button{justify-content:center}.tw-rail.tertiary.full nav button{justify-content:flex-start}.tw-pin{height:44px;flex:none;position:relative;z-index:1;border:0;border-top:1px solid var(--line);background:var(--surface-2);font-size:11px!important;color:var(--pri)!important}
.tw-working{flex:1;min-width:0;display:flex;flex-direction:column;position:relative}.tw-tabbar{height:40px;flex:none;display:flex;align-items:stretch;padding:0 10px;background:var(--surface-2);border-bottom:1px solid var(--line);gap:10px}.tw-tabs{display:flex;overflow:auto;flex:1;scrollbar-width:thin;align-items:stretch;gap:3px}.tw-tab{display:flex;white-space:nowrap;border-bottom:2px solid transparent}.tw-tab.selected{background:var(--pri-50);border-color:var(--pri);border-radius:5px 5px 0 0}.tw-tab button,.tw-tab-actions button,.tw-menu-toggle{border:0;background:transparent;padding:6px 9px;color:var(--t3)}.tw-tab-actions{display:flex;flex:none}.tw-tab-actions button{font-size:12px}.tw-main{overflow:auto;min-height:0;flex:1;padding:14px 18px 78px;scrollbar-width:thin}.tw-menu-toggle{display:none}.tw-frame.focused .tw-rails,.tw-frame.focused .tw-centers{display:none}
.tw-dock-wrap{position:absolute;bottom:14px;left:0;right:0;display:flex;justify-content:center;pointer-events:none;z-index:9}.tw-pill,.tw-dock{pointer-events:auto;background:var(--surface);border:1px solid var(--line);box-shadow:0 5px 20px #172b4612;border-radius:18px}.tw-pill{padding:8px 16px;display:flex;gap:14px;color:var(--t3)}.tw-dock{display:flex;gap:8px;padding:10px 14px;max-width:calc(100% - 28px);overflow:auto}.tw-dock>button{border:0;background:transparent;min-width:78px;display:flex;flex-direction:column;align-items:center;gap:7px;padding:5px 8px;color:var(--pri)}.tw-dock>button .app-icon{box-sizing:content-box;background:var(--pri-50);padding:8px;border-radius:11px}.tw-dock>button span{font-size:12px}.tw-dock-title{font-size:12px;line-height:22px;align-self:center;padding:0 8px;color:var(--t3);white-space:nowrap}.tw-dock-tools{border-left:1px solid var(--line);padding-left:8px;display:flex;flex-direction:column;justify-content:space-evenly}.tw-dock-tools button{border:0;background:transparent;font-size:12px;color:var(--t3)}
.tw-dialog{width:min(590px,calc(100vw - 40px));max-height:80vh;padding:24px;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--t1);box-shadow:0 25px 80px #10182730}.tw-dialog::backdrop{background:#1a273d55;backdrop-filter:blur(3px)}.tw-dialog-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}.tw-dialog h2{margin:0;font-size:20px}.tw-dialog-head button{border:0;background:transparent;font-size:24px}.tw-dialog p{font-size:13px;color:var(--t3);line-height:1.6}.tw-themes{display:grid;grid-template-columns:1fr 1fr;gap:12px}.tw-themes button{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:15px;text-align:left}.tw-themes button[aria-pressed=true]{outline:2px solid var(--pri);background:var(--pri-50)}.tw-themes button>span{display:flex;height:40px;margin-bottom:12px;border-radius:5px;overflow:hidden}.tw-themes i{flex:1}.tw-text-button{border:0;background:transparent;color:var(--pri)!important;padding:8px 0}.tw-shortcut-options{display:flex;flex-direction:column;gap:12px;max-height:34vh;overflow:auto}.tw-shortcut-options label{display:flex;align-items:center;gap:9px}.tw-shortcut-options input{accent-color:var(--pri)}.tw-sort{padding:10px 0 0;list-style:none}.tw-sort li{display:flex;gap:8px;align-items:center;padding:6px 0}.tw-sort input{flex:1;min-width:0;padding:7px;border:1px solid var(--line);border-radius:5px;background:var(--surface-2);color:var(--t1)}.tw-sort select{padding:7px;border:1px solid var(--line);border-radius:5px;background:var(--surface-2);color:var(--t1)}.tw-sort button{border:1px solid var(--line);border-radius:5px;background:var(--surface-2);font-size:12px}
@media(hover:hover){.tw-rail.auto .tw-rail-body:hover,.tw-rail.auto .tw-rail-body:focus-within{position:absolute;inset:0 auto 44px 0;width:204px;border-right:1px solid var(--line);box-shadow:12px 0 24px #172b4614}.tw-rail.auto .tw-rail-body:hover .full-label,.tw-rail.auto .tw-rail-body:focus-within .full-label{display:inline}.tw-rail.auto .tw-rail-body:hover .short-label,.tw-rail.auto .tw-rail-body:focus-within .short-label{display:none}.tw-rail.auto.tertiary .tw-rail-body:hover button{justify-content:flex-start}}
@media(max-width:900px){.tw-centers{padding:0 10px}.tw-centers button{padding:9px}.tw-rails{display:none}.tw-menu-toggle{display:block}.mobile-open .tw-rails{display:flex;position:absolute;inset:100px auto 0 0;z-index:25}.tw-tab-actions button{padding:5px}.tw-main{padding:12px 10px 78px}}
.tw-module-tabs{display:flex;gap:20px;flex-shrink:0;overflow-x:auto;padding:0 20px;background:var(--surface);border-bottom:1px solid var(--line)}
.tw-module-tabs button{flex-shrink:0;border:0;border-bottom:3px solid transparent;background:none;color:var(--t3);font:inherit;padding:16px 2px;cursor:pointer}
.tw-module-tabs button[aria-current=page]{color:var(--pri);border-bottom-color:var(--pri);font-weight:650}
.tw-module-tabs button:focus-visible{outline:2px solid var(--pri);outline-offset:-3px}
.tw-module-tabs button:disabled{opacity:.5;cursor:not-allowed}
</style>

<style scoped>
.tw-directory-controls { padding: 4px 8px 8px; display: grid; gap: 8px; }
.tw-directory-controls button { min-height: 34px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--pri); cursor: pointer; font-size: 12px; }
.tw-directory-controls input { box-sizing: border-box; width: 100%; min-width: 0; height: 36px; padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--t1); }
.tw-directory-section { margin: 12px 10px 4px; color: var(--t3); font-size: 11px; font-weight: 600; }
.tw-rail.compact .tw-directory-controls, .tw-rail.compact .tw-directory-section { display: none; }
.tw-rail.auto .tw-directory-controls, .tw-rail.auto .tw-directory-section { display: none; }
.tw-rail.auto .tw-rail-body:is(:hover, :focus-within) :is(.tw-directory-controls, .tw-directory-section) { display: grid; }

.tw-centers{height:44px;padding:0 22px;overflow:visible;background:var(--surface);gap:16px;position:relative;z-index:22}
.tw-centers nav{gap:8px;min-width:0}.tw-centers nav button{padding:9px 14px;font-size:14px;color:var(--t3)}.tw-centers nav button.selected{color:var(--pri)}
.tw-menu-icon{width:17px;height:17px;flex:none}
.tw-menu-icon--configured{box-sizing:border-box;width:28px;height:28px;padding:5px;border-radius:8px;background:var(--pri-bg);color:var(--pri)}
.tw-rail nav button.selected .tw-menu-icon--configured{background:var(--pri);color:var(--pri-on)}
.tw-tab-icon{width:14px;height:14px;flex:none}
.tw-tabbar{height:36px;padding:0 14px;gap:6px;background:var(--surface)}.tw-tabs{scrollbar-width:none;align-items:stretch}.tw-tabs::-webkit-scrollbar{display:none}
.tw-tab{position:relative;max-width:204px;min-width:98px;margin:3px 0;border:1px solid transparent;border-radius:5px;color:var(--t3)}.tw-tab.selected{border:1px solid var(--line);border-radius:5px;color:var(--pri)}.tw-tab.selected:after{content:'';position:absolute;bottom:-4px;left:9px;right:9px;height:2px;background:var(--pri);border-radius:2px}
.tw-tab button[role=tab]{display:flex;align-items:center;gap:6px;min-width:0;padding:0 6px 0 9px;font-size:12px;color:inherit}.tw-tab button[role=tab] span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.tw-tab button:not([role=tab]){display:flex;align-items:center;justify-content:center;width:24px;padding:4px;flex:none}
.tw-tab-actions{align-items:center;gap:4px}.tw-tab-actions button{width:28px;height:28px;display:flex;align-items:center;justify-content:center;padding:5px;border-radius:5px}.tw-tab-actions svg{width:17px;height:17px}.tw-tab-actions button:hover{background:var(--pri-50)}.tw-tab-actions button[aria-pressed=true]{color:var(--pri);background:var(--pri-50)}.tw-tab-actions button:disabled{opacity:.35}
.tw-main{padding-top:12px}.tw-rail nav button{min-height:38px;font-size:12px}.tw-expand{height:48px}.tw-pin{height:32px}.tw-rail nav{scrollbar-width:none}
.tw-recent header{display:flex;justify-content:space-between;align-items:center}.tw-recent h1{font-size:20px}.tw-recent button{background:transparent;border:0;color:var(--pri);cursor:pointer}.tw-recent-row{display:flex;width:100%;padding:16px 8px;gap:24px;border-bottom:1px solid var(--line)!important;text-align:left}.tw-recent-row span{flex:1}.tw-recent-row small{color:var(--t3)}
.tw-rail.full{width:152px;flex-basis:152px}
.tw-rail .full-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(hover:hover){.tw-rail.auto .tw-rail-body:hover,.tw-rail.auto .tw-rail-body:focus-within{width:152px}}
.tw-shortcut-icon{display:grid;place-items:center;width:36px;height:36px;border-radius:11px;color:#fff;flex:none}.tw-shortcut-icon svg{width:22px;height:22px}.tw-dock>button>span:last-child{max-width:84px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--t3)}
</style>
