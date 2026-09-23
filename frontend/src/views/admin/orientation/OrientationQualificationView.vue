<template>
  <ModulePageShell
    flat title="资格与入学确认"
    watermark-purpose="报到资格判定"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 名新生`" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无新生" description="当前数据范围内没有匹配的新生" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-checkinEligibility="{ row }">
          <StatusTag :type="row.checkinEligibility?.eligible ? 'success' : 'warning'" :label="row.checkinEligibility?.eligible ? '可到校核验' : '暂不能现场核验'" />
        </template>
        <template #cell-qualification="{ row }">
          <StatusTag :type="qualificationType(row.verdict, row.stage)" :label="qualificationText(row.verdict, row.stage)" dot />
        </template>
        <template #cell-blockedReason="{ row }">
          <span :class="{ 'oq-muted': !row.blockers?.length }">{{ blockerText(row) }}</span>
        </template>
        <template #cell-reportStatus="{ row }">
          <StatusTag :type="reportType(row.reportStatus)" :label="reportText(row.reportStatus, row.stage)" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <AppConfirmDialog v-model:visible="dispositionVisible" title="调整报到安排" :message="dispositionRow ? `学生：${dispositionRow.name}。未到校或取消入学会释放预留床位；延期保留床位。` : ''" :submitting="disposing" :confirm-disabled="dispositionReason.trim().length < 5" @confirm="onDisposition"><div class="oq-finalize-field"><label for="disposition-status">处理结果</label><select id="disposition-status" v-model="dispositionStatus"><option value="NO_SHOW">未到校</option><option value="DEFERRED">延期报到</option><option value="CANCELLED">取消入学</option><option value="RESUME">恢复报到</option></select><label for="disposition-reason">原因</label><textarea id="disposition-reason" v-model="dispositionReason" placeholder="填写核实情况，至少 5 个字" /></div></AppConfirmDialog>
      <AppConfirmDialog
        v-model:visible="confirmVisible"
        title="重新计算报到资格"
        :message="confirmRow ? `将更新「${confirmRow.name}」的办理情况。` : ''"
        type="primary"
        confirm-text="确认重算"
        @confirm="onConfirm"
      />

      <AppConfirmDialog
        v-model:visible="activateVisible"
        title="激活学生身份与账号"
        :message="activateRow ? `为「${activateRow.name}」建立或绑定正式学生主档和登录账号，随后学生才能登录并领取报到码。` : ''"
        type="primary"
        confirm-text="确认激活"
        :confirm-disabled="!activateStudentNo.trim()"
        :submitting="activating"
        @confirm="onActivateConfirm"
      >
        <div class="oq-finalize-field">
          <label>正式学号</label>
          <AppTextInput v-model="activateStudentNo" placeholder="请输入学校正式学号" />
          <small>激活后学生可登录 电脑端或小程序办理迎新。</small>
        </div>
      </AppConfirmDialog>

      <AppConfirmDialog
        v-model:visible="finalizeVisible"
        title="学院最终确认入学"
        :message="finalizeRow ? `确认「${finalizeRow.name}」已完成现场报到，并将正式学生主档推进到在读阶段。` : ''"
        type="primary"
        confirm-text="确认入学并建档"
        :confirm-disabled="!finalizeStudentNo.trim()"
        :submitting="finalizing"
        @confirm="onFinalizeConfirm"
      >
        <div class="oq-finalize-field">
          <label>正式学号</label>
          <AppTextInput v-model="finalizeStudentNo" placeholder="请输入学校正式学号" />
          <small>已绑定主档时保持原学号；未绑定时将按此学号幂等创建主档与账号。</small>
        </div>
      </AppConfirmDialog>

      <AppConfirmDialog
        v-model:visible="credentialVisible"
        title="新账号已创建"
        message="初始凭据仅在本次确认后显示，请通过学校安全渠道交给学生。"
        type="warning"
        confirm-text="我已安全记录"
        cancel-text="稍后记录"
        @confirm="credentialVisible = false"
      >
        <div v-if="credential" class="oq-credential">
          <div>登录名：<strong>{{ credential.loginName }}</strong></div>
          <div>临时密码：<strong>{{ credential.temporaryPassword }}</strong></div>
          <small>首次登录必须修改密码。</small>
        </div>
      </AppConfirmDialog>
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/qualification：只展示服务端 OrientationQualificationService 裁决。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog, AppTextInput } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', verdict: '' })

export default {
  name: 'OrientationQualificationView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    EmptyState, LoadingState, ErrorState, AppConfirmDialog, AppTextInput, TableActionColumn, NoPermissionState
  },
  data() {
    return {
      ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(), confirmVisible: false, confirmRow: null,
      activateVisible: false, activateRow: null, activateStudentNo: '', activating: false,
      finalizeVisible: false, finalizeRow: null, finalizeStudentNo: '', finalizing: false,
      dispositionRow: null, dispositionVisible: false, dispositionStatus: 'NO_SHOW', dispositionReason: '', disposing: false, credentialVisible: false, credential: null, activateRequestId: '', finalizeRequestId: ''
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' },
        { key: 'queue', label: '办理队列', type: 'select', options: [{ value: 'ready', label: '可确认入学' }, { value: 'blocked', label: '待补办' }] },
        { key: 'verdict', label: '资格结论', type: 'select', options: [
          { value: 'QUALIFIED', label: '手续齐全' },
          { value: 'NOT_QUALIFIED', label: '仍需补办' },
          { value: 'MANUAL_REVIEW', label: '需人工核查' }
        ] }
      ]
    },
    tableColumns() {
      return [
        { key: 'name', title: '姓名' },
        { key: 'className', title: '班级' },
        { key: 'checkinEligibility', title: '现场核验条件' },
        { key: 'qualification', title: '全部手续' },
        { key: 'reportStatus', title: '现场报到' },
        { key: 'blockedReason', title: '受阻原因' },
        { key: 'actions', title: '操作' }
      ]
    }
  },
  async created() {
    const ctx = await api.getOrientationContext()
    if (ctx.code === 0) this.ctx = ctx.data
    if (this.$route.query.queue) this.filters.queue = String(this.$route.query.queue)
    if (this.$route.query.keyword) this.filters.keyword = String(this.$route.query.keyword)
    await this.load()
  },
  watch: { '$route.query.keyword'(value) { if (value !== undefined) { this.filters.keyword = String(value); this.search() } } },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try {
        const res = await api.getOrientationQualifications({ ...this.filters, batchId: this.$route.query.batchId || undefined, orientationStudentId: this.$route.query.orientationStudentId || undefined, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    qualificationText(verdict, stage) { return ({ CANCELLED: '已停止办理', NO_SHOW: '已登记未到校', DEFERRED: '等待恢复报到' })[stage] || ({ QUALIFIED: '手续齐全', NOT_QUALIFIED: '仍需补办', MANUAL_REVIEW: '需人工核查' })[verdict] || '待核实' },
    qualificationType(verdict, stage) {
      if (['CANCELLED', 'NO_SHOW', 'DEFERRED'].includes(stage)) return 'default'
      return ({ QUALIFIED: 'success', NOT_QUALIFIED: 'danger', MANUAL_REVIEW: 'warning' })[verdict] || 'default'
    },
    reportText(status, stage) {
      if (stage === 'CANCELLED') return '已取消入学'
      return ({ NOT_REPORTED: '未现场报到', PREPARED: '已预报到，待到校', NO_SHOW: '未到校', DELAYED: '延期报到', CANCELLED: '已取消', CHECKED_IN: '已现场报到', COLLEGE_CONFIRMED: '学院已确认' })[status] || (status ? '状态待确认' : '—')
    },
    reportType(status) {
      return ({ CHECKED_IN: 'warning', COLLEGE_CONFIRMED: 'success' })[status] || 'default'
    },
    blockerText(row) {
      if (row.stage === 'CANCELLED') return '已取消入学，后续手续已停止；如需继续请先恢复报到。'
      if (row.stage === 'NO_SHOW') return '已登记未到校；确认继续入学后，请先恢复报到。'
      if (row.stage === 'DEFERRED') return '已延期报到，已有预留床位保留；确认到校计划后恢复办理。'
      return row.blockers?.length ? row.blockers.map((item) => item.message).join('；') : '—'
    },
    rowActions(row) {
      const actions = [
        { key: 'student', label: '学生详情' },
        { key: 'recalculate', label: '刷新资格' }
      ]
      const identityBlocked = !row.profileStudentId || row.blockers?.some((item) => ['IDENTITY_NOT_LINKED', 'ACCOUNT_NOT_LINKED'].includes(item.code))
      const paused = ['NO_SHOW', 'CANCELLED', 'DEFERRED'].includes(row.stage)
      if (!paused && identityBlocked && this.perms['orientation.identity.activate']?.allowed) actions.push({ key: 'activate', label: '激活学生账号' })
      if (row.canFinalize && this.perms['orientation.enrollment.finalize']?.allowed) actions.push({ key: 'finalize', label: '学院确认入学' })
      if (!['CHECKED_IN', 'COLLEGE_CONFIRMED'].includes(row.reportStatus) && this.perms['orientation.enrollment.finalize']?.allowed) actions.push({ key: 'disposition', label: paused ? '恢复或调整报到' : '报到安排' })
      return actions
    },
    onRowAction(key, row) {
      if (key === 'disposition') { this.dispositionRow = row; this.dispositionReason = ''; this.dispositionStatus = ['NO_SHOW', 'CANCELLED', 'DEFERRED'].includes(row.stage) ? 'RESUME' : 'NO_SHOW'; this.dispositionVisible = true }
      if (key === 'student') this.$router.push({ path: `/admin/orientation/students/${row.id}`, query: { batchId: row.batchId || this.$route.query.batchId } })
      if (key === 'recalculate') { this.confirmRow = row; this.confirmVisible = true }
      if (key === 'activate') {
        if (['NO_SHOW', 'CANCELLED', 'DEFERRED'].includes(row.stage)) return
        this.activateRequestId = globalThis.crypto?.randomUUID?.() || `orientation-activate-${Date.now()}`
        this.activateRow = row
        this.activateStudentNo = row.studentNo || ''
        this.activateVisible = true
      }
      if (key === 'finalize') {
        this.finalizeRequestId = globalThis.crypto?.randomUUID?.() || `orientation-finalize-${Date.now()}`
        this.finalizeRow = row
        this.finalizeStudentNo = row.studentNo || ''
        this.finalizeVisible = true
      }
    },
    async onDisposition() { if (this.disposing || !this.dispositionRow) return; this.disposing = true; try { const r = await api.dispositionOrientationStudent(this.dispositionRow.id, { expectedVersion: this.dispositionRow.version, status: this.dispositionStatus, reason: this.dispositionReason }); if (r.code !== 0) return toast.error(r.message); this.dispositionVisible = false; toast.success('报到安排已更新'); await this.load() } finally { this.disposing = false } },
    async onConfirm() {
      const row = this.confirmRow; if (!row) return
      const res = await api.recalculateOrientationQualification(row.id)
      if (res && res.code === 0) { toast.success(`办理情况已更新：${this.qualificationText(res.data.verdict)}`); this.confirmVisible = false; await this.load() }
      else toast.error((res && res.message) || '资格重算失败')
    },
    async onActivateConfirm() {
      if (!this.activateRow || this.activating) return
      this.activating = true
      const clientRequestId = this.activateRequestId
      try {
        const res = await api.activateOrientationIdentity(this.activateRow.id, {
          expectedVersion: this.activateRow.version,
          studentNo: this.activateStudentNo.trim(),
          clientRequestId
        })
        if (!res || res.code !== 0) return toast.error(res?.message || '账号激活失败')
        this.activateVisible = false
        toast.success('学生身份与账号已激活，可登录领取报到凭证')
        this.credential = res.data.initialCredential || null
        if (this.credential) this.credentialVisible = true
        await this.load()
      } finally {
        this.activating = false
      }
    },
    async onFinalizeConfirm() {
      if (!this.finalizeRow || this.finalizing) return
      this.finalizing = true
      const clientRequestId = this.finalizeRequestId
      try {
        const res = await api.finalizeOrientationEnrollment(this.finalizeRow.id, {
          expectedVersion: this.finalizeRow.version,
          studentNo: this.finalizeStudentNo.trim(),
          clientRequestId
        })
        if (!res || res.code !== 0) return toast.error(res?.message || '学院确认失败')
        this.finalizeVisible = false
        toast.success('学院确认完成，学生已进入正式在读阶段')
        this.credential = res.data.initialCredential || null
        if (this.credential) this.credentialVisible = true
        await this.load()
      } finally {
        this.finalizing = false
      }
    }
  }
}
</script>

<style scoped>
.oq-muted {
  color: var(--t3);
}
.oq-finalize-field { display: grid; gap: 8px; margin-top: 14px; }
.oq-finalize-field label { font-weight: 600; }
.oq-finalize-field select,.oq-finalize-field textarea { border:1px solid var(--border-light); border-radius:5px; padding:10px; background:var(--bg-card); color:var(--text-primary); font:inherit; }
.oq-finalize-field small, .oq-credential small { color: var(--text-tertiary); }
.oq-credential { display: grid; gap: 8px; padding: 12px; border-radius: 8px; background: var(--warning-50); }
</style>
