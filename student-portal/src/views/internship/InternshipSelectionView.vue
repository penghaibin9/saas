<template>
  <div class="selection-page">
    <header class="selection-header">
      <div>
        <p class="selection-kicker">岗位实习中心</p>
        <h1>实习选岗</h1>
        <p>浏览学校认可实习岗位，完善材料后选择 1–3 个志愿并整组投递。</p>
      </div>
      <div class="header-actions">
        <button type="button" class="profile-entry" @click="router.push('/internship/profile')">实习档案</button>
        <button type="button" class="volunteer-entry" @click="volunteerOpen = true">我的志愿 {{ volunteerSelectedCount }}/3</button>
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
            :disabled="!context.canSelect || selectedPosition.remaining <= 0 || !volunteerEditable"
            @add-volunteer="prepareVolunteer"
            @view-company="viewCompany"
          />
        </section>

        <div class="volunteer-pane" :class="{ 'is-open': volunteerOpen }">
          <div class="volunteer-pane__mobile-head">
            <strong>我的志愿</strong>
            <button type="button" @click="volunteerOpen = false">关闭</button>
          </div>
          <div v-if="volunteerLoading" class="volunteer-state">正在加载我的志愿…</div>
          <template v-else>
            <VolunteerBoard
              :group="volunteerGroup"
              :slots="volunteerSlots"
              :candidate="candidatePosition"
              :editable="volunteerEditable"
              :busy="volunteerBusy"
              :error="volunteerError"
              @move="moveVolunteerSlot"
              @remove="removeVolunteerSlot"
              @replace="replaceVolunteerSlot"
              @statement="changeVolunteerStatement"
              @save="persistVolunteerSlots(volunteerSlots)"
            />
            <VolunteerSubmissionPanel
              :group="volunteerGroup"
              :slots="volunteerSlots"
              :preview="submissionPreview"
              :contact-sharing-mode="contactSharingMode"
              :confirmed="submissionConfirmed"
              :confirm-open="submitConfirmOpen"
              :busy="submissionBusy"
              :submit-error="submitError"
              @prepare-submit="prepareFinalSubmit"
              @cancel-confirm="cancelFinalSubmit"
              @submit="submitFinalVolunteerGroup"
              @withdraw="withdrawVolunteerGroup"
              @unlock="requestVolunteerUnlock"
              @update:contact-sharing-mode="contactSharingMode = $event"
              @update:confirmed="submissionConfirmed = $event"
            />
          </template>
        </div>
      </div>
    </main>

    <button type="button" class="volunteer-fab" @click="volunteerOpen = true">我的志愿 {{ volunteerSelectedCount }}/3</button>
    <button v-if="volunteerOpen" type="button" class="volunteer-backdrop" aria-label="关闭我的志愿" @click="volunteerOpen = false" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import RecruitmentContextBar from '../../components/recruitment/RecruitmentContextBar.vue'
import PositionSearchFilters from '../../components/recruitment/PositionSearchFilters.vue'
import PositionCard from '../../components/recruitment/PositionCard.vue'
import PositionDetail from '../../components/recruitment/PositionDetail.vue'
import VolunteerBoard from '../../components/recruitment/VolunteerBoard.vue'
import VolunteerSubmissionPanel from '../../components/recruitment/VolunteerSubmissionPanel.vue'
import { normalizeRecruitmentContext } from '../../modules/internshipRecruitment/contextModel.js'
import { normalizeMaterialPreview } from '../../modules/internshipRecruitment/materialPreviewModel.js'
import { normalizePosition } from '../../modules/internshipRecruitment/positionModel.js'
import { normalizeCatalogQuery } from '../../modules/internshipRecruitment/selectionContract.js'
import {
  buildVolunteerFinalSubmitRequest,
  normalizeVolunteerSubmitError
} from '../../modules/internshipRecruitment/submissionModel.js'
import {
  addVolunteer,
  buildVolunteerGroupSaveRequest,
  canEditVolunteerGroup,
  moveVolunteer,
  normalizeVolunteerGroup,
  removeVolunteer,
  replaceVolunteer,
  updateVolunteerStatement
} from '../../modules/internshipRecruitment/volunteerModel.js'
import { internshipSelectionApi } from '../../services/internshipSelectionApi.js'

