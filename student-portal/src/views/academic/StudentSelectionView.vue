<template>
  <div data-academic-page class="sp-page academic-prototype selection-page">
    <AcademicPrototypeHeader :title="receipt ? '选课办理结果' : detailCourse ? '课程详情与确认' : '网上选课'" group="注册与安排" :object="!!receipt || !!detailCourse" :description="receipt ? '提交不等于办结，以本人正式记录确认结果。' : detailCourse ? '确认课程对象、办理条件与提交后的下一步。' : '先核对课程安排与办理方式，提交后查看本人正式记录。'" :loading="loading || !!actingId" @refresh="load()" />
    <StateBlock v-if="loading" type="loading" text="正在读取可办理课程和本人选课记录…" />
    <section v-else-if="error && !groups.length && !records.length" class="card pad">
      <StateBlock type="error" :text="error" /><button class="btn" @click="load()">重新加载</button>
    </section>
    <div v-else class="stack">
      <AcademicDecisionTraceCard v-if="decisionError" :trace="decisionError.decisionTrace" :message="decisionError.message" />
      <div v-if="coursesError || recordsError" class="notice amber" role="alert"><AcademicPrototypeIcon name="triangle-exclamation" /><div><strong>部分数据未能更新</strong><p>{{ [coursesError, recordsError].filter(Boolean).join('；') }}</p></div></div>
      <template v-if="receipt">
        <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone">
          <button v-if="pendingOperation" class="btn primary" :disabled="!!actingId" @click="confirmPending">查询本次办理结果</button>
          <button v-else class="btn primary" @click="receipt = null; detailId = ''; tab = 'mine'">查看我的选课与报名</button>
          <button class="btn" @click="receipt = null; detailId = ''; tab = 'courses'">返回可办理课程</button>
        </AcademicBusinessReceipt>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>规则校验以学校当前条件为准，办理结果来自重新读取的本人记录。网络中断时先查询记录，不会自动再次提交选课。</span></div>
      </template>
      <template v-else-if="detailCourse">
        <div class="steps" aria-label="办理步骤"><div v-for="(label, i) in ['核对课程', '资格预检', '提交办理', '核对结果']" :key="label" class="step" :class="{ current: i === (actingId ? 1 : 0) }"><b>{{ i + 1 }}</b><span>{{ label }}</span></div></div>
        <div class="grid2">
          <section class="card"><header class="card-head"><h2>{{ detailCourse.courseName }}</h2></header><div class="card-body">
            <div class="row wrap"><span v-if="detailCourse.courseTypeLabel || detailCourse.courseType" class="tag">{{ detailCourse.courseTypeLabel || detailCourse.courseType }}</span><span class="tag" :class="{ amber: isLottery(detailCourse) }">{{ modeLabel(detailCourse) }}</span><span class="label">{{ detailCourse.courseCode || '课程代码未提供' }}</span></div>
            <dl class="definition">
              <dt>任课教师</dt><dd>{{ detailCourse.teacherName || '待公布' }}</dd><dt>课程学分</dt><dd>{{ detailCourse.credit ?? '待确认' }} 学分</dd>
              <dt>上课时间</dt><dd>{{ meetingTimes(detailCourse) }}</dd><dt>上课教室</dt><dd>{{ roomsText(detailCourse) }}</dd><dt>教学周次</dt><dd>{{ weeksText(detailCourse) }}</dd>
              <dt>容量快照</dt><dd>{{ isLottery(detailCourse) ? '抽签后确定' : remainText(detailCourse) }}（仅供参考）</dd><dt>办理窗口</dt><dd>{{ windowText(detailBatch) }}</dd>
            </dl>
            <button class="btn link small" @click="detailId = ''">返回可办理课程</button>
          </div></section>
          <section class="card"><header class="card-head"><h2>本人办理条件</h2></header><div class="card-body">
            <div class="taskline"><AcademicPrototypeIcon :name="hasAction(detailCourse, 'ENROLL') ? 'circle-check' : 'triangle-exclamation'" /><span>{{ courseStatusText(detailCourse) }}</span></div>
            <div class="taskline"><AcademicPrototypeIcon name="circle-info" /><span>{{ detailCourse.reason || '请提交前核对资格，当前快照不预留名额。' }}</span></div>
            <div class="notice amber detail-notice"><AcademicPrototypeIcon name="circle-info" /><span>{{ isLottery(detailCourse) ? '本次只登记抽签意向。中签后再形成有效选课结果。' : '提交时服务器重新检查容量、时间和学籍资格。' }}</span></div>
            <p v-if="detailCourse.howToResolve" class="muted">{{ detailCourse.howToResolve }}</p>
            <button v-if="hasAction(detailCourse, 'ENROLL')" class="btn primary" :disabled="!!actingId || !!pendingOperation || !!coursesError || !!recordsError" @click="enroll(detailCourse)">{{ actingId ? '正在核验并办理…' : '核对并提交' }}</button>
            <button v-else-if="hasAction(detailCourse, 'DROP')" class="btn" :disabled="!dropPreflightAvailable || !!actingId || !!pendingOperation || !!coursesError || !!recordsError" @click="drop(detailCourse)">核对退课</button>
            <button v-else class="btn" disabled>当前不可办理</button>
            <p v-if="hasAction(detailCourse, 'DROP') && !dropPreflightAvailable" class="muted">退课资格核验暂不可用，请向教务老师核对；当前不会提交退课。</p>
          </div></section>
        </div>
      </template>
      <template v-else>
        <div v-if="pendingOperation" class="notice amber" role="status"><div><strong>办理结果待确认，暂不重复提交</strong><p>查询不会再次提交选课或退课。</p><button class="btn small" :disabled="!!actingId" @click="confirmPending">查询本次办理结果</button></div></div>
        <div class="toolbar">
          <select v-model="activeBatchId" aria-label="选课批次" data-workspace-filter :disabled="!!actingId || !!pendingOperation" @change="changeBatch"><option value="">{{ batchOptions.length === 1 ? batchOptions[0].batchName : '全部可办理批次' }}</option><option v-for="batch in batchOptions" :key="batch.batchId" :value="String(batch.batchId)">{{ batch.batchName || '选课批次' }}</option></select>
          <span class="grow"></span><small>容量采样：{{ sampledAt }} · 不是名额预留</small>
        </div>
        <nav class="tabs" :aria-label="'选课页面，已取得名额 ' + selectedRecords.length + ' 门'"><button :class="{ active: tab === 'courses' }" @click="tab = 'courses'">可办理课程</button><button :class="{ active: tab === 'mine' }" @click="tab = 'mine'">我的选课与报名</button></nav>
        <template v-if="tab === 'courses'">
          <div class="toolbar"><input v-model.trim="search" class="input" type="search" placeholder="搜索课程、代码或老师" aria-label="搜索选课课程" /><button class="btn small" type="button">搜索</button><span class="grow"></span><small>{{ visibleCourseCount }} 门课程</small></div>
          <section class="card table-wrap">
            <table class="table course-table"><thead><tr><th>课程 / 方式</th><th>授课教师</th><th>安排</th><th>学分</th><th>余量快照</th><th>办理</th></tr></thead>
              <tbody><template v-for="group in visibleGroups" :key="group.batch.batchId"><tr v-for="course in group.courses" :key="course.selectionCourseId">
                <td><strong>{{ course.courseName || '课程名称待补充' }}</strong><small>{{ course.courseCode || '代码未提供' }}<template v-if="course.courseTypeLabel || course.courseType"> · {{ course.courseTypeLabel || course.courseType }}</template></small><span class="tag" :class="{ amber: isLottery(course) }">{{ modeLabel(course) }}</span></td>
                <td>{{ course.teacherName || '待公布' }}</td><td>{{ meetingTimes(course) }}<small class="schedule-meta">{{ roomsText(course) }} · {{ weeksText(course) }}</small></td><td>{{ course.credit ?? '—' }}</td><td>{{ isLottery(course) ? '抽签后确定' : remainText(course) }}</td>
                <td><button class="btn small" :class="{ primary: hasAction(course, 'ENROLL') }" @click="detailId = String(course.selectionCourseId)">{{ hasAction(course, 'ENROLL') ? '查看与办理' : hasAction(course, 'DROP') ? '核对退课' : '查看原因' }}</button></td>
              </tr></template></tbody>
            </table>
            <StateBlock v-if="!visibleCourseCount && !coursesError" type="empty" :text="courseCount ? '没有符合搜索条件的课程，请调整关键词。' : '当前没有可办理的选课批次'" />
          </section>
        </template>
        <template v-else>
          <div class="notice amber"><AcademicPrototypeIcon name="circle-info" /><span>“待抽签”只是报名成功，不计入已获得席位和正式课表。</span></div>
          <section v-if="!records.length && !recordsError" class="empty"><div class="iconbox"><AcademicPrototypeIcon name="book-open" /></div><h2>你还没有选课或报名记录</h2><p>待抽签、已选、未中签、已退课会分别保留。</p><button class="btn primary" @click="tab = 'courses'">查看可办理课程</button></section>
          <article v-for="record in records" :key="record.recordId || record.selectionCourseId + ':' + record.status" class="selection-record">
            <div class="row between"><strong>{{ record.courseName || '课程名称待补充' }}</strong><span class="tag" :class="['SELECTED', 'LOCKED'].includes(record.status) ? 'green' : 'amber'">{{ recordStatusText(record.status) }}</span></div>
            <dl class="definition"><dt>办理方式</dt><dd>{{ projectionForRecord(record) ? modeLabel(projectionForRecord(record)) : '以正式记录为准' }}</dd><dt>学分</dt><dd>{{ record.credit ?? '待确认' }}（不是已获学分）</dd><dt>上课安排</dt><dd>{{ scheduleText(projectionForRecord(record)) }}</dd></dl>
            <div class="row between"><small>记录 {{ record.recordId || '编号未提供' }} · {{ dateText(record.enrolledAt) }}</small><button v-if="hasAction(projectionForRecord(record), 'DROP')" class="btn small" :disabled="!dropPreflightAvailable || !!actingId || !!pendingOperation || !!coursesError || !!recordsError" :title="dropPreflightAvailable ? '' : '退课资格核验暂不可用，请向教务老师核对'" @click="drop(record)">{{ record.status === 'PENDING_LOTTERY' ? '撤回报名' : '核对退课' }}</button><button v-else-if="projectionForRecord(record)" class="btn small" @click="detailId = String(record.selectionCourseId)">查看课程</button></div>
          </article>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AcademicDecisionTraceCard from '../../components/academic/AcademicDecisionTraceCard.vue'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt } from '../../components/academic/studentAcademicUi'
