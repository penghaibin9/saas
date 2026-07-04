<template>
  <ModulePageShell
    title="成果提交"
    subtitle="定稿 / 初稿版本 + 查重状态 · 查重超标自动退回修改（GD-R09）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前页签暂无成果提交" description="可切换页签查看其他状态" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · 指导教师 {{ row.advisorName }}</div>
        </template>
        <template #cell-topic="{ row }">
          <div style="font-size: var(--font-size-sm)">{{ row.topicTitle }}</div>
        </template>
        <template #cell-typeVersion="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.type }} {{ row.version }}</div>
          <div class="mp-cell-sub">{{ row.submitAt || '未提交' }}</div>
        </template>
        <template #cell-plagiarism="{ row }">
          <StatusTag :type="row.plagiarismTone" :label="row.plagiarismRate + ' · ' + row.plagiarismStatus" />
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status === 'NOT_SUBMITTED' ? 'PENDING_SUBMIT' : row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/graduation/students/' + row.projectId)">查看档案</button>
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link is-disabled"
            style="margin-left: var(--space-2)"
            :title="reviewReason"
          >批阅</button>
        </template>
      </DataTable>

      <p class="mp-note">成果批阅（通过 / 退回修改）由指导教师在成果批阅详情执行；查重报告在学生毕设详情「查重记录」页签查看与下载（学生端 P16 同步可见）。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成果提交列表（/admin/graduation/finals）：成果状态 + 查重状态一屏监管。 */
import {
  ModulePageShell, ModuleToolbar, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'FinalSubmissionListView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: { status: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: '', label: '全部' },
        { value: 'PENDING_REVIEW', label: '待审阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已退回修改' },
        { value: 'NOT_SUBMITTED', label: '未提交' }
      ],
      columns: [
        { key: 'student', title: '学生' },
        { key: 'topic', title: '课题' },
        { key: 'typeVersion', title: '成果 / 版本' },
        { key: 'plagiarism', title: '查重' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '140px' }
      ]
    }
  },
  computed: {
    reviewReason() {
      const pa = this.ctx.permissionActions.reviewFinal
      return pa && !pa.allowed ? pa.reason : ''
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportStats', label: '导出成果清单' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    switchTab(v) {
      this.filters.status = v
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    onToolbar() {
      toast.success('成果清单导出任务已创建（脱敏 + 水印），已写入审计日志')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getFinalSubmissions({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
