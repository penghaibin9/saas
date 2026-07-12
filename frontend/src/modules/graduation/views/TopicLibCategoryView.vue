<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    title="调整题目分类"
    :subtitle="topic ? topic.title : ''"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else-if="topic" class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">分类 <i>*</i></span>
        <select v-model="category" class="ie-in">
          <option value="">请选择</option>
          <option v-for="c in GD_TOPIC_CATEGORY" :key="c" :value="c">{{ c }}</option>
        </select>
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
import { GD_TOPIC_CATEGORY } from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

export default {
  name: 'TopicLibCategoryView',
  components: { GraduationFormPageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { GD_TOPIC_CATEGORY, loading: true, error: '', topic: null, category: '', formError: '', submitting: false }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'category'
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
      this.category = d.data.category || ''
      this.loading = false
    },
    async submit() {
      if (!this.category) { this.formError = '请选择分类'; return }
      this.submitting = true
      const r = await gdTopicApi.updateTopic(this.topic.id, { title: this.topic.title, category: this.category })
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('分类已更新')
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
