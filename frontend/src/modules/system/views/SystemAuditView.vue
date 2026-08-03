<template>
  <ModulePageShell
    title="安全审计证据与完整性"
    subtitle="登录风险 · 高危变更 · 敏感下载 · 权限激活 · 紧急访问 · 审计缺口"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body sav-summary">
            <div class="sav-stat"><span class="sav-stat__num">{{ overview.loginRiskCount }}</span><span class="sav-stat__label">登录风险</span></div>
            <div class="sav-stat"><span class="sav-stat__num">{{ overview.highRiskChangeCount }}</span><span class="sav-stat__label">高危变更</span></div>
            <div class="sav-stat"><span class="sav-stat__num">{{ overview.sensitiveDownloadCount }}</span><span class="sav-stat__label">敏感下载</span></div>
            <div class="sav-stat"><span class="sav-stat__num">{{ overview.permissionActivationCount }}</span><span class="sav-stat__label">权限激活</span></div>
            <div class="sav-stat"><span class="sav-stat__num">{{ overview.emergencyAccessCount }}</span><span class="sav-stat__label">紧急访问</span></div>
            <div class="sav-stat" :class="{ 'sav-stat--warn': overview.auditGapCount }"><span class="sav-stat__num">{{ overview.auditGapCount }}</span><span class="sav-stat__label">审计缺口</span></div>
          </div>
          <div v-if="(overview.auditGaps || []).length" class="mp-card__body">
            <p v-for="g in overview.auditGaps" :key="g.auditId" class="sav-warn">
              {{ g.action }} · 缺失字段：{{ g.missing.join('、') }}
            </p>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">证据查询</span>
            <span class="mp-note">高危动作自动做完整性判定</span>
          </header>
          <div class="mp-card__body sav-filters">
            <input v-model.trim="filterAction" class="sav-input" placeholder="动作码，如 PLATFORM_CHANGE_ROLLBACK" @keyup.enter="load" />
            <button class="mp-link" @click="load">查询</button>
            <button class="mp-link" @click="askCreatePack">登记证据包导出</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!evidence.length" title="暂无记录" description="" />
            <DataTable v-else :columns="evidenceColumns" :rows="evidence" row-key="auditId">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ row.action }}</div>
                <div class="mp-cell-sub">{{ row.resource }} · trace {{ row.requestId }}</div>
              </template>
              <template #cell-actor="{ row }">{{ row.actorName || row.actorId || '—' }}</template>
              <template #cell-result="{ row }">
                <StatusTag :type="row.result === 'SUCCESS' ? 'success' : 'danger'" :label="row.result" dot />
              </template>
            </DataTable>
          </div>
        </section>

        <section v-if="packs.length" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">已登记的证据包任务</span></header>
          <div class="mp-card__body">
            <ul class="sav-list">
              <li v-for="p in packs" :key="p.jobId">
                任务 {{ p.jobId }} · 范围：{{ p.scopeSnapshot.actionPrefixAllowlist ? p.scopeSnapshot.actionPrefixAllowlist.join('、') : '不受限（全量审计权限）' }}
              </li>
            </ul>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="dialogOpen"
      type="info"
      title="登记证据包导出"
      :message="`按当前查询条件（动作：${filterAction || '全部'}）登记一次证据包导出；范围会按你当前的权限自动收敛，不会包含你查看权限之外的内容。`"
      confirm-text="登记"
      :submitting="submitting"
      @confirm="submitCreatePack"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemAuditView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      evidence: [],
      packs: [],
      filterAction: '',
      dialogOpen: false,
      submitting: false,
      evidenceColumns: [
        { key: 'scope', title: '动作' },
        { key: 'actor', title: '操作人' },
        { key: 'result', title: '结果' },
        { key: 'occurredAt', title: '时间' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    askCreatePack() {
      this.dialogOpen = true
    },
    async submitCreatePack() {
      this.submitting = true
      const res = await systemApi.createAuditEvidencePack({ action: this.filterAction || undefined })
      this.submitting = false
      if (res.code === 0) {
        toast.success('证据包任务已登记')
        this.dialogOpen = false
        this.packs.unshift(res.data)
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, evidence] = await Promise.all([
        systemApi.getAuditOverview(),
        systemApi.getAuditEvidence({ action: this.filterAction || undefined, pageSize: 20 })
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (evidence.code === 0) this.evidence = evidence.data.items || []
      else if (!this.error) this.error = evidence.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sav-summary { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.sav-stat {
  min-width: 120px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}
.sav-stat--warn { border-color: var(--color-danger); }
.sav-stat__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.sav-stat__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.sav-warn { color: var(--color-danger); margin: 2px 0; }
.sav-filters { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.sav-input { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 220px; }
.sav-list { list-style: none; padding: 0; margin: 0; }
.sav-list li { padding: 4px 0; font-size: var(--font-size-sm); border-bottom: 1px solid var(--border-light); }
</style>
