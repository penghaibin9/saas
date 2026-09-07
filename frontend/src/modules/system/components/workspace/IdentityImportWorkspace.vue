<template>
  <SystemWorkspaceFrame :title="title" subtitle="下载模板 → 安全扫描 → 核对预检 → 确认导入，结果可回读。"
    :ctx="ctx" :watermark="true" :watermark-purpose="title">
    <template #actions>
      <button type="button" class="sw-btn" :disabled="writing" @click="openTasks">数据交换任务</button>
      <button v-if="canUpload" type="button" class="sw-btn sw-btn--primary" :disabled="templateLoading || writing" @click="downloadTemplate">{{ templateLoading ? '正在下载…' : '下载标准 XLSX 模板' }}</button>
    </template>
    <p v-if="templateError" class="sw-alert sw-alert--error" role="alert">{{ templateError }}</p>
    <section v-if="!canRead" class="sw-card sw-state" data-testid="identity-forbidden">
      <h2>当前身份没有导入或任务查看权限</h2><p class="sw-muted">请联系学校管理员核对权限。页面不会提交文件或创建账号。</p>
    </section>
    <template v-else>
      <ol class="iw-steps sw-card" aria-label="身份导入步骤">
        <li v-for="(step, index) in steps" :key="step" :aria-current="stage === index ? 'step' : undefined" :class="{ done: stage > index }">
          <span>{{ index + 1 }}</span><b>{{ step }}</b>
        </li>
      </ol>
      <div class="iw-layout">
        <section class="sw-card sw-pad sw-stack" data-testid="identity-import-workspace" :aria-busy="!!state.busy">
          <div class="sw-between"><div><h2>{{ state.review ? '核对本次导入' : state.job ? '当前导入任务' : '准备' + personLabel + '名单' }}</h2>
            <p class="sw-muted">{{ state.job ? '本页只处理当前身份类型的任务；任务状态以服务端为准。' : '师生名单分开上传，不在浏览器解析或改写表格内容。' }}</p></div>
            <span class="sw-tag sw-tag--blue">{{ personLabel }}身份</span>
          </div>
          <div v-if="state.error" class="sw-alert sw-alert--error" role="alert" data-testid="identity-error">
            <b>{{ state.uncertain ? '确认结果需要核对' : '本次请求未完成' }}</b><p>{{ state.error }}</p>
            <button v-if="state.job || routeJobId" type="button" class="sw-btn sw-space" :disabled="!!state.busy" @click="refreshJob">重新读取任务</button>
          </div>
          <div v-if="state.note" class="sw-alert" :class="state.readback ? 'sw-alert--success' : 'sw-alert--warning'" role="status" data-testid="identity-note">{{ state.note }}</div>
          <template v-if="!state.job && !routeJobId">
            <div v-if="canUpload" class="iw-dropzone">
              <span class="sw-symbol" aria-hidden="true">↑</span><h3>选择标准 Excel 名单</h3>
              <p class="sw-muted">使用本页下载的模板。文件登记成功后，还需等待安全扫描和服务端预检。</p>
              <label for="identity-workbook" class="iw-file-label">选择 .xlsx 文件</label>
              <input id="identity-workbook" ref="fileInput" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                :disabled="!!state.busy" aria-label="选择身份导入文件" @change="selectFile" />
              <p v-if="state.file" class="iw-filename" data-testid="identity-filename">{{ state.file.name }}</p>
              <button type="button" class="sw-btn sw-btn--primary" data-testid="identity-upload" :disabled="!state.file || !!state.busy" @click="controller.upload()">
                {{ state.busy === 'upload' ? '正在登记文件…' : state.uploadUncertain ? '用原上传标识重试' : '上传并开始预检' }}
              </button>
            </div>
            <div v-else class="sw-alert">当前可查看任务，但不能上传名单。请从已有导入任务链接进入，不会自动扩大权限。</div>
          </template>
          <div v-else-if="!state.job" class="sw-state" role="status"><h3>{{ state.busy ? '正在读取任务…' : '尚未取得任务' }}</h3><p class="sw-muted">任务 #{{ routeJobId }}；读取失败不代表不存在，也不代表已经导入。</p></div>
          <template v-else>
            <div class="iw-task-summary">
              <span class="sw-symbol" aria-hidden="true">▤</span>
              <div><h3>{{ state.job.sourceFile?.fileName || state.file?.name || (personLabel + '导入任务') }}</h3><p class="sw-code">任务 #{{ state.job.id }} · 版本 {{ state.job.version }}</p></div>
              <span class="sw-tag" :class="state.job.status === 'SUCCEEDED' ? 'sw-tag--green' : 'sw-tag--orange'" data-testid="identity-status">{{ statusLabel }}</span>
            </div>
            <dl class="iw-counts" data-testid="identity-counts">
              <div><dt>文件行数</dt><dd>{{ countText(counts.totalRows) }}</dd></div>
              <div><dt>有效行</dt><dd>{{ countText(counts.validRows) }}</dd></div>
              <div><dt>需修正行</dt><dd>{{ countText(counts.invalidRows) }}</dd></div>
            </dl>
            <div v-if="processing" class="sw-alert" role="status"><b>文件已登记，尚未形成最终预检结果</b><p>此阶段不会把缺失计数当作 0。离开页面仅停止本地轮询，不取消后台任务。</p></div>
            <p v-if="state.job.errorMessage" class="sw-alert sw-alert--error" role="alert">{{ state.job.errorMessage }}</p>
            <template v-if="state.job.status === 'VALIDATION_FAILED' || state.job.invalidRows > 0">
              <div class="sw-between"><h3>需要修正的条目</h3><small class="sw-muted">错误行与错误条目数量可能不同</small></div>
              <p v-if="state.errors.loading" role="status">正在读取错误明细…</p>
              <div v-else-if="state.errors.error" class="sw-alert sw-alert--error" role="alert">{{ state.errors.error }}<button type="button" class="sw-btn sw-space" @click="controller.loadErrors(state.errors.page)">重试错误明细</button></div>
              <div v-else-if="!state.errors.rows.length" class="sw-alert sw-alert--warning">任务未通过预检，但当前未返回错误条目。请到任务中心核对，不能据此确认导入。</div>
              <div v-else class="sw-table-wrap"><table class="sw-table" data-testid="identity-errors"><thead><tr><th>工作表 / 行号</th><th>字段</th><th>问题与处理</th></tr></thead>
                <tbody><tr v-for="(row, index) in state.errors.rows" :key="row.id || index"><td>{{ row.sheetName || '未标注工作表' }}<small>第 {{ row.rowNo }} 行</small></td><td>{{ fieldLabel(row.fieldCode) }}</td><td>{{ row.message }}<details v-if="row.errorCode"><summary>错误标识</summary><code class="sw-code">{{ row.errorCode }}</code></details></td></tr></tbody></table></div>
              <div v-if="!state.errors.loading && !state.errors.error" class="sw-pager"><span>共 {{ state.errors.total }} 条错误 · 第 {{ state.errors.page }} 页</span><div class="sw-row"><button type="button" class="sw-btn" :disabled="state.errors.loading || state.errors.page <= 1" @click="controller.loadErrors(state.errors.page - 1)">上一页错误</button><button type="button" class="sw-btn" :disabled="state.errors.loading || state.errors.page * state.errors.pageSize >= state.errors.total" @click="controller.loadErrors(state.errors.page + 1)">下一页错误</button></div></div>
            </template>
            <section v-if="state.review" class="iw-review sw-stack" data-testid="identity-review">
              <h3>本次只提交服务端已预检的名单</h3>
              <div class="sw-form"><div><small class="sw-muted">任务编号</small><p>#{{ state.job.id }}</p></div><div><small class="sw-muted">核对版本</small><p>{{ state.job.version }}</p></div><div><small class="sw-muted">确认数量</small><p>{{ counts.validRows }} 行 · {{ personLabel }}</p></div><div><small class="sw-muted">错误行</small><p>{{ counts.invalidRows }} 行</p></div></div>
              <p class="sw-muted">提交前再次读取任务。版本、状态或数量变化时，本次确认会暂停，不覆盖他人处理结果。</p>
              <label class="iw-ack"><input v-model="state.acknowledged" type="checkbox" class="sw-check" :disabled="writing" aria-label="我已核对本次导入名单与数量" />我已核对本次名单、身份类型与数量</label>
            </section>
            <section v-if="state.job.status === 'SUCCEEDED'" class="sw-stack" data-testid="identity-receipt">
              <div class="sw-alert" :class="state.readback ? 'sw-alert--success' : 'sw-alert--warning'"><b>{{ state.readback ? '导入完成，已重新读取服务端结果' : '服务端返回完成，回读仍需核对' }}</b><p>初始凭据不在本页展示、存储或自动下载；请按任务中心的独立下载权限办理。</p></div>
              <div class="iw-receipt-counts"><div v-for="item in receiptCounts" :key="item.label"><small class="sw-muted">{{ item.label }}</small><h3>{{ countText(item.value) }}</h3></div></div>
            </section>
            <div class="sw-savebar">
              <div class="sw-row"><button type="button" class="sw-btn" :disabled="!!state.busy" @click="refreshJob">{{ state.busy === 'poll' ? '正在等待预检…' : '重新读取状态' }}</button><button v-if="canUpload" type="button" class="sw-btn" :disabled="writing" @click="startAnother">开始另一批</button></div>
              <div v-if="state.review" class="sw-row"><button type="button" class="sw-btn" :disabled="writing" @click="controller.cancelReview()">返回预检</button><button type="button" class="sw-btn sw-btn--primary" data-testid="identity-confirm" :disabled="!canConfirm || !state.acknowledged || !!state.busy || state.uncertain || !!state.error" @click="controller.confirm()">{{ writing ? '正在核对并确认…' : '确认导入 ' + counts.validRows + ' 行' }}</button></div>
              <button v-else-if="state.job.status === 'SUCCEEDED'" type="button" class="sw-btn sw-btn--primary" :disabled="writing" @click="openTasks">前往任务中心安全下载</button>
              <button v-else type="button" class="sw-btn sw-btn--primary" data-testid="identity-review-open" :disabled="!canConfirm || !confirmable || !!state.busy || state.uncertain || !!state.error" @click="controller.prepareReview()">核对并继续</button>
            </div>
            <p v-if="!canConfirm && state.job.status === 'VALIDATED'" class="sw-muted">当前身份可以读取任务，但没有确认导入权限。</p>
          </template>
        </section>
        <aside class="sw-card sw-pad iw-guide">
          <span class="sw-kicker">导入前确认</span><h2>先把问题留在预检阶段</h2>
          <div class="iw-guide-item"><span>1</span><div><h3>使用正确模板</h3><p>{{ kind === 'students' ? '学号、姓名、学院、专业、班级与年级按学生模板填写。学生账号不能用于分配教职工权限。' : '工号、姓名、部门、预设角色与数据范围按教职工模板填写，多个角色的分隔规则以模板为准。' }}</p></div></div>
          <div class="iw-guide-item"><span>2</span><div><h3>{{ kind === 'students' ? '核对主档与组织冲突' : '核对角色与岗位范围' }}</h3><p>{{ kind === 'students' ? '已有学生主档按后端规则复用；身份或组织冲突先处理，不强行覆盖学籍事实。' : '角色来源与学院、班级范围分别校验。不能凭页面成功提示推断所有业务关系已配置。' }}</p></div></div>
          <div class="iw-guide-item"><span>3</span><div><h3>凭据单独受控下载</h3><p>原文件、错误与初始凭据回执保留在任务中心。任务可见不等于有权下载凭据。</p></div></div>
          <div class="iw-guide-foot"><b>任务可以继续办理</b><p>登记成功后本页链接会保留任务编号。刷新或重新打开链接，只读取该任务，不自动重新上传或确认。</p></div>
        </aside>
      </div>
    </template>
  </SystemWorkspaceFrame>
