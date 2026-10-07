<template>
  <section class="phone-governance" aria-label="手机号治理">
    <h3>手机号登录凭据</h3>
    <p>联系方式不等于登录凭据。本人短信验证前仅为待核验；原学号 / 工号和密码始终保留。</p>
    <p v-if="!canView" role="status">当前岗位没有号码治理查看权限，请联系学校核对授权。</p>
    <template v-else>
      <form class="pg-filters" @submit.prevent="search">
        <label v-if="!userId">账号 / 姓名<input v-model.trim="filters.keyword" maxlength="100" :disabled="state.busy"></label>
        <label>号码状态<select v-model="filters.state" :disabled="state.busy"><option value="">全部</option><option value="UNBOUND">未绑定</option><option value="PENDING">待本人验证</option><option value="VERIFIED">已验证</option><option value="CONFLICT">号码冲突</option><option value="REVOKED">已撤销</option></select></label>
        <template v-if="canLookup"><label>精确手机号<input v-model.trim="filters.phone" inputmode="tel" autocomplete="off" maxlength="20" :disabled="state.busy"></label><label v-if="filters.phone">核对用途<input v-model.trim="filters.reason" maxlength="300" :disabled="state.busy"></label></template>
        <button type="submit" :disabled="state.busy">{{ state.busy ? '正在读取…' : '查询 / 重新读取' }}</button>
      </form>
      <div v-if="canRemind || canExport" class="pg-filters">
        <label>提醒 / 导出用途<input v-model.trim="state.batchReason" maxlength="300" :disabled="state.busy || !!state.preview"></label>
        <button v-if="canRemind" :disabled="state.busy || state.uncertain" @click="controller.preview('REMIND')">预览待验证本人提醒</button>
        <button v-if="canExport" :disabled="state.busy || state.uncertain" @click="controller.preview('EXPORT')">预览筛选范围脱敏台账</button>
      </div>
      <div v-if="state.preview" role="status" class="pg-edit">
        <strong>{{ state.preview.action === 'REMIND' ? '站内提醒' : '脱敏 xlsx 导出' }} · 已冻结 {{ state.preview.count }} 个账号</strong>
        <p>{{ state.preview.notice }}。预览 5 分钟有效；改筛选后请重新预览，确认不会采用页面新筛选。</p>
        <div class="pg-filters"><button :disabled="state.busy || state.uncertain" @click="controller.confirm()">确认本次预览范围</button><button v-if="state.uncertain" :disabled="state.busy" @click="controller.checkBatchResult()">核对同一操作结果</button><button :disabled="state.busy" @click="state.preview = null">关闭预览</button></div>
      </div>
      <button v-if="state.exportJob" :disabled="state.busy" @click="download">下载本次脱敏台账</button>
      <p v-if="state.error" role="alert" class="pg-error">{{ state.error }}</p>
      <p v-if="state.note" role="status">{{ state.note }}</p>
      <p v-if="state.uncertain">本次结果需要核对，已停止重复提交。输入仍保留；重新读取状态后，请重新选择账号确认版本。</p>
      <p v-if="state.busy" role="status">正在处理，请勿重复提交。</p>
      <div v-else-if="!state.error && !state.rows.length">当前范围和筛选条件下没有匹配账号。</div>
      <div v-else-if="state.rows.length" class="pg-table"><table><thead><tr><th>原账号 / 姓名</th><th>登录号码</th><th>待核验号码</th><th>来源 / 版本</th><th>办理</th></tr></thead><tbody>
        <tr v-for="row in state.rows" :key="row.userId">
          <td>{{ row.loginName }}<br>{{ row.name }}</td>
          <td>{{ row.phoneMasked || '未绑定' }}<br>{{ label(row.state) }}<span v-if="row.recoveryFrozen"> · 找回已冻结</span></td>
          <td>{{ row.candidatePhoneMasked || '未登记' }}<br>{{ label(row.candidateState) }}</td>
          <td>{{ sourceLabel(row.sourceKind) }}<br>凭据 {{ row.bindingVersion }} / 候选 {{ row.candidateVersion }}</td>
          <td><button v-if="row.allowedActions?.candidate" :disabled="state.busy || state.uncertain" @click="controller.edit(row)">登记 / 清除候选</button>
            <button v-if="row.allowedActions?.revoke" :disabled="state.busy || state.uncertain" @click="controller.editRevoke(row)">撤销误绑凭据</button>
            <span v-if="!row.allowedActions?.candidate && !row.allowedActions?.revoke">{{ row.state === 'VERIFIED' ? '已验证号码由本人办理换号' : '当前不可办理' }}</span></td>
        </tr>
      </tbody></table></div>
      <div class="pg-filters"><span>共 {{ state.total }} 个账号 · 第 {{ state.page }} 页</span><button :disabled="state.busy || state.page <= 1" @click="page(-1)">上一页</button><button :disabled="state.busy || state.page * state.pageSize >= state.total" @click="page(1)">下一页</button></div>
      <form v-if="state.edit" class="pg-edit" @submit.prevent="controller.save()">
        <h4>{{ state.edit.kind === 'revoke' ? '撤销' : '登记 / 清除' }}「{{ state.edit.name }}」的{{ state.edit.kind === 'revoke' ? '手机号凭据' : '待验证号码' }}</h4>
        <template v-if="state.edit.kind === 'revoke'"><p>即将撤销 {{ state.edit.phoneMasked }}。旧手机号不能再登录或找回，目标账号的旧会话失效；原账号和密码保留。此操作不会设置新号码。</p><label>经办人当前密码<input v-model="state.edit.currentPassword" type="password" maxlength="128" autocomplete="current-password" :disabled="state.busy"></label></template>
        <template v-else><p>留空表示清除候选，不撤销已验证凭据；学校不能替本人标记验证成功。</p>
        <label>本人手机号<input v-model.trim="state.edit.phone" inputmode="tel" maxlength="20" autocomplete="off" :disabled="state.busy"></label></template>
        <label>办理原因<textarea v-model.trim="state.edit.reason" rows="2" maxlength="300" :disabled="state.busy" /></label>
        <div class="pg-filters"><button type="submit" :disabled="state.busy || state.uncertain">{{ state.edit.kind === 'revoke' ? '确认撤销号码凭据' : state.edit.phone ? '确认登记为待本人验证' : '确认清除候选' }}</button><button type="button" :disabled="state.busy" @click="state.edit = null">取消</button></div>
      </form>
    </template>
  </section>
