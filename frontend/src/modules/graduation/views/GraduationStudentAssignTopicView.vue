<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="student ? `分配选题 · ${student.name}` : '分配选题'"
    subtitle="仅「已确认」且未满员的选题可选"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <p class="ie-hint">仅「已确认」且未满员的选题可选（来自选题库真实数据）。</p>
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">选题 <i>*</i></span>
        <AppGraduationTopicPicker v-model="assignTopicId" placeholder="按题目名 / 导师搜索选题" />
      </div>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template v-if="student" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !assignTopicId" @click="submit">确认分配</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppGraduationTopicPicker } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationStudentAssignTopicView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppGraduationTopicPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', student: null,
      assignTopicId: '', formError: '', submitting: false
    }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'topic'
      return `/admin/graduation/students?panel=${panel}`
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const s = await gdStudentApi.getStudentDetail(id)
      if (s.code !== 0) { this.error = s.message; this.loading = false; return }
      this.student = s.data
      this.assignTopicId = s.data.topicId || ''
      this.loading = false
    },
    async submit() {
      this.formError = ''
      this.submitting = true
      try {
        const res = await gdStudentApi.assignTopic(this.student.id, { topicId: this.assignTopicId })
        if (res.code === 0) { toast.success('已分配选题'); this.$router.push(this.backTo) }
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
