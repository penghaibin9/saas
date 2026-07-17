<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    title="调整题目容量"
    :subtitle="topic ? topic.title : ''"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else-if="topic" class="ie-form" @submit.prevent="submit">
      <div class="mp-kv"><span class="mp-kv__k">当前已选</span><span class="mp-kv__v">{{ topic.selected }} 人</span></div>
      <label class="ie-fld"><span class="ie-lbl">新容量 <i>*</i></span>
        <input v-model.number="capacity" type="number" :min="topic.selected || 1" max="99" class="ie-in" />
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
  name: 'TopicLibCapacityView',
  components: { GraduationFormPageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', topic: null, capacity: 1, formError: '', submitting: false }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'capacity'
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
      this.capacity = d.data.capacity
      this.loading = false
    },
    async submit() {
      const cap = Number(this.capacity)
      if (!cap || cap < (this.topic.selected || 1)) {
        this.formError = `容量不能小于已选人数（${this.topic.selected || 0}）`
        return
      }
      this.submitting = true
      const r = await gdTopicApi.updateCapacity(this.topic.id, cap)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('容量已更新')
      this.$router.push(this.backTo)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
