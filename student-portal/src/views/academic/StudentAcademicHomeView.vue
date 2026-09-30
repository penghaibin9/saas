<template>
  <div data-academic-page class="sp-page academic-prototype">
    <AcademicPrototypeHeader title="学业总览" group="学业工作台" description="先处理今日需要你完成的事。" :term="todaySchedule.termCode" :loading="loading" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在汇总教务任务…" />
    <section v-else-if="accessError" class="card pad" role="alert"><StateBlock type="error" :text="accessError" /><button class="btn" @click="load">重新核对权限</button></section>
    <div v-else class="stack">
      <div class="wide-action" :aria-label="headline">
        <div class="row"><div class="iconbox"><AcademicPrototypeIcon name="graduation-cap" /></div><div><h2>{{ partialError ? '部分学业事项待重新核对' : tasks.length ? '今天有 ' + tasks.length + ' 类事项待办理' : '当前没有待办理的教务事项' }}</h2><p>从具体事项进入，办完后还能回到这里继续。</p></div></div>
        <button class="btn primary" @click="go('/academic/selection')">打开网上选课</button>
      </div>
      <div class="grid2">
        <section class="card">
          <header class="card-head"><h2>今日课程</h2><RouterLink class="btn link small" to="/academic/schedule">完整课表</RouterLink></header>
          <div class="card-body">
            <StateBlock v-if="scheduleError" type="error" :text="scheduleError" />
            <p v-else-if="!todayLessons.length" class="muted">{{ todaySchedule.note || (Array.isArray(todaySchedule.todayItems) ? '今天没有正式课程安排' : '今日课程尚未提供，请进入课表核对') }}</p>
            <div v-for="(lesson,index) in todayLessons" :key="lesson.itemId || index" class="event">
              <div class="time">{{ lessonStart(lesson) }}<small>{{ lessonSlot(lesson) }}</small></div>
              <div><strong>{{ lesson.courseName || '课程待公布' }}</strong><small>{{ lesson.teacherName || '教师待公布' }} · {{ lesson.classroom || '教室待公布' }}{{ todaySchedule.todayWeek ? ' · 第' + todaySchedule.todayWeek + '周' : '' }}</small><span v-if="lesson.changeType || lesson.adjustmentNote" class="tag amber">{{ lesson.adjustmentNote || '课次已调整，请核对详情' }}</span></div>
              <RouterLink class="btn small" :to="{path:'/academic/schedule',query:lesson.itemId ? {lesson:lesson.itemId} : {}}">课次详情</RouterLink>
            </div>
          </div>
        </section>
        <section class="card">
          <header class="card-head"><h2>我的待办</h2><span class="tag">本人事项</span></header>
          <div class="card-body">
            <p v-if="!tasks.length" class="muted">{{ partialError ? '部分任务未能核对，请刷新后确认。' : '当前没有待提交、待确认或待整改的教务任务' }}</p>
            <div v-for="task in tasks" :key="task.key" class="taskline">
              <div class="iconbox" :class="{amber:task.tone === 'warn'}"><AcademicPrototypeIcon :name="taskIcon(task)" /></div><div class="grow"><strong>{{ task.title }}</strong><small>{{ task.description }}</small></div><button class="btn small" @click="go(task.route)">去处理</button>
            </div>
          </div>
        </section>
      </div>
      <div class="grid2">
        <section class="card">
          <header class="card-head"><h2>本学期学业概况</h2></header>
          <div class="card-body">
            <div class="metrics-inline">
              <div class="metric"><span class="label">已获学分</span><strong>{{ academicSummary.earnedCredits ?? '待确认' }}</strong><small>正式成绩口径</small></div>
              <div class="metric"><span class="label">平均绩点</span><strong>{{ academicSummary.gpa ?? '待确认' }}</strong><small>沿学校有效策略</small></div>
              <div class="metric"><span class="label">待补救课程</span><strong>{{ academicSummary.failCount ?? '待确认' }}</strong><small>查看补考重修</small></div>
            </div>
            <div class="divider"></div><RouterLink class="btn link" to="/academic/credits">查看学分修读</RouterLink>
            <div class="overview-statuses"><RouterLink v-for="item in overview" :key="item.route" :to="item.route" class="taskline"><div class="grow"><strong>{{ item.title }}</strong><small>{{ item.next }}</small></div><span class="tag">{{ item.value }}</span></RouterLink></div>
          </div>
        </section>
        <section class="card">
          <header class="card-head"><h2>最近办理</h2></header>
          <div class="card-body">
            <p v-if="!recentRecords.length" class="muted">{{ failedSources.includes('选课记录') ? '办理记录暂时无法读取，请刷新重试。' : '暂无本人选课办理记录。' }}</p>
            <div v-for="(record,index) in recentRecords" :key="record.recordId || index" class="taskline"><AcademicPrototypeIcon name="circle-info" /><div class="grow"><strong>{{ record.courseName || '课程办理记录' }} · {{ selectionState(record.status) }}</strong><small>{{ ['SELECTED','LOCKED'].includes(record.status) ? '名单锁定且课表正式发布后进入正式课表' : record.status === 'PENDING_LOTTERY' ? '已登记报名，等待学校抽签结果' : '以服务器正式记录为准' }}</small></div><RouterLink class="btn link small" to="/academic/selection">查看</RouterLink></div>
          </div>
        </section>
      </div>
      <div v-if="partialError" class="notice amber" role="status"><AcademicPrototypeIcon name="triangle-exclamation" />{{ failedSources.join('、') }}读取失败，请刷新重试。</div>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { academicErrorKind, academicErrorMessage } from '../../components/academic/studentAcademicUi'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity } from '../../components/academic/studentAcademicCommandGuard'
