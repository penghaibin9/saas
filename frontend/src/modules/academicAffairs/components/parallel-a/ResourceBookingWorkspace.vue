<template>
  <ModulePageShell :title="`${label}预约`" subtitle="核对日期、资源与占用来源后申请，办理后查询正式预约记录。">
    <template #actions><AppButton v-if="$route.query.returnToken" :disabled="saving" @click="goBack">返回原位置</AppButton><AppButton variant="primary" :disabled="saving || Boolean(pending)" @click="openBook()">申请预约</AppButton></template>
    <AaOperationReceipt :receipt="receipt" />
    <AppButton v-if="pending" :disabled="saving" @click="queryPending">查询办理结果</AppButton>
    <div class="booking-toolbar"><label>预约日期<AppDatePicker v-model="date" @change="changeDate" /></label><span>单节预约按正式节次保存；未发现占用不代表已取得使用资格。</span></div>
    <AppInlineAlert v-if="canReview && kind === 'LAB'" type="warning" title="审核通过待核验" description="未关联正式排课场地的实训室不能通过预约；请先到实训室资源核对关联，再返回原队列。" />
    <AppInlineAlert v-else-if="canReview" type="info" title="以服务端最终判定为准" description="审核通过时，服务端将在同一事务内重新核对教室状态、开放借用规则、维修、已批准预约和正式课表。" />
    <ErrorState v-if="error" :description="error" @retry="load" /><LoadingState v-else-if="loading" />
    <div v-else class="booking-stack">
      <section class="booking-card">
        <header><h2>{{ label }} · 日期与节次占用</h2><span>{{ date }} · 共 {{ resourceTotal }} 项资源</span></header>
        <p class="booking-note">{{ occupancyNote }}</p>
        <div v-if="resources.length" class="booking-matrix"><table><thead><tr><th>资源 / 容量</th><th v-for="slot in 12" :key="slot">第{{ slot }}节</th></tr></thead><tbody><tr v-for="resource in resources" :key="resource[idKey]"><th>{{ resource.roomName || resource.labName || resource.roomCode }}<small>{{ resource.capacity ?? '未提供' }} 座 · #{{ resource[idKey] }}</small></th><td v-for="slot in 12" :key="slot"><button :class="{ occupied: cell(resource, slot).occupied }" @click="selectSlot(resource, slot)">{{ cell(resource, slot).label }}</button></td></tr></tbody></table></div>
        <EmptyState v-else :title="`当前没有可读取的${label}资源`" />
        <div class="booking-pager"><AppButton :disabled="resourcePage <= 1" @click="turnPage('resourcePage', -1)">上一页资源</AppButton><span>第 {{ resourcePage }} 页 · 每页5项</span><AppButton :disabled="resourcePage * 5 >= resourceTotal" @click="turnPage('resourcePage', 1)">下一页资源</AppButton></div>
      </section>
      <section class="booking-card">
        <header><h2>当日预约记录</h2><AppSelect v-model="filterStatus" :options="statusOptions" @change="changeStatus" /></header>
        <DataTable v-if="rows.length" :columns="columns" :rows="rows" row-key="bookingId">
          <template #cell-resource="{ row }">{{ row[textKey] }}<small>#{{ row.bookingId }}</small></template>
          <template #cell-slot="{ row }">{{ row.bookingDate }} 第{{ row.slotNo }}节</template>
          <template #cell-status="{ row }"><StatusTag :label="statusLabel(row.status)" :type="row.status === 'APPROVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'warning'" /></template>
          <template #cell-actions="{ row }"><template v-if="canReview && row.status === 'PENDING'"><AppButton :disabled="saving || Boolean(pending) || Boolean(approvalBlockReason(row))" :title="approvalBlockReason(row)" @click="openReview(row, 'APPROVE')">审核通过</AppButton><AppButton :disabled="saving || Boolean(pending)" @click="openReview(row, 'REJECT')">驳回</AppButton></template><span v-else-if="!canReview">由资源管理员审核</span></template>
        </DataTable>
        <EmptyState v-else title="所选日期与状态下暂无预约" description="已成功读取所选日期的预约记录。" />
        <div class="booking-pager"><AppButton :disabled="page <= 1" @click="turnPage('page', -1)">上一页</AppButton><span>第 {{ page }} 页 · 共 {{ total }} 条</span><AppButton :disabled="page * 20 >= total" @click="turnPage('page', 1)">下一页</AppButton></div>
      </section>
    </div>
    <AppDrawer :visible="bookVisible" :title="`申请${label}预约`" mode="modal" size="medium" @close="!saving && (bookVisible = false)">
      <div class="booking-form"><AppFormItem :label="label" required><AppClassroomPicker v-if="kind === 'CLASSROOM'" v-model="form.resourceId" :query="{ purpose: 'BORROW' }" :disabled="saving || Boolean(pending)" /><AppLabPicker v-else v-model="form.resourceId" :disabled="saving || Boolean(pending)" /></AppFormItem><AppFormItem label="日期" required><AppDatePicker v-model="form.bookingDate" :disabled="saving || Boolean(pending)" /></AppFormItem><AppFormItem label="节次" required><AppNumberInput v-model="form.slotNo" :min="1" :max="12" :disabled="saving || Boolean(pending)" /></AppFormItem><AppFormItem label="用途" required><AppTextInput v-model="form.purpose" :disabled="saving || Boolean(pending)" /></AppFormItem><AppInlineAlert type="info" description="提交后进入待审；请由资源管理员核对课表、维修情况并审核。" /><AppInlineAlert v-if="formError" type="danger" :description="formError" /></div>
      <template #footer><AppButton :disabled="saving" @click="bookVisible = false">关闭</AppButton><AppButton variant="primary" :disabled="saving || Boolean(pending)" @click="submitBook">提交预约</AppButton></template>
    </AppDrawer>
    <AppDrawer :visible="review.visible" title="核对预约并审核" mode="modal" size="medium" @close="!saving && (review.visible = false)">
      <div class="booking-form"><strong>{{ review.row?.resourceText }} · 预约 #{{ review.row?.bookingId }}</strong><p>{{ review.row?.bookingDate }} 第{{ review.row?.slotNo }}节 · {{ review.row?.applicantName }}</p><p>{{ review.row?.purpose || '未提供用途' }}</p><AppFormItem v-if="review.action === 'REJECT'" label="驳回原因（不少于5字）" required><AppTextarea v-model="review.reason" :disabled="saving" /></AppFormItem><AppInlineAlert v-if="review.error" type="danger" :description="review.error" /><p>将重新读取该预约状态，办理后查询正式结果。</p></div>
      <template #footer><AppButton :disabled="saving" @click="review.visible = false">取消</AppButton><AppButton variant="primary" :disabled="saving || Boolean(pending) || review.row?.status !== 'PENDING' || (review.action === 'APPROVE' && Boolean(approvalBlockReason(review.row)))" @click="submitReview">{{ review.action === 'REJECT' ? '确认驳回' : '确认通过' }}</AppButton></template>
    </AppDrawer>
    <AppDrawer :visible="evidence.visible" title="占用来源" mode="modal" size="medium" @close="evidence.visible = false"><p v-for="(item, index) in evidence.items" :key="index">{{ item.source === 'SCHEDULE' ? '教学占用' : '已批准预约' }} · {{ item.resourceLabel }} · 第{{ item.slotNo }}节 · {{ item.occupant }} · {{ item.purpose }}</p><p>{{ evidence.note }}</p></AppDrawer>
  </ModulePageShell>
