<template>
  <ModulePageShell
    title="信息更正审核"
    :subtitle="'共 ' + pagination.total + ' 条更正申请 · 通过自动同步主档，退回原因必填'"
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
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="暂无更正申请"
        description="学生可在小程序 / 学生门户发起信息更正，提交后在此审核"
      />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · {{ row.channel }}</div>
        </template>
        <template #cell-field="{ row }">
          <div class="mp-cell-main">
            {{ row.fieldLabel }}
            <span v-if="row.sensitive" class="sc-sensitive">敏感</span>
          </div>
          <div class="mp-cell-sub">{{ maskValue(row, row.oldValue) }} → {{ maskValue(row, row.newValue) }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" dot />
        </template>
        <template #cell-review="{ row }">
          <template v-if="row.reviewer">
            <div class="mp-cell-main">{{ row.reviewer }}</div>
            <div class="mp-cell-sub">{{ row.reviewTime }}</div>
          </template>
          <span v-else class="mp-note">待审核</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看详情</button>
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link sc-gap"
            :class="{ 'is-disabled': !can('reviewCorrection') }"
            :title="reason('reviewCorrection')"
            @click="openDetail(row, true)"
          >
            去审核
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        审核通过后主档字段即时同步并记录字段级审计；证件类关键字段更正需附证明材料，退回原因将回传学生端。
      </p>
    </div>

    <!-- 详情 / 审核抽屉 -->
    <AppDrawer :visible="drawer.visible" title="更正申请详情" @update:visible="drawer.visible = $event">
      <div v-if="drawer.target" class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">申请人</span><span class="mp-kv__v">{{ drawer.target.studentName }}（{{ drawer.target.className }}）</span></div>
        <div class="mp-kv"><span class="mp-kv__k">提交渠道</span><span class="mp-kv__v">{{ drawer.target.channel }} · {{ drawer.target.submitTime }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">更正字段</span><span class="mp-kv__v">{{ drawer.target.fieldLabel }}</span></div>

        <div class="sc-diff">
          <div class="sc-diff__col">
            <div class="sc-diff__label">更正前</div>
            <div class="sc-diff__value">{{ maskValue(drawer.target, drawer.target.oldValue) }}</div>
          </div>
          <div class="sc-diff__arrow">→</div>
          <div class="sc-diff__col is-new">
            <div class="sc-diff__label">更正后</div>
            <div class="sc-diff__value">{{ maskValue(drawer.target, drawer.target.newValue) }}</div>
          </div>
        </div>

        <div class="mp-kv"><span class="mp-kv__k">申请理由</span><span class="mp-kv__v">{{ drawer.target.reason }}</span></div>
        <div class="mp-kv">
          <span class="mp-kv__k">证明材料</span>
          <span class="mp-kv__v">
            <template v-if="drawer.target.attachments.length">{{ drawer.target.attachments.join('、') }}</template>
            <span v-else class="mp-note">未上传</span>
          </span>
        </div>
        <div v-if="drawer.target.reviewer" class="mp-kv">
          <span class="mp-kv__k">审核结论</span>
          <span class="mp-kv__v">{{ drawer.target.reviewer }} · {{ drawer.target.reviewTime }} · {{ drawer.target.reviewComment }}</span>
        </div>

        <button class="mp-link" @click="$router.push('/admin/student/' + drawer.target.studentId)">查看学生360 ›</button>

        <template v-if="drawer.reviewMode && drawer.target.status === 'PENDING_REVIEW'">
          <label class="sc-field">
            <span class="sc-field__label">审核意见（通过时选填，退回时必填 ≥5 字）</span>
            <textarea v-model="drawer.comment" class="mp-textarea" placeholder="将写入审核记录与审计留痕，退回原因会回传学生端" />
          </label>
          <p v-if="drawer.error" class="mp-form-err">{{ drawer.error }}</p>
          <div class="sc-drawer-ops">
            <AppButton variant="ghost" @click="drawer.visible = false">取消</AppButton>
            <AppButton variant="secondary" :disabled="drawer.submitting" @click="submitReview('RETURN')">退回修改</AppButton>
            <AppButton variant="primary" :disabled="drawer.submitting" @click="submitReview('APPROVE')">审核通过</AppButton>
          </div>
        </template>
      </div>
    </AppDrawer>

    <!-- 导出更正记录 -->
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
/** 信息更正审核（/admin/student/corrections）：查看 → 通过 / 退回（原因必填）→ 主档同步 + 留痕。 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag as AppStatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', channel: '' })

export default {
  name: 'StudentCorrectionListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    AppStatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppConfirmDialog,
    AppButton,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '申请人' },
        { key: 'field', title: '更正内容' },
        { key: 'submitTime', title: '提交时间', width: '150px' },
        { key: 'status', title: '状态' },
        { key: 'review', title: '审核人' },
        { key: 'actions', title: '操作', width: '160px' }
      ],
      drawer: { visible: false, target: null, reviewMode: false, comment: '', error: '', submitting: false },
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
    }
  },
  created() {
    this.load()
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
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    onToolbar(key) {
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    openDetail(row, reviewMode = false) {
      if (reviewMode && !this.can('reviewCorrection')) return
      this.drawer = { visible: true, target: row, reviewMode, comment: '', error: '', submitting: false }
    },
    async submitReview(action) {
      const d = this.drawer
      d.error = ''
      if (action === 'RETURN' && String(d.comment).trim().length < 5) {
        d.error = '退回原因必填且不少于 5 个字'
        return
      }
      d.submitting = true
      const res = await studentApi.reviewCorrection(d.target.id, { action, reason: d.comment })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success(action === 'APPROVE' ? '审核通过，主档已同步更新（已留痕）' : '已退回学生修改，原因已回传（已留痕）')
        this.load()
      } else {
        d.error = res.message
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
        toast.success('更正记录导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentApi.getCorrections({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.sc-gap {
  margin-left: var(--space-2);
}
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
.sc-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.sc-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sc-drawer-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}
</style>
