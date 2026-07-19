<template>
  <ModulePageShell
    title="租户数据迁移进度"
    subtitle="自动交付 · 各学校老系统数据迁移的批次、行数与已完成域（只读聚合，不含业务明细）"
    :role-name="ctx?.currentRole?.roleName || ''"
    :data-scope-name="ctx?.dataScope?.scopeName || ''"
  >
    <div class="mp-stack">
      <ModuleHero
        title="迁移交付看板"
        subtitle="学校侧在「系统管理 → 数据迁移」执行导入；平台侧此处跟踪各租户交付进度，指导实施排期。"
        :stats="heroStats"
      />

      <section class="mp-card">
        <header class="mp-card__head">
          <span class="mp-card__title">各租户迁移进度</span>
          <AppButton size="sm" variant="ghost" :loading="loading" @click="reload">刷新</AppButton>
        </header>
        <div class="mp-card__body">
          <table v-if="rows.length" class="ptm-table">
            <thead>
              <tr>
                <th>学校（租户）</th><th>迁移批次</th><th>成功批次</th>
                <th>已导入行数</th><th>已完成域</th><th>最近活动</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.tenantId">
                <td>{{ r.tenantName }}</td>
                <td>{{ r.batches }}</td>
                <td>{{ r.successBatches }}</td>
                <td>{{ r.importedRows }}</td>
                <td>
                  <StatusTag
                    :type="r.domainsDone.length >= r.domainsTotal ? 'success' : 'info'"
                    :label="`${r.domainsDone.length}/${r.domainsTotal}`"
                  />
                  <span class="ptm-domains">{{ r.domainsDone.join('、') || '—' }}</span>
                </td>
                <td>{{ r.lastActivityAt || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="ptm-empty">
            暂无租户发起数据迁移。学校侧入口：系统管理 → 数据迁移 → 老系统数据迁移。
          </div>
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 平台运营 · 租户数据迁移进度（只读聚合）。
 * 后端：GET /api/v1/platform/migration/overview（platform.tenant.migration.view，
 * 仅平台角色；返回批次/行数/已完成域聚合，不返回任何学校业务数据）。
 */
import { ModulePageShell, ModuleHero, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformTenantMigrationView',
  components: { ModulePageShell, ModuleHero, StatusTag, AppButton },
  props: { ctx: { type: Object, default: null } },
  data() {
    return { loading: false, rows: [] }
  },
  computed: {
    heroStats() {
      const total = this.rows.length
      const done = this.rows.filter((r) => r.domainsDone.length >= r.domainsTotal).length
      const rowsSum = this.rows.reduce((s, r) => s + (r.importedRows || 0), 0)
      return [
        { label: '迁移中学校', value: String(total), tone: 'info' },
        { label: '全域完成', value: String(done), tone: 'success' },
        { label: '累计导入行数', value: String(rowsSum), tone: 'primary' }
      ]
    }
  },
  created() {
    this.reload()
  },
  methods: {
    async reload() {
      this.loading = true
      try {
        const res = await platformControlApi.getTenantMigrationProgress()
        if (res.code === 0) this.rows = res.data || []
        else toast.error(res.message || '迁移进度加载失败')
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ptm-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.ptm-table th, .ptm-table td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-light); }
.ptm-table th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); }
.ptm-domains { margin-left: var(--space-2); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.ptm-empty { padding: var(--space-5); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
</style>
