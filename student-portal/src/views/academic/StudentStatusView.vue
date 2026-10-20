<template>
  <div data-academic-page class="sp-page academic-prototype status-page">
    <AcademicPrototypeHeader :title="applying ? '学籍异动申请' : '学籍与异动'" group="培养与毕业" :object="applying" description="以学校正式学籍为准，申请与生效结果分别查看。" :loading="loading || submitting" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取本人学籍与申请…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <template v-if="applying">
        <AcademicPrototypeSteps />
        <section class="card"><header class="card-head"><h2>从当前学籍发起</h2></header><form class="card-body" @submit.prevent="submit">
          <div class="form-grid"><label class="field"><span class="req">异动类型</span><select v-model="form.changeType"><option value="">请选择异动类型</option><option v-for="item in changeTypes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <label v-if="form.changeType === 'TRANSFER_MAJOR'" class="field"><span class="req">目标专业</span><select v-model="form.targetMajorId"><option value="">选择学校提供的有效专业</option><option v-for="item in majorOptions" :key="item.majorId || item.id" :value="String(item.majorId || item.id)">{{ item.majorName || item.name }}</option></select></label>
            <label v-else-if="form.changeType === 'TRANSFER_CLASS'" class="field"><span class="req">目标班级</span><select v-model="form.targetClassId"><option value="">选择学校提供的有效班级</option><option v-for="item in classOptions" :key="item.classId" :value="String(item.classId)">{{ item.className }}</option></select></label>
            <label class="field full"><span class="req">申请事由</span><textarea v-model.trim="form.reason" maxlength="300" placeholder="请说明异动事由（至少 5 字）" /></label></div>
          <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>{{ uncertainCommandKey ? '上一笔申请结果仍待服务器正式记录确认，请先刷新核对，不要重复提交。' : status.activeChange ? '已有在途申请，请先查看学校处理结果。' : '申请提交后进入学校受理，审批通过并正式生效后才会改变当前学籍。' }}</span></div>
          <footer class="form-foot"><button class="btn" type="button" @click="applying = false">返回学籍记录</button><button class="btn primary" :disabled="!canSubmit || submitting || !!status.activeChange">{{ submitting ? '提交中…' : '提交异动申请' }}</button></footer>
        </form></section>
      </template>
      <template v-else>
        <div class="grid2">
          <section class="card"><header class="card-head"><h2>本人当前学籍</h2></header><div class="card-body">
            <div class="row"><div class="student-avatar">{{ (status.realName || status.studentName || '本').slice(0,1) }}</div><div><h2>{{ status.realName || status.studentName || '本人' }}</h2><small>学号 {{ status.studentNo || '未提供' }}</small></div><span class="grow"></span><span class="tag" :class="studentStatusTone(status.studentStatus || status.status) === 'success' ? 'green' : 'amber'">{{ studentStatusText(status.studentStatus || status.status) }}</span></div>
            <dl class="definition"><dt>学院</dt><dd>{{ status.collegeName || '未提供' }}</dd><dt>专业</dt><dd>{{ status.majorName || '未提供' }}</dd><dt>行政班</dt><dd>{{ status.className || '未提供' }}</dd><dt>入学年级</dt><dd>{{ status.grade || status.enrollmentYear || '未提供' }}</dd><dt>当前事实</dt><dd>来源于学校权威学籍记录</dd></dl>
            <footer class="form-foot"><button class="btn primary" :disabled="!!status.activeChange" @click="applying = true">发起学籍异动</button></footer>
          </div></section>
          <section class="card"><header class="card-head"><h2>历史与在途申请</h2></header><div class="card-body">
            <div class="taskline"><div class="grow"><strong>本学期注册</strong><small>进入本人注册批次核对状态</small></div><RouterLink class="btn link small" to="/academic/registration">查看</RouterLink></div>
            <p v-if="!records.length" class="muted">暂无本人学籍异动申请。新申请正式生效前，不修改当前身份。</p>
            <article v-for="record in records" :key="record.changeId || record.id" class="taskline"><div class="grow"><strong>{{ changeTypeText(record.changeType) }}</strong><small>{{ record.reason || '申请事由未提供' }}</small><small v-if="record.reviewNote">处理意见：{{ record.reviewNote }}</small><small>提交时间 {{ dateTime(record.createdAt || record.submittedAt) }} · 生效时间 {{ dateTime(record.effectiveDate || record.effectiveAt) }}</small></div><span class="tag" :class="changeStatusTone(record.status) === 'success' ? 'green' : changeStatusTone(record.status) === 'danger' ? 'red' : 'amber'">{{ changeStatusText(record.status) }}</span></article>
          </div></section>
        </div>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>留级与保留学籍是不同状态；当前身份以学校正式生效记录为准。</span></div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'
