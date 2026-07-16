<template>
  <AppPageShell
    title="房源管理"
    subtitle="楼栋 → 房间 → 床位 三级台账；建楼可一键铺满整栋。宿管仅见本人负责楼栋。"
    role-name="学工处 / 宿管"
    data-scope-name="宿管限负责楼栋（DORM_BUILDING）"
    watermark-purpose="宿舍房源管理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="openCreateBuilding">
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
                <AppPermissionButton code="studentAffairs.dorm.resource.manage" size="sm" variant="secondary" :loading="actioning" @click="openGenerateLayout(b)">铺床</AppPermissionButton>
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

    <!-- 新建楼栋 -->
    <AppDrawer v-model:visible="buildingDrawer.visible" title="新建楼栋">
      <div class="sa-form">
        <AppFormItem label="楼栋名称" required :error="buildingDrawer.errors.buildingName">
          <AppTextInput v-model="buildingDrawer.form.buildingName" placeholder="如 紫荆1号楼" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="楼栋编号">
          <AppTextInput v-model="buildingDrawer.form.buildingCode" placeholder="如 ZJ01（选填）" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="性别限制">
          <AppSelect v-model="buildingDrawer.form.genderLimit" :options="genderOptions" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="宿管">
          <AppTextInput v-model="buildingDrawer.form.managerTeacherKey" placeholder="宿管工号（选填，可稍后指派）" :disabled="actioning" />
        </AppFormItem>
        <label class="sa-toggle">
          <input v-model="buildingDrawer.form.autoLayout" type="checkbox" :disabled="actioning" />
          一键铺满整栋（自动生成房间与床位）
        </label>
        <template v-if="buildingDrawer.form.autoLayout">
          <div class="sa-layout-grid">
            <AppFormItem label="层数" :error="buildingDrawer.errors.floors">
              <AppNumberInput v-model="buildingDrawer.form.floors" :min="1" :max="50" :disabled="actioning" />
            </AppFormItem>
            <AppFormItem label="每层房数" :error="buildingDrawer.errors.roomsPerFloor">
              <AppNumberInput v-model="buildingDrawer.form.roomsPerFloor" :min="1" :max="100" :disabled="actioning" />
            </AppFormItem>
            <AppFormItem label="每间床位" :error="buildingDrawer.errors.bedsPerRoom">
              <AppNumberInput v-model="buildingDrawer.form.bedsPerRoom" :min="1" :max="20" :disabled="actioning" />
            </AppFormItem>
          </div>
          <p class="sa-hint">将生成 {{ layoutPreviewText }}</p>
        </template>
        <AppInlineAlert v-if="buildingDrawer.errorMessage" type="danger" :description="buildingDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="buildingDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="submitCreateBuilding">
          新建
        </AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 铺床（已有楼栋补充布局） -->
    <AppDrawer v-model:visible="layoutDrawer.visible" :title="`铺床 · ${layoutDrawer.buildingName}`">
      <div class="sa-form">
        <p class="sa-hint">该楼栋当前暂无房间，按层数 × 每层房数 × 每间床位一次性生成。</p>
        <div class="sa-layout-grid">
          <AppFormItem label="层数" :error="layoutDrawer.errors.floors">
            <AppNumberInput v-model="layoutDrawer.form.floors" :min="1" :max="50" :disabled="actioning" />
          </AppFormItem>
          <AppFormItem label="每层房数" :error="layoutDrawer.errors.roomsPerFloor">
            <AppNumberInput v-model="layoutDrawer.form.roomsPerFloor" :min="1" :max="100" :disabled="actioning" />
          </AppFormItem>
          <AppFormItem label="每间床位" :error="layoutDrawer.errors.bedsPerRoom">
            <AppNumberInput v-model="layoutDrawer.form.bedsPerRoom" :min="1" :max="20" :disabled="actioning" />
          </AppFormItem>
        </div>
        <p class="sa-hint">将生成 {{ layoutDrawerPreviewText }}</p>
        <AppInlineAlert v-if="layoutDrawer.errorMessage" type="danger" :description="layoutDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="layoutDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.dorm.resource.manage" :loading="actioning" @click="submitGenerateLayout">
          生成
        </AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppInlineAlert, AppFormItem, AppMetricCard, AppNumberInput,
        AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const GENDER_OPTIONS = [
  { label: '混合', value: 'MIXED' },
  { label: '男寝', value: 'MALE' },
  { label: '女寝', value: 'FEMALE' }
]

