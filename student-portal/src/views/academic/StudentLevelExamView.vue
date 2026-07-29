<template>
  <div class="sp-page level-page">
    <section class="level-hero">
      <div>
        <div class="level-hero__eyebrow">教务学业 · 等级考试</div>
        <h1>查看开放考试并办理本人报名</h1>
        <p>报名、取消和当前状态均由服务器校验。页面不会因按钮点击而先显示假成功，也不会允许代替他人报名。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingId" @click="load">
        {{ loading ? '加载中…' : '刷新考试' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取开放等级考试和本人报名…" />
    <section v-else-if="error" class="sp-card level-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>

    <template v-else>
      <section class="level-summary">
        <article class="summary-card"><span>开放考试</span><b>{{ exams.length }}</b></article>
        <article class="summary-card"><span>本人已报名</span><b>{{ registeredCount }}</b></article>
        <article class="summary-card" :class="{ 'is-action': actionableCount }"><span>当前可办理</span><b>{{ actionableCount }}</b></article>
      </section>

      <section class="sp-card list-card">
        <header class="section-head">
          <div><strong>等级考试列表</strong><span>按报名窗口和本人资格展示操作</span></div>
          <StatusTag :text="`${exams.length} 项`" tone="default" />
        </header>
        <StateBlock v-if="!exams.length" type="empty" :text="data.note || '暂无开放中的等级考试'" />
        <div v-else class="exam-list">
          <article v-for="exam in exams" :key="examId(exam)" class="exam-item">
            <header>
              <div>
                <strong>{{ exam.examName || exam.name || '等级考试' }}</strong>
                <span>{{ exam.examCode || '' }}{{ exam.levelName ? ` · ${exam.levelName}` : '' }}</span>
              </div>
              <StatusTag :text="registrationText(exam)" :tone="registrationTone(exam)" />
            </header>
            <dl>
              <div><dt>报名窗口</dt><dd>{{ dateTime(exam.registrationStart || exam.registerStart) }} 至 {{ dateTime(exam.registrationEnd || exam.registerEnd) }}</dd></div>
              <div><dt>考试时间</dt><dd>{{ dateTime(exam.examStart || exam.examDate) }}</dd></div>
              <div><dt>报名费用</dt><dd>{{ feeText(exam.feeAmount ?? exam.fee) }}</dd></div>
              <div><dt>资格说明</dt><dd>{{ exam.eligibilityNote || exam.requirement || '以学校报名规则实时校验为准' }}</dd></div>
              <div v-if="exam.registration?.registeredAt || exam.registeredAt"><dt>报名时间</dt><dd>{{ dateTime(exam.registration?.registeredAt || exam.registeredAt) }}</dd></div>
              <div v-if="blockReason(exam)"><dt>不可办理原因</dt><dd>{{ blockReason(exam) }}</dd></div>
            </dl>
            <footer>
              <span>{{ actionHint(exam) }}</span>
              <button
                v-if="isRegistered(exam) && canCancel(exam)"
                class="sp-btn sp-btn--ghost"
                type="button"
                :disabled="!!actingId"
                @click="cancel(exam)"
              >{{ actingId === examId(exam) ? '取消中…' : '取消本人报名' }}</button>
              <button
                v-else-if="!isRegistered(exam)"
                class="sp-btn"
                type="button"
                :disabled="!!actingId || !canRegister(exam)"
                @click="register(exam)"
              >{{ actingId === examId(exam) ? '报名中…' : canRegister(exam) ? '确认报名' : '暂不可报名' }}</button>
            </footer>
          </article>
        </div>
      </section>

      <section class="sp-card level-note">
        <strong>办理提示</strong>
        <span>报名成功不等同于缴费完成或准考资格确认。缴费、照片、考点和准考证要求以学校及考试主办方通知为准。</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const data = ref({})
const exams = computed(() => {
  const value = data.value
  if (Array.isArray(value)) return value
  return (value && (value.items || value.list || value.exams)) || []
})
const registeredCount = computed(() => exams.value.filter(isRegistered).length)
const actionableCount = computed(() => exams.value.filter((exam) => canRegister(exam) || canCancel(exam)).length)

function examId(exam) { return String(exam.examId || exam.id || exam.levelExamId || exam.examCode || exam.examName) }
function registration(exam) { return exam.registration || exam.myRegistration || {} }
function rawRegistrationStatus(exam) {
  return String(registration(exam).status || exam.registrationStatus || exam.myStatus || '').toUpperCase()
}
function isRegistered(exam) {
  const status = rawRegistrationStatus(exam)
  return exam.registered === true || ['REGISTERED', 'PAID', 'CONFIRMED', 'APPROVED'].includes(status)
}
function now() { return Date.now() }
function timestamp(value) {
  if (!value) return null
  const result = new Date(value).getTime()
  return Number.isFinite(result) ? result : null
}
function withinWindow(exam) {
  const start = timestamp(exam.registrationStart || exam.registerStart)
  const end = timestamp(exam.registrationEnd || exam.registerEnd)
  if (start != null && now() < start) return false
  if (end != null && now() > end) return false
  return true
}
function canRegister(exam) {
  if (isRegistered(exam) || !withinWindow(exam)) return false
  if (exam.canRegister === false || exam.eligible === false) return false
  const status = String(exam.status || '').toUpperCase()
  return !['CLOSED', 'CANCELLED', 'FINISHED'].includes(status)
}
function canCancel(exam) {
  if (!isRegistered(exam) || !withinWindow(exam)) return false
  if (exam.canCancel === false) return false
  return !['PAID', 'CONFIRMED', 'APPROVED'].includes(rawRegistrationStatus(exam))
}
function registrationText(exam) {
  const status = rawRegistrationStatus(exam)
  const map = { REGISTERED: '已报名', PAID: '已缴费', CONFIRMED: '资格已确认', APPROVED: '资格已确认', CANCELLED: '已取消', REJECTED: '未通过' }
  if (map[status]) return map[status]
  if (canRegister(exam)) return '可报名'
  if (!withinWindow(exam)) return '窗口未开放'
  return '暂不可报名'
}
function registrationTone(exam) {
  if (isRegistered(exam)) return 'success'
  if (canRegister(exam)) return 'primary'
  return 'default'
}
function blockReason(exam) {
  if (isRegistered(exam)) return ''
  if (exam.blockReason || exam.ineligibleReason) return exam.blockReason || exam.ineligibleReason
  if (!withinWindow(exam)) return '当前不在报名窗口内'
  if (exam.eligible === false) return '当前账号不符合本考试报名资格'
  return ''
}
function actionHint(exam) {
  if (isRegistered(exam)) return canCancel(exam) ? '报名窗口内可取消；取消后须重新校验资格。' : '当前报名已锁定，不能由学生端取消。'
  return canRegister(exam) ? '提交前请核对考试名称、等级和费用。' : blockReason(exam) || '请等待学校开放报名。'
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '待定' }
function feeText(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : '以学校通知为准'
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await portalApi.academicLevelExam() || {}
  } catch (e) {
    error.value = e?.message || '等级考试数据读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function register(exam) {
  const id = exam.examId || exam.id || exam.levelExamId
  if (!id || actingId.value || !canRegister(exam)) return
  const confirmed = window.confirm(`确认报名“${exam.examName || exam.name || '该等级考试'}”？`)
  if (!confirmed) return
  actingId.value = examId(exam)
  try {
    await portalApi.academicLevelRegister(id)
    ui.notify('等级考试报名成功')
    await load()
  } catch (e) {
    ui.notify(e?.message || '报名失败')
  } finally {
    actingId.value = ''
  }
}
async function cancel(exam) {
  const id = exam.examId || exam.id || exam.levelExamId
  if (!id || actingId.value || !canCancel(exam)) return
  const confirmed = window.confirm(`确认取消“${exam.examName || exam.name || '该等级考试'}”报名？`)
  if (!confirmed) return
  actingId.value = examId(exam)
  try {
    await portalApi.academicLevelCancel(id)
    ui.notify('报名已取消')
    await load()
  } catch (e) {
    ui.notify(e?.message || '取消报名失败')
  } finally {
    actingId.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.level-page { max-width: 1080px; margin: 0 auto; }
.level-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.level-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.level-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.level-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.level-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.level-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--t1); font-size: 22px; }
.summary-card.is-action b { color: var(--pri); }
.list-card { padding: 18px 20px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.exam-list { display: grid; gap: 10px; }
.exam-item { padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.exam-item > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.exam-item > header strong, .exam-item > header span { display: block; }
.exam-item > header strong { color: var(--t1); font-size: 14px; }
.exam-item > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.exam-item dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px 16px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.exam-item dl div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 8px; }
.exam-item dt { color: var(--t4); font-size: 12px; }
.exam-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
.exam-item footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 12px; }
.exam-item footer span { color: var(--t4); font-size: 12px; }
.level-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.level-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 720px) {
  .level-hero, .section-head, .exam-item > header, .exam-item footer { align-items: stretch; flex-direction: column; }
  .level-summary { grid-template-columns: 1fr; }
  .exam-item dl { grid-template-columns: 1fr; }
  .exam-item dl div { grid-template-columns: 1fr; gap: 3px; }
  .exam-item footer .sp-btn { width: 100%; }
}
</style>
