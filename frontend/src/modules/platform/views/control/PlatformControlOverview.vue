<template>
  <ModulePageShell
    title="平台总控台"
    subtitle="全平台经营总览 · 数据实时来自后端"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="pco__toolbar">
      <div class="pco__refresh-state" role="status" aria-live="polite">
        <strong>{{ loading ? '正在更新' : error ? '本次读取失败' : qualityRows.length ? '部分来源待恢复' : '数据已更新' }}</strong>
        <span v-if="loadedAt && !loading && !error">本次读取 {{ loadedAt }}</span>
      </div>
      <button type="button" class="pco__refresh" :disabled="loading" @click="load">{{ loading ? '更新中…' : '刷新总览' }}</button>
    </div>
    <LoadingState v-if="loading" text="正在加载平台总览…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pco__grid">
        <AppCard v-for="s in statCards" :key="s.label" class="pco__stat">
          <div class="pco__stat-label">{{ s.label }}</div>
          <div class="pco__stat-num">{{ s.value }}</div>
          <div v-if="s.sub" class="pco__stat-sub">{{ s.sub }}</div>
        </AppCard>
      </div>

      <AppCard v-if="qualityRows.length" class="pco__risks">
        <AppSectionHeader title="数据质量：存在未取得或部分覆盖的数据源" />
        <ul class="pco__list">
          <li v-for="item in qualityRows" :key="item.key">
            <span class="pco__list-name">{{ item.label }}{{ item.message ? ` · ${item.message}` : '' }}</span>
            <StatusTag :type="qualityTone(item.status)" :label="qualityLabel(item.status)" />
          </li>
        </ul>
      </AppCard>

      <AppCard v-if="ov.operationalRisks && ov.operationalRisks.length" class="pco__risks">
        <AppSectionHeader title="运行风险（服务目录 / 事件 / 变更 / 数据质量）" />
        <ul class="pco__list">
          <li v-for="(r, i) in ov.operationalRisks" :key="i">
            <span class="pco__list-name">{{ r.text }}</span>
            <StatusTag :type="r.level === 'HIGH' ? 'danger' : 'warning'" :label="riskSourceLabel(r.sourceCard)" />
          </li>
        </ul>
      </AppCard>

      <div class="pco__cols">
        <AppCard class="pco__panel">
          <AppSectionHeader title="今日动态" />
          <ul class="pco__kv">
            <li><span>今日登录</span><b>{{ formatCount(ov.todayLogin) }}</b></li>
            <li><span>近 7 天登录</span><b>{{ formatCount(ov.weekLogin) }}</b></li>
            <li><span>今日导入 / 导出</span><b>{{ formatCount(ov.todayImport) }} / {{ formatCount(ov.todayExport) }}</b></li>
            <li><span>今日上传</span><b>{{ formatCount(ov.todayUpload) }}</b></li>
            <li><span>今日审批动作</span><b>{{ formatCount(ov.todayApproval) }}</b></li>
            <li><span>待办 / 待审批（全平台）</span><b>{{ formatCount(ov.todoPending) }} / {{ formatCount(ov.approvalPending) }}</b></li>
          </ul>
        </AppCard>
        <AppCard class="pco__panel">
          <AppSectionHeader title="30 天内到期租户" />
          <p v-if="!Array.isArray(ov.expiringTenants)" class="pco__unavailable">临期租户数据未取得</p>
          <EmptyState v-else-if="!ov.expiringTenants.length" text="暂无临期租户" compact />
          <ul v-else class="pco__list">
            <li v-for="t in ov.expiringTenants" :key="t.tenantId || t.tenantName">
              <span class="pco__list-name">{{ t.tenantName }}</span>
              <StatusTag type="warning" :label="t.daysLeft == null ? '到期时间未取得' : `剩 ${formatCount(t.daysLeft)} 天`" />
            </li>
          </ul>
          <AppSectionHeader title="异常租户" class="pco__gap" />
          <p v-if="!Array.isArray(ov.abnormalTenants)" class="pco__unavailable">异常租户数据未取得</p>
          <EmptyState v-else-if="!ov.abnormalTenants.length" text="暂无异常租户" compact />
          <ul v-else class="pco__list">
            <li v-for="t in ov.abnormalTenants" :key="t.tenantId || t.tenantName">
              <span class="pco__list-name">{{ t.tenantName }}</span>
              <StatusTag :type="t.status === 'expired' ? 'danger' : 'default'" :label="t.status === 'expired' ? '已到期' : '已停用'" />
            </li>
          </ul>
        </AppCard>
        <AppCard class="pco__panel">
          <AppSectionHeader title="系统健康" />
          <ul class="pco__kv">
            <li><span>服务状态</span><StatusTag :type="ov.systemHealth === 'UP' ? 'success' : 'warning'" :label="platformStatusLabel(ov.systemHealth)" /></li>
            <li><span>数据库</span><StatusTag :type="ov.dbStatus === 'OK' ? 'success' : 'danger'" :label="platformStatusLabel(ov.dbStatus)" /></li>
            <li><span>文件存储权威口径</span><b>FileObject + 配额预留</b></li>
            <li><span>真实存储占用</span><b>{{ formatStorage(ov.storageUsedBytes) }}</b></li>
          </ul>
          <AppSectionHeader title="最近平台审计" class="pco__gap" />
          <p v-if="!Array.isArray(ov.recentAudits)" class="pco__unavailable">平台审计数据未取得</p>
          <EmptyState v-else-if="!ov.recentAudits.length" text="暂无平台审计记录" compact />
          <ul v-else class="pco__list">
            <li v-for="(a, i) in ov.recentAudits" :key="i">
              <span class="pco__list-name">{{ auditActionLabel(a.action) }} · {{ a.operator }}</span>
              <span class="pco__list-time">{{ (a.at || '').replace('T', ' ').slice(5, 16) }}</span>
            </li>
          </ul>
        </AppCard>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
