<template>
  <ModulePageShell class="aa-statistics" :title="statsPage.title" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName">
    <template #actions><span v-if="updatedAt" class="stats-updated" role="status">更新于 {{ updatedAt }}</span></template>
    <nav v-if="topicTabs.length > 1" class="stats-dimensions" aria-label="本专题统计维度">
      <button v-for="item in topicTabs" :key="item.key" type="button" :aria-current="tab === item.key ? 'page' : undefined" :class="{ active: tab === item.key }" @click="switchTab(item.key)">{{ item.label }}</button>
    </nav>
    <form v-if="!['export', 'snapshot', 'resource'].includes(tab)" class="aa-filter" @submit.prevent="search">
      <label class="aa-filter__item">学期<AppTermEntityPicker v-model="filters.termId" placeholder="全部学期" @change="(value, items) => rememberFilter('termId', value, items)" /></label>
      <label class="aa-filter__item">学院<AppCollegePicker v-model="filters.collegeId" placeholder="全部学院" @change="collegeChanged" /></label>
      <label v-if="tab === 'overview' || tab === 'registration'" class="aa-filter__item">专业<AppMajorPicker v-model="filters.majorId" :query="{ collegeId: filters.collegeId || undefined }" placeholder="全部专业" @change="(value, items) => rememberFilter('majorId', value, items)" /></label>
      <label v-if="tab === 'course'" class="aa-filter__item">课程类别<AppSelect v-model="filters.category" :options="courseCategoryOptions" /></label>
      <label v-if="tab === 'graduation'" class="aa-filter__item">预审批次<AppGraduationBatchPicker v-model="filters.batchId" placeholder="全部批次" /></label>
      <div class="stats-filter-actions"><AppButton type="submit" variant="primary" :loading="loading">查询</AppButton><AppButton variant="ghost" :disabled="loading" @click="resetFilters">重置</AppButton></div>
      <p class="stats-applied">已应用：{{ appliedScopeLabel }}</p>
    </form>
    <p v-if="tab === 'resource'" class="stats-applied">资源按当前授权范围统计，不随学期筛选。<AppButton size="small" variant="ghost" :loading="loading" @click="loadTab">刷新</AppButton></p>
    <p v-if="filtersDirty && !['export', 'snapshot', 'resource'].includes(tab)" class="stats-notice" role="status">筛选尚未查询，下方仍为上次查询结果。</p>
    <ErrorState v-if="error" :description="error" @retry="loadTab" />
    <LoadingState v-else-if="loading" />
    <p v-else-if="scopeBlocked" class="stats-notice">当前账号未配置教务数据范围，请联系管理员。</p>
    <template v-else>
      <section v-if="analyticsCards.length" class="stats-kpi-grid" aria-label="业务指标">
        <article v-for="card in analyticsCards" :key="card.label" class="stats-kpi-card" :class="{ 'is-warning': card.tone === 'warning' }">
          <span>{{ card.label }}</span><strong>{{ displayMetric(card) }}<small v-if="card.unit && card.value !== null" class="stats-unit">{{ card.unit }}</small></strong><small v-if="card.note">{{ card.note }}</small>
        </article>
      </section>
      <template v-if="tab === 'overview'">
        <section v-if="attentionItems.length" class="stats-attention" aria-label="需要关注">
          <strong>需要关注</strong><div v-for="item in attentionItems" :key="item.key"><span>{{ item.attentionLabel }}</span><b>{{ numberLabel(item.attentionValue) }}</b><AppButton size="small" variant="ghost" @click="drillable(item) ? onCardClick(item) : openIndicatorTopic(item)">{{ drillable(item) ? '查看明细' : '查看专题' }}</AppButton></div>
        </section>
        <section class="stats-analysis-panel stats-indicator-ledger">
          <header><h2>业务指标</h2><span>{{ overviewRows.length }} 项指标</span></header>
          <DataTable :columns="overviewColumns" :rows="overviewRows" row-key="key">
            <template #cell-label="{ row }"><strong>{{ indicatorLabel(row) }}</strong><small v-if="row.message" class="stats-cell-note">{{ row.message }}</small></template>
            <template #cell-value="{ row }"><strong>{{ indicatorValue(row) }}</strong></template>
            <template #cell-basis="{ row }">{{ indicatorBasis(row) }}</template>
            <template #cell-action="{ row }"><AppButton v-if="drillable(row)" size="small" variant="ghost" @click="onCardClick(row)">{{ activeDrill === row.key ? '收起明细' : '查看明细' }}</AppButton><AppButton v-else-if="indicatorTopic(row)" size="small" variant="ghost" @click="openIndicatorTopic(row)">查看专题</AppButton><span v-else class="stats-cell-note">仅汇总</span></template>
          </DataTable>
        </section>
        <p class="stats-trend-note">暂无连续统计数据，可查看历史快照。<AppButton v-if="canViewSnapshot" size="small" variant="ghost" @click="switchTab('snapshot')">查看历史快照</AppButton></p>
        <details class="stats-method"><summary>统计口径与数据时间</summary><p>{{ appliedScopeLabel }}；数据截至 {{ sourceTimeLabel }}。不同学期或范围的快照不能直接比较。</p></details>
        <section v-if="activeDrill" class="aa-drill">
          <header><h2>{{ drillTitle }}</h2><AppButton variant="ghost" @click="closeDrill">收起</AppButton></header>
          <LoadingState v-if="drill.loading" /><ErrorState v-else-if="drill.error" :description="drill.error" @retry="loadDrill" @back="closeDrill" /><EmptyState v-else-if="!drill.rows.length" @back="closeDrill" title="当前范围没有明细" description="可调整查询条件后再查看。" />
          <DataTable v-else :columns="drillColumns" :rows="drill.rows" row-key="rowKey" :pagination="drill.pagination" @page-change="onDrillPage"><template #cell-status="{ row }">{{ groupLabel(row.status) }}</template><template #cell-changeType="{ row }">{{ groupLabel(row.changeType) }}</template><template #cell-warnType="{ row }">{{ groupLabel(row.warnType) }}</template><template #cell-fromStatus="{ row }">{{ groupLabel(row.fromStatus) }}</template><template #cell-toStatus="{ row }">{{ groupLabel(row.toStatus) }}</template></DataTable>
        </section>
      </template>
      <template v-else-if="isMetricTab">
        <p v-if="tab === 'registration'" class="stats-applied">按注册记录统计，同一学生跨批次分别计数。</p>
        <p v-if="tab === 'teachingTask'" class="stats-applied">本专题按教师确认时间是否已记录统计；缺少确认时间的历史任务仍可能显示“已就绪”。请核对确认依据，不据此重复要求教师确认或补写时间。</p>
        <section v-if="tab === 'teachingTask' && pendingTaskCount > 0" class="stats-attention"><strong>{{ numberLabel(pendingTaskCount) }} 条教学任务缺少确认时间记录</strong><AppButton variant="primary" @click="openDetail">核对确认依据</AppButton></section>
        <div class="stats-analysis-grid" :class="{ 'has-secondary': tab === 'grade' }">
          <section class="stats-analysis-panel">
            <header><h2>{{ distributionTitle }}</h2><AppButton v-if="canOpenCurrentDetail && !['registration', 'teachingTask', 'grade'].includes(tab)" size="small" variant="ghost" @click="openDetail">{{ detailActionLabel }}</AppButton></header>
            <div class="stats-distribution-body" :class="{ 'side-by-side': analyticsHasServerGroups }">
            <div v-if="compositionTotal !== null && compositionTotal > 0" class="stats-completion">
              <progress :value="analyticsDistribution[0].value" :max="compositionTotal" :aria-label="distributionTitle" />
              <div class="stats-completion-labels"><span v-for="row in analyticsLedgerRows" :key="row.rowKey">{{ row.metric }} {{ row.value }} <small>{{ row.share }}</small></span></div>
            </div>
            <AppG2Chart v-else-if="analyticsDistribution.length && analyticsHasServerGroups" :spec="analyticsDistributionSpec" :height="240" />
            <p v-else-if="!analyticsDistribution.length" class="stats-applied">本次未提供分组数据，汇总指标仍保留原值。</p>
            <DataTable v-if="analyticsLedgerRows.length" :columns="analyticsLedgerColumns" :rows="analyticsLedgerRows" row-key="rowKey">
              <template #cell-action="{ row }"><AppButton v-if="row.canDetail" size="small" variant="ghost" @click="openDetail">{{ detailActionLabel }}</AppButton><span v-else class="stats-cell-note">汇总</span></template>
            </DataTable>
            </div>
          </section>
          <section v-if="tab === 'grade'" class="stats-analysis-panel stats-grade-publish"><header><h2>成绩任务发布</h2></header><strong>{{ percentage(sSummary.entryPublishRate) }}</strong><p>已发布 {{ numberLabel(sSummary.publishNumerator) }} / 共 {{ numberLabel(sSummary.publishDenominator) }} 个任务</p><p class="stats-applied">按成绩任务计数，与成绩记录分开展示。</p></section>
        </div>
        <form v-if="tab === 'grade'" class="stats-detail-filter" @submit.prevent="searchGradeDetail"><label>课程名称（仅筛选明细）<input v-model="detailCourseName" class="aa-input" placeholder="输入课程名称" /></label><AppButton type="submit" variant="primary">查看不及格明细</AppButton></form>
      </template>
      <template v-else-if="tab === 'workload'">
        <p class="stats-applied">用于教学安排参考，不作为绩效结算依据。</p>
        <section class="stats-analysis-panel">
          <header><h2>教师工作量明细</h2><label>搜索教师<input v-model="workloadSearch" class="aa-input" placeholder="教师姓名" @input="workloadPage = 1" /></label></header>
          <EmptyState v-if="!filteredWorkload.length" @back="workloadSearch ? workloadSearch = '' : resetFilters()" :title="workloadSearch ? '没有匹配的教师' : '当前范围没有教学任务'" description="请核对学期、学院或教师检索条件。" />
          <DataTable v-else :columns="workloadColumns" :rows="workloadRows" row-key="teacherKey" :pagination="workloadPagination" @page-change="workloadPage = $event"><template #cell-taskCount="{ row }">{{ numberLabel(row.taskCount) }}</template><template #cell-totalHours="{ row }">{{ numberLabel(row.combinedHours ?? row.totalHours) }}</template><template #cell-ops="{ row }"><AppButton size="small" variant="ghost" @click="viewWorkloadDetail(row)">查看明细</AppButton></template></DataTable>
        </section>
      </template>
      <AaStatsSnapshotWorkspace v-else-if="tab === 'snapshot'" :ctx="ctx" :context-filters="appliedFilters" />
      <template v-else-if="tab === 'export'">
        <section class="stats-analysis-panel stats-export-card">
          <header><h2>导出范围与用途</h2></header>
          <div class="aa-export-form"><label>导出维度<AppSelect v-model="exp.domain" :options="exportDomainOptions" /></label><label>学期<AppTermEntityPicker v-model="exp.termId" placeholder="全部学期" /></label><label>学院<AppCollegePicker v-model="exp.collegeId" placeholder="全部学院" /></label><label class="stats-export-purpose">导出用途（至少5个字）<textarea v-model="exp.purpose" rows="3" maxlength="500" placeholder="如：教务处月度汇报" /></label></div>
          <footer><span>按当前权限与所选范围导出全部结果。</span><AppButton variant="primary" :loading="exp.downloading" @click="doExport">生成并下载表格</AppButton></footer>
          <p v-if="exp.receipt" class="stats-export-result" role="status">{{ exp.receipt.fileName }} · {{ exp.receipt.completedAt }} 已收到系统生成的表格文件</p>
          <p v-else class="stats-applied">尚未生成文件。</p>
        </section>
      </template>
      <section v-if="detail.open" class="aa-drill">
        <header><h2>{{ detail.title }}</h2><AppButton variant="ghost" @click="closeDetail">收起</AppButton></header>
        <LoadingState v-if="detail.loading" /><ErrorState v-else-if="detail.error" :description="detail.error" @retry="loadDetail" @back="closeDetail" /><EmptyState v-else-if="!detail.rows.length" @back="closeDetail" title="当前范围没有明细" description="可调整查询条件后再查看。" />
        <DataTable v-else :columns="detail.columns" :rows="detail.rows" row-key="rowKey" :pagination="detail.pagination" @page-change="onDetailPage"><template #cell-taskSource="{ row }"><AppButton v-if="canOpenTaskSource(row)" size="small" variant="ghost" @click="openTaskSource(row)">核对原任务</AppButton><span v-else>请由教学任务管理岗核对</span></template><template #cell-status="{ row }">{{ groupLabel(row.status) }}</template><template #cell-category="{ row }">{{ groupLabel(row.category) }}</template><template #cell-level="{ row }">{{ groupLabel(row.level) }}</template><template #cell-warnType="{ row }">{{ groupLabel(row.warnType) }}</template><template #cell-incidentType="{ row }">{{ groupLabel(row.incidentType) }}</template><template #cell-abnormalItems="{ row }">{{ (row.abnormalItems || []).map(groupLabel).join('、') }}</template><template #cell-weekParity="{ row }">{{ groupLabel(row.weekParity) }}</template><template #cell-courses="{ row }">{{ (row.courses || []).map(c => c.courseName).join('、') }}</template><template #cell-changeType="{ row }">{{ groupLabel(row.changeType) }}</template><template #cell-fromStatus="{ row }">{{ groupLabel(row.fromStatus) }}</template><template #cell-toStatus="{ row }">{{ groupLabel(row.toStatus) }}</template></DataTable>
      </section>
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * 教务统计（/admin/academic-affairs/stats，`?tab=` 深链接切换三级 Tab）。
 * 数据全部来自真实后端 /api/v1/academic-affairs/stats/*（无 mock）；范围/脱敏/审计由后端裁定。
 * Tab 结构：overview（既有实现原样保留）+ 02/03/04/05/06/10/11/12/13/15 号卡（10 项）+
 * 08/09/14 号卡（选课/考务/教学资源统计，2026-07-16 第三轮续工新增，底层模块已真实建成）。
 * 07 调停课统计不在本页 Tab 内：其完整交互（本人课位自助视角）在独立页面
 * /admin/academic-affairs/schedule-change/stats（navPlan 直接指向该页），本页总览 Tab 的
 * 「调停课统计」卡片是学校/学院口径的全局计数，两者互不冲突（见后端 stats_service 模块头注释）。
 */
