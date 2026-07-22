<template>
  <ModulePageShell
    title="注册工作台"
    subtitle="注册资格核验 · 未注册学生处理 · 暂缓注册审批 · 注册异常处理 · 注册归档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aarw-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aarw-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <AppSectionCard v-if="tab !== 'archive'" class="aarw-batch-bar">
      <div class="aarw-batch-row">
        <label class="aarw-batch-label">批次</label>
        <AppRegistrationBatchPicker v-model="batchId" :options="batchOptions" placeholder="选择注册批次" style="max-width:280px" @change="onBatchChange" />
        <span class="mp-note aarw-batch-hint">{{ batchHint }}</span>
      </div>
    </AppSectionCard>

    <!-- 注册资格核验 -->
    <div v-if="tab === 'eligibility'" class="mp-stack">
      <div class="aarw-toolbar">
        <AppTextInput v-model="elig.keyword" placeholder="按学号 / 姓名检索" clearable @change="loadEligibility" />
        <AppSelect v-model="elig.status" :options="eligStatusOptions" placeholder="全部核验结果" @change="loadEligibility" />
        <AppButton variant="ghost" @click="loadEligibility">查询</AppButton>
      </div>
      <ErrorState v-if="elig.error" :description="elig.error" @retry="loadEligibility" />
      <LoadingState v-else-if="elig.loading" />
      <EmptyState v-else-if="!batchId" title="请先选择批次" description="核验候选名单按批次圈定（入学=待注册在籍生 / 学年=在籍待续生）" />
      <EmptyState v-else-if="!elig.rows.length" title="暂无候选学生" description="该批次下暂无需要核验的学生" />
      <DataTable v-else :columns="eligColumns" :rows="elig.rows" row-key="studentId" :pagination="elig.pagination" @page-change="onEligPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-eligibilityStatus="{ row }">
          <StatusTag :type="eligStatusType(row.eligibilityStatus)" :label="eligStatusLabel(row.eligibilityStatus)" dot />
        </template>
        <template #cell-eligibilityNote="{ row }">{{ row.eligibilityNote || '—' }}</template>
        <template #cell-actions="{ row }">
          <button v-if="row.registrationStatus !== 'REGISTERED' && row.eligibilityStatus !== 'ELIGIBLE'"
                  class="mp-link" @click="askEligible(row)">核验通过</button>
          <button v-if="row.registrationStatus !== 'REGISTERED'" class="mp-link is-danger" @click="openIneligible(row)">标记不合格</button>
        </template>
      </DataTable>
    </div>

    <!-- 未注册学生 -->
    <div v-else-if="tab === 'unregistered'" class="mp-stack">
      <div class="aarw-toolbar">
        <AppButton variant="primary" size="small" :disabled="!batchId || scanning" @click="doScan">
          {{ scanning ? '扫描中…' : '扫描本批次逾期未注册' }}
        </AppButton>
        <AppButton variant="ghost" size="small" @click="openExport">导出名单</AppButton>
      </div>
      <ErrorState v-if="unreg.error" :description="unreg.error" @retry="loadUnregistered" />
      <LoadingState v-else-if="unreg.loading" />
      <EmptyState v-else-if="!unreg.rows.length" title="暂无未注册学生" description="选择批次后可执行「扫描本批次逾期未注册」，或查看全部批次汇总" />
      <DataTable v-else :columns="unregColumns" :rows="unreg.rows" row-key="studentId" :pagination="unreg.pagination" @page-change="onUnregPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-registerType="{ row }">{{ regTypeLabel(row.registerType) }}</template>
        <template #cell-kind="{ row }">
          <StatusTag :type="row.kind === 'UNREGISTERED' ? 'danger' : 'warning'" :label="row.kind === 'UNREGISTERED' ? '未注册' : '逾期待扫描'" dot />
        </template>
      </DataTable>
      <p class="mp-note">
        「未注册」= 学籍主档已判定 UNREGISTERED（经系统扫描/教务处操作转移）；「逾期待扫描」= 批次窗口已截止但学生仍待注册，尚未执行转移。
      </p>
    </div>

    <!-- 暂缓注册 -->
    <div v-else-if="tab === 'deferral'" class="mp-stack">
      <div class="aarw-toolbar">
        <AppSelect v-model="defer.status" :options="deferStatusOptions" placeholder="全部状态" @change="loadDeferrals" />
        <AppButton variant="ghost" size="small" @click="loadDeferrals">查询</AppButton>
        <AppButton variant="primary" size="small" :disabled="!batchId" @click="openDeferralApply">申请暂缓注册</AppButton>
      </div>
      <ErrorState v-if="defer.error" :description="defer.error" @retry="loadDeferrals" />
      <LoadingState v-else-if="defer.loading" />
      <EmptyState v-else-if="!defer.rows.length" title="暂无暂缓注册申请" description="学生材料未齐/特殊原因时可代其提交暂缓注册申请" />
      <DataTable v-else :columns="deferColumns" :rows="defer.rows" row-key="deferralId" :pagination="defer.pagination" @page-change="onDeferPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="deferStatusType(row.status)" :label="deferStatusLabel(row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" @click="askDeferralReview(row, 'APPROVE')">通过</button>
            <button class="mp-link is-danger" @click="askDeferralReview(row, 'REJECT')">驳回</button>
          </template>
          <span v-else class="mp-cell-sub">{{ row.reviewNote || '—' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- 注册异常 -->
    <div v-else-if="tab === 'exception'" class="mp-stack">
      <div class="aarw-toolbar">
        <AppSelect v-model="exc.status" :options="excStatusOptions" placeholder="全部状态" @change="loadExceptions" />
        <AppButton variant="ghost" size="small" @click="loadExceptions">查询</AppButton>
        <AppButton variant="primary" size="small" :disabled="!batchId" @click="openExceptionCreate">标记注册异常</AppButton>
      </div>
      <ErrorState v-if="exc.error" :description="exc.error" @retry="loadExceptions" />
      <LoadingState v-else-if="exc.loading" />
      <EmptyState v-else-if="!exc.rows.length" title="暂无注册异常" description="核验不合格会自动转入本清单；也可直接标记" />
      <DataTable v-else :columns="excColumns" :rows="exc.rows" row-key="exceptionId" :pagination="exc.pagination" @page-change="onExcPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-exceptionType="{ row }">{{ excTypeLabel(row.exceptionType) }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'OPEN' ? 'warning' : 'success'" :label="row.status === 'OPEN' ? '待处理' : '已处理'" dot />
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'OPEN'" class="mp-link" @click="askResolveException(row)">处理</button>
          <span v-else class="mp-cell-sub">{{ row.resolutionNote || '—' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- 注册归档：OPEN→CLOSED→ARCHIVED（关闭/归档动作在「注册批次」列表操作列执行），本页只读查阅+导出 -->
    <div v-else class="mp-stack">
      <ErrorState v-if="archive.error" :description="archive.error" @retry="loadArchive" />
      <LoadingState v-else-if="archive.loading" />
      <EmptyState v-else-if="!archive.rows.length" title="暂无已归档批次" description="批次在「注册批次」列表关闭后再归档，归档后台账只读并可在此导出" />
      <DataTable v-else :columns="archiveColumns" :rows="archive.rows" row-key="batchId" :pagination="archive.pagination" @page-change="onArchivePage">
        <template #cell-registerType="{ row }">{{ regTypeLabel(row.registerType) }}</template>
        <template #cell-completion="{ row }">{{ row.registered === null ? '—' : `${row.registered} / ${row.total}` }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goArchiveDetail(row)">查看名单</button>
          <button class="mp-link" @click="openArchiveExport(row)">导出</button>
        </template>
      </DataTable>
    </div>

    <!-- 标记核验不合格 / 转注册异常 -->
    <AppDrawer :visible="eligDrawer.visible" title="核验不合格" @close="eligDrawer.visible = false">
      <div class="aarw-form">
        <p class="mp-note">学生：{{ eligDrawer.studentName }}</p>
        <AppFormItem label="异常类型" required>
          <AppSelect v-model="eligDrawer.exceptionType" :options="excTypeOptions" :disabled="eligDrawer.saving" />
        </AppFormItem>
        <AppFormItem label="核验意见" required>
          <AppTextarea ref="eligNoteInput" v-model="eligDrawer.note" placeholder="不合格原因（将转入注册异常并通知辅导员）" :disabled="eligDrawer.saving" />
          <AppQuickPhrases scene-key="aa.reg.fail" @pick="onPickEligNote" />
        </AppFormItem>
        <AppInlineAlert v-if="eligDrawer.formError" type="danger" :description="eligDrawer.formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="eligDrawer.saving" @click="eligDrawer.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="eligDrawer.saving" @click="submitIneligible">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 申请暂缓注册 -->
    <AppDrawer :visible="deferDrawer.visible" title="申请暂缓注册" @close="deferDrawer.visible = false">
      <div class="aarw-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="deferDrawer.studentId" :disabled="deferDrawer.saving" />
        </AppFormItem>
        <AppFormItem label="暂缓原因" required>
          <AppTextarea ref="deferReasonInput" v-model="deferDrawer.reason" placeholder="如材料未齐 / 特殊原因说明" :disabled="deferDrawer.saving" />
          <AppQuickPhrases scene-key="aa.reg.defer" @pick="onPickDeferReason" />
        </AppFormItem>
        <AppFormItem label="申请延后至">
          <AppDatePicker v-model="deferDrawer.requestedUntil" placeholder="留空=不限期，由教务处后续处理" :disabled="deferDrawer.saving" />
        </AppFormItem>
        <AppInlineAlert v-if="deferDrawer.formError" type="danger" :description="deferDrawer.formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="deferDrawer.saving" @click="deferDrawer.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="deferDrawer.saving" @click="submitDeferralApply">提交申请</AppButton>
      </template>
    </AppDrawer>

    <!-- 标记注册异常 -->
    <AppDrawer :visible="excDrawer.visible" title="标记注册异常" @close="excDrawer.visible = false">
      <div class="aarw-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="excDrawer.studentId" :disabled="excDrawer.saving" />
        </AppFormItem>
        <AppFormItem label="异常类型" required>
          <AppSelect v-model="excDrawer.exceptionType" :options="excTypeOptions" :disabled="excDrawer.saving" />
        </AppFormItem>
        <AppFormItem label="说明" :required="excDrawer.exceptionType === 'OTHER'">
          <AppTextarea v-model="excDrawer.description" placeholder="异常类型为「其他」时必填" :disabled="excDrawer.saving" />
        </AppFormItem>
        <AppInlineAlert v-if="excDrawer.formError" type="danger" :description="excDrawer.formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="excDrawer.saving" @click="excDrawer.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="excDrawer.saving" @click="submitExceptionCreate">提交</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      @confirm="onConfirm"
    />

    <!-- 导出用途（未注册名单 / 注册归档共用；用途写入审计与文件水印） -->
    <AppConfirmDialog
      v-model:visible="exportDialog.visible" :title="exportDialog.title" type="warning"
      message="导出文件带水印，用途将写入审计留痕。"
      confirm-text="确认导出" require-reason phrase-scene-key="common.exportPurpose"
      reason-label="导出用途（≥5 字）" :submitting="exportDialog.submitting" @confirm="onExportConfirm"
    />

    <!-- 暂缓注册驳回 / 注册异常处理说明：配置方案未给这两个场景词条，只做对话框化不挂快捷用语。
         reason-min-length=1 保持原口径「非空即可」，不擅自收紧为 ≥5 字（原实现只校验 !note.trim()） -->
    <AppConfirmDialog
      v-model:visible="deferRejectDialog.visible" title="驳回暂缓注册申请" type="danger"
      confirm-text="确认驳回" require-reason :reason-min-length="1" reason-label="驳回理由"
      :submitting="deferRejectDialog.submitting" @confirm="onDeferRejectConfirm"
    />
    <AppConfirmDialog
      v-model:visible="resolveDialog.visible" title="处理注册异常" type="primary"
      confirm-text="确认处理" require-reason :reason-min-length="1" reason-label="处理说明"
      :submitting="resolveDialog.submitting" @confirm="onResolveConfirm"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 注册工作台（/admin/academic-affairs/registration/workbench）：
 * 注册资格核验 / 未注册学生 / 暂缓注册 / 注册异常 —— 四叶共用同一批次选择器，Tab 走 ?tab= 深链接。
 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import {
  AppTextInput, AppTextarea, AppSelect, AppFormItem, AppInlineAlert, AppConfirmDialog,
  AppSectionCard, AppStudentPicker, AppDatePicker, AppQuickPhrases, AppRegistrationBatchPicker
} from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const ELIG_STATUS_LABEL = { PENDING: '待核验', ELIGIBLE: '合格', INELIGIBLE: '不合格' }
const EXC_TYPE_LABEL = { IDENTITY_MISMATCH: '身份不符', UNPAID: '未缴费', MATERIAL_MISSING: '材料缺失', OTHER: '其他' }
const DEFER_STATUS_LABEL = { PENDING: '待审', APPROVED: '已通过', REJECTED: '已驳回' }
const REG_TYPE_LABEL = { ENROLL: '入学注册', ANNUAL: '学年注册', SEMESTER: '学期注册' }
const REG_TYPE_SHORT = { ENROLL: '入学', ANNUAL: '学年', SEMESTER: '学期' }

function emptyPage() {
  return { page: 1, pageSize: 20, total: 0 }
}

export default {
  name: 'AaRegistrationWorkbenchView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppTextarea, AppSelect, AppFormItem, AppInlineAlert,
    AppConfirmDialog, AppSectionCard, AppStudentPicker, AppDatePicker, AppQuickPhrases, AppRegistrationBatchPicker
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'eligibility',
      tabs: [
        { key: 'eligibility', label: '注册资格核验' },
        { key: 'unregistered', label: '未注册学生' },
        { key: 'deferral', label: '暂缓注册' },
        { key: 'exception', label: '注册异常' },
        { key: 'archive', label: '注册归档' }
      ],
      batches: [],
      batchId: '',
      scanning: false,
      excTypeOptions: Object.entries(EXC_TYPE_LABEL).map(([value, label]) => ({ label, value })),
      eligStatusOptions: [
        { label: '全部核验结果', value: '' },
        { label: '待核验', value: 'PENDING' },
        { label: '合格', value: 'ELIGIBLE' },
        { label: '不合格', value: 'INELIGIBLE' }
      ],
      deferStatusOptions: [
        { label: '全部状态', value: '' },
        { label: '待审', value: 'PENDING' },
        { label: '已通过', value: 'APPROVED' },
        { label: '已驳回', value: 'REJECTED' }
      ],
      excStatusOptions: [
        { label: '全部状态', value: '' },
        { label: '待处理', value: 'OPEN' },
        { label: '已处理', value: 'RESOLVED' }
      ],
      eligColumns: [
        { key: 'student', title: '学生' },
        { key: 'classId', title: '班级ID' },
        { key: 'eligibilityStatus', title: '核验结果' },
        { key: 'eligibilityNote', title: '核验意见' },
        { key: 'actions', title: '操作', width: '160px' }
      ],
      unregColumns: [
        { key: 'student', title: '学生' },
        { key: 'batchName', title: '批次' },
        { key: 'registerType', title: '类型' },
        { key: 'windowEnd', title: '截止时间' },
        { key: 'kind', title: '状态' }
      ],
      deferColumns: [
        { key: 'student', title: '学生' },
        { key: 'reason', title: '原因' },
        { key: 'requestedUntil', title: '申请延后至' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作/意见' }
      ],
      excColumns: [
        { key: 'student', title: '学生' },
        { key: 'exceptionType', title: '异常类型' },
        { key: 'description', title: '说明' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作/结果' }
      ],
      archiveColumns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'registerType', title: '类型' },
        { key: 'completion', title: '注册完成' },
        { key: 'archivedAt', title: '归档时间' },
        { key: 'actions', title: '操作', width: '140px' }
      ],
      elig: { keyword: '', status: '', rows: [], loading: false, error: '', pagination: emptyPage() },
      unreg: { rows: [], loading: false, error: '', pagination: emptyPage() },
      defer: { status: '', rows: [], loading: false, error: '', pagination: emptyPage() },
      exc: { status: '', rows: [], loading: false, error: '', pagination: emptyPage() },
      archive: { rows: [], loading: false, error: '', pagination: emptyPage() },
      eligDrawer: { visible: false, studentId: '', studentName: '', exceptionType: 'OTHER', note: '', saving: false, formError: '' },
      deferDrawer: { visible: false, studentId: '', reason: '', requestedUntil: '', saving: false, formError: '' },
      excDrawer: { visible: false, studentId: '', exceptionType: 'OTHER', description: '', saving: false, formError: '' },
      confirm: { visible: false, title: '', message: '', type: 'primary' },
      pendingAction: null,
      exportDialog: { visible: false, title: '', submitting: false, action: null },
      deferRejectDialog: { visible: false, deferralId: '', submitting: false },
      resolveDialog: { visible: false, exceptionId: '', submitting: false }
    }
  },
  computed: {
    batchOptions() {
      return this.batches.map((b) => ({
        label: `${b.batchName}（${REG_TYPE_SHORT[b.registerType] || b.registerType}·${this.batchStatusCn(b.status)}）`, value: b.batchId
      }))
    },
    batchHint() {
      if (this.tab === 'eligibility') return '资格核验、暂缓注册、标记异常均需先选择具体批次'
      return '未注册/异常/暂缓列表默认显示全部批次；选择批次可收窄'
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    await this.loadBatches()
    this.loadCurrentTab()
  },
  methods: {
    async onExportConfirm({ reason }) {
      const action = this.exportDialog.action
      this.exportDialog.submitting = true
      const ok = action ? await action(reason) : false
      this.exportDialog.submitting = false
      if (ok) this.exportDialog.visible = false
    },
    async onDeferRejectConfirm({ reason }) {
      this.deferRejectDialog.submitting = true
      const ok = await this.reviewDeferral(this.deferRejectDialog.deferralId, 'REJECT', reason)
      this.deferRejectDialog.submitting = false
      if (ok) this.deferRejectDialog.visible = false
    },
    async onResolveConfirm({ reason }) {
      this.resolveDialog.submitting = true
      const ok = await this.resolveException(this.resolveDialog.exceptionId, reason)
      this.resolveDialog.submitting = false
      if (ok) this.resolveDialog.visible = false
    },
    onPickEligNote(text) {
      const el = this.$refs.eligNoteInput && this.$refs.eligNoteInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.eligDrawer.note, text)
      this.eligDrawer.note = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickDeferReason(text) {
      const el = this.$refs.deferReasonInput && this.$refs.deferReasonInput.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.deferDrawer.reason, text)
      this.deferDrawer.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    batchStatusCn(s) {
      return { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已关闭', ARCHIVED: '已归档' }[s] || s
    },
    regTypeLabel(t) {
      return REG_TYPE_LABEL[t] || t || '—'
    },
    switchTab(key) {
      this.tab = key
      this.$router.replace({ query: { ...this.$route.query, tab: key } }).catch(() => {})
      this.loadCurrentTab()
    },
    loadCurrentTab() {
      if (this.tab === 'eligibility') this.loadEligibility()
      else if (this.tab === 'unregistered') this.loadUnregistered()
      else if (this.tab === 'deferral') this.loadDeferrals()
      else if (this.tab === 'exception') this.loadExceptions()
      else this.loadArchive()
    },
    onBatchChange() {
      this.loadCurrentTab()
    },
    async loadBatches() {
      const res = await academicAffairsApi.getRegistrationBatches({ page: 1, pageSize: 100 })
      const list = res.code === 0 ? (res.data.list || []) : []
      // 已归档批次只读，不进本工作台（资格核验/未注册/暂缓/异常）批次选择器；查阅走「注册归档」Tab。
      this.batches = list.filter((b) => b.status !== 'ARCHIVED')
      if (!this.batchId) {
        const open = this.batches.find((b) => b.status === 'OPEN')
        if (open) this.batchId = open.batchId
      }
    },
    /* ── 资格核验 ── */
    eligStatusLabel(s) { return ELIG_STATUS_LABEL[s] || s },
    eligStatusType(s) { return s === 'ELIGIBLE' ? 'success' : s === 'INELIGIBLE' ? 'danger' : 'default' },
    onEligPage(page) { this.elig.pagination.page = page; this.loadEligibility() },
    async loadEligibility() {
      if (!this.batchId) { this.elig.rows = []; return }
      this.elig.loading = true
      this.elig.error = ''
      const res = await academicAffairsApi.getRegistrationEligibility(this.batchId, {
        status: this.elig.status || undefined, keyword: this.elig.keyword || undefined,
        page: this.elig.pagination.page, pageSize: this.elig.pagination.pageSize
      })
      if (res.code === 0) { this.elig.rows = res.data.list; this.elig.pagination.total = res.data.total } else this.elig.error = res.message
      this.elig.loading = false
    },
    askEligible(row) {
      this.confirm = { visible: true, title: '核验通过', message: `确认「${row.realName}」注册资格核验通过？`, type: 'primary' }
      this.pendingAction = { kind: 'eligible', row }
    },
    openIneligible(row) {
      this.eligDrawer = { visible: true, studentId: row.studentId, studentName: `${row.realName} · ${row.studentNo}`, exceptionType: 'OTHER', note: '', saving: false, formError: '' }
    },
    async submitIneligible() {
      if (!this.eligDrawer.note.trim()) { this.eligDrawer.formError = '核验意见必填'; return }
      this.eligDrawer.saving = true
      this.eligDrawer.formError = ''
      const res = await academicAffairsApi.verifyRegistrationEligibility(this.batchId, this.eligDrawer.studentId, {
        result: 'INELIGIBLE', note: this.eligDrawer.note.trim(), exceptionType: this.eligDrawer.exceptionType
      })
      this.eligDrawer.saving = false
      if (res.code === 0) { toast.success('已标记不合格并转注册异常'); this.eligDrawer.visible = false; this.loadEligibility() } else this.eligDrawer.formError = res.message
    },

    /* ── 未注册学生 ── */
    onUnregPage(page) { this.unreg.pagination.page = page; this.loadUnregistered() },
    async loadUnregistered() {
      this.unreg.loading = true
      this.unreg.error = ''
      const res = await academicAffairsApi.getUnregisteredStudents({
        batchId: this.batchId || undefined, page: this.unreg.pagination.page, pageSize: this.unreg.pagination.pageSize
      })
      if (res.code === 0) { this.unreg.rows = res.data.list; this.unreg.pagination.total = res.data.total } else this.unreg.error = res.message
      this.unreg.loading = false
    },
    async doScan() {
      if (!this.batchId || this.scanning) return
      this.scanning = true
      const res = await academicAffairsApi.scanUnregistered(this.batchId)
      this.scanning = false
      if (res.code === 0) {
        toast.success(`扫描完成：转移 ${res.data.marked} 人，跳过 ${res.data.skipped} 人（含已批准暂缓），通知辅导员 ${res.data.notified} 人`)
        this.loadUnregistered()
      } else toast.error(res.message || '扫描失败')
    },
    openExport() {
      this.exportDialog = {
        visible: true, title: '导出未注册学生名单', submitting: false,
        action: async (purpose) => {
          const res = await academicAffairsApi.exportUnregistered({ batchId: this.batchId || undefined, purpose })
          if (res.code !== 0) { toast.error(res.message || '导出失败'); return false }
          this.downloadBlob(res.data, `未注册学生名单-${Date.now()}.xlsx`)
          toast.success('导出成功')
          return true
        }
      }
    },
    /** 统一 blob 下载（未注册名单 / 注册归档共用，避免每处重复一份 createObjectURL 样板） */
    downloadBlob(blob, filename) {
      const href = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = href
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
    },

    /* ── 暂缓注册 ── */
    deferStatusLabel(s) { return DEFER_STATUS_LABEL[s] || s },
    deferStatusType(s) { return s === 'APPROVED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    onDeferPage(page) { this.defer.pagination.page = page; this.loadDeferrals() },
    async loadDeferrals() {
      this.defer.loading = true
      this.defer.error = ''
      const res = await academicAffairsApi.getRegistrationDeferrals({
        batchId: this.batchId || undefined, status: this.defer.status || undefined,
        page: this.defer.pagination.page, pageSize: this.defer.pagination.pageSize
      })
      if (res.code === 0) { this.defer.rows = res.data.list; this.defer.pagination.total = res.data.total } else this.defer.error = res.message
      this.defer.loading = false
    },
    openDeferralApply() {
      this.deferDrawer = { visible: true, studentId: '', reason: '', requestedUntil: '', saving: false, formError: '' }
    },
    async submitDeferralApply() {
      if (!this.deferDrawer.studentId) { this.deferDrawer.formError = '请选择学生'; return }
      if (!this.deferDrawer.reason.trim()) { this.deferDrawer.formError = '暂缓原因必填'; return }
      this.deferDrawer.saving = true
      this.deferDrawer.formError = ''
      const res = await academicAffairsApi.applyRegistrationDeferral(this.batchId, {
        studentId: this.deferDrawer.studentId, reason: this.deferDrawer.reason.trim(),
        requestedUntil: this.deferDrawer.requestedUntil || undefined
      })
      this.deferDrawer.saving = false
      if (res.code === 0) { toast.success('已提交暂缓注册申请'); this.deferDrawer.visible = false; this.loadDeferrals() } else this.deferDrawer.formError = res.message
    },
    askDeferralReview(row, action) {
      if (action === 'REJECT') {
        this.deferRejectDialog = { visible: true, deferralId: row.deferralId, submitting: false }
        return
      }
      this.confirm = { visible: true, title: '通过暂缓注册申请', message: `确认「${row.realName}」暂缓注册申请通过？`, type: 'primary' }
      this.pendingAction = { kind: 'deferralApprove', row }
    },
    /** @returns {boolean} 是否成功（调用方据此决定关不关弹窗，失败时保留用户已填内容） */
    async reviewDeferral(deferralId, action, note) {
      const res = await academicAffairsApi.reviewRegistrationDeferral(deferralId, { action, note })
      if (res.code !== 0) { toast.error(res.message || '处理失败'); return false }
      toast.success('已处理'); this.loadDeferrals(); return true
    },

    /* ── 注册异常 ── */
    excTypeLabel(t) { return EXC_TYPE_LABEL[t] || t },
    onExcPage(page) { this.exc.pagination.page = page; this.loadExceptions() },
    async loadExceptions() {
      this.exc.loading = true
      this.exc.error = ''
      const res = await academicAffairsApi.getRegistrationExceptions({
        batchId: this.batchId || undefined, status: this.exc.status || undefined,
        page: this.exc.pagination.page, pageSize: this.exc.pagination.pageSize
      })
      if (res.code === 0) { this.exc.rows = res.data.list; this.exc.pagination.total = res.data.total } else this.exc.error = res.message
      this.exc.loading = false
    },
    openExceptionCreate() {
      this.excDrawer = { visible: true, studentId: '', exceptionType: 'OTHER', description: '', saving: false, formError: '' }
    },
    async submitExceptionCreate() {
      if (!this.excDrawer.studentId) { this.excDrawer.formError = '请选择学生'; return }
      if (this.excDrawer.exceptionType === 'OTHER' && !this.excDrawer.description.trim()) {
        this.excDrawer.formError = '异常类型为「其他」时说明必填'; return
      }
      this.excDrawer.saving = true
      this.excDrawer.formError = ''
      const res = await academicAffairsApi.createRegistrationException(this.batchId, {
        studentId: this.excDrawer.studentId, exceptionType: this.excDrawer.exceptionType,
        description: this.excDrawer.description.trim() || undefined
      })
      this.excDrawer.saving = false
      if (res.code === 0) { toast.success('已标记注册异常并通知辅导员'); this.excDrawer.visible = false; this.loadExceptions() } else this.excDrawer.formError = res.message
    },
    askResolveException(row) {
      this.resolveDialog = { visible: true, exceptionId: row.exceptionId, submitting: false }
    },
    /** @returns {boolean} 是否成功（同 reviewDeferral，失败不关弹窗） */
    async resolveException(exceptionId, note) {
      const res = await academicAffairsApi.resolveRegistrationException(exceptionId, note)
      if (res.code !== 0) { toast.error(res.message || '处理失败'); return false }
      toast.success('已处理'); this.loadExceptions(); return true
    },

    /* ── 注册归档：批次在「注册批次」列表关闭→归档后进入本清单，只读+导出 ── */
    onArchivePage(page) { this.archive.pagination.page = page; this.loadArchive() },
    async loadArchive() {
      this.archive.loading = true
      this.archive.error = ''
      const res = await academicAffairsApi.getArchivedRegistrationBatches({
        page: this.archive.pagination.page, pageSize: this.archive.pagination.pageSize
      })
      if (res.code !== 0) { this.archive.error = res.message; this.archive.loading = false; return }
      const list = res.data.list || []
      this.archive.pagination.total = res.data.total
      const details = await Promise.all(list.map((b) => academicAffairsApi.getRegistrationArchiveDetail(b.batchId)))
      this.archive.rows = list.map((b, i) => {
        const d = details[i]
        const ok = d.code === 0
        return { ...b, registered: ok ? d.data.stats.registered : null, total: ok ? d.data.stats.total : null,
                 archivedAt: (ok && d.data.archivedAt) || '' }
      })
      this.archive.loading = false
    },
    goArchiveDetail(row) {
      this.$router.push(`/admin/academic-affairs/registration/${row.batchId}`)
    },
    openArchiveExport(row) {
      this.exportDialog = {
        visible: true, title: `导出注册归档 · ${row.batchName}`, submitting: false,
        action: async (purpose) => {
          const res = await academicAffairsApi.exportRegistrationArchive(row.batchId, purpose)
          if (res.code !== 0) { toast.error(res.message || '导出失败'); return false }
          this.downloadBlob(res.data, `注册归档-${row.batchName}-${Date.now()}.xlsx`)
          toast.success('导出成功')
          return true
        }
      }
    },

    /* ── 通用确认弹窗回调 ── */
    async onConfirm() {
      const a = this.pendingAction
      this.confirm.visible = false
      this.pendingAction = null
      if (!a) return
      if (a.kind === 'eligible') {
        const res = await academicAffairsApi.verifyRegistrationEligibility(this.batchId, a.row.studentId, { result: 'ELIGIBLE' })
        if (res.code === 0) { toast.success('已核验通过'); this.loadEligibility() } else toast.error(res.message || '核验失败')
      } else if (a.kind === 'deferralApprove') {
        await this.reviewDeferral(a.row.deferralId, 'APPROVE', '')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aarw-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aarw-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aarw-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aarw-batch-bar { margin-bottom: 12px; }
.aarw-batch-row { display: flex; align-items: center; gap: 12px; }
.aarw-batch-label { font-size: 13px; color: var(--text-secondary, #64748b); }
.aarw-batch-hint { margin: 0; }
.aarw-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.aarw-form { display: flex; flex-direction: column; gap: 12px; }
</style>
