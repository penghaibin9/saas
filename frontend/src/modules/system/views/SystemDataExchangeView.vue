<template>
  <SystemWorkspaceFrame title="数据交换任务" subtitle="找到任务，核对结果，再继续办理或安全下载。" :ctx="ctx">
    <template #actions>
      <button type="button" class="sw-btn" :disabled="locked" @click="refresh">刷新状态</button>
      <button v-if="rights.migration" type="button" class="sw-btn" :disabled="locked" @click="$router.push('/admin/system/migration')">老系统迁移</button>
      <button v-if="rights.upload" type="button" class="sw-btn" :disabled="locked" @click="$router.push('/admin/system/identity-import/students')">导入学生</button>
      <button v-if="rights.upload" type="button" class="sw-btn sw-btn--primary" :disabled="locked" @click="$router.push('/admin/system/identity-import/teachers')">导入教职工</button>
    </template>
    <div v-if="!rights.read" class="sw-card sw-state"><h2>当前身份不能查看数据交换任务</h2><p>请核对本人任务或模块任务的查看权限，不需要授予导入权限。</p></div>
    <template v-else>
      <section class="sw-card sw-pad dx-viewbar" aria-label="任务可见范围">
        <div><span class="sw-kicker">任务视图</span><div class="dx-segments">
          <button v-for="value in visibilityOptions" :key="value" type="button" :aria-pressed="state.view.visibility === value" :disabled="locked" @click="changeView(value)">{{ viewLabels[value] }}</button>
        </div></div>
        <label v-if="state.view.visibility === 'MODULE'" class="sw-field">业务模块<select class="sw-input" :value="state.view.moduleCode" :disabled="locked" @change="changeView('MODULE', $event.target.value)"><option v-for="code in state.access?.allowedModules || []" :key="code" :value="code">{{ moduleLabel(code) }}</option></select></label>
        <p class="sw-muted">{{ state.view.visibility === 'OWN' ? '只读取本人创建的任务' : state.view.visibility === 'MODULE' ? '只读取当前授权模块的任务' : '只读取本校授权任务' }}。查看、确认与下载分别鉴权。</p>
      </section>
      <section class="dx-metrics" aria-label="独立任务汇总" data-testid="exchange-summary">
        <article v-for="metric in metrics" :key="metric.key" class="sw-card"><span class="sw-muted">{{ metric.label }}</span><strong>{{ state.summary.loading ? '读取中' : taskCount(state.summary.data?.[metric.key]) }}</strong><small class="sw-muted">{{ metric.key === 'total' ? `导入 ${taskCount(state.summary.data?.imports)} · 导出 ${taskCount(state.summary.data?.exports)}` : metric.note }}</small></article>
      </section>
      <div v-if="state.summary.error" class="sw-alert sw-alert--warning" role="alert" data-testid="summary-error"><b>汇总未取得，任务清单仍可独立查看</b><p>{{ state.summary.error }}</p><button type="button" class="sw-btn sw-space" :disabled="locked" @click="controller.loadSummary()">重试汇总</button></div>
      <p class="sw-muted dx-summary-note">汇总统计当前授权视图，不随下方关键词和状态筛选变化；不同状态统计不应直接相加。扫描解析中 {{ taskCount(state.summary.data?.scanning) }} 项 · 已过期 {{ taskCount(state.summary.data?.expired) }} 项。</p>
      <div v-if="state.receipt" class="sw-alert" role="status" data-testid="exchange-receipt">{{ state.receipt }}</div>
      <div v-if="state.operationError || linkError" class="sw-alert sw-alert--error" role="alert">{{ linkError || state.operationError }}</div>

      <section v-if="state.detail.ref || state.detail.error" class="sw-card sw-pad sw-stack" data-testid="exchange-detail">
        <div class="sw-between"><div><span class="sw-kicker">当前任务 · {{ state.detail.ref?.jobType === 'EXPORT' ? '导出与回执' : '导入' }}</span><h2>{{ state.detail.item ? taskLabel(state.detail.item) : '任务详情' }}</h2></div>
          <div class="sw-row"><button type="button" class="sw-btn" :disabled="locked || state.detail.loading" @click="reloadDetail">重新读取任务</button><button type="button" class="sw-btn" :disabled="locked" @click="closeDetail">返回任务清单</button></div></div>
        <p v-if="state.detail.loading" class="sw-state" role="status">正在读取任务、版本与执行结果…</p>
        <div v-else-if="state.detail.error" class="sw-alert sw-alert--error" role="alert">{{ state.detail.error }}<p>没有取得详情，不能执行本任务的写操作。</p></div>
        <template v-else-if="state.detail.item">
          <div class="dx-detail-layout">
            <div class="sw-stack">
              <div class="dx-task-heading"><span class="sw-symbol"><AppIcon :name="state.detail.item.jobType === 'IMPORT' ? 'records' : 'reports'" :size="23" /></span><div><h3>{{ taskLabel(state.detail.item) }}</h3><p class="sw-code">{{ state.detail.item.jobType }} #{{ state.detail.item.id }} · 版本 {{ state.detail.item.version }}</p></div><span class="sw-tag" :class="tone(state.detail.item)">{{ taskStatus(state.detail.item) }}</span></div>
              <div v-if="unresolved(state.detail.item)" class="sw-alert sw-alert--warning"><b>上次请求结果尚未核实</b><p>只允许重新读取；不会因关闭确认框或再次点击而重复执行。</p></div>
              <div v-if="state.detail.item.strongSensitive" class="sw-alert sw-alert--warning"><b>强敏感、24 小时有效、一次性下载</b><p>下载前请核对交接对象；具体截止时间以服务器返回值为准，一次性票据只能消费一次，文件内容不在页面预览。</p></div>
              <dl class="dx-facts"><div><dt>业务模块</dt><dd>{{ moduleLabel(state.detail.item.moduleCode) }}</dd></div><div><dt>创建时间</dt><dd>{{ formatTime(state.detail.item.createdAt) }}</dd></div><div><dt>当前版本</dt><dd>{{ state.detail.item.version }}</dd></div><div><dt>有效截止时间</dt><dd>{{ formatTime(state.detail.item.expiresAt) }}</dd></div></dl>
              <template v-if="state.detail.item.jobType === 'IMPORT'">
                <div class="dx-counts"><div v-for="(label, key) in countLabels" :key="key"><small class="sw-muted">{{ label }}</small><strong>{{ taskCount(taskCounts(state.detail.item)[key]) }}</strong></div></div>
                <div v-if="isProcessing(state.detail.item)" class="sw-alert"><b>文件已登记，尚未形成最终预检结果</b><p>扫描、领取、解析阶段的行数显示“未取得”；后台继续处理，不需要重新上传。</p></div>
                <div v-if="state.detail.item.sourceFile" class="dx-source"><h3>源文件与安全状态</h3><p>{{ state.detail.item.sourceFile.fileName || '文件名称未取得' }}</p><p class="sw-muted">{{ fileState(state.detail.item.sourceFile.status) }} · {{ fileState(state.detail.item.sourceFile.scanStatus) }}</p></div>
                <section class="sw-stack" aria-label="错误条目">
                  <div class="sw-between"><h3>预检错误明细</h3><button type="button" class="sw-btn" :disabled="locked || state.errors.loading" @click="controller.loadErrors(1)">读取错误明细</button></div>
                  <p v-if="state.errors.loading" role="status">正在读取错误条目…</p>
                  <p v-else-if="state.errors.error" class="sw-alert sw-alert--error" role="alert">{{ state.errors.error }}</p>
                  <p v-else-if="state.errors.total === null" class="sw-muted">错误条目按需分页读取，未读取不代表没有错误。</p>
                  <p v-else-if="!state.errors.rows.length" class="sw-muted">当前查询没有返回错误条目；是否可确认仍以任务的最终预检状态为准。</p>
                  <div v-else class="sw-table-wrap"><table class="sw-table"><thead><tr><th>工作表 / 行号</th><th>字段</th><th>错误说明</th></tr></thead><tbody><tr v-for="(row, i) in state.errors.rows" :key="row.id || i"><td>{{ row.sheetName || '未标注' }}<small>第 {{ taskCount(row.rowNo) }} 行</small></td><td>{{ fieldLabel(row.fieldCode) }}</td><td>{{ row.message }}</td></tr></tbody></table></div>
                  <div v-if="state.errors.total !== null && !state.errors.error" class="sw-pager"><span>共 {{ state.errors.total }} 条错误 · 第 {{ state.errors.page }} 页</span><div class="sw-row"><button type="button" class="sw-btn" :disabled="state.errors.loading || state.errors.page <= 1" @click="controller.loadErrors(state.errors.page - 1)">上一页错误</button><button type="button" class="sw-btn" :disabled="state.errors.loading || state.errors.page * state.errors.pageSize >= state.errors.total" @click="controller.loadErrors(state.errors.page + 1)">下一页错误</button></div></div>
                </section>
                <section class="sw-stack" data-testid="related-receipts"><h3>本任务的回执文件</h3>
                  <p v-if="!state.detail.item.receiptJobs" class="sw-muted">本接口尚未返回关联回执清单，请在导出任务中核对；不能把文件编号当作下载任务编号。</p>
                  <template v-else>
                    <p v-if="!state.detail.item.receiptJobs.list.length" class="sw-muted">当前授权视图未返回关联回执。</p>
                    <div v-for="receipt in state.detail.item.receiptJobs.list" :key="taskKey(receipt)" class="dx-receipt-row"><div><b>{{ taskLabel(receipt) }}</b><p class="sw-muted">导出 #{{ receipt.id }} · {{ taskStatus(receipt) }}</p></div><button type="button" class="sw-btn" :disabled="locked" @click="openDetail(receipt)">核对并下载</button></div>
                    <p v-if="state.detail.item.receiptJobs.total > state.detail.item.receiptJobs.list.length" class="sw-muted">共 {{ state.detail.item.receiptJobs.total }} 项，当前展示最近 {{ state.detail.item.receiptJobs.list.length }} 项；其余请在导出清单核对。</p>
                  </template>
                </section>
              </template>
              <div v-else class="dx-counts"><div><small class="sw-muted">文件行数</small><strong>{{ taskCount(taskCounts(state.detail.item).rowCount) }}</strong></div><div><small class="sw-muted">下载次数</small><strong>{{ taskCount(taskCounts(state.detail.item).downloadedCount) }}</strong></div></div>
              <div v-if="state.detail.item.errorMessage" class="sw-alert sw-alert--error" role="alert">{{ state.detail.item.errorMessage }}</div>
              <div class="sw-savebar"><p class="sw-muted">操作前重新读取最新任务，版本变化时必须重新核对。</p><div class="sw-row">
                <button v-for="type in available(state.detail.item)" :key="type" type="button" class="sw-btn" :class="type === 'confirm' || type === 'download' ? 'sw-btn--primary' : ''" :disabled="locked" :data-testid="`task-${type}`" @click="controller.prepare(type, state.detail.item)">{{ actionLabels[type] }}</button>
              </div></div>
            </div>
            <aside class="dx-timeline sw-stack"><h3>执行留痕</h3>
              <div v-for="(event, i) in state.detail.item.timeline || []" :key="i"><b>{{ eventLabel(event.event) }}</b><p class="sw-muted">{{ formatTime(event.at) }}</p></div>
              <p v-if="!state.detail.item.timeline?.length" class="sw-muted">未返回更多执行事件。</p>
              <details v-if="state.detail.item.adapter || state.detail.item.adapterType"><summary>任务来源标识</summary><p class="sw-code">{{ state.detail.item.adapter?.type || state.detail.item.adapterType }}</p><p class="sw-code">{{ state.detail.item.adapter?.ref || state.detail.item.adapterRef }}</p></details>
            </aside>
          </div>
        </template>
      </section>

      <section v-else class="sw-card sw-stack dx-catalog" data-testid="exchange-catalog">
        <form class="sw-row dx-toolbar" @submit.prevent="controller.search()">
          <input v-model="state.filters.keyword" class="sw-input dx-search" :disabled="locked" aria-label="查找数据交换任务" placeholder="任务类型编码、批次号、模块或操作人" />
          <select v-model="state.filters.jobType" class="sw-input" :disabled="locked" aria-label="任务类型"><option value="">全部类型</option><option value="IMPORT">导入任务</option><option value="EXPORT">导出与回执</option></select>
          <select v-model="state.filters.status" class="sw-input" :disabled="locked" aria-label="任务状态"><option value="">全部状态</option><option v-for="(label, status) in statuses" :key="status" :value="status">{{ label }}</option></select>
          <button type="submit" class="sw-btn" :disabled="locked || state.list.loading">查询</button><button type="button" class="sw-btn" :disabled="locked" @click="resetFilters">重置</button>
        </form>
        <div v-if="state.list.loading" class="sw-state" role="status">正在读取任务清单…</div>
        <div v-else-if="state.list.error" class="sw-alert sw-alert--error dx-margin" role="alert" data-testid="task-list-error"><b>任务清单未取得</b><p>{{ state.list.error }}</p><button type="button" class="sw-btn sw-space" @click="controller.loadList()">重试清单</button></div>
        <div v-else-if="!state.list.rows.length" class="sw-state"><h3>当前筛选没有任务</h3><p>清除筛选或切换已授权视图；不会因没有记录自动创建任务。</p></div>
        <div v-else class="sw-table-wrap dx-table" tabindex="0" role="region" aria-label="数据交换任务清单"><table class="sw-table"><thead><tr><th>任务与来源</th><th>当前状态</th><th>数据量</th><th>创建时间 / 有效期</th><th>下一步</th></tr></thead><tbody>
          <tr v-for="row in state.list.rows" :key="taskKey(row)" :data-testid="`task-row-${row.jobType}-${row.id}`"><td><div class="sw-person"><span class="sw-symbol"><AppIcon :name="row.jobType === 'IMPORT' ? 'records' : 'reports'" :size="21" /></span><span><b>{{ taskLabel(row) }}</b><small>{{ moduleLabel(row.moduleCode) }} · {{ row.jobType === 'IMPORT' ? '导入' : '导出' }} #{{ row.id }}</small></span></div><span v-if="row.strongSensitive" class="sw-tag sw-tag--orange dx-sensitive">强敏感回执 · 下载独立授权</span></td>
            <td><span class="sw-tag" :class="tone(row)">{{ taskStatus(row) }}</span><small v-if="unresolved(row)">上次操作结果待核对</small></td>
            <td v-if="row.jobType === 'IMPORT'">总行数 {{ taskCount(taskCounts(row).totalRows) }}<small>有效 {{ taskCount(taskCounts(row).validRows) }} · 错误 {{ taskCount(taskCounts(row).invalidRows) }}</small></td>
            <td v-else>{{ taskCount(taskCounts(row).rowCount) }} 行<small>已下载 {{ taskCount(taskCounts(row).downloadedCount) }} 次</small></td>
            <td>{{ formatTime(row.createdAt) }}<small>{{ row.expiresAt ? '有效至 ' + formatTime(row.expiresAt) : '未设置单独有效期' }}</small></td>
            <td><button type="button" class="sw-link" :disabled="locked" @click="openDetail(row)">{{ row.jobType === 'EXPORT' ? '核对回执' : row.status === 'VALIDATION_FAILED' ? '查看错误' : isProcessing(row) ? '查看进度' : '继续办理' }} →</button></td>
          </tr></tbody></table></div>
        <footer v-if="state.list.total !== null && !state.list.error" class="sw-pager dx-pager"><span>共 {{ state.list.total }} 个任务 · 每页 {{ state.list.pageSize }} 项 · 第 {{ state.list.page }} 页</span><div class="sw-row"><button type="button" class="sw-btn" :disabled="locked || state.list.loading || state.list.page <= 1" @click="controller.loadList(state.list.page - 1)">上一页</button><button type="button" class="sw-btn" :disabled="locked || state.list.loading || state.list.page * state.list.pageSize >= state.list.total" @click="controller.loadList(state.list.page + 1)">下一页</button></div></footer>
      </section>
    </template>
    <WorkspaceConfirmDialog :visible="!!state.pending" :title="state.pending ? actionLabels[state.pending.type] : '核对任务操作'" :type="['cancel', 'revoke'].includes(state.pending?.type) ? 'danger' : 'warning'"
      :submitting="state.busy" :confirm-disabled="!state.pending?.acknowledged" confirm-text="核对无误，继续办理" @update:visible="controller.closeAction()" @confirm="controller.perform()">
      <div v-if="state.pending" class="sw-stack" data-testid="task-action-review"><p><b>{{ taskLabel(state.pending.row) }}</b> · #{{ state.pending.row.id }} · 版本 {{ state.pending.row.version }}</p>
        <p>{{ actionDescriptions[state.pending.type] }}</p>
        <div v-if="state.pending.type === 'download' && state.pending.row.strongSensitive" class="sw-alert sw-alert--warning">初始账号凭据仅交给授权人员。下载文件后请转入学校安全保管流程；页面不展示票据或凭据内容。</div>
        <label v-if="['cancel', 'revoke'].includes(state.pending.type)" class="sw-field">业务原因<textarea v-model="state.pending.reason" class="sw-input" :disabled="state.busy" minlength="5" maxlength="500" aria-label="任务操作原因" /></label>
        <p v-if="state.operationError" class="sw-alert sw-alert--error" role="alert">{{ state.operationError }}</p>
        <label class="sw-row"><input v-model="state.pending.acknowledged" class="sw-check" type="checkbox" :disabled="state.busy" aria-label="我已核对当前任务与本次操作" />我已核对任务、操作范围和当前版本</label>
      </div>
    </WorkspaceConfirmDialog>
  </SystemWorkspaceFrame>