import { academicRoleAllows } from '../config/academicRoleNavigation'
import {
  AppG2Chart, AppSelect,
  AppTermEntityPicker, AppCollegePicker, AppMajorPicker, AppGraduationBatchPicker
} from '@/components/common'
import { AppButton } from '@/components/ui'
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { STATS_TOPICS, statsTopic } from '@/modules/academicAffairs/config/academicNavigation.js'
import { matchPermission } from '@/config/navPlan.js'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaStatsSnapshotWorkspace from '@/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../academicFlowContext'
import { formatDateTime } from '@/utils/dateUtils'
import { COURSE_CATEGORY } from '../constants/course-program'
import { GRAD_ITEM_LABEL } from '../constants/grade-graduation'
import { statsGroupLabel, STATS_INDICATOR_TOPICS } from './parallel-c/stats-presentation.js'

const TABS = [
  { key: 'overview', label: '教务总览' },
  { key: 'statusChange', label: '学籍统计' },
  { key: 'registration', label: '注册统计' },
  { key: 'course', label: '课程统计' },
  { key: 'teachingTask', label: '教学任务统计' },
  { key: 'schedule', label: '课表统计' },
  { key: 'courseSelection', label: '选课统计' },
  { key: 'exam', label: '考务统计' },
  { key: 'grade', label: '成绩统计' },
  { key: 'warning', label: '学业预警统计' },
  { key: 'graduation', label: '毕业资格统计' },
  { key: 'workload', label: '教师工作量统计' },
  { key: 'resource', label: '教学资源统计' },
  { key: 'snapshot', label: '统计快照' },
  { key: 'export', label: '导出报表' }
]

