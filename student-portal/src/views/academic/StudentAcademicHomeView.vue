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
        部分教务数据暂未加载，已保留可用入口；点击“刷新”重新汇总。
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
const tasks = ref([])

const services = [
  { title: '我的课表', description: '当前学期七日课表', icon: '📅', route: '/academic/schedule' },
  { title: '我的成绩', description: '正式发布成绩与有效口径', icon: '📊', route: '/academic/grades' },
  { title: '网上选课', description: '选课、退课和已选记录', icon: '✅', route: '/academic/selection' },
  { title: '学期注册', description: '注册或申请暂缓', icon: '🪪', route: '/academic/registration' },
  { title: '考试与缓考', description: '考试安排、缓考和补重修', icon: '🗓', route: '/academic/exam' },
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
function go(path) { router.push(path || '/academic') }

async function load() {
  loading.value = true
  partialError.value = false
  const results = await Promise.allSettled([
    portalApi.academicRegistration(),
    portalApi.academicEvaluationTasks(),
    portalApi.academicWarning(),
    portalApi.academicExamDefer(),
    portalApi.academicGradeRecheck(),
    portalApi.academicMakeupOptions()
  ])
  partialError.value = results.some((result) => result.status === 'rejected')
  const val = (index, fallback = {}) => results[index].status === 'fulfilled' ? (results[index].value || fallback) : fallback
  const registration = pendingRows(rowsOf(val(0)))
  const evaluation = rowsOf(val(1))
  const warnings = pendingRows(rowsOf(val(2)))
  const deferrals = rowsOf(val(3)).filter((row) => String(row.status || '').toUpperCase() === 'RETURNED')
  const rechecks = rowsOf(val(4)).filter((row) => String(row.status || '').toUpperCase() === 'RETURNED')
  const makeup = val(5, { retakeOptions: [], exemptionOptions: [] })

  const next = []
  if (registration.length) next.push({ key: 'registration', icon: '🪪', title: '完成学期注册', description: '存在尚未完成的注册批次', badge: `${registration.length}项`, tone: 'warn', route: '/academic/registration' })
  if (evaluation.length) next.push({ key: 'evaluation', icon: '⭐', title: '完成学生评教', description: '评教窗口已开放，提交后不可冒名修改', badge: `${evaluation.length}门`, tone: 'primary', route: '/academic/evaluation' })
  if (warnings.length) next.push({ key: 'warning', icon: '⚠️', title: '查看学业预警', description: '确认原因、责任老师和后续处理要求', badge: `${warnings.length}条`, tone: 'danger', route: '/academic/warning' })
  if (deferrals.length) next.push({ key: 'defer', icon: '🗓', title: '补充缓考材料', description: '存在退回待修改的缓考申请', badge: `${deferrals.length}项`, tone: 'warn', route: '/academic/exam' })
  if (rechecks.length) next.push({ key: 'recheck', icon: '🔍', title: '修改成绩复查申请', description: '存在退回待补充说明的复查申请', badge: `${rechecks.length}项`, tone: 'warn', route: '/academic/recheck' })
  const retakeCount = (makeup.retakeOptions || []).length
  if (retakeCount) next.push({ key: 'makeup', icon: '📝', title: '处理补考重修', description: '存在可报名的当前有效未通过课程', badge: `${retakeCount}门`, tone: 'warn', route: '/academic/exam' })
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
.aa-home__warning { padding: 12px 14px; border: 1px solid #fed7aa; border-radius: 10px; background: #fff7ed; color: #9a3412; font-size: 12.5px; }
@media (max-width: 900px) { .aa-home__grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 620px) { .aa-home__hero { align-items: flex-start; flex-direction: column; padding: 20px; } .aa-home__primary { width: 100%; } .aa-home__grid { grid-template-columns: 1fr; } .aa-home__task { align-items: flex-start; flex-wrap: wrap; } }
</style>
