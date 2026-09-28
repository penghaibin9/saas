<template>
  <ModulePageShell
    :title="detail ? detail.studentName + ' · ' + detail.reportTypeLabel : '过程报告批阅'"
    :subtitle="detail ? [detail.className, detail.enterpriseName].filter((item) => item && item !== '-' && item !== 'null').join(' · ') : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ReviewQueueBar
      ref="queueBar"
      :current-id="$route.params.id"
      kind="process-report"
      :make-path="(id) => ({ path: '/admin/internship/process-reports/' + id, query: $route.query })"
      :list-fallback="$router.resolve({ path: '/admin/internship/reports', query: $route.query }).fullPath"
      style="margin-bottom: var(--space-3)"
    />
    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />
    <ErrorState v-if="error" :description="error" @retry="load" @back="$refs.queueBar.backToList()" />
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
            <!-- 同 WeeklyReportDetailView：提示条不能放进会被状态换掉的那块模板里 -->
            <AppInlineAlert v-if="conflict.active" type="warning" title="报告已更新，本次批阅已暂停"
              description="评语已保留，请返回台账重新打开报告，核对最新提交后再批阅。"><p v-if="conflict.kept" class="pr-kept">{{ conflict.kept }}</p></AppInlineAlert>
            <template v-if="detail.status === 'PENDING_REVIEW' && canReview">
              <label class="mp-radio" :class="{ 'is-active': action === 'APPROVE' }">
                <input v-model="action" type="radio" name="process-report-action" value="APPROVE" :disabled="submitting || conflict.active" />
                <div><div class="mp-radio__title">通过</div></div>
              </label>
              <label class="mp-radio" :class="{ 'is-active': action === 'RETURN' }">
                <input v-model="action" type="radio" name="process-report-action" value="RETURN" :disabled="submitting || conflict.active" />
                <div><div class="mp-radio__title">退回修改</div><div class="mp-radio__desc">退回原因必填（≥5 字）</div></div>
              </label>
              <div v-if="action === 'APPROVE'" class="pr-rating">
                <label for="process-rating">五级评价 <b>*</b></label>
                <select id="process-rating" v-model="ratingLevel" :disabled="submitting || conflict.active">
                  <option value="">请选择评价等级</option>
                  <option v-for="item in ratingOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
                <label v-if="isSummary" for="summary-score">总结百分制评分 <b>*</b></label>
                <input v-if="isSummary" id="summary-score" v-model.trim="summaryScore" type="number" min="0" max="100" step="0.5" placeholder="0～100" :disabled="submitting || conflict.active" />
                <span>五级评价用于分类统计；实习总结同时记录 0～100 分，均绑定当前提交版本。</span>
              </div>
              <AppTemplateChips class="pr-chips" :options="activeChips" size="compact" @pick="onPickChip" />
              <AppTextarea aria-label="批阅意见" :disabled="submitting || conflict.active" v-model="comment" :rows="4" :placeholder="action === 'RETURN' ? '请写明退回原因…' : '评语（选填）'" />
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppButton :variant="action === 'RETURN' ? 'warning' : 'primary'" :loading="submitting" :disabled="conflict.active" style="flex: 1" @click="submit(action)">{{ action === 'RETURN' ? '退回修改' : '确认通过' }}</AppButton>
              </div>
            </template>
            <AppInlineAlert v-else-if="detail.status === 'PENDING_REVIEW'" type="info" description="当前账号可查看报告，暂无批阅权限。" />
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
import { AppStatusTag, AppAuditTrail, AppTemplateChips, AppTextarea, AppInlineAlert } from '@/components/common'
import { AppButton } from '@/components/ui'
import ReviewQueueBar from './components/ReviewQueueBar.vue'
import { canCode } from '@/modules/internship/composables/permission'
import ActionReceipt from './components/ActionReceipt.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { toast } from '@/utils/toast'
import { APPROVE_REPORT_SHORT, REJECT_PROCESS_REPORT } from '@/modules/internship/constants/presetPrompts'

