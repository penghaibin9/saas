<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">迎新报到</p>
        <h1>我的报到</h1>
        <p class="sp-hero__sub">查看报到各环节进度、采集预报到信息、申请绿色通道、打印报到回执。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在加载报到信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="!my.hasData" class="sp-notice">
        <strong>暂无报到信息</strong>
        <p>{{ my.message || '你尚未进入迎新批次。' }}</p>
      </section>

      <section v-if="my.blockedReason" class="sp-notice">
        <strong>有环节受阻</strong>
        <p>{{ my.blockedStep ? stepLabel(my.blockedStep) + '：' : '' }}{{ my.blockedReason }}</p>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__head">报到进度</div>
        <ol class="sp-steps">
          <li v-for="s in steps" :key="s.key" :class="'is-' + toneOf(s.status)">
            <span class="sp-steps__dot">{{ toneOf(s.status) === 'success' ? '✓' : '○' }}</span>
            <span class="sp-steps__label">{{ stepLabel(s.key) }}</span>
            <StatusTag :text="stepStatusText(s.status)" :tone="toneOf(s.status)" />
          </li>
        </ol>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__head">报到信息</div>
        <dl class="sp-desc">
          <div><dt>录取通知号</dt><dd>{{ my.admissionNo || '—' }}</dd></div>
          <div><dt>姓名</dt><dd>{{ my.name || '—' }}</dd></div>
          <div><dt>班级</dt><dd>{{ my.className || '—' }}</dd></div>
          <div><dt>年级</dt><dd>{{ my.grade || '—' }}</dd></div>
          <div><dt>宿舍楼</dt><dd>{{ my.building || '—' }}</dd></div>
          <div><dt>房间/床位</dt><dd>{{ my.room || '—' }}</dd></div>
          <div><dt>缴费状态</dt><dd><StatusTag :text="payText(my.paymentStatus)" :tone="my.paymentStatus === 'PAID' ? 'success' : 'warn'" /></dd></div>
          <div><dt>材料状态</dt><dd><StatusTag :text="matText(my.materialStatus)" :tone="my.materialStatus === 'APPROVED' ? 'success' : 'warn'" /></dd></div>
          <div><dt>绿色通道</dt><dd><StatusTag :text="gcText(my.greenChannelStatus)" :tone="my.greenChannelStatus === 'APPROVED' ? 'success' : my.greenChannelStatus === 'NOT_APPLIED' ? 'default' : 'warn'" /></dd></div>
        </dl>
      </section>

      <section class="sp-actions">
        <button class="sp-btn" :disabled="busy" @click="open('collect')">预报到信息采集</button>
        <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="open('green')">申请绿色通道</button>
        <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printReceipt">打印报到回执</button>
      </section>

      <section v-if="panel === 'collect'" class="sp-panel">
        <div class="sp-panel__head">预报到信息采集</div>
        <div class="sp-form">
          <label>常用手机号<input v-model.trim="collectForm.phone" placeholder="手机号" /></label>
          <label>紧急联系人<input v-model.trim="collectForm.emergencyContact" placeholder="联系人姓名" /></label>
          <label>紧急联系电话<input v-model.trim="collectForm.emergencyPhone" placeholder="联系电话" /></label>
          <label>预计到校方式<input v-model.trim="collectForm.arriveWay" placeholder="如：高铁/自驾" /></label>
          <button class="sp-btn" :disabled="busy" @click="submitCollect">提交采集</button>
        </div>
      </section>

      <section v-if="panel === 'green'" class="sp-panel">
        <div class="sp-panel__head">绿色通道申请</div>
        <div class="sp-form">
          <label>困难类型
            <select v-model="greenForm.type">
              <option value="POVERTY">家庭经济困难</option>
              <option value="DISASTER">突发灾害</option>
              <option value="OTHER">其他</option>
            </select>
          </label>
          <label></label>
          <label class="sp-form__full">情况说明<textarea v-model.trim="greenForm.reason" placeholder="请说明申请事由" /></label>
          <button class="sp-btn" :disabled="busy || !greenForm.reason" @click="submitGreen">提交申请</button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const panel = ref('')
const collectForm = reactive({ phone: '', emergencyContact: '', emergencyPhone: '', arriveWay: '' })
const greenForm = reactive({ type: 'POVERTY', reason: '' })

const steps = ref([])
const STEP_LABELS = {
  INFO: '信息采集', CHECKIN: '到校报到', CONFIRM: '注册确认', PAYMENT: '缴费',
  MATERIAL: '材料审核', DORM: '宿舍入住', ACTIVATE: '一卡通激活',
  PREREG: '预报到', ARRIVE: '到校报到', REGISTER: '注册建籍', CARD: '一卡通'
}
const PAY_MAP = { PAID: '已缴费', UNPAID: '待缴费', PARTIAL: '部分缴费', WAIVED: '已减免' }
const MAT_MAP = { APPROVED: '已通过', PENDING: '待审核', REJECTED: '已退回', NONE: '未提交' }
const GC_MAP = { NOT_APPLIED: '未申请', PENDING: '审核中', APPROVED: '已通过', REJECTED: '已退回' }
function stepLabel(k) { return STEP_LABELS[k] || k }
function stepStatusText(s) { return ({ DONE: '已完成', PENDING: '待办', BLOCKED: '受阻', PROCESSING: '进行中' })[s] || s }
function toneOf(s) { return s === 'DONE' ? 'success' : s === 'BLOCKED' ? 'danger' : 'warn' }
function payText(s) { return PAY_MAP[s] || s || '—' }
function matText(s) { return MAT_MAP[s] || s || '—' }
function gcText(s) { return GC_MAP[s] || s || '—' }

function open(p) { panel.value = panel.value === p ? '' : p }

async function load() {
  loading.value = true
  error.value = ''
  try {
    my.value = await portalApi.orientationMy() || {}
    steps.value = my.value.steps || []
  } catch (e) { error.value = e?.message || '报到信息加载失败' }
  finally { loading.value = false }
}
async function submitCollect() {
  busy.value = true
  try { await portalApi.orientationCollect({ ...collectForm }); ui.notify('信息已采集'); panel.value = ''; load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitGreen() {
  busy.value = true
  try { await portalApi.orientationGreenChannel({ ...greenForm }); ui.notify('绿色通道申请已提交'); panel.value = ''; load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function printReceipt() {
  busy.value = true
  try { await portalApi.orientationPrint({}); ui.notify('已生成报到回执打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}

onMounted(load)
</script>

<style scoped>
.sp-steps { list-style: none; margin: 0; padding: 0; }
.sp-steps li { display: flex; align-items: center; gap: 12px; padding: 9px 0; border-bottom: 1px solid #f4f5f7; }
.sp-steps li:last-child { border-bottom: 0; }
.sp-steps__dot { width: 24px; height: 24px; line-height: 24px; text-align: center; border-radius: 50%; background: #f2f3f5; color: #86909c; font-size: 12px; }
.sp-steps li.is-success .sp-steps__dot { background: rgba(0,180,42,.12); color: #00a33a; }
.sp-steps li.is-danger .sp-steps__dot { background: #ffece8; color: #f53f3f; }
.sp-steps__label { flex: 1; font-size: 14px; color: #1d2129; }
</style>
