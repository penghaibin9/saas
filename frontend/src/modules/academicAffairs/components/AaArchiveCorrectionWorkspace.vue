<template>
  <section class="aacw" aria-label="归档后纠错工作区">
    <section class="aacw-context" aria-label="归档后纠错约束">
      <div>
        <span>归档后纠错 · 独立事实链</span>
        <h3>{{ batch.batchName }}</h3>
        <p>原归档批次 {{ batch.batchId }} 与归档清单第 1 版永久保留；纠错只追加新正式事实和后继版本。</p>
      </div>
      <ol>
        <li><b>1</b><span><strong>申请人提交</strong><small>冻结目标事实、原因与证据</small></span></li>
        <li><b>2</b><span><strong>不同操作人复核</strong><small>重新核对权限和原归档清单</small></span></li>
        <li><b>3</b><span><strong>追加正式事实</strong><small>保留原事实并生成后继版本</small></span></li>
      </ol>
    </section>
    <div class="aacw-tabs" role="tablist" aria-label="归档批次工作区">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.key"
        :class="['aacw-tab', { 'is-active': activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <LoadingState v-if="loading" />
    <AppInlineAlert v-if="loadError || actionError" type="danger" :description="loadError || actionError" />
    <AppInlineAlert v-if="actionNotice" type="success" :description="actionNotice" />
    <AppInlineAlert v-if="pendingCommand" type="warning" description="本次命令已发送，办理结果尚未完成核对。请刷新服务端状态，切勿重复提交。" />

    <template v-if="!loading && activeTab === 'facts'">
      <div class="aacw-kpis">
        <div class="aacw-kpi"><span>归档清单当前版本</span><strong>{{ latestManifest ? `第 ${latestManifest.versionNo} 版` : '待核对' }}</strong></div>
        <div class="aacw-kpi"><span>当前完整性校验值</span><strong class="mono">{{ shortHash(latestManifest?.hash) }}</strong></div>
        <div class="aacw-kpi"><span>已应用纠错</span><strong>{{ manifest?.appliedCorrections ?? '待核对' }}</strong></div>
        <div class="aacw-kpi"><span>完整性结论</span><strong :class="manifest?.ok ? 'ok' : 'bad'">{{ manifest ? (manifest.ok ? '完整' : '异常') : '未校验' }}</strong></div>
      </div>
      <div class="aacw-toolbar">
        <AppButton size="small" variant="ghost" :loading="verifyBusy" @click="verifyNow">校验完整性</AppButton>
      </div>
      <AppInlineAlert
        v-if="manifest && !manifest.ok"
        type="danger"
        :description="`归档清单版本链校验未通过：${businessText(manifest.reason, '原因待核对')}`"
      />
      <AppInlineAlert
        v-else-if="manifest?.ok"
        type="success"
        description="归档清单完整性校验值、版本号、前后版本关联与已应用纠错的事实关联校验通过。"
      />
      <div class="aacw-section-title">归档事实</div>
      <EmptyState v-if="!items.length" title="暂无归档事实摘要" description="该批次没有可展示的数据域完整性快照" />
      <DataTable v-else :columns="factColumns" :rows="items" row-key="domain">
        <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
        <template #cell-result="{ row }"><StatusTag :type="factType(row)" :label="factLabel(row)" dot /></template>
      </DataTable>
    </template>

    <template v-else-if="!loading && activeTab === 'corrections'">
      <div class="aacw-kpis">
        <div class="aacw-kpi"><span>待二审</span><strong>{{ correctionSummary.pending }}</strong></div>
        <div class="aacw-kpi"><span>已应用</span><strong>{{ correctionSummary.applied }}</strong></div>
        <div class="aacw-kpi"><span>已拒绝</span><strong>{{ correctionSummary.rejected }}</strong></div>
        <div class="aacw-kpi"><span>允许范围</span><strong>成绩 / 毕业结论</strong></div>
      </div>
      <div class="aacw-toolbar">
        <AppButton size="small" variant="primary" :disabled="busy || checking || !!pendingCommand || !canCreate" @click="openCreate">发起归档后纠错</AppButton>
        <AppButton size="small" variant="ghost" :loading="loading" @click="refreshServerState">刷新服务端状态</AppButton>
      </div>
      <AppInlineAlert v-if="!canCreate" type="info" :description="createReason" />
      <AppInlineAlert
        type="info"
        description="已归档批次永久不解冻。申请仅进入待二审；只有不同操作人批准后才追加正式事实与归档清单后继版本，驳回不会产生正式事实或新归档清单。"
      />
      <EmptyState v-if="!loadError && !corrections.length" title="暂无纠错申请" description="发现归档后错误时从这里发起正式纠错" />
      <DataTable v-else :columns="correctionColumns" :rows="corrections" row-key="caseId">
        <template #cell-businessType="{ row }">{{ businessLabel(row.businessType) }}</template>
        <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-riskLevel="{ row }">{{ riskLabel(row.riskLevel) }}</template>
        <template #cell-actions="{ row }">
          <AppButton size="small" variant="ghost" @click="openDetail(row)">查看 / 复核</AppButton>
        </template>
      </DataTable>
    </template>

    <template v-else-if="!loading">
      <div class="aacw-toolbar">
        <div>
          <div class="aacw-section-title no-margin">归档清单版本链</div>
          <div class="aacw-muted">新版本只追加，旧归档清单永久保留并记录前后版本关联。</div>
        </div>
        <AppButton size="small" variant="ghost" :loading="verifyBusy" @click="verifyNow">重新校验</AppButton>
      </div>
      <AppInlineAlert
        v-if="manifest"
        :type="manifest.ok ? 'success' : 'danger'"
        :description="manifest.ok ? '当前版本链完整。' : `版本链异常：${businessText(manifest.reason, '原因待核对')}`"
      />
      <EmptyState v-if="!manifestVersions.length" title="尚未取得归档清单" description="已归档批次应至少存在归档清单第 1 版，请核对正式数据" />
      <DataTable v-else :columns="manifestColumns" :rows="manifestVersions" row-key="manifestId">
        <template #cell-versionNo="{ row }"><strong>第 {{ row.versionNo }} 版</strong></template>
        <template #cell-hash="{ row }"><span class="mono">{{ row.hash }}</span></template>
        <template #cell-supersedesId="{ row }">{{ row.supersedesId || '根版本' }}</template>
      </DataTable>
    </template>

    <AppDrawer :visible="createVisible" title="发起归档后纠错" mode="modal" size="medium" @close="closeCreate">
      <div class="aacw-form">
        <label class="aacw-field">
          <span>业务类型</span>
          <select v-model="createForm.businessType" :disabled="saving">
            <option value="GRADE">成绩</option>
            <option value="GRADUATION">毕业结论</option>
          </select>
        </label>
        <label class="aacw-field">
          <span>目标正式事实编号</span>
          <input v-model.trim="createForm.targetRef" :disabled="saving" inputmode="numeric" placeholder="填写正式成绩 / 毕业决定事实编号" />
          <small>稳定正式事实引用；服务端应用时再次校验租户、归档批次与当前正式事实。</small>
        </label>
        <label class="aacw-field">
          <span>纠错原因</span>
          <textarea v-model.trim="createForm.reason" :disabled="saving" rows="3" maxlength="500" placeholder="至少 5 个字，说明发现错误的依据与原因" />
        </label>
        <details>
          <summary>实施人员使用：修正内容与证据数据编辑</summary>
        <label class="aacw-field">
          <span>修正内容（数据文本）</span>
          <textarea v-model="createForm.correctionText" :disabled="saving" rows="5" spellcheck="false" />
          <small>成绩示例：{"score":65}。正式写入字段由服务端校验。</small>
        </label>
        <label class="aacw-field">
          <span>证据清单（数据文本）</span>
          <textarea v-model="createForm.evidenceText" :disabled="saving" rows="5" spellcheck="false" />
        </label>
        </details>
        <label class="aacw-field">
          <span>风险等级</span>
          <select v-model="createForm.riskLevel" :disabled="saving">
            <option value="HIGH">高风险</option>
            <option value="MEDIUM">中风险</option>
            <option value="LOW">低风险</option>
          </select>
        </label>
        <AppInlineAlert type="warning" description="提交不修改或解冻原归档版本；必须由另一名有归档管理权限的操作人二次复核。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        <AppInlineAlert v-if="!canCreate" type="info" :description="createReason" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="closeCreate">取消</AppButton>
        <AppButton variant="primary" :loading="saving" :disabled="checking || !!pendingCommand || !canCreate" @click="submitCreate">提交纠错申请</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="detailVisible" title="归档后纠错详情 / 二次复核" mode="modal" size="large" @close="closeDetail">
      <LoadingState v-if="detailLoading" />
      <AppInlineAlert v-if="detailError || actionError" type="danger" :description="detailError || actionError" />
      <AppInlineAlert v-if="detail && !canReview" type="info" :description="reviewReason" />
      <AppButton v-if="detailError && selectedCaseId" variant="ghost" @click="openDetail(selectedCaseId)">重新读取当前纠错单</AppButton>
      <template v-if="!detailLoading && detail">
        <div class="aacw-detail-head">
          <div>
            <strong>纠错 #{{ detail.correctionNo }}</strong>
            <span class="aacw-muted"> · {{ businessLabel(detail.businessType) }} · 目标 {{ detail.targetRef }}</span>
          </div>
          <StatusTag :type="statusType(detail.status)" :label="statusLabel(detail.status)" dot />
        </div>
        <div class="aacw-meta-grid">
          <div><span>申请人</span><strong>{{ personLabel(detail.requestedBy) }}</strong></div>
          <div><span>风险等级</span><strong>{{ riskLabel(detail.riskLevel) }}</strong></div>
          <div><span>二审通过人</span><strong>{{ personLabel(detail.secondApprovedBy) }}</strong></div>
          <div><span>驳回人</span><strong>{{ personLabel(detail.rejectedBy) }}</strong></div>
        </div>
        <div class="aacw-reason"><span>申请原因</span><p>{{ detail.reason }}</p></div>

        <div class="aacw-section-title">原事实与新事实对比</div>
        <div class="aacw-compare">
          <div class="aacw-compare-card">
            <h4>原正式事实</h4>
            <p>{{ factSummary(detail.originalOfficialFact) }}</p>
          </div>
          <div class="aacw-compare-card">
            <h4>{{ detail.status === 'APPLIED' ? '新正式事实' : '拟形成事实（非正式）' }}</h4>
            <p>{{ factSummary(detail.status === 'APPLIED' ? detail.resultingOfficialFact : detail.proposedOfficialFact) }}</p>
          </div>
        </div>

        <div class="aacw-section-title">申请修正与证据</div>
        <div class="aacw-compare">
          <div class="aacw-compare-card"><h4>申请修正</h4><p>{{ factSummary(detail.correction) }}</p></div>
          <div class="aacw-compare-card"><h4>证据清单</h4><p>{{ evidenceSummary(detail.evidenceManifest) }}</p></div>
        </div>
        <details><summary>实施人员使用：完整事实与证据数据</summary>
          <p>申请人编号：{{ detail.requestedBy || '未记录' }}；二审通过人编号：{{ detail.secondApprovedBy || '未记录' }}；驳回人编号：{{ detail.rejectedBy || '未记录' }}</p>
          <h4>原正式事实</h4><pre>{{ pretty(detail.originalOfficialFact) }}</pre>
          <h4>新正式事实或拟形成事实</h4><pre>{{ pretty(detail.status === 'APPLIED' ? detail.resultingOfficialFact : detail.proposedOfficialFact) }}</pre>
          <h4>申请修正</h4><pre>{{ pretty(detail.correction) }}</pre>
          <h4>证据清单</h4><pre>{{ pretty(detail.evidenceManifest) }}</pre>
        </details>

        <AppInlineAlert
          v-if="detail.status === 'APPLIED'"
          type="success"
          :description="`已形成${businessLabel(detail.businessType)}正式事实，编号 ${detail.officialFactId || '待核对'}；新归档清单编号 ${detail.resultingManifestId || '待核对'}。原事实和旧归档清单永久保留。`"
        />
        <AppInlineAlert
          v-else-if="detail.status === 'REJECTED'"
          type="warning"
          :description="`已驳回：${detail.rejectReason || '未提供原因'}。该申请未生成正式事实，也未生成新归档清单。`"
        />
        <AppInlineAlert
          v-else
          type="warning"
          description="批准后将追加正式纠错事实并生成归档清单后继版本，原归档清单永久保留；申请人本人执行二审会被服务端拒绝。"
        />
      </template>
      <template #footer>
        <AppButton variant="ghost" :disabled="busy" @click="closeDetail">关闭</AppButton>
        <AppButton
          v-if="detail?.reviewAction?.allowed === true"
          variant="ghost"
          :disabled="busy || checking || !!pendingCommand"
          @click="askReject"
        >驳回</AppButton>
        <AppButton
          v-if="detail?.reviewAction?.allowed === true"
          variant="primary"
          :disabled="busy || checking || !!pendingCommand"
          @click="askApprove"
        >二审通过并生成新正式事实</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="approveConfirmVisible"
      title="确认二次审批通过"
      message="批准后将追加正式纠错事实并生成新的归档清单版本；原事实和旧归档清单永久保留。确认继续？"
      confirm-text="确认批准并生成新事实"
      :submitting="busy"
      :confirm-disabled="checking || !!pendingCommand || !canReview"
      @confirm="submitApprove"
    ><AppInlineAlert v-if="detailError || actionError || !canReview" type="danger" :description="detailError || actionError || reviewReason" /></AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="rejectConfirmVisible"
      title="确认驳回归档后纠错"
      message="驳回后不能继续二次审批，不生成正式事实，也不生成新的归档清单版本。"
      type="danger"
      confirm-text="确认驳回"
      :require-reason="true"
      reason-label="驳回原因"
      reason-placeholder="请说明证据不足、事实不成立或其他驳回依据"
      :reason-min-length="5"
      :submitting="busy"
      :confirm-disabled="checking || !!pendingCommand || !canReview"
      @confirm="submitReject"
    ><AppInlineAlert v-if="detailError || actionError || !canReview" type="danger" :description="detailError || actionError || reviewReason" /></AppConfirmDialog>
  </section>
