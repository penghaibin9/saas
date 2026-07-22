<template>
  <ModulePageShell
    title="学业预警"
    subtitle="按挂科规则扫描生成预警（幂等）；处置跟进沿用现有学业预警处置页"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" :loading="scanning" @click="scan">执行预警扫描</AppButton>
      <AppButton @click="goHandle">前往处置页</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert v-if="scanResult" type="success" :message="`扫描完成：阈值 ${scanResult.threshold ?? '-'} · 新增 ${scanResult.created} · 更新 ${scanResult.updated} · 通知 ${scanResult.notified}`" />

      <div class="aa-filter">
        <AppSelect v-model="filters.level" :options="levelOptions" @change="search" />
        <AppButton @click="search">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无学业预警" description="点击「执行预警扫描」按挂科规则生成预警" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="warningId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-level="{ row }">
          <AppStatusTag :type="warningColor(row.level)" dot>{{ levelLabel(row.level) }}</AppStatusTag>
        </template>
      </DataTable>
      <p class="mp-note">预警阈值来自规则中心默认值（待校确认）；预警处置、跟进、统计沿用现有「学业预警」处置页，不在此重建。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学业预警（/admin/academic-affairs/warnings）：POST /warnings/scan + GET /warnings。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppInlineAlert, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { WARNING_LEVEL, warningColor } from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'

export default {
  name: 'AaWarningView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppInlineAlert, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      WARNING_LEVEL,
      loading: true, error: '', rows: [], scanning: false, scanResult: null,
      filters: { level: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'studentName', title: '学生' },
        { key: 'level', title: '级别' },
        { key: 'reason', title: '预警原因' },
        { key: 'sourceCode', title: '来源' }
      ]
    }
  },
  computed: {
    levelOptions() {
      return [{ value: '', label: '全部级别' }, ...Object.entries(WARNING_LEVEL).map(([value, label]) => ({ value, label }))]
    }
  },
  created() { this.load() },
  methods: {
    warningColor,
    levelLabel(l) { return WARNING_LEVEL[l] || l || '' },
    goHandle() { this.$router.push('/admin/academic/warnings') },
    onPageChange(p) { this.pagination.page = p; this.load() },
    search() { this.pagination.page = 1; this.load() },
    async scan() {
      if (this.scanning) return
      this.scanning = true
      const res = await academicAffairsApi.scanWarnings()
      this.scanning = false
      if (res.code === 0) { this.scanResult = res.data; toast.success('扫描完成'); this.load() }
      else toast.error(res.message || '扫描失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getWarnings({ level: this.filters.level || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
</style>
