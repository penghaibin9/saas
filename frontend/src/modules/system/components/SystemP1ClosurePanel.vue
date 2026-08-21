<template>
  <section v-if="mode" class="p1-panel">
    <header class="p1-panel__head">
      <div>
        <strong>{{ title }}</strong>
        <p>{{ subtitle }}</p>
      </div>
      <AppButton variant="ghost" :loading="loading" @click="load">刷新</AppButton>
    </header>

    <div v-if="error" class="p1-error">{{ error }}</div>

    <template v-if="mode === 'role'">
      <div class="p1-form p1-form--role">
        <label><span>账号 userId</span><input v-model.trim="roleForm.userId" inputmode="numeric" placeholder="数字主键" /></label>
        <label><span>角色</span>
          <select v-model="roleForm.roleCode">
            <option value="">请选择角色</option>
            <option v-for="role in roles" :key="role.id || role.code" :value="role.code">{{ role.name }}（{{ role.code }}）</option>
          </select>
        </label>
        <label><span>生效时间</span><input v-model="roleForm.effectiveAt" type="datetime-local" /></label>
        <label><span>到期时间</span><input v-model="roleForm.expiresAt" type="datetime-local" /></label>
        <label class="p1-wide"><span>授权原因</span><input v-model.trim="roleForm.reason" placeholder="至少 5 个字；写入授权来源与审计" /></label>
        <div class="p1-actions"><AppButton variant="primary" :loading="saving" @click="grantRole">新增正式角色授权</AppButton></div>
      </div>
      <p class="p1-note">新增后的授权会出现在下方“固定角色成员”台账，可继续复核、转交、回收和自动到期回收。</p>
    </template>

    <template v-else-if="mode === 'config'">
      <div v-if="!configOverrides.length && !loading" class="p1-empty">当前 SECURITY 域没有可撤销的学校层覆盖，全部继承平台/套餐/历史配置。</div>
      <div v-else class="p1-table-wrap">
        <table>
          <thead><tr><th>配置</th><th>当前/计划值</th><th>覆盖链</th><th>当前生效时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in configOverrides" :key="item.configKey">
              <td><b>{{ item.configName }}</b><small>{{ item.configKey }}</small></td>
              <td>{{ displayValue(item.value) }}<small v-if="item.isScheduledOnly">仅有未来计划覆盖</small></td>
              <td>{{ item.overrideCount }} 条学校覆盖<small v-if="item.scheduledCount">其中 {{ item.scheduledCount }} 条待生效</small></td>
              <td>{{ fmt(item.effectiveAt) }}</td>
              <td><AppButton variant="secondary" @click="selectOverride(item)">恢复继承</AppButton></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="selectedOverride" class="p1-confirm">
        <div>
          <b>撤销 {{ selectedOverride.configName }} 的全部学校层覆盖？</b>
          <p>后端会锁住并校验 {{ selectedOverride.overrideCount }} 条当前/计划覆盖的完整链与每条 version，单事务撤销并写高危审计；任何并发变化都会整笔拒绝，不会出现撤了一半。</p>
        </div>
        <input v-model.trim="overrideReason" placeholder="撤销原因，至少 5 个字" />
        <div class="p1-actions">
          <AppButton variant="ghost" @click="selectedOverride = null">取消</AppButton>
          <AppButton variant="primary" :loading="saving" @click="revokeOverride">确认恢复继承</AppButton>
        </div>
      </div>
    </template>

    <template v-else-if="mode === 'identity'">
      <div class="p1-inline-search">
        <input v-model.trim="identityUserId" inputmode="numeric" placeholder="输入账号 userId 查看稳定主体解析" @keyup.enter="resolveIdentity" />
        <AppButton variant="primary" :loading="loading" @click="resolveIdentity">解析身份</AppButton>
      </div>
      <div v-if="identity" class="p1-identity">
        <div class="p1-metrics">
          <article><span>账号</span><strong>{{ identity.realName || identity.loginName }}</strong><small>userId {{ identity.userId }}</small></article>
          <article><span>主体来源</span><strong>{{ identity.identitySource }}</strong><small>{{ identity.accountType }}</small></article>
          <article><span>学籍主体</span><strong>{{ identity.studentId || '未绑定' }}</strong><small>{{ identity.studentNo || '—' }}</small></article>
          <article><span>绑定记录</span><strong>{{ identity.binding?.linkId || '无' }}</strong><small>{{ identity.binding?.linkStatus || '—' }}</small></article>
        </div>
        <div v-if="identity.issues?.length" class="p1-issues">
          <span v-for="issue in identity.issues" :key="issue.code">{{ issue.severity }} · {{ issue.code }}：{{ issue.message }}</span>
        </div>
        <div v-if="identity.binding?.linkStatus === 'ACTIVE'" class="p1-confirm">
          <div><b>解除当前学籍绑定</b><p>仅把当前 ACTIVE link 标记 REVOKED，历史不物理删除；下一次请求立即按新的主体关系重新解析。</p></div>
          <input v-model.trim="unbindReason" placeholder="解绑原因，至少 5 个字" />
          <div class="p1-actions"><AppButton variant="danger" :loading="saving" @click="unbindIdentity">解除错误绑定</AppButton></div>
        </div>
      </div>
    </template>

    <template v-else-if="mode === 'org'">
      <div class="p1-org">
        <label><span>选择准备移动/停用/作废的组织</span>
          <select v-model="orgKey" @change="orgImpact = null">
            <option value="">请选择组织节点</option>
            <option v-for="node in orgOptions" :key="node.key" :value="node.key">{{ node.label }}</option>
          </select>
        </label>
        <AppButton variant="primary" :loading="loading" @click="previewOrgImpact">执行真实影响预演</AppButton>
      </div>
      <div v-if="orgImpact" class="p1-metrics p1-metrics--impact">
        <article><span>受影响专业</span><strong>{{ orgImpact.affectedMajors }}</strong></article>
        <article><span>受影响班级</span><strong>{{ orgImpact.affectedClasses }}</strong></article>
        <article><span>受影响学生</span><strong>{{ orgImpact.affectedStudents }}</strong></article>
        <article><span>在任任职</span><strong>{{ orgImpact.affectedAssignments }}</strong></article>
        <div class="p1-impact-ack">
          <p>下方原组织页面的“作废”动作已被硬门保护：没有对**同一个节点**完成本次预演并确认，真实停用 API 不会执行。</p>
          <AppButton variant="warning" @click="permitOrgDeprecation">我已确认影响，放行该节点下一次作废</AppButton>
        </div>
      </div>
      <p v-else class="p1-note">预演许可只对所选节点有效、5 分钟后失效且只消费一次；不能拿 A 节点的预演去作废 B 节点。</p>
    </template>
  </section>
