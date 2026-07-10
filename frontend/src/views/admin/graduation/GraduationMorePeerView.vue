<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="分配成果互查"
    subtitle="指定互查学生与被评学生"
    back-to="/admin/graduation/more?panel=peer"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">被评学生（毕设学生ID）<i>*</i></span><input v-model.trim="form.gdStudentId" class="ie-in" placeholder="被互查学生 t_gd_student.id" /></label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">互查学生（毕设学生ID）<i>*</i></span><input v-model.trim="form.reviewerGdStudentId" class="ie-in" placeholder="互查人 t_gd_student.id" /></label>
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
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMorePeerView',
  components: { GraduationFormPageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: { gdStudentId: '', reviewerGdStudentId: '' },
      formError: '', submitting: false
    }
  },
  methods: {
    async submit() {
      this.formError = ''
      if (!this.form.gdStudentId || !this.form.reviewerGdStudentId) { this.formError = '两个学生ID必填'; return }
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
