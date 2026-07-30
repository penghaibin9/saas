<template>
  <ModulePageShell
    title="数据交换任务中心"
    subtitle="统一查看导入、迁移、错误回执、初始凭据与导出任务；刷新页面任务不会丢失"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="exchange-page">
      <section class="hero-panel">
        <div>
          <h3>学校自助处理导入导出</h3>
          <p>导入确认只使用服务器保存的任务与版本，不再信任前端回传 Excel 行数据。</p>
        </div>
        <div class="hero-actions">
          <RouterLink class="link-button" to="/admin/system/identity-import/students">学生导入</RouterLink>
          <RouterLink class="link-button" to="/admin/system/identity-import/teachers">教师导入</RouterLink>
          <RouterLink class="link-button secondary" to="/admin/system/migration">老系统迁移</RouterLink>
        </div>
      </section>

      <section class="summary-grid">
        <article><strong>{{ summary.total }}</strong><span>全部任务</span></article>
        <article><strong>{{ summary.pending }}</strong><span>待处理</span></article>
        <article><strong>{{ summary.failed }}</strong><span>异常任务</span></article>
        <article><strong>{{ summary.receipts }}</strong><span>可下载回执</span></article>
      </section>

      <section class="toolbar">
        <select v-model="filters.jobType" @change="search">
          <option value="">全部类型</option>
          <option value="IMPORT">导入任务</option>
          <option value="EXPORT">导出与回执</option>
        </select>
        <select v-model="filters.status" @change="search">
          <option value="">全部状态</option>
          <option value="VALIDATED">待确认</option>
          <option value="VALIDATION_FAILED">预检失败</option>
          <option value="CONFIRMING">确认中</option>
          <option value="SUCCEEDED">已完成</option>
          <option value="FAILED">失败</option>
          <option value="EXPIRED">已过期</option>
          <option value="REVOKED">已撤销</option>
        </select>
        <input v-model.trim="filters.keyword" placeholder="任务类型 / 批次号" @keyup.enter="search">
        <button class="primary" :disabled="loading" @click="search">查询</button>
        <button :disabled="loading" @click="reset">重置</button>
      </section>

      <div v-if="error" class="state error-state">
        <strong>任务加载失败</strong>
        <span>{{ error }}</span>
        <button @click="load">重新加载</button>
      </div>
      <div v-else-if="loading" class="state">正在读取真实任务记录…</div>
      <div v-else-if="!rows.length" class="state">
        <strong>暂无数据交换任务</strong>
        <span>从学生导入、教师导入或老系统迁移入口开始后，任务会自动出现在这里。</span>
      </div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>任务</th>
              <th>状态</th>
              <th>数据量</th>
              <th>文件与时效</th>
              <th>创建时间</th>
              <th class="action-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="`${row.jobType}-${row.id}`">
              <td>
                <div class="task-title">{{ taskLabel(row) }}</div>
                <div class="muted">{{ row.jobType === 'IMPORT' ? `导入 #${row.id}` : `导出 #${row.id}` }}</div>
              </td>
              <td><span class="status-tag" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span></td>
              <td>
                <template v-if="row.jobType === 'IMPORT'">
                  <div>总计 {{ row.totalRows || 0 }}</div>
                  <div class="muted">有效 {{ row.validRows || 0 }} · 错误 {{ row.invalidRows || 0 }}</div>
                </template>
                <template v-else>
                  <div>{{ row.rowCount || 0 }} 行</div>
                  <div class="muted">已下载 {{ row.downloadedCount || 0 }} 次</div>
                </template>
              </td>
              <td>
                <div>{{ row.jobType === 'IMPORT' ? sourceFileLabel(row) : exportFileLabel(row) }}</div>
                <div class="muted">{{ expiryLabel(row) }}</div>
              </td>
              <td>{{ formatTime(row.createdAt) }}</td>
              <td class="actions">
                <button
                  v-if="canConfirm(row)"
                  class="primary small"
                  :disabled="busyKey === keyOf(row)"
                  @click="confirmRow(row)"
                >确认导入</button>
                <button
                  v-if="canDownload(row)"
                  class="small"
                  :disabled="busyKey === keyOf(row)"
                  @click="downloadRow(row)"
                >下载文件</button>
                <button
                  v-if="canRevoke(row)"
                  class="small danger"
                  :disabled="busyKey === keyOf(row)"
                  @click="revokeRow(row)"
                >撤销</button>
                <span v-if="!canConfirm(row) && !canDownload(row) && !canRevoke(row)" class="muted">无需操作</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer v-if="pagination.total > pagination.pageSize" class="pagination">
        <button :disabled="pagination.page <= 1 || loading" @click="turnPage(-1)">上一页</button>
        <span>第 {{ pagination.page }} 页 · 共 {{ pagination.total }} 条</span>
        <button
          :disabled="pagination.page * pagination.pageSize >= pagination.total || loading"
          @click="turnPage(1)"
        >下一页</button>
      </footer>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { toast } from '@/utils/toast'
