<template>
  <div class="app-notif-panel">
    <div v-if="title || $slots.header" class="app-notif-panel__head">
      <span class="app-notif-panel__title">{{ title }}</span>
      <span v-if="unreadCount" class="app-notif-panel__badge">{{ unreadCount }}</span>
      <button
        v-if="unreadCount && showReadAll"
        type="button"
        class="app-notif-panel__readall"
        @click="$emit('read-all')"
      >全部已读</button>
      <slot name="header" />
    </div>

    <div v-if="loading" class="app-notif-panel__state"><span class="app-notif-panel__spinner" /> 加载消息…</div>
    <div v-else-if="!items.length" class="app-notif-panel__empty">{{ emptyText }}</div>

    <ul v-else class="app-notif-panel__list">
      <li
        v-for="(m, i) in items"
        :key="m.id || i"
        class="app-notif-panel__item"
        :class="{ 'is-unread': !m.read }"
        @click="$emit('open', m)"
      >
        <span class="app-notif-panel__icon" :class="`is-${m.type || 'info'}`">{{ iconOf(m) }}</span>
        <div class="app-notif-panel__body">
          <div class="app-notif-panel__item-title">
            {{ m.title }}
            <span v-if="!m.read" class="app-notif-panel__dot" />
          </div>
          <div v-if="m.desc" class="app-notif-panel__desc">{{ m.desc }}</div>
          <div v-if="m.at" class="app-notif-panel__time">{{ m.at }}</div>
        </div>
      </li>
    </ul>

    <button v-if="showMore && items.length" type="button" class="app-notif-panel__more" @click="$emit('more')">
      查看全部消息 ›
    </button>
  </div>
</template>

<script>
/**
 * AppNotificationPanel — 消息通知面板（顶部铃铛下拉 / 工作台消息卡）。
 * Props:
 *  - title、items: [{ id, title, desc?, at?, read?, type?(info|success|warning|danger|approval) }]
 *  - loading、emptyText、showReadAll、showMore
 * Emits: open(item)、read-all、more
 * unreadCount 由 items 内 read=false 数量自动统计。
 */
const TYPE_ICON = { info: 'ℹ', success: '✓', warning: '!', danger: '⚠', approval: '📝' }
export default {
  name: 'AppNotificationPanel',
  props: {
    title: { type: String, default: '消息通知' },
    items: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    emptyText: { type: String, default: '暂无新消息' },
    showReadAll: { type: Boolean, default: true },
    showMore: { type: Boolean, default: false }
  },
  emits: ['open', 'read-all', 'more'],
  computed: {
    unreadCount() {
      return this.items.filter((m) => !m.read).length
    }
  },
  methods: {
    iconOf(m) {
      return TYPE_ICON[m.type] || TYPE_ICON.info
    }
  }
}
</script>

<style scoped>
.app-notif-panel {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  overflow: hidden;
}
.app-notif-panel__head {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}
.app-notif-panel__title { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.app-notif-panel__badge {
  min-width: 20px; height: 20px; padding: 0 var(--space-1);
  border-radius: var(--radius-full); background: var(--danger-500); color: #fff;
  font-size: var(--font-size-xs); display: inline-flex; align-items: center; justify-content: center;
}
.app-notif-panel__readall {
  margin-left: auto; border: none; background: none;
  color: var(--text-link); cursor: pointer; font-size: var(--font-size-xs);
}
.app-notif-panel__readall:hover { color: var(--primary-700); }
.app-notif-panel__state, .app-notif-panel__empty {
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
  padding: var(--space-6); font-size: var(--font-size-sm); color: var(--text-tertiary);
}
.app-notif-panel__spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--primary-100); border-top-color: var(--primary-500);
  border-radius: var(--radius-full); animation: anp-spin 0.7s linear infinite;
}
@keyframes anp-spin { to { transform: rotate(360deg); } }
.app-notif-panel__list { list-style: none; margin: 0; padding: 0; }
.app-notif-panel__item {
  display: flex; gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer; transition: background 0.12s;
}
.app-notif-panel__item:last-child { border-bottom: none; }
.app-notif-panel__item:hover { background: var(--bg-hover); }
.app-notif-panel__item.is-unread { background: var(--primary-25, var(--primary-50)); }
.app-notif-panel__item.is-unread:hover { background: var(--primary-50); }
.app-notif-panel__icon {
  flex-shrink: 0; width: 26px; height: 26px; border-radius: var(--radius-full);
  display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xs);
  background: var(--info-50); color: var(--info-600);
}
.app-notif-panel__icon.is-success { background: var(--success-50); color: var(--success-600); }
.app-notif-panel__icon.is-warning { background: var(--warning-50); color: var(--warning-600); }
.app-notif-panel__icon.is-danger { background: var(--danger-50); color: var(--danger-600); }
.app-notif-panel__icon.is-approval { background: var(--primary-50); color: var(--primary-600); }
.app-notif-panel__body { flex: 1; min-width: 0; }
.app-notif-panel__item-title {
  font-size: var(--font-size-sm); color: var(--text-primary);
  display: flex; align-items: center; gap: var(--space-2);
}
.is-unread .app-notif-panel__item-title { font-weight: var(--font-weight-medium); }
.app-notif-panel__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: var(--danger-500); flex-shrink: 0; }
.app-notif-panel__desc {
  font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.app-notif-panel__time { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.app-notif-panel__more {
  width: 100%; border: none; background: var(--bg-subtle);
  padding: var(--space-2); color: var(--text-link); cursor: pointer; font-size: var(--font-size-sm);
}
.app-notif-panel__more:hover { background: var(--bg-hover); }
</style>
