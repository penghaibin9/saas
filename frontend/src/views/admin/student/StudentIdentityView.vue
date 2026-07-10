<template>
  <ModulePageShell
    title="身份核验记录"
    :subtitle="'共 ' + pagination.total + ' 条核验记录 · 待复核 ' + pendingTotal + ' 条 · 连续复核工作区'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="身份核验管理"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading && !rows.length" />
      <EmptyState v-else-if="!rows.length" title="暂无符合条件的核验记录" description="可调整筛选条件后重新查询" />
      <SplitWorkspace v-else :has-selection="!!selectedId">
        <template #left>
          <div class="si-queue">
            <div class="si-queue__bar"><span>第 {{ positionText }} 条</span></div>
            <div class="si-queue__list" ref="list">
              <div
                v-for="row in rows"
                :key="row.id"
                class="si-item"
                :class="{ 'is-active': row.id === selectedId }"
                :data-row-id="row.id"
                @click="select(row.id)"
              >
                <div class="si-item__line1">
                  <span class="si-item__name">{{ row.studentName }}</span>
                  <span class="si-item__sub">{{ row.className }}</span>
                  <AppStatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
                </div>
                <div class="si-item__line2">
                  <AppStatusTag :type="resultTone(row.result)" :label="resultLabel(row.result)" />
                  <span v-if="row.similarity">相似度 {{ row.similarity }}</span>
                </div>
                <div class="si-item__line3">{{ row.method }} · {{ row.checkedAt }}</div>
              </div>
            </div>
            <div class="si-queue__pager">
              <button class="mp-link" :class="{ 'is-disabled': pagination.page <= 1 }" @click="gotoPage(pagination.page - 1)">上一页</button>
              <span class="mp-note">第 {{ pagination.page }} / {{ maxPage }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :class="{ 'is-disabled': pagination.page >= maxPage }" @click="gotoPage(pagination.page + 1)">下一页</button>
            </div>
          </div>
        </template>

        <template #detail="{ narrow }">
          <div v-if="!selected" class="mp-card si-placeholder">
            <div class="mp-card__body"><p class="mp-note">从左侧选择一条核验记录开始复核</p></div>
          </div>
          <div v-else>
            <div class="si-detail__head">
              <button v-if="narrow" class="mp-link" @click="backToList">← 返回列表</button>
              <div class="si-detail__title">
                {{ selected.studentName }}
                <AppStatusTag :type="statusTone(selected.status)" :label="statusLabel(selected.status)" dot />
              </div>
              <div class="si-detail__nav">
                <span class="mp-note">第 {{ positionText }} 条</span>
                <AppButton variant="ghost" :disabled="!hasPrev" @click="step(-1)">上一条</AppButton>
                <AppButton variant="ghost" :disabled="!hasNext" @click="step(1)">下一条</AppButton>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">核验信息</div></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ selected.studentName }}（{{ selected.className }}）</span></div>
                <div class="mp-kv"><span class="mp-kv__k">核验方式</span><span class="mp-kv__v">{{ selected.method }}</span></div>
                <div class="mp-kv">
                  <span class="mp-kv__k">机器结论</span>
                  <span class="mp-kv__v">
                    <AppStatusTag :type="resultTone(selected.result)" :label="resultLabel(selected.result)" />
                    <template v-if="selected.similarity">（相似度 {{ selected.similarity }}）</template>
                  </span>
                </div>
                <div class="mp-kv"><span class="mp-kv__k">核验时间</span><span class="mp-kv__v">{{ selected.checkedAt }}</span></div>
                <div v-if="selected.reviewer" class="mp-kv"><span class="mp-kv__k">复核结论</span><span class="mp-kv__v">{{ selected.reviewer }} · {{ selected.reviewComment || '—' }}</span></div>
                <div class="mp-kv">
                  <span class="mp-kv__k">快捷入口</span>
                  <span class="mp-kv__v"><button class="mp-link" @click="$router.push('/admin/student/' + selected.studentId)">学生360 ›</button></span>
                </div>
              </div>
            </div>

            <div v-if="selected.status === 'PENDING_REVIEW'" class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">人工复核</div></div>
              <div class="mp-card__body">
                <label class="mp-radio" :class="{ 'is-active': action === 'CONFIRM' }">
                  <input v-model="action" type="radio" value="CONFIRM" />
                  <span>
                    <span class="mp-radio__title">复核通过</span>
                    <span class="mp-radio__desc">确认身份真实有效，主档核验状态更新为「已核验」</span>
                  </span>
                </label>
                <label class="mp-radio" :class="{ 'is-active': action === 'RETURN' }">
                  <input v-model="action" type="radio" value="RETURN" />
                  <span>
                    <span class="mp-radio__title">退回重验</span>
                    <span class="mp-radio__desc">材料不足或比对存疑，退回学生端重新提交（原因必填）</span>
                  </span>
                </label>
                <textarea
                  v-model="comment"
                  class="mp-textarea si-comment"
                  :placeholder="action === 'RETURN' ? '退回原因 *（≥5 字），将写入核验记录与审计留痕' : '复核意见（选填），将写入核验记录与审计留痕'"
                ></textarea>
                <p v-if="formError" class="mp-form-err">{{ formError }}</p>
                <div class="si-actzone__btns">
                  <AppButton
                    variant="secondary"
                    :disabled="!can('markIdentityAbnormal') || submitting"
                    :title="reason('markIdentityAbnormal')"
                    @click="openAbnormal(selected)"
                  >标记异常</AppButton>
                  <span class="si-actzone__sp" />
                  <AppButton variant="primary" :disabled="!can('reviewIdentity') || submitting" :title="reason('reviewIdentity')" @click="submitReview(false)">
                    {{ action === 'RETURN' ? '确认退回' : '确认通过' }}
                  </AppButton>
                  <AppButton variant="primary" :disabled="!can('reviewIdentity') || submitting" :title="reason('reviewIdentity')" @click="submitReview(true)">提交并下一条</AppButton>
                </div>
              </div>
            </div>
            <div v-else class="si-done">
              <p class="mp-note">该记录已处理完毕；可用「上一条 / 下一条」继续处理队列中的其他记录。</p>
              <AppButton
                v-if="selected.status !== 'ABNORMAL'"
                variant="ghost"
                :disabled="!can('markIdentityAbnormal')"
                :title="reason('markIdentityAbnormal')"
                @click="openAbnormal(selected)"
              >标记异常</AppButton>
            </div>
          </div>
        </template>
      </SplitWorkspace>

      <p class="mp-note">核验结论直接回写学生主档身份状态；异常记录将同步生成「身份异常」风险标签建议。</p>
    </div>

    <!-- 标记异常 -->
    <AppConfirmDialog
      :visible="abnormalDialog.visible"
      type="danger"
      title="标记核验异常"
      :message="abnormalDialog.target ? '确认将 ' + abnormalDialog.target.studentName + ' 的本条核验记录标记为异常？主档身份状态将同步为「核验异常」。' : ''"
      confirm-text="确认标记异常"
      require-reason
      reason-label="异常说明"
      reason-placeholder="如：证件照片存在明显 PS 痕迹（不少于 5 个字）"
      :submitting="abnormalDialog.submitting"
      @update:visible="abnormalDialog.visible = $event"
      @confirm="submitAbnormal"
    />

    <!-- 导出核验记录 -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出核验记录"
      :message="'将导出当前筛选范围内 ' + pagination.total + ' 条核验记录：证件号自动脱敏、文件附水印、写入审计日志。'"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：实名核验专项检查（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 身份核验记录（/admin/student/identity）— 列表＋详情双栏连续复核工作区（2026-07-10 第二批交互改造）。
 * 原人工复核抽屉改为右栏复核区（通过/退回单选 + 意见 + 提交并下一条）；标记异常保持确认弹窗（原因必填）。
 * 筛选、页码、选中项同步路由 query；窄屏降级全屏详情；接口与权限零改动
 * （studentApi.getIdentityRecords / reviewIdentityRecord / markIdentityAbnormal）。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag as AppStatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { SplitWorkspace, readListState, writeListState } from '@/modules/campusService/components'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const FILTER_KEYS = ['keyword', 'status', 'result']
const EMPTY_FILTERS = () => ({ keyword: '', status: '', result: '' })

export default {
  name: 'StudentIdentityView',
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
      action: 'CONFIRM',
      comment: '',
      formError: '',
      submitting: false,
      abnormalDialog: { visible: false, target: null, submitting: false },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    filterFields() {
      const s = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '学生姓名', type: 'text', placeholder: '按姓名搜索' },
        { key: 'status', label: '处理状态', type: 'select', options: s.identityRecordStatus },
        { key: 'result', label: '机器结论', type: 'select', options: s.identityResult }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', label: '导出核验记录', perm: 'exportIdentityRecords' }]
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
    resultLabel(v) {
      const hit = this.ctx.statusOptions.identityResult.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    resultTone(v) {
      return { PASS: 'success', FAIL: 'danger', PENDING: 'warning' }[v] || 'default'
    },
    statusLabel(v) {
      const hit = this.ctx.statusOptions.identityRecordStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    statusTone(v) {
      return { PENDING_REVIEW: 'warning', CONFIRMED: 'success', ABNORMAL: 'danger' }[v] || 'default'
    },
    syncQuery() {
      writeListState(this.$router, this.$route, {
        page: this.pagination.page, filters: this.filters, selectedId: this.selectedId, filterKeys: FILTER_KEYS
      })
    },
    async loadPendingTotal() {
      const res = await studentApi.getIdentityRecords({ status: 'PENDING_REVIEW', page: 1, pageSize: 1 })
      if (res.code === 0) this.pendingTotal = res.data.total
    },
    async load({ select = 'keep' } = {}) {
      this.loading = true
      this.error = ''
      const res = await studentApi.getIdentityRecords({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      this.action = 'CONFIRM'
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
    async submitReview(goNext) {
      if (!this.can('reviewIdentity') || !this.selected) return
      this.formError = ''
      if (this.action === 'RETURN' && String(this.comment).trim().length < 5) {
        this.formError = '退回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const prevIndex = this.selectedIndex
      const res = await studentApi.reviewIdentityRecord(this.selected.id, { action: this.action, comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.action === 'RETURN' ? '已退回学生重验，原因已回传（已留痕）' : '复核通过，主档核验状态已更新（已留痕）')
        await this.afterHandled(prevIndex, goNext)
      } else {
        this.formError = res.message
      }
    },
    async afterHandled(prevIndex, goNext) {
      const handledId = this.selectedId
      this.loadPendingTotal()
      const res = await studentApi.getIdentityRecords({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
    openAbnormal(row) {
      if (!this.can('markIdentityAbnormal')) return
      this.abnormalDialog = { visible: true, target: row, submitting: false }
    },
    async submitAbnormal({ reason }) {
      const d = this.abnormalDialog
      d.submitting = true
      const res = await studentApi.markIdentityAbnormal(d.target.id, { reason })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success('已标记核验异常，主档身份状态已同步（已留痕）')
        this.load()
        this.loadPendingTotal()
      } else {
        toast.error(res.message)
      }
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
        toast.success('核验记录导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.si-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
}
.si-queue__bar {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-sm);
}
.si-queue__list {
  max-height: 560px;
  overflow: auto;
}
.si-item {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.si-item:hover {
  background: var(--bg-section-blue, var(--primary-50));
}
.si-item.is-active {
  background: var(--primary-50);
  box-shadow: inset 2px 0 0 var(--primary-500);
}
.si-item__line1 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.si-item__name {
  font-weight: var(--font-weight-semibold);
}
.si-item__sub {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.si-item__line2 {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.si-item__line3 {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 2px;
}
.si-queue__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
}
.si-detail__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.si-detail__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.si-detail__nav {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.mp-stack .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.si-comment {
  width: 100%;
  box-sizing: border-box;
  margin-top: var(--space-2);
}
.si-actzone__btns {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.si-actzone__sp {
  flex: 1;
}
.si-done {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.si-placeholder {
  text-align: center;
}
.mp-link.is-disabled {
  pointer-events: none;
  opacity: 0.5;
}
</style>
