<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="student ? `分配选题 · ${student.name}` : '分配选题'"
    :subtitle="student ? `${student.studentNo} · ${student.className || '班级待确认'}` : '正在读取学生主档'"
    eyebrow="题目与选题 · 学生关系"
    purpose="把当前学生关联到一个已确认、未满员的真实题目；保存后服务器重新读取学生档案确认关系。"
    :status-text="submitting ? '保存中' : (student?.topicId ? '调整选题' : '待分配')"
    status-tone="warning"
    :back-to="backTo"
    :busy="submitting"
    @blocked-back="onBlockedBack"
  >
    <template #context>
      <div class="sat-context">
        <span><b>当前学生</b>{{ student ? `${student.name} · ${student.studentNo}` : '正在读取' }}</span>
        <span><b>当前批次</b>{{ batchLabel }}</span>
        <span><b>当前题目</b>{{ student?.topicTitle || '尚未分配' }}</span>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else class="ie-form sat-form" @submit.prevent="submit">
      <section class="sat-section ie-fld--full">
        <header>
          <span>01</span>
          <div><strong>核对当前业务对象</strong><small>只修改当前学生的选题关系，不修改题目主档。</small></div>
        </header>
        <div class="sat-current">
          <div><span>学生</span><strong>{{ student.name }}</strong><small>{{ student.studentNo }} · {{ student.className || '班级待确认' }}</small></div>
          <div><span>原题目</span><strong>{{ student.topicTitle || '尚未分配' }}</strong><small>{{ student.advisorName ? `指导教师：${student.advisorName}` : '指导教师待分配' }}</small></div>
        </div>
      </section>

      <section class="sat-section ie-fld--full">
        <header>
          <span>02</span>
          <div><strong>选择目标题目</strong><small>候选题目来自真实题目库，容量和确认状态由服务端最终校验。</small></div>
        </header>
        <div class="sat-section__body">
          <div class="ie-fld ie-fld--full">
            <span class="ie-lbl">目标题目 <i>*</i></span>
            <AppGraduationTopicPicker
              v-model="assignTopicId"
              :disabled="submitting"
              placeholder="按题目名 / 导师搜索已确认且未满员的题目"
            />
            <p class="ie-hint">页面只展示候选；提交时仍校验批次、题目状态、容量和学生当前阶段。</p>
          </div>
        </div>
      </section>

      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template v-if="student" #aside>
      <section class="sat-aside-card">
        <span>保存前检查</span>
        <ul>
          <li class="done"><b>✓</b><div><strong>真实学生主档已读取</strong><small>{{ student.studentNo }}</small></div></li>
          <li :class="{ done: Boolean(assignTopicId) }"><b>{{ assignTopicId ? '✓' : '2' }}</b><div><strong>已选择目标题目</strong><small>必填</small></div></li>
          <li :class="{ done: Boolean(batchLabel) }"><b>{{ batchLabel ? '✓' : '3' }}</b><div><strong>批次上下文已保留</strong><small>跨批写入由服务端拒绝</small></div></li>
        </ul>
      </section>
      <section class="sat-aside-card is-next">
        <span>保存后的下一步</span>
        <ol>
          <li>重新读取学生档案确认题目关系</li>
          <li>核对题目指导教师与学生导师</li>
          <li>进入任务书和过程指导</li>
        </ol>
      </section>
      <section class="sat-warning">
        <strong>不会自动改导师</strong>
        <p>调整题目不会静默覆盖导师关系；如需调导师，必须进入独立导师分配流程并保留原因。</p>
      </section>
    </template>

    <template v-if="student" #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !assignTopicId" @click="submit">
        {{ submitting ? '正在保存…' : (student.topicId ? '确认调整题目' : '确认分配题目') }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppGraduationTopicPicker } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationStudentAssignTopicView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppGraduationTopicPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      student: null,
      assignTopicId: '',
      formError: '',
      submitting: false,
      loadToken: 0
    }
  },
  computed: {
    safeReturnTo() {
      const raw = Array.isArray(this.$route.query.returnTo) ? this.$route.query.returnTo[0] : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : ''
    },
    backTo() {
      if (this.safeReturnTo) return this.safeReturnTo
      const panel = String(this.$route.query.returnPanel || 'topic')
      const query = new URLSearchParams({ panel })
      const batchId = this.$route.query.batchId || this.student?.batchId
      if (batchId) query.set('batchId', String(batchId))
      return `/admin/graduation/students?${query}`
    },
    batchLabel() {
      return String(this.$route.query.batchId || this.student?.batchName || this.student?.batchId || '当前批次')
    }
  },
  created() { this.load() },
  beforeUnmount() { ++this.loadToken },
  beforeRouteLeave(_to, _from, next) {
    if (this.submitting) {
      toast.info('选题关系正在保存，请等待服务器回执')
      next(false)
      return
    }
    next()
  },
  methods: {
    onBlockedBack() { toast.info('选题关系正在保存，请勿重复操作') },
    cancel() { if (!this.submitting) this.$router.push(this.backTo) },
    async load() {
      const id = String(this.$route.params.id || '')
      const batchId = String(this.$route.query.batchId || '')
      const token = ++this.loadToken
      this.loading = true
      this.error = ''
      try {
        const response = await gdStudentApi.getStudentDetail(id)
        if (token !== this.loadToken || id !== String(this.$route.params.id || '')) return false
        if (response.code !== 0) {
          this.error = response.message || '学生信息加载失败'
          return false
        }
        const studentBatchId = String(response.data?.batchId || '')
        if (batchId && studentBatchId && batchId !== studentBatchId) {
          this.error = '当前批次与学生上下文不一致，请返回名单重新选择学生'
          return false
        }
        this.student = response.data
        this.assignTopicId = response.data.topicId || ''
        return true
      } catch (error) {
        if (token === this.loadToken) this.error = error?.message || '学生信息加载失败'
        return false
      } finally {
        if (token === this.loadToken) this.loading = false
      }
    },
    async submit() {
      if (this.submitting) return
      this.formError = ''
      if (!this.student?.id) {
        this.formError = '学生信息无效，请返回重新选择'
        return
      }
      if (!this.assignTopicId) {
        this.formError = '请选择目标题目'
        return
      }
      const target = Object.freeze({
        studentId: String(this.student.id),
        topicId: String(this.assignTopicId),
        batchId: String(this.$route.query.batchId || this.student.batchId || ''),
        backTo: this.backTo
      })
      this.submitting = true
      try {
        const response = await gdStudentApi.assignTopic(target.studentId, { topicId: target.topicId })
        if (response.code !== 0) {
          this.formError = response.message || '选题分配失败'
          return
        }
        const latest = await gdStudentApi.getStudentDetail(target.studentId)
        const latestTopicId = String(latest.data?.topicId || '')
        if (latest.code !== 0 || latestTopicId !== target.topicId) {
          this.formError = '分配命令已返回，但学生档案尚未回读到目标题目；请返回名单刷新核对，勿重复提交。'
          return
        }
        toast.success('选题关系已保存，服务器学生档案已回读')
        this.$router.push(target.backTo)
      } catch (error) {
        this.formError = error?.message || '选题分配失败，请稍后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sat-context{display:flex;min-width:0;gap:8px}.sat-context span{display:grid;min-width:150px;gap:2px;padding:7px 10px;border:1px solid var(--border-light,#e2e8f0);border-radius:8px;background:#fff;color:var(--text-secondary);font-size:11px}.sat-context b{color:var(--text-tertiary);font-size:9px}.sat-form{gap:12px}.sat-section{overflow:hidden;border:1px solid var(--border-light);border-radius:10px;background:#fff}.sat-section>header{display:flex;align-items:center;gap:9px;padding:10px 12px;border-bottom:1px solid var(--border-light);background:var(--gray-50)}.sat-section>header>span{display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:var(--primary-50);color:var(--primary-700);font-size:10px;font-weight:700}.sat-section>header div{display:grid;gap:1px}.sat-section>header strong{font-size:12px}.sat-section>header small{color:var(--text-tertiary);font-size:10px}.sat-section__body{padding:12px}.sat-current{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:12px}.sat-current>div{display:grid;gap:2px;padding:9px;border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50)}.sat-current span,.sat-current small{color:var(--text-tertiary);font-size:9px}.sat-current strong{overflow:hidden;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.sat-aside-card,.sat-warning{padding:12px;border:1px solid var(--border-light);border-radius:10px;background:#fff}.sat-aside-card>span{font-size:12px;font-weight:700}.sat-aside-card ul,.sat-aside-card ol{display:grid;gap:8px;margin:9px 0 0;padding:0;list-style:none}.sat-aside-card li{display:flex;align-items:flex-start;gap:8px;font-size:10px}.sat-aside-card ul li>b{display:grid;width:22px;height:22px;flex:none;place-items:center;border-radius:50%;background:var(--gray-100);color:var(--text-tertiary);font-size:9px}.sat-aside-card ul li.done>b{background:var(--success-50);color:var(--success-700)}.sat-aside-card li div{display:grid;gap:1px}.sat-aside-card li strong{font-size:10px}.sat-aside-card li small{color:var(--text-tertiary);font-size:9px}.sat-aside-card.is-next ol{counter-reset:next}.sat-aside-card.is-next li::before{counter-increment:next;content:counter(next);display:grid;width:19px;height:19px;flex:none;place-items:center;border-radius:6px;background:var(--primary-50);color:var(--primary-700);font-size:9px;font-weight:700}.sat-warning{border-color:var(--warning-200);background:var(--warning-50)}.sat-warning strong{color:var(--warning-800);font-size:11px}.sat-warning p{margin:4px 0 0;color:var(--warning-700);font-size:10px;line-height:1.5}.mp-btn{padding:7px 16px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:13px}.mp-btn--primary{border-color:var(--pri,#2563eb);background:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}@media(max-width:760px){.sat-current{grid-template-columns:1fr}}
</style>
