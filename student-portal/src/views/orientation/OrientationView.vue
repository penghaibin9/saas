<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="router.push(t.path)">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="正在加载报到信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 我的迎新 -->
      <template v-if="tab === 'overview'">
        <section v-if="my.blockedReason" class="sp-notice">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D92D20" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" style="flex:none"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
          <div><strong style="color:#B42318">有环节受阻</strong><p class="sp-muted" style="margin:5px 0 0">{{ stepLabel(my.blockedStep) }}：{{ my.blockedReason }}</p></div>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">报到进度 <StatusTag :text="allDone ? '已完成' : '进行中'" :tone="allDone ? 'success' : 'warn'" /></div>
          <FlowSteps :steps="flowSteps" />
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">报到资格 <StatusTag :text="qualificationText" :tone="qualificationTone" /></div>
          <p class="sp-muted">资格由学校服务器按当前正式材料、缴费/绿色通道、住宿和异常事实统一计算。</p>
          <ul v-if="my.qualification?.blockers?.length" class="qualification-blockers">
            <li v-for="item in my.qualification.blockers" :key="`${item.code}-${item.step}`">{{ item.message }}</li>
          </ul>
        </section>
        <section class="sp-card checkin-card">
          <div>
            <div class="sp-panel__head">一次性现场报到凭证 <StatusTag :text="credentialStatusText" :tone="my.checkinCredential?.canIssue ? 'success' : 'default'" /></div>
            <p class="sp-muted">凭证含学校、迎新批次、本人迎新记录、随机数、有效期和服务器签名；录取编号不能代替本凭证。</p>
            <p v-if="checkinToken.expiresAt" class="credential-expiry">有效至 {{ checkinToken.expiresAt.replace('T', ' ').slice(0, 19) }}</p>
            <button class="sp-btn" :disabled="busy || !my.checkinCredential?.canIssue" @click="issueCheckinToken">
              {{ checkinToken.token ? '刷新一次性凭证' : '签发一次性凭证' }}
            </button>
          </div>
          <div v-if="checkinToken.qrDataUrl" class="credential-qr">
            <img :src="checkinToken.qrDataUrl" alt="一次性现场报到二维码" />
            <small>仅供现场教师扫码，过期或使用后立即失效</small>
          </div>
          <div v-else-if="checkinToken.token" class="credential-fallback">
            <strong>二维码组件暂不可用</strong>
            <small>请向现场教师出示本页，不要使用录取编号替代。</small>
          </div>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">报到信息</div>
          <dl class="desc">
            <div><dt>录取通知号</dt><dd>{{ my.admissionNo || '—' }}</dd></div>
            <div><dt>姓名</dt><dd>{{ my.name || studentName }}</dd></div>
            <div><dt>班级</dt><dd>{{ my.className || '—' }}</dd></div>
            <div><dt>年级</dt><dd>{{ my.grade || '—' }}</dd></div>
            <div><dt>宿舍楼</dt><dd>{{ my.building || '—' }}</dd></div>
            <div><dt>房间/床位</dt><dd>{{ my.room || '—' }}</dd></div>
            <div><dt>缴费状态</dt><dd><StatusTag :text="payText(my.paymentStatus)" :tone="my.paymentStatus==='PAID'?'success':'warn'" /></dd></div>
            <div><dt>应缴金额</dt><dd>¥{{ my.payment?.payableAmount || '0.00' }}</dd></div>
            <div><dt>已缴金额</dt><dd>¥{{ my.payment?.paidAmount || '0.00' }}</dd></div>
            <div><dt>材料状态</dt><dd><StatusTag :text="matText(my.materialStatus)" :tone="my.materialStatus==='APPROVED'?'success':'warn'" /></dd></div>
            <div><dt>绿色通道</dt><dd><StatusTag :text="gcText(my.greenChannelStatus)" :tone="my.greenChannelStatus==='APPROVED'?'success':my.greenChannelStatus==='NOT_APPLIED'?'default':'warn'" /></dd></div>
          </dl>
        </section>
      </template>

      <section v-if="my.hasData && my.selfService && !my.selfService.available" class="sp-notice">
        <div><strong>预报到暂不可办理</strong><p class="sp-muted" style="margin:5px 0 0">{{ my.selfService.reason }}</p></div>
      </section>

      <!-- 信息采集 -->
      <template v-if="tab === 'info'">
        <section class="sp-card" style="max-width:640px">
          <div class="sp-panel__head">预报到信息采集 <StatusTag :text="selfService.information?.complete ? '已填写' : '待填写'" :tone="selfService.information?.complete ? 'success' : 'warn'" /></div>
          <div class="two">
            <div><div class="sp-fieldlabel">常用手机号</div><input v-model.trim="collectForm.phone" class="sp-inp" :placeholder="selfService.information?.phoneMasked || '手机号'" /></div>
            <div><div class="sp-fieldlabel">生源地</div><input v-model.trim="collectForm.origin" class="sp-inp" placeholder="省 / 市 / 区县" /></div>
            <div><div class="sp-fieldlabel">紧急联系人</div><input v-model.trim="collectForm.emergencyContactName" class="sp-inp" placeholder="联系人姓名" /></div>
            <div><div class="sp-fieldlabel">紧急联系电话</div><input v-model.trim="collectForm.emergencyPhone" class="sp-inp" placeholder="联系电话" /></div>
          </div>
          <label class="confirm"><input v-model="collectForm.confirmed" type="checkbox" /> 我确认以上信息真实有效，并同意学校用于迎新联络。</label>
          <button class="sp-btn" style="margin-top:16px" :disabled="busy || !selfService.available" @click="submitCollect">保存信息</button>
        </section>
      </template>

      <!-- 到校计划 -->
      <template v-if="tab === 'arrival'">
        <section class="sp-card" style="max-width:720px">
          <div class="sp-panel__head">到校计划 <StatusTag :text="selfService.arrivalPlan ? '已提交' : '待提交'" :tone="selfService.arrivalPlan ? 'success' : 'warn'" /></div>
          <p class="sp-muted">计划到校时间须在本批次报到窗口内；修改时使用当前版本，避免覆盖其他终端刚保存的内容。</p>
          <div class="two">
            <div><div class="sp-fieldlabel">到校方式</div><select v-model="arrivalForm.arrivalMode" class="sp-inp"><option value="TRAIN">高铁/火车</option><option value="AIR">飞机</option><option value="COACH">长途客车</option><option value="SELF_DRIVE">自驾</option><option value="CITY_TRANSIT">市内公共交通</option><option value="OTHER">其他</option></select></div>
            <div><div class="sp-fieldlabel">计划到校日期</div><AppDatePicker v-model="arrivalForm.plannedArrivalDate" class="sp-inp" label="计划到校日期" /></div>
            <div><div class="sp-fieldlabel">计划到校时间</div><input v-model="arrivalForm.plannedArrivalTime" type="time" class="sp-inp" aria-label="计划到校时间" /></div>
            <div><div class="sp-fieldlabel">站点/航站楼</div><input v-model.trim="arrivalForm.stationName" class="sp-inp" placeholder="申请接站时必填" /></div>
            <div><div class="sp-fieldlabel">车次/航班号</div><input v-model.trim="arrivalForm.transportNo" class="sp-inp" placeholder="选填" /></div>
            <div><div class="sp-fieldlabel">随行人数</div><input v-model.number="arrivalForm.companionCount" type="number" min="0" max="20" class="sp-inp" /></div>
            <label class="confirm compact"><input v-model="arrivalForm.pickupRequired" type="checkbox" /> 申请学校接站</label>
          </div>
          <button class="sp-btn" style="margin-top:16px" :disabled="busy || !selfService.available" @click="submitArrival">保存到校计划</button>
        </section>
      </template>

      <!-- 材料 -->
      <template v-if="tab === 'materials'">
        <section class="sp-card" style="max-width:760px">
          <div class="sp-panel__head">预报到材料 <StatusTag :text="matText(my.materialStatus)" :tone="my.materialStatus==='APPROVED'?'success':'warn'" /></div>
          <p class="sp-muted">上传先进入私有安全扫描；提交成功后形成不可覆盖的文件版本。审核中或已通过的材料不可重复提交。</p>
          <div class="material-submit">
            <select v-model="materialForm.materialType" class="sp-inp">
              <option value="ID_CARD">身份证明</option><option value="ADMISSION_LETTER">录取通知书</option><option value="PHOTO">证件照</option><option value="ARCHIVE">纸质档案凭证</option>
            </select>
            <input type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.txt" @change="pickMaterial" />
            <button class="sp-btn" :disabled="busy || !materialFile || !selfService.available" @click="submitMaterial">上传并提交</button>
          </div>
          <div v-if="selfService.materials?.length" class="material-list">
            <div v-for="m in selfService.materials" :key="m.id" class="material-row">
              <div><strong>{{ materialLabel(m.materialType) }}</strong><div class="sp-muted">第 {{ m.submissionNo }} 版 · {{ m.fileName }}</div></div>
              <div><StatusTag :text="matText(m.status)" :tone="m.status==='APPROVED'?'success':m.status==='RETURNED'||m.status==='REJECTED'?'danger':'warn'" /><div v-if="m.returnReason" class="return-reason">{{ m.returnReason }}</div></div>
            </div>
          </div>
          <StateBlock v-else type="empty" text="尚未提交预报到材料" />
        </section>
      </template>

      <!-- 绿色通道 -->
      <template v-if="tab === 'green'">
        <section class="sp-card" style="max-width:640px">
          <div class="sp-panel__head">绿色通道 <StatusTag :text="gcText(my.greenChannelStatus)" :tone="my.greenChannelStatus==='APPROVED'?'success':'warn'" /></div>
          <p class="sp-muted" style="margin-bottom:14px">入学时家庭经济困难可暂缓缴纳学费，凭材料先行报到。</p>
          <div class="sp-fieldlabel">困难类型</div>
          <select v-model="greenForm.type" class="sp-inp" style="margin-bottom:12px">
            <option value="POVERTY">家庭经济困难</option><option value="DISASTER">突发灾害</option><option value="OTHER">其他</option>
          </select>
          <div class="sp-fieldlabel">情况说明</div>
          <textarea v-model.trim="greenForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明申请事由" />
          <button class="sp-btn" :disabled="busy || !greenForm.reason" @click="submitGreen">提交申请</button>
        </section>
      </template>

      <!-- 历史兼容入口：离校本身由独立 /departure Authority 页面承载。 -->
      <button v-if="false" type="button" @click="$router.push('/departure')">前往离校清单</button>

    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import AppDatePicker from '../../components/AppDatePicker.vue'
