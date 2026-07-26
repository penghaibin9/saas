<template>
  <ModulePageShell
    title="岗位实习合规工作台"
    subtitle="当前批次统一上岗、过程与归档口径"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="!batchStore.selectedBatchId"
        type="warning"
        title="请先选择实习批次"
        description="合规指标、列表与下钻均严格使用当前批次。"
      />
      <template v-else>
        <div class="sa-grid sa-grid--metrics">
          <button
            v-for="metric in metrics"
            :key="metric.metricCode"
            type="button"
            class="mp-card metric-card"
            :class="{ 'is-active': selectedFilter === metric.drilldownFilter }"
            @click="selectedFilter = metric.drilldownFilter"
          >
            <span class="mp-note">{{ metric.metricLabel }}</span>
            <strong>{{ metric.count }}</strong>
          </button>
        </div>
        <section class="mp-card">
          <div class="mp-card__head">
            <div>
              <strong>{{ selectedMetric?.metricLabel || '批次学生' }}</strong>
              <p class="mp-note">规则 {{ data.ruleVersion || '-' }} · 评估于 {{ data.evaluatedAt || '-' }}</p>
            </div>
            <AppButton variant="ghost" size="sm" @click="load">刷新</AppButton>
          </div>
          <div class="table-wrap">
            <table class="mp-table">
              <thead><tr><th>学号</th><th>姓名</th><th>班级</th><th>指导教师</th><th>当前状态</th><th>阻断项</th><th>办理入口</th></tr></thead>
              <tbody>
                <tr v-for="row in drilldownRows" :key="row.internshipId">
                  <td>{{ row.studentNo }}</td><td>{{ row.studentName }}</td><td>{{ row.classId || '-' }}</td>
                  <td>{{ row.advisorName || '-' }}</td><td>{{ row.recordStatus }}</td>
                  <td>{{ blockerText(row) }}</td>
                  <td><button class="mp-link" @click="openStudent(row)">进入学生详情</button></td>
                </tr>
                <tr v-if="!drilldownRows.length"><td colspan="7" class="empty-cell">当前口径下暂无学生</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { complianceApi } from '@/modules/internship/api/compliance.api'

export default {
  name: 'InternshipComplianceView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data: () => ({ loading: false, error: '', data: {}, selectedFilter: 'ALL' }),
  computed: {
    batchStore() { return useInternshipBatchStore() },
    metrics() { return this.data.metrics || [] },
    selectedMetric() {
      return this.metrics.find((x) => x.drilldownFilter === this.selectedFilter)
    },
    drilldownRows() {
      return this.data.drilldowns?.[this.selectedFilter] || []
    }
  },
  watch: {
    'batchStore.selectedBatchId': {
      immediate: true,
      handler() { this.load() }
    }
  },
  methods: {
    async load() {
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { this.data = {}; return }
      this.loading = true
      this.error = ''
      const res = await complianceApi.batchStats(batchId)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '合规工作台加载失败'; return }
      this.data = res.data || {}
      if (!this.data.drilldowns?.[this.selectedFilter]) this.selectedFilter = 'ALL'
    },
    blockerText(row) {
      const blockers = row.blockers || []
      return blockers.length ? blockers.map((x) => `${x.label}：${x.reason}`).join('；') : '无'
    },
    openStudent(row) {
      this.$router.push(row.route || `/admin/internship/students/${row.internshipId}`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.metric-card { text-align: left; cursor: pointer; }
.metric-card.is-active { outline: 2px solid var(--color-primary); }
.table-wrap { overflow-x: auto; }
.mp-table { width: 100%; border-collapse: collapse; }
.mp-table th, .mp-table td { padding: 10px; border-bottom: 1px solid var(--border-color); text-align: left; vertical-align: top; }
.empty-cell { text-align: center !important; color: var(--text-tertiary); }
</style>
