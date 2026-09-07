<template>
  <ModulePageShell flat
    title="房源管理"
    subtitle="楼栋、房间与床位维护"
    role-name="学工处 / 宿管"
    data-scope-name="宿管限负责楼栋（DORM_BUILDING）"
    watermark-purpose="宿舍房源管理"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" variant="secondary" :loading="actioning" @click="downloadTemplate">
        下载房源模板
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" variant="secondary" :loading="actioning" @click="$refs.resourceFile.click()">
        导入房源
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.export')" code="studentAffairs.dorm.export" variant="secondary" :loading="actioning" @click="exportDlg.visible = true">
        导出房源台账
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="createBuilding">
        新建楼栋
      </AppPermissionButton>
      <input ref="resourceFile" class="dorm-file-input" type="file" accept=".xlsx" @change="onResourceFile" />
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载房源台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">



      <div class="rv-summary" aria-label="房源概况">
        <span>楼栋 <strong>{{ buildings.length }}</strong></span>
        <span>总床位 <strong>{{ occ.totalBeds ?? '—' }}</strong></span>
        <span>已入住 <strong>{{ occ.occupiedBeds ?? '—' }}</strong></span>
        <span>空床 <strong>{{ occ.vacantBeds ?? '—' }}</strong></span>
        <AppButton size="sm" variant="ghost" @click="load">刷新房态</AppButton>
        <AppButton size="sm" variant="ghost" @click="$router.push('/admin/student-affairs/dorm/allocation')">分配计划</AppButton>
      </div>
      <p v-if="successMessage" class="rv-feedback" role="status">{{ successMessage }}</p>
      <AppInlineAlert v-if="selectionError" type="danger" :description="selectionError" />
      <div class="rv-workspace">
        <aside class="rv-buildings" aria-label="选择楼栋">
          <h2>楼栋 <small>{{ buildings.length }}</small></h2>
          <input v-model.trim="buildingSearch" class="rv-input" type="search" aria-label="搜索楼栋" placeholder="搜索楼栋" />
          <div class="rv-building-list">
            <button v-for="building in visibleBuildings" :key="building.buildingId" type="button" class="rv-building"
                    :class="{ 'is-selected': String(curBuilding) === String(building.buildingId) }"
                    :aria-pressed="String(curBuilding) === String(building.buildingId)" @click="openBuilding(building)">
              <strong>{{ building.buildingName }}</strong>
              <span>{{ genderLabel(building.genderLimit) }} · 空 {{ building.vacantBeds }} / {{ building.totalBeds }}</span>
            </button>
            <p v-if="!visibleBuildings.length" class="rv-empty">{{ buildings.length ? '没有匹配的楼栋' : '暂无楼栋，请先新建或导入房源。' }}</p>
          </div>
        </aside>
        <section class="rv-rooms" aria-label="选择房间" :aria-busy="roomsLoading">
          <div class="rv-heading"><h2>{{ curBuildingName || '房间' }}</h2>
            <AppPermissionButton v-if="selectedBuilding" :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" size="sm" variant="ghost" @click="generate(selectedBuilding)">批量铺床</AppPermissionButton>
          </div>
          <div class="rv-filters">
            <input v-model.trim="roomSearch" class="rv-input" type="search" aria-label="搜索房号" placeholder="搜索房号" />
            <select v-model="floorFilter" class="rv-input" aria-label="筛选楼层"><option value="">全部楼层</option><option v-for="floor in floors" :key="floor" :value="String(floor)">{{ floor }} 层</option></select>
            <label><input v-model="vacantOnly" type="checkbox" /> 只看有空床</label>
          </div>
          <p v-if="roomsLoading" class="rv-empty" role="status">正在加载房间…</p>
          <div v-else class="rv-floor-list">
            <section v-for="group in roomGroups" :key="group.floor" class="rv-floor">
              <h3>{{ group.floor }} 层 <small>{{ group.rooms.length }} 间</small></h3>
              <div class="rv-room-grid">
                <button v-for="room in group.rooms" :key="room.roomId" type="button" class="rv-room"
                        :class="{ 'is-selected': String(curRoom) === String(room.roomId), 'has-vacancy': room.vacantBeds > 0 && room.status === 'ENABLED' }"
                        :aria-pressed="String(curRoom) === String(room.roomId)" @click="openRoom(room)">
                  <strong>{{ room.roomNo }}</strong><span>{{ room.status === 'ENABLED' ? `空 ${room.vacantBeds} / ${room.capacity}` : roomStatusLabel(room.status) }}</span>
                </button>
              </div>
            </section>
            <p v-if="!roomGroups.length" class="rv-empty">{{ rooms.length ? '没有符合筛选条件的房间' : '暂无房间，可通过批量铺床建立房源。' }}</p>
            <AppButton v-if="rooms.length && !roomGroups.length" variant="ghost" size="sm" @click="clearRoomFilters">清除筛选</AppButton>
          </div>
        </section>
        <section class="rv-beds" aria-label="床位与入住" :aria-busy="bedsLoading">
          <h2>{{ curRoomNo ? `${curRoomNo} · 床位` : '床位' }}</h2>
          <p v-if="selectedRoom" class="rv-room-info">{{ selectedRoom.floorNo }} 层 · {{ roomStatusLabel(selectedRoom.status) }} · 已住 {{ roomOccupiedBeds }} · 容量 {{ selectedRoom.capacity }}</p>
          <p v-if="selectedRoom && !bedsLoading && beds.length < selectedRoom.capacity" class="rv-room-info">已配置 {{ beds.length }} 个床位，尚有 {{ selectedRoom.capacity - beds.length }} 个未建床位，不计为空床。</p>
          <div class="rv-legend"><span>空床可入住</span><span>已住看详情</span><span>预留 / 锁定</span></div>
          <p v-if="bedsLoading" class="rv-empty" role="status">正在加载床位…</p>
          <div v-else class="rv-bed-grid">
            <button v-for="bed in beds" :key="bed.bedId" type="button" class="rv-bed"
                    :class="{ 'is-vacant': bed.status === 'VACANT', 'is-occupied': bed.status === 'OCCUPIED', 'is-selected': String(selectedBedId) === String(bed.bedId) }"
                    :aria-pressed="String(selectedBedId) === String(bed.bedId)" @click="openBedAction(bed)">
              <strong>{{ bed.bedNo }} 号床</strong>
              <span>{{ bed.status === 'OCCUPIED' ? (bed.occupantName || '已入住') : bedStatusLabel(bed.status) }}</span>
              <small>{{ bed.status === 'VACANT' ? (selectedRoom?.status === 'ENABLED' && canBtn('studentAffairs.dorm.allocation.manage') ? '点击办理入住' : '仅查看') : '查看详情' }}</small>
            </button>
          </div>
          <p v-if="!bedsLoading && !beds.length" class="rv-empty">{{ curRoom ? '该房间尚未配置床位' : '选择房间查看床位' }}</p>
          <p class="rv-footnote">按床号展示，非实际房间平面图。</p>
        </section>
      </div>
    </AppGlobalState>

    <AppConfirmDialog v-model:visible="inDlg.visible" :title="`办理入住 · ${inDlg.label}`" type="primary" confirm-text="确认入住" :submitting="actioning" @confirm="submitVisualCheckin">
      <AppFormItem label="入住学生" required><AppStudentPicker v-model="inDlg.studentId" placeholder="按姓名 / 学号搜索" :disabled="actioning" /></AppFormItem>
      <p class="dr-hint">已有住宿的学生请办理调宿；入住成功后房态自动更新。</p>
      <AppInlineAlert v-if="inDlg.error" type="danger" :description="inDlg.error" />
    </AppConfirmDialog>
    <AppDrawer :visible="bedDlg.visible" title="床位详情" size="medium" @close="bedDlg.visible = false">
      <template v-if="bedDlg.bed">
        <h3>{{ bedDlg.label }}</h3>
        <p>{{ bedStatusLabel(bedDlg.bed.status) }}</p>
        <p v-if="bedDlg.bed.occupantName">入住学生：{{ bedDlg.bed.occupantName }}</p>
        <p v-if="bedDlg.bed.occupiedAt">入住时间：{{ new Date(bedDlg.bed.occupiedAt).toLocaleString('zh-CN') }}</p>
        <p v-if="bedDlg.bed.status === 'LOCKED'">该床位已预留或锁定。按分配计划核对学生后办理，不可作为普通空床分配。</p>
      </template>
      <template #footer>
        <AppButton variant="ghost" @click="bedDlg.visible = false">关闭</AppButton>
        <AppButton v-if="bedDlg.bed?.status === 'LOCKED'" variant="secondary" @click="$router.push('/admin/student-affairs/dorm/allocation')">查看分配计划</AppButton>
        <AppButton v-if="bedDlg.bed && ['OCCUPIED', 'LOCKED'].includes(bedDlg.bed.status)" @click="goBedOperations(bedDlg.bed)">{{ bedDlg.bed.status === 'OCCUPIED' ? '入住记录 / 办理退宿' : '核对预留入住' }}</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="buildDlg.visible" title="新增楼栋" mode="modal" size="large" @close="buildDlg.visible = false">
      <div class="dr-form dr-building-form">
        <fieldset class="sa-form-section">
          <legend>楼栋信息</legend>
          <div class="sa-form-columns">
        <AppFormItem label="楼栋名称" required>
          <AppTextInput v-model="buildDlg.name" placeholder="如：1 号楼 / 西苑 3 栋" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="性别限制" required>
          <AppSelect v-model="buildDlg.gender" :options="GENDER_LIMITS" :disabled="actioning" />
        </AppFormItem>
          </div>
        <AppFormItem label="负责宿管" required>
          <AppTeacherPicker
            v-model="buildDlg.managerTeacherKey"
            :query="{ roleCode: 'DORM_MANAGER' }"
            placeholder="选择负责宿管"
            data-scope-hint="仅显示已分配宿管角色的在职人员"
            :disabled="actioning"
          />
        </AppFormItem>
        <p class="dr-hint">负责宿管接收调宿审核和宿舍待办。</p>
        </fieldset>
        <fieldset class="sa-form-section">
          <legend>房间与床位</legend>
        <label class="dr-check" :class="{ 'is-on': buildDlg.autoFill }">
          <input v-model="buildDlg.autoFill" type="checkbox" :disabled="actioning" />
          <span><strong>同时创建房间和床位</strong><small>已有固定房号可先建楼栋，再用房源模板导入。</small></span>
        </label>
        <template v-if="buildDlg.autoFill">
          <div class="sa-form-columns sa-form-columns--three">
          <AppFormItem label="层数" required><AppNumberInput v-model="buildDlg.floors" :min="1" :max="50" :disabled="actioning" /></AppFormItem>
          <AppFormItem label="每层房数" required><AppNumberInput v-model="buildDlg.roomsPerFloor" :min="1" :max="100" :disabled="actioning" /></AppFormItem>
          <AppFormItem label="每间床位" required><AppNumberInput v-model="buildDlg.bedsPerRoom" :min="1" :max="12" :disabled="actioning" /></AppFormItem>
          </div>
          <p class="sa-form-receipt">预计创建 <strong>{{ buildDlg.floors * buildDlg.roomsPerFloor }}</strong> 间房 · <strong>{{ buildDlg.floors * buildDlg.roomsPerFloor * buildDlg.bedsPerRoom }}</strong> 个床位</p>
        </template>
        </fieldset>
        <AppInlineAlert v-if="buildDlg.error" type="danger" :description="buildDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="buildDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitBuilding">创建楼栋</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="genDlg.visible" :title="`一键铺满 · ${genDlg.buildingName}`" mode="modal" size="medium" @close="genDlg.visible = false">
      <div class="dr-form">
        <p class="dorm-form-note">核对层数、房数和床位后创建。</p>
        <AppFormItem label="层数" required><AppNumberInput v-model="genDlg.floors" :min="1" :max="50" :disabled="actioning" /></AppFormItem>
        <AppFormItem label="每层房数" required><AppNumberInput v-model="genDlg.roomsPerFloor" :min="1" :max="100" :disabled="actioning" /></AppFormItem>
        <AppFormItem label="每间床位" required><AppNumberInput v-model="genDlg.bedsPerRoom" :min="1" :max="12" :disabled="actioning" /></AppFormItem>
        <p class="dr-hint">预计生成 {{ genDlg.floors * genDlg.roomsPerFloor }} 间房、{{ genDlg.floors * genDlg.roomsPerFloor * genDlg.bedsPerRoom }} 个床位。</p>
        <AppInlineAlert v-if="genDlg.error" type="danger" :description="genDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="genDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitGenerate">创建房间和床位</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="importConfirmVisible"
      title="确认导入宿舍房源"
      :message="importPreview ? `预检通过 ${importPreview.okRows} 行。确认后创建对应楼栋、房间和床位。` : ''"
      confirm-text="确认写入房源"
      :submitting="actioning"
      @confirm="confirmResourceImport"
    />

    <AppDrawer :visible="exportDlg.visible" title="导出房源台账" mode="modal" size="medium" @close="exportDlg.visible = false">
      <div class="dr-form">
        <div class="dorm-form-note">导出只包含当前账号楼栋数据范围，文件带操作人、用途、时间水印并写入审计。</div>
        <AppFormItem label="导出用途" required>
          <AppTextInput v-model="exportDlg.purpose" placeholder="例如：2026年秋季宿舍房源核对" :disabled="actioning" />
        </AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="exportDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :disabled="exportDlg.purpose.trim().length < 5" :loading="actioning" @click="exportResources">生成并下载</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput,
  AppPermissionButton, AppStudentPicker, AppSelect, AppTeacherPicker, AppTextInput } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { ModulePageShell } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const GENDER_LIMITS = [
  { value: 'MIXED', label: '混合' },
  { value: 'MALE', label: '男寝' },
  { value: 'FEMALE', label: '女寝' }
]

