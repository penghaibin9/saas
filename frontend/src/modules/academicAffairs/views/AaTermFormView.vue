<template>
  <ModulePageShell
    title="新建学年学期"
    subtitle="创建后为「草稿」状态，回列表发布即成为当前学期"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="goBack">返回列表</button>
    </template>

    <AppSectionCard title="学期信息">
      <div class="aa-form">
        <div class="aa-form__row">
          <label class="aa-form__label required">学年</label>
          <div class="aa-form__field">
            <input
              v-model.trim="form.yearCode"
              class="aa-input"
              placeholder="如 2026-2027"
              maxlength="9"
            />
            <div v-if="errors.yearCode" class="aa-form__err">{{ errors.yearCode }}</div>
            <div v-else class="aa-form__hint">格式：起止年份用「-」连接，后一年 = 前一年 +1，如 2026-2027</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label required">学期</label>
          <div class="aa-form__field">
            <AppSelect v-model="form.termNo" :options="termOptions" placeholder="请选择学期" />
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label">学期名称</label>
          <div class="aa-form__field">
            <input v-model.trim="form.termName" class="aa-input" placeholder="选填，如 2026学年秋季学期" maxlength="50" />
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label">起止日期</label>
          <div class="aa-form__field aa-form__field--inline">
            <input v-model="form.startDate" type="date" class="aa-input aa-input--date" />
            <span class="aa-form__tilde">至</span>
            <input v-model="form.endDate" type="date" class="aa-input aa-input--date" />
          </div>
        </div>
        <div v-if="errors.dateRange" class="aa-form__err aa-form__err--full">{{ errors.dateRange }}</div>

        <div class="aa-form__row">
          <label class="aa-form__label">教学周数</label>
          <div class="aa-form__field">
            <input v-model.number="form.teachingWeeks" type="number" min="1" max="30" class="aa-input aa-input--num" placeholder="如 18" />
            <div v-if="errors.teachingWeeks" class="aa-form__err">{{ errors.teachingWeeks }}</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label">考试周起</label>
          <div class="aa-form__field">
            <input v-model.number="form.examWeekStart" type="number" min="1" max="30" class="aa-input aa-input--num" placeholder="第几教学周开始考试，选填" />
            <div v-if="errors.examWeekStart" class="aa-form__err">{{ errors.examWeekStart }}</div>
          </div>
        </div>
      </div>

      <div class="aa-form__actions">
        <button class="mp-btn" @click="goBack">取消</button>
        <button class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">
          {{ submitting ? '创建中…' : '创建学期' }}
        </button>
      </div>
    </AppSectionCard>
  </ModulePageShell>
</template>

<script>
/** 新建学年学期（/admin/academic-affairs/terms/new）：POST /academic-affairs/terms。
 *  以代码为准：后端无学期更新端点，本页仅「新建」，编辑功能后续波次补。 */
import { ModulePageShell } from '@/components/business'
import { AppSectionCard, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const YEAR_RE = /^(\d{4})-(\d{4})$/

export default {
  name: 'AaTermFormView',
  components: { ModulePageShell, AppSectionCard, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      submitting: false,
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
  methods: {
    goBack() {
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
        (this.form.teachingWeeks < 1 || this.form.teachingWeeks > 30)) {
        e.teachingWeeks = '教学周数应在 1~30 之间'
      }
      if (this.form.examWeekStart != null && this.form.examWeekStart !== '' &&
        (this.form.examWeekStart < 1 || this.form.examWeekStart > 30)) {
        e.examWeekStart = '考试周起应在 1~30 之间'
      }
      this.errors = e
      return Object.keys(e).length === 0
    },
    async submit() {
      if (this.submitting) return
      if (!this.validate()) return
      this.submitting = true
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
      this.submitting = false
      if (res.code === 0) {
        toast.success('学期已创建，可在列表发布为当前学期')
        this.goBack()
      } else {
        toast.error(res.message || '创建失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
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
  border: 1px solid var(--border-300, #d0d3d9);
  border-radius: 6px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #1f2329);
  font-size: 14px;
  box-sizing: border-box;
}
.aa-input--date { width: 180px; }
.aa-input--num { width: 200px; }
.aa-form__tilde { color: var(--text-500, #646a73); }
.aa-form__hint {
  margin-top: 4px;
  font-size: 12px;
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
</style>
