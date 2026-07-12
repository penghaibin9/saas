<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="分配成果互查"
    subtitle="指定互查学生与被评学生（同批次学生互相检查成果）"
    back-to="/admin/graduation/more?panel=peer"
  >
    <ErrorState v-if="optsError" :description="optsError" @retry="loadStudents" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">被评学生 <i>*</i></span>
        <AppStudentPicker v-model="form.gdStudentId" :options="studentOptions" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索被评学生" />
      </div>
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">互查学生 <i>*</i></span>
        <AppStudentPicker v-model="form.reviewerGdStudentId" :options="reviewerOptions" :remote-search="searchReviewers" placeholder="按姓名 / 学号搜索互查学生" />
      </div>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/more?panel=peer')">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">分配</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { ErrorState } from '@/components/business'
import { AppStudentPicker } from '@/components/common'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMorePeerView',
  components: { GraduationFormPageShell, ErrorState, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { gdStudentId: '', reviewerGdStudentId: '' },
      studentOpts: [], optsError: '', kw: '',
      formError: '', submitting: false
    }
  },
  computed: {
    studentOptions() {
      return this.studentOpts.map(this.mapStu)
    },
    reviewerOptions() {
      return this.studentOpts.map((s) => ({ ...this.mapStu(s), disabled: s.id === this.form.gdStudentId }))
    }
  },
  created() {
    this.loadStudents()
  },
  methods: {
    mapStu(s) {
      return { label: `${s.name}（${s.studentNo}）${s.topicTitle ? ' · ' + s.topicTitle : ''}`, value: s.id }
    },
    async searchStudents(keyword) {
      const res = await gdStudentApi.getStudents({ keyword, pageSize: 20 })
      if (res.code !== 0) throw new Error(res.message || '搜索失败')
      return res.data.list.map(this.mapStu)
    },
    async searchReviewers(keyword) {
      const res = await gdStudentApi.getStudents({ keyword, pageSize: 20 })
      if (res.code !== 0) throw new Error(res.message || '搜索失败')
      return res.data.list.map((s) => ({ ...this.mapStu(s), disabled: s.id === this.form.gdStudentId }))
    },
    async loadStudents() {
      this.optsError = ''
      const res = await gdStudentApi.getStudents({ keyword: this.kw, pageSize: 100 })
      if (res.code === 0) {
        this.studentOpts = res.data.list
      } else {
        this.studentOpts = []
        this.optsError = res.message || '学生列表加载失败'
      }
    },
    async submit() {
      this.formError = ''
      if (!this.form.gdStudentId || !this.form.reviewerGdStudentId) { this.formError = '请选择被评学生和互查学生'; return }
      if (this.form.gdStudentId === this.form.reviewerGdStudentId) { this.formError = '互查学生不能是被评学生本人'; return }
      this.submitting = true
      const res = await graduationMoreApi.assignPeer(this.form.gdStudentId, this.form.reviewerGdStudentId)
      this.submitting = false
      if (res.code === 0) { toast.success('已分配互查'); this.$router.push('/admin/graduation/more?panel=peer') }
      else this.formError = res.message
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
