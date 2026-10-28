<template>
  <div class="aies">
    <div class="aies__summary">
      共解析 <b>{{ total }}</b> 行 · 校验通过
      <b class="is-good">{{ validRows }}</b> 行 · 失败
      <b class="is-bad">{{ invalidRows }}</b> 行。
      {{ invalidRows > 0 ? '本次尚未导入，请修正错误后重新上传。' : '本次尚未导入，核对后请确认保存。' }}
    </div>
    <AppButton
      v-if="invalidRows > 0"
      variant="ghost"
      :loading="downloading"
      @click="$emit('download-errors')"
    >
      下载错误行表格
    </AppButton>
  </div>
</template>

<script>
/**
 * AppImportErrorSummary — 预校验结果汇总条 + 下载错误行 Excel 入口。
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'AppImportErrorSummary',
  components: { AppButton },
  props: {
    total: { type: Number, default: 0 },
    validRows: { type: Number, default: 0 },
    invalidRows: { type: Number, default: 0 },
    downloading: { type: Boolean, default: false }
  },
  emits: ['download-errors']
}
</script>

<style scoped>
.aies {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.aies__summary {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.aies__summary .is-good {
  color: var(--success-600);
}
.aies__summary .is-bad {
  color: var(--danger-600);
}
</style>
