<template>
  <ModulePageShell
    title="信息更正审核"
    :subtitle="'共 ' + pagination.total + ' 条更正申请 · 待审核 ' + pendingTotal + ' 条 · 连续审核工作区'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="信息更正审核"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading && !rows.length" />
      <EmptyState v-else-if="!rows.length" title="暂无更正申请" description="学生可在小程序 / 学生门户发起信息更正，提交后在此审核" />
      <SplitWorkspace v-else :has-selection="!!selectedId">
        <template #left>
          <div class="sc-queue">
            <div class="sc-queue__bar"><span>第 {{ positionText }} 条</span></div>
            <div class="sc-queue__list" ref="list">
              <div
                v-for="row in rows"
                :key="row.id"
                class="sc-item"
                :class="{ 'is-active': row.id === selectedId }"
                :data-row-id="row.id"
                @click="select(row.id)"
              >
                <div class="sc-item__line1">
                  <span class="sc-item__name">{{ row.studentName }}</span>
                  <span class="sc-item__sub">{{ row.className }}</span>
                  <AppStatusTag :status="row.status" dot />
                </div>
                <div class="sc-item__line2">
                  {{ row.fieldLabel }}
                  <span v-if="row.sensitive" class="sc-sensitive">敏感</span>
                </div>
                <div class="sc-item__line3">{{ row.channel }} · {{ row.submitTime }}</div>
              </div>
            </div>
            <div class="sc-queue__pager">
              <button class="mp-link" :class="{ 'is-disabled': pagination.page <= 1 }" @click="gotoPage(pagination.page - 1)">上一页</button>
              <span class="mp-note">第 {{ pagination.page }} / {{ maxPage }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :class="{ 'is-disabled': pagination.page >= maxPage }" @click="gotoPage(pagination.page + 1)">下一页</button>
            </div>
          </div>
        </template>

        <template #detail="{ narrow }">
          <div v-if="!selected" class="mp-card sc-placeholder">
            <div class="mp-card__body"><p class="mp-note">从左侧选择一条更正申请开始审核</p></div>
          </div>
          <div v-else>
            <div class="sc-detail__head">
              <button v-if="narrow" class="mp-link" @click="backToList">← 返回列表</button>
              <div class="sc-detail__title">
                {{ selected.fieldLabel }}
                <span v-if="selected.sensitive" class="sc-sensitive">敏感</span>
                <AppStatusTag :status="selected.status" dot />
              </div>
              <div class="sc-detail__nav">
                <span class="mp-note">第 {{ positionText }} 条</span>
                <AppButton variant="ghost" :disabled="!hasPrev" @click="step(-1)">上一条</AppButton>
                <AppButton variant="ghost" :disabled="!hasNext" @click="step(1)">下一条</AppButton>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">申请信息</div></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">申请人</span><span class="mp-kv__v">{{ selected.studentName }}（{{ selected.className }}）</span></div>
                <div class="mp-kv"><span class="mp-kv__k">提交渠道</span><span class="mp-kv__v">{{ selected.channel }} · {{ selected.submitTime }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">申请理由</span><span class="mp-kv__v">{{ selected.reason }}</span></div>
                <div class="mp-kv">
                  <span class="mp-kv__k">证明材料</span>
                  <span class="mp-kv__v">
                    <template v-if="selected.attachments.length">{{ selected.attachments.join('、') }}</template>
                    <span v-else class="mp-note">未上传</span>
                  </span>
                </div>
                <div class="mp-kv">
                  <span class="mp-kv__k">快捷入口</span>
                  <span class="mp-kv__v"><button class="mp-link" @click="$router.push('/admin/student/' + selected.studentId)">查看学生360 ›</button></span>
                </div>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">更正对比</div></div>
              <div class="mp-card__body">
                <div class="sc-diff">
                  <div class="sc-diff__col">
                    <div class="sc-diff__label">更正前</div>
                    <div class="sc-diff__value">{{ maskValue(selected, selected.oldValue) }}</div>
                  </div>
                  <div class="sc-diff__arrow">→</div>
                  <div class="sc-diff__col is-new">
                    <div class="sc-diff__label">更正后</div>
                    <div class="sc-diff__value">{{ maskValue(selected, selected.newValue) }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="selected.reviewer" class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">审核结论</div></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">审核人 / 时间</span><span class="mp-kv__v">{{ selected.reviewer }} · {{ selected.reviewTime }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">意见</span><span class="mp-kv__v">{{ selected.reviewComment || '—' }}</span></div>
              </div>
            </div>

            <div v-if="selected.status === 'PENDING_REVIEW'" class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">审核意见</div></div>
              <div class="mp-card__body">
                <textarea
                  v-model="comment"
                  class="mp-textarea sc-comment"
                  placeholder="通过时选填，退回时必填 ≥5 字；将写入审核记录与审计留痕，退回原因会回传学生端"
                ></textarea>
                <p v-if="formError" class="mp-form-err">{{ formError }}</p>
                <div class="sc-actzone__btns">
                  <AppButton variant="secondary" :disabled="!can('reviewCorrection') || submitting" :title="reason('reviewCorrection')" @click="submitReview('RETURN', true)">退回修改</AppButton>
                  <span class="sc-actzone__sp" />
                  <AppButton variant="primary" :disabled="!can('reviewCorrection') || submitting" :title="reason('reviewCorrection')" @click="submitReview('APPROVE', false)">审核通过</AppButton>
                  <AppButton variant="primary" :disabled="!can('reviewCorrection') || submitting" :title="reason('reviewCorrection')" @click="submitReview('APPROVE', true)">通过并下一条</AppButton>
                </div>
              </div>
            </div>
            <p v-else class="mp-note">该申请已审核完毕；可用「上一条 / 下一条」继续处理队列中的其他申请。</p>
          </div>
        </template>
      </SplitWorkspace>

      <p class="mp-note">审核通过后主档字段即时同步并记录字段级审计；证件类关键字段更正需附证明材料，退回原因将回传学生端。</p>
    </div>

    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出更正记录"
      :message="'将导出当前筛选范围内 ' + pagination.total + ' 条更正记录：敏感字段脱敏、文件附水印、写入审计日志。'"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：数据质量月度复盘（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 信息更正审核（/admin/student/corrections）— 列表＋详情双栏连续审核工作区（2026-07-10 第二批交互改造）。
 * 原详情/审核抽屉改为：左队列 + 右完整详情（申请信息/更正对比/审核结论/审核区），
 * 支持上一条/下一条/通过并下一条、退回自动进下一条；筛选、页码、选中项同步路由 query；窄屏降级全屏详情。
 * 接口与权限零改动（studentApi.getCorrections / reviewCorrection）；敏感字段脱敏逻辑原样保留。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag as AppStatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { SplitWorkspace, readListState, writeListState } from '@/modules/campusService/components'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const FILTER_KEYS = ['keyword', 'status', 'channel']
const EMPTY_FILTERS = () => ({ keyword: '', status: '', channel: '' })

export default {
  name: 'StudentCorrectionListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, AppStatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppButton, SplitWorkspace
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      pendingTotal: 0,
      selectedId: '',
      comment: '',
      formError: '',
      submitting: false,
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    filterFields() {
      const s = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 字段名' },
        { key: 'status', label: '审核状态', type: 'select', options: s.correctionStatus },
        { key: 'channel', label: '提交渠道', type: 'select', options: s.correctionChannel }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', label: '导出更正记录', perm: 'exportCorrections' }]
        .filter((a) => pa[a.perm] && pa[a.perm].visible)
        .map((a) => ({ ...a, disabled: !pa[a.perm].allowed, disabledReason: pa[a.perm].reason }))
    },
    maxPage() {
      return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
    },
    selected() {
      return this.rows.find((r) => r.id === this.selectedId) || null
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
  created() {
    const st = readListState(this.$route, FILTER_KEYS)
    this.filters = { ...EMPTY_FILTERS(), ...st.filters }
    this.pagination.page = st.page
    this.selectedId = st.selectedId
    this.load()
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
    /** 敏感字段值展示脱敏（无明文权限时） */
    maskValue(row, v) {
      if (!row.sensitive || this.can('viewSensitive')) return v
      const s = String(v || '')
      if (s.length <= 4) return '****'
      return s.slice(0, 3) + '****' + s.slice(-3)
    },
    syncQuery() {
      writeListState(this.$router, this.$route, {
        page: this.pagination.page, filters: this.filters, selectedId: this.selectedId, filterKeys: FILTER_KEYS
      })
    },
    async loadPendingTotal() {
      const res = await studentApi.getCorrections({ status: 'PENDING_REVIEW', page: 1, pageSize: 1 })
      if (res.code === 0) this.pendingTotal = res.data.total
    },
    async load({ select = 'keep' } = {}) {
      this.loading = true
      this.error = ''
      const res = await studentApi.getCorrections({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
        this.ensureSelection(select)
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    ensureSelection(mode) {
      if (!this.rows.length) {
        this.selectedId = ''
        this.syncQuery()
        return
      }
      let target = this.rows.find((r) => r.id === this.selectedId)
      if (!target || mode === 'first') target = mode === 'last' ? this.rows[this.rows.length - 1] : this.rows[0]
      this.select(target.id)
    },
    select(id) {
      this.selectedId = id
      this.comment = ''
      this.formError = ''
      this.syncQuery()
      this.$nextTick(() => {
        const el = this.$refs.list && this.$refs.list.querySelector(`[data-row-id="${id}"]`)
        if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
      })
    },
    backToList() {
      this.selectedId = ''
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
        this.select(this.rows[next].id)
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
    onToolbar(key) {
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    async submitReview(action, goNext) {
      if (!this.can('reviewCorrection') || !this.selected) return
      this.formError = ''
      if (action === 'RETURN' && String(this.comment).trim().length < 5) {
        this.formError = '退回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const prevIndex = this.selectedIndex
      const res = await studentApi.reviewCorrection(this.selected.id, { action, reason: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success(action === 'APPROVE' ? '审核通过，主档已同步更新（已留痕）' : '已退回学生修改，原因已回传（已留痕）')
        await this.afterHandled(prevIndex, goNext)
      } else {
        this.formError = res.message
      }
    },
    async afterHandled(prevIndex, goNext) {
      const handledId = this.selectedId
      this.loadPendingTotal()
      const res = await studentApi.getCorrections({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code !== 0) {
        this.error = res.message
        return
      }
      this.rows = res.data.list
      this.pagination.total = res.data.total
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
      this.select(this.rows[nextIdx].id)
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'FILTERED',
        fieldKeys: ['name', 'studentNo'],
        purpose: 'AUDIT',
        remark: reason,
        rowCount: this.pagination.total
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('更正记录导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-sensitive {
  display: inline-block;
  margin-left: var(--space-1);
  padding: 0 var(--space-1);
  border-radius: var(--radius-base);
  background: var(--warning-50);
  color: var(--warning-600);
  border: 1px solid var(--warning-100);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-normal);
}
.sc-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
}
.sc-queue__bar {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-sm);
}
.sc-queue__list {
  max-height: 560px;
  overflow: auto;
}
.sc-item {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.sc-item:hover {
  background: var(--bg-section-blue, var(--primary-50));
}
.sc-item.is-active {
  background: var(--primary-50);
  box-shadow: inset 2px 0 0 var(--primary-500);
}
.sc-item__line1 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.sc-item__name {
  font-weight: var(--font-weight-semibold);
}
.sc-item__sub {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.sc-item__line2 {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
}
.sc-item__line3 {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 2px;
}
.sc-queue__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
}
.sc-detail__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.sc-detail__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.sc-detail__nav {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.mp-stack .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.sc-diff {
  display: flex;
  align-items: stretch;
  gap: var(--space-2);
}
.sc-diff__col {
  flex: 1;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-section-blue);
}
.sc-diff__col.is-new {
  background: var(--primary-50);
  border-color: var(--primary-100);
}
.sc-diff__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sc-diff__value {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  word-break: break-all;
}
.sc-diff__arrow {
  align-self: center;
  color: var(--text-tertiary);
}
.sc-comment {
  width: 100%;
  box-sizing: border-box;
}
.sc-actzone__btns {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.sc-actzone__sp {
  flex: 1;
}
.sc-placeholder {
  text-align: center;
}
.mp-link.is-disabled {
  pointer-events: none;
  opacity: 0.5;
}
</style>
