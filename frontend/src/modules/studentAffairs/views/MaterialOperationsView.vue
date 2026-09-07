<template>
  <AppPageShell
    title="材料与档案中心"
    subtitle="统一登记缺项、审核学生补交版本，并查看公共文件版本与真实档案清单。"
    :role-name="ctx?.currentRole?.roleName || '当前身份'"
    :data-scope-name="ctx?.dataScope?.scopeName || '当前授权范围'"
    watermark-purpose="学工材料与档案"
  >
    <template #actions>
      <button v-if="materialReturnContext.bizType" class="secondary" @click="returnToApplication">{{ materialReturnContext.bizType === 'PROFILE' ? '返回学生档案' : '返回原申请' }}</button>
      <button class="primary" @click="createVisible = true">登记缺项</button>
      <button class="secondary" :disabled="loading" @click="load">刷新</button>
      <button class="secondary" :disabled="acting === 'backfill'" @click="backfillLegacy">
        {{ acting === 'backfill' ? '正在回填…' : '回填旧材料' }}
      </button>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在读取材料版本…" @retry="load">
      <p v-if="materialReturnContext.bizType" class="material-context">当前对象：{{ bizLabel(materialReturnContext.bizType) }} · #{{ materialReturnContext.bizId }}</p>
      <div v-if="!materialReturnContext.bizType" class="metrics">
        <div class="metric"><span>授权范围材料</span><strong>{{ summary.total }}</strong></div>
        <div class="metric"><span>待学生补交</span><strong>{{ summary.missing }}</strong></div>
        <div class="metric"><span>待老师审核</span><strong>{{ summary.pendingReview }}</strong></div>
        <div class="metric"><span>强敏感材料</span><strong>{{ summary.highlySensitive }}</strong></div>
      </div>

      <p class="material-privacy">家庭经济与心理材料仅限授权人员查看。</p>

      <AppSectionCard v-if="activePreviewVersion" title="站内材料阅读器">
        <div class="reader-head">
          <div>
            <strong>{{ activePreviewVersion.fileName }}</strong>
            <small>
              第 {{ activePreviewVersion.versionNo }} 版 · 文件版本 {{ activePreviewVersion.fileVersionId }} ·
              {{ activePreviewVersion.current ? '当前公共版本' : '历史不可变版本' }}
            </small>
          </div>
          <span class="reader-lock">只读 · 版本绑定授权</span>
        </div>
        <AppDocumentViewer
          :descriptor="previewDescriptor"
          :provider="previewProvider"
          :allow-download="activePreviewVersion.downloadable !== false"
          :show-version-bar="false"
          :show-file-switcher="false"
          @download="downloadPreview"
          @preview-error="previewError"
        />
      </AppSectionCard>



      <AppSectionCard title="材料清单">
        <div class="toolbar filters">
          <select v-model="statusFilter" @change="applyFilters"><option value="">全部状态</option><option value="MISSING">待补交</option><option value="RETURNED">退回重补</option><option value="PENDING_REVIEW">待审核</option><option value="ACCEPTED">已验收</option><option value="WAIVED">已免交</option></select>
          <select v-model="sensitivityFilter" @change="applyFilters"><option value="">全部敏感级别</option><option value="PERSONAL">个人</option><option value="SENSITIVE">敏感</option><option value="HIGHLY_SENSITIVE">强敏感</option></select>
          <button v-if="focusRequirementId" class="focus-return" type="button" @click="clearRequirementFocus">已定位通知材料 · 返回全部</button>
          <button class="primary" :disabled="!selectedRows.length || acting === 'batch'" @click="createReminderBatch">批量提醒已选 {{ selectedRows.length }} 项</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th class="check-col"></th><th>业务与学生</th><th>缺项/敏感级别</th><th>状态/期限</th><th>当前公共版本</th><th>责任人</th><th class="ops-col">操作</th></tr></thead>
            <tbody>
              <tr v-for="row in requirements" :id="`material-requirement-${row.requirementId}`" :key="row.requirementId" :class="{ selectedRow: activeRequirement?.requirementId === row.requirementId, focusRow: String(row.requirementId) === focusRequirementId }" @click="openRequirement(row)">
                <td @click.stop><input type="checkbox" :disabled="!canRemind(row)" :checked="selected.has(row.requirementId)" @change="toggle(row)" /></td>
                <td><strong>{{ studentLine(row) }}</strong><small>{{ bizTitleLine(row) }}</small><small class="tech-trace">{{ bizLabel(row.bizType) }} #{{ row.bizId }} · 学生 #{{ row.studentId }} · 材料编号 {{ row.assetId || '待回填' }}</small></td>
                <td><strong>{{ row.itemName }}</strong><small>{{ row.requirementReason || row.itemCode }}</small><span class="sensitivity" :class="sensitivityClass(row.sensitivityLevel)">{{ sensitivityText(row.sensitivityLevel) }}</span></td>
                <td><span class="status" :class="statusClass(row.status)">{{ operationStatusLabel(row.status, row.statusLabel) }}</span><small :class="{ overdue: row.overdue }">{{ row.dueAt ? `截止 ${fmt(row.dueAt)}` : '未设截止时间' }}</small></td>
                <td>
                  <template v-if="row.currentSubmission">
                    <strong>第 {{ row.currentSubmission.versionNo }} 版 · {{ row.currentSubmission.fileName }}</strong>
                    <small>版本编号 {{ row.currentSubmission.fileVersionId || '待回填' }} · {{ operationStatusLabel(row.currentSubmission.status, row.currentSubmission.statusLabel) }}</small>
                    <div class="inline-actions"><button class="text-btn" @click.stop="preview(row.currentSubmission)">站内预览</button><button class="text-btn" @click.stop="download(row.currentSubmission)">下载</button></div>
                  </template>
                  <span v-else>尚未提交</span>
                </td>
                <td>{{ row.reviewOwner || '未识别' }}</td>
                <td @click.stop><div class="row-actions"><button v-if="allows(row, 'ACCEPT_MATERIAL')" class="primary small" :disabled="acting === row.requirementId" @click="review(row, 'ACCEPT')">验收</button><button v-if="allows(row, 'RETURN_MATERIAL')" class="danger small" :disabled="acting === row.requirementId" @click="review(row, 'RETURN')">退回</button><button v-if="allows(row, 'WAIVE_MATERIAL')" class="secondary small" :disabled="acting === row.requirementId" @click="review(row, 'WAIVE')">免交</button><span v-if="!(row.allowedActions || []).length">—</span></div></td>
              </tr>
              <tr v-if="!requirements.length"><td colspan="7" class="empty">当前授权与筛选条件下暂无材料；强敏感材料不会出现在无权角色的空壳列表中</td></tr>
            </tbody>
          </table>
        </div>
        <div v-if="summary.total > pagination.pageSize" class="pager">
          <AppPagination
            :total="summary.total"
            :page="pagination.page"
            :page-size="pagination.pageSize"
            :show-size-changer="false"
            @change="onPageChange"
          />
        </div>
      </AppSectionCard>

      <div v-if="activeRequirement" class="detail-grid">
        <AppSectionCard title="版本记录">
          <div v-if="!activeRequirement.versions?.length" class="empty">暂无提交版本</div>
          <article v-for="version in activeRequirement.versions || []" :key="version.submissionId" class="version-card" :class="{ previewing: previewIdentity(version) === previewIdentity(activePreviewVersion) }">
            <div><strong>第 {{ version.versionNo }} 版 · {{ version.fileName }}</strong><small>提交编号 {{ version.submissionId }} · 文件版本 {{ version.fileVersionId || '待回填' }}</small></div>
            <div><span class="status" :class="statusClass(version.status)">{{ operationStatusLabel(version.status, version.statusLabel) }}</span><small>{{ fmt(version.submittedAt) }}</small></div>
            <div class="inline-actions"><button class="text-btn" @click="preview(version)">站内预览</button><button class="text-btn" @click="download(version)">下载</button></div>
          </article>
        </AppSectionCard>

        <AppSectionCard title="档案清单">
          <div v-if="manifestLoading" class="empty">正在读取档案清单…</div>
          <div v-else-if="manifestError" class="empty">{{ manifestError }}</div>
          <div v-else-if="!manifest" class="empty">该学生尚未完成档案冻结，或当前角色无档案查看权限</div>
          <template v-else>
            <dl class="manifest-meta"><div><dt>清单编号</dt><dd>{{ manifest.manifestId }}</dd></div><div><dt>修订号</dt><dd>{{ manifest.revision }}</dd></div><div><dt>状态</dt><dd>{{ operationStatusLabel(manifest.status, manifest.statusLabel) }}</dd></div><div><dt>文件摘要（SHA-256）</dt><dd class="mono">{{ manifest.manifestSha256 }}</dd></div></dl>
            <div class="table-wrap"><table><thead><tr><th>材料</th><th>版本编号</th><th>文件</th><th>扫描</th><th>审核</th><th>文件摘要</th></tr></thead><tbody><tr v-for="item in manifest.items || []" :key="`${item.materialCode}-${item.versionId}`"><td>{{ item.materialName || item.materialCode }}</td><td class="mono">{{ item.versionId }}</td><td>{{ item.fileName }}</td><td>{{ scanResultLabel(item.scanResult) }}</td><td>{{ reviewStatusLabel(item.reviewStatus) }}</td><td class="mono">{{ shortHash(item.sha256) }}</td></tr></tbody></table></div>
          </template>
        </AppSectionCard>
      </div>

      <AppSectionCard v-if="!materialReturnContext.bizType || batchJobs.length" title="批量提醒记录">
        <div class="batch-grid">
          <article v-for="job in batchJobs" :key="job.batchJobId" class="batch-card" :class="{ active: activeBatch?.batchJobId === job.batchJobId }" @click="openBatch(job)"><div><strong>{{ job.batchNo }}</strong><small>{{ operationStatusLabel(job.status, job.statusLabel) }} · 成功 {{ job.successCount }} / 失败 {{ job.failureCount }}</small></div><button v-if="(job.allowedActions || []).includes('RETRY_FAILED')" class="secondary small" :disabled="acting === `retry-${job.batchJobId}`" @click.stop="retry(job)">重试失败项</button></article>
          <p v-if="!batchJobs.length" class="empty">暂无批次记录</p>
        </div>
        <div v-if="activeBatch" class="batch-detail"><h4>{{ activeBatch.batchNo }} · {{ operationStatusLabel(activeBatch.status, activeBatch.statusLabel) }}</h4><table><thead><tr><th>记录</th><th>动作</th><th>结果</th><th>尝试次数</th><th>失败原因</th></tr></thead><tbody><tr v-for="item in activeBatch.items || []" :key="item.itemId"><td>{{ item.itemKey }}</td><td>{{ batchActionLabel(item.action) }}</td><td><span class="status" :class="statusClass(item.status)">{{ operationStatusLabel(item.status, item.statusLabel) }}</span></td><td>{{ item.attemptCount }}</td><td>{{ item.errorMessage || '—' }}</td></tr></tbody></table></div>
      </AppSectionCard>
    </AppGlobalState>
    <AppDrawer v-model:visible="createVisible" title="登记材料缺项" mode="modal" size="large">
        <div v-if="bizContext" class="biz-context">
          <div>
            <strong>{{ bizContextStudentLine }}</strong>
            <small>{{ bizContextBizLine }}</small>
            <small class="tech-trace">{{ bizLabel(form.bizType) }} #{{ form.bizId }}</small>
          </div>
          <button class="secondary" type="button" @click="clearBizContext">改为手工指定业务记录</button>
        </div>
        <AppInlineAlert v-if="bizContextError" type="danger" :description="bizContextError" />
        <div class="form-grid">
          <template v-if="!bizContext">
            <label><span>业务类型</span><select v-model="form.bizType" @change="loadItemSuggestions"><option v-for="item in bizTypes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <label><span>业务记录 ID</span><input v-model.trim="form.bizId" inputmode="numeric" placeholder="从申请详情复制记录ID" /></label>
          </template>
          <label><span>材料项编码</span><input v-model.trim="form.itemCode" maxlength="100" list="material-item-codes" placeholder="可从本校已用材料项中选择" /><datalist id="material-item-codes"><option v-for="s in itemSuggestions" :key="s.itemCode" :value="s.itemCode">{{ s.itemName }}（已用 {{ s.usedCount }} 次）</option></datalist></label>
          <label><span>材料项名称</span><input v-model.trim="form.itemName" maxlength="200" placeholder="如 家庭经济情况证明" /></label>
          <label><span>补交截止日期</span><input v-model="form.dueDate" type="date" /></label>
          <label class="wide"><span>缺项说明</span><textarea v-model.trim="form.requirementReason" maxlength="500" placeholder="说明缺失内容和补交要求（5-500字）" /></label>
        </div>
        <template #footer><button class="secondary" :disabled="acting === 'create'" @click="createVisible = false">关闭（保留本页输入）</button><button class="primary" :disabled="acting === 'create' || !createValid" @click="createRequirement">{{ acting === 'create' ? '正在登记…' : '登记缺项并通知学生' }}</button></template>
    </AppDrawer>

    <dialog ref="reviewDialog" class="material-review" aria-labelledby="material-review-title" @cancel="cancelReview($event)">
      <h2 id="material-review-title">{{ reviewAction === 'RETURN' ? '退回补充材料' : reviewAction === 'WAIVE' ? '确认免交材料' : '确认验收材料' }}</h2>
      <p>{{ reviewTarget?.itemName }}</p>
      <p class="review-context">{{ reviewTarget ? studentLine(reviewTarget) : '' }} · {{ reviewTarget?.currentSubmission?.fileName || '尚未上传' }}</p>
      <label for="material-review-reason">{{ reviewAction === 'RETURN' ? '补充要求（5–500字）' : '办理说明（选填）' }}</label>
      <textarea id="material-review-reason" v-model="reviewReason" maxlength="500" :disabled="!!acting" rows="4" />
      <p v-if="reviewError" class="overdue" role="alert">{{ reviewError }}</p>
      <div class="toolbar"><button class="secondary" :disabled="!!acting" @click="cancelReview">返回检查</button><button class="primary" :disabled="!!acting" @click="confirmReview">{{ acting ? '正在提交…' : '确认办理' }}</button></div>
    </dialog>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppSectionCard } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import { affairsOperationsApi } from '@/modules/studentAffairs/api/operations.api'
