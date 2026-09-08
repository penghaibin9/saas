<template>
  <view class="page-wrap lv">
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <view class="card lv__head">
          <text class="card-title">实习请假</text>
          <text class="lv__hint">病假或连续3天及以上请假必须上传证明；审批通过前教师需要真实查看材料。</text>
        </view>

        <view v-if="receipt" class="card lv__receipt">
          <view class="row-between">
            <text class="lv__receipt-title">{{ receipt.actionLabel }}</text>
            <text class="lv__receipt-close" @click="receipt = null">关闭</text>
          </view>
          <text class="lv__receipt-meta">记录 {{ receipt.id }} · {{ receipt.statusLabel || receipt.status }} · v{{ receipt.version ?? 0 }}</text>
          <text class="lv__receipt-next">{{ receipt.nextStep }}</text>
        </view>

        <view v-for="item in list" :key="item.id" class="card lv__item">
          <view class="row-between">
            <text class="lv__range">{{ item.startDate }} ~ {{ item.endDate }}</text>
            <MobileStatusTag :status="item.status" />
          </view>
          <text class="lv__days">{{ item.days }} 天 · {{ item.leaveTypeLabel || item.leaveType }}</text>
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
          <button v-if="item.status === 'PENDING'" class="btn btn-ghost lv__withdraw" :disabled="submitting" @click="withdraw(item)">撤回</button>
          <button v-if="['APPROVED', 'OVERDUE'].includes(item.status)" class="btn btn-ghost lv__withdraw" :disabled="submitting" @click="openReturn(item)">办理销假</button>
          <view v-if="returnDraft.id === String(item.id)" class="lv__return-editor">
            <text class="lv__review-title">确认已经返岗</text>
            <text class="lv__rule">提交后由指导教师核实返岗并同步处理关联风险。</text>
            <textarea v-model="returnDraft.note" class="lv__textarea" maxlength="300" placeholder="销假说明（不少于2字）" />
            <view class="lv__actions">
              <button class="btn btn-ghost flex-1" :disabled="submitting" @click="closeReturn">取消</button>
              <button class="btn btn-primary flex-1" :disabled="submitting || returnDraft.note.trim().length < 2" @click="submitReturn">确认销假</button>
            </view>
          </view>
        </view>
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无请假记录，可点击下方按钮新建申请。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="openApply">新建请假申请</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="closeForm">
      <view class="lv__sheet card">
        <text class="card-title">请假申请</text>
        <view class="lv__field">
          <text class="lv__label">请假类型 <text class="lv__req">*</text></text>
          <picker mode="selector" :range="leaveTypeLabels" :value="leaveTypeIndex" @change="onLeaveType">
            <view class="lv__picker">{{ leaveTypeLabels[leaveTypeIndex] }} <text>▾</text></view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">开始日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.startDate" @change="onStart">
            <view class="lv__picker">{{ form.startDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">结束日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.endDate" @change="onEnd">
            <view class="lv__picker">{{ form.endDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">请假事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="lv__textarea" maxlength="300" placeholder="说明请假原因（不少于2字）" />
        </view>
        <view class="lv__field lv__evidence" :class="{ required: evidenceRequired }">
          <text class="lv__label">证明材料 {{ evidenceRequired ? '（必需）' : '（选传）' }}</text>
          <text class="lv__rule">{{ evidenceRuleText }}</text>
          <button class="btn btn-ghost lv__upload" :disabled="uploading || submitting" @click="chooseEvidence">
            {{ uploading ? '上传中…' : (form.fileName || '选择并上传证明') }}
          </button>
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting || uploading" @click="closeForm">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import {
  studentInternshipLeaveApply,
  studentInternshipLeaves,
  studentInternshipLeaveReturn,
  studentInternshipLeaveWithdraw
} from '@/services/internshipApi'
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
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
      context: {},
      submitting: false, uploading: false, leaveTypeIndex: 0,
      form: { leaveType: 'PERSONAL', startDate: '', endDate: '', reason: '', fileId: '', fileName: '' },
      receipt: null,
      returnDraft: { id: '', note: '', version: null }
    }
  },
  computed: {
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
  onLoad() { this.loadList() },
  onPullDownRefresh() { this.loadList(() => uni.stopPullDownRefresh()) },
  methods: {
    async loadList(done) {
      this.pageState = 'loading'
      try {
        const dashboard = await studentApi.getInternship()
        const rows = await studentInternshipLeaves(dashboard?.batchId, dashboard?.recordId)
        this.list = Array.isArray(rows) ? rows : (rows?.items || [])
        this.context = {
          batchId: dashboard?.batchId || '',
          internshipId: dashboard?.recordId || dashboard?.internshipId || ''
        }
        this.pageState = 'ready'
      } catch (error) {
        this.pageState = 'error'
      } finally { done?.() }
    },
    openApply() {
      this.leaveTypeIndex = 0
      this.form = { leaveType: 'PERSONAL', startDate: '', endDate: '', reason: '', fileId: '', fileName: '' }
      this.formVisible = true
    },
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
      if (this.uploading || this.submitting) return
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个证明文件不能超过20MB')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP', bizId: '' })
        this.form.fileId = uploaded.fileId
        this.form.fileName = uploaded.fileName || file.name || '请假证明'
        toast('证明材料上传成功')
      } catch (error) {
        toast(error?.message || '证明材料上传失败')
      } finally { this.uploading = false }
    },
    async submit() {
      if (this.submitting || this.uploading) return
      if (!this.form.startDate || !this.form.endDate || this.form.reason.trim().length < 2) {
        return toast('请填写起止日期与事由（不少于2字）')
      }
      if (!this.calculatedDays) return toast('结束日期不能早于开始日期')
      if (this.evidenceRequired && !this.form.fileId) return toast(this.evidenceRuleText)
      this.submitting = true
      try {
        const result = await studentInternshipLeaveApply({
          ...this.context,
          leaveType: this.form.leaveType,
          startDate: this.form.startDate,
          endDate: this.form.endDate,
          reason: this.form.reason.trim(),
          fileId: this.form.fileId || ''
        })
        this.receipt = {
          ...(result || {}), actionLabel: '请假申请已提交',
          nextStep: '等待指导教师审批；通过后返岗时请及时办理销假。'
        }
        toast('请假申请已提交')
        this.formVisible = false
        await this.loadList()
      } catch (error) {
        toast(error?.message || '提交失败，请稍后重试')
      } finally { this.submitting = false }
    },
    withdraw(item) {
      if (this.submitting) return
      uni.showModal({
        title: '撤回请假', content: '确认撤回该待审批请假申请？',
        success: async (result) => {
          if (!result.confirm) return
          this.submitting = true
          try {
            const response = await studentInternshipLeaveWithdraw(item.id, {
              ...this.context,
              expectedVersion: item.version
            })
            this.receipt = {
              ...(response || {}), id: response?.id || item.id,
              version: response?.version ?? (Number(item.version || 0) + 1),
              statusLabel: response?.statusLabel || '已撤回', actionLabel: '请假申请已撤回',
              nextStep: '本次申请已结束；如仍需请假，可重新提交。'
            }
            toast('已撤回')
            await this.loadList()
          } catch (error) {
            toast(error?.message || '撤回失败')
            if (String(error?.code || '') === 'DATA_CONFLICT') await this.loadList()
          } finally { this.submitting = false }
        }
      })
    },
    openReturn(item) {
      if (this.submitting) return
      this.returnDraft = { id: String(item.id), note: '', version: item.version }
    },
    closeReturn() {
      if (this.submitting) return
      this.returnDraft = { id: '', note: '', version: null }
    },
    async submitReturn() {
      const draft = this.returnDraft
      const note = String(draft.note || '').trim()
      if (this.submitting || !draft.id || note.length < 2) return
      this.submitting = true
      try {
        const response = await studentInternshipLeaveReturn(draft.id, {
          ...this.context, note, expectedVersion: draft.version
        })
        this.receipt = {
          ...(response || {}), id: response?.id || draft.id,
          statusLabel: response?.statusLabel || '已销假', actionLabel: '销假已登记',
          nextStep: '等待指导教师核实返岗并完成风险同步。'
        }
        this.returnDraft = { id: '', note: '', version: null }
        toast('销假已登记')
        await this.loadList()
      } catch (error) {
        toast(error?.message || '销假失败，填写内容已保留')
        if (String(error?.code || '') === 'DATA_CONFLICT') await this.loadList()
      } finally { this.submitting = false }
    },
    formatTime(value) {
      if (!value) return '—'
      return String(value).replace('T', ' ').slice(0, 16)
    }
  }
}
</script>

