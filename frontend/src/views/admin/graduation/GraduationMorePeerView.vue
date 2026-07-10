<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="分配成果互查"
    subtitle="指定互查学生与被评学生（同批次学生互相检查成果）"
    back-to="/admin/graduation/more?panel=peer"
  >
    <ErrorState v-if="optsError" :description="optsError" @retry="loadStudents" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">搜索学生</span>
        <input v-model.trim="kw" class="ie-in" placeholder="按姓名 / 学号搜索后再选择" @input="loadStudents" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">被评学生 <i>*</i></span>
        <select v-model="form.gdStudentId" class="ie-in">
          <option value="">请选择被评学生</option>
          <option v-for="s in studentOpts" :key="s.id" :value="s.id">{{ s.name }}（{{ s.studentNo }}）{{ s.topicTitle ? ' · ' + s.topicTitle : '' }}</option>
        </select>
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">互查学生 <i>*</i></span>
        <select v-model="form.reviewerGdStudentId" class="ie-in">
          <option value="">请选择互查学生</option>
          <option v-for="s in studentOpts" :key="s.id" :value="s.id" :disabled="s.id === form.gdStudentId">{{ s.name }}（{{ s.studentNo }}）</option>
        </select>
      </label>
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
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMorePeerView',
  components: { GraduationFormPageShell, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { gdStudentId: '', reviewerGdStudentId: '' },
      studentOpts: [], optsError: '', kw: '',
      formError: '', submitting: false
    }
  },
  created() {
    this.loadStudents()
  },
  methods: {
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