import { AppCard, AppSectionHeader } from '@/components/ui'
import { EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { platformStatusLabel } from '@/modules/platform/constants/platform-display.constants'
import { presentAuditRecord } from '@/utils/presentationSafety'

const QUALITY_LABELS = {
  tenantLifecycle: '租户生命周期', fileFoundation: '文件与存储', serviceCatalog: '服务目录',
  incidents: '事件中心', changes: '变更中心', customerSuccess: '客户成功'
}

function nonNegativeNumber(value) {
  if (typeof value !== 'number' && typeof value !== 'string') return null
  if (typeof value === 'string' && !value.trim()) return null
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? number : null
}

export default {
  name: 'PlatformControlOverview',
  components: { AppCard, AppSectionHeader, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  props: { ctx: { type: Object, required: true } },
  data() { return { loading: true, ov: null, error: '', requestEpoch: 0, loadedAt: '' } },
  computed: {
    statCards() {
      const o = this.ov || {}
      const unresolved = o.tenantUnresolved == null ? '状态未知' : `状态未决 ${this.formatCount(o.tenantUnresolved)}`
      return [
        { label: '租户总数', value: this.formatCount(o.tenantTotal), sub: `正式 ${this.formatCount(o.tenantActive)} · 试用 ${this.formatCount(o.tenantTrial)} · ${unresolved}` },
        { label: '已到期 / 已停用', value: `${this.formatCount(o.tenantExpired)} / ${this.formatCount(o.tenantDisabled)}`, sub: '异常需跟进' },
        { label: '学生总数', value: this.formatCount(o.studentTotal), sub: '全平台在库' },
        { label: '账号总数', value: this.formatCount(o.userTotal), sub: '全平台用户' }
      ]
    },
    qualityRows() {
      const sources = this.ov?.dataQuality?.sources || {}
      return Object.keys({ ...QUALITY_LABELS, ...sources })
        .map(key => ({ key, label: QUALITY_LABELS[key] || key, status: sources[key]?.status || 'UNKNOWN', message: sources[key]?.message || '' }))
        .filter(value => value.status !== 'OK')
    }
  },
  created() { this.load() },
  beforeUnmount() { this.requestEpoch += 1 },
  methods: {
    platformStatusLabel,
    auditActionLabel(action) { return presentAuditRecord({ action }).displayAction },
    riskSourceLabel(value) {
      const labels = { SERVICE_CATALOG: '服务目录', INCIDENT: '事件中心', CHANGE: '变更中心', DATA_QUALITY: '数据质量' }
      return labels[String(value || '').toUpperCase()] || '运行风险'
    },
    qualityLabel(status) { return ({ OK: '正常', DEGRADED: '部分覆盖', UNKNOWN: '未取得' })[status] || '未取得' },
    qualityTone(status) { return status === 'OK' ? 'success' : status === 'DEGRADED' ? 'warning' : 'danger' },
    formatCount(value) {
      const number = nonNegativeNumber(value)
      return number !== null && Number.isSafeInteger(number) ? number.toLocaleString('zh-CN') : '未取得'
    },
    formatStorage(value) {
      const bytes = nonNegativeNumber(value)
      if (bytes === null) return '未取得'
      if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GiB`
      return `${(bytes / 1024 ** 2).toFixed(2)} MiB`
    },
    async load() {
      const epoch = ++this.requestEpoch
      this.loading = true
      this.error = ''
      this.ov = null
      this.loadedAt = ''
      try {
        const res = await platformControlApi.getOverview()
        if (epoch !== this.requestEpoch) return
        if (res?.code === 0 && res.data && typeof res.data === 'object' && !Array.isArray(res.data)) {
          this.ov = res.data
          this.loadedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        } else {
          this.error = res?.message && res.code !== 0 ? res.message : '平台总览数据未取得，请重试'
        }
      } catch (error) {
        if (epoch === this.requestEpoch) this.error = error?.message || '平台总览加载失败，请重试'
      } finally {
        if (epoch === this.requestEpoch) this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.pco__toolbar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);margin-bottom:var(--space-3);flex-wrap:wrap}.pco__refresh-state{display:flex;align-items:baseline;gap:var(--space-3);flex-wrap:wrap}.pco__refresh-state strong{font-size:var(--font-size-sm);color:var(--t1)}.pco__refresh-state span{font-size:12px;color:var(--text-secondary)}.pco__refresh{border:1px solid var(--border-color,#e5eaf2);background:var(--bg-card,#fff);color:var(--t1);border-radius:8px;padding:8px 14px;font:inherit;cursor:pointer}.pco__refresh:disabled{opacity:.6;cursor:wait}.pco__refresh:focus-visible{outline:2px solid var(--primary-color,#3c5cdb);outline-offset:3px}.pco__unavailable{font-size:var(--font-size-sm);color:var(--text-secondary);padding:var(--space-2) 0}.pco__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:var(--space-3)}.pco__stat{padding:var(--space-4)}.pco__stat-num{margin-top:var(--space-2);font-size:28px;font-weight:var(--font-weight-bold);color:var(--t1);overflow-wrap:anywhere}.pco__stat-label{font-size:var(--font-size-sm);color:var(--text-secondary)}.pco__stat-sub{margin-top:6px;font-size:12px;color:var(--text-tertiary)}.pco__risks{margin-top:var(--space-3);padding:var(--space-4)}.pco__cols{margin-top:var(--space-3);display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));gap:var(--space-3)}.pco__panel{padding:var(--space-4);min-width:0}.pco__gap{margin-top:var(--space-4)}.pco__kv{list-style:none;margin:var(--space-2) 0 0;padding:0;display:flex;flex-direction:column;gap:var(--space-2)}.pco__kv li{display:flex;align-items:center;justify-content:space-between;font-size:var(--font-size-sm);color:var(--text-secondary);gap:var(--space-2);flex-wrap:wrap}.pco__kv b{color:var(--t1);overflow-wrap:anywhere}.pco__list{list-style:none;margin:var(--space-2) 0 0;padding:0;display:flex;flex-direction:column;gap:var(--space-2)}.pco__list li{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--space-2)}.pco__list-name{font-size:var(--font-size-sm);color:var(--t2);overflow-wrap:anywhere;min-width:0}.pco__list-time{font-size:12px;color:var(--text-tertiary);white-space:nowrap}
</style>
