<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="免实习申请" show-back />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card ex__head">
          <view class="row-between">
            <view>
              <text class="card-title">免实习申请</text>
              <text class="ex__hint">适用于升学、参军入伍、健康原因或学校认可的其他情形。只有学校审核通过后，系统才会把实习去向标记为“免实习”。</text>
            </view>
            <MobileStatusTag v-if="application" :label="application.statusLabel || application.status" :type="statusTone" />
          </view>
        </view>

        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看，不能新建或重新提交免实习申请。" />
        <MobileInlineAlert v-else-if="application?.status === 'PENDING_REVIEW'" type="warning" title="等待学校审核" description="学校审核前可撤回；审核通过后会正式写入免实习去向。" />
        <MobileInlineAlert v-else-if="application?.status === 'APPROVED'" type="success" title="免实习已批准" :description="application.reviewComment || '学校已批准本次免实习申请。'" />
        <MobileInlineAlert v-else-if="application?.status === 'REJECTED'" type="warning" title="申请已驳回" :description="application.reviewComment || '请按学校意见补充材料后重新提交。'" />
        <MobileInlineAlert v-if="errorMessage" type="warning" title="本次操作未完成" :description="errorMessage" />

        <view class="card stack">
          <view class="ex__field">
            <text class="ex__label">免实习类型 <text class="ex__req">*</text></text>
            <picker mode="selector" :disabled="!editable" :range="typeLabels" :value="typeIndex" @change="onType">
              <view class="ex__picker">{{ typeLabels[typeIndex] }} <text v-if="editable">▾</text></view>
            </picker>
          </view>
          <view class="ex__field">
            <text class="ex__label">免实习后去向 <text class="ex__req">*</text></text>
            <input v-model.trim="form.exemptionDestination" class="ex__input" :disabled="!editable" maxlength="200" placeholder="如：已升学至××学校 / 参军入伍" />
          </view>
          <view class="ex__field">
            <text class="ex__label">申请原因 <text class="ex__req">*</text></text>
            <textarea v-model="form.exemptionReason" class="ex__textarea" :disabled="!editable" maxlength="500" placeholder="不少于5字，说明申请免实习的具体原因" />
          </view>
          <view class="ex__field ex__evidence">
            <text class="ex__label">佐证材料 <text class="ex__req">*</text></text>
            <text class="ex__file-name">{{ fileName || (form.evidenceFileId ? '已上传佐证材料' : '需上传录取、入伍、健康证明或学校认可材料') }}</text>
            <button v-if="editable" class="btn btn-ghost ex__upload" :disabled="uploading || submitting" @click="chooseEvidence">
              {{ uploading ? '上传中…' : (form.evidenceFileId ? '重新上传' : '选择并上传材料') }}
            </button>
          </view>
        </view>

        <view v-if="application" class="card">
          <text class="card-title">办理记录</text>
          <view class="ex__record"><text>提交时间</text><text>{{ formatTime(application.submittedAt) }}</text></view>
          <view class="ex__record"><text>当前状态</text><text>{{ application.statusLabel || application.status }}</text></view>
          <view v-if="application.reviewedBy" class="ex__record"><text>审核人</text><text>{{ application.reviewedBy }}</text></view>
          <view v-if="application.reviewedAt" class="ex__record"><text>审核时间</text><text>{{ formatTime(application.reviewedAt) }}</text></view>
          <view v-if="application.reviewComment" class="ex__review"><text class="ex__label">审核意见</text><text>{{ application.reviewComment }}</text></view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="pageState === 'ready' && editable">
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">
        {{ submitting ? '提交中…' : (application?.status === 'REJECTED' ? '补充后重新提交' : '提交免实习申请') }}
      </button>
    </MobileSafeAreaBar>
    <MobileSafeAreaBar v-else-if="pageState === 'ready' && application?.status === 'PENDING_REVIEW' && !historyMode">
      <button class="btn btn-ghost flex-1" :disabled="submitting" @click="withdraw">{{ submitting ? '处理中…' : '撤回申请' }}</button>
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
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
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
      fileName: '', errorMessage: '',
      form: { exemptionType: 'FURTHER_STUDY', exemptionDestination: '', exemptionReason: '', evidenceFileId: '' }
    }
  },
  computed: {
    typeLabels() { return TYPES.map((item) => item.label) },
    editable() {
      if (this.historyMode) return false
      return !this.application || ['DRAFT', 'REJECTED', 'WITHDRAWN'].includes(this.application.status)
    },
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
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    onType(event) {
      this.typeIndex = Number(event.detail.value) || 0
      this.form.exemptionType = TYPES[this.typeIndex]?.value || 'FURTHER_STUDY'
    },
    async load() {
      this.pageState = 'loading'
      this.errorMessage = ''
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        this.context = { batchId: dashboard?.batchId || '', internshipId: dashboard?.recordId || '' }
        this.historyMode = !!dashboard?.historyMode
        const rows = await studentInternshipApplications(this.context.batchId, this.context.internshipId)
        this.application = (rows || []).find((item) => item.applicationType === 'EXEMPTION') || null
        if (this.application) {
          const idx = TYPES.findIndex((item) => item.value === this.application.exemptionType)
          this.typeIndex = idx >= 0 ? idx : 0
          this.form = {
            exemptionType: TYPES[this.typeIndex].value,
            exemptionDestination: this.application.exemptionDestination || '',
            exemptionReason: this.application.exemptionReason || '',
            evidenceFileId: this.application.evidenceFileId || ''
          }
          this.fileName = this.form.evidenceFileId ? '已上传佐证材料' : ''
        }
        this.pageState = 'ready'
      } catch (error) {
        this.errorMessage = error?.message || '免实习申请读取失败'
        this.pageState = 'error'
      }
    },
    async chooseEvidence() {
      if (!this.editable || this.uploading || this.submitting) return
      this.uploading = true
      this.errorMessage = ''
      try {
        const file = await chooseSingleFile()
        if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个佐证文件不能超过20MB')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP', bizId: '' })
        if (!uploaded?.fileId) throw new Error('上传结果不完整')
        this.form.evidenceFileId = uploaded.fileId
        this.fileName = uploaded.fileName || file.name || '免实习佐证材料'
        toast('佐证材料上传成功')
      } catch (error) {
        this.errorMessage = error?.message || '佐证材料上传失败'
      } finally {
        this.uploading = false
      }
    },
    async submit() {
      if (!this.editable || this.submitting || this.uploading) return
      if ((this.form.exemptionDestination || '').trim().length < 2) return toast('请填写免实习后去向')
      if ((this.form.exemptionReason || '').trim().length < 5) return toast('申请原因不少于5字')
      if (!this.form.evidenceFileId) return toast('请上传佐证材料')
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
        await studentInternshipApplicationSubmit(draft.id, {
          ...this.context,
          expectedVersion: draft.version
        })
        toast('免实习申请已提交')
        await this.load()
      } catch (error) {
        this.errorMessage = error?.message || '提交失败，请稍后重试'
      } finally {
        this.submitting = false
      }
    },
    async withdraw() {
      if (!this.application?.id || this.application.status !== 'PENDING_REVIEW' || this.submitting) return
      this.submitting = true
      this.errorMessage = ''
      try {
        await studentInternshipApplicationWithdraw(this.application.id, {
          ...this.context,
          expectedVersion: this.application.version
        })
        toast('申请已撤回')
        await this.load()
      } catch (error) {
        this.errorMessage = error?.message || '撤回失败，请刷新后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.ex__head{border-top:3px solid var(--brand-primary)}.ex__hint{display:block;margin-top:6px;font-size:var(--font-size-xs);line-height:1.6;color:var(--text-secondary)}
.ex__field{margin-bottom:14px}.ex__label{display:block;margin-bottom:6px;font-size:var(--font-size-sm);font-weight:500}.ex__req{color:var(--danger-600)}
.ex__picker,.ex__input,.ex__textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-sm);background:var(--bg-card)}
.ex__textarea{min-height:110px}.ex__evidence{padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}
.ex__file-name{display:block;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-tertiary)}.ex__upload{margin-top:9px}
.ex__record{display:flex;justify-content:space-between;gap:16px;padding:9px 0;border-bottom:1px solid var(--border-light);font-size:var(--font-size-sm)}.ex__record:last-child{border-bottom:0}
.ex__record text:first-child{color:var(--text-tertiary)}.ex__review{margin-top:12px;padding:10px;border-radius:var(--radius-md);background:var(--warning-50,#fff7ed);font-size:var(--font-size-sm);line-height:1.6}
</style>
