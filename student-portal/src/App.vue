<template>
  <div class="sp-app" :style="themeStyle">
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
    <!-- 低频扩展事项放在主流程之后，避免遮挡选题、任务书、开题等首屏主线。 -->
    <GraduationExtensionPanel v-if="showGraduationPanel" />
    <SystemDialogHost />
    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraduationExtensionPanel from './components/graduation/GraduationExtensionPanel.vue'
import SystemDialogHost from './components/SystemDialogHost.vue'
import { useUiStore } from './stores/ui'
import { useGraduationHealth } from './stores/graduationHealth'
import './styles/graduation-usability.css'
import './styles/v5-overrides.css'
import './styles/v5-polish.css'
import { normalizeTheme, themeTokens } from './platform/workspaceTheme'

const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const health = useGraduationHealth()
const graduationErrors = health.items

const themeKey = ref('blue')
const themeStyle = computed(() => themeTokens(themeKey.value))

const showGraduationPanel = computed(() => route.name === 'graduation-workbench')
const showGraduationHealth = computed(() => showGraduationPanel.value && graduationErrors.value.length > 0)

function setTheme(key) {
  themeKey.value = normalizeTheme(key)
  document.documentElement.dataset.spTheme = themeKey.value
}

function onThemeChange(event) {
  setTheme(event?.detail || 'blue')
}
function retryGraduation() {
  health.clear()
  router.go(0)
}

onMounted(() => {
  // 挂载子布局前已接收到账号配色时，不再用旧的全局偏好覆盖。
  if (!document.documentElement.dataset.spTheme) {
    try { setTheme(window.localStorage.getItem('student-portal-theme') || 'blue') } catch { setTheme('blue') }
  }
})
window.addEventListener('student-portal-theme-change', onThemeChange)
onBeforeUnmount(() => window.removeEventListener('student-portal-theme-change', onThemeChange))
</script>

<style scoped>
.gd-health { margin:16px auto; max-width:1120px; padding:14px 16px; display:flex; align-items:flex-start; justify-content:space-between; gap:20px; border:1px solid #ffccc7; border-radius:14px; background:#fff2f0; color:#5c0011; box-shadow:0 6px 22px rgba(207,19,34,.08); }
.gd-health strong { font-size:14px; }
.gd-health p { margin:5px 0; font-size:13px; line-height:1.6; }
.gd-health ul { margin:6px 0 0; padding-left:18px; font-size:12px; line-height:1.6; color:#8c2f39; }
.gd-health button { flex:none; min-height:36px; padding:0 14px; border:1px solid #ff7875; border-radius:9px; background:#fff; color:#cf1322; cursor:pointer; }
@media (max-width: 700px) { .gd-health { margin:10px; flex-direction:column; gap:10px; }.gd-health button { width:100%; } }
</style>
