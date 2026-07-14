<template>
  <ModulePageShell
    title="注册管理"
    subtitle="按入学 / 学年建立注册批次；批次开放后逐个学生注册（经学籍单一入口写主档）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn mp-btn--primary" @click="showCreate = !showCreate">＋ 新建注册批次</button>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="showCreate" title="新建注册批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="draft.batchName" class="aa-input" placeholder="如 2026级新生入学注册" maxlength="50" />
          </label>
          <label class="aa-cal-form__item">
            类型
            <select v-model="draft.registerType" class="aa-select">
              <option value="ENROLL">入学注册</option>
              <option value="ANNUAL">学年注册</option>
            </select>
          </label>
          <label class="aa-cal-form__item">
            注册窗口
            <div class="aa-inline">
              <input v-model="draft.windowStart" type="date" class="aa-input aa-input--date" />
              <span>~</span>
              <input v-model="draft.windowEnd" type="date" class="aa-input aa-input--date" />
            </div>
          </label>
          <label class="aa-cal-form__item aa-cal-form__check">
            <input v-model="draft.open" type="checkbox" /> 创建后立即开放
          </label>
          <button class="mp-btn mp-btn--primary" :disabled="creating || !draft.batchName" @click="createBatch">
            {{ creating ? '创建中…' : '创建' }}
          </button>
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
          {{ row.registerType === 'ENROLL' ? '入学注册' : '学年注册' }}
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">注册名单</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 注册批次列表（/admin/academic-affairs/registration）：GET/POST /academic-affairs/registration-batches。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已关闭' }

export default {
  name: 'AaRegistrationBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      showCreate: false,
      creating: false,
      draft: { batchName: '', registerType: 'ENROLL', windowStart: '', windowEnd: '', open: false },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'type', title: '类型' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '100px' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    goDetail(row) {
      this.$router.push(`/admin/academic-affairs/registration/${row.batchId}`)
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async createBatch() {
      if (this.creating || !this.draft.batchName) return
      this.creating = true
      const res = await academicAffairsApi.createRegistrationBatch({
        batchName: this.draft.batchName,
        registerType: this.draft.registerType,
        windowStart: this.draft.windowStart || undefined,
        windowEnd: this.draft.windowEnd || undefined,
        open: this.draft.open
      })
      this.creating = false
      if (res.code === 0) {
        toast.success('注册批次已创建')
        this.showCreate = false
        this.draft = { batchName: '', registerType: 'ENROLL', windowStart: '', windowEnd: '', open: false }
        this.load()
      } else {
        toast.error(res.message || '创建失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRegistrationBatches({ page: this.pagination.page, pageSize: this.pagination.pageSize })
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
.aa-inline { display: flex; align-items: center; gap: 8px; }
.aa-input, .aa-select {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box;
}
.aa-input--date { width: 150px; }
</style>
