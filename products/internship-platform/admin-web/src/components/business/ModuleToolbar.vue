<template>
  <div class="mtb">
    <div class="mtb__left">
      <AppButton
        v-for="a in actions"
        :key="a.key"
        :variant="a.variant || 'secondary'"
        :disabled="a.disabled"
        :title="a.disabled ? a.disabledReason || '当前角色无此操作权限' : ''"
        @click="onAction(a)"
      >
        {{ a.label }}
      </AppButton>
      <slot name="left" />
    </div>
    <div class="mtb__right">
      <slot name="right" />
      <span v-if="hint" class="mtb__hint">{{ hint }}</span>
    </div>
  </div>
</template>

<script>
/**
 * ModuleToolbar — 列表/看板顶部操作栏（通用）。
 * Props:
 *  - actions: [{ key, label, variant?, disabled?, disabledReason? }]
 *    权限裁剪由业务方基于 permissionActions 预处理后传入：
 *    不可见的操作不传；可见但无权限的传 disabled + disabledReason（置灰并提示原因）。
 *  - hint：右侧辅助说明（如共 N 条 / 审计提示）
 * Emits: action(key)
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'ModuleToolbar',
  components: { AppButton },
  props: {
    actions: { type: Array, default: () => [] },
    hint: { type: String, default: '' }
  },
  emits: ['action'],
  methods: {
    onAction(a) {
      if (a.disabled) return
      this.$emit('action', a.key)
    }
  }
}
</script>

<style scoped>
.mtb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.mtb__left,
.mtb__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.mtb__hint {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