</template>
<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppDatePicker, AppSelect, AppClassroomPicker, AppLabPicker, AppFormItem, AppNumberInput, AppTextInput, AppTextarea, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsLabApi, academicAffairsClassroomBookingApi, academicAffairsLabBookingApi, academicAffairsResourceApi } from '../../api/academic-affairs.api'
import { academicIdentity, academicRouteState, createAcademicRequestGate, routeScalar } from '../../academicFlowContext'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from './AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult } from './resultState'
const labels = { PENDING: '待审核', APPROVED: '已通过', REJECTED: '已驳回', CANCELLED: '已取消' }
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
const PENDING_STORAGE_KEY = 'aa-resource-booking-pending-v1'
const pageValue = value => { const number = Number(value); return Number.isInteger(number) && number > 0 && number <= 1000000 ? number : 1 }
export default {
  name: 'ResourceBookingWorkspace',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppDatePicker, AppSelect, AppClassroomPicker, AppLabPicker, AppFormItem, AppNumberInput, AppTextInput, AppTextarea, AppInlineAlert, AaOperationReceipt },
  props: { kind: { type: String, required: true }, ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() { return { date: today(), loading: true, error: '', rows: [], resources: [], occupancy: [], occupancyNote: '', page: 1, total: 0, resourcePage: 1, resourceTotal: 0, filterStatus: '', disposed: false, saving: false, bookVisible: false, form: {}, formError: '', review: { visible: false, row: null, action: '', reason: '', error: '', token: 0 }, evidence: { visible: false, items: [], note: '' }, receipt: null, pending: null, loadGate: null, activeIdentity: '', operationSerial: 0, routeWriting: false, routeWriteSeq: 0, recoveryError: '',
    statusOptions: [{ label: '全部状态', value: '' }, ...Object.entries(labels).map(([value, label]) => ({ value, label }))], columns: [{ key: 'resource', title: '资源 / 预约编号' }, { key: 'slot', title: '时段' }, { key: 'purpose', title: '用途' }, { key: 'applicantName', title: '申请人' }, { key: 'status', title: '状态' }, { key: 'actions', title: '办理' }] } },
  computed: {
    label() { return this.kind === 'CLASSROOM' ? '教室' : '实训室' }, idKey() { return this.kind === 'CLASSROOM' ? 'classroomId' : 'labId' }, textKey() { return this.kind === 'CLASSROOM' ? 'classroomText' : 'labText' },
    api() { return this.kind === 'CLASSROOM' ? academicAffairsClassroomBookingApi : academicAffairsLabBookingApi },
    canReview() { return matchPermission(this.ctx.permissionPatterns || [], `academicAffairs.${this.kind === 'CLASSROOM' ? 'classroom' : 'lab'}.update`) },
    canReadOccupancy() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.resourceOccupancy.view') }
  },
  created() { this.applyRouteState(); this.activeIdentity = this.identityKey(); this.loadGate = createAcademicRequestGate(() => this.viewKey()); this.restorePending(); this.load() },
  watch: {
    ctx: { deep: true, handler() { this.handleContextChange() } },
    kind() { this.handleContextChange() },
    '$route.fullPath'() { if (this.routeWriting) return; if (this.applyRouteState()) { this.loadGate?.invalidate(); this.load() } }
  },
  beforeUnmount() { this.disposed = true; this.loadGate?.invalidate(); this.persistPending() },
  methods: {
    statusLabel(status) { return labels[status] || '状态待确认' },
    identityKey() {
      const identity = this.academicFlow?.identity?.() || academicIdentity(currentUserFromToken(), this.ctx)
      return identity ? JSON.stringify([identity, this.kind]) : ''
    },
    recoveryKey() {
      const user = currentUserFromToken() || {}
      if (!user.tenantId || !user.userId || !user.currentRoleCode) return ''
      return JSON.stringify([String(user.tenantId), String(user.userId), user.currentRoleCode, user.activeContextId || '', this.kind])
    },
    viewKey() {
      return JSON.stringify([this.identityKey(), this.date, this.page, this.resourcePage, this.filterStatus])
    },
    applyRouteState() {
      const state = academicRouteState(this.$route)
      const rawDate = routeScalar(this.$route.query?.date)
      const nextDate = /^\d{4}-\d{2}-\d{2}$/.test(rawDate) ? rawDate : today()
      const rawStatus = routeScalar(this.$route.query?.status).toUpperCase()
      const nextStatus = Object.prototype.hasOwnProperty.call(labels, rawStatus) ? rawStatus : ''
      const nextResourcePage = pageValue(routeScalar(this.$route.query?.resourcePage))
      const changed = this.date !== nextDate || this.page !== state.page ||
        this.resourcePage !== nextResourcePage || this.filterStatus !== nextStatus
      this.date = nextDate
      this.page = state.page
      this.resourcePage = nextResourcePage
      this.filterStatus = nextStatus
      return changed
    },
    syncRoute() {
      const query = { ...this.$route.query, date: this.date }
      if (this.page > 1) query.page = String(this.page); else delete query.page
      if (this.resourcePage > 1) query.resourcePage = String(this.resourcePage); else delete query.resourcePage
      if (this.filterStatus) query.status = this.filterStatus; else delete query.status
      const sequence = ++this.routeWriteSeq
      this.routeWriting = true
      this.$router.replace({ query }).catch(() => {}).finally(() => {
        if (sequence !== this.routeWriteSeq || this.disposed) return
        this.routeWriting = false
        if (this.applyRouteState()) { this.loadGate?.invalidate(); this.load() }
      })
    },
    changeDate() { this.page = 1; this.syncRoute(); this.load() },
    changeStatus() { this.page = 1; this.syncRoute(); this.load() },
    turnPage(field, delta) {
      const next = Math.max(1, Number(this[field] || 1) + delta)
      if (next === this[field]) return
      this[field] = next
      this.syncRoute()
      this.load()
    },
    goBack() {
      if (this.$route.query.returnToken && this.academicFlow) {
        return this.academicFlow.back(this.$route.query.returnToken,
          this.kind === 'CLASSROOM' ? '/admin/academic-affairs/classrooms' : '/admin/academic-affairs/resources/labs')
      }
      return this.$router.push(this.kind === 'CLASSROOM'
        ? '/admin/academic-affairs/classrooms' : '/admin/academic-affairs/resources/labs')
    },
    handleContextChange() {
      const next = this.identityKey()
      if (next !== this.activeIdentity) {
        this.clearPrivate()
        this.activeIdentity = next
        this.restorePending()
      } else {
        this.loadGate?.invalidate()
      }
      this.load()
    },
    pendingStore() {
      const value = JSON.parse(globalThis.sessionStorage.getItem(PENDING_STORAGE_KEY) || '{}')
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('预约恢复引用格式无效')
      return value
    },
    writePendingStore(value) {
      globalThis.sessionStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify(value))
    },
    persistPending() {
      const operation = this.pending
      if (!operation || operation.referenceUnavailable) return true
      try {
        const store = this.pendingStore(), key = operation.recoveryIdentity
        if (!key) throw new Error('当前身份不足以保存预约恢复引用')
        store[key] = {
          recoveryIdentity: key, kind: operation.kind, action: operation.action, id: operation.id,
          expected: operation.expected, commandKey: operation.commandKey,
          row: { kind: operation.kind, resourceId: operation.row.resourceId,
            bookingDate: operation.row.bookingDate, slotNo: operation.row.slotNo,
            mappedClassroomId: operation.row.mappedClassroomId, labVersion: operation.row.labVersion }
        }
        this.writePendingStore(store)
        this.recoveryError = ''
        return true
      } catch (error) {
        this.recoveryError = error?.message || '预约恢复引用无法保存'
        return false
      }
    },
    forgetPending(identity) {
      try {
        const store = this.pendingStore()
        delete store[identity]
        this.writePendingStore(store)
        this.recoveryError = ''
        return true
      } catch (error) {
        this.recoveryError = error?.message || '预约恢复引用无法清除'
        this.error = this.recoveryError
        return false
      }
    },
    restorePending() {
      let saved
      const key = this.recoveryKey()
      try {
        if (!key) throw new Error('当前身份尚未就绪，暂不能恢复或发送预约')
        saved = this.pendingStore()[key]
        if (saved && (saved.recoveryIdentity !== key || saved.kind !== this.kind ||
            (saved.commandKey != null && !/^[A-Za-z0-9_-]{8,128}$/.test(saved.commandKey)) ||
            !/^[1-9]\d*$/.test(saved.row?.resourceId || '') || !/^\d{4}-\d{2}-\d{2}$/.test(saved.row?.bookingDate || '') ||
            !Number.isInteger(saved.row?.slotNo) || saved.row.slotNo < 1 || saved.row.slotNo > 12 ||
            !['BOOK', 'APPROVE', 'REJECT'].includes(saved.action) ||
            saved.expected !== ({ BOOK: 'PENDING', APPROVE: 'APPROVED', REJECT: 'REJECTED' })[saved.action] ||
            (saved.id && !/^[1-9]\d*$/.test(saved.id)) || (saved.action !== 'BOOK' && !saved.id))) throw new Error('预约恢复引用不完整，不能忽略原命令继续发送')
        this.recoveryError = ''
        if (!saved) return
      } catch (error) {
        this.recoveryError = error?.message || '预约恢复引用暂不可读'
        this.error = this.recoveryError
        this.pending = { identity: this.identityKey(), kind: this.kind, referenceUnavailable: true }
        return
      }
      this.pending = {
        ...saved,
        identity: this.identityKey(), recovered: true, reason: '',
        postState: 'UNKNOWN', postMatches: false,
        serial: ++this.operationSerial
      }
      this.receipt = {
        title: '预约办理回执',
        object: saved.id ? '预约 #' + saved.id : this.label + '预约',
        status: '存在未完成的结果确认',
        pending: true,
        next: saved.id
          ? '可继续精确查询正式预约记录；本页不会再次发送原命令。'
          : '可读取原命令回执恢复正式预约编号；本页不会再次发送原命令。'
      }
    },
    clearPrivate() {
      this.loadGate?.invalidate()
      this.persistPending()
      this.rows = []
      this.resources = []
      this.occupancy = []
      this.form = {}
      this.bookVisible = false
      this.review = { visible: false, row: null, action: '', reason: '', error: '', token: 0 }
      this.evidence = { visible: false, items: [], note: '' }
      this.pending = null
      this.receipt = null
      this.total = 0
      this.resourceTotal = 0
      this.saving = false
    },
    failure(e, field = 'error') {
      if (isDeniedResult(e)) {
        this.clearPrivate()
        this.loading = false
        this.error = (e.message || '无权读取') + '；已清除先前页面数据，原命令引用保留供原身份核对。'
        return
      }
      const message = (isConflictResult(e) ? '事实已变化，保留输入，请重新核对。' : '') +
        (e?.message || '连接失败，请重试。')
      if (field === 'review') this.review.error = message
      else this[field] = message
      if (isConflictResult(e) && this.receipt) {
        this.receipt = { ...this.receipt, status: '事实已变化，需重新核对', pending: true, next: message }
      }
    },
    async load() {
      const current = this.loadGate.begin()
      const date = this.date
      const kind = this.kind
      const api = this.api
      const page = this.page
      const resourcePage = this.resourcePage
      const status = this.filterStatus
      this.loading = true
      this.error = this.recoveryError
      this.rows = []
      this.resources = []
      this.occupancy = []
      this.total = 0
      this.resourceTotal = 0
      if (!date) { this.error = '请选择预约日期。'; this.loading = false; return }
      try {
        const [records, resources, occupancy] = await Promise.all([
          api.list({ date, status: status || undefined, page, pageSize: 20 }),
          kind === 'CLASSROOM'
            ? academicAffairsApi.listClassrooms({ page: resourcePage, pageSize: 5 })
            : academicAffairsLabApi.list({ page: resourcePage, pageSize: 5 }),
          this.canReadOccupancy ? academicAffairsResourceApi.occupancy(date, kind) : Promise.resolve(null)
        ])
        if (!current()) return
        for (const response of [records, resources, occupancy]) {
          if (response && response.code !== 0) throw response
        }
        if (!Array.isArray(records.data?.list) || !Array.isArray(resources.data?.items) ||
          !Number.isInteger(records.data?.total) || records.data.total < 0 || records.data.list.length > 20 ||
          !Number.isInteger(resources.data?.total) || resources.data.total < 0 || resources.data.items.length > 5) {
          throw new Error('资源或预约列表未完整返回，请重新读取。')
        }
        if (occupancy && (occupancy.data?.date !== date || !Array.isArray(occupancy.data?.items) ||
          !Number.isInteger(occupancy.data?.total) || occupancy.data.total !== occupancy.data.items.length)) {
          throw new Error('占用信息的日期或完整性未确认，请重新读取。')
        }
        this.rows = records.data.list
        this.total = records.data.total
        this.resources = resources.data.items
        this.resourceTotal = resources.data.total
        this.occupancy = occupancy?.data?.items || []
        this.occupancyNote = occupancy
          ? '仅按稳定资源编号匹配占用。课表缺资源编号的记录须另行核对，未匹配时显示待核对。'
          : '当前账号没有跨源占用读取权限，请由资源管理员核对课表及维修情况。'
      } catch (e) {
        if (current()) this.failure(e)
      } finally {
        if (current()) {
          this.loading = false
          this.academicFlow?.restorePosition?.()
        }
      }
    },
    cell(resource, slot) {
      const items = this.occupancy.filter(x => x.resourceKind === this.kind && x.resourceId &&
        String(x.resourceId) === String(resource[this.idKey]) && Number(x.slotNo) === slot)
      if (resource.status !== 'AVAILABLE') {
        return { occupied: true, label: resource.status === 'MAINTENANCE' ? '维修停用' : '不可用',
          items, note: '资源当前不可用，不能申请。' }
      }
      if (this.kind === 'CLASSROOM' && resource.allowBorrow !== true) {
        return { occupied: true, label: '未开放借用', items, note: '该教室未开放借用，不能申请。' }
      }
      if (items.length) {
        return { occupied: true,
          label: items.some(x => x.source === 'SCHEDULE') ? '教学占用' : '预约占用', items }
      }
      return { occupied: false, label: '待核对·申请', items }
    },
    selectSlot(resource, slot) {
      const fact = this.cell(resource, slot)
      if (fact.occupied) this.evidence = { visible: true, items: fact.items, note: fact.note || '' }
      else this.openBook(resource, slot)
    },
    openBook(resource, slot = 1) {
      if (this.saving || this.pending) return
      this.form = { resourceId: resource?.[this.idKey] || '', bookingDate: this.date, slotNo: slot, purpose: '' }
      this.formError = ''
      this.bookVisible = true
    },
    freezeRow(row) {
      return {
        kind: this.kind,
        bookingId: String(row?.bookingId || ''),
        resourceId: String(row?.resourceId || row?.[this.idKey] || ''),
        mappedClassroomId: row?.mappedClassroomId ? String(row.mappedClassroomId) : null,
        labVersion: row?.labVersion ?? null,
        classroomId: row?.classroomId ? String(row.classroomId) : null,
        resourceText: row?.resourceText || row?.[this.textKey] || '',
        bookingDate: String(row?.bookingDate || ''),
        slotNo: Number(row?.slotNo),
        purpose: String(row?.purpose || ''),
        applicantName: String(row?.applicantName || ''),
        status: String(row?.status || ''),
        reviewReason: String(row?.reviewReason || '')
      }
    },
    recordMatches(row, frozen, bookingId) {
      const idKey = frozen.kind === 'CLASSROOM' ? 'classroomId' : 'labId'
      return String(row?.bookingId || '') === String(bookingId || '') &&
        String(row?.[idKey] || '') === String(frozen.resourceId || '') &&
        String(row?.bookingDate || '') === String(frozen.bookingDate || '') &&
        Number(row?.slotNo) === Number(frozen.slotNo)
    },
    async readRecord(bookingId, frozen, current = () => true) {
      const idKey = frozen.kind === 'CLASSROOM' ? 'classroomId' : 'labId'
      const api = frozen.kind === 'CLASSROOM'
        ? academicAffairsClassroomBookingApi : academicAffairsLabBookingApi
      const response = await api.list({
        bookingId,
        [idKey]: frozen.resourceId,
        date: frozen.bookingDate,
        page: 1,
        pageSize: 2
      })
      if (!current()) return null
      if (!response || response.code !== 0) throw response || new Error('预约记录读取失败。')
      const list = response.data?.list
      const total = response.data?.total
      if (!Array.isArray(list) || !Number.isInteger(total) || total < 0 || list.length > 2) {
        throw new Error('精确预约查询未返回有效 list/total。')
      }
      if (total === 0 && list.length === 0) return null
      if (total !== 1 || list.length !== 1) throw new Error('精确预约查询返回了多个对象，已停止确认。')
      if (!this.recordMatches(list[0], frozen, bookingId)) {
        throw new Error('预约身份、资源或时段与办理对象不一致。')
      }
      return list[0]
    },
    operationCurrent(operation) {
      return !this.disposed && this.pending === operation &&
        operation.identity === this.identityKey() && operation.kind === this.kind
    },
    startPending({ action, row, expected, reason = '' }) {
      this.restorePending()
      if (this.pending) return null
      if (!globalThis.crypto?.randomUUID) { this.error = '当前浏览器无法生成可靠命令标识，未发送预约'; return null }
      const operation = {
        commandKey: globalThis.crypto.randomUUID(),
        serial: ++this.operationSerial,
        identity: this.identityKey(),
        recoveryIdentity: this.recoveryKey(),
        kind: this.kind,
        action,
        id: String(row.bookingId || ''),
        row: { ...row, kind: this.kind },
        expected,
        reason,
        postState: 'IN_FLIGHT',
        postMatches: false
      }
      this.pending = operation
      this.receipt = {
        title: '预约办理回执',
        object: operation.id ? '预约 #' + operation.id :
          this.label + ' #' + row.resourceId + ' · ' + row.bookingDate + ' 第' + row.slotNo + '节',
        status: '结果待确认',
        pending: true,
        next: '命令只发送一次；将精确查询正式预约记录。'
      }
      if (!this.persistPending()) {
        this.pending = null
        this.receipt = { ...this.receipt, status: '未发送', pending: false, next: this.recoveryError }
        this.error = this.recoveryError
        this.formError = this.recoveryError
        this.review.error = this.recoveryError
        return null
      }
      return this.pending
    },
    postResponseMatches(operation, row) {
      if (!this.recordMatches(row, operation.row, operation.id) ||
        String(row?.status || '') !== operation.expected) return false
      if (operation.kind === 'LAB' && operation.action === 'APPROVE' &&
        String(row?.classroomId || '') !== String(operation.row.mappedClassroomId || '')) return false
      if (operation.action === 'REJECT') {
        return String(row?.reviewReason || '').trim() === operation.reason.trim()
      }
      return true
    },
    clearPending(operation) {
      if (this.pending !== operation) return
      if (!this.forgetPending(operation.recoveryIdentity)) return
      this.pending = null
    },
    async submitBook() {
      if (this.saving || this.pending) return
      const form = { ...this.form }
      if (!/^[1-9]\d*$/.test(String(form.resourceId || '')) || !form.bookingDate || !Number.isInteger(Number(form.slotNo)) ||
        form.slotNo < 1 || form.slotNo > 12 || !form.purpose?.trim()) {
        this.formError = '请填写资源、日期、1–12节及预约用途。'
        return
      }
      const frozen = {
        kind: this.kind,
        bookingId: '',
        resourceId: String(form.resourceId),
        resourceText: '',
        bookingDate: String(form.bookingDate),
        slotNo: Number(form.slotNo),
        purpose: form.purpose.trim(),
        applicantName: '',
        status: ''
      }
      const body = {
        [this.idKey]: frozen.resourceId,
        bookingDate: frozen.bookingDate,
        slotNo: frozen.slotNo,
        purpose: frozen.purpose
      }
      const operation = this.startPending({ action: 'BOOK', row: frozen, expected: 'PENDING' })
      if (!operation) return
      const current = () => this.operationCurrent(operation)
      this.saving = true
      this.formError = ''
      try {
        const response = await this.api.book(body, operation.commandKey)
        if (!current()) return
        if (!response || response.code !== 0) throw response || new Error('预约提交失败。')
        operation.id = String(response.data?.bookingId || '')
        operation.row.bookingId = operation.id
        operation.postState = 'SUCCESS'
        operation.postMatches = Boolean(operation.id) &&
          this.recordMatches(response.data, operation.row, operation.id) &&
          String(response.data?.status || '') === operation.expected
        this.bookVisible = false
        this.persistPending()
        await this.resolvePending(operation)
      } catch (e) {
        if (current()) await this.handlePostFailure(e, operation, 'formError')
      } finally {
        if (!this.disposed && operation.identity === this.identityKey() && operation.kind === this.kind) {
          this.saving = false
        }
      }
    },
    approvalBlockReason(row) {
      if (this.kind === 'LAB') return row?.mappedClassroomId && row?.labVersion != null ? '' : '实训室缺少正式场地关联或资源版本，请先核对资源目录。'
      const resourceId = row?.resourceId || row?.[this.idKey]
      const resource = this.resources.find(item => String(item[this.idKey]) === String(resourceId))
      if (resource && resource.status !== 'AVAILABLE') return '教室当前维修或停用，不能通过预约。'
      if (resource && resource.allowBorrow !== true) return '教室未开放借用，不能通过预约。'
      return ''
    },
    async requireClassroomReviewable(row, current) {
      const response = await academicAffairsApi.getClassroom(row.resourceId)
      if (!current()) return
      if (!response || response.code !== 0) throw response || new Error('教室资料读取失败。')
      const room = response.data
      if (!room || String(room.classroomId || '') !== String(row.resourceId)) {
        throw new Error('教室资料与预约对象不一致。')
      }
      if (room.status !== 'AVAILABLE') {
        throw { code: 409001, message: '教室当前维修或停用，不能审核通过。' }
      }
      if (room.allowBorrow !== true) {
        throw { code: 409001, message: '教室未开放借用，不能审核通过。' }
      }
    },
    openReview(row, action) {
      if (!this.canReview || this.saving || this.pending || row.status !== 'PENDING') return
      const frozen = this.freezeRow(row)
      this.review = {
        visible: true,
        row: frozen,
        action,
        reason: '',
        error: action === 'APPROVE' ? this.approvalBlockReason(frozen) : '',
        identity: this.identityKey(),
        kind: this.kind,
        token: ++this.operationSerial
      }
    },
    reviewCurrent(intent) {
      return !this.disposed && this.review.token === intent.token &&
        intent.identity === this.identityKey() && intent.kind === this.kind
    },
    async refreshReviewAfterConflict(intent, error) {
      const current = () => this.reviewCurrent(intent)
      try {
        const row = await this.readRecord(intent.row.bookingId, intent.row, current)
        if (!current()) return
        if (row) this.review.row = this.freezeRow(row)
        this.review.error = '事实已变化，已重新读取当前预约。' + (error?.message || '')
        this.receipt = {
          title: '预约审核未生效',
          object: '预约 #' + intent.row.bookingId,
          status: row ? this.statusLabel(row.status) : '正式记录不存在',
          pending: true,
          time: row?.reviewedAt || row?.createdAt,
          next: '已保留本次审核意见，请按当前正式状态重新核对。'
        }
      } catch (readError) {
        if (current()) this.failure(readError, 'review')
      }
      await this.load()
    },
    async submitReview() {
      if (!this.canReview || this.saving || this.pending || !this.review.row || this.review.row.status !== 'PENDING' ||
        !['APPROVE', 'REJECT'].includes(this.review.action)) return
      const blocked = this.review.action === 'APPROVE' ? this.approvalBlockReason(this.review.row) : ''
      if (blocked) { this.review.error = blocked; return }
      const intent = {
        token: this.review.token,
        identity: this.review.identity,
        kind: this.review.kind,
        row: { ...this.review.row },
        action: this.review.action,
        reason: this.review.reason.trim()
      }
      const current = () => this.reviewCurrent(intent)
      if (intent.action === 'REJECT' && intent.reason.length < 5) {
        this.review.error = '驳回原因不少于5字。'
        return
      }
      this.saving = true
      this.review.error = ''
      let operation = null
      try {
        const fresh = await this.readRecord(intent.row.bookingId, intent.row, current)
        if (!current()) return
        if (!fresh || fresh.status !== 'PENDING') {
          throw { code: 409001, message: '预约已不在待审状态。' }
        }
        if (intent.action === 'APPROVE') {
          if (intent.kind === 'LAB' && (!fresh.mappedClassroomId ||
            String(fresh.mappedClassroomId) !== String(intent.row.mappedClassroomId) ||
            fresh.labVersion == null || Number(fresh.labVersion) !== Number(intent.row.labVersion))) {
            throw { code: 409001, message: '实训室场地关联或资源版本已变化，请重新核对后确认。' }
          }
          await this.requireClassroomReviewable(intent.kind === 'LAB'
            ? { ...intent.row, resourceId: intent.row.mappedClassroomId } : intent.row, current)
          if (!current()) return
        }
        operation = this.startPending({
          action: intent.action,
          row: intent.row,
          expected: intent.action === 'APPROVE' ? 'APPROVED' : 'REJECTED',
          reason: intent.reason
        })
        if (!operation) return
        const operationIsCurrent = () => this.operationCurrent(operation)
        const response = await this.api.review(intent.row.bookingId, intent.action, intent.reason, intent.kind==='LAB'?{expectedLabVersion:Number(intent.row.labVersion),expectedClassroomId:intent.row.mappedClassroomId}:undefined, operation.commandKey)
        if (!operationIsCurrent()) return
        if (!response || response.code !== 0) throw response || new Error('预约审核提交失败。')
        operation.postState = 'SUCCESS'
        operation.postMatches = this.postResponseMatches(operation, response.data)
        this.review.visible = false
        this.persistPending()
        await this.resolvePending(operation)
      } catch (e) {
        if (operation && this.operationCurrent(operation)) {
          await this.handlePostFailure(e, operation, 'review', intent)
        } else if (current()) {
          this.failure(e, 'review')
          if (isConflictResult(e)) await this.refreshReviewAfterConflict(intent, e)
        }
      } finally {
        if (!this.disposed && intent.identity === this.identityKey() && intent.kind === this.kind) {
          this.saving = false
        }
      }
    },
    async handlePostFailure(error, operation, field, reviewIntent = null) {
      if (!this.operationCurrent(operation)) return
      if (operation.postState === 'SUCCESS') {
        if (isDeniedResult(error)) {
          this.failure(error, field)
          return
        }
        this.persistPending()
        this.failure(error, field)
        if (isConflictResult(error)) await this.load()
        return
      }
      if (isDeniedResult(error)) { this.failure(error, field); return }
      const knownFailure = isConflictResult(error) ||
        /^(400|422)/.test(String(error?.code || '')) || Number(error?.status) === 422 || error?.bizCode === 'VALIDATION_ERROR'
      if (knownFailure) {
        this.receipt = {
          ...this.receipt,
          status: '未办理',
          pending: false,
          next: error?.message || '服务端拒绝了本次命令，请核对后重新办理。'
        }
        this.clearPending(operation)
        this.failure(error, field)
        if (reviewIntent && isConflictResult(error) && this.reviewCurrent(reviewIntent)) {
          await this.refreshReviewAfterConflict(reviewIntent, error)
        } else if (!isDeniedResult(error)) {
          await this.load()
        }
        return
      }
      operation.postState = 'UNKNOWN'
      operation.postMatches = false
      this.persistPending()
      this.failure(error, field)
      try {
        await this.resolvePending(operation)
      } catch (readError) {
        if (this.operationCurrent(operation)) this.failure(readError, field)
      }
    },
    async resolvePending(operation = this.pending) {
      if (!this.operationCurrent(operation)) return
      if (operation.commandKey && (operation.postState !== 'SUCCESS' || !operation.postMatches)) {
        const name = 'RESOURCE_' + operation.kind + (operation.action === 'BOOK' ? '_BOOK' : '_REVIEW')
        const response = await academicAffairsResourceApi.commandReceipt(operation.commandKey, name)
        if (!this.operationCurrent(operation)) return
        if (response?.code !== 0) throw response || new Error('原预约命令回执读取失败')
        const receipt = response.data
        if (receipt?.commandKey !== operation.commandKey || receipt.operation !== name ||
          !['SUCCESS', 'UNRESOLVED'].includes(receipt.state)) throw new Error('原预约命令回执标识不一致')
        if (receipt.state === 'SUCCESS') {
          const result = receipt.result
          const id = operation.id || String(result?.bookingId || '')
          if (!/^[1-9]\d*$/.test(id) || !this.recordMatches(result, operation.row, id) || result.status !== operation.expected) {
            throw new Error('原命令回执与冻结的预约对象不一致')
          }
          if (operation.recovered && operation.action === 'REJECT') operation.reason = String(result.reviewReason || '')
          operation.id = id
          operation.postMatches = this.postResponseMatches(operation, result)
          operation.postState = 'SUCCESS'
          this.persistPending()
        }
      }
      if (!operation.id) {
        this.receipt = {
          ...this.receipt,
          status: '结果待确认',
          pending: true,
          next: '请求没有返回正式预约编号，无法把列表中的相似记录认作本次结果。请联系资源管理员；本页不会再次发送申请。'
        }
        this.persistPending()
        await this.load()
        return
      }
      const current = () => this.operationCurrent(operation)
      const row = await this.readRecord(operation.id, operation.row, current)
      if (!current()) return
      const readMatches = row && String(row.status || '') === operation.expected &&
        (operation.kind !== 'LAB' || operation.action !== 'APPROVE' ||
          String(row.classroomId || '') === String(operation.row.mappedClassroomId || '')) &&
        (operation.recovered || operation.action !== 'REJECT' ||
          String(row.reviewReason || '').trim() === operation.reason.trim())
      const advanced = operation.action === 'BOOK' && row && ['APPROVED', 'REJECTED', 'CANCELLED'].includes(row.status)
      const confirmed = operation.postState === 'SUCCESS' && operation.postMatches && (readMatches || advanced)
      let status = '结果待确认'
      let next = '尚未读到相应正式状态，请继续查询，不要重复提交。'
      if (confirmed) {
        status = this.statusLabel(row.status)
        next = row.status === 'PENDING'
          ? '由资源管理员审核，请在当日预约记录中查看进度。'
          : '请按正式审核结果安排使用，并继续遵守教室开放规则。'
        if (advanced) next = '原申请命令已确认；预约随后已进入' + this.statusLabel(row.status) + '，后续审核不归属于本次申请。'
      } else if (row && readMatches && operation.postState !== 'SUCCESS') {
        status = '正式记录为' + this.statusLabel(row.status) + '，本次请求仍待确认'
        next = '请求结果未知，当前状态不能证明由本次命令产生；请联系资源管理员，本页不会再次发送命令。'
      } else if (operation.postState === 'SUCCESS' && !operation.postMatches) {
        next = '命令响应与冻结的预约对象或预期状态不一致，已停止确认；请联系资源管理员。'
      }
      this.receipt = {
        title: '预约办理回执',
        object: '预约 #' + operation.id + ' · ' +
          (row?.[operation.kind === 'CLASSROOM' ? 'classroomText' : 'labText'] ||
            operation.row.resourceText || operation.row.resourceId) +
          ' · ' + operation.row.bookingDate + ' 第' + operation.row.slotNo + '节',
        status,
        pending: !confirmed,
        time: row?.reviewedAt || row?.createdAt,
        next
      }
      if (confirmed) this.clearPending(operation)
      else this.persistPending()
      await this.load()
    },
    async queryPending() {
      if (this.pending?.referenceUnavailable) { this.pending = null; this.restorePending(); return }
      const operation = this.pending
      if (this.saving || !operation || !this.operationCurrent(operation)) return
      const current = () => this.operationCurrent(operation)
      this.saving = true
      try {
        await this.resolvePending(operation)
      } catch (e) {
        if (current()) this.failure(e)
      } finally {
        if (!this.disposed && operation.identity === this.identityKey() && operation.kind === this.kind) {
          this.saving = false
        }
      }
    }
  }
}
</script>
<style scoped>
.booking-stack{display:grid;gap:18px}.booking-toolbar,.booking-card header,.booking-pager{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.booking-toolbar{margin:18px 0}.booking-toolbar label{display:flex;align-items:center;gap:10px}.booking-toolbar>span,.booking-note,.booking-card header>span,.booking-pager span{font-size:12px;color:var(--text-secondary)}.booking-card{border:1px solid var(--border-base);border-radius:12px;padding:18px;background:var(--bg-card);min-width:0}.booking-card header{margin-bottom:16px}.booking-card h2{font-size:16px;margin:0}.booking-matrix{overflow:auto}.booking-matrix table{border-collapse:collapse;min-width:1250px;width:100%;font-size:12px}.booking-matrix th,.booking-matrix td{padding:12px 8px;border:1px solid var(--border-base);text-align:center}.booking-matrix th{background:var(--pri-bg);font-weight:500}.booking-matrix th:first-child{min-width:150px;text-align:left}.booking-card small{display:block;color:var(--text-secondary);font-size:11px;margin-top:5px}.booking-matrix button{border:1px solid var(--primary-200);border-radius:5px;background:var(--bg-card);padding:8px 5px;color:var(--pri);font:inherit;cursor:pointer}.booking-matrix button.occupied{background:var(--pri-bg);color:var(--text-secondary)}.booking-pager{justify-content:flex-end;margin-top:14px}.booking-form{display:grid;gap:16px}.booking-form p{line-height:1.7;color:var(--text-secondary)}
</style>
