<template>
  <div data-academic-page class="sp-page academic-prototype evaluation-page">
    <AcademicPrototypeHeader :title="activeTask ? '填写课程评价' : '学生评教'" group="成绩与考试" :object="!!activeTask" description="评价本人正式教学班课程，逐门核对提交状态。" :loading="loading || !!submitting" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人评教任务…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="activeTask">
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>{{ activeTask.courseName }} · {{ activeTask.teacherName || '授课教师' }}。答案只属于本任务，切换课程不得沿用。</span></div>
        <section class="card pad"><form @submit.prevent="submit(activeTask)"><h2>请根据实际学习体验评价</h2>
          <div class="question"><label class="field"><b>本门课程总体评价（0—100分）</b><input v-model="drafts[String(activeTask.taskId)].score" class="input" type="number" min="0" max="100" step="1" placeholder="请填写你的评价分数" :disabled="activeTask.submitted || !activeTask.canSubmit" /></label></div>
          <label class="field"><span>补充意见（选填）</span><textarea v-model="drafts[String(activeTask.taskId)].comment" maxlength="500" placeholder="填写对本门课程的意见或建议" :disabled="activeTask.submitted || !activeTask.canSubmit" /></label>
          <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>请依据本门课程实际体验填写。提交后按学校既有匿名机制处理；当前提供总体评价。</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="activeTaskId = ''">返回评教任务</button><button class="btn primary" :disabled="!!submitting || !canSubmit(activeTask)">{{ submitting ? '提交中…' : '提交本门评价' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>只展示本人正式教学班的评教任务；提交后按既有匿名机制处理。</span></div>
        <StateBlock v-if="!tasks.length" type="empty" text="暂无本人评教任务" />
        <div class="grid-equal" :aria-label="'待评价 ' + pendingCount + ' 门，已提交 ' + completedCount + ' 门'"><section v-for="task in tasks" :key="task.taskId" class="card" :class="{ 'is-target': String(task.taskId) === focusTaskId }">
          <header class="card-head"><h2>{{ task.courseName || '本人课程' }}</h2></header><div class="card-body"><p class="muted">{{ task.teacherName || '教师待提供' }} · {{ task.termCode || task.termName || '学期待提供' }} · {{ task.windowEnd || task.endAt || task.deadline || '截止时间以学校通知为准' }}</p><div class="spacer14"></div><div class="row between"><span class="tag" :class="task.submitted ? 'green' : 'amber'">{{ taskStatusText(task) }}</span><button class="btn small" :class="{ primary: task.canSubmit && !task.submitted }" @click="activeTaskId = String(task.taskId)">{{ task.submitted ? '查看提交状态' : task.canSubmit ? '开始评价' : '查看任务' }}</button></div></div>
        </section></div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'

import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'evaluation')
const route = useRoute()
const focusTaskId = computed(() => String(route.query.taskId || ''))
const loading = ref(true)
const error = ref('')
const submitting = ref('')
const worklist = ref({ list: [], total: 0, pending: 0 })
const receipt = ref(null)
const receiptTone = ref('success')
const drafts = reactive({})
const activeTaskId = ref(String(route.query.taskId || ''))
const uncertainTaskIds = ref([])
const activeTask = computed(() => tasks.value.find(task => String(task.taskId) === activeTaskId.value))

const tasks = computed(() => Array.isArray(worklist.value.list) ? worklist.value.list : [])
const pendingCount = computed(() => tasks.value.filter((task) => task.canSubmit === true && task.submitted !== true).length)
const completedCount = computed(() => tasks.value.filter((task) => task.submitted === true).length)

function ensureDraft(task) {
  const key = String(task.taskId || '')
  if (!key || drafts[key]) return
  drafts[key] = { score: '', comment: '' }
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


function canSubmit(task) {
  if (!task || task.canSubmit !== true || task.submitted === true) return false
  if (uncertainTaskIds.value.includes(String(task.taskId || ''))) return false
  const draft = drafts[String(task.taskId || '')]
  if (!draft || draft.score === '' || draft.score == null) return false
  const score = Number(draft.score)
  return Number.isFinite(score) && score >= 0 && score <= 100
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => item.action === 'SUBMIT_EVALUATION')
  uncertainTaskIds.value = pending.map((item) => item.objectId)
  for (const reference of pending) {
    const formal = reference.ackId === reference.objectId ? tasks.value.find((item) => String(item.taskId || '') === reference.objectId) : null
    if (formal?.submitted === true && guard.completePersistentCommand(reference)) {
      receiptTone.value = 'success'
      receipt.value = academicReceipt({ title: '原匿名评价已通过正式任务确认', object: `${formal.courseName || '课程'} · ${formal.teacherName || '授课教师'}`, status: formal.status || '本人本任务已完成', operatedAt: formal.submittedAt, next: '请继续核对是否还有其他待评任务。' })
    } else {
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '原匿名评价结果待确认', object: formal ? `${formal.courseName || '课程'} · ${formal.teacherName || '授课教师'}` : '原评教任务', status: reference.ackId ? formal?.submitted === true ? '正式任务已读到，但本地待确认引用未能安全清理' : '当前任务尚未显示为本人已提交' : '原提交未取得服务端回执编号', next: '本页只会刷新本人正式任务，不会自动再次提交。' })
    }
  }
  uncertainTaskIds.value = guard.pendingCommands().filter((item) => item.action === 'SUBMIT_EVALUATION').map((item) => item.objectId)
}