function freshBuildingForm() {
  return { buildingName: '', buildingCode: '', genderLimit: 'MIXED', managerTeacherKey: '',
          autoLayout: true, floors: 6, roomsPerFloor: 10, bedsPerRoom: 4 }
}

function freshLayoutForm() {
  return { floors: 6, roomsPerFloor: 10, bedsPerRoom: 4 }
}

export default {
  name: 'DormResourceView',
  components: { AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
               AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppTextInput },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', buildings: [], occ: {},
      curBuilding: '', curBuildingName: '', rooms: [], curRoom: '', curRoomNo: '', beds: [],
      genderOptions: GENDER_OPTIONS,
      buildingDrawer: { visible: false, form: freshBuildingForm(), errors: {}, errorMessage: '' },
      layoutDrawer: { visible: false, buildingId: '', buildingName: '', form: freshLayoutForm(),
                     errors: {}, errorMessage: '' }
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
    },
    layoutPreviewText() { return this._previewText(this.buildingDrawer.form) },
    layoutDrawerPreviewText() { return this._previewText(this.layoutDrawer.form) }
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
    _previewText(f) {
      if (!f.floors || !f.roomsPerFloor || !f.bedsPerRoom) return '—'
      return `${f.floors} 层 × ${f.roomsPerFloor} 间/层 × ${f.bedsPerRoom} 床/间 = ${f.floors * f.roomsPerFloor * f.bedsPerRoom} 张床位`
    },
    _validateLayout(form, errors) {
      let ok = true
      for (const [key, label] of [['floors', '层数'], ['roomsPerFloor', '每层房数'], ['bedsPerRoom', '每间床位']]) {
        const v = form[key]
        if (!Number.isInteger(v) || v < 1) { errors[key] = `${label}须为正整数`; ok = false }
        else { errors[key] = '' }
      }
      return ok
    },
    openCreateBuilding() {
      this.buildingDrawer.form = freshBuildingForm()
      this.buildingDrawer.errors = {}
      this.buildingDrawer.errorMessage = ''
      this.buildingDrawer.visible = true
    },
    async submitCreateBuilding() {
      const { form, errors } = this.buildingDrawer
      errors.buildingName = form.buildingName.trim() ? '' : '楼栋名称必填'
      const layoutOk = form.autoLayout ? this._validateLayout(form, errors) : true
      if (errors.buildingName || !layoutOk) return
      const body = { buildingName: form.buildingName.trim(), buildingCode: form.buildingCode.trim() || undefined,
                    genderLimit: form.genderLimit, managerTeacherKey: form.managerTeacherKey.trim() || undefined }
      if (form.autoLayout) {
        body.floors = form.floors; body.roomsPerFloor = form.roomsPerFloor; body.bedsPerRoom = form.bedsPerRoom
      }
      this.actioning = true; this.buildingDrawer.errorMessage = ''
      try {
        await studentAffairsApi.createDormBuilding(body)
        this.buildingDrawer.visible = false
        await this.load()
      } catch (e) { this.buildingDrawer.errorMessage = e.message || '新建失败' }
      finally { this.actioning = false }
    },
    openGenerateLayout(b) {
      this.layoutDrawer.buildingId = b.buildingId
      this.layoutDrawer.buildingName = b.buildingName
      this.layoutDrawer.form = freshLayoutForm()
      this.layoutDrawer.errors = {}
      this.layoutDrawer.errorMessage = ''
      this.layoutDrawer.visible = true
    },
    async submitGenerateLayout() {
      const { form, errors, buildingId } = this.layoutDrawer
      if (!this._validateLayout(form, errors)) return
      this.actioning = true; this.layoutDrawer.errorMessage = ''
      try {
        await studentAffairsApi.generateDormLayout(buildingId, { ...form })
        this.layoutDrawer.visible = false
        await this.load()
      } catch (e) { this.layoutDrawer.errorMessage = e.message || '铺床失败' }
      finally { this.actioning = false }
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

.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.sa-toggle { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-base); color: var(--text-secondary); cursor: pointer; }
.sa-layout-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); }
.sa-hint { margin: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.sa-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.sa-btn:hover { border-color: var(--border-dark); }
.sa-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 600px) { .sa-layout-grid { grid-template-columns: 1fr; } }
</style>
