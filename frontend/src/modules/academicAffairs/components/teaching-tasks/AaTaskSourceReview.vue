<template>
  <section class="aa-source-review" aria-label="重复开课来源核对">
    <header><div><h3>重复开课来源核对</h3><p>对照两条教学任务的正式来源与执行条件；核对通过后，由校教务责任人正式确认来源承接，保留原教学执行和全部历史。</p></div><button type="button" :disabled="saving" @click="$emit('close')">关闭核对</button></header>
    <label v-if="otherTasks.length > 1" class="aa-source-review__choice">选择另一条比较任务
      <select v-model="selectedOtherTaskId" :disabled="saving" aria-label="选择另一条比较任务"><option value="">请选择比较任务</option><option v-for="task in otherTasks" :key="task.taskId" :value="String(task.taskId)">{{ task.label }}</option></select>
    </label>
    <p v-if="state === 'select'" role="status">请明确选择另一条任务后核对，系统不会替你选择执行任务。</p>
    <p v-else-if="state === 'loading'" role="status">正在读取两条任务的正式来源与执行条件…</p>
    <div v-else-if="state === 'error'" role="alert"><p>{{ error }}</p><button type="button" @click="load">重新读取</button></div>
    <div v-else-if="result" class="aa-source-review__result">
      <p :class="result.status === 'BLOCKED' ? 'aa-source-review__blocked' : ''"><strong>{{ result.status === 'BLOCKED' ? '核对存在阻断' : '本次核对完成' }}</strong> · {{ result.summary }}</p>
      <div class="aa-source-review__tasks">
        <article v-for="(task, index) in result.tasks" :key="task.taskId">
          <h4>比较任务{{ index + 1 }} · {{ task.courseName || '课程待核对' }}</h4>
          <dl>
            <div><dt>教学班</dt><dd>{{ task.teachingClassName || '待核对' }}</dd></div>
            <div><dt>来源培养方案</dt><dd>{{ task.sourceProgramName || '待核对' }} · 第{{ task.sourceProgramVersion ?? '待核对' }}版</dd></div>
            <div><dt>方案前后关系</dt><dd>{{ task.sourceRelationLabel || '版本关系待核对' }}</dd></div>
            <div><dt>形成方式</dt><dd>{{ task.formationModeLabel || '待核对' }}</dd></div>
            <div><dt>形成方式依据</dt><dd>{{ task.formationProofLabel || '来源尚未证明' }}</dd></div>
            <div><dt>开课序号 / 学分</dt><dd>{{ task.openTermNo ?? '待核对' }} / {{ task.credit ?? '待核对' }}</dd></div>
            <div><dt>周学时 / 总学时</dt><dd>{{ task.weeklyHours ?? '待核对' }} / {{ task.totalHours ?? '待核对' }}</dd></div>
            <div><dt>授课周次</dt><dd>第 {{ task.startWeek ?? '待核对' }} 至 {{ task.endWeek ?? '待核对' }} 周</dd></div>
            <div><dt>任课教师</dt><dd>{{ task.teacherName || '待核对' }} · {{ task.teacherIdentityProven === true ? '正式身份已核对' : '正式身份待核对' }}</dd></div>
            <div><dt>名单人数</dt><dd>{{ task.rosterCount ?? '待核对' }}</dd></div>
          </dl>
          <button v-if="task.sourceProgramCourseId" type="button" :disabled="saving" @click="openFormationProof(task)">核实形成方式依据</button>
          <AaFormationProof v-if="proofSourceId && proofSourceId === String(task.sourceProgramCourseId)" :key="reviewKey + ':' + proofSourceId" :program-course-id="proofSourceId" :context-key="reviewKey" @close="proofSourceId = ''" @confirmed="load" />
        </article>
      </div>
      <ul class="aa-source-review__checks"><li v-for="check in result.checks" :key="check.code"><strong>{{ check.label }}：{{ check.status === 'PASS' ? '通过核对' : '存在阻断' }}</strong><p>{{ check.message }}</p></li></ul>
      <section class="aa-source-review__handoff" aria-label="正式任务来源承接">
        <h4>正式任务来源承接</h4>
        <p>由原教学任务承接后继方案来源，原任务、正式课表、考勤、调停课及选课历史均保留；后继任务继续可查，但不再独立执行。不会删除历史，也不会把新任务编号代替原编号。</p>
        <article v-if="result.confirmedHandoff" role="status">
          <strong>已读取正式承接记录</strong><p>{{ result.confirmedHandoff.summary }}</p>
          <p>承接说明：{{ result.confirmedHandoff.reason }}</p><p>确认时间：{{ result.confirmedHandoff.confirmedAt }}</p>
        </article>
        <p v-else-if="!canConfirm">{{ result.handoffAction?.reason || '当前条件不允许正式承接，请由校教务责任人核对。' }}</p>
        <form v-if="canConfirm" @submit.prevent="openConfirmation">
          <p>保留执行：{{ taskLabel(result.handoffAction.executionTaskId) }}；来源接替：{{ taskLabel(result.handoffAction.successorTaskId) }}。</p>
          <label>承接说明（必填）<textarea v-model="reason" :disabled="saving || !!pendingCommand" maxlength="500" placeholder="说明核对依据与承接原因，至少4个字" /></label>
          <button type="submit" :disabled="saving || needsReload">{{ pendingCommand ? '按原请求重试确认' : '核对并确认正式承接' }}</button>
        </form>
        <p v-if="handoffError" role="alert" class="aa-source-review__blocked">{{ handoffError }}</p>
        <p v-if="receipt" role="status">{{ receipt }}</p>
        <button type="button" :disabled="saving" @click="load">重新读取并核对正式结果</button>
      </section>
      <footer><strong>{{ result.nextStep?.label || '由责任学院继续核对' }}</strong><p>{{ result.nextStep?.description || '请按正式教学任务流程核对差异。' }}</p></footer>
    </div>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认教学任务来源承接" :message="confirmMessage" confirm-text="正式确认承接" :submitting="saving" :confirm-disabled="!canConfirm || needsReload" @confirm="confirmHandoff" />
  </section>