</template>

<script>
import { AppButton } from '@/components/ui'
import { systemApi } from '@/modules/system/api/system.api'
import { systemP1ClosureApi } from '@/modules/system/api/systemP1Closure.api'
import { toast } from '@/utils/toast'

const permitStore = new Map()
let rawDeprecateOrgNode = null
let guardUsers = 0

function orgPermitKey(type, id) { return `${String(type || '').toUpperCase()}:${String(id)}` }
function toBackendDateTime(value) {
  if (!value) return null
  const raw = String(value).trim().replace('T', ' ')
  return raw.length === 16 ? `${raw}:00` : raw.slice(0, 19)
}
function installOrgGuard() {
  guardUsers += 1
  if (rawDeprecateOrgNode) return
  rawDeprecateOrgNode = systemApi.deprecateOrgNode.bind(systemApi)
  systemApi.deprecateOrgNode = async (id, options = {}) => {
    const key = orgPermitKey(options.type, id)
    const permit = permitStore.get(key)
    if (!permit || permit.expiresAt < Date.now()) {
      permitStore.delete(key)
      return { code: 1, data: null, message: '组织作废前必须先在页面顶部执行真实影响预演，并确认放行该节点' }
    }
    permitStore.delete(key)
    return rawDeprecateOrgNode(id, options)
  }
}
function uninstallOrgGuard() {
  guardUsers = Math.max(0, guardUsers - 1)
  if (guardUsers === 0 && rawDeprecateOrgNode) {
    systemApi.deprecateOrgNode = rawDeprecateOrgNode
    rawDeprecateOrgNode = null
    permitStore.clear()
  }
}

const emptyRole = () => ({ userId: '', roleCode: '', effectiveAt: '', expiresAt: '', reason: '' })

