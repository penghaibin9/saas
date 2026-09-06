<template>
  <div class="sp-page">
    <section class="sp-card material-head">
      <div>
        <div class="sp-panel__head">材料补交中心</div>
        <p v-if="materialReturnContext.bizType" class="sp-muted">仅显示这份{{ materialReturnContext.bizType === 'FUNDING' ? '奖助' : bizLabel(materialReturnContext.bizType) }}申请的材料 <button class="link" @click="backToApplication">返回原申请</button></p>
        <p class="sp-muted">老师登记缺项后在这里按项补交。每次提交审核都会形成新版本，历史版本不会被覆盖。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <nav class="sp-tabs">
      <button v-for="item in filters" :key="item.key" class="sp-tab" :class="{ 'is-active': filter === item.key }" @click="filter = item.key">
        {{ item.label }}<span v-if="item.count" class="count">{{ item.count }}</span>
      </button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="正在加载材料缺项…" />
    <div v-else-if="error" class="error-box"><strong>材料列表加载失败</strong><span>{{ error }}</span><button class="sp-btn sp-btn--ghost" @click="load">重试</button></div>
    <StateBlock v-else-if="!shown.length" type="empty" text="当前没有需要处理的材料" />

    <section v-for="item in shown" :key="item.requirementId" :id="`material-${item.requirementId}`" class="sp-card requirement" :class="{ focus: String(item.requirementId) === focusId }">
      <div class="req-head">
        <div>
          <div class="title-line"><strong>{{ item.itemName }}</strong><StatusTag :text="item.statusLabel || '状态待确认'" :tone="tone(item)" /></div>
          <div class="sp-muted">{{ bizLine(item) }} · 第 {{ item.returnRound || 1 }} 轮</div>
          <div v-if="item.requirementReason" class="reason">缺项说明：{{ item.requirementReason }}</div>
          <div v-if="item.dueAt" class="sp-muted" :class="{ overdue: item.overdue }">截止 {{ fmt(item.dueAt) }}{{ item.overdue ? '（已逾期）' : '' }}</div>
        </div>
        <div class="owner"><span>审核责任人</span><strong>{{ item.reviewOwner || '待分配' }}</strong></div>
      </div>

      <div v-if="canSubmit(item)" class="submit-box">
        <label class="file-pick">
          <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.zip" :disabled="!!submitting" @change="selectFile(item, $event)" />
          <span>{{ selectedFiles[item.requirementId]?.name || '选择补交文件' }}</span>
        </label>
        <input v-model.trim="notes[item.requirementId]" :disabled="!!submitting" maxlength="500" class="sp-inp" placeholder="补充说明（选填）" />
        <button class="sp-btn" :disabled="!!submitting || !selectedFiles[item.requirementId]" @click="prepareSubmit(item)">
          {{ submitting === item.requirementId ? '正在处理…' : uploadedFiles[item.requirementId] ? '检查并提交审核' : '上传并提交审核' }}
        </button>
      </div>
      <div v-else-if="item.status === 'PENDING_REVIEW'" class="pending-note">最新版本已提交，等待老师审核，请勿重复上传。</div>
      <p v-if="uploadedFiles[item.requirementId] && canSubmit(item)" class="pending-note" role="status">{{ materialFileHint(uploadedFiles[item.requirementId]) }}</p>

      <div class="version-title">版本记录（{{ item.versionCount || 0 }}）</div>
      <div v-if="!(item.versions || []).length" class="sp-muted">尚未上传材料</div>
      <div v-for="version in (item.versions || [])" :key="version.submissionId" class="version-row">
        <div>
          <strong>V{{ version.versionNo }} · {{ version.fileName }}</strong>
          <div class="sp-muted">{{ fmtTime(version.submittedAt) }} · {{ version.statusLabel || '状态待确认' }}</div>
          <div v-if="version.reviewNote" class="review-note">审核意见：{{ version.reviewNote }}</div>
        </div>
        <div class="version-actions">
          <span v-if="version.current" class="current-tag">当前版本</span>
          <button v-if="version.downloadable" class="link" @click="download(version)">下载</button>
        </div>
      </div>
    </section>
    <div v-if="!focusId && items.length < total" class="load-more">
      <button class="sp-btn sp-btn--ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '正在加载…' : `加载更多（已显示 ${items.length}/${total}）` }}</button>
    </div>
    <dialog ref="submitDialog" class="material-confirm" aria-labelledby="material-confirm-title" @cancel="cancelSubmission($event)">
      <h2 id="material-confirm-title">确认提交材料</h2>
      <p>{{ pendingSubmission?.itemName }}</p>
      <p class="sp-muted">{{ selectedFiles[pendingSubmission?.requirementId]?.name }} · 提交后等待老师审核，历史版本会保留。</p>
      <p v-if="uploadedFiles[pendingSubmission?.requirementId]" class="pending-note" role="status">{{ materialFileHint(uploadedFiles[pendingSubmission.requirementId]) }}</p>
      <p v-if="submitError" class="review-note" role="alert">{{ submitError }}</p>
      <div class="confirm-actions">
        <button class="sp-btn sp-btn--ghost" :disabled="!!submitting" @click="cancelSubmission">返回检查</button>
        <button class="sp-btn" :disabled="!!submitting" @click="submit(pendingSubmission)">{{ submitting ? '正在处理…' : uploadedFiles[pendingSubmission?.requirementId] ? '检查并提交审核' : '确认提交' }}</button>
      </div>
    </dialog>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, watch, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'
