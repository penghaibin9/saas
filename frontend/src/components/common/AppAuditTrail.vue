<template>
  <div class="app-audit-trail" :class="{ 'is-compact': compact }">
    <!-- loading -->
    <div v-if="loading" class="app-audit-trail__state">
      <span class="app-audit-trail__spinner" />
      <span>加载操作记录…</span>
    </div>

    <!-- error -->
    <div v-else-if="error" class="app-audit-trail__state is-error">
      <span>⚠ {{ error }}</span>
      <button type="button" class="app-audit-trail__retry" @click="$emit('retry')">重试</button>
    </div>

    <!-- empty -->
    <div v-else-if="!records.length" class="app-audit-trail__state is-empty">
      {{ emptyText }}
    </div>

    <!-- list -->
    <ol v-else class="app-audit-trail__list">
      <li
        v-for="(r, i) in records"
        :key="r.id || i"
        class="app-audit-trail__item"
        :class="`is-${resultKind(r)}`"
      >
        <span class="app-audit-trail__node" />
        <div class="app-audit-trail__body">
          <div class="app-audit-trail__line">
            <span class="app-audit-trail__action">{{ r.action || '—' }}</span>
            <span v-if="r.result" class="app-audit-trail__result" :class="`is-${resultKind(r)}`">
              {{ r.result }}
            </span>
          </div>
          <div class="app-audit-trail__meta">
            <span v-if="r.actor" class="app-audit-trail__actor">
              {{ r.actor }}<template v-if="r.actorRole"> · {{ r.actorRole }}</template>
            </span>
            <span v-if="r.target"> · {{ r.target }}</span>
            <span v-if="r.at" class="app-audit-trail__time"> · {{ r.at }}</span>
          </div>
          <div v-if="r.reason" class="app-audit-trail__reason">事由：{{ r.reason }}</div>
          <div v-if="showIp && r.ip" class="app-audit-trail__ip">IP {{ r.ip }}</div>
        </div>
      </li>
    </ol>
  </div>
</template>

<script>
/**
 * AppAuditTrail — 审计/操作留痕展示组件（只做展示，绝不伪造审计后端）。
 *
 * ⚠️ 声明：审计记录必须来自后端真实审计日志（SecurityAuditLog 等）。
 *    本组件只把后端返回的记录渲染成时间线，不产生、不补全、不篡改任何审计数据。
 *    见 CLAUDE.md §6 / §18。
 *
 * Props:
 *  - records: [{ id, action, actor, actorRole, target, reason, ip, at, result }]
 *      result 建议值：成功|已通过|已完成 → success；驳回|失败|拒绝 → danger；退回|异常 → warning
 *  - loading / error / emptyText
 *  - compact: 紧凑模式（详情抽屉/侧栏用）
 *  - showIp: 是否展示 IP（默认展示，敏感场景可关闭）
 * Emits: retry（error 态点击重试）
 */
export default {
  name: 'AppAuditTrail',
  props: {
    records: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' },
    emptyText: { type: String, default: '暂无操作记录' },
    compact: { type: Boolean, default: false },
    showIp: { type: Boolean, default: true }
  },
  emits: ['retry'],
  methods: {
    resultKind(r) {
      const t = String(r.result || r.kind || '').toLowerCase()
      if (/(成功|通过|完成|发布|success|pass|ok)/.test(t)) return 'success'
      if (/(驳回|失败|拒绝|越权|reject|fail|deny|error)/.test(t)) return 'danger'
      if (/(退回|异常|警告|return|warn)/.test(t)) return 'warning'
      return 'default'
    }
  }
}
</script>

<style scoped>
.app-audit-trail {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.app-audit-trail__state {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  justify-content: center;
}
.app-audit-trail__state.is-empty {
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-subtle);
}
.app-audit-trail__state.is-error {
  color: var(--danger-600);
}
.app-audit-trail__retry {
  border: none;
  background: none;
  color: var(--text-link);
  cursor: pointer;
  font-size: var(--font-size-sm);
}
.app-audit-trail__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--primary-100);
  border-top-color: var(--primary-500);
  border-radius: var(--radius-full);
  animation: aat-spin 0.7s linear infinite;
}
@keyframes aat-spin {
  to { transform: rotate(360deg); }
}
.app-audit-trail__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.app-audit-trail__item {
  position: relative;
  padding: 0 0 var(--space-4) var(--space-5);
  border-left: 2px solid var(--border-light);
}
.app-audit-trail__item:last-child {
  border-left-color: transparent;
  padding-bottom: 0;
}
.is-compact .app-audit-trail__item {
  padding-bottom: var(--space-3);
}
.app-audit-trail__node {
  position: absolute;
  left: -6px;
  top: 3px;
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  background: var(--gray-400);
  box-shadow: 0 0 0 3px var(--bg-card);
}
.app-audit-trail__item.is-success .app-audit-trail__node { background: var(--success-500); }
.app-audit-trail__item.is-danger .app-audit-trail__node { background: var(--danger-500); }
.app-audit-trail__item.is-warning .app-audit-trail__node { background: var(--warning-500); }
.app-audit-trail__line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.app-audit-trail__action {
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.app-audit-trail__result {
  font-size: var(--font-size-xs);
  padding: 0 var(--space-2);
  border-radius: var(--radius-full);
  background: var(--gray-100);
  color: var(--text-secondary);
}
.app-audit-trail__result.is-success { background: var(--success-50); color: var(--success-700); }
.app-audit-trail__result.is-danger { background: var(--danger-50); color: var(--danger-600); }
.app-audit-trail__result.is-warning { background: var(--warning-50); color: var(--warning-700); }
.app-audit-trail__meta {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.app-audit-trail__actor {
  color: var(--text-secondary);
}
.app-audit-trail__reason {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.app-audit-trail__ip {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
</style>
