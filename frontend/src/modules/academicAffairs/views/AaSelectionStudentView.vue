<template>
  <ModulePageShell title="选课" subtitle="选课中的批次课程 · 实时余量 · 选课/退课">
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!groups.length" title="当前无开放的选课批次" description="选课批次开选后将在此显示可选课程" />
      <template v-else>
        <section v-for="g in groups" :key="g.batch.batchId" class="aasels-group">
          <h3 class="aasels-batch">{{ g.batch.batchName }}</h3>
          <DataTable :columns="columns" :rows="g.courses" row-key="selectionCourseId">
            <template #cell-course="{ row }">
              <div class="mp-cell-main">{{ row.courseName }}</div>
              <div class="mp-cell-sub">{{ row.teacherName || '未派课' }} · {{ row.credit }} 学分</div>
            </template>
            <template #cell-remain="{ row }">
              <span :class="{ 'is-full': row.remain <= 0 }">{{ row.remain }} / {{ row.capacity }}</span>
            </template>
            <template #cell-op="{ row }">
              <AppButton
                v-if="!selectedIds.has(row.selectionCourseId)"
                size="small" variant="primary"
                :disabled="row.remain <= 0 || busy"
                @click="enroll(row)"
              >{{ row.remain <= 0 ? '已满' : '选课' }}</AppButton>
              <AppButton v-else size="small" variant="ghost" :disabled="busy" @click="drop(row)">退课</AppButton>
            </template>
          </DataTable>
        </section>

        <!-- 补选指引（06号卡）：因人数不足被取消开课的课程，可在批次锁定前补选其余有余量课程 -->
        <section v-for="rg in reselectGroups" :key="'reselect-' + rg.batch.batchId" class="aasels-group aasels-reselect">
          <h3 class="aasels-batch">补选指引 · {{ rg.batch.batchName }}</h3>
          <p class="aasels-reselect-hint">以下课程因人数不足已取消开课，请从可补选课程中重新选择（至批次锁定名单前均可操作）：</p>
          <ul class="aasels-cancelled">
            <li v-for="r in rg.cancelledRecords" :key="r.recordId">{{ r.courseName }}（{{ r.credit }} 学分）已停开</li>
          </ul>
          <EmptyState v-if="!rg.availableCourses.length" title="暂无可补选课程" description="请留意后续通知或联系教务处" />
          <DataTable v-else :columns="reselectColumns" :rows="rg.availableCourses" row-key="selectionCourseId">
            <template #cell-course="{ row }">
              <div class="mp-cell-main">{{ row.courseName }}</div>
              <div class="mp-cell-sub">{{ row.teacherName || '未派课' }} · {{ row.credit }} 学分</div>
            </template>
            <template #cell-remain="{ row }">{{ row.remain }} / {{ row.capacity }}</template>
            <template #cell-op="{ row }">
              <AppButton size="small" variant="primary" :disabled="row.remain <= 0 || busy" @click="reselect(row)">
                {{ row.remain <= 0 ? '已满' : '补选' }}
              </AppButton>
            </template>
          </DataTable>
        </section>

        <section v-if="mine.length" class="aasels-mine">
          <h3 class="aasels-batch">我的选课</h3>
          <ul class="aasels-mylist">
            <li v-for="r in mine" :key="r.recordId">
              <span>{{ r.courseName }}（{{ r.credit }} 学分）</span>
              <StatusTag :type="mineType(r.status)" :label="mineLabel(r.status)" dot />
            </li>
          </ul>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 选课 · 学生自助（/admin/academic-affairs/my-selection）：可选课程+实时余量+选/退课+我的选课+补选指引（06号卡）。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _ML = { SELECTED: '已选', LOCKED: '已锁定', DROPPED: '已退', COURSE_CANCELLED: '已停开' }

export default {
  name: 'AaSelectionStudentView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton },
  data() {
    return {
      loading: true, error: '', busy: false,
      groups: [], mine: [], reselectGroups: [],
      columns: [
        { key: 'course', title: '课程' }, { key: 'remain', title: '余量' }, { key: 'op', title: '操作' }
      ],
      reselectColumns: [
        { key: 'course', title: '课程' }, { key: 'remain', title: '余量' }, { key: 'op', title: '操作' }
      ]
    }
  },
  computed: {
    selectedIds() {
      return new Set(this.mine.filter(r => ['SELECTED', 'LOCKED'].includes(r.status)).map(r => r.selectionCourseId))
    }
  },
  created() { this.load() },
  methods: {
    mineLabel(s) { return _ML[s] || s },
    mineType(s) { return s === 'SELECTED' ? 'success' : s === 'LOCKED' ? 'default' : 'warning' },
    async load() {
      this.loading = true; this.error = ''
      const [cs, my, rg] = await Promise.all([api.studentCourses(), api.mySelections(), api.studentReselectGuide()])
      if (cs.code === 0) this.groups = cs.data.items || []
      else this.error = cs.message
      this.mine = my.code === 0 ? (my.data.items || []) : []
      this.reselectGroups = rg.code === 0 ? (rg.data.items || []) : []
      this.loading = false
    },
    async enroll(row) {
      this.busy = true
      const res = await api.enroll(row.selectionCourseId)
      this.busy = false
      if (res.code === 0) { toast.success('选课成功'); await this.load() }
      else toast.error(res.message || '选课失败')
    },
    async reselect(row) {
      this.busy = true
      const res = await api.enroll(row.selectionCourseId, true)
      this.busy = false
      if (res.code === 0) { toast.success('补选成功'); await this.load() }
      else toast.error(res.message || '补选失败')
    },
    async drop(row) {
      this.busy = true
      const res = await api.drop(row.selectionCourseId)
      this.busy = false
      if (res.code === 0) { toast.success('退课成功'); await this.load() }
      else toast.error(res.message || '退课失败')
    }
  }
}
</script>

<style scoped>
.aasels-group { margin-bottom: 20px; }
.aasels-batch { font-size: 15px; font-weight: 600; margin: 0 0 10px; }
.aasels-mine { border-top: 1px solid var(--border-color, #e5e7eb); padding-top: 16px; }
.aasels-mylist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.aasels-mylist li { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; }
.is-full { color: var(--danger-color, #dc2626); }
.aasels-reselect { border: 1px solid var(--warning-border, #fcd34d); background: var(--warning-bg, #fffbeb); border-radius: 10px; padding: 12px 14px; }
.aasels-reselect-hint { font-size: 13px; color: var(--text-600, #566073); margin: 0 0 8px; }
.aasels-cancelled { list-style: none; margin: 0 0 10px; padding: 0; font-size: 13px; color: var(--text-500, #646a73); }
.aasels-cancelled li { padding: 2px 0; }
</style>