const router = useRouter()
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
const volunteerLoading = ref(true)
const volunteerBusy = ref(false)
const volunteerError = ref('')
const volunteerGroup = ref(normalizeVolunteerGroup())
const volunteerSlots = ref(volunteerGroup.value.slots)
const candidatePosition = ref(null)
const volunteerOpen = ref(false)
const submissionPreview = ref(normalizeMaterialPreview())
const contactSharingMode = ref('AFTER_INTERVIEW')
const submissionConfirmed = ref(false)
const submitConfirmOpen = ref(false)
const submissionBusy = ref(false)
const submitError = ref({ code: '', message: '', invalidItems: [] })
let catalogRequestSeq = 0
let detailRequestSeq = 0
let volunteerRequestSeq = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / query.value.pageSize)))
const volunteerEditable = computed(() => canEditVolunteerGroup(volunteerGroup.value) && context.value.canSelect)
const volunteerSelectedCount = computed(() => volunteerSlots.value.filter((slot) => slot.positionId).length)

function resetSubmitPreview() {
  submissionPreview.value = normalizeMaterialPreview()
  submissionConfirmed.value = false
  submitConfirmOpen.value = false
  submitError.value = { code: '', message: '', invalidItems: [] }
}

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

async function loadVolunteerGroup() {
  const requestId = ++volunteerRequestSeq
  volunteerLoading.value = true
  volunteerError.value = ''
  volunteerGroup.value = normalizeVolunteerGroup({ status: 'UNAVAILABLE' })
  volunteerSlots.value = volunteerGroup.value.slots
  try {
    const data = await internshipSelectionApi.volunteers()
    if (requestId !== volunteerRequestSeq) return
    const normalized = normalizeVolunteerGroup(data || {})
    volunteerGroup.value = normalized
    volunteerSlots.value = normalized.slots
    candidatePosition.value = null
  } catch (err) {
    if (requestId !== volunteerRequestSeq) return
    volunteerGroup.value = normalizeVolunteerGroup({ status: 'UNAVAILABLE' })
    volunteerSlots.value = volunteerGroup.value.slots
    volunteerError.value = err?.message || '暂时无法读取学校志愿记录，请稍后重试；系统不会用本地数据替代学校记录。'
  } finally {
    if (requestId === volunteerRequestSeq) volunteerLoading.value = false
  }
}

async function persistVolunteerSlots(nextSlots) {
  if (!volunteerEditable.value) {
    volunteerError.value = '当前志愿状态不可直接修改。'
    return false
  }
  const previousSlots = volunteerSlots.value
  const proposedSlots = nextSlots.map((slot) => ({ ...slot, position: slot.position ? { ...slot.position } : null }))
  volunteerSlots.value = proposedSlots
  volunteerBusy.value = true
  volunteerError.value = ''
  try {
    const payload = buildVolunteerGroupSaveRequest(volunteerGroup.value, proposedSlots)
    const data = await internshipSelectionApi.saveVolunteers(payload)
    if (data) {
      const normalized = normalizeVolunteerGroup(data)
      volunteerGroup.value = normalized
      volunteerSlots.value = normalized.slots
    } else {
      await loadVolunteerGroup()
    }
    candidatePosition.value = null
    resetSubmitPreview()
    return true
  } catch (err) {
    volunteerSlots.value = previousSlots
    volunteerError.value = err?.message || '志愿整组保存失败，未保留本地修改。'
    return false
  } finally {
    volunteerBusy.value = false
  }
}

async function prepareVolunteer(position) {
  if (!volunteerEditable.value) {
    volunteerOpen.value = true
    volunteerError.value = '当前志愿组不可直接编辑，请查看当前状态说明。'
    return
  }
  if (volunteerSlots.value.some((slot) => String(slot.positionId) === String(position?.id))) {
    volunteerOpen.value = true
    return
  }
  if (volunteerSelectedCount.value >= 3) {
    candidatePosition.value = normalizePosition(position)
    volunteerOpen.value = true
    return
  }
  await persistVolunteerSlots(addVolunteer(volunteerSlots.value, position))
  volunteerOpen.value = true
}

