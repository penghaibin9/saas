<template>
  <AppPageShell
    title="入住管理"
    subtitle="本页办理正式入住与退宿；学生自选由「分配计划」的批次、资源池和时间窗控制。"
    role-name="学工处 / 辅导员 / 宿管"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍入住管理"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" variant="secondary" @click="$router.push('/admin/student-affairs/dorm/allocation')">
        管理分配计划
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前分配模式</span>
          <h2 class="sa-summary-strip__title">{{ config.selfSelectEnabled ? '学生自选床位已开放' : '当前由辅导员 / 宿管统一分配床位' }}</h2>
          <p class="sa-summary-strip__text">{{ config.studentNotice || '选择楼栋和房间后查看床位。空床可办理入住，已住床位可办理退宿。' }}</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" variant="secondary" @click="$router.push('/admin/student-affairs/dorm/allocation')">
            管理分配计划
          </AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="宿舍入住办理流程">
        <div class="sa-workflow-step" data-step="1"><strong>选择楼栋</strong><br>仅展示当前角色可管理的楼栋</div>
        <div class="sa-workflow-step" data-step="2"><strong>选择房间</strong><br>查看房间空床数量和床位清单</div>
        <div class="sa-workflow-step" data-step="3"><strong>核对床位</strong><br>确认空床或当前入住学生</div>
        <div class="sa-workflow-step" data-step="4"><strong>办理结果</strong><br>入住写住宿历史；退宿进入宿管确认后释放床位</div>
      </div>

      <AppSectionCard title="分配模式说明">
        <div class="sa-mode-card" :class="config.selfSelectEnabled ? 'is-open' : 'is-managed'">
          <div>
            <span class="sa-mode-card__label">当前模式</span>
            <strong>{{ config.selfSelectEnabled ? '学生自选' : '统一分配' }}</strong>
          </div>
          <p>{{ config.studentNotice || '当前模式说明暂未配置' }}</p>
        </div>
      </AppSectionCard>

      <AppSectionCard title="选床入住 / 退宿">
        <p class="sa-section-hint">按顺序选择楼栋和房间。床位列表会显示当前状态与入住学生，避免在不同房间间反复查找。</p>
        <AppInlineAlert v-if="routeNotice" type="info" :description="routeNotice" />
        <div class="sa-toolbar dorm-picker-bar">
          <AppDormBuildingPicker v-model="curBuilding" :options="buildingOptions" placeholder="选择楼栋" class="sa-pick" @change="loadRooms" />
          <AppDormRoomPicker v-model="curRoom" :options="roomOptions" :query="{ buildingId: curBuilding }" placeholder="选择房间" class="sa-pick"
                     :disabled="!curBuilding" @change="loadBeds" />
        </div>
        <template v-if="curRoom">
          <DataTable v-if="beds.length" :columns="bedColumns" :rows="beds" row-key="bedId" :row-class="bedRowClass">
            <template #cell-bedNo="{ row }"><span class="mp-cell-main">{{ row.bedNo }} 号床</span></template>
            <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'OCCUPIED' ? 'warning' : 'success'" :label="row.status === 'OCCUPIED' ? '已住' : '空床'" /></template>
            <template #cell-occupant="{ row }"><span :class="row.occupantName ? 'dorm-occupied' : 'sa-muted'">{{ row.occupantName || '暂无学生' }}</span></template>
            <template #cell-actions="{ row }">
              <div class="sa-actions">
                <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.allocation.manage')" v-if="row.status !== 'OCCUPIED'" code="studentAffairs.dorm.allocation.manage" size="sm" :loading="actioning" @click="checkin(row)">入住</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.allocation.manage')" v-else code="studentAffairs.dorm.allocation.manage" size="sm" variant="secondary" :loading="actioning" @click="checkout(row)">退宿</AppPermissionButton>
              </div>
            </template>
          </DataTable>
          <p v-else class="sa-empty">该房间暂未配置床位，请返回宿舍资源配置检查房间和床位。</p>
        </template>
        <p v-else class="sa-empty">请先选择楼栋，再选择房间；系统随后显示该房间全部床位和入住状态。</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="inDlg.visible" :title="`办理入住 · ${inDlg.bedLabel}`" type="primary"
      confirm-text="确认入住" :submitting="actioning" @confirm="submitCheckin"
    >
      <AppFormItem label="入住学生" required>
        <AppStudentPicker v-model="inDlg.studentId"
                          placeholder="按姓名 / 学号搜索" :disabled="actioning" />
      </AppFormItem>
      <AppInlineAlert v-if="inDlg.error" type="danger" :description="inDlg.error" />
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="outDlg.visible" title="办理退宿" type="warning" confirm-text="确认退宿"
      :description="`为 ${outDlg.who} 发起正式退宿单；宿管确认前床位和住宿关系保持不变。`"
      :submitting="actioning" @confirm="submitCheckout"
    >
      <AppFormItem label="退宿类型" required>
        <select v-model="outDlg.requestType" class="sa-native-select" :disabled="actioning">
          <option value="GRADUATION">毕业</option><option value="LEAVE_OF_ABSENCE">休学</option>
          <option value="WITHDRAWAL">退学</option><option value="DAY_STUDENT">转走读</option>
          <option value="SPECIAL">特殊退宿</option>
        </select>
      </AppFormItem>
      <AppFormItem label="退宿原因（5-500字）" required>
        <AppTextarea v-model="outDlg.reason" :rows="3" :maxlength="500" :disabled="actioning" />
      </AppFormItem>
      <AppInlineAlert v-if="outDlg.error" type="danger" :description="outDlg.error" />
    </AppConfirmDialog>

  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
  AppSectionCard, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker,
  AppTextarea
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const BED_COLUMNS = [
  { key: 'bedNo', title: '床号' },
  { key: 'status', title: '状态' },
  { key: 'occupant', title: '入住学生' },
  { key: 'actions', title: '操作', align: 'right', width: '140px' }
]

