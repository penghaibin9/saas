<template>
  <div class="desk-utilities">
    <template v-if="!scopeMode">
      <button class="desk-trigger" :aria-expanded="panel === 'weather'" @click="toggle('weather')"><PartlyCloudy /><span>{{ city.name }} {{ weather ? `${Math.round(weather.temperature_2m)}° ${condition}` : '天气' }}</span></button>
      <span class="desk-divider" />
      <button class="desk-trigger desk-date" :aria-expanded="panel === 'date'" @click="toggle('date')"><Calendar /><span>{{ dateLabel }}</span></button>
    </template>
    <template v-else>
      <button class="desk-trigger desk-scope" :aria-expanded="panel === 'scope'" @click="toggle('scope')"><CircleCheck /><span>当前范围</span><ArrowDown /></button>
      <span class="desk-divider" />
      <button class="desk-trigger desk-timer" :aria-expanded="panel === 'timer'" @click="toggle('timer')"><Timer /><span>本次工作 {{ duration }}</span></button>
    </template>
    <div v-if="panel" class="desk-panel" @keydown.esc.stop.prevent="panel = ''">
      <header><strong>{{ { weather: `${city.name}天气`, date: '日期与时间', scope: '当前数据范围', timer: '本次工作' }[panel] }}</strong><button aria-label="关闭" @click="panel = ''"><Close /></button></header>
      <template v-if="panel === 'weather'">
        <p class="desk-temperature">{{ weather ? `${Math.round(weather.temperature_2m)}°C · ${condition}` : '—' }}</p>
        <p role="status">{{ weatherError || (weatherBusy ? '正在更新…' : '天气数据来自 Open-Meteo') }}</p>
        <form class="desk-city" @submit.prevent="searchCity"><input v-model="cityQuery" aria-label="搜索天气城市" placeholder="搜索城市" /><button :disabled="cityBusy">搜索</button></form>
        <p v-if="cityMessage" role="status">{{ cityMessage }}</p>
        <button v-for="item in cities" :key="item.id" class="desk-city-result" @click="chooseCity(item)">{{ item.name }} · {{ item.admin1 || item.country }}</button>
        <button class="desk-link" :disabled="weatherBusy" @click="loadWeather">刷新天气</button>
      </template>
      <template v-else-if="panel === 'date'"><p class="desk-full-date">{{ new Date(now).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) }}</p><p>{{ new Date(now).toLocaleTimeString('zh-CN', { hour12: false }) }}</p></template>
      <p v-else-if="panel === 'scope'">{{ scopeName || '按当前身份授权范围' }}</p>
      <template v-else><p class="desk-temperature">{{ duration }}</p><button class="desk-link" @click="resetTimer">重新计时</button></template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { PartlyCloudy, Calendar, CircleCheck, ArrowDown, Timer, Close } from '@element-plus/icons-vue'
