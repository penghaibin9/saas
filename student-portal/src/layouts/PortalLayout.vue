<template>
  <div class="sp-shell student-workspace" :class="shellClasses">
    <a class="workspace-skip" href="#student-workspace-main" @click.prevent="mainElement?.focus()">跳到工作区</a>
    <header class="workspace-header">
      <a class="workspace-brand" :href="homeHref" @click.prevent="navigate('/home')">
        <img v-if="brand.logo" :src="brand.logo" alt="学校标识" />
        <span v-else class="workspace-logo"><WorkspaceIcon name="employment" /></span>
        <strong :title="brand.platformName || cfg.portalName">{{ brand.platformName || cfg.portalName }}</strong>
      </a>
      <button class="workspace-search" @click="openDialog(searchDialog)"><WorkspaceIcon name="hall" /><span>搜索我的事项或服务</span><kbd>Ctrl K</kbd></button>
      <time class="workspace-clock" :datetime="now.toISOString()">{{ clockText }}</time>
      <button class="workspace-message" :disabled="!cfg.isModuleEnabled('messages')" aria-label="消息通知" title="消息通知" @click="navigate('/messages')"><WorkspaceIcon name="messages" /><span v-if="unread > 0" class="workspace-badge">{{ unread > 99 ? '99+' : unread }}</span></button>
      <button class="workspace-account" aria-label="打开学生账户" @click="openDialog(accountDialog)"><span class="workspace-avatar">{{ initial }}</span><span class="workspace-account-name"><strong>{{ user?.realName || '同学' }}</strong><small>在读学生</small></span><span aria-hidden="true">⌄</span></button>
    </header>
    <div class="workspace-centerbar">
      <nav aria-label="一级菜单"><button v-for="center in centers" :key="center.id" :class="{ selected: center.id === activeCenter.id }" :aria-current="center.id === activeCenter.id ? 'true' : undefined" @click="selectCenter(center)">{{ center.title }}</button></nav>
      <div class="workspace-utilities"><span title="所有业务仅限当前学生本人">本人范围</span><button :aria-pressed="timerPaused" :title="timerPaused ? '继续本次计时' : '暂停本次计时'" @click="timerPaused = !timerPaused">{{ timerPaused ? '已暂停' : '本次使用' }} <time>{{ durationText }}</time></button></div>
    </div>
    <div class="workspace-body">
      <button v-if="mobileNav" class="workspace-nav-backdrop" aria-label="关闭业务导航" @click="mobileNav = false" />
      <div class="workspace-rails" :class="{ 'mobile-open': mobileNav }">
        <WorkspaceRail v-model:mode="prefs.second" label="二级菜单" :title="activeCenter.title" :items="activeCenter.groups" :active="activeGroup.id" @select="selectGroup" />
        <WorkspaceRail v-model:mode="prefs.third" label="三级菜单" :title="activeGroup.title" :items="activeGroup.pages" :active="currentPage?.id" tertiary @select="item => navigate(item.to)" />
      </div>
      <div class="workspace-working">
        <div class="workspace-tabbar">
          <button class="workspace-menu-toggle" :aria-expanded="mobileNav" aria-label="打开业务导航" @click="mobileNav = !mobileNav">目录</button>
          <div ref="tabStrip" class="workspace-tabs" role="tablist" aria-label="已打开页面" @keydown="onTabKeydown">
            <div v-for="item in openPages" :key="item.id" class="workspace-tab" :class="{ selected: item.to === route.fullPath || item.id === currentPage?.id }">
              <button role="tab" :aria-selected="item.id === currentPage?.id" :tabindex="item.id === currentPage?.id ? 0 : -1" :title="`${item.trail} / ${item.title}`" @click="navigate(item.to)">{{ item.title }}<span v-if="edited && item.id === currentPage?.id" class="workspace-edited" aria-label="本页有编辑操作">●</span></button>
              <button v-if="item.id !== 'home'" class="workspace-close" :aria-label="`关闭${item.title}`" @click="closePage(item)">×</button>
            </div>
          </div>
          <div class="workspace-tab-actions"><button :disabled="!recentlyClosed" title="重新打开已关闭页签" aria-label="恢复关闭页签" @click="reopenPage">恢复</button><button :disabled="!currentPage || currentPage.id === 'current'" :aria-pressed="prefs.shortcuts.includes(currentPage?.id)" title="加入或移出快捷栏" @click="toggleShortcut(currentPage.id)">{{ prefs.shortcuts.includes(currentPage?.id) ? '已收藏' : '收藏' }}</button><button :aria-pressed="focusMode" @click="focusMode = !focusMode">{{ focusMode ? '退出专注' : '专注' }}</button></div>
        </div>
        <main id="student-workspace-main" ref="mainElement" class="workspace-main" tabindex="-1" :aria-label="currentTitle" @input.capture="markEdited" @change.capture="markEdited">
          <div class="workspace-watermark" :style="{ backgroundImage: wmUri }" aria-hidden="true" />
          <div class="sp-content"><div class="sp-content__page"><router-view /></div></div>
        </main>
        <div class="workspace-dock-wrap">
          <button v-if="prefs.collapsed" class="workspace-dock-pill" @click="prefs.collapsed = false">我的常用 <span aria-hidden="true">⌃</span></button>
          <nav v-else class="workspace-dock" aria-label="快捷操作">
            <span class="workspace-dock-label">我的<br />常用</span>
            <div class="workspace-dock-items"><button v-for="item in shortcuts" :key="item.id" :title="`${item.trail} / ${item.title}`" @click="navigate(item.to)"><span class="workspace-dock-icon" :class="`tone-${prefs.appearance[item.id]?.color || 'blue'}`"><WorkspaceIcon :name="item.id" /></span><span>{{ prefs.appearance[item.id]?.label || item.title }}</span></button></div>
            <div class="workspace-dock-tools"><button aria-label="编辑快捷栏" @click="openShortcutEditor">编辑</button><button aria-label="收起快捷栏" @click="prefs.collapsed = true">收起</button></div>
          </nav>
        </div>
      </div>
    </div>

    <dialog ref="leaveDialog" class="workspace-dialog workspace-account-dialog" aria-labelledby="workspace-leave-title" @cancel.prevent="resolveLeave(false)">
      <h2 id="workspace-leave-title">离开当前页面？</h2>
      <p class="workspace-setting-hint">当前页面有编辑操作，请确认已保存。离开后未提交的内容会丢失。</p>
      <div class="workspace-dialog-footer"><button autofocus @click="resolveLeave(false)">继续编辑</button><button class="workspace-primary-button" @click="resolveLeave(true)">确认离开</button></div>
    </dialog>
    <dialog ref="searchDialog" class="workspace-dialog workspace-search-dialog" aria-labelledby="workspace-search-title" @click="dismissBackdrop($event)">
      <form method="dialog" class="workspace-dialog-heading"><h2 id="workspace-search-title">查找我的服务</h2><button aria-label="关闭搜索">×</button></form>
      <input v-model="search" class="workspace-search-input" type="search" aria-label="搜索我的事项或服务" placeholder="输入事项名称，例如请假、材料、课表" autofocus @keydown.down.prevent="focusSearchResult" />
      <div class="workspace-search-results"><p v-if="!results.length" class="workspace-empty">没有找到相关事项，试试其他名称。</p><button v-for="item in results" :key="item.id" @click="openSearchResult(item)"><WorkspaceIcon :name="item.id" /><span><strong>{{ item.title }}</strong><small>{{ item.trail }}</small></span><span aria-hidden="true">→</span></button></div>
    </dialog>
    <dialog ref="accountDialog" class="workspace-dialog workspace-account-dialog" aria-labelledby="workspace-account-title" @click="dismissBackdrop($event)">
      <form method="dialog" class="workspace-dialog-heading"><h2 id="workspace-account-title">我的账户</h2><button aria-label="关闭账户">×</button></form>
      <div class="workspace-account-summary"><span class="workspace-avatar">{{ initial }}</span><div><strong>{{ user?.realName || '同学' }}</strong><p>{{ brand.schoolName || cfg.portalName }}</p><small>学生 · 数据范围仅限本人</small></div></div>
      <button class="workspace-setting-row" @click="accountDialog.close(); openDialog(appearanceDialog)"><span>外观设置</span><small>{{ themeName }} →</small></button>
      <button class="workspace-setting-row" @click="accountDialog.close(); openShortcutEditor()"><span>编辑我的快捷栏</span><small>{{ shortcuts.length }} 个入口 →</small></button>
      <button class="workspace-setting-row workspace-danger" :disabled="loggingOut" @click="logout">{{ loggingOut ? '正在退出…' : '退出登录' }}</button>
    </dialog>
    <dialog ref="appearanceDialog" class="workspace-dialog" aria-labelledby="workspace-appearance-title" @click="dismissBackdrop($event)">
      <form method="dialog" class="workspace-dialog-heading"><h2 id="workspace-appearance-title">外观设置</h2><button aria-label="关闭外观设置">×</button></form>
      <div class="workspace-theme-grid" role="group" aria-label="切换门户主题"><button v-for="theme in WORKSPACE_THEMES" :key="theme.key" class="sp-theme-switch__item" :aria-label="`切换为${theme.label}`" :aria-pressed="themeKey === theme.key" @click="selectTheme(theme.key)"><span class="workspace-theme-swatches"><i v-for="color in [theme.bg, theme.surface, theme.soft, theme.accent]" :key="color" :style="{ background: color }" /></span><strong>{{ theme.label }}<span v-if="themeKey === theme.key" aria-hidden="true">✓</span></strong><small>{{ theme.description }}</small></button></div>
      <p class="workspace-setting-hint">配色、菜单宽度和快捷栏保存在当前浏览器。</p><button class="workspace-text-button" @click="resetPreferences">恢复界面默认设置</button>
    </dialog>
    <dialog ref="shortcutsDialog" class="workspace-dialog" aria-labelledby="workspace-shortcuts-title" @click="dismissBackdrop($event)">
      <form method="dialog" class="workspace-dialog-heading"><h2 id="workspace-shortcuts-title">编辑我的快捷栏</h2><button aria-label="关闭快捷栏编辑">×</button></form>
      <p class="workspace-setting-hint">最多 8 个入口。可以改名称、颜色和顺序。</p>
      <div class="workspace-shortcut-editor"><div v-for="(id, index) in shortcutDraft.shortcuts" :key="id" class="workspace-shortcut-row"><input v-model="shortcutDraft.appearance[id].label" :placeholder="pageById(id)?.title" :aria-label="`${pageById(id)?.title}的快捷名称`" maxlength="12" /><select v-model="shortcutDraft.appearance[id].color" :aria-label="`${pageById(id)?.title}的颜色`"><option v-for="(color, key) in colorLabels" :key="key" :value="key">{{ color }}</option></select><button :disabled="index === 0" :aria-label="`上移${pageById(id)?.title}`" @click="moveShortcut(index, -1)">↑</button><button :disabled="index === shortcutDraft.shortcuts.length - 1" :aria-label="`下移${pageById(id)?.title}`" @click="moveShortcut(index, 1)">↓</button><button :aria-label="`移除${pageById(id)?.title}`" @click="shortcutDraft.shortcuts.splice(index, 1)">×</button></div></div>
      <label class="workspace-add-shortcut">添加事项<select :disabled="shortcutDraft.shortcuts.length >= 8" aria-label="添加快捷事项" @change="addDraftShortcut($event)"><option value="">选择一个事项</option><option v-for="item in pages.filter(item => !shortcutDraft.shortcuts.includes(item.id))" :key="item.id" :value="item.id">{{ item.title }} · {{ item.trail }}</option></select></label>
      <div class="workspace-dialog-footer"><button @click="shortcutsDialog.close()">取消</button><button class="workspace-primary-button" @click="saveShortcuts">保存快捷栏</button></div>
    </dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkspaceIcon from '../components/workspace/WorkspaceIcon.vue'
