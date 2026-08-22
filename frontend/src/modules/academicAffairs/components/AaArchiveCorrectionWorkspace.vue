<template>
  <section class="aacw" aria-label="归档后纠错工作区">
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

    <template v-else-if="activeTab === 'facts'">
      <div class="aacw-kpis">
        <div class="aacw-kpi"><span>Manifest 当前版本</span><strong>{{ latestManifest ? `V${latestManifest.versionNo}` : '—' }}</strong></div>
        <div class="aacw-kpi"><span>当前 Hash</span><strong class="mono">{{ shortHash(latestManifest?.hash) }}</strong></div>
        <div class="aacw-kpi"><span>已应用纠错</span><strong>{{ manifest?.appliedCorrections ?? 0 }}</strong></div>
        <div class="aacw-kpi"><span>完整性结论</span><strong :class="manifest?.ok ? 'ok' : 'bad'">{{ manifest ? (manifest.ok ? '完整' : '异常') : '未校验' }}</strong></div>
      </div>
      <div class="aacw-toolbar">
        <AppButton size="small" variant="ghost" :loading="verifyBusy" @click="verifyNow">校验完整性</AppButton>
      </div>
      <AppInlineAlert
        v-if="manifest && !manifest.ok"
        type="danger"
        :description="`Manifest 版本链校验未通过：${manifest.reason || '未知异常'}`"
      />
      <AppInlineAlert
        v-else-if="manifest?.ok"
        type="success"
        description="Manifest 哈希、版本号、supersedes 链与已应用纠错 lineage 校验通过。"
      />
      <div class="aacw-section-title">归档事实</div>
      <EmptyState v-if="!items.length" title="暂无归档事实摘要" description="该批次没有可展示的数据域完整性快照" />
      <DataTable v-else :columns="factColumns" :rows="items" row-key="domain">
        <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
        <template #cell-result="{ row }"><StatusTag :type="factType(row)" :label="factLabel(row)" dot /></template>
      </DataTable>
    </template>

    <template v-else-if="activeTab === 'corrections'">
      <div class="aacw-kpis">
        <div class="aacw-kpi"><span>待二审</span><strong>{{ correctionSummary.pending }}</strong></div>
        <div class="aacw-kpi"><span>已应用</span><strong>{{ correctionSummary.applied }}</strong></div>
        <div class="aacw-kpi"><span>已拒绝</span><strong>{{ correctionSummary.rejected }}</strong></div>
        <div class="aacw-kpi"><span>允许范围</span><strong>成绩 / 毕业结论</strong></div>
      </div>
      <div class="aacw-toolbar">
        <AppButton size="small" variant="primary" :disabled="busy" @click="openCreate">发起归档后纠错</AppButton>
        <AppButton size="small" variant="ghost" :loading="loading" @click="refreshAll">刷新服务端状态</AppButton>
      </div>
      <AppInlineAlert
        type="info"
        description="ARCHIVED 永久不解冻。申请仅进入待二审；只有不同操作人批准后才追加正式事实与 Manifest V(N+1)，驳回不会产生正式事实或新 Manifest。"
      />
      <EmptyState v-if="!corrections.length" title="暂无纠错申请" description="发现归档后错误时从这里发起正式纠错" />
      <DataTable v-else :columns="correctionColumns" :rows="corrections" row-key="caseId">
        <template #cell-businessType="{ row }">{{ businessLabel(row.businessType) }}</template>
        <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }">
          <AppButton size="small" variant="ghost" @click="openDetail(row)">查看 / 复核</AppButton>
        </template>
      </DataTable>
    </template>

    <template v-else>
      <div class="aacw-toolbar">
        <div>
          <div class="aacw-section-title no-margin">Manifest 版本链</div>
          <div class="aacw-muted">新版本只追加，旧 Manifest 永久保留并通过 supersedesId 串联。</div>
        </div>
        <AppButton size="small" variant="ghost" :loading="verifyBusy" @click="verifyNow">重新校验</AppButton>
      </div>
      <AppInlineAlert
        v-if="manifest"
        :type="manifest.ok ? 'success' : 'danger'"
        :description="manifest.ok ? '当前版本链完整。' : `版本链异常：${manifest.reason || '未知异常'}`"
      />
      <EmptyState v-if="!manifestVersions.length" title="未发现 Manifest" description="ARCHIVED 批次必须至少存在 Manifest V1" />
      <DataTable v-else :columns="manifestColumns" :rows="manifestVersions" row-key="manifestId">
        <template #cell-versionNo="{ row }"><strong>V{{ row.versionNo }}</strong></template>
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
          <span>目标正式事实 ID</span>
          <input v-model.trim="createForm.targetRef" :disabled="saving" inputmode="numeric" placeholder="填写正式成绩 / 毕业决定事实 ID" />
          <small>稳定正式事实引用；服务端应用时再次校验租户、归档批次与当前正式事实。</small>
        </label>
        <label class="aacw-field">
          <span>纠错原因</span>
          <textarea v-model.trim="createForm.reason" :disabled="saving" rows="3" maxlength="500" placeholder="至少 5 个字，说明发现错误的依据与原因" />
        </label>
        <label class="aacw-field">
          <span>修正内容（JSON）</span>
          <textarea v-model="createForm.correctionText" :disabled="saving" rows="5" spellcheck="false" />
          <small>成绩示例：{"score":65}。正式写入字段仍由服务端白名单命令决定。</small>
        </label>
        <label class="aacw-field">
          <span>证据清单（JSON）</span>
          <textarea v-model="createForm.evidenceText" :disabled="saving" rows="5" spellcheck="false" />
        </label>
        <label class="aacw-field">
          <span>风险等级</span>
          <select v-model="createForm.riskLevel" :disabled="saving">
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </label>
        <AppInlineAlert type="warning" description="提交不修改或解冻原归档版本；必须由另一名有归档管理权限的操作人二次复核。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="closeCreate">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">提交纠错申请</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="detailVisible" title="归档后纠错详情 / 二次复核" mode="modal" size="large" @close="closeDetail">
      <LoadingState v-if="detailLoading" />
      <template v-else-if="detail">
        <div class="aacw-detail-head">
          <div>
            <strong>纠错 #{{ detail.correctionNo }}</strong>
            <span class="aacw-muted"> · {{ businessLabel(detail.businessType) }} · 目标 {{ detail.targetRef }}</span>
          </div>
          <StatusTag :type="statusType(detail.status)" :label="statusLabel(detail.status)" dot />
        </div>
        <div class="aacw-meta-grid">
          <div><span>申请人</span><strong>{{ detail.requestedBy || '—' }}</strong></div>
          <div><span>风险等级</span><strong>{{ detail.riskLevel || '—' }}</strong></div>
          <div><span>二审通过人</span><strong>{{ detail.secondApprovedBy || '—' }}</strong></div>
          <div><span>驳回人</span><strong>{{ detail.rejectedBy || '—' }}</strong></div>
        </div>
        <div class="aacw-reason"><span>申请原因</span><p>{{ detail.reason }}</p></div>

        <div class="aacw-section-title">原事实与新事实对比</div>
        <div class="aacw-compare">
          <div class="aacw-compare-card">
            <h4>原正式事实</h4>
            <pre>{{ pretty(detail.originalOfficialFact) }}</pre>
          </div>
          <div class="aacw-compare-card">
            <h4>{{ detail.status === 'APPLIED' ? '新正式事实' : '拟形成事实（非正式）' }}</h4>
            <pre>{{ pretty(detail.status === 'APPLIED' ? detail.resultingOfficialFact : detail.proposedOfficialFact) }}</pre>
          </div>
        </div>

        <div class="aacw-section-title">申请修正与证据</div>
        <div class="aacw-compare">
          <div class="aacw-compare-card"><h4>申请修正</h4><pre>{{ pretty(detail.correction) }}</pre></div>
          <div class="aacw-compare-card"><h4>证据 Manifest</h4><pre>{{ pretty(detail.evidenceManifest) }}</pre></div>
        </div>

        <AppInlineAlert
          v-if="detail.status === 'APPLIED'"
          type="success"
          :description="`已形成正式事实 ${detail.officialFactType || ''}#${detail.officialFactId || ''}，Resulting Manifest #${detail.resultingManifestId || ''}。原事实和旧 Manifest 永久保留。`"
        />
        <AppInlineAlert
          v-else-if="detail.status === 'REJECTED'"
          type="warning"
          :description="`已驳回：${detail.rejectReason || '未提供原因'}。该申请未生成正式事实，也未生成新 Manifest。`"
        />
        <AppInlineAlert
          v-else
          type="warning"
          description="批准后将追加正式纠错事实并生成 Manifest V(N+1)，原 Manifest 永久保留；申请人本人执行二审会被服务端拒绝。"
        />
      </template>
      <template #footer>
        <AppButton variant="ghost" :disabled="busy" @click="closeDetail">关闭</AppButton>
        <AppButton
          v-if="detail?.status === 'PENDING_SECOND_APPROVAL'"
          variant="ghost"
          :disabled="busy"
          @click="askReject"
        >驳回</AppButton>
        <AppButton
          v-if="detail?.status === 'PENDING_SECOND_APPROVAL'"
          variant="primary"
          :disabled="busy"
          @click="askApprove"
        >二审通过并生成新正式事实</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="approveConfirmVisible"
      title="确认二次审批通过"
      message="批准后将追加正式纠错事实并生成新的 Manifest 版本；原事实和旧 Manifest 永久保留。确认继续？"
      confirm-text="确认批准并生成新事实"
      :submitting="busy"
      @confirm="submitApprove"
    />

    <AppConfirmDialog
      v-model:visible="rejectConfirmVisible"
      title="确认驳回归档后纠错"
      message="驳回后状态固定为 REJECTED，不生成正式事实，也不生成新的 Manifest 版本。"
      type="danger"
      confirm-text="确认驳回"
      :require-reason="true"
      reason-label="驳回原因"
      reason-placeholder="请说明证据不足、事实不成立或其他驳回依据"
      :reason-min-length="5"
      :submitting="busy"
      @confirm="submitReject"
    />
  </section>
