<template>
  <ModulePageShell
    :title="detail ? detail.studentName + ' · ' + detail.week + '周报批阅' : '周报批阅'"
    :subtitle="detail ? detail.className + ' · ' + detail.enterpriseName : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ReviewQueueBar
      ref="queueBar"
      :current-id="$route.params.id"
      kind="weekly-report"
      :make-path="(id) => '/admin/internship/reports/' + id"
      list-fallback="/admin/internship/reports"
      style="margin-bottom: var(--space-3)"
    />
    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">{{ detail.week }}周报 · {{ detail.version }}</span>
            <span>
              <AppStatusTag v-if="detail.isResubmit" type="info">重交件</AppStatusTag>
              <AppRiskTag v-if="detail.riskFlag" :level="detail.riskFlag" label="风险学生" style="margin-left: var(--space-2)" />
            </span>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">提交时间</span><span class="mp-kv__v">{{ detail.submitAt }} · {{ detail.wordCount }} 字</span></div>
            <div class="mp-kv"><span class="mp-kv__k">岗位</span><span class="mp-kv__v">{{ detail.positionName }}</span></div>
            <div style="margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.8">
              <p style="margin: 0 0 var(--space-2)"><b style="color: var(--text-primary)">本周工作内容：</b>{{ detail.content.work }}</p>
              <p style="margin: 0 0 var(--space-2)"><b style="color: var(--text-primary)">收获与问题：</b>{{ detail.content.harvest }}</p>
              <p style="margin: 0"><b style="color: var(--text-primary)">下周计划：</b>{{ detail.content.plan }}</p>
            </div>
            <div v-if="detail.attachments && detail.attachments.length" style="margin-top: var(--space-3); display: flex; gap: var(--space-2); flex-wrap: wrap">
              <AppStatusTag v-for="a in detail.attachments" :key="a" type="info">📎 {{ a }}</AppStatusTag>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">版本记录</span></div>
          <div class="mp-card__body">
            <ul v-if="detail.versions && detail.versions.length" class="mp-timeline">
              <li v-for="(v, i) in detail.versions" :key="i" class="mp-timeline__item" :class="'is-' + (v.tone === 'processing' ? 'warning' : v.tone)">
                <div class="mp-timeline__title">{{ v.title }}</div>
                <div v-if="v.desc" class="mp-timeline__desc">{{ v.desc }}</div>
                <div class="mp-timeline__time">{{ v.time }}</div>
              </li>
            </ul>
            <p v-else class="mp-note" style="margin: 0">暂无历史版本，本篇为首次提交。</p>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">批阅</span></div>
          <div class="mp-card__body">
            <template v-if="detail.status === 'PENDING_REVIEW'">
              <div class="mp-radio" :class="{ 'is-active': action === 'APPROVE' }" @click="action = 'APPROVE'">
                <input type="radio" :checked="action === 'APPROVE'" style="margin-top: 3px" />
                <div>
                  <div class="mp-radio__title">通过</div>
                  <div class="mp-radio__desc">计入周报完成率，可附评语</div>
                </div>
              </div>
              <div class="mp-radio" :class="{ 'is-active': action === 'RETURN' }" @click="action = 'RETURN'">
                <input type="radio" :checked="action === 'RETURN'" style="margin-top: 3px" />
                <div>
                  <div class="mp-radio__title">退回修改</div>
                  <div class="mp-radio__desc">退回原因必填（≥5 字），学生端收到不可关闭的退回提醒</div>
                </div>
              </div>
              <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">
                {{ action === 'RETURN' ? '退回原因（必填，≥5 字）' : '评语（选填）' }}
              </label>
              <AppTemplateChips class="wr-chips" :options="activeChips" size="compact" @pick="onPickChip" />
              <textarea v-model="comment" class="mp-textarea" :placeholder="action === 'RETURN' ? '请写明退回原因，将原样同步学生端…' : '例如：联调记录完整，下周补充量化数据…'"></textarea>
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppButton variant="primary" :disabled="!canReview" :title="canReview ? '' : '无周报批阅权限'" :loading="submitting" style="flex: 1" @click="submit('APPROVE')">✓ 通过</AppButton>
                <AppButton variant="warning" :disabled="!canReview" :title="canReview ? '' : '无周报批阅权限'" :loading="submitting" style="flex: 1" @click="submit('RETURN')">↩ 退回修改</AppButton>
              </div>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">批阅动作写入审批留痕，学生端即时同步状态</p>
            </template>
            <EmptyState v-else :title="'该周报' + (detail.status === 'APPROVED' ? '已通过' : '已退回')" description="批阅结果已同步学生端，留痕见下方审批记录" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审批留痕</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="trailRecords" empty-text="暂无批阅记录" />
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 周报批阅详情（/admin/internship/reports/:id）。
 * 闭环：查看正文/附件/版本 → 通过 / 退回（原因必填）→ 留痕 → 学生端同步。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppRiskTag, AppAuditTrail, AppTemplateChips } from '@/components/common'
import { AppButton } from '@/components/ui'
import ReviewQueueBar from './components/ReviewQueueBar.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { APPROVE_WEEKLY, REJECT_WEEKLY } from '@/modules/internship/constants/presetPrompts'

export default {
  name: 'WeeklyReportDetailView',
  components: { ModulePageShell, AppStatusTag, AppRiskTag, AppAuditTrail, AppTemplateChips, LoadingState, ErrorState, EmptyState, AppButton, ReviewQueueBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, action: 'APPROVE', comment: '', formError: '', submitting: false }
  },
  computed: {
    canReview() { return canCode(this.ctx, 'internship.report.review') },
    activeChips() { return this.action === 'RETURN' ? REJECT_WEEKLY : APPROVE_WEEKLY },
    trailRecords() {
      return (this.detail?.trail || []).map((t, i) => ({
        id: i,
        actor: t.who,
        at: t.time,
        action: t.action,
        reason: t.affected
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
  created() {
    this.load()
  },
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
      const res = await internshipApi.getWeeklyReportDetail(id)
      if (id !== this.$route.params.id) return // 队列快速跳转时丢弃过期响应
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async submit(action) {
      if (!this.canReview) return toast.error('无周报批阅权限')
      this.action = action
      this.formError = ''
      if (action === 'RETURN' && (!this.comment || this.comment.trim().length < 5)) {
        this.formError = '退回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await internshipApi.reviewWeeklyReport(this.detail.id, { action, comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success('批阅完成：' + res.data.statusLabel + '，已留痕并同步学生端')
        this.comment = ''
        this.load()
        // 连续批阅：有下一条自动跳转，无则提示队列完成
        this.$refs.queueBar && this.$refs.queueBar.advance()
      } else {
        this.formError = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.wr-chips { margin-bottom: var(--space-2); }
</style>
