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
const roleLabel = computed(() => ({COMPANY_ADMIN:'企业管理员',HR:'企业 HR',MENTOR:'企业导师'}[String(context.memberRole||'').toUpperCase()] || context.memberRole || '企业成员'))
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
      <div class="brand"><span class="brand-mark">跃</span><div class="brand-copy"><strong>跃科</strong><span>企业协同中心</span></div></div>
      <div class="context"><b>{{ context.schoolName || '学校企业协同' }}</b><span class="context-dot">·</span><span>{{ title }}</span><span v-if="context.historyMode" class="history-badge">历史招聘季 · 招聘操作已关闭</span></div>
      <div class="account"><div class="account-copy"><span>{{ context.companyName || '企业账号' }}</span><small>{{ context.memberName || roleLabel }}</small></div><span class="role-badge">{{ roleLabel }}</span><button type="button" class="logout" @click="logout">退出</button></div>
    </header>
    <div class="body">
      <aside class="sidebar" :class="{open:mobileOpen}">
        <div class="workspace-card"><span>当前工作区</span><strong>{{ context.companyName || '企业协同中心' }}</strong><small>{{ title }}</small></div>
        <div class="nav-title">招聘与实习协同</div>
        <nav class="nav-list" aria-label="企业协同中心导航">
          <template v-for="item in nav" :key="item.to">
            <RouterLink v-if="navAllowed(item)" :to="item.to" class="nav-item" @click="mobileOpen=false"><span class="nav-dot"></span><span>{{ item.label }}</span></RouterLink>
            <span v-else class="nav-item nav-disabled" aria-disabled="true" title="仅企业管理员或 HR 可处理报名学生"><span class="nav-dot"></span><span>{{ item.label }}</span><small>管理员/HR</small></span>
          </template>
        </nav>
        <div class="sidebar-foot">所有数据范围由学校、招聘季、企业成员关系与授权共同校验。</div>
      </aside>
      <main class="main">
        <div v-if="context.loading && !context.contextReady" class="access-state ep-card ep-empty">正在校验企业成员关系、学校授权与招聘季范围…</div>
        <section v-else-if="context.error || !context.contextReady" class="access-state access-denied ep-card" role="alert">
          <span class="ep-tag danger">访问授权不可用</span>
          <h1>暂时无法进入企业协同工作区</h1>
          <p>{{ context.error || '企业访问范围校验未通过。' }}</p>
          <p class="ep-muted">可能原因包括：邀请尚未生效、成员已停用、学校账号范围不匹配、访问授权已过期，或当前招聘季尚未接受企业参与。系统不会在校验失败后自动放宽企业访问范围。</p>
          <RouterLink to="/login" class="ep-btn">返回企业登录</RouterLink>
        </section>
        <RouterView v-else />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell{min-height:100vh;background:var(--page)}
.topbar{height:64px;background:rgba(255,255,255,.96);backdrop-filter:saturate(150%) blur(10px);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:26px;padding:0 24px;position:sticky;top:0;z-index:20;box-shadow:0 1px 10px rgba(28,46,76,.03)}
.brand{display:flex;align-items:center;gap:10px;min-width:198px}.brand-mark{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:linear-gradient(145deg,var(--pri),#5b88ff);color:#fff;font-weight:800;box-shadow:0 7px 16px rgba(47,107,255,.22)}.brand-copy{display:flex;flex-direction:column;gap:1px}.brand strong{font-size:17px;line-height:1.2;color:#14203a}.brand-copy>span{font-size:11px;color:var(--t3);letter-spacing:.03em}
.context{display:flex;gap:9px;align-items:center;flex:1;min-width:0}.context b,.context span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.context b{font-size:14px;color:#24324a}.context>span{color:var(--t3);font-size:12px}.context-dot{color:#c0c8d4!important}.history-badge{background:var(--warn-bg);color:var(--warn-fg)!important;padding:5px 9px;border-radius:999px;border:1px solid rgba(154,91,0,.08)}
.account{font-size:12px;color:var(--t2);display:flex;align-items:center;gap:10px}.account-copy{display:flex;flex-direction:column;align-items:flex-end;gap:1px;max-width:190px}.account-copy>span{max-width:190px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600;color:#334158}.account-copy small{color:var(--t3)}.role-badge{padding:5px 8px;border-radius:999px;background:var(--surface-blue);border:1px solid var(--pri-100);color:var(--pri);font-weight:600}.logout{border:1px solid var(--line-strong);background:#fff;color:var(--t2);border-radius:8px;min-height:34px;padding:0 11px;cursor:pointer;font-weight:600}.logout:hover{border-color:var(--pri-200);color:var(--pri);background:var(--pri-50)}
.body{display:flex;min-height:calc(100vh - 64px)}
.sidebar{width:224px;background:#fff;border-right:1px solid var(--line);padding:18px 14px 16px;flex:0 0 224px;display:flex;flex-direction:column}.workspace-card{padding:13px 14px 14px;margin:0 2px 16px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(145deg,#fbfcff,var(--surface-blue));display:flex;flex-direction:column;gap:4px}.workspace-card>span,.workspace-card small{font-size:11px;color:var(--t3)}.workspace-card strong{font-size:13px;color:#27344b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.workspace-card small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nav-title{padding:0 12px 8px;color:var(--t3);font-size:11px;font-weight:600;letter-spacing:.04em}.nav-list{display:flex;flex-direction:column;gap:3px}.nav-item{display:flex;align-items:center;gap:10px;min-height:43px;padding:0 12px;border-radius:9px;color:var(--t2);text-decoration:none;position:relative;font-weight:500}.nav-dot{width:6px;height:6px;border-radius:50%;background:#c9d1dc;flex:0 0 6px}.nav-item:hover:not(.nav-disabled){background:#f8faff;color:#24324a}.nav-item.router-link-active{background:linear-gradient(90deg,var(--pri-50),#f7f9ff);color:var(--pri);font-weight:700}.nav-item.router-link-active::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:3px;background:var(--pri)}.nav-item.router-link-active .nav-dot{background:var(--pri);box-shadow:0 0 0 3px var(--pri-100)}.nav-disabled{justify-content:flex-start;color:var(--t4);background:#fafbfc;cursor:not-allowed}.nav-disabled small{font-size:10px;color:var(--t4);margin-left:auto}.sidebar-foot{margin-top:auto;padding:14px 12px 4px;border-top:1px solid var(--line);font-size:10px;line-height:1.6;color:var(--t4)}
.main{flex:1;min-width:0;padding:28px 30px 44px;background:radial-gradient(circle at 80% 0,rgba(47,107,255,.035),transparent 28%),var(--page)}.access-state{max-width:760px;margin:70px auto}.access-denied{padding:28px}.access-denied h1{font-size:22px;margin:14px 0 8px}.access-denied p{line-height:1.7}.access-denied a{display:inline-flex;align-items:center;text-decoration:none;margin-top:8px}.mobile-menu{display:none;border:0;background:transparent;font-size:20px}
@media(max-width:1100px){.account-copy{display:none}.role-badge{display:none}}
@media(max-width:900px){.topbar{height:58px;padding:0 16px;gap:12px}.mobile-menu{display:block}.brand{min-width:0}.brand-copy>span{display:none}.sidebar{display:none;position:fixed;z-index:30;top:58px;bottom:0;left:0;box-shadow:10px 0 30px rgba(31,41,55,.12)}.sidebar.open{display:flex}.context{display:none}.account{margin-left:auto}.main{padding:18px 16px 32px}.body{min-height:calc(100vh - 58px)}}
</style>
