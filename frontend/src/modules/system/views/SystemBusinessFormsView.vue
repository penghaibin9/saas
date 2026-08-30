<template>
  <section class="forms-page">
    <header class="page-head">
      <div><p class="eyebrow">PLAT-B</p><h1>合规与业务表单</h1><p>发布版本不可变；提交只调用原业务 canonical command。</p></div>
      <button type="button" :disabled="loading" @click="loadDefinitions">刷新</button>
    </header>

    <p v-if="error" class="state error">{{ error }}</p>
    <p v-if="notice" class="state notice">{{ notice }}</p>

    <div class="layout">
      <aside class="card definitions">
        <h2>表单定义</h2>
        <button v-for="item in definitions" :key="item.id" type="button" :class="{ active: selected?.id === item.id }" @click="selectDefinition(item)">
          <strong>{{ item.formName }}</strong><small>{{ item.formCode }} · {{ item.domainCode }}</small>
        </button>
        <p v-if="!definitions.length && !loading">尚无定义。</p>
      </aside>

      <main class="workspace">
        <BusinessFormVersionWorkbench
          v-if="selected"
          :form-code="selected.formCode"
          :versions="versions"
          @preview="preview"
          @validate="validateVersion"
          @impact="impactVersion"
          @publish="publishVersion"
          @disable="disableVersion"
        />
        <section v-else class="card empty">选择一个表单定义查看版本。</section>

        <section v-if="previewVersion" class="card preview">
          <header><h2>版本预览</h2><code>{{ previewVersion.schemaHash || previewVersion.schema_hash }}</code></header>
          <SchemaBusinessForm :form-version="previewVersion" :model-value="{}" client-type="STAFF_PC" @submit="() => {}" />
        </section>

        <section v-if="impact" class="card"><h2>影响分析</h2><pre>{{ JSON.stringify(impact, null, 2) }}</pre></section>

        <section class="card compliance">
          <h2>来源合规评估</h2>
          <div class="fields">
            <input v-model.trim="compliance.providerCode" placeholder="Provider，如 INTERNSHIP_NATIVE" />
            <input v-model.trim="compliance.domain" placeholder="Domain，如 INTERNSHIP" />
            <input v-model.trim="compliance.subjectType" placeholder="Subject type" />
            <input v-model.trim="compliance.subjectId" placeholder="Subject ID" />
            <input v-model.trim="compliance.operation" placeholder="Operation" />
            <button type="button" @click="evaluate">评估</button>
          </div>
          <CompliancePanel v-if="assessment" :assessment="assessment" />
        </section>
      </main>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { businessFormsApi } from '@/modules/system/api/businessForms.api'
import BusinessFormVersionWorkbench from '@/modules/platform/businessForms/components/BusinessFormVersionWorkbench.vue'
import CompliancePanel from '@/modules/platform/businessForms/components/CompliancePanel.vue'
import SchemaBusinessForm from '@/modules/platform/businessForms/components/SchemaBusinessForm.vue'

const definitions = ref([])
const versions = ref([])
const selected = ref(null)
const previewVersion = ref(null)
const impact = ref(null)
const assessment = ref(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const compliance = reactive({ providerCode: 'INTERNSHIP_NATIVE', domain: 'INTERNSHIP', subjectType: 'INTERNSHIP', subjectId: '', operation: 'ONBOARD' })

function messageOf(e, fallback) { return e?.message || fallback }
async function loadDefinitions() {
  loading.value = true; error.value = ''
  try {
    definitions.value = await businessFormsApi.definitions({ limit: 200 })
    if (selected.value) {
      const current = definitions.value.find(item => item.id === selected.value.id)
      if (current) await selectDefinition(current)
    }
  } catch (e) { error.value = messageOf(e, '表单定义加载失败') }
  finally { loading.value = false }
}
async function selectDefinition(item) {
  selected.value = item; previewVersion.value = null; impact.value = null; error.value = ''
  try { versions.value = await businessFormsApi.versions(item.id) }
  catch (e) { error.value = messageOf(e, '表单版本加载失败') }
}
async function preview(item) {
  try { previewVersion.value = (await businessFormsApi.version(item.versionId)).formVersion }
  catch (e) { error.value = messageOf(e, '预览失败') }
}
async function validateVersion(item) {
  try { await businessFormsApi.validate(item.versionId); notice.value = '版本 Schema 与 Hash 校验通过。' }
  catch (e) { error.value = messageOf(e, '版本校验失败') }
}
async function impactVersion(item) {
  try { impact.value = await businessFormsApi.impact(item.versionId) }
  catch (e) { error.value = messageOf(e, '影响分析失败') }
}
async function publishVersion(item) {
  try {
    const analysis = await businessFormsApi.impact(item.versionId)
    const ack = !(analysis.resolveActivePolicyRefs || []).length || window.confirm('该版本引用 RESOLVE_ACTIVE 策略，已审阅影响分析并继续发布？')
    if (!ack) return
    await businessFormsApi.publish(item.versionId, { expectedVersion: item.version, resolveActiveImpactAck: true })
    notice.value = '版本已发布。'; await selectDefinition(selected.value)
  } catch (e) { error.value = messageOf(e, '发布失败') }
}
async function disableVersion(item) {
  if (!window.confirm('停用后四端将无法加载该版本，确认继续？')) return
  try { await businessFormsApi.disable(item.versionId, { expectedVersion: item.version }); notice.value = '版本已停用。'; await selectDefinition(selected.value) }
  catch (e) { error.value = messageOf(e, '停用失败') }
}
async function evaluate() {
  error.value = ''
  try {
    assessment.value = await businessFormsApi.evaluate({
      providerCode: compliance.providerCode,
      subjectRef: { domain: compliance.domain, subject_type: compliance.subjectType, subject_id: compliance.subjectId },
      operation: compliance.operation
    })
  } catch (e) { error.value = messageOf(e, '合规评估失败') }
}
onMounted(loadDefinitions)
</script>

<style scoped>
.forms-page{display:grid;gap:16px}.page-head,.layout,.preview header{display:flex;justify-content:space-between;gap:18px}.page-head h1,.page-head p,.card h2{margin:0}.eyebrow{color:#2563eb;font-weight:700}.layout{align-items:flex-start}.definitions{width:280px;display:grid;gap:8px}.definitions button{display:grid;text-align:left;padding:12px;border:1px solid #e4e7ec;background:#fff;border-radius:8px}.definitions button.active{border-color:#2563eb;background:#eff6ff}.definitions small{color:#667085}.workspace{display:grid;gap:16px;flex:1;min-width:0}.card{background:#fff;border:1px solid #e4e7ec;border-radius:12px;padding:16px}.fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.fields input,.fields button{min-height:38px}.state{padding:10px;border-radius:8px}.error{color:#b42318;background:#fee4e2}.notice{color:#067647;background:#dcfae6}pre{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:900px){.layout{display:grid}.definitions{width:auto}.fields{grid-template-columns:1fr}}
</style>
