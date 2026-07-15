<template>
  <div class="lgx">
    <!-- 左：品牌区 -->
    <div class="lgx-brand">
      <div class="lgx-orb" />
      <div class="lgx-orb2" />
      <div class="lgx-badge">ENTERPRISE CAMPUS SAAS</div>
      <h1 class="lgx-title">校园通 · 高校学生全程管理平台</h1>
      <p class="lgx-slogan">一站式学生全生命周期数字化管理 · 教务 / 学工 / 实习 / 毕业设计全过程贯通</p>

      <div class="lgx-illust">
        <svg width="560" height="240" viewBox="0 0 560 240" fill="none" overflow="visible">
          <defs>
            <linearGradient id="bldA" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#7fd4ff" stop-opacity=".3" />
              <stop offset="100%" stop-color="#2f6bff" stop-opacity=".05" />
            </linearGradient>
            <linearGradient id="floorGlowA" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#4d8dff" stop-opacity=".38" />
              <stop offset="100%" stop-color="#4d8dff" stop-opacity="0" />
            </linearGradient>
            <radialGradient id="hudGlowA" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#bfe0ff" stop-opacity=".55" />
              <stop offset="100%" stop-color="#bfe0ff" stop-opacity="0" />
            </radialGradient>
          </defs>
          <rect x="40" y="150" width="480" height="90" fill="url(#floorGlowA)" />
          <g stroke="rgba(127,196,255,.22)" stroke-width="1">
            <line x1="50" y1="240" x2="300" y2="150" /><line x1="175" y1="240" x2="300" y2="150" />
            <line x1="300" y1="240" x2="300" y2="150" /><line x1="425" y1="240" x2="300" y2="150" />
            <line x1="550" y1="240" x2="300" y2="150" /><line x1="50" y1="240" x2="550" y2="240" />
            <line x1="95" y1="208" x2="505" y2="208" /><line x1="140" y1="182" x2="460" y2="182" />
            <line x1="180" y1="164" x2="420" y2="164" /><line x1="215" y1="152" x2="385" y2="152" />
          </g>
          <g stroke="#7fd4ff" stroke-width="1.3" fill="url(#bldA)">
            <polygon points="152,92 168,83 212,83 196,92" /><polygon points="196,92 212,83 212,141 196,150" />
            <rect x="152" y="92" width="44" height="58" />
            <polygon points="206,66 222,57 264,57 248,66" /><polygon points="248,66 264,57 264,141 248,150" />
            <rect x="206" y="66" width="42" height="84" />
            <polygon points="272,104 288,95 328,95 312,104" /><polygon points="312,104 328,95 328,141 312,150" />
            <rect x="272" y="104" width="40" height="46" />
            <polygon points="334,80 350,71 388,71 372,80" /><polygon points="372,80 388,71 388,141 372,150" />
            <rect x="334" y="80" width="38" height="70" />
          </g>
          <g fill="#bfe0ff">
            <rect class="win-dot" x="160" y="102" width="5" height="6" /><rect class="win-dot" x="172" y="102" width="5" height="6" />
            <rect class="win-dot" x="160" y="116" width="5" height="6" /><rect class="win-dot" x="184" y="116" width="5" height="6" />
            <rect class="win-dot" x="214" y="78" width="5" height="6" /><rect class="win-dot" x="226" y="78" width="5" height="6" />
            <rect class="win-dot" x="214" y="94" width="5" height="6" /><rect class="win-dot" x="238" y="94" width="5" height="6" />
            <rect class="win-dot" x="214" y="110" width="5" height="6" /><rect class="win-dot" x="238" y="110" width="5" height="6" />
            <rect class="win-dot" x="280" y="116" width="5" height="6" /><rect class="win-dot" x="298" y="116" width="5" height="6" />
            <rect class="win-dot" x="342" y="92" width="5" height="6" /><rect class="win-dot" x="358" y="92" width="5" height="6" />
            <rect class="win-dot" x="342" y="108" width="5" height="6" /><rect class="win-dot" x="358" y="122" width="5" height="6" />
          </g>
          <g class="flow-line" stroke="rgba(147,208,255,.65)" stroke-width="1.3">
            <path d="M227 57 C 320 20, 400 40, 470 74" /><path d="M353 71 C 400 50, 440 60, 470 74" />
          </g>
          <g>
            <circle cx="470" cy="74" r="52" fill="url(#hudGlowA)" />
            <circle class="hud-rot" cx="470" cy="74" r="42" fill="none" stroke="#7fd4ff" stroke-width="1.6" stroke-dasharray="30 14" stroke-opacity=".8" />
            <circle class="hud-rev" cx="470" cy="74" r="31" fill="none" stroke="#bfe0ff" stroke-width="1.2" stroke-dasharray="6 10" stroke-opacity=".65" />
            <circle cx="470" cy="74" r="16" fill="rgba(77,141,255,.25)" stroke="#bfe0ff" stroke-width="1.2" />
            <circle cx="470" cy="74" r="4" fill="#dff1ff" />
          </g>
          <g fill="#bfe0ff">
            <circle class="rise-dot" cx="230" cy="140" r="2.4" /><circle class="rise-dot" cx="290" cy="146" r="2" />
            <circle class="rise-dot" cx="350" cy="138" r="2.4" /><circle class="rise-dot" cx="180" cy="146" r="2" />
            <circle class="rise-dot" cx="400" cy="142" r="2.2" />
          </g>
        </svg>
      </div>

      <div class="lgx-trust">多租户隔离<b /> 等保合规<b /> 数据加密</div>
    </div>

    <!-- 右：登录卡 -->
    <div class="lgx-right">
      <div class="lgx-card">
        <div class="lgx-chd">
          <div class="lgx-logo">校</div>
          <div class="lgx-chd-tx">
            <b>校园通 · 高校学生全程管理平台</b>
            <i>企业级统一身份登录</i>
          </div>
        </div>

        <div class="lgx-tabs">
          <button class="lgx-tab" :class="{ on: tab === 'account' }" @click="switchTab('account')">账号登录</button>
          <button class="lgx-tab" :class="{ on: tab === 'sms' }" @click="switchTab('sms')">短信登录</button>
          <button class="lgx-tab" :class="{ on: tab === 'wechat' }" @click="switchTab('wechat')">微信扫码</button>
          <div class="lgx-underline" :style="{ transform: `translateX(${tabIndex * 100}%)` }" />
        </div>

        <!-- 账号登录（真实 /api/v1/auth/login） -->
        <template v-if="tab === 'account'">
          <label class="lgx-lb">学校编码 <span class="lgx-optional">可选</span></label>
          <input
            v-model.trim="form.tenantCode"
            class="lgx-in"
            placeholder="学校专属入口可自动带入；账号重名时填写"
            autocomplete="organization"
          />
          <label class="lgx-lb">账号</label>
          <input v-model.trim="form.loginName" class="lgx-in" placeholder="工号/手机号" @keyup.enter="doLogin" />
          <label class="lgx-lb">密码</label>
          <div class="lgx-field">
            <input
              v-model="form.password"
              :type="pwdVisible ? 'text' : 'password'"
              class="lgx-in lgx-in-pwd"
              placeholder="请输入密码"
              @keyup.enter="doLogin"
            />
            <button class="lgx-eye" type="button" @click="pwdVisible = !pwdVisible">
              <svg v-if="pwdVisible" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" />
              </svg>
              <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.4 5.4A9.6 9.6 0 0112 5c6.5 0 10 7 10 7a15 15 0 01-3.2 4M6.5 6.7C4 8.3 2 12 2 12a15.1 15.1 0 004.2 5" />
              </svg>
            </button>
          </div>
          <div class="lgx-row-between">
            <label class="lgx-chk-lb" @click="remember = !remember">
              <span class="lgx-chk" :class="{ on: remember }">
                <svg v-if="remember" viewBox="0 0 10 10" fill="none" stroke="#fff" stroke-width="1.6"><path d="M1.5 5l2.4 2.4L8.5 2.8" /></svg>
              </span>记住账号
            </label>
            <a class="lgx-link" @click="onForgot">忘记密码？</a>
          </div>
          <p v-if="error" class="lgx-err">{{ error }}</p>
          <button class="lgx-btn" :disabled="loading" @click="doLogin">
            <span v-if="loading" class="lgx-spin" />{{ loading ? '登录中…' : '登 录' }}
          </button>
        </template>

        <!-- 短信登录（后端短信通道尚未接入，占位） -->
        <template v-else-if="tab === 'sms'">
          <label class="lgx-lb">手机号</label>
          <div class="lgx-phone"><span class="lgx-phone-pre">+86</span><input v-model.trim="sms.phone" class="lgx-in" placeholder="请输入手机号" /></div>
          <label class="lgx-lb">验证码</label>
          <div class="lgx-code-row">
            <input v-model.trim="sms.code" class="lgx-in" placeholder="请输入验证码" />
            <button class="lgx-code-btn" :disabled="countdown > 0" @click="getCode">{{ countdown > 0 ? countdown + 's' : '获取验证码' }}</button>
          </div>
          <button class="lgx-btn" @click="notReady('短信登录')">登 录</button>
        </template>

        <!-- 微信扫码（后端微信通道尚未接入，占位） -->
        <template v-else>
          <div class="lgx-qr-wrap">
            <div class="lgx-qr-box">
              <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="#8494b5" stroke-width="1.4">
                <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 14h3v3M20 14v7M14 20h3" />
              </svg>
            </div>
            <p class="lgx-qr-tip">微信扫码登录即将开放，请使用账号登录</p>
          </div>
        </template>

        <div class="lgx-row-between lgx-agree">
          <label class="lgx-chk-lb" @click="agree = !agree">
            <span class="lgx-chk" :class="{ on: agree }">
              <svg v-if="agree" viewBox="0 0 10 10" fill="none" stroke="#fff" stroke-width="1.6"><path d="M1.5 5l2.4 2.4L8.5 2.8" /></svg>
            </span>我已阅读并同意<a class="lgx-link">《用户协议》</a>和<a class="lgx-link">《隐私政策》</a>
          </label>
        </div>

        <div class="lgx-divider" />
        <p class="lgx-foot">首次登录？请联系学校管理员开通账号 {{ trialPhone }}</p>
      </div>

      <div class="lgx-copyright">
        <div>技术支持：湖南跃科信息工程有限公司</div>
        <div>Copyright © 2026 · 湘ICP备XXXXXXXX号</div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * LoginView — 企业级统一身份登录页（对齐设计稿 docs/04-UI与全端交互/企业登录页.dc.html）。
 * 账号登录走真实 POST /api/v1/auth/login（后端 t_user + pbkdf2 校验）；短信/微信通道后端尚未接入，做诚实占位。
 * 不再展示任何演示账号。
 */