import fileSdk from '../../services/fileSdk'
import { useUiStore } from '../../stores/ui'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const items = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loadingMore = ref(false)
const filter = ref('open')
const submitting = ref('')
const submitDialog = ref(null)
const pendingSubmission = ref(null)
const submitError = ref('')
const selectedFiles = reactive({})
const notes = reactive({})
const uploadedFiles = reactive({})
const unregisterForm = inject('registerWorkspaceForm', null)?.(() => !!submitting.value || Object.values(selectedFiles).some(Boolean) || Object.values(notes).some(value => String(value || '').trim()), () => !!submitting.value)
onBeforeUnmount(() => unregisterForm?.())
function materialFileHint(file) {
  if (file.readyForBusiness === true) return '文件已上传且安全可用，确认后提交老师审核。'
  if (file.scanStatus === 'ERROR') return '安全扫描失败，请稍后检查；持续失败可更换文件或联系学校管理员。'
  if (['PENDING', 'RUNNING'].includes(file.scanStatus)) return '文件已上传，正在等待安全扫描；稍后点击“检查并提交审核”，无需重复上传。'
  if (['INFECTED', 'QUARANTINED'].includes(file.scanStatus) || file.status === 'QUARANTINED') return '文件存在安全风险，请更换文件后重新提交。'
  return '文件尚不可提交，请检查最新状态或更换文件。'
}
// SP-M01：深链现在完全由服务端 action_projection_service 生成，query 里保留的是
// actionParams 原始参数名 materialRequirementId；requirementId 只作兼容旧外链保留。
const focusId = computed(() => String(route.query.materialRequirementId || route.query.requirementId || ''))
const leaveContext = computed(() => ['LEAVE', 'AID', 'FUNDING'].includes(route.query.bizType) && /^\d+$/.test(String(route.query.bizId || '')) ? { bizType: route.query.bizType, bizId: route.query.bizId } : {})
const materialReturnContext = computed(() => {
  if (leaveContext.value.bizType) return leaveContext.value
  const row = items.value.find(item => String(item.requirementId) === focusId.value)
  return row && ['LEAVE', 'AID', 'FUNDING'].includes(row.bizType) && /^\d+$/.test(String(row.bizId || '')) ? { bizType: row.bizType, bizId: String(row.bizId) } : {}
})
function backToApplication() { const context = materialReturnContext.value; if (!context.bizType) return; router.push({ name: 'campus-service', query: { tab: context.bizType === 'FUNDING' ? 'funding' : context.bizType === 'AID' ? 'aid' : 'leave', recordId: context.bizId } }) }

const openStates = new Set(['MISSING', 'RETURNED', 'PENDING_REVIEW'])
const filters = computed(() => [
  { key: 'open', label: '待处理', count: items.value.filter((x) => openStates.has(x.status)).length },
  { key: 'done', label: '已完成', count: items.value.filter((x) => ['ACCEPTED', 'WAIVED'].includes(x.status)).length },
  { key: 'all', label: '全部', count: items.value.length }
])
const shown = computed(() => {
  const list = filter.value === 'all'
    ? items.value
    : items.value.filter((x) => filter.value === 'open' ? openStates.has(x.status) : ['ACCEPTED', 'WAIVED'].includes(x.status))
  return [...list].sort((a, b) => (String(b.requirementId) === focusId.value ? 1 : 0) - (String(a.requirementId) === focusId.value ? 1 : 0))
})

