<template>
  <ModulePageShell
    title="问题预警 · 毕设归档 · 毕设统计"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-tabs" aria-label="风险归档工作区">
      <button v-if="canRiskView" class="gp-tabs__item" :class="{ 'is-active': tab === 'risk' }" :disabled="actionLocked" @click="switchTab('risk')">问题预警</button>
      <button v-if="canArchiveView" class="gp-tabs__item" :class="{ 'is-active': tab === 'archive' }" :disabled="actionLocked" @click="switchTab('archive')">毕设归档</button>
      <button v-if="canStatsView" class="gp-tabs__item" :class="{ 'is-active': tab === 'stats' }" :disabled="actionLocked" @click="switchTab('stats')">毕设统计</button>
    </div>

    <aside v-if="actionReceipt" class="ra-receipt" :class="{ 'is-unknown': actionReceipt.unknown }" role="status">
      <div><strong>{{ actionReceipt.title }}</strong><span>{{ actionReceipt.result }}</span><small>{{ actionReceipt.next }}</small></div>
      <button v-if="actionReceipt.unknown" type="button" :disabled="actionLocked" @click="verifyUnknownResult">刷新台账核对</button>
      <button v-else type="button" :disabled="actionLocked" @click="actionReceipt = null">关闭</button>
    </aside>

    <!-- 问题预警：最近扫描事实 + 13 类真实规则 + 连续双栏处置。 -->
    <div v-if="tab === 'risk' && canRiskView" class="mp-stack ra-panel">
      <section v-if="hasBatch" class="rk-command" aria-label="风险扫描结论">
        <div class="rk-command__headline">
          <span>最近扫描事实</span>
          <strong>{{ riskConclusion }}</strong>
          <small>{{ batchStore.selectedBatchName || batchStore.selectedBatchId }} · 风险由服务端规则扫描生成，前端不自行判定。</small>
        </div>
        <div class="rk-command__metrics">
          <div><b>{{ lastScanStats?.scannedStudents ?? '—' }}</b><span>扫描学生</span></div>
          <div><b>{{ lastScanStats?.newCasesCreated ?? '—' }}</b><span>新增风险</span></div>
          <div><b>{{ lastScanStats?.reopenedCases ?? '—' }}</b><span>重新打开</span></div>
          <div><b>{{ lastScanStats?.elapsedMs == null ? '—' : `${lastScanStats.elapsedMs}ms` }}</b><span>扫描耗时</span></div>
        </div>
        <button v-if="canRiskScan" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doScan">{{ actionBusy === 'scan-risk' ? '扫描中…' : '扫描生成风险项' }}</button>
      </section>

      <section v-if="hasBatch" class="rk-rules" aria-label="13类毕业设计风险规则摘要">
        <div class="rk-rules__head"><div><span>服务端规则目录</span><strong>13 类风险全覆盖</strong></div><small v-if="lastScanAt">上次扫描：{{ formatDateTime(lastScanAt) }}</small><small v-else>尚未执行过扫描</small></div>
        <div class="rk-rules__grid">
          <span v-for="rule in riskRuleCatalog" :key="rule.code" :title="rule.label"><b>{{ rule.code }}</b>{{ rule.label }}</span>
        </div>
      </section>

      <AdvancedFilter
        v-if="hasBatch"
        v-model="riskFilters"
        class="ra-filter"
        :class="{ 'is-command-locked': actionLocked }"
        :aria-disabled="actionLocked"
        :fields="riskFilterFields"
        @search="searchRisks"
        @reset="resetRiskFilters"
      />
      <ErrorState v-if="riskError" :description="riskError" @retry="loadRisks" />
      <LoadingState v-else-if="riskLoading" />
      <EmptyState
        v-else-if="!riskRows.length"
        :title="hasBatch ? '还没有风险记录' : '请先选择或创建毕设批次'"
        :description="hasBatch ? '系统按未选题、导师未确认、任务书、开题、中期、成果、查重、评阅、答辩和归档材料等 13 类真实规则扫描。当前筛选下没有记录时，可重新扫描或调整条件。' : '顶部批次条选择当前工作批次后，再扫描与处置风险。'"
      >
        <template v-if="hasBatch && canRiskScan" #actions>
          <button class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doScan">扫描生成风险项</button>
        </template>
      </EmptyState>
      <div v-else class="rk-split" :class="{ 'is-command-locked': actionLocked }" :aria-busy="actionLocked">
        <aside class="rk-list" aria-label="风险处置队列">
          <div class="rk-list__head"><div><strong>风险队列</strong><small>第 {{ riskPage }} 页 · {{ riskTotal }} 条</small></div><span>{{ riskFilters.status || '全部状态' }}</span></div>
          <ul class="rk-rows">
            <li
              v-for="(row, i) in riskRows"
              :key="row.id"
              class="rk-row"
              :class="{ 'is-active': String(row.id) === riskSelKey, 'is-disabled': actionLocked }"
              :tabindex="actionLocked ? -1 : 0"
              :aria-disabled="actionLocked"
              :aria-current="String(row.id) === riskSelKey ? 'true' : undefined"
              role="button"
              @click="selectRisk(row)"
              @keydown.enter.prevent="selectRisk(row)"
              @keydown.space.prevent="selectRisk(row)"
            >
              <div class="rk-row__main">
                <span class="rk-row__name">{{ row.riskName }}</span>
                <StatusTag :type="row.level === 'CRITICAL' || row.level === 'HIGH' ? 'danger' : 'warning'" :label="levelLabel(row.level)" dot />
              </div>
              <div class="rk-row__sub">{{ row.studentName }} · {{ row.studentNo }}</div>
              <div class="rk-row__meta"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /><span class="rk-row__idx">{{ (riskPage - 1) * riskPageSize + i + 1 }}</span></div>
            </li>
          </ul>
          <div class="ra-pagination"><AppPagination :total="riskTotal" :page="riskPage" :page-size="riskPageSize" :show-size-changer="false" @update:page="changeRiskPage" /></div>
        </aside>
        <section class="rk-pane" aria-label="当前风险处置对象">
          <div class="rk-pane__bar">
            <span>本页第 {{ Math.max(riskSelIndex + 1, 0) }} / {{ riskRows.length }} 条 · 共 {{ riskTotal }} 条</span>
            <label class="rk-pane__auto"><input v-model="riskAutoNext" type="checkbox" :disabled="actionLocked" /> 处置后自动进入下一条</label>
            <span class="rk-pane__nav">
              <button class="mp-link" :disabled="actionLocked || riskSelIndex <= 0" @click="stepRisk(-1)">← 上一条</button>
              <button class="mp-link" :disabled="actionLocked || riskSelIndex >= riskRows.length - 1" @click="stepRisk(1)">下一条 →</button>
            </span>
          </div>
          <EmptyState v-if="!selectedRisk" title="从左侧选择一条风险" description="处置后可自动进入下一条待办风险" />
          <section v-else class="mp-card rk-detail">
            <div class="mp-card__head">
              <div><span class="rk-detail__eyebrow">{{ selectedRisk.riskCode || '风险规则' }} · 当前处置对象</span><span class="mp-card__title">{{ selectedRisk.riskName }}</span></div>
              <button v-if="canStudentView && selectedRisk.gdStudentId" class="mp-link" :disabled="actionLocked" @click="openRiskStudent(selectedRisk)">查看学生档案 →</button>
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
              <div class="ie-actions ie-actions--left">
                <button v-if="canRiskAccept && selectedRisk.status === 'OPEN'" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doAccept(selectedRisk)">受理</button>
                <button v-if="canRiskProcess && selectedRisk.status === 'PROCESSING'" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doProcess(selectedRisk)">记录处理</button>
                <button v-if="canRiskClose && (selectedRisk.status === 'PROCESSING' || (selectedRisk.status === 'OPEN' && selectedRisk.conditionActive === false))" class="mp-btn" :disabled="actionLocked" @click="doClose(selectedRisk)">关闭风险</button>
                <span v-if="selectedRisk.status === 'CLOSED'" class="mp-note">该风险已关闭</span>
              </div>
              <p class="mp-note">受理 / 处理 / 关闭均按 permission + status 执行并写入审计留痕；关闭需填写原因。</p>
            </div>
          </section>
        </section>
      </div>
    </div>

    <!-- 毕设归档：一次性 previewToken 证据 + 连续双栏完整性核验。 -->
    <div v-if="tab === 'archive' && canArchiveView" class="mp-stack ra-panel">
      <section v-if="hasBatch" class="ar-command" aria-label="归档批次命令">
        <div class="ar-command__copy"><span>归档工作结论</span><strong>{{ archiveConclusion }}</strong><small>执行顺序固定为：预览 → 用户确认 → 一次性 previewToken → execute → 服务器回读 / 对账。</small></div>
        <div class="ar-command__actions">
          <button v-if="canArchivePreview && canArchiveFile" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doBatchGenerate">{{ previewBusy === 'batch-generate-preview' ? '预览中…' : '批量生成提交' }}</button>
          <button v-if="canArchivePreview && canArchiveFile" class="mp-btn" :disabled="actionLocked" @click="doBatchFile">{{ previewBusy === 'batch-file-preview' ? '预览中…' : '一键核验备案' }}</button>
          <AppExportButton v-if="canArchiveExport" :export-fn="exportArchivesFn">导出台账</AppExportButton>
        </div>
      </section>

      <section v-if="archivePreviewEvidence" class="ar-preview-evidence" role="status" data-testid="archive-preview-token-evidence">
        <div><span>previewToken</span><strong>{{ archivePreviewEvidence.previewTokenIssued ? '已签发 · 一次性' : '未签发' }}</strong><small>执行或重新预览后失效，不展示原始令牌。</small></div>
        <div><span>档案批次号</span><strong>{{ archivePreviewEvidence.archiveBatchNo || '执行时生成' }}</strong><small>批次 {{ archivePreviewEvidence.batchName || archivePreviewEvidence.batchId }}</small></div>
        <div><span>预计执行</span><strong>{{ archivePreviewEvidence.executableCount ?? 0 }}</strong><small>跳过 {{ archivePreviewEvidence.skippedCount ?? 0 }}</small></div>
        <div><span>预览时间</span><strong>{{ formatDateTime(archivePreviewEvidence.previewedAt) }}</strong><small>{{ archivePreviewEvidence.kindLabel }}</small></div>
      </section>

      <AdvancedFilter
        v-if="hasBatch"
        v-model="archiveFilters"
        class="ra-filter"
        :class="{ 'is-command-locked': actionLocked }"
        :aria-disabled="actionLocked"
        :fields="archiveFilterFields"
        @search="searchArchives"
        @reset="resetArchiveFilters"
      />
      <ErrorState v-if="archiveError" :description="archiveError" @retry="loadArchives" />
      <LoadingState v-else-if="archiveLoading" />
      <EmptyState v-else-if="!archiveRows.length" :title="hasBatch ? '暂无归档记录' : '请先选择或创建毕设批次'" :description="hasBatch ? '当前筛选下没有归档记录，可调整状态或关键词。' : '顶部批次条选择当前工作批次后，再办理归档。'" />
      <div v-else class="rk-split" :class="{ 'is-command-locked': actionLocked }" :aria-busy="actionLocked">
        <aside class="rk-list" aria-label="归档办理队列">
          <div class="rk-list__head"><div><strong>归档队列</strong><small>第 {{ archivePage }} 页 · {{ archiveTotal }} 条</small></div><span>{{ archiveFilters.status || '全部状态' }}</span></div>
          <ul class="rk-rows">
            <li
              v-for="(row, i) in archiveRows"
              :key="row.id"
              class="rk-row"
              :class="{ 'is-active': String(row.id) === archiveSelKey, 'is-disabled': actionLocked }"
              :tabindex="actionLocked ? -1 : 0"
              :aria-disabled="actionLocked"
              :aria-current="String(row.id) === archiveSelKey ? 'true' : undefined"
              role="button"
              @click="selectArchive(row)"
              @keydown.enter.prevent="selectArchive(row)"
              @keydown.space.prevent="selectArchive(row)"
            >
              <div class="rk-row__main"><span class="rk-row__name">{{ row.studentName }}</span><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></div>
              <div class="rk-row__sub">{{ row.studentNo }}</div>
              <div class="rk-row__meta"><span :class="row.missingItems.length ? 'is-missing' : 'is-complete'">{{ row.missingItems.length ? '缺 ' + row.missingItems.length + ' 项' : '材料齐全' }}</span><span class="rk-row__idx">{{ (archivePage - 1) * archivePageSize + i + 1 }}</span></div>
            </li>
          </ul>
          <div class="ra-pagination"><AppPagination :total="archiveTotal" :page="archivePage" :page-size="archivePageSize" :show-size-changer="false" @update:page="changeArchivePage" /></div>
        </aside>
        <section class="rk-pane" aria-label="当前归档核验对象">
          <div class="rk-pane__bar">
            <span>本页第 {{ Math.max(archiveSelIndex + 1, 0) }} / {{ archiveRows.length }} 条 · 共 {{ archiveTotal }} 条</span>
            <span class="rk-pane__nav">
              <button class="mp-link" :disabled="actionLocked || archiveSelIndex <= 0" @click="stepArchive(-1)">← 上一条</button>
              <button class="mp-link" :disabled="actionLocked || archiveSelIndex >= archiveRows.length - 1" @click="stepArchive(1)">下一条 →</button>
            </span>
          </div>
          <EmptyState v-if="!selectedArchive" title="从左侧选择一名学生" description="逐个核验材料完整性并办理归档" />
          <section v-else class="mp-card rk-detail">
            <div class="mp-card__head">
              <div><span class="rk-detail__eyebrow">当前归档对象</span><span class="mp-card__title">{{ selectedArchive.studentName }} · 归档核验</span></div>
              <button v-if="canStudentView && selectedArchive.gdStudentId" class="mp-link" :disabled="actionLocked" @click="openArchiveStudent(selectedArchive)">查看学生档案 →</button>
            </div>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">学号</span><span class="mp-kv__v">{{ selectedArchive.studentNo }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">归档状态</span><span class="mp-kv__v"><StatusTag :type="selectedArchive.statusTone" :label="selectedArchive.statusLabel" dot /></span></div>
              <div v-if="selectedArchive.archiveBatchNo" class="mp-kv"><span class="mp-kv__k">档案批次号</span><span class="mp-kv__v">{{ selectedArchive.archiveBatchNo }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">材料完整性</span><span class="mp-kv__v" :class="selectedArchive.missingItems.length ? 'is-missing' : 'is-complete'">{{ selectedArchive.missingItems.length ? '缺失 ' + selectedArchive.missingItems.length + ' 项' : '必备材料齐全' }}</span></div>
              <template v-if="selectedArchive.missingItems.length">
                <div class="ar-missing-head"><div><strong>缺件明细</strong><span>点击后携带学生 ID、缺件类型、批次与 returnTo 精确进入补齐位置。</span></div><b>{{ selectedArchive.missingItems.length }} 项</b></div>
                <ul class="ar-missing">
                  <li v-for="m in selectedArchive.missingItems" :key="m" class="ar-missing__item">
                    <span class="ar-missing__name">✕ {{ m }}</span>
                    <button v-if="canStudentView" class="mp-link" :disabled="actionLocked" @click="goFix(m, selectedArchive)">{{ selectedArchive.dataAnomaly ? '查看学生档案 →' : '去补齐 →' }}</button>
                  </li>
                </ul>
              </template>
              <div class="ie-actions ie-actions--left">
                <span v-if="selectedArchive.dataAnomaly" class="ar-anomaly">历史主档异常，当前归档记录仅允许只读查看</span>
                <template v-else>
                  <button v-if="canArchivePreview && ['NOT_GENERATED', 'REJECTED'].includes(selectedArchive.status)" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doGenerate(selectedArchive)">生成清单</button>
                  <button v-if="canArchiveFile && selectedArchive.status === 'PENDING_SUBMIT' && !selectedArchive.missingItems.length" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doSubmit(selectedArchive)">提交归档</button>
                  <span v-if="selectedArchive.status === 'PENDING_SUBMIT' && selectedArchive.missingItems.length" class="mp-note">缺件补齐后方可提交归档</span>
                  <button v-if="canArchiveFile && selectedArchive.status === 'SUBMITTED'" class="mp-btn mp-btn--primary" :disabled="actionLocked" @click="doFile(selectedArchive)">核验归档</button>
                  <button v-if="canArchiveFile && selectedArchive.status === 'SUBMITTED'" class="mp-btn" :disabled="actionLocked" @click="doReject(selectedArchive)">驳回</button>
                  <span v-if="selectedArchive.status === 'FILED'" class="mp-note">已正式归档备案，记录只读</span>
                </template>
              </div>
              <p class="mp-note">生成 / 提交 / 核验 / 驳回均写入审计留痕；完整性以后端清单核验为准。</p>
            </div>
          </section>
        </section>
      </div>
    </div>

    <!-- 毕设统计 -->
    <div v-if="tab === 'stats' && canStatsView" class="mp-stack ra-panel">
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
        <div class="gm-section-title">阶段分布</div>
        <AppStackedBarChart v-if="stageChartData.length >= 2" title="各阶段学生数" :data="stageChartData" horizontal :height="Math.max(150, stageChartData.length * 38)" x-field="label" y-field="count" series-field="cat" value-label="人数" />
        <ul v-else class="gs-stage-list"><li v-for="s in overview.byStage" :key="s.stage">{{ s.label }}：{{ s.count }}</li></ul>
        <div class="gm-section-title">学院/专业对比</div>
        <DataTable :columns="collegeColumns" :rows="collegeRows" row-key="name" />
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :reason-chips="confirm.reasonChips || []"
      :submitting="Boolean(actionBusy)"
      @confirm="onConfirm"
    />
    <AppPageGuide guide-key="graduation.gd-risk-archive" />
  </ModulePageShell>
</template>

<script>
/** 问题预警+毕设归档+毕设统计：服务端风险扫描、一次性归档预览令牌、精确对账。 */
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

const RISK_RULE_CATALOG = [
  { code: 'GD-R01', label: '未选题' },
  { code: 'GD-R02', label: '指导教师未确认' },
  { code: 'GD-R03', label: '任务书未下达' },
  { code: 'GD-R04', label: '开题报告逾期未提交' },
  { code: 'GD-R05', label: '开题报告待审核' },
  { code: 'GD-R06', label: '中期检查未开始' },
  { code: 'GD-R07', label: '中期整改逾期' },
  { code: 'GD-R08', label: '论文初稿未提交' },
  { code: 'GD-R09', label: '最终论文逾期未提交' },
  { code: 'GD-R10', label: '查重超阈值' },
  { code: 'GD-R11', label: '评阅未通过' },
  { code: 'GD-R12', label: '答辩未安排' },
  { code: 'GD-R13', label: '归档材料不完整' }
]

function errorText(error, fallback) {
  return error?.message || error?.details?.message || fallback
}

export default {
  name: 'GraduationRiskArchiveView',
  components: { AppPageGuide, ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppExportButton, AppPagination, AppStackedBarChart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      riskRuleCatalog: RISK_RULE_CATALOG,
      tab: 'risk', routeReady: false,
      riskSelKey: '', riskAutoNext: true,
      archiveSelKey: '',
      riskFilters: { status: '', level: '', keyword: '' }, riskRows: [], riskTotal: 0, riskPage: 1, riskPageSize: 10, riskLoading: true, riskError: '',
      lastScanAt: '', lastScanStats: null,
      archiveFilters: { keyword: '', status: '' }, archiveRows: [], archiveTotal: 0, archivePage: 1, archivePageSize: 10, archiveLoading: true, archiveError: '',
      overview: null, collegeRows: [], statsLoading: true, statsError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      actionReceipt: null,
      archivePreviewEvidence: null,
      actionBusy: '', previewBusy: '',
      riskLoadToken: 0, scanToken: 0, lastScanToken: 0, archiveLoadToken: 0, statsLoadToken: 0,
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
    availableTabs() { return [this.canRiskView ? 'risk' : '', this.canArchiveView ? 'archive' : '', this.canStatsView ? 'stats' : ''].filter(Boolean) },
    hasBatch() { return !!this.batchStore.selectedBatchId },
    actionLocked() { return Boolean(this.actionBusy || this.previewBusy) },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}风险扫描与处置闭环 / 一次性令牌归档 / 跨模块统计`
    },
    selectedRisk() { return this.riskRows.find((row) => String(row.id) === this.riskSelKey) || null },
    riskSelIndex() { return this.riskRows.findIndex((row) => String(row.id) === this.riskSelKey) },
    selectedArchive() { return this.archiveRows.find((row) => String(row.id) === this.archiveSelKey) || null },
    archiveSelIndex() { return this.archiveRows.findIndex((row) => String(row.id) === this.archiveSelKey) },
    riskConclusion() {
      if (!this.lastScanAt) return '当前批次尚未扫描；先运行服务端 13 类规则，再进入处置队列。'
      const stats = this.lastScanStats || {}
      return `最近扫描 ${stats.scannedStudents ?? 0} 人，新增 ${stats.newCasesCreated ?? 0} 条，重开 ${stats.reopenedCases ?? 0} 条。`
    },
    archiveConclusion() {
      if (this.actionBusy === 'batch-generate' || this.actionBusy === 'batch-file') return '正在执行已确认的归档命令；不要切批、刷新或重复提交。'
      if (this.archivePreviewEvidence?.previewTokenIssued) return `一次性预览凭证已签发，预计执行 ${this.archivePreviewEvidence.executableCount ?? 0} 条；确认后才会正式写入。`
      if (!this.archiveRows.length) return '当前归档队列为空或尚未加载。'
      const missing = this.archiveRows.filter((row) => row.missingItems?.length).length
      return missing ? `当前页 ${missing} 人存在材料缺口；先按精确深链补齐，再办理归档。` : '当前页材料完整性已读取，可逐人办理或先批量预览。'
    },
    stageChartData() { return ((this.overview && this.overview.byStage) || []).filter((row) => (row.count || 0) > 0).map((row) => ({ label: row.label, count: row.count, cat: '人数' })) },
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
    this.applyInitialRouteState(this.$route.query)
    this.routeReady = true
    this.loadActivePanel()
  },
  beforeUnmount() {
    ++this.riskLoadToken; ++this.scanToken; ++this.lastScanToken; ++this.archiveLoadToken; ++this.statsLoadToken
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) { if (this.routeReady) this.onRouteQueryChanged(query) }
    },
    'batchStore.selectedBatchId'(batchId) {
      ++this.riskLoadToken; ++this.lastScanToken; ++this.archiveLoadToken; ++this.statsLoadToken
      this.riskPage = 1; this.archivePage = 1; this.riskSelKey = ''; this.archiveSelKey = ''
      this.archivePreviewEvidence = null; this.confirm.visible = false; this.actionReceipt = null
      void this.replacePanelQuery(this.tab, { batchId: batchId ? String(batchId) : undefined, page: '1', rsel: undefined, asel: undefined })
      this.loadActivePanel()
    }
  },
  methods: {
    formatDateTime,
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    routePage(value) { const page = Number.parseInt(this.routeText(value), 10); return Number.isFinite(page) && page > 0 ? page : 1 },
    isPanelAllowed(panel) { return (panel === 'risk' && this.canRiskView) || (panel === 'archive' && this.canArchiveView) || (panel === 'stats' && this.canStatsView) },
    applyInitialRouteState(query) {
      const requested = this.routeText(query.panel)
      this.tab = this.isPanelAllowed(requested) ? requested : (this.availableTabs[0] || '')
      this.riskSelKey = this.routeText(query.rsel)
      this.archiveSelKey = this.routeText(query.asel)
      if (this.tab === 'risk') {
        this.riskPage = this.routePage(query.page)
        this.riskFilters = { keyword: this.routeText(query.keyword), status: this.routeText(query.status), level: this.routeText(query.level) }
      } else if (this.tab === 'archive') {
        this.archivePage = this.routePage(query.page)
        this.archiveFilters = { keyword: this.routeText(query.keyword), status: this.routeText(query.status) }
      }
      if (requested !== this.tab && this.tab) void this.replacePanelQuery(this.tab)
    },
    onRouteQueryChanged(query) {
      const requested = this.routeText(query.panel)
      const nextTab = this.isPanelAllowed(requested) ? requested : (this.availableTabs[0] || '')
      if (!nextTab || this.actionLocked) return
      let changed = nextTab !== this.tab
      this.tab = nextTab
      if (nextTab === 'risk') {
        const nextPage = this.routePage(query.page)
        const nextFilters = { keyword: this.routeText(query.keyword), status: this.routeText(query.status), level: this.routeText(query.level) }
        const nextSel = this.routeText(query.rsel)
        changed = changed || nextPage !== this.riskPage || JSON.stringify(nextFilters) !== JSON.stringify(this.riskFilters) || nextSel !== this.riskSelKey
        this.riskPage = nextPage; this.riskFilters = nextFilters; this.riskSelKey = nextSel
      } else if (nextTab === 'archive') {
        const nextPage = this.routePage(query.page)
        const nextFilters = { keyword: this.routeText(query.keyword), status: this.routeText(query.status) }
        const nextSel = this.routeText(query.asel)
        changed = changed || nextPage !== this.archivePage || JSON.stringify(nextFilters) !== JSON.stringify(this.archiveFilters) || nextSel !== this.archiveSelKey
        this.archivePage = nextPage; this.archiveFilters = nextFilters; this.archiveSelKey = nextSel
      }
      if (requested !== nextTab) void this.replacePanelQuery(nextTab)
      if (changed) this.loadActivePanel()
    },
    buildPanelQuery(panel, overrides = {}) {
      const query = {
        ...this.$route.query,
        panel,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        ...overrides
      }
      if (panel === 'risk') {
        Object.assign(query, {
          page: String(this.riskPage), rsel: this.riskSelKey || undefined,
          keyword: String(this.riskFilters.keyword || '').trim() || undefined,
          status: this.riskFilters.status || undefined, level: this.riskFilters.level || undefined,
          asel: undefined
        })
      } else if (panel === 'archive') {
        Object.assign(query, {
          page: String(this.archivePage), asel: this.archiveSelKey || undefined,
          keyword: String(this.archiveFilters.keyword || '').trim() || undefined,
          status: this.archiveFilters.status || undefined, source: query.source || 'archive',
          rsel: undefined, level: undefined
        })
      } else {
        Object.assign(query, { page: undefined, rsel: undefined, asel: undefined, keyword: undefined, status: undefined, level: undefined })
      }
      Object.keys(query).forEach((key) => { if (query[key] == null || query[key] === '') delete query[key] })
      return query
    },
    replacePanelQuery(panel, overrides = {}) { return this.$router.replace({ query: this.buildPanelQuery(panel, overrides) }).catch(() => {}) },
    loadActivePanel() {
      if (this.tab === 'risk' && this.canRiskView) { this.loadRisks(); this.loadLastScan() }
      else if (this.tab === 'archive' && this.canArchiveView) this.loadArchives()
      else if (this.tab === 'stats' && this.canStatsView) this.loadStats()
    },
    switchTab(tab) {
      if (this.actionLocked || !this.isPanelAllowed(tab)) return
      this.tab = tab
      void this.replacePanelQuery(tab)
      this.loadActivePanel()
    },
    levelLabel(level) { return { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }[level] || (level ? '等级待确认' : '—') },
    async loadLastScan() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.lastScanToken
      if (!this.canRiskView || !batchId) { this.lastScanAt = ''; this.lastScanStats = null; return false }
      try {
        const res = await graduationRiskArchiveApi.getLastRiskScan({ batchId })
        if (token !== this.lastScanToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0 && res.data) { this.lastScanAt = res.data.lastScanAt || ''; this.lastScanStats = res.data.stats || null; return true }
      } catch { /* 最近扫描摘要降级不阻断队列 */ }
      return false
    },
    async doScan() {
      if (!this.canRiskScan) { toast.error('当前角色无风险扫描权限'); return }
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { toast.error('请先选择毕设批次'); return }
      if (this.actionLocked) return
      const token = ++this.scanToken
      this.actionBusy = 'scan-risk'
      try {
        const res = await graduationRiskArchiveApi.scanRisks({ batchId })
        if (token !== this.scanToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return
        if (res.code === 0) {
          const data = res.data || {}
          this.lastScanAt = data.lastScanAt || this.lastScanAt
          this.lastScanStats = { scannedStudents: data.scannedStudents, newCasesCreated: data.newCasesCreated, reopenedCases: data.reopenedCases, elapsedMs: data.elapsedMs }
          toast.success(res.message || `已扫描 ${data.scannedStudents || 0} 人，新增 ${data.newCasesCreated || 0}，重开 ${data.reopenedCases || 0}`)
          await this.loadRisks()
        } else toast.error(res.message || '风险扫描失败')
      } catch (error) { toast.error(errorText(error, '风险扫描失败')) }
      finally { if (token === this.scanToken) this.actionBusy = '' }
    },
    selectRisk(row, { force = false } = {}) {
      if (!row || (this.actionLocked && !force)) return
      this.riskSelKey = String(row.id)
      void this.replacePanelQuery('risk', { rsel: this.riskSelKey })
    },
    stepRisk(delta) {
      if (this.actionLocked) return
      const index = this.riskSelIndex + delta
      if (index >= 0 && index < this.riskRows.length) this.selectRisk(this.riskRows[index])
    },
    ensureRiskSelection() {
      if (!this.riskRows.length) { this.riskSelKey = ''; void this.replacePanelQuery('risk', { rsel: undefined }); return }
      const current = this.selectedRisk
      const actionable = (row) => row.status === 'OPEN' || row.status === 'PROCESSING'
      if (current && this.riskAutoNext && current.status === 'CLOSED') {
        const from = this.riskSelIndex
        for (let i = from + 1; i < this.riskRows.length; i++) if (actionable(this.riskRows[i])) { this.selectRisk(this.riskRows[i], { force: true }); return }
        for (let i = 0; i < from; i++) if (actionable(this.riskRows[i])) { this.selectRisk(this.riskRows[i], { force: true }); return }
        return
      }
      if (!current) this.selectRisk(this.riskRows.find(actionable) || this.riskRows[0], { force: true })
    },
    async loadRisks() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.riskLoadToken
      if (!this.canRiskView || !batchId) { this.riskLoading = false; this.riskError = ''; this.riskRows = []; this.riskTotal = 0; return false }
      this.riskLoading = true; this.riskError = ''
      try {
        const res = await graduationRiskArchiveApi.getRiskList(buildRiskArchiveQuery(this.riskFilters, { page: this.riskPage, pageSize: this.riskPageSize, batchId }))
        if (token !== this.riskLoadToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) {
          this.riskRows = Array.isArray(res.data?.list) ? res.data.list : []
          this.riskTotal = Number(res.data?.total) || 0
          this.ensureRiskSelection()
          return true
        }
        this.riskRows = []; this.riskTotal = 0; this.riskError = res.message || '加载失败'
      } catch (error) {
        if (token === this.riskLoadToken) { this.riskRows = []; this.riskTotal = 0; this.riskError = errorText(error, '风险队列加载失败') }
      } finally { if (token === this.riskLoadToken) this.riskLoading = false }
      return false
    },
    searchRisks() { if (!this.actionLocked) { this.riskPage = 1; void this.replacePanelQuery('risk', { page: '1' }); this.loadRisks() } },
    resetRiskFilters() { if (!this.actionLocked) { this.riskFilters = { status: '', level: '', keyword: '' }; this.riskPage = 1; void this.replacePanelQuery('risk', { page: '1', keyword: undefined, status: undefined, level: undefined }); this.loadRisks() } },
    changeRiskPage(page) { if (!this.actionLocked) { this.riskPage = page; this.riskSelKey = ''; void this.replacePanelQuery('risk', { page: String(page), rsel: undefined }); this.loadRisks() } },
    openRiskStudent(row) {
      if (this.actionLocked || !row?.gdStudentId) return
      this.$router.push({ name: 'graduation-student-detail', params: { id: String(row.gdStudentId) }, query: { batchId: String(this.batchStore.selectedBatchId), source: 'risk', returnTo: this.$router.resolve({ path: '/admin/graduation/risk-archive', query: this.buildPanelQuery('risk') }).fullPath } })
    },
    doAccept(row) { if (!this.canRiskAccept) toast.error('当前角色无风险受理权限'); else if (!this.actionLocked) this.confirm = { visible: true, title: '受理风险', message: `确认受理「${row.riskName}」（${row.studentName}）？`, type: 'primary', confirmText: '受理', requireReason: false, action: 'accept', row } },
    doProcess(row) { if (!this.canRiskProcess) toast.error('当前角色无风险处理权限'); else if (!this.actionLocked) this.confirm = { visible: true, title: '记录处理', message: '', type: 'primary', confirmText: '提交', requireReason: true, reasonLabel: '处理说明', action: 'process', row } },
    doClose(row) { if (!this.canRiskClose) toast.error('当前角色无风险关闭权限'); else if (!this.actionLocked) this.confirm = { visible: true, title: '关闭风险', message: '', type: 'danger', confirmText: '确认关闭', requireReason: true, reasonLabel: '关闭原因', action: 'close', row } },
    selectArchive(row, { force = false } = {}) {
      if (!row || (this.actionLocked && !force)) return
      this.archiveSelKey = String(row.id)
      void this.replacePanelQuery('archive', { asel: this.archiveSelKey })
    },
    stepArchive(delta) {
      if (this.actionLocked) return
      const index = this.archiveSelIndex + delta
      if (index >= 0 && index < this.archiveRows.length) this.selectArchive(this.archiveRows[index])
    },
    ensureArchiveSelection() {
      if (!this.archiveRows.length) { this.archiveSelKey = ''; void this.replacePanelQuery('archive', { asel: undefined }); return }
      if (!this.selectedArchive) this.selectArchive(this.archiveRows.find((row) => row.status !== 'FILED') || this.archiveRows[0], { force: true })
    },
    async loadArchives() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.archiveLoadToken
      if (!this.canArchiveView || !batchId) { this.archiveLoading = false; this.archiveError = ''; this.archiveRows = []; this.archiveTotal = 0; return false }
      this.archiveLoading = true; this.archiveError = ''
      try {
        const res = await graduationRiskArchiveApi.getArchiveList(buildRiskArchiveQuery(this.archiveFilters, { page: this.archivePage, pageSize: this.archivePageSize, batchId }))
        if (token !== this.archiveLoadToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) {
          this.archiveRows = Array.isArray(res.data?.list) ? res.data.list : []
          this.archiveTotal = Number(res.data?.total) || 0
          this.ensureArchiveSelection()
          return true
        }
        this.archiveRows = []; this.archiveTotal = 0; this.archiveError = res.message || '加载失败'
      } catch (error) {
        if (token === this.archiveLoadToken) { this.archiveRows = []; this.archiveTotal = 0; this.archiveError = errorText(error, '归档队列加载失败') }
      } finally { if (token === this.archiveLoadToken) this.archiveLoading = false }
      return false
    },
    searchArchives() { if (!this.actionLocked) { this.archivePage = 1; void this.replacePanelQuery('archive', { page: '1' }); this.loadArchives() } },
    resetArchiveFilters() { if (!this.actionLocked) { this.archiveFilters = { keyword: '', status: '' }; this.archivePage = 1; void this.replacePanelQuery('archive', { page: '1', keyword: undefined, status: undefined }); this.loadArchives() } },
    changeArchivePage(page) { if (!this.actionLocked) { this.archivePage = page; this.archiveSelKey = ''; void this.replacePanelQuery('archive', { page: String(page), asel: undefined }); this.loadArchives() } },
    archiveReturnTo() { return this.$router.resolve({ path: '/admin/graduation/risk-archive', query: this.buildPanelQuery('archive', { source: 'archive' }) }).fullPath },
    openArchiveStudent(row) {
      if (this.actionLocked || !row?.gdStudentId) return
      this.$router.push({ name: 'graduation-student-detail', params: { id: String(row.gdStudentId) }, query: { batchId: String(this.batchStore.selectedBatchId), source: 'archive', returnTo: this.archiveReturnTo() } })
    },
    /** 缺件补齐入口：绑定 exact gdStudentId、missingItem、batchId、source 与 returnTo。 */
    goFix(item, row) {
      if (!this.canStudentView || this.actionLocked) return
      const sid = row.gdStudentId
      if (!sid) { this.$router.push({ path: '/admin/graduation/students', query: { batchId: String(this.batchStore.selectedBatchId), panel: 'roster', returnTo: this.archiveReturnTo() } }); return }
      const name = String(item || '')
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
          missingItem: name,
          source: 'archive',
          returnTo: this.archiveReturnTo(),
          ...(this.batchStore.selectedBatchId ? { batchId: String(this.batchStore.selectedBatchId) } : {})
        }
      })
    },
    async runArchiveWrite(key, task, success) {
      if (this.actionLocked) return
      this.actionBusy = key
      try {
        const res = await task()
        if (res.code === 0) { await this.loadArchives(); success(res); return true }
        this.archiveWriteFailed(res)
      } catch (error) { this.archiveWriteFailed({ code: 503001, message: errorText(error, '连接中断，无法确认服务器是否已经完成操作。') }) }
      finally { this.actionBusy = '' }
      return false
    },
    async doGenerate(row) {
      if (!this.canArchivePreview) { toast.error('当前角色无归档生成权限'); return }
      await this.runArchiveWrite('generate-archive', () => graduationRiskArchiveApi.generateArchive(row.gdStudentId), () => {
        const latest = this.archiveRows.find((item) => String(item.gdStudentId) === String(row.gdStudentId))
        this.actionReceipt = { title: `${row.studentName} · 归档清单已生成`, result: `服务器最新状态：${latest?.statusLabel || '待提交'}`, next: latest?.missingItems?.length ? `仍缺 ${latest.missingItems.length} 项，点击缺件可直达补齐。` : '材料齐全后可提交归档。' }
        toast.success('清单已生成，状态已回读')
      })
    },
    async doSubmit(row) {
      if (!this.canArchiveFile) { toast.error('当前角色无归档提交权限'); return }
      await this.runArchiveWrite('submit-archive', () => graduationRiskArchiveApi.submitArchive(row.gdStudentId), () => {
        const latest = this.archiveRows.find((item) => String(item.gdStudentId) === String(row.gdStudentId))
        this.actionReceipt = { title: `${row.studentName} · 归档已提交`, result: `服务器最新状态：${latest?.statusLabel || '已提交'}`, next: '下一步由归档授权角色核验并备案。' }
        toast.success('归档已提交，状态已回读')
      })
    },
    async doFile(row) {
      if (!this.canArchiveFile) { toast.error('当前角色无归档备案权限'); return }
      await this.runArchiveWrite('file-archive', () => graduationRiskArchiveApi.fileArchive(row.gdStudentId, row.archiveBatchNo || null), () => {
        const latest = this.archiveRows.find((item) => String(item.gdStudentId) === String(row.gdStudentId))
        this.actionReceipt = { title: `${row.studentName} · 已正式归档备案`, result: `服务器最新状态：${latest?.statusLabel || '已备案'}；真实版本清单已冻结`, next: '当前记录只读，可导出台账或执行备份核验。' }
        toast.success('已归档，冻结状态已回读')
      })
    },
    doReject(row) {
      if (!this.canArchiveFile) { toast.error('当前角色无归档驳回权限'); return }
      if (this.actionLocked) return
      this.confirm = { visible: true, title: '驳回归档', message: '', type: 'danger', confirmText: '确认驳回', requireReason: true, reasonLabel: '驳回原因', reasonChips: ARCHIVE_REJECT_REASON_CHIPS, action: 'reject-archive', row }
    },
    exportArchivesFn() {
      if (!this.canArchiveExport) return Promise.resolve({ code: 403001, data: null, message: '当前角色无归档导出权限' })
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '毕设归档')
      const params = buildRiskArchiveQuery(this.archiveFilters, { batchId: this.batchStore.selectedBatchId })
      return graduationRiskArchiveApi.exportArchives(params).then((res) => {
        if (res.code === 0 && res.data) res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }
        return res
      })
    },
    _formatSkipReasons(preview) {
      const rows = preview?.skipReasons || []
      if (!rows.length) return '无'
      const map = { already_submitted_or_filed: '已提交/已备案', already_submitted: '已提交/已备案', dirty_data: '历史主档异常（只读）', missing_materials: '材料不齐', open_risks: '风险未关闭', out_of_scope: '不在当前范围' }
      return rows.map((row) => `${map[row.reason] || row.reason} ${row.count}`).join('；')
    },
    setArchivePreviewEvidence(kind, data, batchId) {
      this.archivePreviewEvidence = {
        kind,
        kindLabel: kind === 'batch-file' ? '一键核验备案预览' : '批量生成提交预览',
        batchId: String(batchId),
        batchName: data.batchName || this.batchStore.selectedBatchName || '当前批次',
        previewTokenIssued: Boolean(data.previewToken),
        archiveBatchNo: data.archiveBatchNo || '',
        executableCount: Number(data.executableCount || 0),
        skippedCount: Number(data.skippedCount || 0),
        previewedAt: new Date().toISOString()
      }
    },
    async doBatchGenerate() {
      if (!this.canArchivePreview || !this.canArchiveFile) { toast.error('当前角色无批量归档权限'); return }
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { toast.error('请先选择毕设批次'); return }
      if (this.actionLocked) return
      this.previewBusy = 'batch-generate-preview'
      try {
        const prev = await graduationRiskArchiveApi.previewBatchGenerate({ batchId })
        if (String(batchId) !== String(this.batchStore.selectedBatchId)) return
        if (prev.code !== 0) { toast.error(prev.message || '预检查失败'); return }
        const data = prev.data || {}
        this.setArchivePreviewEvidence('batch-generate', data, batchId)
        const batchName = data.batchName || this.batchStore.selectedBatchName || '当前批次'
        this.confirm = {
          visible: true, title: '批量生成提交',
          message: `批次「${batchName}」：候选 ${data.candidateCount} 人，预计成功 ${data.executableCount}，跳过 ${data.skippedCount}。主要跳过原因：${this._formatSkipReasons(data)}。previewToken 已签发且仅供本次确认执行。`,
          type: 'primary', confirmText: data.executableCount > 0 ? '确认生成提交' : '知道了', requireReason: false, reasonLabel: '说明',
          action: data.executableCount > 0 ? 'batch-generate' : 'batch-generate-noop', row: null
        }
      } catch (error) { toast.error(errorText(error, '预检查失败')) }
      finally { this.previewBusy = '' }
    },
    async doBatchFile() {
      if (!this.canArchivePreview || !this.canArchiveFile) { toast.error('当前角色无批量备案权限'); return }
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) { toast.error('请先选择毕设批次'); return }
      if (this.actionLocked) return
      this.previewBusy = 'batch-file-preview'
      try {
        const prev = await graduationRiskArchiveApi.previewBatchFile({ batchId })
        if (String(batchId) !== String(this.batchStore.selectedBatchId)) return
        if (prev.code !== 0) { toast.error(prev.message || '预检查失败'); return }
        const data = prev.data || {}
        this.setArchivePreviewEvidence('batch-file', data, batchId)
        const batchName = data.batchName || this.batchStore.selectedBatchName || '当前批次'
        this.confirm = {
          visible: true, title: '一键核验备案',
          message: `批次「${batchName}」：预计备案 ${data.executableCount} 份，跳过 ${data.skippedCount}。主要跳过原因：${this._formatSkipReasons(data)}。previewToken 已签发且仅供本次确认执行；备案后学生毕设阶段只读。`,
          type: 'warning', confirmText: data.executableCount > 0 ? '确认核验备案' : '知道了', requireReason: false, reasonLabel: '说明',
          action: data.executableCount > 0 ? 'batch-file' : 'batch-file-noop', row: null
        }
      } catch (error) { toast.error(errorText(error, '预检查失败')) }
      finally { this.previewBusy = '' }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      if (action === 'batch-generate-noop' || action === 'batch-file-noop') { this.confirm.visible = false; return }
      const allowed = (action === 'accept' && this.canRiskAccept)
        || (action === 'process' && this.canRiskProcess)
        || (action === 'close' && this.canRiskClose)
        || (action === 'reject-archive' && this.canArchiveFile)
        || (action === 'batch-generate' && this.canArchivePreview && this.canArchiveFile)
        || (action === 'batch-file' && this.canArchivePreview && this.canArchiveFile)
      if (!allowed) { this.confirm.visible = false; toast.error('当前角色无此操作权限'); return }
      if (this.actionLocked) return
      if ((action === 'batch-generate' || action === 'batch-file') && (
        this.archivePreviewEvidence?.kind !== action
        || String(this.archivePreviewEvidence?.batchId || '') !== String(this.batchStore.selectedBatchId || '')
        || !this.archivePreviewEvidence?.previewTokenIssued
      )) {
        this.confirm.visible = false
        toast.error('批次或预览上下文已变化，请重新预览后再确认')
        return
      }
      const batchId = this.batchStore.selectedBatchId
      this.actionBusy = action
      try {
        let res
        if (action === 'accept') res = await graduationRiskArchiveApi.acceptRisk(row.id)
        else if (action === 'process') res = await graduationRiskArchiveApi.processRisk(row.id, reason || '')
        else if (action === 'close') res = await graduationRiskArchiveApi.closeRisk(row.id, reason || '')
        else if (action === 'reject-archive') res = await graduationRiskArchiveApi.rejectArchive(row.gdStudentId, reason || '')
        else if (action === 'batch-generate') res = await graduationRiskArchiveApi.batchGenerateArchive({ batchId })
        else if (action === 'batch-file') res = await graduationRiskArchiveApi.batchFileArchive({ batchId })

        if (res && res.code === 0) {
          let receipt
          if (action === 'batch-generate') {
            toast.success(`已提交 ${res.data.submitted}，跳过 ${res.data.skipped}（缺材料或未关闭风险）`)
            receipt = { title: '批量生成提交已完成', result: `服务器结果：成功 ${res.data.submitted || 0} · 跳过 ${res.data.skipped || 0}`, next: 'previewToken 已一次性消费。下一步在归档队列核对清单，材料齐全后提交归档。' }
          } else if (action === 'batch-file') {
            toast.success(`已批量备案 ${res.data.filed} 份（跳过 ${res.data.skipped}）`)
            receipt = { title: '批量备案已核对', result: `服务器结果：已备案 ${res.data.filed || 0} · 跳过 ${res.data.skipped || 0}`, next: res.data.reconciled ? '连接中断后已按归档批次号完成精确对账，无需再次提交。' : 'previewToken 已一次性消费；备案记录已冻结，可进入导出或备份核验。' }
          } else {
            const label = action === 'accept' ? '风险已受理' : action === 'process' ? '处理记录已保存' : action === 'close' ? '风险已关闭' : '归档已退回'
            toast.success(label)
            receipt = { title: label, result: '服务器已接受操作，列表将回读最新状态。', next: action === 'reject-archive' ? '下一步由学生或责任老师按退回原因补齐材料。' : '可继续处理下一条队列。' }
          }
          this.confirm.visible = false
          if (action === 'reject-archive' || action === 'batch-file' || action === 'batch-generate') await this.loadArchives()
          else await this.loadRisks()
          this.actionReceipt = receipt
          if (action === 'batch-file' || action === 'batch-generate') this.archivePreviewEvidence = null
        } else if (res && Number(res.code) === 503002) {
          this.confirm.visible = false
          this.actionReceipt = { unknown: true, title: '备案结果尚未完全确认', result: res.message || `已核对 ${res.data?.filed || 0}/${res.data?.expectedExecutableCount || 0} 份`, next: '不要直接重复提交。先刷新归档台账核对；如仍不完整，重新执行预览后再决定。' }
          this.archivePreviewEvidence = null
        } else if (res) toast.error(res.message || '操作失败')
      } catch (error) {
        if (action === 'batch-file' || action === 'batch-generate' || action === 'reject-archive') {
          this.archiveWriteFailed({ code: 503001, message: errorText(error, '连接中断，无法确认服务器是否已经完成操作。') })
          this.archivePreviewEvidence = null
        } else toast.error(errorText(error, '风险操作失败'))
      } finally { this.actionBusy = '' }
    },
    async loadStats() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.statsLoadToken
      if (!this.canStatsView || !batchId) { this.statsLoading = false; this.overview = null; this.collegeRows = []; return false }
      this.statsLoading = true; this.statsError = ''
      try {
        const [overview, college] = await Promise.all([graduationRiskArchiveApi.getOverviewStats({ batchId }), graduationRiskArchiveApi.getCollegeComparison({ batchId })])
        if (token !== this.statsLoadToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        this.overview = overview.code === 0 ? overview.data : null
        this.collegeRows = college.code === 0 ? college.data : []
        if (overview.code !== 0) this.statsError = overview.message || '统计加载失败'
        return overview.code === 0
      } catch (error) {
        if (token === this.statsLoadToken) { this.overview = null; this.collegeRows = []; this.statsError = errorText(error, '统计加载失败') }
        return false
      } finally { if (token === this.statsLoadToken) this.statsLoading = false }
    },
    archiveWriteFailed(res) {
      if (Number(res?.code) === 503001 || Number(res?.code) === 503002) {
        this.actionReceipt = { unknown: true, title: '写入结果需要核对', result: res?.message || '连接中断，无法确认服务器是否已经完成操作。', next: '不要重复点击。先刷新归档台账，根据最新状态决定是否需要重新预览。' }
      } else toast.error(res?.message || '归档操作未完成')
    },
    async verifyUnknownResult() {
      if (this.actionLocked) return
      this.actionBusy = 'verify-archive-result'
      try {
        await this.loadArchives()
        this.actionReceipt = { title: '台账已刷新', result: '已从服务器重新读取当前归档状态。', next: '请按最新状态继续；若批量操作仍不完整，必须重新预览，不能复用旧执行凭证。' }
      } finally { this.actionBusy = '' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ra-panel{gap:var(--space-3)}.gp-tabs{display:flex;gap:var(--space-1);border-bottom:1px solid var(--line,#e2e8f0);margin-bottom:var(--space-3)}.gp-tabs__item{padding:8px 14px;border:none;border-bottom:2px solid transparent;background:none;color:var(--t2,#475569);font-size:13px;cursor:pointer}.gp-tabs__item.is-active{border-bottom-color:var(--pri,#2563eb);color:var(--pri,#2563eb);font-weight:600}.gp-tabs__item:disabled{cursor:not-allowed;opacity:.55}.rk-command,.ar-command{display:grid;grid-template-columns:minmax(280px,1fr) minmax(0,1.2fr) auto;align-items:center;gap:14px;padding:13px 15px;border:1px solid var(--primary-100,#dbeafe);border-radius:12px;background:linear-gradient(120deg,var(--primary-50,#eff6ff),#fff 74%);box-shadow:0 14px 30px -28px rgba(37,99,235,.7)}.rk-command__headline,.ar-command__copy{display:grid;min-width:0;gap:3px}.rk-command__headline>span,.ar-command__copy>span{color:var(--primary-600,#2563eb);font-size:10px;font-weight:700;letter-spacing:.08em}.rk-command__headline strong,.ar-command__copy strong{color:var(--text-primary);font-size:14px;line-height:1.45}.rk-command__headline small,.ar-command__copy small{color:var(--text-secondary);font-size:10px;line-height:1.45}.rk-command__metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.rk-command__metrics div{display:grid;justify-items:center;gap:1px;padding:7px;border:1px solid var(--border-light);border-radius:8px;background:rgba(255,255,255,.82)}.rk-command__metrics b{color:var(--primary-700,#1d4ed8);font-size:16px}.rk-command__metrics span{color:var(--text-tertiary);font-size:9px}.rk-rules{padding:10px 12px;border:1px solid var(--border-light);border-radius:10px;background:var(--gray-50,#f8fafc)}.rk-rules__head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px}.rk-rules__head>div{display:flex;align-items:baseline;gap:8px}.rk-rules__head span,.rk-rules__head small{color:var(--text-tertiary);font-size:10px}.rk-rules__head strong{color:var(--text-primary);font-size:12px}.rk-rules__grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}.rk-rules__grid span{display:flex;align-items:center;min-width:0;gap:4px;padding:5px 6px;border:1px solid var(--border-light);border-radius:7px;background:#fff;color:var(--text-secondary);font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rk-rules__grid b{flex:none;color:var(--primary-700,#1d4ed8);font-size:8px}.ar-command{grid-template-columns:minmax(0,1fr) auto}.ar-command__actions{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:7px}.ar-preview-evidence{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:9px;border:1px solid var(--warning-200,#fde68a);border-radius:10px;background:var(--warning-50,#fffbeb)}.ar-preview-evidence>div{display:grid;min-width:0;gap:2px;padding:7px 8px;border-radius:7px;background:rgba(255,255,255,.72)}.ar-preview-evidence span,.ar-preview-evidence small{color:var(--text-tertiary);font-size:9px}.ar-preview-evidence strong{overflow:hidden;color:var(--warning-800,#92400e);font-size:12px;text-overflow:ellipsis;white-space:nowrap}.ra-filter.is-command-locked,.rk-split.is-command-locked{pointer-events:none;opacity:.72}.rk-split{display:flex;gap:var(--space-3);align-items:flex-start}.rk-list{width:330px;flex:none;display:flex;flex-direction:column;gap:var(--space-2);padding:var(--space-3);border:1px solid var(--border-light,#e2e8f0);border-radius:10px;background:var(--card,#fff);box-shadow:0 10px 26px -28px rgba(15,23,42,.55)}.rk-list__head{display:flex;justify-content:space-between;align-items:center;gap:8px}.rk-list__head>div{display:grid}.rk-list__head strong{color:var(--text-primary);font-size:12px}.rk-list__head small,.rk-list__head>span{color:var(--text-tertiary);font-size:9px}.rk-list__head>span{padding:3px 6px;border-radius:999px;background:var(--gray-100,#f1f5f9)}.rk-pane{flex:1;min-width:0;padding:var(--space-3);border:1px solid var(--border-light,#e2e8f0);border-radius:10px;background:var(--card,#fff);box-shadow:0 10px 26px -28px rgba(15,23,42,.55)}.rk-rows{list-style:none;margin:0;padding:0;max-height:600px;overflow-y:auto;border:1px solid var(--border-light,#e2e8f0);border-radius:8px}.rk-row{padding:9px 10px;border-bottom:1px solid var(--border-light,#eef1f6);cursor:pointer;transition:background .12s ease,box-shadow .12s ease}.rk-row:last-child{border-bottom:none}.rk-row:hover{background:var(--gray-50,#f8fafc)}.rk-row.is-active{background:var(--primary-50,#eff6ff);box-shadow:inset 3px 0 0 var(--brand-primary,#2563eb)}.rk-row.is-disabled{cursor:not-allowed}.rk-row:focus-visible{position:relative;z-index:1;outline:2px solid var(--primary-400,#60a5fa);outline-offset:-2px}.rk-row__main{display:flex;align-items:center;gap:var(--space-2)}.rk-row__name{flex:1;overflow:hidden;color:var(--text-primary);font-weight:500;text-overflow:ellipsis;white-space:nowrap}.rk-row__sub{margin-top:2px;color:var(--text-secondary);font-size:11px}.rk-row__meta{display:flex;align-items:center;gap:var(--space-2);margin-top:3px;color:var(--text-tertiary);font-size:10px}.rk-row__idx{margin-left:auto}.ra-pagination{display:flex;justify-content:center}.rk-pane__bar{display:flex;align-items:center;flex-wrap:wrap;gap:var(--space-3);padding:var(--space-2) var(--space-3);margin-bottom:var(--space-3);border:1px solid var(--border-light,#e2e8f0);border-radius:8px;background:var(--gray-50,#f8fafc);color:var(--text-secondary);font-size:11px}.rk-pane__auto{display:inline-flex;align-items:center;gap:4px;cursor:pointer}.rk-pane__nav{display:inline-flex;gap:var(--space-3);margin-left:auto}.rk-pane__nav .mp-link:disabled{cursor:not-allowed;opacity:.4}.rk-detail__eyebrow{display:block;margin-bottom:2px;color:var(--primary-600,#2563eb);font-size:9px;font-weight:700;letter-spacing:.06em}.ar-missing-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:8px}.ar-missing-head>div{display:grid;gap:2px}.ar-missing-head strong{color:var(--text-primary);font-size:11px}.ar-missing-head span{color:var(--text-tertiary);font-size:9px}.ar-missing-head b{color:var(--danger,#dc2626);font-size:12px}.ar-missing{list-style:none;margin:var(--space-1) 0 0;padding:0}.ar-missing__item{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 10px;margin-bottom:6px;border:1px dashed var(--danger,#fca5a5);border-radius:8px;background:var(--danger-50,#fef2f2);font-size:11px}.ar-missing__name,.is-missing{color:var(--danger,#dc2626)}.is-complete{color:var(--success-600,#16a34a)}.ar-anomaly{color:var(--danger,#dc2626);font-weight:600}.ie-actions{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:var(--space-2);margin-bottom:var(--space-3)}.ie-actions--left{justify-content:flex-start;margin-top:var(--space-3)}.mp-btn{padding:7px 14px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;font-size:12px;cursor:pointer}.mp-btn--primary{border-color:var(--pri,#2563eb);background:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.55}.ra-receipt{display:flex;align-items:center;gap:14px;margin-bottom:var(--space-3);padding:11px 12px;border:1px solid #b7ebc6;border-radius:9px;background:#f0fff4}.ra-receipt.is-unknown{border-color:#f6c453;background:#fff9e8}.ra-receipt div{display:grid;flex:1;gap:3px}.ra-receipt strong{color:#137a43}.ra-receipt.is-unknown strong{color:#8a5b00}.ra-receipt span{font-size:12px}.ra-receipt small{color:var(--text-tertiary);font-size:10px}.ra-receipt button{padding:6px 9px;border:1px solid var(--border-light);border-radius:7px;background:#fff;color:var(--primary-600);cursor:pointer}.gs-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:var(--space-3)}.gs-card{padding:12px;border:1px solid var(--line,#e2e8f0);border-radius:10px;background:linear-gradient(145deg,var(--color-bg-subtle,#f8fafc),var(--card,#fff))}.gs-card__label{color:var(--t3,#64748b);font-size:11px}.gs-card__value{margin-top:4px;font-size:21px;font-weight:700}.gm-section-title{margin-top:var(--space-3);font-size:12px;font-weight:600}.gs-stage-list{display:flex;flex-wrap:wrap;gap:var(--space-4);margin:8px 0;padding:0;list-style:none;font-size:12px}
@media(max-width:1280px){.rk-command{grid-template-columns:1fr auto}.rk-command__metrics{grid-column:1/-1}.rk-rules__grid{grid-template-columns:repeat(5,minmax(0,1fr))}}@media(max-width:1100px){.rk-split{flex-direction:column}.rk-list,.rk-pane{width:100%;box-sizing:border-box}.rk-pane{padding:var(--space-3)}.ar-preview-evidence{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.rk-command,.ar-command{grid-template-columns:1fr}.rk-command__metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.rk-rules__grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ar-command__actions{justify-content:flex-start}.ar-preview-evidence{grid-template-columns:1fr}.rk-rules__head{align-items:flex-start;flex-direction:column}}
</style>
