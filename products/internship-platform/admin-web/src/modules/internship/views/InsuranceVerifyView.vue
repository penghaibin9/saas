<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ModulePageShell, DataTable, ErrorState, LoadingState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppSearchBox } from '@/components/common'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { fileSdk } from '@/services/file/fileSdk'
import { normalizeUiError } from '@/utils/presentationSafety'
import { insuranceApi } from '../api/plan-insurance.api'
import { canCode } from '../composables/permission'

const props = defineProps({ ctx: { type: Object, required: true } })
const route = useRoute(), router = useRouter()
const BASE = '/admin/internship/insurance'
const previewProvider = { fetchBytes: descriptor => fileSdk.blob(descriptor.fileId), dispose() {} }
const statuses = [{ value: 'PENDING_VERIFY', label: '待核验' }, { value: 'VERIFIED', label: '已通过' }, { value: 'REJECTED', label: '已退回' }, { value: 'ALL', label: '全部保单' }]
const labels = { PENDING_VERIFY: '待核验', VERIFIED: '已通过', REJECTED: '待学生补正', NOT_SUBMITTED: '未提交' }
const columns = [{ key: 'student', title: '学生', width: '180px' }, { key: 'enterpriseName', title: '实习企业' }, { key: 'insurerName', title: '承保单位' }, { key: 'period', title: '保障期限', width: '195px' }, { key: 'status', title: '核验状态', width: '110px' }, { key: 'actions', title: '办理', width: '110px' }]
const id = computed(() => String(route.params.insuranceId || ''))
const batchId = computed(() => String(route.query.batchId || ''))
const page = computed(() => { const value = Number(route.query.page); return Number.isSafeInteger(value) && value > 0 ? value : 1 })
const status = computed(() => statuses.some(s => s.value === route.query.status) ? route.query.status : 'PENDING_VERIFY')
const key = computed(() => JSON.stringify([id.value, batchId.value, page.value, status.value, route.query.keyword, props.ctx?.tenantId, props.ctx?.permissionPatterns]))
const rows = ref([]), detail = ref(null), total = ref(0), loading = ref(false), error = ref(''), keyword = ref('')
const file = ref(null), fileBusy = ref(false), fileError = ref('')
const reasonInput = ref('')
const action = ref(null), submitting = ref(false), actionError = ref(''), conflict = ref(false), receipt = ref('')
const canVerify = computed(() => Array.isArray(props.ctx?.permissionPatterns) && canCode(props.ctx, 'internship.insurance.verify'))
const canHandle = computed(() => canVerify.value && detail.value?.status === 'PENDING_VERIFY' && !loading.value)
const canContinue = computed(() => !loading.value && !error.value && detail.value?.status === 'VERIFIED' && !!detail.value?.internshipId && !!batchId.value && Array.isArray(props.ctx?.permissionPatterns) && canCode(props.ctx, 'internship.student.view'))
function openOnboard() {
  if (!canContinue.value) return
  return router.push({ path: `/admin/internship/students/${String(detail.value.internshipId)}`, query: { batchId: batchId.value, section: 'placement', returnTo: route.fullPath } })
}
const blockReason = computed(() => !canVerify.value ? '当前账号可查看材料，无核验权限。' : !detail.value?.fileId ? '尚无保单凭证，暂不能核验。' : !Number.isInteger(detail.value?.version) ? '核验信息不完整，请重新读取。' : '')
const approveBlockReason = computed(() => blockReason.value || (fileBusy.value ? '正在读取保单凭证，请稍候。' : fileError.value ? '保单凭证读取失败，请重试读取后再确认通过。' : !file.value || String(file.value.fileId) !== String(detail.value?.fileId) || !file.value.readyForBusiness || !(file.value.canPreview || file.value.canDownload) ? '保单凭证尚未安全可读，暂不能确认通过。' : ''))
const pagination = computed(() => ({ page: page.value, pageSize: 20, total: total.value }))
let alive = true, generation = 0
function message(e) { return normalizeUiError(e, { fallback: '操作未完成，请稍后重试' }).userMessage }
function label(value) { return labels[value] || '状态待确认' }
function navigate(record) {
  return router.push({ path: record ? `${BASE}/${record.id}` : BASE, query: { ...route.query } })
}
function filter(value = status.value) { return router.push({ path: BASE, query: { ...route.query, status: value, keyword: keyword.value.trim() || undefined, page: undefined } }) }
function changePage(value) { return router.push({ path: BASE, query: { ...route.query, page: value } }) }
async function loadFile(ticket, context) {
  file.value = null; fileError.value = ''
  if (!detail.value?.fileId) return
  fileBusy.value = true
  try {
    const result = await fileSdk.metadata(String(detail.value.fileId))
    if (alive && ticket === generation && context === key.value) file.value = result
  } catch (e) { if (alive && ticket === generation && context === key.value) fileError.value = message(e) }
  finally { if (alive && ticket === generation && context === key.value) fileBusy.value = false }
}
async function load({ keepAction = false } = {}) {
  const ticket = ++generation, context = key.value
  loading.value = true; error.value = ''; rows.value = []; total.value = 0; detail.value = null; file.value = null; fileError.value = ''; fileBusy.value = false
  if (!keepAction) { action.value = null; actionError.value = ''; conflict.value = false; receipt.value = '' }
  keyword.value = String(route.query.keyword || '')
  try {
    if (!batchId.value) throw new Error('请先选择实习批次。')
    const res = id.value ? await insuranceApi.getDetail(id.value, batchId.value) : await insuranceApi.getInsurances({ batchId: batchId.value, page: page.value, pageSize: 20, keyword: keyword.value, status: status.value === 'ALL' ? undefined : status.value })
    if (!alive || ticket !== generation || context !== key.value) return
    if (res.code !== 0) throw res
    if (id.value) {
      if (String(res.data?.id) !== id.value) throw new Error('未找到对应保险记录，请返回列表重新选择。')
      detail.value = res.data
      await loadFile(ticket, context)
    } else { rows.value = res.data.list; total.value = res.data.total }
  } catch (e) { if (alive && ticket === generation && context === key.value) error.value = message(e) }
  finally { if (alive && ticket === generation && context === key.value) loading.value = false }
}
function askAction(kind) {
  if (!canHandle.value || blockReason.value || submitting.value || !['APPROVE', 'REJECT'].includes(kind)) return
  if (kind === 'APPROVE' && approveBlockReason.value) return
  action.value = { kind, id: detail.value.id, version: detail.value.version, context: key.value, generation }
  actionError.value = ''; conflict.value = false
}
async function submitAction() {
  const pending = action.value
  if (!pending || submitting.value || conflict.value || !canHandle.value || pending.context !== key.value || pending.generation !== generation) return
  if (pending.kind === 'APPROVE' && approveBlockReason.value) { actionError.value = approveBlockReason.value; return }
  const reason = pending.kind === 'REJECT' ? reasonInput.value : ''
  if (pending.kind === 'REJECT' && reason.trim().length < 5) { actionError.value = '请填写至少 5 个字的具体修改意见。'; return }
  submitting.value = true
  try {
    const res = await insuranceApi.verify(pending.id, { action: pending.kind, comment: reason.trim(), expectedVersion: pending.version })
    if (!alive || pending.context !== key.value || pending.generation !== generation) return
    if (res.code !== 0) {
      actionError.value = message(res)
      conflict.value = Number(res.code) === 409 || Math.floor(Number(res.code) / 1000) === 409 || /已发生变化|仅待核验/.test(actionError.value)
      return
    }
    action.value = null
    reasonInput.value = ''
    receipt.value = pending.kind === 'APPROVE' ? '保险核验已通过。后续上岗仍需完成本批次其他必办项。' : '保险已退回，等待学生按修改意见补正并重新提交。'
    await load({ keepAction: true })
  } catch (e) { if (alive && pending.context === key.value && pending.generation === generation) actionError.value = message(e) }
  finally { submitting.value = false }
}
async function nextPending() {
  if (submitting.value || loading.value) return
  const context = key.value, ticket = generation
  loading.value = true
  try {
    const res = await insuranceApi.getInsurances({ batchId: batchId.value, status: 'PENDING_VERIFY', keyword: String(route.query.keyword || ''), page: 1, pageSize: 1 })
    if (!alive || context !== key.value || ticket !== generation) return
    if (res.code !== 0) throw res
    if (res.data.list.length) await navigate(res.data.list[0])
    else receipt.value = '当前批次、当前筛选条件下已无待核验保单。'
  } catch (e) { if (alive && context === key.value && ticket === generation) error.value = message(e) }
  finally { if (alive && context === key.value && ticket === generation) loading.value = false }
}
watch(key, () => { reasonInput.value = ''; load() }, { immediate: true })
onBeforeUnmount(() => { alive = false; generation++ })
</script>