</template>

<script>
import { DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicArchiveCorrectionApi as api } from '@/modules/academicAffairs/api/academic-archive-correction.api'
import { academicAffairsArchiveApi as archiveApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { academicFlowText } from '../config/academicFlowRegistry.js'
import { toast } from '@/utils/toast'

const STATUS_LABEL = { PENDING_SECOND_APPROVAL: '待二审', APPLIED: '已应用', REJECTED: '已拒绝' }
const FACT_LABEL = { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待治理', NOT_APPLICABLE: '不适用' }
const FACT_TYPE = { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }

export default {
  name: 'AaArchiveCorrectionWorkspace',
  components: { DataTable, StatusTag, LoadingState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, AppInlineAlert },
  props: {
    batch: { type: Object, required: true },
    items: { type: Array, default: () => [] }
  },
  emits: ['refresh-batch'],
  data() {
    return {
      tabs: [
        { key: 'facts', label: '归档事实' },
        { key: 'corrections', label: '归档后纠错' },
        { key: 'manifest', label: '归档清单版本链' }
      ],
      activeTab: 'facts', loading: false, verifyBusy: false, busy: false,
      corrections: [], manifest: null,
      alive: true, contextSeq: 0, loadSeq: 0, detailSeq: 0, permissionSeq: 0, checking: false,
      batchAuthority: null, selectedCaseId: '', loadError: '', detailError: '', actionError: '', actionNotice: '', pendingCommand: null,
      createVisible: false, saving: false, formError: '', createForm: this.emptyCreateForm(),
      detailVisible: false, detailLoading: false, detail: null,
      approveConfirmVisible: false, rejectConfirmVisible: false,
      factColumns: [
        { key: 'domain', title: '数据域' }, { key: 'recordCount', title: '记录数' },
        { key: 'result', title: '归档状态' }, { key: 'remark', title: '备注' }
      ],
      correctionColumns: [
        { key: 'correctionNo', title: '纠错号' }, { key: 'businessType', title: '业务类型' },
        { key: 'targetRef', title: '目标事实' }, { key: 'riskLevel', title: '风险' },
        { key: 'reason', title: '申请原因' }, { key: 'status', title: '状态' },
        { key: 'actions', title: '操作' }
      ],
      manifestColumns: [
        { key: 'versionNo', title: '版本' }, { key: 'hash', title: '完整性校验值' },
        { key: 'supersedesId', title: '上一归档清单编号' }
      ]
    }
  },
  computed: {
    batchId() { return this.batch?.batchId },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.batchId, this.$route?.fullPath]) },
    canCreate() { return (this.batchAuthority || this.batch)?.correctionAction?.allowed === true },
    createReason() { return this.businessText((this.batchAuthority || this.batch)?.correctionAction?.reason, '尚未取得归档后纠错发起许可，请刷新服务端状态。') },
    canReview() { return !this.detailLoading && this.detail?.reviewAction?.allowed === true },
    reviewReason() { return this.businessText(this.detail?.reviewAction?.reason, '尚未取得当前纠错单的二次复核许可，请重新读取当前纠错单。') },
    correctionSummary() {
      if (this.loadError) return { pending: '待核对', applied: '待核对', rejected: '待核对' }
      return this.corrections.reduce((acc, row) => {
        if (row.status === 'PENDING_SECOND_APPROVAL') acc.pending += 1
        else if (row.status === 'APPLIED') acc.applied += 1
        else if (row.status === 'REJECTED') acc.rejected += 1
        return acc
      }, { pending: 0, applied: 0, rejected: 0 })
    },
    manifestVersions() { return Array.isArray(this.manifest?.versions) ? this.manifest.versions : [] },
    latestManifest() { return this.manifestVersions.length ? this.manifestVersions[this.manifestVersions.length - 1] : null }
  },
  watch: {
    identityKey: {
      immediate: true,
      handler() {
        this.clearContext()
        this.refreshAll()
      }
    }
  },
  beforeUnmount() { this.alive = false; this.clearContext() },
  methods: {
    clearContext() {
      this.contextSeq++; this.loadSeq++; this.detailSeq++; this.permissionSeq++
      this.activeTab = 'facts'; this.corrections = []; this.manifest = null; this.batchAuthority = null
      this.loading = false; this.busy = false; this.saving = false; this.checking = false; this.verifyBusy = false
      this.createVisible = false; this.detailVisible = false; this.detailLoading = false; this.detail = null; this.selectedCaseId = ''
      this.createForm = this.emptyCreateForm()
      this.approveConfirmVisible = false; this.rejectConfirmVisible = false
      this.loadError = ''; this.detailError = ''; this.actionError = ''; this.actionNotice = ''; this.formError = ''; this.pendingCommand = null
    },
    contextGuard() {
      const identity = this.identityKey, seq = this.contextSeq
      return () => this.alive && identity === this.identityKey && seq === this.contextSeq
    },
    businessText(value, fallback = '待核对') { return academicFlowText(value, fallback) },
    riskLabel(value) { return ({ HIGH: '高风险', MEDIUM: '中风险', LOW: '低风险' })[value] || '待核对' },
    personLabel(value) { return value ? (/^\d+$/.test(String(value)) ? '已记录身份，姓名待核对' : String(value)) : '未记录' },
    factSummary(value) {
      if (!value || typeof value !== 'object') return '尚未取得正式事实，请核对服务端证据。'
      const facts = []
      if (value.courseName) facts.push(`课程：${value.courseName}`)
      if (value.term) facts.push(`学期：${value.term}`)
      if (value.score != null) facts.push(`成绩：${value.score}`)
      if (value.passLine != null) facts.push(`合格分数：${value.passLine}`)
      if (value.conclusion) facts.push(`毕业结论：${({ GRADUATED: '准予毕业', COMPLETED: '结业', DELAYED: '暂缓毕业' })[value.conclusion] || this.businessText(value.conclusion)}`)
      return facts.length ? facts.join('；') : '已取得服务端事实，具体内容请展开实施人员信息核对。'
    },
    evidenceSummary(value) {
      if (!value || typeof value !== 'object') return '尚未取得证据清单。'
      const note = this.businessText(value.summary || value.description || value.reason, '')
      return note || (Array.isArray(value.refs) ? `已登记 ${value.refs.length} 项证据引用；完整数据可在实施人员信息中核对。` : '已取得服务端证据清单，完整数据可在实施人员信息中核对。')
    },
    emptyCreateForm() {
      return {
        businessType: 'GRADE', targetRef: '', reason: '',
        correctionText: '{\n  "score": 60\n}',
        evidenceText: '{\n  "kind": "MANUAL_REVIEW",\n  "refs": []\n}',
        riskLevel: 'HIGH'
      }
    },
    businessLabel(v) { return v === 'GRADE' ? '成绩' : v === 'GRADUATION' ? '毕业结论' : '业务类型待核对' },
    statusLabel(v) { return STATUS_LABEL[v] || (v ? '待确认' : '—') },
    statusType(v) { return v === 'APPLIED' ? 'success' : v === 'REJECTED' ? 'warning' : 'primary' },
    factState(row) { return String(row?.result || (row?.present ? 'PASS' : 'BLOCKED')).toUpperCase() },
    factLabel(row) { return FACT_LABEL[this.factState(row)] || '待确认' },
    factType(row) { return FACT_TYPE[this.factState(row)] || 'warning' },
    shortHash(hash) { return hash ? `${String(hash).slice(0, 12)}…` : '—' },
    pretty(value) { return value == null ? '—' : JSON.stringify(value, null, 2) },
    async refreshAll() {
      if (!this.batchId || !this.alive) return false
      const guard = this.contextGuard(), seq = ++this.loadSeq, permissionSeq = ++this.permissionSeq, batchId = this.batchId
      const current = () => guard() && seq === this.loadSeq
      this.loading = true; this.loadError = ''; this.corrections = []; this.manifest = null
      this.batchAuthority = { correctionAction: {} }
      try {
        const [queue, verified, authority] = await Promise.all([
          api.list(this.batchId, { page: 1, pageSize: 100 }), api.verifyManifest(this.batchId), archiveApi.getBatch(batchId)
        ])
        if (!current()) return false
        if (queue.code === 0) this.corrections = Array.isArray(queue.data?.items) ? queue.data.items : []
        else this.loadError = this.businessText(queue.message, '纠错列表加载失败')
        if (verified.code === 0) this.manifest = verified.data
        else this.loadError = this.businessText(verified.message, '归档清单校验失败')
        if (permissionSeq === this.permissionSeq) {
          if (authority.code === 0 && authority.data?.batchId === batchId) this.batchAuthority = authority.data
          else this.loadError = this.businessText(authority.message, '当前归档批次的纠错许可读取失败')
        }
        return !this.loadError
      } catch (error) {
        if (current()) this.loadError = this.businessText(error?.message, '归档纠错工作区加载失败')
        return false
      } finally { if (current()) this.loading = false }
    },
    async verifyNow() {
      if (!this.batchId || this.verifyBusy || !this.alive) return
      const current = this.contextGuard()
      this.verifyBusy = true; this.manifest = null; this.loadError = ''
      try {
        const res = await api.verifyManifest(this.batchId)
        if (!current()) return
        if (res.code === 0) {
          this.manifest = res.data
          res.data?.ok ? toast.success('归档清单版本链校验通过') : toast.error(`归档清单校验异常：${this.businessText(res.data?.reason, '原因待核对')}`)
        } else this.loadError = this.businessText(res.message, '归档清单校验失败')
      } catch (error) { if (current()) this.loadError = this.businessText(error?.message, '归档清单校验失败') }
      finally { if (current()) this.verifyBusy = false }
    },
    async readCreateAuthority() {
      const current = this.contextGuard(), seq = ++this.permissionSeq, batchId = this.batchId
      this.batchAuthority = { correctionAction: {} }
      try {
        const res = await archiveApi.getBatch(batchId)
        if (!current() || seq !== this.permissionSeq) return false
        if (res.code !== 0 || res.data?.batchId !== batchId) { this.actionError = this.businessText(res.message, '当前归档批次的纠错许可未能核对'); return false }
        this.batchAuthority = res.data
        if (!this.canCreate) this.actionError = this.createReason
        return this.canCreate
      } catch (error) { if (current() && seq === this.permissionSeq) this.actionError = this.businessText(error?.message, '当前归档批次的纠错许可读取失败'); return false }
    },
    async openCreate() {
      if (this.busy || this.saving || this.checking || this.pendingCommand || !this.alive) return
      if (!this.canCreate) { this.actionError = this.createReason; return }
      const current = this.contextGuard()
      this.checking = true; this.actionError = ''; this.actionNotice = ''
      try {
        if (!await this.readCreateAuthority() || !current()) return
        this.createForm = this.emptyCreateForm(); this.formError = ''; this.createVisible = true
      } finally { if (current()) this.checking = false }
    },
    closeCreate() { if (!this.saving) { this.createVisible = false; this.formError = '' } },
    parseObject(text, label) {
      let value
      try { value = JSON.parse(text) } catch { throw new Error(`${label}必须是合法的数据文本，请由实施人员核对`) }
      if (!value || Array.isArray(value) || typeof value !== 'object' || !Object.keys(value).length) throw new Error(`${label}不能为空对象`)
      return value
    },
    async submitCreate() {
      if (this.saving || this.busy || this.checking || this.pendingCommand || !this.alive) return
      if (!this.canCreate) { this.formError = this.createReason; return }
      this.formError = ''
      if (!this.createForm.targetRef) { this.formError = '请填写目标正式事实编号'; return }
      if (this.createForm.reason.length < 5) { this.formError = '纠错原因至少 5 个字'; return }
      let correction, evidenceManifest
      try {
        correction = this.parseObject(this.createForm.correctionText, '修正内容')
        evidenceManifest = this.parseObject(this.createForm.evidenceText, '证据清单')
      } catch (error) { this.formError = error.message; return }
      const current = this.contextGuard(), batchId = this.batchId
      const body = { businessType: this.createForm.businessType, targetRef: this.createForm.targetRef,
        reason: this.createForm.reason, correction, evidenceManifest, riskLevel: this.createForm.riskLevel }
      this.saving = true; this.actionError = ''; this.actionNotice = ''
      try {
        if (!await this.readCreateAuthority() || !current()) { if (current()) this.formError = this.actionError || this.createReason; return }
        const command = { kind: 'create', batchId, sent: true }
        this.pendingCommand = command
        const res = await api.create(batchId, body)
        if (!current()) return
        if (res.code !== 0) { this.formError = this.businessText(res.message, '提交结果尚未核对'); this.releaseRejectedCommand(res); return }
        const caseId = res.data?.caseId
        if (!caseId) { this.formError = '申请回执缺少正式纠错单编号，请刷新核对，勿重复提交'; return }
        if (this.pendingCommand === command) { command.caseId = caseId; command.acknowledged = true }
        this.createVisible = false
        this.activeTab = 'corrections'
        if (await this.authoritativeRefresh(caseId) && current()) { this.pendingCommand = null; toast.success('纠错申请已提交，等待不同操作人二次审批') }
      } catch (error) { if (current()) this.formError = this.businessText(error?.message, '提交结果尚未核对，请刷新服务端状态，勿重复提交') }
      finally { if (current()) this.saving = false }
    },
    async openDetail(row) {
      const caseId = row?.caseId || row
      if (!caseId || !this.alive || this.busy) return false
      this.detailVisible = true
      this.selectedCaseId = caseId
      this.approveConfirmVisible = false; this.rejectConfirmVisible = false
      return this.readDetail(caseId)
    },
    async readDetail(caseId) {
      const guard = this.contextGuard(), seq = ++this.detailSeq
      const current = () => guard() && seq === this.detailSeq && caseId === this.selectedCaseId
      this.detailLoading = true; this.detail = null; this.detailError = ''
      try {
        const res = await api.detail(caseId)
        if (!current()) return false
        if (res.code === 0 && res.data?.caseId === caseId && res.data?.archiveBatchId === this.batchId) { this.detail = res.data; return true }
        this.detailError = this.businessText(res.message, '当前纠错单未能读取或归档批次不一致'); return false
      } catch (error) { if (current()) this.detailError = this.businessText(error?.message, '当前纠错单读取失败'); return false }
      finally { if (current()) this.detailLoading = false }
    },
    closeDetail() {
      if (this.busy) return
      this.detailSeq++; this.detailVisible = false; this.detail = null; this.selectedCaseId = ''; this.detailLoading = false
      this.approveConfirmVisible = false; this.rejectConfirmVisible = false
    },
    askApprove() { return this.askReview('approve') },
    askReject() { return this.askReview('reject') },
    async askReview(kind) {
      if (this.busy || this.checking || this.pendingCommand || !this.alive) return
      if (!this.canReview) { this.actionError = this.reviewReason; return }
      const current = this.contextGuard(), caseId = this.detail.caseId
      this.checking = true; this.actionError = ''; this.actionNotice = ''
      try {
        if (!await this.readDetail(caseId) || !current() || this.selectedCaseId !== caseId) return
        if (!this.canReview) { this.actionError = this.reviewReason; return }
        if (kind === 'approve') this.approveConfirmVisible = true
        else this.rejectConfirmVisible = true
      } finally { if (current()) this.checking = false }
    },
    async submitApprove() {
      await this.submitReview('approve')
    },
    async submitReject(payload = {}) {
      const reason = String(payload?.reason || '').trim()
      if (reason.length < 5) { toast.error('驳回原因至少 5 个字'); return }
      await this.submitReview('reject', reason)
    },
    releaseRejectedCommand(res) {
      const code = String(res?.code || '')
      if (/^(400|401|403|404|409)/.test(code) || ['NO_PERMISSION', 'NO_DATA_SCOPE', 'DATA_CONFLICT', 'INVALID_STATE', 'VALIDATION_ERROR'].includes(code)) this.pendingCommand = null
    },
    async submitReview(kind, reason = '') {
      if (!this.alive || this.busy || this.checking || this.pendingCommand) return
      if (!this.canReview) { this.actionError = this.reviewReason; return }
      const guard = this.contextGuard()
      const caseId = this.detail.caseId
      const current = () => guard() && caseId === this.selectedCaseId
      this.busy = true; this.actionError = ''; this.actionNotice = ''
      try {
        if (!await this.readDetail(caseId) || !current()) return
        if (!this.canReview) { this.actionError = this.reviewReason; return }
        this.pendingCommand = { kind, batchId: this.batchId, caseId, sent: true }
        const res = kind === 'approve' ? await api.approve(caseId) : await api.reject(caseId, reason)
        if (!current()) return
        if (res.code !== 0) { this.actionError = this.businessText(res.message, '办理结果尚未核对，请刷新服务端状态'); this.releaseRejectedCommand(res); return }
        this.approveConfirmVisible = false; this.rejectConfirmVisible = false
        if (await this.authoritativeRefresh(caseId) && current() && this.detail?.status === (kind === 'approve' ? 'APPLIED' : 'REJECTED')) {
          this.pendingCommand = null
          toast.success(kind === 'approve' ? '已应用正式纠错事实并生成归档清单后继版本' : '已驳回；未生成正式事实或新的归档清单')
        } else if (current()) this.actionError = this.actionError || '命令已返回，纠错单及归档清单结果尚未完成核对，请刷新服务端状态。'
      } catch (error) { if (current()) this.actionError = this.businessText(error?.message, '办理结果尚未核对，请刷新服务端状态，勿重复提交') }
      finally { if (current()) this.busy = false }
    },
    async authoritativeRefresh(caseId) {
      const current = this.contextGuard()
      const loaded = await this.refreshAll()
      if (!current()) return false
      if (caseId) { this.selectedCaseId = caseId; if (!await this.readDetail(caseId)) return false }
      if (!current()) return false
      if (this.manifest?.ok !== true) {
        this.actionError = '部分完成：命令已返回，但归档清单完整性尚未校验通过。请刷新核对，勿重复提交。'
        return false
      }
      if (loaded) this.$emit('refresh-batch')
      return loaded
    },
    async refreshServerState() {
      if (this.busy || this.saving || this.checking || this.loading) return
      const current = this.contextGuard(), command = this.pendingCommand, caseId = this.selectedCaseId
      const loaded = await this.refreshAll()
      if (!current()) return
      const knownCommand = command?.sent === true && (['approve', 'reject'].includes(command.kind) || (command.kind === 'create' && command.acknowledged === true))
      if (!knownCommand || !command.caseId || command.batchId !== this.batchId) {
        if (caseId && this.detailVisible) await this.readDetail(caseId)
        if (current() && command?.kind === 'create' && this.pendingCommand === command) this.actionError = '提交回执未能确认，无法仅凭纠错列表判断本次申请是否创建。请核对原申请记录，勿重复提交。'
        return
      }
      try {
        const res = await api.detail(command.caseId)
        if (!current() || this.pendingCommand !== command) return
        const result = res.code === 0 && res.data?.caseId === command.caseId && res.data?.archiveBatchId === command.batchId ? res.data : null
        if (this.selectedCaseId === command.caseId) this.detail = result
        if (!result) { this.actionError = this.businessText(res.message, '原纠错单结果尚未核对，请勿重复提交'); return }
        const targetMatches = command.kind === 'create' ? ['PENDING_SECOND_APPROVAL', 'APPLIED', 'REJECTED'].includes(result.status) : result.status === (command.kind === 'approve' ? 'APPLIED' : 'REJECTED')
        if (!targetMatches) { this.actionError = '原纠错单尚未确认达到本次命令的目标结果，请继续核对，勿重复提交。'; return }
        if (!loaded || this.manifest?.ok !== true) { this.actionError = '部分完成：原纠错单已到达目标结果，但归档清单完整性尚未校验通过。请继续核对，勿重复提交。'; return }
        this.pendingCommand = null; this.actionError = ''; this.formError = ''; this.detailError = ''
        this.approveConfirmVisible = false; this.rejectConfirmVisible = false
        this.actionNotice = `核对完成：原纠错单${command.kind === 'create' ? `已创建，当前${this.statusLabel(result.status)}` : command.kind === 'approve' ? '已应用' : '已驳回'}，归档清单完整性校验通过；未重复发送命令。`
      } catch (error) {
        if (current() && this.pendingCommand === command) {
          if (this.selectedCaseId === command.caseId) this.detail = null
          this.actionError = this.businessText(error?.message, '原纠错单结果读取失败，请勿重复提交')
        }
      }
    }
  }
}
</script>

