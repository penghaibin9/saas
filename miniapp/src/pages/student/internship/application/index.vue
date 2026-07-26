<template>
  <view class="page-wrap app">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card">
          <text class="card-title">正式实习申请</text>
          <text class="app__hint">选择学校已发布岗位，或提交自主实习单位及真实证明材料。无需手填岗位ID或文件ID。</text>
        </view>
        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看申请记录，不可新增、提交或撤回。" />
        <MobileInlineAlert v-if="editableApplication?.status === 'REJECTED'" type="warning" title="申请已驳回" :description="editableApplication.reviewComment || '请修改后重新提交。'" />

        <view v-if="!historyMode" class="card stack">
          <view class="app__field">
            <text class="app__label">申请类型</text>
            <picker mode="selector" :range="typeLabels" :value="typeIndex" @change="onTypePick">
              <view class="app__picker">{{ typeLabels[typeIndex] }}</view>
            </picker>
          </view>
          <view v-if="isPosition" class="app__field">
            <text class="app__label">实习岗位 <text class="app__req">*</text></text>
            <picker mode="selector" :range="positionLabels" :value="positionIndex" @change="onPositionPick">
              <view class="app__picker">{{ positionLabels[positionIndex] || '请选择学校已发布岗位' }}</view>
            </picker>
            <text v-if="selectedPosition" class="app__desc">{{ selectedPosition.companyName }} · {{ selectedPosition.workLocation || '地点待定' }} · 剩余 {{ selectedPosition.remaining }} 人</text>
          </view>
          <template v-else>
            <view class="app__field"><text class="app__label">企业名称 <text class="app__req">*</text></text><input v-model.trim="form.companyName" class="app__input" placeholder="不少于2字" /></view>
            <view class="app__field"><text class="app__label">岗位名称 <text class="app__req">*</text></text><input v-model.trim="form.positionName" class="app__input" placeholder="不少于2字" /></view>
            <view class="app__field"><text class="app__label">工作地址 <text class="app__req">*</text></text><input v-model.trim="form.workAddress" class="app__input" placeholder="不少于5字" /></view>
            <view class="app__field"><text class="app__label">单位联系人 <text class="app__req">*</text></text><input v-model.trim="form.contactName" class="app__input" placeholder="联系人姓名" /></view>
            <view class="app__field"><text class="app__label">联系人电话 <text class="app__req">*</text></text><input v-model.trim="form.contactPhone" class="app__input" placeholder="联系电话" /></view>
            <view class="app__file">
              <view class="flex-1"><text class="app__label">自主实习证明 <text class="app__req">*</text></text><text class="app__desc">{{ evidenceFileName || (form.evidenceFileId ? '已上传证明材料' : '请上传企业接收函、协议或盖章证明') }}</text></view>
              <button class="btn btn-ghost" :disabled="uploading" @click="pickEvidence">{{ uploading ? '上传中…' : (form.evidenceFileId ? '重新上传' : '选择文件') }}</button>
            </view>
          </template>
          <view class="app__field"><text class="app__label">申请说明 <text class="app__req">*</text></text><textarea v-model="form.applicationNote" class="app__textarea" maxlength="500" placeholder="说明申请原因和岗位匹配情况（至少5字）" /></view>
        </view>

        <view v-if="history.length" class="card">
          <text class="card-title">我的申请</text>
          <view v-for="item in history" :key="item.id" class="app__hist">
            <view class="row-between">
              <view class="flex-1"><text>{{ item.applicationTypeLabel }} · {{ item.statusLabel }}</text><text class="app__hist-note">{{ item.positionName || item.companyName || item.applicationNote || '' }}</text></view>
              <button v-if="item.status === 'PENDING_REVIEW' && !historyMode" class="btn btn-ghost app__wd" :disabled="submitting" @click="withdraw(item)">撤回</button>
            </view>
            <text v-if="item.reviewComment" class="app__review">审核意见：{{ item.reviewComment }}</text>
            <text class="app__version">版本 {{ item.version }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="pageState === 'ready' && !historyMode && !pendingApplication">
      <button class="btn btn-ghost flex-1" :disabled="submitting || uploading" @click="saveDraft">保存草稿</button>
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : '提交审核' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'

const TYPES = [
  { value: 'POSITION', label: '学校岗位志愿' },
  { value: 'SELF_ARRANGED', label: '自主实习' }
]

export default {
  data() {
    return {
      pageState: 'loading', submitting: false, uploading: false, historyMode: false,
      typeIndex: 0, typeLabels: TYPES.map((x) => x.label), positions: [], positionIndex: 0,
      evidenceFileName: '', history: [], editableApplication: null,
      form: { companyName: '', positionName: '', workAddress: '', contactName: '', contactPhone: '', evidenceFileId: '', applicationNote: '' }
    }
  },
  computed: {
    isPosition() { return TYPES[this.typeIndex].value === 'POSITION' },
    positionLabels() { return this.positions.map((x) => `${x.title} · ${x.companyName} · 剩余${x.remaining}人`) },
    selectedPosition() { return this.positions[this.positionIndex] || null },
    pendingApplication() { return this.history.some((x) => x.status === 'PENDING_REVIEW') }
  },
  onLoad() { this.load() },
  methods: {
    onTypePick(e) { this.typeIndex = Number(e.detail.value) || 0; this.editableApplication = null },
    onPositionPick(e) { this.positionIndex = Number(e.detail.value) || 0 },
    async load() {
      this.pageState = 'loading'
      try {
        const [rows, library, dashboard] = await Promise.all([
          studentApi.getInternshipApplications(), studentApi.getInternshipEnterprises(), studentApi.getInternship()
        ])
        this.history = Array.isArray(rows) ? rows : rows?.items || []
        this.positions = (library?.items || []).filter((x) => Number(x.remaining || 0) > 0)
        this.historyMode = !!dashboard?.historyMode
        const editable = this.history.find((x) => ['DRAFT', 'REJECTED', 'WITHDRAWN'].includes(x.status)) || null
        this.editableApplication = editable
        if (editable) this.fillEditable(editable)
        this.pageState = 'ready'
      } catch (e) { this.pageState = 'error' }
    },
    fillEditable(item) {
      const index = TYPES.findIndex((x) => x.value === item.applicationType)
      if (index >= 0) this.typeIndex = index
      this.form = {
        companyName: item.companyName || '', positionName: item.positionName || '',
        workAddress: item.workAddress || '', contactName: item.contactName || '',
        contactPhone: item.contactPhone || '', evidenceFileId: item.evidenceFileId || '',
        applicationNote: item.applicationNote || ''
      }
      if (item.positionId) {
        const positionIndex = this.positions.findIndex((x) => String(x.id) === String(item.positionId))
        if (positionIndex >= 0) this.positionIndex = positionIndex
      }
      this.evidenceFileName = item.evidenceFileId ? '已上传证明材料' : ''
    },
    async pickEvidence() {
      if (this.uploading) return
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_APPLICATION' })
        this.form.evidenceFileId = result.fileId
        this.evidenceFileName = result.fileName || file.name || '证明材料'
        toast('证明材料已上传')
      } catch (e) { toast(e?.message || '文件上传失败') }
      finally { this.uploading = false }
    },
    payload() {
      const applicationType = TYPES[this.typeIndex].value
      const body = { applicationType, applicationNote: String(this.form.applicationNote || '').trim() }
      if (this.editableApplication) {
        body.id = this.editableApplication.id
        body.expectedVersion = this.editableApplication.version
      }
      if (applicationType === 'POSITION') body.positionId = this.selectedPosition?.id || ''
      else Object.assign(body, this.form)
      return body
    },
    validate() {
      if (String(this.form.applicationNote || '').trim().length < 5) return '申请说明不少于5字'
      if (this.isPosition) return this.selectedPosition ? '' : '请选择实习岗位'
      if (String(this.form.companyName || '').trim().length < 2) return '请填写企业名称'
      if (String(this.form.positionName || '').trim().length < 2) return '请填写岗位名称'
      if (String(this.form.workAddress || '').trim().length < 5) return '请填写工作地址'
      if (String(this.form.contactName || '').trim().length < 2) return '请填写单位联系人'
      if (!String(this.form.contactPhone || '').trim()) return '请填写联系电话'
      if (!this.form.evidenceFileId) return '请上传自主实习证明材料'
      return ''
    },
    async saveDraft() {
      if (this.submitting) return
      this.submitting = true
      try {
        const result = await studentApi.saveInternshipApplication(this.payload())
        toast('草稿已保存')
        await this.load()
        this.editableApplication = this.history.find((x) => x.id === result.id) || result
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') { toast('申请版本已变化，正在刷新'); await this.load() }
        else toast(e?.message || '保存失败')
      } finally { this.submitting = false }
    },
    async submit() {
      if (this.submitting) return
      const error = this.validate()
      if (error) return toast(error)
      this.submitting = true
      try {
        const saved = await studentApi.saveInternshipApplication(this.payload())
        await studentApi.submitInternshipApplication(saved.id, saved.version)
        toast('申请已提交审核')
        await this.load()
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') { toast('申请状态已变化，正在刷新'); await this.load() }
        else toast(e?.message || '提交失败')
      } finally { this.submitting = false }
    },
    withdraw(item) {
      uni.showModal({
        title: '撤回申请', content: '确认撤回该待审核申请？',
        success: async (result) => {
          if (!result.confirm) return
          this.submitting = true
          try { await studentApi.withdrawInternshipApplication(item.id, item.version); toast('已撤回'); await this.load() }
          catch (e) { toast(e?.message || '撤回失败'); await this.load() }
          finally { this.submitting = false }
        }
      })
    }
  }
}
</script>

<style scoped>
.app__hint,.app__desc,.app__version { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:var(--space-2); }
.app__field { display:flex;flex-direction:column;gap:6px;margin-bottom:var(--space-3); }
.app__label { font-size:var(--font-size-sm);color:var(--text-secondary); }
.app__req { color:var(--danger-500); }
.app__input,.app__picker { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-sm); }
.app__textarea { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;min-height:90px;width:100%;box-sizing:border-box;font-size:var(--font-size-sm); }
.app__file { display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3); }
.app__hist { padding:var(--space-2) 0;border-bottom:1px solid var(--border-light);font-size:var(--font-size-sm); }
.app__hist-note,.app__review { display:block;margin-top:4px;color:var(--text-tertiary);font-size:var(--font-size-xs); }
.app__review { color:var(--warning-700); }
.app__wd { margin-left:8px;font-size:12px;padding:4px 10px; }
</style>
