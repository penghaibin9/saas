<template>
  <ModulePageShell
    title="问题预警 · 毕设归档 · 毕设统计"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-tabs">
      <button v-if="canRiskView" class="gp-tabs__item" :class="{ 'is-active': tab === 'risk' }" @click="switchTab('risk')">问题预警</button>
      <button v-if="canArchiveView" class="gp-tabs__item" :class="{ 'is-active': tab === 'archive' }" @click="switchTab('archive')">毕设归档</button>
      <button v-if="canStatsView" class="gp-tabs__item" :class="{ 'is-active': tab === 'stats' }" @click="switchTab('stats')">毕设统计</button>
    </div>

    <aside v-if="actionReceipt" class="ra-receipt" :class="{ 'is-unknown': actionReceipt.unknown }" role="status">
      <div><strong>{{ actionReceipt.title }}</strong><span>{{ actionReceipt.result }}</span><small>{{ actionReceipt.next }}</small></div>
      <button v-if="actionReceipt.unknown" type="button" @click="verifyUnknownResult">刷新台账核对</button>
      <button v-else type="button" @click="actionReceipt = null">关闭</button>
    </aside>

    <!-- 问题预警：连续双栏处置 -->
    <div v-if="tab === 'risk' && canRiskView" class="mp-stack">
      <div v-if="hasBatch" class="rk-scan-bar">
        <div class="rk-scan-bar__meta">
          <span>当前批次：{{ batchStore.selectedBatchName || batchStore.selectedBatchId }}</span>
          <span v-if="lastScanAt">上次扫描：{{ formatDateTime(lastScanAt) }}</span>
          <span v-else>尚未扫描</span>
          <span v-if="lastScanStats">扫描 {{ lastScanStats.scannedStudents || 0 }} 人 · 新增 {{ lastScanStats.newCasesCreated || 0 }} · 重开 {{ lastScanStats.reopenedCases || 0 }} · 耗时 {{ lastScanStats.elapsedMs || '—' }}ms</span>
        </div>
        <button v-if="canRiskScan" class="mp-btn mp-btn--primary" @click="doScan">扫描生成风险项</button>
      </div>
      <AdvancedFilter v-if="hasBatch" v-model="riskFilters" :fields="riskFilterFields" @search="loadRisks" @reset="resetRiskFilters" />
      <ErrorState v-if="riskError" :description="riskError" @retry="loadRisks" />
      <LoadingState v-else-if="riskLoading" />
      <EmptyState
        v-else-if="!riskRows.length"
        :title="hasBatch ? '还没有风险记录' : '请先选择或创建毕设批次'"
        :description="hasBatch ? '系统会自动排查 13 类毕设问题（没选题、任务书没下达、开题逾期、中期没做、论文没交、答辩没排、材料没归档、毕业资格受影响等）。点下面的按钮按当前数据扫一遍，出问题的学生会自动列出来，不用手工排查。' : '顶部批次条选择当前工作批次后，再扫描与处置风险。'"
      >
        <template v-if="hasBatch && canRiskScan" #actions>
          <button class="mp-btn mp-btn--primary" @click="doScan">扫描生成风险项</button>
        </template>
      </EmptyState>
      <div v-else class="rk-split">
        <aside class="rk-list">
          <ul class="rk-rows">
            <li v-for="(row, i) in riskRows" :key="row.id" class="rk-row" :class="{ 'is-active': String(row.id) === riskSelKey }" tabindex="0" role="button" @click="selectRisk(row)" @keydown.enter.prevent="selectRisk(row)" @keydown.space.prevent="selectRisk(row)">
              <div class="rk-row__main">
                <span class="rk-row__name">{{ row.riskName }}</span>
                <StatusTag :type="row.level === 'CRITICAL' || row.level === 'HIGH' ? 'danger' : 'warning'" :label="levelLabel(row.level)" dot />
              </div>
              <div class="rk-row__sub">{{ row.studentName }} · {{ row.studentNo }}</div>
              <div class="rk-row__meta"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /><span class="rk-row__idx">{{ (riskPage - 1) * riskPageSize + i + 1 }}</span></div>
            </li>
          </ul>
          <div style="display: flex; justify-content: center"><AppPagination :total="riskTotal" :page="riskPage" :page-size="riskPageSize" :show-size-changer="false" @update:page="p => { riskPage = p; loadRisks() }" /></div>
        </aside>
        <section class="rk-pane">
          <div class="rk-pane__bar">
            <span>本页第 {{ riskSelIndex + 1 }} / {{ riskRows.length }} 条 · 共 {{ riskTotal }} 条</span>
            <label class="rk-pane__auto"><input v-model="riskAutoNext" type="checkbox" /> 处置后自动进入下一条</label>
            <span class="rk-pane__nav">
              <button class="mp-link" :disabled="riskSelIndex <= 0" @click="stepRisk(-1)">← 上一条</button>
              <button class="mp-link" :disabled="riskSelIndex >= riskRows.length - 1" @click="stepRisk(1)">下一条 →</button>
            </span>
          </div>
          <EmptyState v-if="!selectedRisk" title="从左侧选择一条风险" description="处置后可自动进入下一条待办风险" />
          <section v-else class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ selectedRisk.riskName }}</span>
              <button v-if="canStudentView && selectedRisk.gdStudentId" class="mp-link" @click="$router.push('/admin/graduation/students/' + selectedRisk.gdStudentId)">查看学生档案 →</button>
            </div>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">等级</span><span class="mp-kv__v"><StatusTag :type="selectedRisk.level === 'CRITICAL' || selectedRisk.level === 'HIGH' ? 'danger' : 'warning'" :label="levelLabel(selectedRisk.level)" dot /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v"><StatusTag :type="selectedRisk.statusTone" :label="selectedRisk.statusLabel" dot /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ selectedRisk.studentName }} · {{ selectedRisk.studentNo }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ selectedRisk.advisorName || '未分配导师' }}</span></div>
              <div v-if="selectedRisk.nextActionHint" class="mp-kv"><span class="mp-kv__k">下一步</span><span class="mp-kv__v">{{ selectedRisk.nextActionHint }}</span></div>
              <div v-if="selectedRisk.conditionSummary || selectedRisk.detail" class="mp-kv"><span class="mp-kv__k">当前触发原因</span><span class="mp-kv__v">{{ selectedRisk.conditionSummary || selectedRisk.detail }}{{ selectedRisk.conditionActive === false ? '（最近扫描条件已消失）' : '' }}</span></div>
              <div v-if="selectedRisk.firstDetectedAt || selectedRisk.createdAt" class="mp-kv"><span class="mp-kv__k">首次触发</span><span class="mp-kv__v">{{ formatDateTime(selectedRisk.firstDetectedAt || selectedRisk.createdAt) }}</span></div>
              <div v-if="selectedRisk.lastDetectedAt" class="mp-kv"><span class="mp-kv__k">最近仍命中</span><span class="mp-kv__v">{{ formatDateTime(selectedRisk.lastDetectedAt) }}</span></div>
              <div v-if="selectedRisk.reopenCount" class="mp-kv"><span class="mp-kv__k">重开次数</span><span class="mp-kv__v">{{ selectedRisk.reopenCount }}</span></div>
              <div v-if="selectedRisk.handleNote" class="mp-kv"><span class="mp-kv__k">处理记录</span><span class="mp-kv__v">{{ selectedRisk.handleNote }}</span></div>
              <div class="ie-actions" style="justify-content: flex-start; margin-top: var(--space-3)">
                <button v-if="canRiskAccept && selectedRisk.status === 'OPEN'" class="mp-btn mp-btn--primary" @click="doAccept(selectedRisk)">受理</button>
                <button v-if="canRiskProcess && selectedRisk.status === 'PROCESSING'" class="mp-btn mp-btn--primary" @click="doProcess(selectedRisk)">记录处理</button>
                <button v-if="canRiskClose && (selectedRisk.status === 'PROCESSING' || (selectedRisk.status === 'OPEN' && selectedRisk.conditionActive === false))" class="mp-btn" @click="doClose(selectedRisk)">关闭风险</button>
                <span v-if="selectedRisk.status === 'CLOSED'" class="mp-note">该风险已关闭</span>
              </div>
              <p class="mp-note" style="margin-top: var(--space-2)">受理 / 处理 / 关闭均写入审计留痕；关闭需填写原因。</p>
            </div>
          </section>
        </section>
      </div>
    </div>
    <!-- 毕设归档：连续双栏核验（左队列 + 右缺件清单与状态机动作） -->
    <div v-if="tab === 'archive' && canArchiveView" class="mp-stack">
      <div v-if="hasBatch" class="ie-actions" style="justify-content: flex-start">
        <button v-if="canArchivePreview && canArchiveFile" class="mp-btn mp-btn--primary" @click="doBatchGenerate">批量生成提交</button>
        <button v-if="canArchivePreview && canArchiveFile" class="mp-btn" @click="doBatchFile">一键核验备案</button>
        <AppExportButton v-if="canArchiveExport" :export-fn="exportArchivesFn">导出台账</AppExportButton>
      </div>
      <AdvancedFilter v-if="hasBatch" v-model="archiveFilters" :fields="archiveFilterFields" @search="loadArchives" @reset="resetArchiveFilters" />
      <ErrorState v-if="archiveError" :description="archiveError" @retry="loadArchives" />
      <LoadingState v-else-if="archiveLoading" />
      <EmptyState v-else-if="!archiveRows.length" :title="hasBatch ? '暂无归档记录' : '请先选择或创建毕设批次'" :description="hasBatch ? '' : '顶部批次条选择当前工作批次后，再办理归档。'" />
      <div v-else class="rk-split">
        <aside class="rk-list">
          <ul class="rk-rows">
            <li v-for="(row, i) in archiveRows" :key="row.id" class="rk-row" :class="{ 'is-active': String(row.id) === archiveSelKey }" tabindex="0" role="button" @click="selectArchive(row)" @keydown.enter.prevent="selectArchive(row)" @keydown.space.prevent="selectArchive(row)">
              <div class="rk-row__main">
                <span class="rk-row__name">{{ row.studentName }}</span>
                <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
              </div>
              <div class="rk-row__sub">{{ row.studentNo }}</div>
              <div class="rk-row__meta">
                <span :style="row.missingItems.length ? 'color: var(--danger, #dc2626)' : 'color: var(--success-600, #16a34a)'">{{ row.missingItems.length ? '缺 ' + row.missingItems.length + ' 项' : '材料齐全' }}</span>
                <span class="rk-row__idx">{{ (archivePage - 1) * archivePageSize + i + 1 }}</span>
              </div>
            </li>
          </ul>
          <div style="display: flex; justify-content: center"><AppPagination :total="archiveTotal" :page="archivePage" :page-size="archivePageSize" :show-size-changer="false" @update:page="p => { archivePage = p; loadArchives() }" /></div>
        </aside>
        <section class="rk-pane">
          <div class="rk-pane__bar">
            <span>本页第 {{ archiveSelIndex + 1 }} / {{ archiveRows.length }} 条 · 共 {{ archiveTotal }} 条</span>
            <span class="rk-pane__nav">
              <button class="mp-link" :disabled="archiveSelIndex <= 0" @click="stepArchive(-1)">← 上一条</button>
              <button class="mp-link" :disabled="archiveSelIndex >= archiveRows.length - 1" @click="stepArchive(1)">下一条 →</button>
            </span>
          </div>
          <EmptyState v-if="!selectedArchive" title="从左侧选择一名学生" description="逐个核验材料完整性并办理归档" />
          <section v-else class="mp-card">
            <div class="mp-card__head">
              <span class="mp-card__title">{{ selectedArchive.studentName }} · 归档核验</span>
              <button v-if="canStudentView && selectedArchive.gdStudentId" class="mp-link" @click="$router.push('/admin/graduation/students/' + selectedArchive.gdStudentId)">查看学生档案 →</button>
            </div>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">学号</span><span class="mp-kv__v">{{ selectedArchive.studentNo }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">归档状态</span><span class="mp-kv__v"><StatusTag :type="selectedArchive.statusTone" :label="selectedArchive.statusLabel" dot /></span></div>
              <div class="mp-kv"><span class="mp-kv__k">材料完整性</span>
                <span class="mp-kv__v" :style="selectedArchive.missingItems.length ? 'color: var(--danger, #dc2626)' : 'color: var(--success-600, #16a34a)'">
                  {{ selectedArchive.missingItems.length ? '缺失 ' + selectedArchive.missingItems.length + ' 项' : '必备材料齐全' }}
                </span>
              </div>
              <template v-if="selectedArchive.missingItems.length">
                <p class="mp-note" style="margin-top: var(--space-2); font-weight: 600; color: var(--text-primary)">缺件明细（点击直达补齐入口）</p>
                <ul class="ar-missing">
                  <li v-for="m in selectedArchive.missingItems" :key="m" class="ar-missing__item">
                    <span class="ar-missing__name">✕ {{ m }}</span>
                    <button v-if="canStudentView" class="mp-link" @click="goFix(m, selectedArchive)">{{ selectedArchive.dataAnomaly ? '查看学生档案 →' : '去补齐 →' }}</button>
                  </li>
                </ul>
              </template>
              <div class="ie-actions" style="justify-content: flex-start; margin-top: var(--space-3)">
                <span v-if="selectedArchive.dataAnomaly" class="mp-note" style="color: var(--danger, #dc2626); font-weight: 600">历史主档异常，当前归档记录仅允许只读查看</span>
                <template v-else>
                  <button v-if="canArchivePreview && ['NOT_GENERATED', 'REJECTED'].includes(selectedArchive.status)" class="mp-btn mp-btn--primary" @click="doGenerate(selectedArchive)">生成清单</button>
                  <button v-if="canArchiveFile && selectedArchive.status === 'PENDING_SUBMIT' && !selectedArchive.missingItems.length" class="mp-btn mp-btn--primary" @click="doSubmit(selectedArchive)">提交归档</button>
                  <span v-if="selectedArchive.status === 'PENDING_SUBMIT' && selectedArchive.missingItems.length" class="mp-note">缺件补齐后方可提交归档</span>
                  <button v-if="canArchiveFile && selectedArchive.status === 'SUBMITTED'" class="mp-btn mp-btn--primary" @click="doFile(selectedArchive)">核验归档</button>
                  <button v-if="canArchiveFile && selectedArchive.status === 'SUBMITTED'" class="mp-btn" @click="doReject(selectedArchive)">驳回</button>
                  <span v-if="selectedArchive.status === 'FILED'" class="mp-note">已正式归档备案，记录只读</span>
                </template>
              </div>
              <p class="mp-note" style="margin-top: var(--space-2)">生成 / 提交 / 核验 / 驳回均写入审计留痕；完整性以后端清单核验为准。</p>
            </div>
          </section>
        </section>
      </div>
    </div>
    <!-- 毕设统计 -->
    <div v-if="tab === 'stats' && canStatsView" class="mp-stack">
      <p class="mp-note">以下为当前数据范围内的全量汇总（时间筛选待后端统一接入后开放）。</p>
      <ErrorState v-if="statsError" :description="statsError" @retry="loadStats" />
      <LoadingState v-else-if="statsLoading" />
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
        <AppStackedBarChart
          v-if="stageChartData.length >= 2"
          title="各阶段学生数"
          :data="stageChartData"
          horizontal
          :height="Math.max(150, stageChartData.length * 38)"
          x-field="label"
          y-field="count"
          series-field="cat"
          value-label="人数"
        />
        <ul v-else class="gs-stage-list">
          <li v-for="s in overview.byStage" :key="s.stage">{{ s.label }}：{{ s.count }}</li>
        </ul>
        <div class="gm-section-title" style="margin-top: var(--space-4)">学院/专业对比</div>
        <DataTable :columns="collegeColumns" :rows="collegeRows" row-key="name" />
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :reason-chips="confirm.reasonChips || []" @confirm="onConfirm"
    />
    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-risk-archive" />
  </ModulePageShell>
