<template>
  <div class="sp-page">
    <div class="search">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
      <input v-model.trim="kw" placeholder="搜索办事项，如：选课、请假、材料补交、成绩单、去向登记…" />
      <button v-if="kw" type="button" class="search__clear" aria-label="清空搜索" @click="clearSearch">清空</button>
    </div>

    <template v-if="kw">
      <section class="sp-card">
        <div class="sp-panel__head">搜索结果</div>
        <StateBlock v-if="!filtered.length" type="empty" :text="'未找到与「' + kw + '」相关的事项'" />
        <div v-else class="hot">
          <a v-for="h in filtered" :key="h.name" class="hotrow" @click="go(h.path)"><span class="hotdot" /><span style="flex:1">{{ h.name }}</span><span class="sp-muted">{{ h.cat }}</span></a>
        </div>
      </section>
    </template>

    <template v-else>
      <nav class="sp-tabs">
        <button v-for="c in cats" :key="c.key" class="sp-tab" :class="{ 'is-active': cat === c.key }" @click="cat = c.key">{{ c.label }}</button>
      </nav>

      <div v-if="cat === 'all'" class="catgrid">
        <a v-for="m in modules" :key="m.key" class="catcard" @click="go(m.path)">
          <span class="catic"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="m.d1" /><path :d="m.d2" /></svg></span>
          <div style="flex:1;min-width:0"><div style="font-size:14.5px;font-weight:600">{{ m.title }}</div><div class="sp-muted" style="margin-top:3px">{{ countOf(m.key) }} 项可办</div></div>
        </a>
      </div>

      <section class="sp-card">
        <div class="sp-panel__head">{{ cat === 'all' ? '热门事项' : catLabel }}</div>
        <div class="hot">
          <a v-for="h in hotShown" :key="h.name" class="hotrow" @click="go(h.path)"><span class="hotdot" /><span style="flex:1">{{ h.name }}</span><span class="sp-muted">{{ h.cat }}</span></a>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { MODULES } from '../../platform/moduleRegistry'

const route = useRoute()
const router = useRouter()
const kw = ref(String(route.query.kw || '').trim())
const cat = ref('all')
const catalog = ref([])

const modules = computed(() => MODULES.filter((m) => m.key !== 'dashboard' && m.key !== 'messages'))
const cats = [
  { key: 'all', label: '全部事项' }, { key: 'academic', label: '教务学业类' },
  { key: 'affairs', label: '学工事务类', keys: ['campusService'] }, { key: 'gradEmp', label: '毕业就业类', keys: ['graduation', 'internship', 'employment'] }
]
const catLabel = computed(() => (cats.find((c) => c.key === cat.value) || {}).label || '')

const HOT = [
  { name: '选课中心', cat: '教务学业', path: 'academic/selection', c: 'academic' }, { name: '成绩查询', cat: '教务学业', path: 'academic/grades', c: 'academic' },
  { name: '学籍异动申请', cat: '教务学业', path: 'academic/status', c: 'academic' }, { name: '毕业资格自查', cat: '教务学业', path: 'academic/graduation', c: 'academic' },
  { name: '实习周报提交', cat: '毕业就业', path: 'internship', c: 'gradEmp' }, { name: '去向登记', cat: '毕业就业', path: 'employment', c: 'gradEmp' },
  { name: '毕业设计整改重交', cat: '毕业就业', path: 'graduation', c: 'gradEmp' }, { name: '三方协议查看', cat: '毕业就业', path: 'internship', c: 'gradEmp' },
  { name: '请假销假', cat: '学工事务', path: 'campus-service', c: 'affairs' }, { name: '困难认定', cat: '学工事务', path: 'campus-service', c: 'affairs' },
  { name: '材料补交', cat: '学工事务', path: 'materials', c: 'affairs' }, { name: '奖助申请', cat: '学工事务', path: 'campus-service', c: 'affairs' },
  { name: '心理自评', cat: '学工事务', path: 'campus-service', c: 'affairs' }
]
const hotShown = computed(() => (cat.value === 'all' ? HOT : HOT.filter((h) => h.c === cat.value)))
const filtered = computed(() => {
  const query = kw.value.toLowerCase()
  return HOT.filter((item) => `${item.name}${item.cat}`.toLowerCase().includes(query))
})

function countOf(key) { return { academic: 20, graduation: 10, internship: 14, employment: 4, campusService: 8, profile: 3, orientation: 4 }[key] || 1 }
function go(path) { router.push('/' + path) }
function clearSearch() {
  kw.value = ''
  router.replace({ path: '/service-hall' })
}

watch(() => route.query.kw, (value) => {
  const next = String(value || '').trim()
  if (kw.value !== next) kw.value = next
})
watch(kw, (value) => {
  const current = String(route.query.kw || '').trim()
  if (value === current) return
  const query = value ? { ...route.query, kw: value } : { ...route.query }
  if (!value) delete query.kw
  router.replace({ path: '/service-hall', query })
})

onMounted(async () => {
  try { const d = await portalApi.serviceHallCatalog(); catalog.value = d?.items || [] } catch (e) { /* 目录失败不阻断 */ }
})
</script>

<style scoped>
.search { display: flex; align-items: center; gap: 10px; height: 46px; padding: 0 16px; background: var(--surface, #fff); border: 1px solid var(--line); border-radius: 12px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(16,24,40,.04); color: var(--t4); }
.search input { flex: 1; min-width: 0; border: none; outline: none; font-size: 14px; color: var(--t1); background: transparent; }
.search__clear { border: 0; background: transparent; color: var(--pri-text, var(--pri)); cursor: pointer; font-size: 12px; }
.catgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 16px; }
.catcard { display: flex; align-items: center; gap: 13px; padding: 17px 18px; background: var(--surface, #fff); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 1px 2px rgba(16,24,40,.04); cursor: pointer; }
.catcard:hover { border-color: var(--pri-100); }
.catic { width: 42px; height: 42px; flex: none; border-radius: 11px; background: var(--pri-50); color: var(--pri-text, var(--pri)); display: flex; align-items: center; justify-content: center; }
.hot { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.hotrow { display: flex; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; cursor: pointer; font-size: 13.5px; color: var(--t1); background: var(--surface, #fff); }
.hotrow:hover { border-color: var(--pri-100); background: var(--pri-50); }
.hotdot { width: 6px; height: 6px; border-radius: 50%; background: var(--pri); flex: none; }
@media (max-width: 900px) { .catgrid { grid-template-columns: 1fr; } .hot { grid-template-columns: 1fr; } }
</style>
