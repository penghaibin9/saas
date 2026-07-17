<template>
  <ModulePageShell
    title="专业分流 · 教务处控制台"
    :subtitle="'大类招生分流：配置可选专业 → 学生填志愿 → 绩点排序自动分配 → 人工调剂 → 确认写学籍'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建分流批次</AppButton>
    </template>

    <div class="aams-layout">
      <div class="aams-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无分流批次" description="为大类年级新建分流批次" />
        <ul v-else class="aams-batches">
          <li v-for="b in rows" :key="b.batchId"
              :class="['aams-batch', { 'is-active': current && current.batchId === b.batchId }]"
              @click="select(b)">
            <div>
              <div class="aams-batch-name">{{ b.batchName }}</div>
              <div class="mp-cell-sub">{{ b.grade }} 级 · 至多 {{ b.maxChoices }} 志愿</div>
            </div>
            <StatusTag :type="stType(b.status)" :label="stLabel(b.status)" dot />
          </li>
        </ul>
      </div>

      <div class="aams-detail">
        <EmptyState v-if="!current" title="选择一个批次" description="从左侧选择分流批次" />
        <template v-else>
          <div class="aams-head">
            <div>
              <div class="aams-title">{{ current.batchName }}</div>
              <StatusTag :type="stType(current.status)" :label="stLabel(current.status)" dot />
            </div>
            <div class="aams-actions">
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openAddOption">+ 可选专业</AppButton>
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="act('open', '开放志愿填报')">开放填报</AppButton>
              <AppButton v-if="current.status === 'OPEN'" size="small" variant="warning" @click="act('close', '截止志愿')">截止</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" size="small" variant="ghost" @click="allocate(true)">试分预览</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" size="small" variant="primary" @click="allocateConfirm">自动分配</AppButton>
              <AppButton v-if="current.status === 'ALLOCATED'" size="small" variant="primary" @click="act('confirm', '确认分流（写学籍专业）')">确认分流</AppButton>
            </div>
          </div>

          <div class="aams-section-title">可选专业与容量</div>
          <EmptyState v-if="!options.length" title="未配置可选专业" description="草稿阶段添加专业与容量" />
          <DataTable v-else :columns="optionColumns" :rows="options" row-key="optionId">
            <template #cell-fill="{ row }">{{ row.allocatedCount }} / {{ row.capacity }}（余 {{ row.remain }}）</template>
          </DataTable>

          <AppInlineAlert v-if="allocPreview" type="info"
                          :description="'试分结果（未落库）：可分配 ' + allocPreview.allocated + ' 人，待调剂 ' + allocPreview.unallocated + ' 人'" />

          <div class="aams-section-title">志愿与分配结果</div>
          <EmptyState v-if="!volunteers.length" title="暂无志愿" description="开放填报后学生志愿显示在此" />
          <DataTable v-else :columns="volColumns" :rows="volunteers" row-key="volunteerId">
            <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）<span v-if="row.gpa != null" class="mp-cell-sub">绩点 {{ row.gpa }}</span></template>
            <template #cell-result="{ row }">
              <span v-if="row.status === 'UNALLOCATED'" class="aams-warn">待调剂</span>
              <span v-else-if="row.resultMajorId">{{ majorName(row.resultMajorId) }}<span class="mp-cell-sub">（{{ row.resultChoiceRank === 0 ? '调剂' : '第' + row.resultChoiceRank + '志愿' }}）</span></span>
              <span v-else>—</span>
            </template>
            <template #cell-status="{ row }"><StatusTag :type="volType(row.status)" :label="volLabel(row.status)" dot /></template>
            <template #cell-ops="{ row }">
              <button v-if="current.status === 'ALLOCATED' && row.status !== 'CONFIRMED'" class="mp-link" @click="openReassign(row)">调剂</button>
            </template>
          </DataTable>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建专业分流批次" @close="createVisible = false">
      <div class="aams-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024级电子信息大类分流" :disabled="saving" /></AppFormItem>
        <AppFormItem label="分流年级" required><AppTextInput v-model="form.grade" placeholder="如 2024" :disabled="saving" /></AppFormItem>
        <AppFormItem label="大类源专业 ID"><AppTextInput v-model="form.sourceMajorId" placeholder="选填；限定只有该大类学生可报" :disabled="saving" /></AppFormItem>
        <AppFormItem label="志愿数上限"><AppNumberInput v-model="form.maxChoices" :min="1" :max="10" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="optionVisible" title="添加可选专业" @close="optionVisible = false">
      <div class="aams-form">
        <AppFormItem label="专业" required><AppSelect v-model="optionForm.majorId" :options="majorOptions" :disabled="saving" /></AppFormItem>
        <AppFormItem label="容量" required><AppNumberInput v-model="optionForm.capacity" :min="1" :max="2000" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="optionError" type="danger" :description="optionError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="optionVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitOption">添加</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="reassignVisible" :title="'人工调剂 · ' + (reassignRow ? reassignRow.studentName : '')" @close="reassignVisible = false">
      <div class="aams-form">
        <AppFormItem label="目标专业" required>
          <AppSelect v-model="reassignForm.majorId" :options="options.map(o => ({ label: o.majorName + '（余 ' + o.remain + '）', value: o.majorId }))" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="调剂原因（≥5字）" required><AppTextarea v-model="reassignForm.reason" placeholder="如：第一志愿容量满，经与学生沟通同意调剂" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="reassignError" type="danger" :description="reassignError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="reassignVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitReassign">调剂</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 专业分流 · 教务处控制台（/admin/academic-affairs/major-split）：批次→可选专业→志愿→分配→调剂→确认。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect } from '@/components/common'
