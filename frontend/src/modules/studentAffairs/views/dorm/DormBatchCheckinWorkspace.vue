<template>
  <section class="batch-workspace" aria-label="批量入住">
    <div class="batch-toolbar">
      <select v-model="orientationBatchId" aria-label="迎新批次" :disabled="busy || selecting" @change="changeBatch"><option value="">全部迎新批次</option><option v-if="orientationBatchId && !filterOptions.batches.some(item => item.value === orientationBatchId)" :value="orientationBatchId">当前批次 #{{ orientationBatchId }}</option><option v-for="item in filterOptions.batches" :key="item.value" :value="item.value">{{ item.label }}</option></select>
      <select v-model="classId" aria-label="班级" :disabled="busy || selecting" @change="filter"><option value="">全部班级</option><option v-if="classId && !filterOptions.classes.some(item => item.value === classId)" :value="classId">当前班级 #{{ classId }}</option><option v-for="item in filterOptions.classes" :key="item.value" :value="item.value">{{ item.label }}</option></select>
      <AppDormBuildingPicker v-model="buildingId" :disabled="busy || selecting" :options="buildings" placeholder="全部楼栋" @change="filter" />
      <input v-model="keyword" :disabled="busy || selecting" aria-label="搜索预留学生" placeholder="姓名 / 学号" @keyup.enter="filter">
      <button type="button" :disabled="busy" @click="filter">查询</button>
      <button type="button" :disabled="busy" @click="showHistory">办理记录</button>
      <AppPermissionButton :allowed="allowed" code="studentAffairs.dorm.allocation.manage" :disabled="!selection.length || busy || selecting" @click="openConfirm">
        核验并入住{{ selection.length ? `（${selection.length}）` : '' }}
      </AppPermissionButton>
    </div>
    <div class="batch-toolbar" role="status">
      <span>待入住 {{ pagination.total }} · 已选 {{ selection.length }}</span>
      <button type="button" :disabled="!allowed || busy || selecting || loading || !!listError || !pagination.total" @click="selectAll">选择当前筛选全部名单</button>
      <button v-if="selection.length" type="button" :disabled="busy || selecting" @click="selection = []">清空选择</button>
      <span v-if="selecting">正在核对名单 {{ selectionProgress }} / {{ pagination.total }}</span>
      <button v-if="selecting" type="button" @click="cancelSelection">取消读取</button>
      <button v-if="orientationBatchId" type="button" :disabled="busy || selecting" @click="$router.push({path:'/admin/orientation/dorm',query:{batchId:orientationBatchId}})">返回迎新住宿核对</button>
    </div>
    <AppInlineAlert v-if="optionsError" type="warning" :description="optionsError" />
    <button v-if="optionsError" type="button" @click="loadOptions">重试读取批次与班级</button>
    <AppInlineAlert v-if="error" type="danger" :description="error" />
    <section v-if="historyVisible" class="batch-history" aria-label="入住办理记录">
      <div class="batch-toolbar"><h3>办理记录</h3><button type="button" :disabled="busy" @click="showHistory">刷新</button></div>
      <div class="batch-toolbar">
        <button v-for="entry in recent" :key="entry.jobId" type="button" :disabled="busy" @click="openJob(entry.jobId)">
          {{ entry.batchNo.slice(-8) }} · {{ statusLabel(entry.status) }} · {{ entry.total }}
        </button>
        <span v-if="!recent.length && !job" class="muted">暂无本人办理记录</span>
      </div>
      <template v-if="job">
        <div class="batch-progress" role="status">
          <strong>{{ statusLabel(job.status) }}</strong><span>已入住 {{ job.success }}</span><span>待核对 {{ job.failed }}</span><span>未处理 {{ job.pending }}</span>
          <progress :value="job.success + job.failed" :max="job.total" aria-label="批量入住办理进度" />
          <button v-if="busy" type="button" @click="stop = true">{{ stop ? '本段完成后暂停' : '暂停' }}</button>
          <AppPermissionButton v-else-if="job.pending" :allowed="allowed" code="studentAffairs.dorm.allocation.manage" @click="continueJob">继续办理</AppPermissionButton>
        </div>
        <p class="muted">关闭页面会暂停后续办理。已入住结果保留；冲突记录核对后，从待入住名单重新选择。</p>
        <DataTable :columns="receiptColumns" :rows="job.items || []" row-key="itemId" :pagination="{ page: receiptPage, pageSize: 50, total: job.total }" @page-change="receiptChange">
          <template #cell-status="{ row }">{{ statusLabel(row.status) }}</template>
          <template #cell-error="{ row }">{{ row.error || (row.status === 'SUCCESS' ? `${row.result.building} / ${row.result.room} / ${row.result.bedNo}床` : '等待办理') }}</template>
        </DataTable>
      </template>
    </section>

    <AppGlobalState :state="loading ? 'loading' : listError ? 'error' : 'ready'" :description="listError" @retry="load">
      <DataTable :columns="columns" :rows="rows" row-key="stayId" :selectable="allowed && !busy && !selecting" :selected="selection.map(x => x.stayId)" :pagination="pagination" @update:selected="select" @page-change="changePage">
        <template #cell-studentName="{ row }"><strong>{{ row.studentName }}</strong><div class="muted">{{ row.studentNo }}</div></template>
        <template #cell-status>待核验入住</template>
      </DataTable>
      <p v-if="!loading && !listError && !rows.length" class="muted">当前筛选下没有待入住学生。</p>
    </AppGlobalState>

    <AppConfirmDialog v-model:visible="confirmVisible" title="核验到场并办理入住" confirm-text="确认入住" :submitting="busy" @confirm="create">
      <p>本次为 {{ selection.length }} 名学生办理实际入住，沿用各自已预留床位。</p>
      <label class="arrival-check"><input v-model="arrivalConfirmed" type="checkbox"> 已逐人核验本人到场及预留床位</label>
      <AppInlineAlert v-if="confirmError" type="danger" :description="confirmError" />
    </AppConfirmDialog>
  </section>
