<template>
  <ModulePageShell
    title="平台总控台"
    subtitle="全平台经营总览 · 数据实时来自后端"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <LoadingState v-if="loading" text="正在加载平台总览…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pco__grid">
        <AppCard v-for="s in statCards" :key="s.label" class="pco__stat">
          <div class="pco__stat-num">{{ s.value }}</div>
          <div class="pco__stat-label">{{ s.label }}</div>
          <div v-if="s.sub" class="pco__stat-sub">{{ s.sub }}</div>
        </AppCard>
      </div>
      <AppCard v-if="ov.operationalRisks && ov.operationalRisks.length" class="pco__risks">
        <AppSectionHeader title="运行风险（服务目录 / 事件 / 变更）" />
        <ul class="pco__list">
          <li v-for="(r, i) in ov.operationalRisks" :key="i">
            <span class="pco__list-name">{{ r.text }}</span>
            <StatusTag :type="r.level === 'HIGH' ? 'danger' : 'warning'" :label="r.sourceCard" />
          </li>
        </ul>
      </AppCard>
      <div class="pco__cols">
        <AppCard class="pco__panel">
          <AppSectionHeader title="今日动态" />
          <ul class="pco__kv">
            <li><span>今日登录</span><b>{{ ov.todayLogin }}</b></li>
            <li><span>近 7 天登录</span><b>{{ ov.weekLogin }}</b></li>
            <li><span>今日导入 / 导出</span><b>{{ ov.todayImport }} / {{ ov.todayExport }}</b></li>
            <li><span>今日上传</span><b>{{ ov.todayUpload }}</b></li>
            <li><span>今日审批动作</span><b>{{ ov.todayApproval }}</b></li>
            <li><span>待办 / 待审批（全平台）</span><b>{{ ov.todoPending }} / {{ ov.approvalPending }}</b></li>
          </ul>
        </AppCard>
        <AppCard class="pco__panel">
          <AppSectionHeader title="30 天内到期租户" />
          <EmptyState v-if="!ov.expiringTenants.length" text="暂无临期租户" compact />
          <ul v-else class="pco__list">
            <li v-for="t in ov.expiringTenants" :key="t.tenantName">
              <span class="pco__list-name">{{ t.tenantName }}</span>
              <StatusTag type="warning" :label="`剩 ${t.daysLeft} 天`" />
            </li>
          </ul>
          <AppSectionHeader title="异常租户" class="pco__gap" />
          <EmptyState v-if="!ov.abnormalTenants.length" text="暂无异常租户" compact />
          <ul v-else class="pco__list">
            <li v-for="t in ov.abnormalTenants" :key="t.tenantName">
              <span class="pco__list-name">{{ t.tenantName }}</span>
              <StatusTag :type="t.status === 'expired' ? 'danger' : 'default'" :label="t.status === 'expired' ? '已到期' : '已停用'" />
            </li>
          </ul>
        </AppCard>
        <AppCard class="pco__panel">
          <AppSectionHeader title="系统健康" />
          <ul class="pco__kv">
            <li><span>服务状态</span><StatusTag :type="ov.systemHealth === 'UP' ? 'success' : 'danger'" :label="ov.systemHealth" /></li>
            <li><span>数据库</span><StatusTag :type="ov.dbStatus === 'OK' ? 'success' : 'danger'" :label="ov.dbStatus" /></li>
            <li><span>文件目录</span><StatusTag :type="ov.fileDirStatus === 'OK' ? 'success' : 'warning'" :label="ov.fileDirStatus" /></li>
            <li><span>存储占用</span><b>{{ ov.storageUsedMb }} MB</b></li>
          </ul>
          <AppSectionHeader title="最近平台审计" class="pco__gap" />
          <EmptyState v-if="!ov.recentAudits || !ov.recentAudits.length" text="暂无平台审计记录" compact />
          <ul v-else class="pco__list">
            <li v-for="(a, i) in ov.recentAudits" :key="i">
              <span class="pco__list-name">{{ a.action }} · {{ a.operator }}</span>
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

export default {
  name: 'PlatformControlOverview',
  components: { AppCard, AppSectionHeader, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  props: {
    ctx: { type: Object, required: true }
  },
  data() {
    return { loading: true, ov: null, error: '' }
  },
  computed: {
    statCards() {
      const o = this.ov
      return [
        { label: '租户总数', value: o.tenantTotal, sub: `正式 ${o.tenantActive} · 试用 ${o.tenantTrial}` },
        { label: '已到期 / 已停用', value: `${o.tenantExpired} / ${o.tenantDisabled}`, sub: '异常需跟进' },
        { label: '学生总数', value: o.studentTotal, sub: '全平台在库' },
        { label: '账号总数', value: o.userTotal, sub: '全平台用户' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      this.ov = null
      const res = await platformControlApi.getOverview()
      this.loading = false
      if (res.code === 0) this.ov = res.data
      else this.error = res.message || '平台总览加载失败'
    }
  }
}
</script>

<style scoped>
.pco__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}
.pco__stat {
  padding: var(--space-4);
}
.pco__stat-num {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.pco__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pco__stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.pco__risks {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.pco__cols {
  margin-top: var(--space-3);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-3);
}
.pco__panel {
  padding: var(--space-4);
}
.pco__gap {
  margin-top: var(--space-4);
}
.pco__kv {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.pco__kv li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pco__kv b {
  color: var(--t1);
}
.pco__list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.pco__list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.pco__list-name {
  font-size: var(--font-size-sm);
  color: var(--t2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pco__list-time {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