</template>

<script>
import { teachingTaskWorkbenchApi } from '../../api/teaching-task-workbench.api.js'
import AaFormationProof from './AaFormationProof.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'

export default {
  name: 'AaTaskSourceReview',
  components: { AaFormationProof, AppConfirmDialog },
  props: { taskId: { type: String, required: true }, termId: { type: String, default: '' }, otherTasks: { type: Array, default: () => [] }, contextKey: { type: String, required: true } },
  emits: ['close', 'confirmed'],
  data() { return { selectedOtherTaskId: this.otherTasks.length === 1 ? String(this.otherTasks[0].taskId) : '', result: null, state: 'select', error: '', requestSeq: 0, disposed: false, proofSourceId: '', reason: '', saving: false, confirmVisible: false, confirmationBody: null, pendingCommand: null, commandKey: '', commandIdentity: '', needsReload: false, handoffError: '', receipt: '', submittedReceipt: null } },
  computed: {
    reviewKey() { return JSON.stringify([this.contextKey, this.termId, this.taskId, this.selectedOtherTaskId]) },
    canConfirm() {
      const a = this.result?.handoffAction
      return this.state === 'ready' && this.result?.status === 'CHECKED' && !this.result.confirmedHandoff && a?.allowed === true && this.validDirection(a)
    },
    confirmMessage() { return `保留${this.taskLabel(this.result?.handoffAction?.executionTaskId)}作为执行任务，承接${this.taskLabel(this.result?.handoffAction?.successorTaskId)}的方案来源。原课表和全部历史保留，后继任务不再独立执行。承接说明：${this.confirmationBody?.reason || this.reason.trim()}` }
  },
  watch: { reviewKey: { immediate: true, handler() { this.reason = ''; this.pendingCommand = null; this.commandKey = ''; this.commandIdentity = ''; this.submittedReceipt = null; this.receipt = ''; this.handoffError = ''; this.saving = false; this.needsReload = false; this.confirmVisible = false; this.confirmationBody = null; this.load() } } },
  beforeUnmount() { this.disposed = true; this.requestSeq++; this.result = null; this.pendingCommand = null; this.confirmVisible = false },
  methods: {
    taskLabel(id) { const task = this.result?.tasks?.find(t => t.taskId === id); return task ? `${task.sourceProgramName || '培养方案'}第${task.sourceProgramVersion ?? '待核对'}版 · ${task.courseName || '教学任务'}` : '当前任务待核对' },
    validDirection(a) { return !!a && typeof a.executionTaskId === 'string' && typeof a.successorTaskId === 'string' && /^[1-9]\d*$/.test(a.executionTaskId) && /^[1-9]\d*$/.test(a.successorTaskId) && a.executionTaskId !== a.successorTaskId && this.result.taskIds.includes(a.executionTaskId) && this.result.taskIds.includes(a.successorTaskId) && /^[a-fA-F0-9]{64}$/.test(a.expectedSourceFingerprint || '') },
    validReceipt(r) { return !!r && typeof r.handoffId === 'string' && /^[1-9]\d*$/.test(r.handoffId) && typeof r.termId === 'string' && (!this.termId || r.termId === this.termId) && r.termId === String(this.result?.termId || '') && typeof r.executionTaskId === 'string' && typeof r.successorTaskId === 'string' && r.executionTaskId !== r.successorTaskId && this.result?.taskIds?.includes(r.executionTaskId) && this.result?.taskIds?.includes(r.successorTaskId) && typeof r.reason === 'string' && typeof r.confirmedAt === 'string' && !!r.confirmedAt && typeof r.summary === 'string' },
    openFormationProof(task) { if (this.saving) return; const id = String(task?.sourceProgramCourseId || ''); this.proofSourceId = /^[1-9]\d*$/.test(id) ? id : '' },
    validate() { if (!this.canConfirm || this.needsReload) return '当前来源或责任条件已变化，请重新读取并核对'; if (this.reason.trim().length < 4 || this.reason.trim().length > 500) return '请填写4至500字的承接说明'; return '' },
    openConfirmation() {
      if (this.saving) return
      this.handoffError = this.validate(); if (this.handoffError) return
      const a = this.result.handoffAction
      this.confirmationBody = this.pendingCommand ? { ...this.pendingCommand } : { executionTaskId: a.executionTaskId, successorTaskId: a.successorTaskId, expectedSourceFingerprint: a.expectedSourceFingerprint, reason: this.reason.trim() }
      this.confirmVisible = true
    },
    async load() {
      const seq = ++this.requestSeq, key = this.reviewKey
      const current = () => !this.disposed && seq === this.requestSeq && key === this.reviewKey
      this.result = null; this.error = ''; this.state = 'select'; this.proofSourceId = ''; this.confirmVisible = false
      if (!this.taskId || !this.selectedOtherTaskId || this.selectedOtherTaskId === this.taskId || !this.otherTasks.some(task => String(task.taskId) === this.selectedOtherTaskId)) return
      this.state = 'loading'
      try {
        const response = await teachingTaskWorkbenchApi.getSourceReview(this.taskId, this.selectedOtherTaskId)
        if (!current()) return
        if (response.code !== 0) throw new Error(response.message || '来源核对读取失败，请重新读取')
        const result = response.data
        if (result?.reviewOnly !== true || !['CHECKED', 'BLOCKED'].includes(result.status) || !Array.isArray(result.taskIds) || result.taskIds.length !== 2 || !result.taskIds.includes(this.taskId) || !result.taskIds.includes(this.selectedOtherTaskId) || (this.termId && String(result.termId) !== this.termId)) throw new Error('返回的核对对象与当前任务或学期不一致，请重新读取')
        this.result = result
        if (result.confirmedHandoff && !this.validReceipt(result.confirmedHandoff)) throw new Error('正式承接回执与当前任务或学期不一致，请重新核对')
        this.state = 'ready'; this.needsReload = false
        if (this.pendingCommand && result.confirmedHandoff) {
          const r = result.confirmedHandoff, p = this.pendingCommand
          if (r.executionTaskId !== p.executionTaskId || r.successorTaskId !== p.successorTaskId || r.reason !== p.reason || (this.submittedReceipt && r.handoffId !== this.submittedReceipt.handoffId)) { this.needsReload = true; this.handoffError = '读回的承接结果与本次请求不一致，请核对正式记录'; return }
          this.pendingCommand = null; this.submittedReceipt = null; this.handoffError = ''; this.receipt = '正式承接已确认，并已重新读取一致的正式回执。'; this.$emit('confirmed', { ...r })
        } else if (this.submittedReceipt) { this.needsReload = true; this.receipt = '确认请求已返回，正式回执尚未读回；请重新读取核对，勿另建请求。' }
      } catch (error) {
        if (!current()) return
        this.result = null; this.error = error?.message || '来源核对读取失败，请重新读取'; this.state = 'error'
      }
    },
    async confirmHandoff() {
      if (this.saving || !this.confirmVisible) return
      this.handoffError = this.validate(); if (this.handoffError) return
      const a = this.result.handoffAction, saved = this.confirmationBody
      if (!saved || saved.executionTaskId !== a.executionTaskId || saved.successorTaskId !== a.successorTaskId || (!this.pendingCommand && saved.expectedSourceFingerprint !== a.expectedSourceFingerprint)) { this.needsReload = true; this.handoffError = '来源核对已变化，请重新读取后确认'; return }
      const key = this.reviewKey, seq = this.requestSeq
      const current = () => !this.disposed && key === this.reviewKey && seq === this.requestSeq
      const identity = JSON.stringify(saved)
      if (!this.pendingCommand) {
        if (this.commandIdentity !== identity || !this.commandKey) { this.commandIdentity = identity; this.commandKey = globalThis.crypto.randomUUID() }
        this.pendingCommand = { ...saved, idempotencyKey: this.commandKey }
      }
      const { executionTaskId, ...body } = this.pendingCommand
      this.saving = true; this.receipt = ''
      try {
        const response = await teachingTaskWorkbenchApi.confirmSourceHandoff(executionTaskId, { ...body })
        if (!current()) return
        if (response.code !== 0) {
          this.confirmVisible = false
          if (response.httpStatus === 409 || response.code === 'DATA_CONFLICT') { this.needsReload = true; this.pendingCommand = null; this.handoffError = `${response.message || '来源或执行条件已变化'}；已保留说明，请重新读取核对后再确认` }
          else this.handoffError = `${response.message || '确认结果暂不明确'}；已保留原请求，请先回读核对，重试沿用同一请求标识`
          return
        }
        if (!this.validReceipt(response.data) || response.data.executionTaskId !== executionTaskId || response.data.successorTaskId !== body.successorTaskId || response.data.reason !== body.reason) { this.needsReload = true; this.confirmVisible = false; this.handoffError = '确认返回的对象不一致，不能报完成；请重新读取正式结果'; return }
        this.submittedReceipt = response.data; this.confirmVisible = false; this.receipt = '确认请求已返回，正在重新读取正式回执。'
        await this.load()
      } catch (error) { if (current()) { this.confirmVisible = false; this.handoffError = `${error?.message || '网络暂不可用'}；已保留原请求，请先回读核对，重试沿用同一请求标识` } }
      finally { if (!this.disposed && key === this.reviewKey) this.saving = false }
    }
  }
}
</script>

