<template>
  <view class="page-wrap ins">
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看保险信息，不可重新提交。" />
        <MobileInlineAlert v-else-if="info?.canRenew" type="warning" title="请更新保险保障" :description="`${info.coverageReason || '请补充有效保单'}；提交后由学校重新核验，旧核验记录保留。`" />
        <MobileInlineAlert v-else-if="info?.status === 'REJECTED'" type="warning" title="保险材料已驳回" :description="info.verifyComment || '请核对保单和凭证后重新提交。'" />
        <MobileInlineAlert v-if="submitError" type="warning" title="本次操作未完成" :description="submitError" />
        <button v-if="conflict" class="btn btn-ghost" :disabled="submitting || uploading" @click="load">重新读取最新保单</button>
        <view class="card">
          <view class="row-between">
            <text class="card-title">实习保险</text>
            <MobileStatusTag :label="info?.statusLabel || '未提交'" :type="statusTone" />
          </view>
          <text v-if="info?.version" class="ins__version">记录版本 {{ info.version }}</text>
        </view>
        <view class="card stack">
          <view class="ins__field"><text class="ins__label">承保单位 *</text><input v-model.trim="form.insurerName" class="ins__input" :disabled="readonly" placeholder="如：人保财险" /></view>
          <view class="ins__field"><text class="ins__label">保单号 *</text><input v-model.trim="form.policyNo" class="ins__input" :disabled="readonly" placeholder="保险公司出具的保单编号" /></view>
          <view class="ins__field"><text class="ins__label">险种</text><input v-model.trim="form.coverageType" class="ins__input" :disabled="readonly" placeholder="如：实习责任险" /></view>
          <view class="ins__field"><text class="ins__label">生效日期 *</text><input v-model.trim="form.effectiveDate" class="ins__input" :disabled="readonly" placeholder="YYYY-MM-DD" /></view>
          <view class="ins__field"><text class="ins__label">到期日期 *</text><input v-model.trim="form.expiryDate" class="ins__input" :disabled="readonly" placeholder="YYYY-MM-DD" /></view>
          <view class="ins__file">
            <view class="flex-1">
              <text class="ins__label">保险凭证 *</text>
              <text class="ins__file-name">{{ fileName || (form.fileId ? '已上传保险凭证' : '请上传保单或保险证明') }}</text>
            </view>
            <button v-if="!readonly" class="btn btn-ghost" :disabled="uploading" @click="pickFile">{{ uploading ? '上传中…' : (form.fileId ? '重新上传' : '选择文件') }}</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="pageState === 'ready' && !readonly">
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading || conflict" @click="submit">
        {{ submitting ? '提交中…' : info?.canRenew ? '更新保单并提交核验' : (info?.status === 'REJECTED' ? '修改并重新提交' : '提交保险信息') }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      pageState: 'loading', submitting: false, uploading: false, conflict: false, submitError: '', requestSeq: 0,
      info: null, historyMode: false, fileName: '',
      form: { insurerName: '', policyNo: '', coverageType: '', effectiveDate: '', expiryDate: '', fileId: '' }
    }
  },
  computed: {
    readonly() { return this.historyMode || (this.info?.status === 'VERIFIED' && this.info.canRenew !== true) },
    statusTone() {
      if (this.info?.canRenew) return 'warning'
      if (this.info?.status === 'VERIFIED') return 'success'
      if (this.info?.status === 'REJECTED') return 'danger'
      return 'warning'
    }
  },
  onLoad() { this.load() },
  onUnload() { this.requestSeq++ },
  methods: {
    async load() {
      const seq = ++this.requestSeq
      this.pageState = 'loading'
      try {
        const [info, dashboard] = await Promise.all([
          studentApi.getInternshipInsurance(), studentApi.getInternship()
        ])
        if (seq !== this.requestSeq) return
        this.info = info || { status: 'NOT_SUBMITTED', statusLabel: '未提交', version: 0 }
        this.conflict = false; this.submitError = ''
        this.historyMode = !!dashboard?.historyMode
        this.form = {
          insurerName: info?.insurerName || '', policyNo: info?.policyNo || '',
          coverageType: info?.coverageType || '', effectiveDate: info?.effectiveDate || '',
          expiryDate: info?.expiryDate || '', fileId: info?.fileId || ''
        }
        this.fileName = info?.fileId ? '已上传保险凭证' : ''
        this.pageState = 'ready'
      } catch (e) { if (seq === this.requestSeq) this.pageState = 'error' }
    },
    async pickFile() {
      if (this.uploading || this.submitting || this.readonly) return
      const seq = this.requestSeq
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_INSURANCE' })
        if (seq !== this.requestSeq) return
        if (!result?.fileId) throw new Error('上传结果不完整，原凭证已保留')
        this.form.fileId = result.fileId
        this.fileName = result.fileName || file.name || '保险凭证'
        toast('保险凭证已上传')
      } catch (e) { if (seq === this.requestSeq) this.submitError = e?.message || '文件上传失败，原凭证已保留' }
      finally { this.uploading = false }
    },
    async submit() {
      if (this.submitting || this.uploading || this.readonly || this.conflict) return
      if (this.info?.id && !Number.isInteger(this.info.version)) { this.submitError = '保单版本缺失，请重新读取后再提交'; return }
      if (!this.form.insurerName || !this.form.policyNo) return toast('请填写承保单位和保单号')
      if (!this.form.effectiveDate || !this.form.expiryDate) return toast('请填写保险生效和到期日期')
      if (!this.form.fileId) return toast('请上传保险凭证')
      const seq = this.requestSeq
      this.submitError = ''
      this.submitting = true
      try {
        await studentApi.submitInternshipInsurance({
          ...this.form,
          ...(this.info?.id ? { expectedVersion: this.info.version } : {})
        })
        if (seq !== this.requestSeq) return
        toast('已提交，等待学校核验')
        await this.load()
      } catch (e) {
        if (seq !== this.requestSeq) return
        this.conflict = Number(e?.code) === 409 || Math.floor(Number(e?.code) / 1000) === 409 || e?.code === 'DATA_CONFLICT'
        this.submitError = this.conflict ? '保单已变化，填写内容已保留。重新读取将载入最新保单，请核对后提交。' : (e?.message || '提交失败，填写内容已保留')
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.ins__version { display:block;margin-top:6px;font-size:var(--font-size-xs);color:var(--text-tertiary); }
.ins__field { margin-bottom:12px; }
.ins__label { display:block;font-size:var(--font-size-sm);margin-bottom:4px; }
.ins__input { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-sm); }
.ins__file { display:flex;align-items:center;gap:var(--space-3);padding-top:4px; }
.ins__file-name { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary); }
</style>