</template>
<script>
import { markRaw } from 'vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import SystemWorkspaceFrame from '../components/workspace/SystemWorkspaceFrame.vue'
import WorkspaceConfirmDialog from '../components/workspace/WorkspaceConfirmDialog.vue'
import { dataExchangeApi } from '../api/dataExchange.api'
import { matchPermission } from '@/config/navPlan'
import { contextFingerprint } from '../utils/workspaceContract'
import { exchangeRights, createExchangeState, createExchangeController, TASK_STATUSES,
  taskRef, taskKey, taskCount, taskCounts, taskLabel, taskStatus, actionAvailable } from '../utils/dataExchangeWorkspace'
const ACTION_LABELS = { confirm: '确认导入', retry: '重试扫描', cancel: '取消任务', download: '安全下载', revoke: '撤销回执' }
export default {
  name: 'SystemDataExchangeView', components: { AppIcon, SystemWorkspaceFrame, WorkspaceConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() { return { state: createExchangeState(), controller: null, linkError: '', statuses: TASK_STATUSES,
    viewLabels: { OWN: '本人任务', MODULE: '模块任务', TENANT: '全校任务' }, actionLabels: ACTION_LABELS,
    actionDescriptions: { confirm: '仅提交服务端保存的预检任务与版本，不重新发送名单。', retry: '仅重新执行允许重试的安全扫描与解析，不重放已完成的导入。', cancel: '取消后不再执行此任务；历史记录和原因仍保留。', download: '重新校验版本，再申请短时一次性票据。实际下载权限由后端检查。', revoke: '撤销后现有下载票据失效，任务及审计记录仍保留。' },
    metrics: [{ key: 'total', label: '全部任务', note: '' }, { key: 'pending', label: '待处理', note: '待确认或生成中' }, { key: 'failed', label: '异常任务', note: '预检或执行失败' }, { key: 'receipts', label: '有效导出文件', note: '不代表当前身份有下载权限' }],
    countLabels: { totalRows: '文件行数', validRows: '有效行', invalidRows: '需修正行' } } },
  computed: {
    contextKey() { return contextFingerprint(this.ctx) },
    rights() { return exchangeRights(code => Array.isArray(this.ctx.permissionPatterns) && matchPermission(this.ctx.permissionPatterns, code)) },
    locked() { return this.state.busy || !!this.state.pending },
    visibilityOptions() { return this.state.access?.allowedVisibilities || [this.state.view.visibility] }
  },
  watch: { contextKey() { this.recreate() }, '$route.query': { deep: true, handler() { this.syncRoute() } } },
  created() { this.recreate() },
  mounted() { window.addEventListener('beforeunload', this.beforeUnload) },
  beforeUnmount() { this.controller?.dispose(); window.removeEventListener('beforeunload', this.beforeUnload) },
  beforeRouteLeave() { return this.canLeave() }, beforeRouteUpdate() { return this.canLeave() },
  methods: {
    taskKey, taskCount, taskCounts, taskLabel, taskStatus,
    moduleLabel(code) { return { SYSTEM: '系统管理', ACADEMIC_AFFAIRS: '教务中心', GRADUATION: '毕业设计', INTERNSHIP: '岗位实习', STUDENT_AFFAIRS: '学工中心' }[code] || '其他授权模块' },
    formatTime(value) { return value ? String(value).replace('T', ' ').replace(/Z$/, ' UTC') : '未返回' },
    fieldLabel(code) { return { name: '姓名', userNo: '工号', studentNo: '学号', collegeName: '学院', className: '班级', roleCode: '角色', scopeType: '数据范围' }[code] || (/[\u4e00-\u9fff]/.test(code || '') ? code : '其他字段') },
    fileState(code) { return { AVAILABLE: '文件可用', PENDING: '等待扫描', CLEAN: '扫描通过', PASSED: '扫描通过', ERROR: '扫描异常', INFECTED: '安全检查未通过', REJECTED: '文件已拒绝', SCANNING: '扫描中' }[code] || '安全状态待核对' },
    eventLabel(code) { return { CREATED: '任务创建', PARSING_STARTED: '开始预检', PARSING_FINISHED: '预检完成', CONFIRMED: '确认完成', FINISHED: '文件生成完成', REVOKED: '回执已撤销' }[code] || '后台处理事件' },
    isProcessing(row) { return ['SCANNING', 'WORKER_CLAIMED', 'PARSING'].includes(row.status) },
    tone(row) { return row.status === 'SUCCEEDED' ? 'sw-tag--green' : ['VALIDATION_FAILED', 'FAILED', 'EXPIRED'].includes(row.status) ? 'sw-tag--orange' : ['SCANNING', 'WORKER_CLAIMED', 'PARSING', 'VALIDATED', 'CONFIRMING', 'CREATED', 'RUNNING'].includes(row.status) ? 'sw-tag--blue' : '' },
    unresolved(row) { return !!this.state.unresolved[taskKey(row)] },
    available(row) { return this.unresolved(row) ? [] : Object.keys(ACTION_LABELS).filter(type => actionAvailable(type, row, this.rights)) },
    async recreate() {
      this.controller?.dispose(); this.state = createExchangeState(this.rights.initialVisibility); this.linkError = ''
      const controller = createExchangeController({ state: this.state, api: dataExchangeApi, rights: () => this.rights })
      this.controller = markRaw(controller)
      if (this.rights.read) { await controller.refresh(); if (this.controller === controller) await this.syncRoute() }
    },
    async syncRoute() {
      if (!this.controller || !this.rights.read || this.locked) return
      const query = this.$route.query; this.linkError = ''
      try {
        if (query.visibility && (query.visibility !== this.state.view.visibility || (query.visibility === 'MODULE' && String(query.moduleCode || '') !== this.state.view.moduleCode))) {
          if (!await this.controller.changeView(String(query.visibility), String(query.moduleCode || ''))) throw new Error('任务链接中的可见范围未获授权，请从本页选择合法视图')
        }
        if (!query.jobId) { this.controller.closeDetail(); return }
        let ref
        try { ref = taskRef({ id: String(query.jobId), jobType: String(query.jobType || '') }) }
        catch (error) { this.controller.closeDetail(); throw error }
        if (this.state.detail.ref && taskKey(ref) === taskKey(this.state.detail.ref)) return
        await this.controller.openDetail(ref)
      } catch (error) { this.linkError = error.message }
    },
    openDetail(row) { if (!this.locked) this.$router.push({ path: this.$route.path, query: { ...this.$route.query, jobId: taskRef(row).id, jobType: row.jobType, visibility: this.state.view.visibility, moduleCode: this.state.view.moduleCode || undefined } }) },
    closeDetail() { if (this.locked) return; const query = { ...this.$route.query }; delete query.jobId; delete query.jobType; this.$router.push({ path: this.$route.path, query }) },
    reloadDetail() { if (this.state.detail.ref && !this.locked) this.controller.openDetail(this.state.detail.ref) },
    async refresh() { if (this.locked) return; await this.controller.refresh(); this.reloadDetail() },
    async changeView(value, moduleCode) {
      if (this.locked) return
      const module = moduleCode || (value === 'MODULE' ? this.state.access?.allowedModules[0] : '') || ''
      if (await this.controller.changeView(value, module)) this.$router.replace({ path: this.$route.path, query: { visibility: value, ...(module ? { moduleCode: module } : {}) } })
    },
    resetFilters() { if (!this.locked) { this.state.filters = { keyword: '', jobType: '', status: '' }; this.controller.search() } },
    canLeave() { if (this.locked) { this.state.operationError = this.state.busy ? '当前请求尚未返回，请等待结果后再离开。' : '请先完成或取消当前操作核对。'; return false }; return true },
    beforeUnload(event) { if (this.state.busy) { event.preventDefault(); event.returnValue = '' } }
  }
}
</script>
<style scoped>
.dx-viewbar{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}.dx-viewbar .sw-field{min-width:160px}.dx-viewbar>p{max-width:360px}.dx-segments{display:flex;gap:4px;margin-top:10px;background:var(--sw-bg);border-radius:9px;padding:4px}.dx-segments button{font:inherit;font-size:12px;padding:7px 13px;border:1px solid transparent;border-radius:6px;background:transparent;color:var(--sw-muted);cursor:pointer}.dx-segments button[aria-pressed=true]{background:var(--sw-surface);border-color:var(--sw-line);color:var(--sw-accent)}.dx-segments button:disabled{cursor:not-allowed;opacity:.6}
.dx-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.dx-metrics article{display:grid;gap:7px;padding:20px}.dx-metrics strong{font-size:27px;line-height:1.5;font-variant-numeric:tabular-nums}.dx-metrics small{font-size:11px}.dx-summary-note{margin-top:-4px}.dx-toolbar{padding:18px 20px;border-bottom:1px solid var(--sw-line)}.dx-toolbar select{width:auto;max-width:200px}.dx-search{flex:1;min-width:200px}.dx-margin{margin:0 20px 20px}.dx-catalog{gap:0;overflow:hidden}.dx-table{border:0;border-radius:0}.dx-table table{min-width:810px}.dx-table .sw-symbol{width:35px;height:35px;flex-basis:35px}.dx-sensitive{margin:8px 0 0 46px}.dx-pager{padding:15px 20px;border-top:1px solid var(--sw-line)}
.dx-detail-layout{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:24px}.dx-task-heading{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.dx-task-heading>div{flex:1;min-width:0}.dx-facts{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:0;padding:18px;border:1px solid var(--sw-line);border-radius:10px}.dx-facts dt{font-size:11px;color:var(--sw-muted)}.dx-facts dd{margin:6px 0 0;font-size:13px;overflow-wrap:anywhere}.dx-counts{display:flex;border:1px solid var(--sw-line);border-radius:10px;padding:17px 0}.dx-counts>div{flex:1;padding:0 20px;border-right:1px solid var(--sw-line);min-width:0}.dx-counts>div:last-child{border:0}.dx-counts strong{display:block;font-size:23px;margin-top:6px}.dx-timeline{align-content:start;padding:20px;border:1px solid var(--sw-line);border-radius:11px;background:var(--sw-bg)}.dx-timeline>div{padding-left:14px;border-left:2px solid var(--sw-line)}.dx-timeline b{font-size:12px}.dx-source{padding:16px;background:var(--sw-bg);border-radius:9px}.dx-source>p{overflow-wrap:anywhere;font-size:12px}.dx-receipt-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px;border:1px solid var(--sw-line);border-radius:9px}.dx-receipt-row b{font-size:12px}
@container system-workspace (max-width:1000px){.dx-detail-layout{grid-template-columns:minmax(0,1fr)}.dx-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:800px){.dx-detail-layout{grid-template-columns:minmax(0,1fr)}.dx-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.dx-viewbar{align-items:flex-start}.dx-facts{grid-template-columns:1fr}.dx-toolbar{padding:14px}.dx-toolbar select{max-width:100%}.dx-search{flex-basis:100%}.dx-counts>div{padding:0 10px}.dx-counts strong{font-size:19px}.dx-metrics article{padding:15px}}
</style>