import { loginWithPassword } from '@/services/http/client'
import { toast } from '@/utils/toast'

export default {
  name: 'LoginView',
  data() {
    return {
      trialPhone: '13549666867',
      tab: 'account',
      pwdVisible: false,
      remember: true,
      agree: true,
      loading: false,
      error: '',
      form: { tenantCode: '', loginName: '', password: '' },
      sms: { phone: '', code: '' },
      countdown: 0,
      timerId: null
    }
  },
  computed: {
    tabIndex() {
      return this.tab === 'account' ? 0 : this.tab === 'sms' ? 1 : 2
    }
  },
  beforeUnmount() {
    if (this.timerId) clearInterval(this.timerId)
  },
  mounted() {
    const tenantCode = String(this.$route.query.tenant || '').trim()
    if (tenantCode) this.form.tenantCode = tenantCode
  },
  methods: {
    switchTab(t) {
      this.tab = t
      this.error = ''
    },
    async doLogin() {
      this.error = ''
      if (!this.form.loginName || !this.form.password) {
        this.error = '请输入账号与密码'
        return
      }
      this.loading = true
      try {
        const data = await loginWithPassword(
          this.form.loginName,
          this.form.password,
          this.form.tenantCode
        )
        toast.success(`欢迎，${data.displayName}（${data.currentRole.roleName}）`)
        this.$router.push(this.$route.query.redirect || '/')
      } catch (e) {
        this.error = e.message || '登录失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    getCode() {
      if (this.countdown > 0) return
      if (!/^1\d{10}$/.test(this.sms.phone)) {
        toast.info('请输入正确的手机号')
        return
      }
      this.notReady('短信登录')
      this.countdown = 60
      this.timerId = setInterval(() => {
        if (--this.countdown <= 0) clearInterval(this.timerId)
      }, 1000)
    },
    notReady(name) {
      toast.info(`${name}即将开放，请使用账号登录`)
    },
    onForgot() {
      toast.info(`请联系学校管理员重置密码：${this.trialPhone}`)
    }
  }
}
</script>

<style scoped>
.lgx {
  display: flex;
  height: 100vh;
  min-height: 600px;
  font-family: var(--font-family-base, system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif);
  color: #0f1e3d;
  background: #f7f9fc;
}

/* ===== 左品牌区 ===== */
.lgx-brand {
  flex: 0 0 55%;
  position: relative;
  overflow: hidden;
  color: #fff;
  background: linear-gradient(125deg, #0b2352 0%, #123a80 62%, #2f6bff 145%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 clamp(48px, 6vw, 108px);
}
.lgx-brand::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(147, 197, 253, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(147, 197, 253, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
}
.lgx-orb {
  position: absolute;
  right: -180px;
  top: -180px;
  width: 560px;
  height: 560px;
  border-radius: 50%;
  border: 1.5px dashed rgba(147, 197, 253, 0.22);
  animation: orbitSpin 80s linear infinite;
}
.lgx-orb2 {
  position: absolute;
  right: -80px;
  top: -80px;
  width: 380px;
  height: 380px;
  border-radius: 50%;
  border: 1px solid rgba(147, 197, 253, 0.14);
}
.lgx-badge {
  position: relative;
  display: inline-flex;
  width: fit-content;
  padding: 6px 16px;
  border-radius: 20px;
  background: rgba(147, 197, 253, 0.12);
  border: 1px solid rgba(147, 197, 253, 0.3);
  font-size: 13px;
  color: #bfdbfe;
  letter-spacing: 0.08em;
  margin-bottom: 28px;
}
.lgx-title {
  position: relative;
  margin: 0;
  font-size: clamp(30px, 3vw, 46px);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.28;
}
.lgx-slogan {
  position: relative;
  margin: 20px 0 0;
  font-size: clamp(15px, 1.1vw, 19px);
  color: rgba(191, 214, 255, 0.82);
  line-height: 1.7;
  max-width: 560px;
}
.lgx-illust {
  position: relative;
  margin-top: 40px;
  max-width: 560px;
}
.lgx-illust svg {
  width: 100%;
  height: auto;
}
.lgx-trust {
  position: relative;
  margin-top: 40px;
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 13px;
  color: rgba(191, 214, 255, 0.6);
}
.lgx-trust b {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(191, 214, 255, 0.4);
  display: inline-block;
}

/* 品牌区动效 */
.flow-line {
  stroke-dasharray: 6 6;
  animation: dashflow 1.6s linear infinite;
}
.hud-rot {
  transform-box: fill-box;
  transform-origin: center;
  animation: hudspin 9s linear infinite;
}
.hud-rev {
  transform-box: fill-box;
  transform-origin: center;
  animation: hudspin 14s linear infinite reverse;
}
.rise-dot {
  transform-box: fill-box;
  transform-origin: center;
  animation: rise 3.4s ease-out infinite;
}
.rise-dot:nth-child(2) { animation-delay: 0.7s; }
.rise-dot:nth-child(3) { animation-delay: 1.4s; }
.rise-dot:nth-child(4) { animation-delay: 2.1s; }
.rise-dot:nth-child(5) { animation-delay: 2.7s; }
.win-dot { animation: winFlick 3s ease-in-out infinite; }
.win-dot:nth-child(even) { animation-delay: 1.1s; }
.win-dot:nth-child(3n) { animation-delay: 1.9s; }
@keyframes dashflow { to { stroke-dashoffset: -24; } }
@keyframes hudspin { to { transform: rotate(360deg); } }
@keyframes rise { 0% { opacity: 0; transform: translateY(0); } 25% { opacity: 1; } 100% { opacity: 0; transform: translateY(-46px); } }
@keyframes winFlick { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
@keyframes orbitSpin { to { transform: rotate(360deg); } }
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== 右登录区 ===== */
.lgx-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  background: radial-gradient(700px 320px at 50% 0%, rgba(96, 165, 250, 0.1), transparent), #f7f9fc;
  padding: 32px;
}
.lgx-card {
  width: 400px;
  max-width: 100%;
  background: #fff;
  border-radius: 12px;
  border: 1px solid rgba(151, 173, 214, 0.28);
  box-shadow: 0 1px 3px rgba(15, 40, 90, 0.05), 0 20px 48px -24px rgba(15, 40, 90, 0.22);
  padding: 36px 36px 28px;
}
.lgx-chd {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 26px;
}
.lgx-logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #60a5fa, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
  box-shadow: 0 4px 12px -4px rgba(96, 165, 250, 0.5);
}
.lgx-chd-tx b {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: #0f1e3d;
}
.lgx-chd-tx i {
  font-style: normal;
  font-size: 11.5px;
  color: #8494b5;
}
.lgx-tabs {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid rgba(151, 173, 214, 0.28);
  margin-bottom: 24px;
}
.lgx-tab {
  text-align: center;
  padding: 0 0 12px;
  font-size: 13.5px;
  color: #8494b5;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s;
  background: none;
  border: none;
  font-family: inherit;
}
.lgx-tab.on {
  color: #0f1e3d;
  font-weight: 600;
}
.lgx-underline {
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 33.333%;
  height: 2px;
  background: #2563eb;
  border-radius: 2px;
  transition: transform 0.2s ease;
}
.lgx-lb {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #44567e;
  margin: 14px 0 6px;
}
.lgx-lb:first-of-type { margin-top: 0; }
.lgx-optional {
  margin-left: 4px;
  color: #8494b5;
  font-size: 11px;
  font-weight: 400;
}
.lgx-field { position: relative; }
.lgx-in {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid rgba(151, 173, 214, 0.32);
  border-radius: 9px;
  font-size: 13.5px;
  background: #fff;
  outline: none;
  transition: all 0.15s;
  color: #0f1e3d;
  box-sizing: border-box;
  font-family: inherit;
}
.lgx-in:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}
.lgx-in-pwd { padding-right: 40px; }
.lgx-eye {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  cursor: pointer;
  color: #8494b5;
  background: none;
  border: none;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.lgx-eye:hover { color: #44567e; }
.lgx-phone { display: flex; align-items: stretch; }
.lgx-phone-pre {
  display: flex;
  align-items: center;
  padding: 0 12px;
  border: 1px solid rgba(151, 173, 214, 0.32);
  border-right: none;
  border-radius: 9px 0 0 9px;
  font-size: 13.5px;
  color: #44567e;
  background: #f7f9fc;
  white-space: nowrap;
}
.lgx-phone .lgx-in { border-radius: 0 9px 9px 0; }
.lgx-code-row { display: flex; gap: 10px; }
.lgx-code-row .lgx-in { flex: 1; }
.lgx-code-btn {
  flex-shrink: 0;
  width: 118px;
  border-radius: 9px;
  border: 1px solid rgba(37, 99, 235, 0.3);
  background: #fff;
  color: #2563eb;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.lgx-code-btn:hover:not(:disabled) { background: rgba(37, 99, 235, 0.06); }
.lgx-code-btn:disabled { color: #c3cde0; border-color: #e5e9f0; cursor: not-allowed; }
.lgx-row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 0 4px;
  font-size: 12.5px;
}
.lgx-agree { margin-top: 18px; }
.lgx-chk-lb {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #44567e;
  cursor: pointer;
  user-select: none;
}
.lgx-chk {
  width: 14px;
  height: 14px;
  border: 1px solid #c3cde0;
  border-radius: 4px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  transition: all 0.15s;
}
.lgx-chk.on { background: #2563eb; border-color: #2563eb; }
.lgx-chk svg { width: 9px; height: 9px; }
.lgx-link {
  color: #2563eb;
  font-size: 12.5px;
  text-decoration: none;
  cursor: pointer;
}
.lgx-link:hover { text-decoration: underline; }
.lgx-err {
  margin: 12px 0 0;
  font-size: 12px;
  color: #dc2626;
}
.lgx-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  font-family: inherit;
  transition: all 0.15s;
  margin-top: 16px;
  color: #fff;
  background: linear-gradient(135deg, #60a5fa, #2563eb);
  box-shadow: 0 2px 10px -2px rgba(96, 165, 250, 0.5);
}
.lgx-btn:hover:not(:disabled) { background: linear-gradient(135deg, #2f6bff, #1d4ed8); }
.lgx-btn:disabled { opacity: 0.65; cursor: not-allowed; }
.lgx-spin {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  animation: spin 0.7s linear infinite;
}
.lgx-qr-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0 4px;
}
.lgx-qr-box {
  width: 200px;
  height: 200px;
  border-radius: 10px;
  background: #f7f9fc repeating-linear-gradient(45deg, #eef1f6 0 8px, #f7f9fc 8px 16px);
  border: 1px solid rgba(151, 173, 214, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
}
.lgx-qr-tip {
  margin-top: 14px;
  font-size: 12.5px;
  color: #44567e;
}
.lgx-divider {
  height: 1px;
  background: rgba(151, 173, 214, 0.24);
  margin: 22px 0 14px;
}
.lgx-foot {
  margin: 0;
  font-size: 12px;
  color: #8494b5;
  text-align: center;
  line-height: 1.6;
}
.lgx-copyright {
  text-align: center;
  font-size: 11px;
  line-height: 1.7;
  color: #94a3b8;
}

/* ===== 响应式：小屏隐藏品牌区 ===== */
@media (max-width: 900px) {
  .lgx-brand { display: none; }
  .lgx-right { flex: 1; }
}
</style>
