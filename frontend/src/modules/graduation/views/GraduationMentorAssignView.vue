<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="form.mode === 'change' ? '调整指导教师' : '分配指导教师'"
    :subtitle="student ? `${student.name}（${student.studentNo}）· ${student.className || '班级待确认'}` : '正在读取学生主档'"
    eyebrow="批次实施 · 指导关系"
    purpose="为当前学生建立一条真实、可追溯的导师分配关系；导师资格、容量和数据范围仍由服务端最终校验。"
    :status-text="submitting ? '保存中' : (form.mode === 'change' ? '待调整' : '待分配')"
    status-tone="warning"
    :back-to="backTo"
    :busy="submitting"
    @blocked-back="onBlockedBack"
  >
    <template #context>
      <div class="gma-context">
        <span><b>当前学生</b>{{ student ? `${student.name} · ${student.studentNo}` : '正在读取' }}</span>
        <span><b>当前批次</b>{{ batchLabel }}</span>
        <span><b>当前导师</b>{{ student?.advisorName || '尚未分配' }}</span>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="permissionError || loadError" :description="permissionError || loadError" @retry="loadStudent" />
    <form v-else class="ie-form gma-form" @submit.prevent="submit">
      <section class="gma-section ie-fld--full">
        <header>
          <span>01</span>
          <div>
            <strong>核对当前指导关系</strong>
            <small>调整导师不会删除历史分配记录，原关系会转为已变更。</small>
          </div>
        </header>
        <div class="gma-current">
          <div><span>学生</span><strong>{{ student.name }}</strong><small>{{ student.studentNo }} · {{ student.topicTitle || '题目待确认' }}</small></div>
          <div><span>当前导师</span><strong>{{ student.advisorName || '尚未分配' }}</strong><small>{{ form.mode === 'change' ? '本次将建立新的生效关系' : '首次建立指导关系' }}</small></div>
        </div>
      </section>

      <section class="gma-section ie-fld--full">
        <header>
          <span>02</span>
          <div>
            <strong>选择目标导师</strong>
            <small>候选列表只显示已认证且未满员导师；提交时再次校验资格与容量。</small>
          </div>
        </header>
        <div class="gma-section__body">
          <div class="ie-fld ie-fld--full">
            <span class="ie-lbl">目标导师 <i>*</i></span>
            <AppAvailableGraduationMentorPicker
              v-model="form.mentorId"
              :disabled="submitting"
              placeholder="按姓名 / 工号搜索已认证且未满员导师"
            />
            <p class="ie-hint">可见候选不代表可以绕过服务端容量、停用状态、跨学院或数据范围规则。</p>
          </div>
          <label class="ie-fld ie-fld--full">
            <span class="ie-lbl">{{ form.mode === 'change' ? '调整原因' : '分配说明' }} <i v-if="form.mode === 'change'">*</i></span>
            <textarea
              v-model.trim="form.reason"
              class="ie-in"
              rows="4"
              :disabled="submitting"
              :placeholder="form.mode === 'change' ? '说明调整导师的业务原因，不少于 5 个字。' : '可填写分配依据或沟通说明。'"
              @input="formError = ''"
            ></textarea>
            <p class="ie-hint">调整导师的原因会进入分配审计；首次分配说明可选。</p>
          </label>
        </div>
      </section>

      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template v-if="canAssignMentor && student" #aside>
      <section class="gma-aside-card">
        <span>保存前检查</span>
        <ul>
          <li class="done"><b>✓</b><div><strong>学生主档已读取</strong><small>{{ student.studentNo }}</small></div></li>
          <li :class="{ done: Boolean(form.mentorId) }"><b>{{ form.mentorId ? '✓' : '2' }}</b><div><strong>已选择目标导师</strong><small>必填</small></div></li>
          <li :class="{ done: form.mode !== 'change' || form.reason.length >= 5 }"><b>{{ form.mode !== 'change' || form.reason.length >= 5 ? '✓' : '3' }}</b><div><strong>调整原因完整</strong><small>{{ form.mode === 'change' ? '不少于 5 个字' : '首次分配无需强制' }}</small></div></li>
        </ul>
      </section>
      <section class="gma-aside-card is-next">
        <span>保存后的真实流转</span>
        <ol>
          <li>服务端校验导师资格、容量和学生范围</li>
          <li>建立新的 ACTIVE 分配记录</li>
          <li>重新读取学生档案确认指导教师</li>
          <li>返回原导师分配队列继续处理</li>
        </ol>
      </section>
      <section class="gma-warning">
        <strong>不会静默覆盖</strong>
        <p>调整导师时原分配记录保留为历史，题目关系也不会在本页被修改。</p>
      </section>
    </template>

    <template v-if="canAssignMentor && student" #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitDisabled" @click="submit">
        {{ submitting ? '正在保存…' : (form.mode === 'change' ? '确认调整导师' : '确认分配导师') }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppAvailableGraduationMentorPicker } from '@/components/common'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationMentorAssignView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppAvailableGraduationMentorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { mode: 'assign', studentId: '', mentorId: '', reason: '' },
      student: null,
      loading: true,
      loadError: '',
      formError: '',
      submitting: false,
      loadToken: 0
    }
  },
  computed: {
    permissionPatterns() { return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : [] },
    canMentorManage() { return matchPermission(this.permissionPatterns, 'graduationDesign.student.manage') },
    canTopicAssign() { return matchPermission(this.permissionPatterns, 'graduationDesign.topic.assign') },
    canAssignMentor() { return this.canMentorManage && this.canTopicAssign },
    permissionError() { return this.canAssignMentor ? '' : '当前角色无导师分配权限' },
    safeReturnTo() {
      const raw = Array.isArray(this.$route.query.returnTo) ? this.$route.query.returnTo[0] : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : ''
    },
    backTo() {
      if (this.safeReturnTo) return this.safeReturnTo
      const query = new URLSearchParams({ panel: 'assign' })
      const batchId = this.$route.query.batchId || this.student?.batchId
      if (batchId) query.set('batchId', String(batchId))
      const keyword = this.$route.query.keyword
      const page = this.$route.query.page
      if (keyword) query.set('keyword', String(keyword))
      if (page) query.set('page', String(page))
      return `/admin/graduation/mentors?${query}`
    },
    batchLabel() { return String(this.$route.query.batchId || this.student?.batchName || this.student?.batchId || '当前批次') },
    submitDisabled() {
      return this.submitting || !this.form.mentorId || (this.form.mode === 'change' && String(this.form.reason || '').trim().length < 5)
    }
  },
  created() {
    this.form.mode = this.$route.query.mode === 'change' ? 'change' : 'assign'
    this.loadStudent()
  },
  beforeUnmount() { ++this.loadToken },
  beforeRouteLeave(_to, _from, next) {
    if (this.submitting) {
      toast.info('导师关系正在保存，请等待服务器回执')
      next(false)
      return
    }
    next()
  },
  methods: {
    onBlockedBack() { toast.info('导师关系正在保存，请勿重复操作') },
    cancel() { if (!this.submitting) this.$router.push(this.backTo) },
    async loadStudent() {
      if (!this.canAssignMentor) {
        this.loading = false
        return false
      }
      const studentId = String(this.$route.params.studentId || this.$route.query.studentId || '')
      const batchId = String(this.$route.query.batchId || '')
      const token = ++this.loadToken
      this.loading = true
      this.loadError = ''
      if (!studentId) {
        this.loadError = '缺少学生标识，请返回导师分配队列重新选择学生'
        this.loading = false
        return false
      }
      try {
        const response = await gdStudentApi.getStudentDetail(studentId)
        if (token !== this.loadToken || studentId !== String(this.$route.params.studentId || this.$route.query.studentId || '')) return false
        if (response.code !== 0) {
          this.loadError = response.message || '学生信息加载失败'
          return false
        }
        const studentBatchId = String(response.data?.batchId || '')
        if (batchId && studentBatchId && batchId !== studentBatchId) {
          this.loadError = '当前批次与学生上下文不一致，请返回导师分配队列重新选择学生'
          return false
        }
        this.form.studentId = studentId
        this.student = response.data
        return true
      } catch (error) {
        if (token === this.loadToken) this.loadError = error?.message || '学生信息加载失败'
        return false
      } finally {
        if (token === this.loadToken) this.loading = false
      }
    },
    async submit() {
      if (this.submitting || !this.canAssignMentor) return
      this.formError = ''
      if (!this.form.studentId) {
        this.formError = '学生信息无效，请返回重新选择'
        return
      }
      if (!this.form.mentorId) {
        this.formError = '请选择目标导师'
        return
      }
      if (this.form.mode === 'change' && String(this.form.reason || '').trim().length < 5) {
        this.formError = '调整导师原因至少 5 个字'
        return
      }
      const target = Object.freeze({
        mode: this.form.mode,
        studentId: String(this.form.studentId),
        mentorId: String(this.form.mentorId),
        reason: String(this.form.reason || '').trim(),
        batchId: String(this.$route.query.batchId || this.student?.batchId || ''),
        backTo: this.backTo
      })
      this.submitting = true
      try {
        const response = target.mode === 'change'
          ? await graduationMentorApi.changeMentor(target.studentId, target.mentorId, target.reason)
          : await graduationMentorApi.assignMentor(target.studentId, target.mentorId, target.reason)
        if (response.code !== 0) {
          this.formError = response.message || '导师关系保存失败'
          return
        }
        const expectedMentorName = String(response.data?.mentorName || '')
        const latest = await gdStudentApi.getStudentDetail(target.studentId)
        if (latest.code !== 0 || !latest.data?.advisorName || (expectedMentorName && latest.data.advisorName !== expectedMentorName)) {
          this.formError = '分配命令已返回，但学生档案尚未回读到目标导师；请返回台账刷新核对，勿重复提交。'
          return
        }
        toast.success('导师关系已保存，服务器学生档案已回读')
        this.$router.push(target.backTo)
      } catch (error) {
        this.formError = error?.message || '导师关系保存失败，请稍后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gma-context{display:flex;min-width:0;gap:8px}.gma-context span{display:grid;min-width:150px;gap:2px;padding:7px 10px;border:1px solid var(--border-light,#e2e8f0);border-radius:8px;background:#fff;color:var(--text-secondary);font-size:11px}.gma-context b{color:var(--text-tertiary);font-size:9px}.gma-form{gap:12px}.gma-section{overflow:hidden;border:1px solid var(--border-light);border-radius:10px;background:#fff}.gma-section>header{display:flex;align-items:center;gap:9px;padding:10px 12px;border-bottom:1px solid var(--border-light);background:var(--gray-50)}.gma-section>header>span{display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:var(--primary-50);color:var(--primary-700);font-size:10px;font-weight:700}.gma-section>header div{display:grid;gap:1px}.gma-section>header strong{font-size:12px}.gma-section>header small{color:var(--text-tertiary);font-size:10px}.gma-section__body{display:grid;gap:12px;padding:12px}.gma-current{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:12px}.gma-current>div{display:grid;gap:2px;padding:9px;border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50)}.gma-current span,.gma-current small{color:var(--text-tertiary);font-size:9px}.gma-current strong{overflow:hidden;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.gma-aside-card,.gma-warning{padding:12px;border:1px solid var(--border-light);border-radius:10px;background:#fff}.gma-aside-card>span{font-size:12px;font-weight:700}.gma-aside-card ul,.gma-aside-card ol{display:grid;gap:8px;margin:9px 0 0;padding:0;list-style:none}.gma-aside-card li{display:flex;align-items:flex-start;gap:8px;font-size:10px}.gma-aside-card ul li>b{display:grid;width:22px;height:22px;flex:none;place-items:center;border-radius:50%;background:var(--gray-100);color:var(--text-tertiary);font-size:9px}.gma-aside-card ul li.done>b{background:var(--success-50);color:var(--success-700)}.gma-aside-card li div{display:grid;gap:1px}.gma-aside-card li strong{font-size:10px}.gma-aside-card li small{color:var(--text-tertiary);font-size:9px}.gma-aside-card.is-next ol{counter-reset:next}.gma-aside-card.is-next li::before{counter-increment:next;content:counter(next);display:grid;width:19px;height:19px;flex:none;place-items:center;border-radius:6px;background:var(--primary-50);color:var(--primary-700);font-size:9px;font-weight:700}.gma-warning{border-color:var(--warning-200);background:var(--warning-50)}.gma-warning strong{color:var(--warning-800);font-size:11px}.gma-warning p{margin:4px 0 0;color:var(--warning-700);font-size:10px;line-height:1.5}.mp-btn{padding:7px 16px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:13px}.mp-btn--primary{border-color:var(--pri,#2563eb);background:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}@media(max-width:760px){.gma-current{grid-template-columns:1fr}}
</style>