import { toast } from '@/utils/toast'
import { safeLocalizedText } from '@/utils/presentationSafety'

const OPERATION_STATUS_LABELS = { MISSING: '待补交', RETURNED: '退回重补', PENDING_REVIEW: '待审核', ACCEPTED: '已验收', WAIVED: '已免交', CREATED: '等待处理', RUNNING: '处理中', SUCCEEDED: '已完成', FAILED: '失败', DEAD: '多次失败，需处理', EXPIRED: '已过期', REVOKED: '已撤销', ACTIVE: '生效中', FROZEN: '已冻结' }
const SCAN_RESULT_LABELS = { CLEAN: '已通过', NOT_REQUIRED: '无需扫描', PENDING: '待扫描', INFECTED: '未通过', FAILED: '扫描失败' }
const REVIEW_STATUS_LABELS = { PENDING: '待审核', ACCEPTED: '已验收', RETURNED: '已退回', WAIVED: '已免交', APPROVED: '已通过', REJECTED: '未通过' }
const BATCH_ACTION_LABELS = { CREATE: '创建', GENERATE: '生成', REMIND: '提醒', RETRY: '重试', RETRY_FAILED: '重试失败项', ARCHIVE: '归档', FREEZE: '冻结' }

export default {
  name: 'MaterialOperationsView',
  props: { ctx: { type: Object, default: null } },
  components: { AppDrawer, AppDocumentViewer, AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppSectionCard },
  data() {
    return {
      createVisible: false, loading: true, acting: '', errorMessage: '', requirements: [], batchJobs: [], activeBatch: null,
      activeRequirement: null, activePreviewVersion: null, reviewTarget: null, reviewAction: '', reviewReason: '', reviewError: '',
      previewProvider: affairsOperationsApi.createPreviewProvider(),
      manifest: null, manifestLoading: false, manifestError: '', selected: new Set(),
      statusFilter: '', sensitivityFilter: '',
      pagination: { page: 1, pageSize: 20 }, focusRequirementId: '',
      bizContext: null, bizContextError: '', itemSuggestions: [], contextGeneration: 0, requirementsGeneration: 0,
      summary: { total: 0, missing: 0, pendingReview: 0, accepted: 0, highlySensitive: 0 },
      bizTypes: [
        { value: 'PROFILE', label: '学生个人档案' },
        { value: 'LEAVE', label: '请假' }, { value: 'AID', label: '困难认定（强敏感）' },
        { value: 'MENTAL', label: '心理专项材料（强敏感）' }, { value: 'FUNDING', label: '奖助申请' },
        { value: 'DISCIPLINE', label: '违纪处分' }, { value: 'DISCIPLINE_APPEAL', label: '处分申诉' },
        { value: 'DORM_TRANSFER', label: '调宿申请' }, { value: 'CREDIT_APPEAL', label: '第二课堂申诉' }
      ],
      form: { bizType: 'LEAVE', bizId: '', itemCode: '', itemName: '', requirementReason: '', dueDate: '' }
    }
  },
  computed: {
    materialReturnContext() {
      if (this.applicationContext.bizType) return this.applicationContext
      const q = this.$route.query || {}
      const id = String(q.materialRequirementId || q.requirementId || q.recordId || '')
      const row = (this.requirements || []).find(item => String(item.requirementId) === id)
      return row && ['PROFILE', 'LEAVE', 'AID', 'FUNDING'].includes(row.bizType) && /^\d+$/.test(String(row.bizId || '')) ? { bizType: row.bizType, bizId: String(row.bizId) } : {}
    },
    applicationContext() { const q = this.$route.query || {}; return ['PROFILE', 'AID', 'LEAVE', 'FUNDING'].includes(q.bizType) && /^\d+$/.test(String(q.bizId || '')) ? { bizType: q.bizType, bizId: q.bizId } : {} },
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    previewDescriptor() {
      return this.activePreviewVersion ? affairsOperationsApi.previewDescriptor(this.activePreviewVersion) : null
    },
    bizContextStudentLine() {
      const c = (this.bizContext && this.bizContext.businessContext) || {}
      return [c.studentName, c.studentNo, c.className].filter(Boolean).join(' · ') || '未识别学生'
    },
    bizContextBizLine() {
      const c = (this.bizContext && this.bizContext.businessContext) || {}
      return [c.bizPeriod, c.bizDisplayTitle, c.bizDisplaySubtitle].filter(Boolean).join(' · ')
    },
    createValid() { return /^\d+$/.test(this.form.bizId) && /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(this.form.itemCode) && this.form.itemName.trim().length >= 2 && (!this.form.requirementReason || this.form.requirementReason.length >= 5) },
    selectedRows() { return this.requirements.filter((row) => this.selected.has(row.requirementId) && this.canRemind(row)) }
  },
  mounted() { this.applyRouteFocus(); this.load(); this.applyRouteBizContext() },
  watch: {
    '$route.query'() { this.applyRouteFocus(); this.applyRouteBizContext(); this.pagination.page = 1; this.load() }
  },
  methods: {
    returnToApplication() { const context = this.materialReturnContext || this.applicationContext; if (!context.bizType) return; if (context.bizType === 'PROFILE') return this.$router.push({ path: `/admin/student/${context.bizId}` }); this.$router.push({ path: context.bizType === 'FUNDING' ? '/admin/student-affairs/funding' : context.bizType === 'AID' ? '/admin/student-affairs/aid' : '/admin/student-affairs/leave', query: { recordId: context.bizId } }) },
    operationStatusLabel(status, providedLabel = '') { return providedLabel || safeLocalizedText({ value: status, dictionary: OPERATION_STATUS_LABELS, unknownLabel: '状态待确认' }) },
    scanResultLabel(value) { return safeLocalizedText({ value, dictionary: SCAN_RESULT_LABELS, unknownLabel: '扫描结果待确认' }) },
    reviewStatusLabel(value) { return safeLocalizedText({ value, dictionary: REVIEW_STATUS_LABELS, unknownLabel: '审核结果待确认' }) },
    batchActionLabel(value) { return safeLocalizedText({ value, dictionary: BATCH_ACTION_LABELS, unknownLabel: '业务操作' }) },
    fmt(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' },
    previewIdentity(version) {
      if (!version?.fileId || !version?.fileVersionId) return ''
      return `${version.fileId}:${version.fileVersionId}`
    },
    applyRouteFocus() {
      const q = this.$route.query || {}
      this.focusRequirementId = String(q.materialRequirementId || q.requirementId || q.recordId || '')
      if (this.focusRequirementId) this.pagination.page = 1
      this.scrollToFocusedRequirement()
    },
    scrollToFocusedRequirement() {
      if (!this.focusRequirementId) return
      this.$nextTick(() => document.getElementById(`material-requirement-${this.focusRequirementId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    },
    clearRequirementFocus() {
      const query = { ...(this.$route.query || {}) }
      delete query.materialRequirementId
      delete query.requirementId
      delete query.recordId
      this.focusRequirementId = ''
      this.pagination.page = 1
      this.activeRequirement = null
      this.activePreviewVersion = null
      this.$router.replace({ query }).catch(() => {})
      return this.loadRequirements()
    },
    shortHash(value) { const text = String(value || ''); return text ? `${text.slice(0, 10)}…${text.slice(-8)}` : '-' },
    bizLabel(value) { return this.bizTypes.find((x) => x.value === value)?.label || (value ? '待确认' : '—') },
    studentLine(row) {
      const c = row.businessContext || {}
      const parts = [c.studentName, c.studentNo, c.className].filter(Boolean)
      return parts.length ? parts.join(' · ') : `${this.bizLabel(row.bizType)} #${row.bizId}`
    },
    bizTitleLine(row) {
      const c = row.businessContext || {}
      const parts = [c.bizPeriod, c.bizDisplayTitle, c.bizDisplaySubtitle].filter(Boolean)
      return parts.length ? parts.join(' · ') : this.bizLabel(row.bizType)
    },
    allows(row, action) { return (row.allowedActions || []).includes(action) },
    canRemind(row) { return ['MISSING', 'RETURNED'].includes(row.status) && row.version !== undefined && row.version !== null },
    statusClass(status) { return { ACCEPTED: 'ok', SUCCESS: 'ok', WAIVED: 'ok', APPROVED: 'ok', PENDING_REVIEW: 'wait', SUBMITTED: 'wait', MISSING: 'warn', RETURNED: 'warn', REJECTED: 'bad', FAILED: 'bad', PARTIAL_SUCCESS: 'warn', SUPERSEDED: 'muted' }[status] || '' },
    sensitivityText(value) { return { PERSONAL: '个人', SENSITIVE: '敏感', HIGHLY_SENSITIVE: '强敏感' }[value] || (value ? '待确认' : '敏感') },
    sensitivityClass(value) { return value === 'HIGHLY_SENSITIVE' ? 'high' : (value === 'SENSITIVE' ? 'sensitive' : '') },
    async load() { this.loading = true; this.errorMessage = ''; try { await Promise.all([this.loadRequirements(), this.loadBatches()]) } catch (e) { this.errorMessage = e?.message || '材料工作台加载失败' } finally { this.loading = false } },
    async applyRouteBizContext() {
      const generation = ++this.contextGeneration
      this.bizContext = null
      this.form.bizId = ''
      const q = this.$route.query || {}
      const bizType = String(q.bizType || '').trim().toUpperCase()
      const bizId = String(q.bizId || '').trim()
      if (!bizType || !/^\d+$/.test(bizId)) return
      this.bizContextError = ''
      try {
        const data = await affairsOperationsApi.resolveBizContext({ bizType, bizId })
        if (generation !== this.contextGeneration) return
        this.bizContext = data
        this.form.bizType = data.bizType
        this.form.bizId = String(data.bizId)
        await this.loadItemSuggestions()
        if (String(q.intent || '').toLowerCase() === 'create') this.createVisible = true
      } catch (e) {
        if (generation !== this.contextGeneration) return
        this.bizContext = null
        this.bizContextError = e?.message || '该业务记录不存在或不在你的授权范围内'
      }
    },
    clearBizContext() { this.contextGeneration++; this.bizContext = null; this.bizContextError = ''; this.form.bizId = '' },
    async loadItemSuggestions() {
      try {
        const data = await affairsOperationsApi.listItemSuggestions({ bizType: this.form.bizType })
        this.itemSuggestions = data?.items || []
      } catch { this.itemSuggestions = [] }
    },
    applyFilters() { this.pagination.page = 1; return this.loadRequirements() },
    onPageChange({ page }) { this.pagination.page = page; return this.loadRequirements() },
    async loadRequirements() {
      const generation = ++this.requirementsGeneration
      const data = await affairsOperationsApi.listCenter({ ...this.applicationContext, status: this.statusFilter || undefined, sensitivityLevel: this.sensitivityFilter || undefined, requirementId: this.focusRequirementId || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (generation !== this.requirementsGeneration) return
      this.requirements = data?.items || []; this.summary = { ...this.summary, ...(data?.summary || {}), total: Number(data?.total || 0) }
      if (!this.requirements.length && this.summary.total > 0 && this.pagination.page > 1) {
        this.pagination.page -= 1
        return this.loadRequirements()
      }
      const visible = new Set(this.requirements.map((x) => x.requirementId)); this.selected = new Set([...this.selected].filter((id) => visible.has(id)))
      if (this.activeRequirement) {
        this.activeRequirement = this.requirements.find((x) => x.requirementId === this.activeRequirement.requirementId) || null
        if (this.activePreviewVersion && this.activeRequirement) {
          const replacement = (this.activeRequirement.versions || []).find((version) => this.previewIdentity(version) === this.previewIdentity(this.activePreviewVersion))
          this.activePreviewVersion = replacement || null
        }
      }
      const focused = this.requirements.find((x) => String(x.requirementId) === this.focusRequirementId)
      if (focused) { this.activeRequirement = focused; this.scrollToFocusedRequirement() }
    },
    async loadBatches() { const data = await affairsOperationsApi.listBatchJobs({ page: 1, pageSize: 50 }); this.batchJobs = data?.items || [] },
    toggle(row) { const next = new Set(this.selected); next.has(row.requirementId) ? next.delete(row.requirementId) : next.add(row.requirementId); this.selected = next },
    async openRequirement(row) {
      this.activeRequirement = row
      if (this.activePreviewVersion && !(row.versions || []).some((version) => this.previewIdentity(version) === this.previewIdentity(this.activePreviewVersion))) this.activePreviewVersion = null
      this.manifest = null; this.manifestError = ''; this.manifestLoading = true
      try { const data = await affairsOperationsApi.getLatestManifest(row.studentId); this.manifest = data?.manifest || null } catch (e) { this.manifestError = e?.message || '档案清单不可见' } finally { this.manifestLoading = false }
    },
    async createRequirement() {
      if (this.acting || !this.createValid) return
      this.acting = 'create'
      try {
        await affairsOperationsApi.createRequirement({ bizType: this.form.bizType, bizId: String(this.form.bizId), itemCode: this.form.itemCode.toUpperCase(), itemName: this.form.itemName, requirementReason: this.form.requirementReason || undefined, dueAt: this.form.dueDate ? `${this.form.dueDate}T23:59:59` : undefined })
      } catch (e) {
        toast.error(e?.message || '登记失败')
        return
      } finally { this.acting = '' }
      toast.success('材料缺项已登记并通知学生')
      this.createVisible = false
      Object.assign(this.form, { bizId: this.bizContext ? String(this.bizContext.bizId) : '', itemCode: '', itemName: '', requirementReason: '', dueDate: '' })
      try { await this.loadRequirements() } catch { toast.error('登记已成功，材料列表刷新失败，请刷新队列查看') }
    },
    review(row, action) {
      if (this.acting) return
      this.reviewTarget = row; this.reviewAction = action; this.reviewReason = ''; this.reviewError = ''
      this.$refs.reviewDialog.showModal()
    },
    cancelReview(event) {
      if (this.acting) { event?.preventDefault?.(); return }
      this.$refs.reviewDialog.close(); this.reviewTarget = null
    },
    async confirmReview() {
      if (this.acting || !this.reviewTarget) return
      const row = this.reviewTarget, action = this.reviewAction, reason = this.reviewReason.trim()
      if (action === 'RETURN' && reason.length < 5) { this.reviewError = '请填写至少5字的具体补充要求'; return }
      this.reviewError = ''
      this.acting = row.requirementId
      try { await affairsOperationsApi.reviewRequirement(row.requirementId, action, reason, row.version); toast.success('材料状态已更新'); this.$refs.reviewDialog.close(); this.reviewTarget = null; await this.loadRequirements(); if (this.activeRequirement?.requirementId === row.requirementId) this.activeRequirement = this.requirements.find((x) => x.requirementId === row.requirementId) || null } catch (e) { this.reviewError = e?.message || '材料审核失败，办理说明已保留，请重试' } finally { this.acting = '' }
    },
    async backfillLegacy() { if (!window.confirm('确认幂等回填当前学校尚未接入公共版本链的旧材料？')) return; this.acting = 'backfill'; try { const result = await affairsOperationsApi.backfill(500); toast.success(`回填完成：补交版本 ${result.convertedSubmissions}，旧附件 ${result.convertedAttachments}`); await this.loadRequirements() } catch (e) { toast.error(e?.message || '旧材料回填失败') } finally { this.acting = '' } },
    async createReminderBatch() {
      if (!this.selectedRows.length || !window.confirm(`确认向 ${this.selectedRows.length} 项缺失材料发送提醒？`)) return
      this.acting = 'batch'; try { const result = await affairsOperationsApi.createBatchJob({ jobType: 'MATERIAL_REMIND', idempotencyKey: `material-remind:${Date.now()}`, items: this.selectedRows.map((row) => ({ requirementId: Number(row.requirementId), version: Number(row.version) })) }); toast.success(`批次完成：成功 ${result.successCount}，失败 ${result.failureCount}`); this.selected = new Set(); await Promise.all([this.loadRequirements(), this.loadBatches()]) } catch (e) { toast.error(e?.message || '批量提醒失败') } finally { this.acting = '' }
    },
    async openBatch(job) { try { this.activeBatch = await affairsOperationsApi.getBatchJob(job.batchJobId) } catch (e) { toast.error(e?.message || '批次详情加载失败') } },
    async retry(job) { this.acting = `retry-${job.batchJobId}`; try { const result = await affairsOperationsApi.retryFailed(job.batchJobId); toast.success(`重试完成：成功 ${result.successCount}，失败 ${result.failureCount}`); this.activeBatch = result; await this.loadBatches() } catch (e) { toast.error(e?.message || '失败项重试失败') } finally { this.acting = '' } },
    preview(version) {
      if (!version?.fileId || !version?.fileVersionId) return toast.warning('该材料尚未建立不可变 FileVersion，不能站内预览')
      this.activePreviewVersion = { ...version }
      this.$nextTick(() => document.querySelector('.reader-head')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    },
    async download(version) { try { await affairsOperationsApi.downloadMaterial(version) } catch (e) { toast.error(e?.message || '材料下载失败') } },
    downloadPreview() { if (this.activePreviewVersion) return this.download(this.activePreviewVersion) },
    previewError(error) { toast.error(error?.message || '材料预览失败，请刷新版本后重试') }
  }
}
</script>

<style scoped>
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.metric{padding:16px;border:1px solid #e7ebf1;border-radius:12px;background:#fff}.metric span,.metric strong{display:block}.metric span{font-size:12px;color:#667085}.metric strong{font-size:26px;margin-top:5px}.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.form-grid label span{display:block;font-size:12px;color:#667085;margin-bottom:5px}.form-grid input,.form-grid select,.form-grid textarea,.filters select{box-sizing:border-box;width:100%;min-height:38px;border:1px solid #d9dee7;border-radius:8px;padding:8px 10px;background:#fff}.form-grid textarea{min-height:82px}.wide{grid-column:1/-1}.toolbar{display:flex;gap:10px;align-items:center;justify-content:flex-end;margin-top:14px}.filters{justify-content:flex-start}.filters select{width:190px}.primary,.secondary,.danger{border:0;border-radius:8px;padding:9px 14px;cursor:pointer}.primary{background:#315efb;color:#fff}.secondary{background:#eef2f7;color:#344054}.danger{background:#fee4e2;color:#b42318}.small{padding:6px 9px;font-size:12px}.primary:disabled,.secondary:disabled,.danger:disabled{opacity:.5;cursor:not-allowed}.table-wrap{overflow:auto;margin-top:12px}.pager{display:flex;justify-content:center;padding-top:12px;border-top:1px solid #edf0f4;margin-top:12px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:11px 9px;border-bottom:1px solid #edf0f4;vertical-align:top}td strong,td small{display:block}td small{color:#667085;margin-top:4px}.check-col{width:34px}.ops-col{min-width:185px}.row-actions,.inline-actions{display:flex;gap:7px;flex-wrap:wrap}.status,.sensitivity{display:inline-block;padding:3px 7px;border-radius:6px;background:#eef2f7;margin-top:5px}.status.ok{background:#dcfae6;color:#067647}.status.wait{background:#eaf0ff;color:#1d4ed8}.status.warn{background:#fff3d6;color:#b54708}.status.bad,.sensitivity.high{background:#fee4e2;color:#b42318}.status.muted{color:#667085}.sensitivity.sensitive{background:#fff3d6;color:#b54708}.overdue{color:#b42318}.tech-trace{color:#98a2b3;font-size:11px}.biz-context{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px;margin-bottom:12px;border:1px solid #d6e0ff;border-radius:10px;background:#f5f8ff}.biz-context strong,.biz-context small{display:block}.biz-context small{color:#667085;margin-top:3px}.text-btn{all:unset;color:#315efb;cursor:pointer}.empty{text-align:center;color:#98a2b3;padding:24px}.selectedRow{background:#f7f9ff}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.version-card{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:14px;align-items:center;padding:12px;border-bottom:1px solid #edf0f4}.version-card.previewing{background:#f5f8ff;box-shadow:inset 3px 0 0 #315efb}.version-card strong,.version-card small{display:block}.version-card small{color:#667085;margin-top:4px}.manifest-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px}.manifest-meta div{padding:10px;border:1px solid #edf0f4;border-radius:8px}.manifest-meta dt{font-size:12px;color:#667085}.manifest-meta dd{margin:5px 0 0;word-break:break-all}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.batch-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.batch-card{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:12px;border:1px solid #e7ebf1;border-radius:10px;cursor:pointer}.batch-card.active{border-color:#315efb;background:#f5f7ff}.batch-card strong,.batch-card small{display:block}.batch-card small{margin-top:4px;color:#667085}.batch-detail{margin-top:16px;overflow:auto}.reader-head{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:12px}.reader-head strong,.reader-head small{display:block}.reader-head small{margin-top:5px;color:#667085}.reader-lock{flex:none;border:1px solid #b7e4c7;border-radius:999px;padding:5px 10px;background:#effaf3;color:#067647;font-size:12px;font-weight:600}.reader-head+*{min-height:560px}
@media(max-width:1000px){.metrics,.form-grid,.batch-grid,.detail-grid{grid-template-columns:1fr 1fr}}@media(max-width:680px){.metrics,.form-grid,.batch-grid,.detail-grid{grid-template-columns:1fr}.wide{grid-column:auto}.filters{align-items:stretch;flex-direction:column}.filters select{width:100%}.version-card{grid-template-columns:1fr}.reader-head{align-items:flex-start;flex-direction:column}}
.focusRow { background: #fff8e8; box-shadow: inset 4px 0 0 #f59e0b; }
.focus-return { border: 1px solid #f6c75b; border-radius: 999px; padding: 8px 13px; color: #92400e; background: #fff8e8; cursor: pointer; font-weight: 600; }
.metric,.form-grid input,.form-grid select,.form-grid textarea,.filters select{background:var(--surface,var(--bg-card));color:var(--text-primary);border-color:var(--line)}
.metric{padding:12px}.metric strong{font-size:24px}.metric span,.form-grid label span,td small,.biz-context small,.version-card small,.manifest-meta dt,.batch-card small,.reader-head small{color:var(--text-secondary)}
.primary{background:var(--pri);color:var(--pri-on,#fff)}.secondary,.status{background:var(--surface-2,var(--bg-page));color:var(--text-primary)}
.biz-context,.selectedRow,.version-card.previewing,.batch-card.active{background:var(--pri-50,var(--primary-soft));border-color:var(--line)}
.text-btn{color:var(--pri)}th,td,.pager,.version-card,.manifest-meta div,.batch-card{border-color:var(--line)}
.version-card.previewing{box-shadow:inset 3px 0 0 var(--pri)}.batch-card.active{border-color:var(--pri)}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.material-privacy{background:var(--surface-2);border-color:var(--line);color:var(--text-secondary)}.material-privacy :deep(.app-inline-alert__desc){color:var(--text-secondary)}.material-privacy :deep(.app-inline-alert__icon){background:var(--pri);color:var(--pri-on,#fff)}
.material-review{width:min(520px,calc(100vw - 40px));box-sizing:border-box;padding:24px;background:var(--surface);color:var(--text-primary);border:1px solid var(--line);border-radius:14px;box-shadow:0 18px 60px #10182730}.material-review::backdrop{background:#10182766}.material-review h2{font-size:20px;margin:0 0 18px}.material-review p{line-height:1.7;overflow-wrap:anywhere}.review-context{color:var(--text-secondary)}.material-review label{display:block;margin-bottom:8px}.material-review textarea{box-sizing:border-box;width:100%;border:1px solid var(--line);border-radius:8px;background:var(--surface-2);color:var(--text-primary);padding:10px;font:inherit;resize:vertical}
.material-context{margin:0 0 6px;font-size:13px;color:var(--text-secondary)}
.material-privacy{margin:0 0 12px;background:transparent;font-size:12px;color:var(--text-secondary)}
.filters{flex-wrap:wrap;margin-top:0;gap:8px}.filters select{width:150px}.filters button{white-space:nowrap}
.table-wrap table{min-width:760px}.detail-grid{grid-template-columns:minmax(0,1.2fr) minmax(0,1fr)}
@media(max-width:900px){.detail-grid{grid-template-columns:1fr}}
</style>
