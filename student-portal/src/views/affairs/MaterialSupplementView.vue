<template>
  <div class="sp-page">
    <section class="sp-card material-head">
      <div>
        <div class="sp-panel__head">材料补交中心</div>
        <p class="sp-muted">老师登记缺项后在这里按项补交。每次重新上传都会形成新版本，历史版本不会被覆盖。</p>
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
          <div class="title-line"><strong>{{ item.itemName }}</strong><StatusTag :text="item.statusLabel || item.status" :tone="tone(item)" /></div>
          <div class="sp-muted">{{ bizLabel(item.bizType) }} · 业务记录 #{{ item.bizId }} · 第 {{ item.returnRound || 1 }} 轮</div>
          <div v-if="item.requirementReason" class="reason">缺项说明：{{ item.requirementReason }}</div>
          <div v-if="item.dueAt" class="sp-muted" :class="{ overdue: item.overdue }">截止 {{ fmt(item.dueAt) }}{{ item.overdue ? '（已逾期）' : '' }}</div>
        </div>
        <div class="owner"><span>审核责任人</span><strong>{{ item.reviewOwner || '待分配' }}</strong></div>
      </div>

      <div v-if="canSubmit(item)" class="submit-box">
        <label class="file-pick">
          <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.zip" :disabled="submitting === item.requirementId" @change="selectFile(item, $event)" />
          <span>{{ selectedFiles[item.requirementId]?.name || '选择补交文件' }}</span>
        </label>
        <input v-model.trim="notes[item.requirementId]" maxlength="500" class="sp-inp" placeholder="补充说明（选填）" />
        <button class="sp-btn" :disabled="submitting === item.requirementId || !selectedFiles[item.requirementId]" @click="submit(item)">
          {{ submitting === item.requirementId ? '正在上传…' : '上传并提交审核' }}
        </button>
      </div>
      <div v-else-if="item.status === 'PENDING_REVIEW'" class="pending-note">最新版本已提交，等待老师审核，请勿重复上传。</div>

      <div class="version-title">版本记录（{{ item.versionCount || 0 }}）</div>
      <div v-if="!(item.versions || []).length" class="sp-muted">尚未上传材料</div>
      <div v-for="version in (item.versions || [])" :key="version.submissionId" class="version-row">
        <div>
          <strong>V{{ version.versionNo }} · {{ version.fileName }}</strong>
          <div class="sp-muted">{{ fmtTime(version.submittedAt) }} · {{ version.statusLabel || version.status }}</div>
          <div v-if="version.reviewNote" class="review-note">审核意见：{{ version.reviewNote }}</div>
        </div>
        <div class="version-actions">
          <span v-if="version.current" class="current-tag">当前版本</span>
          <button v-if="version.downloadable" class="link" @click="download(version)">下载</button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'
import { useUiStore } from '../../stores/ui'

const route = useRoute()
const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const items = ref([])
const filter = ref('open')
const submitting = ref('')
const selectedFiles = reactive({})
const notes = reactive({})
const focusId = computed(() => String(route.query.requirementId || ''))

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
  return ({ LEAVE: '请假', AID: '困难认定', FUNDING: '奖助申请', DISCIPLINE: '违纪处分', DISCIPLINE_APPEAL: '处分申诉', DORM_TRANSFER: '调宿申请', CREDIT_APPEAL: '第二课堂申诉', SECOND_CLASS_APPEAL: '第二课堂申诉' }[value] || value || '学工申请')
}
function fmt(value) { return value ? String(value).replace('T', ' ').slice(0, 10) : '' }
function fmtTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '' }
function tone(item) { if (item.overdue || item.status === 'RETURNED') return 'warn'; if (['ACCEPTED', 'WAIVED'].includes(item.status)) return 'success'; return 'default' }
function canSubmit(item) { return (item.allowedActions || []).includes('SUBMIT_MATERIAL') }
function selectFile(item, event) { selectedFiles[item.requirementId] = event.target.files?.[0] || null }

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await affairsFourEndApi.myMaterialRequirements()
    items.value = data?.items || []
    if (focusId.value) {
      const target = items.value.find((x) => String(x.requirementId) === focusId.value)
      if (target && ['ACCEPTED', 'WAIVED'].includes(target.status)) filter.value = 'all'
      await nextTick()
      document.getElementById(`material-${focusId.value}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  } catch (e) {
    error.value = e?.message || '材料列表加载失败'
  } finally {
    loading.value = false
  }
}

async function submit(item) {
  const file = selectedFiles[item.requirementId]
  if (!file) return ui.notify('请先选择补交文件')
  if (!window.confirm(`确认提交“${item.itemName}”的新版本？历史版本将保留。`)) return
  submitting.value = item.requirementId
  try {
    const uploaded = await affairsFourEndApi.uploadMaterialFile(file)
    await affairsFourEndApi.submitMaterialVersion(item.requirementId, uploaded.fileId, item.version, notes[item.requirementId] || '')
    ui.notify('材料已补交，等待老师审核')
    selectedFiles[item.requirementId] = null
    notes[item.requirementId] = ''
    await load()
  } catch (e) {
    ui.notify(e?.message || '材料补交失败')
  } finally {
    submitting.value = ''
  }
}

async function download(version) {
  try { await affairsFourEndApi.downloadMaterial(version.fileId, version.fileName) }
  catch (e) { ui.notify(e?.message || '材料下载失败') }
}

onMounted(load)
</script>

<style scoped>
.material-head,.req-head,.title-line,.version-row,.version-actions{display:flex;align-items:flex-start}.material-head,.req-head,.version-row{justify-content:space-between;gap:18px}.material-head{align-items:center;margin-bottom:16px}.count{margin-left:6px;font-size:11px}.requirement{margin-bottom:14px;scroll-margin-top:24px}.requirement.focus{outline:2px solid var(--pri);outline-offset:2px}.title-line{align-items:center;gap:9px}.reason{margin-top:8px;color:var(--t2);font-size:13px}.overdue{color:#b45309}.owner{min-width:120px;text-align:right}.owner span,.owner strong{display:block}.owner span{font-size:12px;color:var(--t3);margin-bottom:4px}.submit-box{display:grid;grid-template-columns:minmax(180px,1fr) minmax(220px,2fr) auto;gap:10px;margin:16px 0;padding:14px;background:#f8fafc;border-radius:10px}.file-pick{display:flex;align-items:center;padding:0 12px;border:1px dashed #b8c4d6;border-radius:9px;cursor:pointer;font-size:13px;color:var(--pri);overflow:hidden}.file-pick input{display:none}.file-pick span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pending-note{margin:14px 0;padding:11px 13px;background:#eff6ff;border-radius:9px;color:#1d4ed8;font-size:13px}.version-title{font-size:14px;font-weight:650;margin:18px 0 6px}.version-row{padding:11px 0;border-bottom:1px solid var(--line2)}.version-actions{align-items:center;gap:10px}.current-tag{padding:3px 7px;border-radius:6px;background:var(--pri-50);color:var(--pri);font-size:11px}.link{all:unset;cursor:pointer;color:var(--pri);font-size:13px}.review-note{margin-top:4px;color:#b45309;font-size:12px}.error-box{display:flex;align-items:center;gap:12px;padding:14px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;color:#9a3412}
@media(max-width:900px){.req-head,.material-head{flex-direction:column}.owner{text-align:left}.submit-box{grid-template-columns:1fr}.version-row{gap:10px}.error-box{align-items:flex-start;flex-direction:column}}
</style>
