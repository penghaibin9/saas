<template>
  <ModulePageShell title="综合成绩" subtitle="实习成绩 · 五项权重核算 · 整批核对工作区 · 缺项不可发布"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="primary" @click="openCompute()">＋ 核算成绩</AppPermissionButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <nav class="queue-tabs" aria-label="成绩工作队列">
        <button type="button" :class="{ active: missingOnly }" @click="setQueue('missing')">缺项</button>
        <button type="button" :class="{ active: statusFilter === 'PENDING_CALC' }" @click="setQueue('calculate')">待核算</button>
        <button type="button" :class="{ active: statusFilter === 'PENDING_REVIEW' }" @click="setQueue('review')">待复核</button>
        <button type="button" :class="{ active: statusFilter === 'PENDING_PUBLISH' }" @click="setQueue('publish')">待发布</button>
        <button type="button" @click="setQueue('appeals')">申诉 {{ appeals.length || '' }}</button>
      </nav>

      <div class="appeals">
        <div class="appeals__head">
          <div><strong>成绩申诉</strong><span>与正式成绩状态机联动，受理后原成绩自动撤回</span></div>
          <AppButton variant="ghost" size="sm" :disabled="appealsLoading" @click="loadAppeals">刷新</AppButton>
        </div>
        <div v-if="appealsLoading" class="state">正在加载申诉…</div>
        <div v-else-if="!appeals.length" class="state">当前批次暂无成绩申诉</div>
        <div v-else class="appeals__list">
          <div v-for="item in appeals" :key="item.id" class="appeal-row">
            <div class="appeal-row__main">
              <div><strong>{{ item.studentName }}</strong> · {{ item.studentNo || '无学号' }} · <AppStatusTag :status="item.status">{{ item.statusLabel }}</AppStatusTag></div>
              <div class="appeal-row__reason">申诉理由：{{ item.reason }}</div>
              <div class="appeal-row__reason">冻结成绩：{{ item.scoreSnapshot?.totalScore ?? '—' }} · 当前成绩状态：{{ item.currentScore?.status || '—' }}</div>
            </div>
            <div v-if="item.status === 'PENDING'" class="appeal-row__ops">
              <AppPermissionButton code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="secondary" size="sm" @click="decideAppeal(item, true)">受理并撤回原成绩</AppPermissionButton>
              <AppPermissionButton code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="ghost" size="sm" :danger="true" @click="decideAppeal(item, false)">驳回</AppPermissionButton>
            </div>
            <div v-else-if="item.status === 'APPROVED_RECALCULATING'" class="appeal-row__tip">请在下方找到该学生的「已撤回」成绩并重新核算、复核、发布。</div>
          </div>
        </div>
      </div>

      <!-- 权重配置（真实 getConfig / saveConfig） -->
      <div class="cfg">
        <span class="cfg__t">五项权重配置</span>
        <div v-for="w in weightDefs" :key="w.key" class="cfg__item">
          <span>{{ w.label }}</span><AppNumberInput v-model="cfg[w.key]" :min="0" :max="100" size="sm" />
        </div>
        <div class="cfg__item"><span>及格线</span><AppNumberInput v-model="cfg.passLine" :min="0" :max="100" size="sm" /></div>
        <span class="cfg__sum" :class="{ 'is-bad': weightSum !== 100 }">合计 {{ weightSum }}/100</span>
        <AppPermissionButton code="internship.score.config.manage" :allowed="canBtn('internship.score.config.manage')" variant="secondary" size="sm" :loading="savingCfg" @click="saveConfig">保存配置</AppPermissionButton>
      </div>

      <!-- 快捷筛选行：状态、仅看缺项都是后端过滤，跨页有效 -->
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
        <AppQuickFilterChips v-model="missingOnly" :options="missingOptions" allow-clear @change="reload" />
        <span v-if="missingOnly" class="bar__note">「仅看缺项」由服务端按全批次筛选，跨页有效，共 {{ total }} 条待补齐</span>
      </div>

      <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
      <template v-else>
        <DataTable :columns="columns" :rows="rows" row-key="id" :loading="loading"
          :pagination="pagination" row-clickable @row-click="openDetail" @page-change="onPageChange">
          <template #cell-studentName="{ row }">
            <span :class="{ 'is-current': row.id === panel.rowId }">{{ row.studentName }}</span>
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
              <AppPermissionButton v-if="row.status === 'PENDING_REVIEW'" code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="secondary" size="sm" :disabled="row.incomplete" :native-title="row.incomplete ? (row.incompleteReason || '成绩缺项，补齐后方可复核') : ''" @click="confirmAct(row, 'review')">复核</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'PENDING_PUBLISH'" code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="secondary" size="sm" @click="confirmAct(row, 'publish')">发布</AppPermissionButton>
              <AppPermissionButton v-if="['PENDING_REVIEW','PENDING_PUBLISH'].includes(row.status)" code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="ghost" size="sm" @click="confirmAct(row, 'return')">退回</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'PUBLISHED'" code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="ghost" size="sm" :danger="true" @click="confirmAct(row, 'withdraw')">撤回</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <div v-if="missingOnly && !loading && !rows.length && !error" class="state">该批次已没有缺项记录</div>
      </template>

      <!-- 选中行工作区：详情核对 / 行内核算（替代原居中弹窗） -->
      <div v-if="panel.visible" class="wsp">
        <div class="wsp__head">
          <span class="wsp__title">{{ panelTitle }}</span>
          <AppStatusTag v-if="panelRow" :status="panelRow.status">{{ panelRow.statusLabel }}</AppStatusTag>
          <span v-if="panelRow && panelRow.incomplete" class="miss-cell">{{ panelRow.incompleteReason || '缺项' }}</span>
          <AppButton class="wsp__close" variant="ghost" size="sm" @click="closePanel">收起</AppButton>
        </div>

        <template v-if="panel.mode === 'detail'">
          <div v-if="panel.loading" class="state">加载中…</div>
          <template v-else-if="panel.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div class="source-readiness">
              <strong>来源闭环</strong>
              <span :class="{ ok: panel.data.sourceReadiness?.enterpriseEvaluation }">企业评价</span>
              <span :class="{ ok: panel.data.sourceReadiness?.studentSelfEvaluation }">学生自评/企业岗位评价</span>
              <span :class="{ ok: panel.data.sourceReadiness?.advisorEvaluation }">导师评价</span>
            </div>
            <div class="sec-t">核算/发布留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            <div v-if="panelRow && canRecalc(panelRow)" class="wsp__ops">
              <AppPermissionButton code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="secondary" size="sm" @click="openCompute(panelRow)">转入核算</AppPermissionButton>
            </div>
          </template>
        </template>

        <template v-else>
          <AppFormItem v-if="panel.mode === 'create'" label="实习学生" required>
            <AppInternshipStudentPicker
              v-model="cForm.internshipId"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <div class="scores">
            <AppFormItem v-for="s in scoreInputs" :key="s.key" :label="s.label" class="score">
              <AppNumberInput v-model="cForm.manualAdjustments[s.key]" :min="-100" :max="100" />
            </AppFormItem>
          </div>
          <p class="hint">五项建议分全部由打卡、周报、月报、当前安置企业评价、自评/导师评价、指导与巡访事实生成；这里只允许填写增减分，不能提交裸分。</p>
          <template v-if="hasManualAdjustment">
            <AppFormItem label="调分原因" required>
              <AppTextarea v-model="cForm.adjustmentReason" :rows="2" placeholder="不少于5字，说明调整依据" />
            </AppFormItem>
            <AppFormItem label="调分依据" required>
              <input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" :disabled="cForm.uploading" @change="uploadAdjustmentEvidence" />
              <span class="hint">{{ cForm.evidenceFileIds.length ? `已绑定 ${cForm.evidenceFileIds.length} 份依据` : '人工调分必须上传已扫描依据文件' }}</span>
            </AppFormItem>
          </template>
          <div class="wsp__ops">
            <AppButton variant="ghost" @click="closePanel">取消</AppButton>
            <AppButton variant="primary" :loading="panel.submitting" @click="submitCompute(false)">核算</AppButton>
            <AppButton v-if="panel.mode === 'edit' && hasNextMissing" variant="secondary" :loading="panel.submitting" @click="submitCompute(true)">核算并跳下一缺项</AppButton>
          </div>
        </template>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppNumberInput, AppFormItem, AppInternshipStudentPicker,
  AppTextarea } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { scoreApi } from '@/modules/internship/api/score.api'
