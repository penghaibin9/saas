<template>
  <view class="page-wrap">
    <MobilePrivacyGate />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="o" class="page-pad stack">
        <MobileInlineAlert v-if="!available" type="warning" :description="o.selfService?.reason || '当前预报到未开放'" />
        <view class="card stack-sm">
          <text class="card-title">提交材料</text>
          <view class="om__field"><text>材料类型</text><picker :range="typeLabels" :value="typeIndex" @change="typeIndex = Number($event.detail.value)"><text class="om__value">{{ typeLabels[typeIndex] }} ›</text></picker></view>
          <view class="om__picker" :class="{ 'is-disabled': uploading || !available }" @click="pickFile"><text>{{ uploading ? '上传中…' : (fileName || '选择并上传文件') }}</text></view>
          <button class="btn btn-primary" :disabled="submitting || !fileId || !available" @click="submit">{{ submitting ? '提交中…' : '提交审核' }}</button>
        </view>
        <view class="card stack-sm">
          <text class="card-title">提交记录</text>
          <view v-for="m in materials" :key="m.id" class="om__row">
            <view><text class="t-md">{{ label(m.materialType) }}</text><text class="om__meta">第 {{ m.submissionNo }} 版 · {{ m.fileName }}</text></view>
            <view class="om__right"><text :class="['om__status', 'is-' + String(m.status).toLowerCase()]">{{ statusLabel(m.status) }}</text><text v-if="m.returnReason" class="om__reason">{{ m.returnReason }}</text></view>
          </view>
          <text v-if="!materials.length" class="t-sm text-secondary">尚未提交迎新材料</text>
        </view>
        <MobileInlineAlert type="info" description="文件先进入私有安全扫描；提交后形成不可覆盖的版本记录。审核中或已通过的材料不能重复提交。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'
import { createClientRequestId } from '@/utils/clientRequestId'

const types = ['ID_CARD', 'ADMISSION_LETTER', 'PHOTO', 'ARCHIVE']
const labels = { ID_CARD: '身份证明', ADMISSION_LETTER: '录取通知书', PHOTO: '证件照', ARCHIVE: '纸质档案凭证' }
export default {
  data() { return { o: null, state: 'loading', uploading: false, submitting: false, typeIndex: 0, typeLabels: types.map((x) => labels[x]), fileId: '', fileName: '', clientSubmissionId: '' } },
  computed: {
    available() { return !!this.o?.selfService?.available },
    materials() { return this.o?.selfService?.materials || [] }
  },
  onLoad() { this.load() },
  methods: {
    label(type) { return labels[type] || type },
    statusLabel(status) { return ({ UPLOADED: '待审核', APPROVED: '已通过', RETURNED: '已退回', REJECTED: '已驳回' })[status] || status },
    async load() { this.state = 'loading'; try { this.o = await studentApi.getOrientation(); this.state = 'ready' } catch (e) { this.state = 'error' } },
    async pickFile() {
      if (this.uploading || !this.available) return
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const result = await uploadBusinessFile(file, { bizType: 'ORIENTATION_MATERIAL' })
        this.fileId = result.fileId; this.fileName = result.fileName || file.name || '迎新材料'
        this.clientSubmissionId = createClientRequestId('orientation-material')
        toast('文件已上传，请提交审核')
      } catch (e) { toast(e?.message || '文件上传失败') } finally { this.uploading = false }
    },
    async submit() {
      if (!this.fileId) return toast('请先选择文件')
      this.submitting = true
      try {
        if (!this.clientSubmissionId) this.clientSubmissionId = createClientRequestId('orientation-material')
        await studentApi.submitOrientationMaterial({ materialType: types[this.typeIndex], fileId: this.fileId, clientSubmissionId: this.clientSubmissionId })
        toast('材料已提交'); this.fileId = ''; this.fileName = ''; this.clientSubmissionId = ''; await this.load()
      } catch (e) { toast(e?.message || '材料提交失败') } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.om__field { display:flex; justify-content:space-between; align-items:center; min-height:48px; border-bottom:1px solid var(--border-light); color:var(--text-secondary); }
.om__value { color:var(--text-primary); }
.om__picker { padding:14px; border:1px dashed var(--brand-primary); border-radius:var(--radius-md); text-align:center; color:var(--brand-primary); }
.om__picker.is-disabled { opacity:.55; }
.om__row { display:flex; justify-content:space-between; gap:12px; padding:12px 0; border-bottom:1px solid var(--border-light); }
.om__meta, .om__reason { display:block; margin-top:4px; font-size:var(--font-size-xs); color:var(--text-tertiary); }
.om__right { max-width:45%; text-align:right; }
.om__status { font-size:var(--font-size-sm); color:var(--warning-600); }
.om__status.is-approved { color:var(--success-600); }
.om__status.is-returned, .om__status.is-rejected, .om__reason { color:var(--danger-500); }
</style>
