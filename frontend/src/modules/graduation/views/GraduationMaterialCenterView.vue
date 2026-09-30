<template>
  <section class="mc-page" :class="{ 'is-command-locked': commandLocked }" :aria-busy="commandLocked">
    <header class="mc-hero">
      <div>
        <span>毕业设计材料中心</span>
        <h2>{{ batchStore.selectedBatchName || '当前批次' }}</h2>
        <p>集中查看学生材料、审核状态和归档缺口；只审核当前提交版本，历史版本用于追溯。</p>
      </div>
      <div class="mc-hero__actions">
        <span v-if="commandLocked" class="mc-lock-note" role="status">审核提交中 · 当前审核对象已锁定</span>
        <button type="button" :disabled="loading || commandLocked" @click="load">
          {{ loading ? '刷新中…' : '刷新数据' }}
        </button>
      </div>
    </header>

    <aside v-if="actionReceipt" class="mc-receipt" role="status" aria-live="polite">
      <div>
        <strong>{{ actionReceipt.title }}</strong>
        <span>{{ actionReceipt.result }}</span>
        <small>{{ actionReceipt.next }}</small>
      </div>
      <button type="button" :disabled="commandLocked" @click="actionReceipt = null">知道了</button>
    </aside>

    <div v-if="error" class="mc-error" role="alert">
      <strong>加载失败</strong><span>{{ error }}</span>
      <button type="button" :disabled="commandLocked" @click="load">重试</button>
    </div>
    <div v-else-if="!batchId" class="mc-empty">请先在顶部选择毕业设计批次。</div>

    <template v-else>
      <section class="mc-summary" aria-label="材料中心统计">
        <article v-for="card in cards" :key="card.label">
          <span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.hint }}</small>
        </article>
      </section>

      <nav class="mc-tabs" aria-label="材料视图">
        <button
          v-for="item in tabs"
          :key="item.key"
          type="button"
          :class="{ active: tab === item.key }"
          :aria-pressed="tab === item.key"
          :disabled="commandLocked"
          @click="changeTab(item.key)"
        >{{ item.label }}</button>
      </nav>

      <section class="mc-filters" aria-label="材料筛选">
        <label>
          关键词
          <input
            v-model.trim="filters.keyword"
            type="search"
            :disabled="commandLocked"
            placeholder="姓名、学号、题目或文件名"
            @keyup.enter="search"
          />
        </label>
        <label>
          材料阶段
          <select v-model="filters.stage" :disabled="commandLocked">
            <option value="">全部</option>
            <option v-for="stage in stages" :key="stage.value" :value="stage.value">{{ stage.label }}</option>
          </select>
        </label>
        <label>
          审核状态
          <select v-model="filters.reviewStatus" :disabled="commandLocked || tab === 'pending'">
            <option value="">全部</option>
            <option value="PENDING">待审核</option>
            <option value="RETURNED">已退回</option>
            <option value="APPROVED">已通过</option>
            <option value="NOT_REQUIRED">无需审核</option>
          </select>
        </label>
        <label>
          文件状态
          <select v-model="filters.scanStatus" :disabled="commandLocked || tab === 'security'">
            <option value="">全部</option>
            <option value="CLEAN">可查看</option>
            <option value="PENDING">检查中</option>
            <option value="ERROR">检查失败</option>
            <option value="INFECTED">风险文件</option>
          </select>
        </label>
        <div>
          <button type="button" class="primary" :disabled="commandLocked" @click="search">查询</button>
          <button type="button" :disabled="commandLocked" @click="reset">重置</button>
        </div>
      </section>

      <section class="mc-panel">
        <div v-if="loading" class="mc-empty">正在加载材料台账…</div>
        <div v-else-if="!rows.length" class="mc-empty">当前筛选下没有材料。</div>
        <div v-else ref="tableWrap" class="mc-table-wrap">
          <table v-if="tab !== 'students'">
            <thead>
              <tr>
                <th>学生</th><th>材料</th><th>当前文件</th><th>提交信息</th>
                <th>文件状态</th><th>审核结论</th><th>归档结论</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.materialId">
                <td>
                  <strong>{{ row.studentName }}</strong>
                  <small>{{ row.studentNo }} · {{ row.className || row.classId || '班级待补' }}</small>
                  <small>指导教师：{{ row.advisorName || '待分配' }}</small>
                </td>
                <td>
                  <span>{{ stageLabel(row.stage) }}</span><strong>{{ row.materialName }}</strong>
                  <details><summary>材料编号</summary><small>{{ row.materialCode || '—' }}</small></details>
                </td>
                <td :title="row.fileName">
                  <strong>{{ row.fileName || '尚未提交' }}</strong>
                  <small>当前第 {{ row.currentVersion || 0 }} 版 · 历史 {{ row.historyVersionCount || 0 }} 版</small>
                </td>
                <td>
                  <span>{{ row.uploader || '提交人待同步' }}</span>
                  <small>{{ row.uploadedAt || '尚未提交' }} · {{ sizeText(row.sizeBytes) }}</small>
                </td>
                <td><b :class="tone(row.scanStatus)">{{ scanLabel(row.scanStatus) }}</b></td>
                <td>{{ reviewLabel(row.reviewStatus) }}</td>
                <td>{{ archiveLabel(row.archiveStatus) }}</td>
                <td class="actions">
                  <button v-if="row.readyForBusiness" type="button" :disabled="commandLocked" @click="openReader(row)">在线查看</button>
                  <button v-if="row.readyForBusiness" type="button" :disabled="commandLocked" @click="download(row)">下载</button>
                  <button type="button" :disabled="commandLocked" @click="history(row)">历史版本</button>
                  <button v-if="row.allowedActions?.includes('review')" type="button" :disabled="commandLocked" @click="openReview(row)">通过</button>
                  <button v-if="row.allowedActions?.includes('review')" type="button" :disabled="commandLocked" @click="openReject(row)">退回</button>
                </td>
              </tr>
            </tbody>
          </table>

          <table v-else>
            <thead>
              <tr>
                <th>学生 / 学号</th><th>学院 / 专业 / 班级</th><th>指导教师</th><th>题目</th>
                <th>应交</th><th>缺失</th><th>待审</th><th>退回</th><th>文件异常</th><th>归档结论</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.gdStudentId">
                <td><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }}</small></td>
                <td><span>{{ row.collegeName || row.collegeId || '-' }} / {{ row.majorName || row.majorId || '-' }}</span><small>{{ row.className || row.classId || '-' }}</small></td>
                <td>{{ row.advisorName || '-' }}</td><td>{{ row.topicTitle || '-' }}</td>
                <td>{{ row.requiredCount }}</td><td>{{ row.missingCount }}</td><td>{{ row.pendingReviewCount }}</td>
                <td>{{ row.returnedCount }}</td><td>{{ row.scanAbnormalCount }}</td>
                <td><b :class="row.archiveReady ? 'ok' : 'warn'">{{ row.archiveReady ? '可归档' : '未齐全' }}</b></td>
                <td class="actions"><button type="button" :disabled="commandLocked" @click="openStudent(row)">学生档案</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="mc-pagebar">
          <span>共 {{ result.total || 0 }} 条</span>
          <button type="button" :disabled="commandLocked || page <= 1" @click="goto(page - 1)">上一页</button>
          <b>第 {{ page }} 页</b>
          <button type="button" :disabled="commandLocked || page * pageSize >= Number(result.total || 0)" @click="goto(page + 1)">下一页</button>
        </footer>
      </section>
    </template>

    <div v-if="historyVisible" class="mc-modal-mask" @click.self="closeHistory">
      <section class="mc-modal" role="dialog" aria-modal="true" aria-label="材料历史版本">
        <header>
          <div><strong>{{ historyTitle }}</strong><span>历史版本仅供追溯，不能覆盖当前提交版本</span></div>
          <button type="button" :disabled="commandLocked" @click="closeHistory">关闭</button>
        </header>
        <FileVersionTimeline :items="historyItems" @select="openHistoryVersion" />
      </section>
    </div>

    <div v-if="readerState.visible" class="mc-reader" role="dialog" aria-modal="true" aria-label="毕业设计材料站内阅读器">
      <header class="mc-reader__head">
        <button type="button" class="mc-reader__back" :disabled="commandLocked" @click="closeReader">← 返回材料中心</button>
        <div class="mc-reader__identity">
          <strong>{{ readerState.row?.studentName || '—' }} / {{ readerState.row?.materialName || readerState.file?.fileName || '材料' }} / v{{ readerState.file?.versionNo || readerState.row?.currentVersion || '—' }}</strong>
          <span>{{ scanLabel(readerState.file?.scanStatus || readerState.row?.scanStatus) }}</span>
          <span>{{ reviewLabel(readerState.row?.reviewStatus) }}</span>
          <b v-if="readerIsHistorical">历史版本 v{{ readerState.file?.versionNo || '—' }} · 只读</b>
          <b v-else>当前提交版本</b>
        </div>
        <button v-if="readerState.file?.canDownload" type="button" :disabled="commandLocked" @click="downloadReaderFile">下载当前版本</button>
      </header>
      <div v-if="readerState.error" class="mc-reader__error" role="alert">{{ readerState.error }}</div>
      <main class="mc-reader__body">
        <AppDocumentViewer
          v-if="readerDescriptor"
          :descriptor="readerDescriptor"
          :provider="previewProvider"
          :versions="readerState.versions"
          :files="[]"
          :active-version-id="readerVersionId"
          :canonical-version-id="readerState.row?.currentVersionId || null"
          :allow-download="Boolean(readerState.file?.canDownload) && !commandLocked"
          :show-version-bar="readerState.versions.length > 1"
          :show-file-switcher="false"
          @select-version="selectReaderVersion"
          @download="downloadReaderFile"
          @preview-error="onReaderError"
        />
        <div v-else class="mc-reader__empty">文件安全检查未通过，暂不能预览。</div>
      </main>
    </div>

    <AppConfirmDialog
      v-model:visible="reviewVisible"
      title="审核当前材料版本"
      :message="reviewMessage"
      confirm-text="通过当前版本"
      cancel-text="取消"
      :submitting="reviewing"
      @confirm="confirmReview('APPROVE', $event)"
    />
    <AppConfirmDialog
      v-model:visible="rejectVisible"
      title="退回当前材料版本"
      :message="reviewMessage"
      danger
      require-reason
      reason-label="退回原因"
      confirm-text="退回材料"
      :submitting="reviewing"
      @confirm="confirmReview('REJECT', $event)"
    />
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import FileVersionTimeline from '@/components/file/FileVersionTimeline.vue'
import { normalizeFile } from '@/services/file/fileSdk'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { graduationMaterialCenterApi as api } from '@/modules/graduation/api/graduation-material-center.api'
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()
const batchStore = useGraduationBatchStore()
const batchId = computed(() => batchStore.selectedBatchId)
const tabs = [
  { key: 'files', label: '全部材料' },
  { key: 'students', label: '学生完整性' },
  { key: 'pending', label: '待审核' },
  { key: 'security', label: '文件异常' }
]
const stages = [
  ['TOPIC', '选题'], ['TASKBOOK', '任务书'], ['PROPOSAL', '开题'], ['GUIDANCE', '过程指导'],
  ['MIDTERM', '中期检查'], ['FINAL_DRAFT', '成果初稿'], ['FINAL_APPROVED', '成果定稿'],
  ['PLAGIARISM', '查重'], ['REVIEW', '正式评阅'], ['DEFENSE', '答辩'], ['GRADE', '成绩'], ['ARCHIVE', '归档']
].map(([value, label]) => ({ value, label }))

