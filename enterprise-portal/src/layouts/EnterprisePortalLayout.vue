<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'
import { clearEnterpriseSession } from '../services/request'

const nav = [
  {to:'/home',label:'首页'}, {to:'/company',label:'企业资料'}, {to:'/positions',label:'我的岗位'},
  {to:'/applications',label:'报名学生',applicationPermission:true}, {to:'/students',label:'实习学生'}, {to:'/evaluations',label:'评价任务'},
]
const router = useRouter()
const context = useEnterpriseContextStore()
const mobileOpen = ref(false)
const title = computed(() => context.campaign?.name || context.campaign?.campaignName || (context.campaign?.id ? `招聘季 #${context.campaign.id}` : '当前招聘季尚未加载'))
function navAllowed(item){return !item.applicationPermission||context.applicationViewAllowed}
function logout(){
  clearEnterpriseSession()
  context.$reset()
  router.replace('/login')
}
onMounted(() => context.load())
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <button class="mobile-menu" type="button" aria-label="打开企业协同导航" @click="mobileOpen=!mobileOpen">☰</button>
      <div class="brand"><strong>跃科</strong><span>企业协同中心</span></div>
      <div class="context"><b>{{ context.schoolName || '学校企业协同' }}</b><span>{{ title }}</span><span v-if="context.historyMode" class="history-badge">历史招聘季 · 招聘写操作已关闭</span></div>
      <div class="account"><span>{{ context.companyName || '企业账号' }} · {{ context.memberName || context.memberRole || '成员' }}</span><button type="button" class="logout" @click="logout">退出</button></div>
    </header>
    <div class="body">
      <aside class="sidebar" :class="{open:mobileOpen}">
        <div class="nav-title">企业协同中心</div>
        <template v-for="item in nav" :key="item.to">
          <RouterLink v-if="navAllowed(item)" :to="item.to" class="nav-item" @click="mobileOpen=false">{{ item.label }}</RouterLink>
          <span v-else class="nav-item nav-disabled" aria-disabled="true" title="仅企业管理员或 HR 可处理报名学生">{{ item.label }}<small>管理员/HR</small></span>
        </template>
      </aside>
      <main class="main">
        <div v-if="context.loading && !context.contextReady" class="access-state ep-card ep-empty">正在校验企业成员、学校租户与访问授权…</div>
        <section v-else-if="context.error || !context.contextReady" class="access-state access-denied ep-card" role="alert">
          <span class="ep-tag danger">访问授权不可用</span>
          <h1>暂时无法进入企业协同工作区</h1>
          <p>{{ context.error || '企业上下文校验未通过。' }}</p>
          <p class="ep-muted">可能原因包括：邀请尚未生效、成员已停用、学校租户不匹配、访问授权已过期，或当前招聘季尚未接受企业参与。客户端不会降级到未校验 companyId 或本地权限。</p>
          <RouterLink to="/login" class="ep-btn">返回企业登录</RouterLink>
        </section>
        <RouterView v-else />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell{min-height:100vh}.topbar{height:56px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:28px;padding:0 22px;position:sticky;top:0;z-index:20}.brand{display:flex;align-items:baseline;gap:9px;min-width:174px}.brand strong{font-size:20px;color:var(--pri)}.brand span{font-size:13px;color:var(--t2)}.context{display:flex;gap:12px;align-items:center;flex:1;min-width:0}.context b,.context span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.context span{color:var(--t3);font-size:13px}.history-badge{background:var(--warn-bg);color:var(--warn-fg)!important;padding:4px 7px;border-radius:4px}.account{font-size:13px;color:var(--t2);display:flex;align-items:center;gap:10px}.logout{border:1px solid var(--line);background:#fff;color:var(--t2);border-radius:6px;min-height:32px;padding:0 10px;cursor:pointer}.logout:hover{border-color:var(--pri-100);color:var(--pri)}.body{display:flex;min-height:calc(100vh - 56px)}.sidebar{width:196px;background:#fff;border-right:1px solid var(--line);padding:18px 12px;flex:0 0 196px}.nav-title{padding:0 12px 12px;color:var(--t3);font-size:12px}.nav-item{display:flex;align-items:center;min-height:44px;padding:0 14px;margin:2px 0;border-radius:8px;color:var(--t2);text-decoration:none}.nav-item.router-link-active{background:var(--pri-50);color:var(--pri);font-weight:600}.nav-disabled{justify-content:space-between;color:var(--t3);background:#f7f8fa;cursor:not-allowed}.nav-disabled small{font-size:10px;color:var(--t3)}.main{flex:1;min-width:0;padding:22px 24px 40px}.access-state{max-width:760px;margin:70px auto}.access-denied{padding:28px}.access-denied h1{font-size:22px;margin:14px 0 8px}.access-denied p{line-height:1.7}.access-denied a{display:inline-flex;align-items:center;text-decoration:none;margin-top:8px}.mobile-menu{display:none;border:0;background:transparent;font-size:20px}@media(max-width:900px){.mobile-menu{display:block}.sidebar{display:none;position:fixed;z-index:30;top:56px;bottom:0;left:0;box-shadow:10px 0 30px rgba(31,41,55,.12)}.sidebar.open{display:block}.context{display:none}.account{margin-left:auto}.account span{display:none}.main{padding:16px}}
</style>
