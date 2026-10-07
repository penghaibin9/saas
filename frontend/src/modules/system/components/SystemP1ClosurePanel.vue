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
      <template v-if="canGrantRole">
        <div class="p1-form p1-form--role">
          <label><span>用户编号</span><input v-model.trim="roleForm.userId" inputmode="numeric" placeholder="数字编号" /></label>
          <label><span>角色</span>
            <select v-model="roleForm.roleCode">
              <option value="">请选择角色</option>
              <option v-for="role in roles" :key="role.id || role.code" :value="role.code">{{ role.name }}</option>
            </select>
          </label>
          <label><span>生效方式</span><input value="立即生效（未来排期暂不开放）" disabled /></label>
          <label><span>到期时间</span><input v-model="roleForm.expiresAt" type="datetime-local" /></label>
          <label class="p1-wide"><span>授权原因</span><input v-model.trim="roleForm.reason" placeholder="至少 5 个字；写入授权来源与审计" /></label>
          <div class="p1-actions"><AppButton variant="primary" :loading="saving" @click="grantRole">新增正式角色授权</AppButton></div>
        </div>
        <p class="p1-note">服务端会拒绝停用角色、学生/教职工角色串用、重复覆盖授权与未来时间提前生效；新增记录继续在下方台账复核、转交、回收。</p>
      </template>
      <p v-else class="p1-note">当前角色只有查看权限；新增正式授权需要“用户分配”或“角色配置”权限。</p>
    </template>

    <template v-else-if="mode === 'config'">
      <div v-if="!configOverrides.length && !loading" class="p1-empty">当前安全配置域没有可撤销的学校层覆盖，全部继承平台、套餐或历史配置。</div>
      <div v-else class="p1-table-wrap">
        <table>
          <thead><tr><th>配置</th><th>当前/计划值</th><th>覆盖链</th><th>当前生效时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in configOverrides" :key="item.configKey">
              <td><b>{{ item.configName }}</b><small>学校安全配置</small></td>
              <td>{{ displayValue(item.value) }}<small v-if="item.isScheduledOnly">仅有未来计划覆盖</small></td>
              <td>{{ item.overrideCount }} 条学校覆盖<small v-if="item.scheduledCount">其中 {{ item.scheduledCount }} 条待生效</small></td>
              <td>{{ fmt(item.effectiveAt) }}</td>
              <td><AppButton v-if="canRestoreConfig" variant="secondary" @click="selectOverride(item)">恢复继承</AppButton><span v-else class="p1-muted">只读</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="selectedOverride && canRestoreConfig" class="p1-confirm">
        <div>
          <b>撤销 {{ selectedOverride.configName }} 的全部学校层覆盖？</b>
          <p>服务端会锁住并校验 {{ selectedOverride.overrideCount }} 条当前或计划覆盖的完整链与每条版本，单事务撤销并写高危审计；任何并发变化都会整笔拒绝。</p>
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
        <input v-model.trim="identityUserId" inputmode="numeric" placeholder="输入用户编号查看稳定主体解析" @keyup.enter="resolveIdentity" />
        <AppButton variant="primary" :loading="loading" @click="resolveIdentity">解析身份</AppButton>
      </div>
      <div v-if="identity" class="p1-identity">
        <div class="p1-metrics">
          <article><span>账号</span><strong>{{ identity.realName || identity.loginName }}</strong><small>用户编号 {{ identity.userId }}</small></article>
          <article><span>主体来源</span><strong>{{ identitySourceLabel(identity.identitySource) }}</strong><small>{{ accountTypeLabel(identity.accountType) }}</small></article>
          <article><span>学籍主体</span><strong>{{ identity.studentId || '未绑定' }}</strong><small>{{ identity.studentNo || '—' }}</small></article>
          <article><span>绑定记录</span><strong>{{ identity.binding?.linkId || '无' }}</strong><small>{{ bindingStatusLabel(identity.binding?.linkStatus) }}</small></article>
        </div>
        <div v-if="identity.issues?.length" class="p1-issues">
          <span v-for="issue in identity.issues" :key="issue.code">{{ severityLabel(issue.severity) }} · {{ issueLabel(issue.code) }}：{{ issue.message }}</span>
        </div>
        <div v-if="identity.binding?.linkStatus === 'ACTIVE' && canUnbindIdentity" class="p1-confirm">
          <div><b>解除当前学籍绑定</b><p>仅把当前生效中的绑定标记为已撤销，历史记录不会物理删除；下一次请求立即按新的主体关系重新解析。</p></div>
          <input v-model.trim="unbindReason" placeholder="解绑原因，至少 5 个字" />
          <div class="p1-actions"><AppButton variant="danger" :loading="saving" @click="unbindIdentity">解除错误绑定</AppButton></div>
        </div>
        <p v-else-if="identity.binding?.linkStatus === 'ACTIVE'" class="p1-note">当前角色可查看异常，但没有身份绑定写权限；解绑入口已隐藏。</p>
      </div>
    </template>

  </section>
</template>

