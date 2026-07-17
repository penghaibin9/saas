<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 我的课表 -->
      <section v-if="tab === 'schedule'" class="sp-card">
        <div class="sp-panel__head">
          <span>我的课表 <span class="sp-muted">{{ schedule.note || '' }}</span></span>
          <button class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="printTranscript('课表')">打印课表</button>
        </div>
        <StateBlock v-if="!(schedule.items||[]).length" type="empty" text="暂无已发布课表" />
        <div v-else class="sched-grid">
          <div /><div v-for="d in days" :key="d" class="sched-day">{{ d }}</div>
          <template v-for="row in scheduleRows" :key="row.label">
            <div class="sched-time">{{ row.label }}</div>
            <div v-for="(cell, ci) in row.cells" :key="ci" class="sched-cell">
              <div v-if="cell" class="sched-course"><div style="font-weight:600;color:var(--pri)">{{ cell.name }}</div><div style="font-size:11px;color:var(--t2);margin-top:3px">{{ cell.room }}</div><div style="font-size:11px;color:var(--t4)">{{ cell.teacher }}</div></div>
            </div>
          </template>
        </div>
      </section>

      <!-- 选课中心 -->
      <section v-else-if="tab === 'select'">
        <div class="select-grid">
          <div class="sp-card" style="padding:0;overflow:hidden">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--line2)"><span style="font-size:16px;font-weight:600">选课</span><span class="sp-muted">已选 {{ selectedCourses.length }} 门 · {{ selectedCredit }} 学分</span></div>
            <StateBlock v-if="!courses.length" type="empty" text="当前没有开放的选课批次" />
            <table v-else class="sp-table">
              <thead><tr><th>课程</th><th>教师</th><th>学分</th><th>容量</th><th style="text-align:right">操作</th></tr></thead>
              <tbody>
                <tr v-for="c in courses" :key="c.selectionCourseId || c.courseId">
                  <td style="font-weight:500;color:var(--t1)">{{ c.courseName || '—' }}</td>
                  <td>{{ c.teacherName || '—' }}</td>
                  <td>{{ c.credit ?? '—' }}</td>
                  <td>余 {{ c.remain ?? '—' }} / {{ c.capacity ?? '—' }}</td>
                  <td style="text-align:right"><button class="mini" :disabled="busy || c.remain === 0" @click="enroll(c)">选课</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="sp-card" style="position:sticky;top:0">
            <div class="sp-panel__head">选课统计</div>
            <div style="display:flex;align-items:baseline;gap:4px"><span style="font-size:30px;font-weight:700;color:var(--pri);font-variant-numeric:tabular-nums">{{ selectedCredit }}</span><span class="sp-muted">/ 建议 26 学分</span></div>
            <div class="bar"><span :style="{ width: Math.min(100, selectedCredit / 26 * 100) + '%' }" /></div>
            <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px;font-size:13px;color:var(--t2)">
              <div style="display:flex;justify-content:space-between"><span>已选门数</span><span>{{ selectedCourses.length }} 门</span></div>
            </div>
          </div>
        </div>
        <AutoTable :rows="selectionRecords" empty="暂无选课记录" title="我的选课记录" style="margin-top:16px" />
      </section>

      <!-- 我的成绩 -->
      <section v-else-if="tab === 'grades'">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <span style="font-size:15px;font-weight:600">我的成绩</span>
          <span class="sp-muted">已获学分 <b style="color:var(--pri)">{{ transcript.earnedCredits ?? 0 }}</b> · GPA <b style="color:var(--pri)">{{ transcript.gpa ?? '—' }}</b> · 不及格 {{ transcript.failCount ?? 0 }} 门</span>
        </div>
        <StateBlock v-if="!(transcript.items||[]).length" type="empty" :text="transcript.note || '暂无学业记录'" />
        <section v-for="t in gradeTerms" :key="t.term" class="sp-card" style="padding:0;overflow:hidden;margin-bottom:16px">
          <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--line2)"><span style="font-size:14px;font-weight:600">{{ t.term || '未分学期' }}</span><span class="sp-muted">{{ t.rows.length }} 门 · {{ t.credit }} 学分</span></div>
          <table class="sp-table">
            <thead><tr><th>课程名称</th><th>学分</th><th>成绩</th><th>结果</th></tr></thead>
            <tbody>
              <tr v-for="(g, i) in t.rows" :key="i">
                <td style="color:var(--t1)">{{ g.courseName }}</td>
                <td>{{ g.credit }}</td>
                <td :style="{ color: scoreColor(g.score), fontWeight: 600 }">{{ g.score ?? '—' }}</td>
                <td><StatusTag :text="g.passStatus === 'PASSED' ? '及格' : '不及格'" :tone="g.passStatus === 'PASSED' ? 'success' : 'danger'" /></td>
              </tr>
            </tbody>
          </table>
        </section>
      </section>

      <!-- 成绩单打印 -->
      <section v-else-if="tab === 'transcript'">
        <div class="two">
          <div class="sp-card">
            <div class="tr-preview">
              <div class="tr-wm">{{ brandSchool }} · 仅供查验</div>
              <div style="position:relative;text-align:center;font-size:17px;font-weight:700">{{ brandSchool }}学生成绩单</div>
              <div style="position:relative;text-align:center;font-size:12px;color:var(--t4);margin-top:4px">Official Academic Transcript</div>
              <div style="position:relative;display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;margin-top:18px;font-size:13px;color:var(--t2)">
                <div>姓名：{{ studentName }}</div><div>学号：{{ info.studentNo || '—' }}</div>
                <div>学院：{{ info.collegeName || '—' }}</div><div>专业：{{ info.majorName || '—' }}</div>
              </div>
              <div style="position:relative;margin-top:16px;font-size:12.5px;color:var(--t4)">已修课程 {{ (transcript.items||[]).length }} 门 · 已获学分 {{ transcript.earnedCredits ?? 0 }} · 平均绩点 {{ transcript.gpa ?? '—' }}</div>
            </div>
          </div>
          <div class="sp-card">
            <div class="sp-panel__head">开具成绩单</div>
            <div class="sp-fieldlabel">开具事由（必填，将写入审计）</div>
            <input v-model.trim="printReason" class="sp-inp" style="margin-bottom:12px" placeholder="如：入党材料 / 转学申请 / 个人留存" />
            <button class="sp-btn" :disabled="busy || !printReason" @click="printTranscript(printReason)">生成并下载（带水印）</button>
          </div>
        </div>
      </section>

      <!-- 成绩申诉 -->
      <section v-else-if="tab === 'appeal'" class="sp-card" style="max-width:640px">
        <div class="sp-panel__head">发起成绩申诉</div>
        <div class="sp-fieldlabel">申诉事由</div>
        <textarea v-model.trim="appealForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明对成绩有异议的具体原因，如核分错误、漏登等" />
        <button class="sp-btn" :disabled="busy || !appealForm.reason" @click="ui.notify('成绩申诉请通过教务成绩更正流程，已记录你的诉求')">提交申诉</button>
        <p class="sp-muted" style="margin-top:10px">成绩申诉进入教务审核；结果将在「消息通知」告知。</p>
      </section>

      <!-- 学籍异动申请 -->
      <section v-else-if="tab === 'status'" class="sp-card">
        <div class="sp-panel__head">学籍异动申请向导</div>
        <div class="wiz">
          <div v-for="(w, i) in wizSteps" :key="w.n" class="wiz__seg">
            <div class="wiz__node"><span class="wiz__c" :class="wizClass(w.n)">{{ w.n }}</span><span class="wiz__t" :class="{ on: wizStep >= w.n }">{{ w.t }}</span></div>
            <span v-if="i < wizSteps.length-1" class="wiz__line" :style="{ background: wizStep > w.n ? 'var(--pri)' : '#E5E8EE' }" />
          </div>
        </div>
        <template v-if="wizStep === 1">
          <div class="sp-muted" style="margin-bottom:12px">当前学籍：<StatusTag :text="statusText(status.studentStatus)" :tone="status.studentStatus==='NORMAL'?'success':'warn'" /> · 请选择异动类型</div>
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <button v-for="ct in changeTypes" :key="ct.k" class="typecard" :class="{ on: statusForm.changeType === ct.k }" @click="statusForm.changeType = ct.k">
              <div style="font-size:14px;font-weight:600" :style="{ color: statusForm.changeType===ct.k ? 'var(--pri)' : 'var(--t1)' }">{{ ct.t }}</div>
              <div class="sp-muted" style="margin-top:5px">{{ ct.desc }}</div>
            </button>
          </div>
          <button class="sp-btn" style="margin-top:20px" @click="wizStep = 2">下一步</button>
        </template>
        <template v-else-if="wizStep === 2">
          <div class="sp-fieldlabel">申请事由</div>
          <textarea v-model.trim="statusForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请详细说明申请原因" />
          <div style="display:flex;gap:10px">
            <button class="sp-btn sp-btn--ghost" @click="wizStep = 1">上一步</button>
            <button class="sp-btn" :disabled="!statusForm.reason" @click="wizStep = 3">下一步：预览</button>
          </div>
        </template>
        <template v-else>
          <div class="preview">异动类型：<b>{{ changeLabel(statusForm.changeType) }}</b><br />申请人：{{ studentName }}（{{ info.studentNo }}）<br />事由：{{ statusForm.reason }}</div>
          <div style="display:flex;gap:10px;margin-top:16px">
            <button class="sp-btn sp-btn--ghost" @click="wizStep = 2">上一步</button>
            <button class="sp-btn" :disabled="busy" @click="submitStatusChange">打印申请表并提交</button>
          </div>
        </template>
        <AutoTable :rows="status.changes" empty="暂无异动记录" title="历史异动记录" style="margin-top:16px" />
      </section>

      <!-- 免修/缓考/补考重修 -->
      <section v-else-if="tab === 'exam'">
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <button v-for="e in examTabs" :key="e" class="sp-tab" :class="{ 'is-active': examTab === e }" @click="examTab = e">{{ e }}</button>
        </div>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ examTab }}</div>
            <div class="sp-fieldlabel">申请理由</div>
            <textarea v-model.trim="examForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明申请理由并准备佐证材料" />
            <button class="sp-btn" :disabled="busy || !examForm.reason" @click="submitExam">提交申请</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">申请记录</div>
            <AutoTable :rows="examTab==='缓考申请' ? examDefer.items : makeupRows" empty="暂无申请记录" />
          </section>
        </div>
      </section>

      <!-- 毕业资格自查 -->
      <section v-else-if="tab === 'audit'">
        <section class="sp-card">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
            <div><div style="font-size:16px;font-weight:600">毕业资格达成度</div><div class="sp-muted" style="margin-top:6px">{{ audit.progress?.note || '数据每日更新' }}</div></div>
            <div style="display:flex;align-items:baseline;gap:6px"><span style="font-size:32px;font-weight:700;color:var(--pri);font-variant-numeric:tabular-nums">{{ auditPct }}</span><span class="sp-muted">%</span></div>
          </div>
          <div class="bar" style="margin-top:14px;height:10px"><span :style="{ width: auditPct + '%' }" /></div>
        </section>
        <section class="sp-card" style="padding:0;overflow:hidden">
          <table class="sp-table">
            <thead><tr><th>培养环节</th><th>要求学分</th><th>已修学分</th><th>状态</th></tr></thead>
            <tbody>
              <tr><td>总学分</td><td>{{ audit.credits?.requiredCredits ?? '—' }}</td><td>{{ audit.credits?.obtainedCredits ?? 0 }}</td><td><StatusTag :text="(audit.credits?.obtainedCredits||0) >= (audit.credits?.requiredCredits||999) ? '已达标' : '进行中'" :tone="(audit.credits?.obtainedCredits||0) >= (audit.credits?.requiredCredits||999) ? 'success':'warn'" /></td></tr>
              <tr v-for="(w, i) in (audit.warnings?.items || [])" :key="i"><td>{{ w.name || w.category || '预警项' }}</td><td>—</td><td>—</td><td><StatusTag :text="w.text || '预警'" tone="danger" /></td></tr>
            </tbody>
          </table>
          <StateBlock v-if="!(audit.warnings?.items||[]).length" type="empty" text="暂无毕业预警" />
        </section>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const cfg = usePortalConfigStore()
