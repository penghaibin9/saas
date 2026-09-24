<template>
  <ModulePageShell
    title="角色成员与业务身份"
    subtitle="固定角色看有效期与来源 · 自动业务身份由业务表实时计算，本页不写业务终态"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onAction" />
    </template>

    <div class="mp-stack">
      <div class="ra-tabs" role="tablist">
        <button class="mp-link" :class="{ 'is-active': tab === 'members' }" @click="switchTab('members')">固定角色成员</button>
        <button class="mp-link" :class="{ 'is-active': tab === 'identities' }" @click="switchTab('identities')">自动业务身份</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else-if="tab === 'members'">
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body ra-buckets">
            <button v-for="b in bucketList" :key="b.key" class="ra-bucket"
                    :class="{ 'is-active': bucket === b.key }" @click="pickBucket(b.key)">
              <span class="ra-bucket__num">{{ b.count }}</span>
              <span class="ra-bucket__label">{{ b.label }}</span>
            </button>
          </div>
        </section>

        <EmptyState v-if="!rows.length" title="没有符合条件的角色成员"
                    description="换一个分类，或先在账号页面授予角色" />
        <DataTable v-else :columns="memberColumns" :rows="rows" row-key="userRoleId">
          <template #cell-user="{ row }">
            <div class="mp-cell-main">{{ row.realName || row.loginName }}</div>
            <div class="mp-cell-sub">{{ row.loginName }} · {{ row.roleName || roleLabel(row.roleCode) }}</div>
          </template>
          <template #cell-validity="{ row }">
            <div class="mp-cell-sub">生效 {{ row.effectiveAt || '—' }}</div>
            <div class="mp-cell-sub">
              到期 {{ row.expiresAt || '长期有效' }}
              <span v-if="row.daysLeft !== null && row.daysLeft !== undefined">（剩 {{ row.daysLeft }} 天）</span>
            </div>
          </template>
          <template #cell-source="{ row }">
            <StatusTag :type="row.sourceType === 'UNKNOWN' ? 'warning' : 'default'"
                       :label="sourceTypeLabel(row.sourceType)" dot />
            <div class="mp-cell-sub">{{ row.reason || '—' }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
            <div v-if="row.lastReviewedAt" class="mp-cell-sub">复核 {{ row.lastReviewedTerm }}</div>
            <div v-else class="mp-cell-sub">未复核</div>
          </template>
          <template #cell-ops="{ row }">
            <template v-if="row.assignmentId">
              <button class="mp-link" @click="ask('review', row)">复核</button>
              <button v-if="canManageAssignments" class="mp-link" @click="ask('transfer', row)">转交</button>
              <button v-if="canManageAssignments" class="mp-link" @click="ask('revoke', row)">回收</button>
            </template>
            <button v-else-if="canManageAssignments" type="button" class="mp-link" @click="ask('register', row)">补登记</button>
            <span v-else class="mp-cell-sub">历史授权，待管理员补登记</span>
          </template>
        </DataTable>
        <nav class="ra-pager" aria-label="角色授权分页">
          <span>共 {{ total }} 条 · 每页 {{ pageSize }} 条 · 第 {{ page }} / {{ pageCount }} 页</span>
          <button type="button" class="mp-link" :disabled="loading || submitting || page <= 1" @click="changePage(page - 1)">上一页</button>
          <button type="button" class="mp-link" :disabled="loading || submitting || page >= pageCount" @click="changePage(page + 1)">下一页</button>
          <label>跳至 <input v-model.number="targetPage" class="ra-page-input" type="number" aria-label="授权清单页码" min="1" :max="pageCount" :disabled="loading || submitting" @keyup.enter="changePage(targetPage)" /> 页</label>
          <button type="button" class="mp-link" :disabled="loading || submitting" @click="changePage(targetPage)">跳转</button>
        </nav>
      </template>

      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">自动业务身份</span>
            <span class="mp-note">{{ identityNote }}</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!identities.length" title="当前没有自动业务身份"
                        description="业务身份来自任课、毕设、实习等业务关系，先在对应业务模块建立关系" />
            <DataTable v-else :columns="identityColumns" :rows="identities" row-key="subjectKey">
              <template #cell-identity="{ row }">
                <div class="mp-cell-main">{{ row.label }}</div>
                <div class="mp-cell-sub">{{ identityTypeLabel(row.identityType) }}</div>
              </template>
              <template #cell-subject="{ row }">
                <div class="mp-cell-main">{{ row.name || row.subjectKey }}</div>
                <div class="mp-cell-sub">
                  <StatusTag v-if="!row.subjectResolved" type="warning" label="未映射到账号" dot />
                  <span v-else>用户编号 {{ row.userId }}</span>
                </div>
              </template>
              <template #cell-scope="{ row }">
                <div class="mp-cell-sub">{{ row.objectCount }} 个对象</div>
                <div class="mp-cell-sub">{{ (row.objects || []).slice(0, 5).join('、') }}</div>
              </template>
              <template #cell-owner="{ row }">
                <div class="mp-cell-sub">{{ moduleLabel(row.ownerModule) }}</div>
                <div class="mp-cell-sub">{{ sourceText(row.source) }}</div>
              </template>
            </DataTable>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      :visible="dialogOpen"
      @update:visible="setDialogVisible"
      :type="pendingAction === 'revoke' ? 'warning' : 'info'"
      :title="dialogTitle"
      :message="dialogMessage"
      :confirm-text="dialogTitle"
      require-reason
      reason-label="原因"
      :submitting="submitting"
      :confirm-disabled="requiresRecheck"
      @confirm="submit"
    >
      <div v-if="mutationError" class="ra-mutation-error" role="alert">
        <p>{{ mutationError }}</p>
        <button v-if="requiresRecheck" type="button" class="mp-link" @click="returnToLatest">返回清单核对最新结果</button>
      </div>
      <section v-if="pendingAction === 'transfer'" class="ra-transfer" aria-label="选择接手老师">
        <label class="ra-field">搜索接手老师
          <input v-model="recipientKeyword" class="ra-input" :disabled="submitting" placeholder="姓名或工号" @keyup.enter="searchRecipients" />
        </label>
        <button type="button" class="mp-link" :disabled="submitting || recipientsLoading" @click="searchRecipients">查询老师</button>
        <p v-if="recipient" role="status">已选：{{ recipient.name }} · {{ recipient.loginName }}</p>
        <p v-if="recipientsLoading" role="status">正在查询老师…</p>
        <div v-else-if="recipientsError" role="alert">{{ recipientsError }} <button type="button" class="mp-link" @click="loadRecipients(recipientPage)">重试查询</button></div>
        <template v-else>
          <div class="ra-recipient-list">
            <label v-for="person in recipients" :key="person.id" class="ra-recipient">
              <input type="radio" name="assignment-recipient" :checked="recipient?.id === person.id" :disabled="submitting" :aria-label="`选择${person.name} ${person.loginName}`" @change="selectRecipient(person)" />
              {{ person.name }} <span>{{ person.loginName }}</span>
            </label>
            <p v-if="!recipients.length">没有符合条件的接手老师，请换个姓名或工号查询。</p>
          </div>
          <div class="ra-pager">
            <span>共 {{ recipientTotal }} 位 · 第 {{ recipientPage }} 页</span>
            <button type="button" class="mp-link" :disabled="submitting || recipientPage <= 1" @click="loadRecipients(recipientPage - 1)">上一页老师</button>
            <button type="button" class="mp-link" :disabled="submitting || recipientPage * 10 >= recipientTotal" @click="loadRecipients(recipientPage + 1)">下一页老师</button>
          </div>
        </template>
      </section>
      <label v-if="pendingAction === 'review'" class="ra-field">
        复核所属学期
        <input v-model.trim="reviewTerm" class="ra-input" placeholder="如 2026-2027-1" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { roleDisplayLabel } from '@/modules/system/utils/permissionLabels'
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const BUCKET_LABELS = {
  EXPIRING_SOON: '即将到期',
  EXPIRED_NOT_RECLAIMED: '过期未回收',
  UNREVIEWED_ACROSS_TERM: '跨学期未复核',
  UNKNOWN_SOURCE: '来源不明',
  HIGH_PRIV_MULTI: '多人持有高权角色'
}
const SOURCE_TYPE_LABELS = { MANUAL: '人工分配', IMPORT: '导入分配', TEMPLATE: '角色模板', BUSINESS: '业务关系自动生成', DELEGATION: '临时委托', UNKNOWN: '来源待确认' }
const IDENTITY_TYPE_LABELS = { TEACHER: '任课教师', COUNSELOR: '辅导员', ADVISOR: '指导教师', DEFENSE_MEMBER: '答辩成员', INTERNSHIP_ADVISOR: '实习指导教师', CLASS_MANAGER: '班级负责人' }
const MODULE_LABELS = { SYSTEM: '系统管理', ACADEMIC_AFFAIRS: '教务中心', STUDENT_AFFAIRS: '学工中心', INTERNSHIP: '实习管理', GRADUATION: '毕业设计', EMPLOYMENT: '就业管理' }

const permissionMatches = (patterns = [], code = '') => (patterns || []).some((pattern) => {
  if (pattern === '*' || pattern === code) return true
  if (pattern.endsWith('.*')) return code.startsWith(pattern.slice(0, -1))
  if (pattern.startsWith('*.')) return code.endsWith(pattern.slice(1))
  return false
})

export default {
  name: 'SystemRoleAssignmentView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      tab: 'members',
      bucket: '',
      rows: [],
      page: 1,
      targetPage: 1,
      pageSize: 50,
      total: 0,
      readSequence: 0,
      summary: {},
      identities: [],
      identityNote: '',
      dialogOpen: false,
      submitting: false,
      mutationError: '',
      requiresRecheck: false,
      pendingAction: '',
      pendingRow: null,
      transferTo: '',
      recipient: null, recipientKeyword: '', appliedRecipientKeyword: '', recipients: [],
      recipientsLoading: false, recipientsError: '', recipientPage: 1, recipientTotal: 0, recipientSequence: 0,
      reviewTerm: '',
      memberColumns: [
        { key: 'user', title: '成员与角色' },
        { key: 'validity', title: '有效期' },
        { key: 'source', title: '来源与原因' },
        { key: 'status', title: '状态' },
        { key: 'ops', title: '操作' }
      ],
      identityColumns: [
        { key: 'identity', title: '身份' },
        { key: 'subject', title: '人' },
        { key: 'scope', title: '覆盖对象' },
        { key: 'owner', title: '归属与权威表' }
      ]
    }
  },
  computed: {
    pageCount() { return Math.max(1, Math.ceil(this.total / this.pageSize)) },
    canManageAssignments() {
      const patterns = this.ctx?.permissionPatterns || []
      return permissionMatches(patterns, 'systemAdmin.user.assign')
        || permissionMatches(patterns, 'systemAdmin.role.config')
    },
    toolbarActions() {
      const actions = [{ key: 'refresh', label: '刷新' }]
      if (this.canManageAssignments) {
        actions.unshift({ key: 'sweep', label: '立即回收到期授权', variant: 'primary' })
      }
      return actions
    },
    bucketList() {
      return Object.keys(BUCKET_LABELS).map((key) => ({
        key, label: BUCKET_LABELS[key], count: this.summary[key] || 0
      }))
    },
    dialogTitle() {
      return { revoke: '回收授权', transfer: '转交工作', review: '记录复核', register: '补登记历史授权' }[this.pendingAction] || '确认'
    },
    dialogMessage() {
      if (!this.pendingRow) return ''
      const who = `${this.pendingRow.realName || this.pendingRow.loginName}（${this.pendingRow.roleCode}）`
      return {
        register: `为 ${who} 补建管理记录，原权限和长期有效状态不变。原始来源仍保留为待确认；登记后可以复核、转交或回收。`,
        revoke: `回收 ${who} 的角色，下一次请求即失效，无需等待重新登录。`,
        transfer: `${who} 将立即失去该角色，接手人按同一有效期获得授权。`,
        review: `确认 ${who} 的长期授权仍然需要保留。`
      }[this.pendingAction] || ''
    }
  },
  created() { this.load() },
  beforeUnmount() { this.readSequence++; this.recipientSequence++ },
  methods: {
    roleLabel: roleDisplayLabel,
    sourceTypeLabel(value) { return SOURCE_TYPE_LABELS[value] || (value ? '来源待确认' : '—') },
    identityTypeLabel(value) { return IDENTITY_TYPE_LABELS[value] || (value ? '其他业务身份' : '—') },
    moduleLabel(value) { return MODULE_LABELS[value] || (value ? '其他业务模块' : '—') },
    sourceText(value) { return /[\u3400-\u9fff]/.test(String(value || '')) ? value : (value ? '业务关系自动生成' : '—') },
    statusLabel(status) {
      return { ACTIVE: '生效中', EXPIRED: '已过期', REVOKED: '已撤销' }[status] || '状态待确认'
    },
    statusTone(s) {
      return { ACTIVE: 'success', EXPIRED: 'warning', REVOKED: 'default' }[s] || 'default'
    },
    onAction(key) {
      if (key === 'refresh') return this.load()
      if (key === 'sweep') return this.sweep()
    },
    switchTab(tab) {
      if (this.tab === tab || this.submitting) return
      this.tab = tab
      this.page = 1
      this.load()
    },
    pickBucket(key) {
      if (this.submitting) return
      this.bucket = this.bucket === key ? '' : key
      this.page = 1
      this.load()
    },
    changePage(page) {
      if (this.loading || this.submitting || !Number.isInteger(page) || page < 1 || page > this.pageCount || page === this.page) return
      this.page = page
      return this.load()
    },
    ask(action, row) {
      if (this.submitting) return
      if (['transfer', 'revoke', 'register'].includes(action) && !this.canManageAssignments) {
        return toast.error('当前角色只有查看权限，不能转交或回收授权')
      }
      this.mutationError = ''; this.requiresRecheck = false
      this.pendingAction = action
      this.pendingRow = row
      this.transferTo = ''; this.recipient = null; this.recipientKeyword = ''; this.appliedRecipientKeyword = ''
      this.recipients = []; this.recipientsError = ''; this.recipientTotal = 0; this.recipientPage = 1; this.recipientSequence++
      this.reviewTerm = ''
      this.dialogOpen = true
      if (action === 'transfer') this.loadRecipients(1)
    },
    async sweep() {
      if (!this.canManageAssignments) return toast.error('当前角色无到期回收权限')
      const res = await systemApi.sweepExpiredAssignments()
      if (res.code === 0) {
        toast.success(`已回收 ${res.data.count} 个账号的到期授权`)
        await this.load()
      } else toast.error(res.message)
    },
    async searchRecipients() {
      if (this.submitting) return
      this.recipient = null; this.transferTo = ''
      this.appliedRecipientKeyword = this.recipientKeyword.trim()
      await this.loadRecipients(1)
    },
    selectRecipient(person) {
      if (this.submitting || this.recipientsLoading || this.recipientsError || !this.recipients.some(row => row.id === person.id)) return
      this.recipient = person; this.transferTo = String(person.id); this.mutationError = ''
    },
    async loadRecipients(page) {
      if (this.submitting) return
      const sequence = ++this.recipientSequence
      this.recipientsLoading = true; this.recipientsError = ''; this.recipients = []; this.recipientPage = page
      try {
        if (!this.pendingRow?.roleId) throw new Error('未取得角色信息，请返回清单刷新后重试。')
        const res = await schoolIamApi.roleMemberCandidates(this.pendingRow.roleId, { keyword: this.appliedRecipientKeyword, page, pageSize: 10 })
        if (sequence !== this.recipientSequence || !this.dialogOpen) return
        if (res.code !== 0) throw new Error(res.message || '老师查询失败')
        if (!Array.isArray(res.data?.items) || !Number.isInteger(res.data.total)) throw new Error('老师清单不完整，请重试。')
        this.recipients = res.data.items.filter(person => person.status === 'ACTIVE' && String(person.id) !== String(this.pendingRow.userId))
        this.recipientTotal = res.data.total
      } catch (error) {
        if (sequence === this.recipientSequence) this.recipientsError = error.message || '老师查询失败'
      } finally {
        if (sequence === this.recipientSequence) this.recipientsLoading = false
      }
    },
    setDialogVisible(value) {
      if (!this.submitting) this.dialogOpen = value
    },
    async returnToLatest() {
      if (this.submitting) return
      this.dialogOpen = false
      await this.load()
    },
    async submit({ reason }) {
      if (!this.pendingRow || this.submitting || this.requiresRecheck) return
      if (['transfer', 'revoke', 'register'].includes(this.pendingAction) && !this.canManageAssignments) {
        this.mutationError = '当前角色无角色授权写权限，请联系学校管理员。'
        return
      }
      this.mutationError = ''
      if (this.pendingAction === 'transfer' && (!this.recipient || this.recipientsLoading || this.recipientsError || this.transferTo !== String(this.recipient.id))) {
        this.mutationError = '请先从查询结果中选择一位接手老师。'
        return
      }
      const id = this.pendingRow.assignmentId
      this.submitting = true
      try {
        let res
        if (this.pendingAction === 'register') {
          res = await systemApi.registerLegacyRoleAssignment(this.pendingRow.userRoleId, { reason, expectedVersion: this.pendingRow.version })
        } else if (this.pendingAction === 'revoke') {
          res = await systemApi.revokeRoleAssignment(id, { reason, expectedVersion: this.pendingRow.version })
        } else if (this.pendingAction === 'transfer') {
          res = await systemApi.transferRoleAssignment(id, { toUserId: this.transferTo, reason, expectedVersion: this.pendingRow.version })
        } else {
          res = await systemApi.reviewRoleAssignment(id, { term: this.reviewTerm, reason })
        }
        if (res?.code === 0) {
          toast.success(`${this.dialogTitle}已完成`)
          this.dialogOpen = false
          this.pendingRow = null
          await this.load()
        } else {
          this.requiresRecheck = res?.bizCode !== 'VALIDATION_ERROR'
          this.mutationError = res?.bizCode === 'DATA_CONFLICT'
            ? '这条授权已被其他操作更新。已保留填写内容，请核对最新结果后重新办理。'
            : `${res?.message || '未能确认操作结果'}${this.requiresRecheck ? '。请先核对最新结果，避免重复办理。' : ''}`
        }
      } catch (error) {
        this.requiresRecheck = true
        this.mutationError = `${error.message || '请求中断'}。未能确认操作结果，已保留填写内容，请先核对最新结果。`
      } finally {
        this.submitting = false
      }
    },
    async load() {
      const sequence = ++this.readSequence
      this.loading = true
      this.error = ''
      this.rows = []; this.identities = []
      try {
        if (this.tab === 'members') {
          const res = await systemApi.listRoleAssignments({ bucket: this.bucket, page: this.page, pageSize: this.pageSize })
          if (sequence !== this.readSequence) return
          if (res.code !== 0) throw new Error(res.message || '角色成员加载失败')
          if (!Array.isArray(res.data?.list) || !Number.isInteger(res.data.total) || res.data.total < 0) throw new Error('角色成员分页信息不完整，请重试')
          this.rows = res.data.list
          this.total = res.data.total
          this.targetPage = this.page
          this.summary = res.data.summary || {}
        } else {
          const res = await systemApi.listBusinessIdentities()
          if (sequence !== this.readSequence) return
          if (res.code !== 0) throw new Error(res.message || '业务身份加载失败')
          this.identities = res.data.list || []
          this.identityNote = res.data.note || ''
        }
      } catch (error) {
        if (sequence === this.readSequence) this.error = error.message || '清单读取失败，请重试'
      } finally {
        if (sequence === this.readSequence) this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ra-tabs {
  display: flex;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-light);
  padding-bottom: var(--space-2);
}
.ra-pager { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: var(--space-3); }
.ra-pager button:disabled { opacity: .45; cursor: not-allowed; }
.ra-page-input { width: 5rem; padding: 4px 6px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); }
.ra-tabs .is-active { color: var(--primary-600); font-weight: var(--font-weight-semibold); }
.ra-buckets { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.ra-bucket {
  min-width: 132px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-container);
  cursor: pointer;
  text-align: left;
}
.ra-bucket.is-active { border-color: var(--color-primary); }
.ra-bucket__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.ra-bucket__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.ra-mutation-error { padding: 12px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); color: var(--danger-600, #b42318); }
.ra-recipient-list { max-height: 220px; overflow-y: auto; margin: 8px 0; }
.ra-recipient { display: flex; align-items: center; gap: 8px; padding: 8px; border-bottom: 1px solid var(--border-light); }
.ra-recipient span { color: var(--text-secondary); }
.ra-field { display: block; margin: var(--space-2) 0; }
.ra-input {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 6px 10px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
}
</style>