import { portalApi } from '../../services/portalApi'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const route = useRoute()
const router = useRouter()
const tabs = [
  { key: 'overview', label: '我的迎新', path: '/orientation' },
  { key: 'info', label: '信息采集', path: '/orientation/info' },
  { key: 'arrival', label: '到校计划', path: '/orientation/arrival' },
  { key: 'materials', label: '材料', path: '/orientation/materials' },
  { key: 'green', label: '绿色通道', path: '/orientation/green-channel' },
  { key: 'departure', label: '离校', path: '/departure' }
]
const tab = computed(() => ({
  '/orientation/info': 'info', '/orientation/arrival': 'arrival',
  '/orientation/materials': 'materials', '/orientation/green-channel': 'green'
}[route.path] || 'overview'))
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const collectForm = reactive({ phone: '', origin: '', emergencyContactName: '', emergencyPhone: '', confirmed: false })
const arrivalForm = reactive({ arrivalMode: 'TRAIN', plannedArrivalDate: '', plannedArrivalTime: '', stationName: '', transportNo: '', pickupRequired: false, companionCount: 0, expectedVersion: 0 })
const materialForm = reactive({ materialType: 'ID_CARD' })
const materialFile = ref(null)
const greenForm = reactive({ type: 'POVERTY', reason: '' })
const checkinToken = reactive({ token: '', qrDataUrl: '', expiresAt: '' })

