<template>
  <ModulePageShell
    title="校历节次 · 作息时间"
    subtitle="配置每天的上课节次、启用停用与实际钟点（上课时间段），供排课与课表使用（全校统一）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <!-- 页签 -->
      <nav class="aa-tabs">
        <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }"
                @click="switchTab(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 节次管理 -->
      <template v-if="tab === 'periods'">
        <AppSectionCard title="新增节次">
          <div class="aa-slot-form">
            <label class="aa-slot-form__item">
              第几节
              <AppNumberInput v-model="draft.slotNo" :min="1" :max="20" placeholder="如 1" />
            </label>
            <label class="aa-slot-form__item">
              名称
              <AppTextInput v-model="draft.slotName" placeholder="选填，如 第一大节" :maxlength="30" />
            </label>
            <label class="aa-slot-form__item">
              开始时间
              <AppTimePicker v-model="draft.startTime" />
            </label>
            <label class="aa-slot-form__item">
              结束时间
              <AppTimePicker v-model="draft.endTime" />
            </label>
            <AppButton variant="primary" :loading="adding" @click="addSlot">添加节次</AppButton>
          </div>
          <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        </AppSectionCard>

        <AppSectionCard title="节次列表">
          <template #header-extra>
            <label class="aa-check">
              <input type="checkbox" v-model="includeDisabled" @change="load" />
              显示已停用
            </label>
          </template>
          <ErrorState v-if="error" :description="error" @retry="load" />
          <LoadingState v-else-if="loading" />
          <EmptyState v-else-if="!rows.length" title="尚未配置节次" description="用上方表单添加第 1 节、第 2 节…及其上课时间" />
          <DataTable v-else :columns="slotColumns" :rows="rows" row-key="slotId">
            <template #cell-slotNo="{ row }">第 {{ row.slotNo }} 节</template>
            <template #cell-status="{ row }">
              <StatusTag :status="row.status" />
            </template>
            <template #cell-actions="{ row }">
              <button class="mp-link" @click="openEdit(row)">编辑</button>
              <button class="mp-link" @click="toggleEnabled(row)">{{ row.enabled ? '停用' : '启用' }}</button>
              <button class="mp-link aa-danger" @click="confirmDelete(row)">删除</button>
            </template>
          </DataTable>
        </AppSectionCard>

        <p class="mp-note">节次为全校统一配置，供「排课 / 课表」的周历网格使用；每个节次可在「上课时间段」页配置多套按校区/生效日期区间的实际钟点（如夏令/冬令作息）。</p>
      </template>

      <!-- 上课时间段 -->
      <template v-else>
        <AppSectionCard title="选择节次">
          <div class="aa-slot-form">
            <label class="aa-slot-form__item aa-slot-form__item--grow">
              节次
              <AppTimeSlotPicker v-model="bandSlotId" :options="slotOptions" :query="{ includeDisabled: true }" placeholder="请选择节次" @change="loadBands" />
            </label>
          </div>
        </AppSectionCard>

        <EmptyState v-if="!bandSlotId" title="请先选择节次" description="上课时间段绑定某个节次的实际上课钟点" />
        <template v-else>
          <AppSectionCard title="新增上课时间段">
            <div class="aa-slot-form">
              <label class="aa-slot-form__item">
                名称
                <AppTextInput v-model="bandDraft.bandName" placeholder="选填，如 夏季作息" :maxlength="50" />
              </label>
              <label class="aa-slot-form__item">
                校区
                <AppTextInput v-model="bandDraft.campusCode" placeholder="选填，多校区预留" :maxlength="50" />
              </label>
              <label class="aa-slot-form__item">
                生效开始
                <AppDatePicker v-model="bandDraft.effectiveStart" />
              </label>
              <label class="aa-slot-form__item">
                生效结束
                <AppDatePicker v-model="bandDraft.effectiveEnd" />
              </label>
              <label class="aa-slot-form__item">
                开始时间
                <AppTimePicker v-model="bandDraft.startTime" />
              </label>
              <label class="aa-slot-form__item">
                结束时间
                <AppTimePicker v-model="bandDraft.endTime" />
              </label>
              <AppButton variant="primary" :loading="bandAdding" @click="addBand">添加时间段</AppButton>
            </div>
            <AppInlineAlert v-if="bandFormError" type="danger" :description="bandFormError" />
          </AppSectionCard>

          <AppSectionCard title="上课时间段列表">
            <ErrorState v-if="bandError" :description="bandError" @retry="loadBands" />
            <LoadingState v-else-if="bandLoading" />
            <EmptyState v-else-if="!bandRows.length" title="该节次尚未配置上课时间段" description="用上方表单添加，可按校区/生效日期区间配置多套作息" />
            <DataTable v-else :columns="bandColumns" :rows="bandRows" row-key="bandId">
              <template #cell-effective="{ row }">
                {{ row.effectiveStart || '不限' }} ~ {{ row.effectiveEnd || '不限' }}
              </template>
              <template #cell-status="{ row }">
                <StatusTag :status="row.status" />
              </template>
              <template #cell-actions="{ row }">
                <button class="mp-link" @click="openEditBand(row)">编辑</button>
                <button class="mp-link" @click="toggleBandStatus(row)">{{ row.status === 'ENABLED' ? '停用' : '启用' }}</button>
                <button class="mp-link aa-danger" @click="confirmDeleteBand(row)">删除</button>
              </template>
            </DataTable>
          </AppSectionCard>
        </template>
      </template>
    </div>

    <!-- 编辑节次 -->
    <AppDrawer :visible="editVisible" title="编辑节次" mode="modal" size="medium" @close="editVisible = false">
      <div class="aa-cal-form--drawer" v-if="editForm">
        <AppFormItem label="第几节" required>
          <AppNumberInput v-model="editForm.slotNo" :min="1" />
        </AppFormItem>
        <AppFormItem label="名称"><AppTextInput v-model="editForm.slotName" :maxlength="30" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTimePicker v-model="editForm.startTime" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTimePicker v-model="editForm.endTime" /></AppFormItem>
        <AppInlineAlert v-if="editError" type="danger" :description="editError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="editVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitEdit">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 编辑上课时间段 -->
    <AppDrawer :visible="editBandVisible" title="编辑上课时间段" mode="modal" size="large" @close="editBandVisible = false">
      <div class="aa-cal-form--drawer" v-if="editBandForm">
        <AppFormItem label="名称"><AppTextInput v-model="editBandForm.bandName" :maxlength="50" /></AppFormItem>
        <AppFormItem label="校区"><AppTextInput v-model="editBandForm.campusCode" :maxlength="50" /></AppFormItem>
        <AppFormItem label="生效开始"><AppDatePicker v-model="editBandForm.effectiveStart" /></AppFormItem>
        <AppFormItem label="生效结束"><AppDatePicker v-model="editBandForm.effectiveEnd" /></AppFormItem>
        <AppFormItem label="开始时间" required><AppTimePicker v-model="editBandForm.startTime" /></AppFormItem>
        <AppFormItem label="结束时间" required><AppTimePicker v-model="editBandForm.endTime" /></AppFormItem>
        <AppInlineAlert v-if="editBandError" type="danger" :description="editBandError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="bandSaving" @click="editBandVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="bandSaving" @click="submitEditBand">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" title="删除节次"
                      message="删除后不可恢复，确认删除该节次？" type="danger" @confirm="doDelete" />
    <AppConfirmDialog v-model:visible="confirmBandVisible" title="删除上课时间段"
                      message="删除后不可恢复，确认删除该时间段？" type="danger" @confirm="doDeleteBand" />
  </ModulePageShell>
