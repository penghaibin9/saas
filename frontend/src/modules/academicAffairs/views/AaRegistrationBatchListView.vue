<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="showCreate = !showCreate">＋ 新建{{ typeLabel || '注册批次' }}</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="showCreate" :title="'新建' + (typeLabel || '注册批次')">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="draft.batchName" class="aa-input" placeholder="如 2026级新生入学注册" maxlength="50" />
          </label>
          <label class="aa-cal-form__item">
            类型
            <AppSelect v-model="draft.registerType" :options="registerTypeOptions" :disabled="!!fixedType" />
          </label>
          <label class="aa-cal-form__item">
            注册窗口
            <AppDateRangePicker v-model="windowRange" mode="form" />
          </label>
          <label class="aa-cal-form__item aa-cal-form__check">
            <input v-model="draft.open" type="checkbox" /> 创建后立即开放
          </label>
          <AppButton variant="primary" :disabled="!draft.batchName" :loading="creating" @click="createBatch">
            创建
          </AppButton>
        </div>
      </AppSectionCard>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有注册批次" description="点击右上角新建一个入学或学年注册批次" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="batchId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-type="{ row }">
          {{ typeLabelOf(row.registerType) }}
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">注册名单</button>
          <button v-if="row.status === 'OPEN'" class="mp-link" :disabled="busyId === row.batchId" @click="askClose(row)">关闭</button>
          <button v-if="row.status === 'CLOSED'" class="mp-link" :disabled="busyId === row.batchId" @click="askArchive(row)">归档</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 注册批次列表（/admin/academic-affairs/registration）：GET/POST /academic-affairs/registration-batches。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppDateRangePicker, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已关闭', ARCHIVED: '已归档' }
const TYPE_LABEL = { ENROLL: '入学注册', ANNUAL: '学年注册', SEMESTER: '学期注册' }

export default {
  name: 'AaRegistrationBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppDateRangePicker, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      showCreate: false,
      creating: false,
      busyId: '',
      draft: { batchName: '', registerType: 'ENROLL', windowStart: '', windowEnd: '', open: false },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'type', title: '类型' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '160px' }
      ],
      confirm: { visible: false, title: '', message: '', type: 'primary' },
      pendingAction: null
    }
  },
  computed: {
    registerTypeOptions() {
      return Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))
    },
    /** ?type=ENROLL/ANNUAL/SEMESTER 收窄为对应三级叶子视图；无 type 为原「注册批次」通栏视图。 */
    fixedType() {
      const t = this.$route && this.$route.query && this.$route.query.type
      return t === 'ENROLL' || t === 'ANNUAL' || t === 'SEMESTER' ? t : ''
    },
    typeLabel() {
      return TYPE_LABEL[this.fixedType] || ''
    },
    pageTitle() {
      return this.typeLabel || '注册管理'
    },
    pageSubtitle() {
      if (this.fixedType === 'ENROLL') return '新生入学注册批次：核身份/专业/班级，报到缴费材料齐全后完成注册'
      if (this.fixedType === 'ANNUAL') return '在籍学生学年注册批次：核对上学年状态/缴费后完成续注册'
      if (this.fixedType === 'SEMESTER') return '在籍学生按学期开的续注册批次：核对本学期在籍/缴费状态后完成注册'
      return '按入学 / 学年 / 学期建立注册批次；批次开放后逐个学生注册（经学籍单一入口写主档）'
    },
    /** AppDateRangePicker（mode=form）v-model 代理：对内仍是 draft.windowStart/windowEnd 两个字段，创建提交逻辑不用改。 */
    windowRange: {
      get() { return { start: this.draft.windowStart, end: this.draft.windowEnd } },
      set(v) { this.draft.windowStart = (v && v.start) || ''; this.draft.windowEnd = (v && v.end) || '' }
    }
  },
  watch: {
    '$route.query.type'() {
      this.draft.registerType = this.fixedType || 'ENROLL'
      this.pagination.page = 1
      this.load()
    }
  },
  created() {
    if (this.fixedType) this.draft.registerType = this.fixedType
    this.load()
  },
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    typeLabelOf(t) {
      return TYPE_LABEL[t] || t || ''
    },
    goDetail(row) {
      this.$router.push(`/admin/academic-affairs/registration/${row.batchId}`)
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    askClose(row) {
      this.confirm = { visible: true, title: '关闭注册批次',
        message: `确认关闭「${row.batchName}」？关闭后不可再为学生办理本批次注册。`, type: 'warning' }
      this.pendingAction = { kind: 'close', row }
    },
    askArchive(row) {
      this.confirm = { visible: true, title: '归档注册批次',
        message: `确认归档「${row.batchName}」？归档后台账只读，进入「注册归档」供查阅与导出。`, type: 'primary' }
      this.pendingAction = { kind: 'archive', row }
    },
    async onConfirm() {
      const a = this.pendingAction
      this.confirm.visible = false
      this.pendingAction = null
      if (!a) return
      this.busyId = a.row.batchId
      const res = a.kind === 'close'
        ? await academicAffairsApi.closeRegistrationBatch(a.row.batchId)
        : await academicAffairsApi.archiveRegistrationBatch(a.row.batchId)
      this.busyId = ''
      if (res.code === 0) {
        toast.success(a.kind === 'close' ? '已关闭' : '已归档')
        this.load()
      } else {
        toast.error(res.message || '操作失败')
      }
    },
    async createBatch() {
      if (this.creating || !this.draft.batchName) return
      this.creating = true
      const res = await academicAffairsApi.createRegistrationBatch({
        batchName: this.draft.batchName,
        registerType: this.fixedType || this.draft.registerType,
        windowStart: this.draft.windowStart || undefined,
        windowEnd: this.draft.windowEnd || undefined,
        open: this.draft.open
      })
      this.creating = false
      if (res.code === 0) {
        toast.success((this.typeLabel || '注册批次') + '已创建')
        this.showCreate = false
        this.draft = { batchName: '', registerType: this.fixedType || 'ENROLL', windowStart: '', windowEnd: '', open: false }
        this.load()
      } else {
        toast.error(res.message || '创建失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (this.fixedType) params.registerType = this.fixedType
      const res = await academicAffairsApi.getRegistrationBatches(params)
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-cal-form__check { flex-direction: row; align-items: center; gap: 6px; }
.aa-input, .aa-select {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box;
}
</style>
