<template>
  <ModulePageShell
    title="投递运维"
    subtitle="死信作业重试、对账与积压告警（partial）"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <div v-else class="mc-ops">
      <section class="mc-card">
        <div class="mc-row">
          <h3>对账与告警</h3>
          <button type="button" class="mc-btn" :disabled="loading" @click="loadReconcile">刷新对账</button>
        </div>
        <pre v-if="reconcile" class="mc-pre">{{ reconcileText }}</pre>
      </section>

      <section class="mc-card">
        <h3>死信台账</h3>
        <table class="mc-table" v-if="letters.length">
          <thead><tr><th>ID</th><th>类型</th><th>发布单/事件</th><th>尝试</th><th>错误</th><th></th></tr></thead>
          <tbody>
            <tr v-for="j in letters" :key="(j.kind || '') + '-' + j.jobId">
              <td>{{ j.jobId }}</td>
              <td>{{ j.kind || 'DELIVERY_JOB' }}</td>
              <td>{{ j.campaignId || j.eventCode || '-' }}</td>
              <td>{{ j.attemptCount }}</td>
              <td>{{ j.lastError || '-' }}</td>
              <td>
                <button type="button" class="mc-btn mc-btn--primary" @click="retry(j)">重试</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="mc-muted">暂无死信</p>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ErrorState } from '@/components/business'
import {
  fetchDeadLetters,
  retryDeadLetter,
  fetchReconcile
} from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageOpsView',
  components: { ModulePageShell, ErrorState },
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
