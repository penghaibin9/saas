<template>
  <ModulePageShell
    title="问题预警 · 毕设归档 · 毕设统计"
    subtitle="风险扫描与处置闭环 / 材料归档核验 / 跨模块统计看板"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-tabs">
      <button class="gp-tabs__item" :class="{ 'is-active': tab === 'risk' }" @click="switchTab('risk')">问题预警</button>
      <button class="gp-tabs__item" :class="{ 'is-active': tab === 'archive' }" @click="switchTab('archive')">毕设归档</button>
      <button class="gp-tabs__item" :class="{ 'is-active': tab === 'stats' }" @click="switchTab('stats')">毕设统计</button>
    </div>

    <!-- 问题预警 -->
    <div v-if="tab === 'risk'" class="mp-stack">
      <div class="ie-actions" style="justify-content: flex-start"><button class="mp-btn mp-btn--primary" @click="doScan">扫描生成风险项</button></div>
      <AdvancedFilter v-model="riskFilters" :fields="riskFilterFields" @search="loadRisks" @reset="resetRiskFilters" />
      <LoadingState v-if="riskLoading" />
      <EmptyState v-else-if="!riskRows.length" title="暂无风险记录" description="点「扫描生成风险项」按当前数据生成" />
      <DataTable v-else :columns="riskColumns" :rows="riskRows" row-key="id" :pagination="{ page: riskPage, pageSize: riskPageSize, total: riskTotal }" @page-change="p => { riskPage = p; loadRisks() }">
        <template #cell-risk="{ row }">
          <div class="mp-cell-main">{{ row.riskName }}（{{ row.riskCode }}）</div>
          <div class="mp-cell-sub">{{ row.studentName }} · {{ row.studentNo }} · {{ row.advisorName || '未分配导师' }}</div>
        </template>
        <template #cell-level="{ row }"><StatusTag :type="row.level === 'CRITICAL' || row.level === 'HIGH' ? 'danger' : 'warning'" :label="row.level" dot /></template>
        <template #cell-status="{ row }"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'OPEN'" class="mp-link" @click="doAccept(row)">受理</button>
          <button v-if="row.status === 'PROCESSING'" class="mp-link" @click="doProcess(row)">记录处理</button>
          <button v-if="row.status === 'PROCESSING'" class="mp-link" @click="doClose(row)">关闭</button>
        </template>
      </DataTable>
    </div>

    <!-- 毕设归档 -->
    <div v-if="tab === 'archive'" class="mp-stack">
      <div class="ie-actions" style="justify-content: flex-start">
        <button class="mp-btn mp-btn--primary" @click="doBatchGenerate">批量生成提交</button>
        <button class="mp-btn" @click="doBatchFile">一键核验备案</button>
        <AppExportButton :export-fn="exportArchivesFn">导出台账</AppExportButton>
      </div>
      <AdvancedFilter v-model="archiveFilters" :fields="archiveFilterFields" @search="loadArchives" @reset="resetArchiveFilters" />
      <LoadingState v-if="archiveLoading" />
      <EmptyState v-else-if="!archiveRows.length" title="暂无归档记录" />
      <DataTable v-else :columns="archiveColumns" :rows="archiveRows" row-key="id" :pagination="{ page: archivePage, pageSize: archivePageSize, total: archiveTotal }" @page-change="p => { archivePage = p; loadArchives() }">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }} · 缺 {{ row.missingItems.length }} 项</div>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button v-if="['NOT_GENERATED', 'REJECTED'].includes(row.status)" class="mp-link" @click="doGenerate(row)">生成清单</button>
          <button v-if="row.status === 'PENDING_SUBMIT' && !row.missingItems.length" class="mp-link" @click="doSubmit(row)">提交</button>
          <button v-if="row.status === 'SUBMITTED'" class="mp-link" @click="doFile(row)">核验归档</button>
          <button v-if="row.status === 'SUBMITTED'" class="mp-link mp-link--danger" @click="doReject(row)">驳回</button>
        </template>
      </DataTable>
    </div>

    <!-- 毕设统计 -->
    <div v-if="tab === 'stats'" class="mp-stack">
      <AppDateRangePicker
        v-model="statsRange"
        label="统计时间范围"
        mode="filter"
        empty-label="全部时间"
        memory-key="graduation.riskArchive.statsRange"
        @change="onStatsRangeChange"
      />
      <LoadingState v-if="statsLoading" />
      <template v-else-if="overview">
        <div class="gs-cards">
          <div class="gs-card"><div class="gs-card__label">毕设学生</div><div class="gs-card__value">{{ overview.studentTotal }}</div></div>
          <div class="gs-card"><div class="gs-card__label">导师已认证</div><div class="gs-card__value">{{ overview.mentor.qualifiedCount }}</div></div>
          <div class="gs-card"><div class="gs-card__label">未分配导师</div><div class="gs-card__value">{{ overview.mentor.unassignedStudents }}</div></div>
          <div class="gs-card"><div class="gs-card__label">开放风险</div><div class="gs-card__value">{{ overview.risk.openCount }}</div></div>
          <div class="gs-card"><div class="gs-card__label">归档率</div><div class="gs-card__value">{{ overview.archive.archiveRate }}%</div></div>
          <div class="gs-card"><div class="gs-card__label">成绩已发布均分</div><div class="gs-card__value">{{ overview.grade.publishedAvg }}</div></div>
        </div>
        <div class="gm-section-title" style="margin-top: var(--space-4)">阶段分布</div>
        <ul class="gs-stage-list">
          <li v-for="s in overview.byStage" :key="s.stage">{{ s.label }}：{{ s.count }}</li>
        </ul>
        <div class="gm-section-title" style="margin-top: var(--space-4)">学院/专业对比</div>
        <DataTable :columns="collegeColumns" :rows="collegeRows" row-key="name" />
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 问题预警+毕设归档+毕设统计（/admin/graduation/risk-archive）：扫描处置闭环 + 材料核验归档 + 跨模块统计看板。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton } from '@/components/common'
import { AppDateRangePicker } from '@/components/common/date'
import { graduationRiskArchiveApi } from '@/modules/graduation/api/graduation-risk-archive.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationRiskArchiveView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, EmptyState, AppConfirmDialog, AppDateRangePicker, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'risk',
      riskFilters: { status: '', level: '', dateStart: '', dateEnd: '' }, riskRows: [], riskTotal: 0, riskPage: 1, riskPageSize: 10, riskLoading: true,
      archiveFilters: { keyword: '', status: '', dateStart: '', dateEnd: '' }, archiveRows: [], archiveTotal: 0, archivePage: 1, archivePageSize: 10, archiveLoading: true,
      statsRange: { start: '', end: '' },
      overview: null, collegeRows: [], statsLoading: true,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      riskColumns: [{ key: 'risk', title: '风险 / 学生' }, { key: 'level', title: '等级' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '160px' }],
      archiveColumns: [{ key: 'student', title: '学生' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '200px' }],
      collegeColumns: [{ key: 'name', title: '学院/专业' }, { key: 'total', title: '学生数' }, { key: 'archived', title: '已归档' }, { key: 'highRisk', title: '高风险' }]
    }
  },
  computed: {
    riskFilterFields() {
      return [
        { key: 'status', label: '状态', type: 'select', options: [{ value: 'OPEN', label: '待受理' }, { value: 'PROCESSING', label: '处理中' }, { value: 'CLOSED', label: '已关闭' }] },
        { key: 'level', label: '等级', type: 'select', options: [{ value: 'LOW', label: 'LOW' }, { value: 'MEDIUM', label: 'MEDIUM' }, { value: 'HIGH', label: 'HIGH' }, { value: 'CRITICAL', label: 'CRITICAL' }] },
        {
          key: 'date', label: '预警时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.risk.dateRange', emptyLabel: '全部时间'
        }
      ]
    },
    archiveFilterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名' },
        { key: 'status', label: '状态', type: 'select', options: [{ value: 'NOT_GENERATED', label: '待生成' }, { value: 'PENDING_SUBMIT', label: '待提交' }, { value: 'SUBMITTED', label: '已提交' }, { value: 'FILED', label: '已备案' }, { value: 'REJECTED', label: '已驳回' }] },
        {
          key: 'date', label: '归档时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.archive.dateRange', emptyLabel: '全部时间'
        }
      ]
    }
  },
  created() {
    const p = this.$route.query.panel
    if (['risk', 'archive', 'stats'].includes(p)) this.tab = p
    this.loadRisks(); this.loadArchives(); this.loadStats()
  },
  methods: {
    switchTab(t) { this.tab = t },
    async doScan() {
      const res = await graduationRiskArchiveApi.scanRisks()
      if (res.code === 0) { toast.success(res.message || '扫描完成'); this.loadRisks() } else toast.error(res.message)
    },
    async loadRisks() {
      this.riskLoading = true
      const res = await graduationRiskArchiveApi.getRiskList({ ...this.riskFilters, page: this.riskPage, pageSize: this.riskPageSize })
      if (res.code === 0) { this.riskRows = res.data.list; this.riskTotal = res.data.total }
      this.riskLoading = false
    },
    resetRiskFilters() { this.riskFilters = { status: '', level: '', dateStart: '', dateEnd: '' }; this.riskPage = 1; this.loadRisks() },
    doAccept(row) {
      this.confirm = { visible: true, title: '受理风险', message: `确认受理「${row.riskName}」（${row.studentName}）？`, type: 'primary', confirmText: '受理', requireReason: false, action: 'accept', row }
    },
    doProcess(row) {
      this.confirm = { visible: true, title: '记录处理', message: '', type: 'primary', confirmText: '提交', requireReason: true, reasonLabel: '处理说明', action: 'process', row }
    },
    doClose(row) {
      this.confirm = { visible: true, title: '关闭风险', message: '', type: 'danger', confirmText: '确认关闭', requireReason: true, reasonLabel: '关闭原因', action: 'close', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      let res
      if (action === 'accept') res = await graduationRiskArchiveApi.acceptRisk(row.id)
      else if (action === 'process') res = await graduationRiskArchiveApi.processRisk(row.id, reason || '')
      else if (action === 'close') res = await graduationRiskArchiveApi.closeRisk(row.id, reason || '')
      else if (action === 'reject-archive') res = await graduationRiskArchiveApi.rejectArchive(row.gdStudentId, reason || '')
      if (res && res.code === 0) {
        toast.success('已更新'); this.confirm.visible = false
        if (action === 'reject-archive') this.loadArchives(); else this.loadRisks()
      } else if (res) toast.error(res.message)
    },
    async loadArchives() {
      this.archiveLoading = true
      const res = await graduationRiskArchiveApi.getArchiveList({ ...this.archiveFilters, page: this.archivePage, pageSize: this.archivePageSize })
      if (res.code === 0) { this.archiveRows = res.data.list; this.archiveTotal = res.data.total }
      this.archiveLoading = false
    },
    resetArchiveFilters() { this.archiveFilters = { keyword: '', status: '', dateStart: '', dateEnd: '' }; this.archivePage = 1; this.loadArchives() },
    onStatsRangeChange() { this.loadStats() },
    async doGenerate(row) {
      const res = await graduationRiskArchiveApi.generateArchive(row.gdStudentId)
      if (res.code === 0) { toast.success('已生成'); this.loadArchives() } else toast.error(res.message)
    },
    async doSubmit(row) {
      const res = await graduationRiskArchiveApi.submitArchive(row.gdStudentId)
      if (res.code === 0) { toast.success('已提交'); this.loadArchives() } else toast.error(res.message)
    },
    async doFile(row) {
      const res = await graduationRiskArchiveApi.fileArchive(row.gdStudentId)
      if (res.code === 0) { toast.success('已归档'); this.loadArchives() } else toast.error(res.message)
    },
    doReject(row) {
      this.confirm = { visible: true, title: '驳回归档', message: '', type: 'danger', confirmText: '确认驳回', requireReason: true, reasonLabel: '驳回原因', action: 'reject-archive', row }
    },
    exportArchivesFn() {
      return graduationRiskArchiveApi.exportArchives({ ...this.archiveFilters })
    },
    async doBatchGenerate() {
      const res = await graduationRiskArchiveApi.batchGenerateArchive()
      if (res.code === 0) { toast.success(`已提交 ${res.data.submitted}，缺材料跳过 ${res.data.skipped}`); this.loadArchives() }
      else toast.error(res.message)
    },
    async doBatchFile() {
      const res = await graduationRiskArchiveApi.batchFileArchive()
      if (res.code === 0) { toast.success(`已批量备案 ${res.data.filed} 份`); this.loadArchives() }
      else toast.error(res.message)
    },
    async loadStats() {
      this.statsLoading = true
      const [o, c] = await Promise.all([graduationRiskArchiveApi.getOverviewStats(), graduationRiskArchiveApi.getCollegeComparison()])
      this.overview = o.code === 0 ? o.data : null
      this.collegeRows = c.code === 0 ? c.data : []
      this.statsLoading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link--danger { color: var(--danger, #dc2626); }
.gp-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gp-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gp-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gs-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.gs-card { border: 1px solid var(--line, #e2e8f0); border-radius: 10px; padding: 12px; }
.gs-card__label { font-size: 12px; color: var(--t3, #64748b); }
.gs-card__value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.gm-section-title { font-size: 13px; font-weight: 600; }
.gs-stage-list { list-style: none; margin: 8px 0; padding: 0; display: flex; gap: var(--space-4); flex-wrap: wrap; font-size: 13px; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-bottom: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
</style>
