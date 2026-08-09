<template>
  <div class="sp-page selection-page">
    <section class="selection-hero">
      <div class="selection-hero__copy">
        <div class="selection-hero__eyebrow"><span></span>教务学业 · 网上选课</div>
        <h1>网上选课</h1>
        <p>先看开放批次和实时余量，再办理选课或退课。所有资格、冲突、容量和时间窗口都由服务器最终校验。</p>
        <div class="selection-hero__trust" aria-label="办理保障">
          <span>实时余量</span><span>规则校验</span><span>办理后回读</span>
        </div>
      </div>
      <aside class="selection-hero__aside">
        <div class="selection-hero__status">
          <span>当前办理状态</span>
          <strong>{{ groups.length ? '有开放批次' : '暂无开放批次' }}</strong>
          <small>{{ groups.length ? `共 ${courseCount} 门课程可查看` : '教务处开放后会自动显示' }}</small>
        </div>
        <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingId" @click="load">
          {{ loading ? '加载中…' : '刷新实时数据' }}
        </button>
      </aside>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取开放课程和本人选课记录…" />
    <section v-else-if="error" class="sp-card selection-error">
      <div class="selection-error__mark" aria-hidden="true">!</div>
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>
    <template v-else>
      <AcademicDecisionTraceCard
        v-if="decisionError"
        class="selection-decision"
        :trace="decisionError.decisionTrace"
        :message="decisionError.message"
      />

      <section class="selection-summary" aria-label="选课概览">
        <article class="summary-card">
          <div class="summary-card__icon is-blue" aria-hidden="true">批</div>
          <div><span>开放批次</span><b>{{ groups.length }}</b><small>{{ courseCount }} 门课程可查看</small></div>
        </article>
        <article class="summary-card">
          <div class="summary-card__icon is-green" aria-hidden="true">选</div>
          <div><span>本人已选</span><b>{{ selectedRecords.length }}</b><small>{{ selectedRecords.length ? '可在“我的选课”中核对' : '当前还没有已选课程' }}</small></div>
        </article>
        <article class="summary-card">
          <div class="summary-card__icon is-violet" aria-hidden="true">分</div>
          <div><span>已选学分</span><b>{{ selectedCredits }}</b><small>以服务器有效选课记录为准</small></div>
        </article>
      </section>

      <nav class="selection-tabs" aria-label="选课页面">
        <button type="button" :class="{ 'is-active': tab === 'courses' }" @click="tab = 'courses'">
          <span>可选课程</span><em>{{ courseCount }}</em>
        </button>
        <button type="button" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">
          <span>我的选课</span><em>{{ records.length }}</em>
        </button>
      </nav>

      <template v-if="tab === 'courses'">
        <section v-if="!groups.length" class="sp-card selection-empty">
          <div class="selection-empty__icon" aria-hidden="true">✓</div>
          <strong>当前没有开放中的选课批次</strong>
          <span>无需反复刷新；教务处开放新的选课窗口后会显示在这里。</span>
        </section>
        <section v-else class="batch-list">
          <article v-for="group in groups" :key="group.batch.batchId" class="sp-card batch-card">
            <header class="batch-card__head">
              <div class="batch-card__title">
                <div class="batch-card__eyebrow">开放批次</div>
                <strong>{{ group.batch.batchName || '选课批次' }}</strong>
                <span>{{ windowText(group.batch) }}</span>
              </div>
              <div class="batch-card__meta">
                <span>{{ group.courses.length }} 门课程</span>
                <span>{{ openCourseCount(group) }} 门当前可选</span>
                <StatusTag :text="group.batch.status || '开放中'" tone="primary" />
              </div>
            </header>
            <StateBlock v-if="!group.courses.length" type="empty" text="本批次暂无可选课程" />
            <div v-else class="course-table-wrap">
              <table class="sp-table course-table">
                <thead><tr><th>课程</th><th>教师</th><th>学分</th><th>实时余量</th><th>状态</th><th class="is-action">操作</th></tr></thead>
                <tbody>
                  <tr v-for="course in group.courses" :key="course.selectionCourseId" :class="{ 'is-selected': isSelected(course) }">
                    <td>
                      <strong>{{ course.courseName || '课程名称待补充' }}</strong>
                      <small>{{ course.courseCode || '课程代码待补充' }}</small>
                    </td>
                    <td>{{ course.teacherName || '待定' }}</td>
                    <td><span class="course-credit">{{ course.credit ?? '—' }}</span></td>
                    <td>
                      <div class="remain-cell">
                        <strong>{{ remainText(course) }}</strong>
                        <span class="remain-bar" aria-hidden="true"><i :style="{ width: `${availabilityPct(course)}%` }"></i></span>
                      </div>
                    </td>
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
                      >{{ actingId === String(course.selectionCourseId) ? '处理中…' : canEnroll(course) ? '立即选课' : '不可选' }}</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>
      </template>

      <template v-else>
        <section v-if="!records.length" class="sp-card selection-empty">
          <div class="selection-empty__icon" aria-hidden="true">课</div>
          <strong>还没有选课记录</strong>
          <span>切换到“可选课程”查看当前开放课程并开始办理。</span>
        </section>
        <section v-else class="sp-card mine-card">
          <header class="mine-card__head">
            <div><strong>我的选课记录</strong><span>同时保留已选、已退和未通过记录，方便核对办理历史。</span></div>
            <span>{{ selectedRecords.length }} 门当前有效</span>
          </header>
          <div class="course-table-wrap">
            <table class="sp-table course-table">
              <thead><tr><th>课程</th><th>学分</th><th>选课时间</th><th>状态</th><th class="is-action">操作</th></tr></thead>
              <tbody>
                <tr v-for="record in records" :key="record.recordId || `${record.selectionCourseId}:${record.status}`" :class="{ 'is-selected': String(record.status || '').toUpperCase() === 'SELECTED' }">
                  <td><strong>{{ record.courseName || '课程名称待补充' }}</strong><small>{{ record.courseCode || '课程代码待补充' }}</small></td>
                  <td><span class="course-credit">{{ record.credit ?? '—' }}</span></td>
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
                    <span v-else class="sp-muted">已结束</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <section class="selection-note">
        <div class="selection-note__icon" aria-hidden="true">i</div>
        <div><strong>办理规则以服务器最终校验为准</strong><span>页面展示的余量用于帮助判断，但真正提交时仍会重新检查时间冲突、课程容量、选退课窗口及培养方案等条件。若未通过，页面会直接给出规则原因和下一步建议。</span></div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AcademicDecisionTraceCard from '../../components/academic/AcademicDecisionTraceCard.vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const decisionError = ref(null)