</template>

<script>
/** 校历节次 · 作息时间（/admin/academic-affairs/time-slots，?tab=bands）：
 * 节次管理=t_aa_time_slot 全 CRUD（含启用/停用）；上课时间段=t_aa_class_time_band（节次的实际钟点，
 * 按校区/生效日期区间可配多套，如夏令/冬令作息）。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppSectionCard, AppTextInput, AppNumberInput, AppFormItem, AppDatePicker, AppTimePicker, AppConfirmDialog, AppInlineAlert, AppTimeSlotPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const HHMM_RE = /^([01]\d|2[0-3]):[0-5]\d$/

export default {
  name: 'AaTimeSlotView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppSectionCard, AppTextInput, AppNumberInput, AppFormItem, AppDatePicker, AppTimePicker, AppTimeSlotPicker,
    AppConfirmDialog, AppInlineAlert
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'periods',
      tabs: [{ key: 'periods', label: '节次管理' }, { key: 'bands', label: '上课时间段' }],
      slotColumns: [
        { key: 'slotNo', title: '节次' }, { key: 'slotName', title: '名称' },
        { key: 'startTime', title: '开始' }, { key: 'endTime', title: '结束' },
        { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }
      ],
      bandColumns: [
        { key: 'bandName', title: '名称' }, { key: 'campusCode', title: '校区' },
        { key: 'effective', title: '生效区间' }, { key: 'startTime', title: '开始' },
        { key: 'endTime', title: '结束' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }
      ],
      loading: true,
      error: '',
      rows: [],
      includeDisabled: false,
      adding: false,
      formError: '',
      draft: { slotNo: null, slotName: '', startTime: '', endTime: '' },
      editVisible: false,
      editForm: null,
      editError: '',
      saving: false,
      confirmVisible: false,
      pendingDelete: null,
      // 上课时间段
      bandSlotId: '',
      bandLoading: false,
      bandError: '',
      bandRows: [],
      bandAdding: false,
      bandFormError: '',
      bandDraft: { bandName: '', campusCode: '', effectiveStart: '', effectiveEnd: '', startTime: '', endTime: '' },
      editBandVisible: false,
      editBandForm: null,
      editBandError: '',
      bandSaving: false,
      confirmBandVisible: false,
      pendingDeleteBand: null
    }
  },
  computed: {
    slotOptions() {
      return this.rows.map((s) => ({ value: s.slotId, label: `第 ${s.slotNo} 节${s.slotName ? ' · ' + s.slotName : ''}` }))
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q === 'bands') this.tab = 'bands'
    this.includeDisabled = this.tab === 'bands' // 上课时间段选节次需覆盖全部（含已停用）
    this.load()
  },
  methods: {
    switchTab(key) {
      if (this.tab === key) return
      this.tab = key
      if (key === 'bands') { this.includeDisabled = true; this.load() }
    },
    validate(d) {
      if (!d.slotNo || d.slotNo < 1) return '请填写有效的节次序号（≥1）'
      if (d.startTime && !HHMM_RE.test(d.startTime)) return '开始时间格式应为 HH:MM，如 08:00'
      if (d.endTime && !HHMM_RE.test(d.endTime)) return '结束时间格式应为 HH:MM，如 08:45'
      if (d.startTime && d.endTime && d.startTime >= d.endTime) return '结束时间应晚于开始时间'
      return ''
    },
    async addSlot() {
      if (this.adding) return
      const err = this.validate(this.draft)
      this.formError = err
      if (err) return
      this.adding = true
      const body = {
        slotNo: Number(this.draft.slotNo),
        slotName: this.draft.slotName || undefined,
        startTime: this.draft.startTime || undefined,
        endTime: this.draft.endTime || undefined
      }
      const res = await academicAffairsApi.createTimeSlot(body)
      this.adding = false
      if (res.code === 0) {
        toast.success(`已添加第 ${body.slotNo} 节`)
        this.draft = { slotNo: null, slotName: '', startTime: '', endTime: '' }
        this.load()
      } else {
        this.formError = res.message || '添加失败'
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTimeSlots(this.includeDisabled)
      if (res.code === 0) {
        this.rows = res.data || []
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    openEdit(row) {
      this.editForm = { slotId: row.slotId, slotNo: row.slotNo, slotName: row.slotName || '',
        startTime: row.startTime || '', endTime: row.endTime || '', enabled: row.enabled }
      this.editError = ''
      this.editVisible = true
    },
    async submitEdit() {
      if (this.saving || !this.editForm) return
      const err = this.validate(this.editForm)
      if (err) { this.editError = err; return }
      this.saving = true
      const res = await academicAffairsApi.updateTimeSlot(this.editForm.slotId, {
        slotNo: Number(this.editForm.slotNo), slotName: this.editForm.slotName || undefined,
        startTime: this.editForm.startTime || undefined, endTime: this.editForm.endTime || undefined
      })
      this.saving = false
      if (res.code === 0) {
        toast.success('已保存')
        this.editVisible = false
        this.load()
      } else {
        this.editError = res.message || '保存失败'
      }
    },
    async toggleEnabled(row) {
      const res = await academicAffairsApi.updateTimeSlot(row.slotId, { enabled: !row.enabled })
      if (res.code === 0) {
        toast.success(row.enabled ? '已停用' : '已启用')
        this.load()
      } else {
        toast.error(res.message || '操作失败')
      }
    },
    confirmDelete(row) {
      this.pendingDelete = row
      this.confirmVisible = true
    },
    async doDelete() {
      if (!this.pendingDelete) return
      const res = await academicAffairsApi.deleteTimeSlot(this.pendingDelete.slotId)
      if (res.code === 0) {
        toast.success('已删除')
        this.load()
        if (this.bandSlotId === this.pendingDelete.slotId) { this.bandSlotId = ''; this.bandRows = [] }
      } else {
        toast.error(res.message || '删除失败')
      }
      this.pendingDelete = null
    },
    // ── 上课时间段 ──
    validateBand(d) {
      if (!d.startTime || !d.endTime) return '开始时间与结束时间必填'
      if (!HHMM_RE.test(d.startTime) || !HHMM_RE.test(d.endTime)) return '时间格式应为 HH:MM，如 08:00'
      if (d.startTime >= d.endTime) return '结束时间应晚于开始时间'
      return ''
    },
    async loadBands() {
      if (!this.bandSlotId) { this.bandRows = []; return }
      this.bandLoading = true
      this.bandError = ''
      const res = await academicAffairsApi.getTimeBands(this.bandSlotId)
      if (res.code === 0) {
        this.bandRows = res.data || []
      } else {
        this.bandError = res.message
      }
      this.bandLoading = false
    },
    async addBand() {
      if (this.bandAdding || !this.bandSlotId) return
      const err = this.validateBand(this.bandDraft)
      this.bandFormError = err
      if (err) return
      this.bandAdding = true
      const body = {
        bandName: this.bandDraft.bandName || undefined,
        campusCode: this.bandDraft.campusCode || undefined,
        effectiveStart: this.bandDraft.effectiveStart || undefined,
        effectiveEnd: this.bandDraft.effectiveEnd || undefined,
        startTime: this.bandDraft.startTime, endTime: this.bandDraft.endTime
      }
      const res = await academicAffairsApi.createTimeBand(this.bandSlotId, body)
      this.bandAdding = false
      if (res.code === 0) {
        toast.success('已添加')
        this.bandDraft = { bandName: '', campusCode: '', effectiveStart: '', effectiveEnd: '', startTime: '', endTime: '' }
        this.loadBands()
      } else {
        this.bandFormError = res.message || '添加失败'
      }
    },
    openEditBand(row) {
      this.editBandForm = { bandId: row.bandId, bandName: row.bandName || '', campusCode: row.campusCode || '',
        effectiveStart: row.effectiveStart || '', effectiveEnd: row.effectiveEnd || '',
        startTime: row.startTime || '', endTime: row.endTime || '' }
      this.editBandError = ''
      this.editBandVisible = true
    },
    async submitEditBand() {
      if (this.bandSaving || !this.editBandForm) return
      const err = this.validateBand(this.editBandForm)
      if (err) { this.editBandError = err; return }
      this.bandSaving = true
      const res = await academicAffairsApi.updateTimeBand(this.editBandForm.bandId, {
        bandName: this.editBandForm.bandName || undefined, campusCode: this.editBandForm.campusCode || undefined,
        effectiveStart: this.editBandForm.effectiveStart || undefined, effectiveEnd: this.editBandForm.effectiveEnd || undefined,
        startTime: this.editBandForm.startTime, endTime: this.editBandForm.endTime
      })
      this.bandSaving = false
      if (res.code === 0) {
        toast.success('已保存')
        this.editBandVisible = false
        this.loadBands()
      } else {
        this.editBandError = res.message || '保存失败'
      }
    },
    async toggleBandStatus(row) {
      const res = await academicAffairsApi.updateTimeBand(row.bandId, { status: row.status === 'ENABLED' ? 'DISABLED' : 'ENABLED' })
      if (res.code === 0) {
        toast.success('已更新')
        this.loadBands()
      } else {
        toast.error(res.message || '操作失败')
      }
    },
    confirmDeleteBand(row) {
      this.pendingDeleteBand = row
      this.confirmBandVisible = true
    },
    async doDeleteBand() {
      if (!this.pendingDeleteBand) return
      const res = await academicAffairsApi.deleteTimeBand(this.pendingDeleteBand.bandId)
      if (res.code === 0) {
        toast.success('已删除')
        this.loadBands()
      } else {
        toast.error(res.message || '删除失败')
      }
      this.pendingDeleteBand = null
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); flex-wrap: wrap; }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aa-slot-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-slot-form__item {
  display: inline-flex; flex-direction: column; gap: 6px;
  font-size: 13px; color: var(--text-700, #4e5969);
}
.aa-slot-form__item--grow { flex: 1; min-width: 220px; }
.aa-input {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
  box-sizing: border-box;
}
.aa-input--num { width: 120px; }
.aa-check { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form--drawer { display: flex; flex-direction: column; gap: 12px; }
.mp-link.aa-danger { color: var(--danger-600, #f53f3f); }
</style>
