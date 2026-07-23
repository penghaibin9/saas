<template>
  <ModulePageShell
    title="发送统计"
    subtitle="按权限范围统计发布与回执"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="data" class="mc-stats">
      <div class="mc-stats__toolbar">
        <label>
          近
          <select v-model.number="days" @change="load">
            <option :value="7">7</option>
            <option :value="30">30</option>
            <option :value="90">90</option>
          </select>
          天
        </label>
        <span class="mc-muted">更新于 {{ data.updatedAt || '—' }}</span>
      </div>
      <p class="mc-note">{{ data.denominatorNote }}</p>
      <div class="mc-grid">
        <div v-for="m in metricCards" :key="m.key" class="mc-card">
          <div class="mc-card__label">{{ m.label }}</div>
          <div class="mc-card__val">{{ m.value }}</div>
        </div>
      </div>
      <div class="mc-two">
        <div class="mc-panel">
          <h3>按状态</h3>
          <div v-for="r in data.byStatus || []" :key="r.status" class="mc-row">
            <span>{{ r.status }}</span><strong>{{ r.count }}</strong>
          </div>
          <EmptyState v-if="!(data.byStatus || []).length" title="暂无发布单" />
        </div>
        <div class="mc-panel">
          <h3>按类型</h3>
          <div v-for="r in data.byCategory || []" :key="r.category" class="mc-row">
            <span>{{ r.category }}</span><strong>{{ r.count }}</strong>
          </div>
        </div>
      </div>
      <div class="mc-panel">
        <h3>渠道状态</h3>
        <div v-for="c in data.channels || []" :key="c.channel" class="mc-row">
          <span>{{ c.label }}</span>
          <strong :class="{ 'is-warn': c.status === 'NOT_CONFIGURED' }">
            {{ c.status === 'READY' ? '已就绪' : c.status === 'NOT_CONFIGURED' ? '未配置' : c.status }}
          </strong>
        </div>
      </div>
      <div class="mc-actions">
        <button type="button" class="mc-btn" @click="$router.push('/admin/messages/outbox')">下钻到发布记录</button>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { fetchCampaignStatistics } from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageStatisticsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, default: null } },
  data() {
    return { loading: false, error: '', data: null, days: 30 }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    metricCards() {
      const m = (this.data && this.data.metrics) || {}
      return [
        { key: 'c', label: '发布次数', value: m.campaignCount ?? 0 },
        { key: 'r', label: '接收人数（分母）', value: m.recipientCount ?? 0 },
        { key: 'd', label: '站内送达', value: `${m.deliveredCount ?? 0}（${m.deliveryRate ?? 0}%）` },
        { key: 'rd', label: '已读', value: `${m.readCount ?? 0}（${m.readRate ?? 0}%）` },
        { key: 'a', label: '确认', value: `${m.ackCount ?? 0}（${m.ackRate ?? 0}%）` },
        { key: 'f', label: '失败', value: m.failureCount ?? 0 }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.data = await fetchCampaignStatistics({ days: this.days })
      } catch (e) {
        this.error = (e && e.message) || '加载统计失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.mc-stats__toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.mc-note { font-size: var(--font-size-sm); color: var(--text-tertiary); margin: 0 0 16px; }
.mc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.mc-card { border: 1px solid var(--border-base); border-radius: 8px; padding: 12px 14px; background: var(--bg-card); }
.mc-card__label { font-size: 12px; color: var(--text-tertiary); }
.mc-card__val { margin-top: 6px; font-size: 20px; font-weight: 600; }
.mc-two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.mc-panel { border: 1px solid var(--border-base); border-radius: 8px; padding: 14px; margin-top: 12px; }
.mc-panel h3 { margin: 0 0 10px; font-size: 14px; }
.mc-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; border-bottom: 1px solid var(--border-base); }
.mc-row .is-warn { color: #b45309; }
.mc-muted { font-size: 12px; color: var(--text-tertiary); }
.mc-actions { margin-top: 16px; }
.mc-btn { height: 32px; padding: 0 14px; border: 1px solid var(--border-base); border-radius: 6px; background: var(--bg-card); cursor: pointer; }
@media (max-width: 720px) { .mc-two { grid-template-columns: 1fr; } }
</style>