const tab = ref('files')
const loading = ref(false)
const error = ref('')
const result = ref({ items: [], total: 0 })
const summary = ref({ filteredSummary: {}, archiveSummary: {} })
const page = ref(1)
const pageSize = 20
const filters = reactive({ keyword: '', stage: '', reviewStatus: '', scanStatus: '' })
const tableWrap = ref(null)
const historyVisible = ref(false)
const historyTitle = ref('')
const historyItems = ref([])
const historyRow = ref(null)
const historyVersions = ref([])
const reviewVisible = ref(false)
const rejectVisible = ref(false)
const reviewRow = ref(null)
const reviewing = ref(false)
const reviewSnapshot = ref(null)
const actionReceipt = ref(null)
const previewProvider = api.createPreviewProvider()
const readerState = reactive({
  visible: false,
  row: null,
  file: null,
  versions: [],
  filterSnapshot: null,
  scrollSnapshot: null,
  error: '',
  bodyOverflow: ''
})

let listToken = 0
let historyToken = 0
let readerToken = 0
let reviewToken = 0
let applyingRoute = false

const rows = computed(() => result.value.items || [])
const commandLocked = computed(() => reviewing.value || Boolean(reviewSnapshot.value))
const effective = computed(() => ({
  ...filters,
  reviewStatus: tab.value === 'pending' ? 'PENDING' : filters.reviewStatus,
  scanStatus: tab.value === 'security' ? 'ABNORMAL' : filters.scanStatus
}))
const cards = computed(() => {
  const filtered = summary.value.filteredSummary || {}
  const archive = summary.value.archiveSummary || {}
  return [
    { label: '学生', value: filtered.expectedStudents || 0, hint: '当前筛选' },
    { label: '缺件', value: filtered.missingStudents || 0, hint: '需要补交' },
    { label: '待审', value: filtered.pendingReviewStudents || 0, hint: '需要处理' },
    { label: '文件异常', value: filtered.scanAbnormalStudents || 0, hint: '需要核验' },
    { label: '可归档', value: archive.archiveReadyStudents || 0, hint: '材料齐全' },
    { label: '已归档', value: archive.archivedStudents || 0, hint: '已经完成' }
  ]
})
const reviewMessage = computed(() => {
  const row = reviewRow.value
  return row ? `${row.studentName} · ${row.materialName} · 当前第 ${row.currentVersion || 0} 版` : ''
})
const readerVersionId = computed(() => readerState.file?.fileVersionId ?? readerState.file?.versionId ?? null)
const readerDescriptor = computed(() => readerState.file?.canPreview ? api.previewDescriptor(readerState.file) : null)
const readerIsHistorical = computed(() => Boolean(readerState.file && (
  readerState.file.isCurrent === false ||
  (readerState.row?.currentVersionId && String(readerVersionId.value) !== String(readerState.row.currentVersionId))
)))

