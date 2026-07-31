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
import './styles/v5-polish.css'

const cfg = usePortalConfigStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const health = useGraduationHealth()
const graduationErrors = health.items

const THEME_PRESETS = {
  purple: { display: '#7b61ff', accent: '#6045d2' },
  green: { display: '#16a078', accent: '#087858' },
  orange: { display: '#f59b23', accent: '#a75400' },
  pink: { display: '#f36ca5', accent: '#b83d72' },
  dark: { display: '#4f8bff', accent: '#71a1ff' }
}
const themeKey = ref('blue')

function normalizeHex(input, fallback = '#2f6bff') {
  const raw = String(input || '').trim().replace('#', '')
  if (/^[0-9a-f]{3}$/i.test(raw)) return `#${raw.split('').map((char) => char + char).join('')}`
  if (/^[0-9a-f]{6}$/i.test(raw)) return `#${raw}`
  return fallback
}

function shadeHex(input, factor = 0.82) {
  const hex = normalizeHex(input).slice(1)
  const channels = [0, 2, 4].map((offset) => Math.max(0, Math.min(255, Math.round(Number.parseInt(hex.slice(offset, offset + 2), 16) * factor))))
  return `#${channels.map((value) => value.toString(16).padStart(2, '0')).join('')}`
}

function rgbOf(input) {
  const hex = normalizeHex(input).slice(1)
  return [0, 2, 4].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16)).join(',')
}

const displayPrimary = computed(() => {
  if (themeKey.value === 'blue') return normalizeHex(cfg.brand?.primaryColor || '#2f6bff')
  return THEME_PRESETS[themeKey.value]?.display || '#2f6bff'
})
const readablePrimary = computed(() => {
  if (themeKey.value === 'blue') return shadeHex(displayPrimary.value, 0.78)
  return THEME_PRESETS[themeKey.value]?.accent || shadeHex(displayPrimary.value, 0.78)
})
const readableHover = computed(() => shadeHex(readablePrimary.value, 0.86))
const themeStyle = computed(() => {
  const dark = themeKey.value === 'dark'
  return {
    '--sp-primary': displayPrimary.value,
    '--sp-primary-rgb': rgbOf(displayPrimary.value),
    '--pri-display': displayPrimary.value,
    '--pri': readablePrimary.value,
    '--pri-text': readablePrimary.value,
    '--pri-h': readableHover.value,
    '--pri-on': '#ffffff',
    '--pri-50': `color-mix(in srgb, ${displayPrimary.value} 9%, ${dark ? '#1b2231' : '#fff'})`,
    '--pri-100': `color-mix(in srgb, ${displayPrimary.value} 18%, ${dark ? '#1b2231' : '#fff'})`,
    '--pri-500': readablePrimary.value,
    '--g1': `color-mix(in srgb, ${displayPrimary.value} 62%, #fff)`,
    '--g2': displayPrimary.value,
    '--bg': dark ? '#161b24' : `color-mix(in srgb, ${displayPrimary.value} 4%, #f8faff)`,
    '--surface': dark ? '#1b2231' : '#ffffff',
    '--surface-2': dark ? '#202838' : '#f8faff',
    '--field-bg': dark ? '#202838' : '#f8faff',
    '--t1': dark ? '#f2f6ff' : '#172033',
    '--t2': dark ? '#d2daea' : '#3f4b63',
    '--t3': dark ? '#adb9cf' : '#65728a',
    '--t4': dark ? '#91a0ba' : '#5f6f89',
    '--line': dark ? '#34405a' : '#dfe5ef',
    '--line2': dark ? '#2a3448' : '#ebeff5'
  }
})

const showGraduationPanel = computed(() => route.name === 'graduation-workbench')
const showGraduationHealth = computed(() => showGraduationPanel.value && graduationErrors.value.length > 0)

function setTheme(key) {
  const allowed = key === 'blue' || Object.prototype.hasOwnProperty.call(THEME_PRESETS, key)
  themeKey.value = allowed ? key : 'blue'
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
