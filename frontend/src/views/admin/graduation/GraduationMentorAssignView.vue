<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="form.mode === 'change' ? '调导师' : '分配导师'"
    subtitle="须导师「已认证」且未满员，调导师原因≥5字"
    :back-to="backTo"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">学生</span><input class="ie-in" :value="form.studentLabel" disabled /></label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">导师 <i>*</i></span>
        <select v-model="form.mentorId" class="ie-in">
          <option value="">请选择已认证且未满员的导师</option>
          <option v-for="m in availableMentors" :key="m.id" :value="m.id">{{ m.teacherName }}（{{ m.capacityText }}）</option>
        </select>
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">{{ form.mode === 'change' ? '调导师原因（≥5字）' : '分配原因' }}<i v-if="form.mode === 'change'">*</i></span><textarea v-model.trim="form.reason" class="ie-in" rows="2" /></label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">确认</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMentorAssignView',
  components: { GraduationFormPageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { mode: 'assign', studentId: '', studentLabel: '', mentorId: '', reason: '' },
      availableMentors: [], formError: '', submitting: false
    }
  },
  computed: {
    backTo() { return '/admin/graduation/mentors?panel=assign' }
  },
  async created() {
    const studentId = this.$route.params.studentId || this.$route.query.studentId
    const mode = this.$route.query.mode === 'change' ? 'change' : 'assign'
    this.form.mode = mode
    if (studentId) {
      const res = await gdStudentApi.getStudentDetail(studentId)
      if (res.code === 0) {
        this.form.studentId = studentId
        this.form.studentLabel = `${res.data.name}（${res.data.studentNo}）`
      }
    }
    await this.loadAvailableMentors()
  },
  methods: {
    async loadAvailableMentors() {
      const res = await graduationMentorApi.getMentors({ qualificationStatus: 'QUALIFIED', hasCapacity: 'true', pageSize: 200 })
      this.availableMentors = res.code === 0 ? res.data.list : []
    },
    async submit() {
      this.formError = ''
      if (!this.form.mentorId) { this.formError = '请选择导师'; return }
      if (this.form.mode === 'change' && (!this.form.reason || this.form.reason.length < 5)) {
        this.formError = '调导师原因至少 5 字'
        return
      }
      this.submitting = true
      try {
        const res = this.form.mode === 'change'
          ? await graduationMentorApi.changeMentor(this.form.studentId, this.form.mentorId, this.form.reason)
          : await graduationMentorApi.assignMentor(this.form.studentId, this.form.mentorId, this.form.reason)
        if (res.code === 0) { toast.success('已保存'); this.$router.push(this.backTo) }
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