import WorkspaceRail from '../components/workspace/WorkspaceRail.vue'
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { useUiStore } from '../stores/ui'
import { portalApi } from '../services/portalApi'
import { availableCenters, flattenPages, normalizePreferences, pageForRoute, searchPages } from '../platform/workspaceNavigation'
import { normalizeTheme, WORKSPACE_THEMES } from '../platform/workspaceTheme'
import '../styles/student-workspace.css'

const route = useRoute(), router = useRouter(), cfg = usePortalConfigStore(), session = useSessionStore(), ui = useUiStore()
const brand = computed(() => cfg.brand), user = computed(() => session.user)
const initial = computed(() => (user.value?.realName || '学').slice(0, 1))
const centers = computed(() => availableCenters(cfg.config)), pages = computed(() => flattenPages(centers.value))
const pageById = id => pages.value.find(item => item.id === id)
const prefs = ref(normalizePreferences(null, pages.value)), search = ref(''), unread = ref(0), focusMode = ref(false), mobileNav = ref(false)
const themeKey = ref('blue'), themeName = computed(() => WORKSPACE_THEMES.find(item => item.key === themeKey.value)?.label)
const recentlyClosed = ref(''), transientPage = ref(null), mainElement = ref(null), tabStrip = ref(null), edited = ref(false), loggingOut = ref(false)
const leaveDialog = ref(null)
const searchDialog = ref(null), accountDialog = ref(null), appearanceDialog = ref(null), shortcutsDialog = ref(null)
const shortcutDraft = ref(normalizePreferences(null, pages.value))
const colorLabels = { blue: '学院蓝', teal: '松石绿', purple: '柔紫', amber: '琥珀', coral: '珊瑚' }
const now = ref(new Date()), elapsed = ref(0), timerPaused = ref(false)
const clockText = computed(() => new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).format(now.value))
const durationText = computed(() => [Math.floor(elapsed.value / 3600), Math.floor(elapsed.value / 60) % 60, elapsed.value % 60].map(value => String(value).padStart(2, '0')).join(':'))
const currentPage = computed(() => pageForRoute(route, pages.value) || transientPage.value)
const currentTitle = computed(() => currentPage.value?.title || '我的服务')
const activeCenter = computed(() => centers.value.find(item => item.id === currentPage.value?.centerId) || centers.value[0])
const activeGroup = computed(() => activeCenter.value.groups.find(item => item.id === currentPage.value?.groupId) || activeCenter.value.groups[0])
const openPages = computed(() => [...prefs.value.tabs.map(pageById).filter(Boolean), ...(transientPage.value ? [transientPage.value] : [])])
const shortcuts = computed(() => prefs.value.shortcuts.map(pageById).filter(Boolean))
const results = computed(() => searchPages(pages.value, search.value, activeCenter.value.id, prefs.value.tabs))
const homeHref = computed(() => router.resolve('/home').href)
const rawModule = computed(() => route.meta?.modulePath || route.path.split('/')[1] || 'home')
const shellClasses = computed(() => ({ 'is-home': route.name === 'home', 'workspace-focus': focusMode.value, 'dock-collapsed': prefs.value.collapsed, [`route-${rawModule.value}`]: true, [`view-${String(route.name || 'page')}`]: true }))
// 不保存表单值、搜索内容、消息、动态详情 URL 或学生资料。账号与学校隔离个人偏好。
const preferenceKey = computed(() => user.value?.userId ? `sp-workspace-v1:${encodeURIComponent(String(cfg.config?.tenantId || brand.value.schoolName || 'school'))}:${user.value.userId}` : '')
const xmlEscape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[char]))
const wmUri = computed(() => `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="310" height="210"><text x="4" y="110" fill="${themeKey.value === 'dark' ? '#ffffff' : '#263c31'}" fill-opacity="0.035" font-size="14" font-family="sans-serif" transform="rotate(-24 4 110)">${xmlEscape(brand.value.watermark || user.value?.realName || '学生')} · 本人范围</text></svg>`)}")`)