export default {
  name: 'DormResourceView',
  props: { ctx: { type: Object, default: null } },
  components: { AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert,
    AppNumberInput, AppPermissionButton, AppStudentPicker, AppSelect, AppTeacherPicker, AppTextInput, ModulePageShell },
  data() {
    return {
      GENDER_LIMITS,
      buildingSearch: '', roomSearch: '', floorFilter: '', vacantOnly: false,
      roomsLoading: false, bedsLoading: false, roomRequest: 0, bedRequest: 0,
      selectionError: '', successMessage: '', selectedBedId: '',
      inDlg: { visible: false, bedId: '', label: '', studentId: '', error: '' },
      bedDlg: { visible: false, bed: null, label: '' },
      loading: true, actioning: false, errorMessage: '', buildings: [], occ: {},
      curBuilding: '', curBuildingName: '', rooms: [], curRoom: '', curRoomNo: '', beds: [],
      buildDlg: { visible: false, name: '', gender: 'MIXED', managerTeacherKey: '', autoFill: false, floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' },
      genDlg: { visible: false, buildingId: '', buildingName: '', floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' },
      importConfirmVisible: false, importPreview: null,
      exportDlg: { visible: false, purpose: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'b', label: '楼栋数', value: this.buildings.length, accent: 'primary' },
        { key: 't', label: '总床位', value: this.occ.totalBeds || 0, accent: 'primary' },
        { key: 'o', label: '已住', value: this.occ.occupiedBeds || 0, accent: 'primary' },
        { key: 'v', label: '空床', value: this.occ.vacantBeds || 0, accent: (this.occ.vacantBeds || 0) ? 'success' : 'warning' }
      ]
    },
    selectedBuilding() { return this.buildings.find(b => String(b.buildingId) === String(this.curBuilding)) },
    visibleBuildings() { return this.buildings.filter(b => `${b.buildingName} ${b.buildingCode || ''}`.toLowerCase().includes(this.buildingSearch.toLowerCase())) },
    floors() { return [...new Set(this.rooms.map(r => r.floorNo))].sort((a, b) => a - b) },
    roomGroups() {
      return this.floors.filter(f => !this.floorFilter || String(f) === this.floorFilter).map(floor => ({
        floor, rooms: this.rooms.filter(r => r.floorNo === floor && String(r.roomNo).toLowerCase().includes(this.roomSearch.toLowerCase()) && (!this.vacantOnly || (r.vacantBeds > 0 && r.status === 'ENABLED')))
      })).filter(g => g.rooms.length)
    },
    selectedRoom() {
      return this.rooms.find((row) => String(row.roomId) === String(this.curRoom)) || null
    },
    roomOccupiedBeds() {
      return this.beds.filter((bed) => bed.status === 'OCCUPIED').length
    }
  },
  mounted() { this.load() },
  watch: { '$route.query': { handler() { this.curBuilding = ''; this.curRoom = ''; this.load() } } },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async downloadTemplate() {
      this.actioning = true
      try { await studentAffairsApi.downloadDormResourceTemplate() }
      catch (e) { this.errorMessage = e.message || '模板下载失败' }
      finally { this.actioning = false }
    },
    async onResourceFile(event) {
      const file = event.target.files?.[0]
      event.target.value = ''
      if (!file) return
      this.actioning = true; this.errorMessage = ''
      try {
        const result = await studentAffairsApi.validateDormResourceFile(file)
        this.importPreview = result.data
        if (result.data.status === 'DRY_RUN_PASSED' && result.data.okRows > 0) {
          this.importConfirmVisible = true
        } else {
          this.errorMessage = `Dry Run 未通过：${result.data.errorRows || 0} 项错误，已下载错误工作簿。`
          if (result.data.batchNo) await studentAffairsApi.downloadDormImportErrors(result.data.batchNo)
        }
      } catch (e) { this.errorMessage = e.message || '房源预检失败' }
      finally { this.actioning = false }
    },
    async confirmResourceImport() {
      if (!this.importPreview?.batchNo) return
      this.actioning = true
      try {
        await studentAffairsApi.confirmDormResourceImport(this.importPreview.batchNo)
        this.importConfirmVisible = false; this.importPreview = null
        await this.load()
      } catch (e) { this.errorMessage = e.message || '房源导入失败' }
      finally { this.actioning = false }
    },
    async exportResources() {
      this.actioning = true
      try {
        await studentAffairsApi.exportDormLedger('resources', this.exportDlg.purpose.trim())
        this.exportDlg.visible = false; this.exportDlg.purpose = ''
      } catch (e) { this.errorMessage = e.message || '房源台账导出失败' }
      finally { this.actioning = false }
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const [bs, oc] = await Promise.all([studentAffairsApi.listAllDormBuildings(), studentAffairsApi.getDormOccupancy()])
        this.buildings = bs.data.items || []; this.occ = oc.data || {}
        await this.applyRouteSelection()
      } catch (e) { this.errorMessage = e.message || '房源加载失败' } finally { this.loading = false }
    },
    async applyRouteSelection() {
      const buildingId = String(this.curBuilding || this.$route.query.buildingId || '')
      const roomId = String(this.curRoom || this.$route.query.roomId || '')
      const building = this.buildings.find(row => String(row.buildingId) === buildingId) || this.buildings[0]
      if (!building) return
      await this.openBuilding(building, roomId)
      this.selectedBedId = String(this.$route.query.bedId || '')
    },
    clearRoomFilters() { this.roomSearch = ''; this.floorFilter = ''; this.vacantOnly = false },
    async openBuilding(b, preferredRoom = '') {
      const request = ++this.roomRequest
      ++this.bedRequest
      this.curBuilding = b.buildingId; this.curBuildingName = b.buildingName
      this.curRoom = ''; this.curRoomNo = ''; this.rooms = []; this.beds = []; this.bedsLoading = false
      this.selectionError = ''; this.clearRoomFilters(); this.roomsLoading = true
      try {
        const result = await studentAffairsApi.listAllDormRooms(b.buildingId)
        if (request !== this.roomRequest) return
        this.rooms = result.data.items || []
        const room = this.rooms.find(r => String(r.roomId) === String(preferredRoom)) || this.rooms[0]
        if (room) await this.openRoom(room)
      } catch (e) { if (request === this.roomRequest) this.selectionError = e.message || '房间加载失败，请刷新重试' }
      finally { if (request === this.roomRequest) this.roomsLoading = false }
    },
    async openRoom(r) {
      const request = ++this.bedRequest
      this.curRoom = r.roomId; this.curRoomNo = r.roomNo; this.beds = []; this.selectedBedId = ''
      this.selectionError = ''; this.bedsLoading = true
      try {
        const result = await studentAffairsApi.listDormBeds(r.roomId)
        if (request === this.bedRequest) this.beds = result.data.items || []
      } catch (e) { if (request === this.bedRequest) this.selectionError = e.message || '床位加载失败，请刷新重试' }
      finally { if (request === this.bedRequest) this.bedsLoading = false }
    },
    bedStatusLabel(status) { return ({ VACANT: '空床', OCCUPIED: '已入住', LOCKED: '预留 / 锁定' })[status] || '状态待核查' },
    openBedAction(bed) {
      this.selectedBedId = String(bed.bedId)
      const label = `${this.curBuildingName} / ${this.curRoomNo} / ${bed.bedNo} 号床`
      if (bed.status === 'VACANT' && this.selectedRoom?.status === 'ENABLED' && this.canBtn('studentAffairs.dorm.allocation.manage')) {
        this.inDlg = { visible: true, bedId: bed.bedId, label, studentId: '', error: '' }
      } else { this.bedDlg = { visible: true, bed, label } }
    },
    async submitVisualCheckin() {
      const d = this.inDlg
      if (this.actioning || !this.canBtn('studentAffairs.dorm.allocation.manage')) return
      if (!d.studentId) { d.error = '请选择入住学生'; return }
      this.actioning = true; d.error = ''; this.successMessage = ''
      try {
        await studentAffairsApi.dormCheckin(d.bedId, d.studentId)
        d.visible = false
        this.successMessage = `${d.label} 入住已完成`
        await this.load()
      } catch (e) {
        d.error = e.message || '入住失败，请核对学生与床位状态'
        if (this.selectedRoom) await this.openRoom(this.selectedRoom)
      } finally { this.actioning = false }
    },
    goBedOperations(bed) {
      this.$router.push({ name: 'student-affairs-dorm-checkin', query: {
        buildingId: String(this.curBuilding), roomId: String(this.curRoom), bedId: String(bed.bedId)
      } })
    },
    createBuilding() {
      this.buildDlg = { visible: true, name: '', gender: 'MIXED', managerTeacherKey: '', autoFill: false,
        floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' }
    },
    async submitBuilding() {
      const d = this.buildDlg
      if (!d.name.trim()) { d.error = '请填写楼栋名称'; return }
      if (!d.managerTeacherKey) { d.error = '请选择负责宿管'; return }
      const body = { buildingName: d.name.trim(), genderLimit: d.gender, managerTeacherKey: String(d.managerTeacherKey) }
      if (d.autoFill) {
        if (!(d.floors > 0 && d.roomsPerFloor > 0 && d.bedsPerRoom > 0)) {
          d.error = '一键铺满时，层数 / 每层房数 / 每间床位均须大于 0'
          return
        }
        Object.assign(body, { floors: d.floors, roomsPerFloor: d.roomsPerFloor, bedsPerRoom: d.bedsPerRoom })
      }
      d.error = ''
      if (await this.runAction(() => studentAffairsApi.createDormBuilding(body))) d.visible = false
    },
    generate(b) {
      this.genDlg = { visible: true, buildingId: b.buildingId, buildingName: b.buildingName || '',
        floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' }
    },
    async submitGenerate() {
      const d = this.genDlg
      if (!(d.floors > 0 && d.roomsPerFloor > 0 && d.bedsPerRoom > 0)) {
        d.error = '层数 / 每层房数 / 每间床位均须大于 0'
        return
      }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.generateDormLayout(d.buildingId, {
        floors: d.floors, roomsPerFloor: d.roomsPerFloor, bedsPerRoom: d.bedsPerRoom
      }))
      if (ok) d.visible = false
    },
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try { await fn(); await this.load(); return true }
      catch (e) { this.errorMessage = e.message || '操作失败'; return false }
      finally { this.actioning = false }
    },
    genderLabel(g) { return ({ MALE: '男寝', FEMALE: '女寝', MIXED: '混合' })[g] || g },
    /** 房间状态：建房时写入 ENABLED（见 affairs_dorm_service 铺床逻辑）；
     *  未收录取值原样显示，避免后端新增状态时显示成空白 */
    roomStatusLabel(s) { return ({ ENABLED: '启用', DISABLED: '停用', MAINTAIN: '维修中', MAINTENANCE: '维修中' })[s] || (s ? '状态待确认' : '—') }
  }
}
</script>

