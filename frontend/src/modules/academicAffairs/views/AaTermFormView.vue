<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="新建学年学期"
    subtitle="先建立学期草稿，再核对校历与教学周，确认后发布。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="goBack">返回列表</AppButton>
    </template>

    <div class="aa-term-create-layout">
    <AppSectionCard title="学期信息" subtitle="按学校已确认的校历填写；学年与学期序号创建后不可修改。">
      <div class="aa-form">
        <div class="aa-form__row">
          <label for="aa-term-year" class="aa-form__label required">学年</label>
          <div class="aa-form__field">
            <input
              v-model.trim="form.yearCode"
              id="aa-term-year"
              :aria-invalid="!!errors.yearCode"
              aria-describedby="aa-term-year-hint"
              class="aa-input"
              placeholder="如 2026-2027"
              maxlength="9"
            />
            <div id="aa-term-year-hint" :class="errors.yearCode ? 'aa-form__err' : 'aa-form__hint'">{{ errors.yearCode || '输入连续两年，例如 2026-2027。' }}</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label for="aa-term-number" class="aa-form__label required">学期</label>
          <div class="aa-form__field">
            <AppSelect id="aa-term-number" v-model="form.termNo" :options="termOptions" placeholder="请选择学期" />
            <div v-if="errors.termNo" class="aa-form__err">{{ errors.termNo }}</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label for="aa-term-name" class="aa-form__label">学期名称</label>
          <div class="aa-form__field">
            <input id="aa-term-name" v-model.trim="form.termName" class="aa-input" placeholder="选填，如 2026学年秋季学期" maxlength="50" />
          </div>
        </div>

        <div class="aa-form__row">
          <span class="aa-form__label">起止日期</span>
          <div class="aa-form__field aa-form__field--inline">
            <input v-model="form.startDate" type="date" aria-label="开学日期" :aria-invalid="!!errors.dateRange" class="aa-input aa-input--date" />
            <span class="aa-form__tilde">至</span>
            <input v-model="form.endDate" type="date" aria-label="结束日期" :aria-invalid="!!errors.dateRange" class="aa-input aa-input--date" />
          </div>
        </div>
        <div v-if="errors.dateRange" class="aa-form__err aa-form__err--full">{{ errors.dateRange }}</div>

        <div class="aa-form__row">
          <label for="aa-term-weeks" class="aa-form__label">教学周数</label>
          <div class="aa-form__field">
            <input id="aa-term-weeks" v-model.number="form.teachingWeeks" type="number" min="1" max="30" step="1" :aria-invalid="!!errors.teachingWeeks" class="aa-input aa-input--num" placeholder="按学校校历填写，如 17 或 20" />
            <div v-if="errors.teachingWeeks" class="aa-form__err">{{ errors.teachingWeeks }}</div>
            <div v-else class="aa-form__hint">填写校历确认的实际周数，用于后续教学任务和课表安排。</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label for="aa-term-exam-week" class="aa-form__label">考试开始周</label>
          <div class="aa-form__field">
            <input id="aa-term-exam-week" v-model.number="form.examWeekStart" type="number" min="1" max="30" step="1" :aria-invalid="!!errors.examWeekStart" class="aa-input aa-input--num" placeholder="第几教学周开始考试，选填" />
            <div v-if="errors.examWeekStart" class="aa-form__err">{{ errors.examWeekStart }}</div>
          </div>
        </div>
      </div>

      <div class="aa-form__actions">
        <AppButton @click="goBack">取消</AppButton>
        <AppButton v-if="canManage" variant="primary" :loading="submitting" @click="submit">
          创建学期草稿
        </AppButton>
      </div>
    </AppSectionCard>
    <aside class="aa-term-create-guide">
      <h2>建立学期的三个步骤</h2>
      <ol>
        <li><strong>建立草稿</strong><p>填写学年、学期和起止日期。</p></li>
        <li><strong>核对教学安排</strong><p>完善教学周、考试周和校历事件。</p></li>
        <li><strong>发布并启用</strong><p>确认后发布，再按学校的学期管理方式启用。</p></li>
      </ol>
      <p class="mp-note">周数尚未确定时可以保存草稿；生成教学任务前需完成配置。</p>
    </aside>
    </div>
  </ModulePageShell>
</template>