</template>

<script>
/** 问题预警+毕设归档+毕设统计（/admin/graduation/risk-archive）：扫描处置闭环 + 材料核验归档 + 跨模块统计看板。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton, AppPagination, AppStackedBarChart, AppPageGuide } from '@/components/common'
import { graduationRiskArchiveApi } from '@/modules/graduation/api/graduation-risk-archive.api'
import { buildRiskArchiveQuery, exportFilenameHint } from '@/modules/graduation/utils/queryParams'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'

const ARCHIVE_REJECT_REASON_CHIPS = [
  '材料不齐全，缺相关附件/签字页',
  '签字或日期不完整（签字应早于答辩日期）',
  '装订顺序不符合规范',
  '重复度超标未完成整改',
  '电子版与纸质版内容不一致'
]

export default {
  name: 'GraduationRiskArchiveView',
  components: { AppPageGuide, ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppExportButton, AppPagination, AppStackedBarChart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      tab: 'risk',
      riskSelKey: '', riskAutoNext: true,
      archiveSelKey: '',
      riskFilters: { status: '', level: '', keyword: '' }, riskRows: [], riskTotal: 0, riskPage: 1, riskPageSize: 10, riskLoading: true, riskError: '',
      lastScanAt: '', lastScanStats: null,
      archiveFilters: { keyword: '', status: '' }, archiveRows: [], archiveTotal: 0, archivePage: 1, archivePageSize: 10, archiveLoading: true, archiveError: '',
      statsError: '',
      overview: null, collegeRows: [], statsLoading: true,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      actionReceipt: null,
      riskColumns: [{ key: 'risk', title: '风险 / 学生' }, { key: 'level', title: '等级' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '160px' }],
      archiveColumns: [{ key: 'student', title: '学生' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '200px' }],
      collegeColumns: [{ key: 'name', title: '学院/专业' }, { key: 'total', title: '学生数' }, { key: 'archived', title: '已归档' }, { key: 'highRisk', title: '高风险' }]
    }
  },
  computed: {
    permissionPatterns() { return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : [] },
    canRiskView() { return matchPermission(this.permissionPatterns, 'graduationDesign.risk.view') },
    canRiskScan() { return matchPermission(this.permissionPatterns, 'graduationDesign.risk.scan') },
    canRiskAccept() { return matchPermission(this.permissionPatterns, 'graduationDesign.risk.accept') },
    canRiskProcess() { return matchPermission(this.permissionPatterns, 'graduationDesign.risk.process') },
    canRiskClose() { return matchPermission(this.permissionPatterns, 'graduationDesign.risk.close') },
    canArchiveView() { return matchPermission(this.permissionPatterns, 'graduationDesign.archive.view') },
    canArchivePreview() { return matchPermission(this.permissionPatterns, 'graduationDesign.archive.preview') },
    canArchiveFile() { return matchPermission(this.permissionPatterns, 'graduationDesign.archive.file') },
    canArchiveExport() { return matchPermission(this.permissionPatterns, 'graduationDesign.archive.export') },
    canStatsView() { return matchPermission(this.permissionPatterns, 'graduationDesign.dashboard.view') },
    canStudentView() { return matchPermission(this.permissionPatterns, 'graduationDesign.student.view') },
    availableTabs() {
      return [
        this.canRiskView ? 'risk' : '',
        this.canArchiveView ? 'archive' : '',
        this.canStatsView ? 'stats' : ''
      ].filter(Boolean)
    },
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}风险扫描与处置闭环 / 材料归档核验 / 跨模块统计看板`
    },
    selectedRisk() {
      return this.riskRows.find((r) => String(r.id) === this.riskSelKey) || null
    },
    riskSelIndex() {
      return this.riskRows.findIndex((r) => String(r.id) === this.riskSelKey)
    },
    stageChartData() {
      return ((this.overview && this.overview.byStage) || []).filter((s) => (s.count || 0) > 0).map((s) => ({ label: s.label, count: s.count, cat: '人数' }))
    },
    selectedArchive() {
      return this.archiveRows.find((r) => String(r.id) === this.archiveSelKey) || null
    },
    archiveSelIndex() {
      return this.archiveRows.findIndex((r) => String(r.id) === this.archiveSelKey)
    },
    riskFilterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 风险名称' },
        { key: 'status', label: '状态', type: 'select', options: [{ value: 'OPEN', label: '待受理' }, { value: 'PROCESSING', label: '处理中' }, { value: 'CLOSED', label: '已关闭' }] },
        { key: 'level', label: '等级', type: 'select', options: [{ value: 'LOW', label: '低' }, { value: 'MEDIUM', label: '中' }, { value: 'HIGH', label: '高' }, { value: 'CRITICAL', label: '紧急' }] }
      ]
    },
    archiveFilterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名' },
        { key: 'status', label: '状态', type: 'select', options: [{ value: 'NOT_GENERATED', label: '待生成' }, { value: 'PENDING_SUBMIT', label: '待提交' }, { value: 'SUBMITTED', label: '已提交' }, { value: 'FILED', label: '已备案' }, { value: 'REJECTED', label: '已驳回' }] }
      ]
    }
  },
  created() {
    const requested = String(this.$route.query.panel || '')
    this.tab = this.isPanelAllowed(requested) ? requested : (this.availableTabs[0] || '')
    this.riskSelKey = (this.$route.query.rsel || '').toString()
    this.archiveSelKey = (this.$route.query.asel || '').toString()
    if (this.tab && requested !== this.tab) {
      this.$router.replace({ query: { ...this.$route.query, panel: this.tab } }).catch(() => {})
    }
    this.loadActivePanel()
  },
  watch: {
    // 应用内点左侧三级菜单（同路由不同 ?panel=）时组件被复用；无权 panel 必须回退到本角色第一个合法工作区。
    '$route.query.panel'(p) {
      const requested = String(p || '')
      const next = this.isPanelAllowed(requested) ? requested : (this.availableTabs[0] || '')
      if (!next) return
      if (next !== this.tab) {
        this.tab = next
        this.loadActivePanel()
      }
      if (requested !== next) this.$router.replace({ query: { ...this.$route.query, panel: next } }).catch(() => {})
    },
    'batchStore.selectedBatchId'() {
      this.riskPage = 1
      this.archivePage = 1
      this.loadActivePanel()
    }
  },
  methods: {
    formatDateTime,
    isPanelAllowed(panel) {
      return (panel === 'risk' && this.canRiskView)
        || (panel === 'archive' && this.canArchiveView)
        || (panel === 'stats' && this.canStatsView)
    },
    loadActivePanel() {
      if (this.tab === 'risk' && this.canRiskView) {
        this.loadRisks()
        this.loadLastScan()
      } else if (this.tab === 'archive' && this.canArchiveView) {
        this.loadArchives()
      } else if (this.tab === 'stats' && this.canStatsView) {
        this.loadStats()
      }
    },
    async loadLastScan() {
      if (!this.canRiskView) return
      if (!this.batchStore.selectedBatchId) {
        this.lastScanAt = ''
        this.lastScanStats = null
        return
      }
      const res = await graduationRiskArchiveApi.getLastRiskScan({ batchId: this.batchStore.selectedBatchId })
      if (res.code === 0 && res.data) {
        this.lastScanAt = res.data.lastScanAt || ''
        this.lastScanStats = res.data.stats || null
      }
    },
    /** 页签切换同步到 URL，保证刷新/分享/左侧菜单高亮一致 */
    switchTab(t) {
      if (!this.isPanelAllowed(t)) return
      if (this.tab !== t) {
        this.tab = t
        this.loadActivePanel()
      }
      if (this.$route.query.panel !== t) this.$router.replace({ query: { ...this.$route.query, panel: t } }).catch(() => {})
    },
    async doScan() {
      if (!this.canRiskScan) { toast.error('当前角色无风险扫描权限'); return }
      if (!this.batchStore.selectedBatchId) {
        toast.error('请先选择毕设批次')
        return
      }
      const res = await graduationRiskArchiveApi.scanRisks({ batchId: this.batchStore.selectedBatchId })
      if (res.code === 0) {
        const d = res.data || {}
        this.lastScanAt = d.lastScanAt || this.lastScanAt
        this.lastScanStats = {
          scannedStudents: d.scannedStudents,
          newCasesCreated: d.newCasesCreated,
          reopenedCases: d.reopenedCases,
          elapsedMs: d.elapsedMs,
        }
        toast.success(
          res.message
          || `已扫描 ${d.scannedStudents || 0} 人，新增 ${d.newCasesCreated || 0}，重开 ${d.reopenedCases || 0}`
        )
        this.loadRisks()
      } else toast.error(res.message)
    },
    /** 风险等级展示映射（不向老师透出内部英文枚举） */
    levelLabel(level) {
      return { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }[level] || (level ? '等级待确认' : '—')
    },
    selectRisk(row) {
      this.riskSelKey = String(row.id)
      this.$router.replace({ query: { ...this.$route.query, rsel: this.riskSelKey } })
    },
    stepRisk(d) {
      const i = this.riskSelIndex + d
      if (i >= 0 && i < this.riskRows.length) this.selectRisk(this.riskRows[i])
    },
    /** 保持/推进选中：处置后若开启自动下一条且当前已关闭，则跳到下一条待办风险 */
    ensureRiskSelection() {
      if (!this.riskRows.length) { this.riskSelKey = ''; return }
      const cur = this.selectedRisk
      const actionable = (r) => r.status === 'OPEN' || r.status === 'PROCESSING'
      if (cur && this.riskAutoNext && cur.status === 'CLOSED') {
        const from = this.riskSelIndex
        for (let i = from + 1; i < this.riskRows.length; i++) if (actionable(this.riskRows[i])) { this.selectRisk(this.riskRows[i]); return }
        for (let i = 0; i < from; i++) if (actionable(this.riskRows[i])) { this.selectRisk(this.riskRows[i]); return }
        return
      }
      if (!cur) {
        const target = this.riskRows.find(actionable) || this.riskRows[0]
        if (target) this.selectRisk(target)
      }
    },
    async loadRisks() {
      if (!this.canRiskView) { this.riskLoading = false; this.riskRows = []; this.riskTotal = 0; return }
      if (!this.batchStore.selectedBatchId) {
        this.riskLoading = false
        this.riskError = ''
        this.riskRows = []
        this.riskTotal = 0
        return
      }
      this.riskLoading = true
      this.riskError = ''
      const res = await graduationRiskArchiveApi.getRiskList(buildRiskArchiveQuery(this.riskFilters, {
        page: this.riskPage,
        pageSize: this.riskPageSize,
        batchId: this.batchStore.selectedBatchId
      }))
      if (res.code === 0) { this.riskRows = res.data.list; this.riskTotal = res.data.total; this.ensureRiskSelection() } else { this.riskRows = []; this.riskError = res.message || '加载失败' }
      this.riskLoading = false
    },
    resetRiskFilters() { this.riskFilters = { status: '', level: '', keyword: '' }; this.riskPage = 1; this.loadRisks() },
    doAccept(row) {
      if (!this.canRiskAccept) { toast.error('当前角色无风险受理权限'); return }
      this.confirm = { visible: true, title: '受理风险', message: `确认受理「${row.riskName}」（${row.studentName}）？`, type: 'primary', confirmText: '受理', requireReason: false, action: 'accept', row }
    },
    doProcess(row) {
      if (!this.canRiskProcess) { toast.error('当前角色无风险处理权限'); return }
      this.confirm = { visible: true, title: '记录处理', message: '', type: 'primary', confirmText: '提交', requireReason: true, reasonLabel: '处理说明', action: 'process', row }
    },
    doClose(row) {
      if (!this.canRiskClose) { toast.error('当前角色无风险关闭权限'); return }
      this.confirm = { visible: true, title: '关闭风险', message: '', type: 'danger', confirmText: '确认关闭', requireReason: true, reasonLabel: '关闭原因', action: 'close', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      if (action === 'batch-generate-noop' || action === 'batch-file-noop') {
        this.confirm.visible = false
        return
      }
      const allowed = (action === 'accept' && this.canRiskAccept)
        || (action === 'process' && this.canRiskProcess)
        || (action === 'close' && this.canRiskClose)
        || (action === 'reject-archive' && this.canArchiveFile)
        || (action === 'batch-generate' && this.canArchivePreview && this.canArchiveFile)
        || (action === 'batch-file' && this.canArchivePreview && this.canArchiveFile)
      if (!allowed) { this.confirm.visible = false; toast.error('当前角色无此操作权限'); return }
      let res
      if (action === 'accept') res = await graduationRiskArchiveApi.acceptRisk(row.id)
      else if (action === 'process') res = await graduationRiskArchiveApi.processRisk(row.id, reason || '')
      else if (action === 'close') res = await graduationRiskArchiveApi.closeRisk(row.id, reason || '')
      else if (action === 'reject-archive') res = await graduationRiskArchiveApi.rejectArchive(row.gdStudentId, reason || '')
      else if (action === 'batch-generate') {
        res = await graduationRiskArchiveApi.batchGenerateArchive({ batchId: this.batchStore.selectedBatchId })
      } else if (action === 'batch-file') {
        res = await graduationRiskArchiveApi.batchFileArchive({ batchId: this.batchStore.selectedBatchId })
      }
      if (res && res.code === 0) {
        let receipt
        if (action === 'batch-generate') {
          toast.success(`已提交 ${res.data.submitted}，跳过 ${res.data.skipped}（缺材料或未关闭风险）`)
          receipt = { title: '批量生成提交已完成', result: `服务器结果：成功 ${res.data.submitted || 0} · 跳过 ${res.data.skipped || 0}`, next: '下一步：在归档队列核对清单，材料齐全后提交归档。' }
        } else if (action === 'batch-file') {
          toast.success(`已批量备案 ${res.data.filed} 份（跳过 ${res.data.skipped}）`)
          receipt = { title: '批量备案已核对', result: `服务器结果：已备案 ${res.data.filed || 0} · 跳过 ${res.data.skipped || 0}`, next: res.data.reconciled ? '连接中断后已按归档批次号完成精确对账，无需再次提交。' : '备案记录已冻结，可进入导出或备份核验。' }
        } else {
          const label = action === 'accept' ? '风险已受理' : action === 'process' ? '处理记录已保存' : action === 'close' ? '风险已关闭' : '归档已退回'
          toast.success(label)
          receipt = { title: label, result: '服务器已接受操作，列表将回读最新状态。', next: action === 'reject-archive' ? '下一步由学生或责任老师按退回原因补齐材料。' : '可继续处理下一条队列。' }
        }
        this.confirm.visible = false
        if (action === 'reject-archive' || action === 'batch-file' || action === 'batch-generate') await this.loadArchives()
        else await this.loadRisks()
        this.actionReceipt = receipt
      } else if (res && Number(res.code) === 503002) {
        this.confirm.visible = false
        this.actionReceipt = {
          unknown: true,
          title: '备案结果尚未完全确认',
          result: res.message || `已核对 ${res.data?.filed || 0}/${res.data?.expectedExecutableCount || 0} 份`,
          next: '不要直接重复提交。先刷新归档台账核对；如仍不完整，重新执行预览后再决定。'
        }
      } else if (res) toast.error(res.message)
    },
    selectArchive(row) {
      this.archiveSelKey = String(row.id)
      this.$router.replace({ query: { ...this.$route.query, asel: this.archiveSelKey } })
    },
    stepArchive(d) {
      const i = this.archiveSelIndex + d
      if (i >= 0 && i < this.archiveRows.length) this.selectArchive(this.archiveRows[i])
    },
    ensureArchiveSelection() {
      if (!this.archiveRows.length) { this.archiveSelKey = ''; return }
      if (!this.selectedArchive) {
        const target = this.archiveRows.find((r) => r.status !== 'FILED') || this.archiveRows[0]
        if (target) this.selectArchive(target)
      }
    },
    /** 缺件补齐入口：永远绑定 exact gdStudentId，并保留批次/source 上下文。 */
    goFix(item, row) {
      if (!this.canStudentView) return
      const sid = row.gdStudentId
      if (!sid) {
        this.$router.push('/admin/graduation/students')
        return
      }
      const name = (item || '').toString()
      let tab = ''
      if (name.includes('任务书')) tab = 'taskbook'
      else if (name.includes('开题')) tab = 'proposals'
      else if (name.includes('中期')) tab = 'midterm'
      else if (name.includes('指导')) tab = 'guidance'
      else if (name.includes('查重')) tab = 'plagiarisms'
      else if (name.includes('评阅') || name.includes('答辩') || name.includes('成绩')) tab = 'review'
      else if (name.includes('成果') || name.includes('论文')) tab = 'finals'
      return this.$router.push({
        name: 'graduation-student-detail',
        params: { id: String(sid) },
        query: {
          ...(tab ? { tab } : {}),
          source: 'archive',
          ...(this.batchStore.selectedBatchId ? { batchId: String(this.batchStore.selectedBatchId) } : {})
        }
      })
    },
    async loadArchives() {
      if (!this.canArchiveView) { this.archiveLoading = false; this.archiveRows = []; this.archiveTotal = 0; return }
      if (!this.batchStore.selectedBatchId) {
        this.archiveLoading = false
        this.archiveError = ''
        this.archiveRows = []
        this.archiveTotal = 0
        return
      }
      this.archiveLoading = true
      this.archiveError = ''
      const res = await graduationRiskArchiveApi.getArchiveList(buildRiskArchiveQuery(this.archiveFilters, {
        page: this.archivePage,
        pageSize: this.archivePageSize,
        batchId: this.batchStore.selectedBatchId
      }))
      if (res.code === 0) { this.archiveRows = res.data.list; this.archiveTotal = res.data.total; this.ensureArchiveSelection() } else { this.archiveRows = []; this.archiveError = res.message || '加载失败' }
      this.archiveLoading = false
    },
    resetArchiveFilters() { this.archiveFilters = { keyword: '', status: '' }; this.archivePage = 1; this.loadArchives() },
    async doGenerate(row) {
      if (!this.canArchivePreview) { toast.error('当前角色无归档生成权限'); return }
      const res = await graduationRiskArchiveApi.generateArchive(row.gdStudentId)
      if (res.code === 0) { await this.loadArchives(); const latest = this.archiveRows.find(item => String(item.gdStudentId) === String(row.gdStudentId)); this.actionReceipt = { title: `${row.studentName} · 归档清单已生成`, result: `服务器最新状态：${latest?.statusLabel || '待提交'}`, next: latest?.missingItems?.length ? `仍缺 ${latest.missingItems.length} 项，点击缺件可直达补齐。` : '材料齐全后可提交归档。' }; toast.success('清单已生成，状态已回读') } else this.archiveWriteFailed(res)
    },
    async doSubmit(row) {
      if (!this.canArchiveFile) { toast.error('当前角色无归档提交权限'); return }
      const res = await graduationRiskArchiveApi.submitArchive(row.gdStudentId)
      if (res.code === 0) { await this.loadArchives(); const latest = this.archiveRows.find(item => String(item.gdStudentId) === String(row.gdStudentId)); this.actionReceipt = { title: `${row.studentName} · 归档已提交`, result: `服务器最新状态：${latest?.statusLabel || '已提交'}`, next: '下一步由归档授权角色核验并备案。' }; toast.success('归档已提交，状态已回读') } else this.archiveWriteFailed(res)
    },
    async doFile(row) {
      if (!this.canArchiveFile) { toast.error('当前角色无归档备案权限'); return }
      // Reuse an existing filing number when present; otherwise let the backend
      // allocate its deterministic daily number.  Passing the second argument is
      // important because the API helper reserves it for archiveBatchNo.
      const res = await graduationRiskArchiveApi.fileArchive(row.gdStudentId, row.archiveBatchNo || null)
      if (res.code === 0) { await this.loadArchives(); const latest = this.archiveRows.find(item => String(item.gdStudentId) === String(row.gdStudentId)); this.actionReceipt = { title: `${row.studentName} · 已正式归档备案`, result: `服务器最新状态：${latest?.statusLabel || '已备案'}；真实版本清单已冻结`, next: '当前记录只读，可导出台账或执行备份核验。' }; toast.success('已归档，冻结状态已回读') } else this.archiveWriteFailed(res)
    },
    doReject(row) {
      if (!this.canArchiveFile) { toast.error('当前角色无归档驳回权限'); return }
      this.confirm = {
        visible: true, title: '驳回归档', message: '', type: 'danger', confirmText: '确认驳回',
        requireReason: true, reasonLabel: '驳回原因', reasonChips: ARCHIVE_REJECT_REASON_CHIPS,
        action: 'reject-archive', row
      }
    },
    exportArchivesFn() {
      if (!this.canArchiveExport) return Promise.resolve({ code: 403001, data: null, message: '当前角色无归档导出权限' })
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '毕设归档')
      const p = buildRiskArchiveQuery(this.archiveFilters, { batchId: this.batchStore.selectedBatchId })
      return graduationRiskArchiveApi.exportArchives(p).then((res) => {
        if (res.code === 0 && res.data) {
          res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }
        }
        return res
      })
    },
    _formatSkipReasons(preview) {
      const rows = (preview && preview.skipReasons) || []
      if (!rows.length) return '无'
      const map = {
        already_submitted_or_filed: '已提交/已备案',
        already_submitted: '已提交/已备案',
        dirty_data: '历史主档异常（只读）',
        missing_materials: '材料不齐',
        open_risks: '风险未关闭',
        out_of_scope: '不在当前范围'
      }
      return rows.map((r) => `${map[r.reason] || r.reason} ${r.count}`).join('；')
    },
    async doBatchGenerate() {
      if (!this.canArchivePreview || !this.canArchiveFile) { toast.error('当前角色无批量归档权限'); return }
      if (!this.batchStore.selectedBatchId) {
        toast.error('请先选择毕设批次')
        return
      }
      const prev = await graduationRiskArchiveApi.previewBatchGenerate({
        batchId: this.batchStore.selectedBatchId
      })
      if (prev.code !== 0) {
        toast.error(prev.message || '预检查失败')
        return
      }
      const p = prev.data || {}
      const batchName = p.batchName || this.batchStore.selectedBatchName || '当前批次'
      this.confirm = {
        visible: true,
        title: '批量生成提交',
        message: (
          `批次「${batchName}」：候选 ${p.candidateCount} 人，预计成功 ${p.executableCount}，跳过 ${p.skippedCount}。`
          + `主要跳过原因：${this._formatSkipReasons(p)}。`
          + '本次只处理当前批次，不会处理其他届次。'
        ),
        type: 'primary',
        confirmText: p.executableCount > 0 ? '确认生成提交' : '知道了',
        requireReason: false,
        reasonLabel: '说明',
        action: p.executableCount > 0 ? 'batch-generate' : 'batch-generate-noop',
        row: null
      }
    },
    async doBatchFile() {
      if (!this.canArchivePreview || !this.canArchiveFile) { toast.error('当前角色无批量备案权限'); return }
      if (!this.batchStore.selectedBatchId) {
        toast.error('请先选择毕设批次')
        return
      }
      const prev = await graduationRiskArchiveApi.previewBatchFile({
        batchId: this.batchStore.selectedBatchId
      })
      if (prev.code !== 0) {
        toast.error(prev.message || '预检查失败')
        return
      }
      const p = prev.data || {}
      const batchName = p.batchName || this.batchStore.selectedBatchName || '当前批次'
      this.confirm = {
        visible: true,
        title: '一键核验备案',
        message: (
          `批次「${batchName}」：预计备案 ${p.executableCount} 份，跳过 ${p.skippedCount}。`
          + `主要跳过原因：${this._formatSkipReasons(p)}。`
          + '备案后学生毕设阶段将变为只读。本次只处理当前批次，不会处理其他届次。'
        ),
        type: 'warning',
        confirmText: p.executableCount > 0 ? '确认核验备案' : '知道了',
        requireReason: false,
        reasonLabel: '说明',
        action: p.executableCount > 0 ? 'batch-file' : 'batch-file-noop',
        row: null
      }
    },
    async loadStats() {
      if (!this.canStatsView) { this.statsLoading = false; this.overview = null; this.collegeRows = []; return }
      this.statsLoading = true
      this.statsError = ''
      if (!this.batchStore.selectedBatchId) {
        this.overview = null
        this.collegeRows = []
        this.statsLoading = false
        return
      }
      const params = { batchId: this.batchStore.selectedBatchId }
      const [o, c] = await Promise.all([
        graduationRiskArchiveApi.getOverviewStats(params),
        graduationRiskArchiveApi.getCollegeComparison(params)
      ])
      this.overview = o.code === 0 ? o.data : null
      this.collegeRows = c.code === 0 ? c.data : []
      if (o.code !== 0) this.statsError = o.message || '统计加载失败'
      this.statsLoading = false
    },
    archiveWriteFailed(res) {
      if (Number(res?.code) === 503001 || Number(res?.code) === 503002) {
        this.actionReceipt = { unknown: true, title: '写入结果需要核对', result: res?.message || '连接中断，无法确认服务器是否已经完成操作。', next: '不要重复点击。先刷新归档台账，根据最新状态决定是否需要重新预览。' }
      } else toast.error(res?.message || '归档操作未完成')
    },
    async verifyUnknownResult() {
      await this.loadArchives()
      this.actionReceipt = { title: '台账已刷新', result: '已从服务器重新读取当前归档状态。', next: '请按最新状态继续；若批量操作仍不完整，必须重新预览，不能复用旧执行凭证。' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.rk-scan-bar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); margin-bottom: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--gray-50, #f8fafc); }
.rk-scan-bar__meta { display: flex; flex-wrap: wrap; gap: var(--space-3); font-size: var(--font-size-sm, 13px); color: var(--text-secondary); }
.rk-split { display: flex; gap: var(--space-4); align-items: flex-start; }
.rk-list { width: 340px; flex: none; display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.rk-pane { flex: 1; min-width: 0; padding: var(--space-4); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.rk-rows { list-style: none; margin: 0; padding: 0; max-height: 600px; overflow-y: auto; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); }
.rk-row { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #eef1f6); cursor: pointer; transition: background .12s ease, box-shadow .12s ease; }
.rk-row:last-child { border-bottom: none; }
.rk-row:hover { background: var(--gray-50, #f8fafc); }
.rk-row.is-active { background: var(--primary-50, #eff6ff); box-shadow: inset 2px 0 0 var(--brand-primary, #2563eb); }
.rk-row:focus-visible { position: relative; z-index: 1; outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.rk-row__main { display: flex; align-items: center; gap: var(--space-2); }
.rk-row__name { font-weight: var(--font-weight-medium, 500); color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rk-row__sub { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.rk-row__meta { margin-top: 2px; display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rk-row__idx { margin-left: auto; }
.rk-pane__bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-2) var(--space-3); margin-bottom: var(--space-3); background: var(--gray-50, #f8fafc); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); font-size: var(--font-size-sm); color: var(--text-secondary); }
.rk-pane__auto { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.rk-pane__nav { margin-left: auto; display: inline-flex; gap: var(--space-3); }
.rk-pane__nav .mp-link:disabled { opacity: 0.4; cursor: not-allowed; }
.ar-missing { list-style: none; margin: var(--space-1) 0 0; padding: 0; }
.ar-missing__item { display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; border: 1px dashed var(--danger, #fca5a5); border-radius: var(--radius-md, 8px); margin-bottom: 6px; background: var(--danger-50, #fef2f2); font-size: var(--font-size-sm, 13px); }
.ar-missing__name { color: var(--danger, #dc2626); }
.mp-link--danger { color: var(--danger, #dc2626); }
.gp-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gp-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gp-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gs-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.gs-card { border: 1px solid var(--line, #e2e8f0); border-radius: 10px; padding: 12px; background: linear-gradient(145deg, var(--color-bg-subtle, #f8fafc), var(--card, #fff)); box-shadow: 0 1px 1px rgba(15, 23, 42, .02); }
.gs-card__label { font-size: 12px; color: var(--t3, #64748b); }
.gs-card__value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.gm-section-title { font-size: 13px; font-weight: 600; }
.gs-stage-list { list-style: none; margin: 8px 0; padding: 0; display: flex; gap: var(--space-4); flex-wrap: wrap; font-size: 13px; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-bottom: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.ra-receipt{display:flex;align-items:center;gap:14px;margin-bottom:var(--space-3);padding:11px 12px;border:1px solid #b7ebc6;border-radius:9px;background:#f0fff4}.ra-receipt.is-unknown{border-color:#f6c453;background:#fff9e8}.ra-receipt div{display:grid;gap:3px;flex:1}.ra-receipt strong{color:#137a43}.ra-receipt.is-unknown strong{color:#8a5b00}.ra-receipt span{font-size:13px}.ra-receipt small{color:var(--text-tertiary)}.ra-receipt button{border:1px solid var(--border-light);border-radius:7px;background:#fff;padding:6px 9px;color:var(--primary-600);cursor:pointer}
@media (max-width: 1100px) { .rk-split { flex-direction: column; } .rk-list, .rk-pane { width: 100%; box-sizing: border-box; } .rk-pane { padding: var(--space-3); } }
</style>
