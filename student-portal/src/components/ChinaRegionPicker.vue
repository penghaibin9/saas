<template>
  <div ref="root" class="region-picker" :class="{ 'is-open': open }" @keydown.esc="closePicker">
    <button type="button" class="region-picker__trigger" :aria-expanded="open" aria-haspopup="dialog" @click="togglePicker">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
        <circle cx="12" cy="10" r="2.4" />
      </svg>
      <span :class="{ 'is-placeholder': !modelValue }">{{ modelValue || placeholder }}</span>
      <svg class="region-picker__chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="m7 10 5 5 5-5" />
      </svg>
    </button>

    <div v-if="open" class="region-picker__panel" role="dialog" aria-label="选择工作城市">
      <div class="region-picker__search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3-3" />
        </svg>
        <input v-model.trim="keyword" aria-label="搜索省、市或区县" placeholder="搜索省、市或区县" />
        <button v-if="keyword" type="button" aria-label="清空搜索" @click.prevent="keyword = ''">×</button>
      </div>

      <div v-if="keyword" class="region-picker__results">
        <button v-for="item in searchResults" :key="item.countyCode" type="button" @click="chooseSearchResult(item)">
          <span>{{ item.label }}</span>
          <small>选择</small>
        </button>
        <div v-if="!searchResults.length" class="region-picker__empty">没有找到匹配地区</div>
      </div>

      <div v-else class="region-picker__columns">
        <section>
          <header>省份</header>
          <div class="region-picker__list">
            <button v-for="item in provinces" :key="item.code" type="button"
                    :class="{ 'is-active': provinceCode === item.code }" @click="chooseProvince(item.code)">
              {{ item.name }}
            </button>
          </div>
        </section>
        <section>
          <header>城市</header>
          <div class="region-picker__list">
            <button v-for="item in cities" :key="item.code" type="button"
                    :class="{ 'is-active': cityCode === item.code }" @click="chooseCity(item.code)">
              {{ item.name }}
            </button>
            <div v-if="!provinceCode" class="region-picker__empty">请先选择省份</div>
          </div>
        </section>
        <section>
          <header>区／县</header>
          <div class="region-picker__list">
            <button v-for="item in counties" :key="item.code" type="button"
                    :class="{ 'is-active': countyCode === item.code }" @click="chooseCounty(item.code)">
              {{ item.name }}
            </button>
            <div v-if="!cityCode" class="region-picker__empty">请先选择城市</div>
          </div>
        </section>
      </div>

      <footer v-if="!keyword" class="region-picker__footer">
        <span>{{ previewLabel || '请选择工作城市' }}</span>
        <button type="button" :disabled="!cityCode" @click="confirmCity">选择当前城市</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  CHINA_PROVINCES,
  citiesForProvince,
  countiesForCity,
  regionLabel,
  resolveChinaRegion,
  searchChinaRegions
} from '../data/chinaRegions'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请选择省、市、区县' }
})
const emit = defineEmits(['update:modelValue'])

const root = ref(null)
const open = ref(false)
const keyword = ref('')
const provinceCode = ref('')
const cityCode = ref('')
const countyCode = ref('')

const provinces = CHINA_PROVINCES
const cities = computed(() => citiesForProvince(provinceCode.value))
const counties = computed(() => countiesForCity(cityCode.value))
const previewLabel = computed(() => regionLabel(provinceCode.value, cityCode.value, countyCode.value))
const searchResults = computed(() => searchChinaRegions(keyword.value))

function syncFromValue(value) {
  const resolved = resolveChinaRegion(value)
  provinceCode.value = resolved?.provinceCode || ''
  cityCode.value = resolved?.cityCode || ''
  countyCode.value = resolved?.countyCode || ''
}

function togglePicker() {
  open.value ? closePicker() : openPicker()
}
function openPicker() {
  syncFromValue(props.modelValue)
  keyword.value = ''
  open.value = true
}
function closePicker() {
  open.value = false
  keyword.value = ''
}
function chooseProvince(code) {
  provinceCode.value = code
  cityCode.value = ''
  countyCode.value = ''
}
function chooseCity(code) {
  cityCode.value = code
  countyCode.value = ''
}
function chooseCounty(code) {
  countyCode.value = code
  commit(previewLabel.value)
}
function confirmCity() {
  commit(regionLabel(provinceCode.value, cityCode.value))
}
function chooseSearchResult(item) {
  provinceCode.value = item.provinceCode
  cityCode.value = item.cityCode
  countyCode.value = item.countyCode
  commit(item.label)
}
function commit(value) {
  emit('update:modelValue', value)
  closePicker()
}
function onOutsidePointer(event) {
  if (open.value && root.value && !root.value.contains(event.target)) closePicker()
}

