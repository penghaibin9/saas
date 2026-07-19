<template>
  <Teleport to="body">
    <Transition name="drawer-fade" :duration="200">
      <div v-if="visible" class="app-drawer-mask" @click.self="close">
        <aside class="app-drawer" role="dialog" aria-modal="true" :aria-label="title">
          <header v-if="title || $slots.header" class="app-drawer__header">
            <slot name="header">
              <h3>{{ title }}</h3>
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
    title: { type: String, default: '' }
  },
  emits: ['update:visible'],
  methods: {
    close() {
      this.$emit('update:visible', false)
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
.app-drawer {
  width: min(420px, 100vw);
  height: 100%;
  background: var(--bg-card);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
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
</style>