const session = useSessionStore()
const tabs = [
  { key: 'schedule', label: '我的课表' }, { key: 'select', label: '选课中心' }, { key: 'grades', label: '我的成绩' },
  { key: 'transcript', label: '成绩单打印' }, { key: 'appeal', label: '成绩申诉' }, { key: 'status', label: '学籍异动' },
  { key: 'exam', label: '免修/缓考/补重修' }, { key: 'audit', label: '毕业自查' }
]
const tab = ref('schedule')
const examTab = ref('免修申请')
const examTabs = ['免修申请', '缓考申请', '补考重修申请']
const wizStep = ref(1)
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const schedule = ref({})
const courses = ref([])
const selectionRecords = ref([])
const transcript = ref({})
const status = ref({})
const examDefer = ref({})
const makeup = ref({})
const audit = ref({})
const info = ref({})

const printReason = ref('')
const appealForm = reactive({ reason: '' })
const statusForm = reactive({ changeType: 'SUSPEND', reason: '' })
const examForm = reactive({ reason: '' })

const days = ['周一', '周二', '周三', '周四', '周五']
const wizSteps = [{ n: 1, t: '选择类型' }, { n: 2, t: '填写事由' }, { n: 3, t: '预览提交' }]
const changeTypes = [
  { k: 'SUSPEND', t: '休学', desc: '保留学籍暂停学业' }, { k: 'RESUME', t: '复学', desc: '休学期满恢复学习' },
  { k: 'TRANSFER', t: '转专业', desc: '跨专业调整培养方案' }, { k: 'WITHDRAW', t: '退学', desc: '终止学业注销学籍' }
]
const brandSchool = computed(() => cfg.brand?.schoolName || '学校')
const studentName = computed(() => session.user?.realName || '同学')
const selectedCourses = computed(() => selectionRecords.value)
const selectedCredit = computed(() => selectionRecords.value.reduce((a, c) => a + (Number(c.credit) || 0), 0))
const TIME_ROWS = ['第1-2节\n08:00-09:40', '第3-4节\n10:00-11:40', '第5-6节\n14:00-15:40', '第7-8节\n16:00-17:40', '第9-10节\n19:00-20:40']
const scheduleRows = computed(() => {
  const items = schedule.value.items || []
  const rows = TIME_ROWS.map((label) => ({ label, cells: [null, null, null, null, null] }))
  for (const it of items) {
    const day = Number(it.weekday ?? it.dayOfWeek ?? it.day) // 1..7
    const sec = Number(it.slotNo ?? it.section ?? it.period) // 节次(1/3/5/7/9 或 1..10)
    const di = (day >= 1 && day <= 5) ? day - 1 : -1
    let ri = -1
    if (sec >= 1 && sec <= 5) ri = sec - 1
    else if (sec >= 1 && sec <= 10) ri = Math.floor((sec - 1) / 2)
    if (di >= 0 && ri >= 0 && !rows[ri].cells[di]) {
      rows[ri].cells[di] = { name: it.courseName || it.name, room: it.classroom || it.room || '', teacher: it.teacherName || it.teacher || '' }
    }
  }
  return rows
})
const gradeTerms = computed(() => {
  const map = {}
  for (const g of (transcript.value.items || [])) {
    const key = g.term || ''
    if (!map[key]) map[key] = { term: key, rows: [], credit: 0 }
    map[key].rows.push(g)
    if (g.passStatus === 'PASSED') map[key].credit += Number(g.credit || 0)
  }
  return Object.values(map).sort((a, b) => (a.term < b.term ? 1 : -1))
})
const makeupRows = computed(() => [...(makeup.value.retakes || []), ...(makeup.value.exemptions || [])])
const auditPct = computed(() => {
  const c = audit.value.credits || {}
  if (!c.requiredCredits) return 0
  return Math.min(100, Math.round((c.obtainedCredits || 0) / c.requiredCredits * 100))
})
const STATUS_MAP = { NORMAL: '正常', SUSPENDED: '休学', TRANSFERRED: '转学', WITHDRAWN: '退学', GRADUATED: '毕业' }
function statusText(s) { return STATUS_MAP[s] || s || '正常' }
function changeLabel(k) { return (changeTypes.find((c) => c.k === k) || {}).t || k }
function scoreColor(s) { const n = Number(s); return n >= 90 ? 'var(--ok-fg)' : n >= 60 ? 'var(--t1)' : 'var(--warn-fg)' }
function wizClass(n) { return wizStep.value > n ? 'done' : wizStep.value === n ? 'cur' : 'todo' }

