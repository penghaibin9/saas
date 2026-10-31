<template>
  <ModulePageShell title="实习请假审批配置" :watermark="false">
    <NoPermissionState v-if="!canView" title="当前身份不能查看请假审批配置" />
    <template v-else>
      <p class="policy-hint">按当前实习批次设置审批责任人。发布后的新申请使用新版本，在办申请保持提交时的审批顺序。</p>
      <LoadingState v-if="loading" text="正在读取当前审批规则…" />
      <ErrorState v-else-if="error && !policy" :description="error" @retry="load" />
      <EmptyState v-else-if="!policy" title="请先选择实习批次" description="选择顶部批次后查看和配置请假审批。" />
      <form v-else class="policy-form" @submit.prevent="publish">
        <p>当前规则：{{ versionLabel }}<span v-if="!canManage"> · 当前身份仅可查看</span></p>
        <p v-if="error" class="policy-error" role="alert">{{ error }}</p>
        <p v-if="receipt" class="policy-receipt" role="status">{{ receipt }}</p>
        <fieldset :disabled="busy || !canManage">
          <legend>审批顺序</legend>
          <ol class="policy-nodes">
            <li v-for="(node, index) in nodes" :key="index">
              <h2>第 {{ index + 1 }} 级</h2>
              <div class="policy-fields">
                <label :for="`leave-policy-type-${index}`">责任岗位
                  <select :id="`leave-policy-type-${index}`" v-model="node.type" @change="changeType(node)">
                    <option v-for="(label, key) in types" :key="key" :value="key">{{ label }}</option>
                  </select>
                </label>
                <label :for="`leave-policy-role-${index}`">工作身份
                  <select :id="`leave-policy-role-${index}`" v-model="node.roleCode" required @change="node.userId = ''">
                    <option value="">请选择工作身份</option>
                    <option v-for="role in rolesFor(node)" :key="role.code" :value="role.code">{{ role.name }}</option>
                  </select>
                </label>
                <label v-if="node.type === 'SCHOOL'" :for="`leave-policy-person-${index}`">校级承办人
                  <select :id="`leave-policy-person-${index}`" v-model="node.userId">
                    <option value="">按责任关系确定</option>
                    <option v-for="person in assigneesFor(node)" :key="person.id" :value="String(person.id)">{{ person.name }}</option>
                  </select>
                </label>
              </div>
              <button v-if="nodes.length > 1" type="button" class="mp-btn" @click="nodes.splice(index, 1)">移除这一级</button>
            </li>
          </ol>
          <div class="policy-actions">
            <button v-if="nodes.length < 3" type="button" class="mp-btn" @click="addNode">增加一级审批</button>
            <button type="button" class="mp-btn" @click="check">{{ checking ? '正在核对责任人…' : '预览实际责任人' }}</button>
          </div>
        </fieldset>
        <section v-if="preview" class="policy-preview" aria-live="polite">
          <h2>责任人核对</h2>
          <p>共 {{ preview.total }} 位学生，责任缺口 {{ preview.errorCount }} 位。下表最多展示前 100 人。</p>
          <div class="policy-table-wrap"><table><thead><tr><th>学号</th><th>姓名</th><th>逐级承办人</th></tr></thead><tbody>
            <tr v-for="(row, index) in preview.items" :key="`${row.studentNo}-${index}`"><td>{{ row.studentNo }}</td><td>{{ row.studentName }}</td><td>{{ row.steps?.map(step => `${step.label}：${step.name}`).join(' → ') || row.error }}</td></tr>
          </tbody></table></div>
        </section>
        <section v-if="conflict" class="policy-conflict" role="alert">
          <h2>规则已被其他人更新</h2>
          <p>你的审批步骤和发布原因已保留。请核对最新规则后，重新预览责任人再发布。</p>
          <p>最新规则：{{ describeNodes(conflict.nodes) }}</p>
          <button type="button" class="mp-btn" :disabled="busy" @click="acknowledgeConflict">已核对，保留草稿并重新预览</button>
        </section>
        <template v-if="canManage">
          <label class="policy-reason" for="leave-policy-reason">发布原因
            <textarea id="leave-policy-reason" v-model="reason" :disabled="busy" required minlength="5" maxlength="500" rows="3" placeholder="请说明本次调整原因，至少 5 个字" />
          </label>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="busy || !!conflict || !preview?.canPublish || reason.trim().length < 5">{{ saving ? '正在发布…' : '发布新版本' }}</button>
        </template>
      </form>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import NoPermissionState from '../components/NoPermissionState.vue'