import { canCode } from '@/modules/internship/composables/permission'
import { restoreWorkContext, captureWorkContext } from '@/modules/internship/composables/workContext'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const WEIGHTS = [
  { key: 'checkinWeight', label: '打卡' }, { key: 'weeklyWeight', label: '周报' },
  { key: 'monthlyWeight', label: '月报' }, { key: 'enterpriseWeight', label: '企业' }, { key: 'schoolWeight', label: '学校' }
]
const SCORE_INPUTS = [
  { key: 'checkin', label: '打卡增减' }, { key: 'weekly', label: '周报增减' },
  { key: 'monthly', label: '月报总结增减' }, { key: 'enterprise', label: '企业评价增减' }, { key: 'school', label: '学校评价增减' }
]
const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
  { key: 'checkinScore', title: '打卡' }, { key: 'weeklyScore', title: '周报' }, { key: 'monthlyScore', title: '月报' },
  { key: 'enterpriseScore', title: '企业评价' }, { key: 'schoolScore', title: '学校评价' }, { key: 'sources', title: '来源闭环' },
  { key: 'total', title: '总分' }, { key: 'pass', title: '及格' }, { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '300px' }
]
const STATUS_MAP = { PENDING_CALC: '待核算', PENDING_REVIEW: '待复核', PENDING_PUBLISH: '待发布', PUBLISHED: '已发布', WITHDRAWN: '已撤回', ARCHIVED: '已归档' }
// U8：只有 stage 在 URL 上，关键词/状态/仅看缺项/页码刷新即丢
const WORK_FIELDS = ['keyword', 'statusFilter', 'missingOnly', 'page']

