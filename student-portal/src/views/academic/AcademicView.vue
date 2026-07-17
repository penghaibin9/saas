<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">学业过程</p>
        <h1>我的学业</h1>
        <p class="sp-hero__sub">成绩单、课表、学籍异动、考试与缓考、补重修免修、毕业资格自查——重活在此办理。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="reload">刷新</button>
    </section>

    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 成绩单 -->
      <section v-show="tab === 'transcript'" class="sp-panel">
        <div class="sp-panel__head">
          我的成绩单
          <button class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="printTranscript">打印留痕</button>
        </div>
        <div class="sp-kpis">
          <div class="sp-kpi"><div class="sp-kpi__label">已获学分</div><div class="sp-kpi__value">{{ transcript.totalCredits ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">平均绩点 GPA</div><div class="sp-kpi__value">{{ transcript.gpa ?? '—' }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">课程数</div><div class="sp-kpi__value">{{ (transcript.items || []).length }}</div></div>
        </div>
        <AutoTable :rows="transcript.items" :empty="transcript.note || '暂无学业记录'" />
      </section>

      <!-- 课表 -->
      <section v-show="tab === 'schedule'" class="sp-panel">
        <div class="sp-panel__head">我的课表</div>
        <AutoTable :rows="schedule.items" :empty="schedule.note || '暂无已发布课表'" />
      </section>

      <!-- 学籍异动 -->
      <section v-show="tab === 'status'" class="sp-panel">
        <div class="sp-panel__head">
          学籍状态与异动
          <button class="sp-btn sp-btn--sm" :disabled="busy" @click="forms.status = !forms.status">发起异动申请</button>
        </div>
        <p class="sp-muted">当前学籍：<StatusTag :text="statusText(status.studentStatus)" :tone="status.studentStatus === 'NORMAL' ? 'success' : 'warn'" /> · {{ status.enrolled ? '在籍' : '非在籍' }}</p>
        <div v-if="forms.status" class="sp-form">
          <label>异动类型
            <select v-model="statusForm.changeType">
              <option value="SUSPEND">休学</option>
              <option value="RESUME">复学</option>
              <option value="TRANSFER">转专业</option>
              <option value="WITHDRAW">退学</option>
            </select>
          </label>
          <label class="sp-form__full">申请原因<textarea v-model.trim="statusForm.reason" placeholder="请说明异动原因" /></label>
          <button class="sp-btn" :disabled="busy || !statusForm.reason" @click="submitStatusChange">提交申请</button>
        </div>
        <AutoTable :rows="status.changes" empty="暂无异动记录" />
      </section>

      <!-- 考试与缓考 -->
      <section v-show="tab === 'exam'" class="sp-panel">
        <div class="sp-panel__head">
          我的考试与缓考
          <button class="sp-btn sp-btn--sm" :disabled="busy" @click="forms.defer = !forms.defer">申请缓考</button>
        </div>
        <AutoTable :rows="exam.items" :empty="exam.note || '考试安排即将上线'" title="考试安排" />
        <div v-if="forms.defer" class="sp-form">
          <label class="sp-form__full">缓考课程/原因<textarea v-model.trim="deferForm.reason" placeholder="请填写缓考课程与原因" /></label>
          <button class="sp-btn" :disabled="busy || !deferForm.reason" @click="submitDefer">提交缓考申请</button>
        </div>
        <AutoTable :rows="examDefer.items" empty="暂无缓考申请" title="我的缓考申请" />
      </section>

      <!-- 补考重修免修 -->
      <section v-show="tab === 'makeup'" class="sp-panel">
        <div class="sp-panel__head">补考 · 重修 · 免修</div>
        <AutoTable :rows="makeup.retakes" empty="暂无补考/重修记录" title="补考与重修" />
        <AutoTable :rows="makeup.exemptions" empty="暂无免修记录" title="免修" />
      </section>

      <!-- 毕业自查 -->
      <section v-show="tab === 'audit'" class="sp-panel">
        <div class="sp-panel__head">毕业资格自查</div>
        <div class="sp-kpis">
          <div class="sp-kpi"><div class="sp-kpi__label">已获学分</div><div class="sp-kpi__value">{{ audit.credits?.obtainedCredits ?? 0 }}<small>/ {{ audit.credits?.requiredCredits ?? '—' }}</small></div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">不及格门数</div><div class="sp-kpi__value">{{ audit.credits?.failCount ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">预警项</div><div class="sp-kpi__value">{{ audit.warnings?.total ?? 0 }}</div></div>
        </div>
        <p class="sp-muted">{{ audit.progress?.note || '毕业预审进度将在此展示。' }}</p>
        <AutoTable :rows="audit.warnings?.items" empty="暂无毕业预警" title="预警明细" />
      </section>

      <!-- 选课 -->
      <section v-show="tab === 'selection'" class="sp-panel">
        <div class="sp-panel__head">选课</div>
        <StateBlock v-if="!selectionCourses.length" type="empty" text="当前没有开放的选课批次" />
        <div v-else class="sp-table-wrap">
          <table class="sp-table">
            <thead><tr><th>课程</th><th>教师</th><th>学分</th><th>容量</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="c in selectionCourses" :key="c.id || c.courseId">
                <td>{{ c.courseName || c.name || '—' }}</td>
                <td>{{ c.teacherName || c.teacher || '—' }}</td>
                <td>{{ c.credit ?? '—' }}</td>
                <td>{{ c.enrolled ?? c.selected ?? '—' }}/{{ c.capacity ?? '—' }}</td>
                <td><button class="sp-link" :disabled="busy" @click="enroll(c)">选课</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <AutoTable :rows="selectionRecords" empty="暂无选课记录" title="我的选课记录" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const tabs = [
  { key: 'transcript', label: '成绩单' },
  { key: 'schedule', label: '课表' },
  { key: 'status', label: '学籍异动' },
  { key: 'exam', label: '考试与缓考' },
  { key: 'makeup', label: '补考重修免修' },
  { key: 'audit', label: '毕业自查' },
  { key: 'selection', label: '选课' }
]
const tab = ref('transcript')
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const transcript = ref({})
const schedule = ref({})
const status = ref({})
const exam = ref({})
const examDefer = ref({})
const makeup = ref({})
const audit = ref({})
const selectionCourses = ref([])
const selectionRecords = ref([])

const forms = reactive({ status: false, defer: false })
const statusForm = reactive({ changeType: 'SUSPEND', reason: '' })
const deferForm = reactive({ reason: '' })

const STATUS_MAP = { NORMAL: '正常', SUSPENDED: '休学', TRANSFERRED: '转学', WITHDRAWN: '退学', GRADUATED: '毕业' }
function statusText(s) { return STATUS_MAP[s] || s || '—' }

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [t, s, st, ex, exd, mk, au] = await Promise.all([
      portalApi.academicTranscript(), portalApi.academicSchedule(), portalApi.academicStatus(),
      portalApi.academicExam(), portalApi.academicExamDefer(), portalApi.academicMakeup(), portalApi.academicGraduationAudit()
    ])
    transcript.value = t || {}; schedule.value = s || {}; status.value = st || {}
    exam.value = ex || {}; examDefer.value = exd || {}; makeup.value = mk || {}; audit.value = au || {}
    const [cs, rec] = await Promise.all([portalApi.academicCourseSelection(), portalApi.academicSelectionRecords()])
    selectionCourses.value = Array.isArray(cs) ? cs : (cs?.items || [])
    selectionRecords.value = Array.isArray(rec) ? rec : (rec?.items || [])
  } catch (e) {
    error.value = e?.message || '学业数据加载失败'
  } finally {
    loading.value = false
  }
}

async function printTranscript() {
  busy.value = true
  try { await portalApi.academicTranscriptPrint({}); ui.notify('已生成打印留痕') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitStatusChange() {
  busy.value = true
  try { await portalApi.academicStatusChange({ ...statusForm }); ui.notify('异动申请已提交'); forms.status = false; statusForm.reason = ''; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitDefer() {
  busy.value = true
  try { await portalApi.academicExamDeferApply({ reason: deferForm.reason }); ui.notify('缓考申请已提交'); forms.defer = false; deferForm.reason = ''; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function enroll(c) {
  busy.value = true
  try { await portalApi.academicEnroll({ courseId: c.id || c.courseId }); ui.notify('选课成功'); reload() }
  catch (e) { ui.notify(e?.message || '选课失败（演示租户为只读）') } finally { busy.value = false }
}

onMounted(reload)
watch(tab, () => { forms.status = false; forms.defer = false })
</script>