</template>

<script>
import SystemWorkspaceFrame from './SystemWorkspaceFrame.vue'
import { systemApi } from '../../api/system.api'
import { dataExchangeApi } from '../../api/dataExchange.api'
import { matchPermission } from '@/config/navPlan'
import { actionAllowed, contextFingerprint } from '../../utils/workspaceContract'
import { isIdentityImportProcessing } from '../../utils/identityImportState'
import { createImportState, createImportController, importCounts, importStatusLabel,
  importReceiptCounts, confirmableJob, countText } from '../../utils/identityImportWorkspace'

const FIELD_LABELS = { studentNo: '学号', name: '姓名', realName: '姓名', gender: '性别', phone: '手机号', idCard: '证件号', college: '学院', collegeName: '学院', major: '专业', majorName: '专业', className: '班级', grade: '年级', userNo: '工号', loginName: '登录名', email: '邮箱', roleCode: '角色', scopeType: '数据范围' }
export default {
  name: 'IdentityImportWorkspace', components: { SystemWorkspaceFrame },
  props: { kind: { type: String, required: true, validator: value => ['teachers', 'students'].includes(value) }, ctx: { type: Object, required: true } },
  data() { return { state: createImportState(), controller: null, templateLoading: false, templateError: '', templateEpoch: 0 } },
  computed: {
    title() { return this.kind === 'students' ? '学生导入与账号开通' : '教职工导入' },
    personLabel() { return this.kind === 'students' ? '学生' : '教职工' },
    contextKey() { return contextFingerprint(this.ctx) },
    routeJobId() { return String(this.$route.query.jobId || '') },
    canUpload() { return this.ctx.permissionActions?.importUsers ? actionAllowed(this.ctx, 'importUsers') : this.has('systemAdmin.user.import') },
    // Compatibility alias is the existing backend rbac09 mapping; never grants viewTenant.
    canConfirm() { return this.has('systemAdmin.dataExchange.confirm') || this.has('systemAdmin.user.import') },
    canRead() { return this.canUpload || this.has('systemAdmin.dataExchange.viewOwn') || this.has('systemAdmin.dataExchange.viewTenant') },
    writing() { return ['upload', 'confirm'].includes(this.state.busy) },
    counts() { return importCounts(this.state.job) },
    statusLabel() { return importStatusLabel(this.state.job) },
    processing() { return isIdentityImportProcessing(this.state.job) },
    confirmable() { return confirmableJob(this.state.job) },
    receiptCounts() { return importReceiptCounts(this.state.job, this.kind) },
    steps() { return ['准备文件', '安全扫描', '服务端预检', '确认导入', '结果回执'] },
    stage() { const status = this.state.job?.status; return status === 'SUCCEEDED' ? 4 : this.state.review || status === 'CONFIRMING' ? 3 : ['SCANNING', 'WORKER_CLAIMED'].includes(status) ? 1 : status ? 2 : 0 }
  },
  watch: {
    routeJobId(value) { if (value !== String(this.state.job?.id || '')) this.recreate() },
    contextKey() { this.recreate() },
    kind() { this.recreate() },
    canRead() { this.recreate() }
  },
  created() { this.recreate() },
  mounted() { window.addEventListener('beforeunload', this.beforeUnload) },
  beforeUnmount() { this.controller?.dispose(); this.templateEpoch += 1; window.removeEventListener('beforeunload', this.beforeUnload) },
  methods: {
    countText,
    has(code) { return Array.isArray(this.ctx.permissionPatterns) && matchPermission(this.ctx.permissionPatterns, code) },
    fieldLabel(code) { return FIELD_LABELS[code] || (/\p{Script=Han}/u.test(String(code || '')) ? code : '其他字段') },
    recreate() {
      this.controller?.dispose(); this.templateEpoch += 1; this.templateError = ''; this.templateLoading = false
      this.state = createImportState()
      this.controller = createImportController({ state: this.state, api: dataExchangeApi, kind: this.kind,
        canUpload: () => this.canUpload, canConfirm: () => this.canConfirm,
        onJobId: jobId => this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, jobId }, hash: this.$route.hash }) })
      if (this.routeJobId && this.canRead) this.controller.resume(this.routeJobId)
    },
    selectFile(event) { this.controller.selectFile(event.target.files?.[0]) },
    async downloadTemplate() {
      if (!this.canUpload || this.templateLoading || this.writing) return
      this.templateLoading = true; this.templateError = ''; const stamp = ++this.templateEpoch
      try {
        const result = await (this.kind === 'students' ? systemApi.downloadStudentImportTemplate() : systemApi.downloadTeacherImportTemplate())
        if (stamp === this.templateEpoch && result?.code !== 0) this.templateError = result?.message || '模板下载失败'
      } catch (error) { if (stamp === this.templateEpoch) this.templateError = error.message || '模板下载失败' }
      finally { if (stamp === this.templateEpoch) this.templateLoading = false }
    },
    refreshJob() { if (this.canRead) this.controller.resume(String(this.state.job?.id || this.routeJobId)) },
    startAnother() {
      if (this.writing || !this.canUpload) return
      if (this.state.job && !window.confirm(`当前任务 #${this.state.job.id} 仍会保留。确认离开本任务，准备另一批名单？`)) return
      const query = { ...this.$route.query }; delete query.jobId
      if (this.routeJobId) this.$router.push({ path: this.$route.path, query })
      else this.recreate()
    },
    openTasks() { if (!this.writing) this.$router.push('/admin/system/data-exchange') },
    canLeave(to) {
      if (to?.path === this.$route.path && String(to.query?.jobId || '') === String(this.state.job?.id || '')) return true
      if (this.writing) { this.state.note = '文件登记或确认请求正在执行，请等待结果后再切换。'; return false }
      return !this.state.file || !!this.state.job || window.confirm('当前文件尚未登记，离开后需重新选择。确认离开？')
    },
    beforeUnload(event) { if (this.writing || (this.state.file && !this.state.job)) { event.preventDefault(); event.returnValue = '' } }
  }
}
</script>