<script>
/** 新建草稿后进入详情，沿用正式影响预览与更新端点。 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'

const YEAR_RE = /^(\d{4})-(\d{4})$/

export default {
  name: 'AaTermFormView',
  components: { ModulePageShell, AppButton, AppSectionCard, AppSelect },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') }
  },
  data() {
    return {
      submitting: false, disposed: false,
      termOptions: [
        { value: 1, label: '第 1 学期（秋季）' },
        { value: 2, label: '第 2 学期（春季）' }
      ],
      form: {
        yearCode: '',
        termNo: 1,
        termName: '',
        startDate: '',
        endDate: '',
        teachingWeeks: null,
        examWeekStart: null
      },
      errors: {}
    }
  },
  beforeUnmount() { this.disposed = true },
  methods: {
    contextKey() { return JSON.stringify([this.disposed, this.academicFlow?.identity() || JSON.stringify(this.ctx), this.$route?.fullPath]) },
    goBack() {
      if (this.academicFlow && this.$route.query.returnToken) return this.academicFlow.back(this.$route.query.returnToken, '/admin/academic-affairs/terms')
      this.$router.push('/admin/academic-affairs/terms')
    },
    validate() {
      const e = {}
      const m = YEAR_RE.exec(this.form.yearCode)
      if (!this.form.yearCode) {
        e.yearCode = '请填写学年'
      } else if (!m) {
        e.yearCode = '学年格式应为「YYYY-YYYY」，如 2026-2027'
      } else if (Number(m[2]) !== Number(m[1]) + 1) {
        e.yearCode = '后一年应为前一年 +1，如 2026-2027'
      }
      if (![1, 2].includes(Number(this.form.termNo))) e.termNo = '学期只能是第 1 或第 2 学期'
      if (this.form.startDate && this.form.endDate && this.form.startDate > this.form.endDate) {
        e.dateRange = '起始日期不能晚于结束日期'
      }
      if (this.form.teachingWeeks != null && this.form.teachingWeeks !== '' &&
        (!Number.isInteger(Number(this.form.teachingWeeks)) || this.form.teachingWeeks < 1 || this.form.teachingWeeks > 30)) {
        e.teachingWeeks = '教学周数应在 1~30 之间'
      }
      if (this.form.examWeekStart != null && this.form.examWeekStart !== '' &&
        (!Number.isInteger(Number(this.form.examWeekStart)) || this.form.examWeekStart < 1 || this.form.examWeekStart > 30)) {
        e.examWeekStart = '考试周起应在 1~30 之间'
      }
      if (this.form.teachingWeeks && this.form.examWeekStart > this.form.teachingWeeks) e.examWeekStart = '考试开始周不能超过教学周数'
      this.errors = e
      return Object.keys(e).length === 0
    },
    async submit() {
      if (!this.canManage || this.submitting) return
      if (!this.validate()) return
      this.submitting = true
      const context = this.contextKey()
      const body = {
        yearCode: this.form.yearCode,
        termNo: Number(this.form.termNo),
        termName: this.form.termName || undefined,
        startDate: this.form.startDate || undefined,
        endDate: this.form.endDate || undefined,
        teachingWeeks: this.form.teachingWeeks || undefined,
        examWeekStart: this.form.examWeekStart || undefined
      }
      const res = await academicAffairsApi.createTerm(body)
      if (context !== this.contextKey()) return
      this.submitting = false
      if (res.code === 0) {
        toast.success('学期草稿已创建')
        this.$router.push({ name: 'aa-term-detail', params: { termId: res.data.termId }, query: this.$route.query.returnToken ? { returnToken: this.$route.query.returnToken } : {} })
      } else {
        toast.error(res.message || '创建失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-term-create-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 20px; align-items: start; }
.aa-term-create-guide { padding: 22px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); }
.aa-term-create-guide h2 { margin: 0 0 20px; font-size: 15px; color: var(--text-primary); }
.aa-term-create-guide ol { margin: 0; padding-left: 20px; }
.aa-term-create-guide li { padding: 0 0 20px 5px; font-size: 13px; color: var(--pri); }
.aa-term-create-guide strong { color: var(--text-primary); }
.aa-term-create-guide li p { margin: 7px 0 0; color: var(--text-secondary); line-height: 1.7; }
.aa-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 640px;
}
.aa-form__row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.aa-form__label {
  width: 88px;
  flex-shrink: 0;
  padding-top: 8px;
  font-size: 13px;
  color: var(--text-700, #4e5969);
  text-align: right;
}
.aa-form__label.required::before {
  content: '*';
  color: var(--danger-600, #f53f3f);
  margin-right: 4px;
}
.aa-form__field {
  flex: 1;
  min-width: 0;
}
.aa-form__field--inline {
  display: flex;
  align-items: center;
  gap: 10px;
}
.aa-input {
  width: 100%;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #1f2329);
  font-size: 14px;
  box-sizing: border-box;
}
.aa-input--date { width: 100%; min-width: 0; }
.aa-input--num { width: 100%; max-width: 300px; }
.aa-form__tilde { color: var(--text-500, #646a73); }
.aa-form__hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-400, #8a9099);
}
.aa-form__err {
  margin-top: 4px;
  font-size: 12px;
  color: var(--danger-600, #f53f3f);
}
.aa-form__err--full {
  margin-left: 104px;
}
.aa-form__actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
  padding-left: 104px;
}
@media (max-width: 1100px) { .aa-term-create-layout { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .aa-form__row { flex-direction: column; gap: 6px; } .aa-form__label { width: auto; text-align: left; } .aa-form__field { width: 100%; } .aa-form__actions { padding-left: 0; } .aa-form__err--full { margin-left: 0; } }
</style>
