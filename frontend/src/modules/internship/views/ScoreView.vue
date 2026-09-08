<template>
  <ModulePageShell :title="pageTitle" :subtitle="pageSubtitle"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton v-if="activeArea === 'scores' && !panel.visible" code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="primary" @click="openCompute()">核算成绩</AppPermissionButton>
      <AppExportButton v-if="activeArea === 'scores' && !panel.visible" :export-fn="exportFn" :has-permission="canBtn('internship.score.export')" @exported="onExported">导出成绩台账</AppExportButton>
    </template>

    <div class="stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

      <nav v-if="!panel.visible && !selectedAppealId" class="queue-tabs" aria-label="成绩工作队列">
        <button type="button" :class="{ active: activeArea === 'scores' && !statusFilter && !missingOnly }" @click="setQueue('overview')">成绩台账</button>
        <button type="button" :class="{ active: activeArea === 'scores' && missingOnly }" @click="setQueue('missing')">缺项</button>
        <button type="button" :class="{ active: activeArea === 'scores' && statusFilter === 'PENDING_CALC' }" @click="setQueue('calculate')">待核算</button>
        <button type="button" :class="{ active: activeArea === 'scores' && statusFilter === 'PENDING_REVIEW' }" @click="setQueue('review')">待复核</button>
        <button type="button" :class="{ active: activeArea === 'scores' && statusFilter === 'PENDING_PUBLISH' }" @click="setQueue('publish')">待发布</button>
        <button v-if="canBtn('internship.score.publish')" type="button" :class="{ active: activeArea === 'appeal' }" @click="setQueue('appeal')">成绩申诉</button>
        <button type="button" :class="{ active: activeArea === 'config' }" @click="setQueue('config')">评分规则</button>
      </nav>

      <ScoreAppealWorkspace v-if="activeArea === 'appeal' && selectedAppealId" :appeal-id="selectedAppealId" :batch-id="String(batchStore.selectedBatchId || '')" :ctx="ctx" @back="closeAppeal" @handled="loadAppeals" @score="openAppealScore" />
      <div v-else-if="activeArea === 'appeal'" class="appeals">
        <div class="appeals__head">
          <div><strong>成绩申诉</strong><span>受理后撤回原成绩，再重新核算、复核和发布。</span></div>
          <AppButton variant="ghost" size="sm" :disabled="appealsLoading" @click="loadAppeals">刷新</AppButton>
        </div>
        <div v-if="appealsLoading" class="state">正在加载申诉…</div>
        <div v-else-if="appealsError" class="state is-err" role="alert">{{ appealsError }}</div>
        <div v-else-if="!appeals.length" class="state">当前批次暂无成绩申诉</div>
        <div v-else class="appeals__list">
          <div v-for="item in appeals" :key="item.id" class="appeal-row">
            <div class="appeal-row__main">
              <div><strong>{{ item.studentName }}</strong> · {{ item.studentNo || '无学号' }} · <AppStatusTag :status="item.status">{{ item.statusLabel }}</AppStatusTag></div>
              <div class="appeal-row__reason">申诉理由：{{ item.reason }}</div>
              <div class="appeal-row__reason">冻结成绩：{{ item.scoreSnapshot?.totalScore ?? '—' }} 分 · 当前成绩状态：{{ scoreStatusLabel(item.currentScore?.status) }}</div>
            </div>
            <AppButton variant="secondary" size="sm" @click="openAppeal(item)">{{ item.status === 'PENDING' ? '办理申诉' : '查看处理结果' }}</AppButton>
          </div>
        </div>
        <AppPagination :page="appealsPage" :page-size="20" :total="appealsTotal" :show-size-changer="false" :disabled="appealsLoading" @change="onAppealsPageChange" />
      </div>

      <!-- 权重配置（真实 getConfig / saveConfig） -->
      <section v-if="activeArea === 'config'" class="cfg-section">
      <h2 class="sec-t">当前批次评分规则</h2>
      <div v-if="cfgLoading" class="state">正在读取评分规则…</div>
      <div v-else-if="cfgError" class="state is-err" role="alert">{{ cfgError }} <AppButton variant="ghost" @click="loadConfig">重试</AppButton></div>
      <template v-else-if="cfgLoaded">
      <p class="hint">{{ cfg.scope === 'BATCH' ? '使用本批次规则' : cfg.scope === 'TENANT_DEFAULT' ? '沿用学校默认规则' : '沿用系统默认规则' }} · {{ batchStore.batchStatus !== 'DRAFT' ? '批次已启用，评分规则只读' : canEditConfig ? '保存后应用于当前草稿批次' : '当前账号可查看评分规则，无修改权限' }}</p>
      <dl v-if="!canEditConfig" class="rule-values">
        <div v-for="w in weightDefs" :key="w.key"><dt>{{ w.label }}权重</dt><dd>{{ cfg[w.key] ?? '—' }}<small>%</small></dd></div>
        <div><dt>及格线</dt><dd>{{ cfg.passLine ?? '—' }}<small>分</small></dd></div>
      </dl>
      <fieldset v-else class="cfg" :disabled="savingCfg">
        <div v-for="w in weightDefs" :key="w.key" class="cfg__item">
          <label :for="`score-${w.key}`">{{ w.label }}权重（%）</label><AppNumberInput :id="`score-${w.key}`" v-model="cfg[w.key]" :min="0" :max="100" :precision="0" size="compact" />
        </div>
        <div class="cfg__item"><label for="score-pass-line">及格线</label><AppNumberInput id="score-pass-line" v-model="cfg.passLine" :min="0" :max="100" size="compact" /></div>
        <span class="cfg__sum" :class="{ 'is-bad': weightSum !== 100 }">合计 {{ weightSum }}/100</span>
        <AppPermissionButton code="internship.score.config.manage" :allowed="canBtn('internship.score.config.manage')" variant="primary" :disabled="!canEditConfig" size="sm" :loading="savingCfg" @click="saveConfig">保存本批次规则</AppPermissionButton>
      </fieldset>
      <p v-if="cfgSaveError" class="local-error" role="alert">{{ cfgSaveError }}</p>
      </template>
      </section>

      <!-- 快捷筛选行：状态、仅看缺项都是后端过滤，跨页有效 -->
      <template v-if="activeArea === 'scores' && !panel.visible">
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <label class="status-filter">成绩状态
          <select v-model="statusFilter" @change="reload"><option value="">全部状态</option><option v-for="option in statusOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select>
        </label>
        <label class="missing-filter"><input v-model="missingOnly" type="checkbox" true-value="MISSING" false-value="" @change="reload" />仅看缺项</label>
        <span v-if="missingOnly && !loading && !error" class="bar__note">当前筛选共 {{ total }} 条缺项记录</span>
      </div>

      <div v-if="loading" class="state">正在加载成绩…</div>
      <div v-else-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
      <div v-else-if="!rows.length" class="state">当前筛选下暂无成绩记录</div>
      <template v-else>
        <DataTable :columns="columns" :rows="rows" row-key="id" :loading="loading"
          :pagination="pagination" row-clickable @row-click="openDetail" @page-change="onPageChange">
          <template #cell-studentName="{ row }">
            <span :class="{ 'is-current': String(row.id) === String(panel.rowId) }">{{ row.studentName }}</span><div class="hint">{{ row.studentNo }}</div>
          </template>
          <template #cell-checkinScore="{ row }">
            <span v-if="isMissing(row.checkinScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.checkinScore }}</span>
          </template>
          <template #cell-weeklyScore="{ row }">
            <span v-if="isMissing(row.weeklyScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.weeklyScore }}</span>
          </template>
          <template #cell-monthlyScore="{ row }">
            <span v-if="isMissing(row.monthlyScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.monthlyScore }}</span>
          </template>
          <template #cell-enterpriseScore="{ row }">
            <span v-if="isMissing(row.enterpriseScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.enterpriseScore }}</span>
          </template>
          <template #cell-schoolScore="{ row }">
            <span v-if="isMissing(row.schoolScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.schoolScore }}</span>
          </template>
          <template #cell-sources="{ row }">
            <div class="source-pills">
              <span :class="{ ok: row.sourceReadiness?.enterpriseEvaluation }">企业</span>
              <span :class="{ ok: row.sourceReadiness?.studentSelfEvaluation }">自评</span>
              <span :class="{ ok: row.sourceReadiness?.advisorEvaluation }">导师</span>
            </div>
          </template>
          <template #cell-total="{ row }">
            <b>{{ row.incomplete ? '—' : row.totalScore }}</b><span v-if="row.incomplete" class="miss-cell">缺项</span>
          </template>
          <template #cell-pass="{ row }">{{ row.incomplete ? '—' : (row.isPass ? '及格' : '不及格') }}</template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag></template>
          <template #cell-actions="{ row }">
            <div class="ops">
              <AppButton variant="ghost" size="sm" @click="openDetail(row)">核对</AppButton>
              <AppPermissionButton v-if="canRecalc(row)" code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="ghost" size="sm" @click="openCompute(row)">核算/重算</AppPermissionButton>
            </div>
          </template>
        </DataTable>
      </template>
      </template>

      <!-- 对象级办理区与列表互斥，地址保留筛选与返回来源。 -->
      <div v-if="panel.visible" class="wsp">
        <div class="wsp__head">
          <span class="wsp__title">{{ panelTitle }}</span>
          <AppStatusTag v-if="panelRow" :status="panelRow.status">{{ panelRow.statusLabel }}</AppStatusTag>
          <span v-if="panelRow && panelRow.incomplete" class="miss-cell">{{ panelRow.incompleteReason || '缺项' }}</span>
          <AppButton class="wsp__close" variant="ghost" size="sm" :disabled="panel.submitting || cForm.uploading || cd.submitting" @click="closePanel">{{ $route.query.fromAppeal ? '返回申诉办理' : '返回成绩台账' }}</AppButton>
        </div>
        <p v-if="panelError" class="local-error" role="alert">{{ panelError }}</p>
        <p v-if="keptReason" class="kept-reason">上次填写意见：{{ keptReason }}</p>
        <div v-if="panel.loading" class="state">正在读取成绩与来源…</div>
        <div v-else-if="panel.error" class="state is-err" role="alert">{{ panel.error }} <AppButton variant="ghost" @click="refreshPanel">重试</AppButton></div>
        <template v-else>
          <template v-if="panel.data">
            <div class="score-result"><div><small>上次核算总分</small><strong>{{ panel.data.incomplete ? '缺项' : panel.data.totalScore ?? '—' }}<small v-if="!panel.data.incomplete">分</small></strong></div><p>{{ scoreNextStep }}</p></div>
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div class="score-breakdown"><table><caption>上次核算的成绩构成</caption><thead><tr><th>分项</th><th>建议分</th><th>人工调整</th><th>分项成绩</th><th>权重</th></tr></thead><tbody><tr v-for="s in scoreInputs" :key="s.key"><th>{{ s.name }}</th><td>{{ panel.data.suggestedScores?.[s.key] ?? '—' }}</td><td>{{ panel.data.manualAdjustments?.[s.key] ?? '—' }}</td><td>{{ panel.data[`${s.key}Score`] ?? '缺项' }}</td><td>{{ panel.data.weights?.[s.key] ?? '—' }}%</td></tr></tbody></table></div>
            <div class="source-readiness">
              <strong>核算来源</strong>
              <span :class="{ ok: panel.data.sourceReadiness?.enterpriseEvaluation }">企业评价 · {{ panel.data.sourceReadiness?.enterpriseEvaluation ? '已关联' : '未关联' }}</span>
              <span :class="{ ok: panel.data.sourceReadiness?.studentSelfEvaluation }">学生自评 · {{ panel.data.sourceReadiness?.studentSelfEvaluation ? '已关联' : '未关联' }}</span>
              <span :class="{ ok: panel.data.sourceReadiness?.advisorEvaluation }">导师评价 · {{ panel.data.sourceReadiness?.advisorEvaluation ? '已关联' : '未关联' }}</span>
            </div>
            <div v-if="panel.data.adjustmentReason" class="adjustment-evidence"><h3>上次调分依据</h3><p class="kept-reason">{{ panel.data.adjustmentReason }}</p><AppButton v-for="(id, index) in panel.data.adjustmentEvidenceFileIds || []" :key="id" variant="ghost" size="sm" :disabled="!!previewingFile" @click="previewEvidence(id)">查看依据 {{ index + 1 }}</AppButton></div>
          </template>
          <template v-if="panel.mode === 'detail' && panel.data">
            <p v-if="hasSavedAdjustment" class="hint">人工调分须由其他授权人员复核；复核与发布时会再次核对来源事实。</p>
            <div class="wsp__ops">
              <AppButton v-if="canAct(panelRow, 'review')" variant="primary" :disabled="actionConflict" @click="confirmAct(panelRow, 'review')">复核通过</AppButton>
              <AppButton v-if="canAct(panelRow, 'publish')" variant="primary" :disabled="actionConflict" @click="confirmAct(panelRow, 'publish')">发布成绩</AppButton>
              <AppButton v-if="canRecalc(panelRow) && canBtn('internship.score.manage')" variant="secondary" @click="openCompute(panelRow)">重新核算</AppButton>
              <AppButton v-if="canAct(panelRow, 'return')" variant="ghost" :disabled="actionConflict" @click="confirmAct(panelRow, 'return')">退回重算</AppButton>
              <AppButton v-if="canAct(panelRow, 'withdraw')" variant="ghost" :disabled="actionConflict" @click="confirmAct(panelRow, 'withdraw')">撤回成绩</AppButton>
            </div>
            <AppButton v-if="actionConflict" variant="secondary" @click="acknowledgeAction">已核对最新成绩，重新选择操作</AppButton>
            <div class="sec-t">处理记录</div><AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
          </template>
          <template v-else-if="panel.mode !== 'detail'">
          <p class="hint">核算时重新读取当前过程和评价事实。需要人工调分时填写增减分，并提供原因与依据。</p>
          <fieldset class="compute-fields" :disabled="!canCompute || panel.submitting || cForm.uploading">
          <AppFormItem v-if="panel.mode === 'create'" label="实习学生" required>
            <AppInternshipStudentPicker
              v-model="cForm.internshipId"
              :key="batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId, status: 'ASSESSING' }"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <div class="scores">
            <AppFormItem v-for="s in scoreInputs" :key="s.key" v-slot="{ id }" :label="s.label" class="score">
              <AppNumberInput :id="id" v-model="cForm.manualAdjustments[s.key]" :min="-100" :max="100" :precision="0" />
            </AppFormItem>
          </div>
          <template v-if="hasManualAdjustment">
            <AppFormItem v-slot="{ id }" label="调分原因" required>
              <AppTextarea :id="id" v-model="cForm.adjustmentReason" :rows="2" placeholder="不少于5字，说明调整依据" />
            </AppFormItem>
            <AppFormItem v-slot="{ id }" label="调分依据" required>
              <input :id="id" type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" :disabled="cForm.uploading" @change="uploadAdjustmentEvidence" />
              <span class="hint">{{ cForm.uploading ? '正在上传…' : '上传文件将在核算成功后绑定，安全状态由文件中心校验。' }}</span>
              <div v-for="(id, index) in cForm.evidenceFileIds" :key="id" class="evidence-row"><AppButton variant="ghost" size="sm" @click="previewEvidence(id)">查看依据 {{ index + 1 }}</AppButton><AppButton variant="ghost" size="sm" @click="cForm.evidenceFileIds = cForm.evidenceFileIds.filter(fileId => fileId !== id)">移出本次调分</AppButton></div>
            </AppFormItem>
          </template>
          </fieldset>
          <p v-if="computeConflict" class="local-error" role="alert">记录或来源已变化，调整内容已保留，请先核对最新结果。</p>
          <AppButton v-if="computeConflict && panel.data" variant="secondary" @click="restoreCompute">放弃当前调整，恢复最新记录</AppButton>
          <p v-if="!canBtn('internship.score.manage')" class="hint">当前账号没有核算权限。</p>
          <p v-else-if="panel.mode === 'edit' && panel.data && !canRecalc(panel.data)" class="hint">当前成绩状态不允许重算，请返回成绩核对页查看可用操作。<AppButton variant="ghost" @click="openDetail(panel.data)">查看成绩</AppButton></p>
          <div class="wsp__ops">
            <AppButton variant="primary" :disabled="!canCompute || cForm.uploading" :loading="panel.submitting" @click="submitCompute(false)">核算成绩</AppButton>
            <AppButton v-if="panel.mode === 'edit' && hasNextMissing" variant="secondary" :disabled="!canCompute || cForm.uploading" :loading="panel.submitting" @click="submitCompute(true)">核算并处理本页下一缺项</AppButton>
          </div>
          </template>
        </template>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" :confirm-disabled="actionConflict" @confirm="onConfirm"><p v-if="panelError" class="local-error" role="alert">{{ panelError }}</p><p v-if="actionConflict" class="hint">本次确认已暂停。请取消确认并核对页面上的最新成绩，原意见已保留。</p></AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppNumberInput, AppFormItem, AppInternshipStudentPicker,
  AppTextarea, AppPagination } from '@/components/common'
