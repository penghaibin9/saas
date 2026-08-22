<template>
  <ModulePageShell
    title="注册名单"
    subtitle="系统先圈定权威候选并解释资格，再批量预览确认；已注册事实在下方持续可追溯"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/registration')">返回批次列表</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="批量办理注册">
        <AaRegistrationBulkPanel :batch-id="batchId" @applied="load" />
      </AppSectionCard>

      <AppSectionCard title="已注册名单">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="本批次暂无注册记录" description="完成上方批量预览并确认后，正式注册事实会出现在这里" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          row-key="registrationId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-status="{ row }">
            <AppStatusTag type="success" dot>{{ academicStatusLabel(row.status) }}</AppStatusTag>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 注册名单：D2-U 以权威候选→批量预览→逐项 canonical 注册替代人工逐个挑学生提交。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import AaRegistrationBulkPanel from '@/modules/academicAffairs/components/AaRegistrationBulkPanel.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'

export default {
  name: 'AaRegistrationDetailView',
  components: {
    ModulePageShell,
    DataTable,
    LoadingState,
    ErrorState,
    EmptyState,
    AppButton,
    AppSectionCard,
    AppStatusTag,
    AaRegistrationBulkPanel
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
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
    academicStatusLabel,
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRegistrations(this.batchId, {
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
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
</style>
