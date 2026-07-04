<template>
  <AppConfirmDialog
    :visible="visible"
    type="warning"
    :title="title"
    :message="confirmMessage"
    :confirm-text="confirmText"
    require-reason
    reason-label="导出用途"
    reason-placeholder="如：学院例会名单核对（不少于 5 个字，将写入审计日志）"
    :submitting="submitting"
    @update:visible="$emit('update:visible', $event)"
    @confirm="$emit('confirm', $event)"
    @cancel="$emit('cancel')"
  />
</template>

<script>
/**
 * AppExportConfirm — 导出安全确认（SECURITY-P0 统一口径，等保三级展示层要求）。
 * 包装 AppConfirmDialog：固定四点安全提醒 + 必填导出用途（写入审计日志）。
 * 用法：
 *   <AppExportConfirm v-model:visible="dlg" :module-name="'学生主档'" :row-count="selected.length"
 *     :scope-label="ctx.dataScope.scopeName" :submitting="busy" @confirm="doExport" />
 * 现有导出确认框可逐步迁移到本组件；迁移前也可仅复用
 * utils/security/confirm-text.js 的 buildExportConfirmMessage 统一文案。
 */
import AppConfirmDialog from './AppConfirmDialog.vue'
import { buildExportConfirmMessage } from '@/utils/security/confirm-text'

export default {
  name: 'AppExportConfirm',
  components: { AppConfirmDialog },
  props: {
    visible: { type: Boolean, default: false },
    /** 模块/数据名称（如：学生主档），仅用于文案 */
    moduleName: { type: String, default: '' },
    /** 本次导出的记录数（0 = 未知，用通用口径） */
    rowCount: { type: Number, default: 0 },
    /** 当前数据范围显示名（来自模块 ctx.dataScope，禁止硬编码） */
    scopeLabel: { type: String, default: '' },
    title: { type: String, default: '导出安全确认' },
    confirmText: { type: String, default: '确认导出' },
    submitting: { type: Boolean, default: false }
  },
  emits: ['update:visible', 'confirm', 'cancel'],
  computed: {
    confirmMessage() {
      return buildExportConfirmMessage({
        module: this.moduleName,
        rowCount: this.rowCount,
        scopeLabel: this.scopeLabel
      })
    }
  }
}
</script>