import { createStudentAcademicCommandGuard, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'

// The shared owner must provide a DROP-specific reader; ENROLL preflight cannot authorize a drop.
const dropPreflightAvailable = typeof portalApi.academicSelectionDropPreflight === 'function'
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'selection')
const loading = ref(true)
const error = ref('')
const coursesError = ref('')
const recordsError = ref('')
const actingId = ref('')
const decisionError = ref(null)
const tab = ref('courses')
const receipt = ref(null)
const receiptTone = ref('success')
const activeBatchId = ref('')
const search = ref('')
const detailId = ref('')
const pendingOperation = ref(null)
const rawGroups = ref([])
const records = ref([])
const availableBatches = ref([])
let requestVersion = 0
let disposed = false
let pageIdentity = ''
let actingToken = 0
let actingIdentity = ''

const groups = computed(() => normalizeGroups(rawGroups.value))
const visibleGroups = computed(() => groups.value.map((group) => ({ ...group, courses: group.courses.filter((course) => !search.value || [course.courseName, course.courseCode, course.teacherName].join(' ').toLowerCase().includes(search.value.toLowerCase())) })).filter((group) => !search.value || group.courses.length))
const detailCourse = computed(() => courseProjectionById.value.get(detailId.value))
const batchOptions = computed(() => availableBatches.value)
const selectedRecords = computed(() => records.value.filter((record) => ['SELECTED', 'LOCKED'].includes(String(record.status || '').toUpperCase())))
const courseCount = computed(() => groups.value.reduce((sum, group) => sum + (group.courses?.length || 0), 0))
const courseProjectionById = computed(() => {
  const map = new Map()
  for (const group of groups.value) {
    for (const course of group.courses || []) map.set(String(course?.selectionCourseId || ''), course)
  }
  return map
})

