<template>
  <ModulePageShell
    title="实习变更审核"
    subtitle="换岗 · 换实习单位 · 自主实习变更"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <DualPaneWorkspace aside-title="变更申请" :aside-count="pagination.total">
        <!-- 左栏：变更申请队列（紧凑列表，连续审核） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">暂无变更申请，学生可在小程序发起换岗/换单位申请</div>
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
          <div class="lv-pager">
            <button type="button" class="mp-link" :disabled="pagination.page <= 1 || loading" @click="onPageChange(pagination.page - 1)">上一页</button>
            <span class="mp-note">第 {{ pagination.page }} / 共 {{ pageCount }} 页</span>
            <button type="button" class="mp-link" :disabled="pagination.page >= pageCount || loading" @click="onPageChange(pagination.page + 1)">下一页</button>
          </div>
        </template>

        <!-- 右栏：当前变更申请详情与审核操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="当前列表变更申请已全部处理"
              description="可翻页或切换页签，继续审核其他变更申请" />
            <EmptyState v-else title="从左侧选择一条变更申请开始审核"
              description="点击列表项查看变更详情与审计留痕，通过或驳回后自动跳到下一条待审核" />
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
              </div>

              <div class="sec-t">变更申请</div>
              <AppDescriptionList :items="detailItems" :columns="2" />

              <div class="sec-t">审计留痕</div>
              <AppAuditTrail :records="auditRecords" compact empty-text="暂无留痕" />
            </div>

            <div v-if="detail.data.status === 'PENDING'" class="lv-foot">
              <AppPermissionButton :allowed="canReview" code="internship.change.review" variant="danger" @click="openReview(detail.data, 'REJECT')">驳回</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" code="internship.change.review" variant="secondary" @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
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
/**
 * 实习变更审核 — 双栏连续审核工作区（原「列表 + 详情弹窗」收口为 DualPaneWorkspace）。
 * 左栏队列点选写入 query.id（可深链恢复），右栏展示变更 6 字段 + 审计留痕，
 * 通过/驳回沿用原 AppConfirmDialog 流程（驳回必填意见），审核后自动跳下一条待审核。
 * 页签（panel 深链 pending/approved/rejected/all）沿用原映射。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppDescriptionList, AppAuditTrail, AppPermissionButton } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

export default {
  name: 'ChangeRequestListView',
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, AppStatusTag, AppConfirmDialog,
    AppDescriptionList, AppAuditTrail, AppPermissionButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [],
      filters: { status: 'PENDING' },
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
      pending: null
    }
  },
  computed: {
    canReview() { return canCode(this.ctx, 'internship.change.review') },
    pageCount() { return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize)) },
    detailItems() {
      const d = this.detail.data || {}
      return [
        { label: '学生', value: d.studentName },
        { label: '变更类型', value: d.changeTypeLabel },
        { label: '当前', value: `${d.currentEnterprise} / ${d.currentPosition}` },
        { label: '目标', value: `${d.targetEnterpriseName || '—'} / ${d.targetPositionName || '—'}` },
        { label: '原因', value: d.reason },
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
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        const map = { pending: 'PENDING', approved: 'APPROVED', rejected: 'REJECTED', all: '' }
        this.filters.status = map[(panel || 'pending').toString()] ?? 'PENDING'
        this.pagination.page = 1
        this.doneHint = false
        this.load()
      }
    },
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
  methods: {
    switchTab(v) {
      const map = { PENDING: 'pending', APPROVED: 'approved', REJECTED: 'rejected', '': 'all' }
      const panel = map[v] || 'all'
      if (this.$route.query.panel !== panel) {
        this.$router.replace({ path: this.$route.path, query: { panel } })
      } else {
        this.filters.status = v
        this.pagination.page = 1
        this.load()
      }
    },
    onPageChange(page) {
      if (page < 1 || page > this.pageCount || page === this.pagination.page) return
      this.pagination.page = page; this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getChangeRequests({
        status: this.filters.status, page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
        this.rows = []
        this.pagination.total = 0
      }
      this.loading = false
      // 处理完当前页最后一条后翻页越界（如页签=待审核时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
      if (!this.error && !this.rows.length && this.pagination.total > 0 && this.pagination.page > pc) {
        this.pagination.page = pc
        return this.load()
      }
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
      const res = await internshipApi.getChangeRequestDetail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    openReview(row, action) {
      if (!this.canReview) return toast.error('无实习变更审核权限')
      const ap = action === 'APPROVE'
      this.pending = { id: row.id, action }
      this.cd = {
        visible: true,
        title: ap ? '通过变更申请' : '驳回变更申请',
        content: `${ap ? '通过' : '驳回'}「${row.studentName}」的${row.changeTypeLabel}申请，将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false
      }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await internshipApi.reviewChangeRequest(this.pending.id, {
        action: this.pending.action, comment: reason || ''
      })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message)
      this.cd.visible = false
      toast.success('审核完成')
      await this.advanceAfterReview(this.pending.id)
    },
    /** 审核成功后：刷新当前页并自动选中下一条待审核；无下一条则清空选中并提示已处理完 */
    async advanceAfterReview(oldId) {
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      await this.load()
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
</style>
