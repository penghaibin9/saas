<template>
  <ModulePageShell flat title="宿舍驾驶舱" watermark-purpose="宿舍房态查看">
    <template #actions>
      <AppPermissionButton
        :allowed="canBtn('studentAffairs.dorm.view')"
        code="studentAffairs.dorm.view"
        variant="secondary"
        :loading="loading"
        @click="load"
      >
        刷新房态
      </AppPermissionButton>
      <AppPermissionButton
        :allowed="canBtn('studentAffairs.risk.view')"
        code="studentAffairs.risk.view"
        variant="secondary"
        @click="$router.push('/admin/student-affairs/risk')"
      >
        宿舍风险
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在同步宿舍房态…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <section class="dc-summary" aria-label="宿舍房态总览">
        <div class="dc-health" :class="{ 'is-warning': dormConclusion.type === 'warning' }">
          <span class="dc-health__dot" aria-hidden="true" />
          <div>
            <strong>{{ dormConclusion.label }}</strong>
            <span>{{ dormConclusion.text }}</span>
          </div>
        </div>
        <dl class="dc-metrics">
          <div><dt>总床位</dt><dd>{{ occupancy.totalBeds || 0 }}</dd></div>
          <div><dt>已入住</dt><dd>{{ occupancy.occupiedBeds || 0 }}</dd></div>
          <div><dt>空床</dt><dd>{{ occupancy.vacantBeds || 0 }}</dd></div>
          <div><dt>入住率</dt><dd>{{ rateLabel }}</dd></div>
        </dl>
      </section>

      <nav class="dc-shortcuts" aria-label="宿舍业务快捷入口">
        <button
          v-for="item in operationalEntries"
          :key="item.path"
          type="button"
          :disabled="!canBtn(item.permission)"
          :title="canBtn(item.permission) ? `进入${item.title}` : '当前身份无权限'"
          @click="go(item.path)"
        >
          <span>{{ item.title }}</span><b aria-hidden="true">›</b>
        </button>
      </nav>

      <section class="dc-workspace" aria-label="楼栋房间床位联动工作区">
        <aside class="dc-buildings" aria-label="选择楼栋">
          <header class="dc-pane-head">
            <div><h2>楼栋</h2><span>{{ filteredBuildings.length }} / {{ buildings.length }}</span></div>
          </header>
          <label class="dc-search">
            <span class="sr-only">搜索楼栋</span>
            <input v-model.trim="buildingQuery" type="search" placeholder="搜索楼栋" />
          </label>
          <div class="dc-building-list">
            <button
              v-for="building in filteredBuildings"
              :key="building.buildingId"
              type="button"
              class="dc-building"
              :class="{ 'is-selected': sameId(building.buildingId, selectedBuildingId) }"
              :aria-pressed="sameId(building.buildingId, selectedBuildingId)"
              @click="selectBuilding(building.buildingId)"
            >
              <span class="dc-building__line">
                <strong>{{ building.buildingName }}</strong>
                <small>{{ genderLabel(building.genderLimit) }}</small>
              </span>
              <span class="dc-building__data">空 {{ building.vacantBeds ?? 0 }} · 共 {{ building.totalBeds ?? 0 }}</span>
              <span class="dc-progress" aria-hidden="true">
                <i :style="{ width: `${buildingOccupancyRate(building)}%` }" />
              </span>
            </button>
            <p v-if="!filteredBuildings.length" class="dc-empty">
              {{ buildings.length ? '没有匹配的楼栋' : '暂无可见楼栋' }}
            </p>
          </div>
        </aside>

        <section class="dc-rooms" aria-label="选择房间" :aria-busy="roomsLoading">
          <header class="dc-pane-head dc-pane-head--rooms">
            <div>
              <h2>{{ selectedBuilding?.buildingName || '房间' }}</h2>
              <span v-if="selectedBuilding">{{ genderLabel(selectedBuilding.genderLimit) }} · 空床 {{ selectedBuilding.vacantBeds ?? 0 }}</span>
            </div>
            <button type="button" class="dc-text-link" @click="openSelectedBuildingResource">管理房源</button>
          </header>
          <div class="dc-room-filters">
            <div class="dc-floor-tabs" aria-label="楼层筛选">
              <button type="button" :class="{ 'is-active': selectedFloor === '' }" @click="selectedFloor = ''">全部</button>
              <button
                v-for="floor in floorOptions"
                :key="floor"
                type="button"
                :class="{ 'is-active': String(selectedFloor) === String(floor) }"
                @click="selectedFloor = String(floor)"
              >
                {{ floor }} 层
              </button>
            </div>
            <select v-model="roomFilter" aria-label="筛选房间状态">
              <option value="ALL">全部房间</option>
              <option value="VACANT">有空床</option>
              <option value="FULL">已住满</option>
            </select>
          </div>
          <p v-if="roomsLoading" class="dc-empty" role="status">正在加载房间…</p>
          <div v-else class="dc-floor-list">
            <section v-for="group in roomGroups" :key="group.floor" class="dc-floor">
              <h3><span>{{ group.floor }} 层</span><small>{{ group.rooms.length }} 间</small></h3>
              <div class="dc-room-grid">
                <button
                  v-for="room in group.rooms"
                  :key="room.roomId"
                  type="button"
                  class="dc-room"
                  :class="{
                    'is-selected': sameId(room.roomId, selectedRoomId),
                    'is-full': Number(room.vacantBeds || 0) === 0
                  }"
                  :aria-pressed="sameId(room.roomId, selectedRoomId)"
                  @click="selectRoom(room.roomId)"
                >
                  <strong>{{ room.roomNo }}</strong>
                  <span>{{ Number(room.vacantBeds || 0) > 0 ? `空 ${room.vacantBeds}` : '已满' }}</span>
                  <small>{{ roomOccupiedBeds(room) }}/{{ room.capacity || 0 }}</small>
                </button>
              </div>
            </section>
            <p v-if="!roomGroups.length" class="dc-empty">
              {{ rooms.length ? '当前筛选下没有房间' : '该楼栋暂无房间' }}
            </p>
          </div>
        </section>

        <aside class="dc-beds" aria-label="床位与入住办理" :aria-busy="bedsLoading">
          <header class="dc-pane-head">
            <div>
              <h2>{{ selectedRoom ? `${selectedRoom.roomNo} 房` : '床位' }}</h2>
              <span v-if="selectedRoom">{{ selectedRoom.floorNo }} 层 · 已住 {{ selectedRoomOccupiedBeds }}/{{ selectedRoom.capacity || 0 }}</span>
            </div>
          </header>
          <div class="dc-bed-legend" aria-label="床位状态说明">
            <span><i class="is-vacant" />空床</span>
            <span><i class="is-occupied" />已入住</span>
            <span><i class="is-locked" />预留 / 锁定</span>
          </div>
          <p v-if="bedsLoading" class="dc-empty" role="status">正在加载床位…</p>
          <div v-else class="dc-bed-grid">
            <button
              v-for="bed in beds"
              :key="bed.bedId"
              type="button"
              class="dc-bed"
              :class="`is-${bedVisualState(bed)}`"
              :aria-label="`${bed.bedNo}号床，${bedStatusLabel(bed.status)}，${bed.status === 'VACANT' ? '办理入住' : '查看详情'}`"
              @click="openBedAction(bed)"
            >
              <span class="dc-bed__number">{{ bed.bedNo }} 号床</span>
              <span class="dc-bed__state">{{ bedStatusLabel(bed.status) }}</span>
              <strong>{{ bed.occupantName || (bed.status === 'VACANT' ? '办理入住' : '查看详情') }}</strong>
              <small>{{ bed.status === 'VACANT' ? '选择学生 →' : '住宿记录 →' }}</small>
            </button>
          </div>
          <p v-if="!bedsLoading && !beds.length" class="dc-empty">
            {{ selectedRoom ? '该房间尚未配置床位' : '选择房间查看床位' }}
          </p>
          <button v-if="selectedRoom" type="button" class="dc-bed-footer" @click="openSelectedRoomOperations">
            查看本房入住与退宿记录 <span aria-hidden="true">→</span>
          </button>
        </aside>
      </section>
    </AppGlobalState>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppGlobalState, AppPermissionButton } from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