function moveVolunteerSlot(volunteerNo, direction) {
  persistVolunteerSlots(moveVolunteer(volunteerSlots.value, volunteerNo, direction))
}
function removeVolunteerSlot(volunteerNo) {
  if (volunteerSelectedCount.value <= 1) {
    volunteerError.value = '至少保留 1 个岗位志愿；如需撤回已提交志愿，请使用整组撤回。'
    return
  }
  persistVolunteerSlots(removeVolunteer(volunteerSlots.value, volunteerNo))
}
function replaceVolunteerSlot(volunteerNo, position) {
  persistVolunteerSlots(replaceVolunteer(volunteerSlots.value, volunteerNo, position))
}
function changeVolunteerStatement(volunteerNo, statement) {
  persistVolunteerSlots(updateVolunteerStatement(volunteerSlots.value, volunteerNo, statement))
}

async function prepareFinalSubmit() {
  if (!volunteerEditable.value || submissionBusy.value) {
    submitError.value = { code: 'VOLUNTEER_NOT_EDITABLE', message: '当前志愿状态不可提交，请刷新后查看学校最新记录。', invalidItems: [] }
    return
  }
  submitError.value = { code: '', message: '', invalidItems: [] }
  submissionConfirmed.value = false
  submissionBusy.value = true
  try {
    const data = await internshipSelectionApi.materialPreview()
    submissionPreview.value = normalizeMaterialPreview(data || {})
    if (!submissionPreview.value.previewHash || !submissionPreview.value.consentPolicyVersion) {
      throw new Error('企业视角材料预览不完整，请先完善实习档案。')
    }
    submitConfirmOpen.value = true
    volunteerOpen.value = true
  } catch (err) {
    submitError.value = normalizeVolunteerSubmitError(err)
    submitConfirmOpen.value = false
  } finally {
    submissionBusy.value = false
  }
}

function cancelFinalSubmit() {
  submissionConfirmed.value = false
  submitConfirmOpen.value = false
}

async function submitFinalVolunteerGroup() {
  if (!submissionConfirmed.value || !volunteerEditable.value || submissionBusy.value) return
  submissionBusy.value = true
  submitError.value = { code: '', message: '', invalidItems: [] }
  try {
    const payload = buildVolunteerFinalSubmitRequest({
      group: volunteerGroup.value,
      preview: submissionPreview.value,
      contactSharingMode: contactSharingMode.value
    })
    await internshipSelectionApi.submitVolunteers(payload)
    submitConfirmOpen.value = false
    submissionConfirmed.value = false
    await Promise.all([loadVolunteerGroup(), loadContext()])
  } catch (err) {
    submitError.value = normalizeVolunteerSubmitError(err)
  } finally {
    submissionBusy.value = false
  }
}

async function withdrawVolunteerGroup() {
  submissionBusy.value = true
  submitError.value = { code: '', message: '', invalidItems: [] }
  try {
    await internshipSelectionApi.withdrawVolunteers({ expectedGroupVersion: volunteerGroup.value.version })
    resetSubmitPreview()
    await Promise.all([loadVolunteerGroup(), loadContext()])
  } catch (err) {
    submitError.value = normalizeVolunteerSubmitError(err)
  } finally {
    submissionBusy.value = false
  }
}

async function requestVolunteerUnlock() {
  submissionBusy.value = true
  submitError.value = { code: '', message: '', invalidItems: [] }
  try {
    await internshipSelectionApi.requestUnlock({
      expectedGroupVersion: volunteerGroup.value.version,
      reason: '学生申请重新调整岗位志愿'
    })
    await loadVolunteerGroup()
  } catch (err) {
    submitError.value = normalizeVolunteerSubmitError(err)
  } finally {
    submissionBusy.value = false
  }
}

function changePage(page) {
  loadPositions({ ...query.value, page })
}
function viewCompany(companyId) {
  if (!companyId) return
  router.push(`/internship/selection/company/${encodeURIComponent(companyId)}`)
}

onMounted(async () => {
  await Promise.all([loadContext(), loadVolunteerGroup()])
  await loadPositions(query.value)
})
onBeforeUnmount(() => {
  catalogRequestSeq += 1
  detailRequestSeq += 1
  volunteerRequestSeq += 1
})
</script>

