<template>
  <section class="w75 sp-panel">
    <header class="w75__head">
      <div>
        <p class="w75__eyebrow">W7.5 · Student PC Feedback / Resubmit</p>
        <h2>评阅反馈与整改重交</h2>
        <p>每条意见绑定评阅时的冻结文件版本；退回后只通过原提交入口生成新版本，不覆盖历史证据。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading || busy" @click="load">刷新反馈</button>
    </header>

    <StateBlock v-if="loading" type="loading" text="正在加载评阅反馈…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <div v-if="actionable" class="w75__action">
        <div class="w75__action-title">
          <div>
            <span>当前需要整改</span>
            <strong>{{ actionable.stageLabel }} · 第 {{ actionable.roundNo || '—' }} 轮</strong>
          </div>
          <span class="w75__danger">退回整改</span>
        </div>
        <p class="w75__summary">{{ actionable.summary || '评阅人已退回，请按意见修改后重新提交。' }}</p>
        <ul v-if="actionable.issues?.length" class="w75__issues">
          <li v-for="(issue, index) in actionable.issues" :key="index">{{ issueText(issue) }}</li>
        </ul>
        <div v-if="actionable.reviewedFile" class="w75__frozen">
          <div>
            <b>本次意见对应冻结版</b>
            <span>{{ actionable.reviewedFile.fileName }} · 文件版本 v{{ actionable.reviewedFile.versionNo }}</span>
            <small>FileVersion {{ actionable.reviewedFile.fileVersionId }} · SHA-256 {{ shortHash(actionable.reviewedFile.sha256) }}</small>
          </div>
          <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="openReviewed(actionable.reviewedFile)">查看被评版本</button>
        </div>

        <div v-if="actionable.resubmitTarget?.kind === 'PROPOSAL'" class="w75__form">
          <h3>整改后重交开题报告</h3>
          <p>正文已带入最近一次开题内容。修改后提交会继续走现有开题 canonical submit + optimistic lock。</p>
          <label>选题背景与研究依据<textarea v-model.trim="proposalForm.background" /></label>
          <label>研究方案与进度计划<textarea v-model.trim="proposalForm.plan" /></label>
          <label>预期成果<textarea v-model.trim="proposalForm.outcome" /></label>
          <label>替换主文档（可选）<input type="file" accept=".pdf,.doc,.docx,.zip" @change="pickFile('proposal', $event)" /></label>
          <UploadState v-if="proposalUpload" :file="proposalUpload" @preview="openPending(proposalUpload)" />
          <button class="sp-btn" :disabled="busy || !proposalForm.background || !proposalForm.plan || (proposalUpload && !proposalUpload.readyForBusiness)" @click="resubmitProposal">
            整改完成，重新提交开题报告
          </button>
        </div>

        <div v-else-if="actionable.resubmitTarget?.kind === 'FINAL'" class="w75__form">
          <h3>整改后重交{{ actionable.resubmitTarget.finalType || '论文成果' }}</h3>
          <p>必须上传修改后的新文件；系统会生成新的不可变 FileVersion，原被评版本继续留在反馈时间线中。</p>
          <label>修改后主文档<input type="file" accept=".pdf,.doc,.docx,.zip" @change="pickFile('final', $event)" /></label>
          <UploadState v-if="finalUpload" :file="finalUpload" @preview="openPending(finalUpload)" />
          <button class="sp-btn" :disabled="busy || !finalUpload?.readyForBusiness" @click="resubmitFinal">
            整改完成，重新提交{{ actionable.resubmitTarget.finalType || '论文成果' }}
          </button>
        </div>
      </div>

      <div v-else class="w75__ok">
        <strong>当前没有待整改的评阅意见</strong>
        <span>{{ timeline.hasData ? '历史反馈已全部进入后续处理或通过。' : '暂未产生可展示的 W7 评阅反馈。' }}</span>
      </div>

      <div v-if="items.length" class="w75__timeline">
        <div class="w75__timeline-head">
          <h3>反馈时间线</h3>
          <span>append-only · {{ items.length }} 条</span>
        </div>
        <article v-for="item in items" :key="item.id" class="w75__event" :class="eventClass(item)">
          <div class="w75__rail"><span></span></div>
          <div class="w75__event-body">
            <header>
              <div>
                <strong>{{ item.stageLabel }} · 第 {{ item.roundNo || '—' }} 轮</strong>
                <span>{{ formatTime(item.createdAt) }}</span>
              </div>
              <b>{{ item.resultLabel || item.result }}</b>
            </header>
            <p v-if="item.summary" class="w75__event-summary">{{ item.summary }}</p>
            <ul v-if="item.issues?.length" class="w75__issues">
              <li v-for="(issue, index) in item.issues" :key="index">{{ issueText(issue) }}</li>
            </ul>
            <div v-if="item.reviewedFile" class="w75__version">
              <span>冻结文件 v{{ item.reviewedFile.versionNo }} · {{ item.reviewedFile.fileName }}</span>
              <span :class="item.reviewedFile.evidenceLocked ? 'is-locked' : 'is-warning'">
                {{ item.reviewedFile.evidenceLocked ? 'SHA-256 已锁定' : '证据哈希需治理' }}
              </span>
              <button class="w75__link" :disabled="busy" @click="openReviewed(item.reviewedFile)">查看该版</button>
              <button class="w75__link" :disabled="busy" @click="downloadReviewed(item.reviewedFile)">下载</button>
            </div>
            <div v-if="item.resubmission" class="w75__resolved">
              已整改重交 → {{ item.resubmission.finalType ? `${item.resubmission.finalType} ` : '' }}{{ item.resubmission.version || '新版本' }} · {{ submissionStatus(item.resubmission.status) }}
            </div>
            <div v-else-if="item.actionRequired" class="w75__pending">待你整改重交</div>
          </div>
        </article>
      </div>
    </template>

    <StudentDocumentViewer
      v-if="readerFile"
      :file="readerFile"
      :load-preview="loadReaderPreview"
      :read-only="true"
      @download="downloadReaderFile"
      @close="readerFile = null"
    />
  </section>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StudentDocumentViewer from '../../components/file/viewer/StudentDocumentViewer.vue'
