<template>
  <section class="renewal-workspace" aria-label="模块续费治理工作区">
    <header class="renewal-head">
      <div>
        <span class="eyebrow">RENEWAL GOVERNANCE</span>
        <h3>到期来源、客户成功跟进与续费办理</h3>
        <p>只读取当前代次最晚的已付来源。创建跟进复用现有 RenewalTask；真正续费订单仍回到原“分项订购与续费”工作区办理。</p>
      </div>
      <div class="head-actions">
        <label>观察窗口
          <select v-model.number="withinDays" :disabled="loading" @change="loadCandidates(1)">
            <option :value="30">30 天</option><option :value="60">60 天</option><option :value="90">90 天</option>
            <option :value="120">120 天</option><option :value="365">365 天</option>
          </select>
        </label>
        <button :disabled="loading || !tenantId" @click="loadCandidates(page)">刷新续费事实</button>
      </div>
    </header>

    <div v-if="!tenantId" class="empty">先在上方销售工作区选择学校。</div>
    <template v-else>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="notice" class="success" role="status">{{ notice }}</p>
      <div class="summary">
        <article><strong>{{ total }}</strong><span>窗口内续费边界</span></article>
        <article><strong>{{ followupCount }}</strong><span>已进入客户成功</span></article>
        <article :class="{ warn: blockerCount }"><strong>{{ blockerCount }}</strong><span>当前有阻断</span></article>
      </div>

      <div class="table-scroll">
        <table>
          <thead><tr><th>模块 / 来源</th><th>已付截止</th><th>客户成功任务</th><th>办理结论</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in items" :key="row.sourceId">
              <td><strong>{{ row.moduleLabel }}</strong><small>generation {{ row.moduleGeneration }} · 来源 #{{ row.sourceId }}</small><small>{{ sourceStatus(row.sourceStatus) }} · {{ row.orderNo }}</small></td>
              <td><strong :class="row.overdue ? 'bad-text' : ''">{{ showTime(row.sourceEndsAt) }}</strong><small>{{ daysText(row) }}</small></td>
              <td v-if="row.renewalTask"><strong>#{{ row.renewalTask.taskId }} · {{ taskStatus(row.renewalTask.status) }}</strong><small>截止 {{ showTime(row.renewalTask.dueAt) }} · v{{ row.renewalTask.version }}</small><small>{{ row.renewalTask.ownerName || '负责人未登记' }}</small></td>
              <td v-else>尚未创建续费跟进</td>
              <td><span v-if="row.blocker" class="blocker">{{ row.blocker.message }}</span><span v-else-if="row.canStartRenewalOrder" class="ok-text">跟进已建立，可进入正式续费录单</span><span v-else class="muted">等待客户成功建立跟进</span></td>
              <td class="ops">
                <button v-if="row.canCreateFollowup && canCustomerSuccess" :disabled="saving || locked" @click="selectFollowup(row)">创建续费跟进</button>
                <router-link v-if="row.renewalTask" to="/admin/platform/customer-success">处理 RenewalTask</router-link>
                <button v-if="row.canStartRenewalOrder && canOrder" class="primary" :disabled="locked" @click="focusSales(row)">定位原分项续费</button>
              </td>
            </tr>
            <tr v-if="!items.length && !loading"><td colspan="5">当前观察窗口内没有可续费的已付来源。</td></tr>
          </tbody>
        </table>
      </div>
      <div class="pager"><button :disabled="loading || page === 1" @click="loadCandidates(page - 1)">上一页</button><span>第 {{ page }} 页 · 共 {{ total }} 条</span><button :disabled="loading || page * 20 >= total" @click="loadCandidates(page + 1)">下一页</button></div>

      <section v-if="selected" class="followup-form">
        <div class="form-title"><div><span class="eyebrow">CUSTOMER SUCCESS HANDOFF</span><h4>{{ selected.moduleLabel }} · 创建现有续费跟进任务</h4><p>不会自动创建续费订单，不会扣款，也不会改变当前模块授权。</p></div><button @click="cancelFollowup">取消</button></div>
        <fieldset :disabled="saving || locked || !canCustomerSuccess">
          <div class="form-grid">
            <label>跟进截止时间<input v-model="form.dueAt" type="datetime-local" step="1"></label>
            <label>跟进负责人<input v-model.trim="form.ownerName" maxlength="100" placeholder="填写真实负责人"></label>
          </div>
          <label>跟进说明<textarea v-model.trim="form.note" minlength="5" maxlength="900" placeholder="说明续费沟通、报价、合同确认等下一步，至少5字符"></textarea></label>
          <div class="handoff-note">已付服务截止：{{ showTime(selected.sourceEndsAt) }}。续费订单开始时间应从此边界衔接；新商品版本、成交价和新的服务截止必须在销售工作区重新明确确认。</div>
          <button class="primary" :disabled="!followupReady" @click="submitFollowup">{{ saving ? '正在创建…' : '创建 RenewalTask 并关联此来源' }}</button>
        </fieldset>
      </section>

      <p v-if="!canCustomerSuccess && !canOrder" class="notice">当前平台主管职责只能查看续费候选，没有客户成功或订单办理权限。</p>
      <p v-else-if="canCustomerSuccess && !canOrder" class="notice">你可以创建和处理客户成功续费任务；正式 RENEW 订单仍需由具备 order.manage 的人员在原销售工作区办理。</p>
      <p v-else-if="canOrder && !canCustomerSuccess" class="notice">你可以办理正式 RENEW 订单，但不能绕过客户成功直接生成跟进任务；先等待客户成功完成来源交接。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { moduleCommerceApi as api } from '@/modules/platform/api/moduleCommerce.api'
