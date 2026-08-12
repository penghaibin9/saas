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
      description="暂无发布记录。完成通知发布后，可在这里查看发布状态与送达情况。"
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
            <div class="mc-sub">{{ categoryLabel(r.category) }} · {{ priorityLabel(r.priority) }}</div>
          </td>
          <td>{{ statusLabel(r.status) }}</td>
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
import { safeEnumLabel } from '@/utils/presentationSafety'

const STATUS_LABEL = {
  DRAFT: '草稿',
  PENDING_REVIEW: '待审核',
  APPROVED: '已通过',
  RETURNED: '已退回',
  SCHEDULED: '已预约',
  PUBLISHING: '投递中',
  PUBLISHED: '已发布',
  WITHDRAWN: '已撤回',
  FAILED: '失败'
}
const CATEGORY_LABEL = { ANNOUNCEMENT: '公告', BUSINESS: '业务通知', REMINDER: '提醒', EMERGENCY: '紧急消息' }
const PRIORITY_LABEL = { LOW: '普通', NORMAL: '普通', MEDIUM: '重要', HIGH: '紧急', URGENT: '紧急' }

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
      return this.total ? `共 ${this.total} 条发布单（含草稿）` : '本人权限范围内的发布记录（含草稿）'
    }
  },
  created() {
    this.load()
  },
  activated() {
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
    statusLabel(status) {
      const key = String(status || '').toUpperCase()
      return safeEnumLabel({ value: key, dictionary: STATUS_LABEL, unknownLabel: '状态待确认' })
    },
    categoryLabel(value) {
      return safeEnumLabel({ value, dictionary: CATEGORY_LABEL, unknownLabel: '消息类型待确认' })
    },
    priorityLabel(value) {
      return safeEnumLabel({ value, dictionary: PRIORITY_LABEL, unknownLabel: '优先级待确认' })
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
