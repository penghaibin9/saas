<template>
  <ModulePageShell flat title="住宿分配计划" watermark-purpose="住宿分配计划">
    <template #actions>
      <AppButton v-if="$route.query.source === 'orientation'" variant="ghost" @click="$router.push('/admin/orientation/dorm-preassign')">返回新生安排</AppButton>
      <AppButton variant="secondary" @click="$router.push('/admin/student-affairs/dorm/resource')">查看房态</AppButton>
      <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" :disabled="actioning" @click="showCreate = true">新建计划</AppPermissionButton>
      <AppButton variant="ghost" :disabled="actioning" @click="load">刷新</AppButton>
    </template>
    <p v-if="errorMessage" class="allocation-error" role="alert">{{ errorMessage }}</p>
    <p v-if="loading" class="empty">正在加载分配计划…</p>
    <template v-else>
      <div class="plan-switcher">
        <label>分配计划 <select v-model="selectedId" class="sa-input" :disabled="actioning" @change="loadDetail(selectedId)"><option value="">请选择计划</option><option v-for="row in batches" :key="row.batchId" :value="String(row.batchId)">{{ row.name }} · {{ statusLabel(row.status) }}</option></select></label>
        <label>状态 <select v-model="statusFilter" class="sa-input" :disabled="actioning" @change="load"><option value="">全部</option><option value="DRAFT">草稿</option><option value="PUBLISHED">已发布</option><option value="CLOSED">已关闭</option></select></label>
      </div>
      <p v-if="detailLoading" class="empty">正在读取计划…</p>
      <p v-else-if="!detail" class="empty">{{ batches.length ? '请选择分配计划。' : '暂无分配计划。新建计划后，选择迎新批次与可用楼栋。' }}</p>
      <section v-else class="allocation-desk">
        <div class="detail-head"><div><h2>{{ detail.batch.name }}</h2><p>{{ modeLabel(detail.batch.mode) }} · {{ fmt(detail.batch.openAt) }} 至 {{ fmt(detail.batch.closeAt) }}</p></div><AppStatusTag :label="statusLabel(detail.batch.status)" /></div>
        <ol class="process-steps" aria-label="分配进度"><li class="done">1 选择批次与楼栋</li><li :class="{ done: !!drySummary || detail.batch.status !== 'DRAFT' }">2 {{ detail.batch.mode === 'STUDENT_SELECT' ? '核对自选范围' : '生成分配方案' }}</li><li :class="{ done: proposedCount > 0 || detail.batch.status !== 'DRAFT' }">3 核对学生与床位</li><li :class="{ done: detail.batch.status !== 'DRAFT' }">4 发布安排</li></ol>
        <div class="summary-line"><span>范围学生 <strong>{{ (detail.candidates?.length || 0) + (detail.missingIdentityCount || 0) }}</strong></span><span>拟分配 <strong>{{ proposedCount }}</strong></span><span>待处理 <strong>{{ unresolvedCount }}</strong></span><span>已预留 <strong>{{ reservedCount }}</strong></span><span>已入住 <strong>{{ activeCount }}</strong></span></div>
        <p v-if="detail.missingIdentityCount" class="allocation-warning">{{ detail.missingIdentityCount }} 名新生尚未关联学生档案，暂时不能分配。<AppButton variant="ghost" @click="$router.push('/admin/orientation/students')">核对新生资料</AppButton></p>
        <section v-if="detail.capacity && detail.batch.status === 'DRAFT'" class="capacity-check" aria-label="分配容量核对">
          <table><caption>容量核对</caption><thead><tr><th>住宿分区</th><th>待分学生</th><th>专用空床</th><th>需补充床位</th><th>专用床余量</th></tr></thead><tbody><tr v-for="row in detail.capacity.rows" :key="row.gender"><th>{{ row.label }}</th><td>{{ row.students }}</td><td>{{ row.dedicatedBeds }}</td><td :class="{ 'danger-text': row.needsSharedBeds > 0 }">{{ row.needsSharedBeds }}</td><td>{{ row.surplusDedicatedBeds }}</td></tr></tbody></table>
          <p class="cell-sub">混合楼空床 {{ detail.capacity.sharedBeds }} · 已有住宿 {{ detail.capacity.alreadyHousedStudents }} · 性别待核实 {{ detail.capacity.unknownGenderStudents }} · 房源分区待核实 {{ detail.capacity.unclassifiedBeds }}</p>
          <p v-if="detail.capacity.minimumShortage" class="allocation-error">按楼栋分区至少缺 {{ detail.capacity.minimumShortage }} 个床位，请调整合法房源范围。</p>
          <p v-if="detail.capacity.requiresRoomValidation" class="allocation-warning">混合楼床位只计一次；仍需核对房间分区，不能仅凭总空床数判断可分配。</p>
        </section>
    <div v-if="publishJob || publishJobError" class="publish-job" role="status" aria-live="polite">
      <template v-if="publishJob">
        <strong>{{ ({ PENDING: '等待发布', RUNNING: '正在发布', SUCCESS: '发布完成', FAILED: '发布未完成' })[publishJob.status] }}</strong>
        <span v-if="['PENDING', 'RUNNING'].includes(publishJob.status)">后台核验与预留床位中，可以离开页面。</span>
        <span v-else-if="publishJob.status === 'SUCCESS'">床位安排已生效，到校后核验办理入住。</span>
        <span v-else>{{ publishJob.error }}</span>
      </template>
      <span v-if="publishJobError" class="allocation-error">{{ publishJobError }}</span>
      <AppButton variant="ghost" @click="refreshPublishJob(selectedId)">刷新进度</AppButton>
    </div>
        <div class="desk-toolbar">
          <input v-model="searchText" class="sa-input search" placeholder="搜索姓名或学号" aria-label="搜索分配学生" @input="page = 1" />
          <select v-model="itemFilter" class="sa-input" aria-label="筛选分配结果" @change="page = 1"><option value="">全部学生</option><option value="UNASSIGNED">待处理</option><option value="PROPOSED">拟分配</option><option value="RESERVED">已预留</option><option value="ACTIVE">已入住</option></select>
          <div class="actions" v-if="detail.batch.status === 'DRAFT'">
            <AppPermissionButton v-if="detail.batch.mode !== 'STUDENT_SELECT'" :allowed="canManage" code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="requestGenerate">{{ drySummary ? '重新生成' : '生成分配方案' }}</AppPermissionButton>
            <AppButton variant="ghost" :disabled="actioning" @click="downloadConflicts">导出异常</AppButton>
            <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" :loading="actioning" :disabled="!publishReady" @click="publishBatch">核对发布</AppPermissionButton>
          </div>
        </div>
        <DataTable :columns="columns" :rows="pagedItems" row-key="studentId" :pagination="{ page, pageSize: 30, total: filteredItems.length }" @page-change="page = $event">
          <template #cell-student="{ row }"><strong>{{ row.studentName }}</strong><small class="cell-sub">{{ row.studentNo }}</small></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'CONFLICT' ? 'danger' : 'default'" :label="itemStatusLabel(row.status)" /></template>
          <template #cell-bed="{ row }">{{ row.bedLabel || '待安排' }}<small v-if="row.source === 'MANUAL' && row.status === 'PROPOSED'" class="cell-sub">人工安排 · 重算保留</small></template>
          <template #cell-housing="{ row }">{{ row.housing?.housingStatusLabel || '未分配' }}</template>
          <template #cell-conflict="{ row }"><span :class="{ 'danger-text': row.conflictCode }">{{ conflictLabel(row.conflictCode) }}</span></template>
          <template #cell-actions="{ row }"><AppPermissionButton v-if="detail.batch.status === 'DRAFT' && detail.batch.mode !== 'STUDENT_SELECT' && !row.housing?.bedId" :allowed="canManage" code="studentAffairs.dorm.allocation.manage" variant="ghost" :disabled="actioning" @click="openManual(row)">{{ row.bedId ? '调整床位' : '安排床位' }}</AppPermissionButton><AppButton v-else-if="row.housing?.bedId" variant="ghost" @click="openHousing(row)">查看床位</AppButton></template>
        </DataTable>
      </section>
    </template>
    <AppDrawer v-model:visible="showCreate" title="新建分配计划" size="large" mode="modal">
      <p v-if="errorMessage" class="allocation-error" role="alert">{{ errorMessage }}</p>
        <div class="form-grid">
          <label><span>批次编号</span><input v-model.trim="form.batchNo" class="sa-input" maxlength="100" /></label>
          <label><span>批次名称</span><input v-model.trim="form.name" class="sa-input" maxlength="200" placeholder="例：2026 级新生住宿分配" /></label>
          <label><span>学年</span><input v-model.trim="form.academicYear" class="sa-input" maxlength="20" /></label>
          <label><span>关联迎新批次</span><select v-model="form.orientationBatchId" class="sa-input"><option value="">请选择</option><option v-for="row in orientationBatches" :key="row.id || row.batchId" :value="row.id || row.batchId">{{ row.name || row.batchName || row.batchNo }}</option></select></label>
          <label><span>分配模式</span><select v-model="form.mode" class="sa-input"><option value="ADMIN_AUTO">管理员自动分配</option><option value="ADMIN_MANUAL">管理员人工分配</option><option value="STUDENT_SELECT">学生在时间窗内自选</option><option value="POST_CHECKIN_PUBLISH">现场报到后公布</option></select></label>
          <label><span>开放时间</span><input v-model="form.openAt" type="datetime-local" class="sa-input" /></label>
          <label><span>关闭时间</span><input v-model="form.closeAt" type="datetime-local" class="sa-input" /></label>
        </div>
        <div class="block-title">选择可用楼栋</div>
        <div class="check-grid">
          <label v-for="building in buildings" :key="building.buildingId"><input v-model="form.buildingIds" type="checkbox" :value="String(building.buildingId)" /> <strong>{{ building.buildingName }}</strong><small>空床 {{ building.vacantBeds ?? '—' }} / {{ building.totalBeds ?? '—' }}</small></label>
        </div>
        <div class="block-title">优先安排方式</div>
        <div class="rule-row"><label><input v-model="form.rules.sameCollege" type="checkbox" /> 学院尽量相近</label><label><input v-model="form.rules.sameMajor" type="checkbox" /> 专业尽量相近</label><label><input v-model="form.rules.sameClass" type="checkbox" /> 班级尽量相近</label><label><input v-model="form.rules.minimizeVacancy" type="checkbox" /> 减少零散空床</label><label><input v-model="form.rules.balanceFloor" type="checkbox" /> 平衡楼层</label></div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="showCreate = false">取消</AppButton>
        <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" :loading="actioning" :disabled="!createValid" @click="createBatch">保存草稿</AppPermissionButton>
      </template>

    </AppDrawer>
    <AppDrawer v-model:visible="manualVisible" :title="`安排床位 · ${manual.studentName || ''}`" size="large" mode="modal">
      <p class="cell-sub">{{ manual.studentNo }} · 人工安排将在重新生成时保留，发布后才预留床位。</p>
      <p v-if="manualError" class="allocation-error" role="alert">{{ manualError }}</p>
      <div class="form-grid"><label>楼栋<select v-model="manual.buildingId" class="sa-input" @change="loadManualRooms"><option value="">请选择楼栋</option><option v-for="b in allocationBuildings" :key="b.buildingId" :value="String(b.buildingId)">{{ b.buildingName }}</option></select></label><label>房间<select v-model="manual.roomId" class="sa-input" @change="loadManualBeds"><option value="">请选择房间</option><option v-for="r in manualRooms" :key="r.roomId" :value="String(r.roomId)">{{ r.roomNo }} · 空床 {{ r.vacantBeds ?? '—' }}</option></select></label></div>
      <p v-if="manualLoading" class="empty">正在读取床位…</p>
      <div v-else class="bed-grid"><button v-for="bed in manualBeds" :key="bed.bedId" type="button" class="bed-option" :class="{ selected: manual.bedId === String(bed.bedId) }" :disabled="!bedAvailable(bed)" :aria-pressed="manual.bedId === String(bed.bedId)" @click="manual.bedId = String(bed.bedId)"><strong>{{ bed.bedNo }} 号床</strong><span>{{ bedAvailable(bed) ? '可分配' : '不可分配' }}</span></button></div>
      <p v-if="manual.roomId && !manualBeds.length && !manualLoading" class="empty">该房间暂无床位。</p>
      <template #footer><AppButton variant="secondary" @click="manualVisible = false">取消</AppButton><AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" :disabled="!manual.bedId || manualLoading" :loading="actioning" @click="manualAssign">保存床位安排</AppPermissionButton></template>
    </AppDrawer>
    <AppConfirmDialog v-model:visible="regenerateVisible" title="重新生成分配方案" message="保留人工安排的床位，仅重新计算其余学生。是否继续？" confirm-text="重新生成" :submitting="actioning" @confirm="dryRun" />

    <AppConfirmDialog v-model:visible="publishConfirm.visible" title="核对并发布住宿安排" :message="publishMessage" confirm-text="确认发布" :confirm-disabled="!publishReady" :submitting="actioning" @confirm="confirmPublishBatch"><p v-if="errorMessage" class="allocation-error" role="alert">{{ errorMessage }}</p></AppConfirmDialog>
  </ModulePageShell>
