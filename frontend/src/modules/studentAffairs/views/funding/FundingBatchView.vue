<template>
  <AppPageShell
    flat
    title="申请批次"
    subtitle="按项目设置申请窗口。草稿可反复核对，发布后四端同步开放，关闭只停止新申请。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助批次管理"
  >
    <template #actions>
      <AppPermissionButton
        code="studentAffairs.funding.project.manage"
        :allowed="canBtn('studentAffairs.funding.project.manage')"
        :loading="saving"
        :disabled="!enabledProjects.length"
        @click="openForm"
      >建批次</AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载资助批次..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/funding')"
    >
      <section class="fb-kpis" aria-label="申请批次概览">
        <div><span>全部批次</span><strong>{{ summary.all }}</strong></div>
        <div><span>当前可申请</span><strong>{{ summary.availableNow || 0 }}</strong></div>
        <div><span>开放状态</span><strong>{{ summary.byStatus.OPEN || 0 }}</strong></div>
        <div><span>待发布草稿</span><strong>{{ summary.byStatus.DRAFT || 0 }}</strong></div>
      </section>

      <AppInlineAlert
        v-if="!loadingProjects && !enabledProjects.length"
        type="warning"
        description="当前没有启用中的奖学金或助学金项目，请先到“资助项目”创建或启用项目。"
      />

      <section class="fb-list" aria-label="批次列表">
        <header class="fb-list__head">
          <h2>批次列表</h2>
          <span>开放批次、启用项目、有效申请窗口</span>
        </header>
        <div class="fb-toolbar">
          <AppTextInput
            v-model="filters.keyword"
            class="fb-search"
            type="search"
            placeholder="搜索项目名称或学年"
            clearable
            @change="applyFilters"
            @clear="applyFilters"
          />
          <AppSelect v-model="filters.projectId" class="fb-project-filter" :options="projectFilterOptions" @change="applyFilters" />
          <AppSelect v-model="filters.status" class="fb-status-filter" :options="statusOptions" @change="applyFilters" />
          <button type="button" class="fb-search-btn" :disabled="loading" @click="applyFilters">查询</button>
        </div>

        <DataTable v-if="batches.length" :columns="batchColumns" :rows="batches" row-key="batchId">
          <template #cell-project="{ row }">
            <strong class="fb-main">{{ row.projectName || projectName(row.projectId) }}</strong>
            <small>{{ typeLabel(row.projectType) }} · {{ row.schoolYear || '学年待核对' }}</small>
          </template>
          <template #cell-window="{ row }">
            <span class="fb-window">
              <template v-if="row.applyStart || row.applyEnd">
                <AppDateDisplay :value="row.applyStart" mode="date" empty-text="不限" />
                <span>至</span>
                <AppDateDisplay :value="row.applyEnd" mode="date" empty-text="不限" />
              </template>
              <template v-else>长期有效</template>
            </span>
            <small>公示 {{ row.publicityDays || 5 }} 天</small>
          </template>
          <template #cell-usage="{ row }">
            <span>已申请 {{ row.applicationCount || 0 }}</span>
            <small>{{ row.quota != null ? `名额 ${row.reservedQuota || 0} / ${row.quota}` : `已确认 ${row.reservedQuota || 0}` }}</small>
          </template>
          <template #cell-intake="{ row }">
            <StatusTag :type="intakeType(row)" :label="intakeLabel(row)" dot />
          </template>
          <template #cell-status="{ row }">
            <span>{{ statusLabel(row.status) }}</span>
            <small>版本 {{ row.version }}</small>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton
              v-if="row.allowedActions?.includes('PUBLISH')"
              code="studentAffairs.funding.project.manage"
              :allowed="canBtn('studentAffairs.funding.project.manage')"
              size="sm"
              :disabled="actionBusy"
              @click="openBatchAction(row, 'PUBLISH')"
            >发布</AppPermissionButton>
            <AppPermissionButton
              v-else-if="row.allowedActions?.includes('CLOSE')"
              code="studentAffairs.funding.project.manage"
              :allowed="canBtn('studentAffairs.funding.project.manage')"
              variant="secondary"
              size="sm"
              :disabled="actionBusy"
              @click="openBatchAction(row, 'CLOSE')"
            >关闭申请</AppPermissionButton>
            <span v-else class="fb-muted">无需操作</span>
          </template>
        </DataTable>
        <div v-else class="fb-empty">
          <strong>{{ hasFilters ? '没有匹配的批次' : '还没有申请批次' }}</strong>
          <p>{{ hasFilters ? '调整搜索条件后再试。' : '选择一个已启用项目，先保存草稿并核对申请窗口。' }}</p>
        </div>
        <AppPagination
          v-if="total > pageSize || page > 1"
          class="fb-pager"
          v-model:page="page"
          v-model:pageSize="pageSize"
          :total="total"
          :disabled="loading"
          @change="load"
        />
      </section>
    </AppGlobalState>

    <AppDrawer v-model:visible="drawer.visible" title="新建申请批次" mode="modal" size="large">
      <div class="fb-form">
        <AppInlineAlert type="info" description="建议先保存为草稿，核对项目、学年与申请时间后再从列表发布。" />
        <AppFormItem label="所属项目" required>
          <AppFundingProjectPicker
            v-model="drawer.form.projectId"
            :options="enabledProjectOptions"
            placeholder="请选择启用中的项目"
            :disabled="saving"
          />
        </AppFormItem>
        <div v-if="selectedProject" class="fb-project-context">
          <strong>{{ selectedProject.projectName }}</strong>
          <span>{{ amountText(selectedProject.amount) }} · {{ selectedProject.quota != null ? `默认 ${selectedProject.quota} 个名额` : '批次单独设置名额' }}</span>
        </div>
        <AppFormItem label="学年" required>
          <AppTextInput v-model="drawer.form.schoolYear" placeholder="如：2026-2027" :disabled="saving" />
        </AppFormItem>
        <div class="fb-grid2">
          <AppFormItem label="本批次名额" hint="选填；未填写时使用项目默认名额。">
            <AppNumberInput v-model="drawer.form.quota" :min="1" placeholder="如：50" :disabled="saving" />
          </AppFormItem>
          <AppFormItem label="公示天数" required>
            <AppNumberInput v-model="drawer.form.publicityDays" :min="1" :max="30" placeholder="1-30 天，默认 5" :disabled="saving" />
          </AppFormItem>
        </div>
        <AppFormItem label="申请窗口" hint="选填；开始时间前显示“未开始”，截止后自动停止新申请。">
          <AppDateRangePicker v-model="drawer.form.applyWindow" mode="form" empty-label="不限" :show-shortcuts="false" :disabled="saving" />
        </AppFormItem>
        <label class="fb-check">
          <input v-model="drawer.form.publish" type="checkbox" :disabled="saving" />
          <span><strong>保存后立即开放</strong><small>勾选前请确认项目、学年和申请窗口已经无误。</small></span>
        </label>
        <AppInlineAlert v-if="drawer.errorMessage" type="danger" :description="drawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="fb-secondary-btn" :disabled="saving" @click="drawer.visible = false">取消</button>
        <AppPermissionButton
          code="studentAffairs.funding.project.manage"
          :allowed="canBtn('studentAffairs.funding.project.manage')"
          :loading="saving"
          @click="save"
        >{{ drawer.form.publish ? '保存并开放' : '保存草稿' }}</AppPermissionButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="actionDialog.visible"
      :title="actionDialog.action === 'PUBLISH' ? '发布申请批次' : '关闭新申请'"
      :type="actionDialog.action === 'PUBLISH' ? 'primary' : 'warning'"
      :confirm-text="actionDialog.action === 'PUBLISH' ? '确认发布' : '确认关闭申请'"
      :submitting="actionBusy"
      @confirm="submitBatchAction"
    >
      <div v-if="actionDialog.row" class="fb-dialog-context">
        <strong>{{ actionDialog.row.projectName }} · {{ actionDialog.row.schoolYear }}</strong>
        <p v-if="actionDialog.action === 'PUBLISH'">发布后，项目启用且处于申请时间内时，学生 PC 与小程序会同步看到该批次。</p>
        <p v-else>关闭后停止接收新申请；已经提交的申请、补件、评审、公示和发放继续办理。</p>
      </div>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppDateDisplay, AppDateRangePicker, AppFormItem, AppFundingProjectPicker,
  AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell, AppPagination,
  AppPermissionButton, AppSelect, AppStatusTag, AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const BATCH_STATUS = {
  DRAFT: '草稿', OPEN: '开放', REVIEWING: '评审中', PUBLICITY: '公示中',
  ANNOUNCED: '已公布', CLOSED: '已关闭', ARCHIVED: '已归档'
}
const BATCH_COLUMNS = [
  { key: 'project', title: '项目与学年' },
  { key: 'window', title: '申请窗口', width: '220px' },
  { key: 'usage', title: '申请与名额', width: '150px' },
  { key: 'intake', title: '学生端', width: '130px' },
  { key: 'status', title: '批次状态', width: '110px' },
  { key: 'actions', title: '操作', align: 'right', width: '120px' }
]

