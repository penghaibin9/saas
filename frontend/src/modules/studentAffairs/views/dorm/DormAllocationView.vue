<template>
  <AppPageShell
    title="分配计划"
    subtitle="按批次冻结学生范围与床位资源池，先 Dry Run 核对异常，再发布自动、人工或学生自选计划。"
    role-name="学工处 / 宿舍管理"
    data-scope-name="学生范围 + 楼栋范围"
    watermark-purpose="住宿分配计划"
  >
    <template #actions>
      <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" variant="secondary" @click="showCreate = !showCreate">
        {{ showCreate ? '收起新建' : '新建分配批次' }}
      </AppPermissionButton>
      <AppPermissionButton :allowed="canView" code="studentAffairs.dorm.view" variant="secondary" :loading="loading" @click="load">刷新</AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载住宿分配批次…" @retry="load" @back="$router.push('/admin/student-affairs/dormitory')">
      <AppInlineAlert type="info" title="发布前校验" description="强制执行性别与房态兼容、一人一床、同批次床位唯一和时间窗重叠检查；不允许民族、籍贯、宗教等敏感分寝规则。" />

      <AppSectionCard v-if="showCreate" title="新建草稿批次">
        <div class="form-grid">
          <label><span>批次编号</span><input v-model.trim="form.batchNo" class="sa-input" maxlength="100" /></label>
          <label><span>批次名称</span><input v-model.trim="form.name" class="sa-input" maxlength="200" placeholder="例：2026 级新生住宿分配" /></label>
          <label><span>学年</span><input v-model.trim="form.academicYear" class="sa-input" maxlength="20" /></label>
          <label><span>关联迎新批次</span><select v-model="form.orientationBatchId" class="sa-input"><option value="">请选择</option><option v-for="row in orientationBatches" :key="row.id || row.batchId" :value="row.id || row.batchId">{{ row.name || row.batchName || row.batchNo }}（ID {{ row.id || row.batchId }}）</option></select></label>
          <label><span>分配模式</span><select v-model="form.mode" class="sa-input"><option value="ADMIN_AUTO">管理员自动分配</option><option value="ADMIN_MANUAL">管理员人工分配</option><option value="STUDENT_SELECT">学生在时间窗内自选</option><option value="POST_CHECKIN_PUBLISH">现场报到后公布</option></select></label>
          <label><span>开放时间</span><input v-model="form.openAt" type="datetime-local" class="sa-input" /></label>
          <label><span>关闭时间</span><input v-model="form.closeAt" type="datetime-local" class="sa-input" /></label>
        </div>
        <div class="block-title">资源池（发布时冻结为精确床位 ID）</div>
        <div class="check-grid">
          <label v-for="building in buildings" :key="building.buildingId"><input v-model="form.buildingIds" type="checkbox" :value="String(building.buildingId)" /> <strong>{{ building.buildingName }}</strong><small>空床 {{ building.vacantBeds ?? '—' }} / {{ building.totalBeds ?? '—' }}</small></label>
        </div>
        <div class="block-title">软规则（仅用于排序与优化）</div>
        <div class="rule-row"><label><input v-model="form.rules.sameCollege" type="checkbox" /> 学院尽量相近</label><label><input v-model="form.rules.sameMajor" type="checkbox" /> 专业尽量相近</label><label><input v-model="form.rules.sameClass" type="checkbox" /> 班级尽量相近</label><label><input v-model="form.rules.minimizeVacancy" type="checkbox" /> 减少零散空床</label><label><input v-model="form.rules.balanceFloor" type="checkbox" /> 平衡楼层</label></div>
        <div class="actions"><AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" :loading="actioning" :disabled="!createValid" @click="createBatch">保存草稿</AppPermissionButton></div>
      </AppSectionCard>

      <div class="workspace">
        <AppSectionCard title="分配批次">
          <div class="filter-row"><select v-model="statusFilter" class="sa-input" @change="load"><option value="">全部状态</option><option value="DRAFT">草稿</option><option value="PUBLISHED">已发布</option><option value="CLOSED">已关闭</option></select></div>
          <button v-for="row in batches" :key="row.batchId" class="batch-row" :class="{ active: selectedId === row.batchId }" @click="selectBatch(row)"><span><strong>{{ row.name }}</strong><small>{{ row.batchNo }} · {{ modeLabel(row.mode) }}</small></span><AppStatusTag :type="row.status === 'PUBLISHED' ? 'success' : 'default'" :label="statusLabel(row.status)" /></button>
          <p v-if="!batches.length" class="sa-empty">当前范围暂无分配批次。</p>
        </AppSectionCard>

        <AppSectionCard title="批次核对与发布">
          <p v-if="!detail" class="sa-empty">请从左侧选择批次。</p>
          <template v-else>
            <div class="detail-head"><div><strong>{{ detail.batch.name }}</strong><p>{{ modeLabel(detail.batch.mode) }} · {{ fmt(detail.batch.openAt) }} 至 {{ fmt(detail.batch.closeAt) }}</p></div><AppStatusTag :label="statusLabel(detail.batch.status)" /></div>
            <div v-if="drySummary" class="metrics"><div><strong>{{ drySummary.totalStudents }}</strong><span>范围学生</span></div><div><strong>{{ drySummary.proposed }}</strong><span>可分配</span></div><div><strong>{{ drySummary.unassigned }}</strong><span>异常/未分配</span></div><div><strong>{{ drySummary.availableBeds }}</strong><span>资源池床位</span></div></div>
            <div class="actions" v-if="detail.batch.status === 'DRAFT'">
              <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="dryRun">Dry Run</AppPermissionButton>
              <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" variant="secondary" :loading="actioning" @click="downloadConflicts">下载异常行.xlsx</AppPermissionButton>
              <AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" :loading="actioning" @click="publishBatch">核对并发布</AppPermissionButton>
            </div>
            <div v-if="detail.batch.status === 'DRAFT' && detail.batch.mode === 'ADMIN_MANUAL'" class="manual-row"><input v-model.trim="manual.studentId" class="sa-input" placeholder="学生稳定 ID" /><input v-model.trim="manual.bedId" class="sa-input" placeholder="床位稳定 ID" /><AppPermissionButton :allowed="canManage" code="studentAffairs.dorm.allocation.manage" variant="secondary" :disabled="!manual.studentId || !manual.bedId" :loading="actioning" @click="manualAssign">保存人工提议</AppPermissionButton></div>
            <DataTable :columns="columns" :rows="detail.items || []" row-key="itemId"><template #cell-student="{ row }"><strong>{{ row.studentName }}</strong><small class="cell-sub">{{ row.studentNo }} · ID {{ row.studentId }}</small></template><template #cell-status="{ row }"><AppStatusTag :type="row.status === 'CONFLICT' ? 'danger' : (['RESERVED','CONFIRMED'].includes(row.status) ? 'success' : 'default')" :label="itemStatusLabel(row.status)" /></template><template #cell-bed="{ row }"><span>{{ row.bedLabel || '—' }}</span><small v-if="row.bedId" class="cell-sub">ID {{ row.bedId }}</small></template><template #cell-conflict="{ row }"><span :class="row.conflictCode ? 'danger-text' : 'sa-muted'">{{ row.conflictCode || '—' }}</span></template></DataTable>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>
    <AppConfirmDialog
      v-model:visible="publishConfirm.visible"
      title="确认发布住宿分配批次"
      type="warning"
      message="发布后学生范围与精确床位资源池将冻结；学生确认后如需变更，必须走正式调宿流程。"
      confirm-text="确认发布"
      :submitting="actioning"
      @confirm="confirmPublishBatch"
    />
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { getOrientationBatches } from '@/modules/orientation/api/orientation.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

