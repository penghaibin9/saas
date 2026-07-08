<template>
  <span v-if="!(mode === 'hide' && !allowed)" class="app-perm-btn">
    <AppButton
      :variant="variant"
      :size="size"
      :loading="loading"
      :disabled="isDisabled"
      :title="allowed ? nativeTitle : reason"
      @click="onClick"
    >
      <slot />
    </AppButton>
    <span v-if="!allowed && showLock" class="app-perm-btn__lock" :title="reason">🔒</span>
  </span>
</template>

<script>
/**
 * AppPermissionButton — 前端权限体验按钮（只做“看得见的权限体验”，不替代后端校验）。
 *
 * ⚠️ 安全声明：本组件只负责按钮的显示/禁用/提示，属于前端体验层。
 *    真正的越权拦截必须由后端接口（模块授权 + 角色 + 数据范围 + 业务关系 + 按钮权限）完成。
 *    禁止把本组件当作权限裁定依据。见 CLAUDE.md §3.4 / §17。
 *
 * Props:
 *  - allowed: 调用方根据权限 store 计算得到的“是否有此操作权限”（默认 true）
 *  - code:    权限 code（仅用于展示/审计标注，如 studentAffairs.leave.approve）
 *  - mode:    无权限时的表现 —— 'disable'(禁用+锁标+提示) | 'hide'(直接不渲染)
 *  - variant/size: 透传给 AppButton
 *  - loading/disabled: 常规态
 *  - danger:  危险操作（透传 danger 语义色）
 *  - reason:  无权限时的提示文案
 *  - showLock: 无权限且 disable 模式时是否显示 🔒
 * Emits:
 *  - click: 仅在有权限且非禁用/加载态时触发
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'AppPermissionButton',
  components: { AppButton },
  props: {
    allowed: { type: Boolean, default: true },
    code: { type: String, default: '' },
    mode: {
      type: String,
      default: 'disable',
      validator: (v) => ['disable', 'hide'].includes(v)
    },
    variant: { type: String, default: 'primary' },
    size: { type: String, default: 'md' },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    danger: { type: Boolean, default: false },
    reason: { type: String, default: '无操作权限，请联系管理员' },
    showLock: { type: Boolean, default: true },
    nativeTitle: { type: String, default: '' }
  },
  emits: ['click'],
  computed: {
    isDisabled() {
      return this.disabled || this.loading || !this.allowed
    }
  },
  methods: {
    onClick(e) {
      if (this.isDisabled) return
      this.$emit('click', e)
    }
  }
}
</script>

<style scoped>
.app-perm-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.app-perm-btn__lock {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  cursor: not-allowed;
  user-select: none;
}
</style>
