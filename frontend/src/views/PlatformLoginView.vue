<template>
  <main class="platform-login">
    <section class="brand-panel">
      <div class="brand-mark">S</div>
      <div>
        <p class="eyebrow">SAAS CONTROL PLANE</p>
        <h1>运营平台</h1>
      </div>
      <div class="brand-copy">
        <h2>只服务平台运营方</h2>
        <p>租户、套餐、开通、发布、安全审计在同一控制面管理；学校账号不能进入此处。</p>
      </div>
    </section>

    <section class="login-panel" aria-labelledby="login-title">
      <div class="login-card">
        <p class="kicker">平台运营人员登录</p>
        <h2 id="login-title">进入 SaaS 运营平台</h2>
        <p class="hint">请使用平台超级管理员账号，不使用学校管理员账号。</p>

        <form @submit.prevent="submit">
          <label>
            平台编码
            <input v-model="form.tenantCode" autocomplete="organization" placeholder="platform" />
          </label>
          <label>
            账号
            <input v-model.trim="form.loginName" autocomplete="username" placeholder="请输入平台账号" required />
          </label>
          <label>
            密码
            <div class="password-row">
              <input v-model="form.password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" required />
              <button type="button" class="text-button" @click="showPassword = !showPassword">
                {{ showPassword ? '隐藏' : '显示' }}
              </button>
            </div>
          </label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="submit" type="submit" :disabled="loading">
            {{ loading ? '正在验证…' : '登录运营平台' }}
          </button>
        </form>

        <p class="security-note">此入口不会提供演示账号或免密登录。首次密码应由平台负责人安全保存并及时修改。</p>
        <router-link class="school-link" to="/login">返回学校端登录</router-link>
      </div>
    </section>
  </main>
</template>

<script>
import { clearAuthSession, isPlatformSuperAdmin, loginWithPassword } from '@/services/http/client'

export default {
  name: 'PlatformLoginView',
  data() {
    return {
      loading: false,
      showPassword: false,
      error: '',
      form: { tenantCode: 'platform', loginName: '', password: '' }
    }
  },
  methods: {
    async submit() {
      this.error = ''
      this.loading = true
      try {
        await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode || 'platform')
        if (!isPlatformSuperAdmin()) {
          clearAuthSession()
          this.error = '此账号不是平台超级管理员，请使用学校端登录。'
          return
        }
        await this.$router.push('/admin/platform/overview')
      } catch (error) {
        this.error = error?.message || '登录失败，请检查账号、密码和平台编码。'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.platform-login { min-height: 100vh; display: grid; grid-template-columns: minmax(300px, 44%) 1fr; font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f7f9fc; color: #16233e; }
.brand-panel { position: relative; overflow: hidden; min-height: 100%; padding: 54px 56px; color: #fff; background: radial-gradient(circle at 15% 20%, #3e7bff 0, transparent 35%), linear-gradient(145deg, #102a57, #1f5fc8); }
.brand-panel::after { content: ''; position: absolute; right: -130px; bottom: -180px; width: 460px; height: 460px; border: 1px solid rgb(255 255 255 / 18%); border-radius: 50%; box-shadow: 0 0 0 55px rgb(255 255 255 / 5%), 0 0 0 110px rgb(255 255 255 / 4%); }
.brand-mark { display: inline-grid; place-items: center; width: 42px; height: 42px; margin-right: 12px; vertical-align: middle; border-radius: 11px; font-weight: 800; background: #fff; color: #2863cf; }
.eyebrow { display: inline-block; margin: 0; vertical-align: middle; font-size: 11px; font-weight: 700; letter-spacing: .14em; opacity: .75; }
h1 { margin: 8px 0 0 56px; font-size: 22px; letter-spacing: .04em; }
.brand-copy { position: relative; z-index: 1; max-width: 390px; margin-top: 31vh; }
.brand-copy h2 { font-size: clamp(28px, 3vw, 44px); margin: 0 0 16px; letter-spacing: -.04em; }
.brand-copy p { max-width: 340px; color: rgb(255 255 255 / 78%); line-height: 1.8; }
.login-panel { display: grid; place-items: center; padding: 40px 24px; }
.login-card { width: min(100%, 420px); }
.kicker { margin: 0 0 9px; color: #2863cf; font-size: 12px; font-weight: 750; letter-spacing: .1em; }
.login-card h2 { margin: 0; font-size: 30px; letter-spacing: -.035em; }
.hint { margin: 12px 0 30px; color: #68738a; font-size: 14px; line-height: 1.7; }
label { display: block; margin-top: 17px; color: #3b4861; font-size: 13px; font-weight: 650; }
input { box-sizing: border-box; width: 100%; height: 46px; margin-top: 8px; padding: 0 13px; border: 1px solid #d9e0ec; border-radius: 9px; outline: none; color: #16233e; font: inherit; font-weight: 400; background: #fff; }
input:focus { border-color: #3974e0; box-shadow: 0 0 0 3px rgb(57 116 224 / 13%); }
.password-row { position: relative; }.password-row input { padding-right: 54px; }.text-button { position: absolute; right: 7px; bottom: 7px; border: 0; padding: 7px; color: #2863cf; background: transparent; cursor: pointer; }
.error { margin: 14px 0 0; color: #bf314c; font-size: 13px; }.submit { width: 100%; height: 48px; margin-top: 24px; border: 0; border-radius: 9px; color: #fff; font: inherit; font-weight: 700; background: #2863cf; cursor: pointer; }.submit:disabled { cursor: wait; opacity: .65; }
.security-note { margin: 23px 0 12px; color: #7a859a; font-size: 12px; line-height: 1.7; }.school-link { color: #2863cf; font-size: 13px; text-decoration: none; }
@media (max-width: 780px) { .platform-login { grid-template-columns: 1fr; }.brand-panel { min-height: 180px; padding: 28px; }.brand-copy { display: none; }.login-panel { padding: 46px 24px; } }
</style>