<style scoped>
/* A confirmation opened from the teleported modal drawer must stay above it. */
.aacw :deep(.app-confirm-dialog__mask) {
  z-index: calc(var(--z-modal) + 1);
}
.aacw { margin-top: 14px; min-width: 0; }
.aacw-context { display:grid; grid-template-columns:minmax(0,1fr) minmax(360px,.9fr); gap:22px; align-items:center; margin-bottom:12px; padding:15px 16px; border:1px solid #dbe5f2; border-left:3px solid var(--primary-color,#2563eb); border-radius:11px; background:var(--surface-color,#fff); }.aacw-context > div > span, .aacw-context p { color:var(--text-secondary,#64748b); font-size:12px; }.aacw-context h3 { margin:4px 0; color:var(--text-primary); font-size:17px; }.aacw-context p { margin:0; line-height:1.6; }.aacw-context ol { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:0; padding:0; list-style:none; }.aacw-context li { display:flex; gap:8px; min-width:0; }.aacw-context li b { display:grid; place-items:center; flex:0 0 24px; height:24px; border-radius:50%; color:#fff; background:var(--primary-color,#2563eb); font-size:11px; }.aacw-context li span, .aacw-context li strong, .aacw-context li small { display:block; }.aacw-context li strong { color:var(--text-primary); font-size:12px; }.aacw-context li small { margin-top:3px; color:var(--text-secondary,#64748b); font-size:10px; line-height:1.4; }
.aacw-tabs { display: flex; gap: 6px; padding: 4px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 10px; background: var(--fill-light, #f8fafc); overflow-x: auto; }
.aacw-tab { border: 0; border-radius: 8px; background: transparent; padding: 8px 14px; white-space: nowrap; cursor: pointer; color: var(--text-secondary, #475569); font: inherit; }
.aacw-tab.is-active { background: var(--surface-color, #fff); color: var(--primary-color, #2563eb); font-weight: 600; box-shadow: 0 1px 2px rgb(15 23 42 / 8%); }
.aacw-tab:focus-visible { outline: 2px solid var(--primary-color, #2563eb); outline-offset: 2px; }
.aacw-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 14px 0 10px; }
.aacw-kpi { min-width: 0; border: 1px solid var(--border-color, #e5e7eb); border-radius: 9px; padding: 12px; background: var(--surface-color, #fff); }
.aacw-kpi span { display: block; color: var(--text-secondary, #64748b); font-size: 12px; margin-bottom: 5px; }
.aacw-kpi strong { display: block; overflow-wrap: anywhere; }
.aacw-kpi .ok { color: var(--success-color, #15803d); }
.aacw-kpi .bad { color: var(--danger-color, #dc2626); }
.aacw-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0; }
.aacw-section-title { font-weight: 600; margin: 16px 0 8px; }
.aacw-section-title.no-margin { margin: 0; }
.aacw-muted { color: var(--text-secondary, #64748b); font-size: 12px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; overflow-wrap: anywhere; }
.aacw-form { display: flex; flex-direction: column; gap: 13px; }
.aacw-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.aacw-field > span { font-weight: 600; }
.aacw-field input, .aacw-field select, .aacw-field textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--border-color, #d1d5db); border-radius: 8px; padding: 9px 10px; background: var(--surface-color, #fff); color: inherit; font: inherit; }
.aacw-field textarea { resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.aacw-field small { color: var(--text-secondary, #64748b); line-height: 1.5; }
.aacw-detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; }
.aacw-meta-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.aacw-meta-grid > div { padding: 10px; border-radius: 8px; background: var(--fill-light, #f8fafc); min-width: 0; }
.aacw-meta-grid span { display: block; font-size: 12px; color: var(--text-secondary, #64748b); margin-bottom: 4px; }
.aacw-meta-grid strong { overflow-wrap: anywhere; }
.aacw-reason { margin-top: 12px; }
.aacw-reason span { font-size: 12px; color: var(--text-secondary, #64748b); }
.aacw-reason p { margin: 5px 0 0; white-space: pre-wrap; }
.aacw-compare { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.aacw-compare-card { min-width: 0; border: 1px solid var(--border-color, #e5e7eb); border-radius: 9px; overflow: hidden; }
.aacw-compare-card h4 { margin: 0; padding: 9px 10px; background: var(--fill-light, #f8fafc); font-size: 13px; }
.aacw-compare-card pre { margin: 0; padding: 10px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.55; max-height: 320px; overflow: auto; }
.aacw-compare-card p { padding: 0 10px; line-height: 1.6; overflow-wrap: anywhere; }
.aacw details { margin-top: 12px; }.aacw details summary { cursor: pointer; color: var(--text-secondary, #64748b); }.aacw details pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 320px; overflow: auto; }
@media (max-width: 980px) { .aacw-context { grid-template-columns:1fr; }.aacw-kpis, .aacw-meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px) { .aacw-context ol, .aacw-kpis, .aacw-meta-grid, .aacw-compare { grid-template-columns: 1fr; } }
</style>
