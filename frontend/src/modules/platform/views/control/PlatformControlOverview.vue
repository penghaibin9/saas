<template>
  <ModulePageShell class="platform-workspace pco" title="平台总控台" subtitle="今日重点、学校服务与平台运行，一处掌握" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName">
    <template #actions>
      <button type="button" class="pw-button" :disabled="loading" @click="load"><span aria-hidden="true">↻</span>{{ loading ? '更新中…' : '刷新总览' }}</button>
    </template>
    <LoadingState v-if="loading" text="正在加载平台总览…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" @back="$router.push('/admin/platform/tenants')" />
    <template v-else-if="ov">
      <section class="pco__welcome" aria-labelledby="pco-focus-title">
        <div class="pco__welcome-main">
          <span class="pw-eyebrow"><AppIcon name="workbench" :size="18" />今日运营</span>
          <h2 id="pco-focus-title">{{ focusTitle }}</h2>
          <p>{{ focusDescription }}</p>
          <div class="pco__welcome-actions">
            <RouterLink v-if="can('platform.tenant.view')" class="pw-button pw-button--primary" to="/admin/platform/tenants">进入学校清单 <span aria-hidden="true">→</span></RouterLink>
            <RouterLink v-if="can('platform.order.view')" class="pw-button" to="/admin/platform/orders">处理合同订单</RouterLink>
          </div>
          <div class="pco__refresh-state" role="status" aria-live="polite"><span class="pco__signal" :class="{ 'pco__signal--warning': qualityRows.length }" /><span>{{ qualityRows.length ? '部分数据来源待恢复' : '本次数据已更新' }}</span><span v-if="loadedAt">{{ loadedAt }}</span></div>
        </div>
        <section class="pco__priority" aria-labelledby="pco-priority-title">
          <header class="pco__section-head"><h2 id="pco-priority-title">优先跟进</h2><span class="pco__count">{{ priorityItems.length }} 项已发现</span></header>
          <ul v-if="priorityItems.length" class="pco__priority-list">
            <li v-for="item in priorityItems.slice(0, 3)" :key="item.key">
              <span class="pco__priority-dot" :data-tone="item.tone" />
              <div class="pco__priority-copy"><strong>{{ item.title }}</strong><p>{{ item.description }}</p></div>
              <RouterLink v-if="item.to && can(item.permission)" class="pco__row-link" :to="item.to" :aria-label="`${item.title}，${item.action}`">{{ item.action }} <span aria-hidden="true">↗</span></RouterLink>
              <span v-else class="pco__readonly">待责任人跟进</span>
            </li>
          </ul>
          <p v-else class="pco__calm">{{ qualityRows.length ? '部分来源尚未取得，恢复后再核对待办。' : '本次已取得的数据中，没有发现待跟进事项。' }}</p>
          <p v-if="priorityItems.length > 3" class="pco__queue-note">先展示前 3 项，高风险优先；完整学校事项与运行风险见下方。</p>
        </section>
      </section>

      <PlatformMetricStrip :items="overviewMetrics" />

      <details v-if="qualityRows.length" class="pco__quality" open>
        <summary><AppIcon name="risk" :size="18" /><strong>{{ qualityRows.length }} 个数据来源需核对</strong><span>缺失数据不会当作 0</span></summary>
        <ul class="pco__quality-list"><li v-for="item in qualityRows" :key="item.key"><span>{{ item.label }}<small v-if="item.message">{{ item.message }}</small></span><StatusTag :type="qualityTone(item.status)" :label="qualityLabel(item.status)" /></li></ul>
      </details>

      <div class="pco__main-grid">
        <section class="pco__panel pco__schools" aria-labelledby="pco-schools-title">
          <header class="pco__section-head"><div><span class="pw-eyebrow">学校服务</span><h2 id="pco-schools-title">临期与异常学校</h2></div><RouterLink v-if="can('platform.tenant.view')" class="pco__row-link" to="/admin/platform/tenants">全部学校 <span aria-hidden="true">→</span></RouterLink></header>
          <p v-if="!Array.isArray(ov.expiringTenants) || !Array.isArray(ov.abnormalTenants)" class="pco__unavailable">部分学校跟进数据未取得，请刷新核对。</p>
          <div v-if="schoolFollowups.length" class="pco__school-list">
            <div v-for="item in schoolFollowups" :key="item.key" class="pco__school-row">
              <span class="pco__school-avatar" :data-tone="item.tone" aria-hidden="true">{{ item.title.slice(0, 1) }}</span>
              <div class="pco__school-copy"><strong>{{ item.title }}</strong><small>{{ item.description }}</small></div>
              <StatusTag :type="item.tone" :label="item.statusLabel" />
              <RouterLink v-if="can('platform.tenant.view')" class="pco__row-link" :to="item.to" :aria-label="`跟进${item.title}`">跟进 <span aria-hidden="true">→</span></RouterLink>
            </div>
          </div>
          <EmptyState v-else-if="Array.isArray(ov.expiringTenants) && Array.isArray(ov.abnormalTenants)" title="暂无临期或异常学校" description="本次读取的学校清单中未发现需要跟进的临期或异常记录。"><template #actions><span class="pw-empty-note">可通过“全部学校”查看完整服务范围。</span></template></EmptyState>
          <p class="pco__panel-foot">临期范围为 30 天内；学校事项以本次返回清单为准。</p>
        </section>
        <section class="pco__panel" aria-labelledby="pco-activity-title">
          <header class="pco__section-head"><div><span class="pw-eyebrow">使用概况</span><h2 id="pco-activity-title">今日动态</h2></div><AppIcon name="kpi" :size="22" /></header>
          <div class="pco__activity-lead"><strong>{{ formatCount(ov.todayLogin) }}</strong><span>今日登录</span><small>近 7 天 {{ formatCount(ov.weekLogin) }} 次</small></div>
          <dl class="pco__activity-grid"><div><dt>导入 / 导出</dt><dd>{{ formatCount(ov.todayImport) }} / {{ formatCount(ov.todayExport) }}</dd></div><div><dt>文件上传</dt><dd>{{ formatCount(ov.todayUpload) }}</dd></div><div><dt>审批动作</dt><dd>{{ formatCount(ov.todayApproval) }}</dd></div><div><dt>待办 / 待审批</dt><dd>{{ formatCount(ov.todoPending) }} / {{ formatCount(ov.approvalPending) }}</dd></div></dl>
        </section>
      </div>

      <div class="pco__bottom-grid">
        <section class="pco__panel" aria-labelledby="pco-risks-title">
          <header class="pco__section-head"><h2 id="pco-risks-title">运行风险</h2><AppIcon name="risk" :size="20" /></header>
          <p v-if="!Array.isArray(ov.operationalRisks)" class="pco__unavailable">运行风险数据未取得</p>
          <EmptyState v-else-if="!ov.operationalRisks.length" :title="qualityRows.length ? '部分来源未取得，暂不能判断全部运行风险' : '本次未发现运行风险'" description="以当前已经返回的数据源为准，不代表所有业务已完成验收。"><template #actions><span class="pw-empty-note">来源恢复后，可刷新总览再次核对。</span></template></EmptyState>
          <ul v-else class="pco__risk-list"><li v-for="(risk, index) in ov.operationalRisks" :key="index"><StatusTag :type="risk.level === 'HIGH' ? 'danger' : 'warning'" :label="riskSourceLabel(risk.sourceCard)" /><p>{{ risk.text }}</p><RouterLink v-if="riskDestination(risk) && can(riskDestination(risk).permission)" class="pco__row-link" :to="riskDestination(risk).to">查看处理 <span aria-hidden="true">→</span></RouterLink></li></ul>
        </section>
        <section class="pco__panel" aria-labelledby="pco-health-title">
          <header class="pco__section-head"><h2 id="pco-health-title">系统健康</h2><AppIcon name="workbench" :size="20" /></header>
          <ul class="pco__kv"><li><span>平台服务</span><StatusTag :type="ov.systemHealth === 'UP' ? 'success' : 'warning'" :label="platformStatusLabel(ov.systemHealth)" /></li><li><span>数据库</span><StatusTag :type="ov.dbStatus === 'OK' ? 'success' : 'danger'" :label="platformStatusLabel(ov.dbStatus)" /></li><li><span>真实存储占用</span><b>{{ formatStorage(ov.storageUsedBytes) }}</b></li></ul>
          <p class="pco__panel-foot">按文件对象与配额预留统计。</p>
        </section>
        <section class="pco__panel" aria-labelledby="pco-audit-title">
          <header class="pco__section-head"><h2 id="pco-audit-title">最近平台审计</h2><AppIcon name="records" :size="20" /></header>
          <p v-if="!Array.isArray(ov.recentAudits)" class="pco__unavailable">平台审计数据未取得</p>
          <EmptyState v-else-if="!ov.recentAudits.length" title="暂无平台审计记录" description="本次查询没有返回最近的平台操作记录。"><template #actions><span class="pw-empty-note">有新的操作记录后会在这里展示。</span></template></EmptyState>
          <ol v-else class="pco__timeline"><li v-for="(a, i) in ov.recentAudits" :key="i"><strong>{{ auditActionLabel(a.action) }}</strong><small>{{ a.operator || '操作人未取得' }}<time>{{ (a.at || '').replace('T', ' ').slice(5, 16) }}</time></small></li></ol>
        </section>
      </div>
    </template>
  </ModulePageShell>
