<template>
  <ModulePageShell
    title="文件存储治理"
    subtitle="学校自助查看容量、配置配额与保留策略、预演清理并处理存储异常；平台默认不查看文件内容"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="governance-page">
      <section class="hero">
        <div>
          <h3>先看结论，再处理异常</h3>
          <p>{{ conclusion }}</p>
        </div>
        <button :disabled="loading" @click="load">刷新治理数据</button>
      </section>

      <section class="metric-grid">
        <article><strong>{{ formatGiB(usage.totalBytes) }}</strong><span>已用容量</span></article>
        <article><strong>{{ usage.quotaBytes ? formatGiB(usage.quotaBytes) : '未配置' }}</strong><span>租户总配额</span></article>
        <article><strong>{{ usage.usagePercent == null ? '—' : `${usage.usagePercent}%` }}</strong><span>配额使用率</span></article>
        <article><strong>{{ formatGiB(usage.estimatedNext30DaysGrowthBytes) }}</strong><span>近 30 天增长</span></article>
        <article><strong>{{ usage.totalFiles || 0 }}</strong><span>文件对象</span></article>
        <article><strong>{{ anomalyTotal }}</strong><span>待治理异常</span></article>
      </section>

      <div v-if="error" class="state error-state">
        <strong>治理数据加载失败</strong><span>{{ error }}</span><button @click="load">重试</button>
      </div>
      <div v-else-if="loading" class="state">正在汇总真实 FileObject、配额、保留与异常数据…</div>

      <template v-else>
        <section class="panel">
          <header><div><h3>容量与配额</h3><p>硬限额在所有物理写入和 COS 直传签发前统一执行。</p></div></header>
          <div class="form-grid">
            <label>总配额（GiB）<input v-model.number="quota.totalQuotaGiB" type="number" min="1" step="1"></label>
            <label>预警阈值（%）<input v-model.number="quota.warningPercent" type="number" min="1" max="100"></label>
            <label class="check"><input v-model="quota.hardLimitEnabled" type="checkbox">达到配额后拒绝新文件</label>
            <label class="wide">说明<input v-model.trim="quota.description" maxlength="500" placeholder="例如：本学年学校文件总配额"></label>
          </div>
          <div class="actions"><button class="primary" :disabled="busy === 'quota'" @click="saveQuota">保存配额</button></div>
          <div class="table-wrap">
            <table><thead><tr><th>业务类型</th><th>文件数</th><th>容量</th></tr></thead>
              <tbody><tr v-for="item in usage.byBizType || []" :key="`${item.moduleCode}-${item.bizType}`">
                <td>{{ item.moduleCode }} · {{ item.bizType }}</td><td>{{ item.files }}</td><td>{{ formatGiB(item.bytes) }}</td>
              </tr><tr v-if="!(usage.byBizType || []).length"><td colspan="3">暂无文件数据</td></tr></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <header><div><h3>存储异常</h3><p>这里只显示数量与状态，不绕过业务授权读取学校敏感文档。</p></div></header>
          <div class="anomaly-grid">
            <article v-for="item in anomalyCards" :key="item.key" :class="{ danger: item.value > 0 }">
              <strong>{{ item.value }}</strong><span>{{ item.label }}</span><small>{{ item.help }}</small>
            </article>
          </div>
        </section>

        <section class="panel">
          <header><div><h3>保留策略</h3><p>优先级越小越先匹配；法律保留始终覆盖自动清理。</p></div></header>
          <div class="policy-form">
            <input v-model.trim="policy.policyCode" placeholder="策略编码，如 EXPORT_7D">
            <select v-model="policy.storageZone"><option value="">全部分区</option><option v-for="zone in zones" :key="zone" :value="zone">{{ zone }}</option></select>
            <input v-model.trim="policy.bizType" placeholder="业务类型（可空）">
            <input v-model.number="policy.retentionDays" type="number" min="0" max="36500" placeholder="保留天数">
            <input v-model.number="policy.priority" type="number" min="0" max="10000" placeholder="优先级">
            <button class="primary" :disabled="busy === 'policy'" @click="savePolicy">保存策略</button>
          </div>
          <div class="table-wrap">
            <table><thead><tr><th>策略</th><th>匹配范围</th><th>保留</th><th>动作</th><th>状态</th></tr></thead>
              <tbody><tr v-for="item in policies" :key="item.id">
                <td>{{ item.policyCode }}<div class="muted">优先级 {{ item.priority }}</div></td>
                <td>{{ [item.moduleCode, item.bizType, item.storageZone].filter(Boolean).join(' / ') || '全局' }}</td>
                <td>{{ item.retentionDays }} 天</td><td>{{ item.cleanupAction }}</td><td>{{ item.active ? '启用' : '停用' }}</td>
              </tr><tr v-if="!policies.length"><td colspan="5">未配置自定义策略，将使用平台安全默认值。</td></tr></tbody>
            </table>
          </div>
        </section>

        <section class="panel danger-panel">
          <header><div><h3>安全清理与法律保留</h3><p>必须先预演；有当前版本、有效绑定、有效归档或法律保留的文件不会删除。</p></div></header>
          <div class="actions">
            <button :disabled="busy" @click="backfill">补算历史保留期</button>
            <button :disabled="busy" @click="runCleanup(true)">预演到期清理</button>
            <button class="danger-button" :disabled="busy || !cleanupPreview" @click="runCleanup(false)">执行已预演清理</button>
          </div>
          <div v-if="cleanupPreview" class="result-box">
            候选 {{ cleanupPreview.candidateCount || 0 }}，可删除 {{ cleanupPreview.items?.filter(i => i.decision === 'WOULD_DELETE').length || 0 }}，
            引用保护 {{ cleanupPreview.skippedReferenced || 0 }}，法律保留 {{ cleanupPreview.skippedLegalHold || 0 }}。
          </div>
          <div class="hold-form">
            <input v-model.trim="hold.fileId" placeholder="文件 ID">
            <input v-model.trim="hold.reason" placeholder="法律保留或解除原因（不少于 5 字）">
            <button :disabled="busy === 'hold'" @click="setHold(true)">设置法律保留</button>
            <button :disabled="busy === 'hold'" @click="setHold(false)">解除法律保留</button>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { fileStorageGovernanceApi } from '@/modules/system/api/fileStorageGovernance.api'