const studentName = computed(() => session.user?.realName || '同学')
const STEP_LABELS = { INFO: '信息采集', CHECKIN: '到校报到', CONFIRM: '注册确认', PAYMENT: '缴费', MATERIAL: '材料审核', DORM: '宿舍入住', ACTIVATE: '一卡通激活' }
const PAY = { PAID: '已缴费', UNPAID: '待缴费', PARTIAL: '部分缴费', WAIVED: '已减免' }
const MAT = { APPROVED: '已通过', UPLOADED: '待审核', PENDING: '待审核', RETURNED: '已退回', REJECTED: '已驳回', NOT_UPLOADED: '未提交', NONE: '未提交' }
const GC = { NOT_APPLIED: '未申请', PENDING: '审核中', APPROVED: '已通过', REJECTED: '已退回' }
function stepLabel(k) { return STEP_LABELS[k] || k || '' }
function payText(s) { return PAY[s] || s || '—' }
function matText(s) { return MAT[s] || s || '—' }
function gcText(s) { return GC[s] || s || '—' }

const terminalStep = (status) => ['DONE', 'WAIVED', 'NOT_REQUIRED'].includes(status)
const flowSteps = computed(() => (my.value.steps || []).map((s) => ({ name: stepLabel(s.key), state: terminalStep(s.status) ? 'done' : s.status === 'BLOCKED' ? 'todo' : 'current' })))
const allDone = computed(() => (my.value.steps || []).length > 0 && (my.value.steps || []).every((s) => terminalStep(s.status)))
const qualificationText = computed(() => my.value.qualification?.verdictLabel || '资格待计算')
const qualificationTone = computed(() => ({ QUALIFIED: 'success', NOT_QUALIFIED: 'danger', MANUAL_REVIEW: 'warn' })[my.value.qualification?.verdict] || 'default')
const credentialStatusText = computed(() => ({
  BLOCKED: '暂不可签发', ELIGIBLE: '可签发', ISSUED: '已签发',
  CHECKED_IN: '已现场报到', FINALIZED: '学院已确认'
})[my.value.checkinCredential?.status] || '待核验')
const selfService = computed(() => my.value.selfService || { available: false, information: {}, arrivalPlan: null, materials: [] })
const MATERIALS = { ID_CARD: '身份证明', ADMISSION_LETTER: '录取通知书', PHOTO: '证件照', ARCHIVE: '纸质档案凭证' }
function materialLabel(k) { return MATERIALS[k] || k }

