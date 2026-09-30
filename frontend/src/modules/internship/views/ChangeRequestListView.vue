<template>
  <ModulePageShell
    title="调岗退岗"
    subtitle="核对学生变更去向与审批影响，再完成审核。"
    :role-name="ctx.currentRole?.roleName"
    :data-scope-name="ctx.dataScope?.scopeName"
    :watermark="false"
  >
    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

      <div class="change-toolbar">
      <div class="mp-tabs" aria-label="申请状态">
        <button v-for="t in tabs" :key="t.value" type="button" class="mp-tab" :aria-pressed="filters.status === t.value" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>
      <AppSearchBox v-model="filters.keyword" placeholder="搜索学生姓名或学号" @search="search" />
      </div>

      <DualPaneWorkspace aside-title="变更申请" :aside-count="pagination.total">
        <!-- 左栏：变更申请队列（紧凑列表，连续审核） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无申请<button v-if="filters.keyword" type="button" class="mp-link" @click="clearSearch">清空搜索</button></div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :status="r.status">{{ r.statusLabel }}</AppStatusTag>
                </div>
                <div class="lv-item__sub">{{ r.studentNo }} · {{ r.changeTypeLabel }}</div>
                <div class="lv-item__sub">{{ r.currentEnterprise }} / {{ r.currentPosition }}<template v-if="r.targetEnterpriseName"> → {{ r.targetEnterpriseName }}</template></div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination :page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total"
                        :show-size-changer="false" :disabled="loading" @change="onPageChange" />
        </template>

        <!-- 右栏：当前变更申请详情与审核操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="已处理到当前列表末尾"
              description="可翻页或切换状态，继续核对其他申请"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
            <EmptyState v-else title="选择一条变更申请"
              description="在此核对变更去向、审批影响与处理记录"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
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
                <AppStatusTag :status="detail.data.status">{{ detail.data.statusLabel }}</AppStatusTag>
                <AppButton v-if="detail.data.internId" variant="ghost" class="lv-head__link" @click="goStudent">学生档案</AppButton>
              </div>

              <div class="sec-t">变更申请</div>
              <AppDescriptionList :items="detailItems" :columns="2" />

              <h2 class="sec-t">当前去向与申请目标</h2>
              <div class="change-impact">
                <div class="change-impact__route">
                  <div><small>当前实习去向</small><strong>{{ detail.data.currentEnterprise || '未落实单位' }}</strong><span>{{ detail.data.currentPosition || '未落实岗位' }}</span></div>
                  <b>→</b>
                  <div class="is-target"><small>本次申请目标</small><strong>{{ targetEnterpriseLabel(detail.data) }}</strong><span>{{ detail.data.targetPositionName || (detail.data.changeType === 'WITHDRAW_POST' ? '结束当前岗位' : '未填写岗位') }}</span></div>
                </div>
                <div v-if="detail.data.targetPosition" class="change-impact__truth">
                  <span>目标岗位：{{ detail.data.targetPosition.exists ? '存在' : '已失效' }}</span>
                  <span>状态：{{ positionStatusLabel(detail.data.targetPosition.status) }}</span>
                  <span>剩余：{{ detail.data.targetPosition.remaining }} / {{ detail.data.targetPosition.headcount || 0 }}</span>
                  <span>同批次：{{ detail.data.targetPosition.sameBatch ? '是' : '否' }}</span>
                  <span>当前可分配：{{ detail.data.targetPosition.capacityAvailable ? '是' : '否' }}</span>
                </div>
                <AppInlineAlert v-if="approvalBlockers.length && detail.data.status === 'PENDING'" type="warning" title="通过前需解决" :description="approvalBlockers.join('；')" />
                <h2 v-if="detail.data.status === 'PENDING'" class="sec-t">通过后的影响</h2>
                <ul v-if="detail.data.status === 'PENDING'" class="change-impact__list">
                  <li v-for="item in detail.data.impactItems || []" :key="item.label"><b>{{ item.label }}</b><span>{{ item.detail }}</span></li>
                </ul>
                <p v-if="detail.data.status === 'PENDING'" class="change-impact__next">通过后：{{ detail.data.nextRecordStatusLabel }}。{{ detail.data.nextStep }}</p>
              </div>

              <h2 class="sec-t">处理记录</h2>
              <AppAuditTrail :records="auditRecords" compact empty-text="暂无留痕" />
            </div>

            <div v-if="detail.data.status === 'PENDING'" class="lv-foot">
              <span class="lv-foot__hint">{{ canReview ? '审核后继续当前列表下一条' : '当前账号无变更审核权限' }}</span>
              <AppPermissionButton :allowed="canReview" code="internship.change.review" variant="secondary" :disabled="cd.submitting" @click="openReview(detail.data, 'REJECT')">驳回申请</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" code="internship.change.review" variant="primary" :disabled="cd.submitting || approvalBlockers.length > 0" @click="openReview(detail.data, 'APPROVE')">通过申请</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-chips="cd.requireReason ? REJECT_CHANGE : []"
      :reason-label="cd.requireReason ? '驳回原因（至少 5 字）' : '审核意见'" :submitting="cd.submitting" :confirm-disabled="conflict.active" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="申请已更新，本次审核已暂停" description="意见已保留，请取消后核对最新详情，再重新选择可用操作。">
        <p v-if="conflict.stale">最新详情暂时无法读取，请关闭后重试加载。</p>
        <AppDescriptionList v-else :items="conflict.latest" :columns="1" />
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 实习变更审核 — 双栏连续审核工作区（原「列表 + 详情弹窗」收口为 DualPaneWorkspace）。
 * 左栏队列点选写入 query.id（可深链恢复），右栏展示变更 6 字段 + 审计留痕，
 * 通过/驳回沿用原 AppConfirmDialog 流程（驳回必填意见），审核后自动跳下一条待审核。
 * 页签（panel 深链 pending/approved/rejected/all）沿用原映射。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppDescriptionList, AppAuditTrail, AppPermissionButton, AppPagination, AppSearchBox, AppInlineAlert } from '@/components/common'
