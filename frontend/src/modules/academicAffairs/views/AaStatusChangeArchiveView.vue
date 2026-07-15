<template>
  <ModulePageShell
    title="异动归档"
    subtitle="学籍异动归档就绪度：类型分布 + 在途未终结件清单（在途件会阻塞学期归档，需先处理完毕）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="load">刷新</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <div class="aa-stats">
        <div class="aa-stat"><b>{{ stats.total }}</b><span>累计异动</span></div>
        <div class="aa-stat aa-stat--success"><b>{{ stats.effective }}</b><span>已生效（可归档）</span></div>
        <div class="aa-stat" :class="{ 'aa-stat--danger': pendingRows.length }"><b>{{ stats.pending }}</b><span>在途未终结（阻塞归档）</span></div>
        <div class="aa-stat aa-stat--danger"><b>{{ stats.rejected }}</b><span>已驳回</span></div>
      </div>

      <AppSectionCard title="按异动类型分布">
        <EmptyState v-if="!stats.byType.length" title="暂无数据" />
        <table v-else class="aa-table">
          <thead><tr><th>类型</th><th>数量</th></tr></thead>
          <tbody>
            <tr v-for="g in stats.byType" :key="g.key">
              <td>{{ g.label }}</td>
              <td>{{ g.count }}</td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard title="在途未终结件清单（归档缺项）">
        <EmptyState v-if="!pendingRows.length" title="当前无在途异动" description="全部异动均已终结（生效/驳回/退回），可正常归档" />
        <table v-else class="aa-table">
          <thead><tr><th>学生</th><th>异动类型</th><th>当前节点</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in pendingRows" :key="row.changeId">
              <td>{{ row.realName || '—' }}</td>
              <td>{{ row.changeTypeLabel }}</td>
              <td>{{ nodeLabel(row.currentNode) }}</td>
              <td><StatusTag :type="statusColor(row.status)" :label="statusLabel(row.status)" dot /></td>
              <td><button class="mp-link" @click="goDetail(row)">跳转处理</button></td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard title="说明">
        <p class="aa-note">
          本页统计范围与「异动台账/审批」一致（按当前身份数据范围过滤）；不区分学期——学籍异动记录暂无可靠的学期归属
          字段回填（term_code 现状未被任何写入口回填，仅作已知限制如实说明，不在此虚构学期筛选）。
          已生效异动的正式归档材料（含水印导出）请见
          <router-link to="/admin/academic-affairs/archive/export">教务归档 → 归档导出</router-link>
          （异动流水域 STATUS_CHANGE）。
        </p>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 异动归档（学籍异动三级模块续工·第三轮补缺，/admin/academic-affairs/status-changes/archive）。
 *
 * 参照教务归档模块（aa-archive）同类归档模式，但完全复用「学籍异动」既有只读端点组合而成，
 * 不新增后端接口：GET /status-changes/stats（类型/状态聚合，含在途总数）+
 * GET /status-changes?status=SUBMITTED|IN_REVIEW（在途件清单，两次调用前端合并）。
 * 正式归档批次/完整性检查/水印导出仍是教务归档模块（aa-archive）的职责，STATUS_CHANGE 域
 * 已是其 9 数据域之一（本页不重复造归档批次/导出，只做「学籍异动」自身的在途监控视图）。
 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, statusColor } from '@/modules/academicAffairs/constants/status-change'

export default {
  name: 'AaStatusChangeArchiveView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      stats: { total: 0, pending: 0, effective: 0, rejected: 0, byType: [], byStatus: [], pendingByNode: [] },
      pendingRows: []
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    statusColor,
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    goDetail(row) { this.$router.push(`/admin/academic-affairs/status-changes/${row.changeId}`) },
    async load() {
      this.loading = true
      this.error = ''
      const [statsRes, submittedRes, inReviewRes] = await Promise.all([
        academicAffairsApi.getStatusChangeStats(),
        academicAffairsApi.getStatusChanges({ status: 'SUBMITTED', pageSize: 200 }),
        academicAffairsApi.getStatusChanges({ status: 'IN_REVIEW', pageSize: 200 })
      ])
      if (statsRes.code !== 0) {
        this.error = statsRes.message
        this.loading = false
        return
      }
      this.stats = statsRes.data
      const submitted = submittedRes.code === 0 ? submittedRes.data.list : []
      const inReview = inReviewRes.code === 0 ? inReviewRes.data.list : []
      this.pendingRows = [...submitted, ...inReview]
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-stats { display: flex; gap: var(--space-3, 12px); flex-wrap: wrap; }
.aa-stat { display: flex; flex-direction: column; align-items: center; min-width: 96px; padding: 12px 18px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; }
.aa-stat b { font-size: 22px; color: var(--primary-600, #2563eb); }
.aa-stat span { font-size: 12px; color: var(--text-500, #646a73); margin-top: 4px; }
.aa-stat--success b { color: var(--success-600, #16a34a); }
.aa-stat--danger b { color: var(--danger-600, #dc2626); }
.aa-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-table th, .aa-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.aa-table th { color: var(--text-500, #646a73); font-weight: 500; }
.aa-note { font-size: 13px; color: var(--text-600, #4e5969); line-height: 1.7; margin: 0; }
</style>