function localInput(date) { const value = new Date(date.getTime() - date.getTimezoneOffset() * 60000); return value.toISOString().slice(0, 16) }
function initialForm() { const now = new Date(); const close = new Date(now.getTime() + 7 * 86400000); const year = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1; return { batchNo: `DORM-${now.toISOString().slice(0,10).replaceAll('-', '')}-${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`, name: '', academicYear: `${year}-${year + 1}`, sourceType: 'ORIENTATION', orientationBatchId: '', mode: 'ADMIN_AUTO', openAt: localInput(now), closeAt: localInput(close), buildingIds: [], rules: { sameCollege: true, sameMajor: true, sameClass: false, minimizeVacancy: true, balanceFloor: false } } }

export default {
  name: 'DormAllocationView',
  props: { ctx: { type: Object, default: null } },
  components: { AppConfirmDialog, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag, DataTable },
  data() { return { loading: true, actioning: false, errorMessage: '', showCreate: false, statusFilter: '', batches: [], buildings: [], orientationBatches: [], selectedId: '', detail: null, drySummary: null, publishConfirm: { visible: false }, form: initialForm(), manual: { studentId: '', bedId: '' }, columns: [{ key: 'student', title: '学生' }, { key: 'status', title: '分配状态' }, { key: 'bed', title: '床位' }, { key: 'conflict', title: '异常码' }] } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    canView() { return canCode(this.ctx, 'studentAffairs.dorm.view') },
    canManage() { return canCode(this.ctx, 'studentAffairs.dorm.allocation.manage') },
    createValid() { return !!(this.form.batchNo && this.form.name && this.form.academicYear && this.form.orientationBatchId && this.form.openAt && this.form.closeAt && this.form.openAt < this.form.closeAt && this.form.buildingIds.length) }
  },
  mounted() { this.load() },
  methods: {
    unwrap(res) { if (!res || res.code !== 0) throw new Error(res?.message || '操作失败'); return res.data },
    fmt(value) { return String(value || '').slice(0, 16).replace('T', ' ') },
    modeLabel(value) { return ({ ADMIN_AUTO: '管理员自动', ADMIN_MANUAL: '管理员人工', STUDENT_SELECT: '学生自选', POST_CHECKIN_PUBLISH: '报到后公布' })[value] || (value ? '待确认' : '—') },
    statusLabel(value) { return ({ DRAFT: '草稿', PUBLISHED: '已发布', CLOSED: '已关闭', CANCELLED: '已取消' })[value] || (value ? '待确认' : '—') },
    itemStatusLabel(value) { return ({ PENDING: '待学生选床', PROPOSED: '待发布', RESERVED: '已预留', CONFIRMED: '学生已确认', CONFLICT: '异常', CANCELLED: '已取消' })[value] || (value ? '待确认' : '—') },
    async load() { this.loading = true; this.errorMessage = ''; try { const [batchRes, buildingRes, oriRes] = await Promise.all([studentAffairsApi.listDormAllocationBatches({ status: this.statusFilter, pageSize: 200 }), studentAffairsApi.getBuildings({ pageSize: 200 }), getOrientationBatches({ page: 1, pageSize: 200 })]); this.batches = this.unwrap(batchRes).items || []; this.buildings = this.unwrap(buildingRes).items || []; if (oriRes.code !== 0) throw new Error(oriRes.message); this.orientationBatches = oriRes.data?.list || []; if (this.selectedId) await this.loadDetail(this.selectedId) } catch (e) { this.errorMessage = e.message || '加载失败' } finally { this.loading = false } },
    async selectBatch(row) { this.selectedId = row.batchId; this.drySummary = row.rules?._dryRun || null; await this.loadDetail(row.batchId) },
    async loadDetail(id) { try { this.detail = this.unwrap(await studentAffairsApi.getDormAllocationBatch(id)); this.drySummary = this.detail.batch.rules?._dryRun || this.drySummary } catch (e) { this.errorMessage = e.message } },
    async act(task, after) { this.actioning = true; this.errorMessage = ''; try { const data = this.unwrap(await task()); if (after) await after(data); return data } catch (e) { this.errorMessage = e.message || '操作失败'; return null } finally { this.actioning = false } },
    async createBatch() { if (!this.createValid) return; const payload = { ...this.form, resourceScope: { buildingIds: this.form.buildingIds.map(Number) }, studentScope: {}, rules: { ...this.form.rules } }; delete payload.buildingIds; await this.act(() => studentAffairsApi.createDormAllocationBatch(payload), async (row) => { this.form = initialForm(); this.showCreate = false; this.selectedId = row.batchId; await this.load() }) },
    async dryRun() { await this.act(() => studentAffairsApi.dryRunDormAllocation(this.selectedId), async (data) => { this.drySummary = data.summary; await this.loadDetail(this.selectedId) }) },
    async manualAssign() { await this.act(() => studentAffairsApi.manualAssignDorm(this.selectedId, this.manual.studentId, this.manual.bedId), async () => { this.manual = { studentId: '', bedId: '' }; await this.loadDetail(this.selectedId) }) },
    publishBatch() { this.publishConfirm.visible = true },
    async confirmPublishBatch() { const data = await this.act(() => studentAffairsApi.publishDormAllocation(this.selectedId), async () => { await this.load() }); if (data) this.publishConfirm.visible = false },
    async downloadConflicts() { await this.act(() => studentAffairsApi.downloadDormAllocationConflicts(this.selectedId)) }
  }
}
</script>

