<template>
  <ModulePageShell
    class="aa-schedule-workspace"
    title="课表发布"
    subtitle="检查课表完整性、发布通知，并查阅发布记录。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="returnToQueue">返回原队列</AppButton>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次 / 排课</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleStageRail :active-index="focusBatch?.status === 'PUBLISHED' ? 4 : 3" />
      <AaOperationReceipt :receipt="receipt" />
      <AppInlineAlert v-if="commandError" type="danger" :description="commandError" />
      <div v-if="pendingWrite" class="aa-pending-read">
        <span>系统只会重新读取指定批次与当前正式头，不会再次提交发布或作废请求。</span>
        <AppButton @click="retryPendingRead">只读核对结果</AppButton>
      </div>
      <AppSectionCard v-if="focusBatchId || focusError" compact title="指定批次与当前正式版本">
        <LoadingState v-if="focusLoading" />
        <ErrorState v-else-if="focusError" :description="focusError" @retry="loadFocusBatch" />
        <div v-else-if="focusBatch" class="aa-truth-card">
          <div class="aa-truth-card__head">
            <div>
              <strong>{{ focusBatch.batchName || `课表批次 ${focusBatch.batchId}` }}</strong>
              <p>批次 ID {{ focusBatch.batchId }} · {{ statusLabel(focusBatch.status) }}</p>
            </div>
            <AppStatusTag :type="formalHead.type" dot>{{ formalHead.label }}</AppStatusTag>
          </div>
          <div class="aa-truth-card__grid">
            <div><span>正式范围</span><strong>{{ formalScopeText(focusBatch) }}</strong></div>
            <div><span>当前正式批次</span><strong>{{ activeBatchText(focusBatch) }}</strong></div>
            <div><span>正式头版本</span><strong>{{ headVersionText(focusBatch) }}</strong></div>
            <div><span>正式头发布时间</span><strong>{{ headPublishedAtText(focusBatch) }}</strong></div>
          </div>
          <p class="mp-note">{{ formalHead.detail }}</p>
        </div>
      </AppSectionCard>
      <AppSectionCard compact v-if="gate.visible" title="发布门禁检查">
        <LoadingState v-if="gate.loading" />
        <template v-else-if="gate.summary">
          <div class="aa-gate-head">
            <div>
              <strong>{{ gate.batch?.batchName }}</strong>
              <p>请先处理漏排、超排和课程冲突。全部检查通过后可继续发布。</p>
            </div>
            <AppStatusTag :type="gate.summary.complete ? 'success' : 'danger'" dot>
              {{ gate.summary.complete ? '全部通过' : '存在阻断项' }}
            </AppStatusTag>
          </div>
          <div class="aa-gate-grid">
            <div v-for="item in gateChecklist" :key="item.label" :class="['aa-gate-item', item.ok ? 'is-ok' : 'is-blocked']">
              <span>{{ item.ok ? '✓' : '!' }}</span>
              <div><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></div>
            </div>
          </div>
          <p v-if="gate.summary.pendingTeacherObjections" class="aa-gate-warning">
            教师异议待处理 {{ gate.summary.pendingTeacherObjections }} 条，建议正式发布前处理完毕。
          </p>
          <div class="aa-gate-actions">
            <AppButton @click="gate.visible = false">收起检查</AppButton>
            <AppButton v-if="!gate.summary.complete" @click="openWorkbench(gate.batch)">返回排课工作台处理</AppButton>
            <AppButton
              v-else-if="gate.intent !== 'view'"
              variant="primary"
              :loading="gate.submitting"
              :disabled="writeBusy"
              @click="confirmGateAction"
            >{{ gate.intent === 'pub' ? '确认正式发布并通知师生' : '确认进入预发布' }}</AppButton>
          </div>
        </template>
      </AppSectionCard>

      <AppSectionCard compact title="待发布 / 已发布批次">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无课表批次" description="请先到「课表批次/排课」页新建批次并排课" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="batchId">
          <template #cell-batchName="{ row }">
            <button class="mp-link" @click="openExactBatch(row)">{{ row.batchName }}</button>
          </template>
          <template #cell-status="{ row }">
            <AppStatusTag :type="scheduleBatchColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <div class="aa-actions">
              <button v-if="row.status === 'DRAFT'" class="mp-link" :disabled="writeBusy || isPending(row, 'pre')" @click="openGate(row, 'pre')">{{ isPending(row, 'pre') ? '结果待确认' : '检查并预发布' }}</button>
              <button v-if="row.status === 'PRE_PUBLISHED'" class="mp-link" :disabled="writeBusy || isPending(row, 'pub')" @click="openGate(row, 'pub')">{{ isPending(row, 'pub') ? '结果待确认' : '检查并正式发布' }}</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openGate(row, 'view')">复核发布门禁</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openPublished(row)">查看已发布课表</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openChangeLedger(row)">调停课台账</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link aa-danger" :disabled="writeBusy || isPending(row, 'void')" @click="openVoid(row)">{{ isPending(row, 'void') ? '结果待确认' : '作废重发（重大纠错）' }}</button>
              <span v-if="row.status === 'ARCHIVED'" class="aa-archived">{{ statusLabel(row.status) }}</span>
            </div>
          </template>
        </DataTable>
        <p class="mp-note">发布后课表不可直接修改。日常单课位调课、停课、补课走「调停课」审批；只有整批课表存在重大错误、必须整体重排时，才使用危险操作「作废重发」。</p>
      </AppSectionCard>

      <AppSectionCard compact title="发布记录（发布/作废历史留痕）">
        <ErrorState v-if="recError" :description="recError" @retry="loadRecords" />
        <LoadingState v-else-if="recLoading" />
        <EmptyState v-else-if="!records.length" title="暂无发布记录" />
        <DataTable v-else :columns="recColumns" :rows="records" row-key="recordId">
          <template #cell-action="{ row }">
            <AppStatusTag :type="row.action === 'PUBLISH' ? 'success' : 'danger'" dot>
              {{ row.action === 'PUBLISH' ? '发布' : '作废重发' }}
            </AppStatusTag>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="voidDlg.visible"
      title="作废重发课表批次"
      type="danger"
      confirm-text="确认作废"
      :require-reason="true"
      reason-label="作废原因"
      :submitting="voidDlg.submitting"
      @confirm="doVoid"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 课表发布（/admin/academic-affairs/schedule/publish）：13B 课表管理 Tier1 R2。
 * 发布/预发布/作废重发动作复用既有 schedule-batches 端点（与「课表批次/排课」页同一批 API，不重复实现）；
 * 本页新增能力是发布记录历史（GET /schedule/publish-records，t_aa_schedule_publish）。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { SCHEDULE_BATCH_STATUS, scheduleBatchColor } from '@/modules/academicAffairs/constants/teaching'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { scheduleTruthPresentation } from '../components/parallel-a/scheduleTruthPresentation'
