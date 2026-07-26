<template>
  <div class="sp-app" :style="{ '--sp-primary': primary }">
    <section v-if="showGraduationHealth" class="gd-health" role="alert">
      <div>
        <strong>部分毕业设计环节加载失败</strong>
        <p>{{ graduationErrors.map((item) => item.label).join('、') }}。这不是“暂无业务”，请重试后再办理。</p>
        <ul>
          <li v-for="item in graduationErrors" :key="item.key">{{ item.label }}：{{ item.message }}</li>
        </ul>
      </div>
      <button type="button" @click="retryGraduation">重新加载</button>
    </section>
    <router-view />
    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePortalConfigStore } from './stores/portalConfig'
import { useUiStore } from './stores/ui'
import { useGraduationHealth } from './stores/graduationHealth'

const cfg = usePortalConfigStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const health = useGraduationHealth()
const graduationErrors = health.items
const primary = computed(() => cfg.brand?.primaryColor || '#1677ff')
const showGraduationHealth = computed(() =>
  String(route.path || '').includes('/graduation') && graduationErrors.value.length > 0
)

function retryGraduation() {
  health.clear()
  // 当前毕业设计工作台会重新执行所有分板块真实请求，避免只刷新壳不刷新业务数据。
  router.go(0)
}
</script>

<style scoped>
.gd-health { margin:16px auto; max-width:1120px; padding:14px 16px; display:flex; align-items:flex-start; justify-content:space-between; gap:20px; border:1px solid #ffccc7; border-radius:10px; background:#fff2f0; color:#5c0011; }
.gd-health strong { font-size:14px; }
.gd-health p { margin:5px 0; font-size:13px; line-height:1.6; }
.gd-health ul { margin:6px 0 0; padding-left:18px; font-size:12px; line-height:1.6; color:#8c2f39; }
.gd-health button { flex:none; min-height:36px; padding:0 14px; border:1px solid #ff7875; border-radius:8px; background:#fff; color:#cf1322; cursor:pointer; }
</style>