import { leavePolicyApi } from '../api/leave-policy.api'
import { canCode } from '../composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { normalizeUiError } from '@/utils/presentationSafety'

const TYPES = { GUIDE: '指导教师', COLLEGE: '院系责任人', SCHOOL: '校级责任人' }
const BASES = { GUIDE: ['INTERN_MENTOR', 'INTERNSHIP_MENTOR', 'INTERN_ADVISOR'], COLLEGE: ['COLLEGE_ADMIN'], SCHOOL: ['SCHOOL_ADMIN'] }
export default {
  name: 'InternshipLeavePolicyView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, NoPermissionState },
  props: { ctx: { type: Object, required: true } },
  data: () => ({ types: TYPES, options: { roles: [], assignees: [] }, policy: null, nodes: [], preview: null, reason: '', loading: false, checking: false, saving: false, conflict: null, error: '', receipt: '', sequence: 0, previewSequence: 0 }),
  computed: {
    batchStore() { return useInternshipBatchStore() },
    batchId() { return String(this.batchStore.selectedBatchId || '') },
    canView() { return canCode(this.ctx, 'internship.leave.policy.view') },
    canManage() { return canCode(this.ctx, 'internship.leave.policy.manage') },
    busy() { return this.loading || this.checking || this.saving },
    versionLabel() { return /^\d+$/.test(String(this.policy?.version)) ? `第 ${this.policy.version} 版` : '默认一级审批' }
  },
  watch: {
    batchId: { immediate: true, handler() { this.load() } },
    'ctx.ctxKey'() { this.load() },
    nodes: { deep: true, flush: 'sync', handler() { this.invalidatePreview() } }
  },
  beforeUnmount() { this.sequence++; this.previewSequence++ },
  methods: {
    rolesFor(node) { return (this.options.roles || []).filter(role => BASES[node.type]?.includes(role.baseRole || role.baseRoleCode || role.code)) },
    assigneesFor(node) { return (this.options.assignees || []).filter(person => person.roleCodes?.includes(node.roleCode)) },
    invalidatePreview() { this.previewSequence++; this.preview = null; this.checking = false },
    changeType(node) { node.roleCode = this.rolesFor(node)[0]?.code || ''; node.userId = '' },
    addNode() {
      const type = Object.keys(TYPES).find(key => !this.nodes.some(node => node.type === key))
      if (!type) return
      const node = { type, roleCode: '', userId: '' }; this.changeType(node); this.nodes.push(node)
      this.nodes.sort((a, b) => Object.keys(TYPES).indexOf(a.type) - Object.keys(TYPES).indexOf(b.type))
    },
    describeNodes(nodes) { return (nodes || []).map(node => `${TYPES[node.type] || '责任岗位待确认'} · ${(this.options.roles || []).find(role => role.code === node.roleCode)?.name || '工作身份待确认'}`).join(' → ') || '暂无可读规则' },
    async load() {
      const run = ++this.sequence, batch = this.batchId
      this.invalidatePreview(); this.policy = null; this.nodes = []; this.reason = ''; this.conflict = null; this.error = ''; this.receipt = ''; this.loading = false; this.saving = false
      if (!batch || !this.canView) return
      this.loading = true
      try {
        const [options, policy] = await Promise.all([leavePolicyApi.options(), leavePolicyApi.read(batch)])
        if (run !== this.sequence) return
        this.options = options; this.policy = policy; this.nodes = (policy.nodes || []).map(node => ({ ...node }))
      } catch (error) { if (run === this.sequence) this.error = normalizeUiError(error).userMessage }
      finally { if (run === this.sequence) this.loading = false }
    },
    async check() {
      if (this.busy || !this.policy || !this.canManage || this.conflict) return
      const run = this.sequence, ticket = ++this.previewSequence
      this.checking = true; this.error = ''; this.preview = null
      try {
        const result = await leavePolicyApi.preview(this.batchId, this.nodes.map(node => ({ ...node })))
        if (run === this.sequence && ticket === this.previewSequence) this.preview = result
      } catch (error) { if (run === this.sequence && ticket === this.previewSequence) this.error = normalizeUiError(error).userMessage }
      finally { if (ticket === this.previewSequence) this.checking = false }
    },
    acknowledgeConflict() { this.policy = { ...this.policy, ...this.conflict }; this.conflict = null; this.error = ''; this.invalidatePreview() },
    async publish() {
      if (this.busy || this.conflict || !this.preview?.canPublish || !this.policy || !this.canManage || this.reason.trim().length < 5) return
      const run = this.sequence, batch = this.batchId
      this.saving = true; this.error = ''; this.receipt = ''
      try {
        const result = await leavePolicyApi.publish(batch, { nodes: this.nodes.map(node => ({ ...node })), expectedVersion: this.policy.expectedVersion, reason: this.reason.trim() })
        if (run !== this.sequence) return
        this.policy = { ...this.policy, ...result }; this.receipt = `新版本已发布，已核对 ${result.checkedStudents} 位学生的责任人。`; this.reason = ''; this.invalidatePreview()
      } catch (error) {
        if (run !== this.sequence) return
        this.error = normalizeUiError(error).userMessage; this.invalidatePreview()
        if (error.httpStatus === 409 || error.bizCode === 'DATA_CONFLICT' || error.code === 409001) {
          try { const current = await leavePolicyApi.read(batch); if (run === this.sequence) this.conflict = current }
          catch { if (run === this.sequence) this.error = '规则发生冲突，最新规则暂未读取成功；草稿已保留，请稍后重试。' }
        }
      } finally { if (run === this.sequence) this.saving = false }
    }
  }
}
</script>

