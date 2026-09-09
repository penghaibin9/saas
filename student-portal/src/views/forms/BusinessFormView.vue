<template>
  <section class="business-form-page">
    <header><p class="eyebrow">PLAT-B</p><h1>{{ title }}</h1><p>表单版本与校验规则来自服务端；提交将进入原业务流程。</p></header>
    <p v-if="loading" class="state">正在加载表单…</p>
    <p v-else-if="error" class="state error">{{ error }}</p>
    <template v-else-if="formVersion">
      <section v-if="compliance.length" class="compliance">
        <article v-for="item in compliance" :key="item.provider_code || item.providerCode">
          <strong>{{ item.provider_code || item.providerCode }}</strong>
          <span :class="{ blocking: item.blocking }">{{ item.blocking ? '存在阻断' : '当前检查通过' }}</span>
          <ul><li v-for="rule in item.items || []" :key="rule.code">{{ rule.label }} · {{ stateLabel(rule.state) }}<small v-if="rule.reason">{{ rule.reason }}</small></li></ul>
        </article>
      </section>
      <SchemaBusinessForm
        :form-version="formVersion"
        :initial-data="initialData"
        :server-errors="fieldErrors"
        @submit="submit"
        @unsupported="unsupported"
        @request-file-center="pickFile"
      />
      <input ref="fileInput" class="hidden" type="file" @change="uploadSelected" />
      <p v-if="fileStatus" class="state">{{ fileStatus }}</p>
      <p v-if="result" class="state success">已提交：{{ result.status }} · 业务版本 {{ result.version }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SchemaBusinessForm from '../../components/businessForms/SchemaBusinessForm.vue'
import { portalApi } from '../../services/portalApi'
import fileSdk from '../../services/fileSdk'

const route = useRoute()
const router = useRouter()
const formVersion = ref(null)
const initialData = ref({})
const compliance = ref([])
const loading = ref(true)
const error = ref('')
const result = ref(null)
const fileInput = ref(null)
const pendingFileField = ref(null)
const fileStatus = ref('')
const fieldErrors = ref({})
const title = computed(() => formVersion.value?.formCode || formVersion.value?.form_code || '业务表单')

const context = computed(() => Object.fromEntries(['action', 'internshipId', 'filingId']
  .filter(key => route.query[key] != null && route.query[key] !== '')
  .map(key => [key, String(route.query[key])])))
const complianceRequests = computed(() => {
  const source = {
    providerCode: route.query.providerCode,
    domain: route.query.subjectDomain,
    subjectType: route.query.subjectType,
    subjectId: route.query.subjectId,
    operation: route.query.operation,
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
})
function stateLabel(state) {
  return ({ PASS: '通过', BLOCKER: '阻断', WARNING: '提醒', PENDING: '处理中', NOT_EVALUATED: '未评估', NOT_APPLICABLE: '不适用', EXEMPTED: '已豁免' })[state] || '未评估'
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const data = await portalApi.businessFormLoad({
      formCode: route.params.formCode,
      versionId: Number(route.params.versionId),
      client: 'STUDENT_PC', context: context.value, complianceRequests: complianceRequests.value
    })
    formVersion.value = data.formVersion
    initialData.value = data.initialData || {}
    compliance.value = data.complianceSummary || []
  } catch (e) { error.value = e?.message || '表单加载失败' }
  finally { loading.value = false }
}
function unsupported() { error.value = 'FORM_CLIENT_UNSUPPORTED：该版本不支持学生 PC，请返回原业务入口。' }
function pickFile(field) { pendingFileField.value = field; fileInput.value?.click() }
async function uploadSelected(event) {
  const file = event.target.files?.[0]
  if (!file || !pendingFileField.value) return
  fileStatus.value = '文件正在进入文件中心并执行安全扫描…'
  try {
    const uploaded = await fileSdk.upload(file, { bizType: 'INTERNSHIP', bizId: context.value.filingId || '' })
    const code = pendingFileField.value.code
    const current = initialData.value[code]
    initialData.value = {
      ...initialData.value,
      [code]: pendingFileField.value.multiple ? [...(Array.isArray(current) ? current : []), uploaded.fileId] : uploaded.fileId
    }
    fileStatus.value = uploaded.readyForBusiness ? '文件已通过安全扫描。' : `文件中心状态：${uploaded.statusText || '等待安全扫描'}`
  } catch (e) { error.value = e?.message || '文件上传失败' }
  finally { event.target.value = ''; pendingFileField.value = null }
}
async function submit(payload) {
  error.value = ''; result.value = null; fieldErrors.value = {}
  try {
    result.value = await portalApi.businessFormSubmit({
      formCode: payload.formCode,
      versionId: payload.formVersionId,
      schemaHash: payload.schemaHash,
      client: 'STUDENT_PC', values: payload.values, context: context.value,
      expectedBusinessVersion: route.query.expectedBusinessVersion == null ? null : Number(route.query.expectedBusinessVersion),
    })
    const target = result.value?.next_action?.target || result.value?.nextAction?.target
    if (target?.path) router.push({ path: target.path, query: target.query || undefined })
  } catch (e) {
    const field = String(e?.details?.field || '')
    if (field) fieldErrors.value = { [field]: e?.message || '字段校验失败' }
    error.value = e?.message || '提交失败'
  }
}
onMounted(load)
</script>

<style scoped>
.business-form-page{max-width:840px;margin:0 auto;display:grid;gap:18px}.business-form-page h1,.business-form-page p{margin:0}.eyebrow{color:#2563eb;font-weight:700}.state{padding:12px;border-radius:8px;background:#f2f4f7}.error{color:#b42318;background:#fee4e2}.success{color:#067647;background:#dcfae6}.compliance{display:grid;gap:10px}.compliance article{padding:14px;border:1px solid #e4e7ec;border-radius:10px}.compliance article>span{float:right;color:#067647}.compliance article>span.blocking{color:#b42318}.compliance small{display:block;color:#667085}.hidden{display:none}
</style>