export default {
  name: 'StudentAffairsDormitoryView',
  props: { ctx: { type: Object, default: null } },
  components: { ModulePageShell, AppGlobalState, AppPermissionButton },
  data() {
    return {
      loading: true,
      roomsLoading: false,
      bedsLoading: false,
      errorMessage: '',
      occupancy: {},
      buildings: [],
      rooms: [],
      beds: [],
      selectedBuildingId: '',
      selectedRoomId: '',
      buildingQuery: '',
      selectedFloor: '',
      roomFilter: 'ALL'
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    rateLabel() {
      return `${Math.round((this.occupancy.occupancyRate || 0) * 100)}%`
    },
    dormConclusion() {
      if (!this.buildings.length) {
        return { type: 'warning', label: '房源未配置', text: '请先建立楼栋、房间和床位' }
      }
      const vacant = Number(this.occupancy.vacantBeds || 0)
      return {
        type: vacant > 0 ? 'success' : 'warning',
        label: vacant > 0 ? '房态正常' : '床位已满',
        text: `当前范围 ${this.buildings.length} 栋 · 数据已同步`
      }
    },
    operationalEntries() {
      return [
        { title: '分配计划', path: '/admin/student-affairs/dorm/allocation', permission: 'studentAffairs.dorm.view' },
        { title: '房源管理', path: '/admin/student-affairs/dorm/resource', permission: 'studentAffairs.dorm.view' },
        { title: '入住管理', path: '/admin/student-affairs/dorm/checkin', permission: 'studentAffairs.dorm.view' },
        { title: '调宿与退宿', path: '/admin/student-affairs/dorm/transfer', permission: 'studentAffairs.dorm.view' },
        { title: '宿舍检查', path: '/admin/student-affairs/dorm/check', permission: 'studentAffairs.dorm.view' },
        { title: '异常处置', path: '/admin/student-affairs/dorm/exception', permission: 'studentAffairs.dorm.view' },
        { title: '宿舍统计', path: '/admin/student-affairs/dorm/stats', permission: 'studentAffairs.dorm.view' }
      ]
    },
    filteredBuildings() {
      const keyword = this.buildingQuery.trim().toLowerCase()
      if (!keyword) return this.buildings
      return this.buildings.filter((building) =>
        String(building.buildingName || '').toLowerCase().includes(keyword)
      )
    },
    selectedBuilding() {
      return this.buildings.find((building) => this.sameId(building.buildingId, this.selectedBuildingId)) || null
    },
    selectedRoom() {
      return this.rooms.find((room) => this.sameId(room.roomId, this.selectedRoomId)) || null
    },
    floorOptions() {
      return [...new Set(this.rooms.map((room) => Number(room.floorNo)).filter(Number.isFinite))].sort((a, b) => a - b)
    },
    filteredRooms() {
      return this.rooms.filter((room) => {
        if (this.selectedFloor !== '' && String(room.floorNo) !== String(this.selectedFloor)) return false
        const vacant = Number(room.vacantBeds || 0)
        if (this.roomFilter === 'VACANT') return vacant > 0
        if (this.roomFilter === 'FULL') return vacant === 0
        return true
      })
    },
    roomGroups() {
      const groups = new Map()
      for (const room of this.filteredRooms) {
        const floor = Number(room.floorNo) || 0
        if (!groups.has(floor)) groups.set(floor, [])
        groups.get(floor).push(room)
      }
      return [...groups.entries()]
        .sort(([a], [b]) => a - b)
        .map(([floor, rooms]) => ({
          floor,
          rooms: rooms.sort((a, b) => String(a.roomNo || '').localeCompare(String(b.roomNo || ''), 'zh-CN', { numeric: true }))
        }))
    },
    selectedRoomOccupiedBeds() {
      return this.selectedRoom ? this.roomOccupiedBeds(this.selectedRoom) : 0
    }
  },
  created() {
    this.load()
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    sameId(left, right) { return String(left ?? '') === String(right ?? '') },
    go(path) { this.$router.push(path) },
    genderLabel(value) {
      return { MALE: '男生', FEMALE: '女生', MIXED: '混合', NONE: '不限' }[String(value || '').toUpperCase()] || '待核对'
    },
    buildingOccupancyRate(building) {
      const total = Number(building.totalBeds || 0)
      if (!total) return 0
      return Math.max(0, Math.min(100, Math.round(((total - Number(building.vacantBeds || 0)) / total) * 100)))
    },
    roomOccupiedBeds(room) {
      return Math.max(0, Number(room.capacity || 0) - Number(room.vacantBeds || 0))
    },
    bedVisualState(bed) {
      if (bed.status === 'VACANT') return 'vacant'
      if (bed.status === 'OCCUPIED') return 'occupied'
      return 'locked'
    },
    bedStatusLabel(status) {
      return {
        VACANT: '空床',
        OCCUPIED: '已入住',
        LOCKED: '已锁定',
        RESERVED: '已预留',
        DISABLED: '已停用',
        MAINTENANCE: '维护中'
      }[status] || '待核对'
    },
    openSelectedBuildingResource() {
      const query = this.selectedBuildingId ? { buildingId: String(this.selectedBuildingId) } : {}
      this.$router.push({ name: 'student-affairs-dorm-resource', query })
    },
    openSelectedRoomOperations() {
      this.$router.push({
        name: 'student-affairs-dorm-checkin',
        query: { buildingId: String(this.selectedBuildingId), roomId: String(this.selectedRoomId) }
      })
    },
    openBedAction(bed) {
      this.$router.push({
        name: 'student-affairs-dorm-checkin',
        query: {
          buildingId: String(this.selectedBuildingId),
          roomId: String(this.selectedRoomId),
          bedId: String(bed.bedId)
        }
      })
    },
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const [occRes, buildingRes] = await Promise.all([
          studentAffairsApi.getDormOccupancy(),
          studentAffairsApi.listDormBuildings({ page: 1, pageSize: 100 })
        ])
        this.occupancy = occRes.data || {}
        this.buildings = buildingRes.data.items || []
        const preferredBuildingId = this.$route.query.buildingId || this.selectedBuildingId
        this.selectedBuildingId = this.buildings.some((item) => this.sameId(item.buildingId, preferredBuildingId))
          ? preferredBuildingId
          : (this.buildings[0]?.buildingId || '')
        await this.loadRooms()
      } catch (error) {
        this.errorMessage = error?.message || '宿舍房态加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadRooms() {
      this.selectedFloor = ''
      this.roomFilter = 'ALL'
      if (!this.selectedBuildingId) {
        this.rooms = []
        this.beds = []
        return
      }
      this.roomsLoading = true
      try {
        const response = await studentAffairsApi.listDormRooms(this.selectedBuildingId, { page: 1, pageSize: 100 })
        this.rooms = response.data.items || []
        const preferredRoomId = this.$route.query.roomId || this.selectedRoomId
        this.selectedRoomId = this.rooms.some((item) => this.sameId(item.roomId, preferredRoomId))
          ? preferredRoomId
          : (this.rooms[0]?.roomId || '')
        await this.loadBeds()
      } finally {
        this.roomsLoading = false
      }
    },
    async loadBeds() {
      if (!this.selectedRoomId) {
        this.beds = []
        return
      }
      this.bedsLoading = true
      try {
        const response = await studentAffairsApi.listDormBeds(this.selectedRoomId)
        this.beds = response.data.items || []
      } finally {
        this.bedsLoading = false
      }
    },
    async selectBuilding(id) {
      if (this.sameId(id, this.selectedBuildingId)) return
      this.selectedBuildingId = id
      this.selectedRoomId = ''
      this.beds = []
      await this.loadRooms()
    },
    async selectRoom(id) {
      if (this.sameId(id, this.selectedRoomId)) return
      this.selectedRoomId = id
      await this.loadBeds()
    }
  }
}
</script>

