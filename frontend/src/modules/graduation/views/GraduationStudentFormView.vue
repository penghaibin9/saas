<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="毕设学生建档"
    subtitle="选择学生并关联毕设批次"
    :back-to="backTo"
  >
    <form class="ie-form" @submit.prevent="submit">
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">学生 <i>*</i></span>
        <AppStudentPicker v-model="form.studentId" :options="studentOptions" :remote-search="searchStudents" placeholder="按学号 / 姓名搜索学生" />
      </div>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">毕设批次</span>
        <select v-model="form.batchId" class="ie-in">
          <option value="">不关联批次</option>
          <option v-for="b in batchOpts" :key="b.id" :value="b.id">{{ b.batchName }}（{{ b.batchNo }}）</option>
        </select>
      </label>
      <label class="ie-fld"><span class="ie-lbl">指导教师</span><input v-model.trim="form.advisorName" class="ie-in" /></label>
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
import { AppStudentPicker } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

const mapStu = (s) => ({ label: `${s.name}（${s.studentNo}）`, value: s.id })

export default {
  name: 'GraduationStudentFormView',
  components: { GraduationFormPageShell, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { studentId: '', batchId: '', advisorName: '' },
      studentOpts: [], batchOpts: [], formError: '', submitting: false
    }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'roster'
      return `/admin/graduation/students?panel=${panel}`
    },
    studentOptions() {
      return this.studentOpts.map(mapStu)
    }
  },
  async created() {
    const [s, b] = await Promise.all([gdStudentApi.getStudentOptions(), gdStudentApi.getBatchOptions()])
    if (s.code === 0) this.studentOpts = s.data
    if (b.code === 0) this.batchOpts = b.data
  },
  methods: {
    /** 学生远程搜索（学籍库真实接口，按姓名/学号，数据范围由后端裁定） */
    async searchStudents(keyword) {
      const res = await gdStudentApi.getStudentOptions(keyword)
      if (res.code !== 0) throw new Error(res.message || '搜索失败')
      return res.data.map(mapStu)
    },
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
