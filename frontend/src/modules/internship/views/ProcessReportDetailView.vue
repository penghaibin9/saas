<template>
  <ModulePageShell
    :title="detail ? detail.studentName + ' · ' + detail.reportTypeLabel : '过程报告批阅'"
    :subtitle="detail ? detail.className + ' · ' + detail.enterpriseName : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ReviewQueueBar
      ref="queueBar"
      :current-id="$route.params.id"
      kind="process-report"
      :make-path="(id) => '/admin/internship/process-reports/' + id"
      list-fallback="/admin/internship/reports?type=daily"
      style="margin-bottom: var(--space-3)"
    />
    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">{{ detail.reportTypeLabel }} · {{ detail.periodKey }}</span>
          <AppStatusTag :status="detail.status">{{ detail.statusLabel }}</AppStatusTag>
        </div>
        <div class="mp-card__body">
          <div class="mp-kv"><span class="mp-kv__k">提交时间</span><span class="mp-kv__v">{{ detail.submitAt }} · {{ detail.wordCount }} 字</span></div>
          <div style="margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.8; white-space: pre-wrap">{{ detail.content }}</div>
        </div>
      </section>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">批阅</span></div>
          <div class="mp-card__body">
            <template v-if="detail.status === 'PENDING_REVIEW'">
              <div class="mp-radio" :class="{ 'is-active': action === 'APPROVE' }" @click="action = 'APPROVE'">
                <input type="radio" :checked="action === 'APPROVE'" />
                <div><div class="mp-radio__title">通过</div></div>
              </div>
              <div class="mp-radio" :class="{ 'is-active': action === 'RETURN' }" @click="action = 'RETURN'">
                <input type="radio" :checked="action === 'RETURN'" />
                <div><div class="mp-radio__title">退回修改</div><div class="mp-radio__desc">退回原因必填（≥5 字）</div></div>
              </div>
              <AppTemplateChips class="pr-chips" :options="activeChips" size="compact" @pick="onPickChip" />
              <AppTextarea v-model="comment" :rows="4" :placeholder="action === 'RETURN' ? '请写明退回原因…' : '评语（选填）'" />
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppButton variant="primary" :loading="submitting" style="flex: 1" @click="submit('APPROVE')">通过</AppButton>
                <AppButton variant="warning" :loading="submitting" style="flex: 1" @click="submit('RETURN')">退回</AppButton>
              </div>
            </template>
            <EmptyState v-else :title="'该报告' + (detail.status === 'APPROVED' ? '已通过' : '已退回')" description="批阅结果已同步学生端" />
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">操作留痕</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="trailRecords" empty-text="暂无记录" />
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppAuditTrail, AppTemplateChips, AppTextarea } from '@/components/common'
import { AppButton } from '@/components/ui'
import ReviewQueueBar from './components/ReviewQueueBar.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'
import { APPROVE_REPORT_SHORT, REJECT_PROCESS_REPORT } from '@/modules/internship/constants/presetPrompts'

export default {
  name: 'ProcessReportDetailView',
  components: { ModulePageShell, AppStatusTag, AppAuditTrail, AppTemplateChips, AppTextarea, LoadingState, ErrorState, EmptyState, AppButton, ReviewQueueBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, action: 'APPROVE', comment: '', formError: '', submitting: false }
  },
  computed: {
    activeChips() { return this.action === 'RETURN' ? REJECT_PROCESS_REPORT : APPROVE_REPORT_SHORT },
    trailRecords() {
      return (this.detail?.auditTrail || []).map((t, i) => ({
        id: i, actor: t.operator, at: t.occurredAt, action: t.action,
        reason: t.detail && (t.detail.comment || '')
      }))
    }
  },
  watch: {
    // 连续批阅队列跳转（同组件复用）时必须重置本页状态并重新加载
    '$route.params.id'(id, oldId) {
      if (!id || id === oldId) return
      this.detail = null
      this.action = 'APPROVE'
      this.comment = ''
      this.formError = ''
      this.load()
    }
  },
  created() { this.load() },
  methods: {
    onPickChip(text) {
      if (!text) return
      const cur = (this.comment || '').trim()
      this.comment = cur ? cur + '；' + text : text
    },
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const res = await internshipApi.getProcessReportDetail(id)
      if (id !== this.$route.params.id) return // 队列快速跳转时丢弃过期响应
      if (res.code === 0) this.detail = res.data
      else this.error = res.message || '加载失败'
      this.loading = false
    },
    async submit(action) {
      if (action === 'RETURN' && (this.comment || '').trim().length < 5) {
        this.formError = '退回原因必填且不少于 5 字'
        return
      }
      this.formError = ''
      this.submitting = true
      const res = await internshipApi.reviewProcessReport(this.$route.params.id, {
        action, comment: this.comment, expectedVersion: this.detail?.version
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('批阅完成')
        this.load()
        // 连续批阅：有下一条自动跳转，无则提示队列完成
        this.$refs.queueBar && this.$refs.queueBar.advance()
      } else {
        toast.error(res.message || '批阅失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pr-chips { margin-bottom: var(--space-2); }
</style>