import { isConflictResult, isDeniedResult } from '../components/parallel-a/resultState'
import { readAllPages } from '../components/parallel-a/pagedRead'
import { academicRouteState, createAcademicRequestGate } from '../academicFlowContext'
import AaScheduleStageRail from '../components/AaScheduleStageRail.vue'

export default {
  name: 'AaSchedulePublishView',
  components: { AaOperationReceipt, ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppInlineAlert, AaScheduleStageRail },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      disposed: false, listSeq: 0, loading: true, error: '', rows: [], receipt: null, commandError: '', pendingWrite: null,
      recSeq: 0, recLoading: true, records: [], recError: '',
      focusBatchId: '', focusBatch: null, focusLoading: false, focusError: '',
      gateSeq: 0, gate: { visible: false, loading: false, submitting: false, batch: null, summary: null, intent: 'pre' },
      voidDlg: { visible: false, submitting: false, batchId: '' },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'status', title: '状态' },
        { key: 'publishAt', title: '发布时间' },
        { key: 'actions', title: '操作', width: '420px' }
      ],
      recColumns: [
        { key: 'action', title: '动作' },
        { key: 'operatorName', title: '操作人' },
        { key: 'notifiedCount', title: '通知教师数' },
        { key: 'note', title: '备注' },
        { key: 'createdAt', title: '时间' }
      ]
    }
  },
  computed: {
    identityKey() { return JSON.stringify([this.academicFlow?.identity?.(), this.ctx?.currentRole, this.ctx?.dataScope, this.ctx?.ctxKey, this.ctx?.permissionVersion]) },
    writeBusy() { return !!this.pendingWrite || this.gate.submitting || this.voidDlg.submitting },
    formalHead() { return scheduleTruthPresentation(this.focusBatch) },
    gateChecklist() {
      const row = this.gate.summary || {}
      return [
        { label: '教学任务可排', ok: row.totalTasks > 0 && !row.invalidTaskCount, detail: `任务 ${row.totalTasks || 0} 个 · 配置异常 ${row.invalidTaskCount || 0} 个` },
        { label: '应排节次完整', ok: !row.missingTaskCount && !row.overScheduledTaskCount, detail: `应排 ${row.expectedSessions || 0} 节 · 已排 ${row.scheduledSessions || 0} 节 · 漏排 ${row.missingTaskCount || 0} 个任务` },
        { label: '课位关联有效', ok: !row.orphanItemCount && !row.invalidCoordinateItemCount, detail: `孤立课位 ${row.orphanItemCount || 0} · 周次坐标异常 ${row.invalidCoordinateItemCount || 0}` },
        { label: '硬冲突清零', ok: !row.hardConflicts, detail: `硬冲突 ${row.hardConflicts || 0} · 软冲突 ${row.softConflicts || 0}` }
      ]
    }
  },
  watch: {
    '$route.fullPath'() { this.syncRoute() },
    identityKey() {
      this.clearSensitive('身份或数据范围已变化，正在重新读取。')
      this.commandError = ''; this.focusError = ''
      this.syncRoute(); this.load(); this.loadRecords()
    }
  },
  created() {
    this.focusGate = createAcademicRequestGate(() => this.focusContextKey())
    this.syncRoute(); this.load(); this.loadRecords()
  },
  beforeUnmount() { this.disposed = true; this.listSeq += 1; this.recSeq += 1; this.gateSeq += 1; this.focusGate.invalidate() },
  methods: {
    isPending(row, kind) { return this.pendingWrite?.batchId === row.batchId && this.pendingWrite?.kind === kind },
    clearSensitive(message) {
      this.listSeq += 1; this.recSeq += 1; this.gateSeq += 1; this.focusGate.invalidate()
      this.rows = []; this.records = []; this.receipt = null; this.pendingWrite = null
      this.focusBatch = null; this.focusLoading = false; this.focusError = message || '读取权限已变化'
      this.commandError = ''
      this.gate = { visible: false, loading: false, submitting: false, batch: null, summary: null, intent: 'pre' }
      this.voidDlg = { visible: false, submitting: false, batchId: '' }
      this.loading = false; this.recLoading = false
      this.error = message || '无权读取课表发布数据，已清除先前显示内容'
      this.recError = this.error
    },
    async requestResult(request) {
      try { return await request() }
      catch (error) { return { code: 'REQUEST_ERROR', status: error?.response?.status, message: error?.message || '网络连接中断，请只读核对结果' } }
    },
    async readBatches() {
      return readAllPages(
        (page, pageSize) => academicAffairsApi.getScheduleBatches({ page, pageSize }),
        { identity: row => row.batchId }
      )
    },
    async readFormalBatch(batchId) {
      const response = await this.requestResult(() => academicAffairsApi.getScheduleBatch(batchId))
      if (response.code !== 0) return response
      if (String(response.data?.batchId || '') !== String(batchId)) {
        return { code: 'OBJECT_MISMATCH', message: '服务端返回了不同的课表批次，已拒绝更新当前页面' }
      }
      return response
    },
    focusContextKey() {
      return JSON.stringify([
        this.identityKey, this.$route?.fullPath, this.focusBatchId
      ])
    },
    syncRoute() {
      if (!this.focusGate || this.disposed) return
      this.focusGate.invalidate(); this.focusBatch = null; this.focusError = ''; this.focusLoading = false
      this.gateSeq += 1
      this.voidDlg = { visible: false, submitting: false, batchId: '' }
      this.gate = { visible: false, loading: false, submitting: false, batch: null, summary: null, intent: 'pre' }
      const state = academicRouteState(this.$route)
      this.focusBatchId = state.error ? '' : state.batchId
      if (state.error) { this.focusError = state.error; return }
      if (this.focusBatchId) this.loadFocusBatch()
    },
    async loadFocusBatch() {
      if (!this.focusBatchId) return
      const current = this.focusGate.begin()
      const batchId = this.focusBatchId
      this.focusLoading = true; this.focusError = ''; this.focusBatch = null
      const response = await this.readFormalBatch(batchId)
      if (!current()) return
      this.focusLoading = false
      if (isDeniedResult(response)) return this.clearSensitive(response.message)
      if (response.code === 0) this.focusBatch = response.data
      else this.focusError = response.message || '指定课表批次读取失败，请重试'
    },
    openExactBatch(row) {
      this.$router.push({ path: this.$route.path, query: { ...this.$route.query, batchId: String(row.batchId) } })
    },
    formalScopeText(batch) {
      const truth = batch?.activeTruth || {}
      if (!truth.scopeType && !truth.scopeId) return '待服务端确认'
      return `${({ SCHOOL: '全校', COLLEGE: '学院' })[truth.scopeType] || '范围待确认'}${truth.scopeId ? ` · ${truth.scopeId}` : ''}`
    },
    activeBatchText(batch) {
      const truth = batch?.activeTruth
      if (truth?.truthStatus === 'VERIFIED') return truth.activeBatchId || '待服务端确认'
      if (truth?.truthStatus === 'NOT_PUBLISHED') return '尚无正式头'
      return '待服务端确认'
    },
    headVersionText(batch) {
      const truth = batch?.activeTruth
      if (truth?.truthStatus === 'NOT_PUBLISHED') return '—'
      return truth?.truthStatus === 'VERIFIED' && truth.headVersion != null ? truth.headVersion : '待服务端确认'
    },
    headPublishedAtText(batch) {
      const truth = batch?.activeTruth
      if (truth?.truthStatus === 'NOT_PUBLISHED') return '—'
      return truth?.truthStatus === 'VERIFIED' ? (truth.publishedAt || '—') : '待服务端确认'
    },
    hasCurrentFormalHead(batch) {
      const truth = batch?.activeTruth
      return truth?.truthStatus === 'VERIFIED' && truth.isCurrent === true && String(truth.activeBatchId || '') === String(batch?.batchId || '')
    },
    async reconcilePendingExact() {
      const pending = this.pendingWrite
      if (!pending || pending.identity !== this.identityKey) return
      const context = this.focusContextKey()
      const formal = await this.readFormalBatch(pending.batchId)
      if (this.disposed || this.pendingWrite !== pending || pending.identity !== this.identityKey || context !== this.focusContextKey()) return
      if (isDeniedResult(formal)) return this.clearSensitive(formal.message)
      if (formal.code !== 0) return formal
      if (formal.data.status !== pending.expectedStatus) return formal
      const headConfirmed = pending.kind !== 'pub' || this.hasCurrentFormalHead(formal.data)
      if (!pending.acknowledged || !headConfirmed) {
        this.receipt = {
          pending: true,
          title: '发布结果待确认',
          object: `${formal.data.batchName}（${formal.data.batchId}）`,
          status: headConfirmed ? `已读取到${this.statusLabel(formal.data.status)}，但无法归属到本次请求` : `${this.statusLabel(formal.data.status)}，尚未取得当前正式头`,
          time: pending.kind === 'pub' && this.hasCurrentFormalHead(formal.data) ? (formal.data.activeTruth?.publishedAt || formal.data.publishAt || '') : '',
          next: '请继续只读核对指定批次和当前正式头；确认前不要重复提交。'
        }
        return formal
      }
      this.pendingWrite = null; this.commandError = ''
      this.receipt = {
        title: pending.kind === 'pre' ? '课表已进入预发布并核对' : pending.kind === 'void' ? '课表批次已作废并完成正式核对' : '课表已正式发布并核对',
        object: `${formal.data.batchName}（${formal.data.batchId}）`,
        status: this.statusLabel(formal.data.status),
        time: pending.kind === 'pub' ? (formal.data.activeTruth?.publishedAt || formal.data.publishAt || '') : '',
        next: pending.kind === 'pub'
          ? '下一步：师生四端继续读取当前正式课表；后续单课位变更走调停课。'
          : pending.kind === 'void'
            ? '下一步：回到排课工作台创建或维护纠错批次，完成后重新发布。'
            : '下一步：复核门禁后执行正式发布。'
      }
      if (String(this.focusBatchId) === String(formal.data.batchId)) this.focusBatch = formal.data
      return formal
    },
    async retryPendingRead() {
      this.commandError = ''
      const context = this.focusContextKey()
      const formal = await this.reconcilePendingExact()
      if (this.disposed || context !== this.focusContextKey()) return
      if (formal && formal.code !== 0 && !isDeniedResult(formal)) this.commandError = formal.message || '指定批次核对失败，请稍后再试'
      if (this.focusBatchId) await this.loadFocusBatch()
    },
    scheduleBatchColor,
    statusLabel(s) { return SCHEDULE_BATCH_STATUS[s] || (s ? '状态待确认' : '') },
    returnToQueue() {
      return this.academicFlow?.back(this.$route.query.returnToken, '/admin/academic-affairs/schedule')
        || this.$router.push('/admin/academic-affairs/schedule')
    },
    openPublished(row) { this.$router.push({ path: `/admin/academic-affairs/schedule/${row.batchId}/views`, query: { returnToken: this.academicFlow?.captureReturn?.() } }) },
    openChangeLedger(row) { this.$router.push({ path: '/admin/academic-affairs/schedule-change', query: { termId: row.termId || '', returnToken: this.academicFlow?.captureReturn?.() } }) },
    openWorkbench(row) { this.$router.push({ path: '/admin/academic-affairs/scheduling', query: { batchId: row?.batchId || '', returnToken: this.academicFlow?.captureReturn?.() } }) },
    async openGate(row, intent = 'pre') {
      if (this.writeBusy) return
      const seq = ++this.gateSeq
      this.commandError = ''; this.receipt = null
      this.gate = { visible: true, loading: true, submitting: false, batch: row, summary: null, intent }
      const context = this.focusContextKey()
      const response = await this.requestResult(() => academicAffairsApi.getScheduleSummary(row.batchId))
      if (this.disposed || context !== this.focusContextKey() || seq !== this.gateSeq || String(this.gate.batch?.batchId) !== String(row.batchId)) return
      this.gate.loading = false
      if (response.code === 0) this.gate.summary = response.data
      else {
        this.gate.visible = false
        if (isDeniedResult(response)) this.clearSensitive(response.message)
        else this.commandError = response.message || '发布门禁检查失败，请重试'
      }
    },
    async confirmGateAction() {
      if (this.writeBusy || !this.gate.summary?.complete || !this.gate.batch || this.gate.intent === 'view') return
      const gate = this.gate
      gate.submitting = true
      try { await this.act(gate.batch, gate.intent) }
      finally { if (this.gate === gate) gate.submitting = false }
    },
    async act(row, kind) {
      if (this.pendingWrite) return
      const operationContext = this.focusContextKey()
      const expectedBefore = kind === 'pre' ? 'DRAFT' : 'PRE_PUBLISHED'
      const expectedAfter = kind === 'pre' ? 'PRE_PUBLISHED' : 'PUBLISHED'
      const gate = await this.requestResult(() => academicAffairsApi.getScheduleSummary(row.batchId))
      if (this.disposed || operationContext !== this.focusContextKey()) return
      if (isDeniedResult(gate)) return this.clearSensitive(gate.message)
      const before = await this.readFormalBatch(row.batchId)
      if (this.disposed || operationContext !== this.focusContextKey()) return
      if (isDeniedResult(before)) return this.clearSensitive(before.message)
      if (gate.code !== 0 || !gate.data?.complete || before.code !== 0 || before.data.status !== expectedBefore) {
        this.commandError = gate.message || '发布门禁或批次状态已变化，请重新核对'
        this.gate.summary = gate.code === 0 ? gate.data : null
        await this.load()
        return
      }
      const fn = kind === 'pre' ? academicAffairsApi.prePublishSchedule : academicAffairsApi.publishSchedule
      this.pendingWrite = { identity: this.identityKey, batchId: row.batchId, batchName: row.batchName, kind, expectedStatus: expectedAfter, acknowledged: false }
      const pending = this.pendingWrite
      const res = await this.requestResult(() => fn(row.batchId))
      if (this.disposed || pending.identity !== this.identityKey || this.pendingWrite !== pending) return
      if (isDeniedResult(res)) return this.clearSensitive(res.message)
      pending.acknowledged = res.code === 0 && String(res.data?.batchId) === String(pending.batchId) && res.data?.status === pending.expectedStatus
      if (isConflictResult(res)) this.pendingWrite = null
      if (operationContext !== this.focusContextKey()) return
      if (isConflictResult(res)) {
        this.commandError = res.message || '批次事实已变化，本次发布被拒绝，请重新核对'
        this.gate.summary = null
        await this.load()
        return
      }
      const formal = await this.reconcilePendingExact()
      if (this.disposed || operationContext !== this.focusContextKey()) return
      if (!this.pendingWrite) {
        this.gate.visible = false
        await this.load(); await this.loadRecords()
        return
      }
      this.commandError = isConflictResult(res) ? `${res.message || '批次事实已变化'}；请重新核对，系统不会自动重放发布请求。` : (formal?.message || res.message || '发布结果待确认，请刷新核对')
      if (!this.receipt?.pending) this.receipt = { pending: true, title: '发布结果待确认', object: `${row.batchName}（${row.batchId}）`, status: '尚未读取到匹配的正式批次状态与正式头', time: '', next: '请继续只读核对指定批次；确认前不要重复发布。' }
    },
    openVoid(row) { if (!this.writeBusy) this.voidDlg = { visible: true, submitting: false, batchId: row.batchId } },
    async doVoid(payload) {
      const reason = (payload && payload.reason) || ''
      const batchId = this.voidDlg.batchId
      const row = this.rows.find(item => String(item.batchId) === String(batchId))
      if (!row || this.writeBusy) return
      const dialog = this.voidDlg
      const operationContext = this.focusContextKey()
      this.commandError = ''; this.receipt = null
      this.voidDlg.submitting = true
      const before = await this.readFormalBatch(batchId)
      if (this.disposed || operationContext !== this.focusContextKey()) return
      if (isDeniedResult(before)) return this.clearSensitive(before.message)
      if (before.code !== 0 || before.data.status !== 'PUBLISHED') {
        this.voidDlg.submitting = false
        this.commandError = before.message || '批次状态已变化；作废原因已保留，请重新核对。'
        await this.load()
        return
      }
      this.pendingWrite = { identity: this.identityKey, batchId, batchName: row.batchName, kind: 'void', expectedStatus: 'ARCHIVED', acknowledged: false }
      const pending = this.pendingWrite
      const res = await this.requestResult(() => academicAffairsApi.voidReissueSchedule(batchId, reason))
      if (this.voidDlg === dialog) dialog.submitting = false
      if (this.disposed || pending.identity !== this.identityKey || this.pendingWrite !== pending) return
      if (isDeniedResult(res)) return this.clearSensitive(res.message)
      pending.acknowledged = res.code === 0 && String(res.data?.batchId) === String(pending.batchId) && res.data?.status === pending.expectedStatus
      if (isConflictResult(res)) this.pendingWrite = null
      if (operationContext !== this.focusContextKey()) return
      if (isConflictResult(res)) {
        this.commandError = res.message || '批次事实已变化，本次作废被拒绝，原因已保留'
        await this.load()
        return
      }
      const formal = await this.reconcilePendingExact()
      if (this.disposed || operationContext !== this.focusContextKey()) return
      if (!this.pendingWrite) {
        this.voidDlg.visible = false
        await this.load(); await this.loadRecords()
        return
      }
      this.commandError = isConflictResult(res)
        ? `${res.message || '批次事实已变化'}；作废原因已保留，请重新核对，系统不会自动重放作废请求。`
        : (formal?.message || res.message || '作废结果待确认，请刷新核对')
      if (!this.receipt?.pending) this.receipt = { pending: true, title: '作废结果待确认', object: `${row.batchName}（${row.batchId}）`, status: '尚未读取到已归档的指定批次状态', time: '', next: '请继续只读核对指定批次；确认前不要重复作废。' }
    },
    async load() {
      const seq = ++this.listSeq, identity = this.identityKey
      this.loading = true
      this.error = ''
      const res = await this.requestResult(() => this.readBatches())
      if (this.disposed || identity !== this.identityKey || seq !== this.listSeq) return
      if (res.code === 0) { this.rows = res.data.list; await this.reconcilePendingExact() }
      else if (isDeniedResult(res)) return this.clearSensitive(res.message)
      else { this.rows = []; this.error = res.message || '课表批次读取失败，请重试' }
      if (!this.disposed && identity === this.identityKey && seq === this.listSeq) this.loading = false
    },
    async loadRecords() {
      const seq = ++this.recSeq, identity = this.identityKey
      this.recLoading = true
      this.recError = ''
      try {
        const res = await readAllPages(
          (page, pageSize) => academicAffairsApi.getSchedulePublishRecords({ page, pageSize }),
          { identity: row => row.recordId }
        )
        if (this.disposed || identity !== this.identityKey || seq !== this.recSeq) return
        if (res.code === 0) this.records = res.data.list
        else if (isDeniedResult(res)) return this.clearSensitive(res.message)
        else { this.records = []; this.recError = res.message || '发布记录读取失败，请重试' }
      } catch (exception) {
        if (this.disposed || identity !== this.identityKey || seq !== this.recSeq) return
        this.records = []
        this.recError = exception?.message || '发布记录读取失败，请重试'
      } finally {
        if (!this.disposed && identity === this.identityKey && seq === this.recSeq) this.recLoading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/schedule-workspace.css';
.aa-danger { color: var(--danger-600, #f53f3f); }
.aa-archived { color: var(--text-400, #8a9099); font-size: 13px; }
.aa-actions { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; }
.aa-pending-read { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid var(--warning-200, #fde68a); border-radius: 8px; background: var(--warning-50, #fffbeb); color: var(--warning-800, #92400e); font-size: 13px; }
.aa-truth-card { display: flex; flex-direction: column; gap: 14px; }
.aa-truth-card__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.aa-truth-card__head p { margin: 5px 0 0; color: var(--text-500, #86909c); font-size: 12px; }
.aa-truth-card__grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.aa-truth-card__grid > div { display: flex; min-width: 0; flex-direction: column; gap: 5px; padding: 10px 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-100, #f7f8fa); }
.aa-truth-card__grid span { color: var(--text-500, #86909c); font-size: 12px; }
.aa-truth-card__grid strong { color: var(--text-900, #1f2329); font-size: 13px; overflow-wrap: anywhere; }
.aa-gate-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.aa-gate-head p { margin: 6px 0 0; color: var(--text-500, #86909c); font-size: 13px; }
.aa-gate-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.aa-gate-item { display: flex; gap: 10px; padding: 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-100, #f7f8fa); }
.aa-gate-item > span { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; flex: 0 0 auto; font-weight: 700; }
.aa-gate-item div { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.aa-gate-item small { color: var(--text-500, #86909c); line-height: 1.5; }
.aa-gate-item.is-ok > span { color: var(--success-700, #15803d); background: var(--success-100, #dcfce7); }
.aa-gate-item.is-blocked { border-color: var(--danger-200, #fecaca); background: var(--danger-50, #fef2f2); }
.aa-gate-item.is-blocked > span { color: var(--danger-700, #b91c1c); background: var(--danger-100, #fee2e2); }
.aa-gate-warning { margin: 12px 0 0; padding: 10px 12px; border-radius: 8px; color: var(--warning-700, #b45309); background: var(--warning-50, #fffbeb); font-size: 13px; }
.aa-gate-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
@media (max-width: 980px) { .aa-truth-card__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .aa-gate-grid, .aa-truth-card__grid { grid-template-columns: 1fr; } .aa-gate-head, .aa-truth-card__head { flex-direction: column; } }
</style>
