<template>
  <ModulePageShell
    title="问题预警 · 毕设归档 · 毕设统计"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-tabs" aria-label="风险归档工作区">
      <button v-if="canRiskView" class="gp-tabs__item" :class="{ 'is-active': tab === 'risk' }" :disabled="contextLocked" @click="switchTab('risk')">问题预警</button>
      <button v-if="canArchiveView" class="gp-tabs__item" :class="{ 'is-active': tab === 'archive' }" :disabled="contextLocked" @click="switchTab('archive')">毕设归档</button>
      <button v-if="canStatsView" class="gp-tabs__item" :class="{ 'is-active': tab === 'stats' }" :disabled="contextLocked" @click="switchTab('stats')">毕设统计</button>
    </div>

    <aside v-if="actionReceipt" class="ra-receipt" :class="{ 'is-unknown': actionReceipt.unknown }" role="status">
      <div>
        <strong>{{ actionReceipt.title }}</strong>
        <span>{{ actionReceipt.result }}</span>
        <small>{{ actionReceipt.next }}</small>
      </div>
      <button v-if="actionReceipt.unknown" type="button" :disabled="contextLocked" @click="verifyUnknownResult">刷新台账核对</button>
      <button v-else type="button" :disabled="contextLocked" @click="actionReceipt = null">关闭</button>
    </aside>

    <div v-if="tab === 'risk' && canRiskView" class="mp-stack ra-panel">
      <EmptyState
        v-if="!hasBatch"
        title="请先选择或创建毕设批次"
        description="顶部批次条选择当前工作批次后，再运行服务端风险扫描与处置。"
      />
      <template v-else>
        <section class="rk-command" aria-label="风险扫描结论">
          <div class="rk-command__headline">
            <span>最近扫描事实</span>
            <strong>{{ riskConclusion }}</strong>
            <small>{{ batchStore.selectedBatchName || batchStore.selectedBatchId }} · 风险由服务端规则扫描生成，前端不自行判定。</small>
          </div>
          <div class="rk-command__metrics">
            <div><b>{{ lastScanStats?.scannedStudents ?? '—' }}</b><span>扫描学生</span></div>
            <div><b>{{ riskStats?.openCount ?? '—' }}</b><span>开放风险</span></div>
            <div><b>{{ riskStats?.criticalOpenCount ?? '—' }}</b><span>紧急风险</span></div>
            <div><b>{{ lastScanStats?.elapsedMs == null ? '—' : `${lastScanStats.elapsedMs}ms` }}</b><span>扫描耗时</span></div>
          </div>
          <button v-if="canRiskScan" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="doScan">{{ actionBusy === 'scan-risk' ? '扫描中…' : '扫描生成风险项' }}</button>
        </section>

        <section class="rk-rules" aria-label="13类毕业设计风险规则摘要">
          <div class="rk-rules__head">
            <div><span>服务端规则统计</span><strong>13 类风险全覆盖</strong></div>
            <small v-if="lastScanAt">上次扫描：{{ formatDateTime(lastScanAt) }}</small>
            <small v-else>尚未执行过扫描</small>
          </div>
          <p v-if="riskStatsError" class="rk-rules__degraded">规则统计暂时不可用：{{ riskStatsError }}。风险队列仍按服务端返回展示，不使用前端静态目录替代。</p>
          <div v-else-if="riskStatsLoading" class="rk-rules__degraded">正在读取服务端 13 类规则统计…</div>
          <div v-else-if="riskRuleRows.length" class="rk-rules__grid">
            <span v-for="rule in riskRuleRows" :key="rule.riskCode" :title="`${rule.riskName}：${rule.count}`">
              <b>{{ rule.riskCode }}</b>
              <i>{{ rule.riskName }}</i>
              <em>{{ rule.count }}</em>
            </span>
          </div>
          <p v-else class="rk-rules__degraded">服务端未返回风险规则统计，请刷新或重新扫描。</p>
        </section>

        <AdvancedFilter
          v-model="riskFilters"
          class="ra-filter"
          :class="{ 'is-command-locked': contextLocked }"
          :aria-disabled="contextLocked"
          :fields="riskFilterFields"
          @search="searchRisks"
          @reset="resetRiskFilters"
        />
        <ErrorState v-if="riskError" :description="riskError" @retry="loadRisks" />
        <LoadingState v-else-if="riskLoading" />
        <EmptyState
          v-else-if="!riskRows.length"
          title="当前筛选下没有风险记录"
          description="可调整条件或重新运行服务端扫描；没有记录不代表浏览器已自行判定无风险。"
        >
          <template v-if="canRiskScan" #actions>
            <button class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="doScan">扫描生成风险项</button>
          </template>
        </EmptyState>
        <div v-else class="rk-split" :class="{ 'is-command-locked': contextLocked }" :aria-busy="contextLocked">
          <aside class="rk-list" aria-label="风险处置队列">
            <div class="rk-list__head">
              <div><strong>风险队列</strong><small>第 {{ riskPage }} 页 · {{ riskTotal }} 条</small></div>
              <span>{{ riskFilters.status || '全部状态' }}</span>
            </div>
            <ul class="rk-rows">
              <li
                v-for="(row, index) in riskRows"
                :key="row.id"
                class="rk-row"
                :class="{ 'is-active': String(row.id) === riskSelKey, 'is-disabled': contextLocked }"
                :tabindex="contextLocked ? -1 : 0"
                :aria-disabled="contextLocked"
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
                <div class="rk-row__meta">
                  <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
                  <span class="rk-row__idx">{{ (riskPage - 1) * riskPageSize + index + 1 }}</span>
                </div>
              </li>
            </ul>
            <div class="ra-pagination">
              <AppPagination :total="riskTotal" :page="riskPage" :page-size="riskPageSize" :show-size-changer="false" @update:page="changeRiskPage" />
            </div>
          </aside>

          <section class="rk-pane" aria-label="当前风险处置对象">
            <div class="rk-pane__bar">
              <span>本页第 {{ Math.max(riskSelIndex + 1, 0) }} / {{ riskRows.length }} 条 · 共 {{ riskTotal }} 条</span>
              <label class="rk-pane__auto"><input v-model="riskAutoNext" type="checkbox" :disabled="contextLocked" /> 处置后自动进入下一条</label>
              <span class="rk-pane__nav">
                <button class="mp-link" :disabled="contextLocked || riskSelIndex <= 0" @click="stepRisk(-1)">← 上一条</button>
                <button class="mp-link" :disabled="contextLocked || riskSelIndex >= riskRows.length - 1" @click="stepRisk(1)">下一条 →</button>
              </span>
            </div>
            <EmptyState v-if="!selectedRisk" title="从左侧选择一条风险" description="处置后可自动进入下一条待办风险" />
            <section v-else class="mp-card rk-detail">
              <div class="mp-card__head">
                <div>
                  <span class="rk-detail__eyebrow">{{ selectedRisk.riskCode || '风险规则' }} · 当前处置对象</span>
                  <span class="mp-card__title">{{ selectedRisk.riskName }}</span>
                </div>
                <button v-if="canStudentView && selectedRisk.gdStudentId" class="mp-link" :disabled="contextLocked" @click="openRiskStudent(selectedRisk)">查看学生档案 →</button>
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
                <div v-if="selectedRisk.handleNote" class="mp-kv"><span class="mp-kv__k">处理记录</span><span class="mp-kv__v">{{ selectedRisk.handleNote }}</span></div>
                <div class="ie-actions ie-actions--left">
                  <button v-if="canRiskAccept && selectedRisk.status === 'OPEN'" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="askRiskAction('accept', selectedRisk)">受理</button>
                  <button v-if="canRiskProcess && selectedRisk.status === 'PROCESSING'" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="askRiskAction('process', selectedRisk)">记录处理</button>
                  <button v-if="canRiskClose && (selectedRisk.status === 'PROCESSING' || (selectedRisk.status === 'OPEN' && selectedRisk.conditionActive === false))" class="mp-btn" :disabled="contextLocked" @click="askRiskAction('close', selectedRisk)">关闭风险</button>
                  <span v-if="selectedRisk.status === 'CLOSED'" class="mp-note">该风险已关闭</span>
                </div>
                <p class="mp-note">受理、处理、关闭均按 permission + status 调用原接口并写入审计；页面不会自动修改风险。</p>
              </div>
            </section>
          </section>
        </div>
      </template>
    </div>

    <div v-if="tab === 'archive' && canArchiveView" class="mp-stack ra-panel">
      <EmptyState
        v-if="!hasBatch"
        title="请先选择或创建毕设批次"
        description="顶部批次条选择当前工作批次后，再核验材料完整性与办理归档。"
      />
      <template v-else>
        <section class="ar-command" aria-label="归档批次命令">
          <div class="ar-command__copy">
            <span>归档工作结论</span>
            <strong>{{ archiveConclusion }}</strong>
            <small>固定顺序：预览 → 用户确认 → 一次性 previewToken → execute → 服务器回读 / 精确对账。</small>
          </div>
          <div class="ar-command__actions">
            <button v-if="canArchivePreview && canArchiveFile" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="startArchivePreview('batch-generate')">{{ previewBusy === 'batch-generate-preview' ? '预览中…' : '批量生成提交' }}</button>
            <button v-if="canArchivePreview && canArchiveFile" class="mp-btn" :disabled="contextLocked" @click="startArchivePreview('batch-file')">{{ previewBusy === 'batch-file-preview' ? '预览中…' : '一键核验备案' }}</button>
            <AppExportButton v-if="canArchiveExport" :export-fn="exportArchivesFn">导出台账</AppExportButton>
          </div>
        </section>

        <section v-if="archivePreviewEvidence" class="ar-preview-evidence" role="status" data-testid="archive-preview-token-evidence">
          <div><span>previewToken</span><strong>{{ archivePreviewEvidence.maskedToken }}</strong><small>原始令牌不进入界面文本；取消、切批、离页或执行后失效。</small></div>
          <div><span>档案批次号</span><strong>{{ archivePreviewEvidence.archiveBatchNo || '执行时生成' }}</strong><small>批次 {{ archivePreviewEvidence.batchName || archivePreviewEvidence.batchId }}</small></div>
          <div><span>候选 / 可执行</span><strong>{{ archivePreviewEvidence.candidateCount }} / {{ archivePreviewEvidence.executableCount }}</strong><small>跳过 {{ archivePreviewEvidence.skippedCount }}</small></div>
          <div><span>预览时间</span><strong>{{ formatDateTime(archivePreviewEvidence.previewedAt) }}</strong><small>{{ archivePreviewEvidence.kindLabel }}</small></div>
        </section>

        <AdvancedFilter
          v-model="archiveFilters"
          class="ra-filter"
          :class="{ 'is-command-locked': contextLocked }"
          :aria-disabled="contextLocked"
          :fields="archiveFilterFields"
          @search="searchArchives"
          @reset="resetArchiveFilters"
        />
        <ErrorState v-if="archiveError" :description="archiveError" @retry="loadArchives" />
        <LoadingState v-else-if="archiveLoading" />
        <EmptyState v-else-if="!archiveRows.length" title="当前筛选下暂无归档记录" description="可调整状态或关键词；完整性以后端归档清单为准。" />
        <div v-else class="rk-split" :class="{ 'is-command-locked': contextLocked }" :aria-busy="contextLocked">
          <aside class="rk-list" aria-label="归档办理队列">
            <div class="rk-list__head">
              <div><strong>归档队列</strong><small>第 {{ archivePage }} 页 · {{ archiveTotal }} 条</small></div>
              <span>{{ archiveFilters.status || '全部状态' }}</span>
            </div>
            <ul class="rk-rows">
              <li
                v-for="(row, index) in archiveRows"
                :key="row.id"
                class="rk-row"
                :class="{ 'is-active': String(row.id) === archiveSelKey, 'is-disabled': contextLocked }"
                :tabindex="contextLocked ? -1 : 0"
                :aria-disabled="contextLocked"
                :aria-current="String(row.id) === archiveSelKey ? 'true' : undefined"
                role="button"
                @click="selectArchive(row)"
                @keydown.enter.prevent="selectArchive(row)"
                @keydown.space.prevent="selectArchive(row)"
              >
                <div class="rk-row__main"><span class="rk-row__name">{{ row.studentName }}</span><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></div>
                <div class="rk-row__sub">{{ row.studentNo }}</div>
                <div class="rk-row__meta"><span :class="row.missingItems?.length ? 'is-missing' : 'is-complete'">{{ row.missingItems?.length ? `缺 ${row.missingItems.length} 项` : '材料齐全' }}</span><span class="rk-row__idx">{{ (archivePage - 1) * archivePageSize + index + 1 }}</span></div>
              </li>
            </ul>
            <div class="ra-pagination"><AppPagination :total="archiveTotal" :page="archivePage" :page-size="archivePageSize" :show-size-changer="false" @update:page="changeArchivePage" /></div>
          </aside>

          <section class="rk-pane" aria-label="当前归档核验对象">
            <div class="rk-pane__bar">
              <span>本页第 {{ Math.max(archiveSelIndex + 1, 0) }} / {{ archiveRows.length }} 条 · 共 {{ archiveTotal }} 条</span>
              <span class="rk-pane__nav">
                <button class="mp-link" :disabled="contextLocked || archiveSelIndex <= 0" @click="stepArchive(-1)">← 上一条</button>
                <button class="mp-link" :disabled="contextLocked || archiveSelIndex >= archiveRows.length - 1" @click="stepArchive(1)">下一条 →</button>
              </span>
            </div>
            <EmptyState v-if="!selectedArchive" title="从左侧选择一名学生" description="逐个核验材料完整性并办理归档" />
            <section v-else class="mp-card rk-detail">
              <div class="mp-card__head">
                <div><span class="rk-detail__eyebrow">当前归档对象</span><span class="mp-card__title">{{ selectedArchive.studentName }} · 归档核验</span></div>
                <button v-if="canStudentView && selectedArchive.gdStudentId" class="mp-link" :disabled="contextLocked" @click="openArchiveStudent(selectedArchive)">查看学生档案 →</button>
              </div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学号</span><span class="mp-kv__v">{{ selectedArchive.studentNo }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">归档状态</span><span class="mp-kv__v"><StatusTag :type="selectedArchive.statusTone" :label="selectedArchive.statusLabel" dot /></span></div>
                <div v-if="selectedArchive.archiveBatchNo" class="mp-kv"><span class="mp-kv__k">档案批次号</span><span class="mp-kv__v">{{ selectedArchive.archiveBatchNo }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">材料完整性</span><span class="mp-kv__v" :class="selectedArchive.missingItems?.length ? 'is-missing' : 'is-complete'">{{ selectedArchive.missingItems?.length ? `缺失 ${selectedArchive.missingItems.length} 项` : '必备材料齐全' }}</span></div>
                <template v-if="selectedArchive.missingItems?.length">
                  <div class="ar-missing-head"><div><strong>缺件明细</strong><span>点击后携带学生、缺件、批次、来源与 returnTo 精确进入补齐位置。</span></div><b>{{ selectedArchive.missingItems.length }} 项</b></div>
                  <ul class="ar-missing">
                    <li v-for="item in selectedArchive.missingItems" :key="item" class="ar-missing__item">
                      <span class="ar-missing__name">✕ {{ item }}</span>
                      <button v-if="canStudentView" class="mp-link" :disabled="contextLocked" @click="goFix(item, selectedArchive)">{{ selectedArchive.dataAnomaly ? '查看学生档案 →' : '去补齐 →' }}</button>
                    </li>
                  </ul>
                </template>
                <div class="ie-actions ie-actions--left">
                  <span v-if="selectedArchive.dataAnomaly" class="ar-anomaly">历史主档异常，当前归档记录仅允许只读查看</span>
                  <template v-else>
                    <button v-if="canArchivePreview && ['NOT_GENERATED', 'REJECTED'].includes(selectedArchive.status)" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="doGenerate(selectedArchive)">生成清单</button>
                    <button v-if="canArchiveFile && selectedArchive.status === 'PENDING_SUBMIT' && !selectedArchive.missingItems.length" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="doSubmit(selectedArchive)">提交归档</button>
                    <span v-if="selectedArchive.status === 'PENDING_SUBMIT' && selectedArchive.missingItems.length" class="mp-note">缺件补齐后方可提交归档</span>
                    <button v-if="canArchiveFile && selectedArchive.status === 'SUBMITTED'" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="doFile(selectedArchive)">核验归档</button>
                    <button v-if="canArchiveFile && selectedArchive.status === 'SUBMITTED'" class="mp-btn" :disabled="contextLocked" @click="askRejectArchive(selectedArchive)">驳回</button>
                    <span v-if="selectedArchive.status === 'FILED'" class="mp-note">已正式归档备案，记录只读</span>
                  </template>
                </div>
                <p class="mp-note">生成、提交、核验、驳回均绑定当前学生与批次并回读服务器；已备案版本只读。</p>
              </div>
            </section>
          </section>
        </div>
      </template>
    </div>

    <div v-if="tab === 'stats' && canStatsView" class="mp-stack ra-panel">
      <EmptyState v-if="!hasBatch" title="请先选择毕设批次" description="选择批次后查看当前数据范围的跨模块统计。" />
      <template v-else>
        <p class="mp-note">以下为当前批次与当前数据范围的服务端汇总；不以当前页二次筛选冒充全量。</p>
        <ErrorState v-if="statsError" :description="statsError" @retry="loadStats" />
        <LoadingState v-else-if="statsLoading" />
        <template v-else-if="overview">
          <div class="gs-cards">
            <div class="gs-card"><span>毕设学生</span><strong>{{ overview.studentTotal }}</strong></div>
            <div class="gs-card"><span>导师已认证</span><strong>{{ overview.mentor?.qualifiedCount }}</strong></div>
            <div class="gs-card"><span>未分配导师</span><strong>{{ overview.mentor?.unassignedStudents }}</strong></div>
            <div class="gs-card"><span>开放风险</span><strong>{{ overview.risk?.openCount }}</strong></div>
            <div class="gs-card"><span>归档率</span><strong>{{ overview.archive?.archiveRate }}%</strong></div>
            <div class="gs-card"><span>成绩已发布均分</span><strong>{{ overview.grade?.publishedAvg }}</strong></div>
          </div>
          <div class="gm-section-title">阶段分布</div>
          <AppStackedBarChart v-if="stageChartData.length >= 2" title="各阶段学生数" :data="stageChartData" horizontal :height="Math.max(150, stageChartData.length * 38)" x-field="label" y-field="count" series-field="cat" value-label="人数" />
          <ul v-else class="gs-stage-list"><li v-for="stage in overview.byStage" :key="stage.stage">{{ stage.label }}：{{ stage.count }}</li></ul>
          <div class="gm-section-title">学院 / 专业对比</div>
          <DataTable :columns="collegeColumns" :rows="collegeRows" row-key="name" />
        </template>
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
      @cancel="onConfirmCancel"
      @confirm="onConfirm"
    />
    <AppPageGuide guide-key="graduation.gd-risk-archive" />
  </ModulePageShell>
</template>

<script>
/** 风险 / 归档 / 统计工作台：服务端规则真值、不可变命令快照、一次性归档令牌。 */
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

const EMPTY_CONFIRM = () => ({
  visible: false,
  title: '',
  message: '',
  type: 'primary',
  confirmText: '确认',
  requireReason: false,
  reasonLabel: '原因',
  reasonChips: [],
  action: '',
  row: null
})

function freezeSnapshot(value) {
  return Object.freeze({ ...value })
}

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
      tab: 'risk',
      routeReady: false,
      riskSelKey: '',
      riskAutoNext: true,
      archiveSelKey: '',
      riskFilters: { status: '', level: '', keyword: '' },
      riskRows: [],
      riskTotal: 0,
      riskPage: 1,
      riskPageSize: 10,
      riskLoading: true,
      riskError: '',
      lastScanAt: '',
      lastScanStats: null,
      riskStats: null,
      riskStatsLoading: false,
      riskStatsError: '',
      archiveFilters: { keyword: '', status: '' },
      archiveRows: [],
      archiveTotal: 0,
      archivePage: 1,
      archivePageSize: 10,
      archiveLoading: true,
      archiveError: '',
      overview: null,
      collegeRows: [],
      statsLoading: true,
      statsError: '',
      confirm: EMPTY_CONFIRM(),
      actionReceipt: null,
      archivePreviewEvidence: null,
      archiveCommandSnapshot: null,
      commandSnapshot: null,
      actionBusy: '',
      previewBusy: '',
      riskLoadToken: 0,
      scanToken: 0,
      lastScanToken: 0,
      riskStatsToken: 0,
      archiveLoadToken: 0,
      statsLoadToken: 0,
      collegeColumns: [
        { key: 'name', title: '学院 / 专业' },
        { key: 'total', title: '学生数' },
        { key: 'archived', title: '已归档' },
        { key: 'highRisk', title: '高风险' }
      ]
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
    hasBatch() { return Boolean(this.batchStore.selectedBatchId) },
    contextLocked() {
      return Boolean(
        this.actionBusy
        || this.previewBusy
        || (this.confirm.visible && (this.commandSnapshot || this.archiveCommandSnapshot))
      )
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}风险扫描与处置 / 一次性令牌归档 / 服务端汇总`
    },
    selectedRisk() { return this.riskRows.find((row) => String(row.id) === this.riskSelKey) || null },
    riskSelIndex() { return this.riskRows.findIndex((row) => String(row.id) === this.riskSelKey) },
    selectedArchive() { return this.archiveRows.find((row) => String(row.id) === this.archiveSelKey) || null },
    archiveSelIndex() { return this.archiveRows.findIndex((row) => String(row.id) === this.archiveSelKey) },
    riskRuleRows() {
      const rows = Array.isArray(this.riskStats?.byCode) ? this.riskStats.byCode : []
      return rows.map((row) => ({
        riskCode: String(row?.riskCode || ''),
        riskName: String(row?.riskName || ''),
        count: Math.max(0, Number(row?.count) || 0)
      }))
    },
    riskConclusion() {
      if (this.riskStatsError) return '风险队列可继续读取，但 13 类规则统计处于降级态。'
      if (!this.lastScanAt) return '当前批次尚未扫描；先运行服务端 13 类规则，再进入处置队列。'
      const stats = this.lastScanStats || {}
      return `最近扫描 ${stats.scannedStudents ?? 0} 人；当前开放 ${this.riskStats?.openCount ?? 0} 条，其中紧急 ${this.riskStats?.criticalOpenCount ?? 0} 条。`
    },
    archiveConclusion() {
      if (this.actionBusy === 'batch-generate' || this.actionBusy === 'batch-file') return '正在执行已确认命令；上下文已锁定，等待服务器回读或精确对账。'
      if (this.archiveCommandSnapshot?.phase === 'READY') return `一次性预览凭证已签发，可执行 ${this.archiveCommandSnapshot.executableCount} 条；取消后凭证作废。`
      if (!this.archiveRows.length) return '当前归档队列为空或尚未加载。'
      const missing = this.archiveRows.filter((row) => row.missingItems?.length).length
      return missing ? `当前页 ${missing} 人存在材料缺口；先按精确深链补齐，再办理归档。` : '当前页材料完整性已回读，可逐人办理或先批量预览。'
    },
    stageChartData() {
      return (this.overview?.byStage || []).filter((row) => Number(row.count) > 0).map((row) => ({ label: row.label, count: row.count, cat: '人数' }))
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
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名 / 学号' },
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
    this.invalidateReads()
    this.invalidateArchivePreview('unmount')
  },
  beforeRouteLeave(to, from, next) {
    if (this.contextLocked) {
      toast.info('当前命令尚未完成，请等待服务器回执或取消确认后再离开')
      next(false)
      return
    }
    this.invalidateArchivePreview('route-leave')
    next()
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) {
        if (!this.routeReady) return
        if (this.contextLocked) {
          this.restoreLockedContext()
          return
        }
        this.onRouteQueryChanged(query)
      }
    },
    'batchStore.selectedBatchId'(batchId) {
      this.invalidateReads()
      const snapshot = this.lockedSnapshot()
      if (snapshot) {
        if (String(batchId || '') !== String(snapshot.batchId || '')) this.batchStore.selectBatch(snapshot.batchId)
        this.restoreLockedContext()
        return
      }
      this.invalidateArchivePreview('batch-change')
      this.riskPage = 1
      this.archivePage = 1
      this.riskSelKey = ''
      this.archiveSelKey = ''
      this.actionReceipt = null
      void this.replacePanelQuery(this.tab, { batchId: batchId ? String(batchId) : undefined, page: '1', rsel: undefined, asel: undefined })
      this.loadActivePanel()
    }
  },
  methods: {
    formatDateTime,
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    routePage(value) {
      const page = Number.parseInt(this.routeText(value), 10)
      return Number.isFinite(page) && page > 0 ? page : 1
    },
    invalidateReads() {
      ++this.riskLoadToken
      ++this.scanToken
      ++this.lastScanToken
      ++this.riskStatsToken
      ++this.archiveLoadToken
      ++this.statsLoadToken
    },
    lockedSnapshot() {
      return this.commandSnapshot || this.archiveCommandSnapshot
    },
    restoreLockedContext() {
      const snapshot = this.lockedSnapshot()
      if (!snapshot?.routeQuery) return
      this.$router.replace({ path: '/admin/graduation/risk-archive', query: snapshot.routeQuery }).catch(() => {})
    },
    isPanelAllowed(panel) {
      return (panel === 'risk' && this.canRiskView) || (panel === 'archive' && this.canArchiveView) || (panel === 'stats' && this.canStatsView)
    },
    applyInitialRouteState(query = {}) {
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
    onRouteQueryChanged(query = {}) {
      const requested = this.routeText(query.panel)
      const nextTab = this.isPanelAllowed(requested) ? requested : (this.availableTabs[0] || '')
      if (!nextTab) return
      let changed = nextTab !== this.tab
      this.tab = nextTab
      if (nextTab === 'risk') {
        const nextPage = this.routePage(query.page)
        const nextFilters = { keyword: this.routeText(query.keyword), status: this.routeText(query.status), level: this.routeText(query.level) }
        const nextSel = this.routeText(query.rsel)
        changed = changed || nextPage !== this.riskPage || JSON.stringify(nextFilters) !== JSON.stringify(this.riskFilters) || nextSel !== this.riskSelKey
        this.riskPage = nextPage
        this.riskFilters = nextFilters
        this.riskSelKey = nextSel
      } else if (nextTab === 'archive') {
        const nextPage = this.routePage(query.page)
        const nextFilters = { keyword: this.routeText(query.keyword), status: this.routeText(query.status) }
        const nextSel = this.routeText(query.asel)
        changed = changed || nextPage !== this.archivePage || JSON.stringify(nextFilters) !== JSON.stringify(this.archiveFilters) || nextSel !== this.archiveSelKey
        this.archivePage = nextPage
        this.archiveFilters = nextFilters
        this.archiveSelKey = nextSel
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
          page: this.riskPage > 1 ? String(this.riskPage) : undefined,
          rsel: this.riskSelKey || undefined,
          keyword: String(this.riskFilters.keyword || '').trim() || undefined,
          status: this.riskFilters.status || undefined,
          level: this.riskFilters.level || undefined,
          asel: undefined
        })
      } else if (panel === 'archive') {
        Object.assign(query, {
          page: this.archivePage > 1 ? String(this.archivePage) : undefined,
          asel: this.archiveSelKey || undefined,
          keyword: String(this.archiveFilters.keyword || '').trim() || undefined,
          status: this.archiveFilters.status || undefined,
          source: query.source || 'archive',
          rsel: undefined,
          level: undefined
        })
      } else {
        Object.assign(query, { page: undefined, rsel: undefined, asel: undefined, keyword: undefined, status: undefined, level: undefined })
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      return query
    },
    replacePanelQuery(panel, overrides = {}) {
      return this.$router.replace({ query: this.buildPanelQuery(panel, overrides) }).catch(() => {})
    },
    loadActivePanel() {
      if (this.tab === 'risk' && this.canRiskView) {
        this.loadRisks()
        this.loadLastScan()
        this.loadRiskStats()
      } else if (this.tab === 'archive' && this.canArchiveView) {
        this.loadArchives()
      } else if (this.tab === 'stats' && this.canStatsView) {
        this.loadStats()
      }
    },
    switchTab(tab) {
      if (this.contextLocked || !this.isPanelAllowed(tab)) return
      this.invalidateArchivePreview('panel-change')
      this.tab = tab
      void this.replacePanelQuery(tab)
      this.loadActivePanel()
    },
    levelLabel(level) { return { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '紧急' }[level] || (level ? '等级待确认' : '—') },
    async loadRiskStats() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.riskStatsToken
      if (!this.canRiskView || !batchId) {
        this.riskStats = null
        this.riskStatsError = ''
        this.riskStatsLoading = false
        return false
      }
      this.riskStatsLoading = true
      this.riskStatsError = ''
      try {
        const res = await graduationRiskArchiveApi.getRiskStats({ batchId })
        if (token !== this.riskStatsToken || batchId !== String(this.batchStore.selectedBatchId || '')) return false
        if (res.code === 0) {
          this.riskStats = res.data || null
          const embedded = res.data?.lastScan
          if (embedded?.lastScanAt && !this.lastScanAt) {
            this.lastScanAt = embedded.lastScanAt
            this.lastScanStats = embedded.stats || null
          }
          return true
        }
        this.riskStats = null
        this.riskStatsError = res.message || '风险规则统计加载失败'
      } catch (error) {
        if (token === this.riskStatsToken) {
          this.riskStats = null
          this.riskStatsError = errorText(error, '风险规则统计加载失败')
        }
      } finally {
        if (token === this.riskStatsToken) this.riskStatsLoading = false
      }
      return false
    },
    async loadLastScan() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.lastScanToken
      if (!this.canRiskView || !batchId) {
        this.lastScanAt = ''
        this.lastScanStats = null
        return false
      }
      try {
        const res = await graduationRiskArchiveApi.getLastRiskScan({ batchId })
        if (token !== this.lastScanToken || batchId !== String(this.batchStore.selectedBatchId || '')) return false
        if (res.code === 0 && res.data) {
          this.lastScanAt = res.data.lastScanAt || ''
          this.lastScanStats = res.data.stats || null
          return true
        }
      } catch { /* 最近扫描摘要独立降级，不覆盖风险队列 */ }
      return false
    },
    async doScan() {
      if (!this.canRiskScan || this.contextLocked) return
      const batchId = String(this.batchStore.selectedBatchId || '')
      if (!batchId) {
        toast.error('请先选择毕设批次')
        return
      }
      const snapshot = freezeSnapshot({ type: 'RISK_SCAN', batchId, routeQuery: this.buildPanelQuery('risk') })
      this.commandSnapshot = snapshot
      const token = ++this.scanToken
      this.actionBusy = 'scan-risk'
      try {
        const res = await graduationRiskArchiveApi.scanRisks({ batchId: snapshot.batchId })
        if (token !== this.scanToken) return
        if (res.code === 0) {
          const data = res.data || {}
          this.lastScanAt = data.lastScanAt || this.lastScanAt
          this.lastScanStats = { scannedStudents: data.scannedStudents, newCasesCreated: data.newCasesCreated, reopenedCases: data.reopenedCases, elapsedMs: data.elapsedMs }
          await Promise.all([this.loadRisks(), this.loadRiskStats()])
          toast.success(res.message || `已扫描 ${data.scannedStudents || 0} 人`)
        } else {
          toast.error(res.message || '风险扫描失败')
        }
      } catch (error) {
        toast.error(errorText(error, '风险扫描失败'))
      } finally {
        if (token === this.scanToken) this.actionBusy = ''
        this.commandSnapshot = null
      }
    },
    selectRisk(row, { force = false } = {}) {
      if (!row || (this.contextLocked && !force)) return
      this.riskSelKey = String(row.id)
      void this.replacePanelQuery('risk', { rsel: this.riskSelKey })
    },
    stepRisk(delta) {
      if (this.contextLocked) return
      const index = this.riskSelIndex + delta
      if (index >= 0 && index < this.riskRows.length) this.selectRisk(this.riskRows[index])
    },
    ensureRiskSelection() {
      if (!this.riskRows.length) {
        this.riskSelKey = ''
        void this.replacePanelQuery('risk', { rsel: undefined })
        return
      }
      const current = this.selectedRisk
      const actionable = (row) => row.status === 'OPEN' || row.status === 'PROCESSING'
      if (current && this.riskAutoNext && current.status === 'CLOSED') {
        const from = this.riskSelIndex
        for (let index = from + 1; index < this.riskRows.length; index += 1) {
          if (actionable(this.riskRows[index])) {
            this.selectRisk(this.riskRows[index], { force: true })
            return
          }
        }
      }
      if (!current) this.selectRisk(this.riskRows.find(actionable) || this.riskRows[0], { force: true })
    },
    async loadRisks() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.riskLoadToken
      const snapshot = { batchId, page: this.riskPage, filters: { ...this.riskFilters } }
      if (!this.canRiskView || !batchId) {
        this.riskLoading = false
        this.riskError = ''
        this.riskRows = []
        this.riskTotal = 0
        return false
      }
      this.riskLoading = true
      this.riskError = ''
      try {
        const res = await graduationRiskArchiveApi.getRiskList(buildRiskArchiveQuery(snapshot.filters, { page: snapshot.page, pageSize: this.riskPageSize, batchId: snapshot.batchId }))
        if (
          token !== this.riskLoadToken
          || snapshot.batchId !== String(this.batchStore.selectedBatchId || '')
          || snapshot.page !== this.riskPage
          || JSON.stringify(snapshot.filters) !== JSON.stringify(this.riskFilters)
        ) return false
        if (res.code === 0) {
          this.riskRows = Array.isArray(res.data?.list) ? res.data.list : []
          this.riskTotal = Number(res.data?.total) || 0
          this.ensureRiskSelection()
          return true
        }
        this.riskRows = []
        this.riskTotal = 0
        this.riskError = res.message || '风险队列加载失败'
      } catch (error) {
        if (token === this.riskLoadToken) {
          this.riskRows = []
          this.riskTotal = 0
          this.riskError = errorText(error, '风险队列加载失败')
        }
      } finally {
        if (token === this.riskLoadToken) this.riskLoading = false
      }
      return false
    },
    searchRisks() {
      if (this.contextLocked) return
      this.riskPage = 1
      void this.replacePanelQuery('risk', { page: undefined })
      this.loadRisks()
    },
    resetRiskFilters() {
      if (this.contextLocked) return
      this.riskFilters = { status: '', level: '', keyword: '' }
      this.riskPage = 1
      void this.replacePanelQuery('risk', { page: undefined, keyword: undefined, status: undefined, level: undefined })
      this.loadRisks()
    },
    changeRiskPage(page) {
      if (this.contextLocked) return
      this.riskPage = page
      this.riskSelKey = ''
      void this.replacePanelQuery('risk', { page: page > 1 ? String(page) : undefined, rsel: undefined })
      this.loadRisks()
    },
    openRiskStudent(row) {
      if (this.contextLocked || !row?.gdStudentId) return
      this.$router.push({
        name: 'graduation-student-detail',
        params: { id: String(row.gdStudentId) },
        query: {
          batchId: String(this.batchStore.selectedBatchId),
          source: 'risk',
          returnTo: this.$router.resolve({ path: '/admin/graduation/risk-archive', query: this.buildPanelQuery('risk') }).fullPath
        }
      })
    },
    askRiskAction(action, row) {
      if (this.contextLocked || !row) return
      const permission = { accept: this.canRiskAccept, process: this.canRiskProcess, close: this.canRiskClose }[action]
      if (!permission) {
        toast.error('当前角色无此风险操作权限')
        return
      }
      const batchId = String(this.batchStore.selectedBatchId || '')
      this.commandSnapshot = freezeSnapshot({ type: `RISK_${action.toUpperCase()}`, action, batchId, rowId: row.id, row: { ...row }, routeQuery: this.buildPanelQuery('risk') })
      const configs = {
        accept: { title: '受理风险', message: `确认受理「${row.riskName}」（${row.studentName}）？`, type: 'primary', confirmText: '受理', requireReason: false, reasonLabel: '说明' },
        process: { title: '记录处理', message: `为「${row.studentName} · ${row.riskName}」记录本次处理结果。`, type: 'primary', confirmText: '提交处理', requireReason: true, reasonLabel: '处理说明' },
        close: { title: '关闭风险', message: `确认关闭「${row.studentName} · ${row.riskName}」？`, type: 'danger', confirmText: '确认关闭', requireReason: true, reasonLabel: '关闭原因' }
      }
      this.confirm = { visible: true, action, row: { ...row }, reasonChips: [], ...configs[action] }
    },
    selectArchive(row, { force = false } = {}) {
      if (!row || (this.contextLocked && !force)) return
      this.archiveSelKey = String(row.id)
      void this.replacePanelQuery('archive', { asel: this.archiveSelKey })
    },
    stepArchive(delta) {
      if (this.contextLocked) return
      const index = this.archiveSelIndex + delta
      if (index >= 0 && index < this.archiveRows.length) this.selectArchive(this.archiveRows[index])
    },
    ensureArchiveSelection() {
      if (!this.archiveRows.length) {
        this.archiveSelKey = ''
        void this.replacePanelQuery('archive', { asel: undefined })
        return
      }
      if (!this.selectedArchive) this.selectArchive(this.archiveRows.find((row) => row.status !== 'FILED') || this.archiveRows[0], { force: true })
    },
    async loadArchives() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.archiveLoadToken
      const snapshot = { batchId, page: this.archivePage, filters: { ...this.archiveFilters } }
      if (!this.canArchiveView || !batchId) {
        this.archiveLoading = false
        this.archiveError = ''
        this.archiveRows = []
        this.archiveTotal = 0
        return false
      }
      this.archiveLoading = true
      this.archiveError = ''
      try {
        const res = await graduationRiskArchiveApi.getArchiveList(buildRiskArchiveQuery(snapshot.filters, { page: snapshot.page, pageSize: this.archivePageSize, batchId: snapshot.batchId }))
        if (
          token !== this.archiveLoadToken
          || snapshot.batchId !== String(this.batchStore.selectedBatchId || '')
          || snapshot.page !== this.archivePage
          || JSON.stringify(snapshot.filters) !== JSON.stringify(this.archiveFilters)
        ) return false
        if (res.code === 0) {
          this.archiveRows = Array.isArray(res.data?.list) ? res.data.list : []
          this.archiveTotal = Number(res.data?.total) || 0
          this.ensureArchiveSelection()
          return true
        }
        this.archiveRows = []
        this.archiveTotal = 0
        this.archiveError = res.message || '归档队列加载失败'
      } catch (error) {
        if (token === this.archiveLoadToken) {
          this.archiveRows = []
          this.archiveTotal = 0
          this.archiveError = errorText(error, '归档队列加载失败')
        }
      } finally {
        if (token === this.archiveLoadToken) this.archiveLoading = false
      }
      return false
    },
    searchArchives() {
      if (this.contextLocked) return
      this.invalidateArchivePreview('archive-filter')
      this.archivePage = 1
      void this.replacePanelQuery('archive', { page: undefined })
      this.loadArchives()
    },
    resetArchiveFilters() {
      if (this.contextLocked) return
      this.invalidateArchivePreview('archive-filter-reset')
      this.archiveFilters = { keyword: '', status: '' }
      this.archivePage = 1
      void this.replacePanelQuery('archive', { page: undefined, keyword: undefined, status: undefined })
      this.loadArchives()
    },
    changeArchivePage(page) {
      if (this.contextLocked) return
      this.invalidateArchivePreview('archive-page')
      this.archivePage = page
      this.archiveSelKey = ''
      void this.replacePanelQuery('archive', { page: page > 1 ? String(page) : undefined, asel: undefined })
      this.loadArchives()
    },
    archiveReturnTo() {
      return this.$router.resolve({ path: '/admin/graduation/risk-archive', query: this.buildPanelQuery('archive', { source: 'archive' }) }).fullPath
    },
    openArchiveStudent(row) {
      if (this.contextLocked || !row?.gdStudentId) return
      this.$router.push({
        name: 'graduation-student-detail',
        params: { id: String(row.gdStudentId) },
        query: {
          batchId: String(this.batchStore.selectedBatchId),
          source: 'archive',
          returnTo: this.archiveReturnTo()
        }
      })
    },
    goFix(item, row) {
      if (!this.canStudentView || this.contextLocked) return
      const sid = row.gdStudentId
      if (!sid) {
        this.$router.push({ path: '/admin/graduation/students', query: { batchId: String(this.batchStore.selectedBatchId), panel: 'roster', returnTo: this.archiveReturnTo() } })
        return
      }
      const name = String(item || '')
      let tab = ''
      if (name.includes('任务书')) tab = 'taskbook'
      else if (name.includes('开题')) tab = 'proposals'
      else if (name.includes('中期')) tab = 'midterm'
      else if (name.includes('指导')) tab = 'guidance'
      else if (name.includes('查重')) tab = 'plagiarisms'
      else if (name.includes('评阅') || name.includes('答辩') || name.includes('成绩')) tab = 'review'
      else if (name.includes('成果') || name.includes('论文')) tab = 'finals'
      this.$router.push({
        name: 'graduation-student-detail',
        params: { id: String(sid) },
        query: {
          ...(tab ? { tab } : {}),
          missingItem: name,
          source: 'archive',
          returnTo: this.archiveReturnTo(),
          batchId: String(this.batchStore.selectedBatchId)
        }
      })
    },
    createSingleArchiveSnapshot(action, row) {
      return freezeSnapshot({
        type: `ARCHIVE_${action.toUpperCase()}`,
        action,
        batchId: String(this.batchStore.selectedBatchId || ''),
        gdStudentId: String(row?.gdStudentId || ''),
        archiveBatchNo: row?.archiveBatchNo || '',
        row: { ...row },
        routeQuery: this.buildPanelQuery('archive')
      })
    },
    async runSingleArchiveWrite(action, row, task, receiptBuilder) {
      if (this.contextLocked || !row) return false
      const snapshot = this.createSingleArchiveSnapshot(action, row)
      this.commandSnapshot = snapshot
      this.actionBusy = action
      try {
        const res = await task(snapshot)
        if (res.code === 0) {
          await this.loadArchives()
          this.actionReceipt = receiptBuilder(res, snapshot)
          toast.success(this.actionReceipt.title)
          return true
        }
        this.archiveWriteFailed(res)
      } catch (error) {
        this.archiveWriteFailed({ code: 503001, message: errorText(error, '连接中断，无法确认服务器是否已经完成操作。') })
      } finally {
        this.actionBusy = ''
        this.commandSnapshot = null
      }
      return false
    },
    doGenerate(row) {
      if (!this.canArchivePreview) return
      return this.runSingleArchiveWrite('generate-archive', row,
        (snapshot) => graduationRiskArchiveApi.generateArchive(snapshot.gdStudentId, { batchId: snapshot.batchId }),
        (_res, snapshot) => ({ title: `${snapshot.row.studentName} · 归档清单已生成`, result: '服务器已回读最新归档状态。', next: '存在缺件时按精确深链补齐；材料齐全后提交归档。' }))
    },
    doSubmit(row) {
      if (!this.canArchiveFile) return
      return this.runSingleArchiveWrite('submit-archive', row,
        (snapshot) => graduationRiskArchiveApi.submitArchive(snapshot.gdStudentId, { batchId: snapshot.batchId }),
        (_res, snapshot) => ({ title: `${snapshot.row.studentName} · 归档已提交`, result: '服务器已回读最新归档状态。', next: '下一步由归档授权角色核验并备案。' }))
    },
    doFile(row) {
      if (!this.canArchiveFile) return
      return this.runSingleArchiveWrite('file-archive', row,
        (snapshot) => graduationRiskArchiveApi.fileArchive(snapshot.gdStudentId, snapshot.archiveBatchNo || null, { batchId: snapshot.batchId }),
        (_res, snapshot) => ({ title: `${snapshot.row.studentName} · 已正式归档备案`, result: '服务器已回读 FILED 状态；归档版本只读。', next: '可导出台账或执行备份核验。' }))
    },
    askRejectArchive(row) {
      if (!this.canArchiveFile || this.contextLocked || !row) return
      this.commandSnapshot = this.createSingleArchiveSnapshot('reject-archive', row)
      this.confirm = {
        visible: true,
        title: '驳回归档',
        message: `驳回「${row.studentName}」的归档申请？`,
        type: 'danger',
        confirmText: '确认驳回',
        requireReason: true,
        reasonLabel: '驳回原因',
        reasonChips: ARCHIVE_REJECT_REASON_CHIPS,
        action: 'reject-archive',
        row: { ...row }
      }
    },
    maskPreviewToken(token) {
      const value = String(token || '')
      if (!value) return '未签发'
      if (value.length <= 10) return '已签发 · 一次性'
      return `${value.slice(0, 5)}…${value.slice(-4)}`
    },
    invalidateArchivePreview(_reason = '') {
      this.archiveCommandSnapshot = null
      this.archivePreviewEvidence = null
    },
    formatSkipReasons(preview = {}) {
      const rows = Array.isArray(preview.skipReasons) ? preview.skipReasons : []
      if (!rows.length) return '无'
      const labels = { already_submitted_or_filed: '已提交 / 已备案', already_submitted: '已提交 / 已备案', dirty_data: '历史主档异常（只读）', missing_materials: '材料不齐', open_risks: '风险未关闭', out_of_scope: '不在当前范围' }
      return rows.map((row) => `${labels[row.reason] || row.reason} ${row.count}`).join('；')
    },
    async startArchivePreview(kind) {
      if (!this.canArchivePreview || !this.canArchiveFile || this.contextLocked) return
      const batchId = String(this.batchStore.selectedBatchId || '')
      if (!batchId) {
        toast.error('请先选择毕设批次')
        return
      }
      this.invalidateArchivePreview('new-preview')
      const previewing = freezeSnapshot({ phase: 'PREVIEWING', kind, batchId, routeQuery: this.buildPanelQuery('archive') })
      this.archiveCommandSnapshot = previewing
      this.previewBusy = `${kind}-preview`
      try {
        const res = kind === 'batch-file'
          ? await graduationRiskArchiveApi.previewBatchFile({ batchId: previewing.batchId })
          : await graduationRiskArchiveApi.previewBatchGenerate({ batchId: previewing.batchId })
        if (res.code !== 0) {
          toast.error(res.message || '归档预览失败')
          this.invalidateArchivePreview('preview-failed')
          return
        }
        const data = res.data || {}
        if (!data.previewToken) {
          toast.error('服务端未签发归档执行凭证，禁止进入正式执行')
          this.invalidateArchivePreview('token-missing')
          return
        }
        const snapshot = freezeSnapshot({
          phase: 'READY',
          kind,
          batchId: previewing.batchId,
          previewToken: data.previewToken,
          archiveBatchNo: data.archiveBatchNo || '',
          candidateCount: Math.max(0, Number(data.candidateCount) || 0),
          executableCount: Math.max(0, Number(data.executableCount) || 0),
          skippedCount: Math.max(0, Number(data.skippedCount) || 0),
          previewedAt: new Date().toISOString(),
          routeQuery: previewing.routeQuery
        })
        this.archiveCommandSnapshot = snapshot
        this.archivePreviewEvidence = {
          kind,
          kindLabel: kind === 'batch-file' ? '一键核验备案预览' : '批量生成提交预览',
          batchId: snapshot.batchId,
          batchName: data.batchName || this.batchStore.selectedBatchName || '当前批次',
          maskedToken: this.maskPreviewToken(snapshot.previewToken),
          archiveBatchNo: snapshot.archiveBatchNo,
          candidateCount: snapshot.candidateCount,
          executableCount: snapshot.executableCount,
          skippedCount: snapshot.skippedCount,
          previewedAt: snapshot.previewedAt
        }
        const action = snapshot.executableCount > 0 ? kind : `${kind}-noop`
        this.confirm = {
          visible: true,
          title: kind === 'batch-file' ? '一键核验备案' : '批量生成提交',
          message: `候选 ${snapshot.candidateCount} 人，可执行 ${snapshot.executableCount}，跳过 ${snapshot.skippedCount}。主要跳过原因：${this.formatSkipReasons(data)}。确认后只消费本次预览凭证一次。`,
          type: kind === 'batch-file' ? 'warning' : 'primary',
          confirmText: snapshot.executableCount > 0 ? (kind === 'batch-file' ? '确认核验备案' : '确认生成提交') : '知道了',
          requireReason: false,
          reasonLabel: '说明',
          reasonChips: [],
          action,
          row: null
        }
      } catch (error) {
        toast.error(errorText(error, '归档预览失败'))
        this.invalidateArchivePreview('preview-error')
      } finally {
        this.previewBusy = ''
      }
    },
    onConfirmCancel() {
      if (this.confirm.action.startsWith('batch-')) this.invalidateArchivePreview('user-cancel')
      this.commandSnapshot = null
      this.confirm = EMPTY_CONFIRM()
    },
    async onConfirm({ reason } = {}) {
      const action = this.confirm.action
      if (action.endsWith('-noop')) {
        this.confirm = EMPTY_CONFIRM()
        this.invalidateArchivePreview('noop-close')
        return
      }
      if (action === 'accept' || action === 'process' || action === 'close') {
        await this.executeRiskAction(action, reason)
        return
      }
      if (action === 'reject-archive') {
        await this.executeArchiveReject(reason)
        return
      }
      if (action === 'batch-generate' || action === 'batch-file') {
        await this.executeArchiveBatch(action)
      }
    },
    async executeRiskAction(action, reason) {
      const snapshot = this.commandSnapshot
      if (!snapshot || snapshot.action !== action || this.actionBusy) return
      this.actionBusy = action
      try {
        let res
        if (action === 'accept') res = await graduationRiskArchiveApi.acceptRisk(snapshot.rowId, undefined, { batchId: snapshot.batchId })
        else if (action === 'process') res = await graduationRiskArchiveApi.processRisk(snapshot.rowId, reason || '', { batchId: snapshot.batchId })
        else res = await graduationRiskArchiveApi.closeRisk(snapshot.rowId, reason || '', { batchId: snapshot.batchId })
        if (res.code === 0) {
          this.confirm = EMPTY_CONFIRM()
          await Promise.all([this.loadRisks(), this.loadRiskStats()])
          const label = action === 'accept' ? '风险已受理' : action === 'process' ? '处理记录已保存' : '风险已关闭'
          this.actionReceipt = { title: label, result: '服务器已接受操作并回读最新风险状态。', next: '可继续处理下一条风险。' }
          toast.success(label)
        } else {
          toast.error(res.message || '风险操作失败')
        }
      } catch (error) {
        toast.error(errorText(error, '风险操作失败'))
      } finally {
        this.actionBusy = ''
        this.commandSnapshot = null
      }
    },
    async executeArchiveReject(reason) {
      const snapshot = this.commandSnapshot
      if (!snapshot || snapshot.action !== 'reject-archive' || this.actionBusy) return
      this.actionBusy = 'reject-archive'
      try {
        const res = await graduationRiskArchiveApi.rejectArchive(snapshot.gdStudentId, reason || '', { batchId: snapshot.batchId })
        if (res.code === 0) {
          this.confirm = EMPTY_CONFIRM()
          await this.loadArchives()
          this.actionReceipt = { title: `${snapshot.row.studentName} · 归档已退回`, result: `服务器已记录退回原因：${reason}`, next: '下一步由学生或责任老师补齐材料后重新提交。' }
          toast.success('归档已退回')
        } else {
          toast.error(res.message || '归档驳回失败')
        }
      } catch (error) {
        this.archiveWriteFailed({ code: 503001, message: errorText(error, '连接中断，无法确认服务器是否已经完成操作。') })
      } finally {
        this.actionBusy = ''
        this.commandSnapshot = null
      }
    },
    async executeArchiveBatch(action) {
      const snapshot = this.archiveCommandSnapshot
      if (!snapshot || snapshot.phase !== 'READY' || snapshot.kind !== action || !snapshot.previewToken || this.actionBusy) {
        toast.error('归档预览上下文已失效，请重新预览')
        this.confirm = EMPTY_CONFIRM()
        this.invalidateArchivePreview('invalid-before-execute')
        return
      }
      const executing = freezeSnapshot({ ...snapshot, phase: 'EXECUTING', consumed: true })
      this.archiveCommandSnapshot = executing
      this.actionBusy = action
      try {
        const params = { batchId: executing.batchId }
        const body = { previewToken: executing.previewToken, archiveBatchNo: executing.archiveBatchNo || undefined }
        const res = action === 'batch-file'
          ? await graduationRiskArchiveApi.batchFileArchive(params, body)
          : await graduationRiskArchiveApi.batchGenerateArchive(params, body)
        this.confirm = EMPTY_CONFIRM()
        if (res.code === 0) {
          await this.loadArchives()
          if (action === 'batch-file') {
            this.actionReceipt = { title: '批量备案已核对', result: `服务器结果：已备案 ${res.data?.filed || 0}，跳过 ${res.data?.skipped || 0}`, next: res.data?.reconciled ? '连接中断后已按归档批次号精确对账，无需重复提交。' : '一次性凭证已消费；备案记录只读。' }
          } else {
            this.actionReceipt = { title: '批量生成提交已完成', result: `服务器结果：成功 ${res.data?.submitted || 0}，跳过 ${res.data?.skipped || 0}`, next: '一次性凭证已消费；请在归档队列核对最新清单。' }
          }
          toast.success(this.actionReceipt.title)
        } else if (Number(res.code) === 503002) {
          this.actionReceipt = { unknown: true, title: '备案结果尚未完全确认', result: res.message || `已核对 ${res.data?.filed || 0}/${res.data?.expectedExecutableCount || 0} 份`, next: '不要直接重复提交。先刷新归档台账核对；仍不完整时必须重新预览。' }
        } else {
          this.archiveWriteFailed(res)
        }
      } catch (error) {
        this.confirm = EMPTY_CONFIRM()
        this.archiveWriteFailed({ code: 503001, message: errorText(error, '连接中断，无法确认服务器是否已经完成操作。') })
      } finally {
        this.actionBusy = ''
        this.invalidateArchivePreview('executed')
      }
    },
    archiveWriteFailed(res) {
      if ([503001, 503002].includes(Number(res?.code))) {
        this.actionReceipt = { unknown: true, title: '写入结果需要核对', result: res?.message || '连接中断，无法确认服务器是否已经完成操作。', next: '不要重复点击。先刷新归档台账；需要重做时必须重新预览。' }
      } else {
        toast.error(res?.message || '归档操作未完成')
      }
    },
    async verifyUnknownResult() {
      if (this.contextLocked) return
      const snapshot = freezeSnapshot({ type: 'ARCHIVE_RECONCILE_READ', batchId: String(this.batchStore.selectedBatchId || ''), routeQuery: this.buildPanelQuery('archive') })
      this.commandSnapshot = snapshot
      this.actionBusy = 'verify-archive-result'
      try {
        await this.loadArchives()
        this.actionReceipt = { title: '台账已刷新', result: '已从服务器重新读取当前归档状态。', next: '按最新状态继续；仍不完整时重新预览，禁止复用旧凭证。' }
      } finally {
        this.actionBusy = ''
        this.commandSnapshot = null
      }
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
    async loadStats() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.statsLoadToken
      if (!this.canStatsView || !batchId) {
        this.statsLoading = false
        this.overview = null
        this.collegeRows = []
        return false
      }
      this.statsLoading = true
      this.statsError = ''
      try {
        const [overview, college] = await Promise.all([
          graduationRiskArchiveApi.getOverviewStats({ batchId }),
          graduationRiskArchiveApi.getCollegeComparison({ batchId })
        ])
        if (token !== this.statsLoadToken || batchId !== String(this.batchStore.selectedBatchId || '')) return false
        this.overview = overview.code === 0 ? overview.data : null
        this.collegeRows = college.code === 0 ? college.data : []
        if (overview.code !== 0) this.statsError = overview.message || '统计加载失败'
        return overview.code === 0
      } catch (error) {
        if (token === this.statsLoadToken) {
          this.overview = null
          this.collegeRows = []
          this.statsError = errorText(error, '统计加载失败')
        }
        return false
      } finally {
        if (token === this.statsLoadToken) this.statsLoading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ra-panel { gap: var(--space-3); }
.gp-tabs { display: flex; gap: var(--space-1); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-light, #e2e8f0); }
.gp-tabs__item { padding: 8px 14px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--text-secondary, #475569); font-size: 13px; cursor: pointer; }
.gp-tabs__item.is-active { border-bottom-color: var(--primary-600, #2563eb); color: var(--primary-600, #2563eb); font-weight: 700; }
.gp-tabs__item:disabled, .mp-link:disabled { cursor: not-allowed; opacity: .5; }
.rk-command, .ar-command { display: grid; grid-template-columns: minmax(300px, 1fr) minmax(0, 1.05fr) auto; gap: 14px; align-items: center; padding: 13px 15px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-lg, 12px); background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--bg-card, #fff) 74%); box-shadow: 0 14px 30px -28px rgba(37, 99, 235, .7); }
.rk-command__headline, .ar-command__copy { display: grid; min-width: 0; gap: 3px; }
.rk-command__headline > span, .ar-command__copy > span { color: var(--primary-600, #2563eb); font-size: 10px; font-weight: 700; letter-spacing: .08em; }
.rk-command__headline strong, .ar-command__copy strong { color: var(--text-primary, #0f172a); font-size: 14px; line-height: 1.45; }
.rk-command__headline small, .ar-command__copy small { color: var(--text-secondary, #475569); font-size: 10px; line-height: 1.45; }
.rk-command__metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.rk-command__metrics div { display: grid; justify-items: center; gap: 1px; padding: 7px; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: color-mix(in srgb, var(--bg-card, #fff) 86%, transparent); }
.rk-command__metrics b { color: var(--primary-700, #1d4ed8); font-size: 16px; }
.rk-command__metrics span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.rk-rules { padding: 10px 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 10px); background: var(--bg-subtle, #f8fafc); }
.rk-rules__head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; }
.rk-rules__head > div { display: flex; align-items: baseline; gap: 8px; }
.rk-rules__head span, .rk-rules__head small, .rk-rules__degraded { color: var(--text-tertiary, #64748b); font-size: 10px; }
.rk-rules__head strong { color: var(--text-primary, #0f172a); font-size: 12px; }
.rk-rules__degraded { margin: 0; padding: 7px 8px; border-radius: 7px; background: var(--warning-50, #fffbeb); line-height: 1.5; }
.rk-rules__grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 5px; }
.rk-rules__grid span { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 5px; align-items: center; min-width: 0; padding: 6px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 7px; background: var(--bg-card, #fff); }
.rk-rules__grid b { color: var(--primary-700, #1d4ed8); font-size: 8px; }
.rk-rules__grid i { overflow: hidden; color: var(--text-secondary, #475569); font-size: 9px; font-style: normal; text-overflow: ellipsis; white-space: nowrap; }
.rk-rules__grid em { display: grid; min-width: 20px; height: 20px; place-items: center; border-radius: 999px; background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); font-size: 9px; font-style: normal; font-weight: 700; }
.ar-command { grid-template-columns: minmax(0, 1fr) auto; }
.ar-command__actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 7px; }
.ar-preview-evidence { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; padding: 9px; border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-lg, 10px); background: var(--warning-50, #fffbeb); }
.ar-preview-evidence > div { display: grid; min-width: 0; gap: 2px; padding: 7px 8px; border-radius: 7px; background: color-mix(in srgb, var(--bg-card, #fff) 76%, transparent); }
.ar-preview-evidence span, .ar-preview-evidence small { color: var(--text-tertiary, #64748b); font-size: 9px; }
.ar-preview-evidence strong { overflow: hidden; color: var(--warning-800, #92400e); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.ra-filter.is-command-locked, .rk-split.is-command-locked { pointer-events: none; opacity: .72; }
.rk-split { display: flex; gap: var(--space-3); align-items: flex-start; }
.rk-list { display: flex; flex: 0 0 330px; flex-direction: column; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 10px); background: var(--bg-card, #fff); box-shadow: 0 10px 26px -28px rgba(15, 23, 42, .55); }
.rk-list__head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.rk-list__head > div { display: grid; }
.rk-list__head strong { color: var(--text-primary, #0f172a); font-size: 12px; }
.rk-list__head small, .rk-list__head > span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.rk-list__head > span { padding: 3px 6px; border-radius: 999px; background: var(--bg-subtle, #f1f5f9); }
.rk-rows { max-height: 600px; margin: 0; padding: 0; overflow-y: auto; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); list-style: none; }
.rk-row { padding: 9px 10px; border-bottom: 1px solid var(--border-light, #eef1f6); cursor: pointer; transition: background .12s ease, box-shadow .12s ease; }
.rk-row:last-child { border-bottom: 0; }
.rk-row:hover { background: var(--bg-subtle, #f8fafc); }
.rk-row.is-active { background: var(--primary-50, #eff6ff); box-shadow: inset 3px 0 0 var(--primary-600, #2563eb); }
.rk-row.is-disabled { cursor: not-allowed; }
.rk-row:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.rk-row__main { display: flex; align-items: center; gap: var(--space-2); }
.rk-row__name { flex: 1; overflow: hidden; color: var(--text-primary, #0f172a); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.rk-row__sub { margin-top: 2px; color: var(--text-secondary, #475569); font-size: 11px; }
.rk-row__meta { display: flex; align-items: center; gap: var(--space-2); margin-top: 3px; color: var(--text-tertiary, #64748b); font-size: 10px; }
.rk-row__idx { margin-left: auto; }
.ra-pagination { display: flex; justify-content: center; }
.rk-pane { min-width: 0; flex: 1; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 10px); background: var(--bg-card, #fff); box-shadow: 0 10px 26px -28px rgba(15, 23, 42, .55); }
.rk-pane__bar { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--bg-subtle, #f8fafc); color: var(--text-secondary, #475569); font-size: 11px; }
.rk-pane__auto { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.rk-pane__nav { display: inline-flex; gap: var(--space-3); margin-left: auto; }
.rk-detail__eyebrow { display: block; margin-bottom: 2px; color: var(--primary-600, #2563eb); font-size: 9px; font-weight: 700; letter-spacing: .06em; }
.ar-missing-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-top: 8px; }
.ar-missing-head > div { display: grid; gap: 2px; }
.ar-missing-head strong { color: var(--text-primary, #0f172a); font-size: 11px; }
.ar-missing-head span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.ar-missing-head b { color: var(--danger-600, #dc2626); font-size: 12px; }
.ar-missing { margin: var(--space-1) 0 0; padding: 0; list-style: none; }
.ar-missing__item { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 6px; padding: 6px 10px; border: 1px dashed var(--danger-300, #fca5a5); border-radius: var(--radius-md, 8px); background: var(--danger-50, #fef2f2); font-size: 11px; }
.ar-missing__name, .is-missing { color: var(--danger-600, #dc2626); }
.is-complete { color: var(--success-600, #16a34a); }
.ar-anomaly { color: var(--danger-600, #dc2626); font-weight: 600; }
.ie-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.ie-actions--left { justify-content: flex-start; margin-top: var(--space-3); }
.ra-receipt { display: flex; align-items: center; gap: 14px; margin-bottom: var(--space-3); padding: 11px 12px; border: 1px solid var(--success-200, #bbf7d0); border-radius: var(--radius-md, 9px); background: var(--success-50, #f0fdf4); }
.ra-receipt.is-unknown { border-color: var(--warning-300, #f6c453); background: var(--warning-50, #fff9e8); }
.ra-receipt div { display: grid; flex: 1; gap: 3px; }
.ra-receipt strong { color: var(--success-700, #137a43); }
.ra-receipt.is-unknown strong { color: var(--warning-800, #8a5b00); }
.ra-receipt span { font-size: 12px; }
.ra-receipt small { color: var(--text-tertiary, #64748b); font-size: 10px; }
.ra-receipt button { padding: 6px 9px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 7px; background: var(--bg-card, #fff); color: var(--primary-600, #2563eb); cursor: pointer; }
.gs-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.gs-card { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 10px); background: linear-gradient(145deg, var(--bg-subtle, #f8fafc), var(--bg-card, #fff)); }
.gs-card span { color: var(--text-tertiary, #64748b); font-size: 11px; }
.gs-card strong { color: var(--text-primary, #0f172a); font-size: 21px; }
.gm-section-title { margin-top: var(--space-3); font-size: 12px; font-weight: 700; }
.gs-stage-list { display: flex; flex-wrap: wrap; gap: var(--space-4); margin: 8px 0; padding: 0; list-style: none; font-size: 12px; }
@media (max-width: 1280px) { .rk-command { grid-template-columns: 1fr auto; } .rk-command__metrics { grid-column: 1 / -1; } .rk-rules__grid { grid-template-columns: repeat(5, minmax(0, 1fr)); } }
@media (max-width: 1100px) { .rk-split { flex-direction: column; } .rk-list, .rk-pane { width: 100%; box-sizing: border-box; } .ar-preview-evidence { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .rk-command, .ar-command { grid-template-columns: 1fr; } .rk-command__metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .rk-rules__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .ar-command__actions { justify-content: flex-start; } .ar-preview-evidence { grid-template-columns: 1fr; } .rk-rules__head { align-items: flex-start; flex-direction: column; } }
</style>
