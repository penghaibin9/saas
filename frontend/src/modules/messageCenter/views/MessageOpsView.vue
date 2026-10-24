<template>
  <ModulePageShell
    title="投递运维"
    subtitle="查看投递异常与积压提醒，处理失败的任务可重试。"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mc-ops">
      <section class="mc-card">
        <div class="mc-row">
          <h3>对账与告警</h3>
          <button type="button" class="mc-btn" :disabled="loading" @click="loadReconcile">刷新对账</button>
        </div>
        <p v-if="reconcile?.error" role="alert">{{ safeBusinessMessage(reconcile.error, '对账失败，请重试') }}</p>
        <template v-else-if="reconcile">
          <p>待处理通知 {{ reconcile.backlog?.outboxPending ?? '—' }} · 处理失败 {{ reconcile.backlog?.outboxDead ?? '—' }}</p>
          <p>待投递消息 {{ reconcile.backlog?.deliveryPending ?? '—' }} · 投递失败 {{ reconcile.backlog?.deliveryDead ?? '—' }}</p>
          <p>本次校正 {{ reconcile.driftFixed ?? '—' }} 项统计</p>
          <p v-for="(alert, index) in reconcile.alerts || []" :key="index">{{ messageAlertLabel(alert.code) }}：{{ alert.count }}</p>
          <details><summary>实施人员使用</summary><pre class="mc-pre">{{ reconcileText }}</pre></details>
        </template>
      </section>

      <section class="mc-card">
        <h3>失败任务</h3>
        <table class="mc-table" v-if="letters.length">
          <thead><tr><th>序号</th><th>类型</th><th>任务信息</th><th>尝试次数</th><th>失败原因</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(j, index) in letters" :key="(j.kind || '') + '-' + j.jobId">
              <td>{{ index + 1 }}</td>
              <td>{{ messageJobKindLabel(j.kind || 'DELIVERY_JOB') }}</td>
              <td><details><summary>实施人员使用</summary>任务编号：{{ j.jobId }}<br>发布记录：{{ j.campaignId || '—' }}<br>事件：{{ j.eventCode || '—' }}</details></td>
              <td>{{ j.attemptCount }}</td>
              <td>{{ j.lastError ? safeBusinessMessage(j.lastError, '投递失败，请联系管理员核查') : '未提供失败原因' }}</td>
              <td>
                <button type="button" class="mc-btn mc-btn--primary" @click="retry(j)">重试</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="mc-muted">暂无失败任务</p>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ErrorState, LoadingState } from '@/components/business'
import { safeBusinessMessage } from '@/utils/presentationSafety'
import { messageJobKindLabel, messageAlertLabel } from '@/modules/messageCenter/constants/message-center.constants'
import {
  fetchDeadLetters,
  retryDeadLetter,
  fetchReconcile
} from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageOpsView',
  components: { ModulePageShell, ErrorState, LoadingState },
  props: { ctx: { type: Object, default: null } },
  data() {
    return { loading: false, error: '', letters: [], reconcile: null }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    reconcileText() {
      return JSON.stringify(this.reconcile || {}, null, 2)
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    safeBusinessMessage,
    messageJobKindLabel,
    messageAlertLabel,
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await fetchDeadLetters()
        this.letters = (data && data.items) || []
        await this.loadReconcile()
      } catch (e) {
        this.error = (e && e.message) || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadReconcile() {
      try {
        this.reconcile = await fetchReconcile()
      } catch (e) {
        this.reconcile = { error: (e && e.message) || '对账失败' }
      }
    },
    async retry(j) {
      try {
        await retryDeadLetter(j.jobId, { kind: j.kind || 'DELIVERY_JOB' })
        await this.load()
      } catch (e) {
        this.error = (e && e.message) || '重试失败'
      }
    }
  }
}
</script>

<style scoped>
.mc-ops { display: flex; flex-direction: column; gap: var(--space-4); }
.mc-card {
  border: 1px solid var(--border-base); border-radius: var(--radius-md);
  background: var(--bg-card); padding: var(--space-4);
}
.mc-row { display: flex; justify-content: space-between; align-items: center; }
.mc-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.mc-table th, .mc-table td { border-bottom: 1px solid var(--border-base); padding: 8px; text-align: left; }
.mc-btn {
  height: 28px; padding: 0 10px; border-radius: var(--radius-sm);
  border: 1px solid var(--border-base); background: var(--bg-card); cursor: pointer;
}
.mc-btn--primary { background: var(--primary-500); border-color: var(--primary-500); color: #fff; }
.mc-muted { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.mc-pre {
  background: var(--bg-subtle, #f8fafc); padding: var(--space-3);
  border-radius: var(--radius-sm); overflow: auto; font-size: 12px;
}
</style>
