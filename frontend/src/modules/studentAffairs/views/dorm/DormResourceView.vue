<template>
  <AppPageShell
    title="房源管理"
    subtitle="楼栋 → 房间 → 床位 三级台账；建楼可一键铺满整栋。宿管仅见本人负责楼栋。"
    role-name="学工处 / 宿管"
    data-scope-name="宿管限负责楼栋（DORM_BUILDING）"
    watermark-purpose="宿舍房源管理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="createBuilding">
        新建楼栋（可一键铺床）
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载房源台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="楼栋列表">
        <table class="sa-table">
          <thead><tr><th>楼栋</th><th>编号</th><th>性别</th><th>层数</th><th>空床/总床</th><th>宿管</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="b in buildings" :key="b.buildingId" :class="{ 'sa-sel': b.buildingId === curBuilding }">
              <td><strong>{{ b.buildingName }}</strong></td>
              <td>{{ b.buildingCode || '—' }}</td>
              <td>{{ genderLabel(b.genderLimit) }}</td>
              <td>{{ b.floorCount || '—' }}</td>
              <td>{{ b.vacantBeds }}/{{ b.totalBeds }}</td>
              <td>{{ b.managerTeacherKey || '未指派' }}</td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openBuilding(b)">查看房间</AppPermissionButton>
                <AppPermissionButton code="studentAffairs.dorm.resource.manage" size="sm" variant="secondary" :loading="actioning" @click="generate(b)">铺床</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!buildings.length"><td colspan="7" class="sa-empty">暂无楼栋，点右上「新建楼栋」</td></tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard v-if="curBuilding" :title="`房间 · ${curBuildingName}`">
        <table class="sa-table">
          <thead><tr><th>房号</th><th>楼层</th><th>床位数</th><th>空床</th><th>状态</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in rooms" :key="r.roomId" :class="{ 'sa-sel': r.roomId === curRoom }">
              <td><strong>{{ r.roomNo }}</strong></td><td>{{ r.floorNo }}</td><td>{{ r.capacity }}</td>
              <td>{{ r.vacantBeds }}</td><td>{{ r.status }}</td>
              <td><AppPermissionButton code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openRoom(r)">床位</AppPermissionButton></td>
            </tr>
            <tr v-if="!rooms.length"><td colspan="6" class="sa-empty">该楼暂无房间，点「铺床」生成</td></tr>
          </tbody>
        </table>
      </AppSectionCard>

      <AppSectionCard v-if="curRoom" :title="`床位 · ${curRoomNo}`">
        <div class="sa-beds">
          <span v-for="bd in beds" :key="bd.bedId" class="sa-bed" :class="bd.status === 'OCCUPIED' ? 'sa-bed--occ' : 'sa-bed--vac'">
            {{ bd.bedNo }} · {{ bd.status === 'OCCUPIED' ? (bd.occupantName || '已住') : '空床' }}
          </span>
          <span v-if="!beds.length" class="sa-empty">该房暂无床位</span>
        </div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormResourceView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', buildings: [], occ: {},
      curBuilding: '', curBuildingName: '', rooms: [], curRoom: '', curRoomNo: '', beds: []
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'b', label: '楼栋数', value: this.buildings.length, accent: 'primary' },
        { key: 't', label: '总床位', value: this.occ.totalBeds || 0, accent: 'info' },
        { key: 'o', label: '已住', value: this.occ.occupiedBeds || 0, accent: 'primary' },
        { key: 'v', label: '空床', value: this.occ.vacantBeds || 0, accent: (this.occ.vacantBeds || 0) ? 'success' : 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const [bs, oc] = await Promise.all([studentAffairsApi.listDormBuildings(), studentAffairsApi.getDormOccupancy()])
        this.buildings = bs.data.items || []; this.occ = oc.data || {}
      } catch (e) { this.errorMessage = e.message || '房源加载失败' } finally { this.loading = false }
    },
    async openBuilding(b) {
      this.curBuilding = b.buildingId; this.curBuildingName = b.buildingName; this.curRoom = ''; this.beds = []
      try { this.rooms = (await studentAffairsApi.listDormRooms(b.buildingId)).data.items || [] }
      catch (e) { this.errorMessage = e.message || '房间加载失败' }
    },
    async openRoom(r) {
      this.curRoom = r.roomId; this.curRoomNo = r.roomNo
      try { this.beds = (await studentAffairsApi.listDormBeds(r.roomId)).data.items || [] }
      catch (e) { this.errorMessage = e.message || '床位加载失败' }
    },
    async createBuilding() {
      const name = window.prompt('楼栋名称', '')
      if (!name) return
      const gender = (window.prompt('性别限制 MALE/FEMALE/MIXED', 'MIXED') || 'MIXED').toUpperCase()
      const body = { buildingName: name.trim(), genderLimit: gender }
      if (window.confirm('是否一键铺满整栋（层数×每层房数×每间床位）？')) {
        body.floors = parseInt(window.prompt('层数', '6') || '0', 10)
        body.roomsPerFloor = parseInt(window.prompt('每层房数', '10') || '0', 10)
        body.bedsPerRoom = parseInt(window.prompt('每间床位', '4') || '0', 10)
      }
      await this.runAction(() => studentAffairsApi.createDormBuilding(body))
    },
    async generate(b) {
      const floors = parseInt(window.prompt('层数', '6') || '0', 10)
      if (!floors) return
      const roomsPerFloor = parseInt(window.prompt('每层房数', '10') || '0', 10)
      const bedsPerRoom = parseInt(window.prompt('每间床位', '4') || '0', 10)
      await this.runAction(() => studentAffairsApi.generateDormLayout(b.buildingId, { floors, roomsPerFloor, bedsPerRoom }))
    },
    async runAction(fn) {
      this.actioning = true
      try { await fn(); await this.load() }
      catch (e) { this.errorMessage = e.message || '操作失败' } finally { this.actioning = false }
    },
    genderLabel(g) { return ({ MALE: '男寝', FEMALE: '女寝', MIXED: '混合' })[g] || g }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-sel { background: var(--primary-50, var(--bg-subtle)); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.sa-beds { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-bed { border: 1px solid var(--border-light); border-radius: var(--radius-base); padding: var(--space-2) var(--space-3); font-size: var(--font-size-sm); }
.sa-bed--occ { background: var(--warning-50); color: var(--warning-700); }
.sa-bed--vac { background: var(--success-50); color: var(--success-700); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