<template>
  <ModulePageShell :title="id ? (detail ? `${detail.studentName} · 保险材料核对` : '保险材料核对') : '保险核验'" :subtitle="id ? '核对投保信息与原始凭证，确认后提交核验结论。' : '先核对保单，再确认保障；退回材料由学生补正后重交。'">
    <template #actions>
      <button v-if="id" class="iv-button" :disabled="submitting" @click="navigate()">返回核验列表</button>
      <button class="iv-button" :disabled="loading || submitting" @click="load()">刷新</button>
    </template>
    <div v-if="!id" class="iv-worklist">
      <div class="iv-toolbar">
        <div class="iv-tabs" role="tablist" aria-label="保险核验状态">
          <button v-for="item in statuses" :key="item.value" role="tab" :aria-selected="status === item.value" :class="{ active: status === item.value }" @click="filter(item.value)">{{ item.label }}</button>
        </div>
        <AppSearchBox v-model="keyword" placeholder="搜索姓名、学号或保单号" @search="filter()" />
      </div>
      <ErrorState v-if="error" :description="error" @retry="load()" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="iv-list-heading"><strong>{{ statuses.find(s => s.value === status)?.label }}</strong><span>{{ total }} 份保单</span></div>
        <DataTable v-if="rows.length" :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="changePage">
          <template #cell-student="{ row }"><strong>{{ row.studentName }}</strong><small class="iv-secondary">{{ row.studentNo }}</small></template>
          <template #cell-period="{ row }"><span>{{ row.effectiveDate || '未填写' }}</span><small class="iv-secondary">至 {{ row.expiryDate || '未填写' }}</small></template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ label(row.status) }}</AppStatusTag><small v-if="row.coverageReason" class="iv-secondary" :title="row.coverageReason">{{ row.canRenew ? '需更新保障' : row.coverageStatus === 'PENDING' ? '保障未生效' : row.coverageStatus === 'EXPIRED' ? '保障已到期' : '保障期限待核对' }}</small></template>
          <template #cell-actions="{ row }"><button class="iv-link" @click="navigate(row)">{{ row.status === 'PENDING_VERIFY' ? '核对材料' : '查看结果' }}</button></template>
        </DataTable>
        <div v-else class="iv-empty"><strong>{{ status === 'PENDING_VERIFY' ? '当前没有待核验保单' : '未找到符合条件的保单' }}</strong><p>{{ keyword ? '可调整搜索词或切换状态后重试。' : '这里展示当前批次、当前权限范围内已提交的保险材料。' }}</p><button v-if="page > 1" class="iv-button" @click="changePage(1)">回到第一页</button></div>
      </template>
    </div>
    <template v-else>
      <p v-if="receipt" class="iv-receipt" role="status">{{ receipt }}</p>
      <ErrorState v-if="error" :description="error" @retry="load()" @back="navigate()" />
      <LoadingState v-else-if="loading" />
      <div v-else-if="detail" class="iv-detail">
        <div class="iv-materials">
          <section class="iv-card">
            <header><h2>投保信息</h2><AppStatusTag :status="detail.status">{{ label(detail.status) }}</AppStatusTag></header>
            <p v-if="detail.coverageReason" class="iv-note" role="status">{{ detail.coverageReason }}{{ detail.canRenew ? '；学生可在保险页面更新保单并重新提交。' : '' }}</p>
            <dl class="iv-facts"><div><dt>学生</dt><dd>{{ detail.studentName }} <span>{{ detail.studentNo }}</span></dd></div><div><dt>实习企业</dt><dd>{{ detail.enterpriseName || '未填写' }}</dd></div><div><dt>承保单位</dt><dd>{{ detail.insurerName || '未填写' }}</dd></div><div><dt>险种</dt><dd>{{ detail.coverageType || '未填写' }}</dd></div><div class="iv-wide"><dt>保单号</dt><dd>{{ detail.policyNo || '未填写' }}</dd></div><div class="iv-wide"><dt>保障期限</dt><dd>{{ detail.effectiveDate || '未填写' }} <span>至</span> {{ detail.expiryDate || '未填写' }}</dd></div></dl>
          </section>
          <section class="iv-card"><header><h2>保单凭证</h2><span>核对姓名、险种与保障期限</span></header><div class="iv-card-body">
            <p v-if="fileBusy">正在读取保单凭证…</p>
            <p v-else-if="fileError" class="iv-error" role="alert">{{ fileError }} <button class="iv-link" @click="loadFile(generation, key)">重试读取凭证</button></p>
            <FilePreviewer v-else-if="file" :file="file" inline :provider="previewProvider" @error="fileError = message($event)" />
            <p v-else class="iv-note">该记录未附保单凭证。</p>
          </div></section>
        </div>
        <aside class="iv-card iv-review"><header><h2>{{ detail.status === 'PENDING_VERIFY' ? '提交核验结论' : '核验结果' }}</h2></header><div class="iv-card-body">
          <template v-if="detail.status === 'PENDING_VERIFY'"><p class="iv-note">请先查看原始凭证，确认与左侧信息一致，并覆盖实习期间。需要补正时，写清修改要求。</p><p v-if="approveBlockReason" class="iv-note" role="status">{{ approveBlockReason }}</p><div class="iv-review-actions"><button class="iv-button iv-primary" :disabled="!canHandle || !!approveBlockReason || submitting" @click="askAction('APPROVE')">核验通过</button><button class="iv-button" :disabled="!canHandle || !!blockReason || submitting" @click="askAction('REJECT')">退回补正</button></div></template>
          <template v-else><strong>{{ label(detail.status) }}</strong><p class="iv-note">{{ detail.status === 'REJECTED' ? '下一步：学生补正材料，重新提交核验。' : detail.status === 'VERIFIED' ? '本项核验已完成，可继续检查其他上岗条件。' : '请返回列表查看可办理记录。' }}</p><dl class="iv-result"><dt>核验人</dt><dd>{{ detail.verifiedByName || '暂无记录' }}</dd><dt>核验意见</dt><dd>{{ detail.verifyComment || '未填写意见' }}</dd></dl><div class="iv-review-actions"><button v-if="canContinue" class="iv-button iv-primary" @click="openOnboard">查看该生上岗条件</button><button class="iv-button" :class="{ 'iv-primary': !canContinue }" @click="nextPending">继续核验下一份</button></div></template>
        </div></aside>
      </div>
    </template>
    <AppConfirmDialog :visible="!!action" :title="action?.kind === 'APPROVE' ? '确认保险核验通过' : '退回保险材料补正'" :content="detail ? `本次处理：${detail.studentName}的保险材料` : ''"  :confirm-text="action?.kind === 'APPROVE' ? '确认通过' : '确认退回'" :submitting="submitting" :confirm-disabled="conflict" @update:visible="!$event && !submitting && (action = null)" @confirm="submitAction">
      <label v-if="action?.kind === 'REJECT'" class="iv-reason">修改意见（必填）<textarea v-model="reasonInput" aria-label="修改意见" rows="4" placeholder="写清需要补充或更正的材料，不少于 5 个字" :disabled="submitting" /></label>
      <p v-if="actionError" class="iv-error" role="alert">{{ actionError }}</p><p v-if="conflict" class="iv-note">意见已保留。请先关闭确认框、重新读取材料，再核对后提交。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<style scoped>
