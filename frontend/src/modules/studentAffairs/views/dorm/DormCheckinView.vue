<template>
  <AppPageShell
    title="入住管理"
    subtitle="按楼→房→床选定空床为学生办理入住，或办理退宿；学校可开关「学生自选宿舍」。"
    role-name="学工处 / 辅导员 / 宿管"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍入住管理"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.allocation.manage')" code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="toggleSelfSelect">
        {{ config.selfSelectEnabled ? '关闭学生自选' : '开放学生自选' }}
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
          <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.allocation.manage')" code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="toggleSelfSelect">
            {{ config.selfSelectEnabled ? '关闭学生自选' : '开放学生自选' }}
          </AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="宿舍入住办理流程">
        <div class="sa-workflow-step" data-step="1"><strong>选择楼栋</strong><br>仅展示当前角色可管理的楼栋</div>
        <div class="sa-workflow-step" data-step="2"><strong>选择房间</strong><br>查看房间空床数量和床位清单</div>
        <div class="sa-workflow-step" data-step="3"><strong>核对床位</strong><br>确认空床或当前入住学生</div>
        <div class="sa-workflow-step" data-step="4"><strong>办理结果</strong><br>入住占床、退宿释放床位并刷新台账</div>
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
        <div class="sa-toolbar dorm-picker-bar">
          <AppDormBuildingPicker v-model="curBuilding" :options="buildingOptions" placeholder="选择楼栋" class="sa-pick" @change="loadRooms" />
          <AppDormRoomPicker v-model="curRoom" :options="roomOptions" :query="{ buildingId: curBuilding }" placeholder="选择房间" class="sa-pick"
                     :disabled="!curBuilding" @change="loadBeds" />
        </div>
        <template v-if="curRoom">
          <DataTable v-if="beds.length" :columns="bedColumns" :rows="beds" row-key="bedId">
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
      :description="`确认为 ${outDlg.who} 办理退宿？该床位将立即释放为空床。`"
      :submitting="actioning" @confirm="submitCheckout"
    />

    <AppConfirmDialog
      v-model:visible="modeDlg.visible"
      :title="config.selfSelectEnabled ? '关闭学生自选宿舍' : '开放学生自选宿舍'"
      :type="config.selfSelectEnabled ? 'warning' : 'primary'"
      :confirm-text="config.selfSelectEnabled ? '确认关闭' : '确认开放'"
      :description="config.selfSelectEnabled
        ? '关闭后学生端将无法自选床位，改回由辅导员/宿管统一分配。已选定的床位不受影响。'
        : '开放后学生可在学生端自行选择空床位。该开关对全校生效。'"
      :submitting="actioning" @confirm="submitToggle"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
  AppSectionCard, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { dormReliabilityApi } from '@/modules/studentAffairs/api/dormReliability.api'
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
    AppSectionCard, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker, DataTable
  },
  data() {
    return {
      bedColumns: BED_COLUMNS,
      loading: true, actioning: false, errorMessage: '', config: {}, buildings: [], curBuilding: '',
      rooms: [], curRoom: '', beds: [],
      inDlg: { visible: false, bedId: '', bedLabel: '', studentId: '', error: '' },
      outDlg: { visible: false, bedId: '', who: '', version: null },
      modeDlg: { visible: false }
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
      } catch (e) { this.errorMessage = e.message || '加载失败' } finally { this.loading = false }
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
        who: bd.occupantName || `${bd.bedNo} 号床`, version: bd.version
      }
    },
    async submitCheckout() {
      this.actioning = true; this.errorMessage = ''
      try {
        await dormReliabilityApi.checkout(this.outDlg.bedId, this.outDlg.version)
        await this.loadRooms2()
        this.outDlg.visible = false
      } catch (e) {
        this.errorMessage = e.message || '退宿失败'
        await this.loadBeds().catch(() => {})
        const latest = this.beds.find((x) => String(x.bedId) === String(this.outDlg.bedId))
        if (latest) this.outDlg.version = latest.version
      } finally {
        this.actioning = false
      }
    },
    toggleSelfSelect() { this.modeDlg.visible = true },
    async submitToggle() {
      const next = !this.config.selfSelectEnabled
      this.actioning = true; this.errorMessage = ''
      try {
        this.config = (await studentAffairsApi.setDormSelfSelect(next)).data
        await this.load()
        this.modeDlg.visible = false
      } catch (e) { this.errorMessage = e.message } finally { this.actioning = false }
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
@media (max-width: 720px) { .sa-mode-card { grid-template-columns: 1fr; } .sa-pick { width: 100%; flex-basis: 100%; } }
@import '@/styles/module-page.css';
</style>
