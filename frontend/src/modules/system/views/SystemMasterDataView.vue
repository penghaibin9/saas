<template>
  <ModulePageShell
    title="主数据责任与数据质量"
    subtitle="数据域责任人 · 质量规则 · 问题闭环 · 合并预览（系统管理不代业务部门确认业务事实）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar
        :actions="[{ key: 'scan', label: '执行质量扫描', variant: 'primary' }, { key: 'refresh', label: '刷新' }]"
        @action="onAction"
      />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body md-summary">
            <div class="md-stat">
              <span class="md-stat__num">{{ worstScore }}</span>
              <span class="md-stat__label">最低质量分</span>
            </div>
            <div class="md-stat">
              <span class="md-stat__num">{{ issueSummary.p0Open || 0 }}</span>
              <span class="md-stat__label">P0 待处理</span>
            </div>
            <div class="md-stat">
              <span class="md-stat__num">{{ issueSummary.overdue || 0 }}</span>
              <span class="md-stat__label">已逾期</span>
            </div>
            <div class="md-stat">
              <span class="md-stat__num">{{ issueSummary.excepted || 0 }}</span>
              <span class="md-stat__label">例外中</span>
            </div>
            <div class="md-stat">
              <span class="md-stat__num">{{ domainsWithoutOwner.length }}</span>
              <span class="md-stat__label">无责任人数据域</span>
            </div>
          </div>
          <div v-if="domainsWithoutOwner.length" class="mp-card__body">
            <p class="md-warn">
              以下数据域还没有责任人，P0 规则无法运行：{{ domainsWithoutOwner.join('、') }}
            </p>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">数据域与责任人</span></header>
          <div class="mp-card__body">
            <DataTable :columns="domainColumns" :rows="domains" row-key="domainCode">
              <template #cell-domain="{ row }">
                <div class="mp-cell-main">{{ row.domainName }}</div>
                <div class="mp-cell-sub">归属 {{ moduleLabel(row.ownerModule) }}</div>
              </template>
              <template #cell-source="{ row }">
                <span class="mp-cell-sub">{{ sourceLabel(row) }}</span>
              </template>
              <template #cell-owner="{ row }">
                <StatusTag :type="row.hasOwner ? 'success' : 'danger'"
                           :label="row.hasOwner ? ownerLabel(row) : '未指定'" dot />
              </template>
              <template #cell-score="{ row }">
                <StatusTag :type="scoreTone(row.qualityScore)" :label="String(row.qualityScore)" dot />
                <div class="mp-cell-sub">未闭环 {{ row.openIssues }} · 逾期 {{ row.overdueIssues }}</div>
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="askOwner(row)">指定责任人</button>
              </template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">问题队列</span>
            <span class="mp-note">修复后必须复扫验证，问题还在会自动打回</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!issues.length" title="当前没有数据质量问题"
                        description="先指定数据域责任人，再执行一次质量扫描" />
            <DataTable v-else :columns="issueColumns" :rows="issues" row-key="issueId">
              <template #cell-issue="{ row }">
                <div class="mp-cell-main">{{ issueSummaryText(row) }}</div>
                <div class="mp-cell-sub">{{ domainLabel(row.domainCode) }} · 数据质量检查</div>
              </template>
              <template #cell-severity="{ row }">
                <StatusTag :type="severityTone(row.severity)" :label="severityLabel(row.severity)" dot />
              </template>
              <template #cell-status="{ row }">
                <StatusTag :type="statusTone(row.status)" :label="issueStatusLabel(row.status)" dot />
                <div v-if="row.verifyResult" class="mp-cell-sub">复扫 {{ verifyLabel(row.verifyResult) }}</div>
              </template>
              <template #cell-sla="{ row }">
                <div class="mp-cell-sub">{{ row.dueAt || '无 SLA' }}</div>
                <StatusTag v-if="row.overdue" type="danger" label="已逾期" dot />
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="ask('assign', row)">指派</button>
                <button class="mp-link" @click="ask('resolve', row)">登记处理</button>
                <button class="mp-link" @click="doVerify(row)">复扫验证</button>
                <button v-if="row.severity !== 'P0'" class="mp-link" @click="ask('except', row)">例外</button>
              </template>
            </DataTable>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="dialogOpen"
      :type="pendingAction === 'except' ? 'warning' : 'info'"
      :title="dialogTitle"
      :message="dialogMessage"
      :confirm-text="dialogTitle"
      require-reason
      :reason-label="pendingAction === 'resolve' ? '处理说明' : '原因'"
      :submitting="submitting"
      @confirm="submit"
    >
      <label v-if="pendingAction === 'assign' || pendingAction === 'owner'" class="md-field">
        责任人
        <AppRemoteSelect v-model="ownerInput" :remote-search="searchUsers" placeholder="选择责任人" search-placeholder="按姓名 / 工号搜索" />
      </label>
      <template v-if="pendingAction === 'except'">
        <label class="md-field">
          例外到期日
          <input v-model.trim="untilInput" class="md-input" placeholder="YYYY-MM-DD" />
        </label>
        <label class="md-field">
          审批人
          <AppRemoteSelect v-model="approverInput" :remote-search="searchUsers" placeholder="选择审批人" search-placeholder="按姓名 / 工号搜索" />
        </label>
      </template>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppRemoteSelect } from '@/components/common'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'