function freshForm() {
  return { projectId: '', schoolYear: '', quota: null, publicityDays: 5, publish: false, applyWindow: { start: '', end: '' } }
}

export default {
  name: 'FundingBatchView',
  components: {
    AppConfirmDialog, AppDateDisplay, AppDateRangePicker, AppDrawer, AppFormItem, AppFundingProjectPicker,
    AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell, AppPagination, AppPermissionButton,
    AppSelect, AppTextInput, StatusTag: AppStatusTag, DataTable
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      batchColumns: BATCH_COLUMNS,
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '草稿', value: 'DRAFT' },
        { label: '开放', value: 'OPEN' },
        { label: '已关闭', value: 'CLOSED' },
        { label: '已归档', value: 'ARCHIVED' }
      ],
      loading: true,
      loadingProjects: true,
      saving: false,
      actionBusy: false,
      loadSeq: 0,
      errorMessage: '',
      batches: [],
      projects: [],
      summary: { all: 0, availableNow: 0, byStatus: {} },
      filters: { keyword: '', projectId: '', status: '' },
      page: 1,
      pageSize: 20,
      total: 0,
      drawer: { visible: false, form: freshForm(), errorMessage: '' },
      actionDialog: { visible: false, row: null, action: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    enabledProjects() { return this.projects.filter((project) => project.status === 'ENABLED') },
    enabledProjectOptions() {
      return this.enabledProjects.map((project) => ({
        label: `${project.projectName}（${this.typeLabel(project.projectType)}）`,
        value: project.projectId
      }))
    },
    projectFilterOptions() {
      return [{ label: '全部项目', value: '' }, ...this.projects.map((project) => ({
        label: project.projectName,
        value: project.projectId
      }))]
    },
    selectedProject() {
      return this.projects.find((project) => String(project.projectId) === String(this.drawer.form.projectId)) || null
    },
    hasFilters() { return Boolean(this.filters.keyword || this.filters.projectId || this.filters.status) }
  },
  async mounted() {
    await this.loadProjects()
    const routeProjectId = String(this.$route.query?.projectId || '').trim()
    if (routeProjectId && this.projects.some((project) => String(project.projectId) === routeProjectId)) {
      this.filters.projectId = routeProjectId
    }
    await this.load()
  },
  beforeUnmount() { this.loadSeq++ },
  watch: {
    '$route.query.projectId'(value) {
      const next = String(value || '').trim()
      if (next !== String(this.filters.projectId || '') && (!next || this.projects.some((project) => String(project.projectId) === next))) {
        this.filters.projectId = next
        this.page = 1
        this.load()
      }
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async loadProjects() {
      this.loadingProjects = true
      try {
        const all = []
        let page = 1
        let total = 0
        do {
          const res = await studentAffairsApi.getFundingProjects({ page, pageSize: 200 })
          if (res.code !== 0 || !res.data) throw new Error(res.message || '资助项目加载失败')
          all.push(...(res.data.items || []))
          total = Number(res.data.total || all.length)
          page++
        } while (all.length < total && page <= 100)
        this.projects = all
      } catch (error) {
        this.projects = []
        toast.error(error.message || '资助项目加载失败')
      } finally {
        this.loadingProjects = false
      }
    },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getFundingBatches({
          ...this.filters,
          keyword: this.filters.keyword.trim(),
          page: this.page,
          pageSize: this.pageSize
        })
        if (seq !== this.loadSeq) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '资助批次加载失败')
        this.batches = res.data.items || []
        this.total = Number(res.data.total || 0)
        this.summary = res.data.summary || { all: 0, availableNow: 0, byStatus: {} }
        const lastPage = Math.max(1, Math.ceil(this.total / this.pageSize))
        if (this.page > lastPage) { this.page = lastPage; await this.load() }
      } catch (error) {
        if (seq === this.loadSeq) this.errorMessage = error.message || '资助批次加载失败'
      } finally {
        if (seq === this.loadSeq) this.loading = false
      }
    },
    applyFilters() { this.page = 1; this.load() },
    openForm() {
      const form = freshForm()
      const contextual = this.enabledProjects.find((project) => String(project.projectId) === String(this.filters.projectId))
      if (contextual) form.projectId = contextual.projectId
      this.drawer = { visible: true, form, errorMessage: '' }
    },
    async save() {
      if (this.saving) return
      const form = this.drawer.form
      const project = this.selectedProject
      const schoolYear = String(form.schoolYear || '').trim()
      const quota = form.quota === '' || form.quota == null ? null : Number(form.quota)
      const publicityDays = Number(form.publicityDays)
      if (!project || project.status !== 'ENABLED') { this.drawer.errorMessage = '请选择一个启用中的资助项目'; return }
      if (!/^\d{4}-\d{4}$/.test(schoolYear)) { this.drawer.errorMessage = '学年格式应为 2026-2027'; return }
      if (quota != null && (!Number.isInteger(quota) || quota < 1)) { this.drawer.errorMessage = '本批次名额应为大于 0 的整数'; return }
      if (!Number.isInteger(publicityDays) || publicityDays < 1 || publicityDays > 30) { this.drawer.errorMessage = '公示天数应为 1-30 天'; return }
      this.drawer.errorMessage = ''
      this.saving = true
      try {
        const body = {
          projectId: project.projectId,
          schoolYear,
          publicityDays,
          publish: Boolean(form.publish),
          ...(quota == null ? {} : { quota })
        }
        if (form.applyWindow.start) body.applyStart = form.applyWindow.start
        if (form.applyWindow.end) body.applyEnd = form.applyWindow.end
        const res = await studentAffairsApi.createFundingBatch(body)
        if (res.code !== 0) throw new Error(res.message || '批次保存失败')
        toast.success(form.publish ? '批次已保存并开放申请' : '批次草稿已保存')
        this.drawer.visible = false
        this.page = 1
        await this.load()
      } catch (error) {
        this.drawer.errorMessage = error.message || '批次保存失败'
      } finally {
        this.saving = false
      }
    },
    openBatchAction(row, action) {
      if (this.actionBusy || row.version == null) return
      this.actionDialog = { visible: true, row: { ...row }, action }
    },
    async submitBatchAction() {
      if (this.actionBusy || !this.actionDialog.visible || !this.actionDialog.row) return
      const { row, action } = this.actionDialog
      this.actionBusy = true
      try {
        const res = await studentAffairsApi.actFundingBatch(row.batchId, action, row.version)
        if (res.code !== 0) throw new Error(res.message || '批次状态更新失败，请刷新后重试')
        toast.success(action === 'PUBLISH' ? '批次已发布，四端按申请窗口同步开放' : '新申请已关闭，既有申请继续办理')
        this.actionDialog.visible = false
        await this.load()
      } catch (error) {
        toast.error(error.message || '批次状态更新失败，请刷新后重试')
      } finally {
        this.actionBusy = false
      }
    },
    projectName(id) {
      return this.projects.find((project) => String(project.projectId) === String(id))?.projectName || '所属项目待核对'
    },
    typeLabel(type) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金' })[type] || '类型待核对' },
    statusLabel(status) { return BATCH_STATUS[status] || '状态待核对' },
    intakeLabel(row) {
      if (row.projectStatus === 'DISABLED') return '项目已停用'
      return ({ DRAFT: '尚未发布', OPEN: '可申请', UPCOMING: '尚未开始', ENDED: '申请已截止', CLOSED: '不可申请' })[row.intakeState] || '待核对'
    },
    intakeType(row) {
      if (row.intakeState === 'OPEN' && row.projectStatus === 'ENABLED') return 'success'
      if (row.intakeState === 'UPCOMING') return 'info'
      if (row.intakeState === 'DRAFT') return 'warning'
      return 'default'
    },
    amountText(amount) {
      if (amount == null || amount === '') return '金额待配置'
      return `¥${Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} / 人`
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.fb-kpis { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:0;border-bottom:1px solid var(--line) }.fb-kpis>div { display:flex;align-items:baseline;justify-content:space-between;gap:12px;min-height:42px;padding:6px 16px;border-right:1px solid var(--line) }.fb-kpis>div:first-child { padding-left:0 }.fb-kpis>div:last-child { border-right:0 }.fb-kpis span { color:var(--t3);font-size:11px }.fb-kpis strong { color:var(--t1);font-size:20px;font-variant-numeric:tabular-nums }
.fb-list { min-width:0 }.fb-list__head { display:flex;align-items:baseline;gap:10px;min-height:32px;padding:5px 0;border-bottom:1px solid var(--line) }.fb-list__head h2 { margin:0;color:var(--t1);font-size:14px }.fb-list__head span { color:var(--t3);font-size:11px }
.fb-toolbar { display:grid;grid-template-columns:minmax(220px,1fr) minmax(180px,260px) 130px auto;gap:8px;margin:8px 0 }.fb-search,.fb-project-filter,.fb-status-filter { min-width:0 }.fb-search-btn,.fb-secondary-btn { height:34px;padding:0 15px;border:1px solid var(--border-base);border-radius:6px;background:var(--bg-card);color:var(--text-secondary);font:inherit;cursor:pointer }.fb-search-btn:hover,.fb-secondary-btn:hover { border-color:var(--primary-400);color:var(--color-primary) }.fb-search-btn:disabled,.fb-secondary-btn:disabled { opacity:.55;cursor:default }
.fb-main { display:block;color:var(--text-primary);font-weight:600 }.fb-main+small,td small { display:block;margin-top:5px;color:var(--text-tertiary);font-size:12px;line-height:1.45 }.fb-window { display:flex;align-items:center;gap:5px;color:var(--text-secondary);font-size:13px;white-space:nowrap }.fb-muted { color:var(--text-tertiary);font-size:12px }.fb-empty { padding:34px 16px;text-align:center }.fb-empty strong { color:var(--text-primary) }.fb-empty p { margin:7px 0 0;color:var(--text-secondary);font-size:13px }.fb-pager { margin-top:14px }
.fb-form { display:flex;flex-direction:column;gap:4px }.fb-grid2 { display:grid;grid-template-columns:1fr 1fr;gap:12px }.fb-project-context { display:flex;align-items:center;justify-content:space-between;gap:12px;margin:-4px 0 8px;padding:10px 12px;border:1px solid var(--border-light);border-radius:9px;background:var(--bg-subtle);font-size:13px }.fb-project-context span { color:var(--text-secondary) }.fb-check { display:flex;align-items:flex-start;gap:9px;margin:2px 0 12px;padding:11px 12px;border:1px solid var(--border-base);border-radius:9px;color:var(--text-primary);cursor:pointer }.fb-check input { margin-top:3px }.fb-check span,.fb-check small { display:block }.fb-check small { margin-top:4px;color:var(--text-tertiary);font-size:12px;line-height:1.5 }.fb-dialog-context { padding:13px 14px;border:1px solid var(--border-base);border-radius:10px;background:var(--bg-subtle) }.fb-dialog-context p { margin:7px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.65 }
@media (max-width:1000px) { .fb-toolbar { grid-template-columns:1fr 1fr }.fb-search { grid-column:1/-1 }.fb-kpis { grid-template-columns:1fr 1fr }.fb-kpis>div:nth-child(2) { border-right:0 }.fb-kpis>div:nth-child(-n+2) { border-bottom:1px solid var(--line) } }
@media (max-width:600px) { .fb-toolbar,.fb-grid2 { grid-template-columns:1fr }.fb-search { grid-column:auto }.fb-project-context { align-items:flex-start;flex-direction:column }.fb-kpis>div { padding:6px 10px }.fb-list__head span { display:none } }
</style>