const tab = ref('courses')
const rawGroups = ref([])
const records = ref([])

const groups = computed(() => normalizeGroups(rawGroups.value))
const selectedRecords = computed(() => records.value.filter((record) => String(record.status || '').toUpperCase() === 'SELECTED'))
const selectedCredits = computed(() => selectedRecords.value.reduce((sum, record) => sum + Number(record.credit || 0), 0))
const courseCount = computed(() => groups.value.reduce((sum, group) => sum + (group.courses?.length || 0), 0))

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
function availabilityPct(course) {
  const value = remain(course)
  const capacity = Number(course.capacity)
  if (value == null || !Number.isFinite(capacity) || capacity <= 0) return 0
  return Math.max(0, Math.min(100, Math.round(value / capacity * 100)))
}
function canEnroll(course) {
  if (isSelected(course)) return false
  const value = remain(course)
  if (value != null && value <= 0) return false
  const status = String(course.status || course.courseStatus || 'OPEN').toUpperCase()
  return !['CLOSED', 'DISABLED', 'FULL'].includes(status)
}
function openCourseCount(group) {
  return (group?.courses || []).filter((course) => canEnroll(course)).length
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
  decisionError.value = null
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
  decisionError.value = null
  try {
    await portalApi.academicEnroll({ selectionCourseId: id })
    ui.notify('选课成功')
    await load()
  } catch (e) {
    if (e?.decisionTrace) decisionError.value = e
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
  decisionError.value = null
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
.selection-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 28px;
  margin-bottom: 16px;
  padding: 28px 30px;
  overflow: hidden;
  border: 1px solid #dbeafe;
  border-radius: 20px;
  background:
    radial-gradient(circle at 88% 16%, rgba(96, 165, 250, .20), transparent 28%),
    linear-gradient(135deg, #fff 0%, #f7fbff 54%, #eef6ff 100%);
  box-shadow: 0 18px 45px -36px rgba(47, 107, 255, .55);
}
.selection-hero::after { content: ''; position: absolute; right: -54px; bottom: -72px; width: 190px; height: 190px; border: 30px solid rgba(47,107,255,.035); border-radius: 50%; pointer-events: none; }
.selection-hero__copy, .selection-hero__aside { position: relative; z-index: 1; }
.selection-hero__eyebrow { display: flex; align-items: center; gap: 8px; color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.selection-hero__eyebrow span { width: 7px; height: 7px; border-radius: 50%; background: var(--pri); box-shadow: 0 0 0 5px rgba(47,107,255,.09); }
.selection-hero h1 { margin: 10px 0 7px; color: var(--t1); font-size: 28px; letter-spacing: -.02em; }
.selection-hero p { max-width: 720px; margin: 0; color: var(--t2); font-size: 13.5px; line-height: 1.75; }
.selection-hero__trust { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.selection-hero__trust span { padding: 6px 10px; border: 1px solid rgba(47,107,255,.10); border-radius: 999px; background: rgba(255,255,255,.72); color: var(--t2); font-size: 11.5px; }
.selection-hero__aside { display: grid; align-content: space-between; gap: 16px; padding-left: 20px; border-left: 1px solid rgba(47,107,255,.10); }
.selection-hero__status span, .selection-hero__status strong, .selection-hero__status small { display: block; }
.selection-hero__status span { color: var(--t4); font-size: 11px; }
.selection-hero__status strong { margin-top: 5px; color: var(--t1); font-size: 17px; }
.selection-hero__status small { margin-top: 5px; color: var(--t3); font-size: 11.5px; line-height: 1.5; }
.selection-hero__aside .sp-btn { width: 100%; }
.selection-error { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 34px 20px; }
.selection-error__mark { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 12px; background: var(--danger-bg); color: var(--danger-fg); font-weight: 800; }
.selection-decision { margin-bottom: 14px; }
.selection-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 13px; align-items: center; padding: 17px 18px; border: 1px solid var(--line); border-radius: 15px; background: #fff; box-shadow: 0 10px 26px -24px rgba(15,23,42,.35); }
.summary-card__icon { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 13px; font-size: 12px; font-weight: 800; }
.summary-card__icon.is-blue { color: var(--pri); background: var(--pri-50); }
.summary-card__icon.is-green { color: var(--ok-fg); background: var(--ok-bg); }
.summary-card__icon.is-violet { color: #6941c6; background: #f4f0ff; }
.summary-card span, .summary-card b, .summary-card small { display: block; }
.summary-card span { color: var(--t3); font-size: 11.5px; }
.summary-card b { margin-top: 3px; color: var(--t1); font-size: 22px; font-variant-numeric: tabular-nums; }
.summary-card small { margin-top: 3px; overflow: hidden; color: var(--t4); font-size: 10.8px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.selection-tabs { display: flex; gap: 6px; margin-bottom: 14px; padding: 5px; border: 1px solid var(--line); border-radius: 12px; background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,.03); }
.selection-tabs button { display: flex; align-items: center; justify-content: center; gap: 8px; flex: 1; min-height: 38px; border: 0; border-radius: 9px; background: transparent; color: var(--t3); cursor: pointer; font-family: inherit; }
.selection-tabs button em { min-width: 23px; padding: 2px 6px; border-radius: 999px; background: #f5f7fa; color: var(--t4); font-size: 10.5px; font-style: normal; font-variant-numeric: tabular-nums; }
.selection-tabs button.is-active { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.selection-tabs button.is-active em { background: #fff; color: var(--pri); }
.batch-list { display: grid; gap: 14px; }
.batch-card { padding: 0; overflow: hidden; }
.batch-card__head { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 18px 20px; border-bottom: 1px solid var(--line2); background: linear-gradient(180deg, #fff, #fcfdff); }
.batch-card__eyebrow { margin-bottom: 5px; color: var(--pri); font-size: 10.5px; font-weight: 700; letter-spacing: .08em; }
.batch-card__title strong, .batch-card__title span { display: block; }
.batch-card__title strong { color: var(--t1); font-size: 15px; }
.batch-card__title span { margin-top: 5px; color: var(--t3); font-size: 11.5px; }
.batch-card__meta { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; color: var(--t3); font-size: 11px; }
.batch-card__meta > span { padding: 5px 8px; border-radius: 7px; background: #f7f8fa; }
.course-table-wrap { overflow-x: auto; }
.course-table { min-width: 760px; }
.course-table tbody tr { transition: background .15s ease; }
.course-table tbody tr:hover { background: #fbfcfe; }
.course-table tbody tr.is-selected { background: #fbfffc; }
.course-table td { vertical-align: middle; }
.course-table td strong, .course-table td small { display: block; }
.course-table td strong { font-weight: 600; }
.course-table td small { margin-top: 4px; color: var(--t4); font-size: 10.8px; }
.course-table .is-action { text-align: right; white-space: nowrap; }
.course-credit { display: inline-flex; align-items: center; min-width: 32px; height: 26px; justify-content: center; border-radius: 8px; background: #f7f8fa; font-weight: 600; font-variant-numeric: tabular-nums; }
.remain-cell { display: grid; gap: 5px; min-width: 88px; }
.remain-cell > strong { color: var(--t2); font-size: 11.5px; font-variant-numeric: tabular-nums; }
.remain-bar { display: block; width: 78px; height: 5px; overflow: hidden; border-radius: 999px; background: #edf0f4; }
.remain-bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--g1), var(--pri)); }
.mine-card { padding: 0; overflow: hidden; }
.mine-card__head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 20px; border-bottom: 1px solid var(--line2); }
.mine-card__head > div strong, .mine-card__head > div span { display: block; }
.mine-card__head > div strong { font-size: 15px; }
.mine-card__head > div span { margin-top: 4px; color: var(--t3); font-size: 11.5px; }
.mine-card__head > span { flex-shrink: 0; padding: 6px 9px; border-radius: 8px; background: var(--ok-bg); color: var(--ok-fg); font-size: 11px; font-weight: 600; }
.selection-empty { display: grid; justify-items: center; gap: 7px; padding: 44px 22px; text-align: center; }
.selection-empty__icon { display: grid; place-items: center; width: 48px; height: 48px; margin-bottom: 3px; border-radius: 15px; background: var(--pri-50); color: var(--pri); font-size: 14px; font-weight: 800; }
.selection-empty strong { font-size: 14px; }
.selection-empty span { max-width: 480px; color: var(--t3); font-size: 12px; line-height: 1.65; }
.selection-note { display: grid; grid-template-columns: 34px minmax(0,1fr); gap: 12px; margin-top: 14px; padding: 15px 17px; border: 1px solid #e5edf9; border-radius: 14px; background: rgba(255,255,255,.72); }
.selection-note__icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: var(--pri-50); color: var(--pri); font-family: Georgia, serif; font-weight: 700; }
.selection-note strong, .selection-note span { display: block; }
.selection-note strong { color: var(--t1); font-size: 12.5px; }
.selection-note span { margin-top: 4px; color: var(--t3); font-size: 11.5px; line-height: 1.7; }
@media (max-width: 820px) {
  .selection-hero { grid-template-columns: 1fr; gap: 18px; padding: 22px; }
  .selection-hero__aside { grid-template-columns: minmax(0,1fr) auto; align-items: end; padding: 14px 0 0; border-top: 1px solid rgba(47,107,255,.10); border-left: 0; }
  .selection-hero__aside .sp-btn { width: auto; }
  .selection-summary { grid-template-columns: 1fr; }
  .summary-card small { white-space: normal; }
  .batch-card__head { align-items: flex-start; flex-direction: column; }
  .batch-card__meta { justify-content: flex-start; }
}
@media (max-width: 520px) {
  .selection-hero__aside { grid-template-columns: 1fr; }
  .selection-hero__aside .sp-btn { width: 100%; }
  .selection-tabs button { font-size: 12.5px; }
  .mine-card__head { align-items: flex-start; flex-direction: column; }
}
</style>
