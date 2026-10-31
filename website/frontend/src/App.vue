<template><OfficialHeader v-if="publicPage" /><RouterView /><OfficialFooter v-if="publicPage" /></template>
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import OfficialHeader from './components/official-site/OfficialHeader.vue'
import OfficialFooter from './components/official-site/OfficialFooter.vue'
const route = useRoute()
const publicPage = computed(() => !/^\/manage(?:\/|$)/.test(route.path))
</script>
<style>
html{scroll-behavior:smooth}body{margin:0;font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#172f49}*{box-sizing:border-box}button,input,select,textarea{font:inherit}a{color:inherit}button,a{touch-action:manipulation}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #2268df;outline-offset:3px}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style>
