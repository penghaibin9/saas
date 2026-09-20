<template>
  <ModulePageShell title="资源冲突" subtitle="预约与已发布课表的跨源冲突台账（区别于排课批次内冲突检测）">
    <template #actions>
      <AppButton v-if="$route.query.returnToken" variant="ghost" @click="returnToOrigin">返回原位置</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aarc-bar">
        <AppDatePicker v-model="dateFrom" placeholder="起始日期" style="max-width:180px" />
        <AppDatePicker v-model="dateTo" placeholder="结束日期（选填）" style="max-width:180px" />
        <AppButton variant="primary" :disabled="loading" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard v-if="coverage" compact title="冲突判定来源">
          <div class="aarc-evidence">
            <div><span>教室课表</span><strong>正式范围头 + 校历换算</strong></div>
            <div><span>关联规则</span><strong>同正式场地 ID + 同节次</strong></div>
            <div><span>未映射课位</span><strong>{{ coverage.unmappedScheduleItems }} 条</strong></div>
          </div>
          <AppInlineAlert
            v-if="coverage.unmappedLabs || coverage.unmappedLabBookings"
            type="warning"
            :description="`尚有 ${coverage.unmappedLabs} 个实训室未关联正式场地，${coverage.unmappedLabBookings} 条已批准预约缺少冻结场地，未据此推断无冲突。`"
          />
          <AppInlineAlert
            v-if="coverage.unmappedScheduleItems"
            type="warning"
            :description="`${coverage.unmappedScheduleItems} 条正式课位缺少 resourceId，未参与冲突关联；请先治理课位资源映射。`"
          />
        </AppSectionCard>

        <EmptyState v-if="!loaded" title="请选择日期范围并查询" description="读取正式课表和已批准预约后才显示冲突台账。" />
        <EmptyState v-else-if="!rows.length" title="所选范围未返回冲突记录" description="当前台账未发现可精确关联的重叠；这不构成任何资源的预约许可，未映射课位和历史预约仍需另行核对。" />
        <DataTable v-else :columns="columns" :rows="pagedRows" row-key="_rowKey" :pagination="pagination" @page-change="onPageChange">
          <template #cell-resourceKind="{ row }">{{ row.resourceKind === 'LAB' ? '实训室' : '教室' }}</template>
          <template #cell-resourceLabel="{ row }">
            <div class="mp-cell-main">{{ row.resourceLabel || '资源名称待确认' }}</div>
            <div class="mp-cell-sub">资源 ID {{ row.resourceId }} · 正式场地 #{{ row.classroomId }}</div>
          </template>
          <template #cell-slotNo="{ row }">{{ row.date }} · 第{{ row.slotNo }}节</template>
          <template #cell-booking="{ row }">
            <div class="mp-cell-main">{{ row.applicantName || '申请人待确认' }}</div>
            <div class="mp-cell-sub">预约 #{{ row.bookingId }} · {{ row.purpose || '未填用途' }}</div>
          </template>
          <template #cell-schedule="{ row }">
            <div class="mp-cell-main">{{ row.scheduleCourseName || '课程待确认' }}｜{{ row.scheduleClassName || '班级待确认' }}</div>
            <div class="mp-cell-sub">{{ row.scheduleTeacherName || '教师待确认' }} · 课位 #{{ row.scheduleItemId }} · 批次 #{{ row.batchId }}</div>
            <div class="mp-cell-sub">{{ row.classId ? `班级 #${row.classId}` : '班级 ID 缺失' }} · {{ row.taskId ? `任务 #${row.taskId}` : '任务 ID 缺失' }}</div>
            <div :class="['mp-cell-sub', { 'aarc-swap': row.calendarSource === 'SWAP' }]">{{ scheduleDateFact(row) }}</div>
          </template>
          <template #cell-actions="{ row }">
            <button v-if="canOpenSchedule(row)" class="mp-link" type="button" @click="openSchedule(row)">核对正式课位</button>
            <span v-else class="mp-cell-sub">缺少班级/任务定位 ID</span>
          </template>
        </DataTable>

        <p v-if="loaded" class="mp-note">
          本页只关联同一稳定 classroom resourceId、同一日期和同一节次的“已批准预约”与“正式课表”。
          正式课表按覆盖日期的所有有效范围头和校历换算读取，草稿、被替代版本、同名资源猜测均不进入冲突结论；本页只读，不提供删除课表或批准预约动作。
        </p>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** AA-223 · 资源冲突：已批准预约 vs 正式范围头/校历换算后的课表，只读精确关联。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppDatePicker, AppInlineAlert, AppSectionCard } from '@/components/common'
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
  name: 'AaResourceConflictView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppDatePicker, AppInlineAlert, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loading: false, loaded: false, disposed: false, routeVersion: 0, routeSyncing: false,
      error: '', dateFrom: todayStr(), dateTo: '', resultRange: null, coverage: null,
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'resourceKind', title: '资源类型' },
        { key: 'resourceLabel', title: '资源' },
        { key: 'slotNo', title: '冲突时段' },
        { key: 'booking', title: '预约来源' },
        { key: 'schedule', title: '正式课表来源', width: '390px' },
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
    dateFrom() { if (!this.routeSyncing) { this.pagination.page = 1; this.invalidate() } },
    dateTo() { if (!this.routeSyncing) { this.pagination.page = 1; this.invalidate() } }
  },
  created() {
    this.readGate = createAcademicRequestGate(() => JSON.stringify([this.identityKey, this.$route?.fullPath, this.dateFrom, this.dateTo]))
    this.syncRoute()
  },
  beforeUnmount() { this.disposed = true; this.routeVersion++; this.readGate.invalidate() },
  methods: {
    invalidate() {
      this.readGate.invalidate(); this.rows = []; this.coverage = null; this.resultRange = null
      this.pagination.total = 0
      this.loaded = false; this.loading = false; this.error = ''
    },
    clearSensitive(message) {
      this.invalidate()
      this.error = `${message || '无权读取资源冲突'}；已清除先前冲突记录。`
    },
    async syncRoute() {
      if (this.disposed || !this.readGate) return
      const version = ++this.routeVersion
      this.invalidate()
      const rawDate = this.$route.query.date
      const rawFrom = this.$route.query.dateFrom
      const rawTo = this.$route.query.dateTo
      const rawPage = this.$route.query.page
      const compactRange = typeof rawDate === 'string' ? rawDate.split('..') : []
      this.routeSyncing = true
      this.dateFrom = routeScalar(rawFrom) || routeScalar(compactRange[0]) || todayStr()
      this.dateTo = routeScalar(rawTo) || routeScalar(compactRange[1])
      this.pagination.page = rawPage == null ? 1 : Number(routeScalar(rawPage))
      if ((rawDate != null && typeof rawDate !== 'string') || (rawFrom != null && typeof rawFrom !== 'string') ||
        (rawTo != null && typeof rawTo !== 'string') || compactRange.length > 2 ||
        (rawPage != null && (typeof rawPage !== 'string' || !/^\d+$/.test(rawPage) || this.pagination.page < 1))) {
        await this.$nextTick()
        this.routeSyncing = false
        this.error = '冲突查询参数无效，请从教学资源目录重新进入。'
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
        throw new Error('冲突来源范围未完整返回，请重新查询。')
      }
      return { ...value, unmappedScheduleItems: count }
    },
    normalizeRows(items) {
      if (!Array.isArray(items)) throw new Error('冲突台账未完整返回，请重新查询。')
      const keys = new Set()
      return items.map((item) => {
        const row = {
          ...item,
          bookingId: stableId(item?.bookingId), scheduleItemId: stableId(item?.scheduleItemId),
          batchId: stableId(item?.batchId), termId: stableId(item?.termId), resourceId: stableId(item?.resourceId),
          classId: stableId(item?.classId, true), taskId: stableId(item?.taskId, true)
        }
        if (!row.bookingId || !row.scheduleItemId || !row.batchId || !row.termId || !row.resourceId ||
          (item.classId != null && !row.classId) || (item.taskId != null && !row.taskId) ||
          !item.date || !item.logicalDate || !['NORMAL', 'SWAP'].includes(item.calendarSource)) {
          throw new Error('冲突记录缺少稳定来源标识，请重新查询。')
        }
        const key = `CONFLICT:${item.resourceKind}:${row.bookingId}:${row.scheduleItemId}:${item.date}:${row.resourceId}:${item.slotNo}`
        if (keys.has(key)) throw new Error('冲突记录来源标识重复，请重新查询。')
        keys.add(key)
        return { ...row, _rowKey: key }
      })
    },
    handleFailure(error) {
      if (isDeniedResult(error)) { this.clearSensitive(error.message); return }
      this.rows = []; this.coverage = null; this.resultRange = null; this.loaded = false
      this.pagination.total = 0
      this.error = isConflictResult(error)
        ? `正式课表、校历或范围头事实已变化；已保留日期范围，请重新查询。${error?.message ? ` ${error.message}` : ''}`
        : (error?.message || '冲突台账读取失败，请重试。')
    },
    async load() {
      if (this.disposed) return
      this.invalidate()
      const from = this.dateFrom, to = this.dateTo
      if (!validDate(from) || (to && (!validDate(to) || to < from))) {
        this.error = '请选择有效的起止日期。'
        return
      }
      if (this.$route.query.date !== from || (this.$route.query.dateTo || '') !== to || this.$route.query.dateFrom != null ||
        String(this.$route.query.page || '1') !== String(this.pagination.page)) {
        const query = { ...this.$route.query, date: from, dateTo: to || undefined, page: this.pagination.page > 1 ? String(this.pagination.page) : undefined }
        delete query.dateFrom
        await this.$router.replace({ path: this.$route.path, query })
        return
      }
      const current = this.readGate.begin()
      this.loading = true
      try {
        const res = await academicAffairsResourceApi.conflicts(from, to)
        if (!current()) return
        if (res.code !== 0) throw res
        const expectedTo = to || from
        if (res.data?.dateFrom !== from || res.data?.dateTo !== expectedTo) throw new Error('服务端返回了不同日期范围的冲突事实，已拒绝展示。')
        const coverage = this.normalizeCoverage(res.data?.coverage)
        const rows = this.normalizeRows(res.data?.items)
        this.coverage = coverage; this.rows = rows; this.pagination.total = rows.length; this.resultRange = { from, to: expectedTo }; this.loaded = true
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
        ? `SWAP 调课：实际 ${row.date} · 逻辑课日 ${row.logicalDate} · 校历事件 #${row.calendarEventId || '待确认'} · ${coordinate}`
        : `教学日 ${row.logicalDate} · ${coordinate}`
    },
    canOpenSchedule(row) { return row.scheduleItemId && row.batchId && row.classId && row.taskId },
    openSchedule(row) {
      if (!this.canOpenSchedule(row)) return
      const returnToken = this.academicFlow?.captureReturn()
      this.$router.push({
        path: `/admin/academic-affairs/schedule/${encodeURIComponent(String(row.batchId))}/edit`,
        query: {
          classId: String(row.classId), taskId: String(row.taskId), itemId: String(row.scheduleItemId),
          termId: String(row.termId), date: String(row.date),
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
.aarc-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
.aarc-evidence { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aarc-evidence > div { padding: 12px; border: 1px solid var(--border-base); border-radius: 8px; background: var(--surface-card); }
.aarc-evidence span, .aarc-evidence strong { display: block; }
.aarc-evidence span { color: var(--text-tertiary); font-size: 12px; }
.aarc-evidence strong { margin-top: 5px; color: var(--text-primary); font-size: 14px; }
.aarc-evidence + :deep(.app-inline-alert) { margin-top: 12px; }
.aarc-swap { color: var(--warning-700, #b45309); }
@media (max-width: 760px) { .aarc-evidence { grid-template-columns: 1fr; } }
</style>