import ActionReceipt from './components/ActionReceipt.vue'
import ScoreAppealWorkspace from './components/ScoreAppealWorkspace.vue'
import { scoreApi } from '@/modules/internship/api/score.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { isConflict } from '@/modules/internship/composables/conflictGuard'
import { fileSdk } from '@/services/file/fileSdk'

const WEIGHTS = [
  { key: 'checkinWeight', label: '打卡' }, { key: 'weeklyWeight', label: '周报' },
  { key: 'monthlyWeight', label: '月报' }, { key: 'enterpriseWeight', label: '企业' }, { key: 'schoolWeight', label: '学校' }
]
const SCORE_INPUTS = [
  { key: 'checkin', name: '打卡', label: '打卡增减' }, { key: 'weekly', name: '周报', label: '周报增减' },
  { key: 'monthly', name: '月报总结', label: '月报总结增减' }, { key: 'enterprise', name: '企业评价', label: '企业评价增减' }, { key: 'school', name: '学校评价', label: '学校评价增减' }
]
const COLUMNS = [
  { key: 'studentName', title: '学生', width: '140px' },
  { key: 'checkinScore', title: '打卡' }, { key: 'weeklyScore', title: '周报' }, { key: 'monthlyScore', title: '月报' },
  { key: 'enterpriseScore', title: '企业评价' }, { key: 'schoolScore', title: '学校评价' }, { key: 'sources', title: '来源闭环' },
  { key: 'total', title: '总分' }, { key: 'pass', title: '及格' }, { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '160px' }
]
const STATUS_MAP = { PENDING_CALC: '待核算', PENDING_REVIEW: '待复核', PENDING_PUBLISH: '待发布', PUBLISHED: '已发布', WITHDRAWN: '已撤回', ARCHIVED: '已归档' }

