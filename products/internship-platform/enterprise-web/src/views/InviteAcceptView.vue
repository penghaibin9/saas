<script>
import { enterpriseAuthApi } from '../services/authApi'
// Auth contract: 同一 tenantCode + 邀请 token 在服务端校验；不会再次提交 campaignId 或 companyId。
export default {
  name: 'InviteAcceptView',
  data() { return { loading: true, submitting: false, error: '', preview: null, sequence: 0, alive: true,
    form: { loginName: '', phone: '', password: '' } } },
  computed: {
    token() { return String(this.$route.query.token || '') },
    tenantCode() { return String(this.$route.query.tenantCode || this.$route.query.tenant || '') },
    inviteKey() { return JSON.stringify([this.tenantCode, this.token]) },
    existing() { return this.preview?.inviteMode === 'EXISTING_MEMBER' },
    roleLabel() { return { COMPANY_ADMIN: '企业管理员', HR: '招聘对接人', MENTOR: '企业导师' }[this.preview?.memberRole] || '企业成员' },
    expiresLabel() { const d = new Date(this.preview?.expiresAt); return Number.isFinite(d.getTime()) ? d.toLocaleString('zh-CN', { hour12: false }) : '以学校邀请为准' }
  },
  watch: { inviteKey() { this.load() } },
  created() { this.load() },
  beforeUnmount() { this.alive = false; this.sequence++; this.form.password = '' },
  methods: {
    current(sequence, key) { return this.alive && this.sequence === sequence && this.inviteKey === key },
    async load() {
      const sequence = ++this.sequence, key = this.inviteKey
      this.loading = true; this.submitting = false; this.error = ''; this.preview = null; this.form = { loginName: '', phone: '', password: '' }
      if (!this.token || !this.tenantCode) { this.error = '邀请链接不完整，请联系学校重新获取'; this.loading = false; return }
      try {
        const preview = await enterpriseAuthApi.inspectInvite({ tenantCode: this.tenantCode, token: this.token })
        if (this.current(sequence, key)) this.preview = preview
      } catch (e) { if (this.current(sequence, key)) this.error = e.message || '邀请已失效或无权访问' }
      finally { if (this.current(sequence, key)) this.loading = false }
    },
    async accept() {
      if (this.loading || this.submitting || !this.preview) return
      const sequence = this.sequence, key = this.inviteKey, existing = this.existing
      const invite = { tenantCode: this.tenantCode, token: this.token }, form = { ...this.form }, memberId = this.preview.memberId
      if (!form.password || (existing ? !form.loginName.trim() : !form.phone.trim() || form.password.length < 8)) { this.error = existing ? '请填写原企业账号和密码' : '请填写受邀手机号，并设置至少 8 位密码'; return }
      if (existing && !memberId) { this.error = '邀请成员信息不完整，请重新校验'; return }
      this.submitting = true; this.error = ''
      try {
        if (existing) {
          await enterpriseAuthApi.login({ tenantCode: invite.tenantCode, loginName: form.loginName.trim(), password: form.password, memberId })
          if (!this.current(sequence, key)) return
          const refreshed = await enterpriseAuthApi.inspectInvite(invite)
          if (!this.current(sequence, key)) return
          if (refreshed.inviteMode !== 'EXISTING_MEMBER' || String(refreshed.memberId) !== String(memberId)) throw new Error('邀请成员已变化，请重新核对')
          await enterpriseAuthApi.acceptExistingInvite(invite)
        } else await enterpriseAuthApi.acceptInvite({ ...invite, phone: form.phone.trim(), password: form.password })
        if (!this.current(sequence, key)) return
        this.form.password = ''
        await this.$router.push('/home')
      } catch (e) { if (this.current(sequence, key)) { this.error = e.message || '接受邀请失败，请核对后重试'; this.form.password = '' } }
      finally { if (this.current(sequence, key)) this.submitting = false }
    }
  }
}
</script>

