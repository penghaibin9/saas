<template>
  <AppCard class="wf-task-detail">
    <div v-if="!task" class="wf-task-detail__empty">从左侧选择一个审批任务查看详情</div>
    <template v-else>
      <div class="wf-task-detail__head">
        <div>
          <h3 class="wf-task-detail__title">{{ task.title }}</h3>
          <div class="wf-task-detail__badges">
            <AppBadge :type="statusType(task.status)">{{ statusText(task.status) }}</AppBadge>
            <AppBadge type="info">{{ moduleLabel(task.businessModule) }}</AppBadge>
          </div>
        </div>
      </div>

      <dl class="wf-task-detail__kv">
        <dt>申请人</dt><dd>{{ task.initiator }}</dd>
        <dt>业务类型</dt><dd>{{ task.businessType }}</dd>
        <dt>业务编号</dt><dd>{{ task.businessId }}</dd>
        <dt>流程名称</dt><dd>{{ task.templateName }}</dd>
        <dt>当前节点</dt><dd>{{ task.currentNode || '—' }}</dd>
        <dt>当前处理人</dt><dd>{{ task.currentAssignee || '—' }}</dd>
        <dt>提交时间</dt><dd>{{ task.submittedAt }}</dd>
      </dl>

      <AppInlineAlert
        v-if="task.status === 'REJECTED' && lastRejectComment"
        type="warning"
        title="已退回"
        :description="`退回原因：${lastRejectComment}。业务已回到发起人，可修改后重新提交。`"
      />

      <div class="wf-task-detail__timeline">
        <h4 class="wf-task-detail__sub">审批记录</h4>
        <ApprovalTimeline :records="task.records" />
      </div>

      <!-- 退回原因输入区（仅退回模式展开） -->
      <div v-if="rejectMode" class="wf-task-detail__reject">
        <label class="wf-task-detail__label">退回原因（必填）</label>
        <textarea
          v-model="rejectReason"
          class="wf-task-detail__textarea"
          rows="3"
          placeholder="请填写具体退回原因，便于发起人修改后重新提交"
          :disabled="readonly"
        />
        <div class="wf-task-detail__count" :class="{ 'is-invalid': !reasonCheck.valid }">
          当前 {{ reasonCheck.length }} 字 / 至少 {{ reasonCheck.minLength }} 字
        </div>
      </div>

      <div class="wf-task-detail__actions">
        <template v-if="rejectMode">
          <AppButton variant="secondary" @click="cancelReject">取消</AppButton>
          <AppButton
            variant="danger"
            :disabled="readonly || !reasonCheck.valid || submitting"
            :loading="submitting"
            @click="confirmReject"
          >
            确认退回
          </AppButton>
        </template>
        <template v-else>
          <AppButton
            v-if="showWithdraw"
            variant="ghost"
            :disabled="readonly || !canWithdraw || submitting"
            @click="$emit('withdraw', task)"
          >
            撤回
          </AppButton>
          <AppButton
            variant="warning"
            :disabled="readonly || !canReject || submitting"
            @click="startReject"
          >
            退回
          </AppButton>
          <AppButton
            variant="primary"
            :disabled="readonly || !canApprove || submitting"
            :loading="submitting"
            @click="$emit('approve', task)"
          >
            通过
          </AppButton>
        </template>
      </div>
      <p v-if="finished" class="wf-task-detail__finished-hint">该任务已处于终态，不可重复审批。</p>
    </template>
  </AppCard>
</template>

<script>
/**
 * ApprovalTaskDetailPanel —— 审批任务详情 + 通过/退回/撤回操作。
 * 退回原因校验统一走 approval.helpers.validateRejectReason（≥5 字 + 实时字数）。
 * readonly（模块到期）时全部写按钮 disabled。
 */
import { AppCard, AppBadge, AppButton } from '@/components/ui'
import AppInlineAlert from '@/components/common/AppInlineAlert.vue'
import ApprovalTimeline from './ApprovalTimeline.vue'
import {
  validateRejectReason,
  canApproveTask,
  canRejectTask,
  canWithdrawTask,
  isTaskFinished,
  getTaskStatusText,
  getTaskStatusType
} from '../helpers/approval.helpers'
import { getModuleLabel } from '../helpers/workflow.helpers'
import { APPROVAL_ACTION } from '../constants/workflow.constants'

export default {
  name: 'ApprovalTaskDetailPanel',
  components: { AppCard, AppBadge, AppButton, AppInlineAlert, ApprovalTimeline },
  props: {
    task: { type: Object, default: null },
    permissionContext: { type: Object, default: null },
    readonly: { type: Boolean, default: false },
    submitting: { type: Boolean, default: false },
    showWithdraw: { type: Boolean, default: true }
  },
  emits: ['approve', 'reject', 'withdraw'],
  data() {
    return { rejectMode: false, rejectReason: '' }
  },
  computed: {
    reasonCheck() {
      return validateRejectReason(this.rejectReason)
    },
    canApprove() {
      return canApproveTask(this.task, this.permissionContext)
    },
    canReject() {
      return canRejectTask(this.task, this.permissionContext)
    },
    canWithdraw() {
      return canWithdrawTask(this.task, this.permissionContext)
    },
    finished() {
      return isTaskFinished(this.task)
    },
    lastRejectComment() {
      const recs = [...(this.task?.records || [])].reverse()
      return recs.find((r) => r.action === APPROVAL_ACTION.REJECT)?.comment || ''
    }
  },
  watch: {
    task() {
      this.cancelReject()
    }
  },
  methods: {
    statusText: getTaskStatusText,
    statusType: getTaskStatusType,
    moduleLabel: getModuleLabel,
    startReject() {
      this.rejectMode = true
    },
    cancelReject() {
      this.rejectMode = false
      this.rejectReason = ''
    },
    confirmReject() {
      if (!this.reasonCheck.valid) return
      this.$emit('reject', { task: this.task, reason: this.rejectReason.trim() })
      this.rejectMode = false
    }
  }
}
</script>

<style scoped>
.wf-task-detail { padding: var(--card-padding-pc); display: flex; flex-direction: column; gap: var(--space-4); }
.wf-task-detail__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; padding: var(--space-10) 0; }
.wf-task-detail__title { margin: 0 0 var(--space-2); font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.wf-task-detail__badges { display: flex; gap: var(--space-2); }
.wf-task-detail__kv {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0;
  font-size: var(--font-size-sm);
}
.wf-task-detail__kv dt { color: var(--text-tertiary); }
.wf-task-detail__kv dd { margin: 0; color: var(--text-primary); }
.wf-task-detail__sub { margin: 0 0 var(--space-3); font-size: var(--font-size-base); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.wf-task-detail__label { font-size: var(--font-size-sm); color: var(--text-primary); display: block; margin-bottom: var(--space-2); }
.wf-task-detail__textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  font: inherit;
  color: var(--text-primary);
  resize: vertical;
}
.wf-task-detail__textarea:focus { outline: none; border-color: var(--primary-500); }
.wf-task-detail__count { margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wf-task-detail__count.is-invalid { color: var(--danger-600); }
.wf-task-detail__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
.wf-task-detail__finished-hint { margin: 0; text-align: right; font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
