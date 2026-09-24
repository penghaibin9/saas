<template>
  <view class="page-shell">
    <MobilePrivacyGate />
    <view class="head"><text class="eyebrow">PLAT-B</text><text class="title">{{ title }}</text><text class="hint">版本与规则来自服务端，提交进入原业务流程。</text></view>
    <view v-if="state === 'loading'" class="state">正在加载表单…</view>
    <view v-else-if="state === 'error'" class="state error"><text>{{ error }}</text><button size="mini" @click="load">重试</button></view>
    <template v-else>
      <view v-for="assessment in compliance" :key="assessment.provider_code || assessment.providerCode" class="compliance">
        <text>{{ assessment.provider_code || assessment.providerCode }}</text>
        <text :class="{ blocker: assessment.blocking }">{{ assessment.blocking ? '存在阻断' : '当前检查通过' }}</text>
      </view>
      <SchemaBusinessForm
        :form-version="formVersion"
        :initial-data="initialData"
        :client-type="clientType"
        @submit="submit"
        @unsupported="unsupported"
        @request-file-center="pickFile"
      />
      <view v-if="notice" class="state success">{{ notice }}</view>
    </template>
  </view>
</template>

<script>
import SchemaBusinessForm from '@/components/businessForms/SchemaBusinessForm.vue'
import { businessFormApi } from '@/services/businessFormApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { normalizeError, safeToast } from '@/services/request'
import { runAction } from '@/services/actionRouter'

export default {
  components: { SchemaBusinessForm },
  data() {
    return { options: {}, formVersion: {}, initialData: {}, compliance: [], state: 'loading', error: '', notice: '', uploading: false }
  },
  computed: {
    clientType() { return String(this.options.client || '').toUpperCase() === 'TEACHER_MINIAPP' ? 'TEACHER_MINIAPP' : 'STUDENT_MINIAPP' },
    side() { return this.clientType === 'TEACHER_MINIAPP' ? 'teacher' : 'student' },
    title() { return this.formVersion.formCode || this.formVersion.form_code || '业务表单' },
    context() {
      return Object.fromEntries(['action', 'internshipId', 'filingId']
        .filter(key => this.options[key] != null && this.options[key] !== '')
        .map(key => [key, String(this.options[key])]))
    },
    complianceRequests() {
      const source = {
        providerCode: this.options.providerCode,
        domain: this.options.subjectDomain,
        subjectType: this.options.subjectType,
        subjectId: this.options.subjectId,
        operation: this.options.operation,
      }
      if (!source.providerCode || !source.domain || !source.subjectType || !source.subjectId) return []
      return [{
        providerCode: String(source.providerCode),
        subjectRef: {
          domain: String(source.domain),
          subject_type: String(source.subjectType),
          subject_id: String(source.subjectId),
        },
        operation: String(source.operation || 'READ'),
      }]
    }
  },
  onLoad(options) { this.options = options || {}; this.load() },
  methods: {
    async load() {
      if (!this.options.formCode || !Number(this.options.versionId)) { this.state = 'error'; this.error = '表单 action 缺少 exact formCode/versionId'; return }
      this.state = 'loading'; this.error = ''
      try {
        const data = await businessFormApi.load({ formCode: this.options.formCode, versionId: Number(this.options.versionId), client: this.clientType, context: this.context, complianceRequests: this.complianceRequests })
        this.formVersion = data.formVersion; this.initialData = data.initialData || {}; this.compliance = data.complianceSummary || []; this.state = 'ready'
      } catch (e) { this.error = normalizeError(e).text; this.state = 'error' }
    },
    unsupported() { this.error = 'FORM_CLIENT_UNSUPPORTED：请前往 PC 办理完整表单。'; this.state = 'error' },
    async pickFile(field) {
      if (this.uploading) return
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP', bizId: this.context.filingId || '' })
        const current = this.initialData[field.code]
        this.initialData = { ...this.initialData, [field.code]: field.multiple ? [...(Array.isArray(current) ? current : []), uploaded.fileId] : uploaded.fileId }
        this.notice = uploaded.readyForBusiness ? '文件已通过安全扫描。' : `文件中心状态：${uploaded.statusText || '等待安全扫描'}`
      } catch (e) { safeToast(normalizeError(e).text || '文件选择失败') }
      finally { this.uploading = false }
    },
    async submit(payload) {
      this.error = ''; this.notice = ''
      try {
        const result = await businessFormApi.submit({
          formCode: payload.formCode, versionId: payload.formVersionId, schemaHash: payload.schemaHash,
          client: this.clientType, values: payload.values, context: this.context,
          expectedBusinessVersion: this.options.expectedBusinessVersion == null ? null : Number(this.options.expectedBusinessVersion),
        })
        this.notice = `已提交：${result.status || 'SUCCESS'}`
        const nextAction = result.nextAction || result.next_action
        if (nextAction) runAction(nextAction, { side: this.side })
      } catch (e) { this.error = normalizeError(e).text; this.state = 'error' }
    }
  }
}
</script>

<style scoped>
.page-shell{padding:24rpx;display:flex;flex-direction:column;gap:24rpx}.head{display:flex;flex-direction:column;gap:8rpx}.eyebrow{color:#2563eb;font-weight:700}.title{font-size:38rpx;font-weight:700}.hint{color:#667085;font-size:24rpx}.state,.compliance{padding:20rpx;border-radius:12rpx;background:#f2f4f7}.error{color:#b42318;background:#fee4e2}.success{color:#067647;background:#dcfae6}.compliance{display:flex;justify-content:space-between}.blocker{color:#b42318}
</style>