<template>
  <main class="invite-page">
    <header class="invite-brand"><span>跃科</span><span>企业协同中心</span></header>
    <section v-if="loading" class="invite-state" aria-live="polite">正在核验学校邀请…</section>
    <section v-else-if="!preview" class="invite-state"><h1>暂时无法打开邀请</h1><p role="alert">{{ error }}</p><button class="ep-btn" type="button" @click="load">重新校验</button><p>链接已失效时，请联系学校重新获取。</p></section>
    <section v-else class="invite-workspace">
      <aside class="invite-summary">
        <div class="invite-kicker">学校发来的岗位实习邀请</div><h1>{{ preview.campaignName }}</h1>
        <p class="invite-school">{{ preview.schoolName }}</p>
        <dl>
          <div><dt>受邀企业</dt><dd>{{ preview.companyName }}</dd></div>
          <div><dt>受邀联系人</dt><dd>{{ preview.inviteeName }}<small>{{ preview.phoneMasked }}</small></dd></div>
          <div><dt>成员身份</dt><dd>{{ roleLabel }}</dd></div>
          <div><dt>邀请有效期至</dt><dd>{{ expiresLabel }}<small>本地时间</small></dd></div>
        </dl>
        <p class="invite-footnote">接受本轮邀请后，可进入企业工作台，按学校安排报送岗位。</p>
      </aside>
      <div class="invite-action">
        <span class="invite-badge">{{ existing ? '沿用已有企业账号' : '首次开通企业账号' }}</span>
        <h2>{{ existing ? '登录并确认本轮参与' : '完成账号激活' }}</h2>
        <p class="invite-intro">{{ existing ? '使用受邀联系人的原账号和密码。原有角色与密码保持不变。' : '核对受邀手机号，设置今后登录企业协同中心的密码。' }}</p>
        <form @submit.prevent="accept">
          <fieldset :disabled="submitting">
            <label v-if="existing" for="invite-account">原企业登录账号<input id="invite-account" v-model.trim="form.loginName" class="ep-input" autocomplete="username" required /></label>
            <label v-else for="invite-phone">受邀手机号<input id="invite-phone" v-model.trim="form.phone" class="ep-input" inputmode="tel" autocomplete="tel" required /></label>
            <label for="invite-password">{{ existing ? '原账号密码' : '设置密码（至少 8 位）' }}<input id="invite-password" v-model="form.password" class="ep-input" type="password" :minlength="existing ? undefined : 8" :autocomplete="existing ? 'current-password' : 'new-password'" required /></label>
          </fieldset>
          <p v-if="error" class="invite-error" role="alert">{{ error }}</p>
          <button class="ep-btn ep-btn-primary invite-submit" :disabled="submitting">{{ submitting ? '正在办理…' : existing ? '登录并接受本轮邀请' : '激活账号并接受邀请' }}</button>
        </form>
        <p class="invite-help">{{ existing ? '登录账号须属于受邀企业及联系人。账号信息不符时，请联系学校核对。' : '手机号须与学校登记的一致。信息有误时，请联系学校修正邀请。' }}</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.invite-page { min-height:100vh; padding:30px 28px 50px; background:var(--page); }
.invite-brand { display:flex; align-items:center; gap:16px; max-width:960px; margin:0 auto 32px; color:var(--t2); font-size:13px; }
.invite-brand span:first-child { color:var(--pri); font-size:22px; font-weight:750; padding-right:16px; border-right:1px solid var(--line-strong); }
.invite-workspace { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); max-width:960px; margin:auto; background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow-sm); overflow:hidden; }
.invite-summary { padding:38px; background:var(--surface-soft); border-right:1px solid var(--line); }
.invite-kicker { font-size:12px; color:var(--pri); font-weight:600; }
.invite-summary h1 { margin:12px 0; font-size:24px; line-height:1.45; color:var(--t1); overflow-wrap:anywhere; }
.invite-school { font-size:13px; line-height:1.7; color:var(--t2); margin:0 0 30px; }
.invite-summary dl { margin:0; display:grid; gap:22px; }
.invite-summary dt { color:var(--t3); font-size:12px; margin-bottom:6px; }
.invite-summary dd { margin:0; color:var(--t1); font-size:14px; line-height:1.6; overflow-wrap:anywhere; }
.invite-summary small { display:block; font-size:12px; color:var(--t3); margin-top:3px; }
.invite-footnote { margin:30px 0 0; padding-top:20px; border-top:1px solid var(--line); font-size:12px; line-height:1.8; color:var(--t3); }
.invite-action { padding:42px 38px; align-self:center; }
.invite-badge { padding:5px 8px; background:var(--pri-50); color:var(--pri); font-size:11px; border-radius:5px; }
.invite-action h2 { font-size:22px; margin:17px 0 10px; color:var(--t1); }
.invite-intro,.invite-help { color:var(--t3); font-size:13px; line-height:1.8; margin:0 0 25px; }
.invite-action fieldset { border:0; padding:0; margin:0; min-width:0; }
.invite-action label { display:flex; flex-direction:column; gap:8px; font-size:13px; color:var(--t2); margin-bottom:20px; }
.invite-action input { width:100%; min-height:42px; }
.invite-submit { width:100%; min-height:42px; margin-top:4px; }
.invite-help { margin:18px 0 0; font-size:12px; }
.invite-error { margin:0 0 14px; padding:10px 12px; border-radius:6px; background:var(--danger-bg); color:var(--danger-fg); font-size:12px; line-height:1.7; }
.invite-state { max-width:650px; padding:30px; margin:60px auto; background:var(--card); border:1px solid var(--line); border-radius:12px; color:var(--t2); line-height:1.8; }
.invite-state h1 { font-size:21px; }
@media(max-width:700px) { .invite-page { padding:20px 16px; } .invite-brand { margin-bottom:20px; } .invite-workspace { grid-template-columns:1fr; } .invite-summary { padding:24px; border-right:0; border-bottom:1px solid var(--line); } .invite-summary h1 { font-size:21px; } .invite-summary dl { grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; } .invite-school { margin-bottom:20px; } .invite-footnote { margin-top:20px; padding-top:14px; } .invite-action { padding:28px 24px; } }
</style>
