<template>
  <ApprovedShowcaseView v-if="ready" />
  <PortalLegacyView v-else-if="checked" />
  <main v-else class="showcase-loading" aria-live="polite">
    <strong>跃科</strong>
    <h1>服务学生成长，成就教师发展。</h1>
    <p>正在载入产品展厅…</p>
    <a :href="TEACHER_LOGIN_URL">学校用户入口</a>
    <a :href="OFFICIAL_SITE_CONTACT.phoneHref">电话咨询 {{ OFFICIAL_SITE_CONTACT.phone }}</a>
  </main>
</template>
<script setup>
import { defineAsyncComponent, onMounted, onBeforeUnmount, ref } from 'vue'
import { hasShowcaseAssets } from '../components/official-site/showcase/asset-gate.js'
import { TEACHER_LOGIN_URL } from '../config/portalConfig.js'
import { OFFICIAL_SITE_CONTACT } from '../config/officialSalesPages.js'
const ApprovedShowcaseView = defineAsyncComponent(() => import('./official-site/ApprovedShowcaseView.vue'))
const PortalLegacyView = defineAsyncComponent(() => import('./PortalLegacyView.vue'))
const ready = ref(false)
const checked = ref(false)
const controller = new AbortController()
onMounted(async () => {
  const found = await hasShowcaseAssets({ signal: controller.signal })
  if (controller.signal.aborted) return
  ready.value = found
  checked.value = true
})
onBeforeUnmount(() => controller.abort())
</script>
<style scoped>
.showcase-loading{min-height:60vh;padding:12vh 7vw;color:#e9f3ff;background:#091b2c;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.showcase-loading strong{font-size:25px}.showcase-loading h1{font-size:clamp(24px,4vw,46px);line-height:1.5}
.showcase-loading p{color:#acc1d6}.showcase-loading a{display:inline-flex;margin:12px 24px 0 0;min-height:44px;align-items:center;color:#85d5ff}
</style>