import { academicAffairsApi, academicAffairsOrgApi, academicAffairsMajorSplitApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', OPEN: '填报中', CLOSED: '已截止', ALLOCATED: '已分配', CONFIRMED: '已确认' }
const _VL = { PENDING: '待分配', ALLOCATED: '已分配', UNALLOCATED: '待调剂', CONFIRMED: '已确认' }

export default {
  name: 'AaMajorSplitView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem,
    AppConfirmDialog, AppInlineAlert, AppSelect
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], current: null, majorOptions: [],
      options: [], volunteers: [], allocPreview: null,
      optionColumns: [{ key: 'majorName', title: '专业' }, { key: 'fill', title: '容量使用' }],
      volColumns: [{ key: 'student', title: '学生' }, { key: 'result', title: '分配结果' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      createVisible: false, form: { batchName: '', grade: '', sourceMajorId: '', maxChoices: 3 }, formError: '',
      optionVisible: false, optionForm: { majorId: '', capacity: 50 }, optionError: '',
      reassignVisible: false, reassignRow: null, reassignForm: { majorId: '', reason: '' }, reassignError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
    const m = await academicAffairsOrgApi.listMajors({ pageSize: 500 })
    if (m.code === 0) this.majorOptions = (m.data.list || []).map((x) => ({ label: x.majorName, value: String(x.majorId) }))
  },
  methods: {
    stLabel(s) { return _L[s] || s },
    stType(s) { return s === 'OPEN' ? 'success' : s === 'CONFIRMED' ? 'default' : s === 'ALLOCATED' ? 'warning' : 'primary' },
    volLabel(s) { return _VL[s] || s },
    volType(s) { return s === 'ALLOCATED' || s === 'CONFIRMED' ? 'success' : s === 'UNALLOCATED' ? 'danger' : 'primary' },
    majorName(id) { const o = this.options.find((x) => String(x.majorId) === String(id)); return o ? o.majorName : id },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listBatches({ pageSize: 50 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    async select(b) { this.current = b; this.allocPreview = null; await this.refresh() },
    async refresh() {
      if (!this.current) return
      const [op, vo] = await Promise.all([
        api.listOptions(this.current.batchId),
        api.listVolunteers(this.current.batchId, { pageSize: 200 })
      ])
      this.options = op.code === 0 ? (op.data.items || []) : []
      this.volunteers = vo.code === 0 ? vo.data.list : []
    },
    openCreate() { this.form = { batchName: '', grade: '', sourceMajorId: '', maxChoices: 3 }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.batchName || !this.form.grade) { this.formError = '批次名称与年级必填'; return }
      this.saving = true
      const res = await api.createBatch({
        batchName: this.form.batchName, grade: this.form.grade,
        sourceMajorId: this.form.sourceMajorId || undefined, maxChoices: this.form.maxChoices
      })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; this.load() } else this.formError = res.message
    },
    openAddOption() { this.optionForm = { majorId: '', capacity: 50 }; this.optionError = ''; this.optionVisible = true },
    async submitOption() {
      if (!this.optionForm.majorId) { this.optionError = '专业必选'; return }
      this.saving = true
      const res = await api.addOption(this.current.batchId, { majorId: String(this.optionForm.majorId), capacity: this.optionForm.capacity })
      this.saving = false
      if (res.code === 0) { toast.success('已添加'); this.optionVisible = false; this.refresh() } else this.optionError = res.message
    },
    act(fn, label) {
      this.confirmTitle = label
      this.confirmMessage = `确认对「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](this.current.batchId)
        if (res.code === 0) { toast.success(res.message || label + '成功'); await this.load(); const cur = this.rows.find((r) => r.batchId === this.current.batchId); if (cur) await this.select(cur) }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    async allocate(dryRun) {
      const res = await api.allocate(this.current.batchId, dryRun)
      if (res.code !== 0) { toast.error(res.message); return }
      if (dryRun) { this.allocPreview = res.data; toast.info('试分完成（未落库）') }
      else { toast.success(res.message); await this.load(); const cur = this.rows.find((r) => r.batchId === this.current.batchId); if (cur) await this.select(cur) }
    },
    allocateConfirm() {
      this.confirmTitle = '自动分配'
      this.confirmMessage = '确认执行自动分配？按绩点降序×志愿顺序录取，志愿全满的学生标记待调剂。'
      this.pendingAction = () => this.allocate(false)
      this.confirmVisible = true
    },
    openReassign(row) { this.reassignRow = row; this.reassignForm = { majorId: '', reason: '' }; this.reassignError = ''; this.reassignVisible = true },
    async submitReassign() {
      if (!this.reassignForm.majorId) { this.reassignError = '目标专业必选'; return }
      if (!this.reassignForm.reason || this.reassignForm.reason.trim().length < 5) { this.reassignError = '调剂原因至少5字'; return }
      this.saving = true
      const res = await api.reassign(this.reassignRow.volunteerId, this.reassignForm.majorId, this.reassignForm.reason.trim())
      this.saving = false
      if (res.code === 0) { toast.success('已调剂'); this.reassignVisible = false; this.refresh() } else this.reassignError = res.message
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aams-layout { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
.aams-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aams-batch { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aams-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-light, #eff6ff); }
.aams-batch-name { font-weight: 500; font-size: 14px; }
.aams-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aams-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.aams-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aams-section-title { font-weight: 500; margin: 16px 0 8px; }
.aams-warn { color: var(--danger-color, #dc2626); font-weight: 600; }
.aams-form { display: flex; flex-direction: column; gap: 12px; }
</style>