</template>

<script>
import { DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicArchiveCorrectionApi as api } from '@/modules/academicAffairs/api/academic-archive-correction.api'
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
        { key: 'manifest', label: 'Manifest版本链' }
      ],
      activeTab: 'facts', loading: false, verifyBusy: false, busy: false,
      corrections: [], manifest: null,
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
        { key: 'versionNo', title: '版本' }, { key: 'hash', title: 'Manifest Hash' },
        { key: 'supersedesId', title: '上一个 Manifest' }
      ]
    }
  },
  computed: {
    batchId() { return this.batch?.batchId },
    correctionSummary() {
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
    batchId: {
      immediate: true,
      handler() {
        this.activeTab = 'facts'
        this.closeCreate()
        this.closeDetail()
        this.refreshAll()
      }
    }
  },
  methods: {
    emptyCreateForm() {
      return {
        businessType: 'GRADE', targetRef: '', reason: '',
        correctionText: '{\n  "score": 60\n}',
        evidenceText: '{\n  "kind": "MANUAL_REVIEW",\n  "refs": []\n}',
        riskLevel: 'HIGH'
      }
    },
    businessLabel(v) { return v === 'GRADE' ? '成绩' : v === 'GRADUATION' ? '毕业结论' : v },
    statusLabel(v) { return STATUS_LABEL[v] || v },
    statusType(v) { return v === 'APPLIED' ? 'success' : v === 'REJECTED' ? 'warning' : 'primary' },
    factState(row) { return String(row?.result || (row?.present ? 'PASS' : 'BLOCKED')).toUpperCase() },
    factLabel(row) { return FACT_LABEL[this.factState(row)] || '待确认' },
    factType(row) { return FACT_TYPE[this.factState(row)] || 'warning' },
    shortHash(hash) { return hash ? `${String(hash).slice(0, 12)}…` : '—' },
    pretty(value) { return value == null ? '—' : JSON.stringify(value, null, 2) },
    async refreshAll() {
      if (!this.batchId) return
      this.loading = true
      try {
        const [queue, verified] = await Promise.all([
          api.list(this.batchId, { page: 1, pageSize: 100 }), api.verifyManifest(this.batchId)
        ])
        if (queue.code === 0) this.corrections = Array.isArray(queue.data?.items) ? queue.data.items : []
        else toast.error(queue.message || '纠错列表加载失败')
        if (verified.code === 0) this.manifest = verified.data
        else toast.error(verified.message || 'Manifest 校验失败')
      } catch (error) {
        toast.error(error?.message || '归档纠错工作区加载失败')
      } finally { this.loading = false }
    },
    async verifyNow() {
      if (!this.batchId || this.verifyBusy) return
      this.verifyBusy = true
      try {
        const res = await api.verifyManifest(this.batchId)
        if (res.code === 0) {
          this.manifest = res.data
          res.data?.ok ? toast.success('Manifest 版本链校验通过') : toast.error(`Manifest 校验异常：${res.data?.reason || '未知异常'}`)
        } else toast.error(res.message || 'Manifest 校验失败')
      } finally { this.verifyBusy = false }
    },
    openCreate() { this.createForm = this.emptyCreateForm(); this.formError = ''; this.createVisible = true },
    closeCreate() { if (!this.saving) { this.createVisible = false; this.formError = '' } },
    parseObject(text, label) {
      let value
      try { value = JSON.parse(text) } catch { throw new Error(`${label}必须是合法 JSON`) }
      if (!value || Array.isArray(value) || typeof value !== 'object' || !Object.keys(value).length) throw new Error(`${label}不能为空对象`)
      return value
    },
    async submitCreate() {
      if (this.saving) return
      this.formError = ''
      if (!this.createForm.targetRef) { this.formError = '请填写目标正式事实 ID'; return }
      if (this.createForm.reason.length < 5) { this.formError = '纠错原因至少 5 个字'; return }
      let correction, evidenceManifest
      try {
        correction = this.parseObject(this.createForm.correctionText, '修正内容')
        evidenceManifest = this.parseObject(this.createForm.evidenceText, '证据清单')
      } catch (error) { this.formError = error.message; return }
      this.saving = true
      try {
        const res = await api.create(this.batchId, {
          businessType: this.createForm.businessType, targetRef: this.createForm.targetRef,
          reason: this.createForm.reason, correction, evidenceManifest, riskLevel: this.createForm.riskLevel
        })
        if (res.code !== 0) { this.formError = res.message || '提交失败'; return }
        const caseId = res.data?.caseId
        toast.success('纠错申请已提交，等待不同操作人二次审批')
        this.createVisible = false
        this.activeTab = 'corrections'
        await this.authoritativeRefresh(caseId)
      } catch (error) { this.formError = error?.message || '提交失败' }
      finally { this.saving = false }
    },
    async openDetail(row) {
      const caseId = row?.caseId || row
      if (!caseId) return
      this.detailVisible = true
      this.detailLoading = true
      try {
        const res = await api.detail(caseId)
        if (res.code === 0) this.detail = res.data
        else { toast.error(res.message || '纠错详情加载失败'); this.detailVisible = false }
      } finally { this.detailLoading = false }
    },
    closeDetail() {
      if (this.busy) return
      this.detailVisible = false; this.detail = null
      this.approveConfirmVisible = false; this.rejectConfirmVisible = false
    },
    askApprove() {
      if (this.detail?.status === 'PENDING_SECOND_APPROVAL' && !this.busy) this.approveConfirmVisible = true
    },
    askReject() {
      if (this.detail?.status === 'PENDING_SECOND_APPROVAL' && !this.busy) this.rejectConfirmVisible = true
    },
    async submitApprove() {
      if (!this.detail || this.busy) return
      const caseId = this.detail.caseId
      this.busy = true
      try {
        const res = await api.approve(caseId)
        if (res.code !== 0) { toast.error(res.message || '二次审批失败'); return }
        this.approveConfirmVisible = false
        toast.success(`已应用正式纠错事实并生成 Manifest V${res.data?.manifestVersion || '(N+1)'}`)
        await this.authoritativeRefresh(caseId)
      } finally { this.busy = false }
    },
    async submitReject(payload = {}) {
      if (!this.detail || this.detail.status !== 'PENDING_SECOND_APPROVAL' || this.busy) return
      const reason = String(payload?.reason || '').trim()
      if (reason.length < 5) { toast.error('驳回原因至少 5 个字'); return }
      const caseId = this.detail.caseId
      this.busy = true
      try {
        const res = await api.reject(caseId, reason)
        if (res.code !== 0) { toast.error(res.message || '驳回失败'); return }
        this.rejectConfirmVisible = false
        toast.success('已驳回；未生成正式事实或新的 Manifest')
        await this.authoritativeRefresh(caseId)
      } finally { this.busy = false }
    },
    async authoritativeRefresh(caseId) {
      await this.refreshAll()
      this.$emit('refresh-batch')
      if (caseId && this.detailVisible) await this.openDetail(caseId)
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
@media (max-width: 980px) { .aacw-kpis, .aacw-meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px) { .aacw-kpis, .aacw-meta-grid, .aacw-compare { grid-template-columns: 1fr; } }
</style>
