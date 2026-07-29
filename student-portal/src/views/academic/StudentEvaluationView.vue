<template>
  <div class="sp-page evaluation-page">
    <section class="evaluation-hero">
      <div>
        <div class="evaluation-hero__eyebrow">教务学业 · 学生评教</div>
        <h1>本人课程匿名评价</h1>
        <p>仅展示本人正式教学班内、教务处已发布的匿名评教任务。提交后不可重复提交。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新任务' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人评教任务…" />
    <section v-else-if="error" class="sp-card evaluation-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>
    <StateBlock
      v-else-if="!tasks.length"
      type="empty"
      :text="worklist.note || '暂无已发布的本人评教任务'"
    />

    <template v-else>
      <section class="evaluation-summary">
        <article class="summary-card">
          <span>全部任务</span><b>{{ tasks.length }}</b>
        </article>
        <article class="summary-card" :class="{ 'is-action': pendingCount > 0 }">
          <span>待我提交</span><b>{{ pendingCount }}</b>
        </article>
        <article class="summary-card">
          <span>本人已提交</span><b>{{ completedCount }}</b>
        </article>
      </section>

      <section class="task-list">
        <article v-for="task in tasks" :key="task.taskId" class="sp-card task-card">
          <header class="task-card__head">
            <div>
              <strong>{{ task.courseName || '课程名称待补充' }}</strong>
              <span>{{ task.teacherName || '授课教师待补充' }} · {{ task.batchName || '评教批次' }}</span>
            </div>
            <StatusTag :text="taskStatusText(task)" :tone="taskStatusTone(task)" />
          </header>

          <div v-if="task.submitted" class="task-card__done">
            本人已完成匿名提交。系统只返回完成状态，不回传答卷内容或个人身份。
          </div>

          <div v-else-if="task.canSubmit" class="task-card__form">
            <label>
              <span>综合评分（0–100）</span>
              <input
                v-model.number="drafts[task.taskId].score"
                class="sp-inp"
                type="number"
                min="0"
                max="100"
                step="1"
                inputmode="decimal"
              />
            </label>
            <label>
              <span>意见建议（选填，最多 200 字）</span>
              <textarea
                v-model.trim="drafts[task.taskId].comment"
                class="sp-inp"
                maxlength="200"
                placeholder="请填写与课程教学相关的具体建议"
              />
            </label>
            <div class="task-card__actions">
              <span>提交前请确认分数；匿名答卷提交后不可重复提交。</span>
              <button
                class="sp-btn"
                type="button"
                :disabled="submitting === task.taskId || !canSubmit(task)"
                @click="submit(task)"
              >
                {{ submitting === task.taskId ? '提交中…' : '匿名提交' }}
              </button>
            </div>
          </div>

          <div v-else class="task-card__closed">
            当前任务不可提交：{{ windowStatusText(task.windowStatus) }}。
          </div>
        </article>
      </section>

      <section class="sp-card evaluation-note">
        <strong>匿名边界</strong>
        <span>页面不展示班级累计提交人数，不提供答卷回看，也不允许使用姓名、学号或账号作为评教凭据。</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const submitting = ref('')
const worklist = ref({ list: [], total: 0, pending: 0 })
const drafts = reactive({})

const tasks = computed(() => Array.isArray(worklist.value.list) ? worklist.value.list : [])
const pendingCount = computed(() => tasks.value.filter((task) => task.canSubmit === true && task.submitted !== true).length)
const completedCount = computed(() => tasks.value.filter((task) => task.submitted === true).length)

function ensureDraft(task) {
  const key = String(task.taskId || '')
  if (!key || drafts[key]) return
  drafts[key] = { score: 90, comment: '' }
}

function windowStatusText(status) {
  const map = {
    DRAFT: '尚未发布',
    PUBLISHED: '等待开放',
    OPEN: '窗口开放中',
    CLOSED: '窗口已关闭',
    RESULT_READY: '结果核算中',
    ARCHIVED: '已归档'
  }
  return map[String(status || '').toUpperCase()] || '窗口未开放'
}

function taskStatusText(task) {
  if (task.submitted) return '本人已提交'
  if (task.canSubmit) return '待提交'
  return windowStatusText(task.windowStatus)
}

function taskStatusTone(task) {
  if (task.submitted) return 'success'
  if (task.canSubmit) return 'primary'
  return 'default'
}

function canSubmit(task) {
  if (!task || task.canSubmit !== true || task.submitted === true) return false
  const draft = drafts[String(task.taskId || '')]
  const score = Number(draft && draft.score)
  return Number.isFinite(score) && score >= 0 && score <= 100
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await portalApi.academicEvaluationTasks()
    worklist.value = data || { list: [], total: 0, pending: 0 }
    for (const task of tasks.value) ensureDraft(task)
  } catch (e) {
    error.value = e?.message || '评教任务读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function submit(task) {
  if (!canSubmit(task) || submitting.value) return
  const key = String(task.taskId)
  const draft = drafts[key]
  submitting.value = key
  try {
    const score = Number(draft.score)
    await portalApi.academicEvaluationSubmit({
      taskId: task.taskId,
      objectiveScore: score,
      answers: { overall: score },
      comment: String(draft.comment || '').trim() || undefined
    })
    ui.notify('已匿名提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '评教提交失败')
  } finally {
    submitting.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.evaluation-page { max-width: 1080px; margin: 0 auto; }
.evaluation-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.evaluation-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.evaluation-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.evaluation-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.evaluation-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.evaluation-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--t1); font-size: 22px; }
.summary-card.is-action b { color: var(--pri); }
.task-list { display: grid; gap: 12px; }
.task-card { padding: 18px 20px; }
.task-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.task-card__head strong, .task-card__head span { display: block; }
.task-card__head strong { color: var(--t1); font-size: 15px; }
.task-card__head span { margin-top: 5px; color: var(--t3); font-size: 12px; }
.task-card__form { display: grid; gap: 12px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--line2); }
.task-card__form label > span { display: block; margin-bottom: 6px; color: var(--t2); font-size: 12px; font-weight: 600; }
.task-card__form input { max-width: 180px; }
.task-card__form textarea { min-height: 84px; resize: vertical; }
.task-card__actions { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.task-card__actions span { color: var(--t4); font-size: 12px; }
.task-card__done, .task-card__closed { margin-top: 14px; padding: 12px 14px; border-radius: 10px; font-size: 12.5px; }
.task-card__done { background: var(--ok-bg); color: var(--ok-fg); }
.task-card__closed { background: var(--draft-bg); color: var(--t3); }
.evaluation-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.evaluation-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 720px) {
  .evaluation-hero, .task-card__head, .task-card__actions { align-items: stretch; flex-direction: column; }
  .evaluation-summary { grid-template-columns: 1fr; }
  .task-card__actions .sp-btn { width: 100%; }
}
</style>
