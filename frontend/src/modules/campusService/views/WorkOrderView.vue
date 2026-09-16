<template>
  <AppPageShell flat title="学生服务工单" subtitle="查看学生申请、记录办理进度。办结后学生可在“我的办理”查看结果。">
    <template v-if="recordId">
      <AppButton variant="secondary" :disabled="submitting" @click="backToList">返回工单列表</AppButton>
      <AppGlobalState :state="detailState" :description="detailError" @retry="loadDetail" @back="backToList">
        <section v-if="detail?.order" class="work-order-detail">
          <header><h2>{{ detail.order.title }}</h2><AppStatusTag :label="detail.order.statusLabel" /></header>
          <p>{{ detail.order.name }} · {{ detail.order.className }} · {{ detail.order.code }}</p>
          <h3>学生申请说明</h3><p class="work-order-content">{{ detail.order.detail || '未填写补充说明' }}</p>
          <p v-if="notice" role="status">{{ notice }}</p>
          <div v-if="detail.order.allowedActions?.includes('handle')">
            <label for="work-order-note">处理说明（至少 5 字）</label>
            <AppTextarea id="work-order-note" v-model="note" :maxlength="1000" :disabled="submitting" placeholder="填写本次处理结果，学生可查看" />
            <p v-if="actionError" role="alert" class="work-order-error">{{ actionError }}</p>
            <div class="work-order-actions">
              <AppPermissionButton :allowed="detail.order.allowedActions.includes('handle')" code="campusService.workOrder.handle" variant="secondary" :loading="submitting" @click="submit(false)">保存办理进度</AppPermissionButton>
              <AppPermissionButton :allowed="detail.order.allowedActions.includes('complete')" code="campusService.workOrder.handle" :loading="submitting" @click="submit(true)">办结申请</AppPermissionButton>
            </div>
          </div>
          <p v-else>{{ detail.order.actionHint || '当前工单仅可查看' }}</p>
          <h3>办理记录</h3>
          <ol v-if="detail.order.trail?.length" class="work-order-trail"><li v-for="(entry, index) in detail.order.trail" :key="index"><strong>{{ entry.title }}</strong><p class="work-order-content">{{ entry.desc }}</p><AppDateDisplay :value="entry.time" /></li></ol>
          <p v-else>暂无办理记录</p>
        </section>
      </AppGlobalState>
    </template>
    <template v-else>
      <form class="work-order-filters" @submit.prevent="search">
        <label>关键词<AppTextInput v-model="keyword" placeholder="学生姓名、事项或工单编号" /></label>
        <label>办理状态<AppSelect v-model="status" :options="statusOptions" placeholder="" /></label>
        <AppButton @click="search">查询</AppButton>
      </form>
      <AppGlobalState :state="listState" :description="listError" @retry="loadList">
        <DataTable :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="changePage">
          <template #cell-statusLabel="{ row }"><AppStatusTag :label="row.statusLabel" /></template>
          <template #cell-createTime="{ row }"><AppDateDisplay :value="row.createTime" /></template>
          <template #cell-actions="{ row }"><AppButton variant="secondary" @click="open(row.id)">查看与办理</AppButton></template>
        </DataTable>
        <p v-if="!rows.length" class="work-order-empty">当前范围与筛选下暂无服务工单</p>
      </AppGlobalState>
    </template>
  </AppPageShell>
</template>

<script>
import { AppPageShell, AppGlobalState, AppStatusTag, AppPermissionButton, AppTextInput, AppSelect, AppTextarea, AppDateDisplay } from '@/components/common'
import { AppButton } from '@/components/ui'
import { DataTable } from '@/components/business'
import { currentSessionGeneration } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'
import { workOrderApi } from '../api/workOrder.api'