import { toast } from '@/utils/toast'

const GIB = 1024 ** 3

export default {
  name: 'SystemFileStorageGovernanceView',
  components: { ModulePageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, error: '', busy: '', usage: {}, anomalies: {}, policies: [], cleanupPreview: null,
      quota: { totalQuotaGiB: 100, warningPercent: 80, hardLimitEnabled: true, description: '' },
      policy: { policyCode: '', storageZone: '', bizType: '', retentionDays: 7, priority: 100 },
      hold: { fileId: '', reason: '' },
      zones: ['QUARANTINE', 'CLEAN', 'PREVIEW', 'ARCHIVE', 'EXPORT', 'REJECTED', 'TEMP']
    }
  },
  computed: {
    anomalyTotal() { return this.anomalyCards.reduce((sum, item) => sum + Number(item.value || 0), 0) },
    anomalyCards() {
      return [
        ['quarantineOverOneHour', '隔离超 1 小时', '检查扫描 worker 与 ClamAV'],
        ['scanErrors', '扫描失败', '失败关闭，不允许业务提交'],
        ['expiredPendingCleanup', '到期待清理', '先预演再执行'],
        ['cosUnverified', 'COS 未核验', '执行对象 HEAD / 哈希巡检'],
        ['unboundOver24Hours', '未绑定超 24 小时', '可能是中断上传或孤儿对象'],
        ['legalHoldFiles', '法律保留', '自动清理不会触碰']
      ].map(([key, label, help]) => ({ key, label, help, value: Number(this.anomalies[key] || 0) }))
    },
    conclusion() {
      if (this.loading) return '正在计算学校文件容量与异常。'
      if (this.anomalyTotal) return `当前发现 ${this.anomalyTotal} 项治理信号，优先处理扫描失败、长期隔离和未核验 COS 对象。`
      if (this.usage.usagePercent >= Number(this.usage.warningPercent || 80)) return '容量已接近预警线，建议清理过期导出与预览文件或扩容。'
      return '当前容量与安全治理未发现阻断项，系统会继续按策略自动清理。'
    }
  },
  created() { this.load() },
  methods: {
    formatGiB(value) { return `${(Number(value || 0) / GIB).toFixed(2)} GiB` },
    async load() {
      this.loading = true; this.error = ''
      try {
        const data = await fileStorageGovernanceApi.overview()
        this.usage = data.usage || {}; this.anomalies = data.anomalies || {}; this.policies = data.policies || []
        if (this.usage.quotaBytes) this.quota.totalQuotaGiB = Math.max(1, Math.round(this.usage.quotaBytes / GIB))
        if (this.usage.warningPercent) this.quota.warningPercent = this.usage.warningPercent
        this.quota.hardLimitEnabled = Boolean(this.usage.hardLimitEnabled)
      } catch (error) { this.error = error.message || '文件存储治理加载失败' }
      finally { this.loading = false }
    },
    async saveQuota() {
      if (Number(this.quota.totalQuotaGiB) <= 0) return toast.warning('总配额必须大于 0 GiB')
      this.busy = 'quota'
      try {
        await fileStorageGovernanceApi.saveQuota({
          totalQuotaBytes: Math.round(Number(this.quota.totalQuotaGiB) * GIB),
          warningPercent: Number(this.quota.warningPercent), hardLimitEnabled: this.quota.hardLimitEnabled,
          moduleQuotaBytes: {}, description: this.quota.description || null
        })
        toast.success('存储配额已保存'); await this.load()
      } catch (error) { toast.error(error.message || '配额保存失败') }
      finally { this.busy = '' }
    },
    async savePolicy() {
      if (!this.policy.policyCode) return toast.warning('请填写策略编码')
      this.busy = 'policy'
      try {
        await fileStorageGovernanceApi.savePolicy({ ...this.policy, moduleCode: null, cleanupAction: 'DELETE_BYTES', active: true })
        toast.success('保留策略已保存'); this.policy.policyCode = ''; await this.load()
      } catch (error) { toast.error(error.message || '策略保存失败') }
      finally { this.busy = '' }
    },
    async backfill() {
      this.busy = 'backfill'
      try { const data = await fileStorageGovernanceApi.backfill(1000); toast.success(`已为 ${data.updated || 0} 个历史文件补算保留期`); await this.load() }
      catch (error) { toast.error(error.message || '保留期补算失败') }
      finally { this.busy = '' }
    },
    async runCleanup(dryRun) {
      if (!dryRun && !window.confirm('只会删除预演中无有效引用、已过保留期且未法律保留的文件。确认执行？')) return
      this.busy = dryRun ? 'preview' : 'cleanup'
      try {
        const data = await fileStorageGovernanceApi.cleanup({ dryRun, limit: 1000 })
        if (dryRun) { this.cleanupPreview = data; toast.success('清理预演完成，请核对结果') }
        else { this.cleanupPreview = null; toast.success(`清理完成，回收 ${this.formatGiB(data.bytesReclaimed)}`) }
        await this.load()
      } catch (error) { toast.error(error.message || '清理任务失败') }
      finally { this.busy = '' }
    },
    async setHold(enabled) {
      if (!this.hold.fileId || this.hold.reason.length < 5) return toast.warning('请填写文件 ID 和不少于 5 字的原因')
      this.busy = 'hold'
      try {
        await fileStorageGovernanceApi.setLegalHold(this.hold.fileId, enabled, this.hold.reason)
        toast.success(enabled ? '已设置法律保留' : '已解除法律保留'); this.hold = { fileId: '', reason: '' }; await this.load()
      } catch (error) { toast.error(error.message || '法律保留状态更新失败') }
      finally { this.busy = '' }
    }
  }
}
</script>