export default {
  name: 'ProcessReportDetailView',
  components: { ModulePageShell, AppStatusTag, AppAuditTrail, AppTemplateChips, AppTextarea,
    LoadingState, ErrorState, EmptyState, AppButton, ReviewQueueBar, AppInlineAlert, ActionReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, action: 'APPROVE', comment: '', ratingLevel: '', summaryScore: '', formError: '', loadEpoch: 0,
      submitting: false, conflict: emptyConflict(), lastReceipt: null }
  },
  computed: {
    canReview() { return canCode(this.ctx, 'internship.report.review') },
    isSummary() { return String(this.detail?.reportType || '').toUpperCase() === 'SUMMARY' },
    ratingOptions() {
      return [
        { value: 1, label: '1级 · 需明显改进' },
        { value: 2, label: '2级 · 待提升' },
        { value: 3, label: '3级 · 合格' },
        { value: 4, label: '4级 · 良好' },
        { value: 5, label: '5级 · 优秀' }
      ]
    },
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
      this.ratingLevel = ''
      this.summaryScore = ''
      this.formError = ''
      this.conflict = emptyConflict(); this.lastReceipt = null
      this.load()
    }
  },
  created() { this.load() },
  beforeUnmount() { this.loadEpoch++ },
  methods: {
    onPickChip(text) {
      if (!text || this.submitting || this.conflict.active) return
      const cur = (this.comment || '').trim()
      this.comment = cur ? cur + '；' + text : text
    },
    async load() {
      const epoch = ++this.loadEpoch
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const res = await internshipApi.getProcessReportDetail(id)
      if (epoch !== this.loadEpoch || id !== this.$route.params.id) return
      if (res.code === 0) this.detail = res.data
      else this.error = res.message || '加载失败'
      this.loading = false
    },
    async submit(action) {
      if (this.submitting || this.loading || this.error || this.conflict.active || !this.canReview || this.detail?.status !== 'PENDING_REVIEW' || !['APPROVE', 'RETURN'].includes(action)) return
      const current = this.detail, id = this.$route.params.id
      if (action === 'RETURN' && (this.comment || '').trim().length < 5) {
        this.formError = '退回原因必填且不少于 5 字'
        return
      }
      if (action === 'APPROVE' && ![1, 2, 3, 4, 5].includes(Number(this.ratingLevel))) {
        this.formError = '通过报告时必须选择 1～5 级评价'
        toast.error(this.formError)
        return
      }
      if (action === 'APPROVE' && this.isSummary) {
        const score = Number(this.summaryScore)
        if (!Number.isFinite(score) || score < 0 || score > 100) {
          this.formError = '通过实习总结时必须填写 0～100 分'
          toast.error(this.formError)
          return
        }
      }
      this.formError = ''
      this.submitting = true
      const res = await internshipApi.reviewProcessReport(this.$route.params.id, {
        action,
        comment: this.comment,
        ratingLevel: action === 'APPROVE' ? Number(this.ratingLevel) : undefined,
        summaryScore: action === 'APPROVE' && this.isSummary ? Number(this.summaryScore) : undefined,
        batchId: this.detail?.batchId || this.$route.query.batchId || undefined,
        expectedVersion: this.detail?.version
      })
      this.submitting = false
      if (this.detail !== current || this.$route.params.id !== id) return
      if (res.code === 0) {
        this.lastReceipt = {
          id: res.data?.id, status: res.data?.status, statusLabel: res.data?.statusLabel,
          version: res.data?.version, actionLabel: action === 'APPROVE' ? '过程报告通过' : '过程报告退回修改',
          objectLabel: `${this.detail.studentName} · ${this.detail.reportTypeLabel} ${this.detail.periodKey}`,
          auditText: '报告状态、评语与审批留痕已同事务提交',
          nextStep: action === 'RETURN' ? '等待学生修正后重交' : '可继续批阅队列下一篇'
        }
        toast.success(this.isSummary ? '批阅完成：五级评价和总结分数已留痕' : '批阅完成：五级评价已留痕')
        this.ratingLevel = ''
        this.summaryScore = ''
        this.load()
        // 连续批阅：有下一条自动跳转，无则提示队列完成
        this.$refs.queueBar && this.$refs.queueBar.advance()
      } else if (isConflict(res)) {
        // 撞车：评语原样留着，只拉最新真值（含 version）让老师自己决定要不要重新提交
        this.conflict = { ...emptyConflict(), active: true }
        const captured = await captureConflict({
          res,
          kept: this.comment,
          refresh: async () => { await this.load(); if (this.error) throw new Error(this.error) },
          latest: () => {
            if (!this.detail) throw new Error('最新详情未拉回')
            return [
              { label: '最新状态', value: this.detail.statusLabel || this.detail.status || '' },
              { label: '最新评语', value: this.detail.reviewComment || '' }
            ]
          }
        })
        if (this.$route.params.id === id) this.conflict = captured
      } else {
        toast.error(res.message || '批阅失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pr-kept { white-space: pre-wrap; overflow-wrap: anywhere; }
.pr-rating { display:grid; gap:7px; margin-bottom:var(--space-3); padding:12px; border:1px solid var(--border-base); border-radius:8px; background:var(--bg-page); }
.pr-rating label { font-size:13px; font-weight:600; color:var(--text-primary); }
.pr-rating label b { color:var(--danger-600); }
.pr-rating select,.pr-rating input { height:38px; box-sizing:border-box; padding:0 10px; border:1px solid var(--border-base); border-radius:7px; background:var(--bg-card); color:var(--text-primary); }
.pr-rating span { font-size:11px; line-height:1.5; color:var(--text-secondary); }
.pr-chips { margin-bottom: var(--space-2); }
</style>
