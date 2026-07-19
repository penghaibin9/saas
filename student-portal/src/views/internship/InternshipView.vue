<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="正在加载实习信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="!my.hasData" class="sp-notice" style="border-color:#FFD591;background:#FFFBE6">
        <div><strong style="color:#613400">暂无实习记录</strong><p class="sp-muted" style="margin:6px 0 0;color:#8b5c00">{{ my.message || '你尚未被纳入实习安排，建档后此处会显示企业、岗位与周月报待办。' }}</p></div>
      </section>

      <!-- 我的实习 -->
      <template v-else-if="tab === 'overview'">
        <section class="sp-card" style="margin-bottom:16px">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap">
            <div>
              <div style="font-size:18px;font-weight:600">{{ my.enterpriseName }} · {{ my.positionName }}</div>
              <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
                <span class="pill"><span style="color:#A9B0BD">指导教师</span>{{ my.advisorName || '待分配' }}</span>
                <span class="pill"><span style="color:#A9B0BD">风险等级</span>{{ riskText(my.riskLevel) }}</span>
              </div>
            </div>
            <span class="statepill"><span class="dot" />{{ statusText(my.status) }}</span>
          </div>
          <FlowSteps :steps="flowSteps" style="margin-top:22px" />
        </section>
        <div class="m4">
          <div v-for="m in metrics" :key="m.t" class="sp-metric"><div class="sp-metric__label">{{ m.t }}</div><div class="sp-metric__value" :style="{color:m.c}">{{ m.v }}<small>{{ m.u }}</small></div></div>
        </div>
      </template>

      <!-- 三方协议 -->
      <template v-else-if="tab === 'agreement'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">实习三方协议 <StatusTag text="已建立" tone="success" /></div>
            <div class="agreement">甲方（学校）：{{ brandSchool }}<br />乙方（企业）：{{ my.enterpriseName }}<br />丙方（学生）：{{ studentName }}<br />实习岗位：{{ my.positionName }} · 指导教师：{{ my.advisorName || '待分配' }}</div>
            <div style="display:flex;gap:10px;margin-top:16px">
              <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printAgreement">打印协议</button>
            </div>
            <p class="sp-muted" style="margin-top:10px">盖章件上传请在学生小程序完成，两端同一数据。</p>
          </section>
        </div>
      </template>

      <!-- 每日打卡 -->
      <template v-else-if="tab === 'checkin'">
        <div class="two2">
          <section class="sp-card" style="text-align:center">
            <div class="sp-muted">今日打卡</div>
            <div style="font-size:30px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums">{{ my.todayCheckin?.done ? (my.todayCheckin.time || '已打卡') : '未打卡' }}</div>
            <div class="sp-muted" style="margin-top:6px">累计出勤 {{ my.todayCheckin?.totalDays ?? 0 }} 天</div>
            <div class="notebox">日常打卡与地理围栏在<strong>学生小程序</strong>完成；PC 门户用于周月报、协议、成绩等重任务。</div>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">考勤异常</div>
            <AutoTable :rows="my.attendanceExceptions" empty="暂无考勤异常" :columns="[{key:'type',label:'类型'},{key:'status',label:'状态'},{key:'date',label:'日期'}]" />
          </section>
        </div>
      </template>

      <!-- 实习请假 -->
      <template v-else-if="tab === 'leave'">
        <section class="sp-card" style="max-width:640px">
          <div class="sp-panel__head">实习请假</div>
          <p class="notebox" style="margin-top:0">实习期请假请在<strong>学生小程序</strong>发起（含定位与销假）；如需线下证明可在此打印请假条。</p>
          <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="ui.notify('请在学生小程序发起实习请假')">前往小程序请假</button>
        </section>
      </template>

      <!-- 周报/月报/总结 -->
      <template v-else-if="tab === 'report'">
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <button v-for="r in reportTabs" :key="r" class="sp-tab" :class="{'is-active':reportTab===r}" @click="reportTab=r">{{ r }}</button>
        </div>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ reportTab }}编辑</div>
            <template v-if="reportTab==='周报'">
              <div class="sp-fieldlabel">周次</div><input v-model.number="weeklyForm.week" type="number" min="1" class="sp-inp" style="margin-bottom:12px" placeholder="第几周" />
              <div class="sp-fieldlabel">本周工作内容</div><textarea v-model.trim="weeklyForm.workContent" class="sp-inp" style="margin-bottom:12px" placeholder="本周主要完成的工作" />
              <div class="sp-fieldlabel">收获与体会</div><textarea v-model.trim="weeklyForm.harvestContent" class="sp-inp" style="margin-bottom:12px" placeholder="本周收获" />
              <div class="sp-fieldlabel">下周计划</div><textarea v-model.trim="weeklyForm.planContent" class="sp-inp" style="margin-bottom:12px" placeholder="下周安排" />
              <button class="sp-btn" :disabled="busy || !weeklyForm.workContent" @click="submitWeekly">提交周报</button>
            </template>
            <template v-else>
              <div class="sp-fieldlabel">报告标题</div><input v-model.trim="reportForm.title" class="sp-inp" style="margin-bottom:12px" :placeholder="reportTab + '标题'" />
              <div class="sp-fieldlabel">正文（长文档）</div><textarea v-model.trim="reportForm.content" class="sp-inp" style="min-height:200px;margin-bottom:12px" :placeholder="reportTab + '正文'" />
              <button class="sp-btn" :disabled="busy || !reportForm.content" @click="submitReport">提交{{ reportTab }}</button>
            </template>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">{{ reportTab === '周报' ? '周报记录' : '月报/总结记录' }}</div>
            <template v-if="reportTab === '周报'">
              <StateBlock v-if="!(my.weeklyReports||[]).length" type="empty" text="暂无周报" />
              <div v-else style="display:flex;flex-direction:column;gap:10px">
                <div v-for="w in my.weeklyReports" :key="w.week" class="repitem" style="flex-direction:column;align-items:stretch;gap:4px">
                  <div style="display:flex;align-items:center;justify-content:space-between">
                    <div style="flex:1"><div style="font-size:13.5px;color:var(--t1)">第 {{ w.week }} 周周报</div><div style="font-size:12px;color:var(--t4);margin-top:2px">{{ fmt(w.submittedAt) }}</div></div>
                    <StatusTag :text="reviewText(w.status)" :tone="w.status==='APPROVED'?'success':w.status==='REJECTED'?'danger':'warn'" />
                  </div>
                  <div v-if="w.reviewComment" class="sp-muted" style="font-size:12px">老师意见：{{ w.reviewComment }}</div>
                </div>
              </div>
            </template>
            <template v-else>
              <StateBlock v-if="!(my.processReports||[]).length" type="empty" text="暂无月报/总结记录" />
              <div v-else style="display:flex;flex-direction:column;gap:10px">
                <div v-for="p in my.processReports" :key="p.id" class="repitem" style="flex-direction:column;align-items:stretch;gap:4px">
                  <div style="display:flex;align-items:center;justify-content:space-between">
                    <div style="flex:1"><div style="font-size:13.5px;color:var(--t1)">{{ p.periodKey }}（{{ p.reportType === 'MONTHLY' ? '月报' : '实习总结' }}）</div><div style="font-size:12px;color:var(--t4);margin-top:2px">{{ fmt(p.submittedAt) }}</div></div>
                    <StatusTag :text="reviewText(p.status)" :tone="p.status==='APPROVED'?'success':p.status==='RETURNED'?'danger':'warn'" />
                  </div>
                  <div v-if="p.reviewComment" class="sp-muted" style="font-size:12px">老师意见：{{ p.reviewComment }}</div>
                </div>
              </div>
            </template>
          </section>
        </div>
      </template>

      <!-- 实习成绩/自评 -->
      <template v-else-if="tab === 'eval'">
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">实习自评 / 鉴定</div>
            <div class="sp-fieldlabel">工作表现自评</div><textarea v-model.trim="evalForm.performance" class="sp-inp" style="margin-bottom:12px" placeholder="请描述实习期间的工作表现" />
            <div class="sp-fieldlabel">收获与反思</div><textarea v-model.trim="evalForm.reflection" class="sp-inp" style="margin-bottom:12px" placeholder="请描述实习收获与不足" />
            <button class="sp-btn" :disabled="busy" @click="ui.notify('自评提交请在学生小程序完成')">提交自评</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">成绩与申诉</div>
            <template v-if="my.score">
              <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px">
                <div style="font-size:32px;font-weight:700;color:var(--pri)">{{ my.score.totalScore ?? '—' }}</div>
                <StatusTag :text="my.score.isPass ? '合格' : '不合格'" :tone="my.score.isPass ? 'success' : 'danger'" />
              </div>
              <dl class="score-grid">
                <div><dt>打卡</dt><dd>{{ my.score.checkinScore ?? '—' }}</dd></div>
                <div><dt>周报</dt><dd>{{ my.score.weeklyScore ?? '—' }}</dd></div>
                <div><dt>月报/总结</dt><dd>{{ my.score.monthlyScore ?? '—' }}</dd></div>
                <div><dt>企业评价</dt><dd>{{ my.score.enterpriseScore ?? '—' }}</dd></div>
                <div><dt>指导教师</dt><dd>{{ my.score.schoolScore ?? '—' }}</dd></div>
              </dl>
              <p class="sp-muted" style="margin-top:8px">发布时间：{{ fmt(my.score.publishedAt) }}</p>
            </template>
            <p v-else class="sp-muted">综合成绩由企业导师、指导教师、周月报打卡按权重生成，发布后可在此查看。</p>
            <div class="sp-fieldlabel" style="margin-top:14px">成绩申诉理由</div>
            <textarea v-model.trim="appealReason" class="sp-inp" style="margin-bottom:12px" placeholder="对成绩有异议？请说明理由" />
            <button class="sp-btn sp-btn--ghost" :disabled="busy || !appealReason" @click="submitAppeal">提交成绩申诉</button>
          </section>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import { portalApi } from '../../services/portalApi'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const cfg = usePortalConfigStore()