async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicEvaluationTasks())
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '评教任务读取失败，请稍后重试')
    loading.value = false
    return false
  }
  worklist.value = read.value || { list: [], total: 0, pending: 0 }
  for (const task of tasks.value) ensureDraft(task)
  reconcilePersistentCommands()
  loading.value = false
  return true
}

async function submit(task) {
  if (!canSubmit(task) || submitting.value) return
  const key = String(task.taskId)
  const draft = drafts[key]
  const score = Number(draft.score)
  const command = guard.beginCommand({ taskId: key, score, comment: String(draft.comment || '').trim(), object: `${task.courseName || '课程'} · ${task.teacherName || '授课教师'}` })
  if (!await systemConfirm({ title: '确认提交匿名评价', message: `确认提交“${command.object}”的匿名评价？提交后不会向任课教师展示本人身份。`, confirmText: '提交匿名评价' })) return
  if (!guard.isCurrentCommand(command)) return
  const persistent = guard.preparePersistentCommand({ action: 'SUBMIT_EVALUATION', objectId: command.taskId })
  if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '匿名评价未发送', object: command.object, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
  submitting.value = command.taskId
  try {
    const result = await portalApi.academicEvaluationSubmit({
      taskId: command.taskId,
      objectiveScore: command.score,
      answers: { overall: command.score },
      comment: command.comment || undefined
    })
    if (!guard.isCurrentCommand(command)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.taskId)
    uncertainTaskIds.value = [...new Set([...uncertainTaskIds.value, command.taskId])]
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: '提交结果待正式任务确认', object: command.object, status: '正在读取本人正式评教任务', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    // 匿名评教的正式读侧明确标识“本人已交”。任务全局 submitted 或旧任务状态不能归因给本次提交。
    const formal = acknowledged?.ackId === command.taskId
      ? tasks.value.find((item) => String(item.taskId) === command.taskId)
      : null
    if (formal?.submitted === true && persistentCommandCleared(persistent)) {
      receiptTone.value = 'success'
      receipt.value = academicReceipt({ title: '本次匿名评价已提交并核对', object: command.object, status: formal.status || '本人本任务已完成', operatedAt: formal.submittedAt || result?.submittedAt, next: '仅当前任务完成；请继续核对是否还有其他待评任务。' })
      uncertainTaskIds.value = uncertainTaskIds.value.filter(value => value !== command.taskId)
      activeTaskId.value = ''
      markStudentAcademicFormClean()
    } else {
      uncertainTaskIds.value = [...new Set([...uncertainTaskIds.value, command.taskId])]
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '提交结果待正式任务确认', object: command.object, status: '当前任务尚未显示为已提交', next: '请保留当前填写并刷新任务；确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
    const kind = studentAcademicWriteErrorKind(e)
    if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
    if (kind === 'conflict' || kind === 'network') {
      if (kind === 'network' || kind === 'conflict') uncertainTaskIds.value = [...new Set([...uncertainTaskIds.value, command.taskId])]
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: kind === 'network' ? '提交结果待确认' : '评教任务状态已变化', object: command.object, status: '待重新读取任务确认', next: academicErrorMessage(e, '请保留当前填写并重新核对。') })
      await load()
    } else ui.notify(academicErrorMessage(e, '评教提交失败'))
  } finally {
    if (guard.isCurrentCommand(command)) submitting.value = ''
  }
}

function clearSensitive(e) {
  guard.invalidate()
  worklist.value = { list: [], total: 0, pending: 0 }; Object.keys(drafts).forEach((key) => delete drafts[key])
  receipt.value = null; activeTaskId.value = ''
  loading.value = false; submitting.value = ''
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.question{padding:18px 0;border-bottom:1px solid var(--line);margin-bottom:14px}.question input{max-width:260px}.form-notice{margin-top:14px}.is-target{border-color:var(--pri)}</style>
