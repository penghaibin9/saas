<template>
  <ModulePageShell
    title="工作量申报审核"
    subtitle="教师在移动端申报教学/监考/阅卷/出卷工作量，教务处在此审核；通过后计入教师工作量统计（仅供教务参考，非薪酬核算）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">状态
          <select v-model="status" class="aa-input aa-input--sm" @change="load">
            <option value="">全部</option>
            <option value="SUBMITTED">待审核</option>
            <option value="APPROVED">已通过</option>
            <option value="REJECTED">已驳回</option>
          </select>
        </label>
        <label class="aa-filter__item">学期<input v-model.trim="termCode" class="aa-input aa-input--sm" placeholder="学期码，选填" @keyup.enter="load" /></label>
        <button class="mp-btn" @click="load">查询</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard title="工作量申报台账">
          <EmptyState v-if="!rows.length" title="暂无申报" description="教师在移动端提交工作量申报后，这里出现待审核记录" />
          <div v-else class="aa-table-wrap">
            <table class="aa-table">
              <thead>
                <tr><th>教师</th><th>学期</th><th>类别</th><th>申报课时</th><th>工作说明</th><th>状态</th><th>操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in rows" :key="r.declarationId">
                  <td>{{ r.teacherName || r.teacherKey }}</td>
                  <td>{{ r.termCode || '—' }}</td>
                  <td>{{ r.categoryLabel }}</td>
                  <td>{{ r.hours }}</td>
                  <td class="aa-td-desc" :title="r.description">{{ r.description || '—' }}</td>
                  <td><AppStatusTag :type="statusColor(r.status)" dot>{{ statusLabel(r.status) }}</AppStatusTag></td>
                  <td>
                    <template v-if="r.status === 'SUBMITTED'">
                      <button class="mp-link" @click="approve(r)">通过</button>
                      <button class="mp-link mp-link--danger" @click="openReject(r)">驳回</button>
                    </template>
                    <span v-else class="aa-note-sm">{{ r.reviewNote || '—' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppSectionCard>

        <AppSectionCard v-if="rejecting" :title="`驳回：${rejecting.teacherName || rejecting.teacherKey} · ${rejecting.categoryLabel} ${rejecting.hours}课时`">
          <textarea v-model.trim="rejectNote" class="aa-textarea" rows="2" placeholder="驳回原因（必填，≥5字）"></textarea>
          <div class="aa-actions">
            <button class="mp-btn mp-btn--primary" :disabled="submitting" @click="doReject">{{ submitting ? '提交中…' : '确认驳回' }}</button>
            <button class="mp-btn" @click="rejecting = null">取消</button>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 工作量申报审核（/admin/academic-affairs/workload-review）：GET /workload-declarations + review。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS = { SUBMITTED: '待审核', APPROVED: '已通过', REJECTED: '已驳回' }

export default {
  name: 'AaWorkloadReviewView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', status: '', termCode: '', rows: [], rejecting: null, rejectNote: '', submitting: false }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS[s] || s },
    statusColor(s) {
      if (s === 'APPROVED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'SUBMITTED') return 'primary'
      return 'default'
    },
    async load() {
      this.loading = true
      this.error = ''
      this.rejecting = null
      const res = await academicAffairsApi.getWorkloadDeclarations({ status: this.status || undefined, termCode: this.termCode || undefined, page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    async approve(r) {
      const res = await academicAffairsApi.reviewWorkloadDeclaration(r.declarationId, { action: 'APPROVE' })
      if (res.code === 0) { toast.success('已通过'); this.load() } else toast.error(res.message || '操作失败')
    },
    openReject(r) { this.rejecting = r; this.rejectNote = '' },
    async doReject() {
      if (this.submitting) return
      if (!this.rejectNote || this.rejectNote.length < 5) { toast.error('驳回原因必填且不少于 5 字'); return }
      this.submitting = true
      const res = await academicAffairsApi.reviewWorkloadDeclaration(this.rejecting.declarationId, { action: 'REJECT', note: this.rejectNote })
      this.submitting = false
      if (res.code === 0) { toast.success('已驳回'); this.rejecting = null; this.load() } else toast.error(res.message || '操作失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 160px; }
.aa-table-wrap { overflow-x: auto; }
.aa-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-table th, .aa-table td { padding: 8px 10px; text-align: center; border-bottom: 1px solid var(--border-200, #e5e6eb); white-space: nowrap; }
.aa-table th { color: var(--text-700, #4e5969); font-weight: 600; background: var(--fill-100, #f7f8fa); }
.aa-td-desc { max-width: 260px; overflow: hidden; text-overflow: ellipsis; text-align: left; }
.aa-note-sm { color: var(--text-500, #646a73); font-size: 12px; }
.mp-link--danger { color: var(--danger-600, #f53f3f); margin-left: 10px; }
.aa-textarea { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font-size: 13px; resize: vertical; }
.aa-actions { margin-top: 12px; display: flex; gap: 12px; }
</style>
