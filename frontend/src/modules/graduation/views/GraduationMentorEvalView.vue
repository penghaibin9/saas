<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="mentor ? mentor.teacherName + ' · 导师评价' : '导师评价'"
    subtitle="评价周期 / 评分 / 等级 / 评价意见"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else>
      <form class="ie-form" @submit.prevent="submit">
        <label class="ie-fld"><span class="ie-lbl">评价周期</span><input v-model.trim="evalForm.period" class="ie-in" placeholder="如 2026春" /></label>
        <label class="ie-fld"><span class="ie-lbl">评分（0-100）<i>*</i></span><input v-model.number="evalForm.score" type="number" min="0" max="100" class="ie-in" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">评价等级 <i>*</i></span>
          <AppSelect v-model="evalForm.level" :options="levelOptions" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">评价意见</span><textarea v-model.trim="evalForm.note" class="ie-in" rows="3" /></label>
        <p v-if="evalError" class="ie-err">{{ evalError }}</p>
      </form>
      <div class="gm-section-title" style="margin-top: var(--space-3)">评价历史</div>
      <EmptyState v-if="!evalHistory.length" title="暂无评价记录" />
      <ul v-else class="gm-trail">
        <li v-for="e in evalHistory" :key="e.id" class="gm-trail__item">
          <span>{{ e.level }} · {{ e.score }}分 {{ e.period ? '（' + e.period + '）' : '' }}{{ e.note ? ' · ' + e.note : '' }}</span>
          <span class="gm-trail__meta">{{ e.evaluatedBy }} · {{ e.evaluatedAt }}</span>
        </li>
      </ul>
    </template>
    <template v-if="mentor" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">返回</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">提交评价</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { AppSelect } from '@/components/common'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMentorEvalView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', mentor: null,
      levelOptions: ['优秀', '良好', '合格', '不合格'].map((value) => ({ value, label: value })),
      evalForm: { period: '', score: 90, level: '良好', note: '' },
      evalError: '', evalHistory: [], submitting: false
    }
  },
  computed: {
    backTo() { return `/admin/graduation/mentors/${this.$route.params.id}` }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const res = await graduationMentorApi.getMentorDetail(id)
      if (res.code !== 0) { this.error = res.message; this.loading = false; return }
      this.mentor = res.data
      const h = await graduationMentorApi.getEvals(id)
      if (h.code === 0) this.evalHistory = h.data.list
      this.loading = false
    },
    async submit() {
      this.evalError = ''
      if (this.evalForm.score === '' || this.evalForm.score < 0 || this.evalForm.score > 100) {
        this.evalError = '评分须 0-100'
        return
      }
      this.submitting = true
      const res = await graduationMentorApi.createEval(this.mentor.id, this.evalForm)
      this.submitting = false
      if (res.code === 0) {
        toast.success('已评价')
        const h = await graduationMentorApi.getEvals(this.mentor.id)
        if (h.code === 0) this.evalHistory = h.data.list
        this.evalForm.note = ''
      } else this.evalError = res.message
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gm-section-title { font-size: 13px; font-weight: 600; margin-bottom: var(--space-2); }
.gm-trail__item { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px dashed var(--line, #eef1f6); font-size: 13px; }
.gm-trail__meta { color: var(--t3, #64748b); font-size: 12px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