import { dataExchangeApi } from '@/modules/system/api/dataExchange.api'

const EMPTY_FILTERS = () => ({ jobType: '', status: '', keyword: '' })

export default {
  name: 'SystemDataExchangeView',
  components: { ModulePageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false,
      error: '',
      rows: [],
      busyKey: '',
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 20, total: 0 }
    }
  },
  computed: {
    summary() {
      const rows = this.rows || []
      return {
        total: this.pagination.total,
        pending: rows.filter((row) => ['VALIDATED', 'CONFIRMING', 'CREATED', 'RUNNING'].includes(row.status)).length,
        failed: rows.filter((row) => ['VALIDATION_FAILED', 'FAILED'].includes(row.status)).length,
        receipts: rows.filter((row) => row.jobType === 'EXPORT' && row.status === 'SUCCEEDED').length
      }
    }
  },
  created() { this.load() },
  methods: {
    keyOf(row) { return `${row.jobType}-${row.id}` },
    taskLabel(row) {
      const labels = {
        IDENTITY_STUDENT: '学生导入与账号开通',
        IDENTITY_TEACHER: '教师导入',
        IMPORT_ERROR_RECEIPT: '导入错误回执',
        INITIAL_CREDENTIAL_RECEIPT: '初始账号凭据回执'
      }
      return labels[row.importType || row.exportType] || row.importType || row.exportType || '数据交换任务'
    },
    statusLabel(status) {
      return {
        VALIDATED: '待确认', VALIDATION_FAILED: '预检失败', CONFIRMING: '确认中',
        CREATED: '待生成', RUNNING: '生成中', SUCCEEDED: '已完成', FAILED: '失败',
        CANCELLED: '已取消', EXPIRED: '已过期', REVOKED: '已撤销'
      }[status] || status || '未知'
    },
    statusClass(status) {
      if (status === 'SUCCEEDED') return 'success'
      if (['VALIDATED', 'CONFIRMING', 'CREATED', 'RUNNING'].includes(status)) return 'warning'
      if (['VALIDATION_FAILED', 'FAILED'].includes(status)) return 'danger'
      return 'neutral'
    },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    expiryLabel(row) {
      if (!row.expiresAt) return '无单独有效期'
      if (['EXPIRED', 'REVOKED'].includes(row.status)) return this.statusLabel(row.status)
      return `有效至 ${this.formatTime(row.expiresAt)}`
    },
    sourceFileLabel(row) {
      if (row.sourceFileId) return `原始文件 #${row.sourceFileId}`
      return '历史 adapter 任务'
    },
    exportFileLabel(row) {
      if (row.fileObjectId) return `文件 #${row.fileObjectId}`
      return '文件尚未生成'
    },
    canConfirm(row) {
      return row.jobType === 'IMPORT' && row.status === 'VALIDATED' && Number(row.invalidRows || 0) === 0
    },
    canDownload(row) {
      return row.jobType === 'EXPORT' && row.status === 'SUCCEEDED' && !!row.fileObjectId
    },
    canRevoke(row) {
      return row.jobType === 'EXPORT' && row.status === 'SUCCEEDED'
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await dataExchangeApi.list({
          ...this.filters,
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
        this.rows = data.list || []
        this.pagination.total = Number(data.total || 0)
      } catch (error) {
        this.error = error.message || '数据交换任务加载失败'
        this.rows = []
      } finally {
        this.loading = false
      }
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.search()
    },
    turnPage(step) {
      this.pagination.page += step
      this.load()
    },
    async confirmRow(row) {
      if (!window.confirm('确认后将按服务器预检结果整批写入，是否继续？')) return
      this.busyKey = this.keyOf(row)
      try {
        await dataExchangeApi.confirmImport(row.id, row.version)
        toast.success('导入任务已确认完成')
        await this.load()
      } catch (error) {
        toast.error(error.message || '确认导入失败')
      } finally {
        this.busyKey = ''
      }
    },
    async downloadRow(row) {
      this.busyKey = this.keyOf(row)
      try {
        await dataExchangeApi.downloadExport(row)
        toast.success('安全下载已开始；一次性票据已消耗')
        await this.load()
      } catch (error) {
        toast.error(error.message || '下载失败')
      } finally {
        this.busyKey = ''
      }
    },
    async revokeRow(row) {
      const reason = window.prompt('请输入撤销原因（不少于 5 个字）')
      if (!reason) return
      this.busyKey = this.keyOf(row)
      try {
        await dataExchangeApi.revokeExport(row.id, row.version, reason)
        toast.success('导出文件已撤销')
        await this.load()
      } catch (error) {
        toast.error(error.message || '撤销失败')
      } finally {
        this.busyKey = ''
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.exchange-page { display: grid; gap: 16px; }
.hero-panel { display: flex; justify-content: space-between; gap: 20px; align-items: center; padding: 22px; border: 1px solid #dbe7f5; border-radius: 16px; background: linear-gradient(135deg, #f5f9ff, #ffffff); }
.hero-panel h3 { margin: 0 0 8px; font-size: 20px; }
.hero-panel p { margin: 0; color: #64748b; }
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.link-button, button { border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 13px; background: #fff; color: #334155; cursor: pointer; text-decoration: none; font-size: 14px; }
.link-button:not(.secondary), button.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
button:disabled { opacity: .55; cursor: not-allowed; }
button.small { padding: 6px 10px; font-size: 13px; }
button.danger { color: #b91c1c; border-color: #fecaca; background: #fff7f7; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.summary-grid article { display: grid; gap: 4px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
.summary-grid strong { font-size: 25px; color: #0f172a; }
.summary-grid span { color: #64748b; }
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
.toolbar select, .toolbar input { min-height: 38px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0 10px; background: #fff; }
.toolbar input { min-width: 220px; flex: 1; }
.state { min-height: 180px; display: grid; place-content: center; gap: 8px; text-align: center; border: 1px dashed #cbd5e1; border-radius: 12px; color: #64748b; }
.error-state { color: #b91c1c; background: #fff7f7; }
.table-wrap { overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
table { width: 100%; border-collapse: collapse; min-width: 900px; }
th, td { padding: 13px 14px; text-align: left; border-bottom: 1px solid #eef2f7; vertical-align: middle; }
th { position: sticky; top: 0; background: #f8fafc; color: #475569; font-size: 13px; }
tr:last-child td { border-bottom: none; }
.task-title { font-weight: 600; color: #0f172a; }
.muted { color: #94a3b8; font-size: 12px; margin-top: 3px; }
.status-tag { display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 999px; font-size: 12px; }
.status-tag.success { color: #047857; background: #ecfdf5; }
.status-tag.warning { color: #a16207; background: #fffbeb; }
.status-tag.danger { color: #b91c1c; background: #fef2f2; }
.status-tag.neutral { color: #475569; background: #f1f5f9; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.action-col { width: 220px; }
.pagination { display: flex; justify-content: flex-end; align-items: center; gap: 12px; color: #64748b; }
@media (max-width: 900px) {
  .hero-panel { align-items: flex-start; flex-direction: column; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
