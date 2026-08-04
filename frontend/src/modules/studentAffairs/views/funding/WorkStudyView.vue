<template>
  <AppPageShell
    title="勤工助学"
    subtitle="岗位发布 → 学生申请 → 录用 → 上岗 → 月度考核 → 补贴台账。容量与累计金额由后端行锁保护。"
    role-name="资助老师 / 学工处"
    data-scope-name="学工数据范围"
    watermark-purpose="勤工助学管理"
  >
    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载勤工助学台账..."
      @retry="loadAll"
      @back="$router.push('/admin/student-affairs/funding')"
    >
      <div class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">勤工助学工作区</span>
          <h3 class="sa-summary-strip__title">优先处理待审核申请和在岗学生月度考核</h3>
          <p class="sa-summary-strip__text">岗位发布、录用、上岗和补贴登记保持在同一台账中。操作列只展示当前状态允许的动作。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" @click="postDlg.visible = true">新建岗位</AppPermissionButton>
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" variant="secondary" @click="applyDlg.visible = true">代录申请</AppPermissionButton>
        </div>
      </div>

      <div class="sa-workflow-strip" aria-label="勤工助学流程">
        <div class="sa-workflow-step" data-step="1">发布岗位并明确需求人数</div>
        <div class="sa-workflow-step" data-step="2">审核申请并确认录用</div>
        <div class="sa-workflow-step" data-step="3">确认上岗并按月登记考核</div>
        <div class="sa-workflow-step" data-step="4">补贴进入正式累计台账</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard title="启用岗位" :value="enabledPosts" accent="primary" />
          <AppMetricCard title="待审核申请" :value="statusCount('APPLIED')" accent="warning" />
          <AppMetricCard title="在岗人数" :value="statusCount('ONBOARD')" accent="success" />
        </div>
      </div>

      <AppInlineAlert v-if="postError" type="warning" :description="postError" />

      <AppSectionCard title="上岗记录与月度考核">
        <p class="ws-section-hint">待审核记录先完成录用或拒绝；已录用记录确认上岗后，才可登记月度考核和补贴。</p>
        <DataTable v-if="records.length" :columns="recordColumns" :rows="records" row-key="recordId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span><div class="mp-cell-sub">{{ row.studentNo || '' }}</div></template>
          <template #cell-post="{ row }">{{ postName(row.postId) }}</template>
          <template #cell-salary="{ row }">{{ money(row.salary) }}</template>
          <template #cell-subsidy="{ row }">{{ money(row.subsidyTotal) }}</template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <div class="ws-ops">
              <AppPermissionButton v-if="allows(row, 'APPROVE')" :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" :disabled="!hasVersion(row)" :loading="acting === row.recordId" @click="openAction(row, 'APPROVE')">录用</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'REJECT')" :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger :disabled="!hasVersion(row)" @click="openAction(row, 'REJECT')">拒绝</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'ONBOARD')" :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" :disabled="!hasVersion(row)" :loading="acting === row.recordId" @click="openAction(row, 'ONBOARD')">确认上岗</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'ONBOARD'" :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click="openMonthly(row)">月度考核</AppPermissionButton>
              <AppPermissionButton v-if="allows(row, 'TERMINATE')" :allowed="canBtn('studentAffairs.funding.workstudy.manage')" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger :disabled="!hasVersion(row)" @click="openAction(row, 'TERMINATE')">终止</AppPermissionButton>
              <span v-if="!rowActions(row).length && row.status !== 'ONBOARD'" class="ws-muted">—</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围暂无勤工助学记录。可先新建岗位，再为已收齐材料的学生代录申请。</p>
        <AppPagination v-if="pagination.total > pagination.pageSize" v-model:page="pagination.page" v-model:pageSize="pagination.pageSize" :total="pagination.total" @change="loadRecords" />
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog v-model:visible="postDlg.visible" title="新建勤工助学岗位" type="primary" message="岗位启用后可接收学生申请，需求人数会在录用时执行并发行锁校验。" confirm-text="创建岗位" :submitting="acting === 'post'" @confirm="submitPost">
      <AppFormItem label="岗位名称" required><AppTextInput v-model="postDlg.postName" :maxlength="200" placeholder="如：图书馆整理助理" /></AppFormItem>
      <AppFormItem label="需求人数" required><AppNumberInput v-model="postDlg.headcount" :min="1" :max="10000" :step="1" /></AppFormItem>
      <AppFormItem label="薪酬（元）"><AppNumberInput v-model="postDlg.salary" :min="0" :max="999999999999.99" :precision="2" /></AppFormItem>
      <AppInlineAlert v-if="postDlg.error" type="danger" :description="postDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog v-model:visible="applyDlg.visible" title="代录勤工助学申请" type="primary" message="代录仅用于学生线下材料已收齐的场景，提交后仍进入正式审核。" confirm-text="提交申请" :submitting="acting === 'apply'" @confirm="submitApply">
      <AppFormItem label="岗位" required><AppSelect v-model="applyDlg.postId" :options="postOptions" /></AppFormItem>
      <AppFormItem label="学生" required><AppStudentPicker v-model="applyDlg.studentId" /></AppFormItem>
      <AppInlineAlert v-if="applyDlg.error" type="danger" :description="applyDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog v-model:visible="actionDlg.visible" :title="actionTitle" :type="actionDlg.action === 'TERMINATE' || actionDlg.action === 'REJECT' ? 'danger' : 'primary'" :message="actionMessage" :confirm-text="actionConfirmText" :require-reason="['REJECT', 'TERMINATE'].includes(actionDlg.action)" :reason-min-length="5" reason-label="处理原因（5-500字）" :submitting="acting === actionDlg.recordId" @confirm="submitAction" />

    <AppConfirmDialog v-model:visible="monthlyDlg.visible" title="登记月度考核" type="primary" message="同一记录同一月份只能登记一次，补贴金额会累加到正式台账。" confirm-text="保存考核" :submitting="acting === monthlyDlg.recordId" @confirm="submitMonthly">
      <AppFormItem label="考核月" required><AppTextInput v-model="monthlyDlg.monthCode" placeholder="YYYY-MM" :maxlength="7" /></AppFormItem>
      <AppFormItem label="工时" required><AppNumberInput v-model="monthlyDlg.workHours" :min="0" :max="9999.99" :precision="2" /></AppFormItem>
      <AppFormItem label="考核等级" required><AppSelect v-model="monthlyDlg.rating" :options="RATING_OPTIONS" /></AppFormItem>
      <AppFormItem label="补贴金额" required><AppNumberInput v-model="monthlyDlg.subsidyAmount" :min="0" :max="999999999999.99" :precision="2" :disabled="monthlyDlg.rating === 'FAIL'" /></AppFormItem>
      <AppInlineAlert v-if="monthlyDlg.error" type="danger" :description="monthlyDlg.error" />
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
  AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag,
  AppStudentPicker, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const RECORD_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'post', title: '岗位' }, { key: 'salary', title: '薪酬' },
  { key: 'subsidy', title: '累计补贴' }, { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '320px' }
]
const RATING_OPTIONS = [{ value: 'GOOD', label: '优秀' }, { value: 'PASS', label: '合格' }, { value: 'FAIL', label: '不合格' }]