import { safeEnumLabel } from '@/utils/presentationSafety'

const MODULE_LABEL = { studentAffairs: '学生工作', systemAdmin: '系统管理', academicAffairs: '教务管理', dataExchange: '数据交换' }
const SOURCE_LABEL = {
  t_student_profile: '学生主档',
  't_college / t_major / t_school_class': '学院、专业与班级主数据',
  't_user / t_student_account_link': '账号与身份档案'
}
const RULE_LABEL = {
  ORG_DUPLICATE_CODE: '组织编码重复', CLASS_MISSING_COUNSELOR: '班级缺少辅导员',
  STUDENT_MISSING_CLASS: '学生尚未关联班级', STUDENT_DUPLICATE_NAME_IN_CLASS: '同班同名记录待核验',
  ACCOUNT_BROKEN_BINDING: '账号与学籍关联异常'
}
const SEVERITY_LABEL = { P0: '阻断', P1: '高', P2: '一般', CRITICAL: '阻断', HIGH: '高', MEDIUM: '一般', LOW: '提示' }
const ISSUE_STATUS_LABEL = { OPEN: '待处理', ASSIGNED: '已指派', RESOLVED: '待复扫', VERIFIED: '已闭环', EXCEPTED: '例外中' }
const VERIFY_LABEL = { GONE: '问题已消除', STILL_EXISTS: '问题仍存在', PASSED: '已通过', FAILED: '未通过' }

