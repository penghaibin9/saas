<template>
  <ModulePageShell title="资源占用" subtitle="按日期查看教室 + 实训室的预约占用与课表占用（统一只读视图）">
    <template #actions>
      <AppButton v-if="$route.query.returnToken" variant="ghost" @click="returnToOrigin">返回原位置</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aaro-bar">
        <AppDatePicker v-model="queryDate" style="max-width:180px" />
        <AppSelect v-model="resourceKind" :options="kindOptions" placeholder="全部资源类型" />
        <AppButton variant="primary" :disabled="loading" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard v-if="coverage" compact title="占用事实来源">
          <div class="aaro-evidence">
            <div><span>教室课表</span><strong>正式范围头 + 校历换算</strong></div>
            <div><span>实训室课表</span><strong>按明确关联的正式场地核对</strong></div>
            <div><span>未映射课位</span><strong>{{ coverage.unmappedScheduleItems }} 条</strong></div>
          </div>
          <AppInlineAlert
            v-if="coverage.unmappedLabs || coverage.unmappedLabBookings"
            type="warning"
            :description="`尚有 ${coverage.unmappedLabs} 个实训室未关联正式场地，${coverage.unmappedLabBookings} 条已批准预约缺少冻结场地；这些缺口不能作为空闲依据。`"
          />
          <AppInlineAlert
            v-if="coverage.unmappedScheduleItems"
            type="warning"
            :description="`${coverage.unmappedScheduleItems} 条正式课位缺少稳定 resourceId，无法归属具体场地，未参与资源冲突关联。`"
          />
        </AppSectionCard>

        <EmptyState v-if="!loaded" title="请选择日期并查询" description="读取真实占用后才显示查询结果。" />
        <EmptyState v-else-if="!rows.length" title="该日期暂无占用记录" description="当前查询未返回预约或正式课表占用；这不代表资源可预约，仍需核对维修、审批与未关联的实训室及历史预约。" />
        <DataTable v-else :columns="columns" :rows="pagedRows" row-key="_rowKey" :pagination="pagination" @page-change="onPageChange">
          <template #cell-resourceKind="{ row }">{{ row.resourceKind === 'LAB' ? '实训室' : '教室' }}</template>
          <template #cell-resourceLabel="{ row }">
            <div class="mp-cell-main">{{ row.resourceLabel || '资源名称待确认' }}</div>
            <div class="mp-cell-sub">{{ row.resourceId ? `资源 ID ${row.resourceId}` : '缺少稳定 resourceId' }} · {{ row.classroomId ? `正式场地 #${row.classroomId}` : '正式场地待核实' }}</div>
          </template>
          <template #cell-slotNo="{ row }">第{{ row.slotNo }}节</template>
          <template #cell-source="{ row }">
            <div class="aaro-source">
              <StatusTag :type="row.source === 'BOOKING' ? 'primary' : 'default'" :label="row.source === 'BOOKING' ? '已批准预约' : '正式课表'" />
              <div v-if="row.source === 'BOOKING'" class="mp-cell-sub">{{ row.bookingResourceKind === 'LAB' ? '实训室预约' : '教室预约' }} #{{ row.bookingId }}</div>
              <template v-else>
                <div class="mp-cell-sub">课位 #{{ row.scheduleItemId }} · 批次 #{{ row.batchId }} · 学期 #{{ row.termId }}</div>
                <div class="mp-cell-sub">{{ row.classId ? `班级 #${row.classId}` : '班级 ID 缺失' }} · {{ row.taskId ? `任务 #${row.taskId}` : '任务 ID 缺失' }}</div>
                <div :class="['mp-cell-sub', { 'aaro-swap': row.calendarSource === 'SWAP' }]">{{ scheduleDateFact(row) }}</div>
              </template>
            </div>
          </template>
          <template #cell-actions="{ row }">
            <button v-if="canOpenSchedule(row)" class="mp-link" type="button" @click="openSchedule(row)">核对正式课位</button>
            <span v-else class="mp-cell-sub">{{ row.source === 'SCHEDULE' ? '缺少班级/任务定位 ID' : '只读占用' }}</span>
          </template>
        </DataTable>

        <p v-if="loaded" class="mp-note">
          「预约」仅来自已批准申请；「正式课表」只来自覆盖所选日期的有效正式范围头，并按 HOLIDAY / SWAP、教学周、星期与单双周换算。
          空结果和未映射记录都不构成可预约许可，本页不会放开或代替任何审批。
        </p>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** AA-222 · 资源占用：已批准预约 + 正式范围头/校历换算后的课表占用，只读展示。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSelect, AppDatePicker, AppInlineAlert, AppSectionCard } from '@/components/common'
import { academicAffairsResourceApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { createAcademicRequestGate, routeScalar } from '../academicFlowContext'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

const COVERAGE = Object.freeze({ classroomSchedule: 'FORMAL_SCOPE_HEAD_CALENDAR', labSchedule: 'EXPLICIT_ROOM_BINDING' })
const WEEKDAY = Object.freeze({ 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' })

function todayStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function validDate(value) { return /^\d{4}-\d{2}-\d{2}$/.test(value) }
function stableId(value, optional = false) {
  if (optional && value == null) return null
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value) ? value : ''
}

export default {
  name: 'AaResourceOccupancyView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppSelect, AppDatePicker, AppInlineAlert, AppSectionCard },
  props: { ctx: { type: Object, default: null } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loading: false, loaded: false, disposed: false, routeVersion: 0, routeSyncing: false,
      error: '', resultDate: '', coverage: null,
      queryDate: todayStr(),
      resourceKind: '',
      kindOptions: [
        { label: '全部资源类型', value: '' },
        { label: '教室', value: 'CLASSROOM' },
        { label: '实训室', value: 'LAB' }
      ],
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'resourceKind', title: '资源类型' },
        { key: 'resourceLabel', title: '资源' },
        { key: 'slotNo', title: '时段' },
        { key: 'source', title: '真实来源', width: '360px' },
        { key: 'occupant', title: '占用人/教师' },
        { key: 'purpose', title: '用途/课程' },
        { key: 'actions', title: '核对' }
      ]
    }
  },
  computed: {
    identityKey() { return JSON.stringify([this.academicFlow?.identity() || '', this.ctx || null]) },
    pagedRows() {
      const start = (this.pagination.page - 1) * this.pagination.pageSize
      return this.rows.slice(start, start + this.pagination.pageSize)
    }
  },
  watch: {
    '$route.fullPath'() { this.syncRoute() },
    identityKey() { this.syncRoute() },
    queryDate() { if (!this.routeSyncing) { this.pagination.page = 1; this.invalidate() } },
    resourceKind() { if (!this.routeSyncing) { this.pagination.page = 1; this.invalidate() } }
  },
  created() {
    this.readGate = createAcademicRequestGate(() => JSON.stringify([this.identityKey, this.$route?.fullPath, this.queryDate, this.resourceKind]))
    this.syncRoute()
  },
  beforeUnmount() { this.disposed = true; this.routeVersion++; this.readGate.invalidate() },
  methods: {
    invalidate() {
      this.readGate.invalidate(); this.rows = []; this.coverage = null; this.resultDate = ''
      this.pagination.total = 0
      this.loaded = false; this.loading = false; this.error = ''
    },
    clearSensitive(message) {
      this.invalidate()
      this.error = `${message || '无权读取资源占用'}；已清除先前占用记录。`
    },
    async syncRoute() {
      if (this.disposed || !this.readGate) return
      const version = ++this.routeVersion
      this.invalidate()
      const rawDate = this.$route.query.date
      const rawKind = this.$route.query.resourceKind
      const rawPage = this.$route.query.page
      this.routeSyncing = true
      this.queryDate = routeScalar(rawDate) || todayStr()
      this.resourceKind = routeScalar(rawKind) || (this.$route.query.tab === 'room' ? 'CLASSROOM' : '')
      this.pagination.page = rawPage == null ? 1 : Number(routeScalar(rawPage))
      if ((rawDate != null && typeof rawDate !== 'string') || (rawKind != null && typeof rawKind !== 'string') ||
        (rawPage != null && (typeof rawPage !== 'string' || !/^\d+$/.test(rawPage) || this.pagination.page < 1))) {
        await this.$nextTick()
        this.routeSyncing = false
        this.error = '占用查询参数无效，请从教学资源目录重新进入。'
        return
      }
      const path = this.$route.fullPath
      await this.$nextTick()
      this.routeSyncing = false
      if (!this.disposed && version === this.routeVersion && path === this.$route.fullPath) await this.load()
    },
    normalizeCoverage(value) {
      const count = value?.unmappedScheduleItems
      if (value?.classroomSchedule !== COVERAGE.classroomSchedule || value?.labSchedule !== COVERAGE.labSchedule || !Number.isSafeInteger(count) || count < 0 ||
        !Number.isSafeInteger(value?.unmappedLabs) || value.unmappedLabs < 0 ||
        !Number.isSafeInteger(value?.unmappedLabBookings) || value.unmappedLabBookings < 0) {
        throw new Error('占用来源范围未完整返回，请重新查询。')
      }
      return { ...value, unmappedScheduleItems: count }
    },
    normalizeRows(items, date) {
      if (!Array.isArray(items)) throw new Error('占用记录未完整返回，请重新查询。')
      const keys = new Set()
      return items.map((item) => {
        let key = ''
        const row = { ...item }
        if (item?.source === 'BOOKING') {
          row.bookingId = stableId(item.bookingId)
          if (!row.bookingId || !['CLASSROOM', 'LAB'].includes(item.resourceKind)) throw new Error('预约占用缺少稳定来源标识，请重新查询。')
          key = `BOOKING:${item.bookingResourceKind || item.resourceKind}:${row.bookingId}:${item.resourceKind}:${item.resourceId}`
        } else if (item?.source === 'SCHEDULE') {
          row.scheduleItemId = stableId(item.scheduleItemId)
          row.batchId = stableId(item.batchId)
          row.termId = stableId(item.termId)
          row.classId = stableId(item.classId, true)
          row.taskId = stableId(item.taskId, true)
          if (!row.scheduleItemId || !row.batchId || !row.termId || (item.classId != null && !row.classId) ||
            (item.taskId != null && !row.taskId) || !item.logicalDate || !['NORMAL', 'SWAP'].includes(item.calendarSource)) {
            throw new Error('正式课表占用缺少稳定来源标识，请重新查询。')
          }
          key = `SCHEDULE:${row.scheduleItemId}:${date}:${item.resourceKind}:${item.resourceId}`
        } else throw new Error('占用记录缺少稳定来源标识，请重新查询。')
        if (keys.has(key)) throw new Error('占用记录来源标识重复，请重新查询。')
        keys.add(key)
        return {
          ...row,
          resourceId: item.resourceId == null ? '' : String(item.resourceId),
          _rowKey: key
        }
      })
    },
    handleFailure(error) {
      if (isDeniedResult(error)) { this.clearSensitive(error.message); return }
      this.rows = []; this.coverage = null; this.resultDate = ''; this.loaded = false
      this.pagination.total = 0
      this.error = isConflictResult(error)
        ? `正式课表、校历或范围头事实已变化；已保留日期条件，请重新查询。${error?.message ? ` ${error.message}` : ''}`
        : (error?.message || '占用读取失败，请重试。')
    },
    async load() {
      if (this.disposed) return
      this.invalidate()
      if (!validDate(this.queryDate) || !['', 'CLASSROOM', 'LAB'].includes(this.resourceKind)) {
        this.error = '请选择有效日期和资源类型后查询。'
        return
      }
      if (this.$route.query.date !== this.queryDate || (this.$route.query.resourceKind || '') !== this.resourceKind ||
        String(this.$route.query.page || '1') !== String(this.pagination.page)) {
        await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, date: this.queryDate, resourceKind: this.resourceKind || undefined, page: this.pagination.page > 1 ? String(this.pagination.page) : undefined } })
        return
      }
      const current = this.readGate.begin()
      const requestedDate = this.queryDate
      this.loading = true
      try {
        const res = await academicAffairsResourceApi.occupancy(requestedDate, this.resourceKind)
        if (!current()) return
        if (res.code !== 0) throw res
        if (res.data?.date !== requestedDate) throw new Error('服务端返回了不同日期的占用事实，已拒绝展示。')
        const coverage = this.normalizeCoverage(res.data?.coverage)
        const rows = this.normalizeRows(res.data?.items, requestedDate)
        this.coverage = coverage; this.rows = rows; this.pagination.total = rows.length; this.resultDate = requestedDate; this.loaded = true
        const lastPage = Math.max(1, Math.ceil(rows.length / this.pagination.pageSize))
        if (this.pagination.page > lastPage) {
          this.pagination.page = lastPage
          await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, page: lastPage > 1 ? String(lastPage) : undefined } })
        }
      } catch (error) {
        if (current()) this.handleFailure(error)
      } finally {
        if (current()) { this.loading = false; this.academicFlow?.restorePosition() }
      }
    },
    async onPageChange(page) {
      if (!Number.isSafeInteger(page) || page < 1 || page === this.pagination.page) return
      this.pagination.page = page
      await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, page: page > 1 ? String(page) : undefined } })
    },
    scheduleDateFact(row) {
      const coordinate = `第 ${row.weekNo} 周 · ${WEEKDAY[row.weekday] || '星期待确认'}`
      return row.calendarSource === 'SWAP'
        ? `SWAP 调课：实际 ${this.resultDate} · 逻辑课日 ${row.logicalDate} · 校历事件 #${row.calendarEventId || '待确认'} · ${coordinate}`
        : `教学日 ${row.logicalDate} · ${coordinate}`
    },
    canOpenSchedule(row) { return row.source === 'SCHEDULE' && row.scheduleItemId && row.batchId && row.classId && row.taskId },
    openSchedule(row) {
      if (!this.canOpenSchedule(row)) return
      const returnToken = this.academicFlow?.captureReturn()
      this.$router.push({
        path: `/admin/academic-affairs/schedule/${encodeURIComponent(String(row.batchId))}/edit`,
        query: {
          classId: String(row.classId), taskId: String(row.taskId), itemId: String(row.scheduleItemId),
          termId: String(row.termId), date: this.resultDate,
          ...(returnToken ? { returnToken } : {})
        }
      })
    },
    returnToOrigin() {
      return this.academicFlow?.back(this.$route.query.returnToken, '/admin/academic-affairs/classrooms')
        || this.$router.push('/admin/academic-affairs/classrooms')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aaro-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
.aaro-evidence { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aaro-evidence > div { padding: 12px; border: 1px solid var(--border-base); border-radius: 8px; background: var(--surface-card); }
.aaro-evidence span, .aaro-evidence strong { display: block; }
.aaro-evidence span { color: var(--text-tertiary); font-size: 12px; }
.aaro-evidence strong { margin-top: 5px; color: var(--text-primary); font-size: 14px; }
.aaro-evidence + :deep(.app-inline-alert) { margin-top: 12px; }
.aaro-source { display: grid; justify-items: start; gap: 5px; }
.aaro-swap { color: var(--warning-700, #b45309); }
@media (max-width: 760px) { .aaro-evidence { grid-template-columns: 1fr; } }
</style>
