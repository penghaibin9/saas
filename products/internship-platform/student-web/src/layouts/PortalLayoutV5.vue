<template>
  <div class="sp-shell" :style="tokens" :data-theme="themeKey">
    <header class="sp-header">
      <div class="sp-brand"><span class="sp-brand__logo"><img v-if="logoUrl" :src="logoUrl" alt="学校校徽"/><svg v-else width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8.5 12 4.5l9.5 4-9.5 4z" /><path d="M6.5 11v4.2c0 1.3 2.5 2.3 5.5 2.3s5.5-1 5.5-2.3V11M21.5 8.5V13" /></svg></span><strong class="sp-brand__school" :title="brand.schoolName || brand.platformName">{{ brand.schoolName || brand.platformName }}</strong><span class="sp-brand__portal">学生端</span></div>
      <div class="sp-command-search">          <label class="sp-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
            <input v-model.trim="search" type="search" aria-label="搜索实习事项" placeholder="搜索实习事项…" @keyup.enter="doSearch" />
          </label>
          <div v-if="search" class="sp-search-results" role="region" aria-label="实习事项搜索结果"><button v-for="item in searchResults" :key="item.key" type="button" @click="openView(item.key); search = ''">{{ item.label }}</button><p v-if="!searchResults.length">未找到相关实习事项</p></div>
</div>
      <div class="sp-header__right">          <button v-if="!user?.mustChangePassword" class="sp-bell" type="button" :title="messageTitle" :aria-label="messageTitle" @click="goMsg">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
            <span v-if="unread > 0" class="sp-bell__badge">{{ unread > 99 ? '99+' : unread }}</span>
          </button>
<details class="sp-service"><summary>学校服务</summary><div><p>{{ cfg.visibleConfig?.service?.reminderText }}</p><p>咨询电话：{{ cfg.visibleConfig?.service?.contactPhone || '学校尚未配置' }}</p><p v-if="cfg.visibleConfig?.service?.supervisionPhone">监督电话：{{ cfg.visibleConfig.service.supervisionPhone }}</p><p v-if="cfg.visibleConfig?.service?.responsibleName">承办人：{{ cfg.visibleConfig.service.responsibleName }}</p><details v-for="item in cfg.visibleConfig?.service?.faq || []" :key="item.question"><summary>{{ item.question }}</summary><p>{{ item.answer }}</p></details></div></details>
        <button type="button" class="sp-control" @click="appearance.showModal()">外观设置</button>
        <button type="button" class="sp-identity" @click="router.push('/account/security')" aria-label="账户安全"><span>{{ initial }}</span>{{ user?.realName || '同学' }} · 学生</button>
        <button type="button" class="sp-control" @click="logout">退出</button>
      </div>
    </header>
    <div class="sp-centers"><nav aria-label="一级菜单"><button type="button" :class="{selected:route.path.startsWith('/internship')}" @click="openView('overview')">岗位实习中心</button></nav><span class="sp-scope">本人数据</span></div>
    <div class="sp-workspace">
      <aside class="sp-rail sp-rail--second" :class="{full:secondExpanded}" aria-label="二级菜单">
        <div class="sp-rail-heading"><strong v-if="secondExpanded">岗位实习中心</strong><button type="button" :aria-label="secondExpanded ? '收起二级菜单' : '展开二级菜单'" :aria-expanded="secondExpanded" @click="secondExpanded=!secondExpanded">{{ secondExpanded?'«':'»' }}</button></div>
        <nav aria-label="办理分组"><button v-for="group in INTERNSHIP_TAB_GROUPS" :key="group.key" type="button" :class="{selected:selectedGroup===group.key}" :aria-label="group.label" :title="group.label" :aria-pressed="selectedGroup===group.key" @click="selectedGroup=group.key">{{ secondExpanded?group.label:group.label.slice(0,2) }}</button></nav>
        <div class="sp-rail-foot">{{ secondExpanded?'已展开':'已收起' }}</div>
      </aside>
      <aside class="sp-rail sp-rail--third" :class="{full:thirdExpanded}" aria-label="三级菜单">
        <div class="sp-rail-heading"><strong v-if="thirdExpanded">{{ activeGroup.label }}</strong><button type="button" :aria-label="thirdExpanded ? '收起三级菜单' : '展开三级菜单'" :aria-expanded="thirdExpanded" @click="thirdExpanded=!thirdExpanded">{{ thirdExpanded?'«':'»' }}</button></div>
        <nav :aria-label="activeGroup.label"><button v-for="item in activeGroup.tabs" :key="item.key" type="button" :class="{selected:route.path.startsWith('/internship') && currentView===item.key}" :aria-label="item.label" :title="item.label" :aria-current="route.path.startsWith('/internship') && currentView===item.key?'page':undefined" @click="openView(item.key)">{{ thirdExpanded?item.label:menuShort(item) }}</button></nav>
        <div class="sp-rail-foot">{{ thirdExpanded?'已展开':'已收起' }}</div>
      </aside>
      <div class="sp-working">
        <div class="sp-tabbar"><nav class="sp-open-tabs" aria-label="已打开页面"><div v-for="item in openPages" :key="item.key" class="sp-open-tab" :class="{selected:item.key===pageKey}"><button type="button" :aria-current="item.key===pageKey?'page':undefined" @click="router.push(item.destination)">{{ item.label }}</button><button type="button" :aria-label="'关闭'+item.label" :disabled="openPages.length===1" :title="openPages.length===1?'至少保留一个已打开页面':'关闭此页签'" @click="closePage(item)">×</button></div></nav></div>
        <main class="sp-main"><div class="sp-content"><div class="sp-content__page"><slot /></div></div></main>
        <div class="sp-common-wrap"><button v-if="!commonOpen" type="button" class="sp-common-pill" @click="commonOpen=true">我的常用 ⌃</button><nav v-else class="sp-common" aria-label="我的常用"><strong>我的常用</strong><button type="button" @click="openView('overview')">我的实习</button><button type="button" @click="openView('checkin')">每日打卡</button><button type="button" @click="openView('report')">实习报告</button><button type="button" @click="goMsg">消息通知</button><button type="button" @click="commonOpen=false">收起</button></nav></div>
      </div>
    </div>
    <dialog ref="appearance" class="sp-appearance" aria-label="外观设置"><form method="dialog"><h2>外观设置</h2><button class="sp-control" aria-label="关闭外观设置">×</button></form><div class="sp-theme-grid"><button v-for="item in themes" :key="item.key" type="button" :aria-pressed="themeKey===item.key" @click="selectTheme(item.key)"><span :style="{background:item.color}"></span>{{ item.label }}</button></div><p>配色保存在当前学校、学生和身份的浏览器设置中。</p></dialog>
  </div>