export default {
  name: 'SystemMasterDataView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppRemoteSelect
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      domains: [],
      domainsWithoutOwner: [],
      issues: [],
      issueSummary: {},
      directoryUsers: [],
      dialogOpen: false,
      submitting: false,
      pendingAction: '',
      pendingRow: null,
      ownerInput: '',
      untilInput: '',
      approverInput: '',
      domainColumns: [
        { key: 'domain', title: '数据域' },
        { key: 'source', title: '权威数据位置' },
        { key: 'owner', title: '责任人' },
        { key: 'score', title: '质量分' },
        { key: 'ops', title: '操作' }
      ],
      issueColumns: [
        { key: 'issue', title: '问题' },
        { key: 'severity', title: '严重度' },
        { key: 'status', title: '状态' },
        { key: 'sla', title: '处理时限' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    worstScore() {
      if (!this.domains.length) return '—'
      return Math.min(...this.domains.map((d) => Number(d.qualityScore) || 0))
    },
    dialogTitle() {
      return {
        assign: '指派责任人', resolve: '登记处理结果',
        except: '登记例外', owner: '指定数据域责任人'
      }[this.pendingAction] || '确认'
    },
    dialogMessage() {
      if (this.pendingAction === 'resolve') {
        return '登记后状态为「待复扫」，必须复扫验证问题真的消失才算闭环。'
      }
      if (this.pendingAction === 'except') {
        return '例外必须有到期日与审批人；到期后下一次扫描会自动打回待处理。'
      }
      if (this.pendingAction === 'owner') {
        return '没有责任人的数据域不能运行 P0 规则。'
      }
      return ''
    }
  },
  created() { this.load() },
  methods: {
    moduleLabel(value) { return safeEnumLabel({ value, dictionary: MODULE_LABEL, unknownLabel: '相关业务模块' }) },
    sourceLabel(row) { return row.authoritativeSourceName || safeEnumLabel({ value: row.authoritativeTable, dictionary: SOURCE_LABEL, unknownLabel: '业务主数据来源' }) },
    severityLabel(value) { return safeEnumLabel({ value, dictionary: SEVERITY_LABEL, unknownLabel: '严重度待确认' }) },
    issueStatusLabel(value) { return safeEnumLabel({ value, dictionary: ISSUE_STATUS_LABEL, unknownLabel: '状态待确认' }) },
    verifyLabel(value) { return safeEnumLabel({ value, dictionary: VERIFY_LABEL, unknownLabel: '结果待确认' }) },
    domainLabel(code) { return this.domains.find((row) => row.domainCode === code)?.domainName || '业务数据域' },
    ownerLabel(row) {
      if (row.ownerName) return row.ownerNo ? `${row.ownerName}（${row.ownerNo}）` : row.ownerName
      const user = this.directoryUsers.find((item) => String(item.id) === String(row.ownerUserId))
      return user ? `${user.name || user.realName || '责任人'}（${user.userNo || user.loginName || '工号待同步'}）` : '责任人信息待同步'
    },
    issueSummaryText(row) {
      const label = safeEnumLabel({ value: row.ruleCode, dictionary: RULE_LABEL, unknownLabel: '待处理的数据质量问题' })
      const count = Number(row.evidence?.count)
      return Number.isFinite(count) && count > 0 ? `${label}（涉及 ${count} 项）` : label
    },
    userOptions(rows) {
      return (rows || []).map((user) => ({ value: user.id, label: user.name || user.realName || '姓名待同步', desc: user.userNo || user.loginName || '工号待同步', disabled: !user.name && !user.realName }))
    },
    async searchUsers(keyword) {
      const res = await systemApi.getUsers({ keyword, pageSize: 50 })
      if (res.code !== 0) throw new Error('人员目录暂时无法读取')
      const rows = res.data?.list || []
      this.directoryUsers = [...this.directoryUsers.filter((known) => !rows.some((row) => String(row.id) === String(known.id))), ...rows]
      return this.userOptions(rows)
    },
    scoreTone(score) {
      const n = Number(score) || 0
      if (n >= 90) return 'success'
      if (n >= 60) return 'warning'
      return 'danger'
    },
    severityTone(s) {
      return { P0: 'danger', P1: 'warning', P2: 'default' }[s] || 'default'
    },
    statusTone(s) {
      return { OPEN: 'danger', ASSIGNED: 'warning', RESOLVED: 'warning',
        VERIFIED: 'success', EXCEPTED: 'default' }[s] || 'default'
    },
    onAction(key) {
      if (key === 'refresh') return this.load()
      if (key === 'scan') return this.doScan()
    },
    ask(action, row) {
      this.pendingAction = action
      this.pendingRow = row
      this.ownerInput = ''
      this.untilInput = ''
      this.approverInput = ''
      this.dialogOpen = true
    },
    askOwner(row) {
      this.ask('owner', row)
    },
    async doScan() {
      const res = await systemApi.scanMasterData()
      if (res.code === 0) {
        toast.success(`新增 ${res.data.opened}，更新 ${res.data.updated}，核销 ${res.data.cleared}`)
        await this.load()
      } else toast.error(res.message)
    },
    async doVerify(row) {
      const res = await systemApi.verifyMasterDataIssue(row.issueId)
      if (res.code === 0) {
        toast.success(res.data.verifyResult === 'GONE' ? '复扫通过，问题已消除' : '问题仍在，已打回待处理')
        await this.load()
      } else toast.error(res.message)
    },
    async submit({ reason }) {
      const row = this.pendingRow
      if (!row) return
      this.submitting = true
      let res
      if (this.pendingAction === 'owner') {
        if (!/^\d+$/.test(this.ownerInput)) {
          this.submitting = false
          return toast.error('请选择责任人')
        }
        res = await systemApi.setMasterDataOwner(row.domainCode, {
          ownerUserId: this.ownerInput, reason
        })
      } else if (this.pendingAction === 'assign') {
        if (!/^\d+$/.test(this.ownerInput)) {
          this.submitting = false
          return toast.error('请选择责任人')
        }
        res = await systemApi.assignMasterDataIssue(row.issueId, {
          ownerUserId: this.ownerInput, reason, expectedVersion: row.version
        })
      } else if (this.pendingAction === 'resolve') {
        res = await systemApi.resolveMasterDataIssue(row.issueId, {
          note: reason, expectedVersion: row.version
        })
      } else {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(this.untilInput) || !/^\d+$/.test(this.approverInput)) {
          this.submitting = false
          return toast.error('例外必须填写到期日并选择审批人')
        }
        res = await systemApi.exceptMasterDataIssue(row.issueId, {
          reason, until: this.untilInput, approvedBy: this.approverInput,
          expectedVersion: row.version
        })
      }
      this.submitting = false
      if (res.code === 0) {
        toast.success('已完成')
        this.dialogOpen = false
        this.pendingRow = null
        await this.load()
      } else {
        toast.error(res.message)
        if (res.bizCode === 'DATA_CONFLICT') {
          this.dialogOpen = false
          await this.load()
        }
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [domains, issues, users] = await Promise.all([
        systemApi.listMasterDataDomains(),
        systemApi.listMasterDataIssues(),
        systemApi.getUsers({ pageSize: 100 })
      ])
      if (domains.code === 0) {
        this.domains = domains.data.list || []
        this.domainsWithoutOwner = domains.data.domainsWithoutOwner || []
      } else this.error = domains.message
      if (issues.code === 0) {
        this.issues = issues.data.list || []
        this.issueSummary = issues.data.summary || {}
      } else if (!this.error) this.error = issues.message
      if (users.code === 0) this.directoryUsers = users.data?.list || []
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.md-summary { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.md-stat {
  min-width: 120px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}
.md-stat__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.md-stat__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.md-warn { color: var(--color-danger); }
.md-field { display: block; margin: var(--space-2) 0; }
.md-input {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 6px 10px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
}
</style>