</template>
<script>
import { AppConfirmDialog, AppPermissionButton, AppStatusTag } from '@/components/common'
import { DataTable, ModulePageShell } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { getOrientationBatches } from '@/modules/orientation/api/orientation.api'
import { AppDrawer, AppButton } from '@/components/ui'
import { studentAffairsApi as resourceApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

function localInput(date) { const value = new Date(date.getTime() - date.getTimezoneOffset() * 60000); return value.toISOString().slice(0, 16) }
function initialForm() { const now = new Date(); const close = new Date(now.getTime() + 7 * 86400000); const year = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1; return { batchNo: `DORM-${now.toISOString().slice(0,10).replaceAll('-', '')}-${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`, name: '', academicYear: `${year}-${year + 1}`, sourceType: 'ORIENTATION', orientationBatchId: '', mode: 'ADMIN_AUTO', openAt: localInput(now), closeAt: localInput(close), buildingIds: [], rules: { sameCollege: true, sameMajor: true, sameClass: true, minimizeVacancy: true, balanceFloor: false } } }

export default {
  name: 'DormAllocationView',
  props: { ctx: { type: Object, default: null } },
  components: { AppConfirmDialog, AppPermissionButton, AppStatusTag, AppDrawer, AppButton, DataTable, ModulePageShell },
  data() { return { loading: true, actioning: false, publishJob: null, publishJobError: '', jobRequest: 0, jobTimer: null, deskActive: true, errorMessage: '', showCreate: false, statusFilter: '', batches: [], buildings: [], orientationBatches: [], selectedId: '', detail: null, drySummary: null, publishConfirm: { visible: false }, form: initialForm(), manual: { studentId: '', bedId: '' }, detailLoading: false, detailRequest: 0, manualRequest: 0, manualVisible: false, manualLoading: false, manualError: '', manualRooms: [], manualBeds: [], regenerateVisible: false, searchText: '', itemFilter: '', page: 1, columns: [{ key: 'student', title: '学生' }, { key: 'status', title: '分配状态' }, { key: 'bed', title: '床位' }, { key: 'housing', title: '实际住宿' }, { key: 'conflict', title: '待处理原因' }, { key: 'actions', title: '操作' }] } },
  computed: {
    allItems() {
      const items = this.detail?.items || []
      const candidates = this.detail?.candidates || []
      const byId = new Map(items.map(row => [String(row.studentId), row]))
      const candidateIds = new Set(candidates.map(row => String(row.studentId)))
      return candidates.map(row => byId.get(String(row.studentId)) || {
        ...row, status: ['ACTIVE', 'RESERVED'].includes(row.housing?.housingStatus) ? 'CONFLICT' : 'UNASSIGNED',
        conflictCode: ['ACTIVE', 'RESERVED'].includes(row.housing?.housingStatus) ? 'ALREADY_HAS_BED' : ''
      }).concat(items.filter(row => !candidateIds.has(String(row.studentId))))
    },
    proposedCount() { return this.allItems.filter(r => r.status === 'PROPOSED').length },
    unresolvedCount() { return this.allItems.filter(r => ['CONFLICT', 'UNASSIGNED'].includes(r.status)).length + (this.detail?.missingIdentityCount || 0) },
    reservedCount() { return this.allItems.filter(r => r.housing?.housingStatus === 'RESERVED').length },
    activeCount() { return this.allItems.filter(r => r.housing?.housingStatus === 'ACTIVE').length },
    filteredItems() { const keyword = this.searchText.trim().toLowerCase(); return this.allItems.filter(r => (!keyword || `${r.studentName} ${r.studentNo}`.toLowerCase().includes(keyword)) && (!this.itemFilter || (this.itemFilter === 'UNASSIGNED' ? ['UNASSIGNED', 'CONFLICT'].includes(r.status) : this.itemFilter === 'PROPOSED' ? r.status === 'PROPOSED' : r.housing?.housingStatus === this.itemFilter))) },
    pagedItems() { return this.filteredItems.slice((this.page - 1) * 30, this.page * 30) },
    allocationBuildings() { const ids = this.detail?.batch.resourceScope?.buildingIds || []; return this.buildings.filter(b => !ids.length || ids.map(String).includes(String(b.buildingId))) },
    publishReady() { if (!this.detail || this.detail.batch.status !== 'DRAFT' || this.detailLoading || this.publishJobError || ['PENDING', 'RUNNING'].includes(this.publishJob?.status)) return false; if (this.detail.batch.mode === 'STUDENT_SELECT') return !!this.detail.candidates?.length; return this.proposedCount > 0 && (this.detail.batch.mode === 'ADMIN_MANUAL' || !!this.drySummary) },
    publishMessage() { return this.detail?.batch.mode === 'STUDENT_SELECT' ? `将向 ${this.detail?.candidates?.length || 0} 名学生开放选床，${this.detail?.missingIdentityCount || 0} 名未关联档案的新生暂不参加。发布后学生范围与精确床位资源池将冻结；选床后仅预留床位，需另行办理入住。` : `本次发布 ${this.proposedCount} 个床位安排，${this.unresolvedCount} 项尚未解决，不会在本次分配床位。发布后学生范围与精确床位资源池将冻结，并预留已分配床位；需另行办理入住。` },
    canView() { return canCode(this.ctx, 'studentAffairs.dorm.view') },
    canManage() { return canCode(this.ctx, 'studentAffairs.dorm.allocation.manage') },
    createValid() { return !!(this.form.batchNo && this.form.name && this.form.academicYear && this.form.orientationBatchId && this.form.openAt && this.form.closeAt && this.form.openAt < this.form.closeAt && this.form.buildingIds.length) }
  },
  mounted() { this.form.orientationBatchId = String(this.$route.query.orientationBatchId || ''); this.load() },
  activated() { this.deskActive = true; if (this.selectedId && this.canManage) this.refreshPublishJob(this.selectedId) },
  deactivated() { this.stopPublishPolling() },
  beforeUnmount() { this.stopPublishPolling() },
  methods: {
    unwrap(res) { if (!res || res.code !== 0) throw new Error(res?.message || '操作失败'); return res.data },
    fmt(value) { return String(value || '').slice(0, 16).replace('T', ' ') },
    modeLabel(value) { return ({ ADMIN_AUTO: '管理员自动', ADMIN_MANUAL: '管理员人工', STUDENT_SELECT: '学生自选', POST_CHECKIN_PUBLISH: '报到后公布' })[value] || (value ? '待确认' : '—') },
    statusLabel(value) { return ({ DRAFT: '草稿', PUBLISHED: '已发布', CLOSED: '已关闭', CANCELLED: '已取消' })[value] || (value ? '待确认' : '—') },
    itemStatusLabel(value) { return ({ UNASSIGNED: '待安排', PENDING: '待学生选床', PROPOSED: '待发布', RESERVED: '已预留', CONFIRMED: '学生已确认', CONFLICT: '异常', CANCELLED: '已取消' })[value] || (value ? '待确认' : '—') },
    conflictLabel(value) { return ({ ALREADY_HAS_BED: '已有住宿或预留，请核对', NO_COMPATIBLE_BED: '缺少合适空床或性别不匹配', DATA_MISSING: '学生档案待补全', OUT_OF_SCOPE: '已移出分配范围' })[value] || (value ? '请核对分配条件' : '—') },
    async load() { if (this.actioning && !this.selectedId) return; this.loading = true; this.errorMessage = ''; try { const [batchRes, buildingRes, oriRes] = await Promise.all([studentAffairsApi.listDormAllocationBatches({ status: this.statusFilter, pageSize: 200 }), resourceApi.listAllDormBuildings(), getOrientationBatches({ page: 1, pageSize: 200 })]); this.batches = this.unwrap(batchRes).items || []; this.buildings = this.unwrap(buildingRes).items || []; this.orientationBatches = oriRes.code === 0 ? oriRes.data?.list || [] : []; this.selectedId = this.batches.some(b => String(b.batchId) === String(this.selectedId)) ? String(this.selectedId) : String(this.batches[0]?.batchId || ''); await this.loadDetail(this.selectedId) } catch (e) { this.errorMessage = e.message || '加载失败' } finally { this.loading = false } },
    async loadDetail(id) { clearTimeout(this.jobTimer); ++this.jobRequest; this.publishJob = null; this.publishJobError = ''; const serial = ++this.detailRequest; this.detail = null; this.drySummary = null; this.page = 1; this.detailLoading = !!id; if (!id) return; try { const data = this.unwrap(await studentAffairsApi.getDormAllocationBatch(id)); if (serial !== this.detailRequest) return; this.detail = data; this.drySummary = data.batch.rules?._dryRun || null; if (this.canManage) await this.refreshPublishJob(id) } catch (e) { if (serial === this.detailRequest) this.errorMessage = e.message } finally { if (serial === this.detailRequest) this.detailLoading = false } },
    openManual(row) { this.manualRequest++; this.manual = { studentId: row.studentId, studentName: row.studentName, studentNo: row.studentNo, buildingId: '', roomId: '', bedId: '' }; this.manualRooms = []; this.manualBeds = []; this.manualError = ''; this.manualVisible = true; this.manualLoading = false },
    async loadManualRooms() { const serial = ++this.manualRequest; this.manual.roomId = ''; this.manual.bedId = ''; this.manualRooms = []; this.manualBeds = []; this.manualError = ''; this.manualLoading = !!this.manual.buildingId; if (!this.manual.buildingId) return; try { const data = this.unwrap(await resourceApi.listAllDormRooms(this.manual.buildingId)); if (serial === this.manualRequest) this.manualRooms = (data.items || []).filter(r => r.status === 'ENABLED') } catch (e) { if (serial === this.manualRequest) this.manualError = e.message } finally { if (serial === this.manualRequest) this.manualLoading = false } },
    async loadManualBeds() { const serial = ++this.manualRequest; this.manual.bedId = ''; this.manualBeds = []; this.manualError = ''; this.manualLoading = !!this.manual.roomId; if (!this.manual.roomId) return; try { const data = this.unwrap(await resourceApi.listDormBeds(this.manual.roomId)); if (serial === this.manualRequest) this.manualBeds = data.items || [] } catch (e) { if (serial === this.manualRequest) this.manualError = e.message } finally { if (serial === this.manualRequest) this.manualLoading = false } },
    bedAvailable(bed) { return bed.status === 'VACANT' && !bed.studentId && !this.allItems.some(i => String(i.studentId) !== String(this.manual.studentId) && String(i.bedId) === String(bed.bedId) && !['CANCELLED', 'CONFLICT'].includes(i.status)) },
    openHousing(row) { const h = row.housing; this.$router.push({ path: '/admin/student-affairs/dorm/resource', query: { buildingId: h.buildingId, roomId: h.roomId, bedId: h.bedId } }) },
    requestGenerate() { if (this.detail?.items?.some(r => r.status === 'PROPOSED')) this.regenerateVisible = true; else this.dryRun() },
    async act(task, after) { this.actioning = true; this.errorMessage = ''; try { const data = this.unwrap(await task()); if (after) await after(data); return data } catch (e) { this.errorMessage = e.message || '操作失败'; return null } finally { this.actioning = false } },
    async createBatch() { if (!this.createValid) return; const payload = { ...this.form, resourceScope: { buildingIds: this.form.buildingIds.map(String) }, studentScope: {}, rules: { ...this.form.rules } }; delete payload.buildingIds; await this.act(() => studentAffairsApi.createDormAllocationBatch(payload), async (row) => { this.form = initialForm(); this.showCreate = false; this.statusFilter = ''; this.selectedId = String(row.batchId); await this.load() }) },
    async dryRun() { this.regenerateVisible = false; await this.act(() => studentAffairsApi.dryRunDormAllocation(this.selectedId), async (data) => { this.drySummary = data.summary; await this.loadDetail(this.selectedId) }) },
    async manualAssign() { if (!this.manual.bedId || this.actioning) return; const batchId = this.selectedId; this.actioning = true; this.manualError = ''; try { this.unwrap(await studentAffairsApi.manualAssignDorm(batchId, this.manual.studentId, this.manual.bedId)); this.manualVisible = false; await this.loadDetail(batchId) } catch (e) { this.manualError = e.message || '安排失败，请重新核对床位' } finally { this.actioning = false } },
    publishBatch() { if (this.publishReady) this.publishConfirm.visible = true },
    async confirmPublishBatch() {
      if (this.actioning || !this.publishReady) return
      const batchId = this.selectedId
      const version = this.detail.batch.version
      this.actioning = true
      this.errorMessage = ''
      try {
        const job = this.unwrap(await studentAffairsApi.queueDormAllocationPublish(batchId, version))
        if (String(this.selectedId) !== String(batchId) || !this.deskActive) return
        this.publishJob = job
        this.publishConfirm.visible = false
        await this.refreshPublishJob(batchId)
      } catch (error) {
        // Read the durable job after a lost response; never resubmit implicitly.
        if (String(this.selectedId) !== String(batchId) || !this.deskActive) return
        await this.refreshPublishJob(batchId)
        if (this.publishJob && this.publishJob.version === version) this.publishConfirm.visible = false
        else this.errorMessage = `${error.message || '未收到任务结果'}。请刷新核对发布任务。`
      } finally { this.actioning = false }
    },
    stopPublishPolling() { this.deskActive = false; ++this.jobRequest; clearTimeout(this.jobTimer) },
    async refreshPublishJob(batchId) {
      clearTimeout(this.jobTimer)
      const serial = ++this.jobRequest
      try {
        const result = this.unwrap(await studentAffairsApi.getDormAllocationPublishJob(batchId))
        const job = result?.jobId ? result : null
        if (serial !== this.jobRequest || !this.deskActive || String(batchId) !== String(this.selectedId)) return
        this.publishJob = job
        this.publishJobError = ''
        if (job?.status === 'SUCCESS' && this.detail?.batch.status === 'DRAFT') {
          await this.loadDetail(batchId)
        } else if (['PENDING', 'RUNNING'].includes(job?.status)) {
          this.jobTimer = setTimeout(() => this.refreshPublishJob(batchId), 3000)
        }
      } catch {
        if (serial === this.jobRequest && this.deskActive) this.publishJobError = '发布状态读取失败，请刷新核对；已保存的任务仍由后台处理。'
      }
    },
    async downloadConflicts() { await this.act(() => studentAffairsApi.downloadDormAllocationConflicts(this.selectedId)) }
  }
}
</script>

<style scoped>
.publish-job{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 0;border-top:1px solid var(--border-light);font-size:13px;color:var(--text-secondary)}.publish-job strong{color:var(--text-primary)}
.capacity-check{padding:12px 0;border-bottom:1px solid var(--border-light);overflow-x:auto}.capacity-check table{width:100%;border-collapse:collapse;font-size:13px;text-align:right;font-variant-numeric:tabular-nums}.capacity-check caption{text-align:left;font-weight:600;padding:0 0 8px}.capacity-check th,.capacity-check td{padding:8px 12px;border-bottom:1px solid var(--border-light)}.capacity-check th:first-child{text-align:left}.capacity-check thead{color:var(--text-secondary);background:var(--bg-card)}
.plan-switcher,.desk-toolbar,.actions,.detail-head,.summary-line,.rule-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.plan-switcher{padding-bottom:16px;border-bottom:1px solid var(--border-light)}.plan-switcher label{display:flex;gap:8px;align-items:center;font-size:13px}.plan-switcher label:first-child{flex:1}.plan-switcher label:first-child select{max-width:480px;flex:1}.sa-input{box-sizing:border-box;min-height:36px;max-width:100%;padding:7px 10px;border:1px solid var(--border-light);border-radius:5px;background:var(--bg-card);color:var(--text-primary);font:inherit;font-size:13px}.allocation-desk{background:var(--bg-card);padding:18px 16px;min-width:0}.detail-head{justify-content:space-between}.detail-head h2{font-size:18px;margin:0}.detail-head p,.cell-sub{font-size:12px;color:var(--text-secondary);margin:6px 0;display:block}.process-steps{display:flex;list-style:none;padding:0;margin:20px 0 0;border-bottom:1px solid var(--border-light);overflow:auto}.process-steps li{flex:1;white-space:nowrap;padding:10px 16px;color:var(--text-secondary);font-size:13px;border-bottom:2px solid transparent}.process-steps li.done{color:var(--primary-600);border-bottom-color:var(--primary-500)}.summary-line{padding:16px 0;gap:24px;color:var(--text-secondary);font-size:13px;border-bottom:1px solid var(--border-light)}.summary-line strong{font-size:20px;color:var(--text-primary);margin-left:8px;font-variant-numeric:tabular-nums}.desk-toolbar{padding:14px 0}.desk-toolbar .search{width:200px}.desk-toolbar .actions{margin-left:auto}.empty{padding:36px 0;color:var(--text-secondary);font-size:13px}.allocation-error,.danger-text{color:var(--danger-600,#c2413b)}.allocation-error,.allocation-warning{font-size:13px;line-height:1.7}.allocation-warning{color:var(--warning-700,#946315);margin:12px 0}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.form-grid label{display:flex;flex-direction:column;gap:7px;font-size:13px}.form-grid .sa-input{width:100%}.block-title{font-size:13px;font-weight:600;margin:24px 0 12px}.check-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.check-grid label{font-size:13px}.check-grid small{display:block;color:var(--text-secondary);margin:5px 0 0 22px}.rule-row{font-size:13px;margin-bottom:24px}.bed-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:20px}.bed-option{display:flex;flex-direction:column;gap:8px;padding:14px;background:var(--bg-card);color:var(--text-primary);border:1px solid var(--border-light);border-radius:5px;text-align:left;cursor:pointer}.bed-option span{font-size:12px;color:var(--text-secondary)}.bed-option.selected{border-color:var(--primary-500);background:var(--primary-50)}.bed-option:disabled{opacity:.45;cursor:not-allowed}button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--primary-500);outline-offset:2px}
@media(max-width:700px){.form-grid,.check-grid{grid-template-columns:1fr}.process-steps li{padding:8px}.summary-line{gap:14px}.desk-toolbar .actions{margin-left:0}.plan-switcher label:first-child{flex-basis:100%}.allocation-desk{padding:12px 0}.bed-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
