<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="变更申请详情"
    subtitle="选题变更申请 · 原题目 → 目标题目"
    back-to="/admin/graduation/topic-changes"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <dl v-else-if="detail" class="tc-meta">
      <div><dt>学生</dt><dd>{{ detail.studentName }}（{{ detail.studentNo }}）</dd></div>
      <div><dt>原题目</dt><dd>{{ detail.oldTopicTitle }} · 导师 {{ detail.oldAdvisorName || '—' }}</dd></div>
      <div><dt>目标题目</dt><dd>{{ detail.newTopicTitle }} · 导师 {{ detail.newAdvisorName || '—' }}</dd></div>
      <div><dt>变更理由</dt><dd>{{ detail.reason }}</dd></div>
      <div><dt>状态</dt><dd><StatusTag :type="detail.statusTone" :label="detail.statusLabel" dot /></dd></div>
      <div v-if="detail.reviewComment"><dt>审核意见</dt><dd>{{ detail.reviewComment }}</dd></div>
      <div v-if="detail.reviewerName"><dt>审核人</dt><dd>{{ detail.reviewerName }} · {{ detail.reviewedAt }}</dd></div>
      <div><dt>发起人</dt><dd>{{ detail.requestedBy }} · {{ detail.requestedAt }}</dd></div>
    </dl>
    <template v-if="detail && detail.status === 'PENDING'" #footer>
      <button type="button" class="mp-btn mp-btn--primary" @click="askApprove">通过</button>
      <button type="button" class="mp-btn mp-link--danger" @click="askReject">驳回</button>
    </template>
    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, StatusTag } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { gdTopicChangeApi } from '@/modules/graduation/api/graduation-topic-change.api'
import { toast } from '@/utils/toast'

export default {
  name: 'TopicChangeDetailView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, StatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', detail: null, submitting: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '理由', action: null }
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await gdTopicChangeApi.getChangeRequestDetail(this.$route.params.id)
      if (res.code !== 0) { this.error = res.message; this.loading = false; return }
      this.detail = res.data
      this.loading = false
    },
    askApprove() {
      this.confirm = {
        visible: true, title: '通过变更申请',
        message: `确认通过「${this.detail.studentName}」由「${this.detail.oldTopicTitle}」变更至「${this.detail.newTopicTitle}」？将立即迁移选题分配。`,
        type: 'primary', confirmText: '通过', requireReason: false, action: 'APPROVE'
      }
    },
    askReject() {
      this.confirm = {
        visible: true, title: '驳回变更申请',
        message: `驳回「${this.detail.studentName}」的变更申请？`,
        type: 'danger', confirmText: '驳回', requireReason: true, reasonLabel: '驳回理由', action: 'REJECT'
      }
    },
    async onConfirm({ reason } = {}) {
      this.submitting = true
      try {
        const res = await gdTopicChangeApi.reviewChangeRequest(this.detail.id, { action: this.confirm.action, comment: reason || '' })
        if (res.code === 0) {
          toast.success('已处理并写入留痕')
          this.confirm.visible = false
          this.$router.push('/admin/graduation/topic-changes')
        } else toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.tc-meta { display: grid; grid-template-columns: 1fr; gap: 10px; }
.tc-meta dt { font-size: 12px; color: var(--t3, #64748b); }
.tc-meta dd { margin: 2px 0 0; font-size: 13px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; margin-left: var(--space-2); }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-link--danger { color: var(--danger, #dc2626); }
</style>
