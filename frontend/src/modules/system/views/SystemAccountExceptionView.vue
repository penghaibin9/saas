<template>
  <ModulePageShell
    title="账号异常排查"
    subtitle="锁定 / 停用 / 长期未登录 / 强制改密 · 只读排查台账"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="ae-tabs" role="tablist" aria-label="账号类型">
        <button class="mp-link" :class="{ 'is-active': accountType === 'STAFF' }" @click="switchType('STAFF')">教职工异常</button>
        <button class="mp-link" :class="{ 'is-active': accountType === 'STUDENT' }" @click="switchType('STUDENT')">学生异常</button>
        <button class="mp-link" :class="{ 'is-active': accountType === 'BINDING' }" @click="switchType('BINDING')">身份绑定异常</button>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />
      <DataTable
        v-else
        :columns="accountType === 'BINDING' ? bindingColumns : columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-user="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.userNo }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="row.statusLabel || row.status" dot />
        </template>
        <template #cell-reasons="{ row }">
          <span v-for="r in (row.exceptionReasons || [])" :key="r" class="ae-tag">{{ r }}</span>
        </template>
        <template #cell-severity="{ row }">
          <StatusTag :type="severityTone(row.topSeverity)" :label="row.topSeverity" dot />
        </template>
        <template #cell-issues="{ row }">
          <div v-for="i in (row.issues || [])" :key="i.code" class="mp-cell-sub">
            <span class="ae-tag">{{ i.code }}</span> {{ i.message }}
          </div>
        </template>
        <template #cell-ops="{ row }">
          <button v-if="row.identitySource !== 'STUDENT_ACCOUNT_LINK'" class="mp-link"
                  @click="askRepair(row)">修复绑定</button>
          <span v-else class="mp-cell-sub">已结构化绑定</span>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="repairOpen"
      type="warning"
      title="修复身份绑定？"
      :message="repairMessage"
      confirm-text="确认修复"
      require-reason
      reason-label="修复原因"
      :submitting="submitting"
      @confirm="doRepair"
    >
      <label class="ae-field">
        学籍主档 ID
        <input v-model.trim="repairStudentId" class="ae-input" placeholder="填写 studentId（学籍主键，不是学号）" />
      </label>
      <p class="mp-note">绑定认的是学籍主键，不是学号；学号以后再改也不会失联。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemAccountExceptionView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      accountType: 'STAFF',
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      repairOpen: false,
      submitting: false,
      repairTarget: null,
      repairStudentId: '',
      columns: [
        { key: 'user', title: '账号' },
        { key: 'orgName', title: '组织' },
        { key: 'status', title: '状态' },
        { key: 'reasons', title: '异常原因' },
        { key: 'lastLoginAt', title: '最近登录' }
      ],
      bindingColumns: [
        { key: 'user', title: '账号' },
        { key: 'identitySource', title: '身份来源' },
        { key: 'severity', title: '严重度' },
        { key: 'issues', title: '异常明细' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    emptyTitle() {
      return this.accountType === 'BINDING' ? '暂无身份绑定异常' : '暂无异常账号'
    },
    emptyDesc() {
      return this.accountType === 'BINDING'
        ? '当前范围内的学生账号都已结构化绑定到学籍主档'
        : '当前范围内没有需要处理的账号异常'
    },
    repairMessage() {
      return this.repairTarget
        ? `将账号「${this.repairTarget.name}（${this.repairTarget.userNo}）」绑定到指定学籍主档，原绑定保留为历史。`
        : ''
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { ACTIVE: 'success', DISABLED: 'default', LOCKED: 'danger', PENDING: 'warning' }[s] || 'warning'
    },
    severityTone(s) {
      return { HIGH: 'danger', MEDIUM: 'warning', LOW: 'default' }[s] || 'default'
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    switchType(type) {
      if (this.accountType === type) return
      this.accountType = type
      this.pagination.page = 1
      this.load()
    },
    askRepair(row) {
      this.repairTarget = row
      this.repairStudentId = ''
      this.repairOpen = true
    },
    async doRepair({ reason }) {
      if (!this.repairTarget) return
      if (!/^\d+$/.test(this.repairStudentId)) {
        toast.error('请填写学籍主档 ID（纯数字主键）')
        return
      }
      this.submitting = true
      const res = await systemApi.repairIdentityBinding(this.repairTarget.userId, {
        studentId: this.repairStudentId,
        reason,
        expectedVersion: this.repairTarget.version
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('绑定已修复')
        this.repairOpen = false
        this.repairTarget = null
        await this.load()
      } else {
        toast.error(res.message)
        if (res.bizCode === 'DATA_CONFLICT') {
          this.repairOpen = false
          await this.load()
        }
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = this.accountType === 'BINDING'
        ? await systemApi.listIdentityIssues({
          page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        : await systemApi.listAccountExceptions({
          accountType: this.accountType,
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
      if (res.code === 0) {
        const list = res.data.list || []
        this.rows = this.accountType === 'BINDING'
          ? list.map((row) => ({ ...row, id: row.userId, name: row.realName, userNo: row.loginName }))
          : list
        this.pagination.total = res.data.total || 0
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
.ae-tag {
  display: inline-block;
  margin: 0 4px 4px 0;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--warning-50);
  color: var(--warning-700);
  font-size: var(--font-size-xs);
}
.ae-tabs {
  display: flex;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-light);
  padding-bottom: var(--space-2);
}
.ae-tabs .is-active {
  color: var(--primary-600);
  font-weight: var(--font-weight-semibold);
}
</style>
