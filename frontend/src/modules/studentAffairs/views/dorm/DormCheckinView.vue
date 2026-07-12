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
          <select v-model="curBuilding" @change="loadRooms">
            <option value="">选择楼栋</option>
            <option v-for="b in buildings" :key="b.buildingId" :value="b.buildingId">{{ b.buildingName }}（空床 {{ b.vacantBeds }}）</option>
          </select>
          <select v-model="curRoom" @change="loadBeds" :disabled="!curBuilding">
            <option value="">选择房间</option>
            <option v-for="r in rooms" :key="r.roomId" :value="r.roomId">{{ r.roomNo }}（空 {{ r.vacantBeds }}）</option>
          </select>
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
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormCheckinView',
  components: { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag },
  data() {
    return { loading: true, actioning: false, errorMessage: '', config: {}, buildings: [], curBuilding: '', rooms: [], curRoom: '', beds: [] }
  },
  computed: { pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') } },
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
    async checkin(bd) {
      const sid = window.prompt('请输入入住学生 ID', '')
      if (!sid) return
      await this.runAction(() => studentAffairsApi.dormCheckin(bd.bedId, sid.trim()))
    },
    async checkout(bd) {
      if (!window.confirm(`确认为 ${bd.occupantName || bd.bedNo} 办理退宿？`)) return
      await this.runAction(() => studentAffairsApi.dormCheckout(bd.bedId))
    },
    async toggleSelfSelect() {
      const next = !this.config.selfSelectEnabled
      if (!window.confirm(next ? '确认开放学生自选宿舍？' : '确认关闭学生自选、改回统一分配？')) return
      this.actioning = true
      try { this.config = (await studentAffairsApi.setDormSelfSelect(next)).data; await this.load() }
      catch (e) { this.errorMessage = e.message } finally { this.actioning = false }
    },
    async runAction(fn) {
      this.actioning = true
      try { await fn(); await this.loadBeds(); await this.loadRooms2() }
      catch (e) { this.errorMessage = e.message || '操作失败' } finally { this.actioning = false }
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
