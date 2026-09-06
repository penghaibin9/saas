<template>
  <div class="sw-stack" data-testid="role-members-panel">
    <section v-if="receipt" class="sw-alert" :class="uncertain ? 'sw-alert--warning' : 'sw-alert--success'" role="status">{{ receipt }}</section>
    <template v-if="tab === 'audit'">
      <div class="sw-between"><h3>角色操作留痕</h3><button type="button" class="sw-btn" :disabled="audit.loading || !canAudit" @click="loadAudit(1)">刷新记录</button></div>
      <p v-if="!canAudit" class="sw-alert">当前身份没有审计查看权限，成员管理不受影响。</p>
      <template v-else>
        <div v-if="audit.loading" class="sw-state" role="status">正在读取审计记录…</div>
        <div v-else-if="audit.error" class="sw-alert sw-alert--error" role="alert">{{ audit.error }}<button type="button" class="sw-btn" @click="loadAudit(audit.page)">重试</button></div>
        <div v-else class="sw-table-wrap"><table class="sw-table"><thead><tr><th>时间 / 操作者</th><th>动作与结果</th><th>原因 / 请求编号</th></tr></thead><tbody>
          <tr v-for="row in audit.rows" :key="row.id"><td>{{ row.createdAt || '未取得' }}<small>{{ row.operatorName || row.operatorId || '未取得' }}</small></td>
            <td>{{ auditLabel(row).displayAction }}<small>{{ auditLabel(row).displayResult }}</small></td>
            <td>{{ row.detail?.reason || row.detail?.summary || '—' }}<small class="sw-code">{{ row.traceId || '无请求编号' }}</small></td></tr>
          <tr v-if="!audit.rows.length"><td colspan="3">当前查询没有审计记录。</td></tr>
        </tbody></table></div>
        <div v-if="!audit.loading && !audit.error" class="sw-pager"><span>共 {{ audit.total }} 条 · 第 {{ audit.page }} 页</span><div class="sw-row">
          <button type="button" class="sw-btn" :disabled="audit.page <= 1" @click="loadAudit(audit.page - 1)">上一页</button>
          <button type="button" class="sw-btn" :disabled="audit.page * audit.pageSize >= audit.total" @click="loadAudit(audit.page + 1)">下一页</button>
        </div></div>
      </template>
    </template>
    <template v-else>
      <div class="sw-between"><div><h3>{{ adding ? '选择要添加的老师' : '角色成员' }}</h3><p class="sw-muted">{{ adding ? '只添加选中的成员，不替换老师已有的其他角色。' : '分页读取全部成员，不把角色详情中的预览当成总数。' }}</p></div>
        <div class="sw-row"><button type="button" class="sw-btn" :disabled="busy" @click="loadMembers(1)">刷新成员</button>
          <button v-if="canAdd && !adding" type="button" class="sw-btn sw-btn--primary" :disabled="busy || locked" data-testid="A022-open" @click="openAdd">＋ 添加成员</button></div>
      </div>
      <p class="sw-alert">角色授权与岗位范围分别管理。添加后请继续核对任职、负责班级或业务指导关系。</p>
      <template v-if="adding">
        <div class="sw-row">
          <label class="sw-field" style="flex:1">搜索老师<input v-model="candidateKeyword" class="sw-input" placeholder="姓名或工号" aria-label="搜索候选老师" @keyup.enter="searchCandidates" /></label>
          <button type="button" class="sw-btn" :disabled="busy" @click="searchCandidates">查询</button>
        </div>
        <div class="sw-selected" data-testid="selected-members">已选 {{ selected.length }} 位老师（最多 100 位）
          <span v-for="row in selected" :key="row.id" class="sw-tag sw-tag--blue">{{ row.name }} / {{ row.loginName }}</span>
          <button v-if="selected.length" type="button" class="sw-link" :disabled="busy" @click="selected = []">清空选择</button>
        </div>
        <div v-if="candidates.loading" class="sw-state" role="status">正在查询可添加成员…</div>
        <div v-else-if="candidates.error" class="sw-alert sw-alert--error" role="alert">{{ candidates.error }}<button type="button" class="sw-btn" @click="loadCandidates(candidates.page)">重试查询</button></div>
        <div v-else class="sw-table-wrap"><table class="sw-table"><thead><tr><th>选择</th><th>老师 / 工号</th><th>账号状态</th></tr></thead><tbody>
          <tr v-for="row in candidates.rows" :key="row.id"><td><input class="sw-check" type="checkbox" :aria-label="`选择${row.name}`" :checked="selected.some(item => item.id === row.id)"
            :disabled="busy || locked || !canAdd || row.status !== 'ACTIVE' || row.userType === 'STUDENT' || (selected.length >= 100 && !selected.some(item => item.id === row.id))" @change="choose(row, $event.target.checked)" /></td>
            <td><b>{{ row.name }}</b><small>{{ row.loginName }}</small></td><td>{{ statusLabel(row.status) }}</td></tr>
          <tr v-if="!candidates.rows.length"><td colspan="3">没有可添加的老师；已排除当前成员及不可用账号。</td></tr>
        </tbody></table></div>
        <div v-if="!candidates.loading && !candidates.error" class="sw-pager"><span>共 {{ candidates.total }} 位候选 · 第 {{ candidates.page }} 页</span><div class="sw-row">
          <button type="button" class="sw-btn" :disabled="busy || candidates.page <= 1" @click="loadCandidates(candidates.page - 1)">上一页</button>
          <button type="button" class="sw-btn" :disabled="busy || candidates.page * candidates.pageSize >= candidates.total" @click="loadCandidates(candidates.page + 1)">下一页</button>
        </div></div>
        <div class="sw-form"><label class="sw-field">授权原因<textarea v-model="reason" class="sw-input" maxlength="500" :disabled="busy" placeholder="填写职责安排原因，至少 5 个字" aria-label="成员授权原因" /></label>
          <label class="sw-field">到期日期（可选）<input v-model="expiresAt" type="date" class="sw-input" :disabled="busy" aria-label="成员到期日期" /><small class="sw-muted">沿用学校现有日期口径，留空为长期授权。</small></label></div>
        <p v-if="validationError" class="sw-alert sw-alert--error" role="alert">{{ validationError }}</p>
        <div class="sw-savebar"><button type="button" class="sw-btn" :disabled="busy" @click="cancelAdd">返回成员清单</button>
          <button type="button" class="sw-btn sw-btn--primary" data-testid="A022-submit" :disabled="!canSubmit" @click="submit">{{ busy ? '正在添加…' : `确认添加 ${selected.length} 位老师` }}</button></div>
        <div v-if="uncertain" class="sw-alert sw-alert--warning"><p>没有自动重复添加。先重新查询成员与候选清单，再核对尚未处理的人。</p><button type="button" class="sw-btn" @click="reconcile">重新读取并核对</button></div>
      </template>
      <template v-else>
        <div v-if="members.loading" class="sw-state" role="status">正在读取成员…</div>
        <div v-else-if="members.error" class="sw-alert sw-alert--error" role="alert">{{ members.error }}<button type="button" class="sw-btn" @click="loadMembers(members.page)">重试</button></div>
        <div v-else class="sw-table-wrap"><table class="sw-table"><thead><tr><th>成员 / 工号</th><th>账号状态</th><th>下一步</th></tr></thead><tbody>
          <tr v-for="row in members.rows" :key="row.id"><td><b>{{ row.name }}</b><small>{{ row.loginName }}</small></td><td><span class="sw-tag" :class="row.status === 'ACTIVE' ? 'sw-tag--green' : ''">{{ statusLabel(row.status) }}</span></td>
            <td><button type="button" class="sw-link" @click="inspect(row)">访问排查</button></td></tr>
          <tr v-if="!members.rows.length"><td colspan="3">此角色当前没有成员。</td></tr>
        </tbody></table></div>
        <div v-if="!members.loading && !members.error" class="sw-pager"><span data-testid="member-total">共 {{ members.total }} 位成员 · 每页 {{ members.pageSize }} 位 · 第 {{ members.page }} 页</span><div class="sw-row">
          <button type="button" class="sw-btn" :disabled="members.page <= 1" @click="loadMembers(members.page - 1)">上一页</button>
          <button type="button" class="sw-btn" :disabled="members.page * members.pageSize >= members.total" @click="loadMembers(members.page + 1)">下一页</button>
        </div></div>
        <div class="sw-row"><button type="button" class="sw-link" @click="$router.push('/admin/system/role-assignments')">核对有效期、来源与业务身份 →</button></div>
      </template>
    </template>
  </div>
