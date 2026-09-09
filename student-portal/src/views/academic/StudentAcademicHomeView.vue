<template>
  <div class="sp-page aa-home">
    <section class="aa-home__hero">
      <div>
        <div class="aa-home__eyebrow">学生教务工作台</div>
        <h1>先处理任务，再查询信息</h1>
        <p>{{ headline }}</p>
      </div>
      <button class="aa-home__primary" type="button" @click="go(primaryRoute)">
        {{ primaryText }} →
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在汇总教务任务…" />
    <template v-else>
      <section class="sp-card aa-home__tasks">
        <div class="aa-home__section-head">
          <div>
            <strong>当前需要我处理</strong>
            <span>只展示会改变下一步的真实事项</span>
          </div>
          <button class="aa-home__refresh" type="button" @click="load">刷新</button>
        </div>
        <StateBlock v-if="!tasks.length" type="empty" text="当前没有待提交、待确认或待整改的教务任务" />
        <div v-else class="aa-home__task-list">
          <button v-for="task in tasks" :key="task.key" type="button" class="aa-home__task" @click="go(task.route)">
            <span class="aa-home__task-icon">{{ task.icon }}</span>
            <span class="aa-home__task-main">
              <strong>{{ task.title }}</strong>
              <small>{{ task.description }}</small>
            </span>
            <StatusTag :text="task.badge" :tone="task.tone" />
            <span class="aa-home__arrow">去处理 ›</span>
          </button>
        </div>
      </section>

      <section class="sp-card">
        <div class="aa-home__section-head">
          <div>
            <strong>独立教务页面</strong>
            <span>每项事务都有固定地址，可收藏、刷新和从消息直达</span>
          </div>
        </div>
        <div class="aa-home__grid">
          <button v-for="item in services" :key="item.route" type="button" class="aa-home__service" @click="go(item.route)">
            <span class="aa-home__service-icon">{{ item.icon }}</span>
            <span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span>
          </button>
        </div>
      </section>

      <section v-if="partialError" class="aa-home__warning" role="status">
        <strong>部分教务数据暂未加载</strong>
        <span>{{ failedSources.join('、') }}读取失败；已保留其他真实任务与全部固定入口，点击“刷新”重试。</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'

const router = useRouter()
const loading = ref(true)
const partialError = ref(false)
const failedSources = ref([])
const tasks = ref([])

const services = [
  { title: '我的课表', description: '当前学期七日课表', icon: '📅', route: '/academic/schedule' },
  { title: '我的成绩', description: '正式发布成绩与有效口径', icon: '📊', route: '/academic/grades' },
  { title: '网上选课', description: '选课、退课和已选记录', icon: '✅', route: '/academic/selection' },
  { title: '学期注册', description: '注册或申请暂缓', icon: '🪪', route: '/academic/registration' },
  { title: '考试与缓考', description: '正式考试安排与缓考申请', icon: '🗓', route: '/academic/exam' },
  { title: '补考与重修', description: '资格、报名和处理结果', icon: '📝', route: '/academic/makeup' },
  { title: '学籍与异动', description: '查看学籍、发起异动', icon: '📋', route: '/academic/status' },
  { title: '学分修读', description: '学分、绩点和达成情况', icon: '🎯', route: '/academic/credits' },
  { title: '学业预警', description: '原因、要求和处理进度', icon: '⚠️', route: '/academic/warning' },
  { title: '学生评教', description: '开放窗口内匿名评价', icon: '⭐', route: '/academic/evaluation' },
  { title: '成绩复查', description: '对已发布成绩申请复查', icon: '🔍', route: '/academic/recheck' },
  { title: '教材领用', description: '教材、费用与签收', icon: '📚', route: '/academic/textbook' },
  { title: '毕业自查', description: '逐项查看毕业条件证据', icon: '🎓', route: '/academic/graduation' }
]

const headline = computed(() => tasks.value.length
  ? `还有 ${tasks.value.length} 类教务事项需要处理，点击可直接进入对应页面。`
  : '当前没有紧急教务任务，可以查询课表、成绩和学分。')
