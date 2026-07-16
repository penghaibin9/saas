<template>
  <ModulePageShell
    title="请假审批"
    :subtitle="'共 ' + pagination.total + ' 条 · 待审批 ' + pendingTotal + ' 条 · 连续审批工作区'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading && !rows.length" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的请假申请" description="学生可通过小程序发起请假申请，审批结果实时同步学生端" />
      <SplitWorkspace v-else :has-selection="!!selectedId">
        <!-- 左：待办队列 -->
        <template #left>
          <div class="lav-queue">
            <div class="lav-queue__bar">
              <span class="lav-queue__pos">第 {{ positionText }} 条</span>
              <span class="lav-queue__ops">
                <button class="mp-link" :class="{ 'is-disabled': !can('campus.leave.batchApprove') || !checked.length }" :title="reason('campus.leave.batchApprove')" @click="openBatch">批量通过{{ checked.length ? '（' + checked.length + '）' : '' }}</button>
                <button class="mp-link" :class="{ 'is-disabled': !can('campus.leave.export') }" :title="reason('campus.leave.export')" @click="openExport">导出</button>
              </span>
            </div>
            <div class="lav-queue__list" ref="list">
              <div
                v-for="row in rows"
                :key="row.id"
                class="lav-item"
                :class="{ 'is-active': row.id === selectedId }"
                :data-row-id="row.id"
                @click="select(row.id)"
              >
                <input class="lav-item__check" type="checkbox" :value="row.id" v-model="checked" @click.stop />
                <div class="lav-item__main">
                  <div class="lav-item__line1">
                    <span class="lav-item__name">{{ row.name }}</span>
                    <span class="lav-item__sub">{{ row.className }}</span>
                    <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
                  </div>
                  <div class="lav-item__line2">{{ typeLabel(row.type) }} · {{ row.duration }} · {{ row.startTime }}</div>
                  <div class="lav-item__line3">{{ row.code }} · 申请于 {{ row.applyTime }}</div>
                </div>
              </div>
            </div>
            <div class="lav-queue__pager">
              <button class="mp-link" :class="{ 'is-disabled': pagination.page <= 1 }" @click="gotoPage(pagination.page - 1)">上一页</button>
              <span class="mp-note">第 {{ pagination.page }} / {{ maxPage }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :class="{ 'is-disabled': pagination.page >= maxPage }" @click="gotoPage(pagination.page + 1)">下一页</button>
            </div>
          </div>
        </template>

        <!-- 右：完整详情 + 连续审批 -->
        <template #detail="{ narrow }">
          <div v-if="!detail" class="mp-card lav-placeholder">
            <div class="mp-card__body"><p class="mp-note">从左侧选择一条请假申请开始处理</p></div>
          </div>
          <div v-else class="lav-detail">
            <div class="lav-detail__head">
              <button v-if="narrow" class="mp-link" @click="backToList">← 返回列表</button>
              <div class="lav-detail__title">
                {{ detail.leave.code }}
                <StatusTag :status="detail.leave.status" :label="statusLabel(detail.leave.status)" dot />
              </div>
              <div class="lav-detail__nav">
                <span class="mp-note">第 {{ positionText }} 条</span>
                <AppButton variant="ghost" :disabled="!hasPrev" @click="step(-1)">上一条</AppButton>
                <AppButton variant="ghost" :disabled="!hasNext" @click="step(1)">下一条</AppButton>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">学生与请假信息</div></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.leave.name }}（{{ detail.leave.className }}）</span></div>
                <div class="mp-kv"><span class="mp-kv__k">类型 / 时长</span><span class="mp-kv__v">{{ typeLabel(detail.leave.type) }} · {{ detail.leave.duration }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">起止时间</span><span class="mp-kv__v">{{ detail.leave.startTime }} ~ {{ detail.leave.endTime }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">事由</span><span class="mp-kv__v">{{ detail.leave.reason }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">附件</span><span class="mp-kv__v">{{ detail.leave.attachments && detail.leave.attachments.length ? detail.leave.attachments.join('、') : '无' }}</span></div>
                <div v-if="detail.leave.returnReason" class="mp-kv"><span class="mp-kv__k">退回原因</span><span class="mp-kv__v">{{ detail.leave.returnReason }}</span></div>
              </div>
            </div>

            <div v-if="detail.leave.conflictHint" class="lav-warn">⚠ {{ detail.leave.conflictHint }}</div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">该生历史请假</div></div>
              <div class="mp-card__body">
                <ul v-if="detail.history && detail.history.length" class="lav-list">
                  <li v-for="h in detail.history" :key="h">{{ h }}</li>
                </ul>
                <p v-else class="mp-note">无历史请假</p>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">审批流程留痕</div></div>
              <div class="mp-card__body">
                <table class="mp-audit">
                  <thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead>
                  <tbody>
                    <tr v-for="a in detail.auditLogs" :key="a.id">
                      <td>{{ a.time }}</td>
                      <td class="is-who">{{ a.operator }}</td>
                      <td>{{ a.detail }}</td>
                    </tr>
                    <tr v-if="!detail.auditLogs.length"><td colspan="3" class="mp-note">暂无审批记录</td></tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="detail.leave.status === 'PENDING_REVIEW'" class="mp-card lav-actzone">
              <div class="mp-card__head"><div class="mp-card__title">审批意见</div></div>
              <div class="mp-card__body">
                <AppQuickPhrases scene-key="sa.leave.approve" @pick="onPickComment" />
                <textarea
                  ref="commentTa"
                  v-model="comment"
                  class="lav-comment"
                  rows="2"
                  placeholder="审批意见（通过时选填；退回时作为退回原因必填，不少于 5 个字，原文同步学生端）"
                ></textarea>
                <div class="lav-actzone__btns">
                  <AppButton variant="danger" :disabled="!can('campus.leave.return')" :title="reason('campus.leave.return')" @click="openReturn">退回修改</AppButton>
                  <span class="lav-actzone__sp" />
                  <AppButton variant="primary" :disabled="!can('campus.leave.approve') || submitting" :title="reason('campus.leave.approve')" @click="approve(false)">通过</AppButton>
                  <AppButton variant="primary" :disabled="!can('campus.leave.approve') || submitting" :title="reason('campus.leave.approve')" @click="approve(true)">通过并下一条</AppButton>
                </div>
              </div>
            </div>
            <p v-else class="mp-note">该申请已处理完毕；可用「上一条 / 下一条」继续处理队列中的其他申请。</p>
          </div>
        </template>
      </SplitWorkspace>

      <p class="mp-note">退回必须填写原因（同步学生端）；通过/退回/批量审批/导出均写入审计日志。请假记录自动进入学生360时间线。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="returnDialog.visible"
      type="danger"
      title="退回修改"
      :message="'退回「' + (detail ? detail.leave.code : '') + '」请假申请，退回原因将原文同步学生端。'"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      reason-placeholder="请说明退回原因（如材料不全、时间冲突），不少于 5 个字"
      phrase-scene-key="sa.leave.return"
      :submitting="returnDialog.submitting"
      @confirm="submitReturn"
    />

    <AppConfirmDialog
      v-model:visible="batchDialog.visible"
      type="primary"
      title="批量审批通过"
      :message="'确认批量通过选中的 ' + checked.length + ' 条待审批请假？非待审批状态将自动跳过，结果同步学生端并留痕。'"
      confirm-text="确认批量通过"
      :submitting="batchDialog.submitting"
      @confirm="submitBatch"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="checked.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 请假审批（/admin/campus-service/leave）— 列表＋详情双栏连续审批工作区（2026-07-10 第一批交互改造）。
 * 原右侧抽屉审批改为：左队列（筛选/勾选/分页/第X条）+ 右完整详情（学生/事由/附件/冲突/历史/留痕/审批区），
 * 支持上一条/下一条/通过并下一条；筛选、页码、选中项同步路由 query（刷新/后退不丢）；窄屏降级全屏详情。
 * 接口与权限零改动：getLeaveApplications / getLeaveApplicationDetail / approveLeave / returnLeave / batchApproveLeaves。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppQuickPhrases } from '@/components/common'
import { AppButton } from '@/components/ui'
import { ExportDrawer, SplitWorkspace, readListState, writeListState } from '@/modules/campusService/components'
import {
  getLeaveApplications, getLeaveApplicationDetail, approveLeave, returnLeave, batchApproveLeaves,
  getExportOptions, createExport
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

const FILTER_KEYS = ['keyword', 'type', 'status', 'classId']
const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '', classId: '' })

export default {
  name: 'LeaveApprovalView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppQuickPhrases, AppButton, ExportDrawer, SplitWorkspace
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      checked: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      pendingTotal: 0,
      selectedId: '',
      detail: null,
      comment: '',
      submitting: false,
      returnDialog: { visible: false, submitting: false },
      batchDialog: { visible: false, submitting: false },
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 请假编号' },
        { key: 'type', label: '请假类型', type: 'select', options: o.leaveType },
        { key: 'status', label: '审批状态', type: 'select', options: o.leaveStatus },
        { key: 'classId', label: '班级', type: 'select', options: f.classes }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', permission: 'campus.leave.export', label: '导出请假记录' }]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    maxPage() {
      return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
    },
    selectedIndex() {
      return this.rows.findIndex((r) => r.id === this.selectedId)
    },
    positionText() {
      const idx = this.selectedIndex
      const abs = idx >= 0 ? (this.pagination.page - 1) * this.pagination.pageSize + idx + 1 : 0
      return `${abs || '—'} / ${this.pagination.total}`
    },
    hasPrev() {
      return this.selectedIndex > 0 || this.pagination.page > 1
    },
    hasNext() {
      return (this.selectedIndex >= 0 && this.selectedIndex < this.rows.length - 1) || this.pagination.page < this.maxPage
    }
  },
  async created() {
    const st = readListState(this.$route, FILTER_KEYS)
    this.filters = { ...EMPTY_FILTERS(), ...st.filters }
    if (this.$route.query.keyword) this.filters.keyword = String(this.$route.query.keyword)
    this.pagination.page = st.page
    this.selectedId = st.selectedId
    await this.load()
    this.loadPendingTotal()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    typeLabel(v) {
      return (this.ctx.statusOptions.leaveType.find((o) => o.value === v) || {}).label || v
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.leaveStatus.find((o) => o.value === v) || {}).label || v
    },
    syncQuery() {
      writeListState(this.$router, this.$route, {
        page: this.pagination.page, filters: this.filters, selectedId: this.selectedId, filterKeys: FILTER_KEYS
      })
    },
    async loadPendingTotal() {
      const res = await getLeaveApplications({ status: 'PENDING_REVIEW', page: 1, pageSize: 1 })
      if (res.code === 0) this.pendingTotal = res.data.total
    },
    async load({ select = 'keep' } = {}) {
      this.loading = true
      this.error = ''
      const res = await getLeaveApplications({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
        this.checked = this.checked.filter((id) => this.rows.some((r) => r.id === id))
        await this.ensureSelection(select)
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async ensureSelection(mode) {
      if (!this.rows.length) {
        this.selectedId = ''
        this.detail = null
        this.syncQuery()
        return
      }
      let target = this.rows.find((r) => r.id === this.selectedId)
      if (!target || mode === 'first') target = mode === 'last' ? this.rows[this.rows.length - 1] : this.rows[0]
      await this.select(target.id)
    },
    async select(id) {
      this.selectedId = id
      this.comment = ''
      this.syncQuery()
      const res = await getLeaveApplicationDetail(id)
      if (res.code === 0) {
        this.detail = res.data
        this.$nextTick(() => {
          const el = this.$refs.list && this.$refs.list.querySelector(`[data-row-id="${id}"]`)
          if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
        })
      } else {
        this.detail = null
        toast.error(res.message)
      }
    },
    backToList() {
      this.selectedId = ''
      this.detail = null
      this.syncQuery()
    },
    async gotoPage(page) {
      if (page < 1 || page > this.maxPage) return
      this.pagination.page = page
      await this.load({ select: 'first' })
    },
    async step(delta) {
      const idx = this.selectedIndex
      const next = idx + delta
      if (next >= 0 && next < this.rows.length) {
        await this.select(this.rows[next].id)
      } else if (delta > 0 && this.pagination.page < this.maxPage) {
        this.pagination.page += 1
        await this.load({ select: 'first' })
      } else if (delta < 0 && this.pagination.page > 1) {
        this.pagination.page -= 1
        await this.load({ select: 'last' })
      }
    },
    search() {
      this.pagination.page = 1
      this.selectedId = ''
      this.load({ select: 'first' })
      this.loadPendingTotal()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.selectedId = ''
      this.load({ select: 'first' })
    },
    async onToolbar(key) {
      if (key === 'export') this.openExport()
    },
    /* 通过（goNext=true 时提交后自动进入下一条） */
    async approve(goNext) {
      if (!this.can('campus.leave.approve') || !this.detail) return
      this.submitting = true
      const prevIndex = this.selectedIndex
      const res = await approveLeave(this.detail.leave.id, { comment: this.comment.trim() })
      this.submitting = false
      if (res.code === 0) {
        toast.success('已审批通过，结果已同步学生端并留痕')
        await this.afterHandled(prevIndex, goNext)
      } else {
        /* 409 等冲突：提示并刷新（该单可能已被他人处理） */
        toast.error(res.message)
        await this.load()
        this.loadPendingTotal()
      }
    },
    onPickComment(text) {
      const el = this.$refs.commentTa
      const { value, selStart, selEnd } = insertAtCursor(el, this.comment, text)
      this.comment = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    openReturn() {
      if (!this.can('campus.leave.return') || !this.detail) return
      this.returnDialog = { visible: true, submitting: false }
    },
    async submitReturn({ reason }) {
      this.returnDialog.submitting = true
      const prevIndex = this.selectedIndex
      const res = await returnLeave(this.detail.leave.id, { reason })
      this.returnDialog.submitting = false
      if (res.code === 0) {
        toast.success('已退回修改，原因已原文同步学生端并留痕')
        this.returnDialog.visible = false
        await this.afterHandled(prevIndex, true)
      } else {
        toast.error(res.message)
        this.returnDialog.visible = false
        await this.load()
        this.loadPendingTotal()
      }
    },
    /* 处理完成后：刷新队列并定位下一条（筛选含状态时已处理单自动离队，同位即下一条） */
    async afterHandled(prevIndex, goNext) {
      const handledId = this.selectedId
      await this.loadPendingTotal()
      this.loading = true
      const res = await getLeaveApplications({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message
        return
      }
      this.rows = res.data.list
      this.pagination.total = res.data.total
      this.checked = this.checked.filter((id) => this.rows.some((r) => r.id === id))
      if (!this.rows.length) {
        if (this.pagination.page > 1) {
          this.pagination.page -= 1
          return this.load({ select: 'first' })
        }
        return this.ensureSelection('keep')
      }
      if (!goNext) {
        const still = this.rows.find((r) => r.id === handledId)
        return this.select(still ? handledId : this.rows[Math.min(prevIndex, this.rows.length - 1)].id)
      }
      const stillIdx = this.rows.findIndex((r) => r.id === handledId)
      let nextIdx = stillIdx >= 0 ? stillIdx + 1 : Math.min(Math.max(prevIndex, 0), this.rows.length - 1)
      if (nextIdx >= this.rows.length) {
        if (this.pagination.page < this.maxPage) {
          this.pagination.page += 1
          return this.load({ select: 'first' })
        }
        nextIdx = this.rows.length - 1
      }
      return this.select(this.rows[nextIdx].id)
    },
    openBatch() {
      if (!this.can('campus.leave.batchApprove') || !this.checked.length) return
      this.batchDialog = { visible: true, submitting: false }
    },
    async submitBatch() {
      this.batchDialog.submitting = true
      const res = await batchApproveLeaves(this.checked)
      this.batchDialog.submitting = false
      this.batchDialog.visible = false
      if (res.code === 0) toast.success(`批量通过 ${res.data.count} 条待审批请假（跳过非待审批状态），已留痕`)
      else toast.error(res.message)
      this.checked = []
      await this.load()
      this.loadPendingTotal()
    },
    async openExport() {
      if (!this.can('campus.leave.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('leaveList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    exportFn(payload) {
      return createExport('leaveList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.lav-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
}
.lav-queue__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-sm);
}
.lav-queue__ops .mp-link + .mp-link {
  margin-left: var(--space-2);
}
.lav-queue__list {
  max-height: 560px;
  overflow: auto;
}
.lav-item {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.lav-item:hover {
  background: var(--bg-section-blue, var(--primary-50));
}
.lav-item.is-active {
  background: var(--primary-50);
  box-shadow: inset 2px 0 0 var(--primary-500);
}
.lav-item__check {
  margin-top: 4px;
  flex-shrink: 0;
}
.lav-item__main {
  min-width: 0;
}
.lav-item__line1 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.lav-item__name {
  font-weight: var(--font-weight-semibold);
}
.lav-item__sub {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.lav-item__line2 {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
}
.lav-item__line3 {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 2px;
}
.lav-queue__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
}
.lav-detail__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.lav-detail__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.lav-detail__nav {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.lav-detail .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.lav-warn {
  font-size: var(--font-size-sm);
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  margin: var(--space-3) 0;
}
.lav-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.lav-actzone {
  margin-top: var(--space-3);
}
.lav-comment {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-base, var(--border-light));
  border-radius: var(--radius-base);
  padding: var(--space-2);
  font: inherit;
  resize: vertical;
}
.lav-actzone__btns {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.lav-actzone__sp {
  flex: 1;
}
.lav-placeholder {
  text-align: center;
}
.mp-link.is-disabled {
  pointer-events: none;
  opacity: 0.5;
}
</style>
