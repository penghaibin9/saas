<template>
  <AppPageShell
    title="房源管理"
    subtitle="楼栋 → 房间 → 床位 三级台账；建楼可一键铺满整栋。宿管仅见本人负责楼栋。"
    role-name="学工处 / 宿管"
    data-scope-name="宿管限负责楼栋（DORM_BUILDING）"
    watermark-purpose="宿舍房源管理"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="createBuilding">
        新建楼栋（可一键铺床）
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载房源台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前房源结论</span>
          <h2 class="sa-summary-strip__title">{{ buildings.length }} 栋楼、{{ occ.totalBeds || 0 }} 张床位，当前空床 {{ occ.vacantBeds || 0 }} 张</h2>
          <p class="sa-summary-strip__text">先选择楼栋查看房间，再选择房间查看具体床位。新建楼栋或一键铺床前，请核对性别限制、层数、房间数和每间床位数。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="createBuilding">新建楼栋</AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="宿舍房源管理流程">
        <div class="sa-workflow-step" data-step="1"><strong>维护楼栋</strong><br>设置楼名、性别限制和宿管范围</div>
        <div class="sa-workflow-step" data-step="2"><strong>生成房间</strong><br>按层数和每层房数铺设房间</div>
        <div class="sa-workflow-step" data-step="3"><strong>生成床位</strong><br>按每间床位数形成床位台账</div>
        <div class="sa-workflow-step" data-step="4"><strong>核对容量</strong><br>确认空床、入住数和房间状态</div>
      </div>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="一、选择楼栋">
        <p class="dorm-resource-hint">点击“查看房间”进入楼栋下钻；选中行会高亮。空床/总床可帮助判断当前容量。</p>
        <DataTable
          v-if="buildings.length"
          :columns="buildingColumns"
          :rows="buildings"
          row-key="buildingId"
          :row-class="(row) => (row.buildingId === curBuilding ? 'sa-sel' : '')"
        >
          <template #cell-name="{ row }"><span class="mp-cell-main">{{ row.buildingName }}</span></template>
          <template #cell-code="{ row }">{{ row.buildingCode || '—' }}</template>
          <template #cell-gender="{ row }"><span class="dorm-gender">{{ genderLabel(row.genderLimit) }}</span></template>
          <template #cell-floorCount="{ row }">{{ row.floorCount || '—' }}</template>
          <template #cell-beds="{ row }"><strong class="dorm-capacity">{{ row.vacantBeds }}/{{ row.totalBeds }}</strong></template>
          <template #cell-manager="{ row }">{{ row.managerTeacherKey || '未指派' }}</template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openBuilding(row)">查看房间</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.resource.manage')" code="studentAffairs.dorm.resource.manage" size="sm" variant="secondary" :loading="actioning" @click="generate(row)">铺床</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无楼栋。点击右上角“新建楼栋”建立第一栋宿舍资源。</p>
      </AppSectionCard>

      <AppSectionCard v-if="curBuilding" :title="`二、房间 · ${curBuildingName}`">
        <p class="dorm-resource-hint">选择房间查看床位。空床数与容量并列展示，便于快速识别满员房间。</p>
        <DataTable
          v-if="rooms.length"
          :columns="roomColumns"
          :rows="rooms"
          row-key="roomId"
          :row-class="(row) => (row.roomId === curRoom ? 'sa-sel' : '')"
        >
          <template #cell-roomNo="{ row }"><span class="mp-cell-main">{{ row.roomNo }}</span></template>
          <template #cell-floorNo="{ row }">{{ row.floorNo }}</template>
          <template #cell-capacity="{ row }">{{ row.capacity }}</template>
          <template #cell-vacantBeds="{ row }"><strong :class="row.vacantBeds ? 'dorm-vacant' : 'dorm-full'">{{ row.vacantBeds }}</strong></template>
          <template #cell-status="{ row }">{{ row.status }}</template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openRoom(row)">查看床位</AppPermissionButton>
          </template>
        </DataTable>
        <p v-else class="sa-empty">该楼暂无房间。可使用“铺床”按层数、房间数和床位数自动生成。</p>
      </AppSectionCard>

      <AppSectionCard v-if="curRoom" :title="`三、床位 · ${curRoomNo}`">
        <div class="bed-legend"><span class="is-vacant">空床</span><span class="is-occupied">已入住</span></div>
        <div class="sa-beds">
          <span v-for="bd in beds" :key="bd.bedId" class="sa-bed" :class="bd.status === 'OCCUPIED' ? 'sa-bed--occ' : 'sa-bed--vac'">
            <strong>{{ bd.bedNo }}</strong><small>{{ bd.status === 'OCCUPIED' ? (bd.occupantName || '已住') : '空床' }}</small>
          </span>
          <span v-if="!beds.length" class="sa-empty">该房暂无床位。</span>
        </div>
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer :visible="buildDlg.visible" title="新增楼栋" mode="modal" size="large" @close="buildDlg.visible = false">
      <div class="dr-form">
        <div class="dorm-form-note">新建楼栋后可选择一键铺满。提交前请核对性别限制和容量参数，避免生成错误房间结构。</div>
        <AppFormItem label="楼栋名称" required>
          <AppTextInput v-model="buildDlg.name" placeholder="如：1 号楼 / 西苑 3 栋" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="性别限制" required>
          <AppSelect v-model="buildDlg.gender" :options="GENDER_LIMITS" :disabled="actioning" />
        </AppFormItem>
        <label class="dr-check" :class="{ 'is-on': buildDlg.autoFill }">
          <input v-model="buildDlg.autoFill" type="checkbox" :disabled="actioning" />
          <span><strong>一键铺满整栋</strong><small>按层数 × 每层房数 × 每间床位自动建房间与床位</small></span>
        </label>
        <template v-if="buildDlg.autoFill">
          <AppFormItem label="层数" required><AppNumberInput v-model="buildDlg.floors" :min="1" :max="50" :disabled="actioning" /></AppFormItem>
          <AppFormItem label="每层房数" required><AppNumberInput v-model="buildDlg.roomsPerFloor" :min="1" :max="100" :disabled="actioning" /></AppFormItem>
          <AppFormItem label="每间床位" required><AppNumberInput v-model="buildDlg.bedsPerRoom" :min="1" :max="12" :disabled="actioning" /></AppFormItem>
          <p class="dr-hint">预计生成 {{ buildDlg.floors * buildDlg.roomsPerFloor }} 间房、{{ buildDlg.floors * buildDlg.roomsPerFloor * buildDlg.bedsPerRoom }} 个床位。</p>
        </template>
        <AppInlineAlert v-if="buildDlg.error" type="danger" :description="buildDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="buildDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitBuilding">新增</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="genDlg.visible" :title="`一键铺满 · ${genDlg.buildingName}`" mode="modal" size="medium" @close="genDlg.visible = false">
      <div class="dr-form">
        <div class="dorm-form-note">系统将按以下参数批量创建房间和床位。请确认目标楼栋与容量参数无误。</div>
        <AppFormItem label="层数" required><AppNumberInput v-model="genDlg.floors" :min="1" :max="50" :disabled="actioning" /></AppFormItem>
        <AppFormItem label="每层房数" required><AppNumberInput v-model="genDlg.roomsPerFloor" :min="1" :max="100" :disabled="actioning" /></AppFormItem>
        <AppFormItem label="每间床位" required><AppNumberInput v-model="genDlg.bedsPerRoom" :min="1" :max="12" :disabled="actioning" /></AppFormItem>
        <p class="dr-hint">预计生成 {{ genDlg.floors * genDlg.roomsPerFloor }} 间房、{{ genDlg.floors * genDlg.roomsPerFloor * genDlg.bedsPerRoom }} 个床位。</p>
        <AppInlineAlert v-if="genDlg.error" type="danger" :description="genDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="genDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitGenerate">铺满</AppButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput, AppPageShell,
  AppPermissionButton, AppSectionCard, AppSelect, AppTextInput } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const GENDER_LIMITS = [
  { value: 'MIXED', label: '混合' },
  { value: 'MALE', label: '男寝' },
  { value: 'FEMALE', label: '女寝' }
]

