<template>
  <ModulePageShell
    title="工作量申报审核"
    subtitle="申报不能越过正式任务与学期边界"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pending" :disabled="submitting || loading" @click="queryPending">查询原审核结果（不会重提）</AppButton>
      <AaTeachingTaskObjectBar
        v-if="primaryRow"
        :name="`${primaryRow.teacherName || primaryRow.teacherKey || '教师'} · ${primaryRow.categoryLabel || '工作量申报'}`"
        :identity="`教师工作量申报 #${primaryRow.declarationId} · ${primaryRow.termCode || '学期待提供'}`"
        source="来源：教师正式申报记录；审核不越过教学任务、学期与统计口径边界。"
        :status="statusLabel(primaryRow.status)"
        owner="统计授权岗"
        next-owner="授权查询/导出岗；需办理时返回业务对象"
      />
      <AaTeachingTaskStageRail :current="3" current-note="当前审核与统计口径" :steps="workloadSteps" />
      <div class="aa-filter">
        <label class="aa-filter-field"><span>状态</span><AppSelect v-model="status" :options="statusOptions" @change="query" /></label>
        <label class="aa-filter-field"><span>学期</span><AppTermCodePicker v-model="termCode" placeholder="全部学期" @change="query" /></label>
        <AppButton variant="ghost" @click="query">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard title="工作量申报台账">
          <EmptyState v-if="!rows.length" title="暂无申报" description="教师在移动端提交工作量申报后，这里出现待审核记录" />
          <DataTable v-else :columns="columns" :rows="rows" row-key="declarationId" :pagination="pagination" @page-change="onPageChange">
            <template #cell-teacher="{ row }">{{ row.teacherName || row.teacherKey }}</template>
            <template #cell-termCode="{ row }">{{ row.termCode || '—' }}</template>
            <template #cell-description="{ row }"><span :title="row.description">{{ row.description || '—' }}</span></template>
            <template #cell-status="{ row }">
              <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
            </template>
            <template #cell-actions="{ row }">
              <template v-if="canReview && row.status === 'SUBMITTED'">
                <button class="mp-link" :disabled="submitting || Boolean(pending)" @click="openApprove(row)">核对并通过</button>
                <button class="mp-link mp-link--danger" :disabled="submitting || Boolean(pending)" @click="openReject(row)">驳回</button>
              </template>
              <span v-else class="aa-note-sm">{{ row.reviewNote || '—' }}</span>
            </template>
          </DataTable>
        </AppSectionCard>

        <AppSectionCard v-if="rejecting" :title="`驳回：${rejecting.teacherName || rejecting.teacherKey} · ${rejecting.categoryLabel} ${rejecting.hours}课时`">
          <AppFormItem label="驳回原因" required>
            <AppTextarea v-model="rejectNote" :rows="2" placeholder="驳回原因（必填，≥5字）" />
          </AppFormItem>
          <div class="aa-actions">
            <AppButton variant="primary" :disabled="invalid || Boolean(pending)" :loading="submitting" @click="doReject">确认驳回</AppButton>
            <AppButton variant="ghost" @click="rejecting = null">取消</AppButton>
          </div>
        </AppSectionCard>
      </template>
    </div>
    <AppConfirmDialog :visible="Boolean(approveTarget)" title="核对工作量申报" confirm-text="确认通过" :confirm-disabled="invalid || Boolean(pending)" :submitting="submitting" @update:visible="value => { if (!value) approveTarget = null }" @confirm="submitReview(approveTarget, 'APPROVE', '')">
      <AaObjectContext :name="approveTarget?.teacherName" :identity="`申报 #${approveTarget?.declarationId} · ${approveTarget?.termCode || '学期未提供'}`" :status="statusLabel(approveTarget?.status)" />
      <p>{{ approveTarget?.categoryLabel }} · {{ approveTarget?.hours }} 课时</p>
      <p>{{ approveTarget?.description || '未提供申报说明' }}</p>
      <p class="aa-note-sm">当前接口未提供关联教学任务与名单版本证据。通过仅表示申报审核状态，不代表正式授课关系、名单或薪酬核算已验证。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 工作量申报审核（/admin/academic-affairs/workload-review）：GET /workload-declarations + review。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextarea, AppTermCodePicker, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaObjectContext from '../components/parallel-a/AaObjectContext.vue'