<style scoped>
.lv__hint{display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--text-secondary);line-height:1.55}.lv__item{margin-bottom:10px}.lv__range{font-weight:var(--font-weight-medium)}.lv__days{display:block;margin-top:4px;font-size:var(--font-size-sm);color:var(--text-secondary)}.lv__reason{display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--text-primary)}.lv__meta{display:block;margin-top:5px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.lv__review{margin-top:9px;padding:9px 10px;border-radius:8px;background:var(--warning-50,#fff7ed)}.lv__review--return{background:var(--success-50,#f0fdf4)}.lv__review--return .lv__review-title{color:var(--success-800,#166534)}.lv__review-title{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--warning-800,#9a3412)}.lv__review-text{display:block;margin-top:4px;font-size:var(--font-size-sm);line-height:1.5}.lv__receipt{border-color:var(--success-200,#bbf7d0);background:var(--success-50,#f0fdf4)}.lv__receipt-title{color:var(--success-800,#166534);font-size:var(--font-size-md);font-weight:600}.lv__receipt-close{color:var(--success-700,#15803d);font-size:var(--font-size-xs)}.lv__receipt-meta,.lv__receipt-next{display:block;margin-top:5px;color:var(--success-700,#15803d);font-size:var(--font-size-xs);line-height:1.5}.lv__return-editor{display:flex;flex-direction:column;gap:8px;margin-top:10px;padding:10px;border:1px solid var(--teacher-200,#bfdbfe);border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.lv__return-editor .lv__textarea{background:var(--bg-card)}.lv__withdraw{margin-top:10px}.lv__mask{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100;display:flex;align-items:flex-end}.lv__sheet{width:100%;border-radius:16px 16px 0 0;padding:16px;box-sizing:border-box;max-height:88vh;overflow-y:auto}.lv__field{margin-top:12px}.lv__label{display:block;font-size:var(--font-size-sm);margin-bottom:6px}.lv__req{color:var(--danger-600)}.lv__picker{padding:10px 12px;background:var(--gray-50);border-radius:var(--radius-md);font-size:var(--font-size-sm)}.lv__textarea{width:100%;min-height:80px;padding:10px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-sm)}.lv__evidence{padding:10px;border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--gray-50)}.lv__evidence.required{border-color:var(--warning-400,#fb923c);background:var(--warning-50,#fff7ed)}.lv__rule{display:block;font-size:var(--font-size-xs);color:var(--text-secondary);line-height:1.45}.lv__upload{margin-top:8px}.lv__actions{display:flex;gap:10px;margin-top:16px}
</style>
