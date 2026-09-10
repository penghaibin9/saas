<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    :title="tab === 'bands' ? '上课时间段' : ['aa.calendar.time.slots.alias1', 'aa-terms:节次管理', 'aa-calendar:节次管理'].includes($route.query._workspace) ? '节次管理' : '作息时间'"
    subtitle="维护每天的节次与钟点，按校区和生效日期配置不同作息。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" :disabled="busy" @click="academicFlow?.back($route.query.returnToken, '/admin/academic-affairs/calendar')">返回原位置</AppButton>
      <AppButton v-if="tab === 'periods' && canManageSlots" variant="primary" :disabled="busy" @click="createSlotVisible = true">新增节次</AppButton>
    </template>
    <div class="mp-stack">
      <AppInlineAlert v-if="commandError" type="danger" :description="commandError" />
      <!-- 页签 -->
      <nav class="aa-tabs">
        <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }" :aria-current="tab === t.key ? 'page' : undefined" :disabled="busy"
                @click="switchTab(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 节次管理 -->
      <template v-if="tab === 'periods'">
        <div class="aa-slot-workspace"><main>
        <details v-if="canManageSlots" class="aa-slot-template">
          <summary>使用标准作息模板</summary>
          <AaTimeSlotTemplatePanel :disabled="adding || saving || actionBusy" @busy="templateApplying = $event" @applied="load" />
        </details>

        <AppDrawer v-if="canManageSlots" :visible="createSlotVisible" title="新增节次" mode="modal" size="medium" @close="createSlotVisible = false">
          <fieldset class="aa-slot-form" :disabled="busy">
            <label class="aa-slot-form__item">
              第几节
              <AppNumberInput v-model="draft.slotNo" :min="1" :step="1" placeholder="如 1" />
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
          </fieldset>
          <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        </AppDrawer>

        <AppSectionCard title="作息时间 · 按节次核对">
          <template #header-extra>
            <label class="aa-check">
              <input type="checkbox" v-model="includeDisabled" :disabled="busy" @change="load" />
              显示已停用
            </label>
          </template>
          <ErrorState v-if="error" :description="error" @retry="load" />
          <LoadingState v-else-if="loading" />
          <EmptyState v-else-if="!rows.length" title="暂无符合条件的节次" :description="canManageSlots ? '可显示已停用节次，或添加新的节次与上课时间。' : '学校尚未配置可查看的作息，请联系教务处。'" />
          <DataTable v-else :columns="slotColumns" :rows="rows" row-key="slotId">
            <template #cell-slotNo="{ row }">第 {{ row.slotNo }} 节</template>
            <template #cell-status="{ row }">
              <StatusTag :status="row.status" />
            </template>
            <template #cell-timeBandCount="{ row }">{{ row.timeBandCount }} 套</template>
            <template #cell-referenceStatus="{ row }">
              <StatusTag :type="row.referenceStatus === 'IN_USE' ? 'warning' : 'success'" :label="row.referenceStatus === 'IN_USE' ? `引用 ${row.referenceCount} 条` : '暂无引用'" dot />
            </template>
            <template #cell-actions="{ row }">
              <div class="aa-slot-actions">
              <button v-if="canViewBands" class="mp-link" :disabled="busy" @click="goBands(row)">时间段</button>
              <template v-if="canManageSlots">
                <button class="mp-link" :disabled="busy" @click="openEdit(row)">编辑</button>
                <button class="mp-link" :disabled="busy" @click="toggleEnabled(row)">{{ row.enabled ? '停用' : '启用' }}</button>
                <button class="mp-link aa-danger" :disabled="busy" @click="confirmDelete(row)">删除</button>
              </template>
              <span v-else-if="!canViewBands" class="mp-note">只读</span>
              </div>
            </template>
          </DataTable>
        </AppSectionCard>

        <p class="mp-note">节次用于排课和师生课表。已有业务引用的节次不能改号、停用或删除；夏令、冬令等钟点变化可在「上课时间段」按生效日期配置。</p>
        </main><aside class="aa-slot-relations">
          <h2>时间段关系</h2>
          <section><strong>节次与钟点</strong><p>节次编号连接课表课位；开始、结束时间按正式作息记录核对。</p></section>
          <section><strong>校区与生效日期</strong><p>夏令、冬令等作息在「上课时间段」按校区和生效范围维护。</p></section>
          <section><strong>变更后</strong><p>已有正式引用时，改号、停用或删除由服务端阻止。请核对受影响课表与资源时间安排。</p></section>
        </aside></div>
      </template>

      <!-- 上课时间段 -->
      <template v-else>
        <AppSectionCard title="选择节次">
          <div class="aa-slot-form">
            <label class="aa-slot-form__item aa-slot-form__item--grow">
              节次
              <AppTimeSlotPicker v-model="bandSlotId" :options="slotOptions" :query="{ includeDisabled: true }" :disabled="busy || loading" placeholder="请选择节次" @change="onBandSlotChange" />
            </label>
          </div>
        </AppSectionCard>

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!bandSlotId" title="请先选择节次" description="查看该节次在不同校区、生效日期内的上课钟点。" />
        <template v-else>
          <div class="aa-slot-workspace"><main>
          <AppSectionCard v-if="canManageBands" title="新增上课时间段">
            <fieldset class="aa-slot-form" :disabled="busy">
              <label class="aa-slot-form__item">
                名称
                <AppTextInput v-model="bandDraft.bandName" placeholder="选填，如 夏季作息" :maxlength="50" />
              </label>
              <label class="aa-slot-form__item">
                校区
                <AppTextInput v-model="bandDraft.campusCode" placeholder="学校使用的校区编码，选填" :maxlength="50" />
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
            </fieldset>
            <AppInlineAlert v-if="bandFormError" type="danger" :description="bandFormError" />
          </AppSectionCard>

          <AppSectionCard title="规则与适用范围">
            <ErrorState v-if="bandError" :description="bandError" @retry="loadBands" />
            <LoadingState v-else-if="bandLoading" />
            <EmptyState v-else-if="!bandRows.length" title="该节次尚未配置上课时间段" description="没有适用的时间段时，师生课表使用节次的基础钟点。" />
            <DataTable v-else :columns="bandColumns" :rows="bandRows" row-key="bandId">
              <template #cell-effective="{ row }">
                {{ dateOnly(row.effectiveStart) || '不限开始' }} 至 {{ dateOnly(row.effectiveEnd) || '不限结束' }}
              </template>
              <template #cell-status="{ row }">
                <StatusTag :status="row.status" />
              </template>
              <template #cell-actions="{ row }">
                <div v-if="canManageBands" class="aa-slot-actions">
                  <button class="mp-link" :disabled="busy" @click="openEditBand(row)">编辑</button>
                  <button class="mp-link" :disabled="busy" @click="toggleBandStatus(row)">{{ row.status === 'ENABLED' ? '停用' : '启用' }}</button>
                  <button class="mp-link aa-danger" :disabled="busy" @click="confirmDeleteBand(row)">删除</button>
                </div>
                <span v-else class="mp-note">只读</span>
              </template>
            </DataTable>
          </AppSectionCard>
          </main><aside class="aa-slot-relations">
            <h2>适用顺序与影响</h2>
            <section><strong>当前对象</strong><p>节次 {{ bandSlotId }}。按校区、生效日期和启用状态核对实际钟点。</p></section>
            <section><strong>下游读取</strong><p>师生课表读取适用的正式时间段；没有适用记录时使用该节次的基础钟点。</p></section>
            <section><strong>调整前核对</strong><p>同一范围的时间段不能重叠。保留历史范围，新增后续生效记录，并由排课岗位核对课程安排。</p></section>
          </aside></div>
        </template>
      </template>
    </div>

    <!-- 编辑节次 -->
    <AppDrawer :visible="editVisible" title="编辑节次" mode="modal" size="medium" @close="editVisible = false">
      <fieldset class="aa-cal-form--drawer" v-if="editForm" :disabled="saving">
        <AppFormItem label="第几节" required>
          <AppNumberInput v-model="editForm.slotNo" :min="1" />
        </AppFormItem>
        <AppFormItem label="名称"><AppTextInput v-model="editForm.slotName" :maxlength="30" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTimePicker v-model="editForm.startTime" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTimePicker v-model="editForm.endTime" /></AppFormItem>
        <AppInlineAlert v-if="editError" type="danger" :description="editError" />
      </fieldset>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="editVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitEdit">保存</AppButton>
      </template>
    </AppDrawer>

    <!-- 编辑上课时间段 -->
    <AppDrawer :visible="editBandVisible" title="编辑上课时间段" mode="modal" size="large" @close="editBandVisible = false">
      <fieldset class="aa-cal-form--drawer" v-if="editBandForm" :disabled="bandSaving">
        <AppFormItem label="名称"><AppTextInput v-model="editBandForm.bandName" :maxlength="50" /></AppFormItem>
        <AppFormItem label="校区"><AppTextInput v-model="editBandForm.campusCode" :maxlength="50" /></AppFormItem>
        <AppFormItem label="生效开始"><AppDatePicker v-model="editBandForm.effectiveStart" /></AppFormItem>
        <AppFormItem label="生效结束"><AppDatePicker v-model="editBandForm.effectiveEnd" /></AppFormItem>
        <AppFormItem label="开始时间" required><AppTimePicker v-model="editBandForm.startTime" /></AppFormItem>
        <AppFormItem label="结束时间" required><AppTimePicker v-model="editBandForm.endTime" /></AppFormItem>
        <AppInlineAlert v-if="editBandError" type="danger" :description="editBandError" />
      </fieldset>
      <template #footer>
        <AppButton variant="ghost" :disabled="bandSaving" @click="editBandVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="bandSaving" @click="submitEditBand">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" title="删除节次"
                      message="删除后，该节次及其时间段将不再提供作息。已有业务引用的节次不能删除。确认删除？" type="danger" :submitting="actionBusy" @confirm="doDelete" />
    <AppConfirmDialog v-model:visible="confirmBandVisible" title="删除上课时间段"
                      message="删除后，课表将按其他适用时间段或基础钟点显示。确认删除？" type="danger" :submitting="actionBusy" @confirm="doDeleteBand" />
  </ModulePageShell>
