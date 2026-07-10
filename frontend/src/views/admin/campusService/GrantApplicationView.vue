<template>
  <ModulePageShell
    title="奖助资助"
    :subtitle="'共 ' + pagination.total + ' 条 · 待审核 ' + pendingTotal + ' 条 · 金额区间化展示，困难材料仅授权角色可见'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的资助申请" description="学生可通过小程序提交奖助/资助申请，审核结果实时同步学生端" />
      <SplitWorkspace v-else :has-selection="!!selectedId">
        <template #left>
          <div class="gav-queue">
            <div class="gav-queue__bar">
              <span class="gav-queue__pos">第 {{ positionText }} 条</span>
              <span class="gav-queue__ops">
                <button class="mp-link" :class="{ 'is-disabled': !can('campus.grant.batchReview') || !checked.length }" :title="reason('campus.grant.batchReview')" @click="openBatch">批量通过{{ checked.length ? '（' + checked.length + '）' : '' }}</button>
                <button class="mp-link" :class="{ 'is-disabled': !can('campus.grant.export') }" :title="reason('campus.grant.export')" @click="openExport">导出</button>
              </span>
            </div>
            <div class="gav-queue__list" ref="list">
              <div
                v-for="row in rows"
                :key="row.id"
                class="gav-item"
                :class="{ 'is-active': row.id === selectedId }"
                :data-row-id="row.id"
                @click="select(row.id)"
              >
                <input class="gav-item__check" type="checkbox" :value="row.id" v-model="checked" @click.stop />
                <div class="gav-item__main">
                  <div class="gav-item__line1">
                    <span class="gav-item__name">{{ row.name }}</span>
                    <span class="gav-item__sub">{{ row.className }}</span>
                    <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
                  </div>
                  <div class="gav-item__line2">{{ typeLabel(row.type) }} · {{ row.amountDisplay }}</div>
                  <div class="gav-item__line3">{{ row.code }} · {{ row.currentNode }}</div>
                </div>
              </div>
            </div>
            <div class="gav-queue__pager">
              <button class="mp-link" :class="{ 'is-disabled': pagination.page <= 1 }" @click="gotoPage(pagination.page - 1)">上一页</button>
              <span class="mp-note">第 {{ pagination.page }} / {{ maxPage }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :class="{ 'is-disabled': pagination.page >= maxPage }" @click="gotoPage(pagination.page + 1)">下一页</button>
            </div>
          </div>
        </template>

        <template #detail="{ narrow }">
          <div v-if="!detail" class="mp-card gav-placeholder">
            <div class="mp-card__body"><p class="mp-note">从左侧选择一条资助申请开始审核</p></div>
          </div>
          <div v-else class="gav-detail">
            <div class="gav-detail__head">
              <button v-if="narrow" class="mp-link" @click="backToList">← 返回列表</button>
              <div class="gav-detail__title">
                {{ detail.grant.code }}
                <StatusTag :status="detail.grant.status" :label="statusLabel(detail.grant.status)" dot />
              </div>
              <div class="gav-detail__nav">
                <span class="mp-note">第 {{ positionText }} 条</span>
                <AppButton variant="ghost" :disabled="!hasPrev" @click="step(-1)">上一条</AppButton>
                <AppButton variant="ghost" :disabled="!hasNext" @click="step(1)">下一条</AppButton>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">学生与申请信息</div></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.grant.name }}（{{ detail.grant.className }}）</span></div>
                <div class="mp-kv"><span class="mp-kv__k">申请项目</span><span class="mp-kv__v">{{ typeLabel(detail.grant.type) }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">金额（区间）</span><span class="mp-kv__v">{{ detail.grant.amountDisplay }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">申请理由</span><span class="mp-kv__v">{{ detail.grant.applyReason }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">当前节点</span><span class="mp-kv__v">{{ detail.grant.currentNode }}</span></div>
                <div v-if="detail.grant.returnReason" class="mp-kv"><span class="mp-kv__k">退回原因</span><span class="mp-kv__v">{{ detail.grant.returnReason }}</span></div>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">困难等级 / 资格信息</div></div>
              <div class="mp-card__body">
                <p class="mp-note">暂无相关数据（困难认定模块尚未接入，接入后此处展示困难等级、认定有效期与资格校验结论，不展示推测数据）。</p>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">申请材料（敏感收敛）</div></div>
              <div class="mp-card__body">
                <template v-if="detail.materials && detail.materials.length">
                  <ul class="gav-list">
                    <li v-for="m in detail.materials" :key="m">{{ m }}</li>
                  </ul>
                  <p class="mp-note">本次查看已写入审计日志。</p>
                </template>
                <div v-else class="gav-warn">{{ detail.materialHint || '当前角色不可查看困难材料明细' }}</div>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">历史申请</div></div>
              <div class="mp-card__body">
                <p class="mp-note">暂无相关数据（历史申请聚合随统一资助抽象接入，不展示推测数据）。</p>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">审核流程留痕</div></div>
              <div class="mp-card__body">
                <table class="mp-audit">
                  <thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead>
                  <tbody>
                    <tr v-for="a in detail.auditLogs" :key="a.id">
                      <td>{{ a.time }}</td>
                      <td class="is-who">{{ a.operator }}</td>
                      <td>{{ a.detail }}</td>
                    </tr>
                    <tr v-if="!detail.auditLogs.length"><td colspan="3" class="mp-note">暂无审核记录</td></tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="reviewable" class="mp-card gav-actzone">
              <div class="mp-card__head"><div class="mp-card__title">审核意见</div></div>
              <div class="mp-card__body">
                <textarea
                  v-model="comment"
                  class="gav-comment"
                  rows="2"
                  placeholder="审核意见（通过时选填；退回时作为退回原因必填，不少于 5 个字，原文同步学生端）"
                ></textarea>
                <div class="gav-actzone__btns">
                  <AppButton variant="danger" :disabled="!can('campus.grant.return')" :title="reason('campus.grant.return')" @click="openReturn">退回补充</AppButton>
                  <span class="gav-actzone__sp" />
                  <AppButton variant="primary" :disabled="!can('campus.grant.review') || submitting" :title="reason('campus.grant.review')" @click="approve(false)">通过</AppButton>
                  <AppButton variant="primary" :disabled="!can('campus.grant.review') || submitting" :title="reason('campus.grant.review')" @click="approve(true)">通过并下一条</AppButton>
                </div>
              </div>
            </div>
            <p v-else class="mp-note">该申请当前不在可审核状态；可用「上一条 / 下一条」继续处理队列中的其他申请。</p>
          </div>
        </template>
      </SplitWorkspace>

      <p class="mp-note">
        资助审核为资助老师专属权限；家庭经济困难材料默认不展示，仅授权角色可查看且查看写审计。退回原因必填并同步学生端；导出台账金额区间化、含水印并留痕。
      </p>
    </div>

    <AppConfirmDialog
      v-model:visible="returnDialog.visible"
      type="danger"
      title="退回补充"
      :message="'退回「' + (detail ? detail.grant.code : '') + '」资助申请，退回原因将原文同步学生端。'"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      reason-placeholder="请说明需补充的材料或不符合项，不少于 5 个字"
      :submitting="returnDialog.submitting"
      @confirm="submitReturn"
    />

    <AppConfirmDialog
      v-model:visible="batchDialog.visible"
      type="primary"
      title="批量审核通过"
      :message="'确认批量通过选中的 ' + checked.length + ' 条资助申请？非待审核状态将自动跳过，结果同步学生端并留痕。'"
      confirm-text="确认批量通过"
      :submitting="batchDialog.submitting"
      @confirm="submitBatch"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="checked.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 奖助 / 资助审核（/admin/campus-service/grants）— 列表＋详情双栏连续审核工作区（2026-07-10 第一批交互改造）。
 * 原右侧抽屉审核改为：左队列 + 右完整详情（学生/项目/金额区间/理由/材料敏感收敛/留痕/审核区），
 * 支持上一条/下一条/通过并下一条；筛选、页码、选中项同步路由 query；窄屏降级全屏详情。
 * 困难等级与历史申请无真实接口，明确显示「暂无相关数据」，不虚构。接口与权限零改动。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppButton } from '@/components/ui'
import { ExportDrawer, SplitWorkspace, readListState, writeListState } from '@/modules/campusService/components'
import {
  getGrantApplications, getGrantApplicationDetail, approveGrant, returnGrant, batchApproveGrants,
  getExportOptions, createExport
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const FILTER_KEYS = ['keyword', 'type', 'status']
const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })
const REVIEWABLE = ['PENDING_REVIEW', 'REVIEWING']

export default {
  name: 'GrantApplicationView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppButton, ExportDrawer, SplitWorkspace
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
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 申请编号' },
        { key: 'type', label: '申请类型', type: 'select', options: o.grantType },
        { key: 'status', label: '审核状态', type: 'select', options: o.grantStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', permission: 'campus.grant.export', label: '导出资助台账' }]
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
    },
    reviewable() {
      return !!(this.detail && REVIEWABLE.includes(this.detail.grant.status))
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
      return (this.ctx.statusOptions.grantType.find((o) => o.value === v) || {}).label || v
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.grantStatus.find((o) => o.value === v) || {}).label || v
    },
    syncQuery() {
      writeListState(this.$router, this.$route, {
        page: this.pagination.page, filters: this.filters, selectedId: this.selectedId, filterKeys: FILTER_KEYS
      })
    },
    async loadPendingTotal() {
      const res = await getGrantApplications({ status: 'PENDING_REVIEW', page: 1, pageSize: 1 })
      if (res.code === 0) this.pendingTotal = res.data.total
    },
    async load({ select = 'keep' } = {}) {
      this.loading = true
      this.error = ''
      const res = await getGrantApplications({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      const res = await getGrantApplicationDetail(id)
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
    async approve(goNext) {
      if (!this.can('campus.grant.review') || !this.detail) return
      this.submitting = true
      const prevIndex = this.selectedIndex
      const res = await approveGrant(this.detail.grant.id, { comment: this.comment.trim() })
      this.submitting = false
      if (res.code === 0) {
        toast.success('已审核通过，进入发放流程（已留痕并同步学生端）')
        await this.afterHandled(prevIndex, goNext)
      } else {
        toast.error(res.message)
        await this.load()
        this.loadPendingTotal()
      }
    },
    openReturn() {
      if (!this.can('campus.grant.return') || !this.detail) return
      this.returnDialog = { visible: true, submitting: false }
    },
    async submitReturn({ reason }) {
      this.returnDialog.submitting = true
      const prevIndex = this.selectedIndex
      const res = await returnGrant(this.detail.grant.id, { reason })
      this.returnDialog.submitting = false
      if (res.code === 0) {
        toast.success('已退回补充，原因已原文同步学生端并留痕')
        this.returnDialog.visible = false
        await this.afterHandled(prevIndex, true)
      } else {
        toast.error(res.message)
        this.returnDialog.visible = false
        await this.load()
        this.loadPendingTotal()
      }
    },
    async afterHandled(prevIndex, goNext) {
      const handledId = this.selectedId
      await this.loadPendingTotal()
      this.loading = true
      const res = await getGrantApplications({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      if (!this.can('campus.grant.batchReview') || !this.checked.length) return
      this.batchDialog = { visible: true, submitting: false }
    },
    async submitBatch() {
      this.batchDialog.submitting = true
      const res = await batchApproveGrants(this.checked)
      this.batchDialog.submitting = false
      this.batchDialog.visible = false
      if (res.code === 0) toast.success(`批量通过 ${res.data.count} 条资助申请（跳过非待审核状态），已留痕`)
      else toast.error(res.message)
      this.checked = []
      await this.load()
      this.loadPendingTotal()
    },
    async openExport() {
      if (!this.can('campus.grant.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('grantList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    exportFn(payload) {
      return createExport('grantList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gav-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
}
.gav-queue__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-sm);
}
.gav-queue__ops .mp-link + .mp-link {
  margin-left: var(--space-2);
}
.gav-queue__list {
  max-height: 560px;
  overflow: auto;
}
.gav-item {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.gav-item:hover {
  background: var(--bg-section-blue, var(--primary-50));
}
.gav-item.is-active {
  background: var(--primary-50);
  box-shadow: inset 2px 0 0 var(--primary-500);
}
.gav-item__check {
  margin-top: 4px;
  flex-shrink: 0;
}
.gav-item__main {
  min-width: 0;
}
.gav-item__line1 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.gav-item__name {
  font-weight: var(--font-weight-semibold);
}
.gav-item__sub {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.gav-item__line2 {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
}
.gav-item__line3 {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 2px;
}
.gav-queue__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
}
.gav-detail__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.gav-detail__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.gav-detail__nav {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.gav-detail .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.gav-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.gav-warn {
  font-size: var(--font-size-sm);
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.gav-actzone {
  margin-top: var(--space-3);
}
.gav-comment {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-base, var(--border-light));
  border-radius: var(--radius-base);
  padding: var(--space-2);
  font: inherit;
  resize: vertical;
}
.gav-actzone__btns {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.gav-actzone__sp {
  flex: 1;
}
.gav-placeholder {
  text-align: center;
}
.mp-link.is-disabled {
  pointer-events: none;
  opacity: 0.5;
}
</style>