const RECALC_STATUSES = ['PENDING_REVIEW', 'PENDING_CALC', 'WITHDRAWN']
const DETAIL = [
  { key: 'studentNo', label: '学号' }, { key: 'advisorName', label: '指导教师' },
  { key: 'passLine', label: '及格线' }, { key: 'incompleteReason', label: '缺项说明' }
]
const emptyComputeForm = () => ({ internshipId: '', manualAdjustments: { checkin: 0, weekly: 0, monthly: 0, enterprise: 0, school: 0 }, adjustmentReason: '', evidenceFileIds: [], uploading: false })
const emptyPanel = () => ({ visible: false, mode: 'detail', rowId: '', loading: false, error: '', data: null, submitting: false })

export default {
  name: 'ScoreView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppNumberInput, AppFormItem, AppInternshipStudentPicker,
    AppTextarea, ActionReceipt, AppPagination, ScoreAppealWorkspace },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '', listSequence: 0,
      appeals: [], appealsLoading: false, appealsError: '', appealsPage: 1, appealsTotal: 0, appealsSequence: 0,
      keyword: '', statusFilter: '', missingOnly: '', columns: COLUMNS, weightDefs: WEIGHTS, scoreInputs: SCORE_INPUTS,
      statusOptions: Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label })),
      cfg: {}, cfgLoading: false, cfgLoaded: false, cfgError: '', cfgSaveError: '', cfgSequence: 0,
      savingCfg: false,
      cForm: emptyComputeForm(), computeVersion: null, computeInitial: '', computeConflict: false, actionConflict: false,
      panel: emptyPanel(), detailSequence: 0, panelError: '', keptReason: '', previewingFile: '', removeGuard: null,
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    selectedAppealId() { return String(this.$route.query.appealId || '') },
    activeArea() { return ['config', 'appeal'].includes(this.$route.query.stage) ? this.$route.query.stage : 'scores' },
    pageTitle() {
      if (this.activeArea === 'appeal') return this.selectedAppealId ? '申诉办理' : '成绩申诉'
      if (this.activeArea === 'config') return '评分规则'
      return this.panel.visible ? this.panelTitle : '综合成绩'
    },
    pageSubtitle() {
      if (this.activeArea === 'appeal') return '对照原成绩与申诉材料，记录核查意见并反馈处理结果。'
      if (this.activeArea === 'config') return '核对当前批次的分项权重与及格线。'
      return this.panel.visible ? '核对成绩来源与当前状态，完成本次办理后返回原队列。' : '补齐成绩来源，依次完成核算、独立复核与发布。'
    },
    canEditConfig() { return this.cfgLoaded && !this.cfgLoading && !this.cfgError && this.batchStore.batchStatus === 'DRAFT' && this.canBtn('internship.score.config.manage') },
    weightSum() { return WEIGHTS.reduce((a, w) => a + (Number(this.cfg[w.key]) || 0), 0) },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },

    panelRow() { return this.panel.data || this.rows.find((r) => String(r.id) === String(this.panel.rowId)) || null },
    canCompute() { return !!this.batchStore.selectedBatchId && this.canBtn('internship.score.manage') && !this.panel.loading && !this.panel.error && !this.computeConflict && (this.panel.mode === 'create' || (this.panel.mode === 'edit' && this.panel.data && this.canRecalc(this.panel.data))) },
    computeDirty() { return this.panel.visible && ['edit', 'create'].includes(this.panel.mode) && !!this.computeInitial && this.computeSnapshot() !== this.computeInitial },
    hasSavedAdjustment() { return Object.values(this.panel.data?.manualAdjustments || {}).some(value => Number(value) !== 0) },
    scoreNextStep() { const d = this.panel.data; if (!d) return ''; if (d.incomplete) return d.incompleteReason || '补齐来源事实后重新核算'; if (this.panel.mode === 'edit' && this.canRecalc(d)) return '核对调整后重新核算，成功后交由授权人员复核'; return ({ PENDING_CALC: '按当前来源事实重新核算', WITHDRAWN: '成绩已撤回，需重新核算、复核与发布', PENDING_REVIEW: '等待授权人员核对来源与成绩，完成独立复核', PENDING_PUBLISH: '复核已完成，等待学校管理员发布', PUBLISHED: '已发布，学生可查询正式成绩', ARCHIVED: '已归档；异议按档案更正流程办理' })[d.status] || '请核对当前状态' },
    panelTitle() {
      if (this.panel.mode === 'create') return '核算成绩（选择学生）'
      const name = (this.panel.data && this.panel.data.studentName) || (this.panelRow && this.panelRow.studentName) || ''
      return (this.panel.mode === 'edit' ? '核算成绩' : '成绩核对') + (name ? ` · ${name}` : '')
    },
    hasNextMissing() {
      return this.rows.some((r) => r.incomplete && this.canRecalc(r) && r.id !== this.panel.rowId)
    },
    hasManualAdjustment() {
      return Object.values(this.cForm.manualAdjustments || {}).some((value) => Number(value || 0) !== 0)
    },
    detailItems() { const d = this.panel.data || {}; return DETAIL.map((f) => ({ label: f.label, value: f.key === 'incompleteReason' ? (d.incomplete ? d.incompleteReason || '需补齐来源' : '无缺项') : d[f.key] })) },
    auditRecords() {
      return (this.panel.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actionLabel: ({ COMPUTE: '核算成绩', COMPUTE_FACT_SNAPSHOT: '保存核算来源', MANUAL_ADJUSTMENT_REVIEW: '复核人工调分', REVIEW: '复核成绩', PUBLISH: '发布成绩', WITHDRAW: '撤回成绩', RETURN: '退回重算' })[t.action], actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.comment || (t.detail.missing || []).join('、')), at: t.occurredAt
      }))
    }
  },
  created() {
    this.loadConfig()
  },
  watch: {
    '$route.query': { immediate: true, deep: true, handler() { this.applyStageFromRoute() } },
    'batchStore.selectedBatchId'(next, previous) {
      this.page = 1; this.appealsPage = 1; this.resetPanel(); this.lastReceipt = null; this.loadConfig(); this.load(); this.loadAppeals()
      if (previous && String(next) !== String(previous)) { const query = this.batchStore.withBatchQuery({ ...this.$route.query, page: '1', appealPage: '1' }); delete query.id; delete query.mode; delete query.appealId; delete query.fromAppeal; this.$router.replace({ query }) }
      else this.syncPanelFromRoute()
    },
    ctx: { deep: true, handler() { this.resetPanel(); this.lastReceipt = null; this.loadConfig(); this.load(); this.loadAppeals(); this.syncPanelFromRoute() } }
  },
  mounted() {
    this.removeGuard = this.$router.beforeEach((to, from) => {
      if (to.fullPath === from.fullPath) return true
      if (this.panel.submitting || this.cForm.uploading || this.cd.submitting) return false
      if (!this.computeDirty) return true
      if (to.path === from.path && ['id', 'mode', 'batchId'].every(key => String(to.query[key] || '') === String(from.query[key] || '')) && !['appeal', 'config'].includes(to.query.stage)) return true
      return window.confirm('当前核算调整尚未提交，离开会丢失填写内容。仍要离开吗？')
    })
    window.addEventListener('beforeunload', this.beforeUnload)
  },
  beforeUnmount() { this.listSequence++; this.appealsSequence++; this.cfgSequence++; this.cfg = {}; this.resetPanel(); this.removeGuard?.(); window.removeEventListener('beforeunload', this.beforeUnload) },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    setQueue(stage) {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, stage })
      delete query.appealId; delete query.id; delete query.mode; delete query.fromAppeal
      if (!['config', 'appeal'].includes(stage)) {
        query.page = '1'
        query.status = ({ calculate: 'PENDING_CALC', review: 'PENDING_REVIEW', publish: 'PENDING_PUBLISH' })[stage] || ''
        query.incompleteOnly = stage === 'missing' ? '1' : ''
      }
      this.$router.replace({ query })
    },
    applyStageFromRoute() {
      const q = this.$route.query, stage = String(q.stage || '').toLowerCase()
      this.statusFilter = q.status != null ? String(q.status) : ({ calculate: 'PENDING_CALC', review: 'PENDING_REVIEW', publish: 'PENDING_PUBLISH' })[stage] || ''
      this.missingOnly = q.incompleteOnly != null ? (['1', 'true'].includes(String(q.incompleteOnly)) ? 'MISSING' : '') : ['missing', 'recheck'].includes(stage) ? 'MISSING' : ''
      this.keyword = String(q.keyword || '')
      this.page = Math.max(1, Number.parseInt(q.page, 10) || 1)
      this.appealsPage = Math.max(1, Number.parseInt(q.appealPage, 10) || 1)
      if (stage === 'appeal') this.loadAppeals()
      else if (stage !== 'config') this.load()
      this.syncPanelFromRoute()
    },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      // 导出口径必须与屏幕上的筛选一致：开着「仅看缺项」看到 3 条、导出却拿到全部，
      // 老师会照着导出的表去核对，成绩是要报出去的。
      const params = { keyword: this.keyword, status: this.statusFilter, batchId: this.batchStore.selectedBatchId }
      if (this.missingOnly) params.incompleteOnly = true
      return scoreApi.exportScores(params)
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    async loadConfig() {
      const sequence = ++this.cfgSequence, batchId = this.batchStore.selectedBatchId
      this.cfg = {}; this.cfgLoaded = false; this.cfgError = ''; this.cfgSaveError = ''; this.savingCfg = false
      if (!batchId) { this.cfgLoading = false; this.cfgError = '请先选择批次'; return }
      this.cfgLoading = true
      const res = await scoreApi.getConfig({ batchId })
      if (sequence !== this.cfgSequence || batchId !== this.batchStore.selectedBatchId) return
      this.cfgLoading = false
      if (res.code !== 0) { this.cfgError = res.message || '评分规则读取失败'; return }
      this.cfg = { ...res.data }; this.cfgLoaded = true
    },
    async saveConfig() {
      if (this.savingCfg || !this.canEditConfig) return
      this.cfgSaveError = ''
      if (WEIGHTS.some(w => this.cfg[w.key] == null || this.cfg[w.key] === '' || !Number.isInteger(Number(this.cfg[w.key])) || Number(this.cfg[w.key]) < 0 || Number(this.cfg[w.key]) > 100)) { this.cfgSaveError = '五项权重须为 0–100 的整数'; return }
      if (this.weightSum !== 100) { this.cfgSaveError = `五项权重之和须为 100，当前 ${this.weightSum}`; return }
      if (this.cfg.passLine == null || this.cfg.passLine === '' || !Number.isFinite(Number(this.cfg.passLine)) || this.cfg.passLine < 0 || this.cfg.passLine > 100) { this.cfgSaveError = '及格线须为 0–100 的数字'; return }
      const batchId = this.batchStore.selectedBatchId, cfg = this.cfg
      const body = { batchId, passLine: cfg.passLine, ...Object.fromEntries(WEIGHTS.map(w => [w.key, cfg[w.key]])) }
      this.savingCfg = true
      const res = await scoreApi.saveConfig(body)
      if (cfg !== this.cfg || batchId !== this.batchStore.selectedBatchId) return
      this.savingCfg = false
      if (res.code !== 0) { this.cfgSaveError = res.message || '保存失败，填写内容已保留'; return }
      toast.success('本批次评分规则已保存')
      await this.loadConfig()
    },
    syncListQuery() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, stage: 'overview', keyword: this.keyword, status: this.statusFilter, incompleteOnly: this.missingOnly ? '1' : '', page: String(this.page) })
      if (Object.keys(query).every(key => String(query[key]) === String(this.$route.query[key]))) this.load()
      else this.$router.replace({ query })
    },
    reload() { this.page = 1; this.syncListQuery() },
    onPageChange(p) { this.page = p; this.syncListQuery() },
    onAppealsPageChange({ page }) { this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, appealPage: String(page) }) }) },
    async loadAppeals() {
      const sequence = ++this.appealsSequence, batchId = this.batchStore.selectedBatchId
      this.appeals = []; this.appealsTotal = 0; this.appealsError = ''
      if (!this.canBtn('internship.score.publish')) { this.appealsLoading = false; this.appealsError = '当前账号无成绩申诉办理权限'; return }
      if (!this.batchStore.selectedBatchId) { this.appeals = []; this.appealsLoading = false; return }
      this.appealsLoading = true
      const res = await scoreApi.getAppeals({ batchId, page: this.appealsPage, pageSize: 20 })
      if (sequence !== this.appealsSequence || batchId !== this.batchStore.selectedBatchId) return
      this.appealsLoading = false
      if (res.code !== 0) { this.appealsError = res.message || '成绩申诉加载失败'; return }
      this.appeals = res.data.list || []
      this.appealsTotal = res.data.total || 0
    },
    scoreStatusLabel(status) { return STATUS_MAP[status] || '状态待确认' },
    openAppeal(item) { this.$router.push({ query: this.batchStore.withBatchQuery({ ...this.$route.query, stage: 'appeal', appealId: String(item.id) }) }) },
    closeAppeal() { const query = this.batchStore.withBatchQuery({ ...this.$route.query }); delete query.appealId; this.$router.replace({ query }) },
    openAppealScore(item) { const query = this.batchStore.withBatchQuery({ ...this.$route.query, stage: 'overview', id: String(item.currentScore.id), mode: 'detail', fromAppeal: String(item.id) }); delete query.appealId; this.$router.push({ query }) },
    async load() {
      const sequence = ++this.listSequence, batchId = this.batchStore.selectedBatchId
      this.rows = []; this.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      // 缺项判定放在服务端（五个分项任一为空），COUNT 与分页共用同一条件，
      // 所以「还剩几条」是全批次真数，「下一条缺项」也能跨页。
      if (this.missingOnly) params.incompleteOnly = true
      const res = await scoreApi.getScores(params)
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId) return false
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return false }
      this.rows = res.data.list; this.total = res.data.total
      return true
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    isMissing(v) { return v === null || v === undefined || v === '' },
    canRecalc(row) { return !!row && RECALC_STATUSES.includes(row.status) },
    beforeUnload(event) { if (this.computeDirty || this.panel.submitting || this.cForm.uploading) { event.preventDefault(); event.returnValue = '' } },
    computeSnapshot() { const { uploading: _uploading, ...form } = this.cForm; return JSON.stringify(form) },
    showPanelError(message) { this.panelError = message; this.$nextTick?.(() => this.$el?.querySelector('.wsp [role="alert"]')?.scrollIntoView({ block: 'center' })) },
    resetPanel() { this.detailSequence++; this.panel = emptyPanel(); this.cForm = emptyComputeForm(); this.computeInitial = ''; this.computeVersion = null; this.computeConflict = false; this.actionConflict = false; this.panelError = ''; this.keptReason = ''; this.previewingFile = ''; this.pending = null; this.cd.visible = false; this.cd.submitting = false },
    closePanel() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query }); delete query.id; delete query.mode
      if (query.fromAppeal) { query.stage = 'appeal'; query.appealId = query.fromAppeal; delete query.fromAppeal }
      this.$router.replace({ query })
    },
    navigateWorkspace(id, mode, replace = false) {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, id: id ? String(id) : undefined, mode })
      if (this.activeArea !== 'scores') query.stage = 'overview'
      delete query.appealId
      this.$router[replace ? 'replace' : 'push']({ query })
    },
    syncPanelFromRoute() {
      const id = String(this.$route.query.id || ''), mode = this.$route.query.mode === 'new' ? 'create' : this.$route.query.mode === 'compute' ? 'edit' : 'detail'
      if (this.activeArea !== 'scores' || (!id && mode !== 'create')) { this.resetPanel(); return }
      if (this.panel.visible && String(this.panel.rowId) === id && this.panel.mode === mode) return
      this.resetPanel()
      if (mode === 'create') { this.panel = { ...emptyPanel(), visible: true, mode }; this.computeInitial = this.computeSnapshot() }
      else this.openDetailById(id, mode)
    },
    openCompute(row) {
      if (!this.canBtn('internship.score.manage') || (row && !this.canRecalc(row))) return
      this.navigateWorkspace(row?.id, row ? 'compute' : 'new')
    },
    restoreCompute() {
      const d = this.panel.data
      if (!d || !this.canRecalc(d) || this.panel.loading || this.panel.error || this.panel.submitting) return
      this.cForm = { ...emptyComputeForm(), internshipId: String(d.internId || d.internshipId || ''), manualAdjustments: Object.fromEntries(SCORE_INPUTS.map(s => [s.key, d.manualAdjustments?.[s.key] ?? 0])), adjustmentReason: d.adjustmentReason || '', evidenceFileIds: (d.adjustmentEvidenceFileIds || []).map(String) }
      this.computeVersion = d.version; this.computeInitial = this.computeSnapshot(); this.computeConflict = false; this.panelError = ''
    },
    async submitCompute(goNext) {
      if (!this.canCompute || this.panel.submitting || this.cForm.uploading || this.cd.submitting) return
      this.panelError = ''
      if (!this.cForm.internshipId) { this.showPanelError('请选择当前批次考核中的实习学生'); return }
      if (Object.values(this.cForm.manualAdjustments).some(v => !Number.isInteger(Number(v || 0)) || Number(v) < -100 || Number(v) > 100)) { this.showPanelError('各项增减分须为 -100 至 100 的整数'); return }
      if (this.hasManualAdjustment && this.cForm.adjustmentReason.trim().length < 5) { this.showPanelError('人工调分原因不少于 5 字'); return }
      if (this.hasManualAdjustment && !this.cForm.evidenceFileIds.length) { this.showPanelError('人工调分必须绑定依据文件'); return }
      const workspace = this.panel, form = this.cForm, batchId = this.batchStore.selectedBatchId
      this.panel.submitting = true
      const body = { internshipId: this.cForm.internshipId }
      if (this.hasManualAdjustment) {
        body.manualAdjustments = Object.fromEntries(Object.entries(this.cForm.manualAdjustments).map(([key, value]) => [key, Number(value || 0)]))
        body.adjustmentReason = this.cForm.adjustmentReason.trim()
        body.adjustmentEvidenceFileIds = [...this.cForm.evidenceFileIds]
      }
      if (this.panel.mode === 'edit') {
        const current = { ...this.panel.data, version: this.computeVersion }
        if (!current || current.version === null || current.version === undefined) {
          this.panel.submitting = false
          return toast.error('成绩版本已失效，请刷新后重试')
        }
        body.expectedVersion = current.version
      }
      const res = await scoreApi.compute(body)
      if (workspace !== this.panel || form !== this.cForm || batchId !== this.batchStore.selectedBatchId) return
      this.panel.submitting = false
      if (res.code !== 0) {
        this.panelError = res.message || '核算失败，填写内容已保留'
        if (isConflict(res)) { this.computeConflict = true; if (this.panel.rowId) await this.refreshPanel() }
        return
      }
      this.lastReceipt = { actionLabel: '成绩已核算', objectLabel: this.panelRow?.studentName || '实习成绩',
        id: res.data.id, version: res.data.version, statusLabel: res.data.incomplete ? '缺项待补齐' : '待复核',
        auditText: `来源快照 ${String(res.data.sourceHash || '').slice(0, 12) || '已生成'}`,
        nextStep: res.data.incomplete ? (res.data.incompleteReason || '补齐来源后重算') : '由授权复核人核对并提交待发布' }
      toast.success(res.data.incomplete ? `已核算（缺项：${res.data.incompleteReason}）` : `已核算，总分 ${res.data.total}`)
      const doneId = String(res.data.id)
      this.computeInitial = this.computeSnapshot(); this.computeVersion = res.data.version
      workspace.data = { ...workspace.data, ...res.data, totalScore: res.data.total }
      const loaded = await this.load()
      if (workspace !== this.panel || batchId !== this.batchStore.selectedBatchId) return
      if (goNext) {
        if (!loaded) { this.panelError = '成绩已核算，列表刷新失败；请返回台账重试'; return }
        const next = this.nextMissingRow(doneId)
        if (next) return this.openCompute(next)
        toast.info('本页已无其他可核算的缺项')
      }
      this.navigateWorkspace(doneId, 'detail', true)
    },
    async uploadAdjustmentEvidence(event) {
      if (!this.canCompute || this.panel.submitting || this.cForm.uploading) return
      const file = event.target.files?.[0]
      if (!file) return
      if (file.size > 20 * 1024 * 1024) { event.target.value = ''; return toast.error('单个文件不能超过20MB') }
      const form = this.cForm, workspace = this.panel, batchId = this.batchStore.selectedBatchId
      this.cForm.uploading = true
      const res = await scoreApi.uploadEvidence(file)
      if (form !== this.cForm || workspace !== this.panel || batchId !== this.batchStore.selectedBatchId) return
      this.cForm.uploading = false
      event.target.value = ''
      if (res.code !== 0) { this.panelError = res.message || '调分依据上传失败'; return }
      const id = res.data?.fileId || res.data?.id
      if (id) this.cForm.evidenceFileIds = [...new Set([...this.cForm.evidenceFileIds, String(id)])]
      else this.panelError = '上传未返回文件编号，请重新上传'
    },
    async previewEvidence(id) {
      if (this.previewingFile) return
      const workspace = this.panel; this.previewingFile = String(id)
      try { await fileSdk.preview(String(id)) }
      catch (e) { if (workspace === this.panel) this.panelError = e.message || '依据暂时无法预览' }
      finally { if (workspace === this.panel) this.previewingFile = '' }
    },
    nextMissingRow(afterId) {
      const eligible = (r) => r.incomplete && this.canRecalc(r) && String(r.id) !== String(afterId)
      const idx = this.rows.findIndex((r) => String(r.id) === String(afterId))
      return this.rows.slice(idx + 1).find(eligible) || this.rows.slice(0, Math.max(idx, 0)).find(eligible) || null
    },
    openDetail(r) { this.navigateWorkspace(r.id, 'detail') },
    refreshPanel() { if (this.panel.rowId) return this.openDetailById(this.panel.rowId, this.panel.mode, true) },
    async openDetailById(id, mode = 'detail', preserve = false) {
      if (!preserve) this.panel = { ...emptyPanel(), visible: true, mode, rowId: String(id) }
      const workspace = this.panel, batchId = this.batchStore.selectedBatchId, sequence = ++this.detailSequence
      workspace.loading = true; workspace.error = ''
      if (!batchId) { workspace.loading = false; workspace.error = '请先选择实习批次'; return false }
      const res = await scoreApi.getDetail(id)
      if (workspace !== this.panel || batchId !== this.batchStore.selectedBatchId || sequence !== this.detailSequence) return false
      if (res.code === 0) {
        const sourceBatch = res.data?.batchId || res.data?.sourceManifest?.facts?.internship?.batchId
        let scoped = sourceBatch ? String(sourceBatch) === String(batchId) : this.rows.some(row => String(row.id) === String(id))
        if (!sourceBatch && !scoped) {
          const list = await scoreApi.getScores({ batchId, page: this.page, pageSize: this.pageSize, keyword: this.keyword, status: this.statusFilter, incompleteOnly: !!this.missingOnly })
          if (workspace !== this.panel || batchId !== this.batchStore.selectedBatchId || sequence !== this.detailSequence) return false
          scoped = list.code === 0 && list.data.list.some(row => String(row.id) === String(id))
        }
        if (!scoped || String(res.data.id) !== String(id)) { workspace.loading = false; workspace.data = null; workspace.error = '无法确认该成绩属于当前批次，请从当前批次台账重新定位'; return false }
      }
      this.panel.loading = false
      if (res.code !== 0) { workspace.data = null; workspace.error = res.message || '成绩读取失败'; return false }
      this.panel.data = res.data
      if (mode === 'edit' && !preserve) this.restoreCompute()
      return true
    },
    canAct(row, kind) {
      if (!row || row.version == null || this.panel.loading || this.panel.error || this.panel.submitting || this.computeDirty) return false
      const code = ['publish', 'withdraw'].includes(kind) ? 'internship.score.publish' : 'internship.score.manage'
      const statuses = { review: ['PENDING_REVIEW'], publish: ['PENDING_PUBLISH'], return: ['PENDING_REVIEW', 'PENDING_PUBLISH'], withdraw: ['PUBLISHED'] }
      return this.canBtn(code) && !!statuses[kind]?.includes(row.status) && (!['review', 'publish'].includes(kind) || !row.incomplete)
    },
    acknowledgeAction() { if (this.panel.data && !this.panel.loading && !this.panel.error && !this.cd.submitting) { this.actionConflict = false; this.panelError = ''; this.pending = null; this.cd.visible = false } },
    confirmAct(r, kind) {
      if (!this.canAct(r, kind) || this.cd.submitting || this.actionConflict) return
      this.panelError = ''
      const map = {
        review: { title: '复核成绩', content: `核对「${r.studentName}」的来源事实与成绩快照，并提交待发布？`, danger: false, confirmText: '复核通过', requireReason: false },
        publish: { title: '发布成绩', content: `发布「${r.studentName}」的实习成绩（总分 ${r.totalScore}）？发布后学生可见。`, danger: false, confirmText: '发布', requireReason: false },
        return: { title: '退回重算', content: `退回「${r.studentName}」的成绩到待核算？请写清需补充或修正的内容。`, danger: false, confirmText: '退回', requireReason: true },
        withdraw: { title: '撤回成绩', content: `撤回「${r.studentName}」的已发布成绩，原因将写审计。`, danger: true, confirmText: '撤回', requireReason: true }
      }[kind]
      this.pending = { id: String(r.id), kind, expectedVersion: r.version }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      if (!p || !this.cd.visible || this.cd.submitting || this.actionConflict || !this.canAct(this.panel.data, p.kind) || String(this.panel.data.id) !== p.id) return
      if (['return', 'withdraw'].includes(p.kind) && String(reason || '').trim().length < 5) { this.panelError = '原因至少填写 5 字'; return }
      if (String(this.panel.data.version) !== String(p.expectedVersion)) { this.actionConflict = true; this.panelError = '成绩版本已变化，请重新核对'; return }
      const workspace = this.panel, dialog = this.cd, batchId = this.batchStore.selectedBatchId
      const ver = { expectedVersion: p.expectedVersion }
      this.cd.submitting = true
      let res
      if (p.kind === 'review') res = await scoreApi.review(p.id, ver)
      else if (p.kind === 'publish') res = await scoreApi.publish(p.id, ver)
      else if (p.kind === 'return') res = await scoreApi.returnRecalc(p.id, { reason, ...ver })
      else res = await scoreApi.withdraw(p.id, { reason, ...ver })
      if (workspace !== this.panel || dialog !== this.cd || p !== this.pending || batchId !== this.batchStore.selectedBatchId) return
      this.cd.submitting = false
      if (res.code !== 0) { this.panelError = res.message || '操作失败'; this.keptReason = reason || ''; if (isConflict(res)) { this.actionConflict = true; await this.refreshPanel() }; return }
      this.lastReceipt = {
        actionLabel: ({ review: '成绩已复核', publish: '成绩已发布', return: '成绩已退回', withdraw: '成绩已撤回' })[p.kind],
        objectLabel: workspace.data.studentName || '实习成绩', id: res.data.id,
        version: res.data.version, statusLabel: res.data.statusLabel || res.data.status,
        auditText: '状态变更与审计已提交',
        nextStep: p.kind === 'review' ? '由学校管理员最终发布' : p.kind === 'publish' ? '学生端已可查看并可按版本申诉' : '按页面队列继续处理'
      }
      this.cd.visible = false; toast.success('操作成功，已写审计')
      workspace.data = { ...workspace.data, ...res.data }; this.pending = null; this.keptReason = ''
      await Promise.all([this.load(), this.refreshPanel()])
    }
  }
}
</script>

