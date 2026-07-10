<template>
  <div class="prc">
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="mp-stack">
      <AppSectionCard :title="'开题报告 · ' + detail.version">
        <template #header-extra>
          <StatusTag :status="detail.status" :label="detail.statusLabel" dot />
          <StatusTag v-if="detail.isResubmit" type="info" label="重交件" style="margin-left: var(--space-1)" />
        </template>
        <AppDescriptionList :items="proposalMetaItems" :columns="compact ? 1 : 2" />
        <div class="prc-content">
          <p><b>选题背景：</b>{{ detail.content.background }}</p>
          <p><b>研究方案与进度：</b>{{ detail.content.plan }}</p>
          <p style="margin-bottom: 0"><b>预期成果：</b>{{ detail.content.outcome }}</p>
        </div>
        <div v-if="detail.attachments.length" style="margin-top: var(--space-3)">
          <p class="mp-note" style="margin-bottom: var(--space-2)">附件材料</p>
          <AppFileList :files="attachmentFiles" :previewable="false" :downloadable="false" :removable="false" />
        </div>
      </AppSectionCard>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">批阅</span></div>
        <div class="mp-card__body">
          <template v-if="detail.status === 'PENDING_REVIEW'">
            <div v-if="!canReview" class="mp-note" style="margin-bottom: var(--space-2); color: var(--warning-600)">
              {{ reviewReason }}（以下操作已置灰，仅指导教师可批阅）
            </div>
            <label class="mp-note" style="display: block; margin-bottom: var(--space-1)">批阅意见（驳回时必填，≥5 字）</label>
            <textarea v-model="comment" class="mp-textarea" :disabled="!canReview" rows="3" placeholder="批注将随批阅结果同步学生端…"></textarea>
            <p v-if="formError" class="mp-form-err">{{ formError }}</p>
            <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="primary" :loading="submitting" style="flex: 1" @click="submit('APPROVE')">✓ 通过</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="warning" :loading="submitting" style="flex: 1" @click="submit('REJECT')">↩ 驳回修改</AppPermissionButton>
            </div>
            <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">批阅写入审批留痕，学生端即时同步</p>
          </template>
          <template v-else-if="detail.status === 'APPROVED'">
            <div class="mp-kv"><span class="mp-kv__k">书面开题</span><span class="mp-kv__v">已通过</span></div>
            <div v-if="detail.reviewComment" class="mp-kv"><span class="mp-kv__k">批注意见</span><span class="mp-kv__v">{{ detail.reviewComment }}</span></div>
            <div v-if="detail.defenseResult" class="mp-kv"><span class="mp-kv__k">开题答辩</span>
              <span class="mp-kv__v">{{ detail.defenseResult === 'PASS' ? '现场答辩通过' : '现场答辩不通过' }}{{ detail.defenseComment ? '：' + detail.defenseComment : '' }}</span>
            </div>
            <template v-else>
              <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">开题答辩评语（不通过时必填 ≥5 字）</label>
              <textarea v-model="defenseComment" class="mp-textarea" rows="2" placeholder="现场开题答辩评语…"></textarea>
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppButton variant="primary" :loading="submitting" style="flex: 1" @click="submitDefense('PASS')">✓ 答辩通过</AppButton>
                <AppButton variant="warning" :loading="submitting" style="flex: 1" @click="submitDefense('FAIL')">✕ 答辩不通过</AppButton>
              </div>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">开题答辩为现场环节，区别于上方书面审核</p>
            </template>
          </template>
          <template v-else>
            <div class="mp-kv"><span class="mp-kv__k">批阅结果</span><span class="mp-kv__v">已驳回修改</span></div>
            <div v-if="detail.reviewComment" class="mp-kv"><span class="mp-kv__k">驳回原因</span><span class="mp-kv__v">{{ detail.reviewComment }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-2)">批阅结果已同步学生端，学生重交后将出现新的待审记录</p>
          </template>
        </div>
      </section>

      <div class="mp-grid-2 prc-bottom" :class="{ 'is-compact': compact }">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">历史版本</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="(v, i) in detail.versions" :key="i" class="mp-timeline__item" :class="'is-' + (v.tone === 'processing' ? 'warning' : v.tone)">
                <div class="mp-timeline__title">{{ v.title }}</div>
                <div v-if="v.desc" class="mp-timeline__desc">{{ v.desc }}</div>
                <div class="mp-timeline__time">{{ v.time }}</div>
              </li>
            </ul>
          </div>
        </section>
        <AppSectionCard title="审批留痕">
          <AppAuditTrail :records="trailRecords" empty-text="暂无批阅记录" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * ProposalReviewCard — 开题批阅卡（可复用）。
 * 使用方：① 开题审核双栏工作区右栏（compact）② 独立批阅详情页 /proposals/:id（深链/窄屏）。
 * 数据：graduationApi.getProposalReviewDetail（真实接口）；批阅/开题答辩均走真实状态机。
 * 事件：reviewed({ id, status, statusLabel })：批阅成功；conflict：并发冲突（外层应刷新队列）。
 */
