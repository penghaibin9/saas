<template>
  <ModulePageShell title="评价与成绩" subtitle="学生鉴定 · 学生自评 · 指导教师意见 · 学校审核"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/enterprise-evals')">返回评价管理</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
        <span class="bar__hint">学生自评经移动端提交</span>
      </div>

      <DualPaneWorkspace aside-title="学生鉴定" :aside-count="total">
        <!-- 左栏：学生鉴定队列（紧凑列表，连续审核） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无学生鉴定</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :type="reviewTone(r.reviewStatus)">{{ r.reviewStatusLabel }}</AppStatusTag>
                </div>
                <div class="lv-item__sub">{{ r.studentNo }}<template v-if="r.advisorName"> · {{ r.advisorName }}</template></div>
                <div class="lv-item__sub">{{ r.createdAt }} · 自评 {{ r.submitStatusLabel }}</div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <div class="lv-pager">
            <button type="button" class="mp-link" :disabled="page <= 1 || loading" @click="onPageChange(page - 1)">上一页</button>
            <span class="mp-note">第 {{ page }} / 共 {{ pageCount }} 页</span>
            <button type="button" class="mp-link" :disabled="page >= pageCount || loading" @click="onPageChange(page + 1)">下一页</button>
          </div>
        </template>

        <!-- 右栏：当前学生鉴定详情、教师意见与审核操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="当前列表鉴定已全部处理"
              description="可翻页或切换筛选条件，继续审核其他学生鉴定" />
            <EmptyState v-else title="从左侧选择一名学生开始处理"
              description="点击列表项查看自评明细、填写指导教师意见，通过或退回后自动跳到下一条待审核" />
          </template>
          <div v-else-if="detail.loading" class="state lv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err lv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="lv-main__body">
              <div class="lv-head">
                <span class="lv-head__name">{{ detail.data.studentName }}</span>
                <span class="mp-note">{{ detail.data.studentNo }}</span>
                <AppStatusTag :type="detail.data.submitStatus === 'SUBMITTED' ? 'success' : 'default'">自评 {{ detail.data.submitStatusLabel }}</AppStatusTag>
                <AppStatusTag :type="reviewTone(detail.data.reviewStatus)">{{ detail.data.reviewStatusLabel }}</AppStatusTag>
              </div>

              <div class="sec-t">自评明细</div>
              <AppDescriptionList :items="detailItems" :columns="1" />

              <template v-if="canComment">
                <div class="sec-t">指导教师意见（待审核期间可填写）</div>
                <div class="cmt">
                  <AppFormItem label="指导教师意见" required>
                    <AppTextarea v-model="cmtForm.advisorOpinion" :rows="3" placeholder="对学生实习表现的鉴定意见" />
                  </AppFormItem>
                  <AppFormItem label="企业导师意见（可选，如实转录）">
                    <AppTextarea v-model="cmtForm.mentorOpinion" :rows="3" placeholder="企业导师对学生的意见" />
                  </AppFormItem>
                  <div class="cmt__actions">
                    <AppPermissionButton code="internship.studentEval.comment" variant="primary" size="sm"
                      :loading="cmtSubmitting" @click="submitComment">保存意见</AppPermissionButton>
                  </div>
                </div>
              </template>

              <div class="sec-t">审核留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            </div>

            <div v-if="canReview" class="lv-foot">
              <AppPermissionButton code="internship.studentEval.review" variant="ghost" :danger="true"
                @click="openReview(detail.data, 'RETURN')">退回</AppPermissionButton>
              <AppPermissionButton code="internship.studentEval.review" variant="secondary"
                @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审核意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextarea, AppFormItem } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { studentEvalApi } from '@/modules/internship/api/student-eval.api'
import { toast } from '@/utils/toast'

