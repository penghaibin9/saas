<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="编辑课题"
    subtitle="修改已入池课题信息"
    back-to="/admin/graduation/topics"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目名称 <i>*</i></span>
        <input v-model.trim="form.title" class="ie-in" />
      </label>
      <label class="ie-fld"><span class="ie-lbl">指导教师</span><input v-model.trim="form.advisorName" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">容量</span>
        <input v-model.number="form.capacity" type="number" min="1" max="99" class="ie-in" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目要求</span>
        <textarea v-model.trim="form.requirements" class="ie-in" rows="3" />
      </label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template v-if="!loading && !error" #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/topics')">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { toast } from '@/utils/toast'

export default {
  name: 'TopicManageFormView',
  components: { GraduationFormPageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', editing: null,
      form: { title: '', advisorName: '', capacity: 1, requirements: '' },
      formError: '', submitting: false
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const d = await gdTopicApi.getTopicDetail(this.$route.params.id)
      if (d.code !== 0) { this.error = d.message; this.loading = false; return }
      this.editing = d.data
      this.form = {
        title: d.data.title, advisorName: d.data.advisorName || '',
        capacity: d.data.capacity, requirements: d.data.requirements || ''
      }
      this.loading = false
    },
    async submit() {
      if (!this.form.title || this.form.title.length < 2) { this.formError = '题目至少2字'; return }
      this.submitting = true
      const r = await gdTopicApi.updateTopic(this.editing.id, this.form)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('已保存')
      this.$router.push('/admin/graduation/topics')
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
