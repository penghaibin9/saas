<template>
  <ModulePageShell title="发布详情" :subtitle="camp ? camp.status : ''">
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="camp" class="mc-detail">
      <h2>{{ camp.title }}</h2>
      <div class="mc-meta">
        <span>状态 {{ statusLabel }}</span>
        <span>接收 {{ camp.recipientCount }}</span>
        <span>送达 {{ camp.deliveredCount }}</span>
        <span>已读 {{ camp.readCount }}</span>
        <span>确认 {{ camp.ackCount }}</span>
        <span v-if="camp.emergency">紧急</span>
      </div>
      <pre class="mc-body">{{ camp.contentPlain }}</pre>
      <div v-if="camp.withdrawReason" class="mc-alert">撤回说明：{{ camp.withdrawReason }}</div>
      <div v-if="camp.status === 'PENDING_REVIEW'" class="mc-alert mc-alert--info">
        待审核：通过后将开始投递；发布人与终审人不得为同一人。
      </div>
      <div v-if="camp.status === 'RETURNED'" class="mc-alert">已退回，请发布人修改后重新提交。</div>
      <div class="mc-actions">
        <button
          v-if="canApprove"
          type="button"
          class="mc-btn mc-btn--primary"
          :disabled="acting"
          @click="doApprove"
        >
          审核通过并投递
        </button>
        <button
          v-if="canApprove"
          type="button"
          class="mc-btn"
          :disabled="acting"
          @click="doReturn"
        >
          退回
        </button>
        <button
          v-if="canWithdraw"
          type="button"
          class="mc-btn"
          :disabled="acting"
          @click="doWithdraw"
        >
          撤回
        </button>
        <button
          v-if="canDrill"
          type="button"
          class="mc-btn"
          :disabled="acting"
          @click="loadRecipients('UNREAD')"
        >
          未读名单
        </button>
        <button
          v-if="canDrill"
          type="button"
          class="mc-btn"
          :disabled="acting"
          @click="loadRecipients('UNACKED')"
        >
          未确认名单
        </button>
        <button
          v-if="canDrill"
          type="button"
          class="mc-btn"
          :disabled="acting"
          @click="doExport"
        >
          导出 Excel
        </button>
        <button type="button" class="mc-btn" @click="$router.push('/admin/messages/outbox')">返回列表</button>
      </div>
      <div v-if="recipients.length" class="mc-recipients">
        <h3>{{ recipientTitle }}</h3>
        <table>
          <thead><tr><th>姓名</th><th>账号</th><th>状态</th><th>确认</th></tr></thead>
          <tbody>
            <tr v-for="r in recipients" :key="r.messageId">
              <td>{{ r.realName || '-' }}</td>
              <td>{{ r.loginName || r.userId }}</td>
              <td>{{ r.status }}</td>
              <td>{{ r.ackAt || (r.requireAck ? '未确认' : '-') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import {
  approveCampaign,
  exportCampaignRecipients,
  fetchCampaign,
  fetchCampaignRecipients,
  returnCampaign,
  withdrawCampaign
} from '@/modules/messageCenter/api/message-campaign.api'

const STATUS_LABEL = {
  DRAFT: '草稿',
  PENDING_REVIEW: '待审核',
  RETURNED: '已退回',
  PUBLISHING: '投递中',
  PUBLISHED: '已发布',
  PARTIAL_FAILED: '部分失败',
  WITHDRAWN: '已撤回'
}

export default {
  name: 'MessageCampaignDetailView',
  components: { ModulePageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      camp: null, loading: false, error: '', acting: false,
      recipients: [], recipientTitle: ''
    }
  },
  computed: {
    statusLabel() {
      if (!this.camp) return ''
      return STATUS_LABEL[this.camp.status] || this.camp.status
    },
    canWithdraw() {
      return this.camp && ['PUBLISHED', 'PUBLISHING', 'PARTIAL_FAILED'].includes(this.camp.status)
    },
    canDrill() {
      return this.camp && ['PUBLISHED', 'PUBLISHING', 'PARTIAL_FAILED', 'EXPIRED'].includes(this.camp.status)
    },
    canApprove() {
      if (!this.camp || this.camp.status !== 'PENDING_REVIEW') return false
      const patterns = (this.ctx && this.ctx.permissionPatterns) || null
      if (!patterns) return true
      if (patterns.includes('*')) return true
      if (patterns.includes('workbench.message.emergency.approve')) return true
      return patterns.some(
        (p) => typeof p === 'string' && p.endsWith('.*') && 'workbench.message.emergency.approve'.startsWith(p.slice(0, -1))
      )
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
        this.camp = await fetchCampaign(this.$route.params.campaignId)
      } catch (e) {
        this.error = (e && e.message) || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadRecipients(filter) {
      this.acting = true
      try {
        const data = await fetchCampaignRecipients(this.camp.campaignId, { filter, pageSize: 100 })
        this.recipients = (data && data.items) || []
        this.recipientTitle = filter === 'UNACKED' ? '未确认名单' : '未读名单'
      } catch (e) {
        this.error = (e && e.message) || '加载名单失败'
      } finally {
        this.acting = false
      }
    },
    async doExport() {
      const purpose = window.prompt('请填写导出用途（审计必填）', '催读/对账')
      if (!purpose || purpose.trim().length < 2) return
      this.acting = true
      try {
        await exportCampaignRecipients(this.camp.campaignId, {
          filter: this.recipientTitle.includes('确认') ? 'UNACKED' : 'UNREAD',
          purpose: purpose.trim()
        })
        window.alert('导出已生成（见接口返回文件）')
      } catch (e) {
        this.error = (e && e.message) || '导出失败'
      } finally {
        this.acting = false
      }
    },
    async doApprove() {
      if (!window.confirm(`确认通过并投递？预计接收 ${this.camp.recipientCount || 0} 人。`)) return
      this.acting = true
      try {
        const result = await approveCampaign(this.camp.campaignId, { version: this.camp.version })
        this.camp = { ...this.camp, ...result, status: result.status || 'PUBLISHED' }
        await this.load()
      } catch (e) {
        this.error = (e && e.message) || '审核失败'
      } finally {
        this.acting = false
      }
    },
    async doReturn() {
      const reason = window.prompt('请输入退回原因（必填）')
      if (!reason || reason.trim().length < 2) return
      this.acting = true
      try {
        this.camp = await returnCampaign(this.camp.campaignId, {
          version: this.camp.version,
          reason: reason.trim()
        })
      } catch (e) {
        this.error = (e && e.message) || '退回失败'
      } finally {
        this.acting = false
      }
    },
    async doWithdraw() {
      const reason = window.prompt('请输入撤回原因（必填）')
      if (!reason || reason.trim().length < 2) return
      this.acting = true
      try {
        this.camp = await withdrawCampaign(this.camp.campaignId, {
          reason: reason.trim(),
          version: this.camp.version
        })
      } catch (e) {
        this.error = (e && e.message) || '撤回失败'
      } finally {
        this.acting = false
      }
    }
  }
}
</script>

<style scoped>
.mc-detail { max-width: 860px; }
.mc-meta { display: flex; flex-wrap: wrap; gap: 12px; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.mc-body { white-space: pre-wrap; font-family: inherit; background: var(--bg-subtle, #f8fafc); padding: 16px; border-radius: 8px; }
.mc-alert { margin-top: 12px; padding: 12px; background: #fff7ed; color: #9a3412; border-radius: 8px; }
.mc-alert--info { background: #eff6ff; color: #1e40af; }
.mc-actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
.mc-btn { height: 32px; padding: 0 14px; border: 1px solid var(--border-base); border-radius: 6px; background: var(--bg-card); cursor: pointer; }
.mc-btn--primary { background: var(--primary-500); border-color: var(--primary-500); color: #fff; }
.mc-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.mc-recipients { margin-top: 16px; }
.mc-recipients table { width: 100%; border-collapse: collapse; font-size: 13px; }
.mc-recipients th, .mc-recipients td { border-bottom: 1px solid var(--border-base); padding: 8px; text-align: left; }
</style>