import { StatusTag, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppPermissionButton, AppAuditTrail, AppFileList, AppSectionCard, AppDescriptionList } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ProposalReviewCard',
  components: { StatusTag, LoadingState, ErrorState, AppButton, AppPermissionButton, AppAuditTrail, AppFileList, AppSectionCard, AppDescriptionList },
  props: {
    ctx: { type: Object, required: true },
    proposalId: { type: [String, Number], required: true },
    /** 双栏右栏使用：布局更紧凑 */
    compact: { type: Boolean, default: false }
  },
  emits: ['reviewed', 'conflict'],
  data() {
    return { loading: true, error: '', detail: null, comment: '', formError: '', submitting: false, defenseComment: '' }
  },
  computed: {
    proposalMetaItems() {
      if (!this.detail) return []
      return [
        { label: '学生', value: `${this.detail.studentName} · ${this.detail.className}` },
        { label: '课题', value: this.detail.topicTitle },
        { label: '指导教师', value: this.detail.advisorName },
        { label: '提交时间', value: this.detail.submitAt }
      ]
    },
    attachmentFiles() {
      return (this.detail?.attachments || []).map((name, i) => ({ id: i, name }))
    },
    trailRecords() {
      return (this.detail?.trail || []).map((t, i) => ({ id: i, action: t.action, actor: t.who, at: t.time, target: t.affected }))
    },
    canReview() {
      const pa = this.ctx.permissionActions.reviewProposal
      return !!(pa && pa.visible && pa.allowed)
    },
    reviewReason() {
      const pa = this.ctx.permissionActions.reviewProposal
      return pa && !pa.allowed ? pa.reason : ''
    }
  },
  watch: {
    proposalId: { immediate: true, handler() { this.load() } }
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      this.formError = ''
      this.comment = ''
      this.defenseComment = ''
      const res = await graduationApi.getProposalReviewDetail(this.proposalId)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async submit(action) {
      if (!this.canReview) return
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) {
        this.formError = '驳回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await graduationApi.reviewProposal(this.detail.id, { action, comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success('批阅完成：' + res.data.statusLabel + '，已留痕并同步学生端')
        this.comment = ''
        this.$emit('reviewed', res.data)
        this.load()
      } else if (res.message && res.message.includes('已批阅')) {
        this.formError = res.message
        this.$emit('conflict')
        this.load()
      } else {
        this.formError = res.message
      }
    },
    async submitDefense(result) {
      if (result === 'FAIL' && (!this.defenseComment || this.defenseComment.trim().length < 5)) {
        toast.error('开题答辩不通过时评语必填且不少于 5 字'); return
      }
      this.submitting = true
      const res = await graduationMoreApi.holdProposalDefense(this.detail.id, result, this.defenseComment)
      this.submitting = false
      if (res.code === 0) { toast.success('开题答辩已录入'); this.defenseComment = ''; this.load() }
      else toast.error(res.message || '录入失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.prc-content {
  margin-top: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.8;
}
.prc-content p { margin: 0 0 var(--space-2); }
.prc-content b { color: var(--text-primary); }
.prc-bottom.is-compact { grid-template-columns: 1fr; }
</style>
