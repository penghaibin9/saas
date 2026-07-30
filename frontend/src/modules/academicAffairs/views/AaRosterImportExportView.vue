<template>
  <ModulePageShell
    title="学籍导入导出"
    subtitle="服务端权威预检 · 可追踪导入 · 可过期撤销导出"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="学籍导入" subtitle="原始 XLSX 进入安全检查；确认时由后端重新解析同一不可变文件">
        <p class="mp-note">
          学号、姓名、班级必填，班级须为已存在的行政班。前端只展示服务端预检结果，不再把 rows 回传作为写库依据；
          确认请求仅包含任务编号和任务版本，多实例重复点击由任务租约拦截。
        </p>
        <AppButton variant="primary" @click="importVisible = true">打开批量导入</AppButton>
      </AppSectionCard>

      <AppSectionCard title="学籍导出" subtitle="生成 FileObject + ExportJob，不再同步直出 Blob">
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
          <span class="mp-note">共 {{ jobs.total }} 个任务</span>
          <AppButton variant="ghost" :disabled="jobs.loading" @click="loadJobs">刷新</AppButton>
        </div>
        <div v-if="jobs.loading" class="mp-note">正在读取任务…</div>
        <div v-else-if="!jobs.list.length" class="mp-note">暂无导入导出任务。</div>
        <div v-else class="aa-task-list">
          <article v-for="item in jobs.list" :key="`${item.jobType}-${item.id}`" class="aa-task-card">
            <div>
              <strong>{{ item.jobType === 'IMPORT' ? '导入' : '导出' }} · {{ item.importType || item.exportType }}</strong>
              <p class="mp-note">状态 {{ item.status }} · 任务 #{{ item.id }} · {{ item.createdAt || '-' }}</p>
              <p v-if="item.errorMessage" class="aa-task-error">{{ item.errorMessage }}</p>
            </div>
            <div class="aa-task-actions">
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
      </AppSectionCard>
    </div>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入学籍名册"
      template-name="学籍导入模板.xlsx"
      :required-fields="['学号', '姓名', '班级']"
      :preview-fields="['studentNo', 'realName', 'className', 'initialStatus']"
      :download-template-fn="() => academicAffairsApi.downloadRosterImportTemplate()"
      :upload-fn="uploadAuthoritative"
      :confirm-fn="confirmAuthoritative"
      :download-errors-fn="({ rows, errors }) => academicAffairsApi.downloadRosterImportErrors(rows, errors)"
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
import { AppSectionCard, AppConfirmDialog, AppSelect } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = {
  NORMAL: '正常', PENDING_REGISTER: '待注册', REGISTERED: '在籍注册', UNREGISTERED: '未注册',
  SUSPENDED: '休学', RETAINED: '留级', WITHDRAWN: '退学', TRANSFER_SCHOOL: '转学',
  GRADUATED: '毕业', COMPLETED: '结业', INCOMPLETE: '肄业'
}

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

export default {
  name: 'AaRosterImportExportView',
  components: { ModulePageShell, AppButton, AppSectionCard, AppExcelImportDrawer, AppConfirmDialog, AppSelect },
  props: { ctx: { type: Object, required: true } },
  computed: {
    statusOptions() {
      return Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))
    }
  },
  data() {
    return {
      academicAffairsApi,
      importVisible: false,
      currentImportJob: null,
      exporting: false,
      exportDialog: { visible: false },
      exportFilters: { keyword: '', status: '' },
      jobs: { list: [], total: 0, loading: false }
    }
  },
  mounted() {
    this.loadJobs()
  },
  methods: {
    async uploadAuthoritative(file) {
      const res = await academicFileExchangeApi.uploadRosterImport(file)
      if (res.code !== 0) return res
      this.currentImportJob = { id: res.data.id, version: res.data.version }
      const preview = res.data.preview || {}
      return {
        code: 0,
        message: res.message,
        data: {
          total: preview.totalRows ?? res.data.totalRows ?? 0,
          validRows: preview.validRows ?? res.data.validRows ?? 0,
          invalidRows: preview.invalidRows ?? res.data.invalidRows ?? 0,
          passed: (preview.invalidRows ?? res.data.invalidRows ?? 0) === 0,
          rows: preview.rows || [],
          errors: preview.errors || [],
          jobId: res.data.id,
          expectedVersion: res.data.version
        }
      }
    },
    async confirmAuthoritative() {
      if (!this.currentImportJob?.id) return { code: 1, message: '导入任务已丢失，请重新上传预检' }
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
    async loadJobs() {
      this.jobs.loading = true
      const res = await academicFileExchangeApi.listJobs({ page: 1, pageSize: 50 })
      this.jobs.loading = false
      if (res.code !== 0) {
        toast.error(res.message || '任务读取失败')
        return
      }
      this.jobs.list = res.data.list || []
      this.jobs.total = res.data.total || 0
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
      const reason = window.prompt('请输入撤销原因（不少于 5 个字）')
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