import AaTeachingTaskStageRail from '../components/teaching-tasks/AaTeachingTaskStageRail.vue'
import AaTeachingTaskObjectBar from '../components/teaching-tasks/AaTeachingTaskObjectBar.vue'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

const STATUS = { SUBMITTED: '待审核', APPROVED: '已通过', REJECTED: '已驳回' }
const evidenceFields = ['declarationId', 'teacherKey', 'teacherName', 'termCode', 'category', 'hours', 'description', 'createdAt']
const sameEvidence = (left, right) => Boolean(left && right && evidenceFields.every(key => String(left[key] ?? '') === String(right[key] ?? '')))

export default {
  name: 'AaWorkloadReviewView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
      AppButton, AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextarea, AppTermCodePicker, AppConfirmDialog, AaOperationReceipt, AaObjectContext, AaTeachingTaskStageRail, AaTeachingTaskObjectBar
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', status: '', termCode: '', rows: [], rejecting: null, rejectNote: '', submitting: false,
      revision: 0, lifecycle: 0, receipt: null, approveTarget: null, pending: null, invalid: false, pagination: { page: 1, pageSize: 20, total: 0 },
      workloadSteps: [
        { label: '正式事实', note: '按真实状态解锁' },
        { label: '范围与学期', note: '按真实状态解锁' },
        { label: '统计口径', note: '按真实状态解锁' },
        { label: '明细下钻', note: '按真实状态解锁' },
        { label: '导出快照', note: '按真实状态解锁' }
      ],
      statusOptions: [
        { label: '全部', value: '' }, { label: '待审核', value: 'SUBMITTED' },
        { label: '已通过', value: 'APPROVED' }, { label: '已驳回', value: 'REJECTED' }
      ],
      columns: [
        { key: 'teacher', title: '教师' }, { key: 'termCode', title: '学期', align: 'center' },
        { key: 'categoryLabel', title: '类别', align: 'center' }, { key: 'hours', title: '申报课时', align: 'center' },
        { key: 'description', title: '工作说明' }, { key: 'status', title: '状态', align: 'center' },
        { key: 'actions', title: '操作', align: 'center' }
      ]
    }
  },
  computed: {
    canReview() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.stats.view') },
    primaryRow() { return this.rows[0] || null }
  },
  watch: {
    ctx: { flush: 'sync', handler() { this.lifecycle++; this.revision++; this.rows = []; this.pagination.total = 0; this.rejecting = null; this.approveTarget = null; this.rejectNote = ''; this.receipt = null; this.pending = null; this.submitting = false; this.load() } },
    termCode: { flush: 'sync', handler() { this.invalidateScope() } },
    status: { flush: 'sync', handler() { this.invalidateScope() } }
  },
  created() { this.load() },
  beforeUnmount() { this.revision++; this.lifecycle++; this.disposed = true },
  methods: {
    invalidateScope() { this.lifecycle++; this.revision++; this.invalid = true; this.approveTarget = null; this.rejecting = null; this.submitting = false; this.rows = []; this.pagination.total = 0; this.receipt = this.pending ? this.receipt : null },
    statusLabel(s) { return STATUS[s] || '状态待确认' },
    statusColor(s) {
      if (s === 'APPROVED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'SUBMITTED') return 'primary'
      return 'default'
    },
    query() { this.pagination.page = 1; this.load() },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      const revision = ++this.revision, context = this.ctx
      const current = () => !this.disposed && revision === this.revision && context === this.ctx
      this.loading = true
      this.error = ''
      this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.getWorkloadDeclarations({ status: this.status || undefined, termCode: this.termCode || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (!current()) return
        if (res.code === 0 && Array.isArray(res.data?.list)) { this.rows = res.data.list; this.pagination.total = res.data.total }
        else this.handleFailure(res, '申报台账读取失败')
      } catch (error) { if (current()) this.handleFailure(error, '网络连接失败，请重试。') }
      finally { if (current()) this.loading = false }
    },
    openApprove(row) { if (this.canReview && !this.submitting && !this.pending && row.status === 'SUBMITTED') { this.approveTarget = { ...row }; this.invalid = false } },
    openReject(row) {
      if (!this.canReview || this.submitting || this.pending || row.status !== 'SUBMITTED') return
      if (String(this.rejecting?.declarationId) !== String(row.declarationId)) this.rejectNote = ''
      this.rejecting = { ...row }; this.invalid = false
    },
    async doReject() {
      if (this.submitting) return
      if (!this.rejectNote || this.rejectNote.trim().length < 5) { toast.error('驳回原因必填且不少于 5 字'); return }
      await this.submitReview(this.rejecting, 'REJECT', this.rejectNote.trim())
    },
    async readDeclaration(row, current) {
      const seen = new Set()
      for (let page = 1; current(); page++) {
        const result = await academicAffairsApi.getWorkloadDeclarations({ termCode: row.termCode || undefined, page, pageSize: 200 })
        if (!current()) return null
        if (result.code !== 0) throw result
        const list = result.data?.list, total = Number(result.data?.total)
        if (!Array.isArray(list) || !Number.isSafeInteger(total) || total < 0) throw new Error('申报分页未完整返回，请重新查询。')
        for (const item of list) {
          const id = String(item.declarationId || '')
          if (!id || seen.has(id)) throw new Error('申报分页重复，请重新查询。')
          seen.add(id)
        }
        const found = list.find(item => String(item.declarationId) === String(row.declarationId))
        if (found) return found
        if (seen.size >= total) return null
        if (!list.length) throw new Error('申报分页缺失，请重新查询。')
      }
      return null
    },
    async readPending(current) {
      const pending = this.pending
      if (!pending) return
      const row = await this.readDeclaration(pending.row, current)
      if (!current() || pending !== this.pending) return
      const matches = sameEvidence(row, pending.row) && row.status === (pending.action === 'APPROVE' ? 'APPROVED' : 'REJECTED') && String(row.reviewNote || '') === pending.note
      const commandMatches = pending.commandEvidence && ['status', 'reviewNote', 'reviewedAt', 'reviewedBy'].every(key => String(row?.[key] ?? '') === String(pending.commandEvidence[key] ?? ''))
      const confirmed = Boolean(pending.acknowledged && matches && commandMatches)
      await this.load()
      if (!current() || pending !== this.pending || this.error) return
      this.receipt = { object: pending.redacted ? `申报 #${pending.row.declarationId} · 原办理信息已清除` : `申报 #${pending.row.declarationId} · ${pending.row.teacherName || pending.row.teacherKey} · ${pending.row.termCode || '学期未提供'}`, status: confirmed ? this.statusLabel(row.status) : '结果待确认', pending: !confirmed, time: confirmed ? row.reviewedAt : undefined, next: confirmed ? '正式审核状态已回读；统计按正式学期与授课关系核算。' : '原审核尚未确认。当前记录不能证明本次办理结果，只查询不重提，请联系教务核对。' }
      if (confirmed) { this.pending = null; this.approveTarget = null; this.rejecting = null; this.rejectNote = '' }
    },
    async queryPending() {
      if (!this.pending || this.submitting || this.loading || !this.canReview) return
      const context = this.ctx, lifecycle = this.lifecycle
      const current = () => !this.disposed && context === this.ctx && lifecycle === this.lifecycle
      this.submitting = true
      try { await this.readPending(current) } catch (error) { if (current()) this.handleFailure(error, '查询失败，请重试原结果。') }
      finally { if (current()) this.submitting = false }
    },
    async submitReview(row, action, note) {
      if (this.pending) return this.queryPending()
      if (!this.canReview || this.invalid || this.submitting || !row?.declarationId || row.status !== 'SUBMITTED' || !['APPROVE', 'REJECT'].includes(action)) return
      if (action === 'REJECT' && (!note || note.trim().length < 5)) return
      const frozen = { ...row }, frozenNote = (note || '').trim(), context = this.ctx, lifecycle = this.lifecycle
      const current = () => !this.disposed && context === this.ctx && lifecycle === this.lifecycle
      this.submitting = true
      let commandPhase = false
      try {
        const check = await this.readDeclaration(frozen, current)
        if (!current()) return
        if (!sameEvidence(check, frozen) || check.status !== 'SUBMITTED') { this.handleFailure({ code: 409001, message: '申报内容已变化，原确认失效，请重新核对。' }); return }
        this.pending = { row: frozen, action, note: frozenNote, acknowledged: false }
        this.receipt = { object: `申报 #${frozen.declarationId}`, status: '结果待确认', pending: true, next: '正在读取正式审核结果，请勿重复办理。' }
        commandPhase = true
        const result = await academicAffairsApi.reviewWorkloadDeclaration(frozen.declarationId, { action, note: frozenNote })
        commandPhase = false
        if (!current()) return
        if (result.code === 0) {
          const evidence = result.data
          const matches = sameEvidence(evidence, frozen) && evidence.status === (action === 'APPROVE' ? 'APPROVED' : 'REJECTED') && String(evidence.reviewNote || '') === frozenNote
          this.pending.acknowledged = Boolean(matches && evidence.reviewedBy && evidence.reviewedAt && Number.isFinite(Date.parse(evidence.reviewedAt)))
          if (this.pending.acknowledged) this.pending.commandEvidence = { status: evidence.status, reviewNote: evidence.reviewNote, reviewedAt: evidence.reviewedAt, reviewedBy: evidence.reviewedBy }
        }
        else {
          if (isDeniedResult(result) || isConflictResult(result) || String(result.code || '').startsWith('400') || result.bizCode === 'VALIDATION_ERROR') this.pending = null
          this.handleFailure(result, '审核结果未确认，请查询原结果。')
          if (!this.pending) { if (isConflictResult(result)) await this.load(); return }
        }
        await this.readPending(current)
      } catch (error) {
        if (current()) {
          if (commandPhase && (isDeniedResult(error) || isConflictResult(error) || String(error?.code || '').startsWith('400') || error?.bizCode === 'VALIDATION_ERROR')) this.pending = null
          this.handleFailure(error, '连接中断，请查询原审核结果。')
          if (isConflictResult(error)) await this.load()
          else if (this.pending && !isDeniedResult(error)) {
            try { await this.readPending(current) } catch (readError) { if (current()) this.handleFailure(readError, '原审核结果查询失败，请重试查询。') }
          }
        }
      } finally { if (current()) this.submitting = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback
      if (isDeniedResult(result)) {
        // A denied read cannot prove that an earlier command was rejected.
        // Keep only its opaque ID as a replay barrier; erase its business payload.
        this.pending = this.pending ? { row: { declarationId: this.pending.row.declarationId }, acknowledged: false, redacted: true } : null
        this.revision++; this.loading = false; this.rows = []; this.pagination.total = 0; this.rejecting = null; this.approveTarget = null; this.rejectNote = ''; this.receipt = null
      }
      else { this.invalid = true; this.receipt = { status: isConflictResult(result) ? '事实已变化，保留输入' : '结果需重新核对', pending: true, next: '重新读取申报台账并重新打开确认；不会自动重提。' } }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-note-sm { color: var(--text-500, #646a73); font-size: 12px; }
.mp-link--danger { color: var(--danger-600, #f53f3f); margin-left: 10px; }
.aa-actions { margin-top: 12px; display: flex; gap: 12px; }
</style>
