<template>
  <view class="internship-surface mobile-page mobile-student page-wrap lv">
    <MobileNavBar variant="brand" title="实习请假" show-back :before-back="beforeBack" :fallback-url="'/pages/student-internship/index' + ((context?.batchId || requestedBatchId) ? '?batchId=' + encodeURIComponent(context?.batchId || requestedBatchId) : '')" />
    <MobilePrivacyGate />
    <view v-if="receipt" class="card lv__receipt" style="margin:12px 16px" role="status">
      <view class="row-between"><text class="lv__receipt-title">{{ receipt.actionLabel }}</text><text class="lv__receipt-close" @click="receipt = null">关闭</text></view>
      <text class="lv__receipt-meta">记录 {{ receipt.id }} · {{ receipt.statusLabel }} · 第{{ receipt.version }}版</text>
      <text class="lv__receipt-next">{{ receipt.nextStep }}</text>
    </view>
    <view v-if="formError" class="card" style="margin:12px 16px" role="alert"><text>{{ formError }}</text></view>
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <view class="lv__head">
          <text class="card-title">请假记录</text>
          <text class="lv__hint">病假或连续3天及以上请假，必须上传证明。</text>
          <text v-if="context?.hasBatch && !writable && pageState === 'ready'" class="lv__hint">{{ context.historyMode ? '历史批次仅可查看。' : '当前实习阶段暂不能提交请假。' }}</text>
        </view>

        <view v-for="item in list" :key="item.id" class="card lv__item">
          <view class="row-between">
            <text class="lv__range">{{ item.startDate }} ~ {{ item.endDate }}</text>
            <MobileStatusTag :status="item.status" :label="leaveStage(item).label" />
          </view>
          <text class="lv__days">{{ item.days }} 天 · {{ typeLabel(item.leaveType) }}</text>
          <text class="lv__meta">{{ leaveStage(item).next }}</text>
          <template v-if="!['APPROVED','RETURNED'].includes(item.status)">
          <text class="lv__reason">{{ item.reason }}</text>
          <text class="lv__meta">证明材料：{{ item.hasEvidence || item.evidenceFileId ? '已上传' : (item.evidenceRequired ? '缺少必需材料' : '未上传') }}</text>
          <text class="lv__meta">提交时间：{{ formatTime(item.submittedAt || item.createdAt) }}</text>
          <view v-if="item.reviewComment" class="lv__review">
            <text class="lv__review-title">审批意见</text>
            <text class="lv__review-text">{{ item.reviewComment }}</text>
          </view>
          <view v-if="item.returnNote" class="lv__review lv__review--return">
            <text class="lv__review-title">销假说明</text>
            <text class="lv__review-text">{{ item.returnNote }}</text>
          </view>
          <text v-if="item.returnedAt" class="lv__meta">销假时间：{{ formatTime(item.returnedAt) }}</text>
          <text v-if="item.reviewAt" class="lv__meta">审批时间：{{ formatTime(item.reviewAt) }}</text>
          </template>
          <button class="mobile-control btn btn-ghost lv__withdraw" :disabled="submitting || uploading || reading" @click="openDetail(item)">查看原单与历次提交</button>
          <button v-if="['REJECTED', 'NEEDS_REVISION'].includes(item.status)" class="mobile-control btn btn-primary lv__withdraw" :disabled="!writable || submitting || uploading || reading || conflict" @click="edit(item)">原单补正重交</button>
          <button v-if="item.status === 'PENDING'" class="mobile-control btn btn-ghost lv__withdraw" :disabled="!writable || submitting || uploading || reading" @click="withdraw(item)">撤回</button>
          <button v-if="['APPROVED', 'OVERDUE'].includes(item.status)" class="mobile-control btn btn-ghost lv__withdraw" :disabled="!writable || submitting || uploading || reading" @click="openReturn(item)">办理销假</button>
          <view v-if="returnDraft.id === String(item.id)" class="lv__return-editor">
            <text class="lv__review-title">确认已经返岗</text>
            <text class="lv__rule">提交后由指导教师核实返岗并同步处理关联风险。</text>
            <textarea v-model="returnDraft.note" class="mobile-textarea lv__textarea" :disabled="submitting" maxlength="500" placeholder="销假说明（2至500字）" />
            <view class="lv__actions">
              <button class="mobile-control btn btn-ghost flex-1" :disabled="submitting" @click="closeReturn">取消</button>
              <button class="mobile-control btn btn-primary flex-1" :disabled="!writable || submitting || reading || returnDraft.conflict || returnDraft.note.trim().length < 2" @click="submitReturn">确认销假</button>
            </view>
            <view v-if="returnDraft.conflict" class="lv__review"><text>说明及原版本已保留，请读取当前原单核对。</text><button class="mobile-control btn btn-ghost" :disabled="submitting || reading" @click="reread">读取当前记录核对</button><button class="mobile-control btn btn-primary" :disabled="submitting || !conflictRead || !['APPROVED','OVERDUE'].includes(detail?.status)" @click="continueReturnAfterConflict">已核对，继续销假</button></view>
          </view>
        </view>
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无请假记录。" />
        <view v-if="detail" class="card lv__item">
          <text class="card-title">原单 {{ detail.id }} · 第{{ detail.version }}版</text>
          <text class="lv__meta">{{ statusLabel(detail.status) }} · {{ detail.startDate }} 至 {{ detail.endDate }}</text>
          <text class="lv__reason">{{ detail.reason }}</text>
          <view v-if="detail.approvalProgress" class="lv__review"><text class="lv__review-title">{{ detail.approvalProgress.label }}</text><view v-for="(step,index) in detail.approvalProgress.steps" :key="index"><text>{{ step.label }} · {{ step.assignee }} · {{ step.statusLabel }}</text><text v-if="step.comment" class="lv__meta">{{ step.comment }}</text></view></view>
          <text v-if="detail.returnNote" class="lv__reason">销假说明：{{ detail.returnNote }}</text>
          <text v-if="detail.returnedAt" class="lv__meta">销假时间：{{ formatTime(detail.returnedAt) }}</text>
          <text v-if="detail.reviewComment" class="lv__meta">审批意见：{{ detail.reviewComment }} · {{ formatTime(detail.reviewAt) }}</text>
          <text v-if="detail.status === 'RETURNED'" class="lv__meta">{{ detail.returnAcknowledged ? '指导教师已确认返岗' : '等待指导教师确认返岗' }}</text>
          <button v-if="detail.evidenceFileId" class="mobile-control btn btn-ghost" @click="openEvidence(detail.evidenceFileId)">查看当前证明</button>
          <view v-for="(snapshot,index) in detail.submissionHistory || []" :key="index" class="lv__review">
            <text class="lv__review-title">第{{ snapshot.version }}版提交 · {{ snapshot.startDate }} 至 {{ snapshot.endDate }}</text>
            <text class="lv__review-text">{{ snapshot.reason }}</text><text class="lv__meta">提交时间：{{ formatTime(snapshot.submittedAt) }}</text>
            <text v-if="snapshot.reviewComment" class="lv__meta">当次审批意见：{{ snapshot.reviewComment }} · {{ formatTime(snapshot.reviewAt) }}</text>
            <button v-if="snapshot.evidenceFileId" class="mobile-control btn btn-ghost" @click="openEvidence(snapshot.evidenceFileId)">查看该版证明</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar>
      <button class="mobile-control btn btn-primary flex-1" :disabled="!writable || submitting || uploading || reading" @click="openApply">{{ editing ? '继续原单补正' : hasDraft ? '继续填写请假草稿' : '新建请假申请' }}</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="closeForm">
      <view class="lv__sheet card">
        <text class="card-title">{{ editing ? `原单 ${editing.id} · 补正重交` : '请假申请' }}</text>
        <text v-if="editing" class="lv__rule">原第{{ editing.version }}版 · 退回原因：{{ editing.reviewComment }}</text>
        <text v-if="formError" class="lv__review-text" role="alert">{{ formError }}</text>
        <view v-if="conflict" class="lv__review"><text>草稿及证明已保留，读取当前记录后明确核对才能继续。</text><button class="mobile-control btn btn-ghost" :disabled="submitting || uploading || reading" @click="reread">读取当前记录核对</button><button class="mobile-control btn btn-primary" :disabled="submitting || !conflictRead || (editing ? !['REJECTED', 'NEEDS_REVISION'].includes(detail?.status) : list.some(item => item.status === 'PENDING'))" @click="continueAfterConflict">已核对，继续办理</button></view>
        <view class="lv__field">
          <text class="lv__label">请假类型 <text class="lv__req">*</text></text>
          <picker class="mobile-picker" mode="selector" :range="leaveTypeLabels" :value="leaveTypeIndex" :disabled="!writable || submitting || uploading || reading" @change="onLeaveType">
            <view class="lv__picker">{{ leaveTypeLabels[leaveTypeIndex] }} <text>▾</text></view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">开始日期 <text class="lv__req">*</text></text>
          <picker class="mobile-picker" mode="date" :value="form.startDate" :disabled="!writable || submitting || uploading || reading" @change="onStart">
            <view class="lv__picker">{{ form.startDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">结束日期 <text class="lv__req">*</text></text>
          <picker class="mobile-picker" mode="date" :value="form.endDate" :disabled="!writable || submitting || uploading || reading" @change="onEnd">
            <view class="lv__picker">{{ form.endDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">请假事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="mobile-textarea lv__textarea" :disabled="!writable || submitting || uploading || reading" maxlength="500" placeholder="说明请假原因（2至500字）" />
        </view>
        <view class="lv__field lv__evidence" :class="{ required: evidenceRequired }">
          <text class="lv__label">证明材料 {{ evidenceRequired ? '（必需）' : '（选传）' }}</text>
          <text class="lv__rule">{{ evidenceRuleText }}</text>
          <button class="mobile-control btn btn-ghost lv__upload" :disabled="uploading || submitting" @click="chooseEvidence">
            {{ uploading ? '上传中…' : (form.fileName || '选择并上传证明') }}
          </button>
          <text v-if="pendingEvidence" class="lv__rule">{{ pendingEvidence.statusText || (pendingEvidence.readyForBusiness ? '安全可用' : '文件状态待核对') }}</text>
          <button v-if="pendingEvidence && !pendingEvidence.readyForBusiness" class="mobile-control btn btn-ghost" :disabled="uploading || submitting" @click="refreshEvidence">读取安全检查结果</button>
        </view>
        <view class="lv__actions">
          <button class="mobile-control btn btn-ghost flex-1" :disabled="submitting || uploading" @click="closeForm">收起，保留草稿</button>
          <button class="mobile-control btn btn-primary flex-1" :disabled="!writable || submitting || uploading || reading || conflict || (pendingEvidence && !pendingEvidence.readyForBusiness)" @click="submit">{{ submitting ? '提交中…' : editing ? '原单补正重交' : '提交申请' }}</button>
        </view>
        <button class="mobile-control btn btn-ghost" :disabled="submitting || uploading" @click="newApply">清除本次草稿，重新填写</button>
      </view>
    </view>
  </view>
</template>

<script>
import {
  studentInternshipLeaveApply,
  studentInternshipLeaveDetail,
  studentInternshipLeaveResubmit,
  studentInternshipLeaves,
  studentInternshipLeaveReturn,
  studentInternshipLeaveWithdraw
} from '@/services/internshipApi'
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { normalizeFileReadiness, refreshFileReadiness } from '@/services/fileReadiness.mjs'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const LEAVE_TYPES = [
  { value: 'PERSONAL', label: '事假' },
  { value: 'SICK', label: '病假' },
  { value: 'OTHER', label: '其他' }
]

export default {
  data() {
    return {
      list: [], pageState: 'loading', formVisible: false,
      context: null, requestedBatchId: '', focusId: '',
      hidden: false, generation: currentSessionGeneration(), epoch: 0, sequence: 0, detailSequence: 0, operation: 0,
      editing: null, detail: null, reading: false, conflict: false, conflictRead: false, pendingEvidence: null, formError: '',
      submitting: false, uploading: false, leaveTypeIndex: 0,
      form: { leaveType: 'PERSONAL', startDate: '', endDate: '', reason: '', fileId: '', fileName: '' },
      receipt: null,
      returnDraft: { id: '', note: '', version: null, conflict: false }
    }
  },
  computed: {
    writable() { return !this.hidden && this.pageState === 'ready' && !!this.context?.hasBatch && !this.context.historyMode && ['ONBOARD', 'ASSESSING'].includes(this.context.statusText) },
    hasDraft() { return !!(this.editing || this.form.startDate || this.form.endDate || this.form.reason.trim() || this.form.fileId || this.pendingEvidence) },
    leaveTypeLabels() { return LEAVE_TYPES.map((item) => item.label) },
    calculatedDays() {
      if (!this.form.startDate || !this.form.endDate) return 0
      const start = new Date(`${this.form.startDate}T00:00:00Z`).getTime()
      const end = new Date(`${this.form.endDate}T00:00:00Z`).getTime()
      if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return 0
      return Math.floor((end - start) / 86400000) + 1
    },
    evidenceRequired() {
      return this.form.leaveType === 'SICK' || this.calculatedDays >= 3
    },
    evidenceRuleText() {
      if (this.form.leaveType === 'SICK') return '病假必须上传医疗或就诊证明。'
      if (this.calculatedDays >= 3) return '连续3天及以上请假必须上传证明材料。'
      return '短期事假可按学校要求选传证明。'
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.focusId = String(options.leaveId || ''); this.loadList() },
  onShow() { const wasHidden = this.hidden; this.hidden = false; if (wasHidden || this.generation !== currentSessionGeneration()) this.loadList() },
  onHide() { this.pause() },
  onUnload() { this.pause(); this.resetDraft(); this.context = null; this.detail = null; this.list = [] },
  onPullDownRefresh() { this.loadList(() => uni.stopPullDownRefresh()) },
  methods: {
    leaveStage(item) {
      if (item.status === 'RETURNED') return item.returnAcknowledged === true
        ? { label:'销假办结', next:'指导教师已确认返岗，原单与历次提交可继续查阅。' }
        : item.returnAcknowledged === false ? { label:'待导师核实返岗', next:'已登记返岗，等待指导教师核实，无需重复销假。' }
        : { label:'返岗确认待核对', next:'请重新读取原单，确认指导教师是否已核实返岗。' }
      return { label:this.statusLabel(item.status), next:({PENDING:'等待学校按审批流程办理。',APPROVED:'请按批准日期返岗，返岗后在原单办理销假。',OVERDUE:'请尽快说明返岗情况并办理销假。',NEEDS_REVISION:'请按审批意见沿原单补正。',REJECTED:'请查看审批意见，可沿原单补正。',WITHDRAWN:'本次申请已撤回，历史记录保留。'})[item.status] || '请查看原单核对当前办理进度。' }
    },
    beforeBack() {
      if (this.submitting || this.uploading || this.reading) return false
      if (this.formVisible) { this.closeForm(); return false }
      return true
    },
    pause() { this.hidden = true; this.epoch++; this.sequence++; this.detailSequence++; this.operation++; this.submitting = false; this.uploading = false; this.reading = false },
    capture() { return { epoch: this.epoch, generation: currentSessionGeneration(), batchId: String(this.context?.batchId || ''), internshipId: String(this.context?.recordId || '') } },
    current(t) { return !this.hidden && t.epoch === this.epoch && t.generation === currentSessionGeneration() && t.batchId === String(this.context?.batchId || '') && t.internshipId === String(this.context?.recordId || '') },
    assertDetail(row, t, id = row?.id) {
      if (!row || String(row.id) !== String(id) || String(row.batchId) !== t.batchId || String(row.internshipId) !== t.internshipId || !Number.isInteger(row.version) || row.version < 0) throw new Error('原单所属批次、实习或版本不一致')
    },
    resetDraft() {
      this.editing = null; this.conflict = false; this.conflictRead = false; this.pendingEvidence = null; this.formError = ''; this.formVisible = false
      this.form = { leaveType: 'PERSONAL', startDate: '', endDate: '', reason: '', fileId: '', fileName: '' }; this.leaveTypeIndex = 0
      this.returnDraft = { id: '', note: '', version: null, conflict: false }
    },
    statusLabel(status) { return ({ PENDING: '审批中', APPROVED: '已通过', REJECTED: '已驳回', NEEDS_REVISION: '已退回，请补正', WITHDRAWN: '已撤回', OVERDUE: '超期未返岗', RETURNED: '已登记返岗' })[status] || '状态待核对' },
    typeLabel(type) { return LEAVE_TYPES.find(item => item.value === type)?.label || '请假类型待核对' },
    isConflict(e) { return e?.bizCode === 'DATA_CONFLICT' || e?.status === 409 || Number(e?.code) === 409001 || e?.code === 'DATA_CONFLICT' },
    async loadList(done) {
      if (this.hidden) return
      if (this.generation !== currentSessionGeneration()) {
        this.pause(); this.hidden = false; this.generation = currentSessionGeneration(); this.context = null; this.list = []; this.detail = null; this.receipt = null; this.requestedBatchId = ''; this.focusId = ''; this.resetDraft()
      }
      const seq = ++this.sequence, generation = currentSessionGeneration()
      this.detailSequence++; this.reading = false
      const current = () => !this.hidden && seq === this.sequence && generation === currentSessionGeneration()
      this.pageState = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (!current()) return
        if (!dashboard?.hasBatch || !dashboard.recordId || !dashboard.batchId) { this.epoch++; this.resetDraft(); this.context = null; this.list = []; this.detail = null; this.receipt = null; this.pageState = 'empty'; return }
        if (String(this.context?.batchId) !== String(dashboard.batchId) || String(this.context?.recordId) !== String(dashboard.recordId)) {
          this.epoch++; this.operation++; this.resetDraft(); this.detail = null; this.receipt = null; this.list = []; this.submitting = false; this.uploading = false
        }
        this.context = dashboard
        const t = this.capture()
        const rows = await studentInternshipLeaves(dashboard?.batchId, dashboard?.recordId)
        if (!current() || !this.current(t)) return
        this.list = Array.isArray(rows) ? rows : (rows?.items || [])
        this.list.forEach(row => this.assertDetail(row, t))
        this.pageState = 'ready'
        if (this.focusId) { const id = this.focusId; this.focusId = ''; await this.openDetail({ id }) }
      } catch (error) {
        if (current()) this.pageState = normalizeError(error).pageState || 'error'
      } finally { done?.() }
    },
    async openDetail(item) {
      if (!item?.id || this.hidden || this.submitting || this.uploading || this.pageState !== 'ready') return
      const t = this.capture(), seq = ++this.detailSequence
      this.reading = true; this.detail = null
      try {
        const row = await studentInternshipLeaveDetail(String(item.id), t.batchId, t.internshipId)
        if (!this.current(t) || seq !== this.detailSequence) return
        this.assertDetail(row, t, item.id); this.detail = row
        this.list = this.list.map(item => String(item.id) === String(row.id) ? row : item)
        return row
      } catch (e) { if (this.current(t) && seq === this.detailSequence) this.formError = '原单详情读取失败，请核对当前申请后重试' }
      finally { if (this.current(t) && seq === this.detailSequence) this.reading = false }
    },
    async refreshAfterWrite(t, op, id) {
      const opened = String(this.detail?.id) === String(id)
      if (opened) this.detail = null
      await this.loadList()
      if (!this.current(t) || op !== this.operation) return
      this.submitting = false
      if (opened && this.pageState === 'ready') await this.openDetail({ id })
    },
    async edit(item) {
      if (!this.writable || this.submitting || this.uploading || this.conflict || !['REJECTED', 'NEEDS_REVISION'].includes(item?.status)) return
      if (this.hasDraft) { this.formError = '请先完成当前草稿，或明确清除后再补正其他原单'; return }
      const row = await this.openDetail(item)
      if (!row || !this.writable || !['REJECTED', 'NEEDS_REVISION'].includes(row.status)) return
      this.resetDraft(); this.editing = { ...row }; this.receipt = null
      this.leaveTypeIndex = LEAVE_TYPES.findIndex(item => item.value === row.leaveType)
      if (this.leaveTypeIndex < 0) { this.resetDraft(); this.formError = '请假类型待学校核对'; return }
      this.form = { leaveType: row.leaveType, startDate: row.startDate, endDate: row.endDate, reason: row.reason || '', fileId: row.evidenceFileId || '', fileName: row.attachment?.fileName || '' }
      this.formVisible = true
    },
    async reread() {
      if (this.submitting || this.uploading) return
      const t = this.capture(), id = this.editing?.id || this.returnDraft.id
      this.conflictRead = false
      await this.loadList()
      if (!this.current(t) || this.pageState !== 'ready') return
      if (id) await this.openDetail({ id })
      if (this.current(t) && (!id || String(this.detail?.id) === String(id))) this.conflictRead = true
    },
    continueAfterConflict() {
      if (this.submitting || this.uploading || !this.writable || !this.conflict || !this.conflictRead) return
      if (this.editing) {
        if (String(this.detail?.id) !== String(this.editing.id) || !['REJECTED', 'NEEDS_REVISION'].includes(this.detail?.status)) return
        this.editing = { ...this.detail }
      } else if (this.list.some(item => item.status === 'PENDING')) return
      this.conflict = false; this.conflictRead = false; this.formError = ''
    },
    continueReturnAfterConflict() {
      if (this.submitting || !this.writable || !this.returnDraft.conflict || !this.conflictRead || String(this.detail?.id) !== this.returnDraft.id || !['APPROVED', 'OVERDUE'].includes(this.detail.status)) return
      this.returnDraft.version = this.detail.version; this.returnDraft.conflict = false; this.conflictRead = false; this.formError = ''
    },
    openApply() {
      if (!this.writable || this.submitting || this.uploading || this.reading) return
      if (this.returnDraft.id) { this.formError = '请先完成或取消销假草稿，再填写新申请'; return }
      this.formVisible = true
    },
    newApply() { if (this.writable && !this.submitting && !this.uploading) { this.resetDraft(); this.formVisible = true } },
    closeForm() {
      if (this.submitting || this.uploading) return
      this.formVisible = false
    },
    onLeaveType(event) {
      this.leaveTypeIndex = Number(event.detail.value)
      this.form.leaveType = LEAVE_TYPES[this.leaveTypeIndex]?.value || 'PERSONAL'
    },
    onStart(event) { this.form.startDate = event.detail.value },
    onEnd(event) { this.form.endDate = event.detail.value },
    async chooseEvidence() {
      if (!this.writable || this.uploading || this.submitting || this.reading) return
      const t = this.capture(), form = this.form, op = ++this.operation
      const current = () => this.current(t) && form === this.form && op === this.operation
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!current() || !file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个证明文件不能超过20MB')
        const uploaded = normalizeFileReadiness(await uploadBusinessFile(file, { bizType: 'INTERNSHIP', bizId: '' }))
        if (!current()) return
        if (!uploaded?.fileId) throw new Error('缺少证明编号')
        this.pendingEvidence = uploaded
        this.form.fileId = uploaded.readyForBusiness === true ? String(uploaded.fileId) : ''
        this.form.fileName = uploaded.fileName || file.name || '请假证明'
        toast(uploaded.readyForBusiness ? '证明安全可用' : '证明已接收，请等待安全检查')
      } catch (error) {
        if (current()) this.formError = '证明上传未完成，草稿已保留，请重试'
      } finally { if (current()) this.uploading = false }
    },
    async refreshEvidence() {
      if (!this.writable || this.uploading || this.submitting || !this.pendingEvidence) return
      const t = this.capture(), op = ++this.operation, original = this.pendingEvidence
      const current = () => this.current(t) && op === this.operation && original === this.pendingEvidence
      this.uploading = true
      try {
        const rows = await refreshFileReadiness([original], id => fileSdk.metadata(id), current)
        if (!rows || !current()) return
        this.pendingEvidence = rows[0]; this.form.fileId = rows[0].readyForBusiness ? String(rows[0].fileId) : ''
      } catch (e) { if (current()) this.formError = '证明安全检查结果读取失败，请重试' }
      finally { if (this.current(t) && op === this.operation) this.uploading = false }
    },
    async openEvidence(fileId) { const t = this.capture(); try { if (this.current(t)) await fileSdk.open(String(fileId)) } catch (e) { if (this.current(t)) this.formError = '证明打开未完成，请重试' } },
    async submit() {
      if (!this.writable || this.submitting || this.uploading || this.reading || this.conflict) return
      if (!this.form.startDate || !this.form.endDate || this.form.reason.trim().length < 2 || this.form.reason.trim().length > 500) {
        return toast('请填写起止日期与2至500字事由')
      }
      if (!this.calculatedDays) return toast('结束日期不能早于开始日期')
      if (this.evidenceRequired && !this.form.fileId) return toast(this.evidenceRuleText)
      if (this.pendingEvidence && this.pendingEvidence.readyForBusiness !== true) return toast('证明尚未安全就绪，请先读取检查结果')
      const t = this.capture(), op = ++this.operation, editing = this.editing
      const current = () => this.current(t) && op === this.operation
      const body = { batchId: t.batchId, internshipId: t.internshipId, leaveType: this.form.leaveType,
        startDate: this.form.startDate, endDate: this.form.endDate, reason: this.form.reason.trim(), fileId: this.form.fileId || '', expectedVersion: editing?.version ?? 0 }
      this.submitting = true
      this.formError = ''
      try {
        const result = editing ? await studentInternshipLeaveResubmit(String(editing.id), body) : await studentInternshipLeaveApply(body)
        if (!current()) return
        this.resetDraft()
        this.receipt = {
          ...(result || {}), statusLabel: this.statusLabel(result.status), actionLabel: editing ? '原请假单已补正重交' : '请假申请已提交',
          nextStep: '等待当前责任人审批；全部必需节点通过后请假才生效，返岗时请及时办理销假。'
        }
        await this.refreshAfterWrite(t, op, result.id)
      } catch (error) {
        if (!current()) return
        if (this.isConflict(error)) { this.conflict = true; this.conflictRead = false }
        this.formError = this.isConflict(error) ? '原单或实习状态已变化，草稿和原版本已保留，请读取后核对' : '提交未完成，填写内容已保留，请重试'
      } finally { if (current()) this.submitting = false }
    },
    withdraw(item) {
      if (!this.writable || this.submitting || this.uploading || this.reading || item?.status !== 'PENDING') return
      const t = this.capture(), snapshot = { ...item }, op = ++this.operation
      this.assertDetail(snapshot, t)
      const current = () => this.current(t) && op === this.operation
      uni.showModal({
        title: '撤回请假', content: '确认撤回该待审批请假申请？',
        success: async (result) => {
          if (!result.confirm || !current() || !this.writable || this.submitting || this.uploading) return
          this.submitting = true
          try {
            const response = await studentInternshipLeaveWithdraw(String(snapshot.id), {
              batchId: t.batchId, internshipId: t.internshipId, expectedVersion: snapshot.version
            })
            if (!current()) return
            this.receipt = {
              ...(response || {}), statusLabel: this.statusLabel(response.status), actionLabel: '请假申请已撤回',
              nextStep: '本次申请已结束；如仍需请假，可重新提交。'
            }
            await this.refreshAfterWrite(t, op, snapshot.id)
          } catch (error) {
            if (current()) this.formError = '撤回未完成，请重新读取原单核对后重试'
          } finally { if (current()) this.submitting = false }
        }
      })
    },
    openReturn(item) {
      if (!this.writable || this.submitting || this.uploading || this.reading || this.returnDraft.id || !['APPROVED', 'OVERDUE'].includes(item?.status)) return
      if (this.hasDraft || this.formVisible) { this.formError = '请先完成或明确清除请假草稿，再办理销假'; return }
      this.assertDetail(item, this.capture())
      this.returnDraft = { id: String(item.id), note: '', version: item.version, conflict: false }
    },
    closeReturn() {
      if (this.submitting) return
      this.returnDraft = { id: '', note: '', version: null, conflict: false }
    },
    async submitReturn() {
      const draft = this.returnDraft
      const note = String(draft.note || '').trim()
      if (!this.writable || this.submitting || this.uploading || this.reading || !draft.id || draft.conflict || note.length < 2 || note.length > 500) return
      const t = this.capture(), op = ++this.operation, current = () => this.current(t) && op === this.operation
      this.submitting = true
      try {
        const response = await studentInternshipLeaveReturn(draft.id, {
          batchId: t.batchId, internshipId: t.internshipId, note, expectedVersion: draft.version
        })
        if (!current()) return
        this.receipt = {
          ...(response || {}), statusLabel: this.statusLabel(response.status), actionLabel: '销假已登记',
          nextStep: '等待指导教师核实返岗并完成风险同步。'
        }
        this.returnDraft = { id: '', note: '', version: null, conflict: false }
        await this.refreshAfterWrite(t, op, draft.id)
      } catch (error) {
        if (!current()) return
        if (this.isConflict(error)) { this.returnDraft.conflict = true; this.conflictRead = false }
        this.formError = '销假未完成，说明和原版本已保留，请读取当前原单后核对'
      } finally { if (current()) this.submitting = false }
    },
    formatTime(value) {
      if (!value) return '—'
      const date = new Date(value)
      return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN', { hour12: false }) : '时间待核对'
    }
  }
}
</script>

<style scoped>
.lv__hint{display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--text-secondary);line-height:1.55}.lv__item{margin-bottom:10px}.lv__range{font-weight:var(--font-weight-medium)}.lv__days{display:block;margin-top:4px;font-size:var(--font-size-sm);color:var(--text-secondary)}.lv__reason{display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--text-primary)}.lv__meta{display:block;margin-top:5px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.lv__review{margin-top:9px;padding:9px 10px;border-radius:8px;background:var(--warning-50,#fff7ed)}.lv__review--return{background:var(--success-50,#f0fdf4)}.lv__review--return .lv__review-title{color:var(--success-800,#166534)}.lv__review-title{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--warning-800,#9a3412)}.lv__review-text{display:block;margin-top:4px;font-size:var(--font-size-sm);line-height:1.5}.lv__receipt{border-color:var(--success-200,#bbf7d0);background:var(--success-50,#f0fdf4)}.lv__receipt-title{color:var(--success-800,#166534);font-size:var(--font-size-md);font-weight:600}.lv__receipt-close{color:var(--success-700,#15803d);font-size:var(--font-size-xs)}.lv__receipt-meta,.lv__receipt-next{display:block;margin-top:5px;color:var(--success-700,#15803d);font-size:var(--font-size-xs);line-height:1.5}.lv__return-editor{display:flex;flex-direction:column;gap:8px;margin-top:10px;padding:10px;border:1px solid var(--teacher-200,#bfdbfe);border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.lv__return-editor .lv__textarea{background:var(--bg-card)}.lv__withdraw{margin-top:10px}.lv__mask{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100;display:flex;align-items:flex-end}.lv__sheet{width:100%;border-radius:16px 16px 0 0;padding:16px;box-sizing:border-box;max-height:88vh;overflow-y:auto}.lv__field{margin-top:12px}.lv__label{display:block;font-size:var(--font-size-sm);margin-bottom:6px}.lv__req{color:var(--danger-600)}.lv__picker{padding:10px 12px;background:var(--gray-50);border-radius:var(--radius-md);font-size:var(--font-size-sm)}.lv__textarea{width:100%;min-height:80px;padding:10px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-sm)}.lv__evidence{padding:10px;border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--gray-50)}.lv__evidence.required{border-color:var(--warning-400,#fb923c);background:var(--warning-50,#fff7ed)}.lv__rule{display:block;font-size:var(--font-size-xs);color:var(--text-secondary);line-height:1.45}.lv__upload{margin-top:8px}.lv__actions{display:flex;gap:10px;margin-top:16px}
.lv{padding-bottom:90px}.lv :deep(.page-pad){max-width:760px;margin:0 auto;box-sizing:border-box;width:100%}.lv .card{border-radius:8px;box-shadow:none}.lv__hint,.lv__days,.lv__reason,.lv__meta,.lv__review-title,.lv__review-text,.lv__receipt-meta,.lv__receipt-next,.lv__rule{font-size:14px;line-height:1.6}.lv__range,.lv__receipt-title{font-size:16px;line-height:24px}.lv__label,.lv__picker,.lv__textarea{font-size:15px;line-height:22px}.lv__picker{min-height:44px;box-sizing:border-box}.lv .btn{min-height:44px;font-size:15px}.lv__receipt-close{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;font-size:14px}.lv__sheet{border-radius:12px 12px 0 0}
</style>
