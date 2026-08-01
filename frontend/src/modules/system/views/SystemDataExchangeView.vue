<template>
  <ModulePageShell
    title="数据交换任务中心"
    subtitle="统一治理导入、迁移、错误回执、初始凭据和导出任务；所有写操作以服务器任务与版本为准"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="exchange-page">
      <section class="hero-panel">
        <div>
          <div class="eyebrow">学校数据交换控制台</div>
          <h3>先看结论，再处理任务</h3>
          <p>汇总来自独立数据库统计，不受当前页影响；导入确认只提交任务编号、版本和幂等键。</p>
        </div>
        <div class="hero-actions">
          <RouterLink class="link-button" to="/admin/system/identity-import/students">学生导入</RouterLink>
          <RouterLink class="link-button" to="/admin/system/identity-import/teachers">教师导入</RouterLink>
          <RouterLink class="link-button secondary" to="/admin/system/migration">老系统迁移</RouterLink>
        </div>
      </section>

      <section class="view-bar">
        <div>
          <label>任务视图</label>
          <div class="segmented">
            <button
              v-for="item in visibilityOptions"
              :key="item.value"
              :class="{ active: visibility === item.value }"
              :disabled="loading"
              @click="changeVisibility(item.value)"
            >{{ item.label }}</button>
          </div>
        </div>
        <div v-if="visibility === 'MODULE'" class="module-select">
          <label for="module-code">业务模块</label>
          <select id="module-code" v-model="moduleCode" :disabled="loading" @change="search">
            <option v-for="code in allowedModules" :key="code" :value="code">{{ moduleLabel(code) }}</option>
          </select>
        </div>
        <div class="view-note">
          <strong>{{ visibilityLabel }}</strong>
          <span>{{ visibilityDescription }}</span>
        </div>
      </section>

      <section class="summary-grid" aria-label="数据交换汇总">
        <article>
          <span>全部任务</span>
          <strong>{{ summary.total }}</strong>
          <small>导入 {{ summary.imports }} · 导出 {{ summary.exports }}</small>
        </article>
        <article>
          <span>待处理</span>
          <strong>{{ summary.pending }}</strong>
          <small>待确认或生成中</small>
        </article>
        <article>
          <span>扫描解析中</span>
          <strong>{{ summary.scanning }}</strong>
          <small>未通过安全门前不能确认</small>
        </article>
        <article :class="{ alert: summary.failed > 0 }">
          <span>异常任务</span>
          <strong>{{ summary.failed }}</strong>
          <small>预检或执行失败</small>
        </article>
        <article :class="{ alert: summary.expired > 0 }">
          <span>已过期</span>
          <strong>{{ summary.expired }}</strong>
          <small>需重新发起或上传</small>
        </article>
        <article>
          <span>可下载回执</span>
          <strong>{{ summary.receipts }}</strong>
          <small>均使用短时一次性票据</small>
        </article>
      </section>

      <section class="toolbar">
        <select v-model="filters.jobType" @change="search">
          <option value="">全部类型</option>
          <option value="IMPORT">导入任务</option>
          <option value="EXPORT">导出与回执</option>
        </select>
        <select v-model="filters.status" @change="search">
          <option value="">全部状态</option>
          <option value="SCANNING">安全扫描中</option>
          <option value="PARSING">解析中</option>
          <option value="VALIDATED">待确认</option>
          <option value="VALIDATION_FAILED">预检失败</option>
          <option value="CONFIRMING">确认中</option>
          <option value="CREATED">待生成</option>
          <option value="RUNNING">生成中</option>
          <option value="SUCCEEDED">已完成</option>
          <option value="FAILED">失败</option>
          <option value="CANCELLED">已取消</option>
          <option value="EXPIRED">已过期</option>
          <option value="REVOKED">已撤销</option>
        </select>
        <input v-model.trim="filters.keyword" placeholder="任务类型、批次号、模块或操作人" @keyup.enter="search">
        <button class="primary" :disabled="loading" @click="search">查询</button>
        <button :disabled="loading" @click="reset">重置</button>
      </section>

      <div v-if="error" class="state error-state">
        <strong>任务加载失败</strong>
        <span>{{ error }}</span>
        <button @click="load">重新加载</button>
      </div>
      <div v-else-if="loading" class="state">正在读取真实任务记录与独立汇总…</div>
      <div v-else-if="!rows.length" class="state">
        <strong>当前视图暂无任务</strong>
        <span>可切换本人、模块或全校视图，或者从学生导入、教师导入、老系统迁移入口创建任务。</span>
      </div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>任务</th>
              <th>状态</th>
              <th>数据量</th>
              <th>文件与时效</th>
              <th>创建人 / 时间</th>
              <th class="action-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="keyOf(row)">
              <td>
                <button class="task-link" @click="openDetail(row)">{{ taskLabel(row) }}</button>
                <div class="muted">{{ moduleLabel(row.moduleCode) }} · {{ row.jobType === 'IMPORT' ? `导入 #${row.id}` : `导出 #${row.id}` }}</div>
                <div v-if="row.strongSensitive" class="sensitive-mark">强敏感 · 一次性凭据回执</div>
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
              <td>
                <div>{{ row.operatorName || '系统任务' }}</div>
                <div class="muted">{{ formatTime(row.createdAt) }}</div>
              </td>
              <td class="actions">
                <button class="small" @click="openDetail(row)">详情</button>
                <button
                  v-if="canConfirm(row)"
                  class="primary small"
                  :disabled="busyKey === keyOf(row)"
                  @click="openAction('confirm', row)"
                >确认导入</button>
                <button
                  v-if="row.retryable"
                  class="small"
                  :disabled="busyKey === keyOf(row)"
                  @click="openAction('retry', row)"
                >重试扫描</button>
                <button
                  v-if="row.cancellable"
                  class="small danger-quiet"
                  :disabled="busyKey === keyOf(row)"
                  @click="openAction('cancel', row)"
                >取消</button>
                <button
                  v-if="canDownload(row)"
                  class="small"
                  :class="{ sensitive: row.strongSensitive }"
                  :disabled="busyKey === keyOf(row)"
                  @click="downloadRow(row)"
                >{{ row.strongSensitive ? '安全下载' : '下载文件' }}</button>
                <button
                  v-if="canRevoke(row)"
                  class="small danger"
                  :disabled="busyKey === keyOf(row)"
                  @click="openAction('revoke', row)"
                >撤销</button>
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

    <div v-if="detail.open" class="modal-mask" @click.self="closeDetail">
      <section class="modal-card detail-card" role="dialog" aria-modal="true" aria-label="任务详情">
        <header class="modal-header">
          <div>
            <div class="eyebrow">{{ detail.item?.jobType === 'IMPORT' ? '导入任务详情' : '导出任务详情' }}</div>
            <h3>{{ taskLabel(detail.item || {}) }}</h3>
          </div>
          <button class="icon-button" aria-label="关闭" @click="closeDetail">×</button>
        </header>
        <div v-if="detail.loading" class="state compact">正在读取任务详情…</div>
        <div v-else-if="detail.error" class="state compact error-state">{{ detail.error }}</div>
        <div v-else-if="detail.item" class="detail-body">
          <div v-if="detail.item.strongSensitive" class="credential-warning">
            <strong>这是初始账号凭据回执</strong>
            <span>强敏感、24 小时有效、一次性下载。请仅交给授权人员，下载后立即转入学校安全保管流程。</span>
          </div>
          <section class="detail-grid">
            <article><span>任务编号</span><strong>#{{ detail.item.id }}</strong></article>
            <article><span>状态</span><strong>{{ statusLabel(detail.item.status) }}</strong></article>
            <article><span>模块</span><strong>{{ moduleLabel(detail.item.moduleCode) }}</strong></article>
            <article><span>版本</span><strong>v{{ detail.item.version }}</strong></article>
            <article><span>创建时间</span><strong>{{ formatTime(detail.item.createdAt) }}</strong></article>
            <article><span>有效期</span><strong>{{ expiryLabel(detail.item) }}</strong></article>
          </section>

          <section v-if="detail.item.jobType === 'IMPORT'" class="detail-section">
            <h4>原始文件与安全状态</h4>
            <div v-if="detail.item.sourceFile" class="kv-list">
              <div><span>文件</span><strong>{{ detail.item.sourceFile.fileName || `#${detail.item.sourceFile.id}` }}</strong></div>
              <div><span>文件状态</span><strong>{{ detail.item.sourceFile.status || '未知' }}</strong></div>
              <div><span>扫描状态</span><strong>{{ detail.item.sourceFile.scanStatus || '未知' }}</strong></div>
              <div><span>安全级别</span><strong>{{ detail.item.sourceFile.securityLevel || '未知' }}</strong></div>
            </div>
            <div v-else class="muted">该历史 adapter 任务没有独立源文件投影。</div>
          </section>

          <section v-if="detail.item.jobType === 'IMPORT'" class="detail-section">
            <div class="section-title-row">
              <h4>预检结果与错误行</h4>
              <span>{{ detail.item.errorCount || 0 }} 条错误</span>
            </div>
            <div class="count-row">
              <span>总计 {{ detail.item.totalRows || 0 }}</span>
              <span>有效 {{ detail.item.validRows || 0 }}</span>
              <span>错误 {{ detail.item.invalidRows || 0 }}</span>
              <span>已确认 {{ detail.item.confirmedRows || 0 }}</span>
            </div>
            <div v-if="detail.errorsLoading" class="muted">正在读取错误明细…</div>
            <div v-else-if="detail.errors.length" class="error-table-wrap">
              <table class="error-table">
                <thead><tr><th>工作表</th><th>行</th><th>字段</th><th>错误</th></tr></thead>
                <tbody>
                  <tr v-for="item in detail.errors" :key="item.id">
                    <td>{{ item.sheetName || '—' }}</td>
                    <td>{{ item.rowNo || '—' }}</td>
                    <td>{{ item.fieldCode || '—' }}</td>
                    <td>{{ item.message }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="muted">没有错误行。</div>
          </section>

          <section class="detail-section">
            <h4>Adapter 与执行时间线</h4>
            <div v-if="detail.item.adapter" class="adapter-line">
              {{ detail.item.adapter.type }} · {{ detail.item.adapter.ref }}
            </div>
            <ol v-if="detail.item.timeline?.length" class="timeline">
              <li v-for="event in detail.item.timeline" :key="`${event.event}-${event.at}`">
                <span>{{ timelineLabel(event.event) }}</span><time>{{ formatTime(event.at) }}</time>
              </li>
            </ol>
            <div v-else class="muted">暂无更多执行事件。</div>
          </section>

          <section v-if="detail.item.errorMessage" class="detail-section error-message">
            <h4>任务异常</h4>
            <p>{{ detail.item.errorMessage }}</p>
          </section>
        </div>
        <footer class="modal-footer">
          <button @click="closeDetail">关闭</button>
        </footer>
      </section>
    </div>

    <div v-if="actionDialog.open" class="modal-mask" @click.self="closeAction">
      <section class="modal-card action-card" role="dialog" aria-modal="true" :aria-label="actionDialog.title">
        <header class="modal-header">
          <div>
            <div class="eyebrow">高风险操作确认</div>
            <h3>{{ actionDialog.title }}</h3>
          </div>
          <button class="icon-button" aria-label="关闭" @click="closeAction">×</button>
        </header>
        <div class="action-content">
          <p>{{ actionDialog.description }}</p>
          <div class="impact-box">
            <span>任务</span><strong>{{ taskLabel(actionDialog.row || {}) }} #{{ actionDialog.row?.id }}</strong>
            <span>当前版本</span><strong>v{{ actionDialog.row?.version }}</strong>
            <span>当前状态</span><strong>{{ statusLabel(actionDialog.row?.status) }}</strong>
          </div>
          <label v-if="actionDialog.requiresReason" class="reason-field">
            <span>操作原因（不少于 5 个字）</span>
            <textarea v-model.trim="actionDialog.reason" rows="4" maxlength="500" placeholder="说明为什么需要执行此操作，记录将进入审计"></textarea>
          </label>
        </div>
        <footer class="modal-footer">
          <button :disabled="actionDialog.submitting" @click="closeAction">取消</button>
          <button
            class="primary"
            :disabled="actionDialog.submitting || (actionDialog.requiresReason && actionDialog.reason.length < 5)"
            @click="submitAction"
          >{{ actionDialog.submitting ? '正在执行…' : actionDialog.confirmLabel }}</button>
        </footer>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { toast } from '@/utils/toast'
import { dataExchangeApi } from '@/modules/system/api/dataExchange.api'

const EMPTY_FILTERS = () => ({ jobType: '', status: '', keyword: '' })
const EMPTY_SUMMARY = () => ({ total: 0, imports: 0, exports: 0, pending: 0, scanning: 0, failed: 0, expired: 0, receipts: 0 })
const EMPTY_DETAIL = () => ({ open: false, loading: false, error: '', item: null, errors: [], errorsLoading: false })
const EMPTY_ACTION = () => ({
  open: false,
  type: '',
  title: '',
  description: '',
  confirmLabel: '确认执行',
  requiresReason: false,
  reason: '',
  row: null,
  submitting: false
})

export default {
  name: 'SystemDataExchangeView',
  components: { ModulePageShell },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false,
      error: '',
      rows: [],
      summary: EMPTY_SUMMARY(),
      busyKey: '',
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 20, total: 0 },
      visibility: 'OWN',
      moduleCode: '',
      allowedVisibilities: ['OWN'],
      allowedModules: [],
      detail: EMPTY_DETAIL(),
      actionDialog: EMPTY_ACTION()
    }
  },
  computed: {
    visibilityOptions() {
      const labels = { OWN: '本人任务', MODULE: '本模块任务', TENANT: '全校任务' }
      return this.allowedVisibilities.map((value) => ({ value, label: labels[value] || value }))
    },
    visibilityLabel() {
      return { OWN: '仅本人创建', MODULE: `模块：${this.moduleLabel(this.moduleCode)}`, TENANT: '全校授权视图' }[this.visibility]
    },
    visibilityDescription() {
      return {
        OWN: '只显示由当前账号创建的导入与导出任务。',
        MODULE: '只显示当前有管理职责的业务模块任务。',
        TENANT: '显示本校全部任务，不包含其他学校数据。'
      }[this.visibility]
    }
  },
  created() { this.load() },
  methods: {
    keyOf(row) { return `${row.jobType}-${row.id}` },
    viewContext() { return { visibility: this.visibility, moduleCode: this.visibility === 'MODULE' ? this.moduleCode : '' } },
    taskLabel(row) {
      const labels = {
        IDENTITY_STUDENT: '学生导入与账号开通',
        IDENTITY_TEACHER: '教师导入',
        ACADEMIC_ROSTER: '教务名册导入',
        ACADEMIC_GRADE: '教务成绩导入',
        ACADEMIC_SCHEDULE: '教务排课导入',
        IMPORT_ERROR_RECEIPT: '导入错误回执',
        INITIAL_CREDENTIAL_RECEIPT: '初始账号凭据回执'
      }
      return labels[row.importType || row.exportType] || row.importType || row.exportType || '数据交换任务'
    },
    moduleLabel(code) {
      return { SYSTEM: '系统管理', ACADEMIC_AFFAIRS: '教务中心' }[code] || code || '未标注模块'
    },
    statusLabel(status) {
      return {
        SCANNING: '安全扫描中', PARSING: '解析中', VALIDATED: '待确认',
        VALIDATION_FAILED: '预检失败', CONFIRMING: '确认中', CREATED: '待生成',
        RUNNING: '生成中', SUCCEEDED: '已完成', FAILED: '失败', CANCELLED: '已取消',
        EXPIRED: '已过期', REVOKED: '已撤销'
      }[status] || status || '未知'
    },
    statusClass(status) {
      if (status === 'SUCCEEDED') return 'success'
      if (['SCANNING', 'PARSING', 'VALIDATED', 'CONFIRMING', 'CREATED', 'RUNNING'].includes(status)) return 'warning'
      if (['VALIDATION_FAILED', 'FAILED'].includes(status)) return 'danger'
      return 'neutral'
    },
    timelineLabel(event) {
      return {
        CREATED: '任务创建', PARSING_STARTED: '开始解析', PARSING_FINISHED: '解析完成',
        CONFIRMED: '确认完成', FINISHED: '文件生成完成', REVOKED: '已撤销'
      }[event] || event
    },
    formatTime(value) { return value ? String(value).replace('T', ' ').replace('Z', '').slice(0, 19) : '—' },
    expiryLabel(row) {
      if (!row.expiresAt) return '无单独有效期'
      if (['EXPIRED', 'REVOKED'].includes(row.status)) return this.statusLabel(row.status)
      return `有效至 ${this.formatTime(row.expiresAt)}`
    },
    sourceFileLabel(row) { return row.sourceFileId ? `原始文件 #${row.sourceFileId}` : '历史 adapter 任务' },
    exportFileLabel(row) { return row.fileObjectId ? `文件 #${row.fileObjectId}` : '文件尚未生成' },
    canConfirm(row) {
      return row.jobType === 'IMPORT' && row.status === 'VALIDATED' && Number(row.invalidRows || 0) === 0
    },
    canDownload(row) {
      return row.jobType === 'EXPORT' && row.status === 'SUCCEEDED' && !!row.fileObjectId && row.downloadable !== false
    },
    canRevoke(row) { return row.jobType === 'EXPORT' && row.status === 'SUCCEEDED' },
    applyAccessContext(data) {
      if (Array.isArray(data.allowedVisibilities) && data.allowedVisibilities.length) {
        this.allowedVisibilities = data.allowedVisibilities
      }
      if (Array.isArray(data.allowedModules)) this.allowedModules = data.allowedModules
      if (!this.allowedVisibilities.includes(this.visibility)) {
        this.visibility = data.defaultVisibility || this.allowedVisibilities[0] || 'OWN'
      }
      if (this.visibility === 'MODULE' && !this.allowedModules.includes(this.moduleCode)) {
        this.moduleCode = this.allowedModules[0] || ''
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const context = this.viewContext()
        const [summary, data] = await Promise.all([
          dataExchangeApi.summary(context),
          dataExchangeApi.list({
            ...this.filters,
            ...context,
            page: this.pagination.page,
            pageSize: this.pagination.pageSize
          })
        ])
        this.applyAccessContext(summary)
        this.applyAccessContext(data)
        this.summary = { ...EMPTY_SUMMARY(), ...summary }
        this.rows = data.list || []
        this.pagination.total = Number(data.total || 0)
      } catch (error) {
        this.error = error.message || '数据交换任务加载失败'
        this.rows = []
        this.summary = EMPTY_SUMMARY()
      } finally {
        this.loading = false
      }
    },
    changeVisibility(value) {
      this.visibility = value
      if (value === 'MODULE' && !this.moduleCode) this.moduleCode = this.allowedModules[0] || ''
      this.search()
    },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.search() },
    turnPage(step) { this.pagination.page += step; this.load() },
    async openDetail(row) {
      this.detail = { ...EMPTY_DETAIL(), open: true, loading: true, item: row }
      try {
        const context = this.viewContext()
        const item = row.jobType === 'IMPORT'
          ? await dataExchangeApi.getImport(row.id, context)
          : await dataExchangeApi.getExport(row.id, context)
        this.detail.item = item
        this.detail.loading = false
        if (item.jobType === 'IMPORT' && Number(item.errorCount || 0) > 0) {
          this.detail.errorsLoading = true
          try {
            const errors = await dataExchangeApi.getImportErrors(row.id, { ...context, page: 1, pageSize: 100 })
            this.detail.errors = errors.list || []
          } finally {
            this.detail.errorsLoading = false
          }
        }
      } catch (error) {
        this.detail.loading = false
        this.detail.error = error.message || '任务详情加载失败'
      }
    },
    closeDetail() { if (!this.detail.loading) this.detail = EMPTY_DETAIL() },
    openAction(type, row) {
      const config = {
        confirm: {
          title: '确认整批导入',
          description: '系统将按服务器保存的预检结果执行整批写入。重复点击会由幂等键和任务租约阻止重复业务写入。',
          confirmLabel: '确认并执行', requiresReason: false
        },
        retry: {
          title: '重试安全扫描或解析',
          description: '仅重新执行可安全重放的身份文件扫描与解析；业务数据错误不会被伪装为重试成功。',
          confirmLabel: '确认重试', requiresReason: false
        },
        cancel: {
          title: '取消导入任务',
          description: '仅可取消尚未进入不可逆业务写入的任务。取消原因会写入任务记录与审计。',
          confirmLabel: '确认取消', requiresReason: true
        },
        revoke: {
          title: '撤销导出文件',
          description: '撤销后现有下载票据立即失效，任务仍保留审计元数据。',
          confirmLabel: '确认撤销', requiresReason: true
        }
      }[type]
      this.actionDialog = { ...EMPTY_ACTION(), ...config, open: true, type, row }
    },
    closeAction() { if (!this.actionDialog.submitting) this.actionDialog = EMPTY_ACTION() },
    async submitAction() {
      const dialog = this.actionDialog
      const row = dialog.row
      if (!row) return
      dialog.submitting = true
      this.busyKey = this.keyOf(row)
      try {
        if (dialog.type === 'confirm') {
          await dataExchangeApi.confirmImport(row.id, row.version)
          toast.success('导入任务已确认完成')
        } else if (dialog.type === 'retry') {
          await dataExchangeApi.retryImport(row.id, row.version)
          toast.success('任务已重新进入安全扫描队列')
        } else if (dialog.type === 'cancel') {
          await dataExchangeApi.cancelImport(row.id, row.version, dialog.reason)
          toast.success('导入任务已取消')
        } else if (dialog.type === 'revoke') {
          await dataExchangeApi.revokeExport(row.id, row.version, dialog.reason)
          toast.success('导出文件已撤销')
        }
        this.actionDialog = EMPTY_ACTION()
        await this.load()
      } catch (error) {
        toast.error(error.message || '操作失败')
      } finally {
        dialog.submitting = false
        this.busyKey = ''
      }
    },
    async downloadRow(row) {
      this.busyKey = this.keyOf(row)
      try {
        await dataExchangeApi.downloadExport(row)
        toast.success(row.strongSensitive ? '强敏感回执已通过一次性票据下载' : '安全下载已开始；一次性票据已消耗')
        await this.load()
      } catch (error) {
        toast.error(error.message || '下载失败')
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
.hero-panel { display: flex; justify-content: space-between; gap: 24px; align-items: center; padding: 24px; border: 1px solid #dbe7f5; border-radius: 18px; background: linear-gradient(135deg, #f2f7ff, #fff); }
.hero-panel h3 { margin: 4px 0 8px; font-size: 22px; color: #0f172a; }
.hero-panel p { max-width: 720px; margin: 0; color: #64748b; line-height: 1.65; }
.eyebrow { color: #2563eb; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.link-button, button { border: 1px solid #cbd5e1; border-radius: 9px; padding: 8px 13px; background: #fff; color: #334155; cursor: pointer; text-decoration: none; font-size: 14px; }
.link-button:not(.secondary), button.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
button:disabled { opacity: .55; cursor: not-allowed; }
.view-bar { display: grid; grid-template-columns: auto auto minmax(220px, 1fr); gap: 18px; align-items: end; padding: 16px; border: 1px solid #dbe5f0; border-radius: 14px; background: #fff; }
.view-bar label, .reason-field > span { display: block; margin-bottom: 7px; color: #64748b; font-size: 12px; font-weight: 600; }
.segmented { display: flex; padding: 3px; border-radius: 10px; background: #f1f5f9; }
.segmented button { border: 0; background: transparent; }
.segmented button.active { color: #1d4ed8; background: #fff; box-shadow: 0 1px 3px rgb(15 23 42 / 12%); }
.module-select select { min-height: 39px; min-width: 170px; border: 1px solid #cbd5e1; border-radius: 9px; padding: 0 10px; background: #fff; }
.view-note { display: grid; gap: 3px; justify-self: end; text-align: right; }
.view-note strong { color: #0f172a; }
.view-note span { color: #64748b; font-size: 12px; }
.summary-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.summary-grid article { display: grid; gap: 4px; min-height: 112px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 13px; background: #fff; }
.summary-grid article.alert { border-color: #fecaca; background: #fffafa; }
.summary-grid span { color: #64748b; font-size: 13px; }
.summary-grid strong { font-size: 27px; color: #0f172a; }
.summary-grid small { color: #94a3b8; line-height: 1.4; }
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
.toolbar select, .toolbar input { min-height: 38px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0 10px; background: #fff; }
.toolbar input { min-width: 260px; flex: 1; }
.state { min-height: 180px; display: grid; place-content: center; gap: 8px; text-align: center; border: 1px dashed #cbd5e1; border-radius: 12px; color: #64748b; }
.state.compact { min-height: 130px; }
.error-state { color: #b91c1c; background: #fff7f7; }
.table-wrap { overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
table { width: 100%; border-collapse: collapse; min-width: 1080px; }
th, td { padding: 13px 14px; text-align: left; border-bottom: 1px solid #eef2f7; vertical-align: middle; }
th { position: sticky; top: 0; background: #f8fafc; color: #475569; font-size: 13px; }
tr:last-child td { border-bottom: none; }
.task-link { border: 0; padding: 0; color: #0f172a; background: transparent; font-weight: 650; text-align: left; }
.task-link:hover { color: #2563eb; }
.muted { color: #94a3b8; font-size: 12px; margin-top: 3px; }
.sensitive-mark { width: fit-content; margin-top: 6px; padding: 3px 7px; border-radius: 999px; color: #9f1239; background: #fff1f2; font-size: 11px; font-weight: 650; }
.status-tag { display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 999px; font-size: 12px; }
.status-tag.success { color: #047857; background: #ecfdf5; }
.status-tag.warning { color: #b45309; background: #fffbeb; }
.status-tag.danger { color: #b91c1c; background: #fef2f2; }
.status-tag.neutral { color: #475569; background: #f1f5f9; }
.actions { display: flex; flex-wrap: wrap; gap: 7px; min-width: 260px; }
button.small { padding: 6px 9px; font-size: 12px; }
button.danger { color: #b91c1c; border-color: #fecaca; background: #fff7f7; }
button.danger-quiet { color: #9a3412; border-color: #fed7aa; background: #fffaf5; }
button.sensitive { color: #9f1239; border-color: #fecdd3; background: #fff1f2; }
.pagination { display: flex; justify-content: flex-end; align-items: center; gap: 12px; color: #64748b; }
.modal-mask { position: fixed; inset: 0; z-index: 1100; display: grid; place-items: center; padding: 24px; background: rgb(15 23 42 / 48%); }
.modal-card { width: min(680px, 100%); max-height: calc(100vh - 48px); overflow: hidden; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; border-radius: 18px; background: #fff; box-shadow: 0 24px 70px rgb(15 23 42 / 28%); }
.detail-card { width: min(920px, 100%); }
.modal-header, .modal-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 20px; border-bottom: 1px solid #e2e8f0; }
.modal-header h3 { margin: 4px 0 0; color: #0f172a; }
.modal-footer { justify-content: flex-end; border-top: 1px solid #e2e8f0; border-bottom: 0; }
.icon-button { border: 0; padding: 2px 8px; background: transparent; font-size: 26px; line-height: 1; }
.detail-body, .action-content { overflow-y: auto; padding: 20px; }
.credential-warning { display: grid; gap: 5px; margin-bottom: 16px; padding: 14px; border: 1px solid #fecdd3; border-radius: 12px; color: #9f1239; background: #fff1f2; }
.credential-warning span { font-size: 13px; line-height: 1.6; }
.detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.detail-grid article { display: grid; gap: 5px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 10px; }
.detail-grid span, .kv-list span, .impact-box span { color: #64748b; font-size: 12px; }
.detail-grid strong { font-size: 14px; overflow-wrap: anywhere; }
.detail-section { margin-top: 18px; padding-top: 18px; border-top: 1px solid #e2e8f0; }
.detail-section h4 { margin: 0 0 12px; color: #0f172a; }
.kv-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
.kv-list div { display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border-radius: 9px; background: #f8fafc; }
.section-title-row { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.section-title-row span { color: #64748b; font-size: 13px; }
.count-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.count-row span { padding: 5px 9px; border-radius: 999px; background: #f1f5f9; color: #475569; font-size: 12px; }
.error-table-wrap { max-height: 260px; overflow: auto; border: 1px solid #e2e8f0; border-radius: 10px; }
.error-table { min-width: 680px; }
.error-table th, .error-table td { padding: 9px 10px; font-size: 12px; }
.adapter-line { padding: 10px 12px; border-radius: 9px; color: #475569; background: #f8fafc; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.timeline { display: grid; gap: 8px; margin: 12px 0 0; padding-left: 22px; }
.timeline li { display: flex; justify-content: space-between; gap: 20px; color: #334155; }
.timeline time { color: #94a3b8; font-size: 12px; }
.error-message { color: #991b1b; }
.error-message p { margin: 0; padding: 12px; border-radius: 9px; background: #fef2f2; white-space: pre-wrap; }
.action-content > p { margin: 0 0 16px; color: #475569; line-height: 1.7; }
.impact-box { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 9px 16px; padding: 14px; border-radius: 12px; background: #f8fafc; }
.reason-field { display: block; margin-top: 16px; }
.reason-field textarea { width: 100%; resize: vertical; border: 1px solid #cbd5e1; border-radius: 9px; padding: 10px; font: inherit; box-sizing: border-box; }
@media (max-width: 1180px) { .summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 820px) {
  .hero-panel { align-items: flex-start; flex-direction: column; }
  .view-bar { grid-template-columns: 1fr; align-items: stretch; }
  .view-note { justify-self: start; text-align: left; }
  .summary-grid, .detail-grid, .kv-list { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 560px) { .summary-grid, .detail-grid, .kv-list { grid-template-columns: 1fr; } }
</style>
