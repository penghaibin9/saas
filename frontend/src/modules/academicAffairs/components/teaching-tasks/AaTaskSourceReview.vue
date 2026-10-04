<template>
  <section class="aa-source-review" aria-label="重复开课来源核对">
    <header><div><h3>重复开课来源核对</h3><p>对照两条教学任务的正式来源与执行条件；本页仅核对，不改变任务或确认承接。</p></div><button type="button" @click="$emit('close')">关闭核对</button></header>
    <label v-if="otherTasks.length > 1" class="aa-source-review__choice">选择另一条比较任务
      <select v-model="selectedOtherTaskId" aria-label="选择另一条比较任务"><option value="">请选择比较任务</option><option v-for="task in otherTasks" :key="task.taskId" :value="String(task.taskId)">{{ task.label }}</option></select>
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
            <div><dt>来源培养方案</dt><dd>{{ task.sourceProgramName || '待核对' }}</dd></div>
            <div><dt>形成方式</dt><dd>{{ task.formationModeLabel || '待核对' }}</dd></div>
            <div><dt>开课序号 / 学分</dt><dd>{{ task.openTermNo ?? '待核对' }} / {{ task.credit ?? '待核对' }}</dd></div>
            <div><dt>周学时 / 总学时</dt><dd>{{ task.weeklyHours ?? '待核对' }} / {{ task.totalHours ?? '待核对' }}</dd></div>
            <div><dt>授课周次</dt><dd>第 {{ task.startWeek ?? '待核对' }} 至 {{ task.endWeek ?? '待核对' }} 周</dd></div>
            <div><dt>任课教师</dt><dd>{{ task.teacherName || '待核对' }} · {{ task.teacherIdentityProven === true ? '正式身份已核对' : '正式身份待核对' }}</dd></div>
            <div><dt>名单人数</dt><dd>{{ task.rosterCount ?? '待核对' }}</dd></div>
          </dl>
        </article>
      </div>
      <ul class="aa-source-review__checks"><li v-for="check in result.checks" :key="check.code"><strong>{{ check.label }}：{{ check.status === 'PASS' ? '通过核对' : '存在阻断' }}</strong><p>{{ check.message }}</p></li></ul>
      <footer><strong>{{ result.nextStep?.label || '由责任学院继续核对' }}</strong><p>{{ result.nextStep?.description || '请按正式教学任务流程核对差异。' }}</p></footer>
    </div>
  </section>
</template>

<script>
import { teachingTaskWorkbenchApi } from '../../api/teaching-task-workbench.api.js'

export default {
  name: 'AaTaskSourceReview',
  props: { taskId: { type: String, required: true }, termId: { type: String, default: '' }, otherTasks: { type: Array, default: () => [] }, contextKey: { type: String, required: true } },
  emits: ['close'],
  data() { return { selectedOtherTaskId: this.otherTasks.length === 1 ? String(this.otherTasks[0].taskId) : '', result: null, state: 'select', error: '', requestSeq: 0, disposed: false } },
  computed: { reviewKey() { return JSON.stringify([this.contextKey, this.termId, this.taskId, this.selectedOtherTaskId]) } },
  watch: { reviewKey: { immediate: true, handler() { this.load() } } },
  beforeUnmount() { this.disposed = true; this.requestSeq++; this.result = null },
  methods: {
    async load() {
      const seq = ++this.requestSeq, key = this.reviewKey
      const current = () => !this.disposed && seq === this.requestSeq && key === this.reviewKey
      this.result = null; this.error = ''; this.state = 'select'
      if (!this.taskId || !this.selectedOtherTaskId || this.selectedOtherTaskId === this.taskId || !this.otherTasks.some(task => String(task.taskId) === this.selectedOtherTaskId)) return
      this.state = 'loading'
      try {
        const response = await teachingTaskWorkbenchApi.getSourceReview(this.taskId, this.selectedOtherTaskId)
        if (!current()) return
        if (response.code !== 0) throw new Error(response.message || '来源核对读取失败，请重新读取')
        const result = response.data
        if (result?.reviewOnly !== true || !['CHECKED', 'BLOCKED'].includes(result.status) || !Array.isArray(result.taskIds) || result.taskIds.length !== 2 || !result.taskIds.includes(this.taskId) || !result.taskIds.includes(this.selectedOtherTaskId) || (this.termId && String(result.termId) !== this.termId)) throw new Error('返回的核对对象与当前任务或学期不一致，请重新读取')
        this.result = result; this.state = 'ready'
      } catch (error) {
        if (!current()) return
        this.result = null; this.error = error?.message || '来源核对读取失败，请重新读取'; this.state = 'error'
      }
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
.aa-source-review__blocked { color: #a33b22; }
.aa-source-review__checks { padding-left: 22px; }
.aa-source-review footer { border-top: 1px solid #dbe3ed; padding-top: 14px; }
@media (max-width: 760px) { .aa-source-review__tasks { grid-template-columns: 1fr; } .aa-source-review header { flex-wrap: wrap; } }
</style>
