<template>
  <ModulePageShell
    class="aa-statistics"
    :title="statsPage.title"
    :subtitle="statsPage.subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <label class="stats-topic-select">统计专题
        <select :value="currentTopic.key" @change="switchTopic($event.target.value)">
          <option v-for="topic in visibleTopics" :key="topic.key" :value="topic.key">{{ topic.label }}</option>
        </select>
      </label>
    </template>
    <div class="stats-intro">
      <p>{{ currentTopic.description }}</p>
      <span v-if="updatedAt" role="status">更新于 {{ updatedAt }}</span>
    </div>
    <nav v-if="topicTabs.length > 1" class="stats-dimensions" aria-label="本专题统计维度">
      <button v-for="item in topicTabs" :key="item.key" type="button" :aria-current="tab === item.key ? 'page' : undefined" :class="{ active: tab === item.key }" @click="switchTab(item.key)">{{ item.label }}</button>
    </nav>

    <div class="mp-stack">
      <!-- 多维筛选栏（导出报表 Tab 使用自己的表单，不复用此栏；教学资源为校级共享资产，
           无学期/学院维度，见 resource_stats 后端注释，本栏对该 Tab 不适用） -->
      <form v-if="tab !== 'export' && tab !== 'resource' && tab !== 'snapshot'" class="aa-filter" @submit.prevent="search">
        <label class="aa-filter__item">学期
          <AppTermEntityPicker v-model="filters.termId" placeholder="全部学期" />
        </label>
        <label class="aa-filter__item">学院
          <AppCollegePicker v-model="filters.collegeId" placeholder="全部学院" @change="filters.majorId = ''" />
        </label>
        <label v-if="tab === 'overview' || tab === 'registration'" class="aa-filter__item">专业
          <AppMajorPicker v-model="filters.majorId" :query="{ collegeId: filters.collegeId || undefined }" placeholder="全部专业" />
        </label>
        <label v-if="tab === 'course'" class="aa-filter__item">类别
          <input v-model="filters.category" class="aa-input aa-input--sm" placeholder="可空=全部" />
        </label>
        <label v-if="tab === 'grade'" class="aa-filter__item">课程名（下钻筛选）
          <input v-model="filters.courseName" class="aa-input aa-input--sm" placeholder="可空=全部" />
        </label>
        <label v-if="tab === 'graduation'" class="aa-filter__item">预审批次
          <AppGraduationBatchPicker v-model="filters.batchId" placeholder="全部批次" />
        </label>
        <AppButton :loading="loading" @click="search">更新统计</AppButton>
        <AppButton v-if="tab === 'overview' && canExport" variant="ghost" :disabled="loading" @click="openExport">导出 Excel</AppButton>
      </form>
      <p v-if="tab !== 'snapshot' && tab !== 'export'" class="stats-scope">{{ tab === 'resource' ? '资源统计按当前授权范围汇总，不随学期筛选。' : '统计范围由当前账号权限限定；修改筛选后点击更新统计。' }} 比例显示“—”表示暂无统计基数。</p>
      <p v-if="filtersDirty && tab !== 'export' && tab !== 'snapshot'" class="aa-scope-note" role="status">筛选条件尚未查询，下方指标、明细和导出仍使用上次查询范围。</p>

      <ErrorState v-if="error" :description="error" @retry="loadTab" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <p v-if="scopeBlocked" class="aa-scope-note">当前账号未配置教务数据范围，暂无可见统计数据（如为学院教务员请联系管理员配置本院范围）。</p>

        <template v-else>
        <section v-if="analyticsCards.length" class="stats-kpi-grid" aria-label="当前统计口径">
          <article v-for="(card, index) in analyticsCards" :key="card.label" class="stats-kpi-card" :class="{ 'is-warning': index === 2 && card.tone === 'warning' }">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.note }}</small>
          </article>
        </section>

        <!-- AA-242：分布、同期趋势状态与正式指标下钻。 -->
        <template v-if="tab === 'overview'">
          <div class="stats-analysis-grid">
            <section class="stats-analysis-panel">
              <header><h2>教务统计总览 · 分布</h2><select v-if="distributionOptions.length" v-model="overviewMetricKey" aria-label="选择分布指标"><option v-for="item in distributionOptions" :key="item.key" :value="item.key">{{ item.label }}</option></select></header>
              <p class="stats-analysis-caption">{{ distributionMetric?.label || '指标分布' }} · 当前查询范围</p>
              <AppG2Chart v-if="distributionMetric" :spec="overviewDistributionSpec" :height="240" />
              <EmptyState v-else title="当前指标未提供分组数据" description="下方保留正式指标结果；无分组回执时不推算学院分布。" />
            </section>
            <section class="stats-analysis-panel">
              <header><h2>当期周期变化</h2></header>
              <EmptyState title="当前统计未提供同期趋势" description="当前接口返回时点指标。需要相同学期、相同范围的连续时点数据后，才能展示周期变化。" />
              <p class="stats-analysis-caption">数据截至 {{ sourceAsOf || '尚未提供' }}<br>历史快照按各自冻结范围留存，不直接拼接为同口径趋势。</p>
              <AppButton v-if="canViewSnapshot" variant="ghost" @click="switchTab('snapshot')">查看历史统计快照</AppButton>
            </section>
          </div>
          <section class="stats-analysis-panel stats-indicator-ledger">
            <header><div><h2>同口径明细下钻</h2><p>选择指标查看其原始明细，保留当前查询范围。</p></div><span>{{ overviewRows.length }} 项正式指标</span></header>
            <DataTable :columns="overviewColumns" :rows="overviewRows" row-key="key">
              <template #cell-label="{ row }"><strong>{{ row.label }}</strong><small class="stats-cell-note">{{ row.sectionLabel }}</small></template>
              <template #cell-value="{ row }"><strong>{{ indicatorValue(row) }}</strong><small v-if="row.unit === '%'" class="stats-cell-note">{{ row.denominator ? `${row.numerator ?? '—'} / ${row.denominator}` : '暂无统计基数' }}</small></template>
              <template #cell-scope><span>{{ appliedScopeLabel }}</span></template>
              <template #cell-time>{{ sourceAsOf || '尚未提供' }}</template>
              <template #cell-status="{ row }"><span>{{ row.status === 'MODULE_NOT_ENABLED' ? '未启用' : row.message || '已返回统计结果' }}</span></template>
              <template #cell-action="{ row }"><AppButton v-if="drillable(row)" size="small" variant="ghost" @click="onCardClick(row)">{{ activeDrill === row.key ? '收起明细' : '查看明细' }}</AppButton><AppButton v-else-if="indicatorTopic(row)" size="small" variant="ghost" @click="openIndicatorTopic(row)">查看专题与异常</AppButton><span v-else class="stats-cell-note">当前仅汇总统计</span></template>
            </DataTable>
          </section>
          <div v-if="activeDrill" class="aa-drill">
            <div class="aa-drill__head">
              <strong>{{ drillTitle }}</strong>
              <button class="mp-link" @click="closeDrill">收起</button>
            </div>
            <LoadingState v-if="drill.loading" />
            <ErrorState v-else-if="drill.error" :description="drill.error" @retry="loadDrill" />
            <EmptyState v-else-if="!drill.rows.length" title="无明细数据" description="当前范围内没有可下钻的记录" />
            <DataTable v-else :columns="drillColumns" :rows="drill.rows" row-key="rowKey" :pagination="drill.pagination" @page-change="onDrillPage" />
          </div>
        </template>

        <!-- AA-243～AA-255：统一的统计阅读顺序，指标和下钻字段仍由各业务真实 DTO 决定。 -->
        <template v-else-if="isMetricTab">
          <div class="stats-analysis-grid">
            <section class="stats-analysis-panel">
              <header><div><h2>{{ statsPage.title }} · 分布</h2><p>仅使用当前接口返回的分组与计数</p></div></header>
              <AppG2Chart v-if="analyticsDistribution.length" :spec="analyticsDistributionSpec" :height="240" />
              <EmptyState v-else title="当前口径没有分组数据" description="保留正式汇总结果，不根据明细页或样例数据推算分布。" />
            </section>
            <section class="stats-analysis-panel">
              <header><div><h2>当前指标构成</h2><p>{{ sourceAsOf ? `数据截至 ${sourceAsOf}` : '当前接口未返回独立数据时间' }}</p></div></header>
              <AppG2Chart v-if="analyticsMetricSeries.length" :spec="analyticsMetricSpec" :height="240" />
              <EmptyState v-else title="暂无可绘制指标" description="当前范围没有可用于图表的数值。" />
              <p class="stats-analysis-caption">当前接口未提供连续同口径快照，本图展示本次查询的指标构成，不冒充周期趋势。</p>
            </section>
          </div>
          <section class="stats-analysis-panel stats-indicator-ledger">
            <header><div><h2>同口径明细下钻</h2><p>汇总口径、数据范围和办理入口保持一致。</p></div><span>{{ analyticsLedgerRows.length }} 项正式统计</span></header>
            <DataTable :columns="analyticsLedgerColumns" :rows="analyticsLedgerRows" row-key="rowKey">
              <template #cell-metric="{ row }"><strong>{{ row.metric }}</strong><small class="stats-cell-note">{{ row.note }}</small></template>
              <template #cell-action><AppButton v-if="canOpenCurrentDetail" size="small" variant="ghost" @click="openDetail">{{ statsPage.primary }}</AppButton><span v-else class="stats-cell-note">只读统计</span></template>
            </DataTable>
          </section>
        </template>

        <!-- ══ 教师工作量统计（13，基础参考，非正式核算）══ -->
        <template v-else-if="tab === 'workload'">
          <AppInlineAlert type="warning" description="本页汇总教学任务数与计划学时，供教学安排参考，不作为绩效结算依据。" />
          <EmptyState v-if="!sSummary.ranking || !sSummary.ranking.length" title="暂无数据" description="当前范围内没有可统计的教学任务" />
          <DataTable v-else :columns="workloadColumns" :rows="sSummary.ranking" row-key="teacherKey">
            <template #cell-ops="{ row }"><button class="mp-link" @click="viewWorkloadDetail(row)">查看明细</button></template>
          </DataTable>
        </template>

        <!-- ══ 统计冻结快照（W3）══ -->
        <template v-else-if="tab === 'snapshot'">
          <AaStatsSnapshotWorkspace :ctx="ctx" :context-filters="appliedFilters" />
        </template>

        <!-- ══ 导出报表（15）══ -->
        <template v-else-if="tab === 'export'">
          <ol class="stats-stage-rail" aria-label="统计导出流程">
            <li class="is-done"><b>✓</b><span><strong>正式事实</strong><small>读取统计口径</small></span></li>
            <li class="is-done"><b>✓</b><span><strong>范围与学期</strong><small>由服务端裁定</small></span></li>
            <li class="is-current"><b>3</b><span><strong>统计口径</strong><small>当前选择</small></span></li>
            <li><b>4</b><span><strong>用途审计</strong><small>用途至少 5 字</small></span></li>
            <li><b>5</b><span><strong>下载文件</strong><small>按本次状态导出</small></span></li>
          </ol>
          <div class="stats-export-grid">
            <section class="stats-export-card">
              <header><h2>导出范围与用途</h2></header>
              <div class="aa-export-form">
                <label class="aa-filter__item">导出维度
                  <AppSelect v-model="exp.domain" :options="exportDomainOptions" />
                </label>
                <label class="aa-filter__item">学期
                  <AppTermEntityPicker v-model="exp.termId" placeholder="全部学期" />
                </label>
                <label class="aa-filter__item">学院
                  <AppCollegePicker v-model="exp.collegeId" placeholder="全部学院" />
                </label>
                <label class="aa-filter__item stats-export-purpose">导出用途（至少5个字）
                  <textarea v-model="exp.purpose" rows="4" maxlength="500" placeholder="如：教务处月度汇报" />
                </label>
              </div>
              <footer><span>完整导出由服务端按当前权限与筛选生成，不放大列表 pageSize。</span><AppButton :loading="exp.downloading" @click="doExport">生成并下载 Excel</AppButton></footer>
            </section>
            <aside class="stats-export-card stats-export-rules">
              <header><h2>三种范围不要混淆</h2></header>
              <dl>
                <div><dt>本页记录</dt><dd>当前页面已经展示的汇总结果</dd></div>
                <div><dt>已选记录</dt><dd>显式选择的业务对象集合</dd></div>
                <div><dt>当前筛选全部</dt><dd>由服务端按权限与筛选生成</dd></div>
              </dl>
            </aside>
          </div>
          <section class="stats-export-card stats-export-receipt">
            <header><h2>文件结果与回执</h2></header>
            <div v-if="exp.receipt"><strong>{{ exp.receipt.fileName }}</strong><span>已于 {{ exp.receipt.completedAt }} 收到服务端 Excel 文件</span></div>
            <EmptyState v-else title="尚未执行导出" description="填写正式用途后生成文件；浏览器下载失败不会被报告为成功。" />
          </section>
        </template>

        <!-- 通用下钻明细面板（除总览/工作量/导出外的 11 个 Tab 共用） -->
        <div v-if="detail.open" class="aa-drill">
          <div class="aa-drill__head">
            <strong>{{ detail.title }}</strong>
            <button class="mp-link" @click="closeDetail">收起</button>
          </div>
          <LoadingState v-if="detail.loading" />
          <ErrorState v-else-if="detail.error" :description="detail.error" @retry="loadDetail" />
          <EmptyState v-else-if="!detail.rows.length" title="无明细数据" description="当前范围内没有可查看的记录" />
          <DataTable v-else :columns="detail.columns" :rows="detail.rows" row-key="rowKey" :pagination="detail.pagination" @page-change="onDetailPage">
            <template #cell-abnormalItems="{ row }">{{ (row.abnormalItems || []).join('、') }}</template>
            <template #cell-courses="{ row }">{{ (row.courses || []).map((c) => c.courseName).join('、') }}</template>
          </DataTable>
        </div>
        </template>
      </template>
    </div>
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
import {
  AppInlineAlert, AppG2Chart, AppSelect,
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
  registration: { id: 'AA-244', aliases: ['AA-258'], title: '学籍与注册', subtitle: '明确注册类型、学期和当前授权范围', primary: '下钻注册明细' },
  course: { id: 'AA-245', title: '开课与教学运行', subtitle: '按课程供给和启用状态核对本期教学运行', primary: '下钻教学任务' },
  teachingTask: { id: 'AA-246', title: '教学任务统计', subtitle: '区分已确认任务与尚未就绪任务', primary: '查看未就绪任务' },
  schedule: { id: 'AA-247', title: '课表统计', subtitle: '依据正式课表批次核对发布覆盖与冲突', primary: '查看课表版本' },
  courseSelection: { id: 'AA-249', title: '选课统计', subtitle: '按批次核对容量、报名与名单状态', primary: '查看名单状态' },
  exam: { id: 'AA-250', title: '考试与成绩', subtitle: '核对考试课程编排完成度与正式异常记录', primary: '下钻考务明细' },
  grade: { id: 'AA-251', aliases: ['AA-259'], title: '成绩统计', subtitle: '只统计正式有效成绩，挂科人数不冒充预警条数', primary: '下钻有效成绩' },
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
  LOW: '低风险', UNKNOWN: '未分类'
}

