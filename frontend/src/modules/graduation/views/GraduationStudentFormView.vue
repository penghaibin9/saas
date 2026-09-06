<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="新建毕设学生档案"
    :subtitle="pageSubtitle"
    eyebrow="批次实施 · 学生建档"
    purpose="把学校学生主档关联到当前毕设批次，建立后续选题、导师、材料、答辩与归档的唯一业务入口。"
    status-text="待建档"
    status-tone="warning"
    :back-to="backTo"
    :busy="submitting"
    @blocked-back="onBlockedBack"
  >
    <template #context>
      <div class="gsf-context">
        <span><b>当前批次</b>{{ currentBatchLabel }}</span>
        <span><b>数据范围</b>{{ ctx.dataScope.scopeName }}</span>
        <span><b>进入来源</b>{{ sourceLabel }}</span>
      </div>
    </template>

    <form class="ie-form gsf-form" @submit.prevent="submit">
      <section class="gsf-section ie-fld--full">
        <header>
          <span>01</span>
          <div>
            <strong>选择学校学生主档</strong>
            <small>这里只建立毕设业务关系，不复制或新造第二套学生主档。</small>
          </div>
        </header>
        <div class="gsf-section__body">
          <div class="ie-fld ie-fld--full">
            <span class="ie-lbl">学生 <i>*</i></span>
            <AppGraduationCandidateStudentPicker
              v-model="form.studentId"
              :disabled="submitting"
              placeholder="按学号 / 姓名搜索尚未建档的学生"
            />
            <p class="ie-hint">候选列表来自学校真实学生主档；已在当前范围建档的学生由服务端拒绝重复创建。</p>
          </div>
        </div>
      </section>

      <section class="gsf-section ie-fld--full">
        <header>
          <span>02</span>
          <div>
            <strong>建立批次与指导关系</strong>
            <small>批次决定后续规则、阶段和数据范围；指导教师仍受资格、容量和冲突校验。</small>
          </div>
        </header>
        <div class="gsf-section__body gsf-grid">
          <div class="ie-fld">
            <span class="ie-lbl">毕业设计批次</span>
            <AppGraduationDesignBatchPicker
              v-model="form.batchId"
              :disabled="submitting"
              clearable
              placeholder="选择毕业设计批次"
            />
            <p class="ie-hint">已默认带入顶部当前批次；不关联批次时，该档案不能进入该批次的正式流程。</p>
          </div>
          <div class="ie-fld">
            <span class="ie-lbl">指导教师</span>
            <AppGraduationMentorPicker
              v-model="form.advisorName"
              :disabled="submitting"
              clearable
              placeholder="可暂不分配"
            />
            <p class="ie-hint">可以建档后再从“导师与分配”工作区处理；服务端会校验导师资格与容量。</p>
          </div>
        </div>
      </section>

      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template #aside>
      <section class="gsf-aside-card">
        <span>保存前检查</span>
        <ul>
          <li :class="{ done: Boolean(form.studentId) }">
            <b>{{ form.studentId ? '✓' : '1' }}</b>
            <div><strong>已选择真实学生</strong><small>必填</small></div>
          </li>
          <li :class="{ done: Boolean(form.batchId) }">
            <b>{{ form.batchId ? '✓' : '2' }}</b>
            <div><strong>已关联毕业设计批次</strong><small>建议完成</small></div>
          </li>
          <li :class="{ done: Boolean(form.advisorName) }">
            <b>{{ form.advisorName ? '✓' : '3' }}</b>
            <div><strong>已建立指导关系</strong><small>可稍后分配</small></div>
          </li>
        </ul>
      </section>

      <section class="gsf-aside-card is-next">
        <span>建档后的下一步</span>
        <ol>
          <li>核验学生是否进入当前批次名单</li>
          <li>分配题目与指导教师</li>
          <li>下达任务书并等待学生确认</li>
          <li>进入开题、过程指导和成果提交</li>
        </ol>
      </section>

      <section class="gsf-warning">
        <strong>不会发生的事情</strong>
        <p>本页不会创建新的学校学生、不会修改教务毕业资格，也不会绕过导师资格和批次状态机。</p>
      </section>
    </template>

    <template #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !form.studentId" @click="submit">
        {{ submitting ? '正在建档…' : '确认建档' }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import {
  AppGraduationCandidateStudentPicker,
  AppGraduationDesignBatchPicker,
  AppGraduationMentorPicker
} from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationStudentFormView',
  components: {
    GraduationFormPageShell,
    AppGraduationCandidateStudentPicker,
    AppGraduationDesignBatchPicker,
    AppGraduationMentorPicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      form: { studentId: '', batchId: '', advisorName: '' },
      formError: '',
      submitting: false
    }
  },
  computed: {
    safeReturnTo() {
      const raw = Array.isArray(this.$route.query.returnTo)
        ? this.$route.query.returnTo[0]
        : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : ''
    },
    backTo() {
      const panel = String(this.$route.query.returnPanel || 'roster')
      const query = new URLSearchParams({ panel })
      const batchId = this.form.batchId || this.batchStore.selectedBatchId || this.$route.query.batchId
      if (batchId) query.set('batchId', String(batchId))
      return `/admin/graduation/students?${query}`
    },
    pageSubtitle() {
      return this.batchStore.selectedBatchName
        ? `${this.batchStore.selectedBatchName} · 选择学校真实学生并建立毕设业务关系`
        : '选择学校真实学生并关联毕业设计批次'
    },
    currentBatchLabel() {
      return this.batchStore.selectedBatchName || (this.form.batchId ? '已选择批次' : '尚未选择')
    },
    sourceLabel() {
      return this.$route.query.source === 'dashboard' ? '毕设总览'
        : this.$route.query.source === 'students' ? '学生与进度'
          : '学生名单'
    }
  },
  created() {
    const routeBatchId = String(this.$route.query.batchId || '')
    const selectedBatchId = String(this.batchStore.selectedBatchId || '')
    this.form.batchId = routeBatchId || selectedBatchId
  },
  beforeRouteLeave(_to, _from, next) {
    if (this.submitting) {
      toast.info('学生档案正在保存，请等待服务器回执')
      next(false)
      return
    }
    next()
  },
  methods: {
    onBlockedBack() {
      toast.info('学生档案正在保存，请勿重复操作')
    },
    cancel() {
      if (this.submitting) return
      this.$router.push(this.safeReturnTo || this.backTo)
    },
    async submit() {
      if (this.submitting) return
      this.formError = ''
      if (!this.form.studentId) {
        this.formError = '请选择要建立毕设档案的学生'
        return
      }

      const target = Object.freeze({
        studentId: String(this.form.studentId),
        batchId: this.form.batchId ? String(this.form.batchId) : '',
        advisorName: this.form.advisorName || '',
        returnTo: this.safeReturnTo || this.backTo
      })
      this.submitting = true
      try {
        const body = {
          studentId: target.studentId,
          advisorName: target.advisorName || undefined
        }
        if (target.batchId) body.batchId = target.batchId

        const res = await gdStudentApi.createStudent(body)
        if (res.code !== 0) {
          this.formError = res.message || '学生建档失败'
          return
        }
        const recordId = String(res.data?.id || res.data?.gdStudentId || '')
        toast.success(recordId ? '毕设学生档案已建立' : '毕设学生档案已建立，正在返回名单')
        this.$router.push(target.returnTo)
      } catch (error) {
        this.formError = error?.message || '学生建档失败，请稍后重试'
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.gsf-context {
  display: flex;
  min-width: 0;
  gap: 8px;
}

.gsf-context span {
  display: grid;
  min-width: 150px;
  gap: 2px;
  padding: 7px 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-secondary, #475569);
  font-size: 11px;
}

.gsf-context b {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
  font-weight: 600;
}

.gsf-form {
  gap: 12px;
}

.gsf-section {
  overflow: hidden;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  background: var(--bg-card, #fff);
}

.gsf-section > header {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light, #e8edf5);
  background: var(--bg-subtle, #f8fafc);
}

.gsf-section > header > span {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 50%;
  background: var(--primary-50, #eff6ff);
  color: var(--primary-700, #1d4ed8);
  font-size: 10px;
  font-weight: 700;
}

.gsf-section > header div {
  display: grid;
  gap: 1px;
}

.gsf-section > header strong {
  color: var(--text-primary, #0f172a);
  font-size: 12px;
}

.gsf-section > header small {
  color: var(--text-tertiary, #64748b);
  font-size: 10px;
}

.gsf-section__body {
  padding: 12px;
}

.gsf-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.gsf-aside-card,
.gsf-warning {
  padding: 12px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  background: var(--bg-card, #fff);
}

.gsf-aside-card > span {
  color: var(--text-primary, #0f172a);
  font-size: 12px;
  font-weight: 700;
}

.gsf-aside-card ul,
.gsf-aside-card ol {
  display: grid;
  gap: 8px;
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
}

.gsf-aside-card li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--text-secondary, #475569);
  font-size: 11px;
}

.gsf-aside-card ul li > b {
  display: grid;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 50%;
  background: var(--gray-100, #f1f5f9);
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

.gsf-aside-card ul li.done > b {
  background: var(--success-50, #ecfdf5);
  color: var(--success-700, #047857);
}

.gsf-aside-card li div {
  display: grid;
  gap: 1px;
}

.gsf-aside-card li strong {
  color: var(--text-primary, #0f172a);
  font-size: 11px;
}

.gsf-aside-card li small {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

.gsf-aside-card.is-next ol {
  counter-reset: next;
}

.gsf-aside-card.is-next li::before {
  counter-increment: next;
  content: counter(next);
  display: grid;
  flex: 0 0 auto;
  width: 19px;
  height: 19px;
  place-items: center;
  border-radius: 6px;
  background: var(--primary-50, #eff6ff);
  color: var(--primary-700, #1d4ed8);
  font-size: 9px;
  font-weight: 700;
}

.gsf-warning {
  border-color: var(--warning-200, #fde68a);
  background: var(--warning-50, #fffbeb);
}

.gsf-warning strong {
  color: var(--warning-800, #92400e);
  font-size: 11px;
}

.gsf-warning p {
  margin: 4px 0 0;
  color: var(--warning-700, #a16207);
  font-size: 10px;
  line-height: 1.5;
}

.mp-btn {
  padding: 7px 16px;
  border: 1px solid var(--line, #d9dee8);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.mp-btn--primary {
  border-color: var(--pri, #2563eb);
  background: var(--pri, #2563eb);
  color: #fff;
}

.mp-btn:disabled {
  cursor: not-allowed;
  opacity: .5;
}

@media (max-width: 760px) {
  .gsf-grid {
    grid-template-columns: 1fr;
  }
}
</style>
