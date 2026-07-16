<template>
  <AppPageShell
    title="入住管理"
    subtitle="按楼→房→床选定空床为学生办理入住，或办理退宿；学校可开关「学生自选宿舍」。"
    role-name="学工处 / 辅导员 / 宿管"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍入住管理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="toggleSelfSelect">
        {{ config.selfSelectEnabled ? '关闭学生自选' : '开放学生自选' }}
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <AppSectionCard title="分配模式">
        <p class="sa-mode">当前：<strong>{{ config.selfSelectEnabled ? '学生自选' : '辅导员/宿管统一分配' }}</strong> · {{ config.studentNotice }}</p>
      </AppSectionCard>

      <AppSectionCard title="选床入住">
        <div class="sa-toolbar">
          <AppSelect v-model="curBuilding" :options="buildingOptions" placeholder="选择楼栋" class="sa-pick" @change="loadRooms" />
          <AppSelect v-model="curRoom" :options="roomOptions" placeholder="选择房间" class="sa-pick"
                     :disabled="!curBuilding" @change="loadBeds" />
        </div>
        <table class="sa-table" v-if="curRoom">
          <thead><tr><th>床号</th><th>状态</th><th>入住学生</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="bd in beds" :key="bd.bedId">
              <td><strong>{{ bd.bedNo }}</strong></td>
              <td><AppStatusTag :type="bd.status === 'OCCUPIED' ? 'warning' : 'success'" :label="bd.status === 'OCCUPIED' ? '已住' : '空床'" /></td>
              <td>{{ bd.occupantName || '—' }}</td>
              <td class="sa-actions">
                <AppPermissionButton v-if="bd.status !== 'OCCUPIED'" code="studentAffairs.dorm.allocation.manage" size="sm" :loading="actioning" @click="checkin(bd)">入住</AppPermissionButton>
                <AppPermissionButton v-else code="studentAffairs.dorm.allocation.manage" size="sm" variant="secondary" :loading="actioning" @click="checkout(bd)">退宿</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!beds.length"><td colspan="4" class="sa-empty">该房暂无床位</td></tr>
          </tbody>
        </table>
        <p v-else class="sa-empty">请先选择楼栋与房间</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 入住：原为「请输入入住学生 ID」原生弹窗，要求老师手打学生内部 ID -->
    <AppConfirmDialog
      v-model:visible="inDlg.visible" :title="`办理入住 · ${inDlg.bedLabel}`" type="primary"
      confirm-text="确认入住" :submitting="actioning" @confirm="submitCheckin"
    >
      <AppFormItem label="入住学生" required>
        <AppStudentPicker v-model="inDlg.studentId" :remote-search="searchStudents"
                          placeholder="按姓名 / 学号搜索" :disabled="actioning" />
      </AppFormItem>
      <AppInlineAlert v-if="inDlg.error" type="danger" :description="inDlg.error" />
    </AppConfirmDialog>

    <!-- 退宿确认：原为 window.confirm -->
    <AppConfirmDialog
      v-model:visible="outDlg.visible" title="办理退宿" type="warning" confirm-text="确认退宿"
      :description="`确认为 ${outDlg.who} 办理退宿？该床位将立即释放为空床。`"
      :submitting="actioning" @confirm="submitCheckout"
    />

    <!-- 自选宿舍开关：全校级策略，原为 window.confirm，看不出影响面 -->
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
  AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormCheckinView',
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker
  },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', config: {}, buildings: [], curBuilding: '',
      rooms: [], curRoom: '', beds: [],
      inDlg: { visible: false, bedId: '', bedLabel: '', studentId: '', error: '' },
      outDlg: { visible: false, bedId: '', who: '' },
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
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
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
      this.outDlg = { visible: true, bedId: bd.bedId, who: bd.occupantName || `${bd.bedNo} 号床` }
    },
    async submitCheckout() {
      const ok = await this.runAction(() => studentAffairsApi.dormCheckout(this.outDlg.bedId))
      if (ok) this.outDlg.visible = false
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
    /** @returns {boolean} 是否成功；失败时保留弹窗与已选内容。 */
    async runAction(fn) {
      this.actioning = true; this.errorMessage = ''
      try { await fn(); await this.loadBeds(); await this.loadRooms2(); return true }
      catch (e) { this.errorMessage = e.message || '操作失败'; return false }
      finally { this.actioning = false }
    },
    async loadRooms2() {
      // 刷新空床数
      const bs = await studentAffairsApi.listDormBuildings(); this.buildings = bs.data.items || []
      if (this.curBuilding) this.rooms = (await studentAffairsApi.listDormRooms(this.curBuilding)).data.items || []
      if (this.curRoom) this.beds = (await studentAffairsApi.listDormBeds(this.curRoom)).data.items || []
    }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.sa-toolbar select { min-width: 200px; border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-surface); padding: var(--space-2) var(--space-3); }
.sa-mode { margin: 0; color: var(--text-secondary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-actions { display: flex; gap: var(--space-2); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
</style>