import fileSdk from '../../services/fileSdk'
import graduationW75Api from '../../services/graduationW75Api'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const timeline = ref({ items: [], latestActionable: null })
const proposal = ref({})
const final = ref({})
const materials = ref({ items: [] })
const proposalUpload = ref(null)
const finalUpload = ref(null)
const readerFile = ref(null)
const proposalForm = reactive({ background: '', plan: '', outcome: '' })

const actionable = computed(() => timeline.value.latestActionable || null)
const items = computed(() => [...(timeline.value.items || [])].reverse())

const UploadState = defineComponent({
  props: { file: { type: Object, required: true } },
  emits: ['preview'],
  setup(props, { emit }) {
    return () => h('div', { class: 'w75__upload' }, [
      h('span', `${props.file.fileName || '已上传文件'} · ${props.file.statusText || props.file.scanStatus || '待确认'}`),
      props.file.readyForBusiness && props.file.canPreview
        ? h('button', { class: 'w75__link', type: 'button', onClick: () => emit('preview') }, '提交前预览')
        : null,
    ])
  },
})

function materialVersion(code) {
  const row = (materials.value.items || []).find((item) => item.materialCode === code)
  return Number(row?.version || 0)
}

function hydrateProposal() {
  const latest = proposal.value.latest || {}
  proposalForm.background = latest.background || ''
  proposalForm.plan = latest.plan || ''
  proposalForm.outcome = latest.outcome || ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [feedback, p, f, library] = await Promise.all([
      graduationW75Api.feedback(),
      graduationW75Api.proposal(),
      graduationW75Api.final(),
      graduationW75Api.materialLibrary(),
    ])
    timeline.value = feedback || { items: [], latestActionable: null }
    proposal.value = p || {}
    final.value = f || {}
    materials.value = library || { items: [] }
    hydrateProposal()
  } catch (e) {
    error.value = e?.message || '评阅反馈加载失败'
  } finally {
    loading.value = false
  }
}

async function pickFile(kind, event) {
  const file = Array.from(event.target.files || [])[0]
  if (!file) return
  busy.value = true
  try {
    const uploaded = await graduationW75Api.upload(file)
    if (kind === 'proposal') proposalUpload.value = uploaded
    else finalUpload.value = uploaded
    ui.notify(uploaded.readyForBusiness ? '修改后文件已上传，可确认后重交' : '文件已上传，等待安全扫描')
  } catch (e) {
    ui.notify(e?.message || '文件上传失败')
  } finally {
    busy.value = false
    event.target.value = ''
  }
}

