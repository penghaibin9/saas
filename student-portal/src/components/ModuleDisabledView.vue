<template>
  <div class="sp-center">
    <div class="sp-empty-card">
      <div class="sp-empty-icon">🚧</div>
      <h2>该模块未开通</h2>
      <p>「{{ moduleTitle }}」模块未开通，请联系学校管理员开通后再使用。</p>
      <RouterLink class="sp-btn" to="/portal/home">返回首页</RouterLink>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { moduleByPath } from '../platform/moduleRegistry'

const route = useRoute()
const moduleTitle = computed(() => moduleByPath(route.params.module)?.title || route.params.module || '该')
</script>