</template>
<script>
import AppIcon from '@/components/ui/AppIcon.vue'
import PlatformMetricStrip from '@/modules/platform/components/PlatformMetricStrip.vue'
import { canEnterRoute, getPermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'
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
  components: { AppIcon, PlatformMetricStrip, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  props: { ctx: { type: Object, required: true } },
  data() { return { loading: true, ov: null, error: '', requestEpoch: 0, loadedAt: '' } },
  computed: {
    overviewMetrics() {
      return this.statCards.map((card, index) => ({ ...card, caption: card.sub, tone: ['brand', 'warning', 'success', 'brand'][index], icon: ['enrollment', 'risk', 'students', 'records'][index] }))
    },
    schoolFollowups() {
      const result = new Map()
      const groups = [[this.ov?.abnormalTenants, 'abnormal'], [this.ov?.expiringTenants, 'expiring']]
      for (const [rows, kind] of groups) {
        for (const [index, row] of (Array.isArray(rows) ? rows : []).entries()) {
          if (!row || typeof row !== 'object') continue
          const key = String(row.tenantId || row.tenantCode || `${kind}-${index}`)
          if (result.has(key)) continue
          const title = row.tenantName || '学校名称未取得'
          const expired = kind === 'abnormal' && row.status === 'expired'
          const disabled = kind === 'abnormal' && row.status === 'disabled'
          result.set(key, { key, title, tone: expired ? 'danger' : 'warning',
            description: expired ? '核对续费与授权激活' : disabled ? '核对停用原因与恢复条件' : kind === 'expiring' ? '提前跟进合同与续费安排' : '先核实学校生命周期状态',
            statusLabel: expired ? '已到期' : disabled ? '已停用' : kind === 'expiring' && nonNegativeNumber(row.daysLeft) !== null ? `剩 ${this.formatCount(row.daysLeft)} 天` : '状态待核验',
            to: typeof row.tenantId === 'string' && /^[1-9]\d*$/.test(row.tenantId) ? { path: `/admin/platform/tenants/${row.tenantId}` } : { path: '/admin/platform/tenants', query: { keyword: row.tenantCode || row.tenantName || '' } } })
        }
      }
      return [...result.values()]
    },
    priorityItems() {
      const schools = this.schoolFollowups.map(item => ({ ...item, key: `school-${item.key}`, permission: 'platform.tenant.view', action: '跟进学校' }))
      const risks = (Array.isArray(this.ov?.operationalRisks) ? this.ov.operationalRisks : []).map((risk, index) => ({
        key: `risk-${index}`, title: this.riskSourceLabel(risk.sourceCard), description: risk.text,
        tone: risk.level === 'HIGH' ? 'danger' : 'warning', ...this.riskDestination(risk), action: '查看处理'
      }))
      return [...risks.filter(item => item.tone === 'danger'), ...schools, ...risks.filter(item => item.tone !== 'danger')]
    },
    focusTitle() {
      if (this.qualityRows.length || !Array.isArray(this.ov?.abnormalTenants) || !Array.isArray(this.ov?.expiringTenants) || !Array.isArray(this.ov?.operationalRisks)) return '先核对数据，再处理学校事项'
      return this.priorityItems.length ? '先处理待跟进事项，再看经营概况' : '本次未发现待跟进事项'
    },
    focusDescription() {
      return this.qualityRows.length ? '部分来源尚未恢复，已取得的学校事项仍可继续跟进。' : '到期、续费和运行风险集中查看，点击事项直接进入办理。'
    },
    statCards() {
      const o = this.ov || {}
      const unresolved = o.tenantUnresolved == null ? '状态未知' : `状态未决 ${this.formatCount(o.tenantUnresolved)}`
      return [
        { label: '服务学校', value: this.formatCount(o.tenantTotal), sub: `正式 ${this.formatCount(o.tenantActive)} · 试用 ${this.formatCount(o.tenantTrial)} · ${unresolved}` },
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
    can(key) { return Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() && canEnterRoute({ moduleCode: 'PLATFORM', permissionKey: key }) },
    riskDestination(risk) {
      return ({
        SERVICE_CATALOG: { to: '/admin/platform/services', permission: 'platform.control.view' },
        INCIDENT: { to: '/admin/platform/incidents', permission: 'platform.incident.view' },
        CHANGE: { to: '/admin/platform/changes', permission: 'platform.change.manage' }
      })[String(risk.sourceCard || '').toUpperCase()] || null
    },
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

<style src="../../styles/workspace.css"></style>
<style scoped>
.pco__welcome { display: grid; grid-template-columns: minmax(0, .95fr) minmax(0, 1.15fr); border: 1px solid var(--card-b); border-radius: var(--r); overflow: hidden; background: var(--bg-card); box-shadow: var(--s1); }
.pco__welcome-main { padding: var(--space-5); background: linear-gradient(120deg, var(--pri-bg), var(--bg-card)); display: flex; flex-direction: column; align-items: flex-start; }
.pco__welcome-main h2 { margin: var(--space-3) 0 var(--space-2); font-size: var(--font-size-xl); line-height: 1.5; letter-spacing: -.03em; text-wrap: balance; }
.pco__welcome-main > p { margin: 0; max-width: 36em; font-size: var(--font-size-sm); line-height: 1.8; color: var(--t2); }
.pco__welcome-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: var(--space-4) 0; }
.pco__refresh-state { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); margin-top: auto; font-size: var(--font-size-xs); color: var(--t2); }
.pco__signal { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); }.pco__signal--warning { background: var(--warn); }
.pco__priority { padding: var(--space-5); min-width: 0; border-left: 1px solid var(--card-b); }
.pco__section-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); min-height: 28px; color: var(--t2); }
.pco__section-head h2 { margin: 0; font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); color: var(--t1); }.pco__section-head .pw-eyebrow { margin-bottom: var(--space-2); }
.pco__count { font-size: var(--font-size-xs); color: var(--t2); white-space: nowrap; }
.pco__priority-list { list-style: none; margin: var(--space-2) 0 0; padding: 0; }.pco__priority-list li { display: flex; gap: var(--space-3); align-items: center; padding: var(--space-3) 0; border-bottom: 1px solid var(--dv); }.pco__priority-list li:last-child { border: 0; }
.pco__priority-dot { width: 7px; height: 7px; flex: none; background: var(--warn); border-radius: 50%; }.pco__priority-dot[data-tone="danger"] { background: var(--err); }
.pco__priority-copy { min-width: 0; flex: 1; }.pco__priority-copy strong { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); overflow-wrap: anywhere; }.pco__priority-copy p { margin: 4px 0 0; color: var(--t2); font-size: var(--font-size-xs); line-height: 1.6; overflow-wrap: anywhere; }
.pco__row-link { display: inline-flex; align-items: center; gap: var(--space-2); min-height: 32px; flex: none; font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--pri); text-decoration: none; }.pco__row-link:hover { text-decoration: underline; }
.pco__readonly,.pco__queue-note,.pco__panel-foot { font-size: var(--font-size-xs); color: var(--t2); line-height: 1.7; }.pco__readonly { flex: none; }.pco__queue-note { margin-bottom: 0; }.pco__calm { margin: var(--space-5) 0; font-size: var(--font-size-sm); line-height: 1.8; color: var(--t2); }
.pco__quality { border: 1px solid var(--warning-100); background: var(--warn-l); border-radius: var(--r); padding: var(--space-3) var(--space-4); }.pco__quality summary { display: flex; align-items: center; gap: var(--space-2); min-height: 32px; flex-wrap: wrap; color: var(--warning-700); font-size: var(--font-size-sm); cursor: pointer; }.pco__quality summary span { font-size: var(--font-size-xs); margin-left: auto; }.pco__quality summary::after { content: '⌄'; }.pco__quality[open] summary::after { content: '⌃'; }.pco__quality-list { list-style: none; padding: 0; margin: var(--space-3) 0 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }.pco__quality-list li { display: flex; justify-content: space-between; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--t2); }.pco__quality-list small { display: block; margin-top: var(--space-1); overflow-wrap: anywhere; }
.pco__main-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: var(--space-4); }.pco__bottom-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-4); }
.pco__panel { min-width: 0; padding: var(--space-5); border: 1px solid var(--card-b); border-radius: var(--r); background: var(--bg-card); box-shadow: var(--s1); }.pco__unavailable { color: var(--warning-700); font-size: var(--font-size-sm); line-height: 1.7; }
.pco__school-list { margin-top: var(--space-3); max-height: 380px; overflow-y: auto; }.pco__school-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--dv); }.pco__school-row:last-child { border: 0; }.pco__school-avatar { display: grid; place-items: center; width: 38px; height: 38px; flex: none; border-radius: var(--rs); background: var(--pri-bg); color: var(--pri); font-weight: var(--font-weight-semibold); }.pco__school-copy { flex: 1; min-width: 0; }.pco__school-copy strong { font-size: var(--font-size-sm); overflow-wrap: anywhere; }.pco__school-copy small { display: block; margin-top: 4px; font-size: var(--font-size-xs); color: var(--t2); line-height: 1.6; }
.pco__panel-foot { margin: var(--space-3) 0 0; padding-top: var(--space-3); border-top: 1px solid var(--dv); }
.pco__activity-lead { display: flex; flex-wrap: wrap; align-items: baseline; column-gap: var(--space-2); margin: var(--space-4) 0; }.pco__activity-lead strong { font-size: var(--font-size-3xl); font-variant-numeric: tabular-nums; letter-spacing: -.03em; }.pco__activity-lead span,.pco__activity-lead small { font-size: var(--font-size-xs); color: var(--t2); }.pco__activity-lead small { margin-left: auto; }
.pco__activity-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); margin: 0; }.pco__activity-grid > div { padding: var(--space-3); border-radius: var(--rs); background: var(--bg-section); }.pco__activity-grid dt { font-size: var(--font-size-xs); color: var(--t2); }.pco__activity-grid dd { margin: var(--space-2) 0 0; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.pco__kv { list-style: none; margin: var(--space-3) 0 0; padding: 0; }.pco__kv li { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; min-height: 45px; font-size: var(--font-size-sm); color: var(--t2); }.pco__kv b { color: var(--t1); font-variant-numeric: tabular-nums; }
.pco__risk-list { list-style: none; margin: var(--space-3) 0 0; padding: 0; }.pco__risk-list li { padding: var(--space-3) 0; border-bottom: 1px solid var(--dv); }.pco__risk-list li:last-child { border: 0; }.pco__risk-list p { margin: var(--space-2) 0; font-size: var(--font-size-sm); color: var(--t2); line-height: 1.7; overflow-wrap: anywhere; }
.pco__timeline { list-style: none; padding: 0; margin: var(--space-4) 0 0; }.pco__timeline li { position: relative; margin-left: 4px; padding: 0 0 var(--space-4) var(--space-4); border-left: 1px solid var(--card-b); }.pco__timeline li::before { content: ''; position: absolute; left: -4px; top: 6px; height: 7px; width: 7px; background: var(--pri); border-radius: 50%; }.pco__timeline li:last-child { padding-bottom: 0; }.pco__timeline strong { font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); }.pco__timeline small { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--space-2); margin-top: var(--space-1); color: var(--t2); font-size: var(--font-size-xs); }
@media (max-width: 1100px) { .pco__welcome,.pco__main-grid { grid-template-columns: minmax(0, 1fr); }.pco__priority { border-left: 0; border-top: 1px solid var(--card-b); }.pco__bottom-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.pco__welcome-main { padding: var(--space-5); }.pco__welcome-main h2 { font-size: var(--font-size-xl); } }
@media (max-width: 650px) { .pco__bottom-grid,.pco__quality-list { grid-template-columns: minmax(0, 1fr); }.pco__priority,.pco__panel,.pco__welcome-main { padding: var(--space-4); }.pco__priority-list li,.pco__school-row { flex-wrap: wrap; }.pco__school-row .pco__school-copy { flex-basis: calc(100% - 60px); }.pco__quality summary span { margin-left: 0; } }
</style>
