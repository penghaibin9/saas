<template>
  <div
    class="app-global-state"
    :class="{ 'app-global-state--refreshing': state === 'loading' && hasReadyContent }"
    :aria-busy="state === 'loading' ? 'true' : 'false'"
  >
    <!-- ready：正常渲染业务内容；二次刷新时保留已加载内容，避免整页闪白。 -->
    <slot v-if="state === 'ready' || (state === 'loading' && hasReadyContent)" />

    <!-- 已有内容后的刷新只显示轻量状态，不卸载业务区。 -->
    <div
      v-if="state === 'loading' && hasReadyContent"
      class="ags-refreshing"
      role="status"
      aria-live="polite"
    >
      <span class="ags-refreshing__spinner" aria-hidden="true" />
      {{ loadingText }}
    </div>

    <!-- 首次 loading：使用骨架屏。 -->
    <div v-else-if="state === 'loading'" class="ags-panel ags-loading">
      <div class="ags-skeleton ags-skeleton--title" />
      <div class="ags-skeleton" />
      <div class="ags-skeleton" />
      <div class="ags-skeleton ags-skeleton--short" />
      <div class="ags-loading__text">{{ loadingText }}</div>
    </div>

    <!-- 其余状态：图标 + 标题 + 说明 + 操作按钮 -->
    <div v-else-if="state !== 'ready'" class="ags-panel" :class="`ags-${state}`" role="status">
      <div class="ags-icon" :class="`ags-icon--${state}`">{{ meta.icon }}</div>
      <div class="ags-title">{{ title || meta.title }}</div>
      <div class="ags-desc">{{ description || meta.description }}</div>
      <div v-if="errorCode && state === 'error'" class="ags-code">错误码：{{ errorCode }}</div>
      <div class="ags-actions">
        <slot name="actions">
          <button
            v-if="meta.retry"
            type="button"
            class="ags-btn ags-btn--primary"
            @click="$emit('retry')"
          >
            {{ meta.retry }}
          </button>
          <button v-if="meta.back" type="button" class="ags-btn" @click="$emit('back')">
            {{ meta.back }}
          </button>
          <button v-if="meta.contact" type="button" class="ags-btn" @click="$emit('contact')">
            {{ meta.contact }}
          </button>
        </slot>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * AppGlobalState 全局页面状态容器
 * 依据 V2.1 §12：所有 PC 页面必须使用本组件处理页面状态。
 * Props:
 *  - state: ready | loading | empty | error | forbidden | offline | readonly | noLicense
 *  - title / description: 覆盖默认文案
 *  - errorCode: error 状态下显示错误码
 *  - loadingText: loading 提示文案
 * Emits: retry / back / contact
 * Slots: default（state=ready 时渲染业务内容）、actions（自定义操作区）
 */
const STATE_META = {
  empty: {
    icon: '▢',
    title: '暂无数据',
    description: '当前条件下没有可展示的内容，可尝试调整筛选或创建新数据',
    retry: '',
    back: '返回',
    contact: ''
  },
  error: {
    icon: '!',
    title: '加载失败',
    description: '数据加载出现问题，请重试；若持续失败请联系管理员',
    retry: '重试',
    back: '返回',
    contact: ''
  },
  forbidden: {
    icon: '⊘',
    title: '当前身份无权查看',
    description: '原因：不在授权范围内。建议：切换身份或联系管理员开通权限',
    retry: '',
    back: '返回首页',
    contact: '联系管理员'
  },
  offline: {
    icon: '⇅',
    title: '网络异常',
    description: '当前网络不可用，请检查网络连接后重试',
    retry: '重试',
    back: '',
    contact: ''
  },
  readonly: {
    icon: '🔒',
    title: '当前模块只读',
    description: '模块授权已到期，历史数据可查看，新增和修改已停用',
    retry: '',
    back: '查看历史',
    contact: '联系管理员'
  },
  noLicense: {
    icon: '◇',
    title: '模块未开通',
    description: '当前学校尚未开通该模块，如需使用请联系学校管理员',
    retry: '',
    back: '返回',
    contact: '联系学校管理员'
  }
}

export default {
  name: 'AppGlobalState',
  props: {
    state: {
      type: String,
      default: 'ready',
      validator: (v) =>
        [
          'ready',
          'loading',
          'empty',
          'error',
          'forbidden',
          'offline',
          'readonly',
          'noLicense'
        ].includes(v)
    },
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    errorCode: { type: [String, Number], default: '' },
    loadingText: { type: String, default: '正在加载…' }
  },
  emits: ['retry', 'back', 'contact'],
  data() {
    return {
      hasReadyContent: this.state === 'ready'
    }
  },
  watch: {
    state(value) {
      if (value === 'ready') this.hasReadyContent = true
    }
  },
  computed: {
    meta() {
      return STATE_META[this.state] || STATE_META.error
    }
  }
}
</script>

<style scoped>
.app-global-state {
  position: relative;
  width: 100%;
}
.ags-refreshing {
  position: absolute;
  z-index: 8;
  top: var(--space-2);
  right: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 30px;
  padding: 5px 10px;
  border: 1px solid var(--primary-100, #dbeafe);
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--shadow-sm);
  color: var(--primary-700, #1d4ed8);
  font-size: var(--font-size-xs);
  font-weight: 600;
  pointer-events: none;
}
.ags-refreshing__spinner {
  width: 13px;
  height: 13px;
  border: 2px solid var(--primary-100, #dbeafe);
  border-top-color: var(--primary-600, #2563eb);
  border-radius: 50%;
  animation: ags-spin 0.75s linear infinite;
}
.ags-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-8);
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  text-align: center;
}
.ags-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-3xl);
  margin-bottom: var(--space-4);
}
.ags-icon--empty {
  background: var(--gray-100);
  color: var(--gray-400);
}
.ags-icon--error {
  background: var(--danger-50);
  color: var(--danger-600);
}
.ags-icon--forbidden {
  background: var(--warning-50);
  color: var(--warning-600);
}
.ags-icon--offline {
  background: var(--gray-100);
  color: var(--gray-500);
}
.ags-icon--readonly {
  background: var(--info-50);
  color: var(--info-600);
  font-size: var(--font-size-xl);
}
.ags-icon--noLicense {
  background: var(--primary-50);
  color: var(--primary-600);
}
.ags-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.ags-desc {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  max-width: 420px;
  line-height: var(--line-height-base);
}
.ags-code {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ags-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-5);
}
.ags-btn {
  height: 32px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  cursor: pointer;
}
.ags-btn:hover {
  border-color: var(--primary-500);
  color: var(--primary-600);
}
.ags-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: var(--text-inverse);
}
.ags-btn--primary:hover {
  background: var(--primary-700);
  border-color: var(--primary-700);
  color: var(--text-inverse);
}

/* loading 骨架屏 */
.ags-loading {
  align-items: stretch;
  text-align: left;
  gap: var(--space-3);
}
.ags-skeleton {
  height: 16px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--gray-100) 25%, var(--gray-200) 50%, var(--gray-100) 75%);
  background-size: 200% 100%;
  animation: ags-shimmer 1.4s ease infinite;
}
.ags-skeleton--title {
  width: 40%;
  height: 20px;
}
.ags-skeleton--short {
  width: 60%;
}
.ags-loading__text {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  text-align: center;
}
@keyframes ags-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
@keyframes ags-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .ags-skeleton,
  .ags-refreshing__spinner {
    animation: none;
  }
}
</style>