</template>

<script>
/** 校历节次 · 作息时间（/admin/academic-affairs/time-slots，?tab=bands）：
 * 节次管理=t_aa_time_slot 全 CRUD（含启用/停用）；上课时间段=t_aa_class_time_band（节次的实际钟点，
 * 按校区/生效日期区间可配多套，如夏令/冬令作息）。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppSectionCard, AppTextInput, AppNumberInput, AppFormItem, AppDatePicker, AppTimePicker, AppConfirmDialog, AppInlineAlert, AppTimeSlotPicker } from '@/components/common'
import AaTimeSlotTemplatePanel from '@/modules/academicAffairs/components/AaTimeSlotTemplatePanel.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'

const HHMM_RE = /^([01]\d|2[0-3]):[0-5]\d$/

export default {
  name: 'AaTimeSlotView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppSectionCard, AppTextInput, AppNumberInput, AppFormItem, AppDatePicker, AppTimePicker, AppTimeSlotPicker,
    AppConfirmDialog, AppInlineAlert, AaTimeSlotTemplatePanel
  },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      tab: 'periods', createSlotVisible: false,
      actionBusy: false, templateApplying: false, loadVersion: 0, bandLoadVersion: 0,
      commandError: '',
      slotColumns: [
        { key: 'slotNo', title: '节次' }, { key: 'slotName', title: '名称' },
        { key: 'startTime', title: '开始' }, { key: 'endTime', title: '结束' },
        { key: 'timeBandCount', title: '时间段' }, { key: 'referenceStatus', title: '引用状态' },
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
    canManageSlots() { return this.hasPermission('academicAffairs.timeslot.manage') },
    canViewBands() { return this.hasPermission('academicAffairs.classTimeBand.view') },
    canManageBands() { return this.canViewBands && this.hasPermission('academicAffairs.classTimeBand.manage') },
    busy() { return this.adding || this.saving || this.bandAdding || this.bandSaving || this.actionBusy || this.templateApplying },
    tabs() { return [{ key: 'periods', label: '节次管理' }, ...(this.canViewBands ? [{ key: 'bands', label: '上课时间段' }] : [])] },
    slotOptions() {
      return this.rows.map((s) => ({ value: s.slotId, label: `第 ${s.slotNo} 节${s.slotName ? ' · ' + s.slotName : ''}` }))
    }
  },
  created() {
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q === 'bands' && this.canViewBands) this.tab = 'bands'
    this.bandSlotId = this.$route.query.slotId || ''
    this.includeDisabled = this.tab === 'bands'
    this.load()
  },
  watch: {
    '$route.query.tab'(key) { this.switchTab(key === 'bands' && this.canViewBands ? 'bands' : 'periods') },
    '$route.query.slotId'(id) {
      if (id && String(id) !== String(this.bandSlotId) && !this.busy) { this.bandSlotId = id; this.onBandSlotChange() }
    }
  },
  beforeUnmount() { this.loadVersion++; this.bandLoadVersion++ },
  beforeRouteUpdate(to, from, next) { if (this.busy) { toast.warning('正在保存作息，请稍候再切换'); next(false) } else next() },
  beforeRouteLeave(to, from, next) { if (this.busy) { toast.warning('正在保存作息，请稍候再离开'); next(false) } else next() },
  methods: {
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    dateOnly(value) { return value ? String(value).slice(0, 10) : '' },
    syncQuery() {
      const slotId = this.tab === 'bands' && this.bandSlotId ? String(this.bandSlotId) : undefined
      if (this.$route.query.tab !== this.tab || this.$route.query.slotId !== slotId) this.$router.replace({ query: { ...this.$route.query, tab: this.tab, slotId } })
    },
    goBands(row) {
      if (!this.canViewBands || this.busy) return
      this.bandSlotId = row.slotId
      this.switchTab('bands')
    },
    onBandSlotChange() {
      this.editBandVisible = false; this.confirmBandVisible = false; this.bandFormError = ''
      this.bandDraft = { bandName: '', campusCode: '', effectiveStart: '', effectiveEnd: '', startTime: '', endTime: '' }
      this.syncQuery(); this.loadBands()
    },
    switchTab(key) {
      if (this.tab === key || this.busy || (key === 'bands' && !this.canViewBands)) return
      this.tab = key
      this.createSlotVisible = false
      this.editVisible = false; this.editBandVisible = false; this.confirmVisible = false; this.confirmBandVisible = false
      this.syncQuery()
      this.load()
    },
    validate(d) {
      if (!Number.isInteger(Number(d.slotNo)) || Number(d.slotNo) < 1) return '请填写有效的节次序号（正整数）'
      if (!!d.startTime !== !!d.endTime) return '开始时间与结束时间需成对填写，或同时留空'
      if (d.startTime && !HHMM_RE.test(d.startTime)) return '开始时间格式应为 HH:MM，如 08:00'
      if (d.endTime && !HHMM_RE.test(d.endTime)) return '结束时间格式应为 HH:MM，如 08:45'
      if (d.startTime && d.endTime && d.startTime >= d.endTime) return '结束时间应晚于开始时间'
      return ''
    },
    async addSlot() {
      if (!this.canManageSlots || this.busy) return
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
        this.createSlotVisible = false
        this.draft = { slotNo: null, slotName: '', startTime: '', endTime: '' }
        this.load()
      } else {
        this.formError = res.message || '添加失败'
      }
    },
    async load() {
      const version = ++this.loadVersion
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTimeSlots(this.includeDisabled || this.tab === 'bands')
      if (version !== this.loadVersion) return
      if (res.code === 0) {
        this.rows = res.data || []
        if (this.bandSlotId && !this.rows.some(s => String(s.slotId) === String(this.bandSlotId))) this.bandSlotId = ''
        if (this.tab === 'bands') this.loadBands()
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    openEdit(row) {
      if (!this.canManageSlots || this.busy) return
      this.editForm = { slotId: row.slotId, slotNo: row.slotNo, slotName: row.slotName || '',
        startTime: row.startTime || '', endTime: row.endTime || '', enabled: row.enabled }
      this.editError = ''
      this.editVisible = true
    },
    async submitEdit() {
      if (!this.canManageSlots || this.busy || !this.editForm) return
      const err = this.validate(this.editForm)
      if (err) { this.editError = err; return }
      this.saving = true
      const res = await academicAffairsApi.updateTimeSlot(this.editForm.slotId, {
        slotNo: Number(this.editForm.slotNo), slotName: this.editForm.slotName || '',
        startTime: this.editForm.startTime || null, endTime: this.editForm.endTime || null
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
      if (!this.canManageSlots || this.busy) return
      this.commandError = ''
      this.actionBusy = true
      const res = await academicAffairsApi.updateTimeSlot(row.slotId, { enabled: !row.enabled })
      this.actionBusy = false
      if (res.code === 0) {
        toast.success(row.enabled ? '已停用' : '已启用')
        this.load()
      } else {
        this.commandError = `第 ${row.slotNo} 节（${row.slotId}）：${res.message || '操作未完成，请核对状态'}`
        toast.error(res.message || '操作失败')
      }
    },
    confirmDelete(row) {
      if (!this.canManageSlots || this.busy) return
      this.pendingDelete = row
      this.confirmVisible = true
    },
    async doDelete() {
      if (!this.canManageSlots || this.busy || !this.pendingDelete) return
      this.actionBusy = true
      const res = await academicAffairsApi.deleteTimeSlot(this.pendingDelete.slotId)
      if (res.code === 0) {
        toast.success('已删除')
        this.load()
        if (this.bandSlotId === this.pendingDelete.slotId) { this.bandSlotId = ''; this.bandRows = [] }
      } else {
        toast.error(res.message || '删除失败')
      }
      this.pendingDelete = null
      this.confirmVisible = false; this.actionBusy = false
    },
    // ── 上课时间段 ──
    validateBand(d) {
      if (!d.startTime || !d.endTime) return '开始时间与结束时间必填'
      if (!HHMM_RE.test(d.startTime) || !HHMM_RE.test(d.endTime)) return '时间格式应为 HH:MM，如 08:00'
      if (d.startTime >= d.endTime) return '结束时间应晚于开始时间'
      if (d.effectiveStart && d.effectiveEnd && d.effectiveStart > d.effectiveEnd) return '生效结束日期不能早于开始日期'
      return ''
    },
    async loadBands() {
      const version = ++this.bandLoadVersion
      this.bandRows = []; this.bandError = ''; this.bandLoading = false
      if (!this.canViewBands || !this.bandSlotId) return
      this.bandLoading = true
      this.bandError = ''
      const res = await academicAffairsApi.getTimeBands(this.bandSlotId)
      if (version !== this.bandLoadVersion) return
      if (res.code === 0) {
        this.bandRows = res.data || []
      } else {
        this.bandError = res.message
      }
      this.bandLoading = false
    },
    async addBand() {
      if (!this.canManageBands || this.busy || !this.bandSlotId) return
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
      if (!this.canManageBands || this.busy) return
      this.editBandForm = { bandId: row.bandId, bandName: row.bandName || '', campusCode: row.campusCode || '',
        effectiveStart: this.dateOnly(row.effectiveStart), effectiveEnd: this.dateOnly(row.effectiveEnd),
        startTime: row.startTime || '', endTime: row.endTime || '' }
      this.editBandError = ''
      this.editBandVisible = true
    },
    async submitEditBand() {
      if (!this.canManageBands || this.busy || !this.editBandForm) return
      const err = this.validateBand(this.editBandForm)
      if (err) { this.editBandError = err; return }
      this.bandSaving = true
      const res = await academicAffairsApi.updateTimeBand(this.editBandForm.bandId, {
        bandName: this.editBandForm.bandName || '', campusCode: this.editBandForm.campusCode || '',
        effectiveStart: this.editBandForm.effectiveStart || null, effectiveEnd: this.editBandForm.effectiveEnd || null,
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
      if (!this.canManageBands || this.busy) return
      this.actionBusy = true
      const res = await academicAffairsApi.updateTimeBand(row.bandId, { status: row.status === 'ENABLED' ? 'DISABLED' : 'ENABLED' })
      this.actionBusy = false
      if (res.code === 0) {
        toast.success('已更新')
        this.loadBands()
      } else {
        toast.error(res.message || '操作失败')
      }
    },
    confirmDeleteBand(row) {
      if (!this.canManageBands || this.busy) return
      this.pendingDeleteBand = row
      this.confirmBandVisible = true
    },
    async doDeleteBand() {
      if (!this.canManageBands || this.busy || !this.pendingDeleteBand) return
      this.actionBusy = true
      const res = await academicAffairsApi.deleteTimeBand(this.pendingDeleteBand.bandId)
      if (res.code === 0) {
        toast.success('已删除')
        this.loadBands()
      } else {
        toast.error(res.message || '删除失败')
      }
      this.pendingDeleteBand = null
      this.confirmBandVisible = false; this.actionBusy = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-slot-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; align-items: start; }
.aa-slot-workspace > main { min-width: 0; }
.aa-slot-relations { border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.aa-slot-relations h2 { margin: 0; padding: 15px 17px; border-bottom: 1px solid var(--border-base); font-size: 14px; }
.aa-slot-relations section { margin: 19px 17px 19px 25px; padding-left: 12px; border-left: 2px solid var(--pri); }
.aa-slot-relations strong { font-size: 13px; }
.aa-slot-relations p { color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
@media (max-width: 1100px) { .aa-slot-workspace { grid-template-columns: minmax(0, 1fr); } }
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); flex-wrap: wrap; }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aa-slot-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; margin: 0; padding: 0; border: 0; min-width: 0; }
.aa-slot-template > summary { cursor: pointer; width: fit-content; padding: 6px 0; color: var(--pri); font-size: 13px; }
.aa-slot-template[open] > summary { margin-bottom: 10px; }
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
.aa-cal-form--drawer { display: flex; flex-direction: column; gap: 12px; margin: 0; padding: 0; border: 0; min-width: 0; }
.mp-link.aa-danger { color: var(--danger-600, #f53f3f); }
.mp-link { border: 0; padding: 0; background: transparent; color: var(--pri); font: inherit; cursor: pointer; }
.mp-link:disabled { opacity: .55; cursor: not-allowed; }
.aa-slot-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.aa-slot-actions .mp-link { white-space: nowrap; }
</style>
