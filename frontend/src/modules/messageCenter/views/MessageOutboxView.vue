<template>
  <ModulePageShell
    title="发布记录"
    :subtitle="subtitle"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!rows.length"
      title="暂无发布记录"
      description="可在「通知发布」创建本班或本院通知"
    />
    <table v-else class="mc-table">
      <thead>
        <tr>
          <th>标题</th>
          <th>状态</th>
          <th>人数</th>
          <th>已送达</th>
          <th>时间</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.campaignId">
          <td>
            <div class="mc-main">{{ r.title }}</div>
            <div class="mc-sub">{{ r.category }} · {{ r.priority }}</div>
          </td>
          <td>{{ r.status }}</td>
          <td>{{ r.recipientCount }}</td>
          <td>{{ r.deliveredCount }}</td>
          <td>{{ formatTime(r.publishedAt || r.createdAt) }}</td>
          <td>
            <button type="button" class="mc-link" @click="goDetail(r.campaignId)">详情</button>
          </td>
        </tr>
      </tbody>
    </table>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, EmptyState, ErrorState } from '@/components/business'
import { fetchCampaigns } from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageOutboxView',
  components: { ModulePageShell, LoadingState, EmptyState, ErrorState },
  props: { ctx: { type: Object, default: null } },
  data() {
    return { rows: [], loading: false, error: '', total: 0 }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    subtitle() {
      return this.total ? `共 ${this.total} 条发布单` : '本人权限范围内的发布记录'
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await fetchCampaigns({ page: 1, pageSize: 50 })
        this.rows = (data && data.items) || []
        this.total = (data && data.total) || 0
      } catch (e) {
        this.error = (e && e.message) || '加载失败'
      } finally {
        this.loading = false
      }
    },
    goDetail(id) {
      this.$router.push(`/admin/messages/outbox/${id}`)
    },
    formatTime(v) {
      if (!v) return ''
      return String(v).replace('T', ' ').slice(0, 16)
    }
  }
}
</script>

<style scoped>
.mc-table { width: 100%; border-collapse: collapse; background: var(--bg-card); }
.mc-table th, .mc-table td {
  padding: 12px 14px; border-bottom: 1px solid var(--border-light);
  text-align: left; font-size: var(--font-size-sm);
}
.mc-table th { color: var(--text-tertiary); font-weight: 500; }
.mc-main { color: var(--text-primary); }
.mc-sub { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-top: 2px; }
.mc-link { border: none; background: none; color: var(--text-link); cursor: pointer; }
</style>