/* 右栏只渲染 /internship/student-evals/{id} 真实返回字段（见 internship_student_eval_service._row + _full + get_eval） */
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'selfSummary', label: '实习总结' }, { key: 'selfHarvest', label: '学习收获' },
  { key: 'selfProblem', label: '存在问题' },
  { key: 'enterpriseRating', label: '对企业评分（1-5）' }, { key: 'enterpriseFeedback', label: '对企业评价' },
  { key: 'positionRating', label: '对岗位评分（1-5）' }, { key: 'positionFeedback', label: '对岗位评价' },
  { key: 'advisorOpinion', label: '指导教师意见' },
  { key: 'mentorOpinion', label: '企业导师意见' }, { key: 'reviewStatusLabel', label: '学校审核' },
  { key: 'reviewComment', label: '审核意见' }
]
const STATUS_OPTIONS = [{ label: '待审核', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已退回', value: 'RETURNED' }]

export default {
  name: 'StudentEvalView',
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, ModuleSummaryStrip, AppButton,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
    AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextarea, AppFormItem },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: 'PENDING', statusOptions: STATUS_OPTIONS,
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cmtForm: { advisorOpinion: '', mentorOpinion: '' }, cmtSubmitting: false,
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pageCount() { return Math.max(1, Math.ceil(this.total / this.pageSize)) },
    summaryMetrics() {
      // 仅在列表真实加载成功后展示服务端 total；loading / error 一律不展示
      if (this.loading || this.error) return []
      const cur = this.statusOptions.find((o) => o.value === this.statusFilter)
      return [{ label: '学生鉴定 · ' + (cur ? cur.label : '全部'), value: this.total,
        tone: this.statusFilter === 'PENDING' && this.total ? 'warn' : undefined }]
    },
    detailItems() {
      const d = this.detail.data || {}
      return DETAIL.map((f) => ({
        label: f.label,
        value: d[f.key] != null && d[f.key] !== '' ? d[f.key] : '—'
      }))
    },
    canComment() {
      const d = this.detail.data || {}
      return d.submitStatus === 'SUBMITTED' && d.reviewStatus === 'PENDING'
    },
    canReview() {
      const d = this.detail.data || {}
      return d.submitStatus === 'SUBMITTED' && d.reviewStatus === 'PENDING'
    },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = (id || '').toString()
        if (sid === this.selectedId) return
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    }
  },
  created() { this.load() },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    exportFn() { return studentEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) {
      if (p < 1 || p > this.pageCount || p === this.page) return
      this.page = p; this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await studentEvalApi.getEvals(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 处理完当前页最后一条后翻页越界（如筛选=待审核时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      this.doneHint = false
      if (String(this.$route.query.id || '') === sid) {
        if (this.selectedId !== sid) { this.selectedId = sid; this.loadDetail(sid) }
        return
      }
      this.$router.replace({ query: { ...this.$route.query, id: sid } })
    },
    clearSelection() {
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query })
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = await studentEvalApi.getDetail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
      // 意见表单从接口真实返回值带出，便于在已有意见上续写
      this.cmtForm = { advisorOpinion: res.data.advisorOpinion || '', mentorOpinion: res.data.mentorOpinion || '' }
    },
    async submitComment() {
      if (!this.cmtForm.advisorOpinion.trim()) return toast.error('请填写指导教师意见')
      this.cmtSubmitting = true
      const res = await studentEvalApi.advisorComment(this.detail.data.id, this.cmtForm)
      this.cmtSubmitting = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      toast.success('已保存意见')
      await Promise.all([this.loadDetail(this.selectedId), this.load()])
    },
    openReview(r, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action }
      this.cd = { visible: true, title: ap ? '鉴定 · 通过' : '鉴定 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的实习鉴定，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await studentEvalApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审核完成，已写审计')
      await this.advanceAfterReview(this.pending.id)
    },
    /** 审核成功后：刷新当前页并自动选中下一条待审核（已提交自评）；无下一条则清空选中并提示已处理完 */
    async advanceAfterReview(oldId) {
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      await this.load()
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (r.submitStatus !== 'SUBMITTED' || r.reviewStatus !== 'PENDING' || String(r.id) === String(oldId)) return
        if (i >= oldIndex) { if (!after) after = r } else if (!before) before = r
      })
      const next = after || before
      if (next) { this.select(next.id); return }
      this.clearSelection()
      this.doneHint = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }

/* 左栏紧凑列表 */
.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.lv-pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }

/* 右栏详情与固定操作区 */
.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }

/* 右栏内联意见表单 */
.cmt { border: 1px solid var(--border-light); border-radius: var(--radius-md, 8px); padding: var(--space-3); }
.cmt__actions { display: flex; justify-content: flex-end; }

</style>
