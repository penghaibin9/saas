<template>
  <ModulePageShell title="资源占用" subtitle="按日期查看教室 + 实训室的预约占用与课表占用（统一只读视图）">
    <div class="mp-stack">
      <div class="aaro-bar">
        <AppTextInput v-model="queryDate" placeholder="YYYY-MM-DD" style="max-width:180px" />
        <AppSelect v-model="resourceKind" :options="kindOptions" placeholder="全部资源类型" />
        <AppButton variant="primary" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="该日期暂无占用" description="预约或课表占用会显示在此" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="_rowKey">
        <template #cell-resourceKind="{ row }">{{ row.resourceKind === 'LAB' ? '实训室' : '教室' }}</template>
        <template #cell-slotNo="{ row }">第{{ row.slotNo }}节</template>
        <template #cell-source="{ row }">
          <StatusTag :type="row.source === 'BOOKING' ? 'primary' : 'default'" :label="row.source === 'BOOKING' ? '预约' : '课表'" />
        </template>
      </DataTable>

      <p class="mp-note">
        「预约」来源=教室/实训室已批准的占用申请；「课表」来源=当日按已发布课表换算出的教学占用。
        课表来源需要该日期落在当前学期教学周范围内才能换算，否则只显示预约占用。
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 资源占用（/admin/academic-affairs/resources/occupancy）：教室+实训室预约与课表统一只读聚合。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTextInput, AppSelect } from '@/components/common'
import { academicAffairsResourceApi } from '@/modules/academicAffairs/api/academic-affairs.api'

function todayStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export default {
  name: 'AaResourceOccupancyView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppTextInput, AppSelect },
  data() {
    return {
      loading: true,
      error: '',
      queryDate: todayStr(),
      resourceKind: '',
      kindOptions: [
        { label: '全部资源类型', value: '' },
        { label: '教室', value: 'CLASSROOM' },
        { label: '实训室', value: 'LAB' }
      ],
      rows: [],
      columns: [
        { key: 'resourceKind', title: '资源类型' },
        { key: 'resourceLabel', title: '资源' },
        { key: 'slotNo', title: '时段' },
        { key: 'source', title: '来源' },
        { key: 'occupant', title: '占用人/教师' },
        { key: 'purpose', title: '用途/课程' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      if (!this.queryDate) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsResourceApi.occupancy(this.queryDate, this.resourceKind)
      if (res.code === 0) {
        this.rows = res.data.items.map((it, idx) => ({ ...it, _rowKey: `${it.source}-${idx}` }))
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
.aaro-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
</style>
