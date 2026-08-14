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

      <div class="catalog-workspace">
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
          <div v-else class="position-list">
            <PositionCard
              v-for="position in positions"
              :key="position.id"
              :position="position"
              :selected="String(selectedPositionId) === String(position.id)"
              @select="selectPosition"
            />
          </div>

          <div v-if="totalPages > 1" class="catalog-pagination">
            <button type="button" :disabled="query.page <= 1 || catalogLoading" @click="changePage(query.page - 1)">上一页</button>
            <span>第 {{ query.page }} / {{ totalPages }} 页</span>
            <button type="button" :disabled="query.page >= totalPages || catalogLoading" @click="changePage(query.page + 1)">下一页</button>
          </div>
        </section>

        <section class="detail-panel" aria-live="polite">
          <div v-if="detailLoading" class="catalog-state">正在加载岗位详情…</div>
          <div v-else-if="detailError" class="catalog-state catalog-state--error">
            <span>{{ detailError }}</span>
            <button v-if="selectedPositionId" type="button" @click="selectPosition(selectedPositionId, true)">重新加载</button>
          </div>
          <div v-else-if="!selectedPosition" class="catalog-state">从左侧选择一个岗位查看完整实习条件。</div>
          <PositionDetail
            v-else
            :position="selectedPosition"
            :disabled="!context.canSelect || selectedPosition.remaining <= 0"
            @add-volunteer="prepareVolunteer"
            @view-company="viewCompany"
          />
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import RecruitmentContextBar from '../../components/recruitment/RecruitmentContextBar.vue'
import PositionSearchFilters from '../../components/recruitment/PositionSearchFilters.vue'
import PositionCard from '../../components/recruitment/PositionCard.vue'
import PositionDetail from '../../components/recruitment/PositionDetail.vue'
import { normalizeRecruitmentContext } from '../../modules/internshipRecruitment/contextModel'
import { normalizePosition } from '../../modules/internshipRecruitment/positionModel'
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
const selectedPosition = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const pendingVolunteerPositionId = ref(null)
const pendingCompanyId = ref(null)
let catalogRequestSeq = 0
let detailRequestSeq = 0

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
    positions.value = (Array.isArray(items) ? items : []).map(normalizePosition)
    total.value = Number(data?.total ?? data?.pagination?.total ?? positions.value.length) || 0
    const currentStillVisible = positions.value.find((item) => String(item.id) === String(selectedPositionId.value))
    if (!currentStillVisible) {
      selectedPositionId.value = null
      selectedPosition.value = null
      if (positions.value[0]?.id) await selectPosition(positions.value[0].id)
    }
  } catch (err) {
    if (requestId !== catalogRequestSeq) return
    positions.value = []
    total.value = 0
    selectedPositionId.value = null
    selectedPosition.value = null
    catalogError.value = err?.message || '岗位查询失败，请稍后重试'
  } finally {
    if (requestId === catalogRequestSeq) catalogLoading.value = false
  }
}

async function selectPosition(positionId, force = false) {
  if (!positionId) return
  if (!force && String(selectedPositionId.value) === String(positionId) && selectedPosition.value) return
  selectedPositionId.value = positionId
  const requestId = ++detailRequestSeq
  detailLoading.value = true
  detailError.value = ''
  try {
    const data = await internshipSelectionApi.position(positionId)
    if (requestId !== detailRequestSeq) return
    selectedPosition.value = normalizePosition(data || {})
  } catch (err) {
    if (requestId !== detailRequestSeq) return
    selectedPosition.value = positions.value.find((item) => String(item.id) === String(positionId)) || null
    detailError.value = err?.message || '岗位详情加载失败，请稍后重试'
  } finally {
    if (requestId === detailRequestSeq) detailLoading.value = false
  }
}

function changePage(page) {
  loadPositions({ ...query.value, page })
}

function prepareVolunteer(position) {
  pendingVolunteerPositionId.value = position?.id || null
}

function viewCompany(companyId) {
  pendingCompanyId.value = companyId || null
}

onMounted(async () => {
  await loadContext()
  await loadPositions(query.value)
})
onBeforeUnmount(() => {
  catalogRequestSeq += 1
  detailRequestSeq += 1
})
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
.catalog-workspace { display:grid; grid-template-columns:360px minmax(0,1fr); gap:12px; align-items:start; }
.catalog-panel,.detail-panel { min-width:0; }
.catalog-panel { border:1px solid #eef0f3; border-radius:10px; background:#fff; overflow:hidden; }
.catalog-summary { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:13px 14px; border-bottom:1px solid #f0f0f0; }
.catalog-summary div { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }
.catalog-summary strong { color:#1a1a1a; font-size:15px; }
.catalog-summary span { color:#8c8c8c; font-size:12px; }
.server-note { white-space:nowrap; }
.catalog-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:160px; padding:20px; color:#8c8c8c; text-align:center; }
.catalog-state--error { color:#a8071a; }
.position-list { display:flex; flex-direction:column; gap:8px; padding:10px; max-height:calc(100vh - 320px); overflow:auto; }
.catalog-pagination { display:flex; align-items:center; justify-content:center; gap:12px; padding:12px; border-top:1px solid #f0f0f0; color:#666; font-size:13px; }
.catalog-pagination button:disabled { background:#d9d9d9; cursor:not-allowed; }
.detail-panel { position:sticky; top:12px; }
@media (max-width:1099px) {
  .catalog-workspace { grid-template-columns:340px minmax(0,1fr); }
}
@media (max-width:899px) {
  .selection-page { padding:12px; }
  .catalog-workspace { grid-template-columns:1fr; }
  .catalog-summary { align-items:flex-start; flex-direction:column; }
  .position-list { max-height:none; overflow:visible; }
  .detail-panel { position:static; }
}
</style>
