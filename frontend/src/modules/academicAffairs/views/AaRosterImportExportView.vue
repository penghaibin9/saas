<template>
  <ModulePageShell
    title="学籍导入导出"
    subtitle="系统预检查 · 可追踪导入 · 可过期撤销导出"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="mp-stack">
      <AppSectionCard title="学籍导入" subtitle="原始表格先完成安全扫描，再由系统对同一份文件预检查">
        <p class="mp-note">
          学号、姓名、班级必填，班级须为已存在的行政班。页面只展示系统预检结果，不再把名单回传作为写入依据；
          扫描或解析未完成时不能确认。
        </p>
        <AppButton variant="primary" @click="openNewImport">打开批量导入</AppButton>
      </AppSectionCard>

      <AppSectionCard title="学籍导出" subtitle="生成导出文件和导出任务，不再直接下载">
        <div class="aa-export-row">
          <label class="aa-filter__item">
            关键字
            <input v-model.trim="exportFilters.keyword" class="aa-input" placeholder="姓名 / 学号（可选）" />
          </label>
          <label class="aa-filter__item">
            学籍状态
            <AppSelect v-model="exportFilters.status" :options="statusOptions" placeholder="全部" />
          </label>
          <AppButton :disabled="exporting" @click="doExport">创建导出任务</AppButton>
        </div>
        <p class="mp-note">文件带水印并记录用途；下载使用短时一次性票据，任务过期或撤销后不可继续下载。</p>
      </AppSectionCard>

      <AppSectionCard title="教务数据交换任务" subtitle="刷新页面任务不丢失；这里只展示当前操作者的教务任务">
        <div class="aa-task-head">
          <span v-if="!jobs.loading && !jobs.error" class="mp-note">共 {{ jobs.total }} 个任务</span>
          <AppButton variant="ghost" :disabled="jobs.loading || jobsNavigationBusy" @click="loadJobs">刷新</AppButton>
        </div>
        <AppGlobalState
          :state="jobListState"
          :title="jobs.error ? (jobs.error.title || '任务读取失败') : '暂无导入导出任务。'"
          :description="jobs.error?.userMessage || '当前没有可展示的导入导出任务。'"
          loading-text="正在读取任务…"
          @retry="loadJobs"
        >
        <div class="aa-task-list">
          <article v-for="item in jobs.list" :key="`${item.jobType}-${item.id}`" class="aa-task-card" :data-job-id="item.id">
            <div>
              <strong>{{ item.jobType === 'IMPORT' ? '导入' : '导出' }} · {{ academicExchangeTypeLabel(item.importType || item.exportType) }}</strong>
              <p class="mp-note">状态 {{ academicStatusLabel(item.status) }} · {{ item.createdAt || '-' }}</p>
              <p v-if="item.status === 'SCANNING'" class="mp-note">安全扫描进行中，文件不会被提前解析。</p>
              <p v-else-if="item.status === 'PARSING'" class="mp-note">安全扫描已通过，正在预检查。</p>
              <p v-if="item.errorMessage" class="aa-task-error">{{ item.errorMessage }}</p>
            </div>
            <div class="aa-task-actions">
              <AppButton v-if="canResumeJob(item)" size="small" :disabled="importVisible" @click="resumeImport(item)">继续处理</AppButton>
              <AppButton
                v-if="item.jobType === 'EXPORT' && item.status === 'SUCCEEDED'"
                size="small"
                @click="downloadExportJob(item)"
              >下载</AppButton>
              <AppButton
                v-if="item.jobType === 'EXPORT' && item.status === 'SUCCEEDED'"
                size="small" variant="ghost"
                @click="revokeExportJob(item)"
              >撤销</AppButton>
            </div>
          </article>
        </div>
        <AppPagination
          v-if="jobs.total > 50"
          :total="jobs.total"
          :page="jobs.page"
          :page-size="50"
          :show-size-changer="false"
          :disabled="jobs.loading || jobsNavigationBusy"
          @change="onJobsPageChange"
        />
        </AppGlobalState>
      </AppSectionCard>
    </div>

    <AaAuthoritativeImportDrawer
      v-model:visible="importVisible"
      title="学籍名册表格导入"
      :existing-job-id="existingImportJobId"
      expected-import-type="ACADEMIC_ROSTER"
      :ctx="ctx"
      template-name="学籍导入模板.xlsx"
      :preview-fields="['studentNo', 'realName', 'className', 'initialStatus']"
      :download-template-fn="() => academicAffairsApi.downloadRosterImportTemplate()"
      :upload-fn="academicFileExchangeApi.uploadRosterImport"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="exportDialog.visible" title="创建学籍名册导出任务" type="warning"
      message="系统将生成短期有效的导出文件并写入审计；下载票据仅可使用一次。"
      confirm-text="创建任务" require-reason phrase-scene-key="common.exportPurpose"
      reason-label="导出用途（≥5 字）" :submitting="exporting" @confirm="doExportConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppConfirmDialog, AppSelect, AppGlobalState, AppPagination } from '@/components/common'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import { academicExchangeTypeLabel, academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'