export default {
  name: 'WorkOrderView',
  components: { AppPageShell, AppGlobalState, AppStatusTag, AppPermissionButton, AppTextInput, AppSelect, AppTextarea, AppDateDisplay, AppButton, DataTable },
  data() { return {
    rows: [], keyword: '', status: '', listState: 'loading', listError: '', detailState: 'loading', detailError: '', detail: null,
    pagination: { page: 1, pageSize: 20, total: 0 }, note: '', actionError: '', notice: '', submitting: false, disposed: false, listSeq: 0, detailSeq: 0,
    statusOptions: [{ value: '', label: '全部' }, { value: 'PENDING_HANDLE', label: '待处理' }, { value: 'PROCESSING', label: '处理中' }, { value: 'COMPLETED', label: '已办结' }, { value: 'CLOSED', label: '已关闭' }],
    columns: [{ key: 'name', title: '学生' }, { key: 'className', title: '班级' }, { key: 'title', title: '申请事项' }, { key: 'code', title: '工单编号' }, { key: 'statusLabel', title: '状态' }, { key: 'createTime', title: '申请时间' }, { key: 'actions', title: '操作' }]
  } },
  computed: { recordId() { return String(this.$route.query.recordId || '') } },
  watch: { '$route.query': { immediate: true, handler() { this.listSeq++; this.detailSeq++; this.detail = null; this.note = ''; this.notice = ''; this.actionError = ''; this.recordId ? this.loadDetail() : this.restoreList() } } },
  beforeUnmount() { this.disposed = true; this.listSeq++; this.detailSeq++ },
  methods: {
    current(generation) { return !this.disposed && generation === currentSessionGeneration() },
    restoreList() { const q = this.$route.query; this.keyword = String(q.keyword || ''); this.status = String(q.status || ''); this.pagination.page = Math.max(1, Number(q.page) || 1); this.loadList() },
    async loadList() {
      const seq = ++this.listSeq, generation = currentSessionGeneration(); this.listState = 'loading'; this.listError = ''
      try {
        const data = await workOrderApi.list({ page: this.pagination.page, pageSize: 20, keyword: this.keyword || undefined, status: this.status || undefined })
        if (!this.current(generation) || seq !== this.listSeq) return
        if (!Array.isArray(data?.items)) throw new Error('工单列表未能完整加载，请重试')
        this.rows = data.items; this.pagination.total = data.total; this.listState = 'ready'
      } catch (e) { if (this.current(generation) && seq === this.listSeq) { const err = normalizeUiError(e); this.rows = []; this.listError = err.userMessage; this.listState = err.pageState } }
    },
    async loadDetail() {
      const seq = ++this.detailSeq, generation = currentSessionGeneration(); this.detailState = 'loading'; this.detailError = ''; this.detail = null
      try {
        const data = await workOrderApi.detail(this.recordId)
        if (!this.current(generation) || seq !== this.detailSeq) return
        if (!data?.order) throw new Error('工单详情未能完整加载，请重试')
        this.detail = data; this.detailState = 'ready'
      } catch (e) { if (this.current(generation) && seq === this.detailSeq) { const err = normalizeUiError(e); this.detailError = err.userMessage; this.detailState = err.pageState } }
    },
    async submit(close) {
      if (this.submitting) return
      const order = this.detail?.order
      if (!order?.allowedActions?.includes(close ? 'complete' : 'handle')) return
      if (this.note.trim().length < 5) { this.actionError = '处理说明至少填写 5 个字'; return }
      const generation = currentSessionGeneration(), detailSeq = this.detailSeq, recordId = this.recordId
      const sameOrder = () => this.current(generation) && detailSeq === this.detailSeq && recordId === this.recordId
      this.submitting = true; this.actionError = ''; this.notice = ''
      try {
        await workOrderApi.handle(order.id, { note: this.note.trim(), close, version: order.version })
        if (!sameOrder()) return
        this.note = ''; this.notice = close ? '申请已办结，学生可查看处理结果' : '办理进度已保存'
        await this.loadDetail()
      } catch (e) { if (sameOrder()) this.actionError = normalizeUiError(e).userMessage }
      finally { if (this.current(generation)) this.submitting = false }
    },
    open(id) { this.$router.push({ query: { ...this.$route.query, recordId: String(id) } }) },
    backToList() { const query = { ...this.$route.query }; delete query.recordId; this.$router.push({ query }) },
    search() { this.pagination.page = 1; this.updateFilters() },
    changePage(page) { this.pagination.page = page; this.updateFilters() },
    updateFilters() {
      const query = { keyword: this.keyword || undefined, status: this.status || undefined, page: String(this.pagination.page) }
      if (String(this.$route.query.keyword || '') === this.keyword && String(this.$route.query.status || '') === this.status && String(this.$route.query.page || '1') === query.page) this.loadList()
      else this.$router.replace({ query })
    }
  }
}
</script>

<style scoped>
.work-order-filters { display:flex; align-items:end; gap:16px; margin-bottom:20px; flex-wrap:wrap; }
.work-order-filters label { display:grid; gap:6px; min-width:220px; }
.work-order-detail { margin-top:20px; max-width:960px; background:var(--bg-card, white); padding:24px; border:1px solid var(--line); border-radius:12px; }
.work-order-detail header { display:flex; align-items:center; gap:16px; }.work-order-detail h2 { margin:0; }.work-order-detail h3 { margin-top:24px; }
.work-order-content { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; }.work-order-actions { display:flex; gap:12px; margin-top:16px; }
.work-order-error { color:var(--danger, #b42318); }.work-order-trail { padding-left:24px; }.work-order-trail li { padding:10px 0; }.work-order-empty { text-align:center; padding:24px; color:var(--text-secondary); }
</style>