<style scoped>
.dorm-file-input { display: none; }
.dr-form { display: flex; flex-direction: column; gap: var(--space-3); }
.dorm-form-note { padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.dr-check { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); color: var(--text-secondary); font-size: var(--font-size-sm); }
.dr-check.is-on { border-color: var(--primary-200); background: var(--primary-50); }
.dr-check span { display: grid; gap: 2px; }
.dr-check strong { color: var(--text-primary); }
.dr-check small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.dr-hint { margin: 0; padding: 9px 11px; border-radius: var(--radius-md); background: var(--bg-section); color: var(--text-secondary); font-size: var(--font-size-xs); }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.dorm-resource-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.dorm-room-detail { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-2); margin-bottom: var(--space-3); }
.dorm-room-detail > div { display: grid; gap: 3px; padding: var(--space-3); border-radius: var(--radius-md); background: var(--bg-section); }
.dorm-room-detail span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); justify-content: flex-end; }
:deep(.dt__tr.sa-sel) .dt__td { background: var(--primary-50, var(--bg-subtle)); }
:deep(.dt__tr.sa-sel) .dt__td:first-child { box-shadow: inset 3px 0 0 var(--primary-500); }
.dorm-gender { padding: 2px 7px; border-radius: var(--radius-full); background: var(--bg-section); color: var(--text-secondary); font-size: var(--font-size-xs); }
.dorm-capacity, .dorm-vacant { color: var(--success-700, #15803d); font-variant-numeric: tabular-nums; }
.dorm-full { color: var(--warning-700, #b45309); font-variant-numeric: tabular-nums; }
.bed-legend { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.bed-legend span { display: inline-flex; align-items: center; gap: 5px; }
.bed-legend span::before { content: ''; width: 8px; height: 8px; border-radius: 50%; }
.bed-legend .is-vacant::before { background: var(--success-500, #22c55e); }
.bed-legend .is-occupied::before { background: var(--warning-500, #f59e0b); }
.sa-beds { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: var(--space-2); }
.sa-bed { display: grid; gap: 3px; min-width: 0; padding: 10px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); font: inherit; font-size: var(--font-size-sm); text-align: left; cursor: pointer; }
.sa-bed strong { font-size: var(--font-size-base); }
.sa-bed small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sa-bed__action { margin-top: 4px; font-weight: 600; }
.sa-bed--occ { background: var(--warning-50); color: var(--warning-700); }
.sa-bed--vac { background: var(--success-50); color: var(--success-700); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .sa-grid--metrics, .dorm-room-detail { grid-template-columns: 1fr; } .sa-beds { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@import '@/styles/module-page.css';
</style>

<style scoped>
.rv-summary { display:flex; align-items:center; flex-wrap:wrap; gap:20px; padding:10px 0 14px; border-bottom:1px solid var(--border-light); font-size:13px; color:var(--text-secondary); }
.rv-summary strong { margin-left:6px; font-size:20px; color:var(--text-primary); font-variant-numeric:tabular-nums; }
.rv-workspace { display:grid; grid-template-columns:190px minmax(300px, 1fr) minmax(280px, 340px); min-height:460px; }
.rv-workspace h2 { margin:0; font-size:15px; line-height:34px; color:var(--text-primary); }
.rv-workspace h2 small, .rv-floor h3 small { margin-left:8px; font-weight:400; color:var(--text-secondary); font-size:12px; }
.rv-buildings { padding:12px 16px 0 0; border-right:1px solid var(--border-light); }
.rv-rooms { padding:12px 18px; min-width:0; }
.rv-beds { padding:12px 0 0 18px; border-left:1px solid var(--border-light); min-width:0; }
.rv-input { height:34px; min-width:0; width:100%; padding:0 10px; background:var(--bg-card); border:1px solid var(--border-light); border-radius:5px; color:var(--text-primary); font:inherit; font-size:13px; }
.rv-building-list { margin-top:10px; }
.rv-building { display:flex; flex-direction:column; gap:7px; width:100%; padding:13px 10px; margin-bottom:4px; text-align:left; border:1px solid transparent; border-radius:5px; background:transparent; color:var(--text-primary); cursor:pointer; font:inherit; font-size:13px; }
.rv-building span { color:var(--text-secondary); font-size:12px; }
.rv-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.rv-filters { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:4px 0 12px; font-size:12px; }
.rv-filters input[type=search] { flex:1; min-width:100px; }
.rv-filters select { width:105px; }
.rv-filters label { display:flex; align-items:center; gap:4px; white-space:nowrap; }
.rv-floor h3 { margin:16px 0 9px; font-size:13px; font-weight:600; }
.rv-room-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(100px,1fr)); gap:8px; }
.rv-room, .rv-bed { display:flex; flex-direction:column; align-items:flex-start; gap:9px; padding:12px; border:1px solid var(--border-light); background:var(--bg-card); border-radius:6px; color:var(--text-primary); cursor:pointer; text-align:left; font:inherit; font-size:13px; min-width:0; }
.rv-room span { color:var(--text-secondary); font-size:12px; }
.rv-room.has-vacancy span { color:var(--success-700, #15803d); }
.rv-bed-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.rv-bed { min-height:112px; }
.rv-bed strong, .rv-bed span { overflow-wrap:anywhere; }
.rv-bed.is-vacant { border-color:var(--success-300, #86cbb3); background:var(--success-50, #f0faf5); }
.rv-bed.is-vacant span { color:var(--success-700, #15803d); }
.rv-bed small { font-size:11px; color:var(--text-secondary); margin-top:auto; }
.rv-building.is-selected, .rv-room.is-selected, .rv-bed.is-selected { border-color:var(--primary-500); background:var(--primary-50); box-shadow:inset 3px 0 var(--primary-500); }
.rv-workspace button:hover { border-color:var(--primary-400); }
.rv-workspace button:focus-visible, .rv-input:focus-visible { outline:2px solid var(--primary-500); outline-offset:2px; }
.rv-room-info, .rv-footnote { color:var(--text-secondary); font-size:12px; line-height:1.6; margin:4px 0 14px; }
.rv-footnote { margin-top:18px; }
.rv-legend { display:flex; flex-wrap:wrap; gap:10px; margin:12px 0; font-size:11px; color:var(--text-secondary); }
.rv-empty { padding:24px 0; margin:0; color:var(--text-secondary); font-size:13px; line-height:1.8; }
.rv-feedback { color:var(--success-700, #15803d); font-size:13px; }
@media(min-width:1500px) { .rv-workspace { grid-template-columns:210px minmax(400px,1fr) 380px; } }
@media(max-width:1150px) { .rv-workspace { grid-template-columns:155px minmax(230px,1fr) 240px; }.rv-rooms {padding:12px;}.rv-beds {padding-left:12px;} }
@media(max-width:900px) { .rv-workspace { grid-template-columns:155px minmax(0,1fr); }.rv-beds {grid-column:1 / -1; border-left:0; border-top:1px solid var(--border-light); padding:14px 0;}.rv-bed-grid {grid-template-columns:repeat(auto-fill,minmax(135px,1fr));} }
@media(max-width:600px) { .rv-workspace {display:block;}.rv-buildings {border-right:0; padding-right:0;}.rv-building-list {display:flex; overflow:auto;}.rv-building {min-width:155px;}.rv-rooms {padding:12px 0;} }
</style>