function routeText(value) {
  return Array.isArray(value) ? String(value[0] || '') : String(value || '')
}

function routePage(value) {
  const candidate = Number.parseInt(routeText(value), 10)
  return Number.isFinite(candidate) && candidate > 0 ? candidate : 1
}

function normalizeTab(value) {
  const candidate = routeText(value)
  return tabs.some((item) => item.key === candidate) ? candidate : 'files'
}

function applyRouteState(query = route.query) {
  tab.value = normalizeTab(query.tab)
  page.value = routePage(query.page)
  filters.keyword = routeText(query.keyword)
  filters.stage = routeText(query.stage)
  filters.reviewStatus = routeText(query.reviewStatus)
  filters.scanStatus = routeText(query.scanStatus)
}

function buildRouteQuery(overrides = {}) {
  const query = {
    ...route.query,
    batchId: batchId.value ? String(batchId.value) : undefined,
    tab: tab.value,
    page: page.value > 1 ? String(page.value) : undefined,
    keyword: String(filters.keyword || '').trim() || undefined,
    stage: filters.stage || undefined,
    reviewStatus: filters.reviewStatus || undefined,
    scanStatus: filters.scanStatus || undefined,
    ...overrides
  }
  Object.keys(query).forEach((key) => {
    if (query[key] == null || query[key] === '') delete query[key]
  })
  return query
}