import { portalApi } from '../../services/portalApi'
import { useSessionStore } from '../../stores/session'

const router = useRouter()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session))
const loading = ref(true)
const partialError = ref(false)
const failedSources = ref([])
const tasks = ref([])
const todaySchedule = ref({})
const scheduleError = ref('')
const accessError = ref('')
const overview = ref([])
const academicSummary = ref({})
const recentRecords = ref([])
const todayLessons = computed(() => Array.isArray(todaySchedule.value.todayItems) ? todaySchedule.value.todayItems : [])

const headline = computed(() => loading.value ? '正在核对课程与本人办理进度…' : accessError.value ? '当前数据访问权限需要重新核对。' : partialError.value ? '部分数据读取失败，已保留其他真实任务，请先核对后再安排办理。' : tasks.value.length
  ? `还有 ${tasks.value.length} 类教务事项需要处理，点击可直接进入对应页面。`
  : '当前没有紧急教务任务，可以查询课表、成绩和学分。')


function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.batches || data.records || data.changes || data.applications || data.distributions)) || []
}
function pendingRows(rows) {
  const done = new Set(['DONE', 'COMPLETED', 'APPROVED', 'REGISTERED', 'SUBMITTED', 'PUBLISHED', 'CLOSED'])
  return (rows || []).filter((row) => !done.has(String(row.registrationStatus || row.status || '').toUpperCase()))
}
function actionableEvaluationRows(data) {
  return rowsOf(data).filter((row) => row && row.canSubmit === true && row.submitted !== true)
}
function withQuery(path, params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''))
  return query.size ? `${path}?${query.toString()}` : path
}
function go(path) { router.push(path || '/academic') }

