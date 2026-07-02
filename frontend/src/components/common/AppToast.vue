<template>
  <div class="app-toast" aria-live="polite">
    <transition-group name="app-toast-slide">
      <div
        v-for="t in toastState.items"
        :key="t.id"
        class="app-toast__item"
        :class="`is-${t.type}`"
      >
        <span class="app-toast__icon">{{ icons[t.type] }}</span>
        <span class="app-toast__text">{{ t.message }}</span>
        <button type="button" class="app-toast__close" aria-label="关闭" @click="remove(t.id)">
          ×
        </button>
      </div>
    </transition-group>
  </div>
</template>

<script>
import { toastState, remove } from '../../utils/toast'

/**
 * AppToast 轻提示容器（在 App.vue 挂载一次）
 * 类型：success / error / info / warning
 * 通过 utils/toast 的 toast.success() 等方法触发，不需要 props。
 */
export default {
  name: 'AppToast',
  setup() {
    return { toastState, remove, icons: { success: '✓', error: '!', info: 'ℹ', warning: '!' } }
  }
}
</script>

<style scoped>
.app-toast {
  position: fixed;
  top: var(--space-5);
  right: var(--space-5);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
  max-width: 380px;
}
.app-toast__item {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: var(--space-3) var(--space-4);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  line-height: var(--line-height-base);
}
.app-toast__icon {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  color: var(--text-inverse);
  font-size: var(--font-size-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}
.is-success .app-toast__icon {
  background: var(--success-500);
}
.is-error .app-toast__icon {
  background: var(--danger-500);
}
.is-info .app-toast__icon {
  background: var(--info-500);
}
.is-warning .app-toast__icon {
  background: var(--warning-500);
}
.is-success {
  border-color: var(--success-100);
}
.is-error {
  border-color: var(--danger-100);
}
.is-warning {
  border-color: var(--warning-100);
}
.app-toast__text {
  flex: 1;
}
.app-toast__close {
  border: none;
  background: none;
  color: var(--text-tertiary);
  font-size: var(--font-size-lg);
  line-height: 1;
  padding: 0;
  cursor: pointer;
}
.app-toast-slide-enter-active,
.app-toast-slide-leave-active {
  transition: all 0.2s ease;
}
.app-toast-slide-enter-from,
.app-toast-slide-leave-to {
  opacity: 0;
  transform: translateX(12px);
}
</style>
