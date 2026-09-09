<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="student ? `分配答辩组 · ${student.name}` : '分配答辩组'"
    :subtitle="student ? `${student.studentNo} · ${student.className || '班级待确认'}` : '正在读取学生主档'"
    eyebrow="答辩与成绩 · 学生编排"
    purpose="把当前学生加入一个真实答辩组；时间、地点、评委、秘书、容量和回避冲突仍由服务端及答辩发布前检查负责。"
    :status-text="submitting ? '保存中' : (student?.defenseGroupId ? '调整分组' : '待分配')"
    status-tone="warning"
    :back-to="backTo"
    :busy="submitting"
    @blocked-back="onBlockedBack"
  >
    <template #context>
      <div class="sdg-context">
        <span><b>当前学生</b>{{ student ? `${student.name} · ${student.studentNo}` : '正在读取' }}</span>
        <span><b>当前批次</b>{{ batchLabel }}</span>
        <span><b>当前答辩组</b>{{ student?.defenseGroup || student?.defenseGroupName || '尚未分配' }}</span>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else class="ie-form sdg-form" @submit.prevent="submit">
      <section class="sdg-section ie-fld--full">
        <header>
          <span>01</span>
          <div>
            <strong>核对当前学生与答辩状态</strong>
            <small>本页只维护学生—答辩组关系，不创建答辩组，也不直接发布通知。</small>
          </div>
        </header>
        <div class="sdg-current">
          <div><span>学生</span><strong>{{ student.name }}</strong><small>{{ student.studentNo }} · {{ student.topicTitle || '题目待确认' }}</small></div>
          <div><span>当前答辩组</span><strong>{{ student.defenseGroup || student.defenseGroupName || '尚未分配' }}</strong><small>{{ student.stageLabel || student.stage || '阶段待确认' }}</small></div>
        </div>
      </section>

      <section class="sdg-section ie-fld--full">
        <header>
          <span>02</span>
          <div>
            <strong>选择目标答辩组</strong>
            <small>候选组来自当前批次真实答辩安排，按组名、日期和地点搜索。</small>
          </div>
        </header>
        <div class="sdg-section__body">
          <div class="ie-fld ie-fld--full">
            <span class="ie-lbl">目标答辩组 <i>*</i></span>
            <AppDefenseGroupPicker
              v-model="defenseGroupId"
              :disabled="submitting"
              placeholder="按组名 / 日期 / 地点搜索答辩组"
            />
            <p class="ie-hint">选择器只展示当前批次候选；保存时服务端仍校验组容量、学生状态和跨批关系。</p>
          </div>
          <label class="ie-fld ie-fld--full">
            <span class="ie-lbl">分配说明</span>
            <textarea
              v-model.trim="reason"
              class="ie-in"
              rows="3"
              :disabled="submitting"
              placeholder="可填写调整分组、特殊安排或线下沟通说明。"
              @input="formError = ''"
            ></textarea>
            <p class="ie-hint">说明会随原分配接口提交并进入可追溯记录。</p>
          </label>
        </div>
      </section>

      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template v-if="student" #aside>
      <section class="sdg-aside-card">
        <span>保存前检查</span>
        <ul>
          <li class="done"><b>✓</b><div><strong>学生主档已读取</strong><small>{{ student.studentNo }}</small></div></li>
          <li :class="{ done: Boolean(defenseGroupId) }"><b>{{ defenseGroupId ? '✓' : '2' }}</b><div><strong>已选择目标答辩组</strong><small>必填</small></div></li>
          <li :class="{ done: Boolean(batchLabel) }"><b>{{ batchLabel ? '✓' : '3' }}</b><div><strong>批次上下文已保留</strong><small>跨批分配由服务端拒绝</small></div></li>
        </ul>
      </section>

      <section class="sdg-aside-card is-next">
        <span>保存后的真实流转</span>
        <ol>
          <li>服务端更新学生—答辩组关系和组内人数</li>
          <li>重新读取学生档案确认分组结果</li>
          <li>回到答辩安排核验时间、地点和角色</li>
          <li>满足发布前检查后正式通知学生与教师</li>
        </ol>
      </section>

      <section class="sdg-warning">
        <strong>分配不等于发布</strong>
        <p>只有答辩组时间、地点、评委、秘书、学生数和回避冲突都通过检查后，发布动作才会产生正式通知。</p>
      </section>
    </template>

    <template v-if="student" #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !defenseGroupId" @click="submit">
        {{ submitting ? '正在保存…' : '确认分配答辩组' }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppDefenseGroupPicker } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationStudentDefenseView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppDefenseGroupPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      student: null,
      defenseGroupId: '',
      reason: '',
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
      const panel = String(this.$route.query.returnPanel || 'defense')
      const query = new URLSearchParams({ panel })
      const batchId = this.$route.query.batchId || this.student?.batchId
      if (batchId) query.set('batchId', String(batchId))
      const keyword = this.$route.query.keyword
      const page = this.$route.query.page
      if (keyword) query.set('keyword', String(keyword))
      if (page) query.set('page', String(page))
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
      toast.info('答辩组关系正在保存，请等待服务器回执')
      next(false)
      return
    }
    next()
  },
  methods: {
    onBlockedBack() { toast.info('答辩组关系正在保存，请勿重复操作') },
    cancel() { if (!this.submitting) this.$router.push(this.backTo) },
    async load() {
      const studentId = String(this.$route.params.id || '')
      const batchId = String(this.$route.query.batchId || '')
      const token = ++this.loadToken
      this.loading = true
      this.error = ''
      try {
        const response = await gdStudentApi.getStudentDetail(studentId)
        if (token !== this.loadToken || studentId !== String(this.$route.params.id || '')) return false
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
        this.defenseGroupId = response.data.defenseGroupId || ''
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
      if (!this.defenseGroupId) {
        this.formError = '请选择目标答辩组'
        return
      }
      const target = Object.freeze({
        studentId: String(this.student.id),
        defenseGroupId: String(this.defenseGroupId),
        reason: String(this.reason || '').trim(),
        batchId: String(this.$route.query.batchId || this.student.batchId || ''),
        backTo: this.backTo
      })
      this.submitting = true
      try {
        const response = await gdStudentApi.assignDefenseGroup(target.studentId, {
          defenseGroupId: target.defenseGroupId,
          reason: target.reason
        })
        if (response.code !== 0) {
          this.formError = response.message || '答辩组分配失败'
          return
        }
        const latest = await gdStudentApi.getStudentDetail(target.studentId)
        if (latest.code !== 0 || String(latest.data?.defenseGroupId || '') !== target.defenseGroupId) {
          this.formError = '分配命令已返回，但学生档案尚未回读到目标答辩组；请返回台账刷新核对，勿重复提交。'
          return
        }
        toast.success('答辩组关系已保存，服务器学生档案已回读')
        this.$router.push(target.backTo)
      } catch (error) {
        this.formError = error?.message || '答辩组分配失败，请稍后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sdg-context{display:flex;min-width:0;gap:8px}.sdg-context span{display:grid;min-width:150px;gap:2px;padding:7px 10px;border:1px solid var(--border-light,#e2e8f0);border-radius:8px;background:#fff;color:var(--text-secondary);font-size:11px}.sdg-context b{color:var(--text-tertiary);font-size:9px}.sdg-form{gap:12px}.sdg-section{overflow:hidden;border:1px solid var(--border-light);border-radius:10px;background:#fff}.sdg-section>header{display:flex;align-items:center;gap:9px;padding:10px 12px;border-bottom:1px solid var(--border-light);background:var(--gray-50)}.sdg-section>header>span{display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:var(--primary-50);color:var(--primary-700);font-size:10px;font-weight:700}.sdg-section>header div{display:grid;gap:1px}.sdg-section>header strong{font-size:12px}.sdg-section>header small{color:var(--text-tertiary);font-size:10px}.sdg-section__body{display:grid;gap:12px;padding:12px}.sdg-current{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:12px}.sdg-current>div{display:grid;gap:2px;padding:9px;border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50)}.sdg-current span,.sdg-current small{color:var(--text-tertiary);font-size:9px}.sdg-current strong{overflow:hidden;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.sdg-aside-card,.sdg-warning{padding:12px;border:1px solid var(--border-light);border-radius:10px;background:#fff}.sdg-aside-card>span{font-size:12px;font-weight:700}.sdg-aside-card ul,.sdg-aside-card ol{display:grid;gap:8px;margin:9px 0 0;padding:0;list-style:none}.sdg-aside-card li{display:flex;align-items:flex-start;gap:8px;font-size:10px}.sdg-aside-card ul li>b{display:grid;width:22px;height:22px;flex:none;place-items:center;border-radius:50%;background:var(--gray-100);color:var(--text-tertiary);font-size:9px}.sdg-aside-card ul li.done>b{background:var(--success-50);color:var(--success-700)}.sdg-aside-card li div{display:grid;gap:1px}.sdg-aside-card li strong{font-size:10px}.sdg-aside-card li small{color:var(--text-tertiary);font-size:9px}.sdg-aside-card.is-next ol{counter-reset:next}.sdg-aside-card.is-next li::before{counter-increment:next;content:counter(next);display:grid;width:19px;height:19px;flex:none;place-items:center;border-radius:6px;background:var(--primary-50);color:var(--primary-700);font-size:9px;font-weight:700}.sdg-warning{border-color:var(--warning-200);background:var(--warning-50)}.sdg-warning strong{color:var(--warning-800);font-size:11px}.sdg-warning p{margin:4px 0 0;color:var(--warning-700);font-size:10px;line-height:1.5}.mp-btn{padding:7px 16px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:13px}.mp-btn--primary{border-color:var(--pri,#2563eb);background:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}@media(max-width:760px){.sdg-current{grid-template-columns:1fr}}
</style>