<style scoped>
.form-grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px }.form-grid label span,.block-title { display:block;font-size:12px;color:#64748b;margin-bottom:5px }.sa-input { width:100%;min-height:38px;box-sizing:border-box;border:1px solid #dbe2ea;border-radius:8px;padding:7px 10px;background:#fff }.block-title { margin-top:16px;font-weight:650;color:#334155 }.check-grid { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px }.check-grid label { padding:10px;border:1px solid #e2e8f0;border-radius:9px }.check-grid small,.cell-sub { display:block;color:#64748b;font-size:11px;margin-top:3px }.rule-row,.actions,.filter-row,.manual-row { display:flex;gap:10px;flex-wrap:wrap;align-items:center }.rule-row label { font-size:13px }.actions { margin-top:16px }.workspace { display:grid;grid-template-columns:minmax(260px,0.72fr) minmax(0,1.8fr);gap:16px;margin-top:16px;align-items:start }.batch-row { width:100%;display:flex;justify-content:space-between;align-items:center;gap:10px;border:0;border-bottom:1px solid #edf0f4;background:transparent;text-align:left;padding:12px 8px;cursor:pointer }.batch-row.active { background:#eff6ff;border-radius:8px }.batch-row span,.batch-row small { display:block }.detail-head { display:flex;justify-content:space-between;gap:12px }.detail-head p { margin:5px 0;color:#64748b;font-size:12px }.metrics { display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0 }.metrics div { padding:12px;background:#f8fafc;border-radius:9px }.metrics strong,.metrics span { display:block }.metrics strong { font-size:20px }.metrics span { color:#64748b;font-size:12px;margin-top:4px }.manual-row { margin:14px 0;padding:12px;background:#f8fafc;border-radius:9px }.manual-row .sa-input { width:180px }.danger-text { color:#dc2626;font-weight:600 }
@media(max-width:900px){.form-grid,.workspace,.check-grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}}
</style>
