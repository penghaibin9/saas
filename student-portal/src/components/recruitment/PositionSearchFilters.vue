<template>
  <section class="catalog-filters" aria-label="岗位搜索与筛选">
    <div class="catalog-search-row">
      <label class="catalog-search">
        <span aria-hidden="true">⌕</span>
        <input
          :value="draft.keyword"
          type="search"
          placeholder="搜索岗位、企业、地点"
          @input="onKeywordInput"
          @keydown.enter.prevent="flushKeyword"
        />
        <button v-if="draft.keyword" type="button" aria-label="清空搜索" @click="clearKeyword">×</button>
      </label>
      <select v-model="draft.sort" class="catalog-sort" aria-label="排序" @change="emitSearch">
        <option value="RECOMMENDED">推荐</option>
        <option value="LATEST">最新</option>
        <option value="REMUNERATION">薪资</option>
        <option value="REMAINING">剩余名额</option>
      </select>
    </div>

    <div class="quick-filters">
      <input v-model.trim="draft.city" class="filter-control" placeholder="城市" @change="emitSearch" />
      <select v-model="draft.majorMatched" class="filter-control" @change="emitSearch">
        <option value="">专业匹配</option>
        <option value="true">仅看匹配</option>
      </select>
      <input v-model.trim="draft.remuneration" class="filter-control" placeholder="最低薪资" inputmode="numeric" @change="emitSearch" />
      <select v-model="draft.accommodation" class="filter-control" @change="emitSearch">
        <option value="">住宿</option><option value="true">提供住宿</option><option value="false">不提供</option>
      </select>
      <select v-model="draft.meal" class="filter-control" @change="emitSearch">
        <option value="">餐食</option><option value="true">提供餐食</option><option value="false">不提供</option>
      </select>
      <button type="button" class="more-button" :aria-expanded="moreOpen" @click="moreOpen = !moreOpen">
        更多筛选{{ activeMoreCount ? ` · ${activeMoreCount}` : '' }}
      </button>
      <button v-if="hasActiveFilters" type="button" class="reset-button" @click="reset">重置</button>
    </div>

    <div v-if="moreOpen" class="more-filters">
      <input v-model.trim="draft.companyId" class="filter-control" placeholder="企业" @change="emitSearch" />
      <input v-model.trim="draft.industry" class="filter-control" placeholder="行业" @change="emitSearch" />
      <input v-model.trim="draft.scale" class="filter-control" placeholder="企业规模" @change="emitSearch" />
      <select v-model="draft.nightShift" class="filter-control" @change="emitSearch">
        <option value="">夜班</option><option value="false">无夜班</option><option value="true">含夜班</option>
      </select>
      <input v-model.trim="draft.weeklyHours" class="filter-control" placeholder="周工时上限" inputmode="numeric" @change="emitSearch" />
      <input v-model.trim="draft.remaining" class="filter-control" placeholder="最低剩余名额" inputmode="numeric" @change="emitSearch" />
      <AppDatePicker v-model="draft.publishedFrom" class="filter-control" aria-label="发布时间起" @change="emitSearch" />
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AppDatePicker from '../AppDatePicker.vue'

const props = defineProps({ modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue', 'search'])
const moreOpen = ref(false)
const draft = reactive({ ...props.modelValue })
let keywordTimer = null

watch(() => props.modelValue, (value) => Object.assign(draft, value || {}), { deep: true })

const MORE_KEYS = ['companyId', 'industry', 'scale', 'nightShift', 'weeklyHours', 'remaining', 'publishedFrom']
const activeMoreCount = computed(() => MORE_KEYS.filter((key) => draft[key] !== '' && draft[key] !== null && draft[key] !== undefined).length)
const hasActiveFilters = computed(() => Object.entries(draft).some(([key, value]) => key !== 'sort' && key !== 'page' && key !== 'pageSize' && value !== '' && value !== null && value !== undefined))

function snapshot() {
  return { ...draft, page: 1 }
}
function emitSearch() {
  clearTimeout(keywordTimer)
  const value = snapshot()
  emit('update:modelValue', value)
  emit('search', value)
}
function onKeywordInput(event) {
  draft.keyword = event.target.value
  clearTimeout(keywordTimer)
  keywordTimer = setTimeout(emitSearch, 350)
}
function flushKeyword() {
  emitSearch()
}
function clearKeyword() {
  draft.keyword = ''
  emitSearch()
}
function reset() {
  Object.assign(draft, {
    page: 1, pageSize: 20, keyword: '', city: '', companyId: '', accommodation: '', meal: '',
    sort: 'RECOMMENDED', industry: '', scale: '', nightShift: '', weeklyHours: '', remaining: '',
    publishedFrom: '', majorMatched: '', remuneration: ''
  })
  emitSearch()
}

onBeforeUnmount(() => clearTimeout(keywordTimer))
</script>

<style scoped>
.catalog-filters { padding:14px; border:1px solid #eef0f3; border-radius:10px; background:#fff; }
.catalog-search-row { display:flex; gap:10px; }
.catalog-search { display:flex; align-items:center; gap:8px; flex:1; min-width:0; height:40px; padding:0 12px; border:1px solid #d9d9d9; border-radius:8px; background:#fff; }
.catalog-search:focus-within { border-color:#2f6bff; box-shadow:0 0 0 2px rgba(47,107,255,.08); }
.catalog-search input { flex:1; min-width:0; border:0; outline:0; color:#1a1a1a; font:inherit; }
.catalog-search button { border:0; background:transparent; color:#8c8c8c; cursor:pointer; font-size:18px; }
.catalog-sort,.filter-control { height:36px; border:1px solid #d9d9d9; border-radius:6px; padding:0 10px; background:#fff; color:#333; }
.catalog-sort { height:40px; min-width:108px; }
.quick-filters,.more-filters { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:10px; }
.filter-control { max-width:132px; }
.more-button,.reset-button { height:36px; border:1px solid #d9d9d9; border-radius:6px; padding:0 12px; background:#fff; color:#595959; cursor:pointer; }
.reset-button { border-color:transparent; color:#2f6bff; }
@media (max-width:899px) {
  .catalog-search-row { align-items:stretch; flex-direction:column; }
  .catalog-sort { width:100%; }
  .filter-control { max-width:none; flex:1 1 44%; min-width:120px; }
}
</style>