import { ensurePlatformAccessContext } from '@/security/platformAccessGate'

const props = defineProps({ tenantId: { type: String, default: '' }, locked: Boolean })
const emit = defineEmits(['focus-sales'])
const access = ref(null), items = ref([]), page = ref(1), total = ref(0), withinDays = ref(120)
const loading = ref(false), saving = ref(false), error = ref(''), notice = ref(''), selected = ref(null)
const blankForm = () => ({ dueAt: '', ownerName: '', note: '' })
const form = ref(blankForm())
let requestSeq = 0
const canCustomerSuccess = computed(() => !!access.value?.duties?.some(d => ['*', 'customerSuccess.manage'].includes(d)))
const canOrder = computed(() => !!access.value?.duties?.some(d => ['*', 'order.manage'].includes(d)))
const blockerCount = computed(() => items.value.filter(row => row.blocker).length)
const followupCount = computed(() => items.value.filter(row => row.renewalTask).length)
const followupReady = computed(() => canCustomerSuccess.value && !saving.value && !props.locked && !!selected.value && !!form.value.dueAt && form.value.note.length >= 5)

function showTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN', { hour12: false }) : String(value)
}
function daysText(row) {
  if (row.overdue) return `已超过服务截止 ${Math.abs(Number(row.daysUntilEnd || 0))} 天`
  if (Number(row.daysUntilEnd) === 0) return '今天到期'
  return `距服务截止 ${row.daysUntilEnd} 天`
}
function sourceStatus(value) { return ({ ACTIVE: '生效中', SCHEDULED: '待生效', CANCEL_SCHEDULED: '期末停续' })[value] || value || '—' }
function taskStatus(value) { return ({ PENDING: '待联系', CONTACTED: '已联系', COMMITTED: '已承诺', RENEWED: '已续费', CHURNED: '流失' })[value] || value || '—' }
function cancelFollowup() { selected.value = null; form.value = blankForm() }
function selectFollowup(row) { selected.value = row; form.value = blankForm(); notice.value = ''; error.value = '' }
async function recheckDuty(duty) {
  const current = await ensurePlatformAccessContext({ force: true })
  if (!current || String(current.subjectId) !== String(access.value?.subjectId) || !current.duties?.some(value => ['*', duty].includes(value))) {
    throw new Error(`平台身份或职责已变化，缺少 ${duty}，写操作已停止`)
  }
}
async function loadCandidates(targetPage = 1) {
  if (!props.tenantId) { items.value = []; total.value = 0; return }
  const seq = ++requestSeq; loading.value = true; error.value = ''
  try {
    const data = await api.listRenewalCandidates(props.tenantId, { withinDays: withinDays.value, page: targetPage, pageSize: 20 })
    if (seq !== requestSeq) return
    items.value = data.items || []; total.value = Number(data.total || 0); page.value = targetPage
  } catch (e) { if (seq === requestSeq) { items.value = []; total.value = 0; error.value = e.message || '读取续费候选失败' } }
  finally { if (seq === requestSeq) loading.value = false }
}
async function submitFollowup() {
  if (!followupReady.value) return
  saving.value = true; error.value = ''; notice.value = ''
  try {
    await recheckDuty('customerSuccess.manage')
    const date = new Date(form.value.dueAt)
    if (!Number.isFinite(date.getTime())) throw new Error('跟进截止时间无效')
    const sourceId = selected.value.sourceId
    const result = await api.createRenewalFollowup(props.tenantId, sourceId, {
      dueAt: date.toISOString(), ownerName: form.value.ownerName, note: form.value.note
    })
    notice.value = result?.replayed ? `已找回原 RenewalTask #${result.renewalTask?.taskId || '—'}，没有重复建任务` : `RenewalTask #${result?.renewalTask?.taskId || '—'} 已创建并关联已付来源`
    cancelFollowup(); await loadCandidates(page.value)
  } catch (e) { error.value = e.message || '续费跟进创建失败，请刷新后核对原任务' }
  finally { saving.value = false }
}
async function focusSales(row) {
  try {
    await recheckDuty('order.manage')
    emit('focus-sales', row)
  } catch (e) { error.value = e.message || '当前不能进入续费录单' }
}
watch(() => props.tenantId, () => { requestSeq++; cancelFollowup(); items.value = []; total.value = 0; page.value = 1; error.value = ''; notice.value = ''; if (props.tenantId) loadCandidates(1) })
onMounted(async () => { access.value = await ensurePlatformAccessContext({ force: true }); if (!access.value) error.value = '平台主管职责核验失败'; if (props.tenantId) await loadCandidates(1) })
</script>