<style scoped>
.iw-steps { display:flex; list-style:none; padding:20px 25px; margin:0 0 20px; gap:16px; }
.iw-steps li { display:flex; align-items:center; gap:8px; flex:1; min-width:0; color:var(--sw-muted); font-size:12px; }
.iw-steps li:not(:last-child)::after { content:''; flex:1; height:1px; background:var(--sw-line); }
.iw-steps li > span { border:1px solid var(--sw-line); width:27px; height:27px; border-radius:50%; display:grid; place-items:center; flex:none; }
.iw-steps li[aria-current=step] { color:var(--sw-accent); }.iw-steps li[aria-current=step] > span { background:var(--sw-accent); color:white; border-color:var(--sw-accent); }
.iw-steps li.done > span { background:#eaf7f1; color:var(--sw-green); }.iw-steps b { font-weight:550; }
.iw-layout { display:grid; grid-template-columns:minmax(0,1.9fr) minmax(260px,1fr); gap:20px; align-items:start; }
.iw-dropzone { display:grid; justify-items:center; text-align:center; gap:16px; padding:35px 24px; min-height:310px; border:1.5px dashed #c7d4ee; border-radius:11px; background:var(--sw-bg); }
.iw-dropzone .sw-symbol { width:52px; height:52px; font-size:27px; }.iw-dropzone p { max-width:420px; }
.iw-file-label { font-size:12px; font-weight:550; }.iw-dropzone input { max-width:100%; font-size:12px; }.iw-filename { word-break:break-all; font-size:12px; }
.iw-task-summary { display:flex; gap:13px; align-items:center; padding:15px; background:var(--sw-bg); border-radius:10px; }.iw-task-summary > div { min-width:0; flex:1; }.iw-task-summary h3 { overflow-wrap:anywhere; }
.iw-counts { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); border:1px solid var(--sw-line); border-radius:10px; margin:0; padding:17px 0; }
.iw-counts > div { padding:0 20px; border-right:1px solid var(--sw-line); }.iw-counts > div:last-child { border-right:0; }.iw-counts dt { color:var(--sw-muted); font-size:11px; }.iw-counts dd { font-size:24px; margin:6px 0 0; font-weight:650; }
.iw-review { padding:18px; border:1px solid #cddaf9; background:var(--sw-bg); border-radius:10px; }.iw-ack { display:flex; gap:8px; align-items:flex-start; font-size:12px; }
.iw-guide h2 { margin-top:7px; }.iw-guide-item { display:flex; gap:11px; margin-top:24px; }.iw-guide-item > span { width:24px; height:24px; background:var(--sw-soft); color:var(--sw-accent); border-radius:50%; display:grid; place-items:center; font-size:11px; flex:none; }.iw-guide-item h3 { font-size:12px; }.iw-guide-item p,.iw-guide-foot p { color:var(--sw-muted); font-size:11px; margin-top:5px; line-height:1.8; }.iw-guide-foot { border-top:1px solid var(--sw-line); padding-top:18px; margin-top:24px; font-size:12px; }
.iw-receipt-counts { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }
@media(max-width:1050px) { .iw-layout { grid-template-columns:minmax(0,1fr); }.iw-guide { display:none; } }
@media(max-width:700px) { .iw-steps { padding:14px 10px; gap:6px; }.iw-steps li { font-size:10px; flex-direction:column; gap:5px; }.iw-steps li::after { display:none; }.iw-task-summary { flex-wrap:wrap; }.iw-counts > div { padding:0 10px; }.iw-counts dd { font-size:20px; } }
</style>