.iv-reason{display:grid;gap:10px;font-size:13px}.iv-reason textarea{font:inherit;border:1px solid #cbd7e8;border-radius:6px;padding:12px;resize:vertical;width:100%;box-sizing:border-box}
.iv-worklist,.iv-card{background:var(--bg-card,#fff);border:1px solid var(--border-base,#e1e7f0);border-radius:12px;overflow:hidden}
.iv-toolbar{display:flex;justify-content:space-between;gap:20px;padding:16px 20px;border-bottom:1px solid var(--border-base,#e1e7f0);flex-wrap:wrap}
.iv-tabs{display:flex;gap:22px;align-items:center}.iv-tabs button{border:0;background:none;padding:10px 0;color:var(--text-secondary,#65748b);cursor:pointer;font:inherit;border-bottom:2px solid transparent}.iv-tabs button.active{border-color:#2863bc;color:#235bb1;font-weight:600}
.iv-list-heading{display:flex;gap:10px;padding:18px 20px 12px;align-items:center}.iv-list-heading span,.iv-secondary,.iv-note,.iv-card header>span{color:var(--text-secondary,#65748b);font-size:13px}.iv-secondary{display:block;margin-top:5px}
.iv-button{font:inherit;font-size:13px;background:#fff;border:1px solid #d7e0ed;border-radius:7px;min-height:36px;padding:8px 14px;color:#304565;cursor:pointer}.iv-button:disabled{opacity:.5;cursor:not-allowed}.iv-primary{background:#285eb5;color:white;border-color:#285eb5}.iv-link{border:0;background:none;color:#235bb1;font:inherit;font-size:13px;cursor:pointer;padding:6px 0}
.iv-empty{padding:64px 24px;text-align:center;color:#364963}.iv-empty p{color:#718097;font-size:13px}.iv-detail{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;align-items:start}.iv-review{position:sticky;top:16px}.iv-materials{display:grid;gap:20px}.iv-card header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:18px 22px;border-bottom:1px solid #e9eef5}.iv-card h2{font-size:15px;margin:0;color:#283e5b}.iv-card-body{padding:20px 22px}.iv-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin:0;padding:24px}.iv-facts dt,.iv-result dt{font-size:12px;color:#748197;margin-bottom:8px}.iv-facts dd,.iv-result dd{margin:0;font-size:14px;color:#263e5c;overflow-wrap:anywhere}.iv-facts dd span{font-size:12px;color:#748197;margin:0 8px}.iv-wide{grid-column:1/-1}.iv-note{line-height:1.8;margin-top:0}.iv-review-actions{display:grid;gap:10px;margin-top:20px}.iv-result{margin:24px 0}.iv-result dd{margin-bottom:18px;white-space:pre-wrap}.iv-error{color:#b53b35;font-size:13px;line-height:1.7}.iv-receipt{margin:0;padding:14px 20px;border:1px solid #bddfcd;background:#f2fbf6;border-radius:9px;color:#256546;font-size:14px}
@media(max-width:1100px){.iv-detail{grid-template-columns:1fr}.iv-review-actions{grid-template-columns:1fr 1fr}}@media(max-width:600px){.iv-facts{grid-template-columns:1fr}.iv-toolbar{padding:12px}.iv-tabs{gap:14px}.iv-card header{flex-wrap:wrap}}
</style>
