<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    title="维护题目要求"
    :subtitle="topic ? topic.title : ''"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else-if="topic" class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目要求 <i>*</i></span>
        <textarea v-model.trim="form.requirements" class="ie-in" rows="4" placeholder="不少于10字，说明研究/开发目标与验收标准" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">预期成果</span>
        <textarea v-model.trim="form.outcome" class="ie-in" rows="2" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">技能要求</span>
        <textarea v-model.trim="form.skills" class="ie-in" rows="2" />
      </label>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template v-if="topic" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
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
  name: 'TopicLibRequirementsView',
  components: { GraduationFormPageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', topic: null,
      form: { requirements: '', outcome: '', skills: '' },
      formError: '', submitting: false
    }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'requirements'
      return `/admin/graduation/topic-lib?panel=${panel}`
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const d = await gdTopicApi.getTopicDetail(this.$route.params.id)
      if (d.code !== 0) { this.error = d.message; this.loading = false; return }
      this.topic = d.data
      this.form = { requirements: d.data.requirements || '', outcome: d.data.outcome || '', skills: d.data.skills || '' }
      this.loading = false
    },
    async submit() {
      if (!this.form.requirements || this.form.requirements.length < 10) {
        this.formError = '题目要求至少10字'
        return
      }
      this.submitting = true
      const r = await gdTopicApi.updateTopic(this.topic.id, {
        title: this.topic.title,
        requirements: this.form.requirements,
        outcome: this.form.outcome,
        skills: this.form.skills
      })
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('要求已保存')
      this.$router.push(this.backTo)
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