import { createStudentAcademicCommandGuard, exactPositiveDecimalId, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'

import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session))
const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const status = ref({})
const records = ref([])
const majorOptions = ref([])
const classOptions = ref([])
const applying = ref(false)
const receipt = ref(null)
const receiptTone = ref('success')
const receiptChangeId = ref('')
const uncertainCommandKey = ref('')
const pendingStatusReference = ref(null)
const form = reactive({ changeType: '', targetMajorId: '', targetClassId: '', reason: '' })

const changeTypes = [
  { value: 'SUSPEND', label: '休学' },
  { value: 'RESUME', label: '复学' },
  { value: 'TRANSFER_MAJOR', label: '转专业' },
  { value: 'TRANSFER_CLASS', label: '转班' },
  { value: 'PRESERVE', label: '保留学籍' },
  { value: 'RETAIN', label: '留级' },
  { value: 'WITHDRAW', label: '退学' }
]
const canSubmit = computed(() => {
  if (uncertainCommandKey.value || !form.changeType || form.reason.trim().length < 5) return false
  if (form.changeType === 'TRANSFER_MAJOR' && (!exactPositiveDecimalId(form.targetMajorId) || !majorOptions.value.some((item) => exactPositiveDecimalId(item.majorId || item.id) === exactPositiveDecimalId(form.targetMajorId)))) return false
  if (form.changeType === 'TRANSFER_CLASS' && (!exactPositiveDecimalId(form.targetClassId) || !classOptions.value.some(item => exactPositiveDecimalId(item.classId) === exactPositiveDecimalId(form.targetClassId)))) return false
  return true
})

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.changes || data.items || data.list || data.records || data.applications)) || []
}
function studentStatusText(value) {
  const map = { NORMAL: '在籍', REGISTERED: '在籍注册', PRESERVED: '保留学籍', SUSPENDED: '休学', WITHDRAWN: '退学', GRADUATED: '毕业', COMPLETED: '结业', PENDING_REGISTER: '待注册' }
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
  const map = { SUBMITTED: '已提交', PENDING: '审核中', REVIEWING: '审核中', IN_REVIEW: '审批中', APPROVED: '审核通过', APPROVED_PENDING_EFFECTIVE: '已通过·待生效', EFFECTIVE: '已正式生效', REJECTED: '未通过', RETURNED: '已退回', CANCELLED: '已撤销', COMPLETED: '已办结' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function changeStatusTone(value) {
  const statusValue = String(value || '').toUpperCase()
  if (['APPROVED', 'EFFECTIVE', 'COMPLETED'].includes(statusValue)) return 'success'
  if (['REJECTED', 'CANCELLED'].includes(statusValue)) return 'danger'
  return 'warn'
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => Promise.all([
      portalApi.academicStatus(),
      portalApi.academicTransferOptions(),
      portalApi.profileEnrollment()
    ]), 'academic-status')
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '学籍信息读取失败，请稍后重试')
    loading.value = false
    return false
  }
  const [statusResult, optionsResult, profile] = read.value
  // Reuse the existing本人档案 reader; retain only the fields needed on this page.
  status.value = { realName: profile?.name, studentNo: profile?.studentNo, collegeName: profile?.collegeName, majorName: profile?.majorName, className: profile?.className, grade: profile?.grade, ...(statusResult || {}) }
  records.value = rowsOf(statusResult)
  status.value = { ...status.value, activeChange: statusResult?.activeChange || records.value.find((row) => ['PENDING', 'SUBMITTED', 'REVIEWING', 'IN_REVIEW'].includes(String(row.status).toUpperCase())) }
  classOptions.value = optionsResult?.classes || []
  majorOptions.value = Array.isArray(optionsResult) ? optionsResult : (optionsResult?.items || optionsResult?.list || optionsResult?.majors || [])
  loading.value = false
  resolvePendingStatus()
  syncReceiptFromFormal()
  return true
}
function syncReceiptFromFormal() {
  if (!receiptChangeId.value || pendingStatusReference.value) return false
  const formal = records.value.find(row => exactPositiveDecimalId(row.changeId || row.id) === receiptChangeId.value)
  if (!formal) return false
  receiptTone.value = ['REJECTED', 'CANCELLED'].includes(String(formal.status || '').toUpperCase()) ? 'danger' : 'success'
  receipt.value = academicReceipt({ title: '学籍异动正式状态已更新', object: changeTypeText(formal.changeType), status: changeStatusText(formal.status), operatedAt: formal.effectiveDate || formal.createdAt || formal.submittedAt, next: formal.status === 'EFFECTIVE' ? '当前学籍已按学校正式事实更新。' : '请继续在本页跟踪学校办理结果。', relatedTo: '/academic/registration', relatedLabel: '查看学期注册' })
  return true
}
function resolvePendingStatus() {
  const pending = pendingStatusReference.value
  if (!pending?.changeId || pending.identity !== studentAcademicIdentity(session)) return false
  const formal = records.value.find(row => exactPositiveDecimalId(row.changeId || row.id) === pending.changeId && String(row.changeType).toUpperCase() === pending.changeType)
  if (!formal || !['SUBMITTED', 'PENDING', 'REVIEWING', 'IN_REVIEW', 'APPROVED', 'APPROVED_PENDING_EFFECTIVE', 'EFFECTIVE', 'REJECTED', 'RETURNED', 'CANCELLED', 'COMPLETED'].includes(String(formal.status).toUpperCase())) return false
  receiptTone.value = 'success'
  receiptChangeId.value = pending.changeId
  receipt.value = academicReceipt({ title: '学籍异动申请已提交并核对', object: pending.object, status: changeStatusText(formal.status), operatedAt: formal.createdAt || formal.submittedAt, next: '当前学籍不会立即改变，请在本页跟踪审核和正式生效结果。', relatedTo: '/academic/registration', relatedLabel: '查看学期注册' })
  pendingStatusReference.value = null
  uncertainCommandKey.value = ''
  return true
}
async function submit() {
  if (!canSubmit.value || submitting.value || status.value.activeChange) return
  const payload = {
    changeType: form.changeType,
    reason: form.reason.trim(),
    ...(form.changeType === 'TRANSFER_MAJOR' ? { toMajorId: exactPositiveDecimalId(form.targetMajorId) } : {}),
    ...(form.changeType === 'TRANSFER_CLASS' ? { toClassId: exactPositiveDecimalId(form.targetClassId) } : {})
  }
  const object = changeTypeText(payload.changeType)
  const commandKey = [payload.changeType, payload.toMajorId || '', payload.toClassId || ''].join(':')
  const draft = JSON.stringify(form)
  const command = guard.beginCommand({ payload: Object.freeze({ ...payload }), object, commandKey })
  if (!await systemConfirm({ title: `确认提交${command.object}申请`, message: '提交后需以本人正式申请记录为准。', confirmText: '确认提交' })) return
  if (!guard.isCurrentCommand(command)) return
  submitting.value = true
  uncertainCommandKey.value = command.commandKey
  pendingStatusReference.value = { identity: command.identity, changeId: '', changeType: payload.changeType, object: command.object }
  try {
    const result = await portalApi.academicStatusChange(command.payload)
    if (!guard.isCurrentCommand(command)) return
    pendingStatusReference.value.changeId = exactPositiveDecimalId(result?.changeId || result?.id)
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '正在读取本人正式异动申请', next: '确认前不要重复提交。' })
    const readOk = await load()
    if (!guard.isCurrentCommand(command) || !readOk) return
    if (!pendingStatusReference.value) {
      if (JSON.stringify(form) === draft) {
        Object.assign(form, { changeType: '', targetMajorId: '', targetClassId: '', reason: '' }); applying.value = false
        markStudentAcademicFormClean()
      }
    } else {
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.object, status: '尚未读取到匹配的本人异动申请', next: '请刷新本页核对。确认前不要重复提交。' })
    }
  } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    const kind = studentAcademicWriteErrorKind(e)
    if (kind === 'forbidden') { clearSensitive(e); return }
    if (kind !== 'network') { pendingStatusReference.value = null; uncertainCommandKey.value = '' }
    receiptTone.value = 'waiting'
    receipt.value = academicReceipt({ title: kind === 'conflict' ? '学籍事实已变化' : kind === 'network' ? '申请结果待确认' : '申请未提交', object: command.object, status: kind === 'network' ? '待服务器记录确认' : '未完成', next: academicErrorMessage(e, kind === 'conflict' ? '已保留填写内容，请重新核对当前事实。' : '请核对填写内容后重试。') })

    if (kind === 'network' || kind === 'conflict') {
      await load()
    }
  } finally {
    if (guard.isCurrentCommand(command)) submitting.value = false
  }
}

function clearSensitive(e) {
  guard.invalidate()
  status.value = {}; records.value = []; majorOptions.value = []; classOptions.value = []; applying.value = false; Object.assign(form, { changeType: '', targetMajorId: '', targetClassId: '', reason: '' })
  receipt.value = null
  receiptChangeId.value = ''
  submitting.value = false
  loading.value = false
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.definition{margin:14px 0}.form-notice{margin-top:14px}.student-avatar{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:var(--priSoft);color:var(--pri);font-weight:700}</style>
