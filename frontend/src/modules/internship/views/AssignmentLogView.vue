<template>
  <ModulePageShell title="分配记录" subtitle="查询岗位分配、退岗与指导教师调整，追溯每次变更。">
    <section class="al-card">
      <div class="al-toolbar"><AppSearchBox v-model="keyword" placeholder="搜索学生、学号或操作人" aria-label="搜索分配记录" @search="reload" /><span>权限范围内各批次记录</span><strong v-if="!loading && !error">{{ total }} 条</strong></div>
      <p v-if="openError" class="al-error" role="alert">{{ openError }}</p>
      <ErrorState v-if="error" :description="error" @retry="load" /><LoadingState v-else-if="loading" />
      <DataTable v-else-if="rows.length" :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }"><div class="al-student"><strong>{{ row.studentName }}</strong><span>{{ row.studentNo }}</span></div></template>
        <template #cell-action="{ row }"><AppStatusTag :type="row.action === 'UNASSIGN_POSITION' ? 'warning' : 'info'">{{ actionLabel(row.action) }}</AppStatusTag></template>
        <template #cell-detail="{ row }"><span class="al-detail">{{ detailText(row) }}</span></template>
        <template #cell-occurredAt="{ row }"><span class="al-time">{{ formatDateTime(row.occurredAt) }}</span></template>
        <template #cell-actions="{ row }"><AppPermissionButton code="internship.student.view" :allowed="canReadStudent" variant="ghost" size="sm" :loading="opening === String(row.recordId)" :disabled="!!opening" @click="openStudent(row)">查看档案</AppPermissionButton></template>
      </DataTable>
      <p v-else class="al-empty">当前条件下暂无分配记录，可调整关键词后查询。</p>
    </section>
  </ModulePageShell>
</template>
<script>
import { ModulePageShell, DataTable, ErrorState, LoadingState } from '@/components/business'
import { AppSearchBox, AppStatusTag, AppPermissionButton } from '@/components/common'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { canCode } from '@/modules/internship/composables/permission'
import { formatDateTime } from '@/utils/dateUtils'
const ACTIONS = { ASSIGN_ADVISOR: '分配指导教师', ASSIGN_POSITION: '分配岗位', UNASSIGN_POSITION: '退岗' }
export default {
  name: 'AssignmentLogView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, ErrorState, LoadingState, AppSearchBox, AppStatusTag, AppPermissionButton },
  data() { return { rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '', keyword: '', appliedKeyword: '', opening: '', openError: '', ticket: 0, openTicket: 0, columns: [
    { key: 'student', title: '学生', width: '160px' }, { key: 'action', title: '变更类型', width: '145px' }, { key: 'detail', title: '变更内容' },
    { key: 'operator', title: '操作人', width: '105px' }, { key: 'occurredAt', title: '操作时间', width: '165px' }, { key: 'actions', title: '档案', width: '110px' }
  ] } },
  computed: { pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } }, canReadStudent() { return canCode(this.ctx, 'internship.student.view') } },
  watch: { '$route.fullPath': { immediate: true, handler() { this.restoreLocation() } } },
  beforeUnmount() { this.ticket++; this.openTicket++ },
  methods: {
    restoreLocation() {
    this.keyword = this.appliedKeyword = String(this.$route.query.keyword || '')
    const page = Number(this.$route.query.page); this.page = Number.isSafeInteger(page) && page > 0 ? page : 1
    this.openTicket++; this.opening = ''; this.openError = ''; this.load()
    },
    formatDateTime,
    actionLabel(value) { return ACTIONS[value] || '其他变更' },
    detailText(row) { const d = row.detail || {}; return d.title || d.reason || (d.toUserId ? '已调整指导教师' : '未填写补充说明') },
    reload() { this.appliedKeyword = this.keyword.trim(); this.page = 1; this.updateLocation() }, onPageChange(page) { this.page = page; this.updateLocation() },
    updateLocation() { const to = { path: this.$route.path, query: { ...this.$route.query, keyword: this.appliedKeyword || undefined, page: this.page > 1 ? this.page : undefined } }; if (this.$router.resolve(to).fullPath === this.$route.fullPath) this.load(); else this.$router.replace(to) },
    async openStudent(row) {
      if (this.opening || !row.recordId || !this.canReadStudent) return
      this.opening = String(row.recordId); this.openError = ''
      const ticket = this.ticket, openTicket = ++this.openTicket, returnTo = this.$route.fullPath
      const current = () => ticket === this.ticket && openTicket === this.openTicket && returnTo === this.$route.fullPath
      try {
        const result = await internStudentApi.getStudentDetail(String(row.recordId))
        if (!current() || !this.canReadStudent) return
        if (result.code !== 0 || !result.data?.batchId) { this.openError = result.message || '档案暂时无法打开，请重试。'; return }
        await this.$router.push({ path: `/admin/internship/students/${row.recordId}`, query: { batchId: String(result.data.batchId), returnTo } })
      } catch (error) { if (current()) this.openError = error.message || '档案读取失败，请重试。' }
      finally { if (openTicket === this.openTicket) this.opening = '' }
    },
    async load() {
      const ticket = ++this.ticket
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      let res
      try { res = await internStudentApi.getAssignmentLogs({ page: this.page, pageSize: this.pageSize, keyword: this.appliedKeyword }) }
      catch (error) { res = { code: -1, message: error.message || '分配记录暂时无法读取，请重试。' } }
      if (ticket !== this.ticket) return
      this.loading = false
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
      else this.error = res.message || '分配记录暂时无法读取，请重试。'
    }
  }
}
</script>
<style scoped>
.al-card { border: 1px solid var(--card-b, #e2e8f0); border-radius: 12px; background: var(--card, #fff); overflow: hidden; }
.al-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; padding: 20px; }.al-toolbar > span { font-size: 13px; color: var(--text-tertiary); }.al-toolbar > strong { margin-left: auto; font-size: 13px; font-weight: 500; color: var(--text-secondary); }
.al-student { display: grid; gap: 5px; line-height: 1.5; }.al-student strong { font-size: 14px; font-weight: 500; }.al-student span { font-size: 12px; color: var(--text-tertiary); }.al-detail { font-size: 13px; line-height: 1.7; color: var(--text-secondary); overflow-wrap: anywhere; }.al-time { white-space: nowrap; font-size: 13px; }
.al-empty { padding: 48px 24px; margin: 0; text-align: center; color: var(--text-tertiary); font-size: 13px; }.al-error { margin: 0; padding: 0 20px 16px; font-size: 13px; color: var(--danger-600, #b91c1c); }
</style>
