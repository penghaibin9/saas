<template>
  <ModulePageShell
    title="风险异常处置"
    :subtitle="'发现并处理学生实习中的安全、失联、打卡、协议和企业风险 · 风险来源统一挂 INT-R 编码 · 关闭风险需填写原因并留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出风险名单</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div class="mp-stack">
      <nav class="ir-focus" aria-label="风险处置视图">
        <span class="ir-focus__title">风险聚焦</span>
        <button
          v-for="focus in focusViews"
          :key="focus.key"
          type="button"
          class="ir-focus__item"
          :class="{ 'is-active': activePanel === focus.key }"
          @click="goPanel(focus.key)"
        >{{ focus.label }}</button>
      </nav>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前数据范围内暂无风险学生" description="系统预警（INT-R01~R17）命中后会自动生成风险记录" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-source="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.source }}</div>
          <div class="mp-cell-sub">{{ row.sourceDetail }}</div>
        </template>
        <template #cell-level="{ row }">
          <AppRiskTag :level="row.level" />
        </template>
        <template #cell-deadline="{ row }">
          <span :style="isUrgent(row.deadline) ? 'color: var(--danger-600); font-weight: 500' : ''">{{ row.deadline }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/students/' + row.internId)">查看学生</button>
          <button class="mp-link" style="margin-left: var(--space-2)" @click="remind(row)">提醒</button>
        </template>
      </DataTable>

      <p class="mp-note">跟进 / 升级 / 关闭风险入口在学生实习详情的风险页签内；关闭为审慎操作：原因必填 + 二次确认 + 永久留痕。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 风险学生列表（/admin/internship/risks）：风险等级 / 跟进状态 / 责任人 / 处理期限。 */
import {
  ModulePageShell, AdvancedFilter, DataTable,
  LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppStatusTag, AppRiskTag, AppExportButton } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { riskApi } from '@/modules/internship/api/leave-risk.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ level: '', status: '', riskCode: '' })
const PANEL_PRESETS = {
  board: () => EMPTY_FILTERS(),
  'no-position': () => ({ level: '', status: '', riskCode: 'INT-R02' }),
  'no-checkin': () => ({ level: '', status: '', riskCode: 'INT-R07' }),
  'report-overdue': () => ({ level: '', status: '', riskCode: 'INT-R10' }),
  'leave-post': () => ({ level: '', status: '', riskCode: 'INT-R06' })
}

export default {
  name: 'InternshipRiskView',
  components: { ModulePageShell, AdvancedFilter, DataTable, AppStatusTag, AppRiskTag, AppExportButton,
    LoadingState, ErrorState, EmptyState, ModuleSummaryStrip },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(), activePanel: 'board',
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'source', title: '风险来源' },
        { key: 'level', title: '等级' },
        { key: 'owner', title: '责任人' },
        { key: 'deadline', title: '处理期限' },
        { key: 'lastFollow', title: '最近跟进' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '140px' }
      ]
    }
  },
  computed: {
    focusViews() {
      return [
        { key: 'board', label: '全部风险' },
        { key: 'no-position', label: '未落岗' },
        { key: 'no-checkin', label: '打卡异常' },
        { key: 'report-overdue', label: '报告逾期' },
        { key: 'leave-post', label: '请假未返岗' }
      ]
    },
    filterFields() {
      return [
        { key: 'level', label: '风险等级', type: 'select', options: this.ctx.statusOptions.riskLevel },
        {
          key: 'status', label: '跟进状态', type: 'select',
          options: [
            { value: 'PENDING_HANDLE', label: '待处理' },
            { value: 'PROCESSING', label: '跟进中' }
          ]
        }
      ]
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      return [{ label: '风险学生', value: this.pagination.total, tone: this.pagination.total ? 'warn' : undefined }]
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'board').toString())
      }
    }
  },
  methods: {
    exportFn() { return riskApi.exportRisks({ ...this.filters }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.board
      this.activePanel = PANEL_PRESETS[panel] ? panel : 'board'
      this.filters = { ...preset() }
      this.pagination.page = 1
      this.load()
    },
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
    },
    isUrgent(d) {
      return d && d <= '07-05'
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    remind(row) {
      riskApi.remind(row.id).then((res) => {
        if (res.code === 0) {
          const owner = (res.data && res.data.ownerName) || row.owner || '责任人'
          toast.success(`已提醒 ${owner} 跟进 ${row.studentName} 的风险记录，已留痕`)
        } else {
          toast.error(res.message || '提醒失败')
        }
      })
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getRiskStudents({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ir-focus { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--danger-100); border-radius: 12px; background: linear-gradient(100deg, var(--danger-50), var(--card) 58%); box-shadow: var(--s1); overflow-x: auto; }
.ir-focus__title { flex: 0 0 auto; padding: 0 8px 0 2px; color: var(--danger-600); font-size: 12px; font-weight: var(--font-weight-semibold); }
.ir-focus__item { flex: 0 0 auto; padding: 6px 11px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2); cursor: pointer; font-size: 12px; transition: .16s ease; }
.ir-focus__item:hover { color: var(--danger-600); background: var(--danger-50); }
.ir-focus__item.is-active { border-color: var(--danger-100); background: var(--card); color: var(--danger-600); box-shadow: 0 2px 5px rgba(127, 29, 29, .08); font-weight: var(--font-weight-semibold); }
</style>
