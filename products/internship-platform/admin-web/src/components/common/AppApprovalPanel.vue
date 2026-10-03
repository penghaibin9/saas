<template>
  <div class="app-approval">
    <div class="app-approval__head">
      <span class="app-approval__title">{{ title }}</span>
      <AppStatusTag v-if="status" :status="status" />
    </div>

    <!-- 当前节点 -->
    <div v-if="currentNode" class="app-approval__node">
      <span class="app-approval__node-label">当前节点</span>
      <span class="app-approval__node-name">{{ currentNode }}</span>
      <span v-if="currentHandler" class="app-approval__node-handler">待办人：{{ currentHandler }}</span>
    </div>

    <!-- 审批历史（复用审计时间线样式风格） -->
    <div v-if="history.length" class="app-approval__history">
      <div class="app-approval__history-title">审批记录</div>
      <ol class="app-approval__list">
        <li v-for="(h, i) in history" :key="h.id || i" class="app-approval__item" :class="`is-${kindOf(h)}`">
          <span class="app-approval__dot" />
          <div class="app-approval__item-body">
            <div class="app-approval__item-line">
              <span class="app-approval__item-node">{{ h.node || h.action || '—' }}</span>
              <span class="app-approval__item-result" :class="`is-${kindOf(h)}`">{{ h.result || '' }}</span>
            </div>
            <div class="app-approval__item-meta">
              {{ h.handler }}<template v-if="h.at"> · {{ h.at }}</template>
            </div>
            <div v-if="h.comment" class="app-approval__item-comment">意见：{{ h.comment }}</div>
          </div>
        </li>
      </ol>
    </div>

    <!-- 审批动作区 -->
    <div v-if="canAct" class="app-approval__act">
      <label class="app-approval__reason-label">
        审批意见<span v-if="reasonRequired" class="app-approval__req">（驳回/退回必填，不少于 {{ reasonMinLength }} 字）</span>
      </label>
      <textarea
        v-model="reason"
        class="app-approval__textarea"
        :placeholder="reasonPlaceholder"
        rows="3"
      />
      <div class="app-approval__buttons">
        <AppButton
          v-if="canApprove"
          variant="primary"
          :loading="submitting === 'approve'"
          :disabled="!!submitting"
          @click="emitAction('approve')"
        >{{ approveText }}</AppButton>
        <AppButton
          v-if="canReturn"
          variant="secondary"
          :loading="submitting === 'return'"
          :disabled="!!submitting"
          @click="emitAction('return')"
        >退回修改</AppButton>
        <AppButton
          v-if="canReject"
          variant="danger"
          :loading="submitting === 'reject'"
          :disabled="!!submitting"
          @click="emitAction('reject')"
        >驳回</AppButton>
      </div>
      <p v-if="reasonError" class="app-approval__error">{{ reasonError }}</p>
    </div>
    <div v-else-if="actedHint" class="app-approval__done">{{ actedHint }}</div>
  </div>
</template>

<script>
/**
 * AppApprovalPanel — 通用审批面板（当前节点 + 审批记录 + 通过/退回/驳回动作）。
 *
 * ⚠️ 声明：本组件只做审批交互与展示。真正的状态流转、节点权限、数据范围、审批留痕
 *    必须由后端审批流引擎完成（见 CLAUDE.md §18）。驳回/退回强制填写意见并写审计。
 *
 * Props:
 *  - title / status / currentNode / currentHandler
 *  - history: [{ id, node, action, result, handler, at, comment }]
 *  - canApprove / canReject / canReturn: 由调用方按“审批节点权限 + 业务关系”计算
 *  - submitting: '' | 'approve' | 'reject' | 'return'（对应按钮转圈）
 *  - reasonMinLength / approveText / actedHint
 * Emits:
 *  - approve({ reason }) / reject({ reason }) / return({ reason })
 *    reject/return 时 reason 已做非空+长度校验。
 */
import AppStatusTag from './AppStatusTag.vue'
import { AppButton } from '@/components/ui'