import { toast } from '@/utils/toast'
import { systemPrompt } from '@/services/systemDialog'
import { normalizeUiError } from '@/utils/presentationSafety'
import { academicRouteState, routeScalar } from '../academicFlowContext.js'

const TASK_ROUTE = '/admin/academic-affairs/roster/import-export'

const STATUS_LABEL = {
  NORMAL: '正常', PENDING_REGISTER: '待注册', REGISTERED: '在籍注册', UNREGISTERED: '未注册',
  SUSPENDED: '休学', RETAINED: '留级', WITHDRAWN: '退学', TRANSFER_SCHOOL: '转学',
  GRADUATED: '毕业', COMPLETED: '结业', INCOMPLETE: '肄业'
}
const IMPORT_TERMINAL = new Set(['VALIDATED', 'VALIDATION_FAILED', 'FAILED', 'EXPIRED', 'SUCCEEDED'])
const delay = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

function saveBlob(blob, filename) {
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
}

function previewResponse(item, message) {
  const preview = item.preview || {}
  const invalidRows = preview.invalidRows ?? item.invalidRows ?? 0
  const validated = item.status === 'VALIDATED'
  return {
    code: validated || item.status === 'VALIDATION_FAILED' ? 0 : 1,
    message: message || item.errorMessage || '导入任务尚未完成安全扫描与预检查',
    data: {
      total: preview.totalRows ?? item.totalRows ?? 0,
      validRows: preview.validRows ?? item.validRows ?? 0,
      invalidRows,
      passed: validated && invalidRows === 0,
      rows: preview.rows || [],
      errors: preview.errors || [],
      jobId: item.id,
      expectedVersion: item.version,
      status: item.status
    }
  }
}