function finite(value, fallback = 0) {
  const result = Number(value)
  return Number.isFinite(result) ? result : fallback
}

function percent(value) {
  return value === null || value === undefined || !Number.isFinite(Number(value)) ? '—' : `${Number(value)}%`
}

function metricCards(tab, summary, scopeLabel, updatedAt) {
  const scope = { label: '当前统计范围', value: scopeLabel, note: '由当前账号权限和筛选条件共同限定' }
  const time = { label: '数据状态', value: updatedAt || '读取中', note: '显示本次成功查询时间' }
  const pending = (total, done) => Math.max(0, finite(total) - finite(done))
  const maps = {
    statusChange: [scope, { label: '已生效异动', value: finite(summary.total), note: '只计正式生效结果' }, { label: '异动类型', value: (summary.byType || []).length, note: '接口返回的正式分类数' }, time],
    registration: [scope, { label: '应注册', value: finite(summary.expected), note: '当前口径内应注册学生' }, { label: '未注册', value: pending(summary.expected, summary.registered), note: '应注册减已注册', tone: 'warning' }, { label: '完成比例', value: percent(summary.rate), note: `${finite(summary.registered)} / ${finite(summary.expected)}` }],
    course: [scope, { label: '启用课程', value: finite(summary.total), note: '当前范围启用课程' }, { label: '课程类别', value: (summary.byCategory || []).length, note: '接口返回的正式类别' }, { label: '覆盖学院', value: (summary.byCollege || []).length, note: '当前口径有课程的学院' }],
    teachingTask: [scope, { label: '教学任务', value: finite(summary.expected), note: '当前范围任务总量' }, { label: '未确认', value: pending(summary.expected, summary.confirmed), note: '总任务减已确认任务', tone: 'warning' }, { label: '确认比例', value: percent(summary.rate), note: `${finite(summary.confirmed)} / ${finite(summary.expected)}` }],
    schedule: [scope, { label: '课表批次', value: finite(summary.totalBatches), note: '当前范围批次总量' }, { label: '未解决冲突', value: finite(summary.unresolvedConflicts), note: '正式冲突检测结果', tone: 'warning' }, { label: '发布覆盖', value: percent(summary.publishedRate), note: `${finite(summary.published)} / ${finite(summary.totalBatches)}` }],
    courseSelection: [scope, { label: '容量', value: finite(summary.totalCapacity ?? summary.capacity), note: '当前批次供给容量' }, { label: '低人数课程', value: finite(summary.lowEnrollCount), note: '低于正式开课下限', tone: 'warning' }, { label: '填充比例', value: percent(summary.fillRate), note: `${finite(summary.totalSelected ?? summary.selected)} / ${finite(summary.totalCapacity ?? summary.capacity)}` }],
    exam: [scope, { label: '应考课程', value: finite(summary.courseTotal ?? summary.confirmedCourses), note: '当前范围考试课程' }, { label: '缺考与违纪', value: finite(summary.absentCount) + finite(summary.violationCount), note: '只计正式异常记录', tone: 'warning' }, { label: '编排完成', value: percent(summary.confirmRate ?? summary.rate), note: `${finite(summary.confirmedCount ?? summary.arranged)} / ${finite(summary.courseTotal ?? summary.confirmedCourses)}` }],
    grade: [scope, { label: '有效成绩', value: finite(summary.failDenominator), note: '正式有效成绩统计基数' }, { label: '不及格人数', value: finite(summary.failNumerator), note: '不是学业预警条数', tone: 'warning' }, { label: '成绩发布', value: percent(summary.entryPublishRate), note: `${finite(summary.publishNumerator)} / ${finite(summary.publishDenominator)}` }],
    warning: [scope, { label: '未闭环预警', value: finite(summary.total), note: '排除已关闭预警' }, { label: '风险等级', value: (summary.byLevel || []).length, note: '正式预警等级分布', tone: 'warning' }, { label: '预警来源', value: (summary.bySource || []).length, note: '真实规则命中来源' }],
    graduation: [scope, { label: '应审人数', value: finite(summary.expected), note: '当前批次毕业审核对象' }, { label: '待核或异常', value: pending(summary.expected, summary.passed), note: '应审减已通过', tone: 'warning' }, { label: '通过比例', value: percent(summary.passRate), note: `${finite(summary.passed)} / ${finite(summary.expected)}` }],
    resource: [scope, { label: '可用教室', value: finite(summary.availableRooms ?? summary.classroomTotal), note: '按资源正式状态统计' }, { label: '待审预约', value: finite(summary.pendingBookings ?? summary.bookingTotal), note: '需要资源管理员处理', tone: 'warning' }, { label: '资源类型', value: (summary.byRoomType || summary.byType || summary.byStatus || []).length, note: '接口返回的资源分类' }]
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
    detailTitle: '未确认教学任务',
    detailColumns: [
      { key: 'courseName', title: '课程' }, { key: 'teachingClassName', title: '教学班' },
      { key: 'teacherName', title: '教师' }, { key: 'status', title: '状态' }
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
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton,
    AppInlineAlert, AppG2Chart, AppSelect, AppTermEntityPicker,
    AppCollegePicker, AppMajorPicker, AppGraduationBatchPicker, AaStatsSnapshotWorkspace
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TABS, STATS_TOPICS, requestId: 0, detailRequestId: 0, exportRequestId: 0, updatedAt: '',
      sourceAsOf: '', overviewMetricKey: '',
      overviewColumns: [{ key: 'label', title: '业务主题 / 指标' }, { key: 'value', title: '当前值' }, { key: 'scope', title: '统计范围' }, { key: 'time', title: '数据时间' }, { key: 'status', title: '结果说明' }, { key: 'action', title: '办理入口' }],
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
      workloadTeacherKey: '',
      workloadColumns: [
        { key: 'teacherName', title: '教师' }, { key: 'totalHours', title: '学时合计' },
        { key: 'taskCount', title: '任务数' }, { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    statsPage() { return STATS_PAGE_META[this.tab] || STATS_PAGE_META.overview },
    isMetricTab() { return !!TAB_META[this.tab] && this.tab !== 'overview' },
    canOpenCurrentDetail() { return !!TAB_META[this.tab]?.detailFetch },
    analyticsCards() {
      if (this.tab === 'export' || this.tab === 'snapshot') return []
      if (this.tab === 'overview') {
        const available = this.indicators.filter(item => item.status !== 'MODULE_NOT_ENABLED')
        return [
          { label: '当前统计范围', value: this.appliedScopeLabel, note: '筛选与当前账号权限共同限定' },
          { label: '正式指标', value: this.indicators.length, note: '后端本次返回的指标总数' },
          { label: '可下钻指标', value: available.filter(item => this.drillable(item)).length, note: '可进入同口径正式明细' },
          { label: '数据状态', value: this.updatedAt || '读取中', note: '显示本次成功查询时间' }
        ]
      }
      if (this.tab === 'workload') {
        const rows = this.sSummary.ranking || []
        return [
          { label: '当前统计范围', value: this.appliedScopeLabel, note: '筛选与当前账号权限共同限定' },
          { label: '授课教师', value: rows.length, note: '当前范围有任务的教师' },
          { label: '教学任务', value: rows.reduce((sum, row) => sum + finite(row.taskCount), 0), note: '按教学任务聚合' },
          { label: '计划学时', value: rows.reduce((sum, row) => sum + finite(row.combinedHours ?? row.totalHours), 0), note: '安排参考，非绩效结算' }
        ]
      }
      return metricCards(this.tab, this.sSummary, this.appliedScopeLabel, this.updatedAt)
    },
    analyticsDistribution() {
      const summary = this.sSummary || {}
      const candidates = [summary.byType, summary.byCategory, summary.byCollege, summary.byBatchStatus,
        summary.byStatus, summary.byLevel, summary.bySource, summary.byAbnormalItem, summary.byRoomType]
      const returned = candidates.find(rows => Array.isArray(rows) && rows.length)
      if (returned) return returned.map(row => ({ name: STATUS_NAMES[row.key] || row.label || row.key, value: finite(row.count) }))
      const compositions = {
        registration: [
          { name: '已注册', value: finite(summary.registered) },
          { name: '未注册', value: Math.max(0, finite(summary.expected) - finite(summary.registered)) }
        ],
        teachingTask: [
          { name: '已确认', value: finite(summary.confirmed) },
          { name: '未确认', value: Math.max(0, finite(summary.expected) - finite(summary.confirmed)) }
        ],
        schedule: [
          { name: '已发布批次', value: finite(summary.published) },
          { name: '未发布批次', value: Math.max(0, finite(summary.totalBatches) - finite(summary.published)) },
          { name: '未解决冲突', value: finite(summary.unresolvedConflicts) }
        ],
        courseSelection: [
          { name: '已选人次', value: finite(summary.totalSelected ?? summary.selected) },
          { name: '剩余容量', value: Math.max(0, finite(summary.totalCapacity ?? summary.capacity) - finite(summary.totalSelected ?? summary.selected)) }
        ],
        exam: [
          { name: '已完成编排', value: finite(summary.confirmedCount ?? summary.arranged) },
          { name: '待编排', value: Math.max(0, finite(summary.courseTotal ?? summary.confirmedCourses) - finite(summary.confirmedCount ?? summary.arranged)) },
          { name: '正式异常', value: finite(summary.absentCount) + finite(summary.violationCount) }
        ],
        grade: [
          { name: '及格记录', value: Math.max(0, finite(summary.failDenominator) - finite(summary.failNumerator)) },
          { name: '不及格记录', value: finite(summary.failNumerator) }
        ],
        graduation: [
          { name: '已通过', value: finite(summary.passed) },
          { name: '待核或异常', value: Math.max(0, finite(summary.expected) - finite(summary.passed)) }
        ]
      }
      if (compositions[this.tab]) return compositions[this.tab]
      const cards = this.analyticsCards.slice(1).map(card => ({ name: card.label, value: Number.parseFloat(String(card.value)) }))
        .filter(row => Number.isFinite(row.value))
      return cards
    },
    analyticsHasServerGroups() {
      return [this.sSummary.byType, this.sSummary.byCategory, this.sSummary.byCollege, this.sSummary.byBatchStatus,
        this.sSummary.byStatus, this.sSummary.byLevel, this.sSummary.bySource, this.sSummary.byAbnormalItem,
        this.sSummary.byRoomType].some(rows => Array.isArray(rows) && rows.length)
    },
    analyticsMetricSeries() {
      return this.analyticsCards.slice(1).map(card => ({ name: card.label, value: Number.parseFloat(String(card.value)) }))
        .filter(row => Number.isFinite(row.value))
    },
    analyticsDistributionSpec() {
      return { type: 'interval', data: this.analyticsDistribution, encode: { x: 'name', y: 'value' }, coordinate: { transform: [{ type: 'transpose' }] }, axis: { x: { title: null }, y: { title: null } }, style: { radiusTopRight: 4, radiusBottomRight: 4 } }
    },
    analyticsMetricSpec() {
      return { type: 'interval', data: this.analyticsMetricSeries, encode: { x: 'name', y: 'value' }, axis: { x: { title: null }, y: { title: null } }, style: { radiusTopLeft: 4, radiusTopRight: 4 } }
    },
    analyticsLedgerColumns() {
      return [{ key: 'metric', title: '统计项' }, { key: 'value', title: '本学期值' }, { key: 'scope', title: '统计范围' }, { key: 'time', title: '更新时间' }, { key: 'action', title: '办理入口' }]
    },
    analyticsLedgerRows() {
      const rows = this.analyticsDistribution.length ? this.analyticsDistribution : this.analyticsMetricSeries
      return rows.map((row, index) => ({
        rowKey: `${this.tab}-${index}-${row.name}`,
        metric: row.name,
        value: row.value,
        scope: this.appliedScopeLabel,
        time: this.sourceAsOf || this.updatedAt || '—',
        note: this.analyticsHasServerGroups ? '接口返回的正式分组结果' : '由本次正式汇总值构成，不跨口径推算'
      }))
    },
    overviewRows() { return this.overviewSections.flatMap(section => section.items.map(item => ({ ...item, sectionLabel: section.label }))) },
    distributionOptions() { return this.indicators.filter(item => item.status !== 'MODULE_NOT_ENABLED' && Array.isArray(item.groups) && item.groups.some(group => typeof group.count === 'number' && Number.isFinite(group.count))) },
    distributionMetric() { return this.distributionOptions.find(item => item.key === this.overviewMetricKey) || this.distributionOptions[0] || null },
    overviewDistributionSpec() {
      return { type: 'interval', data: (this.distributionMetric?.groups || []).filter(group => typeof group.count === 'number' && Number.isFinite(group.count)).map(group => ({ name: statsGroupLabel(group), value: group.count })), encode: { x: 'name', y: 'value' }, coordinate: { transform: [{ type: 'transpose' }] }, axis: { y: { title: null }, x: { title: null } } }
    },
    appliedScopeLabel() { return [this.appliedFilters.termId ? `学期 #${this.appliedFilters.termId}` : '各指标原有学期范围', this.appliedFilters.collegeId ? `学院 #${this.appliedFilters.collegeId}` : '当前授权范围', this.appliedFilters.majorId ? `专业 #${this.appliedFilters.majorId}` : ''].filter(Boolean).join(' · ') },
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
      this.activeDrill = ''; this.workloadTeacherKey = ''; this.exp.purpose = ''; this.exp.downloading = false; this.exp.receipt = null
      this.loadTab()
    }
  },
  methods: {
    indicatorValue(item) {
      if (item.status === 'MODULE_NOT_ENABLED') return '未启用'
      const value = item.unit === '%' ? item.rate : item.value
      return typeof value === 'number' && Number.isFinite(value) ? `${value}${item.unit || ''}` : '—'
    },
    identity() { return academicIdentity(currentUserFromToken(), this.ctx) },
    allowedTab(tab) { return tab === 'export' ? this.canExport : tab === 'snapshot' ? this.canViewSnapshot : true },
    restoreRoute() {
      const query = this.$route.query || {}
      const previous = JSON.stringify([this.tab, this.appliedFilters])
      this.tab = TABS.some(item => item.key === query.tab) ? query.tab : 'overview'
      for (const key of Object.keys(this.filters)) this.filters[key] = typeof query[key] === 'string' ? query[key] : ''
      this.appliedFilters = { ...this.filters }
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
        this.detail.open = true; this.detail.title = `${row?.teacherName || query.teacherKey} · 授课明细`
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
      this.indicators = []; this.sSummary = {}; this.scopeBlocked = false
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
        this.detail.rows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `${this.tab}-${i}-${r.studentNo || r.courseId || r.taskId || r.gradeId || r.resultId || r.incidentId || r.bookingId || ''}` }))
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
.stats-kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 16px; }
.stats-kpi-card { display: flex; min-width: 0; min-height: 108px; flex-direction: column; gap: 8px; padding: 16px 18px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.stats-kpi-card.is-warning { border-color: #efd19d; background: #fff8e9; }
.stats-kpi-card > span { color: var(--text-secondary); font-size: 12px; }
.stats-kpi-card > strong { overflow: hidden; color: var(--text-primary); font-size: 25px; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
.stats-kpi-card.is-warning > strong { color: #9a5b00; }
.stats-kpi-card > small { margin-top: auto; color: var(--text-secondary); font-size: 11px; line-height: 1.5; }
.stats-stage-rail { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; padding: 15px 18px; margin: 0 0 16px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); list-style: none; }
.stats-stage-rail li { position: relative; display: flex; align-items: center; gap: 10px; min-width: 0; }
.stats-stage-rail li:not(:last-child)::after { position: absolute; top: 15px; right: 10px; width: calc(100% - 46px); height: 1px; background: var(--border-base); content: ''; transform: translateX(100%); }
.stats-stage-rail b { z-index: 1; display: grid; width: 30px; height: 30px; flex: 0 0 30px; place-items: center; border: 1px solid var(--border-base); border-radius: 50%; background: var(--bg-card); color: var(--text-secondary); font-size: 12px; }
.stats-stage-rail span { display: grid; gap: 3px; min-width: 0; }
.stats-stage-rail strong { color: var(--text-primary); font-size: 12px; }
.stats-stage-rail small { color: var(--text-secondary); font-size: 10px; }
.stats-stage-rail .is-done b { border-color: #b8dbc8; background: #eef9f3; color: #2f8657; }
.stats-stage-rail .is-current b { border-color: var(--stats-accent); background: var(--stats-accent); color: #fff; }
.stats-export-grid { display: grid; grid-template-columns: minmax(0, 3fr) minmax(240px, 1fr); gap: 16px; }
.stats-export-card { overflow: hidden; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.stats-export-card > header { padding: 15px 18px; border-bottom: 1px solid var(--border-base); }
.stats-export-card h2 { margin: 0; color: var(--text-primary); font-size: 15px; }
.stats-export-card .aa-export-form { border: 0; border-radius: 0; }
.stats-export-purpose { min-width: 100% !important; max-width: none !important; }
.stats-export-purpose textarea { min-height: 92px; resize: vertical; padding: 10px 12px; border: 1px solid var(--border-base); border-radius: 7px; background: var(--bg-card); color: var(--text-primary); font: inherit; line-height: 1.5; }
.stats-export-card > footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 13px 18px; border-top: 1px solid var(--border-base); background: var(--bg-soft, #f5f8fd); color: var(--text-secondary); font-size: 11px; }
.stats-export-rules dl { display: grid; gap: 0; margin: 0; }
.stats-export-rules dl > div { padding: 15px 18px; border-bottom: 1px solid var(--border-base); }
.stats-export-rules dl > div:last-child { border-bottom: 0; }
.stats-export-rules dt { margin-bottom: 5px; color: var(--text-primary); font-size: 12px; font-weight: 650; }
.stats-export-rules dd { margin: 0; color: var(--text-secondary); font-size: 11px; line-height: 1.55; }
.stats-export-receipt { margin-top: 16px; }
.stats-export-receipt > div { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 18px; }
.stats-export-receipt span { color: var(--text-secondary); font-size: 12px; }
.stats-analysis-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.stats-analysis-panel { min-width: 0; overflow: hidden; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.stats-analysis-panel > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 15px 18px; border-bottom: 1px solid var(--border-base); }
.stats-analysis-panel h2 { font-size: 15px; margin: 0; }
.stats-analysis-panel header p, .stats-analysis-panel header > span, .stats-analysis-caption, .stats-cell-note { font-size: 12px; color: var(--text-secondary); line-height: 1.6; }
.stats-analysis-panel header p { margin: 6px 0 0; }
.stats-analysis-panel select { max-width: 220px; min-width: 120px; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: 6px; padding: 6px; font: inherit; font-size: 12px; }
.stats-analysis-caption { margin: 12px 18px; }
.stats-analysis-panel > .app-button { margin: 0 18px 18px; }
.stats-cell-note { display: block; margin-top: 4px; }
.stats-indicator-ledger { margin-bottom: 16px; }
@container academic-body (max-width: 900px) { .stats-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@container academic-body (max-width: 720px) { .stats-analysis-grid { grid-template-columns: minmax(0, 1fr); } }
@container academic-body (max-width: 720px) { .stats-export-grid { grid-template-columns: minmax(0, 1fr); }.stats-stage-rail { grid-template-columns: minmax(0, 1fr); gap: 10px; }.stats-stage-rail li::after { display: none; } }
@container academic-body (max-width: 430px) { .stats-kpi-grid { grid-template-columns: minmax(0, 1fr); } }
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-200, #e5e6eb); margin-bottom: 14px; flex-wrap: wrap; }
.aa-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; white-space: nowrap; }
.aa-tab.is-active { color: var(--primary-color, #165dff); border-bottom-color: var(--primary-color, #165dff); font-weight: 600; }
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { min-width: 160px; }
.mp-btn--ghost { background: transparent; border: 1px solid var(--border-300, #d0d3d9); color: var(--text-700, #4e5969); }
.aa-scope-note { margin: 4px 0; padding: 10px 12px; background: var(--warning-50, #fff7e8); border: 1px solid var(--warning-200, #ffcf8b); border-radius: 6px; color: var(--warning-700, #a86400); font-size: 13px; }
.aa-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.aa-groups .app-g2-chart { margin-bottom: 8px; }
.aa-card { display: flex; flex-direction: column; gap: 6px; padding: 16px; text-align: left; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); cursor: default; transition: box-shadow .15s, border-color .15s; }
.aa-card--drill { cursor: pointer; }
.aa-card--drill:hover { border-color: var(--primary-400, #6aa1ff); box-shadow: 0 2px 10px rgba(22, 93, 255, .08); }
.aa-card--active { border-color: var(--primary-500, #165dff); box-shadow: 0 2px 12px rgba(22, 93, 255, .14); }
.aa-card--muted { background: var(--fill-50, #f7f8fa); }
.aa-card--static { cursor: default; }
.aa-card__label { font-size: 13px; color: var(--text-600, #6b7280); }
.aa-card__value { font-size: 26px; font-weight: 700; color: var(--text-900, #1f2329); line-height: 1.1; }
.aa-card__value em { font-size: 14px; font-weight: 500; margin-left: 2px; color: var(--text-500, #86909c); font-style: normal; }
.aa-card__value--empty { color: var(--text-400, #c9cdd4); }
.aa-card__sub { font-size: 12px; color: var(--text-500, #86909c); }
.aa-card__na { font-size: 18px; font-weight: 600; color: var(--text-400, #c9cdd4); }
.aa-card__drill-hint { font-size: 12px; color: var(--primary-500, #165dff); margin-top: 2px; }
.aa-groups { margin-top: 12px; padding: 12px 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-groups__title { font-size: 12px; color: var(--text-500, #86909c); margin-bottom: 6px; }
.aa-group-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; border-bottom: 1px dashed var(--border-100, #f0f1f3); }
.aa-group-row:last-child { border-bottom: none; }
.aa-drill { margin-top: 12px; padding: 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-drill__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.aa-export-form { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; padding: 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.mp-link { margin-top: 10px; }

/* Statistics stays inside the shared shell; styles are limited to this page. */
.aa-statistics { --stats-accent: var(--pri, #285bb5); }
.stats-topic-select { display: flex; align-items: center; gap: 10px; color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
.stats-topic-select select { max-width: 100%; height: 38px; padding: 0 30px 0 12px; border: 1px solid var(--border-base); border-radius: 7px; background: var(--bg-card); color: var(--text-primary); font: inherit; font-size: 13px; }
.stats-intro { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: -10px; color: var(--text-secondary); font-size: 13px; }
.stats-intro p { margin: 0; line-height: 1.6; }
.stats-intro span { font-size: 12px; white-space: nowrap; }
.stats-dimensions { display: flex; gap: 20px; border-bottom: 1px solid var(--border-base); overflow-x: auto; }
.stats-dimensions button { flex: 0 0 auto; min-height: 40px; padding: 8px 0; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--text-secondary); font-size: 13px; cursor: pointer; }
.stats-dimensions button.active { border-bottom-color: var(--stats-accent); color: var(--stats-accent); font-weight: 650; }
.aa-statistics .aa-filter { display: flex; align-items: flex-end; gap: 14px; padding: 16px; margin: 0; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-statistics .aa-filter__item { display: flex; flex-direction: column; align-items: stretch; gap: 7px; min-width: 160px; max-width: 240px; flex: 1 1 170px; white-space: nowrap; font-size: 12px; }
.aa-statistics .aa-filter__item :deep(.app-entity-picker) { width: 100%; min-width: 0; }
.stats-scope { margin: 8px 0 16px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.stats-section { margin-bottom: 22px; }
.stats-section > header { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; margin: 0 0 12px; }
.stats-section h2 { margin: 0; font-size: 15px; color: var(--text-primary); font-weight: 650; }
.stats-section header span { font-size: 12px; color: var(--text-secondary); }
.aa-statistics .aa-cards, .aa-statistics .aa-metric-grid { grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.aa-statistics .aa-card { min-height: 118px; padding: 16px 18px; gap: 10px; box-shadow: none; border-color: var(--border-base); background: var(--bg-card); }
.aa-statistics .aa-card__value { font-size: 30px; font-variant-numeric: tabular-nums; letter-spacing: -.5px; }
.aa-statistics .aa-card__label { font-size: 13px; }
.aa-statistics .aa-card__sub { line-height: 1.5; }
.aa-statistics .aa-card__drill-hint { margin-top: auto; }
.aa-statistics :is(button, select, input):focus-visible { outline: 2px solid var(--stats-accent); outline-offset: 2px; }
@container academic-body (max-width: 550px) {
  .aa-statistics .aa-filter__item { max-width: none; min-width: 120px; flex-basis: 135px; }
  .aa-statistics .aa-cards, .aa-statistics .aa-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aa-statistics .aa-card { padding: 14px; }
}
@container academic-body (max-width: 350px) {
  .aa-statistics .aa-cards, .aa-statistics .aa-metric-grid { grid-template-columns: minmax(0, 1fr); }
}

</style>