function selectTheme(key) {
  themeKey.value = normalizeTheme(key)
  prefs.value.theme = themeKey.value
  window.dispatchEvent(new CustomEvent('student-portal-theme-change', { detail: themeKey.value }))
}
function readPreferences() {
  let saved = null
  try { saved = preferenceKey.value ? JSON.parse(localStorage.getItem(preferenceKey.value) || 'null') : null } catch { /* 存储不可用时仍可使用当前会话 */ }
  prefs.value = normalizePreferences(saved, pages.value)
  let legacyTheme = 'blue'
  try { legacyTheme = localStorage.getItem('student-portal-theme') || 'blue' } catch { /* 无存储权限 */ }
  selectTheme(saved?.theme || legacyTheme)
}
watch(preferenceKey, () => { edited.value = false; recentlyClosed.value = ''; transientPage.value = null; unread.value = 0; readPreferences(); rememberRoute() }, { immediate: true })
watch(pages, () => { prefs.value = normalizePreferences(prefs.value, pages.value); rememberRoute() })
watch(prefs, value => {
  if (!preferenceKey.value) return
  try { localStorage.setItem(preferenceKey.value, JSON.stringify(normalizePreferences(value, pages.value))) } catch { /* 关闭持久化不影响办理 */ }
}, { deep: true })
function rememberRoute() {
  const page = pageForRoute(route, pages.value)
  if (page) {
    transientPage.value = null
    if (!prefs.value.tabs.includes(page.id)) prefs.value.tabs = [...prefs.value.tabs, page.id].slice(-16)
  } else {
    const modulePage = pages.value.find(item => item.to.split('?')[0] === `/${rawModule.value}`)
    const titles = { 'module-disabled': '模块未开通', 'not-enabled': '门户未开通', 'internship-selection-company': '企业详情', 'business-form': '业务表单' }
    transientPage.value = { id: 'current', title: titles[route.name] || route.meta?.academicTitle || '事项详情', to: route.fullPath, trail: modulePage?.trail || '我的服务', centerId: modulePage?.centerId || 'student', groupId: modulePage?.groupId || 'work' }
  }
  nextTick(() => tabStrip.value?.querySelector('.selected')?.scrollIntoView({ block: 'nearest', inline: 'nearest' }))
}
watch(() => route.fullPath, () => { mobileNav.value = false; edited.value = false; rememberRoute(); nextTick(() => { if (mainElement.value) mainElement.value.scrollTop = 0 }) }, { immediate: true })
function navigate(to) { return router.push(to) }
function selectCenter(center) { navigate(center.groups[0].pages[0].to) }
function selectGroup(group) { navigate(group.pages[0].to) }
async function closePage(item) {
  if (item.id === currentPage.value?.id) {
    const others = openPages.value.filter(page => page.id !== item.id)
    const failure = await navigate(others.at(-1)?.to || '/home')
    if (failure) return
  }
  prefs.value.tabs = prefs.value.tabs.filter(id => id !== item.id)
  recentlyClosed.value = pageById(item.id) ? item.id : ''
}
function reopenPage() { const page = pageById(recentlyClosed.value); if (page) navigate(page.to); recentlyClosed.value = '' }
function onTabKeydown(event) {
  if (event.target.getAttribute('role') !== 'tab' || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  const buttons = [...tabStrip.value.querySelectorAll('[role="tab"]')], index = buttons.indexOf(event.target)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length
  event.preventDefault(); buttons[next]?.focus(); buttons[next]?.click()
}
function openDialog(element) { element?.showModal() }
function dismissBackdrop(event) { if (event.target === event.currentTarget) { const box = event.currentTarget.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) event.currentTarget.close() } }
function focusSearchResult() { searchDialog.value?.querySelector('.workspace-search-results button')?.focus() }
async function openSearchResult(item) { const failure = await navigate(item.to); if (!failure) searchDialog.value.close() }
function toggleShortcut(id) {
  if (prefs.value.shortcuts.includes(id)) prefs.value.shortcuts = prefs.value.shortcuts.filter(value => value !== id)
  else if (prefs.value.shortcuts.length >= 8) ui.notify('快捷栏最多 8 个入口，请先移除一个')
  else { prefs.value.shortcuts.push(id); prefs.value.appearance[id] = { label: '', color: 'blue' } }
}
function openShortcutEditor() { shortcutDraft.value = normalizePreferences(prefs.value, pages.value); openDialog(shortcutsDialog.value) }
function moveShortcut(index, delta) { const list = shortcutDraft.value.shortcuts; [list[index], list[index + delta]] = [list[index + delta], list[index]] }
function addDraftShortcut(event) { const id = event.target.value; if (pageById(id) && shortcutDraft.value.shortcuts.length < 8) { shortcutDraft.value.shortcuts.push(id); shortcutDraft.value.appearance[id] = { label: '', color: 'blue' } } event.target.value = '' }
function saveShortcuts() { const draft = normalizePreferences(shortcutDraft.value, pages.value); prefs.value.shortcuts = draft.shortcuts; prefs.value.appearance = draft.appearance; shortcutsDialog.value.close(); ui.notify('快捷栏已保存') }
function resetPreferences() { const tabs = prefs.value.tabs; prefs.value = normalizePreferences(null, pages.value); prefs.value.tabs = tabs; selectTheme('blue'); ui.notify('界面设置已恢复默认') }
// 跨业务页不缓存组件，避免 useRoute 监听和后台请求在隐藏页面继续运行。
// 离开编辑过的页面前明确确认；草稿内容留在当前页面内存，不落浏览器存储。
function markEdited(event) {
  const field = event.target
  if (!field.matches('input,textarea,select') || field.type === 'search' || field.readOnly || field.disabled || field.closest('.search,.filters,.filter-bar,[data-workspace-filter]')) return
  edited.value = true
}
function markFormClean() { edited.value = false }
let leavePromise = null, leaveResolver = null
function mayLeave() {
  if (!edited.value) return true
  if (!leavePromise) { leavePromise = new Promise(resolve => { leaveResolver = resolve }); openDialog(leaveDialog.value) }
  return leavePromise
}
function resolveLeave(allowed) { const resolve = leaveResolver; leaveResolver = null; leavePromise = null; leaveDialog.value?.close(); resolve?.(allowed) }
const removeGuard = router.beforeEach((to, from) => to.fullPath === from.fullPath || !session.isLoggedIn || mayLeave())
function onKeydown(event) { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); if (!document.querySelector('dialog[open]')) openDialog(searchDialog.value) } if (event.key === 'Escape') { mobileNav.value = false; if (!document.querySelector('dialog[open]')) focusMode.value = false } }
async function logout() {
  if (!await mayLeave()) return
  edited.value = false; loggingOut.value = true
  await session.logout(); cfg.reset(); accountDialog.value?.close(); await router.replace('/login')
}
let timer, previousTick = Date.now()
onMounted(async () => {
  window.addEventListener('keydown', onKeydown); window.addEventListener('student-portal-form-clean', markFormClean)
  timer = window.setInterval(() => { const tick = Date.now(); if (!timerPaused.value) elapsed.value += Math.max(0, Math.floor((tick - previousTick) / 1000)); previousTick = tick; now.value = new Date(tick) }, 1000)
  if (cfg.isModuleEnabled('messages')) {
    const identity = preferenceKey.value
    try { const data = await portalApi.messagesInbox('notice', 1, 1); if (identity === preferenceKey.value) unread.value = Math.max(0, Number(data?.tabs?.find(item => item.key === 'notice')?.badge) || 0) } catch { /* 不用假数据替代未读数 */ }
  }
})
onBeforeUnmount(() => { resolveLeave(false); clearInterval(timer); removeGuard(); window.removeEventListener('keydown', onKeydown); window.removeEventListener('student-portal-form-clean', markFormClean) })
</script>