<style scoped>
.renewal-workspace{background:#fff;border:1px solid #dce5f0;border-radius:16px;padding:24px;color:#21354e;display:grid;gap:16px}.renewal-head,.head-actions,.form-title,.pager{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}.renewal-head h3,.form-title h4{margin:5px 0}.renewal-head p,.form-title p{margin:4px 0;color:#63748a;font-size:13px;line-height:1.6}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.4px;color:#3b67a8}.head-actions{align-items:end}.head-actions label,label{display:grid;gap:6px;font-size:12px;color:#53647d}input,select,textarea{border:1px solid #ccd8e8;border-radius:7px;padding:8px 10px;font:inherit;color:#223750;background:#fff}textarea{min-height:86px;resize:vertical}button{min-height:36px;border:1px solid #ccd8e8;border-radius:7px;background:#fff;color:#355274;padding:8px 12px;cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}.primary{background:#2563eb;color:#fff;border-color:#2563eb}.summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.summary article{padding:12px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc}.summary article.warn{background:#fff8eb;border-color:#fedf89}.summary strong,.summary span{display:block}.summary strong{font-size:22px}.summary span{margin-top:3px;font-size:11px;color:#6b7c92}.table-scroll{overflow:auto;border:1px solid #e2e8f0;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:12px;min-width:960px}th,td{padding:11px;border-bottom:1px solid #e8edf4;text-align:left;vertical-align:top}th{background:#f4f7fb;color:#60758f}td small{display:block;color:#7a8b9e;margin-top:4px}.ops{display:flex;gap:7px;align-items:flex-start;flex-wrap:wrap}.blocker{color:#b54708;line-height:1.55}.ok-text{color:#067647}.bad-text{color:#b42318}.muted{color:#7a8b9e}.followup-form{border:1px solid #bfd2ee;background:#f8fbff;border-radius:12px;padding:18px;display:grid;gap:12px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.handoff-note,.notice,.success,.error,.empty{padding:11px 13px;border-radius:8px;font-size:13px;line-height:1.6}.handoff-note,.notice{background:#fff7e8;color:#865e1c}.success{background:#edf9f2;color:#246546}.error{background:#fff0f0;color:#a93d3d}.empty{background:#f4f7fb;color:#697b94}.pager{justify-content:flex-start;align-items:center;font-size:12px;color:#697b94}a{color:#245fb6}@media(max-width:760px){.renewal-workspace{padding:16px}.summary,.form-grid{grid-template-columns:1fr}.renewal-head{display:grid}}
</style>