export default {
  name: 'AppApprovalPanel',
  components: { AppStatusTag, AppButton },
  props: {
    title: { type: String, default: '审批处理' },
    status: { type: String, default: '' },
    currentNode: { type: String, default: '' },
    currentHandler: { type: String, default: '' },
    history: { type: Array, default: () => [] },
    canApprove: { type: Boolean, default: false },
    canReject: { type: Boolean, default: false },
    canReturn: { type: Boolean, default: false },
    submitting: { type: String, default: '' },
    reasonMinLength: { type: Number, default: 5 },
    reasonPlaceholder: { type: String, default: '请填写审批意见；驳回或退回时为必填' },
    approveText: { type: String, default: '同意' },
    actedHint: { type: String, default: '' }
  },
  emits: ['approve', 'reject', 'return'],
  data() {
    return { reason: '', reasonError: '' }
  },
  computed: {
    canAct() {
      return this.canApprove || this.canReject || this.canReturn
    },
    reasonRequired() {
      return this.canReject || this.canReturn
    }
  },
  methods: {
    kindOf(h) {
      const t = String(h.result || h.kind || '').toLowerCase()
      if (/(同意|通过|完成|发布|success|pass)/.test(t)) return 'success'
      if (/(驳回|拒绝|不同意|reject|fail)/.test(t)) return 'danger'
      if (/(退回|异常|return|warn)/.test(t)) return 'warning'
      return 'default'
    },
    emitAction(action) {
      this.reasonError = ''
      const reason = this.reason.trim()
      if ((action === 'reject' || action === 'return') && reason.length < this.reasonMinLength) {
        this.reasonError = `驳回/退回必须填写意见，且不少于 ${this.reasonMinLength} 字`
        return
      }
      this.$emit(action, { reason })
    }
  }
}
</script>

<style scoped>
.app-approval {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  padding: var(--space-4);
}
.app-approval__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.app-approval__title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.app-approval__node {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--primary-25, var(--primary-50));
  border-radius: var(--radius-base);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-3);
}
.app-approval__node-label { color: var(--text-tertiary); }
.app-approval__node-name { font-weight: var(--font-weight-medium); color: var(--primary-700); }
.app-approval__node-handler { color: var(--text-secondary); }
.app-approval__history { margin-bottom: var(--space-3); }
.app-approval__history-title {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.app-approval__list { list-style: none; margin: 0; padding: 0; }
.app-approval__item {
  position: relative;
  padding: 0 0 var(--space-3) var(--space-5);
  border-left: 2px solid var(--border-light);
}
.app-approval__item:last-child { border-left-color: transparent; padding-bottom: 0; }
.app-approval__dot {
  position: absolute; left: -6px; top: 3px;
  width: 10px; height: 10px; border-radius: var(--radius-full);
  background: var(--gray-400); box-shadow: 0 0 0 3px var(--bg-card);
}
.app-approval__item.is-success .app-approval__dot { background: var(--success-500); }
.app-approval__item.is-danger .app-approval__dot { background: var(--danger-500); }
.app-approval__item.is-warning .app-approval__dot { background: var(--warning-500); }
.app-approval__item-line { display: flex; align-items: center; gap: var(--space-2); }
.app-approval__item-node { font-weight: var(--font-weight-medium); color: var(--text-primary); font-size: var(--font-size-sm); }
.app-approval__item-result { font-size: var(--font-size-xs); }
.app-approval__item-result.is-success { color: var(--success-700); }
.app-approval__item-result.is-danger { color: var(--danger-600); }
.app-approval__item-result.is-warning { color: var(--warning-700); }
.app-approval__item-meta { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.app-approval__item-comment { font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: var(--space-1); }
.app-approval__act { border-top: 1px solid var(--border-light); padding-top: var(--space-3); }
.app-approval__reason-label {
  display: block; font-size: var(--font-size-sm);
  color: var(--text-secondary); margin-bottom: var(--space-2);
}
.app-approval__req { color: var(--danger-600); font-size: var(--font-size-xs); }
.app-approval__textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  resize: vertical;
  font-family: inherit;
}
.app-approval__textarea:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-100);
}
.app-approval__buttons { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.app-approval__error { color: var(--danger-600); font-size: var(--font-size-xs); margin: var(--space-2) 0 0; }
.app-approval__done {
  font-size: var(--font-size-sm); color: var(--text-tertiary);
  padding: var(--space-2) 0;
}
</style>