<style scoped>
.dc-summary {
  display: grid;
  grid-template-columns: minmax(230px, 1.15fr) minmax(500px, 2fr);
  min-height: 58px;
  border-bottom: 1px solid var(--line);
}
.dc-health {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 6px 20px 9px 0;
  border-right: 1px solid var(--line);
}
.dc-health__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--success-500, #16a36a);
  box-shadow: 0 0 0 4px var(--success-50, #ecfdf5);
}
.dc-health.is-warning .dc-health__dot {
  background: var(--warning-500, #d97706);
  box-shadow: 0 0 0 4px var(--warning-50, #fffbeb);
}
.dc-health div { display: grid; gap: 2px; min-width: 0; }
.dc-health strong { color: var(--t1); font-size: 14px; }
.dc-health span:last-child { color: var(--t3); font-size: 11px; }
.dc-metrics { display: grid; grid-template-columns: repeat(4, minmax(100px, 1fr)); margin: 0; }
.dc-metrics div {
  display: grid;
  align-content: center;
  gap: 1px;
  padding: 4px 16px 7px;
  border-right: 1px solid var(--line);
}
.dc-metrics div:last-child { border-right: 0; }
.dc-metrics dt { color: var(--t3); font-size: 11px; }
.dc-metrics dd {
  margin: 0;
  color: var(--t1);
  font-size: 22px;
  font-weight: 700;
  line-height: 27px;
  font-variant-numeric: tabular-nums;
}
.dc-shortcuts {
  display: flex;
  align-items: center;
  min-width: 0;
  overflow-x: auto;
  border-bottom: 1px solid var(--line);
  scrollbar-width: thin;
}
.dc-shortcuts button {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 124px;
  min-height: 38px;
  padding: 6px 12px;
  border: 0;
  border-right: 1px solid var(--line);
  background: transparent;
  color: var(--t2);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.dc-shortcuts button:first-child { padding-left: 0; }
.dc-shortcuts button:hover { color: var(--pri); background: var(--pri-bg); }
.dc-shortcuts button:disabled { color: var(--t3); cursor: not-allowed; opacity: .55; }
.dc-shortcuts b { color: var(--t3); font-size: 17px; font-weight: 400; }
.dc-workspace {
  display: grid;
  grid-template-columns: minmax(190px, 224px) minmax(400px, 1fr) minmax(270px, 310px);
  min-width: 0;
  height: clamp(360px, calc(100dvh - 396px), 600px);
  min-height: 360px;
  border-bottom: 1px solid var(--line);
  background: var(--surface, var(--bg-card));
}
.dc-buildings, .dc-rooms, .dc-beds { min-width: 0; min-height: 0; overflow: hidden; }
.dc-buildings, .dc-beds { display: flex; flex-direction: column; }
.dc-buildings { padding-right: 14px; border-right: 1px solid var(--line); }
.dc-rooms { padding: 0 18px; border-right: 1px solid var(--line); }
.dc-beds { padding-left: 18px; }
.dc-pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 44px;
  padding: 3px 0;
  border-bottom: 1px solid var(--line);
}
.dc-pane-head > div { display: flex; align-items: baseline; gap: 7px; min-width: 0; }
.dc-pane-head h2 { margin: 0; color: var(--t1); font-size: 14px; line-height: 22px; }
.dc-pane-head span { color: var(--t3); font-size: 11px; white-space: nowrap; }
.dc-pane-head--rooms > div { overflow: hidden; }
.dc-pane-head--rooms h2 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-text-link {
  flex: 0 0 auto;
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: var(--pri);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.dc-search { display: block; padding: 8px 0 6px; }
.dc-search input, .dc-room-filters select {
  width: 100%;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--line);
  border-radius: 5px;
  outline: 0;
  background: var(--field-bg, var(--surface));
  color: var(--t1);
  font: inherit;
  font-size: 11px;
}
.dc-search input:focus, .dc-room-filters select:focus { border-color: var(--pri); }
.dc-building-list {
  min-height: 0;
  overflow-y: auto;
  padding: 0 3px 12px 0;
  scrollbar-width: thin;
}
.dc-building {
  position: relative;
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 8px 8px 8px 10px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: var(--t2);
  text-align: left;
  cursor: pointer;
}
.dc-building::before {
  content: '';
  position: absolute;
  inset: 6px auto 6px 0;
  width: 2px;
  border-radius: 2px;
  background: transparent;
}
.dc-building:hover { background: var(--bg-soft, var(--surface-2)); }
.dc-building.is-selected { background: var(--pri-bg); color: var(--t1); }
.dc-building.is-selected::before { background: var(--pri); }
.dc-building__line { display: flex; align-items: center; justify-content: space-between; gap: 7px; }
.dc-building__line strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.dc-building__line small, .dc-building__data { color: var(--t3); font-size: 10px; font-weight: 400; }
.dc-progress { display: block; height: 2px; overflow: hidden; border-radius: 2px; background: var(--line); }
.dc-progress i { display: block; height: 100%; border-radius: inherit; background: var(--pri); }
.dc-room-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.dc-floor-tabs {
  display: flex;
  align-items: center;
  gap: 1px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.dc-floor-tabs::-webkit-scrollbar { display: none; }
.dc-floor-tabs button {
  flex: 0 0 auto;
  min-height: 28px;
  padding: 3px 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--t3);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.dc-floor-tabs button:hover { color: var(--t1); background: var(--bg-soft); }
.dc-floor-tabs button.is-active { color: var(--pri); background: var(--pri-bg); font-weight: 600; }
.dc-floor-list {
  height: calc(100% - 88px);
  overflow-y: auto;
  padding: 2px 3px 12px 0;
  scrollbar-width: thin;
}
.dc-floor { padding: 8px 0 2px; }
.dc-floor h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 6px;
  color: var(--t2);
  font-size: 11px;
  font-weight: 600;
}
.dc-floor h3 small { color: var(--t3); font-weight: 400; }
.dc-room-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(84px, 1fr)); gap: 6px; }
.dc-room {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 3px 6px;
  min-height: 50px;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: transparent;
  color: var(--t2);
  text-align: left;
  cursor: pointer;
}
.dc-room:hover { border-color: var(--pri); }
.dc-room.is-selected { border-color: var(--pri); background: var(--pri-bg); box-shadow: inset 0 0 0 1px var(--pri); }
.dc-room.is-full:not(.is-selected) { background: var(--bg-soft, var(--surface-2)); color: var(--t3); }
.dc-room strong { color: var(--t1); font-size: 12px; }
.dc-room span { color: var(--success-700, #047857); font-size: 10px; }
.dc-room.is-full span { color: var(--t3); }
.dc-room small { grid-column: 1 / -1; color: var(--t3); font-size: 9px; font-variant-numeric: tabular-nums; }
.dc-bed-legend {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 34px;
  border-bottom: 1px solid var(--line);
  color: var(--t3);
  font-size: 10px;
}
.dc-bed-legend span { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.dc-bed-legend i { width: 6px; height: 6px; border-radius: 50%; background: var(--t3); }
.dc-bed-legend i.is-vacant { background: var(--success-500, #16a36a); }
.dc-bed-legend i.is-occupied { background: var(--pri); }
.dc-bed-legend i.is-locked { background: var(--warning-500, #d97706); }
.dc-bed-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-content: start;
  gap: 6px;
  min-height: 0;
  overflow-y: auto;
  padding: 9px 3px 10px 0;
  scrollbar-width: thin;
}
.dc-bed {
  position: relative;
  display: grid;
  gap: 3px;
  min-height: 78px;
  padding: 9px 9px 8px 10px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: transparent;
  color: var(--t2);
  text-align: left;
  cursor: pointer;
}
.dc-bed::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--warning-500, #d97706);
}
.dc-bed.is-vacant::before { background: var(--success-500, #16a36a); }
.dc-bed.is-occupied::before { background: var(--pri); }
.dc-bed:hover { border-color: var(--pri); transform: translateY(-1px); }
.dc-bed__number { color: var(--t3); font-size: 10px; }
.dc-bed__state { position: absolute; top: 8px; right: 8px; color: var(--t3); font-size: 9px; }
.dc-bed.is-vacant .dc-bed__state { color: var(--success-700, #047857); }
.dc-bed.is-occupied .dc-bed__state { color: var(--pri); }
.dc-bed strong { max-width: 100%; overflow: hidden; color: var(--t1); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.dc-bed small { color: var(--t3); font-size: 9px; }
.dc-bed-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 auto;
  width: 100%;
  min-height: 36px;
  padding: 6px 0;
  border: 0;
  border-top: 1px solid var(--line);
  background: transparent;
  color: var(--pri);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.dc-empty { margin: 0; padding: 24px 8px; color: var(--t3); font-size: 11px; text-align: center; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@media (max-width: 1240px) {
  .dc-workspace { grid-template-columns: 190px minmax(350px, 1fr) 260px; }
  .dc-room-grid { grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); }
}
@media (max-width: 1000px) {
  .dc-summary { grid-template-columns: 1fr; }
  .dc-health { border-right: 0; border-bottom: 1px solid var(--line); }
  .dc-workspace { height: auto; grid-template-columns: 190px minmax(0, 1fr); }
  .dc-buildings, .dc-rooms { min-height: 430px; }
  .dc-beds { grid-column: 1 / -1; min-height: 280px; padding: 0; border-top: 1px solid var(--line); }
  .dc-bed-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
}
@media (max-width: 700px) {
  .dc-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dc-metrics div:nth-child(2) { border-right: 0; }
  .dc-metrics div:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
  .dc-shortcuts button { min-width: 110px; }
  .dc-workspace { display: block; }
  .dc-buildings, .dc-rooms, .dc-beds { min-height: 0; max-height: none; padding: 0; border: 0; border-bottom: 1px solid var(--line); }
  .dc-building-list { max-height: 260px; }
  .dc-floor-list { height: auto; max-height: 400px; }
  .dc-room-filters { grid-template-columns: 1fr; }
  .dc-bed-grid { max-height: 380px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