export default {
  name: 'AaRosterImportExportView',
  components: { ModulePageShell, AppButton, AppSectionCard, AaAuthoritativeImportDrawer, AppConfirmDialog, AppSelect, AppGlobalState, AppPagination },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  computed: {
    jobListContextKey() {
      return JSON.stringify([this.ctx?.ctxKey, this.ctx?.currentRole, this.ctx?.dataScope, this.ctx?.permissionPatterns, this.academicFlow?.identity?.() || ''])
    },
    jobRoutePositionKey() {
      const route = this.$router ? this.$route : null
      const query = route?.query || {}
      return JSON.stringify([route?.path || '', query.page, Object.prototype.hasOwnProperty.call(query, 'returnToken'), query.returnToken])
    },
    jobListState() {
      if (this.jobs.loading) return 'loading'
      if (this.jobs.error) return this.jobs.error.pageState
      return this.jobs.list.length ? 'ready' : 'empty'
    },
    statusOptions() {
      return Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))
    }
  },
  data() {
    return {
      academicAffairsApi, academicFileExchangeApi,
      importVisible: false,
      existingImportJobId: '',
      currentImportJob: null,
      exporting: false,
      exportDialog: { visible: false },
      exportFilters: { keyword: '', status: '' },
      jobsRequestEpoch: 0,
      jobsDisposed: false,
      jobsNavigationEpoch: 0,
      jobsNavigationBusy: false,
      jobsNavigationTarget: '',
      jobsNavigationContext: '',
      jobsSuppressedRoute: '',
      jobsSuppressedRouteEpoch: 0,
      jobs: { list: [], total: 0, page: 1, loading: false, error: null }
    }
  },
  mounted() {
    this.jobs.page = this.readJobsRoutePage()
    this.loadJobs()
  },
  watch: {
    jobRoutePositionKey: {
      flush: 'sync',
      handler(_next, previous) {
        if (!previous || this.jobsDisposed || !this.isJobsRoute()) return
        if (this.$route.fullPath === this.jobsSuppressedRoute) { this.jobsSuppressedRoute = ''; return }
        if (this.jobsNavigationBusy && this.$route.fullPath === this.jobsNavigationTarget && this.jobsNavigationContext === this.jobListContextKey) return
        this.cancelJobsNavigation(false)
        this.jobsRequestEpoch++
        this.jobs.loading = false
        this.jobs.page = this.readJobsRoutePage()
        this.loadJobs()
      }
    },
    jobListContextKey: {
      flush: 'sync',
      handler() {
        if (this.jobsDisposed) return
        this.cancelJobsNavigation(true)
        this.jobsRequestEpoch++
        this.jobs.list = []
        this.jobs.total = 0
        this.jobs.page = 1
        this.jobs.loading = false
        this.jobs.error = { pageState: 'error', title: '任务列表需刷新', userMessage: '身份或管理范围已变化，请重新读取任务列表' }
      }
    }
  },
  beforeRouteLeave() {
    this.cancelJobsNavigation(false)
    return true
  },
  beforeUnmount() {
    this.cancelJobsNavigation(false)
    this.jobsDisposed = true
    this.jobsRequestEpoch++
  },
  methods: {
    canResumeJob(item) {
      return item.jobType === 'IMPORT' && item.moduleCode === 'ACADEMIC_AFFAIRS' &&
        item.importType === 'ACADEMIC_ROSTER' && item.adapterType === 'EXCEL_IMPORT_JOB' &&
        typeof item.id === 'string' && !!item.id.trim()
    },
    openNewImport() {
      if (this.importVisible) return
      this.existingImportJobId = ''
      this.importVisible = true
    },
    resumeImport(item) {
      if (this.importVisible || !this.canResumeJob(item)) return
      this.existingImportJobId = item.id
      this.importVisible = true
    },
    academicExchangeTypeLabel,
    academicStatusLabel,
    async waitForImportJob(initial) {
      let item = initial
      for (let attempt = 0; attempt < 60 && !IMPORT_TERMINAL.has(item.status); attempt += 1) {
        await delay(1500)
        const detail = await academicFileExchangeApi.getImportJob(item.id)
        if (detail.code !== 0) return detail
        item = detail.data
        this.currentImportJob = { id: item.id, version: item.version, status: item.status }
      }
      await this.loadJobs()
      if (!IMPORT_TERMINAL.has(item.status)) {
        return {
          code: 1,
          data: null,
          message: '文件仍在后台安全扫描，请稍后在任务中心刷新；扫描完成前不会开放确认'
        }
      }
      return { code: 0, data: item, message: item.errorMessage || '预检查已完成' }
    },
    async uploadAuthoritative(file) {
      const res = await academicFileExchangeApi.uploadRosterImport(file)
      if (res.code !== 0) return res
      this.currentImportJob = { id: res.data.id, version: res.data.version, status: res.data.status }
      const terminal = IMPORT_TERMINAL.has(res.data.status)
        ? { code: 0, data: res.data, message: res.message }
        : await this.waitForImportJob(res.data)
      if (terminal.code !== 0) return terminal
      this.currentImportJob = {
        id: terminal.data.id,
        version: terminal.data.version,
        status: terminal.data.status
      }
      return previewResponse(terminal.data, terminal.message)
    },
    async confirmAuthoritative() {
      if (!this.currentImportJob?.id) return { code: 1, message: '导入任务已丢失，请重新上传预检' }
      if (this.currentImportJob.status !== 'VALIDATED') {
        const detail = await academicFileExchangeApi.getImportJob(this.currentImportJob.id)
        if (detail.code !== 0) return detail
        this.currentImportJob = {
          id: detail.data.id,
          version: detail.data.version,
          status: detail.data.status
        }
        if (detail.data.status !== 'VALIDATED') {
          return { code: 1, message: '安全扫描或预检查尚未通过，禁止确认导入' }
        }
      }
      const res = await academicFileExchangeApi.confirmImport(
        this.currentImportJob.id,
        this.currentImportJob.version
      )
      if (res.code === 0) this.currentImportJob = null
      return res
    },
    onImported(data) {
      const d = data?.result || data || {}
      const parts = [`新建 ${d.created ?? 0}`]
      if (d.reused) parts.push(`复用已有主档 ${d.reused}`)
      if (d.skipped) parts.push(`已存在跳过 ${d.skipped}`)
      const conflicts = (d.identityConflict ?? 0) + (d.orgConflict ?? 0) + (d.voidedConflict ?? 0)
      if (conflicts) parts.push(`冲突待处理 ${conflicts}`)
      if (d.failed) parts.push(`失败 ${d.failed}`)
      const msg = `学籍导入完成：${parts.join(' / ')}`
      if (conflicts || d.failed) toast.warning(msg)
      else toast.success(msg)
      this.loadJobs()
    },
    doExport() {
      this.exportDialog.visible = true
    },
    async doExportConfirm({ reason }) {
      this.exporting = true
      const res = await academicFileExchangeApi.createRosterExport({
        purpose: reason,
        keyword: this.exportFilters.keyword || undefined,
        status: this.exportFilters.status || undefined
      })
      this.exporting = false
      if (res.code !== 0) {
        toast.error(res.message || '导出任务创建失败')
        return
      }
      this.exportDialog.visible = false
      toast.success('导出任务已生成，可在任务列表下载')
      await this.loadJobs()
    },
    isJobsRoute() { return !!this.$router && this.$route?.path === TASK_ROUTE },
    readJobsRoutePosition() {
      if (!this.isJobsRoute()) return { page: 1, validToken: false }
      const query = this.$route.query || {}
      const livePage = academicRouteState(this.$route).page
      if (!Object.prototype.hasOwnProperty.call(query, 'returnToken')) return { page: livePage, validToken: false }
      const identity = this.academicFlow?.identity?.() || ''
      const token = routeScalar(query.returnToken)
      if (!identity || !token || token.length > 200 || typeof query.returnToken !== 'string') return { page: 1, validToken: false }
      const entry = this.academicFlow?.returns?.resolve(token, identity)
      if (!entry) return { page: 1, validToken: false }
      try {
        const saved = new URL(entry.path, 'http://academic.local')
        if (saved.origin !== 'http://academic.local' || saved.pathname !== TASK_ROUTE) return { page: 1, validToken: false }
        const savedPage = academicRouteState({ query: Object.fromEntries(saved.searchParams) }).page
        return savedPage === livePage ? { page: savedPage, validToken: true } : { page: 1, validToken: false }
      } catch { return { page: 1, validToken: false } }
    },
    readJobsRoutePage() { return this.readJobsRoutePosition().page },
    jobsPositionMatches(page) {
      const position = this.readJobsRoutePosition()
      return position.validToken && position.page === page
    },
    cancelJobsNavigation(clearPosition) {
      const pending = this.jobsNavigationBusy
      const epoch = ++this.jobsNavigationEpoch
      this.jobsNavigationBusy = false
      this.jobsNavigationTarget = ''
      this.jobsNavigationContext = ''
      if (!clearPosition || !this.isJobsRoute()) return
      const query = { ...this.$route.query }
      const hadPosition = Object.prototype.hasOwnProperty.call(query, 'page') || Object.prototype.hasOwnProperty.call(query, 'returnToken')
      delete query.page; delete query.returnToken
      if (!pending && !hadPosition) return
      const destination = { path: TASK_ROUTE, query }
      const fullPath = this.$router.resolve(destination).fullPath
      if (fullPath !== this.$route.fullPath) {
        this.jobsSuppressedRoute = fullPath
        this.jobsSuppressedRouteEpoch = epoch
      }
      // A normal replace supersedes pendingLocation even when the URL is duplicated.
      // This cancels our old pending publication before Router can commit it.
      Promise.resolve(this.$router.replace(destination)).catch(() => {}).finally(() => {
        if (this.jobsSuppressedRouteEpoch === epoch) this.jobsSuppressedRoute = ''
      })
    },
    async publishJobsPosition(page) {
      if (!this.$router) return true
      if (this.jobsDisposed || !this.isJobsRoute() || this.jobsNavigationBusy) return false
      const epoch = ++this.jobsNavigationEpoch
      const contextKey = this.jobListContextKey
      const identity = this.academicFlow?.identity?.() || ''
      const query = { ...this.$route.query }
      delete query.page; delete query.returnToken
      if (page !== 1) query.page = String(page)
      const token = identity && this.academicFlow?.returns?.remember({ path: TASK_ROUTE, query }, identity)
      if (!token) {
        toast.error('任务页位置暂未保存，请重试')
        return false
      }
      query.returnToken = token
      const destination = { path: TASK_ROUTE, query }
      const target = this.$router.resolve(destination).fullPath
      this.jobsNavigationBusy = true
      this.jobsNavigationTarget = target
      this.jobsNavigationContext = contextKey
      const ownsNavigation = () => !this.jobsDisposed && epoch === this.jobsNavigationEpoch && contextKey === this.jobListContextKey && this.$route?.path === TASK_ROUTE
      try {
        await this.$router.replace(destination)
        const published = ownsNavigation() && this.$route.fullPath === target
        if (ownsNavigation() && !published) toast.error('任务页暂未切换，请重试')
        return published
      } catch (error) {
        if (ownsNavigation()) toast.error(normalizeUiError(error, { fallback: '任务页暂未切换，请重试' }).userMessage)
        return false
      } finally {
        if (ownsNavigation()) {
          this.jobsNavigationBusy = false
          this.jobsNavigationTarget = ''
          this.jobsNavigationContext = ''
        }
      }
    },
    async onJobsPageChange({ page }) {
      if (this.jobsDisposed || this.jobs.loading || this.jobsNavigationBusy || !Number.isInteger(page) || page < 1 || page === this.jobs.page) return
      const contextKey = this.jobListContextKey
      if (!await this.publishJobsPosition(page) || this.jobsDisposed || contextKey !== this.jobListContextKey) return
      this.jobs.page = page
      this.loadJobs()
    },
    async loadJobs() {
      if (this.jobsDisposed || !this.ctx || this.jobs.loading || this.jobsNavigationBusy) return
      const epoch = ++this.jobsRequestEpoch
      const contextKey = this.jobListContextKey
      let activePage = this.jobs.page
      const ownsRequest = () => !this.jobsDisposed && epoch === this.jobsRequestEpoch && contextKey === this.jobListContextKey && activePage === this.jobs.page && (!this.$router || this.isJobsRoute())
      this.jobs.loading = true
      this.jobs.error = null
      this.jobs.list = []
      this.jobs.total = 0
      try {
        let corrected = false
        while (true) {
          const res = await academicFileExchangeApi.listJobs({ page: activePage, pageSize: 50 })
          if (!ownsRequest()) return
          if (res.code !== 0) throw res
          const total = res.data.total || 0
          const lastPage = Math.max(1, Math.ceil(total / 50))
          if (total === 0) {
            activePage = 1
            this.jobs.page = activePage
            if (this.$router && !this.jobsPositionMatches(activePage) && !await this.publishJobsPosition(activePage)) {
              if (ownsRequest()) throw new Error('任务页位置暂未保存，请重试')
              return
            }
            if (!ownsRequest()) return
          } else if (activePage > lastPage) {
            activePage = lastPage
            this.jobs.page = activePage
            if (this.$router && !await this.publishJobsPosition(activePage)) {
              if (ownsRequest()) throw new Error('任务页位置暂未保存，请重试')
              return
            }
            if (!ownsRequest()) return
            if (corrected) throw new Error('任务数量已变化，请重试')
            corrected = true
            continue
          }
          if (this.$router && !this.jobsPositionMatches(activePage) && !await this.publishJobsPosition(activePage)) {
            if (ownsRequest()) throw new Error('任务页位置暂未保存，请重试')
            return
          }
          if (!ownsRequest()) return
          this.jobs.list = res.data.list || []
          this.jobs.total = total
          return
        }
      } catch (error) {
        if (!ownsRequest()) return
        const { pageState, userMessage } = normalizeUiError(error, { fallback: '任务读取失败，请重试' })
        this.jobs.error = { pageState, userMessage }
      } finally {
        if (ownsRequest()) this.jobs.loading = false
      }
    },
    async downloadExportJob(item) {
      const ticket = await academicFileExchangeApi.createExportDownloadTicket(item.id, item.version)
      if (ticket.code !== 0) {
        toast.error(ticket.message || '下载票据创建失败')
        return
      }
      const file = await academicFileExchangeApi.downloadExport(ticket.data.downloadUrl)
      if (file.code !== 0) {
        toast.error(file.message || '导出文件下载失败')
        return
      }
      saveBlob(file.data, `学籍名册-${Date.now()}.xlsx`)
      toast.success('下载完成；本次票据已失效')
      await this.loadJobs()
    },
    async revokeExportJob(item) {
      const reason = await systemPrompt({ title:'填写撤销原因', message:'撤销原因将写入审计记录。', placeholder:'不少于 5 个字', minLength:5, confirmText:'确认撤销' })
      if (!reason) return
      const res = await academicFileExchangeApi.revokeExport(item.id, item.version, reason)
      if (res.code !== 0) {
        toast.error(res.message || '撤销失败')
        return
      }
      toast.success('导出任务已撤销')
      await this.loadJobs()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-export-row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: var(--space-2); }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-task-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.aa-task-list { display: grid; gap: 10px; margin-top: 12px; }
.aa-task-card { display: flex; justify-content: space-between; gap: 16px; padding: 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; }
.aa-task-card p { margin: 4px 0 0; }
.aa-task-actions { display: flex; align-items: center; gap: 8px; }
.aa-task-error { color: var(--danger-600, #d92d20); font-size: 12px; }
</style>