watch(() => props.modelValue, syncFromValue, { immediate: true })
onMounted(() => document.addEventListener('pointerdown', onOutsidePointer))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onOutsidePointer))
</script>

<style scoped>
.region-picker { position:relative; width:100%; }
.region-picker__trigger { width:100%; height:43px; padding:0 12px; display:flex; align-items:center; gap:9px; border:1px solid var(--line); border-radius:9px; background:var(--surface,#fff); color:var(--t1); font:inherit; text-align:left; cursor:pointer; transition:border-color .15s ease,box-shadow .15s ease; }
.region-picker__trigger:hover,.region-picker.is-open .region-picker__trigger { border-color:var(--pri); box-shadow:0 0 0 3px var(--pri-50); }
.region-picker__trigger > svg { width:17px; height:17px; flex:none; color:var(--pri); }
.region-picker__trigger span { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }
.region-picker__trigger span.is-placeholder { color:var(--t4); }
.region-picker__trigger .region-picker__chevron { width:15px; height:15px; color:var(--t4); transition:transform .15s ease; }
.region-picker.is-open .region-picker__chevron { transform:rotate(180deg); }
.region-picker__panel { position:absolute; z-index:80; left:0; top:calc(100% + 7px); width:min(620px,calc(100vw - 120px)); padding:12px; border:1px solid var(--line); border-radius:14px; background:var(--surface,#fff); box-shadow:0 18px 48px rgba(26,48,82,.18); }
.region-picker__search { height:40px; padding:0 11px; display:flex; align-items:center; gap:8px; border:1px solid var(--line); border-radius:10px; background:var(--field-bg,#f8faff); color:var(--t4); }
.region-picker__search:focus-within { border-color:var(--pri); box-shadow:0 0 0 3px var(--pri-50); }
.region-picker__search svg { width:15px; height:15px; flex:none; }
.region-picker__search input { flex:1; min-width:0; border:0; outline:0; background:transparent; color:var(--t1); font:inherit; font-size:12.5px; }
.region-picker__search button { all:unset; width:22px; height:22px; cursor:pointer; display:grid; place-items:center; border-radius:50%; color:var(--t4); }
.region-picker__search button:hover { background:var(--pri-50); color:var(--pri); }
.region-picker__columns { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:10px; }
.region-picker__columns section { min-width:0; border:1px solid var(--line2); border-radius:10px; overflow:hidden; background:var(--surface-2,#f8faff); }
.region-picker__columns header { height:31px; padding:0 10px; display:flex; align-items:center; border-bottom:1px solid var(--line2); color:var(--t3); font-size:11px; font-weight:700; }
.region-picker__list { height:224px; padding:5px; overflow-y:auto; }
.region-picker__list::-webkit-scrollbar,.region-picker__results::-webkit-scrollbar { width:5px; }
.region-picker__list::-webkit-scrollbar-thumb,.region-picker__results::-webkit-scrollbar-thumb { border-radius:5px; background:var(--line); }
.region-picker__list > button { width:100%; min-height:32px; padding:5px 8px; border:0; border-radius:7px; background:transparent; color:var(--t2); font:inherit; font-size:12px; text-align:left; cursor:pointer; }
.region-picker__list > button:hover { background:var(--pri-50); color:var(--pri-text,var(--pri)); }
.region-picker__list > button.is-active { background:var(--pri-100); color:var(--pri-text,var(--pri)); font-weight:700; }
.region-picker__results { max-height:270px; margin-top:10px; overflow-y:auto; }
.region-picker__results > button { width:100%; min-height:39px; padding:7px 10px; display:flex; align-items:center; justify-content:space-between; gap:14px; border:0; border-radius:8px; background:transparent; color:var(--t2); font:inherit; font-size:12.5px; text-align:left; cursor:pointer; }
.region-picker__results > button:hover { background:var(--pri-50); color:var(--pri-text,var(--pri)); }
.region-picker__results small { flex:none; color:var(--pri-text,var(--pri)); }
.region-picker__empty { padding:20px 8px; color:var(--t4); font-size:11.5px; text-align:center; }
.region-picker__footer { min-height:44px; margin-top:9px; padding-top:9px; display:flex; align-items:center; justify-content:space-between; gap:12px; border-top:1px solid var(--line2); }
.region-picker__footer span { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--t3); font-size:11.5px; }
.region-picker__footer button { flex:none; min-height:32px; padding:0 12px; border:0; border-radius:8px; background:var(--pri); color:#fff; font:inherit; font-size:11.5px; font-weight:700; cursor:pointer; }
.region-picker__footer button:disabled { opacity:.45; cursor:not-allowed; }
@media(max-width:700px){.region-picker__panel{position:fixed;left:12px;right:12px;top:76px;width:auto}.region-picker__columns{grid-template-columns:1fr}.region-picker__list{height:112px}}
</style>
