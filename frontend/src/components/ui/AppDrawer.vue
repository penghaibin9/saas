<template>
  <Teleport to="body">
    <Transition name="drawer-fade" :duration="200">
      <div
        v-if="visible"
        class="app-drawer-mask"
        :class="`is-${mode}`"
        @click.self="close"
      >
        <aside
          class="app-drawer"
          :class="[`is-${mode}`, `is-${size}`]"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
        >
          <header v-if="title || $slots.header" class="app-drawer__header">
            <slot name="header">
              <div class="app-drawer__heading">
                <h3>{{ title }}</h3>
                <p v-if="subtitle">{{ subtitle }}</p>
              </div>
            </slot>
            <button type="button" class="app-drawer__close" aria-label="关闭" @click="close">×</button>
          </header>
          <div class="app-drawer__body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="app-drawer__footer">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
export default {
  name: 'AppDrawer',
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    mode: {
      type: String,
      default: 'drawer',
      validator: (value) => ['drawer', 'modal'].includes(value)
    },
    size: {
      type: String,
      default: 'medium',
      validator: (value) => ['small', 'medium', 'large', 'xlarge'].includes(value)
    }
  },
  emits: ['update:visible', 'close'],
  methods: {
    close() {
      this.$emit('update:visible', false)
      this.$emit('close')
    }
  }
}
</script>

<style scoped>
.app-drawer-mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-drawer);
  background: var(--bg-mask);
  display: flex;
  justify-content: flex-end;
}
.app-drawer-mask.is-modal {
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: var(--z-modal);
  backdrop-filter: blur(2px);
}
.app-drawer {
  width: min(420px, 100vw);
  height: 100%;
  background: var(--bg-card);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
}
.app-drawer.is-modal {
  width: min(720px, calc(100vw - 48px));
  height: auto;
  max-height: min(86vh, 900px);
  border: 1px solid var(--border-base);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 24px 70px rgba(15, 23, 42, .22);
}
.app-drawer.is-modal.is-small { width: min(520px, calc(100vw - 48px)); }
.app-drawer.is-modal.is-large { width: min(880px, calc(100vw - 48px)); }
.app-drawer.is-modal.is-xlarge { width: min(1040px, calc(100vw - 48px)); }
.app-drawer.is-modal .app-drawer__header {
  flex: 0 0 auto;
  min-height: 72px;
  padding: 16px 24px 17px;
  border-top: 4px solid var(--color-primary);
  background: var(--bg-card);
}
.app-drawer.is-modal .app-drawer__header h3 {
  font-size: 20px;
}
.app-drawer__heading { min-width: 0; }
.app-drawer__heading p {
  margin: 5px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}
.app-drawer.is-modal .app-drawer__body {
  min-height: 0;
  padding: 24px;
  background: var(--bg-page);
  overflow-x: auto;
  overscroll-behavior: contain;
}
.app-drawer.is-modal .app-drawer__footer {
  flex: 0 0 auto;
  justify-content: flex-end;
  padding: 14px 24px;
  background: var(--bg-card);
}
.app-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-base);
}
.app-drawer__header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.app-drawer__close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 22px;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background var(--motion-fast) var(--ease-standard);
}
.app-drawer__close:hover {
  background: var(--gray-100);
  color: var(--text-primary);
}
.app-drawer__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
}
.app-drawer__footer {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-base);
}
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity var(--motion-normal) var(--ease-standard);
}
.drawer-fade-enter-active .app-drawer,
.drawer-fade-leave-active .app-drawer {
  transition: transform var(--motion-normal) var(--ease-standard);
}
.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}
.drawer-fade-enter-from .app-drawer,
.drawer-fade-leave-to .app-drawer {
  transform: translateX(100%);
}
.drawer-fade-enter-active .app-drawer.is-modal,
.drawer-fade-leave-active .app-drawer.is-modal {
  transition: transform var(--motion-normal) var(--ease-standard);
}
.drawer-fade-enter-from .app-drawer.is-modal,
.drawer-fade-leave-to .app-drawer.is-modal {
  transform: translateY(12px) scale(.97);
}
@media (max-width: 720px) {
  .app-drawer-mask.is-modal { padding: 12px; }
  .app-drawer.is-modal,
  .app-drawer.is-modal.is-small,
  .app-drawer.is-modal.is-large,
  .app-drawer.is-modal.is-xlarge {
    width: calc(100vw - 24px);
    max-height: calc(100vh - 24px);
    border-radius: 14px;
  }
  .app-drawer.is-modal .app-drawer__body { padding: 18px; }
}
</style>
