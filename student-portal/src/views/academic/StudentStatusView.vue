<template>
  <div class="sp-page status-page">
    <section class="status-hero">
      <div>
        <div class="status-hero__eyebrow">教务学业 · 学籍与异动</div>
        <h1>核对当前学籍并发起异动</h1>
        <p>学籍主档只读；异动申请独立提交并保留处理记录。页面不允许直接改写学院、专业、班级或在籍状态。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || submitting" @click="load">
        {{ loading ? '加载中…' : '刷新学籍' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人学籍与异动记录…" />
    <section v-else-if="error" class="sp-card status-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>
    <template v-else>
      <section class="sp-card profile-card">
        <header class="section-head">
          <div><strong>当前学籍</strong><span>来自学校学生主档，只读展示</span></div>
          <StatusTag :text="studentStatusText(status.studentStatus)" :tone="studentStatusTone(status.studentStatus)" />
        </header>
        <dl class="profile-grid">
          <div><dt>姓名</dt><dd>{{ status.realName || '—' }}</dd></div>
          <div><dt>学号</dt><dd>{{ status.studentNo || '—' }}</dd></div>
          <div><dt>学院</dt><dd>{{ status.collegeName || '—' }}</dd></div>
          <div><dt>专业</dt><dd>{{ status.majorName || '—' }}</dd></div>
          <div><dt>行政班</dt><dd>{{ status.className || '—' }}</dd></div>
          <div><dt>年级</dt><dd>{{ status.grade || '—' }}</dd></div>
        </dl>
        <div v-if="status.activeChange" class="profile-card__active">
          <strong>当前存在在途异动</strong>
          <span>{{ changeTypeText(status.activeChange.changeType) }} · {{ changeStatusText(status.activeChange.status) }}</span>
        </div>
      </section>

      <section class="sp-card apply-card">
        <header class="section-head">
          <div><strong>发起学籍异动</strong><span>只提交申请，不直接修改学籍主档</span></div>
          <StatusTag :text="status.activeChange ? '存在在途申请' : '可填写申请'" :tone="status.activeChange ? 'warn' : 'primary'" />
        </header>
        <form class="apply-form" @submit.prevent="submit">
          <label>
            <span>异动类型</span>
            <select v-model="form.changeType" class="sp-inp" :disabled="!!status.activeChange">
              <option value="">请选择异动类型</option>
              <option v-for="option in changeTypes" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </label>
          <label v-if="form.changeType === 'TRANSFER_MAJOR'">
            <span>目标专业</span>
            <select v-if="majorOptions.length" v-model="form.targetMajorId" class="sp-inp" :disabled="!!status.activeChange">
              <option value="">请选择目标专业</option>
              <option v-for="major in majorOptions" :key="major.majorId || major.id" :value="String(major.majorId || major.id)">
                {{ major.majorName || major.name || '未命名专业' }}{{ major.collegeName ? ` · ${major.collegeName}` : '' }}
              </option>
            </select>
            <input v-else v-model.trim="form.targetMajorId" class="sp-inp" placeholder="请输入目标专业编号" :disabled="!!status.activeChange" />
          </label>
          <label>
            <span>申请理由（至少 5 字，最多 300 字）</span>
            <textarea
              v-model.trim="form.reason"
              class="sp-inp"
              maxlength="300"
              placeholder="请说明申请原因和需要学校核实的情况"
              :disabled="!!status.activeChange"
            />
          </label>
          <footer>
            <span>提交后由学校按流程审核；材料要求和办理时限以学校制度为准。</span>
            <button class="sp-btn" type="submit" :disabled="!canSubmit || submitting || !!status.activeChange">
              {{ submitting ? '提交中…' : '提交异动申请' }}
            </button>
          </footer>
        </form>
      </section>

      <section class="sp-card records-card">
        <header class="section-head">
          <div><strong>我的异动记录</strong><span>仅展示本人申请和处理结果</span></div>
          <StatusTag :text="`${records.length} 条`" tone="default" />
        </header>
        <StateBlock v-if="!records.length" type="empty" text="暂无学籍异动记录" />
        <div v-else class="record-list">
          <article v-for="record in records" :key="record.changeId || record.id" class="record-item">
            <header>
              <div><strong>{{ changeTypeText(record.changeType) }}</strong><span>{{ dateTime(record.createdAt || record.appliedAt) }}</span></div>
              <StatusTag :text="changeStatusText(record.status)" :tone="changeStatusTone(record.status)" />
            </header>
            <dl>
              <div><dt>申请理由</dt><dd>{{ record.reason || '—' }}</dd></div>
              <div v-if="record.targetMajorName || record.targetMajorId"><dt>目标专业</dt><dd>{{ record.targetMajorName || record.targetMajorId }}</dd></div>
              <div v-if="record.reviewNote || record.rejectReason"><dt>处理意见</dt><dd>{{ record.reviewNote || record.rejectReason }}</dd></div>
            </dl>
          </article>
        </div>
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
const submitting = ref(false)
const status = ref({})
const records = ref([])
const majorOptions = ref([])
const form = reactive({ changeType: '', targetMajorId: '', reason: '' })

const changeTypes = [
  { value: 'SUSPEND', label: '休学' },
  { value: 'RESUME', label: '复学' },
  { value: 'TRANSFER_MAJOR', label: '转专业' },
  { value: 'RETAIN', label: '留级' },
  { value: 'WITHDRAW', label: '退学' }
]
const canSubmit = computed(() => {
  if (!form.changeType || form.reason.trim().length < 5) return false
  if (form.changeType === 'TRANSFER_MAJOR' && !String(form.targetMajorId || '').trim()) return false
  return true
})

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records || data.applications)) || []
}
function studentStatusText(value) {
  const map = { NORMAL: '在籍', REGISTERED: '在籍注册', SUSPENDED: '休学', WITHDRAWN: '退学', GRADUATED: '毕业', COMPLETED: '结业', PENDING_REGISTER: '待注册' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function studentStatusTone(value) {
  return ['NORMAL', 'REGISTERED'].includes(String(value || '').toUpperCase()) ? 'success' : 'warn'
}
function changeTypeText(value) {
  const found = changeTypes.find((item) => item.value === String(value || '').toUpperCase())
  return found?.label || value || '学籍异动'
}
function changeStatusText(value) {
  const map = { SUBMITTED: '已提交', PENDING: '审核中', APPROVED: '已通过', REJECTED: '未通过', RETURNED: '已退回', CANCELLED: '已撤销', COMPLETED: '已办结' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function changeStatusTone(value) {
  const statusValue = String(value || '').toUpperCase()
  if (['APPROVED', 'COMPLETED'].includes(statusValue)) return 'success'
  if (['REJECTED', 'CANCELLED'].includes(statusValue)) return 'danger'
  return 'warn'
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [statusResult, optionsResult] = await Promise.all([
      portalApi.academicStatus(),
      portalApi.academicTransferOptions()
    ])
    status.value = statusResult || {}
    records.value = rowsOf(statusResult)
    majorOptions.value = Array.isArray(optionsResult) ? optionsResult : (optionsResult?.items || optionsResult?.list || optionsResult?.majors || [])
  } catch (e) {
    error.value = e?.message || '学籍信息读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (!canSubmit.value || submitting.value || status.value.activeChange) return
  submitting.value = true
  try {
    await portalApi.academicStatusChange({
      changeType: form.changeType,
      reason: form.reason.trim(),
      ...(form.changeType === 'TRANSFER_MAJOR' ? { targetMajorId: form.targetMajorId } : {})
    })
    form.changeType = ''
    form.targetMajorId = ''
    form.reason = ''
    ui.notify('异动申请已提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '异动申请提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.status-page { max-width: 1080px; margin: 0 auto; }
.status-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.status-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.status-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.status-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.status-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.profile-card, .apply-card, .records-card { padding: 18px 20px; }
.apply-card, .records-card { margin-top: 14px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.profile-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
.profile-grid div { padding: 11px 12px; border-radius: 10px; background: var(--bg2); }
.profile-grid dt { color: var(--t4); font-size: 11px; }
.profile-grid dd { margin: 5px 0 0; color: var(--t1); font-size: 13px; font-weight: 600; }
.profile-card__active { display: grid; gap: 4px; margin-top: 12px; padding: 11px 13px; border-radius: 10px; background: var(--warn-bg); color: var(--warn-fg); font-size: 12px; }
.apply-form { display: grid; gap: 12px; }
.apply-form label > span { display: block; margin-bottom: 6px; color: var(--t2); font-size: 12px; font-weight: 600; }
.apply-form textarea { min-height: 86px; resize: vertical; }
.apply-form footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.apply-form footer span { color: var(--t4); font-size: 12px; }
.record-list { display: grid; gap: 10px; }
.record-item { padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.record-item > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.record-item > header strong, .record-item > header span { display: block; }
.record-item > header strong { color: var(--t1); font-size: 14px; }
.record-item > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.record-item dl { display: grid; gap: 7px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.record-item dl div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 12px; }
.record-item dt { color: var(--t4); font-size: 12px; }
.record-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
@media (max-width: 720px) {
  .status-hero, .section-head, .apply-form footer, .record-item > header { align-items: stretch; flex-direction: column; }
  .profile-grid { grid-template-columns: 1fr; }
  .apply-form footer .sp-btn { width: 100%; }
  .record-item dl div { grid-template-columns: 1fr; gap: 3px; }
}
</style>
