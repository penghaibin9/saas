<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">岗位实习</p>
        <h1>我的实习</h1>
        <p class="sp-hero__sub">查看实习进度、提交周报与月报总结、打印三方协议、申诉实习成绩。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在加载实习信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="!my.hasData" class="sp-notice">
        <strong>暂无实习记录</strong>
        <p>{{ my.message || '你尚未被纳入实习安排，建档后此处会显示企业、岗位与周月报待办。' }}</p>
      </section>

      <template v-else>
        <section class="sp-kpis">
          <div class="sp-kpi"><div class="sp-kpi__label">实习单位</div><div class="sp-kpi__value" style="font-size:16px">{{ my.enterpriseName || '—' }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">岗位</div><div class="sp-kpi__value" style="font-size:16px">{{ my.positionName || '—' }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">企业导师</div><div class="sp-kpi__value" style="font-size:16px">{{ my.advisorName || '待分配' }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">实习状态</div><div class="sp-kpi__value" style="font-size:16px"><StatusTag :text="statusText(my.status)" :tone="my.status === 'ONBOARD' ? 'success' : 'warn'" /></div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">风险等级</div><div class="sp-kpi__value" style="font-size:16px"><StatusTag :text="riskText(my.riskLevel)" :tone="my.riskLevel === 'HIGH' ? 'danger' : my.riskLevel === 'MID' ? 'warn' : 'success'" /></div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">累计打卡</div><div class="sp-kpi__value">{{ my.todayCheckin?.totalDays ?? 0 }}<small>天</small></div></div>
        </section>

        <section class="sp-actions">
          <button class="sp-btn" :disabled="busy" @click="open('weekly')">提交周报</button>
          <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="open('report')">提交月报/总结</button>
          <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printAgreement">打印三方协议</button>
          <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="open('appeal')">成绩申诉</button>
        </section>

        <section v-if="panel" class="sp-panel">
          <div class="sp-panel__head">{{ panelTitle }}</div>
          <div v-if="panel === 'weekly'" class="sp-form">
            <label>周次<input v-model.number="weeklyForm.week" type="number" min="1" placeholder="第几周" /></label>
            <label></label>
            <label class="sp-form__full">本周工作内容<textarea v-model.trim="weeklyForm.workContent" placeholder="本周主要完成的工作" /></label>
            <label class="sp-form__full">收获与体会<textarea v-model.trim="weeklyForm.harvestContent" placeholder="本周收获" /></label>
            <label class="sp-form__full">下周计划<textarea v-model.trim="weeklyForm.planContent" placeholder="下周安排" /></label>
            <button class="sp-btn" :disabled="busy || !weeklyForm.workContent" @click="submitWeekly">提交周报</button>
          </div>
          <div v-else-if="panel === 'report'" class="sp-form">
            <label class="sp-form__full">报告标题<input v-model.trim="reportForm.title" placeholder="如：实习月度总结" /></label>
            <label class="sp-form__full">正文（长文档）<textarea v-model.trim="reportForm.content" style="min-height:180px" placeholder="实习总结正文" /></label>
            <button class="sp-btn" :disabled="busy || !reportForm.content" @click="submitReport">提交长文档</button>
          </div>
          <div v-else-if="panel === 'appeal'" class="sp-form">
            <label class="sp-form__full">申诉理由<textarea v-model.trim="appealForm.reason" placeholder="请说明成绩申诉理由" /></label>
            <button class="sp-btn" :disabled="busy || !appealForm.reason" @click="submitAppeal">提交申诉</button>
          </div>
        </section>

        <section class="sp-panel">
          <div class="sp-panel__head">周报记录</div>
          <StateBlock v-if="!(my.weeklyReports || []).length" type="empty" text="暂无周报" />
          <div v-else class="sp-cardlist">
            <article v-for="w in my.weeklyReports" :key="w.week" class="sp-card">
              <div class="sp-card__head">
                <h3 class="sp-card__title">第 {{ w.week }} 周周报</h3>
                <StatusTag :text="reviewText(w.status)" :tone="w.status === 'APPROVED' ? 'success' : w.status === 'REJECTED' ? 'danger' : 'warn'" />
              </div>
              <p class="sp-card__meta">提交于 {{ fmtTime(w.submittedAt) }}</p>
              <p class="sp-card__body">工作：{{ w.workContent || '—' }}
收获：{{ w.harvestContent || '—' }}
计划：{{ w.planContent || '—' }}</p>
              <p v-if="w.reviewComment" class="sp-card__meta">导师批注：{{ w.reviewComment }}</p>
            </article>
          </div>
        </section>

        <section class="sp-panel">
          <div class="sp-panel__head">考勤异常</div>
          <AutoTable :rows="my.attendanceExceptions" empty="暂无考勤异常" :columns="[
            { key: 'type', label: '类型' }, { key: 'status', label: '状态' }, { key: 'date', label: '日期' }
          ]" />
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const panel = ref('')
const weeklyForm = reactive({ week: null, workContent: '', harvestContent: '', planContent: '' })
const reportForm = reactive({ title: '', content: '' })
const appealForm = reactive({ reason: '' })

const panelTitle = computed(() => ({ weekly: '提交实习周报', report: '提交月报 / 实习总结', appeal: '实习成绩申诉' }[panel.value] || ''))

const STATUS_MAP = { ONBOARD: '实习中', PENDING: '待入职', ENDED: '已结束', PAUSED: '暂停' }
const RISK_MAP = { LOW: '低', MID: '中', HIGH: '高' }
const REVIEW_MAP = { PENDING_REVIEW: '待审阅', APPROVED: '已通过', REJECTED: '已退回' }
function statusText(s) { return STATUS_MAP[s] || s || '—' }
function riskText(s) { return RISK_MAP[s] || s || '—' }
function reviewText(s) { return REVIEW_MAP[s] || s || '—' }
function fmtTime(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '—' }

function open(p) { panel.value = panel.value === p ? '' : p }

async function load() {
  loading.value = true
  error.value = ''
  try { my.value = await portalApi.internshipMy() || {} }
  catch (e) { error.value = e?.message || '实习信息加载失败' }
  finally { loading.value = false }
}
async function submitWeekly() {
  busy.value = true
  try { await portalApi.internshipWeeklySubmit({ ...weeklyForm }); ui.notify('周报已提交'); panel.value = ''; Object.assign(weeklyForm, { workContent: '', harvestContent: '', planContent: '' }); load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitReport() {
  busy.value = true
  try { await portalApi.internshipReportSubmit({ ...reportForm }); ui.notify('长文档已提交'); panel.value = ''; reportForm.content = ''; load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitAppeal() {
  busy.value = true
  try { await portalApi.internshipScoreAppeal({ reason: appealForm.reason }); ui.notify('成绩申诉已提交'); panel.value = ''; appealForm.reason = '' }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function printAgreement() {
  busy.value = true
  try { await portalApi.internshipAgreementPrint({}); ui.notify('已生成三方协议打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}

onMounted(load)
</script>