const STATS_PAGE_META = {
  overview: { id: 'AA-242', title: '统计总览', subtitle: '核对教务运行指标的来源、范围与更新时间', primary: '下钻当前指标' },
  statusChange: { id: 'AA-243', title: '学籍统计', subtitle: '按正式生效结果核对学籍异动，不把申请量当作异动结果', primary: '下钻学籍明细' },
  registration: { id: 'AA-244', aliases: ['AA-258'], title: '学籍与注册', subtitle: '明确注册类型、学期和当前授权范围', primary: '查看未完成明细' },
  course: { id: 'AA-245', title: '开课与教学运行', subtitle: '按课程供给和启用状态核对本期教学运行', primary: '下钻教学任务' },
  teachingTask: { id: 'AA-246', title: '教学任务统计', subtitle: '核对教师确认时间记录与任务业务状态', primary: '核对确认依据' },
  schedule: { id: 'AA-247', title: '课表统计', subtitle: '依据正式课表批次核对发布覆盖与冲突', primary: '查看课表版本' },
  courseSelection: { id: 'AA-249', title: '选课统计', subtitle: '按批次核对容量、报名与名单状态', primary: '查看名单状态' },
  exam: { id: 'AA-250', title: '考试与成绩', subtitle: '核对考试课程编排完成度与正式异常记录', primary: '下钻考务明细' },
  grade: { id: 'AA-251', aliases: ['AA-259'], title: '成绩统计', subtitle: '只统计正式有效成绩，挂科人数不冒充预警条数', primary: '查看不及格明细' },
  warning: { id: 'AA-252', title: '学业与毕业', subtitle: '核对未闭环预警与毕业审核风险', primary: '查看风险明细' },
  graduation: { id: 'AA-253', title: '毕业资格统计', subtitle: '按批次与当前权限范围核对毕业决定', primary: '查看毕业决定' },
  workload: { id: 'AA-254', title: '师资与资源', subtitle: '教学任务工作量仅作安排参考，正式核算以学校规则为准', primary: '下钻工作量' },
  resource: { id: 'AA-255', title: '教学资源统计', subtitle: '按当前授权范围核对教室与预约占用', primary: '下钻资源占用' },
  export: { id: 'AA-256', title: '报表与快照', subtitle: '申请统计导出并记录用途、范围和作业结果', primary: '申请统计导出' },
  snapshot: { id: 'AA-257', title: '统计快照', subtitle: '冻结同一统计口径，保留指标版本和保存时间', primary: '保存统计快照' }
}

// AA-248 使用独立正式地址和 AaScheduleChangeStatsView.vue，避免把调停课个人课位统计混进本页汇总接口。

const STATUS_NAMES = {
  REGISTERED: '已注册', UNREGISTERED: '未注册', PENDING: '待处理', CONFIRMED: '已确认',
  PUBLISHED: '已发布', OPEN: '开放', CLOSED: '已关闭', ACTIVE: '生效', FINISHED: '已完成',
  makeup: '补考', retake: '重修', conflict: '硬冲突', HIGH: '高风险', MEDIUM: '中风险',
  LOW: '低风险', UNKNOWN: '未分类', AVAILABLE: '可用', MAINTENANCE: '维修中', DISABLED: '停用', VIOLATION: '违纪', PENDING_REGISTER: '待注册'
}

function percent(value) {
  const n = numeric(value)
  return n === null ? '—' : `${n}%`
}

function numeric(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  return typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value.trim()) ? Number(value) : null
}
function remaining(total, done) { return numeric(total) === null || numeric(done) === null ? null : Math.max(0, numeric(total) - numeric(done)) }
function countLabel(value, unit = '') { const n = numeric(value); return n === null ? '—' : `${n.toLocaleString('zh-CN')}${unit}` }
function ratioLabel(numerator, denominator) { const n = numeric(numerator), d = numeric(denominator); return n === null || d === null || d <= 0 ? '—' : `${Math.round(n / d * 1000) / 10}%` }
function basis(n, d) { return `${countLabel(n)} / ${countLabel(d)}` }
function metricCards(tab, x) {
  const card = (label, value, unit = '', note = '', tone = '') => ({ label, value, unit, note, tone })
  const maps = {
    statusChange: [card('已生效异动', numeric(x.total), '条')],
    registration: [card('统计注册记录', numeric(x.expected), '条'), card('已完成注册', numeric(x.registered), '条'), card('未完成注册', remaining(x.expected, x.registered), '条', '', 'warning'), card('完成率', percent(x.rate), '', basis(x.registered, x.expected))],
    course: [card('启用课程', numeric(x.total), '门'), card('覆盖学院', Array.isArray(x.byCollege) ? x.byCollege.length : null, '个')],
    teachingTask: [card('任务总数', numeric(x.expected), '项'), card('已记录确认时间', numeric(x.confirmed), '项'), card('缺少确认时间', remaining(x.expected, x.confirmed), '项', '', 'warning'), card('确认时间记录率', percent(x.rate), '', basis(x.confirmed, x.expected))],
    schedule: [card('课表批次', numeric(x.totalBatches), '个'), card('已发布批次', numeric(x.published), '个'), card('未解决冲突', numeric(x.unresolvedConflicts), '条', '', 'warning'), card('发布率', percent(x.publishedRate), '', basis(x.published, x.totalBatches))],
    courseSelection: [card('选课容量', numeric(x.totalCapacity ?? x.capacity), '人次'), card('已选', numeric(x.totalSelected ?? x.selected), '人次'), card('低人数课程', numeric(x.lowEnrollCount), '门', '', 'warning'), card('填充率', percent(x.fillRate), '', basis(x.totalSelected ?? x.selected, x.totalCapacity ?? x.capacity))],
    exam: [card('应考课程', numeric(x.courseTotal ?? x.confirmedCourses), '门'), card('已完成编排', numeric(x.confirmedCount ?? x.arranged), '门'), card('缺考与违纪', numeric(x.absentCount) === null || numeric(x.violationCount) === null ? null : numeric(x.absentCount) + numeric(x.violationCount), '条', '', 'warning'), card('编排完成率', percent(x.confirmRate ?? x.rate), '', basis(x.confirmedCount ?? x.arranged, x.courseTotal ?? x.confirmedCourses))],
    grade: [card('有效成绩记录', numeric(x.failDenominator), '条'), card('不及格成绩记录', numeric(x.failNumerator), '条', '', 'warning'), card('不及格占比', ratioLabel(x.failNumerator, x.failDenominator), '', basis(x.failNumerator, x.failDenominator))],
    warning: [card('未闭环预警', numeric(x.total), '条', '排除已关闭预警'), ...(x.byLevel || []).map(g => card(STATUS_NAMES[g.key] || statsGroupLabel(g), numeric(g.count), '条', '', g.key === 'LOW' ? '' : 'warning'))],
    graduation: [card('应审人数', numeric(x.expected), '人'), card('已通过', numeric(x.passed), '人'), card('待核或异常', remaining(x.expected, x.passed), '人', '', 'warning'), card('通过率', percent(x.passRate), '', basis(x.passed, x.expected))],
    resource: [card(x.classroomTotal != null ? '教室总数' : '可用教室', numeric(x.classroomTotal ?? x.availableRooms), '间', '资源状态不代表时段空闲'), card('待审预约', numeric(x.pendingBookings ?? x.bookingTotal), '条', '', 'warning')]
  }
  return maps[tab] || []
}

const DRILL_META = {
  registration: {
    title: '未注册学生名单',
    columns: [
      { key: 'studentName', title: '学生' },
      { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'status', title: '注册状态' }
    ],
    fetch: (api, p) => api.getStatsRegistration(p)
  },
  statusChange: {
    title: '学籍异动明细',
    columns: [
      { key: 'studentName', title: '学生' },
      { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'changeType', title: '异动类型' },
      { key: 'fromStatus', title: '原状态' },
      { key: 'toStatus', title: '现状态' }
    ],
    fetch: (api, p) => api.getStatsStatusChange(p)
  },
  warning: {
    title: '学业预警明细',
    columns: [
      { key: 'studentName', title: '学生' },
      { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'className', title: '班级' },
      { key: 'level', title: '等级' },
      { key: 'warnType', title: '类型' },
      { key: 'status', title: '状态' }
    ],
    fetch: (api, p) => api.getStatsWarning(p)
  }
}

