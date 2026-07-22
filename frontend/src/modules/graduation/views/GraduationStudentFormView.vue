<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="毕设学生建档"
    subtitle="选择学生并关联毕设批次"
    :back-to="backTo"
  >
    <form class="ie-form" @submit.prevent="submit">
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">学生 <i>*</i></span>
        <AppGraduationCandidateStudentPicker v-model="form.studentId" placeholder="按学号 / 姓名搜索学生" />
      </div>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">毕设批次</span>
        <AppGraduationDesignBatchPicker v-model="form.batchId" clearable placeholder="不关联批次" />
      </label>
      <div class="ie-fld"><span class="ie-lbl">指导教师</span><AppGraduationMentorPicker v-model="form.advisorName" clearable /></div>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">建档</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { AppGraduationCandidateStudentPicker, AppGraduationDesignBatchPicker, AppGraduationMentorPicker } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentFormView',
  components: { GraduationFormPageShell, AppGraduationCandidateStudentPicker, AppGraduationDesignBatchPicker, AppGraduationMentorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { studentId: '', batchId: '', advisorName: '' }, formError: '', submitting: false
    }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'roster'
      return `/admin/graduation/students?panel=${panel}`
    }
  },
  methods: {
    async submit() {
      this.formError = ''
      if (!this.form.studentId) { this.formError = '请选择学生'; return }
      this.submitting = true
      try {
        const body = { studentId: this.form.studentId, advisorName: this.form.advisorName || undefined }
        if (this.form.batchId) body.batchId = this.form.batchId
        const res = await gdStudentApi.createStudent(body)
        if (res.code === 0) { toast.success('已建档'); this.$router.push(this.backTo) }
        else this.formError = res.message
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