function normalizeGroups(data) {
  const source = Array.isArray(data) ? data : (data?.items || data?.list || data?.batches || [])
  if (!Array.isArray(source)) return []
  if (source.some((item) => item && item.batch && Array.isArray(item.courses))) {
    return source.map((item) => ({ batch: item.batch || {}, courses: item.courses || [] }))
  }
  if (source.some((item) => item && Array.isArray(item.courses))) {
    return source.map((item) => ({ batch: item.batch || item, courses: item.courses || [] }))
  }
  return source.length ? [{ batch: { batchId: 'current', batchName: '当前可办理课程', status: 'OPEN' }, courses: source }] : []
}
function dateText(value) { return String(value || '').slice(0, 10) || '—' }
const weekdayLabels = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' }
function scheduleText(course) {
  const rows = Array.isArray(course?.scheduleItems) ? course.scheduleItems : []
  if (!rows.length) return '时间待排，以正式课表为准'
  return rows.map((row) => {
    const parity = row.weekParity === 'ODD' ? '单周' : row.weekParity === 'EVEN' ? '双周' : ''
    const weeks = row.startWeek && row.endWeek ? `第${row.startWeek}—${row.endWeek}周` : ''
    return [weekdayLabels[Number(row.weekday)] || `周${row.weekday}`, `第${row.slotNo}节`, parity, weeks, row.classroom].filter(Boolean).join(' · ')
  }).join('；')
}
function windowText(batch) {
  const start = dateText(batch.selectStartAt || batch.windowStart || batch.startAt)
  const end = dateText(batch.selectEndAt || batch.windowEnd || batch.endAt)
  return start === '—' && end === '—' ? '办理窗口以教务处设置为准' : `${start} 至 ${end}`
}
function hasAction(course, action) {
  const wanted = String(action || '').toUpperCase()
  return Array.isArray(course?.allowedActions)
    && course.allowedActions.some((value) => String(value || '').toUpperCase() === wanted)
}
function sameIdentity(left, right) {
  return left !== undefined && left !== null && left !== '' && right !== undefined && right !== null && right !== '' && String(left) === String(right)
}
function stableCommandId(value) {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) return ''
  const text = String(value ?? '').trim()
  if (!text || text.length > 128 || [...text].some((character) => character.charCodeAt(0) <= 31 || character.charCodeAt(0) === 127)) return ''
  return text
}
function dropPreflightMatches(preflight, operation) {
  if (String(preflight?.action || '').toUpperCase() !== 'DROP') return false
  if (!sameIdentity(preflight?.selectionCourseId, operation.course.selectionCourseId)) return false
  const expectedRecordId = operation.course.recordId || operation.course.selectionRecordId
  if (expectedRecordId && !sameIdentity(preflight?.selectionRecordId, expectedRecordId)) return false
  const expectedBatchId = operation.course.batchId || operation.course.selectionBatchId || operation.batchId
  return !expectedBatchId || sameIdentity(preflight?.batchId, expectedBatchId)
}
function projectionForRecord(record) {
  return courseProjectionById.value.get(String(record?.selectionCourseId || '')) || null
}
function remain(course) {
  if (course.remain == null || course.remain === '') return null
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
function courseStatusText(course) {
  return course?.statusLabel || course?.status || '待确认'
}
function recordStatusText(status) {
  const map = { SELECTED: '已取得名额', DROPPED: '已退', CANCELLED: '已取消', COURSE_CANCELLED: '课程已取消', PENDING: '待抽签', PENDING_LOTTERY: '已报名等待抽签', LOST: '未中签', LOTTERY_LOST: '未中签', LOCKED: '名单已锁定', REJECTED: '未通过' }
  return map[String(status || '').toUpperCase()] || status || '待确认'
}
const rowsOf = (data) => Array.isArray(data) ? data : (data?.items || data?.list || [])
function isLottery(course) { return String(course?.mode || course?.lottery?.mode || '').toUpperCase() === 'LOTTERY' }
function selectionMode(course) { return isLottery(course) ? '抽签报名 · 不保证名额' : '选课办理 · 提交时核对名额' }
function modeLabel(course) { return String(course?.mode || course?.lottery?.mode || '').toUpperCase() === 'FCFS' ? '先到先得' : selectionMode(course).split(' · ')[0] }
function roomsText(course) { return [...new Set((course?.scheduleItems || []).map(row => row.classroom).filter(Boolean))].join('、') || '待公布' }
function meetingTimes(course) { return (course?.scheduleItems || []).map(row => [weekdayLabels[Number(row.weekday)] || '星期待定', row.slotLabel || (row.slotNo ? '第' + row.slotNo + '节' : '节次待定'), row.weekParity === 'ODD' ? '单周' : row.weekParity === 'EVEN' ? '双周' : ''].filter(Boolean).join(' ')).join('；') || '时间待排，以正式课表为准' }
function weeksText(course) { return [...new Set((course?.scheduleItems || []).map(row => row.startWeek && row.endWeek ? '第' + row.startWeek + '—' + row.endWeek + '周' : '').filter(Boolean))].join('、') || '待公布' }
const detailBatch = computed(() => groups.value.find(group => group.courses.some(course => String(course.selectionCourseId) === detailId.value))?.batch || {})
const visibleCourseCount = computed(() => visibleGroups.value.reduce((sum, group) => sum + group.courses.length, 0))
const sampledAt = computed(() => {
  const times = groups.value.flatMap(group => group.courses.map(course => course.sampledAt || course.capacitySampledAt || course.evaluatedAt || group.batch.sampledAt)).filter(Boolean)
  return times.length ? String(times.sort().at(-1)).replace('T', ' ').slice(11,16) : '时间未提供'
})
function clearForbidden(e) {
  guard.invalidate()
  requestVersion += 1
  rawGroups.value = []; records.value = []; availableBatches.value = []
  receipt.value = null; pendingOperation.value = null; detailId.value = ''; decisionError.value = null
  coursesError.value = recordsError.value = error.value = academicErrorMessage(e)
  loading.value = false
}
function startActing(id) {
  const token = ++actingToken
  actingIdentity = studentAcademicIdentity(session)
  actingId.value = String(id)
  return token
}
function finishActing(token, identity) {
  if (token === actingToken && identity === studentAcademicIdentity(session)) { actingId.value = ''; actingIdentity = '' }
}
function keepPendingAfterDeleteFailure(operation) {
  pendingOperation.value = operation
  receiptTone.value = 'waiting'
  receipt.value = academicReceipt({ title: '本次办理结果待确认', object: operation.course?.courseName || '原选课对象', status: '已读取正式记录，但本地待确认引用未能安全清除', next: '请只查询本人正式记录；确认本地引用已安全清除前，不会再次提交选课或退课。' })
}
function settleConfirmedOperation(operation, record) {
  if (!guard.completePersistentCommand(operation.persistent)) {
    keepPendingAfterDeleteFailure(operation)
    return false
  }
  setFormalReceipt(operation.course, record, operation.action)
  pendingOperation.value = null
  return true
}
async function load(batchId = activeBatchId.value) {
  const version = ++requestVersion
  const identity = studentAcademicIdentity(session)
  if ((pageIdentity && pageIdentity !== identity) || (actingId.value && actingIdentity !== identity)) {
    actingToken += 1
    actingId.value = ''; actingIdentity = ''
    pendingOperation.value = null
    receipt.value = null
  }
  pageIdentity = identity
  loading.value = true
  error.value = coursesError.value = recordsError.value = ''
  decisionError.value = null
  detailId.value = ''
  rawGroups.value = []; records.value = []
  const [coursesResult, recordsResult] = await Promise.allSettled([
    portalApi.academicCourseSelection(batchId || undefined),
    portalApi.academicSelectionRecords(batchId || undefined)
  ])
  if (disposed || version !== requestVersion || identity !== studentAcademicIdentity(session)) return
  const forbidden = [coursesResult, recordsResult].find((result) => result.status === 'rejected' && academicErrorKind(result.reason) === 'forbidden')
  if (forbidden) { clearForbidden(forbidden.reason); return }
  if (coursesResult.status === 'fulfilled') {
    rawGroups.value = coursesResult.value || []
    if (!batchId) availableBatches.value = normalizeGroups(coursesResult.value).map((group) => group.batch).filter((batch) => batch?.batchId)
  } else coursesError.value = academicErrorMessage(coursesResult.reason, '可办理课程读取失败')
  if (recordsResult.status === 'fulfilled') records.value = rowsOf(recordsResult.value)
  else recordsError.value = academicErrorMessage(recordsResult.reason, '本人选课记录读取失败')
  error.value = coursesError.value && recordsError.value ? `${coursesError.value}；${recordsError.value}` : ''
  restorePersistentOperation()
  loading.value = false
}
function changeBatch() { receipt.value = null; load(activeBatchId.value) }
async function refreshRecords(context = { batchId: activeBatchId.value, version: requestVersion }) {
  const identity = context.identity || studentAcademicIdentity(session)
  try {
    const data = rowsOf(await portalApi.academicSelectionRecords(context.batchId || undefined))
    if (disposed || context.version !== requestVersion || context.batchId !== activeBatchId.value || identity !== studentAcademicIdentity(session)) return null
    records.value = data; recordsError.value = ''
    return data
  } catch (e) {
    if (disposed || context.version !== requestVersion || identity !== studentAcademicIdentity(session)) return null
    if (academicErrorKind(e) === 'forbidden') clearForbidden(e)
    else { records.value = []; recordsError.value = academicErrorMessage(e, '本人选课记录读取失败') }
    return null
  }
}
async function reconcile(operation) {
  // 办理后回读本人正式记录；POST 返回或容量快照不能替代正式状态。
  const fresh = await refreshRecords(operation)
  if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session)) return
  const reference = operation.persistent
  const record = reference?.ackId ? fresh?.find((row) => sameIdentity(row.recordId || row.id, reference.ackId) && sameIdentity(row.selectionCourseId, reference.objectId) && (!reference.parentId || sameIdentity(row.batchId, reference.parentId))) : null
  const observed = fresh?.find((row) => sameIdentity(row.selectionCourseId, operation.course.selectionCourseId))
  const expected = operation.action === 'drop' ? ['DROPPED', 'COURSE_CANCELLED'] : ['PENDING_LOTTERY', 'SELECTED', 'LOCKED', 'LOTTERY_LOST', 'COURSE_CANCELLED']
  const confirmed = expected.includes(String(record?.status || '').toUpperCase())
  if (confirmed) {
    if (!settleConfirmedOperation(operation, record)) return
  } else setPendingReceipt(operation.course, observed, reference)
  pendingOperation.value = confirmed ? null : operation
  if (confirmed) {
    try {
      const data = await portalApi.academicCourseSelection(operation.batchId || undefined)
      if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session)) return
      rawGroups.value = data || []; coursesError.value = ''
    } catch (e) {
      if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session)) return
      if (academicErrorKind(e) === 'forbidden') clearForbidden(e)
      else { rawGroups.value = []; coursesError.value = academicErrorMessage(e, '课程办理状态更新失败') }
    }
  }
}
function restorePersistentOperation() {
  const reference = guard.pendingCommands().find((item) => ['ENROLL_SELECTION', 'DROP_SELECTION'].includes(item.action))
  if (!reference) return
  const action = reference.action === 'DROP_SELECTION' ? 'drop' : 'enroll'
  const observed = records.value.find((row) => sameIdentity(row.selectionCourseId, reference.objectId))
  const projection = courseProjectionById.value.get(reference.objectId)
  const course = { ...(projection || observed || {}), selectionCourseId: reference.objectId }
  const operation = { course, action, batchId: activeBatchId.value, version: requestVersion, identity: studentAcademicIdentity(session), persistent: reference }
  const exact = reference.ackId ? records.value.find((row) => sameIdentity(row.recordId || row.id, reference.ackId) && sameIdentity(row.selectionCourseId, reference.objectId) && (!reference.parentId || sameIdentity(row.batchId, reference.parentId))) : null
  const expected = action === 'drop' ? ['DROPPED', 'COURSE_CANCELLED'] : ['PENDING_LOTTERY', 'SELECTED', 'LOCKED', 'LOTTERY_LOST', 'COURSE_CANCELLED']
  if (exact && expected.includes(String(exact.status || '').toUpperCase())) {
    settleConfirmedOperation(operation, exact)
  } else {
    setPendingReceipt(course, observed, reference)
    pendingOperation.value = operation
  }
}
async function confirmPending() {
  if (!pendingOperation.value || actingId.value) return
  const operation = { ...pendingOperation.value, version: requestVersion }
  const token = startActing(operation.course.selectionCourseId)
  try { await reconcile(operation) }
  finally { finishActing(token, operation.identity) }
}
function setFormalReceipt(course, record, action = 'enroll') {
  const status = String(record?.status || '').toUpperCase()
  const name = course?.courseName || record?.courseName || '该课程'
  const map = {
    PENDING_LOTTERY: ['报名已登记，等待抽签', '本次没有保证名额；请继续在“我的选课”核对抽签结果。', 'waiting'],
    SELECTED: ['选课已确认', '已取得课程名额；名单锁定且课表正式发布后再进入正式课表。', 'success'],
    LOCKED: ['选课名单已锁定', '请前往我的课表核对正式教学安排。', 'success'],
    LOTTERY_LOST: ['本次未中签', '没有取得课程名额，可查看其他可办理课程。', 'danger'],
    DROPPED: ['已退出本次选课或报名', '服务器正式记录已更新，可返回课程列表继续办理。', 'success'],
    COURSE_CANCELLED: ['课程已取消', '该课程不再形成有效选课，请留意后续安排。', 'danger']
  }
  const [title, next, tone] = map[status] || ['结果待确认，请勿重复提交', '尚未读到可确认的服务器正式记录，请稍后只查询本人记录。', 'waiting']
  receiptTone.value = tone
  receipt.value = academicReceipt({ title: action === 'drop' && status === 'DROPPED' ? '退课已确认' : title, object: name, status: recordStatusText(status), operatedAt: record?.updatedAt || record?.enrolledAt, next, relatedTo: status === 'LOCKED' ? '/academic/schedule' : '', relatedLabel: '查看我的课表' })
}
function setPendingReceipt(course, observed, reference) {
  receiptTone.value = 'waiting'
  receipt.value = academicReceipt({ title: '本次办理结果待确认', object: course?.courseName || observed?.courseName || '原选课对象', status: observed ? recordStatusText(observed.status) : reference?.ackId ? '尚未读取到原回执对应的本人记录' : '原提交未取得服务端回执编号', next: reference?.ackId ? '请继续只查询本人正式记录，确认前不要重复提交。' : '当前记录不能归因于原提交；刷新不会自动再次提交。' })
}
async function enroll(course) {
  const id = stableCommandId(course?.selectionCourseId)
  if (!id || actingId.value || pendingOperation.value || coursesError.value || recordsError.value || !hasAction(course, 'ENROLL')) return
  const operation = guard.beginCommand({ course: { ...course, selectionCourseId: id }, action: 'enroll', batchId: activeBatchId.value, originalBatchId: stableCommandId(activeBatchId.value || course.batchId), version: requestVersion })
  const token = startActing(id)
  decisionError.value = null
  let submitted = false
  let persistent = null
  try {
    const preflight = await portalApi.academicSelectionPreflight({ selectionCourseId: id })
    if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session) || !guard.isCurrentCommand(operation)) return
    if (preflight?.allowed !== true) {
      decisionError.value = { message: preflight?.message || preflight?.reason || '当前课程未通过选课预检', decisionTrace: preflight?.decisionTrace || null }
      return
    }
    persistent = guard.preparePersistentCommand({ action: 'ENROLL_SELECTION', objectId: id, parentId: operation.originalBatchId })
    if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '选课未发送', object: operation.course.courseName || '原选课对象', status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
    submitted = true
    const result = await portalApi.academicEnroll({ selectionCourseId: id })
    if (!guard.isCurrentCommand(operation)) return
    const acknowledged = result?.selectionCourseId == null || sameIdentity(result.selectionCourseId, id) ? guard.rememberPersistentAck(persistent, result?.recordId) : null
    await reconcile({ ...operation, persistent: acknowledged || persistent })
  } catch (e) {
    if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session) || !guard.isCurrentCommand(operation)) return
    const kind = studentAcademicWriteErrorKind(e)
    if (kind === 'forbidden') { clearForbidden(e); return }
    if (submitted && kind === 'network') await reconcile({ ...operation, persistent })
    else if (submitted && kind === 'conflict') {
      if (!guard.completePersistentCommand(persistent)) {
        keepPendingAfterDeleteFailure({ ...operation, persistent })
        return
      }
      pendingOperation.value = null
      await refreshRecords(operation)
      if (operation.version === requestVersion && operation.identity === studentAcademicIdentity(session)) {
        receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '选课事实已变化', object: operation.course.courseName || '原选课对象', status: '本次办理未确认完成', next: '已保留当前页面，请根据本人正式记录重新核对。' })
        decisionError.value = { message: '业务事实已变化，已重新查询本人记录，请核对后再办理。', decisionTrace: e?.decisionTrace }
      }
    } else {
      if (persistent && !guard.completePersistentCommand(persistent)) keepPendingAfterDeleteFailure({ ...operation, persistent })
      else decisionError.value = { message: academicErrorMessage(e, '选课办理失败'), decisionTrace: e?.decisionTrace || null }
    }
  } finally { finishActing(token, operation.identity) }
}
async function drop(course) {
  const id = stableCommandId(course?.selectionCourseId)
  const projection = Array.isArray(course?.allowedActions) ? course : projectionForRecord(course)
  if (!id || actingId.value || pendingOperation.value || coursesError.value || recordsError.value || !hasAction(projection, 'DROP')) return
  if (!dropPreflightAvailable) { decisionError.value = { message: '退课资格核验暂不可用，请向教务老师核对；当前没有提交退课。' }; return }
  const confirmationBatchId = activeBatchId.value
  const confirmationVersion = requestVersion
  const confirmationIdentity = studentAcademicIdentity(session)
  if (!await systemConfirm({ title: '确认退课', message: `确认退出“${course.courseName || projection?.courseName || '该课程'}”？退课结果须在本人记录中确认。`, confirmText: '确认退课', type: 'danger' })) return
  if (confirmationBatchId !== activeBatchId.value || confirmationVersion !== requestVersion || confirmationIdentity !== studentAcademicIdentity(session)) return
  const operation = guard.beginCommand({ course: { ...course, selectionCourseId: id }, action: 'drop', batchId: confirmationBatchId, originalBatchId: stableCommandId(confirmationBatchId || course.batchId || course.selectionBatchId), version: confirmationVersion })
  const token = startActing(id); decisionError.value = null
  let submitted = false
  let persistent = null
  try {
    const preflight = await portalApi.academicSelectionDropPreflight({ selectionCourseId: id })
    if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session) || !guard.isCurrentCommand(operation)) return
    if (operation.batchId !== activeBatchId.value) return
    if (preflight?.allowed !== true) { decisionError.value = { message: preflight?.message || preflight?.reason || '当前课程未通过退课预检', decisionTrace: preflight?.decisionTrace }; return }
    if (!dropPreflightMatches(preflight, operation)) {
      decisionError.value = { message: '退课预检返回的课程或批次与当前对象不一致，未提交退课。请重新核对。', decisionTrace: preflight?.decisionTrace }
      return
    }
    persistent = guard.preparePersistentCommand({ action: 'DROP_SELECTION', objectId: id, parentId: operation.originalBatchId })
    if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '退课未发送', object: operation.course.courseName || '原选课对象', status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
    submitted = true
    const result = await portalApi.academicDrop({ selectionCourseId: id })
    if (!guard.isCurrentCommand(operation)) return
    const acknowledged = guard.rememberPersistentAck(persistent, result?.recordId)
    await reconcile({ ...operation, persistent: acknowledged || persistent })
  } catch (e) {
    if (disposed || operation.version !== requestVersion || operation.identity !== studentAcademicIdentity(session) || !guard.isCurrentCommand(operation)) return
    const kind = studentAcademicWriteErrorKind(e)
    if (kind === 'forbidden') { clearForbidden(e); return }
    if (submitted && kind === 'network') await reconcile({ ...operation, persistent })
    else if (submitted && kind === 'conflict') {
      if (!guard.completePersistentCommand(persistent)) {
        keepPendingAfterDeleteFailure({ ...operation, persistent })
        return
      }
      pendingOperation.value = null
      await refreshRecords(operation)
      if (operation.version === requestVersion && operation.identity === studentAcademicIdentity(session)) {
        receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '退课事实已变化', object: operation.course.courseName || '原选课对象', status: '本次办理未确认完成', next: '已保留当前页面，请根据本人正式记录重新核对。' })
        decisionError.value = { message: '业务事实已变化，已重新查询本人记录，请核对后再办理。', decisionTrace: e?.decisionTrace }
      }
    } else {
      if (persistent && !guard.completePersistentCommand(persistent)) keepPendingAfterDeleteFailure({ ...operation, persistent })
      else decisionError.value = { message: academicErrorMessage(e, '退课办理失败'), decisionTrace: e?.decisionTrace }
    }
  } finally { finishActing(token, operation.identity) }
}

onMounted(load)
onBeforeUnmount(() => { disposed = true; requestVersion += 1; guard.dispose() })
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.course-table { min-width: 800px; }
.schedule-meta { display:block; margin-top:4px; }
.detail-notice { margin: 14px 0; }
.definition { margin: 14px 0; }
.selection-record { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:16px; }
.receipt .bigmark :deep(svg) { width:26px; height:26px; }
</style>