<style scoped>
.governance-page { display: grid; gap: 16px; }
.hero, .panel { border: 1px solid #e5e6eb; border-radius: 12px; background: #fff; padding: 18px; }
.hero, .panel header, .actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
h3 { margin: 0 0 6px; } p { margin: 0; color: #646a73; }
.metric-grid, .anomaly-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.metric-grid article, .anomaly-grid article { display: grid; gap: 5px; padding: 14px; border: 1px solid #e5e6eb; border-radius: 10px; background: #fafbfc; }
.metric-grid strong, .anomaly-grid strong { font-size: 24px; }.metric-grid span, .anomaly-grid span { color: #4e5969; }
.anomaly-grid small { color: #86909c; }.anomaly-grid .danger { border-color: #ffccc7; background: #fff2f0; }
.form-grid { display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }
.form-grid label { display: grid; gap: 6px; font-size: 13px; }.form-grid .wide { grid-column: 1 / -1; }.form-grid .check { display: flex; align-items: center; }
input, select, button { min-height: 36px; border: 1px solid #c9cdd4; border-radius: 7px; padding: 0 10px; background: #fff; }
button { cursor: pointer; } button:disabled { opacity: .55; cursor: not-allowed; }.primary { background: #165dff; border-color: #165dff; color: #fff; }.danger-button { color: #b42318; border-color: #f04438; }
.actions { justify-content: flex-start; margin-top: 14px; }.table-wrap { overflow: auto; margin-top: 14px; }table { width: 100%; border-collapse: collapse; }th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e5e6eb; }th { background: #f7f8fa; }.muted { color: #86909c; font-size: 12px; }
.policy-form, .hold-form { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; margin-top: 16px; }.hold-form { grid-template-columns: 140px 1fr auto auto; }
.result-box, .state { margin-top: 14px; padding: 12px; border-radius: 8px; background: #f2f3f5; }.error-state { color: #b42318; background: #fff2f0; }.danger-panel { border-color: #ffd591; }
@media (max-width: 900px) { .form-grid, .policy-form, .hold-form { grid-template-columns: 1fr; }.hero, .panel header { align-items: flex-start; flex-direction: column; } }
</style>