<script>
import { AppButton } from '@/components/ui'
import { systemApi } from '@/modules/system/api/system.api'
import { systemP1ClosureApi } from '@/modules/system/api/systemP1Closure.api'
import { toast } from '@/utils/toast'

function toBackendDateTime(value) {
  if (!value) return null
  const raw = String(value).trim().replace('T', ' ')
  return raw.length === 16 ? `${raw}:00` : raw.slice(0, 19)
}
function permissionMatch(pattern, required) {
  const p = String(pattern || '').trim()
  const r = String(required || '').trim()
  if (!p || !r) return false
  if (p === '*' || p === r) return true
  if (p.endsWith('.*')) return r.startsWith(p.slice(0, -1))
  if (p.startsWith('*.')) return r.endsWith(p.slice(1))
  return false
}
const emptyRole = () => ({ userId: '', roleCode: '', expiresAt: '', reason: '' })

export default {
  name: 'SystemP1ClosurePanel',
  components: { AppButton },
  props: { ctx: { type: Object, required: true } },
  emits: ['refresh-child'],
  data() {
    return {
      loading: false, saving: false, error: '', roles: [], roleForm: emptyRole(),
      configOverrides: [], selectedOverride: null, overrideReason: '',
      identityUserId: '', identity: null, unbindReason: ''
    }
  },
  computed: {
    mode() {
      const p = this.$route.path
      if (p === '/admin/system/role-assignments') return 'role'
      if (p === '/admin/system/login-policy') return 'config'
      if (p === '/admin/system/account-exceptions') return 'identity'
      return ''
    },
    title() {
      return { role: '正式角色授权闭环', config: '配置继承与恢复', identity: '稳定主体解析与解绑' }[this.mode] || ''
    },
    subtitle() {
      return {
        role: '在既有角色治理页创建带来源、到期与审计原因的正式授权；高危边界由服务端强制。',
        config: '撤销学校层当前与计划覆盖后恢复后端 Resolver 继承，不手填“默认值”。',
        identity: '按稳定 userId/studentId 解释账号是谁；有写权限时可留痕解除错误绑定。'
      }[this.mode] || ''
    },
    permissionPatterns() {
      const raw = this.ctx?.permissionPatterns
      if (Array.isArray(raw)) return raw
      if (raw && typeof raw === 'object') return Object.keys(raw).filter((key) => raw[key])
      return []
    },
    canGrantRole() { return this.hasAnyPermission('systemAdmin.user.assign', 'systemAdmin.role.config') },
    canRestoreConfig() { return this.hasAnyPermission('systemAdmin.config.manage', 'systemAdmin.security.policy.manage') },
    canUnbindIdentity() { return this.hasAnyPermission('systemAdmin.user.bind', 'systemAdmin.user.manage') }
  },
  created() {
    this.load()
  },
  methods: {
    identitySourceLabel(value) { return ({ STUDENT_PROFILE: '学生主档', STAFF_PROFILE: '教职工主档', ACCOUNT: '系统账号', IMPORT: '批量导入', MANUAL: '人工维护' })[value] || (value ? '来源待确认' : '—') },
    accountTypeLabel(value) { return ({ STUDENT: '学生账号', STAFF: '教职工账号', ADMIN: '管理账号', PLATFORM: '平台账号' })[value] || (value ? '账号类型待确认' : '—') },
    bindingStatusLabel(value) { return ({ ACTIVE: '生效中', REVOKED: '已撤销', PENDING: '待确认', CONFLICT: '存在冲突' })[value] || (value ? '状态待确认' : '—') },
    severityLabel(value) { return ({ CRITICAL: '紧急', HIGH: '高风险', MEDIUM: '中风险', LOW: '低风险', WARNING: '警告', ERROR: '异常' })[value] || (value ? '等级待确认' : '—') },
    issueLabel(value) { return ({ DUPLICATE_BINDING: '存在重复绑定', MISSING_PROFILE: '缺少主体主档', TYPE_MISMATCH: '账号类型不一致', INVALID_BINDING: '绑定关系无效', ORPHAN_ACCOUNT: '账号缺少业务主体' })[value] || (value ? '身份解析异常' : '—') },
    hasAnyPermission(...codes) { return codes.some((code) => this.permissionPatterns.some((pattern) => permissionMatch(pattern, code))) },
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' },
    displayValue(v) {
      if (v === null || v === undefined || v === '') return '—'
      if (typeof v === 'boolean') return v ? '是' : '否'
      if (typeof v === 'object') return `已配置 ${Object.keys(v).length} 项参数`
      return String(v)
    },
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

        }
      } catch (error) {
        this.error = error.message || '闭环数据加载失败'
      } finally {
        this.loading = false
      }
    },
    async grantRole() {
      if (!this.canGrantRole) return toast.error('当前角色没有正式授权写权限')
      if (!/^\d+$/.test(this.roleForm.userId)) return toast.error('userId 必须是数字主键')
      if (!this.roleForm.roleCode) return toast.error('请选择角色')
      if (this.roleForm.reason.trim().length < 5) return toast.error('授权原因不少于 5 个字')
      if (this.roleForm.expiresAt && new Date(this.roleForm.expiresAt).getTime() <= Date.now()) return toast.error('到期时间必须晚于当前时间')
      this.saving = true
      const res = await systemApi.grantRoleAssignment({
        userId: Number(this.roleForm.userId), roleCode: this.roleForm.roleCode,
        reason: this.roleForm.reason.trim(), sourceType: 'MANUAL',
        effectiveAt: null,
        expiresAt: toBackendDateTime(this.roleForm.expiresAt)
      })
      this.saving = false
      if (res.code !== 0) return toast.error(res.message)
      toast.success('正式角色授权已创建')
      this.roleForm = emptyRole()
      this.$emit('refresh-child')
    },
    selectOverride(item) { if (this.canRestoreConfig) { this.selectedOverride = item; this.overrideReason = '' } },
    async revokeOverride() {
      if (!this.selectedOverride || !this.canRestoreConfig) return
      if (this.overrideReason.trim().length < 5) return toast.error('撤销原因不少于 5 个字')
      const selected = this.selectedOverride
      this.saving = true
      try {
        await systemP1ClosureApi.restoreConfigInheritance(
          selected.configKey, selected.overrideChain || [], this.overrideReason.trim()
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
      if (!this.identity || !this.canUnbindIdentity) return toast.error('当前角色没有身份解绑权限')
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
    }

  }
}
</script>

