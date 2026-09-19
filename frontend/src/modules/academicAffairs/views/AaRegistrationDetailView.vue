<template>
  <ModulePageShell
    title="注册名单"
    subtitle="先核对本批次候选与资格，再预览注册；正式记录按真实状态回读。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton :disabled="applying" @click="goBack">{{ $route.query.returnToken ? '返回原位置' : '返回批次列表' }}</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="当前注册批次">
        <p class="mp-note">批次 ID：{{ batchId }}<template v-if="batchRecord && batchContext === detailContext"> · {{ batchRecord.batchName || '名称未提供' }}</template></p>
        <p><AppStatusTag :status="batchState" dot>{{ batchStateLabel }}</AppStatusTag></p>
        <AppInlineAlert v-if="batchError" type="warning">{{ batchError }}</AppInlineAlert>
        <AppButton :disabled="applying || batchLoading" @click="load">{{ batchLoading ? '正在核对批次…' : '重新核对批次与记录' }}</AppButton>
      </AppSectionCard>
      <AppSectionCard :title="batchState === 'OPEN' ? '批量办理注册' : '批次记录查看'">
        <AaRegistrationBulkPanel :batch-id="batchId" :batch-state="batchState" :ctx="ctx" @busy="applying = $event" @applied="load" @recheck="load" />
      </AppSectionCard>

      <AppSectionCard title="注册记录与当前状态">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="本批次暂无注册记录" description="资格核验与正式注册的记录在此回读，以每条记录的当前状态为准" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          row-key="registrationId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-status="{ row }">
            <AppStatusTag :type="row.status === 'REGISTERED' ? 'success' : 'warning'" dot>{{ registrationStateLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-registerAt="{ row }">{{ registrationTime(row.registerAt) }}</template>
        </DataTable>
      </AppSectionCard>
      <p class="mp-note">后续办理：返回批次队列核对其余候选、暂缓与异常；批次关闭和归档由具备相应权限的岗位办理。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 注册名单：D2-U 以权威候选→批量预览→逐项 canonical 注册替代人工逐个挑学生提交。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppInlineAlert } from '@/components/common'
import AaRegistrationBulkPanel from '@/modules/academicAffairs/components/AaRegistrationBulkPanel.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import { formatDateTime } from '@/utils/dateUtils'

const BATCH_STATUS = { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已关闭', ARCHIVED: '已归档' }

export default {
  name: 'AaRegistrationDetailView',
  components: {
    ModulePageShell,
    DataTable,
    LoadingState,
    ErrorState,
    EmptyState,
    AppButton,
    AppSectionCard,
    AppStatusTag,
    AppInlineAlert,
    AaRegistrationBulkPanel
  },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loading: true,
      applying: false, requestVersion: 0, disposed: false,
      error: '',
      batchRecord: null, batchContext: '', batchError: '', batchLoading: true, batchDenied: false,
      rows: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
      columns: [
        { key: 'realName', title: '学生' },
        { key: 'registerAt', title: '注册时间（本地）' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  computed: {
    detailContext() { return JSON.stringify([String(this.batchId), this.ctx]) },
    canRead() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.view') },
    batchState() {
      if (!this.canRead || this.batchLoading || this.batchDenied || this.batchContext !== this.detailContext || String(this.batchRecord?.batchId) !== String(this.batchId)) return 'UNKNOWN'
      return Object.hasOwn(BATCH_STATUS, this.batchRecord?.status) ? this.batchRecord.status : 'UNKNOWN'
    },
    batchStateLabel() { return BATCH_STATUS[this.batchState] || '批次状态待核对' },
    batchId() {
      return this.$route.params.batchId
    }
  },
  created() {
    this.load()
  },
  watch: { batchId() { this.pagination.page = 1; this.load() }, ctx: { deep: true, handler() { this.load() } } },
  beforeRouteUpdate(to, from, next) { next(!this.applying) },
  beforeRouteLeave(to, from, next) { next(!this.applying) },
  beforeUnmount() { this.disposed = true; this.requestVersion++ },
  methods: {
    goBack() { if (this.applying) return; if (this.$route.query.returnToken && this.academicFlow) this.academicFlow.back(this.$route.query.returnToken, '/admin/academic-affairs/registration'); else this.$router.push('/admin/academic-affairs/registration') },
    registrationStateLabel(status) { return { REGISTERED: '已注册', PENDING_REGISTER: '待注册', UNREGISTERED: '本批次未注册' }[status] || '状态待确认' },
    registrationTime(value) { return formatDateTime(value, '未提供') },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    loadCurrent(version, context) { return !this.disposed && version === this.requestVersion && context === this.detailContext },
    isReadForbidden(res) { return String(res?.code).startsWith('403') || ['NO_PERMISSION', 'NO_DATA_SCOPE'].includes(res?.bizCode) },
    denyCurrentBatch(message) {
      this.batchDenied = true; this.batchRecord = null; this.batchContext = ''; this.rows = []; this.pagination.total = 0
      this.batchError = message || '当前身份无法核对原批次，已暂停注册办理'
    },
    async loadBatch(version, context, batchId) {
      try {
        for (let page = 1; page <= 5; page++) {
          const res = await academicAffairsApi.getRegistrationBatches({ page, pageSize: 100 })
          if (!this.loadCurrent(version, context) || this.batchDenied) return
          if (this.isReadForbidden(res)) { this.denyCurrentBatch(res?.message); return }
          if (res?.code !== 0 || !Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data.total) || res.data.total < 0) throw new Error(res?.message || '批次列表回执不完整')
          const row = res.data.list.find(item => String(item.batchId) === batchId)
          if (row) {
            if (!Object.hasOwn(BATCH_STATUS, row.status) || !['ENROLL', 'ANNUAL', 'SEMESTER'].includes(row.registerType)) throw new Error('原批次类型或状态未能核对')
            this.batchRecord = { ...row }; this.batchContext = context; return
          }
          if (page * 100 >= res.data.total) break
        }
        this.batchError = '在本次最多 500 条批次中未定位原 ID，不能推定批次不存在或仍开放；请重新核对。'
      } catch (error) {
        if (this.loadCurrent(version, context)) this.batchError = error?.message || '批次状态读取失败，暂不开放注册办理'
      } finally { if (this.loadCurrent(version, context)) this.batchLoading = false }
    },
    async loadRecords(version, context, batchId) {
      try {
        const res = await academicAffairsApi.getRegistrations(batchId, { page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (!this.loadCurrent(version, context) || this.batchDenied) return
        if (this.isReadForbidden(res)) { this.denyCurrentBatch(res?.message); this.error = res?.message || '当前身份无权读取注册记录'; return }
        if (res?.code === 0 && Array.isArray(res.data?.list) && Number.isSafeInteger(res.data.total) && res.data.total >= 0) {
          this.rows = res.data.list; this.pagination.total = res.data.total
        } else this.error = res?.message || '注册记录读取失败，请重试'
      } catch {
        if (this.loadCurrent(version, context)) this.error = '注册记录读取失败，请重试'
      } finally { if (this.loadCurrent(version, context)) this.loading = false }
    },
    async load() {
      const version = ++this.requestVersion, context = this.detailContext, batchId = String(this.batchId)
      this.loading = true; this.rows = []; this.error = ''; this.batchRecord = null; this.batchContext = ''; this.batchError = ''; this.batchLoading = true; this.batchDenied = false
      if (!this.canRead) {
        this.denyCurrentBatch('当前身份缺少注册批次查看权限'); this.error = this.batchError; this.loading = false; this.batchLoading = false; return
      }
      await Promise.all([this.loadBatch(version, context, batchId), this.loadRecords(version, context, batchId)])
      if (this.loadCurrent(version, context)) this.academicFlow?.restorePosition()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