<style scoped>
.stack { display: flex; flex-direction: column; gap: var(--space-3); }
.queue-tabs { display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid var(--border-base); padding-bottom: 10px; }
.queue-tabs button { min-height: 36px; padding: 6px 14px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--text-secondary); font: inherit; font-size: var(--font-size-sm); cursor: pointer; }
.queue-tabs button:hover { background: var(--bg-subtle); }
.queue-tabs button:focus-visible { outline: 2px solid var(--primary-500, #3b82f6); outline-offset: 2px; }
.queue-tabs button.active { border-color: var(--primary-500, #3b82f6); background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); }
.cfg-section { border: 1px solid var(--border-base); border-radius: var(--radius-lg, 12px); background: var(--card, #fff); padding: var(--space-4); }
.cfg-section .sec-t { margin-top: 0; color: var(--text-primary); }
.rule-values { display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 20px; margin: 24px 0 8px; }
.rule-values dt { color: var(--text-secondary); font-size: var(--font-size-sm); }
.rule-values dd { margin: 8px 0 0; color: var(--text-primary); font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.rule-values small { margin-left: 4px; color: var(--text-tertiary); font-size: 12px; font-weight: 400; }
.cfg { display: flex; align-items: flex-end; gap: var(--space-4); flex-wrap: wrap; min-width: 0; margin: var(--space-4) 0 0; padding: 0; border: 0; }
.cfg__item { display: flex; flex-direction: column; align-items: flex-start; gap: var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); }
.cfg__item :deep(.app-number-input) { width: 116px; }
.local-error { color: var(--danger-600); font-size: var(--font-size-sm); }
.cfg__sum { font-size: var(--font-size-sm); color: var(--success-700); }
.cfg__sum.is-bad { color: var(--danger-600); }
.appeals { border: 1px solid var(--border-base); border-radius: var(--radius-lg, 12px); padding: var(--space-3); background: var(--card, #fff); }
.appeals__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); }
.appeals__head > div { display: flex; flex-direction: column; gap: var(--space-2); }
.appeals__head span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.appeals__list { display: flex; flex-direction: column; gap: var(--space-2); }
.appeal-row { display: flex; gap: var(--space-3); align-items: center; justify-content: space-between; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-subtle); }
.appeal-row__main { min-width: 0; }
.appeal-row__reason, .appeal-row__tip { margin-top: var(--space-1); color: var(--text-secondary); font-size: var(--font-size-xs); }
.appeal-row__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; flex: none; }
.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.status-filter, .missing-filter { display: inline-flex; align-items: center; gap: 8px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.status-filter select { min-height: 36px; padding: 6px 28px 6px 10px; border: 1px solid var(--border-base); border-radius: 6px; color: var(--text-primary); background: var(--card, #fff); font: inherit; }
.status-filter select:focus-visible, .missing-filter input:focus-visible { outline: 2px solid var(--primary-500, #3b82f6); outline-offset: 2px; }
.missing-filter input { width: 16px; height: 16px; accent-color: var(--primary-500, #3b82f6); }
.bar__note { font-size: var(--font-size-xs); color: var(--warning-700, #b45309); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.miss-cell { display: inline-flex; align-items: center; height: 20px; padding: 0 8px; margin-left: 4px; border-radius: 10px; font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); background: var(--danger-bg, #fef2f2); color: var(--danger-600, #dc2626); border: 1px solid var(--danger-bd, #fecaca); white-space: nowrap; }
.miss-cell:first-child { margin-left: 0; }
.is-current { color: var(--pri, #2563eb); font-weight: var(--font-weight-semibold); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.scores { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--space-3); }
.compute-fields { min-width: 0; border: 0; padding: 0; margin: 20px 0 0; }
.score-result { display: flex; align-items: center; gap: 28px; margin: 20px 0; }
.score-result small { color: var(--text-secondary); font-size: 12px; font-weight: 400; }
.score-result strong { display: block; margin-top: 8px; font-size: 32px; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.score-result strong small { margin-left: 6px; }
.score-result p { font-size: 14px; line-height: 1.6; color: var(--text-secondary); }
.score-breakdown { overflow-x: auto; margin: 24px 0 16px; border: 1px solid var(--border-base); border-radius: 8px; }
.score-breakdown table { width: 100%; min-width: 480px; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.score-breakdown caption { padding: 14px; text-align: left; font-weight: 600; }
.score-breakdown th, .score-breakdown td { padding: 12px 14px; text-align: right; border-top: 1px solid var(--border-base); }
.score-breakdown th:first-child { text-align: left; }
.score-breakdown thead { background: var(--bg-subtle); color: var(--text-secondary); }
.score-breakdown tbody th { font-weight: 500; }
.kept-reason { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 1.7; }
.adjustment-evidence { padding: 16px 0; border-top: 1px solid var(--border-base); }
.adjustment-evidence h3 { font-size: 14px; margin: 0 0 8px; }
.evidence-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
.source-pills, .source-readiness { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.source-pills span, .source-readiness span { padding: 3px 7px; border-radius: 999px; background: var(--danger-bg, #fef2f2); color: var(--danger-600, #dc2626); font-size: 12px; }
.source-pills span.ok, .source-readiness span.ok { background: var(--success-50, #ecfdf5); color: var(--success-700, #047857); }
.source-readiness { margin: var(--space-3) 0; padding: var(--space-3); border-radius: 10px; background: var(--bg-subtle); }
.source-readiness strong { margin-right: 4px; font-size: 12px; }
.score { min-width: 0; }
.wsp { border: 1px solid var(--card-b, #e5e7eb); border-radius: var(--radius-lg, 12px); background: var(--card, #fff); padding: var(--space-4); box-shadow: var(--s1); }
.wsp__head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3); }
.wsp__title { font-weight: var(--font-weight-semibold); }
.wsp__close { margin-left: auto; }
.wsp__ops { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
@media (max-width: 900px) { .scores { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 720px) { .scores { grid-template-columns: repeat(2, minmax(0, 1fr)); } .appeal-row { align-items: flex-start; flex-direction: column; } .wsp__ops { flex-wrap: wrap; } }
</style>