async function replaceRouteQuery(overrides = {}) {
  applyingRoute = true
  try {
    await router.replace({ query: buildRouteQuery(overrides) })
  } catch {
    // Vue Router rejects duplicate navigations in some host versions.
  } finally {
    applyingRoute = false
  }
}

function currentReturnTo() {
  return router.resolve({
    path: '/admin/graduation/material-center',
    query: buildRouteQuery()
  }).fullPath
}

function requestParams() {
  return { batchId: batchId.value, page: page.value, pageSize, ...effective.value }
}

function sameListSnapshot(snapshot) {
  return (
    snapshot.batchId === String(batchId.value || '') &&
    snapshot.tab === tab.value &&
    snapshot.page === page.value &&
    snapshot.keyword === String(filters.keyword || '') &&
    snapshot.stage === filters.stage &&
    snapshot.reviewStatus === filters.reviewStatus &&
    snapshot.scanStatus === filters.scanStatus
  )
}

async function load({ syncRoute = false } = {}) {
  const snapshot = {
    batchId: String(batchId.value || ''),
    tab: tab.value,
    page: page.value,
    keyword: String(filters.keyword || ''),
    stage: filters.stage,
    reviewStatus: filters.reviewStatus,
    scanStatus: filters.scanStatus
  }
  const token = ++listToken
  if (!snapshot.batchId) {
    result.value = { items: [], total: 0 }
    summary.value = { filteredSummary: {}, archiveSummary: {} }
    loading.value = false
    error.value = ''
    return false
  }
  loading.value = true
  error.value = ''
  try {
    const params = requestParams()
    const listRequest = snapshot.tab === 'students' ? api.students(params) : api.files(params)
    const [nextResult, nextSummary] = await Promise.all([listRequest, api.summary(params)])
    if (token !== listToken || !sameListSnapshot(snapshot)) return false
    result.value = nextResult
    summary.value = nextSummary
    if (syncRoute) await replaceRouteQuery()
    return true
  } catch (failure) {
    if (token === listToken && sameListSnapshot(snapshot)) {
      error.value = failure?.message || '材料中心加载失败'
    }
    return false
  } finally {
    if (token === listToken && sameListSnapshot(snapshot)) loading.value = false
  }
}

function changeTab(value) {
  if (commandLocked.value || !tabs.some((item) => item.key === value)) return
  tab.value = value
  page.value = 1
  replaceRouteQuery({ tab: value, page: undefined })
  load()
}

function search() {
  if (commandLocked.value) return
  page.value = 1
  replaceRouteQuery({ page: undefined })
  load()
}

function reset() {
  if (commandLocked.value) return
  Object.assign(filters, { keyword: '', stage: '', reviewStatus: '', scanStatus: '' })
  page.value = 1
  replaceRouteQuery({
    page: undefined,
    keyword: undefined,
    stage: undefined,
    reviewStatus: undefined,
    scanStatus: undefined
  })
  load()
}

function goto(value) {
  if (commandLocked.value) return
  page.value = Math.max(1, Number(value) || 1)
  replaceRouteQuery({ page: page.value > 1 ? String(page.value) : undefined })
  load()
}

