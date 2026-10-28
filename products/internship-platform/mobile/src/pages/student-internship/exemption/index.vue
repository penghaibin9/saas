<template>
  <view class="mobile-page mobile-student page-wrap exemption">
    <MobileNavBar variant="brand" title="免实习申请" show-back :before-back="() => !submitting && !uploading" :fallback-url="'/pages/student-internship/index' + (requestedBatchId ? '?batchId=' + encodeURIComponent(requestedBatchId) : '')" />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view v-if="!historyMode && !application" class="ex__summary">
              <text class="ex__hint">提交后需学校审核，不等于已批准免实习。</text>
            <MobileStatusTag v-if="application" :label="application.statusLabel || '状态待核对'" :type="statusTone" />
        </view>

        <MobileInlineAlert v-if="historyMode && application" type="info" description="历史免实习申请仅供查阅。" />
        <MobileInlineAlert v-else-if="application?.status === 'PENDING_REVIEW'" type="warning" title="等待学校审核" description="学校审核前可撤回申请。" />
        <MobileInlineAlert v-else-if="application?.status === 'APPROVED'" type="success" title="免实习已批准" :description="application.reviewComment || '学校已批准本次免实习申请。'" />
        <MobileInlineAlert v-else-if="application?.status === 'REJECTED'" type="warning" title="申请已驳回" :description="application.reviewComment || '请按学校意见补充材料后重新提交。'" />
        <MobileInlineAlert v-if="errorMessage" type="warning" title="本次操作未完成" :description="errorMessage" />
        <view v-if="conflict" class="card stack">
          <text>原输入和版本已保留，请先核对最新原单。</text>
          <button class="mobile-control btn btn-ghost" :disabled="submitting || uploading || fileBusy" @click="reread">读取最新原单核对</button>
          <template v-if="latest">
            <text>最新第{{ latest.version }}版 · {{ latest.statusLabel || '状态待核对' }}</text>
            <text>{{ latest.exemptionDestination }} · {{ latest.exemptionReason }}</text><text>{{ latest.reviewComment || '' }}</text>
            <button class="mobile-control btn btn-ghost" :disabled="submitting || uploading || fileBusy" @click="adoptLatest">采用已核对原单，替换当前未保存输入</button>
          </template>
          <button v-if="latestRead && !latest && !application" class="mobile-control btn btn-ghost" :disabled="fileBusy" @click="adoptLatest">本批次尚无原单，保留填写继续申请</button>
        </view>

        <view v-if="!editable && application && !submitting && !uploading" class="card stack"><text class="card-title">免实习申请内容</text><text>免实习类型：{{ typeLabels[typeIndex] }}</text><text>免实习后去向：{{ form.exemptionDestination }}</text><text class="ex__read-body">申请原因：{{ form.exemptionReason }}</text><text v-if="application.status==='PENDING_REVIEW'">下一步由学校审核，批准前仍须遵守当前实习安排。</text><text v-if="form.evidenceFileId">{{ evidence?.statusText || '材料安全状态待核对' }}</text><button v-if="evidenceReady" class="mobile-control btn btn-primary" @click="previewEvidence">查看申请佐证</button><button v-if="form.evidenceFileId" class="mobile-control btn btn-ghost" :disabled="fileBusy" @click="refreshEvidence">重新核对佐证安全状态</button></view>
        <view v-else-if="editable || application || submitting || uploading || conflict" class="card stack">
          <view class="ex__field">
            <text class="ex__label">免实习类型 <text class="ex__req">*</text></text>
            <picker class="mobile-picker" mode="selector" :disabled="!editable" :range="typeLabels" :value="typeIndex" @change="onType">
              <view class="ex__picker">{{ typeLabels[typeIndex] }} <text v-if="editable">▾</text></view>
            </picker>
          </view>
          <view class="ex__field">
            <text class="ex__label">免实习后去向 <text class="ex__req">*</text></text>
            <input v-model.trim="form.exemptionDestination" class="mobile-input ex__input" :disabled="!editable" maxlength="200" placeholder="如：已升学至××学校 / 参军入伍" />
          </view>
          <view class="ex__field">
            <text class="ex__label">申请原因 <text class="ex__req">*</text></text>
            <textarea v-model="form.exemptionReason" class="mobile-textarea ex__textarea" :disabled="!editable" maxlength="500" placeholder="不少于5字，说明申请免实习的具体原因" />
          </view>
          <view class="ex__field ex__evidence">
            <text class="ex__label">佐证材料 <text class="ex__req">*</text></text>
            <text class="ex__file-name">{{ fileName || (form.evidenceFileId ? '已上传佐证材料' : '需上传录取、入伍、健康证明或学校认可材料') }}</text>
            <button v-if="editable" class="mobile-control btn btn-ghost ex__upload" :disabled="uploading || submitting" @click="chooseEvidence">
              {{ uploading ? '上传中…' : (form.evidenceFileId ? '重新上传' : '选择并上传材料') }}
            </button>
            <text v-if="form.evidenceFileId">{{ evidence?.statusText || '材料安全状态待核对' }}</text>
            <button v-if="form.evidenceFileId" class="mobile-control btn btn-ghost" :disabled="uploading || submitting || fileBusy" @click="refreshEvidence">刷新材料安全检查</button>
          </view>
        </view>

        <MobileInlineAlert v-else type="info" title="暂无免实习申请" :description="historyMode ? '历史实习仅供查阅。' : '当前阶段不能新增，请联系学校核对适用条件；原实习安排保持。'" />
        <view v-if="application" class="card">
          <text class="card-title">办理记录</text>
          <view class="ex__record"><text>提交时间</text><text>{{ formatTime(application.submittedAt) }}</text></view>
          <view class="ex__record"><text>当前状态</text><text>{{ application.statusLabel || '状态待核对' }}</text></view>
          <view v-if="application.reviewedBy" class="ex__record"><text>审核人</text><text>{{ application.reviewedBy }}</text></view>
          <view v-if="application.reviewedAt" class="ex__record"><text>审核时间</text><text>{{ formatTime(application.reviewedAt) }}</text></view>
          <view v-if="application.reviewComment" class="ex__review"><text class="ex__label">审核意见</text><text>{{ application.reviewComment }}</text></view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="pageState === 'ready' && editable">
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || uploading || fileBusy || !evidenceReady" @click="submit">
        {{ submitting ? '提交中…' : (application?.status === 'REJECTED' ? '补充后重新提交' : '提交免实习申请') }}
      </button>
    </MobileSafeAreaBar>
    <MobileSafeAreaBar v-else-if="pageState === 'ready' && application?.status === 'PENDING_REVIEW' && !historyMode">
      <button class="mobile-control btn btn-ghost flex-1" :disabled="submitting" @click="withdraw">{{ submitting ? '处理中…' : '撤回申请' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import {
  studentInternshipApplications,
  studentInternshipApplicationSave,
  studentInternshipApplicationSubmit,
  studentInternshipApplicationWithdraw
} from '@/services/internshipApi'
import { chooseSingleFile, uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'
import { toast } from '@/utils/nav'

const TYPES = [
  { value: 'FURTHER_STUDY', label: '升学' },
  { value: 'MILITARY', label: '参军入伍' },
  { value: 'HEALTH', label: '健康原因' },
  { value: 'OTHER', label: '其他' }
]

export default {
  data() {
    return {
      pageState: 'loading', requestedBatchId: '', context: {}, historyMode: false,
      application: null, typeIndex: 0, submitting: false, uploading: false,
      fileName: '', errorMessage: '', evidence: null, fileBusy: false, conflict: false, latest: null,
      recordStatus: '', destinationType: '', hidden: false, sequence: 0, generation: currentSessionGeneration(), latestRead: false,
      form: { exemptionType: 'FURTHER_STUDY', exemptionDestination: '', exemptionReason: '', evidenceFileId: '' }
    }
  },
  computed: {
    typeLabels() { return TYPES.map((item) => item.label) },
    editable() {
      if (this.historyMode || this.hidden || this.conflict || !['PREPARING','READY'].includes(this.recordStatus) || ['ASSIGNED','SELF_ARRANGED','EXEMPTED'].includes(this.destinationType)) return false
      return !this.application || ['DRAFT', 'REJECTED', 'WITHDRAWN'].includes(this.application.status)
    },
    evidenceReady() { return !!this.form.evidenceFileId && String(this.evidence?.fileId) === String(this.form.evidenceFileId) && this.evidence?.readyForBusiness === true },
    statusTone() {
      if (this.application?.status === 'APPROVED') return 'success'
      if (this.application?.status === 'REJECTED') return 'danger'
      if (this.application?.status === 'PENDING_REVIEW') return 'warning'
      return 'info'
    }
  },
  onLoad(options = {}) {
    this.requestedBatchId = String(options.batchId || '')
    this.load()
  },
  onHide() { this.hidden = true; this.sequence++; this.submitting = false; this.uploading = false; this.fileBusy = false },
  onUnload() { this.hidden = true; this.sequence++ },
  onShow() {
    if (!this.hidden) return
    this.hidden = false
    if (this.generation !== currentSessionGeneration()) { this.application = null; this.form = { exemptionType:'FURTHER_STUDY',exemptionDestination:'',exemptionReason:'',evidenceFileId:'' }; this.evidence = null; this.conflict = false; this.generation = currentSessionGeneration(); this.load() }
    else if (!this.context.batchId || this.pageState === 'loading') this.load()
    else { this.conflict = true; this.errorMessage = '返回后请核对原单，未保存输入已保留'; this.pageState = 'ready' }
  },
  methods: {
    async previewEvidence(){if(!this.evidenceReady || this.hidden || this.generation!==currentSessionGeneration())return;try{await fileSdk.open(String(this.form.evidenceFileId))}catch{this.errorMessage='佐证暂时无法打开，请重新核对安全状态'}} ,
    formatTime(value) { return formatDateTime(value) },
    capture() { const sequence = this.sequence, generation = currentSessionGeneration(), context = this.context; return () => !this.hidden && sequence === this.sequence && generation === currentSessionGeneration() && context === this.context },
    fill(row) {
      this.application = row; this.typeIndex = Math.max(0, TYPES.findIndex(item => item.value === row?.exemptionType))
      this.form = { exemptionType: row?.exemptionType || TYPES[this.typeIndex].value, exemptionDestination: row?.exemptionDestination || '', exemptionReason: row?.exemptionReason || '', evidenceFileId: String(row?.evidenceFileId || '') }
      this.evidence = null; this.fileName = this.form.evidenceFileId ? '已上传佐证材料' : ''
    },
    onType(event) {
      this.typeIndex = Number(event.detail.value) || 0
      this.form.exemptionType = TYPES[this.typeIndex]?.value || 'FURTHER_STUDY'
    },
    async load() {
      this.sequence++
      const sequence = this.sequence, generation = currentSessionGeneration(), requested = this.requestedBatchId
      const current = () => !this.hidden && sequence === this.sequence && generation === currentSessionGeneration() && requested === this.requestedBatchId
      this.pageState = 'loading'
      this.errorMessage = ''
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (!current()) return
        this.context = { batchId: dashboard?.batchId || '', internshipId: dashboard?.recordId || '' }
        const loaded = this.capture()
        this.historyMode = !!dashboard?.historyMode
        this.recordStatus = dashboard?.statusText || ''
        this.destinationType = dashboard?.destinationType || ''
        const rows = await studentInternshipApplications(this.context.batchId, this.context.internshipId)
        if (!loaded()) return
        this.fill((rows || []).find((item) => item.applicationType === 'EXEMPTION') || null)
        this.conflict = false; this.latest = null
        this.pageState = 'ready'
        await this.refreshEvidence(true)
      } catch (error) {
        if (!current()) return
        this.errorMessage = error?.message || '免实习申请读取失败'
        this.pageState = 'error'
      }
    },
    async chooseEvidence() {
      if (!this.editable || this.uploading || this.submitting) return
      const current = this.capture()
      this.uploading = true
      this.errorMessage = ''
      try {
        const file = await chooseSingleFile()
        if (!current()) return
        if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个佐证文件不能超过20MB')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_APPLICATION_EVIDENCE', bizId: '' })
        if (!current()) return
        if (!uploaded?.fileId) throw new Error('上传结果不完整')
        this.form.evidenceFileId = String(uploaded.fileId); this.evidence = uploaded
        this.fileName = uploaded.fileName || file.name || '免实习佐证材料'
        if (uploaded.readyForBusiness !== true) this.errorMessage = '材料已接收，安全检查未完成，请刷新检查结果；填写内容已保留'
        else toast('佐证材料安全可用')
      } catch (error) {
        if (current()) this.errorMessage = error?.message || '佐证材料上传失败'
      } finally {
        if (current()) this.uploading = false
      }
    },
    async refreshEvidence(duringRead = false) {
      if (!this.form.evidenceFileId || this.hidden || this.fileBusy || this.uploading || (this.submitting && duringRead !== true)) return false
      const current = this.capture(), id = String(this.form.evidenceFileId)
      this.fileBusy = true; this.evidence = null
      try {
        const meta = await fileSdk.metadata(id)
        if (!current() || id !== String(this.form.evidenceFileId)) return false
        if (String(meta?.fileId) !== id) throw new Error('材料编号不一致，请重新核对')
        this.evidence = meta; this.fileName = meta.fileName || this.fileName
        this.errorMessage = meta.readyForBusiness === true ? '' : '材料安全检查未完成，请稍后刷新；填写内容已保留'
        return this.evidenceReady
      } catch (error) { if (current()) this.errorMessage = error?.message || '材料安全状态读取失败'; return false }
      finally { if (current()) this.fileBusy = false }
    },
    async reread() {
      if (this.hidden || this.submitting || this.uploading || this.fileBusy) return
      const current = this.capture(); this.fileBusy = true; this.latest = null; this.latestRead = false
      try { const rows = await studentInternshipApplications(this.context.batchId, this.context.internshipId); if (current()) { this.latest = (rows || []).find(row => this.application?.id ? String(row.id) === String(this.application.id) : row.applicationType === 'EXEMPTION') || null; this.latestRead = true; this.errorMessage = this.latest ? '' : '未读取到原单，输入仍保留' } }
      catch (error) { if (current()) this.errorMessage = error?.message || '原单核对失败' }
      finally { if (current()) this.fileBusy = false }
    },
    async adoptLatest() { if (this.hidden || this.submitting || this.uploading || this.fileBusy || (!this.latest && (!this.latestRead || this.application))) return; if (this.latest) this.fill(this.latest); this.conflict = false; this.latest = null; this.latestRead = false; this.errorMessage = ''; await this.refreshEvidence() },
    async submit() {
      if (!this.editable || this.submitting || this.uploading) return
      if ((this.form.exemptionDestination || '').trim().length < 2) return toast('请填写免实习后去向')
      if ((this.form.exemptionReason || '').trim().length < 5) return toast('申请原因不少于5字')
      if (!this.form.evidenceFileId) return toast('请上传佐证材料')
      if (!await this.refreshEvidence()) return
      const current = this.capture()
      this.submitting = true
      this.errorMessage = ''
      try {
        const draft = await studentInternshipApplicationSave({
          ...this.context,
          ...(this.application?.id ? { id: this.application.id, expectedVersion: this.application.version } : {}),
          applicationType: 'EXEMPTION',
          exemptionType: this.form.exemptionType,
          exemptionDestination: this.form.exemptionDestination.trim(),
          exemptionReason: this.form.exemptionReason.trim(),
          evidenceFileId: this.form.evidenceFileId,
          applicationNote: this.form.exemptionReason.trim()
        })
        if (!current()) return
        this.application = draft
        await studentInternshipApplicationSubmit(draft.id, {
          ...this.context,
          expectedVersion: draft.version
        })
        if (!current()) return
        toast('免实习申请已提交')
        await this.load()
      } catch (error) {
        if (!current()) return
        this.errorMessage = error?.message || '提交失败，原输入和已保存原单已保留'
        if (error?.bizCode === 'DATA_CONFLICT' || Number(error?.status) === 409 || Number(error?.code) === 409001) { this.conflict = true; this.latest = null }
      } finally {
        this.submitting = false
      }
    },
    async withdraw() {
      if (!this.application?.id || this.application.status !== 'PENDING_REVIEW' || this.submitting) return
      const current = this.capture()
      this.submitting = true
      this.errorMessage = ''
      try {
        await studentInternshipApplicationWithdraw(this.application.id, {
          ...this.context,
          expectedVersion: this.application.version
        })
        if (!current()) return
        toast('申请已撤回')
        await this.load()
      } catch (error) {
        if (current()) this.errorMessage = error?.message || '撤回失败，请核对原单后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.ex__summary{display:flex;align-items:center;justify-content:space-between;gap:12px}.ex__hint{display:block;font-size:14px;line-height:1.6;color:var(--text-secondary)}
.ex__field{margin-bottom:14px}.ex__label{display:block;margin-bottom:6px;font-size:var(--font-size-sm);font-weight:500}.ex__req{color:var(--danger-600)}
.ex__picker,.ex__input,.ex__textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-sm);background:var(--bg-card)}
.ex__textarea{min-height:110px}.ex__evidence{padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}
.ex__file-name{display:block;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-tertiary)}.ex__upload{margin-top:9px}
.ex__record{display:flex;justify-content:space-between;gap:16px;padding:9px 0;border-bottom:1px solid var(--border-light);font-size:var(--font-size-sm)}.ex__record:last-child{border-bottom:0}
.ex__record text:first-child{color:var(--text-tertiary)}.ex__review{margin-top:12px;padding:10px;border-radius:var(--radius-md);background:var(--warning-50,#fff7ed);font-size:var(--font-size-sm);line-height:1.6}
.exemption :deep(.page-pad){max-width:760px;margin:0 auto;box-sizing:border-box;width:100%}.exemption .card{border-radius:8px;box-shadow:none}.ex__label{font-size:15px;line-height:22px}.ex__picker,.ex__input{min-height:44px}.ex__input{height:44px}.ex__picker,.ex__input,.ex__textarea,.ex__file-name,.ex__record,.ex__review{font-size:14px;line-height:1.6}.exemption .btn{min-height:44px;font-size:15px}
.ex__read-body{white-space:pre-wrap;overflow-wrap:anywhere;font-size:15px;line-height:1.8}
</style>
