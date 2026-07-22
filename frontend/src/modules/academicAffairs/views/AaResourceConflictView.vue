<template>
  <ModulePageShell title="资源冲突" subtitle="预约与已发布课表的跨源冲突台账（区别于排课批次内冲突检测）">
    <div class="mp-stack">
      <div class="aarc-bar">
        <AppDatePicker v-model="dateFrom" placeholder="起始日期" style="max-width:180px" />
        <AppDatePicker v-model="dateTo" placeholder="结束日期（选填）" style="max-width:180px" />
        <AppButton variant="primary" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="该范围内无冲突" description="预约与已发布课表未发现同教室/实训室同时段重叠" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="_rowKey">
        <template #cell-resourceKind="{ row }">{{ row.resourceKind === 'LAB' ? '实训室' : '教室' }}</template>
        <template #cell-slotNo="{ row }">{{ row.date }} 第{{ row.slotNo }}节</template>
        <template #cell-booking="{ row }">{{ row.applicantName }}｜{{ row.purpose || '未填用途' }}</template>
        <template #cell-schedule="{ row }">{{ row.scheduleCourseName }}｜{{ row.scheduleClassName }}｜{{ row.scheduleTeacherName }}</template>
      </DataTable>

      <p class="mp-note">
        本页只显示"已批准预约"与"已发布课表"在同一教室/实训室同一时段重叠的记录，是排课模块批次内冲突检测覆盖不到的盲区。
        发现冲突后建议教务处线下协调后驳回其中一方预约，或联系排课人员调整课表。
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 资源冲突（/admin/academic-affairs/resources/conflicts）：预约 vs 已发布课表跨源冲突台账。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppDatePicker } from '@/components/common'
import { academicAffairsResourceApi } from '@/modules/academicAffairs/api/academic-affairs.api'

function todayStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export default {
  name: 'AaResourceConflictView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDatePicker },
  data() {
    return {
      loading: true,
      error: '',
      dateFrom: todayStr(),
      dateTo: '',
      rows: [],
      columns: [
        { key: 'resourceKind', title: '资源类型' },
        { key: 'resourceLabel', title: '资源' },
        { key: 'slotNo', title: '日期/时段' },
        { key: 'booking', title: '预约方' },
        { key: 'schedule', title: '课表方' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      if (!this.dateFrom) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsResourceApi.conflicts(this.dateFrom, this.dateTo)
      if (res.code === 0) {
        this.rows = res.data.items.map((it, idx) => ({ ...it, _rowKey: `${it.bookingId}-${idx}` }))
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
.aarc-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
</style>