async function resubmitProposal() {
  if (!actionable.value || actionable.value.resubmitTarget?.kind !== 'PROPOSAL') return
  busy.value = true
  try {
    await graduationW75Api.submitProposal({
      background: proposalForm.background,
      plan: proposalForm.plan,
      outcome: proposalForm.outcome,
      attachments: proposalUpload.value ? [proposalUpload.value.fileId] : [],
      expectedVersion: materialVersion('PROPOSAL_REPORT'),
    })
    proposalUpload.value = null
    ui.notify('开题报告已整改重交，等待重新审阅')
    await load()
  } catch (e) {
    ui.notify(e?.message || '开题报告重交失败')
  } finally {
    busy.value = false
  }
}

async function resubmitFinal() {
  const target = actionable.value?.resubmitTarget
  if (target?.kind !== 'FINAL' || !finalUpload.value?.readyForBusiness) return
  const finalType = target.finalType || (final.value.canSubmitFinal ? '定稿' : '初稿')
  busy.value = true
  try {
    await graduationW75Api.submitFinal({
      finalType,
      attachments: [finalUpload.value.fileId],
      expectedVersion: materialVersion(finalType === '定稿' ? 'THESIS_FINAL' : 'THESIS_DRAFT'),
    })
    finalUpload.value = null
    ui.notify(`${finalType}已整改重交，等待重新审阅`)
    await load()
  } catch (e) {
    ui.notify(e?.message || `${finalType}重交失败`)
  } finally {
    busy.value = false
  }
}

function openReviewed(file) {
  if (!file?.fileId || busy.value) return
  readerFile.value = { ...file, isCurrent: Boolean(file.isCurrent), statusText: file.statusText || '评阅冻结版本' }
}

function openPending(file) {
  if (!file?.fileId || !file?.readyForBusiness || busy.value) return
  readerFile.value = { ...file, temporary: true, isCurrent: true, versionNo: '待重交', statusText: '整改后待提交文件' }
}

async function loadReaderPreview(file, options) {
  if (file?.temporary) return fileSdk.fetchPreviewBlob(file.fileId, options)
  const ticket = await graduationW75Api.issueTicket(file.fileId, 'preview')
  return fileSdk.fetchPreviewBlobFrom(ticket, options)
}

async function downloadReaderFile(file) {
  if (!file?.fileId) return
  if (file.temporary) return fileSdk.download(file.fileId, file.fileName)
  return downloadReviewed(file)
}

async function downloadReviewed(file) {
  if (!file?.fileId || busy.value) return
  busy.value = true
  try {
    await graduationW75Api.download(file.fileId, file.fileName)
    ui.notify('冻结版本已开始下载')
  } catch (e) {
    ui.notify(e?.message || '冻结版本下载失败')
  } finally {
    busy.value = false
  }
}

function issueText(issue) {
  if (typeof issue === 'string') return issue
  if (!issue || typeof issue !== 'object') return String(issue || '')
  return issue.message || issue.summary || issue.label || issue.title || Object.values(issue).filter((v) => typeof v === 'string').join(' · ') || '结构化整改项'
}

function shortHash(value) {
  const raw = String(value || '')
  return raw ? `${raw.slice(0, 12)}…${raw.slice(-8)}` : '—'
}

function formatTime(value) {
  if (!value) return '时间未记录'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}

function submissionStatus(status) {
  return ({ PENDING_REVIEW: '待重新审阅', APPROVED: '已通过', REJECTED: '再次退回' })[status] || status || '状态待确认'
}

function eventClass(item) {
  if (item.result === 'REJECTED') return 'is-danger'
  if (item.result === 'APPROVED' || item.result === 'COMPLETED') return 'is-success'
  return ''
}

onMounted(load)
</script>