export default {
  name: 'SystemP1ClosurePanel',
  components: { AppButton },
  props: { ctx: { type: Object, required: true } },
  emits: ['refresh-child'],
  data() {
    return {
      loading: false, saving: false, error: '', roles: [], roleForm: emptyRole(),
      configOverrides: [], selectedOverride: null, overrideReason: '',
      identityUserId: '', identity: null, unbindReason: '',
      orgOptions: [], orgKey: '', orgImpact: null, guardInstalled: false
    }
  },
  computed: {
    mode() {
      const p = this.$route.path
      if (p === '/admin/system/role-assignments') return 'role'
      if (p === '/admin/system/login-policy') return 'config'
      if (p === '/admin/system/account-exceptions') return 'identity'
      if (p === '/admin/system/org') return 'org'
      return ''
    },
    title() {
      return { role: '正式角色授权闭环', config: '配置继承与恢复', identity: '稳定主体解析与解绑', org: '组织高危变更影响预演' }[this.mode] || ''
    },
    subtitle() {
      return {
        role: '在既有角色治理页直接创建带来源、起止时间和审计原因的正式授权。',
        config: '撤销学校层当前与计划覆盖后恢复后端 Resolver 继承，不手填“默认值”。',
        identity: '按稳定 userId/studentId 解释账号是谁；错误绑定可留痕解除。',
        org: '移动/停用/作废前先计算专业、班级、学生和任职影响，并作为真实写操作前置门。'
      }[this.mode] || ''
    }
  },
  created() {
    if (this.mode === 'org') { installOrgGuard(); this.guardInstalled = true }
    this.load()
  },
  beforeUnmount() {
    if (this.guardInstalled) uninstallOrgGuard()
  },
  methods: {
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' },
    displayValue(v) { return typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—') },
    async load() {
      this.error = ''
      if (!this.mode) return
      this.loading = true
      try {
        if (this.mode === 'role') {
          const res = await systemApi.getRoles({ page: 1, pageSize: 100, status: 'ENABLED' })
          if (res.code !== 0) throw new Error(res.message)
          this.roles = res.data.list || []
        } else if (this.mode === 'config') {
          const data = await systemP1ClosureApi.listActiveConfigOverrides('SECURITY')
          this.configOverrides = data.items || []
        } else if (this.mode === 'org') {
          const res = await systemApi.getDepartmentTree()
          if (res.code !== 0) throw new Error(res.message)
          this.orgOptions = this.flattenOrg(res.data || [])
        }
      } catch (error) {
        this.error = error.message || '闭环数据加载失败'
      } finally {
        this.loading = false
      }
    },
    async grantRole() {
      if (!/^\d+$/.test(this.roleForm.userId)) return toast.error('userId 必须是数字主键')
      if (!this.roleForm.roleCode) return toast.error('请选择角色')
      if (this.roleForm.reason.trim().length < 5) return toast.error('授权原因不少于 5 个字')
      if (this.roleForm.effectiveAt && this.roleForm.expiresAt && this.roleForm.expiresAt <= this.roleForm.effectiveAt) return toast.error('到期时间必须晚于生效时间')
      this.saving = true
      const res = await systemApi.grantRoleAssignment({
        userId: Number(this.roleForm.userId), roleCode: this.roleForm.roleCode,
        reason: this.roleForm.reason.trim(), sourceType: 'MANUAL',
        effectiveAt: toBackendDateTime(this.roleForm.effectiveAt),
        expiresAt: toBackendDateTime(this.roleForm.expiresAt)
      })
      this.saving = false
      if (res.code !== 0) return toast.error(res.message)
      toast.success('正式角色授权已创建')
      this.roleForm = emptyRole()
      this.$emit('refresh-child')
    },
    selectOverride(item) { this.selectedOverride = item; this.overrideReason = '' },
    async revokeOverride() {
      if (!this.selectedOverride) return
      if (this.overrideReason.trim().length < 5) return toast.error('撤销原因不少于 5 个字')
      const selected = this.selectedOverride
      this.saving = true
      try {
        await systemP1ClosureApi.restoreConfigInheritance(
          selected.configKey,
          selected.overrideChain || [],
          this.overrideReason.trim()
        )
      } catch (error) {
        this.saving = false
        await this.load()
        return toast.error(`恢复继承失败：${error.message || '并发版本冲突，请刷新重试'}`)
      }
      this.saving = false
      toast.success(`已原子撤销 ${selected.overrideCount} 条学校层覆盖，当前值恢复继承`)
      this.selectedOverride = null
      await this.load()
      this.$emit('refresh-child')
    },
    async resolveIdentity() {
      if (!/^\d+$/.test(this.identityUserId)) return toast.error('请输入数字 userId')
      this.loading = true
      const res = await systemApi.getEffectiveIdentity(this.identityUserId)
      this.loading = false
      if (res.code !== 0) return toast.error(res.message)
      this.identity = res.data
      this.unbindReason = ''
    },
    async unbindIdentity() {
      if (!this.identity) return
      if (this.unbindReason.trim().length < 5) return toast.error('解绑原因不少于 5 个字')
      this.saving = true
      const res = await systemApi.unbindIdentity(this.identity.userId, {
        reason: this.unbindReason.trim(), expectedVersion: this.identity.version
      })
      this.saving = false
      if (res.code !== 0) return toast.error(res.message)
      this.identity = res.data
      this.unbindReason = ''
      toast.success('错误绑定已解除，历史记录保留')
      this.$emit('refresh-child')
    },
    flattenOrg(tree) {
      const out = []
      const walk = (nodes, prefix = '') => (nodes || []).forEach((node) => {
        const label = prefix ? `${prefix} / ${node.name}` : node.name
        out.push({ key: orgPermitKey(node.type, node.id), type: node.type, id: node.id, label: `${label}（${node.typeLabel || node.type}）` })
        walk(node.children, label)
      })
      walk(tree)
      return out
    },
    selectedOrg() { return this.orgOptions.find((item) => item.key === this.orgKey) || null },
    async previewOrgImpact() {
      const node = this.selectedOrg()
      if (!node) return toast.error('请选择组织节点')
      this.loading = true
      const res = await systemApi.getOrgNodeImpact(node.type, node.id)
      this.loading = false
      if (res.code !== 0) return toast.error(res.message)
      this.orgImpact = res.data
      permitStore.delete(node.key)
    },
    permitOrgDeprecation() {
      const node = this.selectedOrg()
      if (!node || !this.orgImpact) return
      permitStore.set(node.key, { expiresAt: Date.now() + 5 * 60 * 1000, impact: this.orgImpact })
      toast.success('已放行该节点下一次作废；许可 5 分钟内且仅可使用一次')
    }
  }
}
</script>

<style scoped>
.p1-panel { margin-bottom:14px; padding:14px 16px; border:1px solid var(--primary-200,#bfdbfe); border-radius:12px; background:linear-gradient(180deg,rgba(37,99,235,.055),#fff 96px); }
.p1-panel__head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }.p1-panel__head strong{font-size:15px;color:var(--t1)}.p1-panel__head p{margin:4px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.6}
.p1-form { display:grid; gap:10px; margin-top:12px; }.p1-form--role{grid-template-columns:repeat(4,minmax(0,1fr))}.p1-form label,.p1-org label{display:grid;gap:5px;color:var(--text-secondary);font-size:12px}.p1-panel input,.p1-panel select{min-height:36px;box-sizing:border-box;width:100%;padding:7px 9px;border:1px solid var(--card-b,#e5e6eb);border-radius:8px;background:#fff;color:var(--t1)}.p1-wide{grid-column:span 3}.p1-actions{display:flex;justify-content:flex-end;gap:8px;align-items:end}
.p1-table-wrap{overflow:auto;margin-top:12px}.p1-panel table{width:100%;border-collapse:collapse;min-width:760px}.p1-panel th,.p1-panel td{padding:9px;border-bottom:1px solid var(--card-b,#e5e6eb);text-align:left;vertical-align:top;font-size:12px}.p1-panel td small{display:block;color:var(--text-tertiary);margin-top:3px}
.p1-confirm{display:grid;grid-template-columns:minmax(220px,1fr) minmax(220px,1fr) auto;gap:10px;align-items:center;margin-top:12px;padding:12px;border:1px solid var(--warning-200,#fed7aa);border-radius:10px;background:var(--warning-50,#fff7ed)}.p1-confirm p{margin:3px 0 0;color:var(--text-secondary);font-size:12px}
.p1-inline-search,.p1-org{display:flex;gap:8px;align-items:end;margin-top:12px}.p1-inline-search input{max-width:360px}.p1-org label{min-width:420px}.p1-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}.p1-metrics article{display:grid;gap:3px;padding:10px;border:1px solid var(--card-b,#e5e6eb);border-radius:9px;background:#fff}.p1-metrics span,.p1-metrics small{font-size:12px;color:var(--text-secondary)}.p1-metrics strong{font-size:17px;color:var(--t1)}.p1-issues{display:grid;gap:5px;margin-top:10px;padding:10px;border-radius:9px;background:#fff7ed;color:#9a3412;font-size:12px}.p1-impact-ack{grid-column:1/-1;padding:10px;border:1px solid var(--warning-200,#fed7aa);border-radius:9px;background:var(--warning-50,#fff7ed)}.p1-impact-ack p{margin:0 0 8px;color:var(--text-secondary);font-size:12px}.p1-note,.p1-empty{margin:10px 0 0;color:var(--text-secondary);font-size:12px}.p1-error{margin-top:10px;padding:9px;border-radius:8px;background:#fff2f0;color:#b42318;font-size:12px}
@media(max-width:980px){.p1-form--role{grid-template-columns:repeat(2,minmax(0,1fr))}.p1-wide{grid-column:span 2}.p1-confirm{grid-template-columns:1fr}.p1-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.p1-panel__head,.p1-inline-search,.p1-org{display:grid}.p1-form--role,.p1-metrics{grid-template-columns:1fr}.p1-wide{grid-column:auto}.p1-org label{min-width:0}}
</style>