const BUILDING_COLUMNS = [
  { key: 'name', title: '楼栋' },
  { key: 'code', title: '编号' },
  { key: 'gender', title: '性别' },
  { key: 'floorCount', title: '层数' },
  { key: 'beds', title: '空床/总床' },
  { key: 'manager', title: '宿管' },
  { key: 'actions', title: '操作', align: 'right', width: '200px' }
]
const ROOM_COLUMNS = [
  { key: 'roomNo', title: '房号' },
  { key: 'floorNo', title: '楼层' },
  { key: 'capacity', title: '床位数' },
  { key: 'vacantBeds', title: '空床' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '', align: 'right', width: '100px' }
]

export default {
  name: 'DormResourceView',
  props: { ctx: { type: Object, default: null } },
  components: { AppButton, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
    AppNumberInput, AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppTextInput, DataTable },
  data() {
    return {
      buildingColumns: BUILDING_COLUMNS,
      roomColumns: ROOM_COLUMNS,
      GENDER_LIMITS,
      loading: true, actioning: false, errorMessage: '', buildings: [], occ: {},
      curBuilding: '', curBuildingName: '', rooms: [], curRoom: '', curRoomNo: '', beds: [],
      buildDlg: { visible: false, name: '', gender: 'MIXED', autoFill: false, floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' },
      genDlg: { visible: false, buildingId: '', buildingName: '', floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' }
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
    canBtn(code) { return canCode(this.ctx, code) },
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
    createBuilding() {
      this.buildDlg = { visible: true, name: '', gender: 'MIXED', autoFill: false,
        floors: 6, roomsPerFloor: 10, bedsPerRoom: 4, error: '' }
    },
    async submitBuilding() {
      const d = this.buildDlg
      if (!d.name.trim()) { d.error = '请填写楼栋名称'; return }
      const body = { buildingName: d.name.trim(), genderLimit: d.gender }
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
    genderLabel(g) { return ({ MALE: '男寝', FEMALE: '女寝', MIXED: '混合' })[g] || g }
  }
}
</script>

<style scoped>
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
.sa-bed { display: grid; gap: 3px; min-width: 0; padding: 10px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.sa-bed strong { font-size: var(--font-size-base); }
.sa-bed small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sa-bed--occ { background: var(--warning-50); color: var(--warning-700); }
.sa-bed--vac { background: var(--success-50); color: var(--success-700); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .sa-grid--metrics { grid-template-columns: 1fr; } .sa-beds { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@import '@/styles/module-page.css';
</style>
