<template>
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div v-if="visible" class="handle-drawer-mask" @click.self="close">
        <aside class="handle-drawer" role="dialog" aria-modal="true" :aria-label="title">
          <header class="handle-drawer__header">
            <h3>{{ title }}</h3>
            <button type="button" class="handle-drawer__close" aria-label="关闭" @click="close">
              ×
            </button>
          </header>

          <div v-if="payload" class="handle-drawer__body">
            <div class="handle-drawer__row">
              <span class="handle-drawer__label">学生姓名</span>
              <span class="handle-drawer__value">{{ payload.studentName || '—' }}</span>
            </div>
            <div class="handle-drawer__row">
              <span class="handle-drawer__label">风险类型</span>
              <span class="handle-drawer__value">{{ payload.riskType || '—' }}</span>
            </div>
            <div class="handle-drawer__row handle-drawer__row--block">
              <span class="handle-drawer__label">风险原因</span>
              <p class="handle-drawer__reason">{{ payload.riskReason || '—' }}</p>
            </div>
            <div class="handle-drawer__row">
              <span class="handle-drawer__label">责任老师</span>
              <span class="handle-drawer__value">{{ payload.responsibleTeacher || '—' }}</span>
            </div>
            <div class="handle-drawer__row">
              <span class="handle-drawer__label">处理时限</span>
              <span class="handle-drawer__value">{{ payload.deadline || '—' }}</span>
            </div>
            <div class="handle-drawer__row">
              <span class="handle-drawer__label">当前状态</span>
              <AppStatusTag :status="payload.status" />
            </div>

            <div v-if="payload.suggestions?.length" class="handle-drawer__suggestions">
              <div class="handle-drawer__suggestions-title">处理建议</div>
              <ul>
                <li v-for="(s, i) in payload.suggestions" :key="i">{{ s }}</li>
              </ul>
            </div>
          </div>

          <footer class="handle-drawer__footer">
            <button type="button" class="handle-drawer__btn" @click="$emit('contact')">
              联系学生
            </button>
            <button type="button" class="handle-drawer__btn" @click="$emit('remind')">
              发起提醒
            </button>
            <button type="button" class="handle-drawer__btn" @click="$emit('follow')">
              填写跟进
            </button>
            <button
              type="button"
              class="handle-drawer__btn handle-drawer__btn--primary"
              @click="$emit('resolve')"
            >
              标记已处理
            </button>
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
import AppStatusTag from '../common/AppStatusTag.vue'

export default {
  name: 'AppHandleDrawer',
  components: { AppStatusTag },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '风险处理' },
    payload: { type: Object, default: null }
  },
  emits: ['update:visible', 'contact', 'remind', 'follow', 'resolve'],
  methods: {
    close() {
      this.$emit('update:visible', false)
    }
  }
}
</script>

<style scoped>
.handle-drawer-mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-drawer);
  background: var(--bg-mask);
  display: flex;
  justify-content: flex-end;
}
.handle-drawer {
  width: min(420px, 100vw);
  height: 100%;
  background: var(--bg-card);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
}
.handle-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-base);
}
.handle-drawer__header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.handle-drawer__close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 22px;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-md);
}
.handle-drawer__close:hover {
  background: var(--gray-100);
  color: var(--text-primary);
}
.handle-drawer__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.handle-drawer__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  font-size: var(--font-size-sm);
}
.handle-drawer__row--block {
  flex-direction: column;
  align-items: flex-start;
}
.handle-drawer__label {
  color: var(--text-secondary);
  flex-shrink: 0;
}
.handle-drawer__value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  text-align: right;
}
.handle-drawer__reason {
  margin: var(--space-1) 0 0;
  padding: var(--space-3);
  width: 100%;
  border-radius: var(--radius-md);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}
.handle-drawer__suggestions {
  margin-top: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
}
.handle-drawer__suggestions-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--warning-700);
  margin-bottom: var(--space-1);
}
.handle-drawer__suggestions ul {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.7;
}
.handle-drawer__footer {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-base);
}
.handle-drawer__btn {
  height: 36px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}
.handle-drawer__btn:hover {
  border-color: var(--primary-100);
  color: var(--primary-600);
  background: var(--primary-50);
}
.handle-drawer__btn--primary {
  border-color: var(--primary-600);
  background: var(--primary-600);
  color: var(--text-inverse);
}
.handle-drawer__btn--primary:hover {
  background: var(--primary-700);
  border-color: var(--primary-700);
  color: var(--text-inverse);
}
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-fade-enter-active .handle-drawer,
.drawer-fade-leave-active .handle-drawer {
  transition: transform 0.2s ease;
}
.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}
.drawer-fade-enter-from .handle-drawer,
.drawer-fade-leave-to .handle-drawer {
  transform: translateX(100%);
}
</style>