const props = defineProps({ scopeMode: Boolean, scopeName: { type: String, default: '' }, identityKey: { type: String, default: '' } })
const panel = ref(''), now = ref(Date.now()), started = ref(Date.now())
const city = ref({ name: '北京', latitude: 39.9042, longitude: 116.4074 })
const weather = ref(null), weatherError = ref(''), weatherBusy = ref(false)
const cityQuery = ref(''), cities = ref([]), cityMessage = ref(''), cityBusy = ref(false)
let clock, weatherRequest, cityRequest
const dateLabel = computed(() => new Date(now.value).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', weekday: 'short' }) + ' ' + new Date(now.value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }))
const duration = computed(() => { const seconds = Math.max(0, Math.floor((now.value - started.value) / 1000)); return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map(x => String(x).padStart(2, '0')).join(':') })
const condition = computed(() => { const code = weather.value?.weather_code; if (code === 0) return '晴'; if (code <= 3) return ['晴', '晴间多云', '多云', '阴'][code]; if ([45, 48].includes(code)) return '雾'; if (code >= 95) return '雷雨'; if ([71, 73, 75, 77, 85, 86].includes(code)) return '雪'; if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return '雨'; return '天气待确认' })
function toggle(name) { panel.value = panel.value === name ? '' : name }
function resetTimer() { started.value = Date.now(); try { sessionStorage.setItem(`teacher-work-start:${props.identityKey}`, String(started.value)) } catch { /* Storage is optional. */ } }
function outside(event) { if (!event.target.closest('.desk-utilities')) panel.value = '' }
async function loadWeather() {
  weatherRequest?.abort(); const request = new AbortController(); weatherRequest = request
  const timeout = setTimeout(() => request.abort(), 10000)
  weatherBusy.value = true; weatherError.value = ''
  try {
    const params = new URLSearchParams({ latitude: city.value.latitude, longitude: city.value.longitude, current: 'temperature_2m,weather_code', timezone: 'auto' })
    const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`, { signal: request.signal })
    if (!response.ok) throw new Error()
    const result = await response.json()
    if (!Number.isFinite(result.current?.temperature_2m)) throw new Error()
    if (weatherRequest === request) weather.value = result.current
  } catch { if (weatherRequest === request) weatherError.value = weather.value ? '更新失败，显示上次天气' : '天气暂不可用，请重试' }
  finally { clearTimeout(timeout); if (weatherRequest === request) weatherBusy.value = false }
}
async function searchCity() {
  if (!cityQuery.value.trim()) return
  cityRequest?.abort(); const request = new AbortController(); cityRequest = request
  const timeout = setTimeout(() => request.abort(), 10000)
  cityBusy.value = true; cityMessage.value = ''; cities.value = []
  try {
    const response = await fetch(`https://geocoding-api.open-meteo.com/v1/search?${new URLSearchParams({ name: cityQuery.value.trim(), count: '5', language: 'zh', format: 'json' })}`, { signal: request.signal })
    if (!response.ok) throw new Error()
    const result = await response.json()
    if (cityRequest === request) { cities.value = result.results || []; if (!cities.value.length) cityMessage.value = '未找到城市' }
  } catch { if (cityRequest === request) cityMessage.value = '城市搜索暂不可用' }
  finally { clearTimeout(timeout); if (cityRequest === request) cityBusy.value = false }
}
function chooseCity(item) { city.value = item; cities.value = []; weather.value = null; try { localStorage.setItem('student-ui-weather-city-v1', JSON.stringify(item)) } catch { /* Storage is optional. */ } loadWeather() }
onMounted(() => {
  clock = setInterval(() => { now.value = Date.now() }, 1000)
  document.addEventListener('click', outside)
  if (props.scopeMode) { try { const saved = Number(sessionStorage.getItem(`teacher-work-start:${props.identityKey}`)); if (saved > 0 && saved <= now.value) started.value = saved; else resetTimer() } catch { /* Storage is optional. */ } }
  else { try { const saved = JSON.parse(localStorage.getItem('student-ui-weather-city-v1')); if (saved?.name && Number.isFinite(saved.latitude) && Number.isFinite(saved.longitude)) city.value = saved } catch { /* Invalid city falls back to Beijing. */ } loadWeather() }
})
onBeforeUnmount(() => { clearInterval(clock); document.removeEventListener('click', outside); weatherRequest?.abort(); cityRequest?.abort() })
</script>

<style scoped>
.desk-utilities{display:flex;align-items:center;gap:12px;position:relative;flex:none;color:var(--t3);font-size:12px}.desk-trigger{display:flex;align-items:center;gap:7px;white-space:nowrap;border:0;background:transparent;color:inherit;padding:7px 4px;font:inherit;cursor:pointer}.desk-utilities svg{width:17px;height:17px;flex:none}.desk-divider{height:17px;width:1px;background:var(--line)}.desk-scope,.desk-timer{padding:7px 10px;border-radius:6px;background:var(--surface);border:1px solid var(--line)}.desk-timer{background:var(--pri-50);color:var(--pri);border-color:transparent;font-variant-numeric:tabular-nums}.desk-panel{position:absolute;right:0;top:calc(100% + 14px);width:286px;padding:18px;border:1px solid var(--line);border-radius:12px;background:var(--surface);box-shadow:0 16px 48px -16px #14294440;z-index:60;color:var(--t1)}.desk-panel header{display:flex;align-items:center;justify-content:space-between}.desk-panel header button{border:0;background:transparent;color:var(--t3);cursor:pointer}.desk-panel p{line-height:1.7;color:var(--t3)}.desk-panel .desk-temperature{font-size:24px;color:var(--t1);margin:18px 0 8px;font-variant-numeric:tabular-nums}.desk-city{display:flex;gap:6px}.desk-city input{min-width:0;flex:1;background:var(--surface-2);border:1px solid var(--line);border-radius:5px;padding:7px;color:var(--t1)}.desk-city button,.desk-link{background:var(--pri-50);border:0;border-radius:5px;color:var(--pri);padding:7px 10px;cursor:pointer}.desk-link{margin-top:12px}.desk-city-result{display:block;width:100%;text-align:left;padding:8px;border:0;background:transparent;color:var(--t1);cursor:pointer}.desk-city-result:hover{background:var(--pri-50)}button:focus-visible{outline:2px solid var(--pri);outline-offset:2px}@media(max-width:1250px){.desk-utilities:not(:has(.desk-scope)){display:none}}@media(max-width:1000px){.desk-timer,.desk-divider{display:none}}
</style>