</template>

<script>
import { AppConfirmDialog, AppDormBuildingPicker, AppGlobalState, AppInlineAlert, AppPermissionButton } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi as api } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  components: { AppConfirmDialog, AppDormBuildingPicker, AppGlobalState, AppInlineAlert, AppPermissionButton, DataTable },
  props: { buildings: { type: Array, default: () => [] }, allowed: Boolean },
  data: () => ({
    orientationBatchId: '', classId: '', filterOptions: {batches:[],classes:[]}, optionsError: '', optionsSequence: 0, selecting: false, selectionSequence: 0, selectionProgress: 0,
    buildingId: '', keyword: '', rows: [], selection: [], loading: false, listError: '', error: '',
    pagination: { page: 1, pageSize: 50, total: 0 }, loadSequence: 0, jobSequence: 0,
    confirmVisible: false, arrivalConfirmed: false, confirmError: '', requestId: '', requestSnapshot: '',
    historyVisible: false, recent: [], job: null, receiptPage: 1, busy: false, stop: false, disposed: false,
    columns: [{ key: 'studentName', title: '学生' }, { key: 'className', title: '班级' }, { key: 'bedLabel', title: '预留床位' }, { key: 'status', title: '状态' }],
    receiptColumns: [{ key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号' }, { key: 'status', title: '结果' }, { key: 'error', title: '床位 / 待核对原因' }]
  }),
  mounted() { this.orientationBatchId = String(this.$route.query.orientationBatchId || ''); this.classId = String(this.$route.query.classId || ''); this.loadOptions(); this.load(); if (this.$route.query.checkinJob) this.openJob(String(this.$route.query.checkinJob)) },
  beforeUnmount() { this.disposed = true; this.stop = true; this.loadSequence++; this.jobSequence++; this.selectionSequence++; this.optionsSequence++ },
  deactivated() { this.stop = true; this.cancelSelection() },
  watch: { '$route.query': { handler(query) { const batch=String(query.orientationBatchId || ''), cls=String(query.classId || ''); if (batch === this.orientationBatchId && cls === this.classId) return; this.orientationBatchId=batch; this.classId=cls; this.filter(); this.loadOptions() } } },
  methods: {
    queryFilters() { return {status:'RESERVED',orientationBatchId:this.orientationBatchId,classId:this.classId,buildingId:this.buildingId,keyword:this.keyword} },
    cancelSelection() { this.selectionSequence++; this.selecting = false },
    async loadOptions() {
      const sequence = ++this.optionsSequence; this.optionsError = ''
      try {
        const {data} = await api.getDormStayFilterOptions(this.orientationBatchId ? {orientationBatchId:this.orientationBatchId} : {})
        if (sequence !== this.optionsSequence) return
        this.filterOptions = data
      } catch(e) { if (sequence === this.optionsSequence) this.optionsError = e.message || '批次与班级读取失败' }
    },
    changeBatch() { this.classId = ''; this.loadOptions(); return this.filter() },
    async selectAll() {
      if (this.busy || this.selecting) return
      const sequence = ++this.selectionSequence, query = this.queryFilters()
      this.selecting = true; this.error = ''; this.selectionProgress = 0; this.selection = []
      const selected = new Map(); let total = null
      try {
        for (let page = 1; ; page++) {
          const {data} = await api.listDormStays({...query,page,pageSize:200})
          if (sequence !== this.selectionSequence || this.disposed) return
          if (!Array.isArray(data?.items)) throw new Error('名单读取失败，请重新查询')
          if (total === null) total = Number(data.total)
          if (!Number.isInteger(total) || total < 0 || total > 5000) throw new Error('每次最多选择5000人，请按批次或班级缩小范围')
          if (Number(data.total) !== total) throw new Error('读取期间名单发生变化，请重新查询后选择')
          for (const row of data.items) {
            if (selected.has(String(row.stayId))) throw new Error('名单顺序发生变化，请重新查询后选择')
            selected.set(String(row.stayId), row)
          }
          this.selectionProgress = selected.size
          if (selected.size === total) break
          if (!data.items.length || selected.size > total) throw new Error('名单发生变化，请重新查询后选择')
        }
        this.selection = [...selected.values()]
        this.pagination.page = 1; await this.load()
      } catch(e) { if (sequence === this.selectionSequence) this.error = e.message || '名单读取失败，请重试' }
      finally { if (sequence === this.selectionSequence) this.selecting = false }
    },
    statusLabel(value) { return ({ PENDING: '待办理', RUNNING: '办理中 / 可继续', SUCCESS: '已完成', FAILED: '待核对', PARTIAL_SUCCESS: '部分完成' })[value] || '状态待核对' },
    async load() {
      const sequence = ++this.loadSequence
      this.loading = true; this.listError = ''; this.rows = []
      try {
        const { data } = await api.listDormStays({ ...this.queryFilters(), ...this.pagination })
        if (sequence !== this.loadSequence) return
        this.rows = data.items; this.pagination.total = data.total
      } catch (e) { if (sequence === this.loadSequence) this.listError = e.message || '待入住名单读取失败' }
      finally { if (sequence === this.loadSequence) this.loading = false }
    },
    filter() {
      this.cancelSelection(); this.selection = []; this.pagination.page = 1
      const query = {...this.$route.query}; delete query.orientationBatchId; delete query.classId
      if (this.orientationBatchId) query.orientationBatchId = this.orientationBatchId
      if (this.classId) query.classId = this.classId
      this.$router.replace({path:this.$route.path,query})
      return this.load()
    },
    changePage(page) { this.pagination.page = page; this.load() },
    select(ids) {
      const visible = new Set(this.rows.map(x => x.stayId))
      this.selection = [...this.selection.filter(x => !visible.has(x.stayId)), ...this.rows.filter(x => ids.includes(x.stayId))]
    },
    openConfirm() { this.arrivalConfirmed = false; this.confirmError = ''; this.confirmVisible = true },
    async create() {
      if (this.busy) return
      if (!this.arrivalConfirmed) { this.confirmError = '请先核验所选学生本人到场及床位。'; return }
      const items = this.selection.map(x => ({ stayId: x.stayId, version: x.version }))
      const snapshot = JSON.stringify(items)
      if (snapshot !== this.requestSnapshot) { this.requestSnapshot = snapshot; this.requestId = crypto.randomUUID() }
      this.busy = true; this.confirmError = ''
      try {
        const { data } = await api.createDormCheckinBatch({ items, arrivalConfirmed: true, clientRequestId: this.requestId })
        if (this.disposed) return
        this.confirmVisible = false; this.selection = []; this.historyVisible = true; this.job = data
        await this.$router.replace({ query: { ...this.$route.query, checkinJob: data.jobId } })
      } catch (e) { this.confirmError = e.message || '未能确认批次结果，可保留本名单重试'; return }
      finally { this.busy = false }
      if (!this.disposed) await this.continueJob()
    },
    async showHistory() {
      this.historyVisible = true; this.error = ''
      try { const result = await api.recentDormCheckinBatches(); if (!this.disposed) this.recent = result.data.items }
      catch (e) { this.recent = []; this.error = e.message || '办理记录读取失败' }
    },
    async openJob(id) {
      if (this.busy) return
      const sequence = ++this.jobSequence
      this.historyVisible = true; this.receiptPage = 1; this.error = ''; this.job = null
      try {
        const result = await api.getDormCheckinBatch(id)
        if (sequence !== this.jobSequence) return
        this.job = result.data
        await this.$router.replace({ query: { ...this.$route.query, checkinJob: id } })
      } catch (e) { if (sequence === this.jobSequence) this.error = e.message || '办理结果读取失败' }
    },
    async receiptChange(page) {
      if (this.busy) return
      const sequence = ++this.jobSequence
      this.receiptPage = page
      try { const result = await api.getDormCheckinBatch(this.job.jobId, { page }); if (sequence === this.jobSequence) this.job = result.data }
      catch (e) { if (sequence === this.jobSequence) this.error = e.message || '回执读取失败' }
    },
    async continueJob() {
      if (this.busy || !this.job?.pending) return
      const id = this.job.jobId
      this.busy = true; this.stop = false; this.error = ''; this.receiptPage = 1
      try {
        do {
          const { data } = await api.continueDormCheckinBatch(id)
          if (this.disposed) return
          this.job = { ...this.job, ...data }
        } while (this.job.pending && !this.stop)
      } catch (e) { this.error = `${e.message || '连接中断'}。请读取办理记录核对进度，已完成学生不会重复办理。` }
      finally {
        if (!this.disposed) {
          try { this.job = (await api.getDormCheckinBatch(id)).data }
          catch { this.error = '暂时无法确认最新进度，请稍后刷新办理记录。' }
          this.busy = false; await this.load()
        }
      }
    }
  }
}
</script>

<style scoped>
.batch-workspace { min-width: 0; }
.batch-toolbar, .batch-progress { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
.batch-toolbar h3 { margin: 0; margin-right: auto; }
.batch-toolbar input, .batch-toolbar select, .batch-toolbar button, .batch-progress button { min-height: 36px; padding: 6px 12px; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-light); border-radius: 6px; }
.batch-toolbar select { max-width: 260px; }
button { cursor: pointer; } button:disabled { cursor: default; opacity: .55; }
.muted { color: var(--text-secondary); font-size: 13px; }
.batch-history { margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--border-light); }
.batch-progress { padding: 12px 0; border-bottom: 1px solid var(--border-light); }
.batch-progress progress { flex: 1; min-width: 140px; accent-color: var(--primary-500); }
.arrival-check { display: flex; align-items: center; gap: 8px; margin: 16px 0; }
:deep(.dt) { border-radius: 0; box-shadow: none; }
:deep(.dt__batch) { background: var(--bg-section); color: var(--text-primary); }
:deep(.dt__batch-clear) { color: var(--text-secondary); }
@media (max-width: 720px) { .batch-toolbar > * { max-width: 100%; } }
</style>
