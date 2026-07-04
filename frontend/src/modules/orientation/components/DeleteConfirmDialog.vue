<template>
  <AppConfirmDialog
    :visible="visible"
    :title="title"
    :message="message"
    type="danger"
    :confirm-text="confirmText"
    require-reason
    :reason-label="reasonLabel"
    :reason-placeholder="reasonPlaceholder"
    :submitting="submitting"
    @update:visible="$emit('update:visible', $event)"
    @confirm="$emit('confirm', $event)"
    @cancel="$emit('cancel')"
  >
    <p class="dcd__notice">此操作为逻辑作废，数据不会被物理删除，作废原因与操作人将写入审计日志，可追溯。</p>
  </AppConfirmDialog>
</template>

<script>
/**
 * DeleteConfirmDialog — 作废/逻辑删除确认弹窗（模块局部组件）。
 * 平台约定：业务数据禁止物理删除；作废必须填写原因并留痕。
 */
import { AppConfirmDialog } from '@/components/common'

export default {
  name: 'DeleteConfirmDialog',
  components: { AppConfirmDialog },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, required: true },
    message: { type: String, default: '' },
    confirmText: { type: String, default: '确认作废' },
    reasonLabel: { type: String, default: '作废原因' },
    reasonPlaceholder: { type: String, default: '请填写作废原因（不少于 5 个字），将写入审计日志' },
    submitting: { type: Boolean, default: false }
  },
  emits: ['update:visible', 'confirm', 'cancel']
}
</script>

<style scoped>
.dcd__notice {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>