<style scoped>
.w75{max-width:1120px;margin:0 auto 18px;padding:18px 20px}.w75__head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.w75__eyebrow{margin:0 0 5px;color:var(--sp-primary);font-size:12px;font-weight:700;letter-spacing:.03em}.w75 h2{margin:0;font-size:19px}.w75__head p:not(.w75__eyebrow){margin:7px 0 0;color:#86909c;font-size:13px;line-height:1.6}.w75__action{margin-top:16px;padding:16px;border:1px solid #ffccc7;border-radius:10px;background:#fff7f6}.w75__action-title{display:flex;justify-content:space-between;gap:14px;align-items:center}.w75__action-title div span,.w75__action-title div strong{display:block}.w75__action-title div span{color:#86909c;font-size:12px;margin-bottom:4px}.w75__danger{padding:4px 8px;border-radius:999px;background:#ffece8;color:#d4380d;font-size:12px;font-weight:700}.w75__summary{margin:12px 0 0;color:#4e5969;line-height:1.7;white-space:pre-wrap}.w75__issues{margin:10px 0 0;padding-left:20px;color:#4e5969;font-size:13px;line-height:1.7}.w75__frozen{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-top:13px;padding:11px 12px;border:1px solid #ffd591;border-radius:8px;background:#fff}.w75__frozen b,.w75__frozen span,.w75__frozen small{display:block}.w75__frozen span{margin-top:4px;color:#4e5969;font-size:12px}.w75__frozen small{margin-top:3px;color:#86909c}.w75__form{margin-top:14px;padding:14px;background:#fff;border:1px solid #edf0f3;border-radius:8px}.w75__form h3{margin:0;font-size:15px}.w75__form>p{margin:6px 0 10px;color:#86909c;font-size:12px;line-height:1.6}.w75__form label{display:block;margin:10px 0;color:#4e5969;font-size:13px}.w75__form textarea{display:block;width:100%;min-height:72px;margin-top:6px;padding:8px 10px;border:1px solid #dcdfe6;border-radius:6px;font:inherit;resize:vertical}.w75__form input[type=file]{display:block;margin-top:7px}.w75__upload{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0 12px;padding:9px 10px;border-radius:7px;background:#f5f9ff;color:#53647a;font-size:12px}.w75__ok{display:flex;gap:8px;flex-direction:column;margin-top:16px;padding:13px 14px;border:1px solid #b7eb8f;border-radius:8px;background:#f6ffed}.w75__ok strong{color:#237804;font-size:14px}.w75__ok span{color:#5b6b57;font-size:12px}.w75__timeline{margin-top:18px}.w75__timeline-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px}.w75__timeline-head h3{margin:0;font-size:15px}.w75__timeline-head span{color:#86909c;font-size:12px}.w75__event{display:grid;grid-template-columns:24px minmax(0,1fr)}.w75__rail{position:relative;border-right:1px solid #e5e6eb}.w75__rail span{position:absolute;right:-5px;top:17px;width:9px;height:9px;border-radius:50%;background:#c9cdd4}.w75__event.is-danger .w75__rail span{background:#f53f3f}.w75__event.is-success .w75__rail span{background:#00b42a}.w75__event-body{margin:0 0 11px 14px;padding:12px 14px;border:1px solid #edf0f3;border-radius:8px;background:#fff}.w75__event-body header{display:flex;justify-content:space-between;gap:12px}.w75__event-body header div strong,.w75__event-body header div span{display:block}.w75__event-body header div strong{font-size:13px}.w75__event-body header div span{margin-top:4px;color:#86909c;font-size:11px}.w75__event-body header>b{font-size:12px;color:#53647a}.w75__event.is-danger header>b{color:#d4380d}.w75__event.is-success header>b{color:#237804}.w75__event-summary{margin:9px 0 0;color:#4e5969;font-size:13px;line-height:1.65;white-space:pre-wrap}.w75__version{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px;padding:8px 10px;border-radius:6px;background:#f7f8fa;color:#53647a;font-size:11px}.w75__version .is-locked{color:#237804}.w75__version .is-warning{color:#ad6800}.w75__link{border:0;background:transparent;color:var(--sp-primary);font:inherit;cursor:pointer;padding:2px 4px}.w75__link:disabled{opacity:.5;cursor:not-allowed}.w75__resolved,.w75__pending{margin-top:9px;padding:7px 9px;border-radius:6px;font-size:12px}.w75__resolved{background:#f6ffed;color:#237804}.w75__pending{background:#fff7e8;color:#ad6800;font-weight:600}@media(max-width:760px){.w75__head,.w75__frozen{display:block}.w75__head .sp-btn,.w75__frozen .sp-btn{margin-top:10px}.w75{padding:15px}.w75__event{grid-template-columns:16px minmax(0,1fr)}.w75__event-body{margin-left:10px}}
</style>