</template>
<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { fileSdk } from '../services/fileSdk'
import { portalApi } from '../services/portalApi'
import { currentSessionGeneration } from '../services/request'
import { useRoute, useRouter } from 'vue-router'
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { WORKSPACE_THEMES, normalizeTheme, themeTokens } from '../platform/workspaceTheme'
import { INTERNSHIP_TABS, INTERNSHIP_TAB_GROUPS } from '../platform/internshipNavigation'
const emit = defineEmits(['logout'])
const route = useRoute(), router = useRouter()
const cfg = usePortalConfigStore(), session = useSessionStore()
const brand = computed(() => cfg.brand)
const user = computed(() => session.user)
const logoUrl=ref('');let logoSequence=0
function clearLogo(){if(logoUrl.value) URL.revokeObjectURL(logoUrl.value);logoUrl.value=''}
watch(()=>[brand.value?.logoFileId,user.value?.tenantId,user.value?.userId],async ([id])=>{
  const run=++logoSequence;clearLogo();if(!id)return
  try{const blob=await fileSdk.fetchPreviewBlob(id);if(run===logoSequence)logoUrl.value=URL.createObjectURL(blob)}catch{ /* 显示默认校徽，业务继续可用。 */ }
},{immediate:true})
onBeforeUnmount(()=>{logoSequence++;clearLogo()})
const initial = computed(() => (user.value?.realName || '同').slice(0, 1))
const search = ref(''), themeKey = ref('blue')
const themes = WORKSPACE_THEMES.map(item => ({ ...item, color: item.accent }))
const tokens = computed(() => themeTokens(themeKey.value))
const prefKey = computed(() => 'internship-student-shell:' + JSON.stringify([String(user.value?.tenantId || ''), String(user.value?.userId || ''), user.value?.roleCode || '']))
watch(prefKey, key => { search.value = ''; try { themeKey.value = normalizeTheme(localStorage.getItem(key)) } catch { themeKey.value = 'blue' } }, { immediate: true })
const currentView = computed(() => route.meta?.internshipView || (typeof route.query.view === 'string' ? route.query.view : 'overview'))
const pageTitle = computed(() => route.path === '/account/security' ? '账户安全' : route.path === '/messages' ? '消息通知' : route.path === '/internship/volunteer-result' ? '志愿办理结果' : route.params?.companyId ? '企业详情' : INTERNSHIP_TABS.find(item => item.key === currentView.value)?.label || '岗位实习')
const appearance=ref(null), secondExpanded=ref(true), thirdExpanded=ref(false), commonOpen=ref(false)
const selectedGroup=ref(INTERNSHIP_TAB_GROUPS[0].key)
const activeGroup=computed(()=>INTERNSHIP_TAB_GROUPS.find(group=>group.key===selectedGroup.value) || INTERNSHIP_TAB_GROUPS[0])
const pageKey=computed(()=>route.path==='/internship'?'internship:'+currentView.value:route.path)
const menuShort=item=>({overview:'首页',notices:'公告',consent:'知情',agreement:'协议',insurance:'保险',plan:'计划',checkin:'打卡',leave:'请假',makeup:'补卡',intention:'意向',application:'申请',enterprises:'岗位',change:'调岗',help:'求助',report:'报告',eval:'评价'})[item.key] || item.label.slice(0,2)
const openPages=ref([])
let pageIdentity=''
watch(()=>[route.fullPath,prefKey.value],()=>{
  if(pageIdentity!==prefKey.value){
    openPages.value=[];commonOpen.value=false;secondExpanded.value=true;thirdExpanded.value=false;pageIdentity=prefKey.value
    try{const saved=JSON.parse(localStorage.getItem(prefKey.value+':frame') || 'null');if(saved){secondExpanded.value=saved.secondExpanded!==false;thirdExpanded.value=saved.thirdExpanded===true}}catch{ /* 无效菜单偏好恢复默认宽度。 */ }
  }
  if(!route.path.startsWith('/internship') && !['/messages','/account/security'].includes(route.path))return
  const group=INTERNSHIP_TAB_GROUPS.find(group=>group.keys.includes(currentView.value))
  if(route.path.startsWith('/internship') && group)selectedGroup.value=group.key
  const item={key:pageKey.value,label:pageTitle.value,destination:route.fullPath}
  const index=openPages.value.findIndex(page=>page.key===item.key)
  if(index<0)openPages.value.push(item);else openPages.value[index]=item
},{immediate:true})
watch(()=>[secondExpanded.value,thirdExpanded.value],()=>{try{localStorage.setItem(prefKey.value+':frame',JSON.stringify({secondExpanded:secondExpanded.value,thirdExpanded:thirdExpanded.value}))}catch{ /* 菜单仍可正常使用。 */ }})
function closePage(item){
  if(openPages.value.length<=1)return
  const index=openPages.value.findIndex(page=>page.key===item.key)
  if(item.key===pageKey.value){const next=openPages.value[index-1] || openPages.value[index+1];if(!next)return;router.push(next.destination)}
  openPages.value=openPages.value.filter(page=>page.key!==item.key)
}
const searchResults = computed(() => INTERNSHIP_TABS.filter(item => item.label.includes(search.value)))
function openView(view) {
  const path = ({selection:'/internship/selection',profile:'/internship/profile',safety:'/internship/compliance',materials:'/internship/materials'})[view]
  const query = route.query.batchId ? {batchId:route.query.batchId} : {}
  if (path) {
    if (['selection','profile'].includes(view) && route.query.campaignId && route.query.recordId) Object.assign(query,{campaignId:route.query.campaignId,recordId:route.query.recordId})
    router.push({path,query})
  } else router.push({path:'/internship',query:{...query,view}})
}
function goMsg() { router.push('/messages') }
function doSearch() { if (searchResults.value.length === 1) { openView(searchResults.value[0].key); search.value = '' } }
function selectTheme(key) { themeKey.value = normalizeTheme(key); try { localStorage.setItem(prefKey.value, themeKey.value) } catch { /* 外观保存失败不影响办理。 */ } }
function logout() { emit('logout') }
const unread = ref(null), countError = ref(false)
let countSequence = 0, countAlive = true
const messageTitle = computed(() => countError.value ? '未读数量读取失败，点击查看消息' : unread.value === null ? '消息通知，未读数量正在读取' : `消息通知，${unread.value}条未读`)
async function reloadUnread() {
  const sequence = ++countSequence, generation = currentSessionGeneration(), identity = prefKey.value
  unread.value = null; countError.value = false
  if (!user.value?.userId || user.value.mustChangePassword) return
  try {
    const result = await portalApi.messageCount()
    if (!countAlive || sequence !== countSequence || generation !== currentSessionGeneration() || identity !== prefKey.value) return
    if (!Number.isInteger(result?.unread) || result.unread < 0) throw new Error('消息计数返回异常')
    unread.value = result.unread
  } catch {
    if (countAlive && sequence === countSequence && generation === currentSessionGeneration() && identity === prefKey.value) countError.value = true
  }
}
watch(() => [route.fullPath, prefKey.value], reloadUnread, { immediate: true })
if (typeof window !== 'undefined') window.addEventListener('internship-message-read', reloadUnread)
onBeforeUnmount(() => { countAlive = false; countSequence++; if (typeof window !== 'undefined') window.removeEventListener('internship-message-read', reloadUnread) })
</script>
<style scoped>
.sp-shell{height:100vh;width:100%;display:flex;flex-direction:column;overflow:hidden;background:var(--bg);color:var(--t1);font-size:14px}
.sp-header{height:60px;flex:none;display:flex;align-items:center;gap:10px;padding:0 20px;background:var(--surface-2);border-bottom:1px solid var(--line);position:relative;z-index:30}
.sp-brand{display:flex;align-items:center;gap:12px;flex:none;min-width:0}.sp-brand__logo{width:36px;height:36px;flex:none;border-radius:9px;display:grid;place-items:center;background:var(--pri);color:var(--pri-on)}.sp-brand__logo img{width:36px;height:36px;object-fit:contain}.sp-brand__school{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:17px}.sp-brand__portal{font-size:12px;color:var(--t3)}
.sp-command-search{position:relative;flex:1;min-width:140px;max-width:600px;margin:0 10px}.sp-search{height:36px;padding:0 12px;display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--t3)}.sp-search input{min-width:0;width:100%;border:0;outline:none;background:transparent;color:var(--t1);font:inherit}.sp-search svg{flex:none}.sp-search-results{position:absolute;top:42px;left:0;right:0;max-height:360px;overflow:auto;padding:8px;background:var(--surface);border:1px solid var(--line);border-radius:9px;box-shadow:0 8px 24px #10203020}.sp-search-results button{display:block;width:100%;min-height:40px;padding:10px;border:0;background:transparent;text-align:left;color:var(--t1);cursor:pointer}.sp-search-results button:hover{background:var(--pri-50)}.sp-search-results p{color:var(--t3)}
.sp-header__right{display:flex;align-items:center;gap:14px;margin-left:auto;white-space:nowrap;font-size:13px}.sp-control{padding:6px 10px;min-height:32px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--t1);font:inherit;cursor:pointer}.sp-identity{display:flex;align-items:center;gap:7px;border:0;background:transparent;color:var(--t1);font:inherit;cursor:pointer}.sp-identity>span{display:grid;place-items:center;background:var(--pri-50);color:var(--pri);border-radius:7px;width:30px;height:30px}.sp-bell{position:relative;width:36px;height:36px;display:grid;place-items:center;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--t2);cursor:pointer}.sp-bell__badge{position:absolute;right:-5px;top:-5px;min-width:16px;padding:0 4px;line-height:16px;border-radius:10px;background:#b42318;color:#fff;font-size:10px}
.sp-service{position:relative}.sp-service>summary{cursor:pointer}.sp-service>div{position:absolute;right:0;top:32px;width:min(360px,80vw);white-space:normal;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:0 8px 30px #0002;max-height:65vh;overflow:auto}.sp-service p{line-height:1.7}
.sp-centers{height:44px;flex:none;padding:0 22px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);background:var(--surface)}.sp-centers nav{display:flex;gap:8px}.sp-centers button{padding:9px 14px;border:0;border-radius:5px;font:inherit;color:var(--t3);background:transparent;cursor:pointer}.sp-centers button.selected{background:var(--pri-50);color:var(--pri);font-weight:700}.sp-scope{padding:6px 12px;font-size:12px;color:var(--pri);background:var(--pri-50);border-radius:5px}
.sp-workspace{flex:1;min-height:0;display:flex}.sp-rail{width:68px;flex:0 0 68px;display:flex;flex-direction:column;min-height:0;background:var(--surface-2);border-right:1px solid var(--line);transition:width .15s,flex-basis .15s}.sp-rail--second{width:88px;flex-basis:88px}.sp-rail.full{width:152px;flex-basis:152px}.sp-rail-heading{height:48px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:12px}.sp-rail-heading button{min-width:28px;height:32px;margin-left:auto;border:0;background:transparent;color:var(--t2);font-size:18px;cursor:pointer}.sp-rail nav{flex:1;min-height:0;overflow:auto;padding:0 6px}.sp-rail nav button{display:block;width:100%;min-height:38px;margin:3px 0;padding:8px 10px;border:0;border-left:2px solid transparent;border-radius:5px;background:transparent;color:var(--t3);font-size:12px;font-family:inherit;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sp-rail.full nav button{text-align:left}.sp-rail nav button.selected{background:var(--pri-50);border-left-color:var(--pri);color:var(--pri);font-weight:700}.sp-rail nav button:hover{background:var(--pri-50);color:var(--pri)}.sp-rail-foot{height:32px;flex:none;border-top:1px solid var(--line);text-align:center;padding:8px 0;color:var(--t3);font-size:11px}
.sp-working{flex:1;min-width:0;min-height:0;position:relative;display:flex;flex-direction:column}.sp-tabbar{height:36px;flex:none;padding:0 14px;display:flex;align-items:stretch;gap:6px;border-bottom:1px solid var(--line);background:var(--surface)}.sp-open-tabs{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}.sp-open-tab{position:relative;display:flex;max-width:204px;min-width:98px;margin:3px 0;border:1px solid transparent;border-radius:5px;color:var(--t3)}.sp-open-tab.selected{border-color:var(--line);color:var(--pri);background:var(--pri-50)}.sp-open-tab.selected:after{content:'';position:absolute;bottom:-4px;left:9px;right:9px;height:2px;background:var(--pri);border-radius:2px}.sp-open-tab button{border:0;background:transparent;color:inherit;cursor:pointer;font:inherit;font-size:12px}.sp-open-tab button:first-child{padding:0 6px 0 9px;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.sp-open-tab button:last-child{width:24px;flex:none;padding:4px}
.sp-main{flex:1;min-height:0;min-width:0;overflow:auto;background:var(--bg)}.sp-content{padding:12px 18px 78px}.sp-content__page{max-width:1680px;margin:0 auto}.sp-common-wrap{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);max-width:calc(100% - 28px);z-index:15}.sp-common-pill{border:1px solid var(--line);border-radius:20px;background:var(--surface);color:var(--t3);padding:8px 18px;box-shadow:0 4px 18px #10203014;font:inherit;cursor:pointer}.sp-common{display:flex;align-items:center;gap:8px;padding:10px 14px;border:1px solid var(--line);border-radius:16px;background:var(--surface);box-shadow:0 6px 24px #10203020;white-space:nowrap}.sp-common strong{font-size:12px;color:var(--t3)}.sp-common button{border:0;border-radius:7px;padding:10px;background:var(--pri-50);color:var(--pri);font:inherit;font-size:13px;cursor:pointer}
.sp-appearance{width:min(520px,90vw);padding:24px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--t1);box-shadow:0 20px 80px #0003}.sp-appearance::backdrop{background:#10203055}.sp-appearance form{display:flex;align-items:center;justify-content:space-between}.sp-appearance h2{font-size:18px;margin:0 0 18px}.sp-appearance p{font-size:13px;color:var(--t3)}.sp-theme-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.sp-theme-grid button{display:flex;align-items:center;gap:10px;min-height:64px;padding:12px;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--t2);font:inherit;cursor:pointer}.sp-theme-grid button[aria-pressed=true]{border-color:var(--pri);color:var(--pri);background:var(--pri-50)}.sp-theme-grid span{width:24px;height:24px;border-radius:6px}
.sp-shell button:focus-visible,.sp-search:focus-within,.sp-service>summary:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
@media(max-width:1250px){.sp-brand__school{font-size:14px;max-width:220px}.sp-brand__portal{display:none}.sp-command-search{margin:0 2px}.sp-header__right{gap:8px}}
@media(max-width:900px){.sp-header{padding:0 10px}.sp-brand__school{display:none}.sp-header__right{gap:6px}.sp-command-search{min-width:100px}.sp-content{padding:12px 14px 78px}.sp-identity{font-size:12px}.sp-identity>span{display:none}}
</style>