import { AppButton } from '@/components/ui'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { toast } from '@/utils/toast'
import { REJECT_CHANGE } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

export default {
  name: 'ChangeRequestListView',
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, AppStatusTag, AppConfirmDialog,
    AppDescriptionList, AppAuditTrail, AppPermissionButton, AppPagination, ActionReceipt, AppSearchBox, AppInlineAlert, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      REJECT_CHANGE,
      loading: true, error: '', rows: [], listSequence: 0,
      filters: { status: 'PENDING', keyword: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      tabs: [
        { value: 'PENDING', label: '待审核' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已驳回' },
        { value: '', label: '全部' }
      ],
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null, conflict: emptyConflict(), lastReceipt: null
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    canReview() { return canCode(this.ctx, 'internship.change.review') },
    approvalBlockers() {
      const d = this.detail.data
      if (!d || d.status !== 'PENDING') return []
      const blockers = [...(d.targetPosition?.blockers || [])]
      if (d.recordVersion != null && d.recordVersionSnapshot != null && String(d.recordVersion) !== String(d.recordVersionSnapshot)) blockers.push('学生实习信息在申请后已变化，请驳回并由学生按最新情况重新申请')
      if (d.targetPosition?.sameBatch === false) blockers.push('目标岗位不属于当前批次')
      if (d.targetPosition?.capacityAvailable === false) blockers.push('目标岗位当前不可分配')
      return [...new Set(blockers)]
    },
    detailItems() {
      const d = this.detail.data || {}
      return [
        { label: '申请编号', value: d.id },
        { label: '变更类型', value: d.changeTypeLabel },
        { label: '申请时间', value: d.createdAt },
        { label: '申请原因', value: d.reason },
        { label: '审核意见', value: d.reviewComment || '—' }
      ]
    },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, at: t.occurredAt,
        reason: t.detail && (t.detail.comment || '')
      }))
    }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.pagination.page = 1
      this.doneHint = false
      this.lastReceipt = null
      this.clearSelection()
      this.load()
    },
    '$route.query': {
      deep: true,
      immediate: true,
      handler(query, previous) {
        if (!previous || ['panel', 'keyword', 'page', 'batchId'].some(key => String(query[key] || '') !== String(previous[key] || ''))) this.applyQuery()
        const sid = String(query.id || '')
        if (sid === this.selectedId) return
        this.resetDetail()
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) }
      }
    }
  },
  beforeUnmount() { this.listSequence++; this.resetDetail() },
  methods: {
    positionStatusLabel(value) { return ({ PUBLISHED: '招聘中', DRAFT: '草稿', OPEN: '招聘中', ACTIVE: '招聘中', PAUSED: '已暂停', CLOSED: '已关闭', FILLED: '已招满', CANCELLED: '已取消', MISSING: '已失效' })[value] || (value ? '状态待确认' : '—') },
    targetEnterpriseLabel(row) { return row.targetEnterpriseName || ({ WITHDRAW_POST: '退岗', SELF_ARRANGED: '自主实习' })[row.changeType] || '未填写目标单位' },
    applyQuery() {
      const q = this.$route.query || {}
      this.filters.status = ({ pending: 'PENDING', approved: 'APPROVED', rejected: 'REJECTED', all: '' })[q.panel || 'pending'] ?? 'PENDING'
      this.filters.keyword = String(q.keyword || '')
      this.pagination.page = Math.max(1, Number.parseInt(q.page, 10) || 1)
      this.doneHint = false
      this.load()
    },
    syncQuery() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, keyword: this.filters.keyword, page: String(this.pagination.page) })
      if (Object.keys(query).every(key => String(query[key] ?? '') === String(this.$route.query[key] ?? ''))) this.load()
      else this.$router.replace({ query })
    },
    search() { this.pagination.page = 1; this.doneHint = false; this.syncQuery() },
    clearSearch() { this.filters.keyword = ''; this.search() },
    onPageChange({ page }) { this.pagination.page = page; this.syncQuery() },
    switchTab(v) {
      const map = { PENDING: 'pending', APPROVED: 'approved', REJECTED: 'rejected', '': 'all' }
      const panel = map[v] || 'all'
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery({ panel, keyword: this.filters.keyword, page: '1' }) })
      } else {
        this.filters.status = v
        this.pagination.page = 1
        this.syncQuery()
      }
    },
    async load() {
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      this.rows = []; this.pagination.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = '请先选择实习批次'
        this.rows = []
        this.pagination.total = 0
        return
      }
      this.loading = true
      this.error = ''
      const res = await internshipApi.getChangeRequests({
        status: this.filters.status,
        keyword: this.filters.keyword,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize,
        batchId: this.batchStore.selectedBatchId
      })
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message || '变更申请加载失败，请重试'
        this.rows = []
        this.pagination.total = 0
      }
      this.loading = false
      // 处理完当前页最后一条后翻页越界（如页签=待审核时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
      if (!this.error && !this.rows.length && this.pagination.total > 0 && this.pagination.page > pc) {
        this.pagination.page = pc
        this.syncQuery()
        return false
      }
      return !this.error
    },
    select(id) {
      if (id == null || id === '') return
      const sid = String(id)
      this.doneHint = false
      if (this.selectedId === sid) return
      this.resetDetail(); this.selectedId = sid; this.loadDetail(sid)
      this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id: sid, page: String(this.pagination.page) }) })
    },
    resetDetail() {
      this.detail = { loading: false, error: '', data: null }
      this.pending = null; this.cd = { ...this.cd, visible: false, submitting: false }; this.conflict = emptyConflict()
    },
    clearSelection() {
      this.resetDetail(); this.selectedId = ''
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, page: String(this.pagination.page) })
      delete query.id
      this.$router.replace({ query })
    },
    async loadDetail(id) {
      if (!id || !this.batchStore.selectedBatchId) return
      const batchId = this.batchStore.selectedBatchId
      this.detail = { loading: true, error: '', data: null }
      const workspace = this.detail
      const res = await internshipApi.getChangeRequestDetail(id)
      if (this.detail !== workspace || batchId !== this.batchStore.selectedBatchId || String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    goStudent() {
      if (this.detail.data?.internId) this.$router.push({ path: `/admin/internship/students/${this.detail.data.internId}`, query: this.batchStore.withBatchQuery({}) })
    },
    openReview(row, action) {
      if (!this.canReview) return toast.error('无实习变更审核权限')
      if (!row || this.detail.loading || this.detail.error || this.cd.submitting || row.status !== 'PENDING' || String(row.id) !== this.selectedId || !['APPROVE', 'REJECT'].includes(action)) return
      if (action === 'APPROVE' && this.approvalBlockers.length) return
      const ap = action === 'APPROVE'
      this.pending = {
        id: row.id, action, expectedVersion: row.version,
        recordExpectedVersion: row.recordVersionSnapshot
      }
      this.conflict = emptyConflict()
      this.cd = {
        visible: true,
        title: ap ? '通过变更申请' : '驳回变更申请',
        content: ap ? `通过「${row.studentName}」的${row.changeTypeLabel}申请。原岗位关系与协议将按本次申请调整，学生需重新完成上岗核验。` : `驳回「${row.studentName}」的${row.changeTypeLabel}申请，请说明需要修改的内容。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false
      }
    },
    async onConfirm({ reason }) {
      const pending = this.pending
      if (!pending || this.cd.submitting || this.conflict.active || !this.canReview || this.detail.loading || this.detail.error || this.detail.data?.status !== 'PENDING' || String(pending.id) !== this.selectedId) return
      if (pending.action === 'APPROVE' && this.approvalBlockers.length) return
      if (pending.action === 'REJECT' && String(reason || '').trim().length < 5) return toast.error('请填写至少 5 字的驳回原因')
      const dialog = this.cd
      const batchId = this.batchStore.selectedBatchId
      const reviewed = this.detail.data
      dialog.submitting = true
      const res = await internshipApi.reviewChangeRequest(pending.id, {
        action: pending.action,
        comment: reason || '',
        expectedVersion: pending.expectedVersion,
        recordExpectedVersion: pending.recordExpectedVersion
      })
      if (this.cd === dialog) dialog.submitting = false
      if (this.pending !== pending || this.cd !== dialog || batchId !== this.batchStore.selectedBatchId || String(pending.id) !== this.selectedId) return
      if (res.code !== 0) {
        if (isConflict(res)) {
          this.conflict = { ...emptyConflict(), active: true, kept: reason || '' }
          const conflict = await captureConflict({
            res,
            kept: reason || '',
            refresh: async () => {
              await this.loadDetail(pending.id)
              if (this.detail.error || !this.detail.data) throw new Error(this.detail.error || '刷新失败')
            },
            latest: () => [
              { label: '申请状态', value: this.detail.data?.statusLabel },
              { label: '最新审核意见', value: this.detail.data?.reviewComment || '—' },
              { label: '当前关系', value: `${this.detail.data?.currentEnterprise || '—'} / ${this.detail.data?.currentPosition || '—'}` }
            ]
          })
          if (this.pending === pending && this.cd === dialog) this.conflict = conflict
          return
        }
        return toast.error(res.message || '审核未完成，请重试')
      }
      const data = res.data || {}
      this.detail.data = { ...reviewed, ...data }
      this.lastReceipt = {
        actionLabel: pending.action === 'APPROVE' ? '变更审批通过' : '变更申请驳回',
        objectLabel: `${reviewed.studentName || '学生'} · ${reviewed.changeTypeLabel || '实习变更'}`,
        id: data.id, status: data.status, statusLabel: data.statusLabel,
        version: data.version,
        auditText: pending.action === 'APPROVE'
          ? `主记录已回退为${data.recordStatusLabel || data.recordStatus || '待重新上岗'}`
          : '驳回意见与审批结果已写入审计',
        nextStep: data.nextStep || (pending.action === 'REJECT' ? '等待学生按意见重新申请' : '重新办理合规、协议与上岗')
      }
      this.cd.visible = false
      this.conflict = emptyConflict()
      toast.success('审核完成')
      await this.advanceAfterReview(pending.id)
    },
    /** 审核成功后：刷新当前页并自动选中下一条待审核；无下一条则清空选中并提示已处理完 */
    async advanceAfterReview(oldId) {
      const batchId = this.batchStore.selectedBatchId
      const query = this.$route.fullPath
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      const loaded = await this.load()
      if (!loaded || this.error || batchId !== this.batchStore.selectedBatchId || query !== this.$route.fullPath || String(this.selectedId) !== String(oldId)) return
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (r.status !== 'PENDING' || String(r.id) === String(oldId)) return
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

.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.state .mp-link { margin-inline-start: 8px; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }
.change-impact { padding: 14px; border: 1px solid var(--border-light); border-radius: 12px; background: var(--bg-subtle, #f8fafc); }.change-impact__route { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: stretch; gap: 12px; }.change-impact__route > div { display: grid; gap: 4px; padding: 12px; border-radius: 9px; background: var(--bg-card, #fff); }.change-impact__route > b { align-self: center; color: var(--primary-600); font-size: 22px; }.change-impact__route small { color: var(--text-tertiary); }.change-impact__route strong,.change-impact__route span { overflow-wrap: anywhere; }.change-impact__route .is-target { border: 1px solid var(--primary-200, #bfdbfe); }.change-impact__truth { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 10px; padding: 9px 11px; border-radius: 8px; background: var(--bg-card, #fff); color: var(--text-secondary); font-size: var(--font-size-xs); }.change-impact__list { display: grid; gap: 7px; margin: 12px 0 0; padding: 0; list-style: none; }.change-impact__list li { display: grid; grid-template-columns: 6em 1fr; gap: 10px; font-size: var(--font-size-sm); line-height: 1.55; }.change-impact__list span { color: var(--text-secondary); }.change-impact__next { margin: 12px 0 0; padding: 9px 11px; border-radius: 8px; background: var(--warning-50, #fffbeb); color: var(--warning-700, #b45309); font-size: var(--font-size-sm); }

/* 左栏紧凑列表 */
.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 右栏详情与固定操作区 */
.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }
@media (max-width: 980px) { .change-impact__route { grid-template-columns: 1fr; }.change-impact__route > b { justify-self: center; transform: rotate(90deg); } }
.change-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.change-toolbar .mp-tabs { margin: 0; }
.change-toolbar :deep(.app-search-box) { width: min(100%, 300px); }
.lv-head__link { margin-left: auto; }
.lv-item:focus-visible { outline: 2px solid var(--primary-600, #2563eb); outline-offset: 2px; }
.lv-item__sub { overflow-wrap: anywhere; }
.lv-foot { align-items: center; flex-wrap: wrap; }
.lv-foot__hint { margin-right: auto; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.change-impact :deep(.app-inline-alert) { margin-top: 12px; }
@media (max-width: 600px) { .lv-foot__hint { flex-basis: 100%; }.change-impact__list li { grid-template-columns: 1fr; gap: 2px; } }
</style>