function bizLabel(value) {
  return ({ LEAVE: '请假', AID: '困难认定', FUNDING: '奖助申请', DISCIPLINE: '违纪处分', DISCIPLINE_APPEAL: '处分申诉', DORM_TRANSFER: '调宿申请', CREDIT_APPEAL: '第二课堂申诉', SECOND_CLASS_APPEAL: '第二课堂申诉' }[value] || '学工申请')
}
// 学生看不懂"业务记录 #123"。后端下发 businessContext 时用业务语言
// （如"2026-03-01 ~ 2026-03-05 · 请假申请"），没下发时退回原有可读文案。
function bizLine(item) {
  const c = item.businessContext || {}
  const parts = [c.bizPeriod, c.bizDisplayTitle || bizLabel(item.bizType), c.bizDisplaySubtitle].filter(Boolean)
  return parts.length ? parts.join(' · ') : `${bizLabel(item.bizType)} · 业务记录 #${item.bizId}`
}
function fmt(value) { return value ? String(value).replace('T', ' ').slice(0, 10) : '' }
function fmtTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' }
function tone(item) { if (item.overdue || item.status === 'RETURNED') return 'warn'; if (['ACCEPTED', 'WAIVED'].includes(item.status)) return 'success'; return 'default' }
function canSubmit(item) { return (item.allowedActions || []).includes('SUBMIT_MATERIAL') }
function selectFile(item, event) {
  if (submitting.value) return
  const file = event.target.files?.[0]
  if (!file) return
  selectedFiles[item.requirementId] = file
  delete uploadedFiles[item.requirementId]
}