async function load() {
  loading.value = true
  academicSummary.value = {}; recentRecords.value = []
  tasks.value = []; overview.value = []; todaySchedule.value = {}; accessError.value = ''; scheduleError.value = ''
  partialError.value = false
  failedSources.value = []
  const sourceNames = ['学期注册', '学生评教', '学业预警', '缓考申请', '补考重修资格', '今日课表', '选课记录', '正式成绩', '考试安排', '学籍异动', '教材签收', '毕业审核']
  const read = await readStudentAcademicSnapshot(guard, () => Promise.allSettled([
    portalApi.academicRegistration(),
    portalApi.academicEvaluationTasks(),
    portalApi.academicWarning(),
    portalApi.academicExamDefer(),
    portalApi.academicMakeupOptions(),
    portalApi.academicSchedule(),
    portalApi.academicSelectionRecords(),
    portalApi.academicTranscript(),
    portalApi.academicExam(),
    portalApi.academicStatus(),
    portalApi.academicTextbook(),
    portalApi.academicGraduationAudit()
  ]), 'academic-home')
  if (read.stale) return
  if (!read.ok) {
    accessError.value = academicErrorMessage(read.error, '学业总览读取失败，请稍后重试')
    loading.value = false
    return
  }
  const results = read.value
  const denied = results.find((result) => result.status === 'rejected' && academicErrorKind(result.reason) === 'forbidden')
  if (denied) { accessError.value = academicErrorMessage(denied.reason); loading.value = false; return }
  partialError.value = results.some((result) => result.status === 'rejected')
  failedSources.value = results.map((result, index) => result.status === 'rejected' ? sourceNames[index] : '').filter(Boolean)
  const val = (index, fallback = {}) => results[index].status === 'fulfilled' ? (results[index].value || fallback) : fallback
  const registration = pendingRows(rowsOf(val(0)))
  const evaluation = actionableEvaluationRows(val(1))
  const warnings = pendingRows(rowsOf(val(2)))
  const deferrals = rowsOf(val(3)).filter((row) => String(row.status || '').toUpperCase() === 'RETURNED')
  const makeup = val(4, { retakeOptions: [], exemptionOptions: [] })

  const next = []
  if (registration.length) {
    const first = registration[0]
    next.push({ key: `registration-${first.batchId}`, icon: '🪪', title: first.batchName || '完成学期注册',
      description: `该批次尚未完成 · ${first.blockReason || '请在办理窗口内完成注册'}`,
      badge: `${registration.length}项`, tone: 'warn', route: withQuery('/academic/registration', { batchId: first.batchId }) })
  }
  if (evaluation.length) {
    const first = evaluation[0]
    next.push({ key: `evaluation-${first.taskId}`, icon: '⭐', title: first.courseName || '完成学生评教',
      description: `${first.teacherName || '授课教师'} · 匿名提交后不可重复提交`,
      badge: `${evaluation.length}门`, tone: 'primary', route: withQuery('/academic/evaluation', { taskId: first.taskId }) })
  }
  if (warnings.length) {
    const first = warnings[0]
    next.push({ key: `warning-${first.warningId || first.id}`, icon: '⚠️', title: first.reason || first.warningName || '查看学业预警',
      description: `${first.levelLabel || first.level || '预警'} · ${first.responsibleTeacherName || first.teacherName || first.owner || '责任老师待确认'}`,
      badge: `${warnings.length}条`, tone: 'danger', route: withQuery('/academic/warning', { warningId: first.warningId || first.id }) })
  }
  if (deferrals.length) {
    const first = deferrals[0]
    next.push({ key: `defer-${first.deferId || first.id}`, icon: '🗓', title: first.courseName || '补充缓考材料',
      description: first.reviewNote || first.returnReason || '申请已退回，请按处理意见补充',
      badge: `${deferrals.length}项`, tone: 'warn', route: withQuery('/academic/exam', { tab: 'records', deferId: first.deferId || first.id }) })
  }
  const retakeCount = (makeup.retakeOptions || []).length
  if (retakeCount) {
    const first = makeup.retakeOptions[0]
    const optionId = first.gradeId || first.sourceId || first.acadGradeId || first.id
    next.push({ key: `makeup-${optionId}`, icon: '📝', title: first.courseName || '处理补考重修',
      description: `${first.termCode || '原修学期待确认'} · 当前有效未通过课程可报名`,
      badge: `${retakeCount}门`, tone: 'warn', route: withQuery('/academic/makeup', { tab: 'retake', optionId }) })
  }
  todaySchedule.value = val(5)
  scheduleError.value = results[5].status === 'rejected' ? academicErrorMessage(results[5].reason, '今日课表读取失败') : ''
  const selectionRecords = rowsOf(val(6))
  const transcript = val(7)
  academicSummary.value = transcript
  recentRecords.value = selectionRecords.slice().sort((a, b) => String(b.updatedAt || b.createdAt || b.operatedAt || '').localeCompare(String(a.updatedAt || a.createdAt || a.operatedAt || ''))).slice(0, 3)
  const statusData = val(9)
  const textbookRecords = rowsOf(val(10))
  const unsignedBooks = textbookRecords.filter(row => !row.signedAt && !row.receivedAt && ['PENDING', 'DISTRIBUTED', 'ISSUED'].includes(String(row.status || row.signStatus || '').toUpperCase()))
  if (unsignedBooks.length) next.push({ key: 'textbook-receipt', title: `${unsignedBooks.length} 项教材待签收`, description: '实际领到教材后再确认签收', tone: 'warn', route: '/academic/textbook' })
  const audit = val(11)
  const unavailable = (index, value) => results[index].status === 'rejected' ? '读取失败' : value
  const pendingLottery = selectionRecords.filter((row) => row.status === 'PENDING_LOTTERY').length
  overview.value = [
    { title: '选课进度', value: unavailable(6, pendingLottery ? `${pendingLottery} 门等待抽签` : `${selectionRecords.filter((row) => ['SELECTED', 'LOCKED'].includes(row.status)).length} 门已取得名额`), next: '核对报名与正式名额', route: '/academic/selection' },
    { title: '考试安排', value: unavailable(8, `${rowsOf(val(8)).length} 项安排可查`), next: '查看时间、考场与缓考进度', route: '/academic/exam' },
    { title: '正式成绩', value: unavailable(7, `${rowsOf(transcript).length} 门已发布`), next: '核对成绩与需补救课程', route: '/academic/grades' },
    { title: '学期注册', value: unavailable(0, registration.length ? `${registration.length} 个批次待核对` : rowsOf(val(0)).length ? '当前批次已登记' : '暂无注册批次'), next: '核对注册条件与实际状态', route: '/academic/registration' },
    { title: '学籍异动', value: unavailable(9, `${rowsOf(statusData).length} 条申请可查`), next: '查看本人学籍与审批进度', route: '/academic/status' },
    { title: '教材签收', value: unavailable(10, `${textbookRecords.filter((row) => !row.signedAt && !row.receivedAt && ['PENDING', 'DISTRIBUTED', 'ISSUED'].includes(String(row.status || row.signStatus || '').toUpperCase())).length} 项待签收`), next: '领取教材后再确认签收', route: '/academic/textbook' },
    { title: '学业预警', value: unavailable(2, warnings.length ? `${warnings.length} 项需要关注` : '暂无待处理预警'), next: '核对原因与处理要求', route: '/academic/warning' },
    { title: '毕业进度', value: unavailable(11, audit.progress?.items?.length ? `${audit.progress.items.filter((item) => item.result !== 'PASS').length} 项待进一步核对` : '审核证据待提供'), next: '查看缺口与正式审核结论', route: '/academic/graduation' }
  ]
  tasks.value = next
  loading.value = false
}

