<template>
  <ModulePageShell
    title="注册名单"
    subtitle="批次内已注册学生；从下方检索在籍学生并逐个注册"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/registration')">返回批次列表</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="注册学生">
        <div class="aa-reg-search">
          <AppStudentPicker v-model="selectedStudentId" class="aa-input--grow" placeholder="按姓名/学号检索在籍学生" :disabled="!!registeringId" @change="onStudentChange" />
        </div>
      </AppSectionCard>

      <AppSectionCard title="已注册名单">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="本批次暂无注册记录" description="用上方检索为学生完成注册" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          row-key="registrationId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-status="{ row }">
            <AppStatusTag type="success" dot>{{ row.status === 'REGISTERED' ? '已注册' : row.status }}</AppStatusTag>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 注册名单（/admin/academic-affairs/registration/:batchId）：注册记录 + roster 检索注册。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppStudentPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaRegistrationDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
      selectedStudentId: '',
      registeringId: '',
      columns: [
        { key: 'realName', title: '学生' },
        { key: 'registerAt', title: '注册时间' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  computed: {
    batchId() {
      return this.$route.params.batchId
    }
  },
  created() {
    this.load()
  },
  methods: {
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    onStudentChange(value, items) {
      const item = items?.[0]
      if (!value || !item) return
      this.doRegister(item.raw || { studentId: value, realName: item.label })
    },
    async doRegister(s) {
      if (this.registeringId) return
      this.registeringId = s.studentId
      const res = await academicAffairsApi.registerStudent(this.batchId, s.studentId)
      this.registeringId = ''
      if (res.code === 0) {
        toast.success(`${s.realName} 注册成功`)
        this.selectedStudentId = ''
        this.load()
      } else {
        toast.error(res.message || '注册失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRegistrations(this.batchId, { page: this.pagination.page, pageSize: this.pagination.pageSize })
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
.aa-reg-search { display: flex; gap: 12px; align-items: center; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-cand-list { list-style: none; margin: 12px 0 0; padding: 0; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
</style>