const session = useSessionStore()
const tabs = [
  { key: 'overview', label: '我的实习' }, { key: 'agreement', label: '三方协议' },
  { key: 'checkin', label: '每日打卡' }, { key: 'leave', label: '实习请假' },
  { key: 'report', label: '周报/月报/总结' }, { key: 'eval', label: '实习成绩/自评' }
]
const tab = ref('overview')
const reportTab = ref('周报')
const reportTabs = ['周报', '月报', '实习总结']
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const weeklyForm = reactive({ week: null, workContent: '', harvestContent: '', planContent: '' })
const reportForm = reactive({ title: '', content: '' })
const evalForm = reactive({ performance: '', reflection: '' })
const appealReason = ref('')

const brandSchool = computed(() => cfg.brand?.schoolName || '学校')
const studentName = computed(() => session.user?.realName || '同学')
const STATUS_MAP = { ONBOARD: '实习中', PENDING: '待入职', ENDED: '已结束', PAUSED: '暂停' }
const RISK_MAP = { LOW: '低', MID: '中', HIGH: '高' }
const REVIEW_MAP = { PENDING_REVIEW: '待审阅', APPROVED: '已通过', REJECTED: '已退回', RETURNED: '已退回' }
function statusText(s) { return STATUS_MAP[s] || s || '—' }
function riskText(s) { return RISK_MAP[s] || s || '—' }
function reviewText(s) { return REVIEW_MAP[s] || s || '—' }
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '—' }

