<template>
  <AppPageShell
    title="处分送达与申诉"
    subtitle="已生效处分的送达登记与申诉复核；变更处分必须明确新的处分类型，所有写操作携带当前版本。"
    role-name="学工处 / 学院"
    data-scope-name="学院本院 / 学工处全校"
    watermark-purpose="处分送达与申诉复核"
  >
    <AppGlobalState
      :state="pageState"
      loading-text="正在加载处分送达与申诉工作台..."
      @retry="loadAll"
      @back="$router.push('/admin/student-affairs/discipline')"
    >
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前处理重点</span>
          <h2 class="sa-summary-strip__title">
            {{ pendingAppealCount === '—' ? '正在核对处分送达与申诉待办' : `待复核申诉 ${pendingAppealCount} 件，本页待送达 ${pageUndelivered} 件` }}
          </h2>
          <p class="sa-summary-strip__text">
            先完成处分决定送达，再受理学生申诉。复核时必须核对原处分、学生理由和证据；选择“变更处分”后会真实更新处分及有效投影。
          </p>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="处分送达与申诉流程">
        <div class="sa-workflow-step" data-step="1"><strong>处分已生效</strong><br>确认当前处分类型与决定内容</div>
        <div class="sa-workflow-step" data-step="2"><strong>登记送达</strong><br>记录送达方式、时间和操作人</div>
        <div class="sa-workflow-step" data-step="3"><strong>学生申诉</strong><br>完整陈述事实、理由与诉求</div>
        <div class="sa-workflow-step" data-step="4"><strong>复核结论</strong><br>维持、真实变更或撤销并通知学生</div>
      </div>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard title="已生效处分" :value="casePagination.total" accent="primary" />
        <AppMetricCard title="本页待送达" :value="pageUndelivered" accent="warning" />
        <AppMetricCard title="待复核申诉" :value="pendingAppealCount" accent="warning" />
      </div>

      <AppSectionCard title="已生效处分 · 送达与申诉入口">
        <p class="ap-section-hint">先核对学生、处分类型和送达状态。未送达记录优先完成正式送达；允许申诉的记录可直接进入申诉流程。</p>
        <p v-if="caseError" class="ap-error">{{ caseError }} <button type="button" @click="loadCases">重试</button></p>
        <DataTable
          v-else-if="effectiveCases.length || casePagination.total > 0"
          :columns="caseColumns"
          :rows="effectiveCases"
          row-key="caseId"
          :pagination="casePagination"
          @page-change="onCasePageChange"
        >
          <template #cell-student="{ row }">
            <span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span>
            <div class="mp-cell-sub">{{ row.studentNo || '' }}</div>
          </template>
          <template #cell-discType="{ row }"><strong>{{ discLabel(row.discType) }}</strong></template>
          <template #cell-delivered="{ row }">
            <span :class="row.deliveredAt ? 'ap-delivered' : 'ap-undelivered'">
              {{ row.deliveredAt ? (deliveryLabel(row.deliveryMethod) + ' · ' + row.deliveredAt.slice(0, 10)) : '未送达' }}
            </span>
          </template>
          <template #cell-actions="{ row }">
            <div class="ap-ops">
              <AppPermissionButton
                v-if="canDeliver(row)"
                :allowed="canBtn('studentAffairs.discipline.deliver')"
                code="studentAffairs.discipline.deliver"
                size="sm"
                :loading="acting === row.caseId"
                :disabled="!hasVersion(row)"
                @click="deliver(row)"
              >登记送达</AppPermissionButton>
              <AppPermissionButton
                v-if="canAppeal(row)"
                :allowed="canBtn('studentAffairs.discipline.appeal.create')"
                code="studentAffairs.discipline.appeal.create"
                size="sm"
                variant="secondary"
                :loading="acting === row.caseId"
                @click="appeal(row)"
              >发起申诉</AppPermissionButton>
              <span v-if="!canDeliver(row) && !canAppeal(row)" class="ap-dash">无需处理</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前数据范围内暂无已生效处分。处分生效后，送达与申诉入口会在这里出现。</p>
      </AppSectionCard>

      <AppSectionCard title="申诉复核">
        <p class="ap-section-hint">优先处理“待复核”。复核意见将保留审计并同步结果通知；长理由和复核意见可在表格内完整换行查看。</p>
        <div class="ap-filters sa-filter-bar">
          <button
            v-for="filter in appealFilters"
            :key="filter.key"
            type="button"
            class="ap-chip"
            :class="{ 'is-on': appealStatus === filter.key }"
            @click="setAppealStatus(filter.key)"
          >{{ filter.label }}</button>
        </div>
        <p v-if="appealError" class="ap-error">{{ appealError }} <button type="button" @click="loadAppeals">重试</button></p>
        <DataTable
          v-else-if="appeals.length || appealPagination.total > 0"
          :columns="appealColumns"
          :rows="appeals"
          row-key="appealId"
          :pagination="appealPagination"
          @page-change="onAppealPageChange"
        >
          <template #cell-student="{ row }">
            <span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span>
            <div class="mp-cell-sub">{{ row.studentNo || '' }}</div>
          </template>
          <template #cell-reason="{ row }"><span class="ap-reason sa-cell-wrap">{{ row.reason }}</span></template>
          <template #cell-status="{ row }">
            <StatusTag :type="appealType(row.status)" :label="row.statusLabel || row.status" dot />
          </template>
          <template #cell-opinion="{ row }"><span class="ap-opinion sa-cell-wrap">{{ row.reviewOpinion || '—' }}</span></template>
          <template #cell-actions="{ row }">
            <AppPermissionButton
              v-if="canReview(row)"
              :allowed="canBtn('studentAffairs.discipline.appeal.review')"
              code="studentAffairs.discipline.appeal.review"
              size="sm"
              :loading="acting === row.appealId"
              :disabled="!hasVersion(row)"
              @click="review(row)"
            >复核</AppPermissionButton>
            <span v-else class="ap-dash">已处理</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前筛选下暂无申诉。可切换状态查看已维持、已变更或已撤销记录。</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="delDlg.visible"
      title="登记处分送达"
      type="primary"
      message="登记后将形成正式送达记录。请核对送达方式，系统会保留操作人、时间和版本。"
      confirm-text="确认登记送达"
      :submitting="acting === delDlg.caseId"
      @confirm="submitDeliver"
    >
      <AppFormItem label="送达方式" required>
        <AppSelect v-model="delDlg.method" :options="DELIVERY_OPTIONS" />
      </AppFormItem>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="apDlg.visible"
      title="提交处分申诉"
      type="warning"
      confirm-text="提交申诉"
      require-reason
      :reason-min-length="5"
      reason-label="申诉理由（5-1000字）"
      message="申诉将进入正式复核流程。一案仅允许提交一次，请确认理由完整、事实明确。"
      :submitting="acting === apDlg.caseId"
      @confirm="submitAppeal"
    />

    <AppConfirmDialog
      v-model:visible="revDlg.visible"
      title="复核处分申诉"
      type="primary"
      confirm-text="提交复核结论"
      require-reason
      :reason-min-length="5"
      reason-label="复核意见（5-1000字）"
      phrase-scene-key="common.reviewOpinion"
      message="复核结论会同步更新原处分、处分投影、学生成长时间线和结果通知。"
      :submitting="acting === revDlg.appealId"
      @confirm="submitReview"
    >
      <AppFormItem label="复核结论" required>
        <AppSelect v-model="revDlg.result" :options="RESULT_OPTIONS" />
      </AppFormItem>
      <AppFormItem v-if="revDlg.result === 'REVISED'" label="变更后的处分类型" required>
        <AppSelect v-model="revDlg.revisedDiscType" :options="DISC_OPTIONS" />
      </AppFormItem>
      <p v-if="revDlg.result === 'REVISED'" class="ap-hint">
        “变更处分”不是只改申诉状态；提交后会真实更新原处分及其有效投影。
      </p>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell,
  AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { disciplineIntegrityApi } from '@/modules/studentAffairs/api/disciplineIntegrity.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const DISC = {
  WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过',
  PROBATION: '留校察看', EXPEL: '开除学籍'
}
const DELIVERY = { DIRECT: '直接送达', MAIL: '邮寄', PUBLIC: '公告', LEAVE: '留置' }
const RESULT = { UPHELD: '维持原处分', REVISED: '变更处分', REVOKED: '撤销处分' }
const DELIVERY_OPTIONS = Object.entries(DELIVERY).map(([value, label]) => ({ value, label }))
const RESULT_OPTIONS = Object.entries(RESULT).map(([value, label]) => ({ value, label }))
const DISC_OPTIONS = Object.entries(DISC).map(([value, label]) => ({ value, label }))
const APPEAL_FILTERS = [
  { key: '', label: '全部' }, { key: 'SUBMITTED', label: '待复核' },
  { key: 'UPHELD', label: '已维持' }, { key: 'REVISED', label: '已变更' },
  { key: 'REVOKED', label: '已撤销' }
]
const CASE_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'discType', title: '处分类型' },
  { key: 'delivered', title: '送达' }, { key: 'actions', title: '操作', align: 'right', width: '220px' }
]
const APPEAL_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'reason', title: '申诉理由' },
  { key: 'status', title: '状态' }, { key: 'opinion', title: '复核意见' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]

