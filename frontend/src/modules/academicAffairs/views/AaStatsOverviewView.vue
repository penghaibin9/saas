<template>
  <ModulePageShell
    title="教务统计"
    subtitle="15 项教务运行指标 · 按学年学期 / 学院 / 专业多维筛选 · 汇总卡下钻明细"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aa-tabs">
      <button v-for="t in TABS" :key="t.key" :class="['aa-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div class="mp-stack">
      <!-- 多维筛选栏（导出报表 Tab 使用自己的表单，不复用此栏；教学资源为校级共享资产，
           无学期/学院维度，见 resource_stats 后端注释，本栏对该 Tab 不适用） -->
      <div v-if="tab !== 'export' && tab !== 'resource'" class="aa-filter">
        <label class="aa-filter__item">学期
          <select v-model="filters.termId" class="aa-input aa-input--sm">
            <option value="">全部学期</option>
            <option v-for="t in opts.terms" :key="t.id" :value="t.id">{{ t.label }}{{ t.isCurrent ? '（当前）' : '' }}</option>
          </select>
        </label>
        <label class="aa-filter__item">学院
          <select v-model="filters.collegeId" class="aa-input aa-input--sm" @change="filters.majorId = ''">
            <option value="">全部学院</option>
            <option v-for="c in opts.colleges" :key="c.id" :value="c.id">{{ c.label }}</option>
          </select>
        </label>
        <label v-if="tab === 'overview' || tab === 'registration'" class="aa-filter__item">专业
          <select v-model="filters.majorId" class="aa-input aa-input--sm">
            <option value="">全部专业</option>
            <option v-for="m in majorOptions" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
        </label>
        <label v-if="tab === 'course'" class="aa-filter__item">类别
          <input v-model="filters.category" class="aa-input aa-input--sm" placeholder="可空=全部" />
        </label>
        <label v-if="tab === 'grade'" class="aa-filter__item">课程名（下钻筛选）
          <input v-model="filters.courseName" class="aa-input aa-input--sm" placeholder="可空=全部" />
        </label>
        <label v-if="tab === 'graduation'" class="aa-filter__item">预审批次ID
          <input v-model="filters.batchId" class="aa-input aa-input--sm" placeholder="可空=不按批次" />
        </label>
        <button class="mp-btn" :disabled="loading" @click="search">查询</button>
        <button v-if="tab === 'overview'" class="mp-btn mp-btn--ghost" :disabled="loading" @click="openExport">导出 Excel</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="loadTab" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <p v-if="scopeBlocked" class="aa-scope-note">当前账号未配置教务数据范围，暂无可见统计数据（如为学院教务员请联系管理员配置本院范围）。</p>

        <!-- ══ 教务总览（既有实现，保持不变） ══ -->
        <template v-if="tab === 'overview'">
          <div class="aa-cards">
            <button
              v-for="ind in indicators"
              :key="ind.key"
              class="aa-card"
              :class="{ 'aa-card--muted': ind.status === 'MODULE_NOT_ENABLED', 'aa-card--active': activeDrill === ind.key, 'aa-card--drill': drillable(ind) }"
              :disabled="ind.status === 'MODULE_NOT_ENABLED'"
              @click="onCardClick(ind)"
            >
              <span class="aa-card__label">{{ ind.label }}</span>
              <template v-if="ind.status === 'MODULE_NOT_ENABLED'">
                <span class="aa-card__na">未启用</span>
                <span class="aa-card__sub">{{ ind.message }}</span>
              </template>
              <template v-else-if="ind.rate !== null && ind.rate !== undefined && ind.denominator !== undefined && ind.numerator !== undefined && ind.unit === '%'">
                <span class="aa-card__value">{{ ind.rate }}<em>%</em></span>
                <span class="aa-card__sub">{{ ind.numerator }} / {{ ind.denominator }}</span>
              </template>
              <template v-else-if="ind.unit === '%'">
                <span class="aa-card__value aa-card__value--empty">—</span>
                <span class="aa-card__sub">{{ ind.numerator }} / {{ ind.denominator }}</span>
              </template>
              <template v-else>
                <span class="aa-card__value">{{ ind.value }}<em v-if="ind.unit">{{ ind.unit }}</em></span>
                <span v-if="ind.groups && ind.groups.length" class="aa-card__sub">{{ groupSummary(ind) }}</span>
              </template>
              <span v-if="drillable(ind)" class="aa-card__drill-hint">点击下钻 →</span>
            </button>
          </div>

          <div v-if="activeDrill" class="aa-drill">
            <div class="aa-drill__head">
              <strong>{{ drillTitle }}</strong>
              <button class="mp-link" @click="closeDrill">收起</button>
            </div>
            <LoadingState v-if="drill.loading" />
            <EmptyState v-else-if="!drill.rows.length" title="无明细数据" description="当前范围内没有可下钻的记录" />
            <DataTable v-else :columns="drillColumns" :rows="drill.rows" row-key="rowKey" :pagination="drill.pagination" @page-change="onDrillPage" />
          </div>
        </template>

        <!-- ══ 学籍统计（02）══ -->
        <template v-else-if="tab === 'statusChange'">
          <div class="aa-metric-grid">
            <AppMetricCard title="学籍异动人数（本学期 EFFECTIVE）" :value="sSummary.total ?? 0" />
          </div>
          <div v-if="sSummary.byType && sSummary.byType.length" class="aa-groups">
            <AppG2Chart :spec="distSpec(sSummary.byType)" :height="200" />
            <div v-for="g in sSummary.byType" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看异动明细 →</button>
        </template>

        <!-- ══ 注册统计（03）══ -->
        <template v-else-if="tab === 'registration'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">注册完成率</span>
              <span class="aa-card__value">{{ sSummary.rate ?? '—' }}<em v-if="sSummary.rate !== null && sSummary.rate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.registered ?? 0 }} / {{ sSummary.expected ?? 0 }}</span>
            </div>
          </div>
          <button class="mp-link" @click="openDetail">查看未注册学生名单 →</button>
        </template>

        <!-- ══ 课程统计（04）══ -->
        <template v-else-if="tab === 'course'">
          <div class="aa-metric-grid">
            <AppMetricCard title="启用课程总数" :value="sSummary.total ?? 0" unit="门" />
          </div>
          <div v-if="sSummary.byCategory && sSummary.byCategory.length" class="aa-groups">
            <div class="aa-groups__title">按类别</div>
            <AppG2Chart :spec="distSpec(sSummary.byCategory)" :height="200" />
            <div v-for="g in sSummary.byCategory" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <div v-if="sSummary.byCollege && sSummary.byCollege.length" class="aa-groups">
            <div class="aa-groups__title">按学院</div>
            <AppG2Chart :spec="distSpec(sSummary.byCollege, '学院#')" :height="200" />
            <div v-for="g in sSummary.byCollege" :key="g.key" class="aa-group-row"><span>学院#{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看课程明细 →</button>
        </template>

        <!-- ══ 教学任务统计（05）══ -->
        <template v-else-if="tab === 'teachingTask'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">教学任务确认完成率</span>
              <span class="aa-card__value">{{ sSummary.rate ?? '—' }}<em v-if="sSummary.rate !== null && sSummary.rate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.confirmed ?? 0 }} / {{ sSummary.expected ?? 0 }}</span>
            </div>
          </div>
          <button class="mp-link" @click="openDetail">查看未确认任务 →</button>
        </template>

        <!-- ══ 课表统计（06）══ -->
        <template v-else-if="tab === 'schedule'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">课表发布覆盖率</span>
              <span class="aa-card__value">{{ sSummary.publishedRate ?? '—' }}<em v-if="sSummary.publishedRate !== null && sSummary.publishedRate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.published ?? 0 }} / {{ sSummary.totalBatches ?? 0 }} 批次</span>
            </div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">未解决冲突数</span><span class="aa-card__value">{{ sSummary.unresolvedConflicts ?? 0 }}</span></div>
          </div>
          <button class="mp-link" @click="openDetail">查看冲突明细 →</button>
        </template>

        <!-- ══ 选课统计（08）══ -->
        <template v-else-if="tab === 'courseSelection'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">选课填充率</span>
              <span class="aa-card__value">{{ sSummary.fillRate ?? '—' }}<em v-if="sSummary.fillRate !== null && sSummary.fillRate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.totalSelected ?? 0 }} / {{ sSummary.totalCapacity ?? 0 }}</span>
            </div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">选课记录数</span><span class="aa-card__value">{{ sSummary.recordCount ?? 0 }}</span></div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">低人数课程</span><span class="aa-card__value" :class="{ 'aa-card__value--empty': !sSummary.lowEnrollCount }">{{ sSummary.lowEnrollCount ?? 0 }}</span></div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">满额课程</span><span class="aa-card__value">{{ sSummary.fullCount ?? 0 }}</span></div>
          </div>
          <div v-if="sSummary.byBatchStatus && sSummary.byBatchStatus.length" class="aa-groups">
            <div class="aa-groups__title">批次状态分布</div>
            <AppG2Chart :spec="distSpec(sSummary.byBatchStatus)" :height="200" />
            <div v-for="g in sSummary.byBatchStatus" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看低人数课程清单 →</button>
        </template>

        <!-- ══ 考务统计（09）══ -->
        <template v-else-if="tab === 'exam'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">考试课程确认率</span>
              <span class="aa-card__value">{{ sSummary.confirmRate ?? '—' }}<em v-if="sSummary.confirmRate !== null && sSummary.confirmRate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.confirmedCount ?? 0 }} / {{ sSummary.courseTotal ?? 0 }}</span>
            </div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">缺考人次</span><span class="aa-card__value">{{ sSummary.absentCount ?? 0 }}</span></div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">违纪人次</span><span class="aa-card__value">{{ sSummary.violationCount ?? 0 }}</span></div>
          </div>
          <div v-if="sSummary.byBatchStatus && sSummary.byBatchStatus.length" class="aa-groups">
            <div class="aa-groups__title">批次状态分布</div>
            <AppG2Chart :spec="distSpec(sSummary.byBatchStatus)" :height="200" />
            <div v-for="g in sSummary.byBatchStatus" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看缺考/违纪明细 →</button>
        </template>

        <!-- ══ 成绩统计（10）══ -->
        <template v-else-if="tab === 'grade'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">挂科率</span>
              <span class="aa-card__value">{{ sSummary.failRate ?? '—' }}<em v-if="sSummary.failRate !== null && sSummary.failRate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.failNumerator ?? 0 }} / {{ sSummary.failDenominator ?? 0 }}</span>
            </div>
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">成绩录入发布率</span>
              <span class="aa-card__value">{{ sSummary.entryPublishRate ?? '—' }}<em v-if="sSummary.entryPublishRate !== null && sSummary.entryPublishRate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.publishNumerator ?? 0 }} / {{ sSummary.publishDenominator ?? 0 }}</span>
            </div>
            <div class="aa-card aa-card--static"><span class="aa-card__label">补考/重修人次</span><span class="aa-card__value">{{ sSummary.makeupCount ?? 0 }} / {{ sSummary.retakeCount ?? 0 }}</span><span class="aa-card__sub">补考 / 重修</span></div>
          </div>
          <button class="mp-link" @click="openDetail">查看挂科学生明细 →</button>
        </template>

        <!-- ══ 学业预警统计（11）══ -->
        <template v-else-if="tab === 'warning'">
          <div class="aa-metric-grid">
            <AppMetricCard title="未关闭预警数" :value="sSummary.total ?? 0" accent="warning" />
          </div>
          <div v-if="sSummary.byLevel && sSummary.byLevel.length" class="aa-groups">
            <div class="aa-groups__title">按等级</div>
            <AppG2Chart :spec="distSpec(sSummary.byLevel)" :height="200" />
            <div v-for="g in sSummary.byLevel" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <div v-if="sSummary.bySource && sSummary.bySource.length" class="aa-groups">
            <div class="aa-groups__title">按来源</div>
            <AppG2Chart :spec="distSpec(sSummary.bySource)" :height="200" />
            <div v-for="g in sSummary.bySource" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看预警明细 →</button>
        </template>

        <!-- ══ 毕业资格统计（12）══ -->
        <template v-else-if="tab === 'graduation'">
          <div class="aa-cards">
            <div class="aa-card aa-card--static">
              <span class="aa-card__label">毕业资格通过率</span>
              <span class="aa-card__value">{{ sSummary.passRate ?? '—' }}<em v-if="sSummary.passRate !== null && sSummary.passRate !== undefined">%</em></span>
              <span class="aa-card__sub">{{ sSummary.passed ?? 0 }} / {{ sSummary.expected ?? 0 }}</span>
            </div>
          </div>
          <div v-if="sSummary.byAbnormalItem && sSummary.byAbnormalItem.length" class="aa-groups">
            <div class="aa-groups__title">异常项分布</div>
            <AppG2Chart :spec="distSpec(sSummary.byAbnormalItem)" :height="200" />
            <div v-for="g in sSummary.byAbnormalItem" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看异常学生名单 →</button>
        </template>

        <!-- ══ 教师工作量统计（13，基础参考，非正式核算）══ -->
        <template v-else-if="tab === 'workload'">
          <AppInlineAlert type="warning" description="本页为教学任务量基础统计（学时合计+任务数），非学校正式工作量核算结果；如需正式核算（含课程/班型/职称系数），需学校教务处/人事处明确规则后另行实现。" />
          <EmptyState v-if="!sSummary.ranking || !sSummary.ranking.length" title="暂无数据" description="当前范围内没有可统计的教学任务" />
          <DataTable v-else :columns="workloadColumns" :rows="sSummary.ranking" row-key="teacherKey">
            <template #cell-ops="{ row }"><button class="mp-link" @click="viewWorkloadDetail(row)">查看明细</button></template>
          </DataTable>
        </template>

        <!-- ══ 教学资源统计（14）══ -->
        <template v-else-if="tab === 'resource'">
          <div class="aa-metric-grid">
            <AppMetricCard title="教室总数" :value="sSummary.classroomTotal ?? 0" unit="间" />
            <AppMetricCard title="预约总数" :value="sSummary.bookingTotal ?? 0" />
          </div>
          <div v-if="sSummary.byStatus && sSummary.byStatus.length" class="aa-groups">
            <div class="aa-groups__title">教室状态分布</div>
            <AppG2Chart :spec="distSpec(sSummary.byStatus)" :height="200" />
            <div v-for="g in sSummary.byStatus" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <div v-if="sSummary.byType && sSummary.byType.length" class="aa-groups">
            <div class="aa-groups__title">教室类型分布</div>
            <AppG2Chart :spec="distSpec(sSummary.byType)" :height="200" />
            <div v-for="g in sSummary.byType" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <div v-if="sSummary.byBookingStatus && sSummary.byBookingStatus.length" class="aa-groups">
            <div class="aa-groups__title">预约状态分布</div>
            <AppG2Chart :spec="distSpec(sSummary.byBookingStatus)" :height="200" />
            <div v-for="g in sSummary.byBookingStatus" :key="g.key" class="aa-group-row"><span>{{ g.key }}</span><b>{{ g.count }}</b></div>
          </div>
          <button class="mp-link" @click="openDetail">查看待审核预约 →</button>
        </template>

        <!-- ══ 导出报表（15）══ -->
        <template v-else-if="tab === 'export'">
          <div class="aa-export-form">
            <label class="aa-filter__item">导出维度
              <select v-model="exp.domain" class="aa-input">
                <option v-for="d in exportDomains" :key="d.key" :value="d.key">{{ d.label }}</option>
              </select>
            </label>
            <label class="aa-filter__item">学期
              <select v-model="exp.termId" class="aa-input"><option value="">全部学期</option><option v-for="t in opts.terms" :key="t.id" :value="t.id">{{ t.label }}</option></select>
            </label>
            <label class="aa-filter__item">学院
              <select v-model="exp.collegeId" class="aa-input"><option value="">全部学院</option><option v-for="c in opts.colleges" :key="c.id" :value="c.id">{{ c.label }}</option></select>
            </label>
            <label class="aa-filter__item">导出用途（必填，≥5字，写审计+水印）
              <input v-model="exp.purpose" class="aa-input" placeholder="如：教务处月度汇报" />
            </label>
            <button class="mp-btn" :disabled="exp.downloading" @click="doExport">{{ exp.downloading ? '导出中…' : '发起导出' }}</button>
          </div>
          <p class="aa-scope-note">当前为同步下载：点击后立即生成并下载 xlsx 文件（不保留异步导出历史列表，如需"导出历史/失败重试"请登记待办）。</p>
        </template>

        <!-- 通用下钻明细面板（除总览/工作量/导出外的 11 个 Tab 共用） -->
        <div v-if="detail.open" class="aa-drill">
          <div class="aa-drill__head">
            <strong>{{ detail.title }}</strong>
            <button class="mp-link" @click="detail.open = false">收起</button>
          </div>
          <LoadingState v-if="detail.loading" />
          <EmptyState v-else-if="!detail.rows.length" title="无明细数据" description="当前范围内没有可查看的记录" />
          <DataTable v-else :columns="detail.columns" :rows="detail.rows" row-key="rowKey" :pagination="detail.pagination" @page-change="onDetailPage">
            <template #cell-abnormalItems="{ row }">{{ (row.abnormalItems || []).join('、') }}</template>
            <template #cell-courses="{ row }">{{ (row.courses || []).map((c) => c.courseName).join('、') }}</template>
          </DataTable>
        </div>
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
import { AppInlineAlert, AppMetricCard, AppG2Chart } from '@/components/common'
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

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
  { key: 'export', label: '导出报表' }
]

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
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppInlineAlert, AppMetricCard, AppG2Chart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TABS,
      tab: 'overview',
      loading: true,
      error: '',
      filters: { termId: '', collegeId: '', majorId: '', category: '', courseName: '', batchId: '', itemType: '' },
      opts: { terms: [], colleges: [], majors: [] },
      // 教务总览（既有）
      indicators: [],
      scopeBlocked: false,
      activeDrill: '',
      drill: { loading: false, rows: [], pagination: { page: 1, pageSize: 20, total: 0 } },
      // 其余 9 个 Tab 的聚合结果
      sSummary: {},
      // 通用下钻明细面板（8 个 Tab 共用）
      detail: { open: false, loading: false, title: '', rows: [], columns: [], pagination: { page: 1, pageSize: 20, total: 0 } },
      // 导出报表
      exp: { domain: 'overview', termId: '', collegeId: '', purpose: '', downloading: false },
      exportDomains: EXPORT_DOMAINS,
      workloadTeacherKey: '',
      workloadColumns: [
        { key: 'teacherName', title: '教师' }, { key: 'totalHours', title: '学时合计' },
        { key: 'taskCount', title: '任务数' }, { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    majorOptions() {
      if (!this.filters.collegeId) return this.opts.majors
      return this.opts.majors.filter((m) => String(m.collegeId) === String(this.filters.collegeId))
    },
    drillTitle() {
      return this.activeDrill ? (DRILL_META[this.activeDrill]?.title || '明细') : ''
    },
    drillColumns() {
      return this.activeDrill ? (DRILL_META[this.activeDrill]?.columns || []) : []
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && TABS.some((t) => t.key === q)) this.tab = q
    this.init()
  },
  methods: {
    drillable(ind) {
      return !!DRILL_META[ind.key] && ind.status !== 'MODULE_NOT_ENABLED'
    },
    // 仅用于展示：把既有分布数组 [{key,count}] 映射为柱状图 spec，不改动任何数据来源
    distSpec(arr, prefix = '') {
      return {
        type: 'interval',
        data: (arr || []).map((g) => ({ name: `${prefix}${g.key}`, value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    groupSummary(ind) {
      return (ind.groups || []).map((g) => `${g.key}:${g.count}`).join('  ')
    },
    switchTab(k) {
      this.tab = k
      this.activeDrill = ''
      this.detail.open = false
      this.loadTab()
    },
    async init() {
      const f = await academicAffairsApi.getStatsFilters()
      if (f.code === 0) this.opts = f.data
      await this.loadTab()
    },
    search() {
      this.activeDrill = ''
      this.detail.open = false
      this.loadTab()
    },
    baseParams() {
      return {
        termId: this.filters.termId || undefined,
        collegeId: this.filters.collegeId || undefined,
        majorId: this.filters.majorId || undefined
      }
    },
    async loadTab() {
      this.loading = true
      this.error = ''
      if (this.tab === 'overview') {
        await this.loadOverview()
      } else if (this.tab === 'workload') {
        await this.loadWorkload()
      } else if (this.tab === 'export') {
        this.loading = false
      } else {
        await this.loadSummaryTab()
      }
      this.loading = false
    },
    async loadOverview() {
      const res = await academicAffairsApi.getStatsOverview(this.baseParams())
      if (res.code === 0) {
        this.indicators = res.data.indicators || []
        this.scopeBlocked = !!res.data.scope?.blocked
      } else {
        this.error = res.message || '加载失败'
      }
      if (this.activeDrill) this.loadDrill()
    },
    async loadSummaryTab() {
      const meta = TAB_META[this.tab]
      if (!meta) return
      const params = { ...this.baseParams() }
      if (this.tab === 'course') params.category = this.filters.category || undefined
      if (this.tab === 'graduation') params.batchId = this.filters.batchId || undefined
      const res = await meta.summary(academicAffairsApi, params)
      if (res.code === 0) {
        this.sSummary = res.data || {}
        this.scopeBlocked = !!this.sSummary.scope?.blocked
      } else {
        this.error = res.message || '加载失败'
        this.sSummary = {}
      }
      if (this.detail.open) this.loadDetail()
    },
    async loadWorkload() {
      const res = await academicAffairsApi.getStatsWorkload(this.baseParams())
      if (res.code === 0) {
        this.sSummary = res.data || {}
        this.scopeBlocked = !!this.sSummary.scope?.blocked
      } else {
        this.error = res.message || '加载失败'
        this.sSummary = {}
      }
    },
    onCardClick(ind) {
      if (!this.drillable(ind)) return
      if (this.activeDrill === ind.key) {
        this.closeDrill()
        return
      }
      this.activeDrill = ind.key
      this.drill.pagination.page = 1
      this.loadDrill()
    },
    closeDrill() {
      this.activeDrill = ''
      this.drill.rows = []
    },
    onDrillPage(p) {
      this.drill.pagination.page = p
      this.loadDrill()
    },
    async loadDrill() {
      const meta = DRILL_META[this.activeDrill]
      if (!meta) return
      this.drill.loading = true
      const params = { ...this.baseParams(), page: this.drill.pagination.page, pageSize: this.drill.pagination.pageSize }
      const res = await meta.fetch(academicAffairsApi, params)
      if (res.code === 0) {
        this.drill.rows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `${this.activeDrill}-${i}-${r.studentNo || ''}` }))
        this.drill.pagination.total = res.data.total || 0
      } else {
        toast.error(res.message || '下钻失败')
        this.drill.rows = []
      }
      this.drill.loading = false
    },
    openDetail() {
      const meta = TAB_META[this.tab]
      if (!meta) return
      this.detail.open = true
      this.detail.title = meta.detailTitle
      this.detail.columns = meta.detailColumns
      this.detail.pagination.page = 1
      this.loadDetail()
    },
    onDetailPage(p) {
      this.detail.pagination.page = p
      this.loadDetail()
    },
    async loadDetail() {
      const meta = TAB_META[this.tab]
      if (!meta) return
      this.detail.loading = true
      const params = {
        ...this.baseParams(),
        category: this.filters.category || undefined,
        courseName: this.filters.courseName || undefined,
        batchId: this.filters.batchId || undefined,
        itemType: this.filters.itemType || undefined,
        page: this.detail.pagination.page,
        pageSize: this.detail.pagination.pageSize
      }
      const res = await meta.detailFetch(academicAffairsApi, params)
      if (res.code === 0) {
        this.detail.rows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `${this.tab}-${i}-${r.studentNo || r.courseId || r.taskId || r.gradeId || r.resultId || r.incidentId || r.bookingId || ''}` }))
        this.detail.pagination.total = res.data.total || 0
      } else {
        toast.error(res.message || '下钻失败')
        this.detail.rows = []
      }
      this.detail.loading = false
    },
    async viewWorkloadDetail(row) {
      const res = await academicAffairsApi.getStatsWorkloadDetail({ teacherKey: row.teacherKey, collegeId: this.filters.collegeId || undefined, page: 1, pageSize: 20 })
      if (res.code !== 0) {
        toast.error(res.message || '加载失败')
        return
      }
      this.detail.open = true
      this.detail.title = `${row.teacherName || row.teacherKey} · 授课明细`
      this.detail.columns = [
        { key: 'courseName', title: '课程' }, { key: 'teachingClassName', title: '教学班' },
        { key: 'weeklyHours', title: '周学时' }, { key: 'totalHours', title: '计划总学时' }, { key: 'status', title: '状态' }
      ]
      this.detail.rows = (res.data.list || []).map((r, i) => ({ ...r, rowKey: `wl-${i}-${r.taskId}` }))
      this.detail.pagination = { page: 1, pageSize: 20, total: res.data.total || 0 }
    },
    async openExport() {
      this.tab = 'export'
      this.exp.domain = 'overview'
    },
    async doExport() {
      if (!this.exp.purpose || this.exp.purpose.trim().length < 5) {
        toast.error('导出用途必填且不少于 5 个字')
        return
      }
      this.exp.downloading = true
      const res = await academicAffairsApi.exportStats({
        domain: this.exp.domain,
        termId: this.exp.termId ? Number(this.exp.termId) : undefined,
        collegeId: this.exp.collegeId ? Number(this.exp.collegeId) : undefined,
        purpose: this.exp.purpose.trim()
      })
      this.exp.downloading = false
      if (res.code !== 0) {
        toast.error(res.message || '导出失败')
        return
      }
      const label = (EXPORT_DOMAINS.find((d) => d.key === this.exp.domain) || {}).label || '教务统计'
      const href = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = href
      a.download = `${label}-${Date.now()}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
      toast.success('导出成功')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
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
.aa-card__drill-hint { font-size: 11px; color: var(--primary-500, #165dff); margin-top: 2px; }
.aa-groups { margin-top: 12px; padding: 12px 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-groups__title { font-size: 12px; color: var(--text-500, #86909c); margin-bottom: 6px; }
.aa-group-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; border-bottom: 1px dashed var(--border-100, #f0f1f3); }
.aa-group-row:last-child { border-bottom: none; }
.aa-drill { margin-top: 12px; padding: 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-drill__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.aa-export-form { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; padding: 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.mp-link { margin-top: 10px; }
</style>
