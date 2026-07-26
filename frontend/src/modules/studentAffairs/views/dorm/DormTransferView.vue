<template>
  <AppPageShell
    title="调宿与退宿"
    subtitle="调宿走「辅导员 → 宿管」两级审批；审批人必须核对原床、目标床、学生和事由。"
    role-name="辅导员 / 宿管 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍调宿审批"
  >
    <template #actions>
      <AppPermissionButton
        :allowed="canBtn('studentAffairs.dorm.transfer.create')"
        code="studentAffairs.dorm.transfer.create"
        :loading="actioning"
        @click="openTransfer"
      >发起调宿</AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载调宿申请..." @retry="load" @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="调宿申请">
        <div v-if="studentFilterLabel" class="sa-student-filter"><span>{{ studentFilterLabel }}</span><button type="button" class="mp-link" @click="clearStudentFilter">清除筛选</button></div>
        <AppInlineAlert v-if="items.some((x) => isPending(x.status) && (!x.fromBedLabel || !x.toBedLabel))" type="warning" description="部分待审批记录缺少可读床位信息，已禁止通过。请刷新或联系宿舍管理员核对房源数据。" />

        <DataTable v-if="items.length || pagination.total > 0" :columns="transferColumns" :rows="items" row-key="transferId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span><div class="mp-cell-sub">{{ row.studentNo || '学号未提供' }}</div></template>
          <template #cell-route="{ row }">
            <div class="route-cell"><span class="route-from">{{ row.fromBedLabel || fallbackBed(row, 'from') }}</span><span class="route-arrow">→</span><strong class="route-to">{{ row.toBedLabel || fallbackBed(row, 'to') }}</strong></div>
          </template>
          <template #cell-reason="{ row }"><span class="reason-cell">{{ row.reason || '未填写事由' }}</span></template>
          <template #cell-node="{ row }">{{ nodeLabel(row.currentNode || row.status) }}</template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="statusLabel(row.status)" /></template>
          <template #cell-actions="{ row }">
            <div class="sa-actions" v-if="canAction(row, 'APPROVE') || canAction(row, 'REJECT')">
              <AppPermissionButton v-if="canAction(row, 'APPROVE')" :allowed="canBtn('studentAffairs.dorm.transfer.approve')" code="studentAffairs.dorm.transfer.approve" size="sm" :loading="actioning" :disabled="!row.fromBedLabel || !row.toBedLabel || !hasVersion(row)" @click="openApprove(row)">核对后通过</AppPermissionButton>
              <AppPermissionButton v-if="canAction(row, 'REJECT')" :allowed="canBtn('studentAffairs.dorm.transfer.approve')" code="studentAffairs.dorm.transfer.approve" size="sm" variant="secondary" danger :loading="actioning" :disabled="!hasVersion(row)" @click="openReject(row)">驳回</AppPermissionButton>
            </div>
            <span v-else class="sa-muted">当前节点无操作</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无调宿申请</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer :visible="dlg.visible" title="发起调宿" @close="closeTransfer">
      <div class="dr-form">
        <AppFormItem label="调宿学生" required><AppStudentPicker v-model="dlg.studentId" placeholder="按姓名 / 学号搜索" :disabled="actioning" /></AppFormItem>
        <AppFormItem label="目标楼栋" required><AppDormBuildingPicker v-model="dlg.buildingId" :options="buildingOptions" placeholder="选择楼栋" :disabled="actioning" @change="onBuildingChange" /></AppFormItem>
        <AppFormItem label="目标房间" required><AppDormRoomPicker v-model="dlg.roomId" :options="roomOptions" :query="{ buildingId: dlg.buildingId }" :disabled="actioning || !dlg.buildingId" :placeholder="dlg.buildingId ? '选择房间' : '请先选楼栋'" @change="onRoomChange" /></AppFormItem>
        <AppFormItem label="目标床位（仅列空床）" required><AppDormBedPicker v-model="dlg.toBedId" :options="bedOptions" :query="{ roomId: dlg.roomId, vacantOnly: true }" :disabled="actioning || !dlg.roomId" :placeholder="bedPlaceholder" /></AppFormItem>
        <div v-if="dlg.toBedId" class="target-preview"><span>目标床位</span><strong>{{ selectedTargetLabel }}</strong></div>
        <AppFormItem label="调宿事由（5-300字）" required><AppTextarea v-model="dlg.reason" :rows="3" :maxlength="300" :disabled="actioning" placeholder="请填写可供审批核验的真实调宿原因" /></AppFormItem>
        <p class="char-count">{{ (dlg.reason || '').trim().length }}/300</p>
        <p class="dr-hint">提交后进入辅导员、宿管两级审批；终审通过前原床保持不变。</p>
        <AppInlineAlert v-if="dlg.error" type="danger" :description="dlg.error" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="actioning" @click="closeTransfer">取消</AppButton><AppButton variant="primary" :loading="actioning" :disabled="!validTransferForm" @click="submitDlg">核对并提交</AppButton></template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="approveDlg.visible"
      title="确认通过调宿申请"
      :message="approveDlg.message"
      confirm-text="确认通过"
      :submitting="actioning"
      @confirm="submitApprove"
    />
    <AppConfirmDialog
      v-model:visible="rejDlg.visible"
      title="驳回调宿申请"
      type="danger"
      confirm-text="确认驳回"
      require-reason
      :reason-min-length="5"
      reason-label="驳回原因（5-300字）"
      phrase-scene-key="sa.dorm.reject"
      :submitting="actioning"
      @confirm="submitReject"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
  AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag, AppStudentPicker,
  AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker, AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { resolveTodoStatus, readStudentFilter } from '@/modules/studentAffairs/utils/todoFilterSemantics'