/** 8 个 Tab 共用的通用下钻明细配置（summary 聚合 + detail 明细）。 */
const TAB_META = {
  statusChange: {
    summary: (api, p) => api.getStatsStatusChangeSummary(p),
    detailTitle: '学籍异动明细',
    detailColumns: [
      { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'changeType', title: '异动类型' }, { key: 'fromStatus', title: '原状态' }, { key: 'toStatus', title: '现状态' }
    ],
    detailFetch: (api, p) => api.getStatsStatusChange(p)
  },
  registration: {
    summary: (api, p) => api.getStatsRegistrationSummary(p),
    detailTitle: '未注册学生名单',
    detailColumns: [
      { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号（脱敏）' }, { key: 'status', title: '注册状态' }
    ],
    detailFetch: (api, p) => api.getStatsRegistration(p)
  },
  course: {
    summary: (api, p) => api.getStatsCourse(p),
    detailTitle: '课程明细',
    detailColumns: [
      { key: 'courseCode', title: '课程代码' }, { key: 'courseName', title: '课程名称' },
      { key: 'category', title: '类别' }, { key: 'credit', title: '学分' }, { key: 'hoursTotal', title: '总学时' }
    ],
    detailFetch: (api, p) => api.getStatsCourseDetail(p)
  },
  teachingTask: {
    summary: (api, p) => api.getStatsTeachingTask(p),
    detailTitle: '缺少确认时间的教学任务',
    detailColumns: [
      { key: 'courseName', title: '课程' }, { key: 'teachingClassName', title: '教学班' },
      { key: 'teacherName', title: '教师' }, { key: 'status', title: '业务状态' },
      { key: 'confirmationEvidence', title: '确认依据' }, { key: 'taskSource', title: '处理入口' }
    ],
    detailFetch: (api, p) => api.getStatsTeachingTaskPending(p)
  },
  schedule: {
    summary: (api, p) => api.getStatsSchedule(p),
    detailTitle: '课表冲突明细',
    detailColumns: [
      { key: 'className', title: '班级' }, { key: 'weekday', title: '星期' }, { key: 'slotNo', title: '节次' },
      { key: 'weekParity', title: '单双周' }, { key: 'conflictCount', title: '冲突数' }, { key: 'courses', title: '涉及课程' }
    ],
    detailFetch: (api, p) => api.getStatsScheduleConflicts(p)
  },
  grade: {
    summary: (api, p) => api.getStatsGrade(p),
    detailTitle: '挂科学生明细',
    detailColumns: [
      { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'courseName', title: '课程' }, { key: 'term', title: '学期' }, { key: 'score', title: '分数' }
    ],
    detailFetch: (api, p) => api.getStatsGradeDetail({ ...p, courseName: p.courseName || undefined })
  },
  warning: {
    summary: (api, p) => api.getStatsWarningSummary(p),
    detailTitle: '学业预警明细',
    detailColumns: [
      { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号（脱敏）' }, { key: 'className', title: '班级' },
      { key: 'level', title: '等级' }, { key: 'warnType', title: '类型' }, { key: 'status', title: '状态' }
    ],
    detailFetch: (api, p) => api.getStatsWarning(p)
  },
  graduation: {
    summary: (api, p) => api.getStatsGraduation(p),
    detailTitle: '毕业资格异常学生名单',
    detailColumns: [
      { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号（脱敏）' },
      { key: 'abnormalItems', title: '异常项' }, { key: 'status', title: '批次状态' }
    ],
    detailFetch: (api, p) => api.getStatsGraduationAbnormal(p)
  },
  courseSelection: {
    summary: (api, p) => api.getStatsCourseSelection(p),
    detailTitle: '低人数课程清单',
    detailColumns: [
      { key: 'batchName', title: '批次' }, { key: 'courseName', title: '课程' }, { key: 'teacherName', title: '教师' },
      { key: 'capacity', title: '容量' }, { key: 'minCapacity', title: '开课下限' }, { key: 'selectedCount', title: '已选' }
    ],
    detailFetch: (api, p) => api.getStatsCourseSelectionDetail(p)
  },
  exam: {
    summary: (api, p) => api.getStatsExam(p),
    detailTitle: '缺考/违纪明细',
    detailColumns: [
      { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号（脱敏）' }, { key: 'incidentType', title: '类型' }
    ],
    detailFetch: (api, p) => api.getStatsExamDetail(p)
  },
  resource: {
    summary: (api, p) => api.getStatsResource(p),
    detailTitle: '待审核教室预约',
    detailColumns: [
      { key: 'classroomText', title: '教室' }, { key: 'bookingDate', title: '日期' }, { key: 'slotNo', title: '节次' },
      { key: 'applicantName', title: '申请人' }, { key: 'purpose', title: '用途' }
    ],
    detailFetch: (api, p) => api.getStatsResourceDetail(p)
  }
}

const EXPORT_DOMAINS = [
  { key: 'overview', label: '教务总览' }, { key: 'statusChange', label: '学籍统计' },
  { key: 'registration', label: '注册统计' }, { key: 'course', label: '课程统计' },
  { key: 'teachingTask', label: '教学任务统计' }, { key: 'schedule', label: '课表统计' },
  { key: 'courseSelection', label: '选课统计' }, { key: 'exam', label: '考务统计' },
  { key: 'grade', label: '成绩统计' }, { key: 'warning', label: '学业预警统计' },
  { key: 'graduation', label: '毕业资格统计' }, { key: 'workload', label: '教师工作量统计' },
  { key: 'resource', label: '教学资源统计' }
]

export default {
  name: 'AaStatsOverviewView',
  inject: { academicFlow: { default: null } },
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton,
    AppG2Chart, AppSelect, AppTermEntityPicker,
    AppCollegePicker, AppMajorPicker, AppGraduationBatchPicker, AaStatsSnapshotWorkspace
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TABS, STATS_TOPICS, requestId: 0, detailRequestId: 0, exportRequestId: 0, updatedAt: '',
      sourceAsOf: '', overviewMetricKey: '',
      overviewColumns: [{ key: 'sectionLabel', title: '业务主题' }, { key: 'label', title: '指标' }, { key: 'value', title: '当前值' }, { key: 'basis', title: '统计基数' }, { key: 'action', title: '查看' }],
      tab: 'overview',
      loading: true,
      error: '',
      filters: { termId: '', collegeId: '', majorId: '', category: '', courseName: '', batchId: '', itemType: '' },
      appliedFilters: { termId: '', collegeId: '', majorId: '', category: '', courseName: '', batchId: '', itemType: '' },
      // 教务总览（既有）
      indicators: [],
      scopeBlocked: false,
      activeDrill: '',
      drill: { error: '', loading: false, rows: [], pagination: { page: 1, pageSize: 20, total: 0 } },
      // 其余 9 个 Tab 的聚合结果
      sSummary: {},
      // 通用下钻明细面板（8 个 Tab 共用）
      detail: { error: '', open: false, loading: false, title: '', rows: [], columns: [], pagination: { page: 1, pageSize: 20, total: 0 } },
      // 导出报表
      exp: { domain: 'overview', termId: '', collegeId: '', purpose: '', downloading: false, receipt: null },
      workloadTeacherKey: '', workloadSearch: '', workloadPage: 1, detailCourseName: '', filterLabels: {},
      workloadColumns: [
        { key: 'teacherName', title: '教师' }, { key: 'taskCount', title: '教学任务数（项）' },
        { key: 'totalHours', title: '计划学时（学时）' }, { key: 'ops', title: '查看' }
      ]
    }
  },
  computed: {
    statsPage() { return STATS_PAGE_META[this.tab] || STATS_PAGE_META.overview },
    isMetricTab() { return !!TAB_META[this.tab] && this.tab !== 'overview' },
    canOpenCurrentDetail() { return !!TAB_META[this.tab]?.detailFetch },
    courseCategoryOptions() { return [{ value: '', label: '全部类别' }, ...Object.entries(COURSE_CATEGORY).map(([value, label]) => ({ value, label }))] },
    sourceTimeLabel() { return this.sourceAsOf ? formatDateTime(this.sourceAsOf, '时间待核对') : '未提供' },
    analyticsCards() {
      if (['export', 'snapshot'].includes(this.tab)) return []
      if (this.tab === 'overview') return ['registration', 'teachingTask', 'schedule', 'gradePublish'].map(key => this.indicators.find(x => x.key === key)).filter(Boolean).map(x => ({ label: this.indicatorLabel(x), value: this.indicatorValue(x), note: this.indicatorBasis(x) }))
      if (this.tab === 'workload') {
        const rows = this.sSummary.ranking
        const sum = key => !Array.isArray(rows) || rows.some(r => numeric(r[key]) === null) ? null : rows.reduce((n, r) => n + numeric(r[key]), 0)
        const hours = !Array.isArray(rows) || rows.some(r => numeric(r.combinedHours ?? r.totalHours) === null) ? null : rows.reduce((n, r) => n + numeric(r.combinedHours ?? r.totalHours), 0)
        return [{ label: '授课教师', value: Array.isArray(rows) ? rows.length : null, unit: '人' }, { label: '教学任务（按教师汇总）', value: sum('taskCount'), unit: '项' }, { label: '计划学时', value: hours, unit: '学时' }]
      }
      return metricCards(this.tab, this.sSummary)
    },
    attentionItems() {
      return ['registration', 'teachingTask', 'warning'].map(key => {
        const item = this.indicators.find(x => x.key === key && x.status !== 'MODULE_NOT_ENABLED')
        if (!item) return null
        const value = key === 'warning' ? numeric(item.value) : remaining(item.denominator, item.numerator)
        return value > 0 ? { ...item, attentionValue: value, attentionLabel: { registration: '未完成注册记录', teachingTask: '缺少确认时间的教学任务', warning: '未闭环预警' }[key] } : null
      }).filter(Boolean)
    },
    pendingTaskCount() { return remaining(this.sSummary.expected, this.sSummary.confirmed) },
    distributionTitle() { return { registration: '注册完成情况', teachingTask: '确认情况', grade: '成绩记录分布', warning: '风险分布', resource: '资源状态分布', graduation: '资格审核结果' }[this.tab] || `${this.statsPage.title} · 分布` },
    detailActionLabel() { return { registration: '查看未完成明细', teachingTask: '核对确认依据', grade: '查看不及格明细', schedule: '查看冲突明细', exam: '查看缺考与违纪明细', courseSelection: '查看低人数课程', resource: '查看待审预约', warning: '查看预警明细', graduation: '查看异常明细', course: '查看课程明细', statusChange: '查看异动明细' }[this.tab] || '查看明细' },
    analyticsDistribution() {
      const x = this.sSummary
      const groups = [x.byType, x.byCategory, x.byStatus, x.byLevel, x.byBatchStatus, x.byAbnormalItem, x.byRoomType, x.bySource].find(rows => Array.isArray(rows) && rows.length)
      if (groups) return groups.filter(g => numeric(g.count) !== null).map(g => ({ name: g.label ? statsGroupLabel(g) : this.groupLabel(g.key), value: numeric(g.count) }))
      const pairs = {
        registration: [['已完成注册', x.registered], ['未完成注册', remaining(x.expected, x.registered)]],
        teachingTask: [['已记录确认时间', x.confirmed], ['缺少确认时间', remaining(x.expected, x.confirmed)]],
        schedule: [['已发布批次', x.published], ['其他批次', remaining(x.totalBatches, x.published)]],
        courseSelection: [['已选人次', x.totalSelected ?? x.selected], ['剩余容量', remaining(x.totalCapacity ?? x.capacity, x.totalSelected ?? x.selected)]],
        exam: [['已完成编排', x.confirmedCount ?? x.arranged], ['待编排', remaining(x.courseTotal ?? x.confirmedCourses, x.confirmedCount ?? x.arranged)]],
        grade: [['及格记录', remaining(x.failDenominator, x.failNumerator)], ['不及格记录', x.failNumerator]],
        graduation: [['已通过', x.passed], ['待核或异常', remaining(x.expected, x.passed)]]
      }
      const rows = pairs[this.tab]
      return rows && rows.every(([, value]) => numeric(value) !== null) ? rows.map(([name, value]) => ({ name, value: numeric(value) })) : []
    },
    analyticsHasServerGroups() { return [this.sSummary.byType, this.sSummary.byCategory, this.sSummary.byStatus, this.sSummary.byLevel, this.sSummary.byBatchStatus, this.sSummary.byAbnormalItem, this.sSummary.byRoomType, this.sSummary.bySource].some(rows => Array.isArray(rows) && rows.length) },
    compositionTotal() {
      if (this.analyticsHasServerGroups || !['registration', 'teachingTask', 'grade', 'graduation', 'courseSelection'].includes(this.tab) || this.analyticsDistribution.length !== 2) return null
      return this.analyticsDistribution.reduce((n, row) => n + row.value, 0)
    },
    analyticsDistributionSpec() {
      const riskColors = this.tab === 'warning' ? { legend: false, scale: { color: { range: this.analyticsDistribution.map(row => row.name === '低风险' ? '#2b5eb4' : row.name === '中风险' ? '#b76700' : '#c23232') } } } : {}
      return { type: 'interval', data: this.analyticsDistribution, encode: { x: 'name', y: 'value', ...(this.tab === 'warning' ? { color: 'name' } : {}) }, coordinate: { transform: [{ type: 'transpose' }] }, axis: { x: { title: null }, y: { title: null } }, ...riskColors }
    },
    ledgerTotal() { return this.compositionTotal ?? (this.tab === 'warning' && this.sSummary.byLevel?.length ? numeric(this.sSummary.total) : null) },
    analyticsLedgerColumns() { return [{ key: 'metric', title: '统计项' }, { key: 'value', title: '当前值' }, ...(this.ledgerTotal !== null ? [{ key: 'share', title: '占比' }] : []), { key: 'action', title: '查看' }] },
    analyticsLedgerRows() {
      const units = { course: '门', registration: '条', teachingTask: '项', schedule: '个', grade: '条', warning: '条', graduation: '人', resource: '间', exam: '门', courseSelection: '人次', statusChange: '条' }
      const target = { registration: '未完成注册', teachingTask: '缺少确认时间', grade: '不及格记录' }[this.tab]
      const unit = this.tab === 'courseSelection' && this.sSummary.byBatchStatus?.length ? '个批次' : this.tab === 'graduation' && this.sSummary.byAbnormalItem?.length ? '项' : units[this.tab] || ''
      return this.analyticsDistribution.map((r, i) => ({ rowKey: `${this.tab}-${i}-${r.name}`, metric: r.name, value: countLabel(r.value, unit), share: ratioLabel(r.value, this.ledgerTotal), canDetail: this.canOpenCurrentDetail && r.name === target }))
    },
    // shortcut: 仅检索当前接口已返回的授权汇总；接口提供分页契约后改为服务端查询。
    filteredWorkload() { const q = this.workloadSearch.trim().toLocaleLowerCase(); return (this.sSummary.ranking || []).filter(r => !q || String(r.teacherName || '').toLocaleLowerCase().includes(q)) },
    workloadRows() { return this.filteredWorkload.slice((this.workloadPagination.page - 1) * 20, this.workloadPagination.page * 20) },
    workloadPagination() { return { page: Math.min(Math.max(1, this.workloadPage), Math.max(1, Math.ceil(this.filteredWorkload.length / 20))), pageSize: 20, total: this.filteredWorkload.length } },
    overviewRows() { return this.overviewSections.flatMap(section => section.items.map(item => ({ ...item, sectionLabel: section.label }))) },
    distributionOptions() { return this.indicators.filter(item => item.status !== 'MODULE_NOT_ENABLED' && Array.isArray(item.groups) && item.groups.some(group => typeof group.count === 'number' && Number.isFinite(group.count))) },
    distributionMetric() { return this.distributionOptions.find(item => item.key === this.overviewMetricKey) || this.distributionOptions[0] || null },
    overviewDistributionSpec() {
      return { type: 'interval', data: (this.distributionMetric?.groups || []).filter(group => typeof group.count === 'number' && Number.isFinite(group.count)).map(group => ({ name: statsGroupLabel(group), value: group.count })), encode: { x: 'name', y: 'value' }, coordinate: { transform: [{ type: 'transpose' }] }, axis: { y: { title: null }, x: { title: null } } }
    },
    appliedScopeLabel() {
      if (this.tab === 'resource') return this.ctx.dataScope?.scopeName || '当前授权资源范围'
      return [['termId', '学期', '默认学期口径'], ['collegeId', '学院', '全部授权学院'], ...(['overview', 'registration'].includes(this.tab) ? [['majorId', '专业', '全部专业']] : [])].map(([key, title, empty]) => {
        const value = this.appliedFilters[key], saved = this.filterLabels[key]
        return value ? saved?.value === String(value) && saved.label ? saved.label : `已选${title}` : empty
      }).join(' · ')
    },
    filtersDirty() { return JSON.stringify(this.filters) !== JSON.stringify(this.appliedFilters) },
    contextSignature() { return JSON.stringify([this.ctx.ctxKey, this.ctx.permissionPatterns, this.ctx.dataScope, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    canExport() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.stats.export') },
    canViewSnapshot() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.stats.snapshot.view') },
    visibleTopics() { return STATS_TOPICS.filter(topic => topic.tabs.some(tab => this.allowedTab(tab))) },
    currentTopic() { return statsTopic(this.tab) },
    topicTabs() { return TABS.filter(item => this.currentTopic.tabs.includes(item.key) && this.allowedTab(item.key)) },
    overviewSections() {
      const groups = [
        { key: 'preparation', label: '开学与教学准备', description: '培养方案 · 开课任务 · 课表', keys: ['registration', 'program', 'course', 'teachingTask', 'schedule'] },
        { key: 'teaching', label: '教学运行', description: '选课 · 调停课 · 考试 · 资源', keys: ['courseSelection', 'scheduleChange', 'exam', 'resource'] },
        { key: 'achievement', label: '学业与毕业', description: '成绩 · 学籍 · 学业风险 · 毕业资格', keys: ['gradePublish', 'failRate', 'makeupRetake', 'statusChange', 'warning', 'graduation'] }
      ]
      const known = new Set(groups.flatMap(group => group.keys))
      return [...groups.map(group => ({ ...group, items: this.indicators.filter(item => group.keys.includes(item.key)) })),
        { key: 'other', label: '其他统计', description: '', items: this.indicators.filter(item => !known.has(item.key)) }].filter(group => group.items.length)
    },
    exportDomainOptions() { return EXPORT_DOMAINS.map((d) => ({ value: d.key, label: d.label })) },
    drillTitle() {
      return this.activeDrill ? (DRILL_META[this.activeDrill]?.title || '明细') : ''
    },
    drillColumns() {
      return this.activeDrill ? (DRILL_META[this.activeDrill]?.columns || []) : []
    }
  },
  created() { this.restoreRoute() },
  beforeUnmount() { this.requestId++; this.detailRequestId++; this.exportRequestId++ },
  watch: {
    '$route.query': { deep: true, handler() { this.restoreRoute() } },
    contextSignature() {
      this.requestId++; this.detailRequestId++; this.exportRequestId++
      this.updatedAt = ''; this.detail.open = false; this.detail.rows = []; this.drill.rows = []
      this.activeDrill = ''; this.workloadSearch = ''; this.workloadPage = 1; this.filterLabels = {}; this.workloadTeacherKey = ''; this.exp.purpose = ''; this.exp.downloading = false; this.exp.receipt = null
      this.loadTab()
    }
  },
  methods: {
    numberLabel: countLabel,
    percentage: percent,
    groupLabel(value) { return value == null || value === '' ? '未提供' : STATUS_NAMES[value] || GRAD_ITEM_LABEL[value] || statsGroupLabel({ key: value }) },
    displayMetric(card) { return typeof card.value === 'string' ? card.value : countLabel(card.value) },
    indicatorLabel(item) { return { teachingTask: '教学任务确认率', gradePublish: '成绩任务发布率', failRate: '不及格成绩记录占比' }[item.key] || item.label },
    indicatorBasis(item) { return item.unit === '%' && numeric(item.denominator) !== null ? numeric(item.denominator) === 0 ? '暂无统计基数' : basis(item.numerator, item.denominator) : '—' },
    rememberFilter(key, value, items) { const item = Array.isArray(items) ? items[0] : items; this.filterLabels[key] = { value: String(value || ''), label: typeof item?.label === 'string' ? item.label : '' } },
    collegeChanged(value, items) { this.rememberFilter('collegeId', value, items); this.filters.majorId = ''; delete this.filterLabels.majorId },
    resetFilters() { for (const key of Object.keys(this.filters)) this.filters[key] = ''; this.filterLabels = {}; this.detailCourseName = ''; this.search() },
    searchGradeDetail() {
      this.filters = { ...this.appliedFilters, courseName: this.detailCourseName.trim() }
      const query = { ...this.routeQuery(), detail: '1' }
      if (JSON.stringify(query) === JSON.stringify(this.$route.query)) { this.detail.pagination.page = 1; return this.loadDetail() }
      return this.$router.push({ path: this.$route.path, query })
    },
    indicatorValue(item) {
      if (item.status === 'MODULE_NOT_ENABLED') return '未启用'
      const value = item.unit === '%' ? item.rate : item.value
      return typeof value === 'number' && Number.isFinite(value) ? `${value}${item.unit || ''}` : '—'
    },
    identity() { return academicIdentity(currentUserFromToken(), this.ctx) },
    allowedTab(tab) {
      return academicRoleAllows({ path: '/admin/academic-affairs/stats', query: { tab } }, this.ctx)
        && (tab === 'export' ? this.canExport : tab === 'snapshot' ? this.canViewSnapshot : true)
    },
    restoreRoute() {
      const query = this.$route.query || {}
      const previous = JSON.stringify([this.tab, this.appliedFilters])
      this.tab = TABS.some(item => item.key === query.tab) ? query.tab : 'overview'
      for (const key of Object.keys(this.filters)) this.filters[key] = typeof query[key] === 'string' ? query[key] : ''
      this.appliedFilters = { ...this.filters }; this.detailCourseName = this.appliedFilters.courseName
      this.activeDrill = ''; this.detail.open = false; this.detailRequestId++; this.workloadTeacherKey = ''
      if (!this.loading && this.updatedAt && !this.error && !this.scopeBlocked && previous === JSON.stringify([this.tab, this.appliedFilters])) this.restoreDetailRoute()
      else this.loadTab()
    },
    restoreDetailRoute() {
      const query = this.$route.query || {}, page = Number(query.detailPage)
      const detailPage = Number.isSafeInteger(page) && page > 0 && page <= 1000000 ? page : 1
      if (this.tab === 'overview' && typeof query.drill === 'string' && this.indicators.some(item => item.key === query.drill && this.drillable(item))) {
        this.activeDrill = query.drill; this.drill.pagination.page = detailPage; this.loadDrill()
      } else if (query.detail === '1' && TAB_META[this.tab]) {
        const meta = TAB_META[this.tab]
        this.detail.open = true; this.detail.title = meta.detailTitle; this.detail.columns = meta.detailColumns
        this.detail.pagination.page = detailPage; this.loadDetail()
      } else if (this.tab === 'workload' && typeof query.teacherKey === 'string' && query.teacherKey.trim()) {
        this.workloadTeacherKey = query.teacherKey
        const row = (this.sSummary.ranking || []).find(item => String(item.teacherKey) === query.teacherKey)
        this.detail.open = true; this.detail.title = `${row?.teacherName || '教师名称待核对'} · 授课明细`
        this.detail.columns = [
          { key: 'courseName', title: '课程' }, { key: 'teachingClassName', title: '教学班' },
          { key: 'weeklyHours', title: '周学时' }, { key: 'totalHours', title: '计划总学时' }, { key: 'status', title: '状态' }
        ]
        this.detail.pagination.page = detailPage; this.loadDetail()
      }
    },
    detailRoute(changes = {}) {
      const query = { ...this.$route.query, tab: this.tab }
      for (const key of ['drill', 'detail', 'teacherKey', 'detailPage']) delete query[key]
      this.$router.push({ path: this.$route.path, query: { ...query, ...changes } })
    },
    switchTopic(key) {
      const topic = STATS_TOPICS.find(item => item.key === key)
      if (topic) this.switchTab(topic.tabs.find(tab => this.allowedTab(tab)))
    },
    routeQuery(tab = this.tab) {
      const query = { ...this.$route.query, tab }
      delete query._workspace
      for (const key of ['drill', 'detail', 'teacherKey', 'detailPage']) delete query[key]
      for (const [key, value] of Object.entries(this.filters)) {
        if (value) query[key] = String(value)
        else delete query[key]
      }
      return query
    },
    drillable(ind) {
      return !!DRILL_META[ind.key] && ind.status !== 'MODULE_NOT_ENABLED'
    },
    indicatorTopic(ind) { return ind.status !== 'MODULE_NOT_ENABLED' ? STATS_INDICATOR_TOPICS[ind.key] : '' },
    openIndicatorTopic(ind) {
      const tab = this.indicatorTopic(ind)
      if (!tab) return
      this.filters = { ...this.appliedFilters }
      this.switchTab(tab)
    },
    // 仅用于展示：把既有分布数组 [{key,count}] 映射为柱状图 spec，不改动任何数据来源
    distSpec(arr, prefix = '') {
      return {
        type: 'interval',
        data: (arr || []).map((g) => ({ name: `${prefix}${statsGroupLabel(g)}`, value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    groupSummary(ind) {
      return (ind.groups || []).map((g) => `${statsGroupLabel(g)} ${g.count}`).join(' · ')
    },
    switchTab(k) {
      if (!TABS.some(item => item.key === k)) return
      this.$router.push({ path: this.$route.path, query: this.routeQuery(k) })
    },
    search() {
      const query = this.routeQuery()
      if (JSON.stringify(query) === JSON.stringify(this.$route.query)) {
        this.appliedFilters = { ...this.filters }; this.activeDrill = ''; this.detail.open = false; this.loadTab()
      } else this.$router.push({ path: this.$route.path, query })
    },
    baseParams() {
      return {
        termId: this.appliedFilters.termId || undefined,
        collegeId: this.appliedFilters.collegeId || undefined,
        majorId: this.appliedFilters.majorId || undefined
      }
    },
    async loadTab() {
      const request = ++this.requestId, identity = this.identity()
      this.detailRequestId++
      this.loading = true; this.error = ''; this.updatedAt = ''
      this.sourceAsOf = ''
      this.indicators = []; this.sSummary = {}; this.scopeBlocked = false; this.workloadPage = 1
      const tab = this.tab
      try {
        if (!this.allowedTab(tab)) throw new Error(tab === 'export' ? '当前账号没有报表导出权限' : '当前账号没有统计快照查看权限')
        if (tab === 'export' || tab === 'snapshot') return
        const params = { ...this.baseParams() }
        if (tab === 'course') params.category = this.appliedFilters.category || undefined
        if (tab === 'graduation') params.batchId = this.appliedFilters.batchId || undefined
        const res = tab === 'overview' ? await academicAffairsApi.getStatsOverview(params)
          : tab === 'workload' ? await academicAffairsApi.getStatsWorkload(params)
            : await TAB_META[tab].summary(academicAffairsApi, params)
        if (request !== this.requestId || identity !== this.identity()) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '统计读取失败，请重试')
        this.scopeBlocked = !!res.data.scope?.blocked
        this.sourceAsOf = res.data.asOf ? `${String(res.data.asOf).replace('T', ' ')} UTC` : ''
        if (tab === 'overview') {
          if (!Array.isArray(res.data.indicators)) throw new Error('统计指标回执不完整，请重试')
          this.indicators = res.data.indicators
          if (!this.distributionOptions.some(item => item.key === this.overviewMetricKey)) this.overviewMetricKey = this.distributionOptions[0]?.key || ''
        } else this.sSummary = res.data
        this.updatedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        if (!this.scopeBlocked) this.restoreDetailRoute()
      } catch (error) {
        if (request === this.requestId && identity === this.identity()) this.error = error.message || '统计读取失败，请重试'
      } finally {
        if (request === this.requestId && identity === this.identity()) this.loading = false
      }
    },
    onCardClick(ind) {
      if (!this.drillable(ind)) return
      if (this.activeDrill === ind.key) {
        this.closeDrill()
        return
      }
      this.detailRoute({ drill: ind.key })
    },
    closeDrill() {
      this.detailRequestId++
      this.activeDrill = ''
      this.drill.rows = []
      this.detailRoute()
    },
    closeDetail() { this.detailRequestId++; this.detail.open = false; this.detail.rows = []; this.detailRoute() },
    onDrillPage(p) {
      this.detailRoute({ drill: this.activeDrill, detailPage: String(p) })
    },
    async loadDrill() {
      const meta = DRILL_META[this.activeDrill]
      if (!meta) return
      const request = ++this.detailRequestId, identity = this.identity()
      this.drill.error = ''; this.drill.rows = []
      this.drill.pagination.total = 0
      this.drill.loading = true
      try {
      const params = { ...this.baseParams(), page: this.drill.pagination.page, pageSize: this.drill.pagination.pageSize }
      const res = await meta.fetch(academicAffairsApi, params)
      if (request !== this.detailRequestId || identity !== this.identity()) return
      if (res.code === 0) {
        if (!Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data.total) || res.data.total < 0) throw new Error('明细分页回执不完整，请重试')
        this.drill.rows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `${this.activeDrill}-${i}-${r.studentNo || ''}` }))
        this.drill.pagination.total = res.data.total || 0
      } else {
        this.drill.error = res.message || '明细读取失败，请重试'
        this.drill.rows = []
      }
      } catch (error) {
        if (request === this.detailRequestId && identity === this.identity()) this.drill.error = error.message || '明细读取失败，请重试'
      } finally {
        if (request === this.detailRequestId && identity === this.identity()) this.drill.loading = false
      }
    },
    openDetail() {
      const meta = TAB_META[this.tab]
      if (!meta) return
      this.detailRoute({ detail: '1' })
    },
    onDetailPage(p) {
      this.detailRoute({ ...(this.workloadTeacherKey ? { teacherKey: this.workloadTeacherKey } : { detail: '1' }), detailPage: String(p) })
    },
    async loadDetail() {
      const meta = this.tab === 'workload' && this.workloadTeacherKey
        ? { detailFetch: (api, params) => api.getStatsWorkloadDetail({ ...params, teacherKey: this.workloadTeacherKey }) }
        : TAB_META[this.tab]
      if (!meta) return
      const request = ++this.detailRequestId, identity = this.identity()
      this.detail.error = ''; this.detail.rows = []
      this.detail.pagination.total = 0
      this.detail.loading = true
      try {
      const params = {
        ...this.baseParams(),
        category: this.appliedFilters.category || undefined,
        courseName: this.appliedFilters.courseName || undefined,
        batchId: this.appliedFilters.batchId || undefined,
        itemType: this.appliedFilters.itemType || undefined,
        page: this.detail.pagination.page,
        pageSize: this.detail.pagination.pageSize
      }
      const res = await meta.detailFetch(academicAffairsApi, params)
      if (request !== this.detailRequestId || identity !== this.identity()) return
      if (res.code === 0) {
        if (!Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data.total) || res.data.total < 0) throw new Error('明细分页回执不完整，请重试')
        this.detail.rows = (res.data.list || []).map((r, i) => ({ ...r, ...(this.tab === 'teachingTask' ? { confirmationEvidence: '缺少教师确认时间，请核对原任务确认记录' } : {}), rowKey: `${this.tab}-${i}-${r.studentNo || r.courseId || r.taskId || r.gradeId || r.resultId || r.incidentId || r.bookingId || ''}` }))
        this.detail.pagination.total = res.data.total || 0
      } else {
        this.detail.error = res.message || '明细读取失败，请重试'
        this.detail.rows = []
      }
      } catch (error) {
        if (request === this.detailRequestId && identity === this.identity()) this.detail.error = error.message || '明细读取失败，请重试'
      } finally {
        if (request === this.detailRequestId && identity === this.identity()) this.detail.loading = false
      }
    },
    viewWorkloadDetail(row) {
      if (row?.teacherKey) this.detailRoute({ teacherKey: String(row.teacherKey) })
    },
    canOpenTaskSource(row) {
      return this.tab === 'teachingTask' && !this.detail.loading && !this.detail.error && this.detail.rows.includes(row) &&
        matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.view') &&
        /^[1-9]\d*$/.test(String(row?.batchId)) && /^[1-9]\d*$/.test(String(row?.taskId))
    },
    openTaskSource(row) {
      if (!this.canOpenTaskSource(row)) return
      const returnToken = this.academicFlow?.captureReturn()
      this.$router.push({ path: `/admin/academic-affairs/teaching-tasks/${row.batchId}`,
        query: { teachingTaskId: String(row.taskId), ...(returnToken ? { returnToken } : {}) } })
    },
    async openExport() {
      this.exp.domain = this.tab === 'snapshot' ? 'overview' : this.tab
      this.exp.termId = this.appliedFilters.termId
      this.exp.collegeId = this.appliedFilters.collegeId
      const query = { ...this.$route.query, tab: 'export' }
      for (const key of ['drill', 'detail', 'teacherKey', 'detailPage']) delete query[key]
      this.$router.push({ path: this.$route.path, query })
    },
    async doExport() {
      if (this.exp.downloading) return
      if (!this.canExport) { toast.error('当前账号没有报表导出权限'); return }
      if (!this.exp.purpose || this.exp.purpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      this.exp.downloading = true
      const requestId = ++this.exportRequestId, identity = this.identity(), query = JSON.stringify(this.exp), route = this.$route.fullPath, domain = this.exp.domain
      try {
      const res = await academicAffairsApi.exportStats({
        domain: this.exp.domain,
        termId: this.exp.termId || undefined,
        collegeId: this.exp.collegeId || undefined,
        purpose: this.exp.purpose.trim()
      })
      if (requestId !== this.exportRequestId || identity !== this.identity() || route !== this.$route.fullPath || query !== JSON.stringify(this.exp)) return
      if (res.code !== 0) {
        toast.error(res.message || '导出失败')
        return
      }
      const label = (EXPORT_DOMAINS.find((d) => d.key === domain) || {}).label || '教务统计'
      const fileName = `${label}-${Date.now()}.xlsx`
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = fileName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
      this.exp.receipt = { fileName, completedAt: new Date().toLocaleString('zh-CN', { hour12: false }) }
      toast.success('导出成功')
      } catch (error) {
        if (requestId === this.exportRequestId && identity === this.identity()) toast.error(error.message || '导出失败，请重试')
      } finally {
        if (requestId === this.exportRequestId && identity === this.identity()) this.exp.downloading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-statistics { gap: 18px; }
.stats-updated,.stats-applied,.stats-cell-note,.stats-trend-note,.stats-method { color: var(--text-secondary); font-size: 13px; }
.stats-dimensions { display:flex; gap:24px; border-bottom:1px solid var(--border-base); overflow-x:auto; }
.stats-dimensions button { flex-shrink:0; border:0; border-bottom:2px solid transparent; background:transparent; color:var(--text-secondary); padding:10px 2px; font:inherit; cursor:pointer; }
.stats-dimensions button.active { color:var(--pri); border-bottom-color:var(--pri); font-weight:650; }
.aa-filter { display:flex; align-items:end; gap:14px; flex-wrap:wrap; background:var(--bg-card); border:1px solid var(--border-base); border-radius:10px; padding:16px 20px; }
.aa-filter__item { display:flex; flex:1 1 180px; flex-direction:column; gap:8px; font-size:13px; min-width:0; }
.stats-filter-actions { display:flex; gap:10px; margin-left:auto; }
.aa-statistics .aa-input { box-sizing:border-box; min-width:0; min-height:36px; border:1px solid var(--border-base); border-radius:8px; padding:8px 10px; font:inherit; background:var(--bg-card); color:var(--text-primary); }
.stats-applied { margin:0; line-height:1.65; }
.aa-filter .stats-applied { flex-basis:100%; }
.stats-notice { background:var(--warning-bg, #fff8e8); color:var(--warning-color, #966109); border-radius:8px; padding:10px 14px; margin:0; }
.stats-kpi-grid { display:flex; background:var(--bg-card); border:1px solid var(--border-base); border-radius:10px; padding:20px 8px; }
.stats-kpi-card { flex:1; min-width:0; padding:0 20px; display:flex; flex-direction:column; gap:9px; border-right:1px solid var(--border-base); }
.stats-kpi-card:last-child { border:0; }
.stats-kpi-card > span { font-size:14px; color:var(--text-primary); }
.stats-kpi-card > strong { color:var(--pri); font-size:30px; font-weight:700; line-height:1.3; overflow-wrap:anywhere; }
.stats-kpi-card.is-warning > strong { color:var(--warning-color,#b76700); }
.stats-kpi-card > small { color:var(--text-secondary); font-size:13px; }
.stats-unit { margin-left:5px; font-size:15px; font-weight:400; }
.stats-attention { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:12px 18px; border:1px solid var(--warning-border,#efd5ae); border-radius:10px; background:var(--warning-bg,#fff8ed); }
.stats-attention > div { display:flex; flex:1; align-items:center; flex-wrap:wrap; gap:10px; }
.stats-attention b { color:var(--warning-color,#b76700); font-size:22px; }
.stats-attention > :last-child { margin-left:auto; }
.stats-analysis-panel,.aa-drill { min-width:0; background:var(--bg-card); border:1px solid var(--border-base); border-radius:10px; overflow:hidden; }
.stats-analysis-panel > header,.aa-drill > header { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; padding:16px 20px; }
.stats-analysis-panel h2,.aa-drill h2 { margin:0; font-size:18px; line-height:1.4; }
.stats-analysis-panel > header > span { color:var(--text-secondary); font-size:13px; }
.stats-analysis-panel :deep(.dt),.aa-drill :deep(.dt) { border:0; border-radius:0; }
.stats-analysis-panel :deep(.dt__table) { min-width:600px; }
.stats-analysis-panel > .stats-applied { padding:8px 20px 16px; }
.stats-analysis-grid { display:grid; grid-template-columns:minmax(0,1fr); gap:16px; }
.stats-analysis-grid.has-secondary { grid-template-columns:minmax(0,1.6fr) minmax(260px,1fr); }
.stats-distribution-body.side-by-side { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); align-items:center; gap:20px; padding:0 20px 18px; }
.stats-distribution-body.side-by-side :deep(.dt__table) { min-width:360px; }
.stats-distribution-body > .stats-applied { padding:10px 20px; }
.stats-cell-note { display:block; margin-top:4px; }
.aa-statistics :deep(.app-button--ghost) { color:var(--pri); }
.stats-completion { padding:8px 20px 20px; }
.stats-completion progress { display:block; width:100%; height:22px; border:0; border-radius:5px; overflow:hidden; background:#fff0d8; accent-color:var(--pri); }
.stats-completion progress::-webkit-progress-bar { background:#fff0d8; }
.stats-completion progress::-webkit-progress-value { background:var(--pri); }
.stats-completion-labels { display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px; margin-top:10px; font-size:14px; }
.stats-completion-labels small { color:var(--text-secondary); }
.stats-grade-publish > strong { display:block; margin:10px 20px; color:var(--pri); font-size:36px; }
.stats-grade-publish > p,.stats-grade-publish > button { margin:12px 20px; }
.stats-detail-filter { display:flex; align-items:end; flex-wrap:wrap; gap:14px; padding:16px 20px; background:var(--bg-card); border:1px solid var(--border-base); border-radius:10px; }
.stats-detail-filter label { display:flex; flex:1; flex-direction:column; gap:8px; min-width:180px; }
.stats-analysis-panel header label { display:flex; align-items:center; flex-wrap:wrap; gap:8px; font-size:13px; }
.stats-trend-note { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin:0; }
.stats-method summary { cursor:pointer; }
.stats-method p { line-height:1.7; }
.aa-export-form { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; padding:0 20px 20px; }
.aa-export-form label { display:flex; flex-direction:column; gap:8px; min-width:0; }
.stats-export-purpose { grid-column:1/-1; }
.aa-export-form textarea { font:inherit; resize:vertical; min-height:84px; border:1px solid var(--border-base); border-radius:6px; padding:10px; }
.stats-export-card footer { display:flex; gap:12px; align-items:center; justify-content:space-between; flex-wrap:wrap; border-top:1px solid var(--border-base); padding:16px 20px; }
.stats-export-card footer span,.stats-export-result { color:var(--text-secondary); font-size:13px; }
.stats-export-result { padding:0 20px 16px; }
@media(max-width:900px) { .stats-analysis-grid.has-secondary,.stats-distribution-body.side-by-side { grid-template-columns:1fr; } .stats-kpi-card { padding:0 12px; } .stats-kpi-card > strong { font-size:25px; } }
@media(max-width:600px) { .aa-filter { padding:12px; } .aa-filter__item { flex-basis:100%; } .stats-filter-actions { width:100%; margin:0; } .stats-kpi-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px 0; } .stats-kpi-card:nth-child(2n) { border:0; } .stats-kpi-card > strong { font-size:22px; } .stats-attention > div { flex-basis:100%; } .aa-export-form { grid-template-columns:1fr; } .stats-analysis-panel > header,.aa-drill > header { padding:12px; } }
</style>
