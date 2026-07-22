<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="新建选题轮次"
    subtitle="设置轮次名称、批次、时间与最多志愿数"
    back-to="/admin/graduation/topic-rounds"
  >
    <form class="ie-form" @submit.prevent="submit">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">轮次名称 <i>*</i></span>
        <input v-model.trim="form.roundName" class="ie-in" placeholder="如 2026届第一轮选题" />
      </label>
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">毕设批次</span>
        <AppGraduationDesignBatchPicker v-model="form.batchId" clearable placeholder="不关联批次" @change="onBatchChange" />
      </label>
      <label class="ie-fld"><span class="ie-lbl">轮次序号</span><input v-model.number="form.roundNo" type="number" min="1" class="ie-in" /></label>
      <label class="ie-fld"><span class="ie-lbl">最多志愿数</span><input v-model.number="form.maxChoices" type="number" min="1" max="10" class="ie-in" /></label>
      <AppDateTimePicker v-model="form.startAt" class="ie-fld" label="开始时间" role="start" :end-value="form.endAt" hint="选题开放时间" />
      <AppDeadlinePicker v-model="form.endAt" class="ie-fld" label="结束时间（截止）" :batch="selectedBatch" hint="选题截止，默认 23:59" />
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/topic-rounds')">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">创建</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { AppDateTimePicker, AppDeadlinePicker } from '@/components/common/date'
import { gdTopicRoundApi } from '@/modules/graduation/api/graduation-topic-round.api'
import { AppGraduationDesignBatchPicker } from '@/components/common'
import { toast } from '@/utils/toast'
import { toDateTimeInputValue, withDeadlineTime, addDays, validateRange } from '@/utils/dateUtils'

const EMPTY_FORM = () => ({
  roundName: '', batchId: '', roundNo: 1, maxChoices: 3,
  startAt: toDateTimeInputValue(new Date()),
  endAt: withDeadlineTime(addDays(new Date(), 14))
})

export default {
  name: 'TopicRoundFormView',
  components: { GraduationFormPageShell, AppDateTimePicker, AppDeadlinePicker, AppGraduationDesignBatchPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { form: EMPTY_FORM(), selectedBatchInfo: null, formError: '', submitting: false }
  },
  computed: {
    selectedBatch() {
      return this.selectedBatchInfo
    }
  },
  methods: {
    onBatchChange(_, items) {
      this.selectedBatchInfo = items?.[0]?.raw || null
    },
    async submit() {
      if (!this.form.roundName || this.form.roundName.length < 2) { this.formError = '名称至少2字'; return }
      const range = validateRange(this.form.startAt, this.form.endAt)
      if (!range.ok) { this.formError = range.message; return }
      this.submitting = true
      const body = {
        ...this.form, batchId: this.form.batchId || null,
        startAt: this.form.startAt ? new Date(this.form.startAt).toISOString() : null,
        endAt: this.form.endAt ? new Date(this.form.endAt).toISOString() : null
      }
      const r = await gdTopicRoundApi.createRound(body)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('轮次已创建')
      this.$router.push('/admin/graduation/topic-rounds')
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
