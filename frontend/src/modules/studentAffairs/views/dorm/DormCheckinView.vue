<template>
  <AppPageShell
    title="入住管理"
    subtitle="按楼→房→床选定空床为学生办理入住，或办理退宿；学校可开关「学生自选宿舍」。"
    role-name="学工处 / 辅导员 / 宿管"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍入住管理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="openToggleSelfSelect">
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
                <AppPermissionButton v-if="bd.status !== 'OCCUPIED'" code="studentAffairs.dorm.allocation.manage" size="sm" :loading="actioning" @click="openCheckin(bd)">入住</AppPermissionButton>
                <AppPermissionButton v-else code="studentAffairs.dorm.allocation.manage" size="sm" variant="secondary" :loading="actioning" @click="openCheckout(bd)">退宿</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!beds.length"><td colspan="4" class="sa-empty">该房暂无床位</td></tr>
          </tbody>
        </table>
        <p v-else class="sa-empty">请先选择楼栋与房间</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 办理入住 -->
    <AppDrawer v-model:visible="checkinDrawer.visible" title="办理入住">
      <div class="sa-form">
        <p class="sa-hint">床位：{{ checkinDrawer.bedNo }}</p>
        <AppFormItem label="入住学生 ID" required :error="checkinDrawer.errors.studentId">
          <AppTextInput v-model="checkinDrawer.form.studentId" placeholder="请输入学生 ID" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="checkinDrawer.errorMessage" type="danger" :description="checkinDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="checkinDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.dorm.allocation.manage" :loading="actioning" @click="submitCheckin">
          确认入住
        </AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 退宿二次确认 -->
    <AppConfirmDialog
      v-model:visible="checkoutConfirm.visible"
      title="办理退宿"
      :message="checkoutConfirm.message"
      type="warning"
      confirm-text="确认退宿"
      :submitting="actioning"
      @confirm="submitCheckout"
    >
      <AppInlineAlert v-if="checkoutConfirm.errorMessage" type="danger" :description="checkoutConfirm.errorMessage" />
    </AppConfirmDialog>

    <!-- 学生自选开关二次确认 -->
    <AppConfirmDialog
      v-model:visible="selfSelectConfirm.visible"
      title="切换分配模式"
      :message="selfSelectConfirm.message"
      type="warning"
      confirm-text="确认切换"
      :submitting="actioning"
      @confirm="submitToggleSelfSelect"
    >
      <AppInlineAlert v-if="selfSelectConfirm.errorMessage" type="danger" :description="selfSelectConfirm.errorMessage" />
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
        AppSectionCard, AppStatusTag, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormCheckinView',
  components: { AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell,
               AppPermissionButton, AppSectionCard, AppStatusTag, AppTextInput },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', config: {}, buildings: [], curBuilding: '', rooms: [], curRoom: '', beds: [],
      checkinDrawer: { visible: false, bedId: '', bedNo: '', form: { studentId: '' }, errors: {}, errorMessage: '' },
      checkoutConfirm: { visible: false, bedId: '', message: '', errorMessage: '' },
      selfSelectConfirm: { visible: false, next: false, message: '', errorMessage: '' }
    }
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
    openCheckin(bd) {
      this.checkinDrawer.bedId = bd.bedId
      this.checkinDrawer.bedNo = bd.bedNo
      this.checkinDrawer.form = { studentId: '' }
      this.checkinDrawer.errors = {}
      this.checkinDrawer.errorMessage = ''
      this.checkinDrawer.visible = true
    },
    async submitCheckin() {
      const { form, errors, bedId } = this.checkinDrawer
      errors.studentId = form.studentId.trim() ? '' : '入住学生 ID 必填'
      if (errors.studentId) return
      this.actioning = true; this.checkinDrawer.errorMessage = ''
      try {
        await studentAffairsApi.dormCheckin(bedId, form.studentId.trim())
        this.checkinDrawer.visible = false
        await this.loadBeds(); await this.loadRooms2()
      } catch (e) { this.checkinDrawer.errorMessage = e.message || '入住失败' }
      finally { this.actioning = false }
    },
    openCheckout(bd) {
      this.checkoutConfirm.bedId = bd.bedId
      this.checkoutConfirm.message = `确认为 ${bd.occupantName || bd.bedNo} 办理退宿？`
      this.checkoutConfirm.errorMessage = ''
      this.checkoutConfirm.visible = true
    },
    async submitCheckout() {
      const { bedId } = this.checkoutConfirm
      this.actioning = true; this.checkoutConfirm.errorMessage = ''
      try {
        await studentAffairsApi.dormCheckout(bedId)
        this.checkoutConfirm.visible = false
        await this.loadBeds(); await this.loadRooms2()
      } catch (e) { this.checkoutConfirm.errorMessage = e.message || '退宿失败' }
      finally { this.actioning = false }
    },
    openToggleSelfSelect() {
      const next = !this.config.selfSelectEnabled
      this.selfSelectConfirm.next = next
      this.selfSelectConfirm.message = next ? '确认开放学生自选宿舍？' : '确认关闭学生自选、改回统一分配？'
      this.selfSelectConfirm.errorMessage = ''
      this.selfSelectConfirm.visible = true
    },
    async submitToggleSelfSelect() {
      this.actioning = true; this.selfSelectConfirm.errorMessage = ''
      try {
        this.config = (await studentAffairsApi.setDormSelfSelect(this.selfSelectConfirm.next)).data
        this.selfSelectConfirm.visible = false
        await this.load()
      } catch (e) { this.selfSelectConfirm.errorMessage = e.message || '切换失败' }
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
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.sa-hint { margin: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.sa-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.sa-btn:hover { border-color: var(--border-dark); }
.sa-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