const RECALC_STATUSES = ['PENDING_REVIEW', 'PENDING_CALC', 'WITHDRAWN']
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'statusLabel', label: '状态' },
  { key: 'totalScore', label: '总分' }, { key: 'passLine', label: '及格线' },
  { key: 'checkinScore', label: '打卡分' }, { key: 'weeklyScore', label: '周报分' },
  { key: 'monthlyScore', label: '月报分' }, { key: 'enterpriseScore', label: '企业分' },
  { key: 'schoolScore', label: '学校分' }, { key: 'incompleteReason', label: '缺项' }
]

export default {
  name: 'ScoreView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, ModuleSummaryStrip, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppNumberInput, AppFormItem, AppInternshipStudentPicker,
    AppTextarea, ActionReceipt },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      appeals: [], appealsLoading: false,
      keyword: '', statusFilter: '', missingOnly: '', columns: COLUMNS, weightDefs: WEIGHTS, scoreInputs: SCORE_INPUTS,
      statusOptions: Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label })),
      missingOptions: [{ value: 'MISSING', label: '仅看缺项' }],
      cfg: { checkinWeight: 20, weeklyWeight: 20, monthlyWeight: 10, enterpriseWeight: 30, schoolWeight: 20, passLine: 60 },
      savingCfg: false,
      cForm: { internshipId: '', manualAdjustments: { checkin: 0, weekly: 0, monthly: 0, enterprise: 0, school: 0 }, adjustmentReason: '', evidenceFileIds: [], uploading: false },
      // 选中行工作区：mode = detail（核对）/ edit（行内核算）/ create（新核算）
      panel: { visible: false, mode: 'detail', rowId: '', loading: false, data: null, submitting: false },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    weightSum() { return WEIGHTS.reduce((a, w) => a + (Number(this.cfg[w.key]) || 0), 0) },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },

    summaryMetrics() {
      if (this.loading || this.error) return []
      const cur = this.statusOptions.find((o) => o.value === this.statusFilter)
      if (this.missingOnly) {
        // 开了「仅看缺项」时 total 就是服务端按全批次数出来的缺项数，不再是本页估算
        return [
          { label: '缺项记录 · 全批次', value: this.total, tone: this.total ? 'warn' : 'good' }
        ]
      }
      const missOnPage = this.rows.filter((r) => r.incomplete).length
      return [
        { label: '成绩记录 · ' + (cur ? cur.label : '全部'), value: this.total },
        { label: '本页缺项', value: missOnPage, tone: missOnPage ? 'warn' : 'good' }
      ]
    },
    panelRow() { return this.rows.find((r) => r.id === this.panel.rowId) || null },
    panelTitle() {
      if (this.panel.mode === 'create') return '核算成绩（选择学生）'
      const name = (this.panel.data && this.panel.data.studentName) || (this.panelRow && this.panelRow.studentName) || ''
      return (this.panel.mode === 'edit' ? '行内核算 · ' : '核对详情 · ') + name
    },
    hasNextMissing() {
      return this.rows.some((r) => r.incomplete && this.canRecalc(r) && r.id !== this.panel.rowId)
    },
    hasManualAdjustment() {
      return Object.values(this.cForm.manualAdjustments || {}).some((value) => Number(value || 0) !== 0)
    },
    detailItems() { const d = this.panel.data || {}; return DETAIL.map((f) => ({ label: f.label, value: d[f.key] })) },
    auditRecords() {
      return (this.panel.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.comment || (t.detail.missing || []).join('、')), at: t.occurredAt
      }))
    }
  },
  created() {
    this.applyStageFromRoute()
    // 带 ?stage= 的深链（待办卡片/菜单）说明用户要的就是那一屏，不能被上次筛选改写
    restoreWorkContext(this, WORK_FIELDS, { skipWhenQuery: ['stage'] })
    this.loadConfig()
    this.load()
    this.loadAppeals()
  },
  watch: {
    '$route.query.stage'() { this.applyStageFromRoute(); this.reload() },
    'batchStore.selectedBatchId'() { this.page = 1; this.closePanel(); this.load(); this.loadAppeals() }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    setQueue(stage) {
      if (stage === 'appeals') {
        document.querySelector('.appeals')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        return
      }
      this.missingOnly = stage === 'missing' ? 'MISSING' : ''
      this.statusFilter = ({ calculate: 'PENDING_CALC', review: 'PENDING_REVIEW', publish: 'PENDING_PUBLISH' })[stage] || ''
      this.reload()
    },
    applyStageFromRoute() {
      const stage = String(this.$route.query.stage || '').toLowerCase()
      // 状态机：PENDING_CALC → PENDING_REVIEW → PENDING_PUBLISH → PUBLISHED → WITHDRAWN。
      // 单独成绩归档被后端禁用，最终冻结统一由实习总档案完成。
      if (stage === 'review') { this.statusFilter = 'PENDING_REVIEW'; this.missingOnly = '' }
      else if (stage === 'publish') { this.statusFilter = 'PENDING_PUBLISH'; this.missingOnly = '' }
      else if (stage === 'recheck') { this.statusFilter = ''; this.missingOnly = 'MISSING' }
      else if (stage === 'overview') { this.statusFilter = ''; this.missingOnly = '' }
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
    async loadConfig() { const res = await scoreApi.getConfig(); if (res.code === 0) this.cfg = { ...this.cfg, ...res.data } },
    async saveConfig() {
      if (this.weightSum !== 100) return toast.error(`五项权重之和须为 100，当前 ${this.weightSum}`)
      this.savingCfg = true
      const res = await scoreApi.saveConfig(this.cfg)
      this.savingCfg = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      toast.success('权重配置已保存')
    },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async loadAppeals() {
      if (!this.batchStore.selectedBatchId) { this.appeals = []; this.appealsLoading = false; return }
      this.appealsLoading = true
      const res = await scoreApi.getAppeals({ batchId: this.batchStore.selectedBatchId, page: 1, pageSize: 100 })
      this.appealsLoading = false
      if (res.code !== 0) { this.appeals = []; return toast.error(res.message || '成绩申诉加载失败') }
      this.appeals = res.data.list || []
    },
    async decideAppeal(item, approve) {
      const promptText = approve ? '请输入受理意见（不少于5字）' : '请输入驳回原因（不少于5字）'
      const reason = (window.prompt(promptText) || '').trim()
      if (reason.length < 5) return toast.error('处理意见不少于 5 字')
      const fn = approve ? scoreApi.approveAppeal : scoreApi.rejectAppeal
      const res = await fn(item.id, { reason, expectedVersion: item.version })
      if (res.code !== 0) return toast.error(res.message || '申诉处理失败')
      this.lastReceipt = {
        actionLabel: approve ? '申诉已受理并撤回原成绩' : '申诉已驳回',
        objectLabel: item.studentName || '成绩申诉', id: res.data.id,
        version: res.data.version,
        statusLabel: approve ? '待重新核算' : '已驳回',
        auditText: `冻结成绩 ${res.data.scoreId || item.scoreId || '—'} / v${res.data.scoreVersion ?? item.scoreVersion ?? '—'}`,
        nextStep: approve ? '按已撤回队列重新核算、独立复核并发布' : '原正式成绩保持不变'
      }
      toast.success(res.data?.message || (approve ? '申诉已受理，原成绩已撤回' : '申诉已驳回'))
      await this.loadAppeals()
      await this.load()
    },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      captureWorkContext(this, WORK_FIELDS)
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      // 缺项判定放在服务端（五个分项任一为空），COUNT 与分页共用同一条件，
      // 所以「还剩几条」是全批次真数，「下一条缺项」也能跨页。
      if (this.missingOnly) params.incompleteOnly = true
      const res = await scoreApi.getScores(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    isMissing(v) { return v === null || v === undefined || v === '' },
    canRecalc(row) { return RECALC_STATUSES.includes(row.status) },
    closePanel() { this.panel = { visible: false, mode: 'detail', rowId: '', loading: false, data: null, submitting: false } },
    openCompute(row) {
      this.cForm = { internshipId: '', manualAdjustments: { checkin: 0, weekly: 0, monthly: 0, enterprise: 0, school: 0 }, adjustmentReason: '', evidenceFileIds: [], uploading: false }
      if (row && row.internId) {
        // 行内重算：学生锁定，带出当前调分；系统建议分不允许客户端覆盖。
        this.cForm.internshipId = row.internId
        for (const s of SCORE_INPUTS) this.cForm.manualAdjustments[s.key] = Number(row.manualAdjustments?.[s.key] || 0)
        this.panel = { visible: true, mode: 'edit', rowId: row.id, loading: false, data: null, submitting: false }
      } else {
        this.panel = { visible: true, mode: 'create', rowId: '', loading: false, data: null, submitting: false }
      }
    },
    async submitCompute(goNext) {
      if (!this.cForm.internshipId) return toast.error('请选择实习学生')
      if (this.hasManualAdjustment && this.cForm.adjustmentReason.trim().length < 5) return toast.error('人工调分原因不少于5字')
      if (this.hasManualAdjustment && !this.cForm.evidenceFileIds.length) return toast.error('人工调分必须绑定依据文件')
      this.panel.submitting = true
      const body = { internshipId: this.cForm.internshipId }
      if (this.hasManualAdjustment) {
        body.manualAdjustments = Object.fromEntries(Object.entries(this.cForm.manualAdjustments).map(([key, value]) => [key, Number(value || 0)]))
        body.adjustmentReason = this.cForm.adjustmentReason.trim()
        body.adjustmentEvidenceFileIds = [...this.cForm.evidenceFileIds]
      }
      if (this.panel.mode === 'edit') {
        const current = this.panelRow
        if (!current || current.version === null || current.version === undefined) {
          this.panel.submitting = false
          return toast.error('成绩版本已失效，请刷新后重试')
        }
        body.expectedVersion = current.version
      }
      const res = await scoreApi.compute(body)
      this.panel.submitting = false
      if (res.code !== 0) return toast.error(res.message || '核算失败')
      this.lastReceipt = { actionLabel: '成绩已核算', objectLabel: this.panelRow?.studentName || '实习成绩',
        id: res.data.id, version: res.data.version, statusLabel: res.data.incomplete ? '缺项待补齐' : '待复核',
        auditText: `来源快照 ${String(res.data.sourceHash || '').slice(0, 12) || '已生成'}`,
        nextStep: res.data.incomplete ? (res.data.incompleteReason || '补齐来源后重算') : '由授权复核人核对并提交待发布' }
      toast.success(res.data.incomplete ? `已核算（缺项：${res.data.incompleteReason}）` : `已核算，总分 ${res.data.total}`)
      const doneId = this.panel.mode === 'edit' ? this.panel.rowId : res.data.id
      await this.load()
      if (goNext) {
        const next = this.nextMissingRow(doneId)
        if (next) return this.openCompute(next)
        toast.info('本页已无其他可核算的缺项')
        this.closePanel()
      } else if (doneId) {
        this.openDetailById(doneId)
      } else {
        this.closePanel()
      }
    },
    async uploadAdjustmentEvidence(event) {
      const file = event.target.files?.[0]
      if (!file) return
      if (file.size > 20 * 1024 * 1024) { event.target.value = ''; return toast.error('单个文件不能超过20MB') }
      this.cForm.uploading = true
      const res = await scoreApi.uploadEvidence(file)
      this.cForm.uploading = false
      event.target.value = ''
      if (res.code !== 0) return toast.error(res.message || '调分依据上传失败')
      const id = res.data?.fileId || res.data?.id
      if (id) this.cForm.evidenceFileIds = [...new Set([...this.cForm.evidenceFileIds, String(id)])]
    },
    nextMissingRow(afterId) {
      const eligible = (r) => r.incomplete && this.canRecalc(r) && r.id !== afterId
      const idx = this.rows.findIndex((r) => r.id === afterId)
      return this.rows.slice(idx + 1).find(eligible) || this.rows.slice(0, Math.max(idx, 0)).find(eligible) || null
    },
    openDetail(r) { this.openDetailById(r.id) },
    async openDetailById(id) {
      this.panel = { visible: true, mode: 'detail', rowId: id, loading: true, data: null, submitting: false }
      const res = await scoreApi.getDetail(id)
      if (!this.panel.visible || this.panel.rowId !== id || this.panel.mode !== 'detail') return
      this.panel.loading = false
      if (res.code !== 0) { toast.error(res.message || '加载失败'); this.closePanel(); return }
      this.panel.data = res.data
    },
    confirmAct(r, kind) {
      const map = {
        review: { title: '复核成绩', content: `核对「${r.studentName}」的来源事实与成绩快照，并提交待发布？`, danger: false, confirmText: '复核通过', requireReason: false },
        publish: { title: '发布成绩', content: `发布「${r.studentName}」的实习成绩（总分 ${r.totalScore}）？发布后学生可见。`, danger: false, confirmText: '发布', requireReason: false },
        return: { title: '退回重算', content: `退回「${r.studentName}」的成绩到待核算？`, danger: false, confirmText: '退回', requireReason: false },
        withdraw: { title: '撤回成绩', content: `撤回「${r.studentName}」的已发布成绩，原因将写审计。`, danger: true, confirmText: '撤回', requireReason: true }
      }[kind]
      this.pending = { id: r.id, kind, expectedVersion: r.version }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      const ver = { expectedVersion: p.expectedVersion }
      this.cd.submitting = true
      let res
      if (p.kind === 'review') res = await scoreApi.review(p.id, ver)
      else if (p.kind === 'publish') res = await scoreApi.publish(p.id, ver)
      else if (p.kind === 'return') res = await scoreApi.returnRecalc(p.id, { reason, ...ver })
      else res = await scoreApi.withdraw(p.id, { reason, ...ver })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.lastReceipt = {
        actionLabel: ({ review: '成绩已复核', publish: '成绩已发布', return: '成绩已退回', withdraw: '成绩已撤回' })[p.kind],
        objectLabel: this.rows.find((r) => r.id === p.id)?.studentName || '实习成绩', id: res.data.id,
        version: res.data.version, statusLabel: res.data.statusLabel || res.data.status,
        auditText: '状态变更与审计已提交',
        nextStep: p.kind === 'review' ? '由学校管理员最终发布' : p.kind === 'publish' ? '学生端已可查看并可按版本申诉' : '按页面队列继续处理'
      }
      this.cd.visible = false; toast.success('操作成功，已写审计')
      await this.load()
      await this.loadAppeals()
      // 若工作区正在核对该行，动作后刷新留痕
      if (this.panel.visible && this.panel.mode === 'detail' && this.panel.rowId === p.id) this.openDetailById(p.id)
    }
  }
}
</script>

<style scoped>
.stack { display: flex; flex-direction: column; gap: var(--space-3); }
.queue-tabs { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.queue-tabs button { min-height: 42px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--card, #fff); color: var(--text-secondary); font-weight: 650; }
.queue-tabs button.active { border-color: var(--primary-500, #3b82f6); background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); }
.cfg { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-base); }
.cfg__t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); }
.cfg__item { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); }
.cfg__item :deep(.app-number-input) { width: 64px; }
.cfg__sum { font-size: var(--font-size-sm); color: var(--success-700); }
.cfg__sum.is-bad { color: var(--danger-600); }
.appeals { border: 1px solid var(--border-base); border-radius: var(--radius-lg, 12px); padding: var(--space-3); background: var(--card, #fff); }
.appeals__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); }
.appeals__head > div { display: flex; align-items: baseline; gap: var(--space-2); }
.appeals__head span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.appeals__list { display: flex; flex-direction: column; gap: var(--space-2); }
.appeal-row { display: flex; gap: var(--space-3); align-items: center; justify-content: space-between; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-subtle); }
.appeal-row__main { min-width: 0; }
.appeal-row__reason, .appeal-row__tip { margin-top: var(--space-1); color: var(--text-secondary); font-size: var(--font-size-xs); }
.appeal-row__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; flex: none; }
.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.bar__note { font-size: var(--font-size-xs); color: var(--warning-700, #b45309); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.miss-cell { display: inline-flex; align-items: center; height: 20px; padding: 0 8px; margin-left: 4px; border-radius: 10px; font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); background: var(--danger-bg, #fef2f2); color: var(--danger-600, #dc2626); border: 1px solid var(--danger-bd, #fecaca); white-space: nowrap; }
.miss-cell:first-child { margin-left: 0; }
.is-current { color: var(--pri, #2563eb); font-weight: var(--font-weight-semibold); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.source-pills, .source-readiness { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.source-pills span, .source-readiness span { padding: 3px 7px; border-radius: 999px; background: var(--danger-bg, #fef2f2); color: var(--danger-600, #dc2626); font-size: 10px; }
.source-pills span.ok, .source-readiness span.ok { background: var(--success-50, #ecfdf5); color: var(--success-700, #047857); }
.source-readiness { margin: var(--space-3) 0; padding: var(--space-3); border-radius: 10px; background: var(--bg-subtle); }
.source-readiness strong { margin-right: 4px; font-size: 12px; }
.score { width: calc(20% - var(--space-2)); min-width: 92px; }
.wsp { border: 1px solid var(--card-b, #e5e7eb); border-radius: var(--radius-lg, 12px); background: var(--card, #fff); padding: var(--space-4); box-shadow: var(--s1); }
.wsp__head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3); }
.wsp__title { font-weight: var(--font-weight-semibold); }
.wsp__close { margin-left: auto; }
.wsp__ops { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
@media (max-width: 720px) { .queue-tabs { grid-template-columns: 1fr 1fr; } }
</style>
