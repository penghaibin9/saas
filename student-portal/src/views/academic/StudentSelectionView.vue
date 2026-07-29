<template>
  <div class="sp-page selection-page">
    <section class="selection-hero">
      <div>
        <div class="selection-hero__eyebrow">教务学业 · 网上选课</div>
        <h1>查询余量并办理选退课</h1>
        <p>只读取开放批次和本人选课记录。每次操作后重新读取服务器状态，不用本地假成功覆盖真实结果。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingId" @click="load">
        {{ loading ? '加载中…' : '刷新余量' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取开放课程和本人选课记录…" />
    <section v-else-if="error" class="sp-card selection-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>
    <template v-else>
      <section class="selection-summary">
        <article class="summary-card"><span>开放批次</span><b>{{ groups.length }}</b></article>
        <article class="summary-card"><span>本人已选</span><b>{{ selectedRecords.length }}</b></article>
        <article class="summary-card"><span>已选学分</span><b>{{ selectedCredits }}</b></article>
      </section>

      <nav class="selection-tabs" aria-label="选课页面">
        <button type="button" :class="{ 'is-active': tab === 'courses' }" @click="tab = 'courses'">可选课程</button>
        <button type="button" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">我的选课</button>
      </nav>

      <template v-if="tab === 'courses'">
        <StateBlock v-if="!groups.length" type="empty" text="暂无开放中的选课批次" />
        <section v-else class="batch-list">
          <article v-for="group in groups" :key="group.batch.batchId" class="sp-card batch-card">
            <header class="batch-card__head">
              <div>
                <strong>{{ group.batch.batchName || '选课批次' }}</strong>
                <span>{{ windowText(group.batch) }}</span>
              </div>
              <StatusTag :text="group.batch.status || '开放中'" tone="primary" />
            </header>
            <StateBlock v-if="!group.courses.length" type="empty" text="本批次暂无可选课程" />
            <div v-else class="course-table-wrap">
              <table class="sp-table course-table">
                <thead><tr><th>课程</th><th>教师</th><th>学分</th><th>余量</th><th>状态</th><th class="is-action">操作</th></tr></thead>
                <tbody>
                  <tr v-for="course in group.courses" :key="course.selectionCourseId">
                    <td><strong>{{ course.courseName || '课程名称待补充' }}</strong><small>{{ course.courseCode || '' }}</small></td>
                    <td>{{ course.teacherName || '待定' }}</td>
                    <td>{{ course.credit ?? '—' }}</td>
                    <td>{{ remainText(course) }}</td>
                    <td><StatusTag :text="courseStatusText(course)" :tone="courseStatusTone(course)" /></td>
                    <td class="is-action">
                      <button
                        v-if="isSelected(course)"
                        class="sp-btn sp-btn--ghost sp-btn--sm"
                        type="button"
                        :disabled="!!actingId"
                        @click="drop(course)"
                      >{{ actingId === String(course.selectionCourseId) ? '处理中…' : '退课' }}</button>
                      <button
                        v-else
                        class="sp-btn sp-btn--sm"
                        type="button"
                        :disabled="!!actingId || !canEnroll(course)"
                        @click="enroll(course)"
                      >{{ actingId === String(course.selectionCourseId) ? '处理中…' : canEnroll(course) ? '选课' : '不可选' }}</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>
      </template>

      <template v-else>
        <StateBlock v-if="!records.length" type="empty" text="暂无本人选课记录" />
        <section v-else class="sp-card mine-card">
          <table class="sp-table course-table">
            <thead><tr><th>课程</th><th>学分</th><th>选课时间</th><th>状态</th><th class="is-action">操作</th></tr></thead>
            <tbody>
              <tr v-for="record in records" :key="record.recordId || `${record.selectionCourseId}:${record.status}`">
                <td><strong>{{ record.courseName || '课程名称待补充' }}</strong><small>{{ record.courseCode || '' }}</small></td>
                <td>{{ record.credit ?? '—' }}</td>
                <td>{{ dateText(record.enrolledAt) }}</td>
                <td><StatusTag :text="recordStatusText(record.status)" :tone="recordTone(record.status)" /></td>
                <td class="is-action">
                  <button
                    v-if="String(record.status || '').toUpperCase() === 'SELECTED'"
                    class="sp-btn sp-btn--ghost sp-btn--sm"
                    type="button"
                    :disabled="!!actingId"
                    @click="drop(record)"
                  >{{ actingId === String(record.selectionCourseId) ? '处理中…' : '退课' }}</button>
                  <span v-else class="sp-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </template>

      <section class="sp-card selection-note">
        <strong>办理提示</strong>
        <span>余量、冲突和选退课窗口以服务器最终校验为准。页面显示可选不代表绕过时间冲突、容量和培养方案限制。</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const tab = ref('courses')
const rawGroups = ref([])
const records = ref([])

const groups = computed(() => normalizeGroups(rawGroups.value))
const selectedRecords = computed(() => records.value.filter((record) => String(record.status || '').toUpperCase() === 'SELECTED'))
const selectedCredits = computed(() => selectedRecords.value.reduce((sum, record) => sum + Number(record.credit || 0), 0))

function normalizeGroups(data) {
  const source = Array.isArray(data) ? data : (data?.items || data?.list || data?.batches || [])
  if (!Array.isArray(source)) return []
  if (source.some((item) => item && item.batch && Array.isArray(item.courses))) {
    return source.map((item) => ({ batch: item.batch || {}, courses: item.courses || [] }))
  }
  if (source.some((item) => item && Array.isArray(item.courses))) {
    return source.map((item) => ({ batch: item.batch || item, courses: item.courses || [] }))
  }
  return source.length ? [{ batch: { batchId: 'current', batchName: '当前开放课程', status: 'OPEN' }, courses: source }] : []
}
function dateText(value) { return String(value || '').slice(0, 10) || '—' }
function windowText(batch) {
  const start = dateText(batch.windowStart || batch.startAt)
  const end = dateText(batch.windowEnd || batch.endAt)
  return start === '—' && end === '—' ? '开放窗口以教务处设置为准' : `${start} 至 ${end}`
}
function isSelected(course) {
  const id = String(course.selectionCourseId || '')
  return selectedRecords.value.some((record) => String(record.selectionCourseId || '') === id)
}
function remain(course) {
  const explicit = Number(course.remain)
  if (Number.isFinite(explicit)) return explicit
  const capacity = Number(course.capacity)
  const selected = Number(course.selectedCount || course.enrolledCount || 0)
  return Number.isFinite(capacity) ? Math.max(0, capacity - selected) : null
}
function remainText(course) {
  const value = remain(course)
  const capacity = Number(course.capacity)
  if (value == null) return '待确认'
  return Number.isFinite(capacity) ? `${value} / ${capacity}` : String(value)
}
function canEnroll(course) {
  if (isSelected(course)) return false
  const value = remain(course)
  if (value != null && value <= 0) return false
  const status = String(course.status || course.courseStatus || 'OPEN').toUpperCase()
  return !['CLOSED', 'DISABLED', 'FULL'].includes(status)
}
function courseStatusText(course) {
  if (isSelected(course)) return '本人已选'
  if (!canEnroll(course)) return remain(course) === 0 ? '已满' : '不可选'
  return '可选'
}
function courseStatusTone(course) {
  if (isSelected(course)) return 'success'
  return canEnroll(course) ? 'primary' : 'danger'
}
function recordStatusText(status) {
  const map = { SELECTED: '已选', DROPPED: '已退', CANCELLED: '已取消', REJECTED: '未通过' }
  return map[String(status || '').toUpperCase()] || status || '待确认'
}
function recordTone(status) {
  return String(status || '').toUpperCase() === 'SELECTED' ? 'success' : 'default'
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [coursesResult, recordsResult] = await Promise.all([
      portalApi.academicCourseSelection(),
      portalApi.academicSelectionRecords()
    ])
    rawGroups.value = coursesResult || []
    records.value = Array.isArray(recordsResult) ? recordsResult : (recordsResult?.items || recordsResult?.list || [])
  } catch (e) {
    error.value = e?.message || '选课数据读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function enroll(course) {
  const id = course?.selectionCourseId
  if (!id || actingId.value || !canEnroll(course)) return
  actingId.value = String(id)
  try {
    await portalApi.academicEnroll({ selectionCourseId: id })
    ui.notify('选课成功')
    await load()
  } catch (e) {
    ui.notify(e?.message || '选课失败')
  } finally {
    actingId.value = ''
  }
}
async function drop(course) {
  const id = course?.selectionCourseId
  if (!id || actingId.value || !isSelected(course)) return
  const confirmed = window.confirm(`确认退选“${course.courseName || '该课程'}”？`)
  if (!confirmed) return
  actingId.value = String(id)
  try {
    await portalApi.academicDrop({ selectionCourseId: id })
    ui.notify('已退课')
    await load()
  } catch (e) {
    ui.notify(e?.message || '退课失败')
  } finally {
    actingId.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.selection-page { max-width: 1180px; margin: 0 auto; }
.selection-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.selection-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.selection-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.selection-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.selection-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.selection-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--t1); font-size: 22px; }
.selection-tabs { display: flex; gap: 6px; margin-bottom: 14px; padding: 5px; border: 1px solid var(--line); border-radius: 11px; background: #fff; }
.selection-tabs button { flex: 1; min-height: 36px; border: 0; border-radius: 8px; background: transparent; color: var(--t3); cursor: pointer; }
.selection-tabs button.is-active { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.batch-list { display: grid; gap: 12px; }
.batch-card { padding: 18px 20px; }
.batch-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.batch-card__head strong, .batch-card__head span { display: block; }
.batch-card__head strong { color: var(--t1); font-size: 15px; }
.batch-card__head span { margin-top: 5px; color: var(--t3); font-size: 12px; }
.course-table-wrap { overflow-x: auto; }
.course-table td strong, .course-table td small { display: block; }
.course-table td small { margin-top: 3px; color: var(--t4); font-size: 11px; }
.course-table .is-action { text-align: right; white-space: nowrap; }
.mine-card { padding: 0; overflow-x: auto; }
.selection-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.selection-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 720px) {
  .selection-hero, .batch-card__head { align-items: stretch; flex-direction: column; }
  .selection-summary { grid-template-columns: 1fr; }
}
</style>