const flowSteps = computed(() => {
  const order = ['协议签署', '岗前培训', '在岗实习', '考核评价', '归档']
  const cur = my.value.status === 'ENDED' ? 4 : 2
  return order.map((name, i) => ({ name, state: i < cur ? 'done' : i === cur ? 'current' : 'todo' }))
})
const metrics = computed(() => [
  { t: '累计出勤', v: my.value.todayCheckin?.totalDays ?? 0, u: '天', c: 'var(--t1)' },
  { t: '周报数', v: (my.value.weeklyReports || []).length, u: '篇', c: 'var(--t1)' },
  { t: '考勤异常', v: (my.value.attendanceExceptions || []).length, u: '次', c: (my.value.attendanceExceptions || []).length ? 'var(--warn-fg)' : 'var(--ok-fg)' },
  { t: '风险等级', v: riskText(my.value.riskLevel), u: '', c: my.value.riskLevel === 'HIGH' ? 'var(--danger-fg)' : 'var(--ok-fg)' }
])

async function load() {
  loading.value = true; error.value = ''
  try { my.value = await portalApi.internshipMy() || {} }
  catch (e) { error.value = e?.message || '实习信息加载失败' } finally { loading.value = false }
}
async function submitWeekly() {
  busy.value = true
  try { await portalApi.internshipWeeklySubmit({ weekNo: weeklyForm.week, workContent: weeklyForm.workContent, harvestContent: weeklyForm.harvestContent, planContent: weeklyForm.planContent }); ui.notify('周报已提交'); Object.assign(weeklyForm, { workContent: '', harvestContent: '', planContent: '' }); load() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitReport() {
  busy.value = true
  try {
    const RT = { 月报: 'MONTHLY', 实习总结: 'SUMMARY', 周报: 'WEEKLY' }
    await portalApi.internshipReportSubmit({ reportType: RT[reportTab.value] || 'MONTHLY', periodKey: reportForm.title || reportTab.value, content: reportForm.content })
    ui.notify(reportTab.value + '已提交'); reportForm.content = ''; load()
  }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitAppeal() {
  busy.value = true
  try { await portalApi.internshipScoreAppeal({ reason: appealReason.value }); ui.notify('成绩申诉已提交'); appealReason.value = '' }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function printAgreement() {
  busy.value = true
  try { await portalApi.internshipAgreementPrint({}); ui.notify('已生成三方协议打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.pill { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; background: #F5F7FA; border: 1px solid #EDEFF3; border-radius: 7px; font-size: 12.5px; color: var(--t2); }
.statepill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; background: var(--pri-50); border-radius: 9px; color: var(--pri); font-weight: 600; font-size: 13.5px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--pri); }
.m4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.two { display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; align-items: start; }
.two2 { display: grid; grid-template-columns: 1fr 1.3fr; gap: 18px; align-items: start; }
.agreement { border: 1px solid var(--line); border-radius: 11px; padding: 18px; font-size: 13.5px; color: var(--t2); line-height: 2; }
.notebox { margin-top: 14px; padding: 12px 14px; background: #F2F7FF; border-radius: 10px; font-size: 12.5px; color: var(--t2); line-height: 1.6; }
.repitem { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 11px; }
.score-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.score-grid dt { font-size: 12px; color: var(--t3); margin-bottom: 4px; }
.score-grid dd { margin: 0; font-size: 15px; font-weight: 600; color: var(--t1); }
@media (max-width: 900px) { .score-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .m4 { grid-template-columns: repeat(2,1fr); } .two, .two2 { grid-template-columns: 1fr; } }
</style>