<style scoped>
.p1-panel { margin-bottom:14px; padding:14px 16px; border:1px solid var(--primary-200,#bfdbfe); border-radius:12px; background:linear-gradient(180deg,rgba(37,99,235,.055),#fff 96px); }
.p1-panel__head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }.p1-panel__head strong{font-size:15px;color:var(--t1)}.p1-panel__head p{margin:4px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.6}
.p1-form { display:grid; gap:10px; margin-top:12px; }.p1-form--role{grid-template-columns:repeat(4,minmax(0,1fr))}.p1-form label,.p1-org label{display:grid;gap:5px;color:var(--text-secondary);font-size:12px}.p1-panel input,.p1-panel select{min-height:36px;box-sizing:border-box;width:100%;padding:7px 9px;border:1px solid var(--card-b,#e5e6eb);border-radius:8px;background:#fff;color:var(--t1)}.p1-panel input:disabled{background:var(--fill-secondary,#f3f4f6);color:var(--text-tertiary)}.p1-wide{grid-column:span 3}.p1-actions{display:flex;justify-content:flex-end;gap:8px;align-items:end}
.p1-table-wrap{overflow:auto;margin-top:12px}.p1-panel table{width:100%;border-collapse:collapse;min-width:760px}.p1-panel th,.p1-panel td{padding:9px;border-bottom:1px solid var(--card-b,#e5e6eb);text-align:left;vertical-align:top;font-size:12px}.p1-panel td small{display:block;color:var(--text-tertiary);margin-top:3px}
.p1-confirm{display:grid;grid-template-columns:minmax(220px,1fr) minmax(220px,1fr) auto;gap:10px;align-items:center;margin-top:12px;padding:12px;border:1px solid var(--warning-200,#fed7aa);border-radius:10px;background:var(--warning-50,#fff7ed)}.p1-confirm p{margin:3px 0 0;color:var(--text-secondary);font-size:12px}
.p1-inline-search,.p1-org{display:flex;gap:8px;align-items:end;margin-top:12px}.p1-inline-search input{max-width:360px}.p1-org label{min-width:420px}.p1-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}.p1-metrics article{display:grid;gap:3px;padding:10px;border:1px solid var(--card-b,#e5e6eb);border-radius:9px;background:#fff}.p1-metrics span,.p1-metrics small{font-size:12px;color:var(--text-secondary)}.p1-metrics strong{font-size:17px;color:var(--t1)}.p1-issues{display:grid;gap:5px;margin-top:10px;padding:10px;border-radius:9px;background:#fff7ed;color:#9a3412;font-size:12px}.p1-impact-ack{grid-column:1/-1;padding:10px;border:1px solid var(--warning-200,#fed7aa);border-radius:9px;background:var(--warning-50,#fff7ed)}.p1-impact-ack p{margin:0 0 8px;color:var(--text-secondary);font-size:12px}.p1-note,.p1-empty,.p1-muted{margin:10px 0 0;color:var(--text-secondary);font-size:12px}.p1-error{margin-top:10px;padding:9px;border-radius:8px;background:#fff2f0;color:#b42318;font-size:12px}
@media(max-width:980px){.p1-form--role{grid-template-columns:repeat(2,minmax(0,1fr))}.p1-wide{grid-column:span 2}.p1-confirm{grid-template-columns:1fr}.p1-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.p1-panel__head,.p1-inline-search,.p1-org{display:grid}.p1-form--role,.p1-metrics{grid-template-columns:1fr}.p1-wide{grid-column:auto}.p1-org label{min-width:0}}
</style>
