<template>
  <AppPageShell
    title="调宿与退宿"
    subtitle="调宿走「辅导员 → 宿管」两级审批，终审通过自动执行（原床释放 / 新床占用 / 回写我的宿舍）。"
    role-name="辅导员 / 宿管 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍调宿审批"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.transfer.create')" code="studentAffairs.dorm.transfer.create" :loading="actioning" @click="submitTransfer">
        发起调宿
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载调宿申请..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="调宿申请">
        <div v-if="studentFilterLabel" class="sa-student-filter">
          <span>{{ studentFilterLabel }}</span>
          <button type="button" class="mp-link" @click="clearStudentFilter">清除筛选</button>
        </div>
        <DataTable v-if="displayItems.length || pagination.total > 0" :columns="transferColumns" :rows="displayItems" row-key="transferId"
                   :pagination="pagination" @page-change="onPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || row.studentId }}</span><div class="mp-cell-sub">{{ row.studentNo }}</div></template>
          <template #cell-toBed="{ row }">床 #{{ row.toBedId }}</template>
          <template #cell-reason="{ row }">{{ row.reason || '—' }}</template>
          <template #cell-node="{ row }">{{ nodeLabel(row.currentNode) }}</template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="statusLabel(row.status)" /></template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <template v-if="isPending(row.status)">
                <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.transfer.approve')" code="studentAffairs.dorm.transfer.approve" size="sm" :loading="actioning" @click="review(row, 'APPROVE')">通过</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.transfer.approve')" code="studentAffairs.dorm.transfer.approve" size="sm" variant="secondary" :loading="actioning" @click="review(row, 'REJECT')">驳回</AppPermissionButton>
              </template>
              <span v-else class="sa-muted">—</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无调宿申请</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 发起调宿：原为「学生 ID→目标床位 ID→事由」3 连原生弹窗，两个 ID 全靠手打，
         而后端 buildings/rooms/beds 三个端点本就是为「选床级联」设计的（见 service docstring），前端此前未用。 -->
    <AppDrawer :visible="dlg.visible" title="发起调宿" @close="dlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="调宿学生" required>
          <AppStudentPicker v-model="dlg.studentId"
                            placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="目标楼栋" required>
          <AppDormBuildingPicker v-model="dlg.buildingId" :options="buildingOptions" placeholder="选择楼栋"
                     :disabled="actioning" @change="onBuildingChange" />
        </AppFormItem>
        <AppFormItem label="目标房间" required>
          <AppDormRoomPicker v-model="dlg.roomId" :options="roomOptions" :query="{ buildingId: dlg.buildingId }" :disabled="actioning || !dlg.buildingId"
                     :placeholder="dlg.buildingId ? '选择房间' : '请先选楼栋'" @change="onRoomChange" />
        </AppFormItem>
        <AppFormItem label="目标床位（仅列空床）" required>
          <AppDormBedPicker v-model="dlg.toBedId" :options="bedOptions" :query="{ roomId: dlg.roomId, vacantOnly: true }" :disabled="actioning || !dlg.roomId"
                     :placeholder="bedPlaceholder" />
        </AppFormItem>
        <AppFormItem label="调宿事由">
          <AppTextarea v-model="dlg.reason" :rows="3" :maxlength="500" :disabled="actioning"
                       placeholder="如：与同宿舍同学作息冲突，申请调至同楼层空床" />
        </AppFormItem>
        <p class="dr-hint">提交后走「辅导员 → 宿管」两级审批，终审通过自动执行换床。</p>
        <AppInlineAlert v-if="dlg.error" type="danger" :description="dlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="dlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitDlg">提交申请</AppButton>
      </template>
    </AppDrawer>

    <!-- 驳回原因：原生 prompt 无法多行、无快捷用语 -->
    <AppConfirmDialog
      v-model:visible="rejDlg.visible" title="驳回调宿申请" type="danger" confirm-text="确认驳回"
      require-reason :reason-min-length="5" reason-label="驳回原因（≥5 字）"
      phrase-scene-key="sa.dorm.reject" :submitting="actioning" @confirm="submitReject"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
  AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker, AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { resolveTodoStatus, readStudentFilter } from '@/modules/studentAffairs/utils/todoFilterSemantics'


const TRANSFER_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'toBed', title: '目标床' },
  { key: 'reason', title: '事由' },
  { key: 'node', title: '当前节点' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '180px' }
]