function sizeText(value) {
  const bytes = Number(value || 0)
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function tone(value) {
  return ['CLEAN', 'PASSED', 'NOT_REQUIRED'].includes(String(value).toUpperCase()) ? 'ok' : 'danger'
}

function stageLabel(value) {
  return stages.find((item) => item.value === value)?.label || '其他材料'
}

function scanLabel(value) {
  return ({
    CLEAN: '可查看',
    PASSED: '可查看',
    PENDING: '检查中',
    ERROR: '检查失败',
    INFECTED: '风险文件',
    NOT_REQUIRED: '无需检查'
  })[String(value || '').toUpperCase()] || '待确认'
}

function reviewLabel(value) {
  return ({
    PENDING: '等待审核',
    RETURNED: '已退回，等待补交',
    APPROVED: '审核通过',
    NOT_REQUIRED: '无需审核'
  })[String(value || '').toUpperCase()] || '审核结论待确认'
}

function archiveLabel(value) {
  return ({
    READY: '可归档',
    ARCHIVED: '已归档',
    MISSING: '缺少材料',
    BLOCKED: '暂不可归档',
    PENDING: '等待归档'
  })[String(value || '').toUpperCase()] || '归档结论待确认'
}

function versionKey(file) {
  return file?.fileVersionId ?? file?.versionId ?? file?.id ?? null
}

function fileRow(row) {
  return normalizeFile({
    fileId: row.fileId,
    fileName: row.fileName,
    assetId: row.assetId,
    versionId: row.currentVersionId,
    fileVersionId: row.currentVersionId,
    versionNo: row.currentVersion,
    isCurrent: true,
    sizeBytes: row.sizeBytes,
    scanStatus: row.scanStatus,
    readyForBusiness: row.readyForBusiness,
    allowedActions: row.allowedActions || []
  })
}

async function fetchMaterialVersions(row, token, batchSnapshot, tokenKind) {
  const library = await api.studentLibrary(row.gdStudentId, true)
  const currentToken = tokenKind === 'history' ? historyToken : readerToken
  if (token !== currentToken || batchSnapshot !== String(batchId.value || '')) return null
  const material = (library.items || []).find((item) => String(item.materialId || '') === String(row.materialId || ''))
  const versions = api.normalizeVersions(material?.versions || [])
  return versions.length ? versions : [fileRow(row)]
}

function captureReaderContext() {
  return {
    filterSnapshot: {
      tab: tab.value,
      page: page.value,
      filters: { ...filters },
      routeQuery: buildRouteQuery()
    },
    scrollSnapshot: {
      windowY: window.scrollY || 0,
      tableTop: tableWrap.value?.scrollTop || 0,
      tableLeft: tableWrap.value?.scrollLeft || 0
    }
  }
}

async function openReader(row, exactFile = null, knownVersions = null) {
  if (!row || commandLocked.value) return
  const token = ++readerToken
  const batchSnapshot = String(batchId.value || '')
  const context = readerState.visible
    ? { filterSnapshot: readerState.filterSnapshot, scrollSnapshot: readerState.scrollSnapshot }
    : captureReaderContext()
  try {
    const versions = knownVersions || await fetchMaterialVersions(row, token, batchSnapshot, 'reader')
    if (!versions || token !== readerToken || batchSnapshot !== String(batchId.value || '')) return
    const exactId = versionKey(exactFile)
    const currentId = row.currentVersionId
    const target = exactFile
      ? (versions.find((item) => String(versionKey(item)) === String(exactId)) || normalizeFile(exactFile))
      : (versions.find((item) => String(versionKey(item)) === String(currentId)) || versions.find((item) => item.isCurrent) || versions[0])
    if (!target?.canPreview) {
      error.value = target?.statusText
        ? `该版本${target.statusText}，不能预览`
        : '文件安全检查未通过，暂不能预览'
      return
    }
    readerState.row = { ...row }
    readerState.file = target
    readerState.versions = versions
    readerState.filterSnapshot = context.filterSnapshot
    readerState.scrollSnapshot = context.scrollSnapshot
    readerState.error = ''
    readerState.bodyOverflow = document.body.style.overflow
    readerState.visible = true
    document.body.style.overflow = 'hidden'
  } catch (failure) {
    if (token === readerToken && batchSnapshot === String(batchId.value || '')) {
      error.value = failure?.message || '材料版本读取失败'
    }
  }
}

function selectReaderVersion(file) {
  if (commandLocked.value) return
  const target = normalizeFile(file || {})
  if (!target.canPreview) {
    readerState.error = target.statusText
      ? `该历史版本${target.statusText}，不能预览`
      : '该历史版本未通过安全检查，不能预览'
    return
  }
  readerState.file = target
  readerState.error = ''
}

function onReaderError(payload) {
  readerState.error = payload?.message || payload?.error?.message || '材料预览失败，请重试'
}

async function closeReader() {
  if (commandLocked.value) return
  ++readerToken
  const filterSnapshot = readerState.filterSnapshot
  const scrollSnapshot = readerState.scrollSnapshot
  document.body.style.overflow = readerState.bodyOverflow || ''
  readerState.visible = false
  readerState.row = null
  readerState.file = null
  readerState.versions = []
  readerState.error = ''
  if (filterSnapshot) {
    tab.value = filterSnapshot.tab
    page.value = filterSnapshot.page
    Object.assign(filters, filterSnapshot.filters)
    await router.replace({ query: filterSnapshot.routeQuery }).catch(() => {})
  }
  await nextTick()
  window.requestAnimationFrame(() => {
    if (tableWrap.value && scrollSnapshot) {
      tableWrap.value.scrollTop = scrollSnapshot.tableTop
      tableWrap.value.scrollLeft = scrollSnapshot.tableLeft
    }
    if (scrollSnapshot) window.scrollTo(0, scrollSnapshot.windowY)
  })
}

async function download(row) {
  if (commandLocked.value) return
  try {
    await api.downloadMaterial(fileRow(row))
  } catch (failure) {
    error.value = failure?.message || '下载失败'
  }
}

async function downloadReaderFile() {
  if (commandLocked.value || !readerState.file?.canDownload) return
  try {
    await api.downloadMaterial(readerState.file)
  } catch (failure) {
    readerState.error = failure?.message || '下载失败'
  }
}

async function history(row) {
  if (!row || commandLocked.value) return
  const token = ++historyToken
  const batchSnapshot = String(batchId.value || '')
  try {
    const versions = await fetchMaterialVersions(row, token, batchSnapshot, 'history')
    if (!versions || token !== historyToken || batchSnapshot !== String(batchId.value || '')) return
    historyRow.value = { ...row }
    historyVersions.value = versions
    historyTitle.value = `${row.studentName} · ${row.materialName}`
    historyItems.value = versions.map((version) => ({
      bindingId: version.bindingId || versionKey(version),
      versionNo: version.versionNo,
      isCurrent: version.isCurrent,
      boundAt: version.submittedAt,
      file: version
    }))
    historyVisible.value = true
  } catch (failure) {
    if (token === historyToken && batchSnapshot === String(batchId.value || '')) {
      error.value = failure?.message || '版本历史加载失败'
    }
  }
}

function closeHistory() {
  if (commandLocked.value) return
  ++historyToken
  historyVisible.value = false
}

async function openHistoryVersion(item) {
  const row = historyRow.value
  const file = item?.file
  const versions = historyVersions.value
  historyVisible.value = false
  await openReader(row, file, versions)
}

function openStudent(row) {
  if (commandLocked.value || !row?.gdStudentId) return
  router.push({
    name: 'graduation-student-detail',
    params: { id: String(row.gdStudentId) },
    query: {
      batchId: String(batchId.value),
      source: 'material-center',
      returnTo: currentReturnTo()
    }
  })
}

function openReview(row) {
  if (!row || commandLocked.value) return
  reviewRow.value = { ...row }
  reviewVisible.value = true
}

function openReject(row) {
  if (!row || commandLocked.value) return
  reviewRow.value = { ...row }
  rejectVisible.value = true
}

function freezeReviewTarget(row, action, reason) {
  return Object.freeze({
    materialId: String(row.materialId),
    gdStudentId: String(row.gdStudentId),
    studentName: row.studentName,
    materialName: row.materialName,
    fileVersionId: String(row.currentVersionId),
    expectedVersion: row.version,
    batchId: String(batchId.value),
    action,
    reason: String(reason || ''),
    routeQuery: buildRouteQuery()
  })
}

async function readReviewTruth(target, token) {
  const library = await api.studentLibrary(target.gdStudentId, true)
  if (
    token !== reviewToken ||
    target.batchId !== String(batchId.value || '') ||
    reviewSnapshot.value !== target
  ) return null
  return (library.items || []).find((item) => String(item.materialId || '') === target.materialId) || null
}

async function confirmReview(action, payload) {
  if (!reviewRow.value || commandLocked.value) return
  const target = freezeReviewTarget(reviewRow.value, action, payload?.reason || '')
  const token = ++reviewToken
  reviewSnapshot.value = target
  reviewing.value = true
  error.value = ''
  try {
    await api.reviewMaterial(target.materialId, {
      fileVersionId: target.fileVersionId,
      expectedVersion: target.expectedVersion,
      action: target.action,
      comment: target.reason
    })
    reviewVisible.value = false
    rejectVisible.value = false

    const [loaded, latest] = await Promise.all([
      load(),
      readReviewTruth(target, token)
    ])
    if (
      token !== reviewToken ||
      reviewSnapshot.value !== target ||
      target.batchId !== String(batchId.value || '')
    ) return

    const expectedStatus = action === 'APPROVE' ? 'APPROVED' : 'RETURNED'
    const latestStatus = String(latest?.reviewStatus || '').toUpperCase()
    if (!latest || latestStatus !== expectedStatus) {
      throw new Error('审核请求已提交，但最新材料状态尚未确认；请刷新核对，勿重复提交。')
    }
    if (!loaded && tab.value !== 'pending') {
      throw new Error('审核已完成，但当前列表刷新失败；请重新打开材料中心核对。')
    }

    actionReceipt.value = {
      title: `${target.studentName} · ${target.materialName} 已处理`,
      result: `最新结论：${reviewLabel(latestStatus)} · 当前提交版本已核对`,
      next: action === 'APPROVE'
        ? '该版本已进入后续完整性与归档校验。'
        : '下一步由学生按退回原因补交新版本。'
    }
    toast.success('材料审核已完成，最新状态已确认')
  } catch (failure) {
    if (token === reviewToken && reviewSnapshot.value === target) {
      error.value = failure?.message || '审核失败'
    }
  } finally {
    if (token === reviewToken && reviewSnapshot.value === target) {
      reviewing.value = false
      reviewSnapshot.value = null
      reviewRow.value = null
    }
  }
}

watch(
  () => route.query,
  (query) => {
    if (applyingRoute) return
    if (commandLocked.value && reviewSnapshot.value) {
      router.replace({ query: reviewSnapshot.value.routeQuery }).catch(() => {})
      return
    }
    const nextState = {
      tab: normalizeTab(query.tab),
      page: routePage(query.page),
      keyword: routeText(query.keyword),
      stage: routeText(query.stage),
      reviewStatus: routeText(query.reviewStatus),
      scanStatus: routeText(query.scanStatus)
    }
    const changed = (
      nextState.tab !== tab.value ||
      nextState.page !== page.value ||
      nextState.keyword !== filters.keyword ||
      nextState.stage !== filters.stage ||
      nextState.reviewStatus !== filters.reviewStatus ||
      nextState.scanStatus !== filters.scanStatus
    )
    if (!changed) return
    applyRouteState(query)
    load()
  },
  { deep: true }
)

watch(batchId, (nextBatchId) => {
  if (commandLocked.value && reviewSnapshot.value) {
    if (String(nextBatchId || '') !== reviewSnapshot.value.batchId) {
      batchStore.selectBatch(reviewSnapshot.value.batchId)
      router.replace({ query: reviewSnapshot.value.routeQuery }).catch(() => {})
    }
    return
  }
  ++listToken
  ++historyToken
  ++readerToken
  page.value = 1
  actionReceipt.value = null
  reviewVisible.value = false
  rejectVisible.value = false
  replaceRouteQuery({ batchId: nextBatchId ? String(nextBatchId) : undefined, page: undefined })
  load()
})

onBeforeRouteLeave((_to, _from, next) => {
  if (commandLocked.value) {
    toast.info('当前材料审核正在等待处理结果，请完成后再离开')
    next(false)
    return
  }
  next()
})

onBeforeUnmount(() => {
  ++listToken
  ++historyToken
  ++readerToken
  ++reviewToken
  previewProvider?.dispose?.()
  if (readerState.visible) document.body.style.overflow = readerState.bodyOverflow || ''
})

onMounted(async () => {
  applyRouteState()
  await batchStore.ensureLoaded({ batchIdFromUrl: routeText(route.query.batchId) })
  await load()
})
</script>

<style scoped>
.mc-page{display:grid;gap:12px;min-width:0}.mc-hero,.mc-panel,.mc-filters{background:#fff;border:1px solid #dfe7f3;border-radius:12px}.mc-hero{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 18px;background:linear-gradient(135deg,#f7fbff,#eef5ff)}.mc-hero span{color:#1769e0;font-size:11px;font-weight:700;letter-spacing:.08em}.mc-hero h2{margin:3px 0;font-size:18px}.mc-hero p{margin:0;color:#69768b;font-size:12px}.mc-hero__actions{display:flex;align-items:center;gap:10px}.mc-lock-note{padding:4px 8px;border-radius:999px;background:#fff7df;color:#8a5b00!important;letter-spacing:0!important}.mc-page button{border:1px solid #ccd8e8;border-radius:8px;background:#fff;color:#29415f;padding:7px 11px;cursor:pointer}.mc-page button:disabled{cursor:not-allowed;opacity:.45}.mc-page .primary{background:#1769e0;border-color:#1769e0;color:#fff}.mc-error,.mc-empty{padding:22px;text-align:center;color:#69768b}.mc-error{display:flex;gap:12px;align-items:center;text-align:left;border-radius:12px;background:#fff1f1;color:#a61b1b}.mc-error button{margin-left:auto}.mc-summary{display:grid;grid-template-columns:repeat(6,minmax(100px,1fr));gap:8px}.mc-summary article{display:grid;gap:2px;padding:10px 12px;border:1px solid #e2e8f2;border-radius:10px;background:#fff}.mc-summary strong{font-size:20px}.mc-summary small,td small{display:block;color:#7b8798}.mc-tabs{display:flex;gap:4px;border-bottom:1px solid #dfe7f3}.mc-tabs button{border:0;border-radius:8px 8px 0 0;padding:9px 15px}.mc-tabs button.active{background:#1769e0;color:#fff}.mc-filters{display:grid;grid-template-columns:1.6fr repeat(3,1fr) auto;gap:10px;align-items:end;padding:12px}.mc-filters label{display:grid;gap:4px;color:#526176;font-size:12px}.mc-filters input,.mc-filters select{min-width:0;border:1px solid #ccd8e8;border-radius:8px;padding:8px;background:#fff}.mc-filters>div{display:flex;gap:7px}.mc-panel{overflow:hidden}.mc-table-wrap{max-height:66vh;overflow:auto}table{width:100%;min-width:1080px;border-collapse:collapse}th,td{padding:9px 11px;border-bottom:1px solid #edf1f7;text-align:left;vertical-align:top;font-size:12px}th{position:sticky;top:0;z-index:1;background:#f7f9fc;color:#526176;white-space:nowrap}td strong,td span{display:block}td details{margin-top:4px;color:#7b8798;font-size:10px}td summary{cursor:pointer}.actions{white-space:nowrap}.actions button{border:0;padding:4px 5px;color:#1769e0}.ok,.warn,.danger{display:inline-block!important;padding:2px 7px;border-radius:999px}.ok{color:#137a43;background:#eafaf1}.warn{color:#9a5b00;background:#fff7df}.danger{color:#b42318;background:#fff0f0}.mc-pagebar{display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:11px 14px}.mc-pagebar span{margin-right:auto;color:#69768b}.mc-modal-mask{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(15,23,42,.42)}.mc-modal{width:min(680px,100%);max-height:80vh;overflow:auto;padding:20px;border-radius:14px;background:#fff;box-shadow:0 18px 60px rgba(15,23,42,.2)}.mc-modal>header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px}.mc-modal>header div{display:grid;gap:4px}.mc-modal>header span{color:#69768b;font-size:13px}.mc-reader{position:fixed;inset:0;z-index:1200;display:grid;grid-template-rows:auto auto minmax(0,1fr);background:#f4f7fb}.mc-reader__head{display:flex;align-items:center;gap:14px;padding:10px 14px;border-bottom:1px solid #dfe7f3;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.06)}.mc-reader__back{flex:none}.mc-reader__identity{display:flex;flex:1;min-width:0;align-items:center;gap:8px}.mc-reader__identity strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc-reader__identity span,.mc-reader__identity b{flex:none;padding:3px 7px;border-radius:999px;background:#eef4ff;color:#315986;font-size:11px}.mc-reader__identity b{background:#fff7df;color:#8a5b00}.mc-reader__error{padding:7px 14px;background:#fff1f1;color:#a61b1b;font-size:12px}.mc-reader__body{min-height:0;padding:12px;overflow:hidden}.mc-reader__body :deep(.document-viewer){height:100%}.mc-reader__body :deep(.document-viewer__body){min-height:0}.mc-reader__empty{display:grid;height:100%;place-items:center;border:1px dashed #ccd8e8;border-radius:12px;background:#fff;color:#69768b}.mc-receipt{display:flex;align-items:center;gap:16px;padding:11px 13px;border:1px solid #b7ebc6;border-radius:10px;background:#f0fff4}.mc-receipt div{display:grid;flex:1;gap:2px}.mc-receipt strong{color:#137a43}.mc-receipt span{color:#29415f;font-size:12px}.mc-receipt small{color:#69768b}.is-command-locked .mc-tabs,.is-command-locked .mc-filters,.is-command-locked .mc-table-wrap,.is-command-locked .mc-pagebar{cursor:progress}@media(max-width:1100px){.mc-summary{grid-template-columns:repeat(3,1fr)}.mc-filters{grid-template-columns:repeat(2,1fr)}.mc-reader__identity{flex-wrap:wrap}.mc-reader__identity strong{width:100%}}@media(max-width:700px){.mc-hero{display:grid;gap:12px}.mc-hero__actions{justify-content:space-between}.mc-summary{grid-template-columns:repeat(2,1fr)}.mc-filters{grid-template-columns:1fr}.mc-tabs{overflow:auto}.mc-reader__head{align-items:flex-start;flex-wrap:wrap}.mc-reader__identity{order:3;width:100%}}
</style>
