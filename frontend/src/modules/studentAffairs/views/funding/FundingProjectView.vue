<template>
  <AppPageShell
    title="资助项目"
    subtitle="统一维护奖学金与助学金标准。停用项目只停止新申请，已受理流程仍继续办理。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助项目管理"
  >
    <template #actions>
      <AppPermissionButton
        code="studentAffairs.funding.project.manage"
        :allowed="canBtn('studentAffairs.funding.project.manage')"
        :loading="saving"
        @click="openForm"
      >建项目</AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载资助项目..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/funding')"
    >
      <section class="fp-summary" aria-label="资助项目概览">
        <div><span>全部项目</span><strong>{{ summary.all }}</strong></div>
        <div><span>启用中</span><strong>{{ summary.byStatus.ENABLED || 0 }}</strong></div>
        <div><span>奖学金</span><strong>{{ summary.byType.SCHOLARSHIP || 0 }}</strong></div>
        <div><span>助学金</span><strong>{{ summary.byType.GRANT || 0 }}</strong></div>
      </section>

      <AppSectionCard
        title="项目目录"
        subtitle="金额与资格规则会在申请提交时冻结，后续调整不改写历史申请。"
        compact
      >
        <div class="fp-toolbar">
          <AppTextInput
            v-model="filters.keyword"
            class="fp-search"
            type="search"
            placeholder="搜索项目名称"
            clearable
            @change="applyFilters"
            @clear="applyFilters"
          />
          <AppSelect v-model="filters.projectType" class="fp-filter" :options="typeOptions" @change="applyFilters" />
          <AppSelect v-model="filters.status" class="fp-filter" :options="statusOptions" @change="applyFilters" />
          <button type="button" class="fp-search-btn" :disabled="loading" @click="applyFilters">查询</button>
        </div>

        <DataTable v-if="projects.length" :columns="projectColumns" :rows="projects" row-key="projectId">
          <template #cell-project="{ row }">
            <strong class="fp-main">{{ row.projectName }}</strong>
            <small>{{ typeLabel(row.projectType) }} · 规则 {{ row.eligibilityRuleVersion || '按学校当前配置' }}</small>
          </template>
          <template #cell-standard="{ row }">
            <strong>{{ amountText(row.amount) }}</strong>
            <small>{{ row.quota != null ? `项目默认 ${row.quota} 个名额` : '批次另设名额' }}</small>
          </template>
          <template #cell-eligibility="{ row }">{{ eligibilityText(row) }}</template>
          <template #cell-batches="{ row }">
            <span>{{ row.batchCount || 0 }} 个批次</span>
            <small>{{ row.openBatchCount || 0 }} 个正在开放</small>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.status === 'ENABLED' ? '启用' : '停用'" dot />
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton
              v-if="row.allowedActions?.includes('DISABLE')"
              code="studentAffairs.funding.project.manage"
              :allowed="canBtn('studentAffairs.funding.project.manage')"
              variant="secondary"
              size="sm"
              :disabled="actionBusy"
              @click="openStatusDialog(row, 'DISABLED')"
            >停用</AppPermissionButton>
            <AppPermissionButton
              v-else-if="row.allowedActions?.includes('ENABLE')"
              code="studentAffairs.funding.project.manage"
              :allowed="canBtn('studentAffairs.funding.project.manage')"
              size="sm"
              :disabled="actionBusy"
              @click="openStatusDialog(row, 'ENABLED')"
            >启用</AppPermissionButton>
            <span v-else class="fp-muted">无需操作</span>
          </template>
        </DataTable>
        <div v-else class="fp-empty">
          <strong>{{ hasFilters ? '没有匹配的项目' : '还没有资助项目' }}</strong>
          <p>{{ hasFilters ? '调整搜索条件后再试。' : '先创建项目，再到批次管理设置申请窗口。' }}</p>
        </div>
        <AppPagination
          v-if="total > pageSize || page > 1"
          class="fp-pager"
          v-model:page="page"
          v-model:pageSize="pageSize"
          :total="total"
          :disabled="loading"
          @change="load"
        />
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer v-model:visible="drawer.visible" title="新建资助项目" mode="modal" size="medium">
      <div class="fp-form">
        <AppInlineAlert
          type="info"
          description="项目保存后立即启用；学生仍需等批次发布并进入申请窗口后才能申请。"
        />
        <AppFormItem label="项目名称" required>
          <AppTextInput v-model="drawer.form.projectName" :maxlength="200" placeholder="如：国家励志奖学金" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="项目类型" required>
          <AppSelect v-model="drawer.form.projectType" :options="projectTypeOptions" :disabled="saving" />
        </AppFormItem>
        <div class="fp-grid2">
          <AppFormItem label="每人标准金额（元）" required hint="申请提交时按此金额冻结，不能由申请人自行填写。">
            <AppNumberInput v-model="drawer.form.amount" :min="0.01" placeholder="如：3000" :disabled="saving" />
          </AppFormItem>
          <AppFormItem label="默认名额" hint="选填；建批次时可覆盖。">
            <AppNumberInput v-model="drawer.form.quota" :min="1" placeholder="如：50" :disabled="saving" />
          </AppFormItem>
        </div>
        <p class="fp-rule-hint">{{ drawer.form.projectType === 'GRANT' ? '助学金默认要求学生处于有效困难认定库。' : '奖学金默认核验正常学籍、未解除处分与未通过课程。' }}</p>
        <AppInlineAlert v-if="drawer.errorMessage" type="danger" :description="drawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="fp-secondary-btn" :disabled="saving" @click="drawer.visible = false">取消</button>
        <AppPermissionButton
          code="studentAffairs.funding.project.manage"
          :allowed="canBtn('studentAffairs.funding.project.manage')"
          :loading="saving"
          @click="save"
        >保存项目</AppPermissionButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="statusDialog.visible"
      :title="statusDialog.target === 'DISABLED' ? '停用资助项目' : '启用资助项目'"
      :type="statusDialog.target === 'DISABLED' ? 'warning' : 'primary'"
      :confirm-text="statusDialog.target === 'DISABLED' ? '停止接收新申请' : '启用项目'"
      :submitting="actionBusy"
      @confirm="submitStatusChange"
    >
      <div v-if="statusDialog.row" class="fp-dialog-context">
        <strong>{{ statusDialog.row.projectName }}</strong>
        <p v-if="statusDialog.target === 'DISABLED'">开放批次将不再出现在学生端，但已提交申请仍按原流程继续办理。</p>
        <p v-else>启用后，处于有效申请窗口的开放批次会重新对学生可见。</p>
      </div>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell,
  AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const PROJECT_COLUMNS = [
  { key: 'project', title: '项目' },
  { key: 'standard', title: '资助标准', width: '170px' },
  { key: 'eligibility', title: '默认准入' },
  { key: 'batches', title: '批次', width: '130px' },
  { key: 'status', title: '状态', width: '100px' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]
const PROJECT_TYPES = [
  { label: '奖学金', value: 'SCHOLARSHIP' },
  { label: '助学金', value: 'GRANT' }
]

function freshForm() {
  return { projectName: '', projectType: 'GRANT', amount: null, quota: null }
}

export default {
  name: 'FundingProjectView',
  components: {
    AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput,
    AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppTextInput,
    StatusTag: AppStatusTag, DataTable
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      projectColumns: PROJECT_COLUMNS,
      projectTypeOptions: PROJECT_TYPES,
      typeOptions: [{ label: '全部类型', value: '' }, ...PROJECT_TYPES],
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '启用中', value: 'ENABLED' },
        { label: '已停用', value: 'DISABLED' }
      ],
      loading: true,
      saving: false,
      actionBusy: false,
      loadSeq: 0,
      errorMessage: '',
      projects: [],
      summary: { all: 0, byStatus: {}, byType: {} },
      filters: { keyword: '', projectType: '', status: '' },
      page: 1,
      pageSize: 20,
      total: 0,
      drawer: { visible: false, form: freshForm(), errorMessage: '' },
      statusDialog: { visible: false, row: null, target: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    hasFilters() { return Boolean(this.filters.keyword || this.filters.projectType || this.filters.status) }
  },
  mounted() { this.load() },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      const seq = ++this.loadSeq
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getFundingProjects({
          ...this.filters,
          keyword: this.filters.keyword.trim(),
          page: this.page,
          pageSize: this.pageSize
        })
        if (seq !== this.loadSeq) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '资助项目加载失败')
        this.projects = res.data.items || []
        this.total = Number(res.data.total || 0)
        this.summary = res.data.summary || { all: 0, byStatus: {}, byType: {} }
        const lastPage = Math.max(1, Math.ceil(this.total / this.pageSize))
        if (this.page > lastPage) { this.page = lastPage; await this.load() }
      } catch (error) {
        if (seq === this.loadSeq) this.errorMessage = error.message || '资助项目加载失败'
      } finally {
        if (seq === this.loadSeq) this.loading = false
      }
    },
    applyFilters() { this.page = 1; this.load() },
    openForm() {
      this.drawer = { visible: true, form: freshForm(), errorMessage: '' }
    },
    async save() {
      if (this.saving) return
      const form = this.drawer.form
      const projectName = String(form.projectName || '').trim()
      const amount = Number(form.amount)
      const quota = form.quota === '' || form.quota == null ? null : Number(form.quota)
      if (!projectName) { this.drawer.errorMessage = '请填写项目名称'; return }
      if (!Number.isFinite(amount) || amount <= 0) { this.drawer.errorMessage = '请填写大于 0 的每人标准金额'; return }
      if (quota != null && (!Number.isInteger(quota) || quota < 1)) { this.drawer.errorMessage = '默认名额应为大于 0 的整数'; return }
      this.drawer.errorMessage = ''
      this.saving = true
      try {
        const res = await studentAffairsApi.createFundingProject({
          projectName,
          projectType: form.projectType,
          amount: String(amount),
          ...(quota == null ? {} : { quota })
        })
        if (res.code !== 0) throw new Error(res.message || '项目创建失败')
        toast.success('项目已创建，可继续设置申请批次')
        this.drawer.visible = false
        this.page = 1
        await this.load()
      } catch (error) {
        this.drawer.errorMessage = error.message || '项目创建失败'
      } finally {
        this.saving = false
      }
    },
    openStatusDialog(row, target) {
      if (this.actionBusy || row.version == null) return
      this.statusDialog = { visible: true, row: { ...row }, target }
    },
    async submitStatusChange() {
      if (this.actionBusy || !this.statusDialog.visible || !this.statusDialog.row) return
      const { row, target } = this.statusDialog
      this.actionBusy = true
      try {
        const res = await studentAffairsApi.setFundingProjectStatus(row.projectId, target, row.version)
        if (res.code !== 0) throw new Error(res.message || '项目状态更新失败，请刷新后重试')
        toast.success(target === 'DISABLED' ? '项目已停用，学生端已停止新申请' : '项目已启用')
        this.statusDialog.visible = false
        await this.load()
      } catch (error) {
        toast.error(error.message || '项目状态更新失败，请刷新后重试')
      } finally {
        this.actionBusy = false
      }
    },
    typeLabel(type) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金' })[type] || '类型待核对' },
    amountText(amount) {
      if (amount == null || amount === '') return '金额待配置'
      return `¥${Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} / 人`
    },
    eligibilityText(row) {
      const rules = row.eligibilityRules || {}
      if (row.projectType === 'GRANT') {
        if (rules.requireDifficultLibrary === false) return '按项目专项资格核验'
        const levels = Array.isArray(rules.allowedAidLevels) ? rules.allowedAidLevels.length : 0
        return levels ? `困难认定在库 · ${levels} 类等级可申请` : '困难认定在库'
      }
      const checks = []
      if (rules.requireActiveStatus !== false) checks.push('正常学籍')
      if (rules.requireNoActiveDiscipline !== false) checks.push('无在处分')
      if (rules.requireNoFailedGrade !== false) checks.push('无挂科')
      return checks.length ? checks.join(' · ') : '按项目专项资格核验'
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.fp-summary { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px;border:1px solid var(--border-base);border-radius:12px;background:var(--bg-card);overflow:hidden }
.fp-summary>div { display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:12px 16px;border-right:1px solid var(--border-light) }
.fp-summary>div:last-child { border-right:0 }.fp-summary span { color:var(--text-secondary);font-size:12px }.fp-summary strong { color:var(--text-primary);font-size:20px;font-variant-numeric:tabular-nums }
.fp-toolbar { display:grid;grid-template-columns:minmax(220px,1fr) 150px 130px auto;gap:10px;margin-bottom:14px }.fp-search,.fp-filter { min-width:0 }.fp-search-btn,.fp-secondary-btn { height:34px;padding:0 15px;border:1px solid var(--border-base);border-radius:8px;background:var(--bg-card);color:var(--text-secondary);font:inherit;cursor:pointer }.fp-search-btn:hover,.fp-secondary-btn:hover { border-color:var(--primary-400);color:var(--color-primary) }.fp-search-btn:disabled,.fp-secondary-btn:disabled { opacity:.55;cursor:default }
.fp-main { display:block;color:var(--text-primary);font-weight:600 }.fp-main+small,td small { display:block;margin-top:5px;color:var(--text-tertiary);font-size:12px;line-height:1.45 }.fp-muted { color:var(--text-tertiary);font-size:12px }.fp-empty { padding:34px 16px;text-align:center }.fp-empty strong { color:var(--text-primary) }.fp-empty p { margin:7px 0 0;color:var(--text-secondary);font-size:13px }.fp-pager { margin-top:14px }
.fp-form { display:flex;flex-direction:column;gap:4px }.fp-grid2 { display:grid;grid-template-columns:1fr 1fr;gap:12px }.fp-rule-hint { margin:2px 0 12px;padding:10px 12px;border-radius:9px;background:var(--bg-subtle);color:var(--text-secondary);font-size:13px;line-height:1.6 }.fp-dialog-context { padding:13px 14px;border:1px solid var(--border-base);border-radius:10px;background:var(--bg-subtle) }.fp-dialog-context p { margin:7px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.65 }
@media (max-width:900px) { .fp-summary { grid-template-columns:1fr 1fr }.fp-summary>div:nth-child(2) { border-right:0 }.fp-summary>div:nth-child(-n+2) { border-bottom:1px solid var(--border-light) }.fp-toolbar { grid-template-columns:1fr 1fr }.fp-search { grid-column:1/-1 } }
@media (max-width:560px) { .fp-summary { grid-template-columns:1fr 1fr }.fp-summary>div { padding:10px 12px }.fp-toolbar,.fp-grid2 { grid-template-columns:1fr }.fp-search { grid-column:auto } }
</style>
