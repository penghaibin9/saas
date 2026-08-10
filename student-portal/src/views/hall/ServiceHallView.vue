<template>
  <div class="sp-page">
    <div class="search">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
      <input v-model.trim="kw" placeholder="搜索已开通事项，如：教务学业、岗位实习、材料补交…" />
      <button v-if="kw" type="button" class="search__clear" aria-label="清空搜索" @click="clearSearch">清空</button>
    </div>

    <StateBlock v-if="loading" type="loading" text="正在读取学校已开通事项…" />
    <StateBlock v-else-if="error" type="error" :text="error" />

    <template v-else-if="kw">
      <section class="sp-card">
        <div class="sp-panel__head">搜索结果</div>
        <StateBlock v-if="!filtered.length" type="empty" :text="'未找到与「' + kw + '」相关的已开通事项'" />
        <div v-else class="hot">
          <button v-for="item in filtered" :key="item.key" type="button" class="hotrow" @click="go(item.path)">
            <span class="hotdot" />
            <span style="flex:1">{{ item.label }}</span>
            <span class="sp-muted">{{ item.categoryLabel }}</span>
          </button>
        </div>
      </section>
    </template>

    <template v-else-if="catalogItems.length">
      <nav class="sp-tabs">
        <button v-for="c in visibleCats" :key="c.key" class="sp-tab" :class="{ 'is-active': cat === c.key }" @click="cat = c.key">{{ c.label }}</button>
      </nav>

      <div class="catgrid">
        <button v-for="item in shownItems" :key="item.key" type="button" class="catcard" @click="go(item.path)">
          <span class="catic">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="item.d1" /><path :d="item.d2" /></svg>
          </span>
          <div style="flex:1;min-width:0;text-align:left">
            <div style="font-size:14.5px;font-weight:600">{{ item.label }}</div>
            <div class="sp-muted" style="margin-top:3px">学校已开通 · 点击进入正式页面</div>
          </div>
        </button>
      </div>

      <section class="sp-card">
        <div class="sp-panel__head">入口说明</div>
        <p class="sp-muted hall-note">这里仅展示服务端返回的“本校已开通模块”。事项数量、热门入口和目标地址不再由浏览器硬编码；未登记或未开通的能力不会伪装成可办事项。</p>
      </section>
    </template>

    <StateBlock v-else type="empty" text="当前学校没有返回可办事项。请联系学校管理员核对学生门户模块开通配置。" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { moduleByKey } from '../../platform/moduleRegistry'

const route = useRoute()
const router = useRouter()
const kw = ref(String(route.query.kw || '').trim())
const cat = ref('all')
const catalog = ref([])
const loading = ref(true)
const error = ref('')

const CATEGORY_BY_KEY = {
  profile: 'profile',
  orientation: 'affairs',
  campusService: 'affairs',
  academic: 'academic',
  graduation: 'gradEmp',
  internship: 'gradEmp',
  employment: 'gradEmp'
}
const cats = [
  { key: 'all', label: '全部事项' },
  { key: 'academic', label: '教务学业类' },
  { key: 'affairs', label: '学生事务类' },
  { key: 'gradEmp', label: '毕业就业类' },
  { key: 'profile', label: '个人信息类' }
]

const catalogItems = computed(() => catalog.value
  .filter((item) => item && item.key && item.path && !['dashboard', 'messages'].includes(item.key))
  .map((item) => {
    const registry = moduleByKey(item.key)
    const category = CATEGORY_BY_KEY[item.key] || 'all'
    return {
      key: String(item.key),
      label: String(item.label || registry?.title || item.key),
      path: String(item.path).replace(/^\/+/, ''),
      category,
      categoryLabel: (cats.find((c) => c.key === category) || cats[0]).label,
      d1: registry?.d1 || 'M5 5h14v14H5z',
      d2: registry?.d2 || 'M8 9h8M8 13h8'
    }
  }))

const visibleCats = computed(() => cats.filter((c) => c.key === 'all' || catalogItems.value.some((item) => item.category === c.key)))
const shownItems = computed(() => cat.value === 'all' ? catalogItems.value : catalogItems.value.filter((item) => item.category === cat.value))
const filtered = computed(() => {
  const query = kw.value.toLowerCase()
  return catalogItems.value.filter((item) => `${item.label}${item.categoryLabel}`.toLowerCase().includes(query))
})

function go(path) {
  const normalized = String(path || '').replace(/^\/+/, '')
  if (!normalized) return
  router.push('/' + normalized)
}

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
watch(visibleCats, (items) => {
  if (!items.some((item) => item.key === cat.value)) cat.value = 'all'
})

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await portalApi.serviceHallCatalog()
    catalog.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    catalog.value = []
    error.value = e?.message || '办事大厅目录读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.search { display: flex; align-items: center; gap: 10px; height: 46px; padding: 0 16px; background: var(--surface, #fff); border: 1px solid var(--line); border-radius: 12px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(16,24,40,.04); color: var(--t4); }
.search input { flex: 1; min-width: 0; border: none; outline: none; font-size: 14px; color: var(--t1); background: transparent; }
.search__clear { border: 0; background: transparent; color: var(--pri-text, var(--pri)); cursor: pointer; font-size: 12px; }
.catgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 16px; }
.catcard { width: 100%; display: flex; align-items: center; gap: 13px; padding: 17px 18px; background: var(--surface, #fff); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 1px 2px rgba(16,24,40,.04); cursor: pointer; color: var(--t1); font: inherit; }
.catcard:hover { border-color: var(--pri-100); }
.catic { width: 42px; height: 42px; flex: none; border-radius: 11px; background: var(--pri-50); color: var(--pri-text, var(--pri)); display: flex; align-items: center; justify-content: center; }
.hot { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.hotrow { width: 100%; display: flex; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid var(--line); border-radius: 10px; cursor: pointer; font-size: 13.5px; color: var(--t1); background: var(--surface, #fff); text-align: left; }
.hotrow:hover { border-color: var(--pri-100); background: var(--pri-50); }
.hotdot { width: 6px; height: 6px; border-radius: 50%; background: var(--pri); flex: none; }
.hall-note { margin: 0; line-height: 1.7; }
@media (max-width: 900px) { .catgrid { grid-template-columns: 1fr; } .hot { grid-template-columns: 1fr; } }
</style>
