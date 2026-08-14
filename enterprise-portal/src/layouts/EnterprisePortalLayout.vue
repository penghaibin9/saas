<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'

const nav = [
  ['/home','首页'], ['/company','企业资料'], ['/positions','我的岗位'],
  ['/applications','报名学生'], ['/students','实习学生'], ['/evaluations','评价任务'],
]
const context = useEnterpriseContextStore()
const mobileOpen = ref(false)
const title = computed(() => context.campaign?.name || '当前招聘季尚未加载')
onMounted(() => context.load())
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <button class="mobile-menu" type="button" @click="mobileOpen=!mobileOpen">☰</button>
      <div class="brand"><strong>跃科</strong><span>企业协同中心</span></div>
      <div class="context"><b>{{ context.schoolName || '学校企业协同' }}</b><span>{{ title }}</span></div>
      <div class="account">{{ context.companyName || '企业账号' }} · {{ context.memberName || '成员' }}</div>
    </header>
    <div class="body">
      <aside class="sidebar" :class="{open:mobileOpen}">
        <div class="nav-title">企业协同中心</div>
        <RouterLink v-for="item in nav" :key="item[0]" :to="item[0]" class="nav-item" @click="mobileOpen=false">{{ item[1] }}</RouterLink>
      </aside>
      <main class="main"><RouterView /></main>
    </div>
  </div>
</template>

<style scoped>
.shell{min-height:100vh}.topbar{height:56px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:28px;padding:0 22px;position:sticky;top:0;z-index:20}.brand{display:flex;align-items:baseline;gap:9px;min-width:174px}.brand strong{font-size:20px;color:var(--pri)}.brand span{font-size:13px;color:var(--t2)}.context{display:flex;gap:12px;align-items:center;flex:1;min-width:0}.context b,.context span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.context span{color:var(--t3);font-size:13px}.account{font-size:13px;color:var(--t2)}.body{display:flex;min-height:calc(100vh - 56px)}.sidebar{width:196px;background:#fff;border-right:1px solid var(--line);padding:18px 12px;flex:0 0 196px}.nav-title{padding:0 12px 12px;color:var(--t3);font-size:12px}.nav-item{display:flex;align-items:center;min-height:44px;padding:0 14px;margin:2px 0;border-radius:8px;color:var(--t2);text-decoration:none}.nav-item.router-link-active{background:var(--pri-50);color:var(--pri);font-weight:600}.main{flex:1;min-width:0;padding:22px 24px 40px}.mobile-menu{display:none;border:0;background:transparent;font-size:20px}@media(max-width:900px){.mobile-menu{display:block}.sidebar{display:none;position:fixed;z-index:30;top:56px;bottom:0;left:0;box-shadow:10px 0 30px rgba(31,41,55,.12)}.sidebar.open{display:block}.context{display:none}.account{margin-left:auto}.main{padding:16px}}
</style>