async function loadAll() {
  loading.value = true; error.value = ''
  try {
    const [sc, tr, st, ex, mk, au, cs, rec, en] = await Promise.allSettled([
      portalApi.academicSchedule(), portalApi.academicTranscript(), portalApi.academicStatus(),
      portalApi.academicExamDefer(), portalApi.academicMakeup(), portalApi.academicGraduationAudit(),
      portalApi.academicCourseSelection(), portalApi.academicSelectionRecords(), portalApi.profileEnrollment()
    ])
    const val = (r, d) => (r.status === 'fulfilled' ? (r.value ?? d) : d)
    schedule.value = val(sc, {}); transcript.value = val(tr, {}); status.value = val(st, {})
    examDefer.value = val(ex, {}); makeup.value = val(mk, {}); audit.value = val(au, {})
    const c = val(cs, []); courses.value = Array.isArray(c) ? c.flatMap((x) => x.courses || []) : (c.courses || c.items || [])
    const r = val(rec, []); selectionRecords.value = Array.isArray(r) ? r : (r.items || [])
    info.value = val(en, {})
  } catch (e) { error.value = e?.message || '学业数据加载失败' } finally { loading.value = false }
}
async function printTranscript(reason) {
  busy.value = true
  try { await portalApi.academicTranscriptPrint({ reason }); ui.notify('已生成打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}
async function enroll(c) {
  busy.value = true
  try { await portalApi.academicEnroll({ selectionCourseId: c.selectionCourseId }); ui.notify('选课成功'); loadAll() }
  catch (e) { ui.notify(e?.message || '选课失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitStatusChange() {
  busy.value = true
  try { await portalApi.academicStatusChange({ ...statusForm }); ui.notify('异动申请已提交'); wizStep.value = 1; statusForm.reason = ''; loadAll() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitExam() {
  busy.value = true
  try {
    if (examTab.value === '缓考申请') await portalApi.academicExamDeferApply({ reason: examForm.reason })
    else await portalApi.academicRetakeApply({ reason: examForm.reason, type: examTab.value })
    ui.notify('申请已提交'); examForm.reason = ''; loadAll()
  } catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
onMounted(loadAll)
</script>

<style scoped>
.sched-grid { display: grid; grid-template-columns: 96px repeat(5, 1fr); gap: 6px; }
.sched-day { text-align: center; font-size: 13px; font-weight: 600; color: var(--t2); padding: 8px 0; }
.sched-time { font-size: 11.5px; color: var(--t4); padding: 10px 6px; white-space: pre-line; line-height: 1.4; }
.sched-cell { min-height: 64px; border-radius: 9px; border: 1px solid #F0F1F3; padding: 8px; }
.sched-course { background: var(--pri-50); border-radius: 7px; padding: 7px 8px; height: 100%; font-size: 12.5px; }
.select-grid { display: grid; grid-template-columns: 1fr 260px; gap: 18px; align-items: start; }
.bar { margin-top: 10px; height: 8px; border-radius: 4px; background: #F0F1F3; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 4px; background: var(--pri); }
.mini { all: unset; cursor: pointer; padding: 7px 14px; border-radius: 8px; font-size: 12.5px; font-weight: 600; background: var(--pri); color: #fff; }
.mini:disabled { opacity: .5; cursor: not-allowed; }
.two { display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px; align-items: start; }
.tr-preview { border: 1.5px solid #DDE1E8; border-radius: 10px; padding: 24px; position: relative; overflow: hidden; }
.tr-wm { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 44px; font-weight: 700; color: rgba(37,99,235,.05); transform: rotate(-18deg); pointer-events: none; white-space: nowrap; }
.wiz { display: flex; align-items: center; margin-bottom: 22px; }
.wiz__seg { display: flex; align-items: center; flex: 1; }
.wiz__node { display: flex; align-items: center; gap: 8px; flex: none; }
.wiz__c { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; background: #fff; border: 2px solid #DDE1E8; color: #A9B0BD; }
.wiz__c.cur { border-color: var(--pri); color: var(--pri); }
.wiz__c.done { background: var(--pri); border-color: var(--pri); color: #fff; }
.wiz__t { font-size: 13px; color: #A9B0BD; white-space: nowrap; }
.wiz__t.on { color: var(--t1); font-weight: 600; }
.wiz__line { flex: 1; height: 2px; margin: 0 10px; }
.typecard { all: unset; box-sizing: border-box; cursor: pointer; width: 170px; padding: 16px; border-radius: 12px; border: 1.5px solid var(--line); background: #fff; }
.typecard.on { border-color: var(--pri); background: var(--pri-50); }
.preview { padding: 16px; border: 1px solid var(--line); border-radius: 10px; max-width: 520px; font-size: 13px; color: var(--t2); line-height: 1.8; }
@media (max-width: 900px) { .select-grid, .two { grid-template-columns: 1fr; } }
</style>
