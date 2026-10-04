<template>
  <div class="sp-shell" :class="shellClasses" :style="tokens" :data-theme="themeKey">
    <aside class="sp-aside">
      <div class="sp-brand">
        <span class="sp-brand__logo">
          <svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8.5 12 4.5l9.5 4-9.5 4z" /><path d="M6.5 11v4.2c0 1.3 2.5 2.3 5.5 2.3s5.5-1 5.5-2.3V11M21.5 8.5V13" /></svg>
        </span>
        <div class="sp-brand__text">
          <div class="sp-brand__school">{{ brand.schoolName || brand.platformName }}</div>
          <div class="sp-brand__portal">{{ portalName }}</div>
        </div>
      </div>

      <div class="sp-nav__label">门户导航</div>
      <nav class="sp-nav">
        <button v-for="m in nav" :key="m.key" type="button" class="sp-nav__item"
                :class="{ 'is-active': m.active, 'is-locked': m.locked }" :title="m.title" @click="onNav(m)">
          <span class="sp-nav__icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="m.d1" /><path :d="m.d2" /></svg>
          </span>
          <span class="sp-nav__text">{{ m.title }}</span>
          <span v-if="m.badge" class="sp-nav__badge">{{ m.badge }}</span>
          <svg v-else-if="m.locked" class="sp-nav__lock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
        </button>
      </nav>

      <section class="sp-theme" aria-label="门户主题">
        <div class="sp-theme__title">主题换色</div>
        <div class="sp-theme__grid">
          <button v-for="item in themes" :key="item.key" type="button" class="sp-theme__item"
                  :class="{ 'is-active': themeKey === item.key }" :title="item.label" @click="selectTheme(item.key)">
            <span class="sp-theme__dot" :style="{ background: item.color }" />
            <span class="sp-theme__label">{{ item.label }}</span>
          </button>
        </div>
      </section>

      <div class="sp-aside__foot">
        <span class="sp-version">学生服务门户</span>
        <button type="button" class="sp-logout" title="退出登录" @click="logout">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3M16 17l5-5-5-5M21 12H9" /></svg>
          <span>退出</span>
        </button>
      </div>
    </aside>

    <div class="sp-body">
      <header class="sp-header">
        <div class="sp-header__left">
          <div class="sp-header__heading">
            <span class="sp-header__eyebrow">学生服务门户</span>
            <span class="sp-header__title">{{ pageTitle }}</span>
          </div>
        </div>
        <div class="sp-header__right">
          <label class="sp-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
            <input v-model.trim="search" type="search" aria-label="搜索实习事项" placeholder="搜索实习事项…" @keyup.enter="doSearch" />
          </label>
          <div v-if="search" class="sp-search-results" role="region" aria-label="实习事项搜索结果"><button v-for="item in searchResults" :key="item.key" type="button" @click="openView(item.key); search = ''">{{ item.label }}</button><p v-if="!searchResults.length">未找到相关实习事项</p></div>
          <div class="sp-scope">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
            本人数据
          </div>
          <button class="sp-bell" type="button" title="消息通知" @click="goMsg">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
            <span v-if="unread > 0" class="sp-bell__badge">{{ unread > 99 ? '99+' : unread }}</span>
          </button>
          <div class="sp-user">
            <span class="sp-user__avatar">{{ initial }}</span>
            <div class="sp-user__meta">
              <div class="sp-user__name">{{ user?.realName || '同学' }}</div>
              <div class="sp-user__role">学生 · 数据范围本人</div>
            </div>
          </div>
        </div>
      </header>

      <main class="sp-main">
        
        <div class="sp-content" >
          <div class="sp-content__page"><slot /></div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { WORKSPACE_THEMES, normalizeTheme, themeTokens } from '../platform/workspaceTheme'
