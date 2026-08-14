<template>
  <div class="selection-page">
    <header class="selection-header">
      <div>
        <p class="selection-kicker">岗位实习中心</p>
        <h1>实习选岗</h1>
        <p>浏览学校认可实习岗位，完善材料后选择 1–3 个志愿并整组投递。</p>
      </div>
    </header>

    <div v-if="loading" class="selection-state">正在加载当前招聘季…</div>
    <div v-else-if="error" class="selection-state selection-state--error">
      <strong>招聘季信息加载失败</strong>
      <span>{{ error }}</span>
      <button type="button" @click="loadContext">重新加载</button>
    </div>
    <RecruitmentContextBar v-else :context="context" />

    <main class="selection-shell" aria-label="实习选岗工作区">
      <PositionSearchFilters v-model="query" @search="loadPositions" />

      <section class="catalog-panel" aria-live="polite">
        <div class="catalog-summary">
          <div>
            <strong>学校认可岗位</strong>
            <span v-if="!catalogLoading">共 {{ total }} 个符合条件的岗位</span>
          </div>
          <span class="server-note">服务端筛选 · 每页 {{ query.pageSize }} 条</span>
        </div>

        <div v-if="catalogLoading" class="catalog-state">正在查询岗位…</div>
        <div v-else-if="catalogError" class="catalog-state catalog-state--error">
          <span>{{ catalogError }}</span>
          <button type="button" @click="loadPositions(query)">重新查询</button>
        </div>
        <div v-else-if="!positions.length" class="catalog-state">暂无符合条件的岗位，请调整筛选条件。</div>
        <div v-else class="catalog-rows">
          <button
            v-for="position in positions"
            :key="position.id"
            type="button"
            class="catalog-row"
            @click="selectedPositionId = position.id"
          >
            <strong>{{ position.title || position.positionName || '岗位名称待完善' }}</strong>
            <span>{{ position.companyName || '企业信息待完善' }}</span>
            <span>{{ position.workLocation || position.city || '地点待定' }}</span>
          </button>
        </div>

        <div v-if="totalPages > 1" class="catalog-pagination">
          <button type="button" :disabled="query.page <= 1 || catalogLoading" @click="changePage(query.page - 1)">上一页</button>
          <span>第 {{ query.page }} / {{ totalPages }} 页</span>
          <button type="button" :disabled="query.page >= totalPages || catalogLoading" @click="changePage(query.page + 1)">下一页</button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import RecruitmentContextBar from '../../components/recruitment/RecruitmentContextBar.vue'
import PositionSearchFilters from '../../components/recruitment/PositionSearchFilters.vue'
import { normalizeRecruitmentContext } from '../../modules/internshipRecruitment/contextModel'
import { normalizeCatalogQuery } from '../../modules/internshipRecruitment/selectionContract'
import { internshipSelectionApi } from '../../services/internshipSelectionApi'

const loading = ref(true)
const error = ref('')
const context = ref(normalizeRecruitmentContext())
const query = ref(normalizeCatalogQuery({
  page: 1, pageSize: 20, keyword: '', city: '', companyId: '', accommodation: '', meal: '', sort: 'RECOMMENDED'
}))
const positions = ref([])
const total = ref(0)
const catalogLoading = ref(false)
const catalogError = ref('')
const selectedPositionId = ref(null)
let catalogRequestSeq = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / query.value.pageSize)))

async function loadContext() {
  loading.value = true
  error.value = ''
  try {
    context.value = normalizeRecruitmentContext(await internshipSelectionApi.context())
  } catch (err) {
    error.value = err?.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

async function loadPositions(nextQuery = query.value) {
  const normalized = normalizeCatalogQuery(nextQuery)
  query.value = normalized
  const requestId = ++catalogRequestSeq
  catalogLoading.value = true
  catalogError.value = ''
  try {
    const data = await internshipSelectionApi.positions(normalized)
    if (requestId !== catalogRequestSeq) return
    const items = data?.items || data?.list || []
    positions.value = Array.isArray(items) ? items : []
    total.value = Number(data?.total ?? data?.pagination?.total ?? positions.value.length) || 0
    if (selectedPositionId.value && !positions.value.some((item) => String(item.id) === String(selectedPositionId.value))) {
      selectedPositionId.value = null
    }
  } catch (err) {
    if (requestId !== catalogRequestSeq) return
    positions.value = []
    total.value = 0
    catalogError.value = err?.message || '岗位查询失败，请稍后重试'
  } finally {
    if (requestId === catalogRequestSeq) catalogLoading.value = false
  }
}

function changePage(page) {
  loadPositions({ ...query.value, page })
}

onMounted(async () => {
  await loadContext()
  await loadPositions(query.value)
})
onBeforeUnmount(() => { catalogRequestSeq += 1 })
</script>

<style scoped>
.selection-page { min-width:0; padding:20px; background:#f7f8fa; min-height:100%; }
.selection-header { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin-bottom:16px; }
.selection-kicker { margin:0 0 4px; color:#2f6bff; font-size:12px; font-weight:600; }
h1 { margin:0; color:#1a1a1a; font-size:24px; line-height:1.35; }
.selection-header p:last-child { margin:6px 0 0; color:#666; font-size:13px; }
.selection-state { display:flex; align-items:center; gap:12px; padding:18px 20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; color:#595959; }
.selection-state--error { align-items:flex-start; flex-direction:column; border-color:#ffccc7; background:#fff2f0; color:#a8071a; }
.selection-state button,.catalog-state button,.catalog-pagination button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
.selection-shell { display:grid; gap:12px; margin-top:14px; }
.catalog-panel { min-width:0; border:1px solid #eef0f3; border-radius:10px; background:#fff; overflow:hidden; }
.catalog-summary { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:13px 14px; border-bottom:1px solid #f0f0f0; }
.catalog-summary div { display:flex; align-items:baseline; gap:10px; }
.catalog-summary strong { color:#1a1a1a; font-size:15px; }
.catalog-summary span { color:#8c8c8c; font-size:12px; }
.server-note { white-space:nowrap; }
.catalog-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:160px; padding:20px; color:#8c8c8c; }
.catalog-state--error { color:#a8071a; }
.catalog-rows { display:flex; flex-direction:column; }
.catalog-row { display:grid; grid-template-columns:minmax(220px,1.4fr) minmax(160px,1fr) minmax(120px,.8fr); gap:12px; width:100%; padding:14px; border:0; border-bottom:1px solid #f3f3f3; background:#fff; text-align:left; cursor:pointer; }
.catalog-row:hover { background:#f7faff; }
.catalog-row strong { color:#1a1a1a; }
.catalog-row span { color:#666; font-size:13px; }
.catalog-pagination { display:flex; align-items:center; justify-content:center; gap:12px; padding:12px; border-top:1px solid #f0f0f0; color:#666; font-size:13px; }
.catalog-pagination button:disabled { background:#d9d9d9; cursor:not-allowed; }
@media (max-width:899px) {
  .selection-page { padding:12px; }
  .catalog-summary { align-items:flex-start; flex-direction:column; }
  .catalog-row { grid-template-columns:1fr; gap:4px; }
}
</style>