<style scoped>
.selection-page { min-width:0; padding:20px; background:#f7f8fa; min-height:100%; }
.selection-header { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin-bottom:16px; }
.selection-kicker { margin:0 0 4px; color:#2f6bff; font-size:12px; font-weight:600; }
h1 { margin:0; color:#1a1a1a; font-size:24px; line-height:1.35; }
.selection-header p:last-child { margin:6px 0 0; color:#666; font-size:13px; }
.header-actions { display:flex; gap:8px; }
.profile-entry,.volunteer-entry { flex-shrink:0; height:36px; padding:0 13px; border:1px solid #adc6ff; border-radius:7px; background:#fff; color:#2f6bff; cursor:pointer; font-weight:600; }
.volunteer-entry { display:none; background:#2f6bff; color:#fff; border-color:#2f6bff; }
.selection-state { display:flex; align-items:center; gap:12px; padding:18px 20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; color:#595959; }
.selection-state--error { align-items:flex-start; flex-direction:column; border-color:#ffccc7; background:#fff2f0; color:#a8071a; }
.selection-state button,.catalog-state button,.catalog-pagination button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
.selection-shell { display:grid; gap:12px; margin-top:14px; }
.catalog-workspace { display:grid; grid-template-columns:360px minmax(0,1fr) 280px; gap:12px; align-items:start; }
.catalog-panel,.detail-panel,.volunteer-pane { min-width:0; }
.catalog-panel { border:1px solid #eef0f3; border-radius:10px; background:#fff; overflow:hidden; }
.catalog-summary { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:13px 14px; border-bottom:1px solid #f0f0f0; }
.catalog-summary div { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }
.catalog-summary strong { color:#1a1a1a; font-size:15px; }
.catalog-summary span { color:#8c8c8c; font-size:12px; }
.server-note { white-space:nowrap; }
.catalog-state,.volunteer-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:160px; padding:20px; color:#8c8c8c; text-align:center; }
.catalog-state--error { color:#a8071a; }
.position-list { display:flex; flex-direction:column; gap:8px; padding:10px; max-height:calc(100vh - 320px); overflow:auto; }
.catalog-pagination { display:flex; align-items:center; justify-content:center; gap:12px; padding:12px; border-top:1px solid #f0f0f0; color:#666; font-size:13px; }
.catalog-pagination button:disabled { background:#d9d9d9; cursor:not-allowed; }
.detail-panel,.volunteer-pane { position:sticky; top:12px; }
.volunteer-pane__mobile-head { display:none; }
.volunteer-fab,.volunteer-backdrop { display:none; }
@media (max-width:1439px) {
  .catalog-workspace { grid-template-columns:360px minmax(0,1fr); }
  .volunteer-entry { display:inline-flex; align-items:center; }
  .volunteer-pane { position:fixed; z-index:60; top:78px; right:18px; width:310px; max-height:calc(100vh - 96px); overflow:auto; transform:translateX(calc(100% + 32px)); transition:transform .18s ease; box-shadow:0 14px 40px rgba(25,49,83,.18); }
  .volunteer-pane.is-open { transform:translateX(0); }
  .volunteer-pane__mobile-head { display:flex; align-items:center; justify-content:space-between; padding:9px 10px; border:1px solid #dfe8f8; border-bottom:0; border-radius:10px 10px 0 0; background:#fff; }
  .volunteer-pane__mobile-head strong { color:#333; font-size:13px; }
  .volunteer-pane__mobile-head button { border:0; background:transparent; color:#2f6bff; cursor:pointer; }
  .volunteer-pane .volunteer-board { border-radius:0 0 10px 10px; }
  .volunteer-backdrop { display:block; position:fixed; z-index:50; inset:0; border:0; background:rgba(17,31,51,.18); }
}
@media (max-width:1099px) {
  .catalog-workspace { grid-template-columns:340px minmax(0,1fr); }
}
@media (max-width:899px) {
  .selection-page { padding:12px 12px 70px; }
  .selection-header { align-items:flex-start; flex-direction:column; }
  .header-actions { width:100%; }
  .profile-entry { flex:1; }
  .volunteer-entry { flex:1; justify-content:center; }
  .catalog-workspace { grid-template-columns:1fr; }
  .catalog-summary { align-items:flex-start; flex-direction:column; }
  .position-list { max-height:none; overflow:visible; }
  .detail-panel { position:static; }
  .volunteer-pane { top:auto; left:10px; right:10px; bottom:10px; width:auto; max-height:82vh; transform:translateY(calc(100% + 24px)); }
  .volunteer-pane.is-open { transform:translateY(0); }
  .volunteer-fab { display:block; position:fixed; z-index:40; left:50%; bottom:12px; transform:translateX(-50%); min-width:180px; height:42px; border:0; border-radius:21px; background:#2f6bff; color:#fff; box-shadow:0 8px 24px rgba(47,107,255,.28); font-weight:700; }
}
</style>
