<template>
  <AppPageShell
    title="调宿与退宿"
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

    <nav v-if="!recordId" class="dr-tabs" aria-label="住宿办理工作区">
      <button v-for="tab in workspaceTabs" :key="tab.key" type="button" :aria-current="activeTab === tab.key ? 'page' : undefined" :class="{ active: activeTab === tab.key }" @click="switchTab(tab.key)">{{ tab.label }}</button>
    </nav>
    <div v-if="recordId" class="sa-student-filter"><span>{{ activeTab === 'checkout' ? '退宿单' : '调宿申请' }} #{{ recordId }}</span><button type="button" class="mp-link" @click="clearRecordFocus">返回{{ activeTab === 'checkout' ? '退宿' : '调宿' }}队列</button></div>
    <div v-if="studentFilterLabel" class="sa-student-filter"><span>{{ studentFilterLabel }}</span><button type="button" class="mp-link" @click="clearStudentFilter">清除筛选</button></div>
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载调宿申请..." @retry="load" @back="$router.push('/admin/student-affairs/dashboard')">



      <section v-if="activeTab === 'transfer'" class="dr-workspace">
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
        <p v-else class="sa-empty">当前范围暂无调宿申请。需要办理时，可从页面右上角发起调宿。</p>
      </section>

      <section v-if="activeTab === 'checkout'" class="dr-workspace">
        <p class="dr-section-hint">确认退宿后释放床位；有未完成调宿或住宿记录冲突的，请先处理。</p>
        <DataTable v-if="checkoutItems.length" :columns="checkoutColumns" :rows="checkoutItems" row-key="requestId" :pagination="checkoutPagination" @page-change="onCheckoutPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.studentName || ('学生#' + row.studentId) }}</span><div class="mp-cell-sub">{{ row.studentNo }}</div></template>
          <template #cell-bed="{ row }">{{ row.bedLabel || ('床位#' + row.bedId) }}</template>
          <template #cell-type="{ row }">{{ checkoutTypeLabel(row.requestType) }}</template>
          <template #cell-blockers="{ row }"><span :class="row.blockers?.length ? 'dr-blocked' : 'sa-muted'">{{ row.blockers?.length ? row.blockers.map((x) => x.message).join('；') : '无阻断' }}</span></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'BLOCKED' ? 'danger' : 'warning'" :label="checkoutStatusLabel(row.status)" /></template>
          <template #cell-actions="{ row }"><AppPermissionButton :allowed="canBtn('studentAffairs.dorm.allocation.manage')" code="studentAffairs.dorm.allocation.manage" size="sm" :loading="actioning" :disabled="!row.allowedActions?.includes('CONFIRM')" @click="confirmCheckout(row)">核对并确认</AppPermissionButton></template>
        </DataTable>
        <p v-else class="sa-empty">当前范围暂无待确认退宿单。</p>
      </section>

      <section v-if="activeTab === 'history'" class="dr-workspace">
        <DataTable v-if="stayItems.length" :columns="stayColumns" :rows="stayItems" row-key="stayId" :pagination="stayPagination" @page-change="onStayPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.studentName || ('学生#' + row.studentId) }}</span><div class="mp-cell-sub">{{ row.studentNo }}</div></template>
          <template #cell-bed="{ row }">{{ row.bedLabel || ('床位#' + row.bedId) }}</template>
          <template #cell-period="{ row }">{{ row.checkinAt || '未记录' }} → {{ row.checkoutAt || '当前' }}</template>
          <template #cell-source="{ row }">{{ staySourceLabel(row) }}</template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ACTIVE' ? 'success' : 'info'" :label="stayStatusLabel(row.status)" /></template>
        </DataTable>
        <p v-else class="sa-empty">当前范围暂无住宿历史。</p>
      </section>
    </AppGlobalState>

    <AppDrawer :visible="dlg.visible" title="发起调宿" mode="modal" size="large" @close="closeTransfer">
      <div class="dr-form">
        <p class="dr-workspace-intro">按“学生 → 楼栋 → 房间 → 空床”顺序选择，提交后进入辅导员和宿管两级审批。</p>
        <AppInlineAlert v-if="prefilledStudentHint" type="info" :description="prefilledStudentHint" />
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
      v-model:visible="transferSubmitDlg.visible"
      title="确认发起调宿"
      :message="transferSubmitDlg.message"
      confirm-text="确认提交审批"
      :submitting="actioning"
      @confirm="submitTransfer"
    />
    <AppConfirmDialog
      v-model:visible="checkoutConfirmDlg.visible"
      title="确认办理退宿"
      type="warning"
      :message="checkoutConfirmDlg.message"
      confirm-text="确认退宿并释放床位"
      :submitting="actioning"
      @confirm="submitConfirmCheckout"
    />
    <AppConfirmDialog
      v-model:visible="rejDlg.visible"
      title="驳回调宿申请"
      type="danger"
      confirm-text="确认驳回"
      require-reason
      :reason-min-length="5"
      reason-label="驳回原因（5-300字）"
      reason-placeholder="请说明本次调宿未通过的具体原因，原床位保持不变"
      :submitting="actioning"
      @confirm="submitReject"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert,
  AppPageShell, AppPermissionButton, AppStatusTag, AppStudentPicker,
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
const CHECKOUT_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'bed', title: '当前床位' },
  { key: 'type', title: '退宿类型' }, { key: 'blockers', title: '阻断事项' },
  { key: 'status', title: '状态' }, { key: 'actions', title: '操作', align: 'right', width: '130px' }
]
const STAY_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'bed', title: '楼 / 房 / 床' },
  { key: 'period', title: '入住 → 退宿' }, { key: 'source', title: '历史来源' },
  { key: 'status', title: '状态' }
]

