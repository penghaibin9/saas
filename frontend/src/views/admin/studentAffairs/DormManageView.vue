<template>
  <ModulePageShell
    title="宿舍管理"
    subtitle="楼栋 / 房间 / 床位台账 · 入住与退宿"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="宿舍管理"
  >
    <div class="dm-toolbar">
      <div v-if="occupancy" class="dm-occ">
        入住率 <b>{{ occRate }}%</b> · 已住 {{ occupancy.occupiedBeds ?? occupancy.occupied ?? '—' }} / 总床位 {{ occupancy.totalBeds ?? occupancy.total ?? '—' }}
      </div>
      <div class="dm-toolbar__btns">
        <button type="button" class="dm-btn" @click="openCheck">宿舍检查</button>
        <button type="button" class="dm-btn dm-btn--primary" @click="openBuilding">建楼栋</button>
      </div>
    </div>

    <div class="dm-workspace">
      <!-- 楼栋 -->
      <div class="dm-col dm-col--buildings">
        <div class="dm-col__head">楼栋<span v-if="buildings.length">{{ buildings.length }}</span></div>
        <LoadingState v-if="loading" text="加载楼栋…" />
        <ErrorState v-else-if="error" :description="error" @retry="loadBuildings" />
        <EmptyState v-else-if="!buildings.length" title="暂无楼栋" description="点「建楼栋」创建并一键铺床" />
        <ul v-else class="dm-blist">
          <li
            v-for="b in buildings"
            :key="b.buildingId"
            class="dm-bitem"
            :class="{ 'is-active': building && building.buildingId === b.buildingId }"
            @click="selectBuilding(b)"
          >
            <div class="dm-bitem__name">{{ b.buildingName }}<span class="dm-gender">{{ genderLabel(b.genderLimit) }}</span></div>
            <div class="dm-bitem__beds">空 {{ b.vacantBeds ?? '—' }} / {{ b.totalBeds ?? '—' }} 床</div>
          </li>
        </ul>
      </div>

      <!-- 房间 -->
      <div class="dm-col dm-col--rooms">
        <div class="dm-col__head">房间</div>
        <EmptyState v-if="!building" title="选择楼栋" description="查看房间与床位" />
        <template v-else>
          <button v-if="!rooms.length && !roomsLoading" type="button" class="dm-btn" @click="openGenerate">一键铺床（房+床）</button>
          <LoadingState v-if="roomsLoading" text="加载房间…" />
          <EmptyState v-else-if="!rooms.length" title="该楼栋暂无房间" description="点「一键铺床」按层数×房数×床位铺满" />
          <div v-else class="dm-rooms">
            <button
              v-for="r in rooms"
              :key="r.roomId"
              type="button"
              class="dm-room"
              :class="{ 'is-active': room && room.roomId === r.roomId, 'is-full': r.vacantBeds === 0 }"
              @click="selectRoom(r)"
            >
              <span class="dm-room__no">{{ r.roomNo || (r.floorNo + '层') }}</span>
              <span class="dm-room__beds">空{{ r.vacantBeds }}</span>
            </button>
          </div>
        </template>
      </div>

      <!-- 床位 -->
      <div class="dm-col dm-col--beds">
        <div class="dm-col__head">床位</div>
        <EmptyState v-if="!room" title="选择房间" description="查看床位并办理入住 / 退宿" />
        <template v-else>
          <LoadingState v-if="bedsLoading" text="加载床位…" />
          <ul v-else class="dm-beds">
            <li v-for="bed in beds" :key="bed.bedId" class="dm-bed">
              <div>
                <span class="dm-bed__no">{{ bed.bedNo }}</span>
                <span class="dm-bed__status" :class="'dm-bed__status--' + bed.status.toLowerCase()">{{ bed.status === 'OCCUPIED' ? '已住' : '空床' }}</span>
                <span v-if="bed.studentId" class="dm-bed__stu">学生#{{ bed.studentId }}</span>
              </div>
              <button v-if="bed.status === 'VACANT'" type="button" class="dm-btn dm-btn--primary dm-btn--sm" :disabled="acting" @click="openCheckin(bed)">入住</button>
              <template v-else>
                <button type="button" class="dm-btn dm-btn--sm" :disabled="acting" @click="openTransfer(bed)">调宿</button>
                <button type="button" class="dm-btn dm-btn--danger dm-btn--sm" :disabled="acting" @click="onCheckout(bed)">退宿</button>
              </template>
            </li>
          </ul>
        </template>
      </div>
    </div>

    <!-- 调宿审批（本会话发起的调宿单） -->
    <section v-if="transfers.length" class="dm-transfers">
      <h3 class="dm-transfers__title">调宿审批</h3>
      <ul class="dm-tlist">
        <li v-for="t in transfers" :key="t.transferId" class="dm-titem">
          <span>学生#{{ t.studentId }} → 床位#{{ t.toBedId }}</span>
          <span class="dm-titem__status">{{ transferStatusLabel(t.status) }}</span>
          <template v-if="['COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW'].includes(t.status)">
            <button type="button" class="dm-btn dm-btn--primary dm-btn--sm" :disabled="acting" @click="onTransferReview(t, 'APPROVE')">通过</button>
            <button type="button" class="dm-btn dm-btn--danger dm-btn--sm" :disabled="acting" @click="onTransferReview(t, 'REJECT')">驳回</button>
          </template>
        </li>
      </ul>
    </section>

    <!-- 调宿 modal（目标空床级联） -->
    <div v-if="transferModal.visible" class="dm-mask" @click.self="transferModal.visible = false">
      <div class="dm-modal">
        <h3 class="dm-modal__title">发起调宿 · 学生#{{ transferModal.studentId }}</h3>
        <p class="dm-modal__hint">从 {{ transferModal.fromBedNo }} 调至目标空床，经辅导员→宿管两级审批后执行换床。</p>
        <label class="dm-field"><span>目标楼栋 <i>*</i></span>
          <select v-model="transferModal.buildingId" class="dm-input" @change="loadTransferRooms">
            <option value="">（选择楼栋）</option>
            <option v-for="b in buildings" :key="b.buildingId" :value="b.buildingId">{{ b.buildingName }}</option>
          </select>
        </label>
        <label class="dm-field"><span>目标房间 <i>*</i></span>
          <select v-model="transferModal.roomId" class="dm-input" :disabled="!transferModal.buildingId" @change="loadTransferBeds">
            <option value="">（选择房间）</option>
            <option v-for="r in transferModal.rooms" :key="r.roomId" :value="r.roomId">{{ r.roomNo || (r.floorNo + '层') }}（空{{ r.vacantBeds }}）</option>
          </select>
        </label>
        <label class="dm-field"><span>目标床位 <i>*</i></span>
          <select v-model="transferModal.toBedId" class="dm-input" :disabled="!transferModal.roomId">
            <option value="">（选择空床）</option>
            <option v-for="bd in transferModal.beds" :key="bd.bedId" :value="bd.bedId">{{ bd.bedNo }}</option>
          </select>
        </label>
        <label class="dm-field"><span>调宿原因</span><input v-model.trim="transferModal.reason" class="dm-input" placeholder="选填" /></label>
        <p v-if="transferModal.error" class="dm-err">{{ transferModal.error }}</p>
        <div class="dm-modal__foot">
          <button type="button" class="dm-btn" @click="transferModal.visible = false">取消</button>
          <button type="button" class="dm-btn dm-btn--primary" :disabled="acting" @click="submitTransfer">提交调宿</button>
        </div>
      </div>
    </div>

    <!-- 宿舍检查 modal（建任务 → 录结果） -->
    <div v-if="checkModal.visible" class="dm-mask" @click.self="checkModal.visible = false">
      <div class="dm-modal">
        <h3 class="dm-modal__title">宿舍检查</h3>
        <template v-if="!checkTask">
          <label class="dm-field"><span>检查任务名称 <i>*</i></span><input v-model.trim="checkModal.taskName" class="dm-input" placeholder="如：11月宿舍卫生检查" /></label>
          <label class="dm-field"><span>检查类型</span>
            <select v-model="checkModal.checkType" class="dm-input">
              <option value="HYGIENE">卫生</option><option value="SAFETY">安全</option><option value="CONTRABAND">违禁品</option><option value="NIGHT_ABSENCE">夜不归宿</option>
            </select>
          </label>
          <p v-if="checkModal.error" class="dm-err">{{ checkModal.error }}</p>
          <div class="dm-modal__foot">
            <button type="button" class="dm-btn" @click="checkModal.visible = false">取消</button>
            <button type="button" class="dm-btn dm-btn--primary" :disabled="acting" @click="submitCheckTask">建任务</button>
          </div>
        </template>
        <template v-else>
          <p class="dm-modal__hint">任务「{{ checkTask.taskName }}」进行中，录入检查结果；异常将回写异常表并生成风险单。</p>
          <label class="dm-field"><span>房间</span>
            <select v-model="checkForm.roomId" class="dm-input">
              <option value="">（选填，可不指定房间）</option>
              <option v-for="r in rooms" :key="r.roomId" :value="r.roomId">{{ r.roomNo || (r.floorNo + '层') }}</option>
            </select>
          </label>
          <label class="dm-field"><span>检查结果 <i>*</i></span>
            <select v-model="checkForm.result" class="dm-input">
              <option value="NORMAL">正常</option><option value="ABNORMAL">异常</option>
            </select>
          </label>
          <label v-if="checkForm.result === 'ABNORMAL'" class="dm-field"><span>异常说明（≥5字） <i>*</i></span>
            <input v-model.trim="checkForm.detail" class="dm-input" placeholder="描述异常情况，不少于 5 字" />
          </label>
          <p v-if="checkModal.error" class="dm-err">{{ checkModal.error }}</p>
          <div v-if="checkRecords.length" class="dm-crecs">已录：{{ checkRecords.join('、') }}</div>
          <div class="dm-modal__foot">
            <button type="button" class="dm-btn" @click="checkModal.visible = false">完成</button>
            <button type="button" class="dm-btn dm-btn--primary" :disabled="acting" @click="submitCheckRecord">录入结果</button>
          </div>
        </template>
      </div>
    </div>

    <!-- 建楼栋 modal -->
    <div v-if="buildingModal.visible" class="dm-mask" @click.self="buildingModal.visible = false">
      <div class="dm-modal">
        <h3 class="dm-modal__title">新建楼栋</h3>
        <label class="dm-field"><span>楼栋名称 <i>*</i></span><input v-model.trim="buildingModal.buildingName" class="dm-input" placeholder="如：紫荆1号楼" /></label>
        <label class="dm-field"><span>性别限制</span>
          <select v-model="buildingModal.genderLimit" class="dm-input">
            <option value="MIXED">不限</option><option value="MALE">男生</option><option value="FEMALE">女生</option>
          </select>
        </label>
        <div class="dm-gen">
          <div class="dm-gen__title">一键铺床（选填，填了即建楼铺满）</div>
          <div class="dm-grid3">
            <label class="dm-field"><span>层数</span><input v-model.number="buildingModal.floors" type="number" min="1" class="dm-input" /></label>
            <label class="dm-field"><span>每层房数</span><input v-model.number="buildingModal.roomsPerFloor" type="number" min="1" class="dm-input" /></label>
            <label class="dm-field"><span>每间床位</span><input v-model.number="buildingModal.bedsPerRoom" type="number" min="1" class="dm-input" /></label>
          </div>
        </div>
        <p v-if="buildingModal.error" class="dm-err">{{ buildingModal.error }}</p>
        <div class="dm-modal__foot">
          <button type="button" class="dm-btn" @click="buildingModal.visible = false">取消</button>
          <button type="button" class="dm-btn dm-btn--primary" :disabled="acting" @click="submitBuilding">创建</button>
        </div>
      </div>
    </div>

    <!-- 一键铺床 modal -->
    <div v-if="generateModal.visible" class="dm-mask" @click.self="generateModal.visible = false">
      <div class="dm-modal">
        <h3 class="dm-modal__title">一键铺床 · {{ building && building.buildingName }}</h3>
        <div class="dm-grid3">
          <label class="dm-field"><span>层数 <i>*</i></span><input v-model.number="generateModal.floors" type="number" min="1" class="dm-input" /></label>
          <label class="dm-field"><span>每层房数 <i>*</i></span><input v-model.number="generateModal.roomsPerFloor" type="number" min="1" class="dm-input" /></label>
          <label class="dm-field"><span>每间床位 <i>*</i></span><input v-model.number="generateModal.bedsPerRoom" type="number" min="1" class="dm-input" /></label>
        </div>
        <p v-if="generateModal.error" class="dm-err">{{ generateModal.error }}</p>
        <div class="dm-modal__foot">
          <button type="button" class="dm-btn" @click="generateModal.visible = false">取消</button>
          <button type="button" class="dm-btn dm-btn--primary" :disabled="acting" @click="submitGenerate">铺满</button>
        </div>
      </div>
    </div>

    <!-- 入住 modal -->
    <div v-if="checkinModal.visible" class="dm-mask" @click.self="checkinModal.visible = false">
      <div class="dm-modal">
        <h3 class="dm-modal__title">办理入住 · {{ checkinModal.bedNo }}</h3>
        <div class="dm-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="checkinModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
        </div>
        <p v-if="checkinModal.error" class="dm-err">{{ checkinModal.error }}</p>
        <div class="dm-modal__foot">
          <button type="button" class="dm-btn" @click="checkinModal.visible = false">取消</button>
          <button type="button" class="dm-btn dm-btn--primary" :disabled="acting" @click="submitCheckin">确认入住</button>
        </div>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="checkoutDialog.visible"
      title="办理退宿"
      :message="checkoutDialog.message"
      type="danger"
      confirm-text="确认退宿"
      :submitting="acting"
      @confirm="confirmCheckout"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 宿舍管理（/admin/student-affairs/dorm）—— 13A P7 宿舍基础台账。
 * 真实对接 /api/v1/student-affairs/dorm/*：楼栋（一键铺床）→ 房间 → 床位 → 入住/退宿；入住率统计。
 * 调宿审批、宿舍检查为后续子流程（后端已就绪，本页聚焦房源台账与入住）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const GENDER = { MALE: '男', FEMALE: '女', MIXED: '不限' }

export default {
  name: 'DormManageView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, error: '', buildings: [], occupancy: null,
      building: null, rooms: [], roomsLoading: false,
      room: null, beds: [], bedsLoading: false, acting: false,
      buildingModal: { visible: false, buildingName: '', genderLimit: 'MIXED', floors: null, roomsPerFloor: null, bedsPerRoom: null, error: '' },
      generateModal: { visible: false, floors: 4, roomsPerFloor: 10, bedsPerRoom: 4, error: '' },
      checkinModal: { visible: false, bedId: '', bedNo: '', studentId: '', error: '' },
      checkoutDialog: { visible: false, message: '', bed: null },
      transfers: [],
      transferModal: { visible: false, studentId: '', fromBedNo: '', buildingId: '', rooms: [], roomId: '', beds: [], toBedId: '', reason: '', error: '' },
      checkTask: null,
      checkModal: { visible: false, taskName: '', checkType: 'HYGIENE', error: '' },
      checkForm: { roomId: '', result: 'NORMAL', detail: '' },
      checkRecords: []
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    occRate() {
      const o = this.occupancy || {}
      const occ = o.occupiedBeds ?? o.occupied
      const tot = o.totalBeds ?? o.total
      if (!tot) return 0
      return Math.round((occ / tot) * 100)
    }
  },
  created() {
    this.loadBuildings()
    this.loadOccupancy()
  },
  methods: {
    genderLabel(g) {
      return GENDER[g] || g || ''
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async loadBuildings() {
      this.loading = true
      this.error = ''
      const res = await studentAffairsApi.getBuildings({ page: 1, pageSize: 50 })
      this.loading = false
      if (res.code === 0 && res.data) this.buildings = res.data.items || []
      else this.error = res.message || '楼栋加载失败'
    },
    async loadOccupancy() {
      const res = await studentAffairsApi.getOccupancy()
      if (res.code === 0) this.occupancy = res.data
    },
    async selectBuilding(b) {
      this.building = b
      this.room = null
      this.beds = []
      await this.loadRooms()
    },
    async loadRooms() {
      if (!this.building) return
      this.roomsLoading = true
      const res = await studentAffairsApi.getRooms(this.building.buildingId, { page: 1, pageSize: 200 })
      this.roomsLoading = false
      this.rooms = res.code === 0 && res.data ? (res.data.items || []) : []
    },
    async selectRoom(r) {
      this.room = r
      await this.loadBeds()
    },
    async loadBeds() {
      if (!this.room) return
      this.bedsLoading = true
      const res = await studentAffairsApi.getBeds(this.room.roomId)
      this.bedsLoading = false
      this.beds = res.code === 0 && res.data ? (res.data.items || []) : []
    },
    async refreshAfterBedChange() {
      await this.loadBeds()
      await this.loadRooms()
      await this.loadBuildings()
      await this.loadOccupancy()
    },
    openBuilding() {
      this.buildingModal = { visible: true, buildingName: '', genderLimit: 'MIXED', floors: null, roomsPerFloor: null, bedsPerRoom: null, error: '' }
    },
    async submitBuilding() {
      const m = this.buildingModal
      if (!m.buildingName) { m.error = '请填写楼栋名称'; return }
      const body = { buildingName: m.buildingName, genderLimit: m.genderLimit }
      if (m.floors && m.roomsPerFloor && m.bedsPerRoom) {
        body.floors = m.floors; body.roomsPerFloor = m.roomsPerFloor; body.bedsPerRoom = m.bedsPerRoom
      }
      this.acting = true
      const res = await studentAffairsApi.createBuilding(body)
      this.acting = false
      if (res.code === 0) {
        toast.success('楼栋已创建')
        this.buildingModal.visible = false
        await this.loadBuildings()
        this.loadOccupancy()
      } else { m.error = res.message || '创建失败' }
    },
    openGenerate() {
      this.generateModal = { visible: true, floors: 4, roomsPerFloor: 10, bedsPerRoom: 4, error: '' }
    },
    async submitGenerate() {
      const m = this.generateModal
      if (!m.floors || !m.roomsPerFloor || !m.bedsPerRoom) { m.error = '请填写层数/房数/床位'; return }
      this.acting = true
      const res = await studentAffairsApi.generateLayout(this.building.buildingId, { floors: m.floors, roomsPerFloor: m.roomsPerFloor, bedsPerRoom: m.bedsPerRoom })
      this.acting = false
      if (res.code === 0) {
        toast.success('已铺满床位')
        this.generateModal.visible = false
        await this.loadRooms()
        this.loadBuildings()
        this.loadOccupancy()
      } else { m.error = res.message || '铺床失败' }
    },
    openCheckin(bed) {
      this.checkinModal = { visible: true, bedId: bed.bedId, bedNo: bed.bedNo, studentId: '', error: '' }
    },
    async submitCheckin() {
      const m = this.checkinModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      this.acting = true
      const res = await studentAffairsApi.checkinBed(m.bedId, m.studentId)
      this.acting = false
      if (res.code === 0) {
        toast.success('已入住')
        this.checkinModal.visible = false
        this.refreshAfterBedChange()
      } else {
        m.error = res.message || '入住失败'
        toast.error(m.error)
      }
    },
    onCheckout(bed) {
      this.checkoutDialog = { visible: true, bed, message: `确认为床位 ${bed.bedNo}（学生#${bed.studentId}）办理退宿？` }
    },
    async confirmCheckout() {
      this.acting = true
      const res = await studentAffairsApi.checkoutBed(this.checkoutDialog.bed.bedId)
      this.acting = false
      this.checkoutDialog.visible = false
      if (res.code === 0) {
        toast.success('已退宿')
        this.refreshAfterBedChange()
      } else {
        toast.error(res.message || '退宿失败')
      }
    },
    // ── 调宿 ──
    transferStatusLabel(s) {
      return { COUNSELOR_REVIEW: '辅导员审批', DORM_MANAGER_REVIEW: '宿管审批', EXECUTED: '已执行换床', REJECTED: '已驳回' }[s] || s
    },
    openTransfer(bed) {
      this.transferModal = { visible: true, studentId: bed.studentId, fromBedNo: bed.bedNo, buildingId: '', rooms: [], roomId: '', beds: [], toBedId: '', reason: '', error: '' }
    },
    async loadTransferRooms() {
      this.transferModal.roomId = ''
      this.transferModal.beds = []
      this.transferModal.toBedId = ''
      this.transferModal.rooms = []
      if (!this.transferModal.buildingId) return
      const res = await studentAffairsApi.getRooms(this.transferModal.buildingId, { page: 1, pageSize: 200 })
      if (res.code === 0 && res.data) this.transferModal.rooms = (res.data.items || []).filter((r) => r.vacantBeds > 0)
    },
    async loadTransferBeds() {
      this.transferModal.toBedId = ''
      this.transferModal.beds = []
      if (!this.transferModal.roomId) return
      const res = await studentAffairsApi.getBeds(this.transferModal.roomId)
      if (res.code === 0 && res.data) this.transferModal.beds = (res.data.items || []).filter((b) => b.status === 'VACANT')
    },
    async submitTransfer() {
      const m = this.transferModal
      if (!m.toBedId) { m.error = '请选择目标空床'; return }
      this.acting = true
      const res = await studentAffairsApi.submitDormTransfer({ studentId: String(m.studentId), toBedId: String(m.toBedId), reason: m.reason || '' })
      this.acting = false
      if (res.code === 0 && res.data) {
        toast.success('调宿已提交，待审批')
        this.transferModal.visible = false
        this.transfers.unshift(res.data)
      } else {
        m.error = res.message || '提交失败'
        toast.error(m.error)
      }
    },
    async onTransferReview(t, action) {
      let reason = ''
      if (action === 'REJECT') {
        reason = window.prompt('请填写驳回原因（≥5字）') || ''
        if (reason.trim().length < 5) { toast.error('驳回原因不少于 5 字'); return }
      }
      this.acting = true
      const res = await studentAffairsApi.reviewDormTransfer(t.transferId, action, reason)
      this.acting = false
      if (res.code === 0 && res.data) {
        toast.success(res.data.status === 'EXECUTED' ? '调宿已执行换床' : (action === 'REJECT' ? '已驳回' : '已通过，待下一级'))
        const idx = this.transfers.findIndex((x) => x.transferId === t.transferId)
        if (idx > -1) this.transfers.splice(idx, 1, res.data)
        if (res.data.status === 'EXECUTED') this.refreshAfterBedChange()
      } else {
        toast.error(res.message || '审批失败')
      }
    },
    // ── 宿舍检查 ──
    openCheck() {
      this.checkTask = null
      this.checkRecords = []
      this.checkForm = { roomId: '', result: 'NORMAL', detail: '' }
      this.checkModal = { visible: true, taskName: '', checkType: 'HYGIENE', error: '' }
    },
    async submitCheckTask() {
      const m = this.checkModal
      if (!m.taskName) { m.error = '请填写检查任务名称'; return }
      this.acting = true
      const res = await studentAffairsApi.createDormCheckTask({
        taskName: m.taskName, checkType: m.checkType,
        buildingId: this.building ? String(this.building.buildingId) : null
      })
      this.acting = false
      if (res.code === 0 && res.data) {
        this.checkTask = res.data
        this.checkModal.error = ''
        toast.success('检查任务已创建')
      } else { m.error = res.message || '创建失败' }
    },
    async submitCheckRecord() {
      const f = this.checkForm
      if (f.result === 'ABNORMAL' && (!f.detail || f.detail.length < 5)) { this.checkModal.error = '异常说明不少于 5 字'; return }
      this.acting = true
      const res = await studentAffairsApi.submitDormCheckRecord(this.checkTask.taskId, {
        roomId: f.roomId || null, result: f.result, detail: f.detail || ''
      })
      this.acting = false
      if (res.code === 0) {
        this.checkModal.error = ''
        this.checkRecords.push(f.result === 'ABNORMAL' ? '异常(已生成风险)' : '正常')
        toast.success(f.result === 'ABNORMAL' ? '已录入异常，已生成风险单' : '已录入正常')
        this.checkForm = { roomId: '', result: 'NORMAL', detail: '' }
      } else {
        this.checkModal.error = res.message || '录入失败'
        toast.error(this.checkModal.error)
      }
    }
  }
}
</script>

<style scoped>
.dm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
.dm-occ {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.dm-toolbar__btns {
  display: flex;
  gap: var(--space-2);
}
.dm-crecs {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.dm-occ b {
  color: var(--primary-700);
  font-size: var(--font-size-base);
}
.dm-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.dm-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.dm-btn--sm {
  height: 26px;
  padding: 0 var(--space-2);
  font-size: var(--font-size-xs);
}
.dm-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.dm-btn--danger {
  border-color: var(--danger-300, #fca5a5);
  color: var(--danger-600, #dc2626);
}
.dm-workspace {
  display: grid;
  grid-template-columns: minmax(200px, 260px) 1fr minmax(220px, 300px);
  gap: var(--space-3);
  align-items: start;
}
.dm-col {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-3);
}
.dm-col__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}
.dm-col__head span {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-weight: 400;
}
.dm-blist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dm-bitem {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.dm-bitem:hover {
  border-color: var(--primary-300);
}
.dm-bitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.dm-bitem__name {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-primary);
}
.dm-gender {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-left: var(--space-2);
}
.dm-bitem__beds {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}
.dm-rooms {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: var(--space-2);
}
.dm-room {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  cursor: pointer;
}
.dm-room.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.dm-room.is-full {
  opacity: 0.6;
}
.dm-room__no {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
}
.dm-room__beds {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dm-beds {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dm-bed {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
}
.dm-bed__no {
  font-weight: 600;
  color: var(--text-primary);
  margin-right: var(--space-2);
}
.dm-bed__status {
  font-size: var(--font-size-xs);
  padding: 1px var(--space-1);
  border-radius: var(--radius-base);
}
.dm-bed__status--occupied {
  color: var(--warning-700, #b45309);
  background: var(--warning-50, #fffbeb);
}
.dm-bed__status--vacant {
  color: var(--success-700, #15803d);
  background: var(--success-50, #f0fdf4);
}
.dm-bed__stu {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-left: var(--space-2);
}
.dm-transfers {
  margin-top: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}
.dm-transfers__title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
}
.dm-tlist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dm-titem {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.dm-titem__status {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-right: auto;
}
.dm-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.dm-modal {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.dm-modal__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.dm-gen {
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
}
.dm-gen__title {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.dm-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.dm-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.dm-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.dm-grid3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--space-2);
}
.dm-input {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.dm-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.dm-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