export default {
  name: 'WorkStudyView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
    AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect,
    StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      recordColumns: RECORD_COLUMNS,
      loading: true, acting: '', errorMessage: '', postError: '', posts: [], records: [], statusCounts: null,
      pagination: { page: 1, pageSize: 50, total: 0 },
      postDlg: { visible: false, postName: '', headcount: 1, salary: null, error: '' },
      applyDlg: { visible: false, postId: '', studentId: '', error: '' },
      actionDlg: { visible: false, recordId: '', version: null, action: '' },
      monthlyDlg: { visible: false, recordId: '', monthCode: '', workHours: null, rating: 'PASS', subsidyAmount: null, error: '' }
    }
  },
  computed: {
    RATING_OPTIONS: () => RATING_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    enabledPosts() { return this.posts.filter((post) => post.status === 'ENABLED').length },
    postOptions() { return this.posts.filter((post) => post.status === 'ENABLED').map((post) => ({ value: post.postId, label: post.postName })) },
    actionTitle() { return ({ APPROVE: '确认录用', REJECT: '拒绝申请', ONBOARD: '确认上岗', TERMINATE: '终止勤工助学' })[this.actionDlg.action] || '处理勤工助学' },
    actionConfirmText() { return ({ APPROVE: '确认录用', REJECT: '确认拒绝', ONBOARD: '确认上岗', TERMINATE: '确认终止' })[this.actionDlg.action] || '确认' },
    actionMessage() { return ({ APPROVE: '录用时会校验岗位剩余人数；达到上限将拒绝。', ONBOARD: '确认后该学生进入在岗状态，可登记月度考核。', REJECT: '拒绝后本次申请终止。', TERMINATE: '终止后不可继续登记月度考核，原因会写入审计。' })[this.actionDlg.action] || '' }
  },
  mounted() { this.loadAll() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row?.version !== undefined && row?.version !== null && row?.version !== '' },
    rowActions(row) { return Array.isArray(row?.allowedActions) ? row.allowedActions : [] },
    allows(row, action) { return this.rowActions(row).includes(action) },
    statusCount(key) { return this.statusCounts === null ? '—' : Number(this.statusCounts[key] || 0) },
    postName(id) { return this.posts.find((post) => String(post.postId) === String(id))?.postName || `岗位#${id}` },
    money(value) { return value == null || value === '' ? '—' : (typeof value === 'number' ? `¥${value}` : value) },
    statusType(status) { return ({ APPLIED: 'warning', APPROVED: 'processing', REJECTED: 'default', ONBOARD: 'success', TERMINATED: 'danger' })[status] || 'default' },
    async loadAll() { this.loading = true; await Promise.all([this.loadPosts(), this.loadRecords()]); this.loading = false },
    async loadPosts() {
      this.postError = ''
      const response = await studentAffairsApi.getWorkStudyPosts()
      if (response.code === 0 && response.data) this.posts = response.data.items || []
      else { this.posts = []; this.postError = response.message || '岗位加载失败，暂不能新建申请' }
    },
    async loadRecords() {
      this.errorMessage = ''
      const response = await studentAffairsApi.getWorkStudyRecords({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (response.code !== 0 || !response.data) {
        this.records = []; this.pagination.total = 0; this.statusCounts = null
        this.errorMessage = response.message || '勤工助学记录加载失败'
        return
      }
      this.records = response.data.items || []
      this.pagination.total = response.data.total != null ? response.data.total : this.records.length
      this.statusCounts = response.data.statusCounts || null
    },
    async submitPost() {
      const dialog = this.postDlg
      const name = dialog.postName.trim()
      if (name.length < 2 || name.length > 200) { dialog.error = '岗位名称需2-200字'; return }
      if (!Number.isInteger(Number(dialog.headcount)) || Number(dialog.headcount) < 1 || Number(dialog.headcount) > 10000) { dialog.error = '需求人数应为1-10000整数'; return }
      dialog.error = ''; this.acting = 'post'
      const response = await studentAffairsApi.createWorkStudyPost({ postName: name, headcount: Number(dialog.headcount), salary: dialog.salary != null ? String(dialog.salary) : undefined })
      this.acting = ''
      if (response.code === 0) { dialog.visible = false; Object.assign(dialog, { postName: '', headcount: 1, salary: null, error: '' }); toast.success('岗位已创建'); await this.loadPosts() }
      else dialog.error = response.message || '创建失败'
    },
    async submitApply() {
      const dialog = this.applyDlg
      if (!dialog.postId || !dialog.studentId) { dialog.error = '岗位和学生必填'; return }
      dialog.error = ''; this.acting = 'apply'
      const response = await studentAffairsApi.applyWorkStudy(dialog.postId, Number(dialog.studentId))
      this.acting = ''
      if (response.code === 0) { dialog.visible = false; Object.assign(dialog, { postId: '', studentId: '', error: '' }); toast.success('申请已提交'); await this.loadRecords() }
      else dialog.error = response.message || '提交失败'
    },
    openAction(row, action) { if (this.allows(row, action) && this.hasVersion(row)) this.actionDlg = { visible: true, recordId: row.recordId, version: row.version, action } },
    async submitAction({ reason }) {
      const dialog = this.actionDlg
      const text = (reason || '').trim()
      if (['REJECT', 'TERMINATE'].includes(dialog.action) && (text.length < 5 || text.length > 500)) { toast.error('处理原因需5-500字'); return }
      this.acting = dialog.recordId
      const response = await studentAffairsApi.actWorkStudy(dialog.recordId, dialog.action, text, dialog.version)
      this.acting = ''
      if (response.code === 0) { dialog.visible = false; toast.success('已处理'); await this.loadRecords() }
      else { toast.error(response.message || '操作失败'); if (response.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.loadRecords() }
    },
    openMonthly(row) { this.monthlyDlg = { visible: true, recordId: row.recordId, monthCode: '', workHours: null, rating: 'PASS', subsidyAmount: null, error: '' } },
    async submitMonthly() {
      const dialog = this.monthlyDlg
      if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(dialog.monthCode.trim())) { dialog.error = '考核月格式应为YYYY-MM'; return }
      if (dialog.workHours == null || Number(dialog.workHours) < 0 || Number(dialog.workHours) > 9999.99) { dialog.error = '工时应为0-9999.99'; return }
      if (dialog.rating !== 'FAIL' && (dialog.subsidyAmount == null || Number(dialog.subsidyAmount) < 0)) { dialog.error = '请填写有效补贴金额'; return }
      dialog.error = ''; this.acting = dialog.recordId
      const response = await studentAffairsApi.addWorkStudyMonthly(dialog.recordId, { monthCode: dialog.monthCode.trim(), workHours: String(dialog.workHours), rating: dialog.rating, subsidyAmount: dialog.rating === 'FAIL' ? '0' : String(dialog.subsidyAmount) })
      this.acting = ''
      if (response.code === 0) { dialog.visible = false; toast.success('月度考核已登记'); await this.loadRecords() }
      else dialog.error = response.message || '登记失败'
    }
  }
}
</script>

<style scoped>
.ws-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.ws-tools, .ws-ops { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.ws-ops { justify-content: flex-end; }
.ws-muted { color: var(--text-tertiary); }
@media (max-width: 960px) { .ws-ops { justify-content: flex-start; } }
@import '@/styles/module-page.css';
</style>