import { INTERNSHIP_TABS } from '../platform/internshipNavigation'
const emit = defineEmits(['logout'])
const route = useRoute(), router = useRouter()
const cfg = usePortalConfigStore(), session = useSessionStore()
const brand = computed(() => cfg.brand)
const portalName = '学生服务门户'
const user = computed(() => session.user)
const initial = computed(() => (user.value?.realName || '同').slice(0, 1))
const search = ref(''), themeKey = ref('blue')
const themes = WORKSPACE_THEMES.map(item => ({ ...item, color: item.accent }))
const tokens = computed(() => themeTokens(themeKey.value))
const prefKey = computed(() => 'internship-student-shell:' + JSON.stringify([String(user.value?.tenantId || ''), String(user.value?.userId || ''), user.value?.roleCode || '']))
watch(prefKey, key => { search.value = ''; try { themeKey.value = normalizeTheme(localStorage.getItem(key)) } catch { themeKey.value = 'blue' } }, { immediate: true })
const currentView = computed(() => typeof route.query.view === 'string' ? route.query.view : 'overview')
const shellClasses = computed(() => ({ 'is-compact': true, 'route-internship': true }))
const pageTitle = computed(() => INTERNSHIP_TABS.find(item => item.key === currentView.value)?.label || '岗位实习')
const nav = computed(() => [
  { key: 'internship', title: '岗位实习', view: 'overview', active: currentView.value !== 'notices', d1: 'M4 7h16v13H4z M8 7V4h8v3', d2: 'M4 12h16 M10 12v3h4v-3' },
  { key: 'notices', title: '通知公告', view: 'notices', active: currentView.value === 'notices', d1: 'M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6', d2: 'M10 20a2 2 0 0 0 4 0' }
])
const searchResults = computed(() => INTERNSHIP_TABS.filter(item => item.label.includes(search.value)))
function openView(view) { router.push({ path: '/internship', query: { ...route.query, view } }) }
function onNav(item) { openView(item.view) }
function goMsg() { openView('notices') }
function doSearch() { if (searchResults.value.length === 1) { openView(searchResults.value[0].key); search.value = '' } }
function selectTheme(key) { themeKey.value = normalizeTheme(key); try { localStorage.setItem(prefKey.value, themeKey.value) } catch { /* 外观保存失败不影响办理。 */ } }
function logout() { emit('logout') }
// 通知来源未提供统一未读计数时，不虚构角标。
const unread = 0
</script>
<style scoped>
.sp-shell { display:flex; height:100vh; width:100%; overflow:hidden; background:var(--bg); }
.sp-aside { position:relative; width:224px; flex:none; overflow:hidden; display:flex; flex-direction:column; color:#fff; background:linear-gradient(180deg, color-mix(in srgb,var(--pri) 45%,#071b47) 0%, var(--pri) 57%, color-mix(in srgb,var(--pri) 58%,#fff) 100%); transition:width .18s ease; }
.sp-aside::before { content:""; position:absolute; width:260px; height:260px; right:-150px; top:-120px; border-radius:50%; background:rgba(255,255,255,.08); pointer-events:none; }
.sp-shell.is-compact .sp-aside { width:76px; }
.sp-brand { position:relative; display:flex; align-items:center; gap:11px; padding:18px 14px 16px; min-height:72px; }
.sp-brand__logo { width:43px; height:43px; flex:none; border-radius:14px; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.2); box-shadow:0 8px 24px rgba(0,0,0,.12); }
.sp-brand__text { min-width:0; }
.sp-brand__school { font-size:14px; font-weight:700; line-height:1.25; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sp-brand__portal { margin-top:3px; font-size:11px; color:rgba(255,255,255,.7); }
.sp-nav__label { position:relative; padding:3px 18px 7px; font-size:10.5px; letter-spacing:.12em; color:rgba(255,255,255,.54); }
.sp-nav { position:relative; flex:1; overflow-y:auto; padding:0 11px 12px; }
.sp-nav::-webkit-scrollbar { width:0; }
.sp-nav__item { all:unset; box-sizing:border-box; cursor:pointer; width:100%; min-height:43px; margin:3px 0; padding:0 11px; border-radius:13px; display:flex; align-items:center; gap:10px; color:rgba(255,255,255,.8); font-size:13.5px; transition:background .15s ease,color .15s ease,transform .15s ease; }
.sp-nav__item:hover { background:rgba(255,255,255,.09); color:#fff; }
.sp-nav__item.is-active { background:#fff; color:var(--pri-text,var(--pri)); font-weight:750; box-shadow:0 10px 26px rgba(3,18,56,.18); }
.sp-nav__item.is-locked { color:rgba(255,255,255,.38); cursor:not-allowed; }
.sp-nav__item.is-locked:hover { background:transparent; }
.sp-nav__icon { width:28px; height:28px; flex:none; display:grid; place-items:center; }
.sp-nav__text { flex:1; white-space:nowrap; }
.sp-nav__lock { flex:none; opacity:.65; }
.sp-nav__badge { min-width:19px; height:19px; padding:0 5px; border-radius:10px; display:inline-flex; align-items:center; justify-content:center; background:#ff5d67; color:#fff; font-size:10px; font-weight:700; }
.sp-shell.is-compact :where(.sp-brand__text,.sp-nav__label,.sp-nav__text,.sp-nav__lock) { display:none; }
.sp-shell.is-compact .sp-brand { justify-content:center; padding-inline:0; }
.sp-shell.is-compact .sp-nav { padding-inline:10px; }
.sp-shell.is-compact .sp-nav__item { justify-content:center; padding:0; }
.sp-shell.is-compact .sp-nav__badge { position:absolute; top:2px; right:1px; }
.sp-theme { position:relative; padding:13px 11px 12px; border-top:1px solid rgba(255,255,255,.14); }
.sp-theme__title { padding:0 4px 9px; font-size:11.5px; font-weight:650; color:rgba(255,255,255,.78); }
.sp-theme__grid { display:grid; grid-template-columns:1fr 1fr; gap:7px; }
.sp-theme__item { all:unset; box-sizing:border-box; cursor:pointer; min-height:31px; padding:0 8px; border-radius:10px; display:flex; align-items:center; gap:7px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.07); color:rgba(255,255,255,.78); font-size:10.5px; }
.sp-theme__item:hover,.sp-theme__item.is-active { background:#fff; color:var(--pri-text,var(--pri)); }
.sp-theme__dot { width:12px; height:12px; flex:none; border-radius:50%; border:2px solid rgba(255,255,255,.48); box-shadow:0 0 0 1px rgba(0,0,0,.07); }
.sp-shell.is-compact .sp-theme { padding:11px 15px; }
.sp-shell.is-compact .sp-theme__title,.sp-shell.is-compact .sp-theme__label { display:none; }
.sp-shell.is-compact .sp-theme__grid { grid-template-columns:1fr; gap:7px; }
.sp-shell.is-compact .sp-theme__item { min-height:25px; padding:0; justify-content:center; border:0; background:transparent; }
.sp-shell.is-compact .sp-theme__item.is-active { background:rgba(255,255,255,.16); }
.sp-aside__foot { position:relative; min-height:50px; padding:10px 14px; border-top:1px solid rgba(255,255,255,.14); display:flex; align-items:center; justify-content:space-between; gap:8px; }
.sp-version { font-size:10.5px; color:rgba(255,255,255,.62); }
.sp-logout { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:6px; color:rgba(255,255,255,.72); font-size:12px; }
.sp-logout:hover { color:#fff; }
.sp-shell.is-compact .sp-version,.sp-shell.is-compact .sp-logout span { display:none; }
.sp-shell.is-compact .sp-aside__foot { justify-content:center; padding-inline:0; }
.sp-body { flex:1; min-width:0; display:flex; flex-direction:column; }
.sp-header { height:72px; flex:none; display:flex; align-items:center; justify-content:space-between; gap:18px; padding:0 26px; background:var(--surface,#fff); border-bottom:1px solid var(--line); }
.sp-header__left,.sp-header__right { display:flex; align-items:center; gap:12px; min-width:0; }
.sp-header__right { flex:none; gap:11px; }
.sp-header__heading { min-width:0; display:flex; flex-direction:column; }
.sp-header__eyebrow { color:var(--t4); font-size:9.5px; letter-spacing:.12em; line-height:1; }
.sp-header__title { margin-top:5px; color:var(--t1); font-size:20px; font-weight:750; line-height:1.15; white-space:nowrap; }
.sp-context-link { height:33px; padding:0 12px; border:1px solid var(--pri); border-radius:9px; background:var(--pri-50); color:var(--pri-text,var(--pri)); font-size:12px; font-weight:700; cursor:pointer; white-space:nowrap; }
.sp-search { width:280px; height:40px; padding:0 12px; display:flex; align-items:center; gap:8px; border:1px solid var(--line); border-radius:12px; background:var(--field-bg,#f8faff); color:var(--t4); }
.sp-search input { width:100%; border:0; outline:0; background:transparent; color:var(--t1); font-size:13px; }
.sp-scope { height:31px; padding:0 10px; display:flex; align-items:center; gap:6px; border-radius:9px; background:var(--pri-50); color:var(--pri-text,var(--pri)); font-size:11.5px; font-weight:700; white-space:nowrap; }
.sp-bell { all:unset; position:relative; cursor:pointer; width:38px; height:38px; border:1px solid var(--line); border-radius:11px; display:grid; place-items:center; color:var(--t2); }
.sp-bell:hover { background:var(--field-bg,#f6f8fc); }
.sp-bell__badge { position:absolute; top:-4px; right:-4px; min-width:17px; height:17px; padding:0 4px; border-radius:9px; display:grid; place-items:center; background:var(--danger-fg); color:#fff; border:2px solid var(--surface,#fff); font-size:9px; font-weight:700; }
.sp-user { display:flex; align-items:center; gap:9px; padding-left:11px; border-left:1px solid var(--line); }
.sp-user__avatar { width:38px; height:38px; border-radius:12px; display:grid; place-items:center; background:linear-gradient(135deg,var(--pri-50),var(--pri-100)); color:var(--pri-text,var(--pri)); border:1px solid var(--pri-100); font-size:14px; font-weight:800; }
.sp-user__name { color:var(--t1); font-size:12.5px; font-weight:700; }
.sp-user__role { margin-top:3px; color:var(--t3); font-size:10.5px; }
.sp-main { flex:1; overflow-y:auto; position:relative; background:var(--bg); }
.sp-watermark { position:absolute; inset:0; pointer-events:none; background-repeat:repeat; z-index:0; }
.sp-content { position:relative; z-index:1; margin:0 auto; }
.sp-content.has-academic-context { display:grid; grid-template-columns:208px minmax(0,1fr); gap:18px; align-items:start; }
.sp-content__page { min-width:0; }
@media(max-width:1180px){.sp-search{width:210px}.sp-user__meta{display:none}.sp-user{border-left:0;padding-left:0}.sp-scope{display:none}.sp-content.has-academic-context{grid-template-columns:196px minmax(0,1fr)}}
@media(max-width:900px){.sp-aside,.sp-shell.is-home .sp-aside{width:64px}.sp-brand__text,.sp-nav__label,.sp-nav__text,.sp-nav__lock,.sp-theme__title,.sp-theme__label,.sp-version,.sp-logout span{display:none}.sp-brand{justify-content:center;padding-inline:0}.sp-nav{padding-inline:7px}.sp-nav__item{justify-content:center;padding:0}.sp-theme{padding-inline:10px}.sp-theme__grid{grid-template-columns:1fr}.sp-theme__item{justify-content:center;padding:0;border:0;background:transparent}.sp-aside__foot{justify-content:center;padding-inline:0}.sp-header{padding:0 16px}.sp-search{width:160px}.sp-context-link{display:none}}
@media(max-width:820px){.sp-content.has-academic-context{display:block}.sp-content.has-academic-context > :first-child{margin-bottom:14px}}
@media(max-width:700px){.sp-header__eyebrow,.sp-search{display:none}.sp-header{height:62px}.sp-header__title{font-size:17px}.sp-user__avatar{width:34px;height:34px}}
.sp-content{width:100%;max-width:1600px;padding:22px 24px 34px;box-sizing:border-box}.sp-header__right{position:relative}.sp-search-results{position:absolute;right:100px;top:48px;width:280px;max-height:360px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface);box-shadow:0 8px 28px #1f305616;z-index:40;padding:8px}.sp-search-results button{display:block;width:100%;text-align:left;border:0;background:transparent;color:var(--t1);padding:10px;cursor:pointer;border-radius:7px}.sp-search-results button:hover{background:var(--pri-50)}.sp-search-results p{padding:10px;color:var(--t3)}
@media(max-width:700px){.sp-content{padding:14px}.sp-search-results{display:none}}
.sp-shell[data-theme='blue'] .sp-aside {
  color: #173f60;
  background: linear-gradient(180deg, #e2eff8 0%, #cfe4f3 56%, #bddbed 100%) !important;
  border-right: 1px solid #b5d2e6;
}

.sp-shell[data-theme='blue'] .sp-aside::before {
  background: rgba(255, 255, 255, .34);
}

.sp-shell[data-theme='blue'] :where(
  .sp-brand__portal, .sp-nav__label, .sp-nav__item
) {
  color: #466984 !important;
}

.sp-shell[data-theme='blue'] .sp-brand__logo {
  background: rgba(255, 255, 255, .54);
  border-color: rgba(74, 128, 168, .18);
  box-shadow: 0 8px 22px rgba(45, 96, 134, .10);
}

.sp-shell[data-theme='blue'] .sp-nav__item:hover {
  color: #173f60 !important;
  background: rgba(255, 255, 255, .45);
}

.sp-shell[data-theme='blue'] .sp-nav__item.is-active {
  color: #245b86 !important;
  background: rgba(255, 255, 255, .92);
  box-shadow: 0 8px 22px rgba(45, 96, 134, .12);
}

.sp-shell[data-theme='blue'] .sp-nav__item.is-locked {
  color: rgba(46, 79, 103, .48) !important;
}

</style>