export default {
  name: 'DormTransferView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
    AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker, AppTextarea, DataTable
  },
  data() {
    return {
      transferColumns: TRANSFER_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [], statusCounts: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      buildings: [], rooms: [], beds: [],
      studentFilter: { studentId: '', studentNo: '', studentName: '' },
      statusMatch: null,
      dlg: { visible: false, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' },
      rejDlg: { visible: false, transferId: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      let name = f.studentName || ''
      let no = f.studentNo || ''
      const id = f.studentId || ''
      if ((!name || !no) && id && this.items && this.items.length) {
        const hit = this.items.find((x) => String(x.studentId) === String(id))
        if (hit) {
          if (!name) name = hit.realName || ''
          if (!no) no = hit.studentNo || ''
        }
      }
      if (name || no) return `当前学生筛选：${name || '学生'}${no ? ` / ${no}` : ''}`
      return `当前学生筛选：#${id}`
    },
    displayItems() {
      let arr = this.items
      const sid = this.studentFilter && this.studentFilter.studentId
      if (sid) arr = arr.filter((x) => String(x.studentId) === String(sid))
      if (this.statusMatch && this.statusMatch.length) {
        arr = arr.filter((x) => this.statusMatch.includes(x.status) || (this.statusMatch.includes('PENDING') && this.isPending(x.status)))
      }
      return arr
    },
    metricCards() {
      return [
        { key: 'p', label: '待审批', value: '—', accent: 'warning' },
        { key: 'e', label: '已执行', value: this.statusCounts === null ? '—' : (this.statusCounts.EXECUTED || 0), accent: 'primary' },
        { key: 'r', label: '已驳回', value: this.statusCounts === null ? '—' : (this.statusCounts.REJECTED || 0), accent: 'info' },
        { key: 't', label: '合计', value: this.statusCounts === null ? '—' : (this.statusCounts.ALL || 0), accent: 'info' }
      ]
    },
    buildingOptions() {
      return this.buildings.map((b) => ({ value: String(b.buildingId), label: b.buildingName || `楼栋 #${b.buildingId}` }))
    },
    roomOptions() {
      return this.rooms.map((r) => ({
        value: String(r.roomId),
        label: `${r.roomNo || `房间 #${r.roomId}`}${r.vacantBeds != null ? `（空 ${r.vacantBeds}）` : ''}`
      }))
    },
    /** 只列空床——调宿目标必须是空床，列出已住床位只会让人选错后被后端打回。 */
    bedOptions() {
      return this.beds.filter((b) => b.status === 'VACANT')
        .map((b) => ({ value: String(b.bedId), label: `${b.bedNo} 号床` }))
    },
    bedPlaceholder() {
      if (!this.dlg.roomId) return '请先选房间'
      return this.bedOptions.length ? '选择空床' : '该房间当前无空床'
    }
  },
  mounted() {
    this.applyRouteFilters()
    this.load()
    this.loadBuildings()
  },
  watch: {
    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.load() }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      if (!q.status) { this.statusMatch = null; return }
      const resolved = resolveTodoStatus('dormTransfer', q.status)
      this.statusMatch = resolved.matchStatuses
    },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      const q = { ...this.$route.query }
      delete q.studentId
      delete q.studentNo
      delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const sid = this.studentFilter && this.studentFilter.studentId
        const res = await studentAffairsApi.listDormTransfers({
          page: this.pagination.page, pageSize: this.pagination.pageSize, studentId: sid || undefined
        })
        this.items = res.data.items || []
        this.pagination.total = res.data.total != null ? res.data.total : this.items.length
        this.statusCounts = res.data.statusCounts || null
      }
      catch (e) { this.errorMessage = e.message || '调宿加载失败' } finally { this.loading = false }
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async loadBuildings() {
      try { this.buildings = (await studentAffairsApi.listDormBuildings({ pageSize: 200 })).data.items || [] }
      catch { this.buildings = [] }
    },
    /* ── 发起调宿：学生选择器 + 楼栋/房间/床位三级联动 ── */
    submitTransfer() {
      this.dlg = { visible: true, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' }
      this.rooms = []; this.beds = []
    },
    async onBuildingChange() {
      this.dlg.roomId = ''; this.dlg.toBedId = ''; this.beds = []
      if (!this.dlg.buildingId) { this.rooms = []; return }
      // 待服务端全量统计：下拉列表仅加载 API 单页上限。
      try { this.rooms = (await studentAffairsApi.listDormRooms(this.dlg.buildingId, { pageSize: 200 })).data.items || [] }
      catch (e) { this.rooms = []; this.dlg.error = e.message || '房间加载失败' }
    },
    async onRoomChange() {
      this.dlg.toBedId = ''
      if (!this.dlg.roomId) { this.beds = []; return }
      try { this.beds = (await studentAffairsApi.listDormBeds(this.dlg.roomId)).data.items || [] }
      catch (e) { this.beds = []; this.dlg.error = e.message || '床位加载失败' }
    },
    async submitDlg() {
      const d = this.dlg
      if (!d.studentId) { d.error = '请选择调宿学生'; return }
      if (!d.toBedId) { d.error = '请选择目标空床'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.submitDormTransfer({
        studentId: d.studentId, toBedId: d.toBedId, reason: (d.reason || '').trim()
      }))
      if (ok) d.visible = false
      else d.error = this.errorMessage
    },
    /* ── 审批 ── */
    async review(t, action) {
      if (action === 'REJECT') {
        this.rejDlg = { visible: true, transferId: t.transferId, version: t.version }
        return
      }
      await this.runAction(() => studentAffairsApi.reviewDormTransfer(t.transferId, action, '', t.version))
    },
    async submitReject({ reason }) {
      const d = this.rejDlg
      const ok = await this.runAction(() => studentAffairsApi.reviewDormTransfer(d.transferId, 'REJECT', reason.trim(), d.version))
      if (ok) this.rejDlg.visible = false
    },
    /** @returns {boolean} 是否成功；失败时保留弹窗与已填内容。 */
    async runAction(fn) {
      this.actioning = true; this.errorMessage = ''
      try { await fn(); await this.load(); return true }
      catch (e) { this.errorMessage = e.message || '操作失败'; return false }
      finally { this.actioning = false }
    },
    isPending(s) { return s === 'COUNSELOR_REVIEW' || s === 'DORM_MANAGER_REVIEW' || s === 'SUBMITTED' },
    nodeLabel(n) { return ({ COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核' })[n] || (n || '—') },
    statusLabel(s) { return ({ SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回', CANCELLED: '已取消' })[s] || s },
    statusKind(s) { if (s === 'EXECUTED') return 'success'; if (s === 'REJECTED') return 'danger'; if (this.isPending(s)) return 'warning'; return 'info' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-student-filter {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);
  margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md); background: var(--warning-50, #fffbeb);
  border: 1px solid var(--warning-200, #fde68a); font-size: var(--font-size-sm); color: var(--text-primary);
}
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.dr-form { display: flex; flex-direction: column; gap: var(--space-4); }
.dr-hint { margin: 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@import '@/styles/module-page.css';
</style>
