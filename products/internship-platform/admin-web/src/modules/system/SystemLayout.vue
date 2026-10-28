<template>
  <ElConfigProvider :locale="zhCn"><BasePortalLayout :title="ctx?.brand?.platformName || '岗位实习管理平台'" :ctx="ctx" workspace>
    <div v-if="error" class="system-load-error" role="alert"><p>{{ error }}</p><el-button @click="load">重新加载</el-button></div>
    <p v-else-if="!ctx" role="status">正在读取学校与工作身份……</p>
    <router-view v-else :key="ctx.ctxKey" />
  </BasePortalLayout></ElConfigProvider>
</template>
<script setup>
import { ElButton, ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/button/style/css'

import { ref, onMounted } from 'vue'
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { request } from '@/services/http/client'
const ctx = ref(null), error = ref('')
async function load() {
  error.value = ''
  try { const value = await request('/system/context'); ctx.value = { ...value, ctxKey: JSON.stringify([value.tenantId, value.userId, value.currentRole?.contextId, value.currentRole?.permissionVersion]) } }
  catch (e) { ctx.value = null; error.value = e.message || '学校配置读取失败，请重试' }
}
onMounted(load)
</script>
<style scoped>.system-load-error{padding:32px}</style>