export default {
  name: 'DormCheckinView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
    AppSectionCard, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker,
    AppTextarea, DataTable
  },
  data() {
    return {
      bedColumns: BED_COLUMNS,
      loading: true, actioning: false, errorMessage: '', config: {}, buildings: [], curBuilding: '',
      rooms: [], curRoom: '', beds: [], routeBedId: '', routeNotice: '',
      inDlg: { visible: false, bedId: '', bedLabel: '', studentId: '', error: '' },
      outDlg: { visible: false, bedId: '', who: '', version: null, requestType: 'SPECIAL', reason: '', clientRequestId: '', error: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    buildingOptions() {
      return this.buildings.map((b) => ({
        value: String(b.buildingId),
        label: `${b.buildingName || `楼栋 #${b.buildingId}`}${b.vacantBeds != null ? `（空床 ${b.vacantBeds}）` : ''}`
      }))
    },
    roomOptions() {
      return this.rooms.map((r) => ({
        value: String(r.roomId),
        label: `${r.roomNo || `房间 #${r.roomId}`}${r.vacantBeds != null ? `（空 ${r.vacantBeds}）` : ''}`
      }))
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const [cfg, bs] = await Promise.all([studentAffairsApi.getDormConfig(), studentAffairsApi.listDormBuildings()])
        this.config = cfg.data || {}; this.buildings = bs.data.items || []
        await this.applyRouteSelection()
      } catch (e) { this.errorMessage = e.message || '加载失败' } finally { this.loading = false }
    },
    async applyRouteSelection() {
      this.routeNotice = ''
      const buildingId = String(this.$route.query.buildingId || '')
      if (!buildingId) return
      const building = this.buildings.find((row) => String(row.buildingId) === buildingId)
      if (!building) {
        this.routeNotice = '目标楼栋不在当前数据范围内，请从可见楼栋重新选择。'
        return
      }
      this.curBuilding = buildingId
      await this.loadRooms()
      const roomId = String(this.$route.query.roomId || '')
      const room = this.rooms.find((row) => String(row.roomId) === roomId)
      if (!room) {
        if (roomId) this.routeNotice = '目标房间已不可用，请从当前楼栋重新选择。'
        return
      }
      this.curRoom = roomId
      await this.loadBeds()
      const bedId = String(this.$route.query.bedId || '')
      const bed = this.beds.find((row) => String(row.bedId) === bedId)
      if (!bed) {
        if (bedId) this.routeNotice = '目标床位已不可用，请核对当前房间的最新床位状态。'
        return
      }
      this.routeBedId = bedId
      this.routeNotice = `已定位 ${building.buildingName || '目标楼栋'} / ${room.roomNo || '目标房间'} / ${bed.bedNo} 号床，请核对实时状态后办理。`
    },
    bedRowClass(row) {
      return String(row.bedId) === String(this.routeBedId) ? 'sa-sel' : ''
    },
    async loadRooms() {
      this.curRoom = ''; this.beds = []
      if (!this.curBuilding) { this.rooms = []; return }
      try { this.rooms = (await studentAffairsApi.listDormRooms(this.curBuilding)).data.items || [] }
      catch (e) { this.errorMessage = e.message }
    },
    async loadBeds() {
      if (!this.curRoom) { this.beds = []; return }
      try { this.beds = (await studentAffairsApi.listDormBeds(this.curRoom)).data.items || [] }
      catch (e) { this.errorMessage = e.message }
    },
    checkin(bd) {
      this.inDlg = { visible: true, bedId: bd.bedId, bedLabel: `${bd.bedNo} 号床`, studentId: '', error: '' }
    },
    async submitCheckin() {
      const d = this.inDlg
      if (!d.studentId) { d.error = '请选择入住学生'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.dormCheckin(d.bedId, d.studentId))
      if (ok) d.visible = false
      else d.error = this.errorMessage
    },
    checkout(bd) {
      this.outDlg = {
        visible: true, bedId: bd.bedId,
        who: bd.occupantName || `${bd.bedNo} 号床`, version: bd.version,
        requestType: 'SPECIAL', reason: '', clientRequestId: `checkout:${globalThis.crypto.randomUUID()}`, error: ''
      }
    },
    async submitCheckout() {
      const reason = (this.outDlg.reason || '').trim()
      if (reason.length < 5 || reason.length > 500) { this.outDlg.error = '退宿原因需5-500字'; return }
      this.actioning = true; this.errorMessage = ''
      try {
        await studentAffairsApi.createDormCheckout({
          bedId: Number(this.outDlg.bedId), expectedBedVersion: Number(this.outDlg.version),
          requestType: this.outDlg.requestType, reason,
          clientRequestId: this.outDlg.clientRequestId
        })
        this.outDlg.visible = false
        await this.$router.push({ path: '/admin/student-affairs/dorm/transfer', query: { tab: 'checkout' } })
      } catch (e) {
        this.outDlg.error = e.message || '退宿单发起失败'
        await this.loadBeds().catch(() => {})
        const latest = this.beds.find((x) => String(x.bedId) === String(this.outDlg.bedId))
        if (latest) this.outDlg.version = latest.version
      } finally {
        this.actioning = false
      }
    },
    async runAction(fn) {
      this.actioning = true; this.errorMessage = ''
      try { await fn(); await this.loadBeds(); await this.loadRooms2(); return true }
      catch (e) { this.errorMessage = e.message || '操作失败'; return false }
      finally { this.actioning = false }
    },
    async loadRooms2() {
      const bs = await studentAffairsApi.listDormBuildings(); this.buildings = bs.data.items || []
      if (this.curBuilding) this.rooms = (await studentAffairsApi.listDormRooms(this.curBuilding)).data.items || []
      if (this.curRoom) this.beds = (await studentAffairsApi.listDormBeds(this.curRoom)).data.items || []
    }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.sa-pick { min-width: 240px; flex: 0 1 320px; }
.sa-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.sa-mode-card { display: grid; grid-template-columns: minmax(180px, .45fr) minmax(0, 1fr); gap: var(--space-4); align-items: center; padding: var(--space-3) var(--space-4); border: 1px solid var(--border-light); border-radius: var(--radius-lg); background: var(--bg-section); }
.sa-mode-card.is-open { border-color: var(--success-200, #bbf7d0); background: var(--success-50, #f0fdf4); }
.sa-mode-card.is-managed { border-color: var(--primary-100, #dbeafe); background: var(--primary-50, #eff6ff); }
.sa-mode-card__label { display: block; margin-bottom: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sa-mode-card strong { color: var(--text-primary); font-size: var(--font-size-lg); }
.sa-mode-card p { margin: 0; color: var(--text-secondary); line-height: 1.65; }
.dorm-picker-bar { padding: 10px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-section); }
.sa-actions { display: flex; gap: var(--space-2); }
.dorm-occupied { color: var(--text-primary); font-weight: 600; }
.sa-native-select { width: 100%; min-height: 40px; padding: 8px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-card); color: var(--text-primary); }
@media (max-width: 720px) { .sa-mode-card { grid-template-columns: 1fr; } .sa-pick { width: 100%; flex-basis: 100%; } }
@import '@/styles/module-page.css';
</style>
