<template>
  <AppPageShell
    title="调宿与退宿"
    subtitle="调宿走「辅导员 → 宿管」两级审批，终审通过自动执行（原床释放 / 新床占用 / 回写我的宿舍）。"
    role-name="辅导员 / 宿管 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍调宿审批"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.transfer.create" :loading="actioning" @click="submitTransfer">
        发起调宿
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载调宿申请..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="调宿申请">
        <table class="sa-table">
          <thead><tr><th>学生</th><th>目标床</th><th>事由</th><th>当前节点</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in items" :key="t.transferId">
              <td><strong>{{ t.realName || t.studentId }}</strong><small>{{ t.studentNo }}</small></td>
              <td>床 #{{ t.toBedId }}</td>
              <td>{{ t.reason || '—' }}</td>
              <td>{{ nodeLabel(t.currentNode) }}</td>
              <td><AppStatusTag :type="statusKind(t.status)" :label="statusLabel(t.status)" /></td>
              <td class="sa-actions">
                <template v-if="isPending(t.status)">
                  <AppPermissionButton code="studentAffairs.dorm.transfer.approve" size="sm" :loading="actioning" @click="review(t, 'APPROVE')">通过</AppPermissionButton>
                  <AppPermissionButton code="studentAffairs.dorm.transfer.approve" size="sm" variant="secondary" :loading="actioning" @click="review(t, 'REJECT')">驳回</AppPermissionButton>
                </template>
                <span v-else class="sa-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无调宿申请</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 发起调宿：原为「学生 ID→目标床位 ID→事由」3 连原生弹窗，两个 ID 全靠手打，
         而后端 buildings/rooms/beds 三个端点本就是为「选床级联」设计的（见 service docstring），前端此前未用。 -->
    <AppDrawer :visible="dlg.visible" title="发起调宿" @close="dlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="调宿学生" required>
          <AppStudentPicker v-model="dlg.studentId" :remote-search="searchStudents"
                            placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="目标楼栋" required>
          <AppSelect v-model="dlg.buildingId" :options="buildingOptions" placeholder="选择楼栋"
                     :disabled="actioning" @change="onBuildingChange" />
        </AppFormItem>
        <AppFormItem label="目标房间" required>
          <AppSelect v-model="dlg.roomId" :options="roomOptions" :disabled="actioning || !dlg.buildingId"
                     :placeholder="dlg.buildingId ? '选择房间' : '请先选楼栋'" @change="onRoomChange" />
        </AppFormItem>
        <AppFormItem label="目标床位（仅列空床）" required>
          <AppSelect v-model="dlg.toBedId" :options="bedOptions" :disabled="actioning || !dlg.roomId"
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
  AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormTransferView',
  components: {
    AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
    AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextarea
  },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', items: [],
      buildings: [], rooms: [], beds: [],
      dlg: { visible: false, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' },
      rejDlg: { visible: false, transferId: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = this.items.filter((t) => this.isPending(t.status)).length
      const executed = this.items.filter((t) => t.status === 'EXECUTED').length
      const rejected = this.items.filter((t) => t.status === 'REJECTED').length
      return [
        { key: 'p', label: '待审批', value: pending, accent: pending ? 'warning' : 'success' },
        { key: 'e', label: '已执行', value: executed, accent: 'primary' },
        { key: 'r', label: '已驳回', value: rejected, accent: 'info' },
        { key: 't', label: '合计', value: this.items.length, accent: 'info' }
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
  mounted() { this.load(); this.loadBuildings() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try { this.items = (await studentAffairsApi.listDormTransfers({ pageSize: 100 })).data.items || [] }
      catch (e) { this.errorMessage = e.message || '调宿加载失败' } finally { this.loading = false }
    },
    async loadBuildings() {
      try { this.buildings = (await studentAffairsApi.listDormBuildings({ pageSize: 200 })).data.items || [] }
      catch { this.buildings = [] }
    },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    /* ── 发起调宿：学生选择器 + 楼栋/房间/床位三级联动 ── */
    submitTransfer() {
      this.dlg = { visible: true, studentId: '', buildingId: '', roomId: '', toBedId: '', reason: '', error: '' }
      this.rooms = []; this.beds = []
    },
    async onBuildingChange() {
      this.dlg.roomId = ''; this.dlg.toBedId = ''; this.beds = []
      if (!this.dlg.buildingId) { this.rooms = []; return }
      try { this.rooms = (await studentAffairsApi.listDormRooms(this.dlg.buildingId, { pageSize: 500 })).data.items || [] }
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
      if (action === 'REJECT') { this.rejDlg = { visible: true, transferId: t.transferId }; return }
      await this.runAction(() => studentAffairsApi.reviewDormTransfer(t.transferId, action, ''))
    },
    async submitReject({ reason }) {
      const ok = await this.runAction(() => studentAffairsApi.reviewDormTransfer(this.rejDlg.transferId, 'REJECT', reason.trim()))
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
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; vertical-align: top; }
.sa-table small { display: block; color: var(--text-tertiary); }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.dr-form { display: flex; flex-direction: column; gap: var(--space-4); }
.dr-hint { margin: 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