export default {
  name: 'DisciplineAppealView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell,
    AppPermissionButton, AppSectionCard, AppSelect, StatusTag: AppStatusTag, DataTable
  },
  data() {
    return {
      caseColumns: CASE_COLUMNS,
      appealColumns: APPEAL_COLUMNS,
      loading: true,
      acting: '',
      effectiveCases: [],
      appeals: [],
      caseError: '',
      appealError: '',
      pendingAppealCount: '—',
      appealStatus: '',
      appealFilters: APPEAL_FILTERS,
      casePagination: { page: 1, pageSize: 50, total: 0 },
      appealPagination: { page: 1, pageSize: 50, total: 0 },
      delDlg: { visible: false, caseId: '', method: 'DIRECT', version: null },
      apDlg: { visible: false, caseId: '' },
      revDlg: { visible: false, appealId: '', version: null, result: 'UPHELD', revisedDiscType: '' }
    }
  },
  computed: {
    DELIVERY_OPTIONS: () => DELIVERY_OPTIONS,
    RESULT_OPTIONS: () => RESULT_OPTIONS,
    DISC_OPTIONS: () => DISC_OPTIONS,
    pageState() { return this.loading ? 'loading' : 'ready' },
    pageUndelivered() { return this.effectiveCases.filter((row) => !row.deliveredAt).length }
  },
  mounted() { this.loadAll() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row?.version !== undefined && row?.version !== null && row?.version !== '' },
    allows(row, action, fallback) {
      return Array.isArray(row?.allowedActions) ? row.allowedActions.includes(action) : fallback
    },
    canDeliver(row) { return !row.deliveredAt && this.allows(row, 'DELIVER', row.status === 'EFFECTIVE') },
    canAppeal(row) { return this.allows(row, 'APPEAL', row.status === 'EFFECTIVE') },
    canReview(row) { return this.allows(row, 'REVIEW', ['SUBMITTED', 'REVIEWING'].includes(row.status)) },
    async loadAll() {
      this.loading = true
      await Promise.all([this.loadCases(), this.loadAppeals(), this.loadPendingCount()])
      this.loading = false
    },
    async loadCases() {
      this.caseError = ''
      const response = await studentAffairsApi.getDisciplineCases({
        status: 'EFFECTIVE', page: this.casePagination.page, pageSize: this.casePagination.pageSize
      })
      if (response.code !== 0 || !response.data) {
        this.effectiveCases = []
        this.casePagination.total = 0
        this.caseError = response.message || '已生效处分加载失败'
        return
      }
      this.effectiveCases = response.data.items || []
      this.casePagination.total = response.data.total != null ? response.data.total : this.effectiveCases.length
    },
    async loadAppeals() {
      this.appealError = ''
      const response = await studentAffairsApi.getDisciplineAppeals({
        status: this.appealStatus,
        page: this.appealPagination.page,
        pageSize: this.appealPagination.pageSize
      })
      if (response.code !== 0 || !response.data) {
        this.appeals = []
        this.appealPagination.total = 0
        this.appealError = response.message || '处分申诉加载失败'
        return
      }
      this.appeals = response.data.items || []
      this.appealPagination.total = response.data.total != null ? response.data.total : this.appeals.length
    },
    async loadPendingCount() {
      const response = await studentAffairsApi.getDisciplineAppeals({ status: 'SUBMITTED', page: 1, pageSize: 1 })
      this.pendingAppealCount = response.code === 0 && response.data
        ? Number(response.data.total != null ? response.data.total : (response.data.items || []).length)
        : '—'
    },
    setAppealStatus(key) {
      if (this.appealStatus === key) return
      this.appealStatus = key
      this.appealPagination.page = 1
      this.loadAppeals()
    },
    onCasePageChange(page) { this.casePagination.page = page; this.loadCases() },
    onAppealPageChange(page) { this.appealPagination.page = page; this.loadAppeals() },
    deliver(row) {
      if (!this.canDeliver(row) || !this.hasVersion(row)) return
      this.delDlg = { visible: true, caseId: row.caseId, method: 'DIRECT', version: row.version }
    },
    async submitDeliver() {
      const dialog = this.delDlg
      this.acting = dialog.caseId
      const response = await disciplineIntegrityApi.deliverCase(dialog.caseId, {
        method: dialog.method, version: dialog.version
      })
      this.acting = ''
      if (response.code === 0) {
        dialog.visible = false
        toast.success('处分送达已登记')
        await this.loadCases()
      } else {
        toast.error(response.message || '送达失败')
        if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadCases()
      }
    },
    appeal(row) { if (this.canAppeal(row)) this.apDlg = { visible: true, caseId: row.caseId } },
    async submitAppeal({ reason }) {
      const text = (reason || '').trim()
      if (text.length < 5 || text.length > 1000) { toast.error('申诉理由需5-1000字'); return }
      const dialog = this.apDlg
      this.acting = dialog.caseId
      const response = await studentAffairsApi.submitDisciplineAppeal(dialog.caseId, text)
      this.acting = ''
      if (response.code === 0) {
        dialog.visible = false
        toast.success('申诉已提交')
        await Promise.all([this.loadAppeals(), this.loadPendingCount()])
      } else toast.error(response.message || '申诉失败')
    },
    review(row) {
      if (!this.canReview(row) || !this.hasVersion(row)) return
      this.revDlg = {
        visible: true, appealId: row.appealId, version: row.version,
        result: 'UPHELD', revisedDiscType: ''
      }
    },
    async submitReview({ reason }) {
      const dialog = this.revDlg
      const opinion = (reason || '').trim()
      if (opinion.length < 5 || opinion.length > 1000) { toast.error('复核意见需5-1000字'); return }
      if (dialog.result === 'REVISED' && !dialog.revisedDiscType) {
        toast.error('变更处分必须选择新的处分类型')
        return
      }
      this.acting = dialog.appealId
      const response = await disciplineIntegrityApi.reviewAppeal(dialog.appealId, {
        result: dialog.result,
        opinion,
        version: dialog.version,
        revisedDiscType: dialog.revisedDiscType
      })
      this.acting = ''
      if (response.code === 0) {
        dialog.visible = false
        toast.success(dialog.result === 'REVISED' ? '处分已真实变更' : '申诉已复核')
        await Promise.all([this.loadCases(), this.loadAppeals(), this.loadPendingCount()])
      } else {
        toast.error(response.message || '复核失败')
        if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadAppeals()
      }
    },
    discLabel(type) { return DISC[type] || type },
    deliveryLabel(method) { return DELIVERY[method] || method },
    appealType(status) {
      return ({
        SUBMITTED: 'warning', REVIEWING: 'processing', UPHELD: 'default',
        REVISED: 'success', REVOKED: 'success', WITHDRAWN: 'default'
      })[status] || 'default'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.ap-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.ap-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ap-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 5px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.ap-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.ap-error { margin: 0; padding: var(--space-3); color: var(--danger-700); background: var(--danger-50); border: 1px solid var(--danger-100, #fee2e2); border-radius: var(--radius-md); }
.ap-error button { margin-left: var(--space-2); border: 0; background: transparent; color: inherit; font-weight: 600; cursor: pointer; }
.ap-reason, .ap-opinion { color: var(--text-secondary); font-size: var(--font-size-sm); }
.ap-ops { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.ap-dash { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.ap-hint { margin: var(--space-2) 0 0; color: var(--warning-700); font-size: var(--font-size-sm); line-height: 1.6; }
.ap-delivered { color: var(--success-700, #15803d); font-weight: 600; }
.ap-undelivered { color: var(--warning-700, #b45309); font-weight: 600; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