</template>

<script>
import { phoneGovernanceApi } from '../api/phoneGovernance.api'
import { createPhoneGovernance, phoneGovernanceState } from '../utils/phoneGovernance'
import { contextFingerprint } from '../utils/workspaceContract'
import { matchPermission } from '@/config/navPlan'
import { dataExchangeApi } from '../api/dataExchange.api'
export default {
  props: { ctx: { type: Object, required: true }, accountType: { type: String, default: '' }, userId: { type: String, default: '' }, initialState: { type: String, default: '' } },
  data() { return { state: phoneGovernanceState(), controller: null, filters: { keyword: '', phone: '', reason: '', state: this.initialState } } },
  computed: {
    contextKey() { return contextFingerprint(this.ctx) },
    canView() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.phoneBinding.view') },
    canLookup() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.phoneBinding.lookup') },
    canRemind() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.phoneBinding.remind') },
    canExport() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.phoneBinding.export') }
  },
  watch: { contextKey() { this.recreate() }, accountType() { this.recreate() }, userId() { this.recreate() }, canView() { this.recreate() } },
  created() { this.recreate() },
  beforeUnmount() { this.controller?.dispose() },
  methods: {
    async download() {
      if (this.state.busy || !this.state.exportJob) return
      const state = this.state; state.busy = true
      try {
        const ticket = await dataExchangeApi.downloadExport(state.exportJob)
        if (this.state === state) state.exportJob.version = ticket.version
      } catch (error) { if (this.state === state) state.error = error.message || '下载失败，请从原数据交换任务中重新读取后下载' }
      finally { if (this.state === state) state.busy = false }
    },
    label(state) { return { UNBOUND: '未绑定', VERIFIED: '已验证', REVOKED: '已撤销', NONE: '无候选', PENDING: '待本人验证', CONFLICT: '需核对冲突', APPLIED: '已用于本人验证', CLEARED: '已清除' }[state] || '状态待核对' },
    sourceLabel(value) { return { ADMIN: '后台登记', SELF_SERVICE: '本人登记', IDENTITY_IMPORT: '师生导入' }[value] || '无候选来源' },
    recreate() {
      this.controller?.dispose(); this.state = phoneGovernanceState()
      this.filters = { keyword: '', phone: '', reason: '', state: this.initialState }
      this.controller = createPhoneGovernance(this.state, phoneGovernanceApi, () => ({ ...this.filters, accountType: this.accountType, userId: this.userId }))
      if (this.canView) this.controller.load()
    },
    search() { if (!this.state.busy) { this.state.page = 1; this.controller.load() } },
    page(delta) { if (!this.state.busy) { this.state.page += delta; this.controller.load() } }
  }
}
</script>

<style scoped>
.phone-governance { padding:20px; background:white; border:1px solid #dce3ed; border-radius:12px; color:#23354c; }
.phone-governance p { font-size:13px; line-height:1.7; }.pg-filters { display:flex; gap:12px; align-items:end; flex-wrap:wrap; margin:14px 0; }
.phone-governance label { display:grid; gap:6px; font-size:13px; }.phone-governance input,.phone-governance select,.phone-governance textarea { border:1px solid #cbd5e1; border-radius:6px; padding:9px; font:inherit; max-width:100%; box-sizing:border-box; }
.phone-governance button { border:1px solid #cbd5e1; border-radius:6px; padding:9px 12px; background:#f3f7ff; color:#2454a0; cursor:pointer; }.phone-governance button:disabled { opacity:.5; cursor:default; }
.pg-table { overflow-x:auto; }table { border-collapse:collapse; width:100%; font-size:13px; }th,td { text-align:left; padding:12px; border-bottom:1px solid #e5eaf0; line-height:1.7; }td { overflow-wrap:anywhere; }.pg-error { color:#b42318; }.pg-edit { border-top:1px solid #dce3ed; padding-top:14px; display:grid; gap:12px; }
</style>