</template>

<script>
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import { presentAuditRecord } from '@/utils/presentationSafety'
import * as wc from '@/modules/system/utils/workspaceContract'
const emptyPage = size => ({ rows: [], total: 0, page: 1, pageSize: size, loading: false, error: '' })
export default {
  name: 'RoleMembersPanel',
  props: { ctx: { type: Object, required: true }, roleId: { type: String, required: true }, tab: { type: String, default: 'members' }, locked: { type: Boolean, default: false } },
  emits: ['dirty', 'busy', 'count'],
  data() { return { fence: null, members: emptyPage(50), candidates: emptyPage(20), audit: emptyPage(50), adding: false, selected: [], candidateKeyword: '', appliedKeyword: '', reason: '', expiresAt: '', busy: false, receipt: '', uncertain: false, validationError: '' } },
  computed: {
    canAdd() { return wc.actionAllowed(this.ctx, 'assignRole') },
    canAudit() { return wc.actionAllowed(this.ctx, 'viewOperationLogs') },
    dirty() { return this.adding && !!(this.selected.length || this.reason || this.expiresAt) },
    canSubmit() { return this.canAdd && !this.locked && !this.busy && !this.uncertain && !this.candidates.loading && !this.candidates.error && this.selected.length > 0 && this.selected.length <= 100 },
    contextKey() { return wc.contextFingerprint(this.ctx) }
  },
  watch: {
    dirty(value) { this.$emit('dirty', value) },
    tab(value) { if (value === 'audit' && !this.audit.loading && !this.audit.rows.length) this.loadAudit(1) },
    contextKey() { this.resetContext() },
    roleId() { this.resetContext() }
  },
  created() { this.fence = wc.createRequestFence(); this.loadMembers(1); if (this.tab === 'audit') this.loadAudit(1) },
  beforeUnmount() { this.fence.invalidate() },
  methods: {
    auditLabel: presentAuditRecord,
    statusLabel(value) { return { ACTIVE: '启用中', DISABLED: '已停用', LOCKED: '已锁定', EXPIRED: '已过期' }[value] || value || '未取得' },
    resetContext() {
      this.fence.invalidate(); this.members = emptyPage(50); this.candidates = emptyPage(20); this.audit = emptyPage(50)
      this.selected = []; this.adding = false; this.reason = ''; this.expiresAt = ''; this.receipt = ''; this.busy = false; this.uncertain = false
      this.$emit('busy', false); this.$emit('dirty', false); this.loadMembers(1)
      if (this.tab === 'audit') this.loadAudit(1)
    },
    async readPage(target, page, fn) {
      const current = this.fence.start(target)
      this[target].loading = true; this[target].error = ''
      try {
        const result = wc.paged(wc.unwrap(await fn()))
        if (!current()) return false
        this[target] = { ...result, loading: false, error: '' }
        if (target === 'members') this.$emit('count', result.total)
        return true
      } catch (error) {
        if (current()) { this[target].loading = false; this[target].error = error.message || '清单读取失败'; this[target].page = page }
        return false
      }
    },
    loadMembers(page) { return this.readPage('members', page, () => schoolIamApi.roleMembers(this.roleId, page, 50)) },
    loadAudit(page) { if (this.canAudit) return this.readPage('audit', page, () => schoolIamApi.roleAudit(this.roleId, page, 50)) },
    loadCandidates(page) { if (this.canAdd) return this.readPage('candidates', page, () => schoolIamApi.roleMemberCandidates(this.roleId, { keyword: this.appliedKeyword, page, pageSize: 20 })) },
    openAdd() { if (!this.canAdd || this.busy || this.locked) return; this.adding = true; this.loadCandidates(1) },
    searchCandidates() {
      if (this.busy) return
      if (this.selected.length && !window.confirm('更换查询条件会清空已选老师，是否继续？')) return
      this.selected = []; this.appliedKeyword = this.candidateKeyword.trim(); this.loadCandidates(1)
    },
    choose(row, checked) {
      if (!this.canAdd || this.busy || this.locked || row.status !== 'ACTIVE' || row.userType === 'STUDENT') return
      this.selected = this.selected.filter(item => item.id !== row.id)
      if (checked && this.selected.length < 100) this.selected.push({ id: row.id, name: row.name, loginName: row.loginName })
    },
    cancelAdd() {
      if (this.busy || (this.dirty && !window.confirm('放弃尚未提交的成员选择与原因？'))) return
      this.adding = false; this.selected = []; this.reason = ''; this.expiresAt = ''; this.validationError = ''; this.uncertain = false
    },
    inspect(row) { this.$router.push({ path: '/admin/system/iam', query: { surface: 'access', userId: String(row.id) }, hash: '#access-explain' }) },
    async reconcile() {
      if (this.busy) return
      const results = await Promise.all([this.loadMembers(1), this.loadCandidates(1)])
      if (results.every(Boolean)) {
        // Do not infer absence from the first members page. Clear the intent and require reselection.
        this.selected = []; this.uncertain = false; this.receipt = '已重新读取。请从最新候选清单重新选择仍需要添加的老师。'
      }
    },
    async submit() {
      if (!this.canSubmit) return
      this.validationError = ''
      if (this.reason.trim().length < 5) { this.validationError = '授权原因不少于 5 个字'; return }
      if (this.expiresAt) {
        const date = new Date(`${this.expiresAt}T23:59:59`)
        if (!/^\d{4}-\d{2}-\d{2}$/.test(this.expiresAt) || Number.isNaN(date.getTime()) || date.getTime() <= Date.now()) {
          this.validationError = '请填写有效且尚未到期的日期'; return
        }
      }
      const current = this.fence.start('write')
      const payload = { userIds: [...new Set(this.selected.map(row => String(row.id)))], reason: this.reason.trim(), effectiveAt: null, expiresAt: this.expiresAt || null, sourceType: 'MANUAL' }
      this.busy = true; this.$emit('busy', true)
      try {
        const result = wc.unwrap(await schoolIamApi.batchAddRoleMembers(this.roleId, payload))
        if (!current()) return
        if (!Number.isInteger(result?.addedCount) || !Number.isInteger(result?.skippedCount)) throw new Error('成员回执不完整，请重新读取清单核对')
        this.receipt = `已添加 ${result.addedCount} 位老师，跳过 ${result.skippedCount} 位已有成员。请继续核对岗位数据范围。`
        this.selected = []; this.reason = ''; this.expiresAt = ''; this.adding = false; this.uncertain = false
        await this.loadMembers(1)
      } catch (error) {
        if (current()) { this.uncertain = true; this.receipt = `未确认本次添加结果：${error.message || '请求异常'}` }
      } finally { if (current()) { this.busy = false; this.$emit('busy', false) } }
    }
  }
}
</script>