const primaryRoute = computed(() => tasks.value[0]?.route || '/academic/schedule')
const primaryText = computed(() => tasks.value[0]?.title || '查看我的课表')

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.batches)) || []
}
function pendingRows(rows) {
  const done = new Set(['DONE', 'COMPLETED', 'APPROVED', 'REGISTERED', 'SUBMITTED', 'PUBLISHED', 'CLOSED'])
  return (rows || []).filter((row) => !done.has(String(row.status || row.registrationStatus || '').toUpperCase()))
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
  partialError.value = false
  failedSources.value = []
  const sourceNames = ['学期注册', '学生评教', '学业预警', '缓考申请', '补考重修资格']
  const results = await Promise.allSettled([
    portalApi.academicRegistration(),
    portalApi.academicEvaluationTasks(),
    portalApi.academicWarning(),
    portalApi.academicExamDefer(),
    portalApi.academicMakeupOptions()
  ])
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
      description: `${first.levelLabel || first.level || '预警'} · ${first.responsibleTeacherName || first.teacherName || '责任老师待确认'}`,
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
    const optionId = first.sourceId || first.acadGradeId || first.id
    next.push({ key: `makeup-${optionId}`, icon: '📝', title: first.courseName || '处理补考重修',
      description: `${first.termCode || '原修学期待确认'} · 当前有效未通过课程可报名`,
      badge: `${retakeCount}门`, tone: 'warn', route: withQuery('/academic/makeup', { tab: 'retake', optionId }) })
  }
  tasks.value = next
  loading.value = false
}

onMounted(load)
</script>

<style scoped>
.aa-home { display: flex; flex-direction: column; gap: 18px; }
.aa-home__hero { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 26px 28px; border: 1px solid #dbeafe; border-radius: 16px; background: linear-gradient(135deg,#eff6ff,#fff); }
.aa-home__eyebrow { color: #2563eb; font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.aa-home__hero h1 { margin: 7px 0 6px; color: var(--t1); font-size: 24px; }
.aa-home__hero p { margin: 0; color: var(--t3); font-size: 13px; }
.aa-home__primary { min-height: 42px; padding: 0 18px; border: 0; border-radius: 10px; background: #2563eb; color: #fff; cursor: pointer; font-weight: 600; white-space: nowrap; }
.aa-home__section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.aa-home__section-head strong { display: block; color: var(--t1); font-size: 16px; }
.aa-home__section-head span { display: block; margin-top: 4px; color: var(--t4); font-size: 12px; }
.aa-home__refresh { border: 0; background: transparent; color: #2563eb; cursor: pointer; }
.aa-home__task-list { display: flex; flex-direction: column; gap: 9px; }
.aa-home__task { display: flex; align-items: center; gap: 12px; width: 100%; padding: 13px 14px; border: 1px solid var(--line2); border-radius: 11px; background: #fff; cursor: pointer; text-align: left; }
.aa-home__task:hover { border-color: #93c5fd; background: #f8fbff; }
.aa-home__task-icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 9px; background: #eff6ff; }
.aa-home__task-main { flex: 1; min-width: 0; }
.aa-home__task-main strong, .aa-home__task-main small { display: block; }
.aa-home__task-main strong { color: var(--t1); font-size: 14px; }
.aa-home__task-main small { margin-top: 3px; color: var(--t4); font-size: 12px; }
.aa-home__arrow { color: #2563eb; font-size: 12px; }
.aa-home__grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 10px; }
.aa-home__service { display: flex; align-items: flex-start; gap: 10px; min-height: 82px; padding: 14px; border: 1px solid var(--line2); border-radius: 11px; background: #fff; cursor: pointer; text-align: left; }
.aa-home__service:hover { border-color: #93c5fd; box-shadow: 0 4px 14px rgba(37,99,235,.08); }
.aa-home__service-icon { font-size: 20px; }
.aa-home__service strong, .aa-home__service small { display: block; }
.aa-home__service strong { color: var(--t1); font-size: 13.5px; }
.aa-home__service small { margin-top: 5px; color: var(--t4); font-size: 11.5px; line-height: 1.45; }
.aa-home__warning { display: grid; gap: 4px; padding: 12px 14px; border: 1px solid #fed7aa; border-radius: 10px; background: #fff7ed; color: #9a3412; font-size: 12.5px; }
@media (max-width: 900px) { .aa-home__grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 620px) { .aa-home__hero { align-items: flex-start; flex-direction: column; padding: 20px; } .aa-home__primary { width: 100%; } .aa-home__grid { grid-template-columns: 1fr; } .aa-home__task { align-items: flex-start; flex-wrap: wrap; } }
</style>