<style scoped>
.aa-source-review { padding: 20px; border: 1px solid var(--border-200, #dbe3ed); border-radius: 10px; background: white; color: #253951; }
.aa-source-review header { display: flex; align-items: start; justify-content: space-between; gap: 16px; }
.aa-source-review h3, .aa-source-review h4 { margin: 0 0 8px; }
.aa-source-review p { margin: 8px 0; line-height: 1.6; }
.aa-source-review button, .aa-source-review select { min-height: 36px; padding: 6px 12px; border: 1px solid #c7d2e0; border-radius: 5px; background: white; color: #2d5cad; }
.aa-source-review__choice { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; align-items: center; }
.aa-source-review__tasks { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin: 16px 0; }
.aa-source-review article { padding: 16px; background: #f7f9fc; border-radius: 8px; overflow-wrap: anywhere; }
.aa-source-review dl { margin: 0; }
.aa-source-review dl div { display: grid; grid-template-columns: 120px minmax(0, 1fr); margin-top: 10px; gap: 12px; }
.aa-source-review dt { color: #68788c; }
.aa-source-review dd { margin: 0; }
.aa-source-review__handoff { margin: 16px 0; padding: 16px; background: #f7f9fc; border-radius: 8px; }
.aa-source-review__handoff label { display: grid; gap: 8px; }
.aa-source-review__handoff textarea { box-sizing: border-box; width: 100%; min-height: 88px; padding: 8px; border: 1px solid #c7d2e0; border-radius: 5px; }
.aa-source-review button:disabled { opacity: .6; cursor: not-allowed; }
.aa-source-review__blocked { color: #a33b22; }
.aa-source-review__checks { padding-left: 22px; }
.aa-source-review footer { border-top: 1px solid #dbe3ed; padding-top: 14px; }
@media (max-width: 760px) { .aa-source-review__tasks { grid-template-columns: 1fr; } .aa-source-review header { flex-wrap: wrap; } }
</style>
