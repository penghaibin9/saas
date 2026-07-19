<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
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
          <div class="sp-panel__head">报到信息</div>
          <dl class="desc">
            <div><dt>录取通知号</dt><dd>{{ my.admissionNo || '—' }}</dd></div>
            <div><dt>姓名</dt><dd>{{ my.name || studentName }}</dd></div>
            <div><dt>班级</dt><dd>{{ my.className || '—' }}</dd></div>
            <div><dt>年级</dt><dd>{{ my.grade || '—' }}</dd></div>
            <div><dt>宿舍楼</dt><dd>{{ my.building || '—' }}</dd></div>
            <div><dt>房间/床位</dt><dd>{{ my.room || '—' }}</dd></div>
            <div><dt>缴费状态</dt><dd><StatusTag :text="payText(my.paymentStatus)" :tone="my.paymentStatus==='PAID'?'success':'warn'" /></dd></div>
            <div><dt>材料状态</dt><dd><StatusTag :text="matText(my.materialStatus)" :tone="my.materialStatus==='APPROVED'?'success':'warn'" /></dd></div>
            <div><dt>绿色通道</dt><dd><StatusTag :text="gcText(my.greenChannelStatus)" :tone="my.greenChannelStatus==='APPROVED'?'success':my.greenChannelStatus==='NOT_APPLIED'?'default':'warn'" /></dd></div>
          </dl>
        </section>
      </template>

      <!-- 信息采集 -->
      <template v-else-if="tab === 'collect'">
        <section class="sp-card" style="max-width:640px">
          <div class="sp-panel__head">预报到信息采集 <StatusTag text="可更新" tone="primary" /></div>
          <div class="two">
            <div><div class="sp-fieldlabel">常用手机号</div><input v-model.trim="collectForm.phone" class="sp-inp" placeholder="手机号" /></div>
            <div><div class="sp-fieldlabel">紧急联系人</div><input v-model.trim="collectForm.emergencyContact" class="sp-inp" placeholder="联系人姓名" /></div>
            <div><div class="sp-fieldlabel">紧急联系电话</div><input v-model.trim="collectForm.emergencyPhone" class="sp-inp" placeholder="联系电话" /></div>
            <div><div class="sp-fieldlabel">预计到校方式</div><input v-model.trim="collectForm.arriveWay" class="sp-inp" placeholder="如：高铁 / 自驾" /></div>
          </div>
          <button class="sp-btn" style="margin-top:16px" :disabled="busy" @click="submitCollect">提交采集</button>
        </section>
      </template>

      <!-- 绿色通道 -->
      <template v-else-if="tab === 'green'">
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

      <!-- 离校 -->
      <template v-else-if="tab === 'departure'">
        <section class="sp-card">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
            <div><div style="font-size:16px;font-weight:600">毕业离校手续</div><div class="sp-muted" style="margin-top:6px">全部环节办理完成后，可打印《离校证明》</div></div>
          </div>
        </section>
        <section class="sp-card">
          <StateBlock type="empty" text="离校清单待学校启用后开放" />
          <div class="notebox">离校环节由学校在毕业季统一开启；开启后此处显示图书馆 / 宿舍 / 财务 / 教务 / 团组织 / 就业等各环节办理状态与打印入口。</div>
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import { portalApi } from '../../services/portalApi'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const tabs = [
  { key: 'overview', label: '我的迎新' }, { key: 'collect', label: '信息采集' },
  { key: 'green', label: '绿色通道' }, { key: 'departure', label: '离校' }
]
const tab = ref('overview')
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const collectForm = reactive({ phone: '', emergencyContact: '', emergencyPhone: '', arriveWay: '' })
const greenForm = reactive({ type: 'POVERTY', reason: '' })

const studentName = computed(() => session.user?.realName || '同学')
const STEP_LABELS = { INFO: '信息采集', CHECKIN: '到校报到', CONFIRM: '注册确认', PAYMENT: '缴费', MATERIAL: '材料审核', DORM: '宿舍入住', ACTIVATE: '一卡通激活' }
const PAY = { PAID: '已缴费', UNPAID: '待缴费', PARTIAL: '部分缴费', WAIVED: '已减免' }
const MAT = { APPROVED: '已通过', PENDING: '待审核', REJECTED: '已退回', NONE: '未提交' }
const GC = { NOT_APPLIED: '未申请', PENDING: '审核中', APPROVED: '已通过', REJECTED: '已退回' }
function stepLabel(k) { return STEP_LABELS[k] || k || '' }
function payText(s) { return PAY[s] || s || '—' }
function matText(s) { return MAT[s] || s || '—' }
function gcText(s) { return GC[s] || s || '—' }

const flowSteps = computed(() => (my.value.steps || []).map((s) => ({ name: stepLabel(s.key), state: s.status === 'DONE' ? 'done' : s.status === 'BLOCKED' ? 'todo' : 'current' })))
const allDone = computed(() => (my.value.steps || []).length > 0 && (my.value.steps || []).every((s) => s.status === 'DONE'))

async function load() {
  loading.value = true; error.value = ''
  try { my.value = await portalApi.orientationMy() || {} }
  catch (e) { error.value = e?.message || '报到信息加载失败' } finally { loading.value = false }
}
async function submitCollect() {
  busy.value = true
  try { await portalApi.orientationCollect({ ...collectForm }); ui.notify('信息已采集'); load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitGreen() {
  busy.value = true
  try { await portalApi.orientationGreenChannel({ applyType: greenForm.type, reason: greenForm.reason }); ui.notify('绿色通道申请已提交'); tab.value = 'overview'; load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.desc { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px 24px; margin: 0; }
.desc dt { font-size: 12px; color: var(--t3); margin-bottom: 5px; }
.desc dd { margin: 0; font-size: 14px; color: var(--t1); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.notebox { margin-top: 14px; padding: 12px 16px; background: var(--warn-bg); border: 1px solid #FBE3B8; border-radius: 10px; font-size: 12.5px; color: #8A5300; line-height: 1.6; }
@media (max-width: 900px) { .desc { grid-template-columns: 1fr 1fr; } .two { grid-template-columns: 1fr; } }
</style>