<style scoped>
.policy-form{max-width:1100px}.policy-hint,.policy-form>p{color:var(--t2);line-height:1.7}.policy-form fieldset{border:0;padding:0;margin:0}.policy-form legend{font-weight:600}.policy-nodes{padding-left:24px}.policy-nodes li{padding:16px;border:1px solid var(--line);border-radius:10px;margin:12px 0}.policy-form h2{font-size:16px;margin:0 0 12px}.policy-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:12px}.policy-form label{display:flex;flex-direction:column;gap:8px;font-size:14px}.policy-form select,.policy-form textarea{width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:6px;padding:10px;font:inherit;background:var(--bg-card,#fff);color:inherit}.policy-actions{display:flex;gap:12px;flex-wrap:wrap}.policy-preview,.policy-conflict{padding:16px;border:1px solid var(--line);border-radius:10px;margin:20px 0}.policy-table-wrap{overflow:auto}.policy-preview table{width:100%;border-collapse:collapse;text-align:left}.policy-preview th,.policy-preview td{padding:10px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.policy-reason{margin:20px 0}.policy-error,.policy-conflict{color:#9f341b;background:#fff4ed}.policy-receipt{color:#17643a;background:#edf8f1;padding:12px}.policy-form button{min-height:42px}@media(max-width:800px){.policy-fields{grid-template-columns:1fr}.policy-nodes{padding-left:20px}.policy-nodes li{padding:12px}.policy-preview{padding:12px}.policy-preview th,.policy-preview td{padding:8px;font-size:13px}}
</style>