async function load() {
  loading.value = true; error.value = ''
  try {
    my.value = await portalApi.orientationMy() || {}
    const ss = my.value.selfService || {}
    collectForm.origin = ss.information?.origin || my.value.origin || ''
    collectForm.emergencyContactName = ss.information?.emergencyContactName || ''
    const arrival = ss.arrivalPlan
    if (arrival) {
      const value = String(arrival.plannedArrivalAt || '')
      Object.assign(arrivalForm, { ...arrival, plannedArrivalDate: value.slice(0, 10), plannedArrivalTime: value.slice(11, 16), expectedVersion: arrival.version })
    }
  }
  catch (e) { error.value = e?.message || '报到信息加载失败' } finally { loading.value = false }
}
async function submitCollect() {
  busy.value = true
  try { await portalApi.orientationCollect({ ...collectForm }); ui.notify('信息已保存'); await load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitArrival() {
  busy.value = true
  try {
    const { plannedArrivalDate, plannedArrivalTime, ...rest } = arrivalForm
    await portalApi.orientationArrival({ ...rest, plannedArrivalAt: `${plannedArrivalDate}T${plannedArrivalTime}:00` })
    ui.notify('到校计划已保存'); await load()
  }
  catch (e) { ui.notify(e?.message || '到校计划保存失败') } finally { busy.value = false }
}
function pickMaterial(event) { materialFile.value = event.target.files?.[0] || null }
function clientSubmissionId() { return globalThis.crypto.randomUUID() }
async function submitMaterial() {
  if (!materialFile.value) return
  busy.value = true
  try {
    const uploaded = await portalApi.uploadOrientationMaterial(materialFile.value)
    await portalApi.orientationMaterial({ materialType: materialForm.materialType, fileId: uploaded.fileId, clientSubmissionId: clientSubmissionId() })
    ui.notify('材料已提交'); materialFile.value = null; await load()
  } catch (e) { ui.notify(e?.message || '材料提交失败') } finally { busy.value = false }
}
async function submitGreen() {
  busy.value = true
  try { await portalApi.orientationGreenChannel({ applyType: greenForm.type, remark: greenForm.reason, clientRequestId: clientSubmissionId() }); ui.notify('绿色通道申请已提交'); await router.push('/orientation'); await load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function issueCheckinToken() {
  if (busy.value) return
  busy.value = true
  try {
    const data = await portalApi.orientationCheckinToken()
    Object.assign(checkinToken, data || {})
    ui.notify('一次性报到凭证已签发，请在有效期内使用')
    await load()
  } catch (e) {
    ui.notify(e?.message || '报到凭证签发失败')
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.desc { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px 24px; margin: 0; }
.desc dt { font-size: 12px; color: var(--t3); margin-bottom: 5px; }
.desc dd { margin: 0; font-size: 14px; color: var(--t1); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.confirm { display:flex; align-items:center; gap:8px; margin-top:14px; font-size:13px; color:var(--t2); }
.confirm.compact { align-self:end; min-height:40px; margin:0; }
.material-submit { display:grid; grid-template-columns:180px 1fr auto; align-items:center; gap:12px; margin:16px 0; }
.material-list { border-top:1px solid var(--line); }
.material-row { display:flex; justify-content:space-between; gap:20px; padding:14px 0; border-bottom:1px solid var(--line); }
.return-reason { max-width:280px; margin-top:6px; color:#B42318; font-size:12px; text-align:right; }
.qualification-blockers { margin:12px 0 0; padding-left:20px; color:#B42318; line-height:1.7; font-size:13px; }
.notebox { margin-top: 14px; padding: 12px 16px; background: var(--warn-bg); border: 1px solid #FBE3B8; border-radius: 10px; font-size: 12.5px; color: #8A5300; line-height: 1.6; }
.checkin-card { display:grid; grid-template-columns:minmax(0,1fr) 220px; align-items:center; gap:24px; }
.credential-qr { display:grid; justify-items:center; gap:8px; }
.credential-qr img { width:200px; height:200px; border:1px solid var(--line); border-radius:10px; background:#fff; }
.credential-qr small, .credential-fallback small { color:var(--t3); text-align:center; }
.credential-expiry { font-size:13px; color:#067647; }
.credential-fallback { display:grid; gap:8px; padding:18px; border:1px dashed var(--line); border-radius:10px; text-align:center; }
@media (max-width: 900px) { .desc { grid-template-columns: 1fr 1fr; } .two, .material-submit, .checkin-card { grid-template-columns: 1fr; } }
</style>
