<template>
  <ModulePageShell
    title="学籍异动详情"
    :subtitle="change ? (change.changeTypeLabel + ' · ' + change.realName) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/status-changes')">返回列表</button>
      <button v-if="change" class="mp-btn" @click="print">打印审批表</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="change" class="mp-stack">
      <AppSectionCard title="基本信息">
        <div class="aa-kv-grid">
          <div class="aa-kv"><span>学生</span><b>{{ change.realName }}（ID {{ change.studentId }}）</b></div>
          <div class="aa-kv"><span>异动类型</span><b>{{ change.changeTypeLabel }}</b></div>
          <div class="aa-kv"><span>状态变化</span><b>{{ change.fromStatus }} → {{ change.toStatus }}</b></div>
          <div class="aa-kv"><span>当前状态</span><b><AppStatusTag :type="statusColor(change.status)" dot>{{ statusLabel(change.status) }}</AppStatusTag></b></div>
          <div class="aa-kv"><span>当前节点</span><b>{{ nodeLabel(change.currentNode) }}</b></div>
          <div v-if="change.expireDate" class="aa-kv"><span>休学到期</span><b>{{ change.expireDate }}</b></div>
          <div v-if="change.effectiveDate" class="aa-kv"><span>生效日期</span><b>{{ change.effectiveDate }}</b></div>
          <div class="aa-kv aa-kv--full"><span>申请原因</span><b>{{ change.reason || '（无）' }}</b></div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="审批流程">
        <ol class="aa-flow">
          <li v-for="(n, i) in flowNodes" :key="n" class="aa-flow__node" :class="nodeState(i)">
            <span class="aa-flow__dot">{{ i + 1 }}</span>
            <span class="aa-flow__label">{{ nodeLabel(n) }}</span>
            <span class="aa-flow__state">{{ nodeStateText(i) }}</span>
          </li>
        </ol>
      </AppSectionCard>

      <AppSectionCard v-if="canReview" title="审批操作">
        <div class="aa-review-btns">
          <button class="mp-btn mp-btn--primary" @click="openApprove">通过</button>
          <button class="mp-btn" @click="openReturn">退回</button>
          <button class="mp-btn mp-btn--danger" @click="openReject">驳回</button>
        </div>
        <p class="mp-note">驳回 / 退回原因必填且不少于 5 字。终审「通过」后异动即刻生效并写入学籍主档。</p>
      </AppSectionCard>
      <AppInlineAlert v-else-if="!isActive(change.status)" type="info" :message="`本异动已${statusLabel(change.status)}，无需再审批。`" />
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :message="dlg.message"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :require-reason="dlg.requireReason"
      reason-label="审批意见"
      :submitting="dlg.submitting"
      @confirm="doReview"
    />
  </ModulePageShell>
</template>

<script>
/** 学籍异动详情 + 审批（/admin/academic-affairs/status-changes/:id）：GET + POST review。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TYPE_LABEL, STATUS_LABEL, NODE_LABEL, CHANGE_FLOW_NODES, statusColor, isActive } from '@/modules/academicAffairs/constants/status-change'
import { toast } from '@/utils/toast'

export default {
  name: 'AaStatusChangeDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      change: null,
      dlg: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, action: '' }
    }
  },
  computed: {
    changeId() { return this.$route.params.id },
    flowNodes() { return this.change ? (CHANGE_FLOW_NODES[this.change.changeType] || []) : [] },
    currentIndex() {
      if (!this.change || !this.change.currentNode) return -1
      return this.flowNodes.indexOf(this.change.currentNode)
    },
    canReview() {
      return this.change && isActive(this.change.status) && this.currentIndex >= 0
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusColor,
    isActive,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    nodeState(i) {
      if (this.change && this.change.status === 'EFFECTIVE') return 'is-done'
      if (i < this.currentIndex) return 'is-done'
      if (i === this.currentIndex) return 'is-current'
      return 'is-todo'
    },
    nodeStateText(i) {
      if (this.change && this.change.status === 'EFFECTIVE') return '已通过'
      if (i < this.currentIndex) return '已通过'
      if (i === this.currentIndex) return '审批中'
      return '待处理'
    },
    print() {
      window.open(`/admin/academic-affairs/print/status-change/${this.changeId}`, '_blank')
    },
    openApprove() {
      this.dlg = { visible: true, title: `通过「${this.change.changeTypeLabel}」`, message: this.currentIndex + 1 >= this.flowNodes.length ? '这是终审节点，通过后异动将即刻生效并写入学籍主档。' : '通过后流转到下一审批节点。', type: 'primary', confirmText: '确认通过', requireReason: false, submitting: false, action: 'APPROVE' }
    },
    openReturn() {
      this.dlg = { visible: true, title: '退回异动', message: '退回给申请方修改，请填写退回原因。', type: 'warning', confirmText: '确认退回', requireReason: true, submitting: false, action: 'RETURN' }
    },
    openReject() {
      this.dlg = { visible: true, title: '驳回异动', message: '驳回后本异动终止，请填写驳回原因。', type: 'danger', confirmText: '确认驳回', requireReason: true, submitting: false, action: 'REJECT' }
    },
    async doReview(payload) {
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.reviewStatusChange(this.changeId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) {
        this.dlg.visible = false
        toast.success('已处理')
        this.load()
      } else {
        toast.error(res.message || '处理失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getStatusChange(this.changeId)
      if (res.code === 0) {
        this.change = res.data
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-kv-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px 24px; }
.aa-kv { display: flex; gap: 12px; font-size: 14px; }
.aa-kv--full { grid-column: 1 / -1; }
.aa-kv span { color: var(--text-500, #646a73); min-width: 72px; }
.aa-kv b { color: var(--text-900, #1f2329); font-weight: 500; }
.aa-flow { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.aa-flow__node { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
.aa-flow__dot { width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; background: var(--fill-200, #e5e6eb); color: var(--text-500, #646a73); }
.aa-flow__node.is-done .aa-flow__dot { background: var(--success-500, #22c55e); color: #fff; }
.aa-flow__node.is-current .aa-flow__dot { background: var(--primary-500, #3b82f6); color: #fff; }
.aa-flow__label { font-size: 14px; color: var(--text-900, #1f2329); }
.aa-flow__state { font-size: 12px; color: var(--text-400, #8a9099); }
.aa-flow__node.is-current .aa-flow__state { color: var(--primary-600, #2563eb); }
.aa-review-btns { display: flex; gap: 12px; }
</style>
