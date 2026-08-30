<template>
  <section v-if="receipt" class="acr" :class="`is-${tone}`" role="status" aria-live="polite">
    <div class="acr__mark">{{ mark }}</div>
    <div class="acr__body">
      <div class="acr__head">
        <div>
          <small>操作回执 · {{ receipt.actionLabel || '已完成' }}</small>
          <strong>{{ receipt.objectLabel || '业务对象已更新' }}</strong>
        </div>
        <AppStatusTag :type="tone">{{ receipt.statusLabel || receipt.status || '成功' }}</AppStatusTag>
      </div>
      <dl class="acr__facts">
        <div><dt>对象 ID</dt><dd>{{ receipt.id || '—' }}</dd></div>
        <div><dt>服务端版本</dt><dd>{{ receipt.version == null ? '—' : 'v' + receipt.version }}</dd></div>
        <div><dt>审计结果</dt><dd>{{ receipt.auditText || '动作与业务更新已提交' }}</dd></div>
        <div><dt>下一步</dt><dd>{{ receipt.nextStep || '可继续处理下一条' }}</dd></div>
      </dl>
    </div>
    <button type="button" class="acr__close" aria-label="关闭操作回执" @click="$emit('close')">×</button>
  </section>
</template>

<script>
import { AppStatusTag } from '@/components/common'

/**
 * 关键写动作的页面内持久回执。
 * 只展示服务端成功响应真实返回的 id/status/version；不伪造 auditId 或服务端时间。
 */
export default {
  name: 'ActionReceipt',
  components: { AppStatusTag },
  emits: ['close'],
  props: { receipt: { type: Object, default: null } },
  computed: {
    tone() {
      if (this.receipt?.type) return this.receipt.type
      const status = String(this.receipt?.status || '').toUpperCase()
      if (['BLOCKED', 'FAILED', 'REJECTED'].includes(status)) return 'danger'
      if (['WARNING', 'PENDING', 'UNKNOWN'].includes(status)) return 'warning'
      return 'success'
    },
    mark() { return this.tone === 'success' ? '✓' : (this.tone === 'warning' ? '!' : '×') }
  }
}
</script>

<style scoped>
.acr { position: relative; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: start; margin-bottom: var(--space-3); padding: 14px 16px; border: 1px solid var(--success-200, #a7f3d0); border-radius: 13px; background: linear-gradient(115deg, var(--success-50, #ecfdf5), var(--card, #fff) 70%); box-shadow: 0 10px 28px rgba(5, 150, 105, .08); }
.acr__mark { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; background: var(--success-600, #059669); color: #fff; font-weight: 800; }
.acr__body { min-width: 0; }.acr__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.acr__head > div { display: grid; gap: 2px; }.acr__head small { color: var(--success-700, #047857); font-size: 10px; font-weight: 800; letter-spacing: .08em; }.acr__head strong { color: var(--t1, #111827); font-size: 14px; }
.acr__facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 10px 0 0; }.acr__facts div { min-width: 0; padding: 7px 9px; border-radius: 8px; background: rgba(255,255,255,.72); }.acr__facts dt { color: var(--t3, #6b7280); font-size: 10px; }.acr__facts dd { overflow-wrap: anywhere; margin: 3px 0 0; color: var(--t2, #374151); font-size: 12px; line-height: 1.4; }
.acr__close { border: 0; background: transparent; color: var(--t3, #6b7280); cursor: pointer; font-size: 20px; line-height: 1; }
.acr.is-warning { border-color: var(--warning-200, #fde68a); background: linear-gradient(115deg, var(--warning-50, #fffbeb), var(--card, #fff) 70%); }
.acr.is-warning .acr__mark { background: var(--warning-600, #d97706); }
.acr.is-danger { border-color: var(--danger-200, #fecaca); background: linear-gradient(115deg, var(--danger-50, #fef2f2), var(--card, #fff) 70%); }
.acr.is-danger .acr__mark { background: var(--danger-600, #dc2626); }
@media (max-width: 820px) { .acr__facts { grid-template-columns: 1fr 1fr; } }
@media (max-width: 520px) { .acr { grid-template-columns: auto minmax(0, 1fr); }.acr__close { position: absolute; top: 8px; right: 8px; }.acr__head { align-items: flex-start; flex-direction: column; }.acr__facts { grid-template-columns: 1fr; } }
</style>
