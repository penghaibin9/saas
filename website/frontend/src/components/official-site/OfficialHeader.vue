<template>
  <header class="site-header" @keydown.esc="closeMenu(true)">
    <a class="skip-link" href="#main">跳到主要内容</a>
    <div class="site-nav">
      <RouterLink class="site-brand" to="/" aria-label="跃科官网首页"><span class="brand-mark">跃</span><span><strong>跃科</strong><small>服务学生成长 · 成就教师发展</small></span></RouterLink>
      <nav class="desktop-links" aria-label="官网导航"><template v-for="item in items" :key="item.path"><a v-if="item.external" :href="item.path">{{ item.label }}</a><RouterLink v-else :to="item.path" active-class="" :class="{ current: isCurrent(item.path) }" :aria-current="isCurrent(item.path) ? 'page' : undefined">{{ item.label }}</RouterLink></template></nav>
      <div class="nav-actions"><RouterLink class="system-link" to="/#login">系统登录 ↗</RouterLink><RouterLink class="consult-link" :to="contactRoute">预约产品演示 ↗</RouterLink><button ref="menuButton" class="menu-button" aria-controls="website-mobile-menu" :aria-expanded="open" @click="open = !open">{{ open ? '收起' : '菜单' }}</button></div>
    </div>
    <nav v-if="open" id="website-mobile-menu" class="mobile-links" aria-label="手机官网导航"><template v-for="item in items" :key="item.path"><a v-if="item.external" :href="item.path" @click="closeMenu()">{{ item.label }}</a><RouterLink v-else :to="item.path" @click="closeMenu()">{{ item.label }}</RouterLink></template><RouterLink to="/#login" @click="closeMenu()">系统登录 ↗</RouterLink></nav>
  </header>
</template>
<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { COMPANY_NAVIGATION as items, solutionContactRoute } from '../../config/companyProducts.js'
const route = useRoute()
const open = ref(false), menuButton = ref(null), hydrated = ref(false)
onMounted(() => { hydrated.value = true })
const contactRoute = computed(() => ({ path: '/contact', query: route.path.startsWith('/products/') ? { product: route.path.split('/').at(-1) } : route.path === '/contact' ? (hydrated.value ? route.query : {}) : (solutionContactRoute(route.path).query || {}) }))
function isCurrent(path) { if (path.includes('#')) return route.path === '/' && route.hash === '#showcase'; return route.path === path || route.path.startsWith(path + '/') }
function closeMenu(focus = false) { open.value = false; if (focus) menuButton.value?.focus() }
watch(() => route.fullPath, () => closeMenu())
</script>

