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
    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraduationExtensionPanel from './components/graduation/GraduationExtensionPanel.vue'
import { usePortalConfigStore } from './stores/portalConfig'
import { useUiStore } from './stores/ui'
import { useGraduationHealth } from './stores/graduationHealth'
import './styles/graduation-usability.css'
import './styles/v5-overrides.css'

const cfg = usePortalConfigStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const health = useGraduationHealth()
const graduationErrors = health.items

const THEME_COLORS = {
  purple: '#7b61ff',
  green: '#16a078',
  orange: '#f59b23',
  pink: '#f36ca5',
  dark: '#4f8bff'
}
const themeKey = ref('blue')
const primary = computed(() => THEME_COLORS[themeKey.value] || cfg.brand?.primaryColor || '#2f6bff')
const primaryRgb = computed(() => {
  const hex = String(primary.value || '#2f6bff').replace('#', '')
  const value = hex.length === 3 ? hex.split('').map((c) => c + c).join('') : hex.padEnd(6, '0').slice(0, 6)
  const number = Number.parseInt(value, 16)
  if (!Number.isFinite(number)) return '47,107,255'
  return `${(number >> 16) & 255},${(number >> 8) & 255},${number & 255}`
})
const themeStyle = computed(() => ({
  '--sp-primary': primary.value,
  '--sp-primary-rgb': primaryRgb.value,
  '--pri': primary.value,
  '--pri-h': `color-mix(in srgb, ${primary.value} 84%, #000)`,
  '--pri-50': `color-mix(in srgb, ${primary.value} 9%, #fff)`,
  '--pri-100': `color-mix(in srgb, ${primary.value} 18%, #fff)`,
  '--pri-500': primary.value,
  '--g1': `color-mix(in srgb, ${primary.value} 62%, #fff)`,
  '--g2': primary.value,
  '--bg': themeKey.value === 'dark' ? '#161b24' : `color-mix(in srgb, ${primary.value} 4%, #f8faff)`
}))

const showGraduationPanel = computed(() => route.name === 'graduation-workbench')
const showGraduationHealth = computed(() => showGraduationPanel.value && graduationErrors.value.length > 0)

function setTheme(key) {
  themeKey.value = THEME_COLORS[key] || key === 'blue' ? key : 'blue'
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
  const saved = window.localStorage.getItem('student-portal-theme') || 'blue'
  setTheme(saved)
  window.addEventListener('student-portal-theme-change', onThemeChange)
})
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