let loadGeneration = 0
async function load(reset = true) {
  const generation = ++loadGeneration
  loading.value = true
  loadingMore.value = false
  error.value = ''
  try {
    if (reset) page.value = 1
    const data = await affairsFourEndApi.myMaterialRequirements({
      page: page.value, pageSize, ...leaveContext.value,
      requirementId: focusId.value || undefined
    })
    if (generation !== loadGeneration) return
    items.value = data?.items || []
    total.value = Number(data?.total || 0)
    if (focusId.value) {
      const target = items.value.find((x) => String(x.requirementId) === focusId.value)
      if (target && ['ACCEPTED', 'WAIVED'].includes(target.status)) filter.value = 'all'
      await nextTick()
      document.getElementById(`material-${focusId.value}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  } catch (e) {
    if (generation === loadGeneration) error.value = e?.message || '材料列表加载失败'
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

async function loadMore() {
  if (loading.value || loadingMore.value || items.value.length >= total.value) return
  const generation = loadGeneration
  loadingMore.value = true
  try {
    const nextPage = page.value + 1
    const data = await affairsFourEndApi.myMaterialRequirements({ page: nextPage, pageSize, ...leaveContext.value, requirementId: focusId.value || undefined })
    if (generation !== loadGeneration) return
    items.value = items.value.concat(data?.items || [])
    total.value = Number(data?.total || total.value)
    page.value = nextPage
  } catch (e) {
    if (generation === loadGeneration) ui.notify(e?.message || '更多材料加载失败')
  } finally {
    if (generation === loadGeneration) loadingMore.value = false
  }
}

function prepareSubmit(item) {
  if (submitting.value || !selectedFiles[item.requirementId]) return
  pendingSubmission.value = item
  submitError.value = ''
  submitDialog.value?.showModal()
}
function cancelSubmission(event) {
  if (submitting.value) { event?.preventDefault?.(); return }
  submitDialog.value?.close()
  pendingSubmission.value = null
}
async function submit(item) {
  if (!item || submitting.value) return
  const file = selectedFiles[item.requirementId]
  if (!file) return ui.notify('请先选择补交文件')
  submitError.value = ''
  submitting.value = item.requirementId
  try {
    if (!uploadedFiles[item.requirementId]) uploadedFiles[item.requirementId] = await affairsFourEndApi.uploadMaterialFile(file)
    const uploaded = uploadedFiles[item.requirementId]
    const metadata = await fileSdk.metadata(uploaded.fileId)
    uploadedFiles[item.requirementId] = metadata
    if (metadata.readyForBusiness !== true) return
    await affairsFourEndApi.submitMaterialVersion(item.requirementId, uploaded.fileId, item.version, notes[item.requirementId] || '')
    ui.notify('材料已补交，等待老师审核')
    selectedFiles[item.requirementId] = null
    notes[item.requirementId] = ''
    delete uploadedFiles[item.requirementId]
    submitDialog.value?.close()
    pendingSubmission.value = null
    await load()
  } catch (e) {
    submitError.value = e?.message || '材料补交失败，文件与说明已保留，请重试'
  } finally {
    submitting.value = ''
  }
}

async function download(version) {
  try { await affairsFourEndApi.downloadMaterial(version.fileId, version.fileName) }
  catch (e) { ui.notify(e?.message || '材料下载失败') }
}

watch(() => [focusId.value, leaveContext.value.bizType, leaveContext.value.bizId], () => {
  submitDialog.value?.close()
  pendingSubmission.value = null
  for (const drafts of [selectedFiles, notes, uploadedFiles]) for (const key of Object.keys(drafts)) delete drafts[key]
  items.value = []
  total.value = 0
  filter.value = 'open'
  load()
}, { immediate: true })
</script>

<style scoped>
.material-head,.req-head,.title-line,.version-row,.version-actions{display:flex;align-items:flex-start}.material-head,.req-head,.version-row{justify-content:space-between;gap:18px}.material-head{align-items:center;margin-bottom:16px}.count{margin-left:6px;font-size:11px}.requirement{margin-bottom:14px;scroll-margin-top:24px}.requirement.focus{outline:2px solid var(--pri);outline-offset:2px}.title-line{align-items:center;gap:9px}.reason{margin-top:8px;color:var(--t2);font-size:13px}.overdue{color:#b45309}.owner{min-width:120px;text-align:right}.owner span,.owner strong{display:block}.owner span{font-size:12px;color:var(--t3);margin-bottom:4px}.submit-box{display:grid;grid-template-columns:minmax(180px,1fr) minmax(220px,2fr) auto;gap:10px;margin:16px 0;padding:14px;background:#f8fafc;border-radius:10px}.file-pick{display:flex;align-items:center;padding:0 12px;border:1px dashed #b8c4d6;border-radius:9px;cursor:pointer;font-size:13px;color:var(--pri);overflow:hidden}.file-pick input{position:absolute;width:1px;height:1px;opacity:0}.file-pick:focus-within{outline:2px solid var(--pri);outline-offset:3px}.file-pick span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pending-note{margin:14px 0;padding:11px 13px;background:#eff6ff;border-radius:9px;color:#1d4ed8;font-size:13px}.version-title{font-size:14px;font-weight:650;margin:18px 0 6px}.version-row{padding:11px 0;border-bottom:1px solid var(--line2)}.version-actions{align-items:center;gap:10px}.current-tag{padding:3px 7px;border-radius:6px;background:var(--pri-50);color:var(--pri);font-size:11px}.link{all:unset;cursor:pointer;color:var(--pri);font-size:13px}.review-note{margin-top:4px;color:#b45309;font-size:12px}.error-box{display:flex;align-items:center;gap:12px;padding:14px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;color:#9a3412}.load-more{display:flex;justify-content:center;padding:6px 0 22px}
@media(max-width:900px){.req-head,.material-head{flex-direction:column}.owner{text-align:left}.submit-box{grid-template-columns:1fr}.version-row{gap:10px}.error-box{align-items:flex-start;flex-direction:column}}
.submit-box{background:var(--bg)}.file-pick{border-color:var(--line)}.pending-note{background:var(--pri-50);color:var(--pri)}.link:focus-visible{outline:2px solid var(--pri);outline-offset:3px}
.material-confirm{width:min(480px,calc(100vw - 40px));box-sizing:border-box;border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--t1);padding:24px;box-shadow:0 18px 60px #10182730}.material-confirm::backdrop{background:#10182766}.material-confirm h2{margin:0 0 18px;font-size:20px}.material-confirm p{overflow-wrap:anywhere;line-height:1.7}.confirm-actions{display:flex;justify-content:flex-end;gap:12px;margin-top:22px}
</style>