export default {
  name: 'DormTransferView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert,
    AppPageShell, AppPermissionButton, AppStatusTag, AppStudentPicker,
    AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker, AppTextarea, DataTable
  },
  data() {
    return {
      transferColumns: TRANSFER_COLUMNS, checkoutColumns: CHECKOUT_COLUMNS, stayColumns: STAY_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [], statusCounts: null,
      checkoutItems: [], stayItems: [], stayTotal: 0, loadSerial: 0, activeTab: 'transfer',
      workspaceTabs: [{ key: 'transfer', label: '调宿申请' }, { key: 'checkout', label: '退宿待确认' }, { key: 'history', label: '住宿历史' }],
      checkoutPagination: { page: 1, pageSize: 20, total: 0 },
      stayPagination: { page: 1, pageSize: 20, total: 0 },
      pagination: { page: 1, pageSize: 20, total: 0 },
      buildings: [], rooms: [], beds: [],
      studentFilter: { studentId: '', studentNo: '', studentName: '' }, statusMatch: null,
      routeIntentConsumed: false,
      dlg: { visible: false, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' },
      approveDlg: { visible: false, transferId: '', version: null, message: '' },
      transferSubmitDlg: { visible: false, message: '' },
      checkoutConfirmDlg: { visible: false, requestId: '', version: null, message: '' },
      rejDlg: { visible: false, transferId: '', version: null }
    }
  },
  computed: {
    recordId() { return String(this.$route?.query?.recordId || '') },
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      const hit = this.items.find((x) => String(x.studentId) === String(f.studentId)) || {}
      const name = f.studentName || hit.realName || '学生'
      const no = f.studentNo || hit.studentNo || ''
      return `当前学生筛选：${name}${no ? ` / ${no}` : ''}`
    },
    /** 表单里的学生确实来自上一页带入时才提示，老师改过人就不再显示。 */
    prefilledStudentHint() {
      const f = this.studentFilter || {}
      if (!f.studentId || String(this.dlg.studentId) !== String(f.studentId)) return ''
      const hit = this.items.find((x) => String(x.studentId) === String(f.studentId)) || {}
      const name = f.studentName || hit.realName || '学生'
      const no = f.studentNo || hit.studentNo || ''
      return `已带入学生画像中的当前学生：${name}${no ? ` / ${no}` : ''}；如需换人可直接在下方重新选择。`
    },
    metricCards() {
      const s = this.statusCounts
      const pending = s === null ? '—' : PENDING_STATUSES.reduce((n, key) => n + Number(s[key] || 0), 0)
      return [
        { key: 'p', label: '待审批', value: pending, accent: 'warning' },
        { key: 'e', label: '已执行', value: s === null ? '—' : Number(s.EXECUTED || 0), accent: 'primary' },
        { key: 'r', label: '已驳回', value: s === null ? '—' : Number(s.REJECTED || 0), accent: 'risk' },
        { key: 't', label: '合计', value: s === null ? '—' : Number(s.ALL || Object.values(s).reduce((a, b) => a + Number(b || 0), 0)), accent: 'primary' }
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
  mounted() { this.applyRouteFilters(); this.load(); this.loadBuildings(); this.consumeRouteIntent() },
  watch: { '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.checkoutPagination.page = 1; this.stayPagination.page = 1; this.load() } },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    consumeRouteIntent() {
      if (this.routeIntentConsumed || this.$route.query?.intent !== 'create') return
      if (!this.studentFilter?.studentId || !this.canBtn('studentAffairs.dorm.transfer.create')) return
      this.routeIntentConsumed = true
      this.openTransfer()
    },
    hasVersion(row) { return row && row.version !== undefined && row.version !== null && row.version !== '' },
    canAction(row, action) { return Array.isArray(row.allowedActions) && row.allowedActions.includes(action) },
    fallbackBed(row, side) {
      const prefix = side === 'from' ? 'from' : 'to'
      return [row[`${prefix}BuildingName`], row[`${prefix}RoomNo`] && `${row[`${prefix}RoomNo`]}室`, row[`${prefix}BedNo`] && `${row[`${prefix}BedNo`]}床`].filter(Boolean).join(' / ') || (row[`${prefix}BedId`] ? `床位 #${row[`${prefix}BedId`]}` : '未记录')
    },
    applyRouteFilters() {
      const q = this.$route.query || {}; this.activeTab = ['checkout', 'history'].includes(q.tab) ? q.tab : 'transfer'; this.studentFilter = readStudentFilter(q)
      if (this.recordId) { this.activeTab = q.tab === 'checkout' ? 'checkout' : 'transfer'; this.statusMatch = null; return }
      if (!q.status) { this.statusMatch = null; return }
      this.statusMatch = resolveTodoStatus('dormTransfer', q.status).matchStatuses
    },
    clearRecordFocus() { const query = { ...this.$route.query }; delete query.recordId; this.$router.replace({ query }).catch(() => {}) },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      const q = { ...this.$route.query }; delete q.studentId; delete q.studentNo; delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
    },
    switchTab(tab) { this.$router.replace({ query: { ...this.$route.query, tab } }).catch(() => {}) },
    async load() {
      const serial = ++this.loadSerial
      this.loading = true; this.errorMessage = ''
      try {
        if (this.recordId && !/^[1-9]\d*$/.test(this.recordId)) throw new Error('调宿申请编号无效，请从待办重新进入')
        const sid = this.studentFilter?.studentId || undefined
        if (this.activeTab === 'checkout') {
          const query = { page: this.recordId ? 1 : this.checkoutPagination.page, pageSize: this.checkoutPagination.pageSize,
            ...(this.recordId ? { recordId: this.recordId } : { studentId: sid, status: 'PENDING' }) }
          const res = await studentAffairsApi.listDormCheckouts(query)
          if (serial !== this.loadSerial) return
          this.checkoutItems = res.data.items || []; this.checkoutPagination.total = Number(res.data.total || 0)
          if (this.recordId && !this.checkoutItems.length) throw new Error('该退宿单不存在或不在当前权限范围内')
        } else if (this.activeTab === 'history') {
          const res = await studentAffairsApi.listDormStays({ page: this.stayPagination.page, pageSize: this.stayPagination.pageSize, studentId: sid })
          if (serial !== this.loadSerial) return
          this.stayItems = res.data.items || []; this.stayTotal = Number(res.data.total || 0); this.stayPagination.total = this.stayTotal
        } else {
          const query = { page: this.recordId ? 1 : this.pagination.page, pageSize: this.pagination.pageSize,
            ...(this.recordId ? { recordId: this.recordId } : { studentId: sid, status: this.serverStatus }) }
          const res = await studentAffairsApi.listDormTransfers(query)
          if (serial !== this.loadSerial) return
          let rows = res.data.items || []
          if (!this.recordId && this.statusMatch?.length && !this.serverStatus) rows = rows.filter(x => this.statusMatch.includes(x.status) || (this.statusMatch.includes('PENDING') && this.isPending(x.status)))
          if (this.recordId && !rows.length) throw new Error('该调宿申请不存在或不在当前权限范围内')
          this.items = rows; this.pagination.total = res.data.total ?? rows.length; this.statusCounts = res.data.statusCounts || null
        }
      } catch (e) { if (serial === this.loadSerial) this.errorMessage = e.message || '住宿记录加载失败' } finally { if (serial === this.loadSerial) this.loading = false }
    },
    onCheckoutPageChange(page) { this.checkoutPagination.page = page; this.load() },
    onStayPageChange(page) { this.stayPagination.page = page; this.load() },
    onPageChange(page) { this.pagination.page = page; this.load() },
    stayStatusLabel(value) { return ({ RESERVED: '已预留', ACTIVE: '当前在住', ENDED: '已结束', CANCELLED: '已取消' })[value] || '待核查' },
    staySourceLabel(row) { return ({ TRANSFER: '调宿入住', ALLOCATION: '分配入住', MANUAL: '人工办理', ORIENTATION: '迎新分配', CHECKIN: '入住办理', MIGRATION: '历史迁入' })[row.sourceType] || ({ TRANSFER: '调宿入住', CURRENT_OCCUPANCY: '入住办理', RESERVED: '床位预留' })[row.stayType] || '住宿办理' },
    checkoutTypeLabel(value) { return ({ GRADUATION: '毕业', LEAVE_OF_ABSENCE: '休学', WITHDRAWAL: '退学', DAY_STUDENT: '转走读', SPECIAL: '特殊退宿' }[value] || (value ? '待确认' : '—')) },
    checkoutStatusLabel(value) { return ({ PENDING_CONFIRMATION: '待宿管确认', BLOCKED: '存在阻断', CONFIRMED: '已退宿', CANCELLED: '已取消' }[value] || (value ? '待确认' : '—')) },
    confirmCheckout(row) {
      if (!row.allowedActions?.includes('CONFIRM')) return
      this.checkoutConfirmDlg = {
        visible: true, requestId: row.requestId, version: row.version,
        message: `${row.studentName || '该学生'}\n${row.bedLabel}\n\n确认后将关闭当前住宿历史并立即释放床位。`
      }
    },
    async submitConfirmCheckout() {
      const d = this.checkoutConfirmDlg
      const ok = await this.runAction(() => studentAffairsApi.confirmDormCheckout(d.requestId, d.version))
      if (ok) d.visible = false
    },
    async loadBuildings() { try { this.buildings = (await studentAffairsApi.listAllDormBuildings()).data.items || [] } catch { this.buildings = [] } },
    /**
     * 从学生画像跳进来时 URL 已带 studentId，列表也按它筛过；
     * 但此前打开"发起调宿"会把 studentId 清空，老师得把同一个学生再搜一遍——
     * 上下文断在动作层。这里沿用当前学生，仍可在选择器里主动改人，
     * 提交时后端 submit_transfer 照常重新校验学生与目标床位。
     */
    openTransfer() {
      const sid = (this.studentFilter && this.studentFilter.studentId) || ''
      this.dlg = { visible: true, studentId: sid ? String(sid) : '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' }
      this.rooms = []; this.beds = []
    },
    closeTransfer() { if (!this.actioning) this.dlg.visible = false },
    async onBuildingChange() {
      this.dlg.roomId = ''; this.dlg.toBedId = ''; this.dlg.error = ''; this.beds = []
      if (!this.dlg.buildingId) { this.rooms = []; return }
      try { this.rooms = (await studentAffairsApi.listAllDormRooms(this.dlg.buildingId)).data.items || [] }
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
      d.error = ''
      this.transferSubmitDlg = {
        visible: true,
        message: `目标：${this.selectedTargetLabel}\n事由：${reason}\n\n提交后进入辅导员、宿管两级审批。`
      }
    },
    async submitTransfer() {
      const d = this.dlg; const reason = (d.reason || '').trim()
      const ok = await this.runAction(() => studentAffairsApi.submitDormTransfer({ studentId: d.studentId, toBedId: d.toBedId, reason }))
      if (ok) { d.visible = false; this.transferSubmitDlg.visible = false } else d.error = this.errorMessage
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
    nodeLabel(n) { return this.statusLabel(n) },
    statusLabel(s) { return ({ SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', DORM_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回', CANCELLED: '已取消' })[s] || (s ? '状态待确认' : '—') },
    statusKind(s) { if (s === 'EXECUTED') return 'success'; if (s === 'REJECTED') return 'danger'; if (this.isPending(s)) return 'warning'; return 'info' }
  }
}
</script>

<style scoped>
.dr-tabs{display:flex;gap:24px;border-bottom:1px solid var(--color-border,#dbe4f2);margin-bottom:16px}.dr-tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:inherit;padding:12px 2px;cursor:pointer;font:inherit}.dr-tabs button.active{color:var(--color-primary,#295bbb);border-bottom-color:currentColor;font-weight:600}.dr-tabs button:focus-visible{outline:2px solid var(--color-primary,#295bbb);outline-offset:2px}.dr-workspace{min-width:0}

.dr-section-hint,
.dr-workspace-intro { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.sa-student-filter { display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);margin-bottom:var(--space-3);padding:var(--space-2) var(--space-3);border-radius:var(--radius-md);background:var(--warning-50,#fffbeb);border:1px solid var(--warning-200,#fde68a);font-size:var(--font-size-sm);color:var(--text-primary) }
.route-cell { display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:12px;line-height:1.5 }
.route-from { color:var(--text-secondary) }
.route-arrow { color:var(--text-tertiary);font-weight:700 }
.route-to { color:var(--success-700,#15803d) }
.reason-cell { display:block;max-width:240px;white-space:normal;line-height:1.55;overflow-wrap:anywhere }
.dr-form { display:flex;flex-direction:column;gap:var(--space-4) }
.dr-hint,.char-count { margin:0;color:var(--text-tertiary);font-size:var(--font-size-sm) }
.char-count { text-align:right;margin-top:-12px }
.dr-blocked { color:var(--danger-600,#dc2626) }
.target-preview { padding:10px 12px;border-radius:var(--radius-md);background:var(--primary-50,#eff6ff);border:1px solid var(--primary-100,#dbeafe) }
.target-preview span,.target-preview strong { display:block }
.target-preview span { color:var(--text-tertiary);font-size:12px }
.target-preview strong { margin-top:3px;color:var(--primary-700,#1d4ed8) }
@media (max-width:960px){.route-cell{align-items:flex-start;flex-direction:column}.route-arrow{transform:rotate(90deg)}}
@import '@/styles/module-page.css';
</style>