const PENDING_STATUSES = ['SUBMITTED', 'COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'DORM_REVIEW', 'PENDING']
const TRANSFER_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'route', title: '原床 → 目标床', width: '280px' },
  { key: 'reason', title: '调宿事由' },
  { key: 'node', title: '当前节点' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '210px' }
]

export default {
  name: 'DormTransferView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
    AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag, AppStudentPicker,
    AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker, AppTextarea, DataTable
  },
  data() {
    return {
      transferColumns: TRANSFER_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [], statusCounts: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      buildings: [], rooms: [], beds: [],
      studentFilter: { studentId: '', studentNo: '', studentName: '' }, statusMatch: null,
      dlg: { visible: false, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' },
      approveDlg: { visible: false, transferId: '', version: null, message: '' },
      rejDlg: { visible: false, transferId: '', version: null }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      const hit = this.items.find((x) => String(x.studentId) === String(f.studentId)) || {}
      const name = f.studentName || hit.realName || '学生'
      const no = f.studentNo || hit.studentNo || ''
      return `当前学生筛选：${name}${no ? ` / ${no}` : ''}`
    },
    metricCards() {
      const s = this.statusCounts
      const pending = s === null ? '—' : PENDING_STATUSES.reduce((n, key) => n + Number(s[key] || 0), 0)
      return [
        { key: 'p', label: '待审批', value: pending, accent: 'warning' },
        { key: 'e', label: '已执行', value: s === null ? '—' : Number(s.EXECUTED || 0), accent: 'primary' },
        { key: 'r', label: '已驳回', value: s === null ? '—' : Number(s.REJECTED || 0), accent: 'info' },
        { key: 't', label: '合计', value: s === null ? '—' : Number(s.ALL || Object.values(s).reduce((a, b) => a + Number(b || 0), 0)), accent: 'info' }
      ]
    },
    buildingOptions() { return this.buildings.map((b) => ({ value: String(b.buildingId), label: b.buildingName || `楼栋 #${b.buildingId}` })) },
    roomOptions() { return this.rooms.map((r) => ({ value: String(r.roomId), label: `${r.roomNo || `房间 #${r.roomId}`}${r.vacantBeds != null ? `（空 ${r.vacantBeds}）` : ''}` })) },
    bedOptions() { return this.beds.filter((b) => b.status === 'VACANT' && !b.isCurrent).map((b) => ({ value: String(b.bedId), label: `${b.bedNo} 号床` })) },
    bedPlaceholder() { if (!this.dlg.roomId) return '请先选房间'; return this.bedOptions.length ? '选择空床' : '该房间当前无空床' },
    selectedTargetLabel() {
      const b = this.buildings.find((x) => String(x.buildingId) === String(this.dlg.buildingId)) || {}
      const r = this.rooms.find((x) => String(x.roomId) === String(this.dlg.roomId)) || {}
      const bed = this.beds.find((x) => String(x.bedId) === String(this.dlg.toBedId)) || {}
      return [b.buildingName, r.roomNo && `${r.roomNo}室`, bed.bedNo && `${bed.bedNo}床`].filter(Boolean).join(' / ') || `床位 #${this.dlg.toBedId}`
    },
    validTransferForm() {
      const reason = (this.dlg.reason || '').trim()
      return !!this.dlg.studentId && !!this.dlg.toBedId && reason.length >= 5 && reason.length <= 300
    },
    serverStatus() {
      if (!this.statusMatch || !this.statusMatch.length) return undefined
      if (this.statusMatch.every((x) => PENDING_STATUSES.includes(x))) return 'PENDING'
      return this.statusMatch.length === 1 ? this.statusMatch[0] : undefined
    }
  },
  mounted() { this.applyRouteFilters(); this.load(); this.loadBuildings() },
  watch: { '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.load() } },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row && row.version !== undefined && row.version !== null && row.version !== '' },
    canAction(row, action) { return Array.isArray(row.allowedActions) ? row.allowedActions.includes(action) : (this.isPending(row.status) && ['APPROVE', 'REJECT'].includes(action)) },
    fallbackBed(row, side) {
      const prefix = side === 'from' ? 'from' : 'to'
      return [row[`${prefix}BuildingName`], row[`${prefix}RoomNo`] && `${row[`${prefix}RoomNo`]}室`, row[`${prefix}BedNo`] && `${row[`${prefix}BedNo`]}床`].filter(Boolean).join(' / ') || (row[`${prefix}BedId`] ? `床位 #${row[`${prefix}BedId`]}` : '未记录')
    },
    applyRouteFilters() {
      const q = this.$route.query || {}; this.studentFilter = readStudentFilter(q)
      if (!q.status) { this.statusMatch = null; return }
      this.statusMatch = resolveTodoStatus('dormTransfer', q.status).matchStatuses
    },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      const q = { ...this.$route.query }; delete q.studentId; delete q.studentNo; delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const sid = this.studentFilter && this.studentFilter.studentId
        const res = await studentAffairsApi.listDormTransfers({ page: this.pagination.page, pageSize: this.pagination.pageSize, studentId: sid || undefined, status: this.serverStatus })
        let rows = res.data.items || []
        if (this.statusMatch && this.statusMatch.length && !this.serverStatus) rows = rows.filter((x) => this.statusMatch.includes(x.status) || (this.statusMatch.includes('PENDING') && this.isPending(x.status)))
        this.items = rows
        this.pagination.total = res.data.total != null ? res.data.total : rows.length
        this.statusCounts = res.data.statusCounts || null
      } catch (e) { this.errorMessage = e.message || '调宿加载失败' } finally { this.loading = false }
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async loadBuildings() { try { this.buildings = (await studentAffairsApi.listDormBuildings({ pageSize: 200 })).data.items || [] } catch { this.buildings = [] } },
    openTransfer() { this.dlg = { visible: true, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' }; this.rooms = []; this.beds = [] },
    closeTransfer() { if (!this.actioning) this.dlg.visible = false },
    async onBuildingChange() {
      this.dlg.roomId = ''; this.dlg.toBedId = ''; this.dlg.error = ''; this.beds = []
      if (!this.dlg.buildingId) { this.rooms = []; return }
      try { this.rooms = (await studentAffairsApi.listDormRooms(this.dlg.buildingId, { pageSize: 200 })).data.items || [] }
      catch (e) { this.rooms = []; this.dlg.error = e.message || '房间加载失败' }
    },
    async onRoomChange() {
      this.dlg.toBedId = ''; this.dlg.error = ''
      if (!this.dlg.roomId) { this.beds = []; return }
      try { this.beds = (await studentAffairsApi.listDormBeds(this.dlg.roomId)).data.items || [] }
      catch (e) { this.beds = []; this.dlg.error = e.message || '床位加载失败' }
    },
    async submitDlg() {
      const d = this.dlg; const reason = (d.reason || '').trim()
      if (!d.studentId) { d.error = '请选择调宿学生'; return }
      if (!d.toBedId) { d.error = '请选择目标空床'; return }
      if (reason.length < 5 || reason.length > 300) { d.error = '调宿事由需5-300字'; return }
      if (!window.confirm(`确认发起调宿？\n目标：${this.selectedTargetLabel}\n\n提交后进入辅导员、宿管两级审批。`)) return
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.submitDormTransfer({ studentId: d.studentId, toBedId: d.toBedId, reason }))
      if (ok) d.visible = false; else d.error = this.errorMessage
    },
    openApprove(row) {
      if (!this.canAction(row, 'APPROVE') || !row.fromBedLabel || !row.toBedLabel || !this.hasVersion(row)) return
      this.approveDlg = { visible: true, transferId: row.transferId, version: row.version, message: `${row.realName || '该学生'}\n${row.fromBedLabel}\n→ ${row.toBedLabel}\n\n确认学生、床位、事由及当前审批节点均无误。` }
    },
    openReject(row) { if (this.canAction(row, 'REJECT') && this.hasVersion(row)) this.rejDlg = { visible: true, transferId: row.transferId, version: row.version } },
    async submitApprove() {
      const d = this.approveDlg
      const ok = await this.runAction(() => studentAffairsApi.reviewDormTransfer(d.transferId, 'APPROVE', '', d.version))
      if (ok) d.visible = false
    },
    async submitReject({ reason }) {
      const d = this.rejDlg
      if ((reason || '').trim().length > 300) { this.errorMessage = '驳回原因不能超过300字'; return }
      const ok = await this.runAction(() => studentAffairsApi.reviewDormTransfer(d.transferId, 'REJECT', reason.trim(), d.version))
      if (ok) d.visible = false
    },
    async runAction(fn) {
      this.actioning = true; this.errorMessage = ''
      try { await fn(); await this.load(); return true }
      catch (e) { this.errorMessage = e.message || '操作失败'; return false }
      finally { this.actioning = false }
    },
    isPending(s) { return PENDING_STATUSES.includes(s) },
    nodeLabel(n) { return ({ COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', DORM_REVIEW: '宿管审核' })[n] || (n || '—') },
    statusLabel(s) { return ({ SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', DORM_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回', CANCELLED: '已取消' })[s] || s },
    statusKind(s) { if (s === 'EXECUTED') return 'success'; if (s === 'REJECTED') return 'danger'; if (this.isPending(s)) return 'warning'; return 'info' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--space-4);margin-bottom:var(--space-4) }.sa-student-filter { display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);margin-bottom:var(--space-3);padding:var(--space-2) var(--space-3);border-radius:var(--radius-md);background:var(--warning-50,#fffbeb);border:1px solid var(--warning-200,#fde68a);font-size:var(--font-size-sm);color:var(--text-primary) }.sa-actions { display:flex;flex-wrap:wrap;gap:var(--space-2) }.sa-muted { color:var(--text-tertiary) }.sa-empty { color:var(--text-tertiary);padding:var(--space-4);text-align:center }.route-cell { display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:12px }.route-from { color:var(--text-secondary) }.route-arrow { color:var(--text-tertiary) }.route-to { color:var(--success-700,#15803d) }.reason-cell { display:block;max-width:220px;white-space:normal;line-height:1.5 }.dr-form { display:flex;flex-direction:column;gap:var(--space-4) }.dr-hint,.char-count { margin:0;color:var(--text-tertiary);font-size:var(--font-size-sm) }.char-count { text-align:right;margin-top:-12px }.target-preview { padding:10px 12px;border-radius:var(--radius-md);background:var(--primary-50,#eff6ff) }.target-preview span,.target-preview strong { display:block }.target-preview span { color:var(--text-tertiary);font-size:12px }.target-preview strong { margin-top:3px;color:var(--primary-700,#1d4ed8) }
@media (max-width:960px){.sa-grid--metrics{grid-template-columns:1fr 1fr}}
@import '@/styles/module-page.css';
</style>