onMounted(load)
onBeforeUnmount(() => guard.dispose())

function lessonStart(lesson) { return lesson.startTime || todaySchedule.value.timeBands?.find(band => Number(band.slotNo) === Number(lesson.slotNo))?.startTime || '时间待定' }
function lessonSlot(lesson) { return lesson.slotLabel || (lesson.slotNo ? '第' + lesson.slotNo + '节' : '节次待定') }
function taskIcon(task) { return task.key.startsWith('registration') ? 'id-card' : task.key.startsWith('evaluation') ? 'star' : task.key.startsWith('warning') ? 'triangle-exclamation' : 'book-open' }
function selectionState(status) { return ({PENDING_LOTTERY:'已报名等待抽签',SELECTED:'已取得名额',LOCKED:'名单锁定',LOTTERY_LOST:'未中签',DROPPED:'已退',COURSE_CANCELLED:'课程取消'})[status] || '结果待确认' }
</script>
<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.wide-action{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:16px;border-radius:10px;background:var(--soft)}.wide-action p{color:var(--muted);font-size:13px;margin-top:4px}.card-body>.muted{padding:14px 0;font-size:13px}.iconbox .prototype-icon{width:22px;height:22px}@media(max-width:760px){.wide-action{align-items:stretch;flex-direction:column}.metrics-inline{gap:14px}.metrics-inline .metric{padding-right:14px}.event{grid-template-columns:58px 1fr}.event>.btn{grid-column:2;justify-self:start}}
</style>
