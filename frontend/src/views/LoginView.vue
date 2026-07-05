<template>
  <div class="lg thw th-a">
    <!-- 左：品牌区（母版 lg-l） -->
    <div class="lg-l">
      <div class="lg-orb" />
      <div class="lg-orb2" />
      <div class="lg-badge">FUTURE CAMPUS SAAS</div>
      <div class="lg-tt">高校学生全生命周期管理平台</div>
      <div class="lg-sub">从招生、迎新、在校培养、岗位实习、毕业设计到就业落实，一条学生成长轨道贯穿始终。</div>
      <div class="lg-feats">
        <span class="lg-ft">角色感知</span>
        <span class="lg-ft">数据范围清晰</span>
        <span class="lg-ft">隐私脱敏与审计留痕</span>
      </div>

      <!-- 演示账号（放品牌区空位，不占登录卡；点击填入右侧表单，仍需真实登录） -->
      <div class="lg-demo">
        <div class="lg-demo__group">
          <div class="lg-demo__tt">正式演示 · 演示职业技术学校<span class="lg-demo__tag">数据只读</span></div>
          <div class="lg-demo__row" v-for="a in demoAccounts" :key="a.login" @click="fillDemo(a)">
            <span class="lg-demo__role">{{ a.role }}</span>
            <b class="lg-demo__login">{{ a.login }}</b>
            <span class="lg-demo__pwd">{{ demoPassword }}</span>
            <button class="lg-demo__copy" @click.stop="copyText(a.login)">复制账号</button>
            <button class="lg-demo__copy" @click.stop="copyText(demoPassword)">复制密码</button>
          </div>
        </div>
        <div class="lg-demo__group">
          <div class="lg-demo__tt">自由体验 · 体验沙箱学校<span class="lg-demo__tag lg-demo__tag--warn">随便操作 · 每晚 0 点重置</span></div>
          <div class="lg-demo__row" v-for="a in sandboxAccounts" :key="a.login" @click="fillDemo(a)">
            <span class="lg-demo__role">{{ a.role }}</span>
            <b class="lg-demo__login">{{ a.login }}</b>
            <span class="lg-demo__pwd">{{ demoPassword }}</span>
            <button class="lg-demo__copy" @click.stop="copyText(a.login)">复制账号</button>
            <button class="lg-demo__copy" @click.stop="copyText(demoPassword)">复制密码</button>
          </div>
        </div>
        <div class="lg-demo__tip">点击账号自动填入右侧表单，仍需点「登 录」；学生端请在手机 H5/小程序使用 student / student2（密码同 123456）</div>
      </div>
    </div>
    <!-- 右：登录卡 -->
    <div class="lg-r">
      <div class="lg-c">
        <div class="lg-head">
          <span class="lg-logo">校</span>
          <span class="lg-head__tx">
            <b>高校学生全生命周期管理平台</b>
            <i>教职工统一身份登录</i>
          </span>
        </div>

        <label class="in-lb">账号</label>
        <input v-model.trim="form.loginName" class="in" placeholder="请输入账号" @keyup.enter="doLogin" />
        <label class="in-lb">密码</label>
        <input v-model="form.password" class="in" type="password" placeholder="请输入密码" @keyup.enter="doLogin" />
        <p v-if="error" class="lg-err">{{ error }}</p>

        <button class="lg-btn lg-btn--p" :disabled="loading" @click="doLogin">
          {{ loading ? '登录中…' : '登 录' }}
        </button>

        <!-- 小屏（左侧品牌区隐藏时）给一行演示账号提示，保证可发现 -->
        <div class="lg-demo-mini">
          演示：admin · teacher（只读）｜沙箱：admin2 · teacher2（可随便点）密码均 123456
        </div>

        <!-- 试用咨询（可公开电话，不含任何账号密码） -->
        <div class="lg-trial">
          <div class="lg-trial__tt">想为学校开通正式试用？</div>
          <div class="lg-trial__ph">
            请联系平台服务顾问：<b>{{ trialPhone }}</b>
          </div>
          <div class="lg-trial__ops">
            <button class="lg-btn--mini" @click="copyPhone">复制手机号</button>
            <a class="lg-btn--mini lg-btn--tel" :href="'tel:' + trialPhone">拨打电话</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * LoginView — PC 登录页（母版 00-基准 登录屏）。
 * 账号密码走 POST /api/v1/auth/login（后端 t_user + pbkdf2 校验，不展示任何演示密码）；
 * 「进入演示环境」保持原 mock 工作台入口，不影响既有演示流程。
 */
import { loginWithPassword } from '@/services/http/client'
import { toast } from '@/utils/toast'

export default {
  name: 'LoginView',
  data() {
    return {
      trialPhone: '13549666867',
      form: { loginName: '', password: '' },
      loading: false,
      error: '',
      demoPassword: '123456',
      demoAccounts: [
        { role: '管理员', login: 'admin' },
        { role: '教师', login: 'teacher' }
      ],
      sandboxAccounts: [
        { role: '管理员', login: 'admin2' },
        { role: '教师', login: 'teacher2' }
      ]
    }
  },
  methods: {
    async doLogin() {
      this.error = ''
      if (!this.form.loginName || !this.form.password) {
        this.error = '请输入账号与密码'
        return
      }
      this.loading = true
      try {
        const data = await loginWithPassword(this.form.loginName, this.form.password)
        toast.success(`欢迎，${data.displayName}（${data.currentRole.roleName}）`)
        this.$router.push(this.$route.query.redirect || '/')
      } catch (e) {
        this.error = e.message || '登录失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    /** 点演示账号仅自动填入表单——不绕过登录，仍需点「登 录」走真实 /auth/login */
    fillDemo(a) {
      this.form.loginName = a.login
      this.form.password = this.demoPassword
      this.error = ''
    },
    async copyText(text) {
      try {
        await navigator.clipboard.writeText(text)
        toast.success('已复制')
      } catch {
        toast.info(text)
      }
    },
    async copyPhone() {
      try {
        await navigator.clipboard.writeText(this.trialPhone)
        toast.success('手机号已复制')
      } catch {
        toast.info(this.trialPhone)
      }
    }
  }
}
</script>

<style scoped>
.lg {
  display: flex;
  height: 100vh;
  font-family: var(--font-family-base);
  color: var(--t1);
}
/* 左品牌区（母版 .lg-l） */
.lg-l {
  flex: 1.25;
  background: linear-gradient(125deg, var(--deep1) 0%, var(--deep2) 65%, var(--g2) 145%);
  color: #fff;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 64px;
}
.lg-l::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(147, 197, 253, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(147, 197, 253, 0.05) 1px, transparent 1px);
  background-size: 32px 32px;
}
.lg-orb {
  position: absolute;
  right: -130px;
  top: -130px;
  width: 440px;
  height: 440px;
  border-radius: 50%;
  border: 1.5px dashed rgba(147, 197, 253, 0.22);
  animation: orbitSpin 70s linear infinite;
}
.lg-orb2 {
  position: absolute;
  right: -60px;
  top: -60px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  border: 1px solid rgba(147, 197, 253, 0.14);
}
.lg-badge {
  display: inline-flex;
  padding: 5px 14px;
  border-radius: 18px;
  background: rgba(147, 197, 253, 0.12);
  border: 1px solid rgba(147, 197, 253, 0.3);
  font-size: 11.5px;
  color: #bfdbfe;
  width: fit-content;
  margin-bottom: 22px;
  position: relative;
  letter-spacing: 0.06em;
}
.lg-tt {
  font-size: 34px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.02em;
  line-height: 1.3;
  position: relative;
}
.lg-sub {
  font-size: 14px;
  color: rgba(191, 214, 255, 0.75);
  margin-top: 14px;
  max-width: 440px;
  position: relative;
  line-height: 1.7;
}
.lg-feats {
  display: flex;
  gap: 20px;
  margin-top: 36px;
  position: relative;
  flex-wrap: wrap;
}
.lg-ft {
  font-size: 12px;
  color: rgba(219, 234, 254, 0.75);
}
/* 右登录卡（母版 .lg-r / .lg-c / .in） */
.lg-r {
  width: 480px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(700px 300px at 50% 0%, rgba(96, 165, 250, 0.12), transparent),
    linear-gradient(rgba(37, 99, 235, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(37, 99, 235, 0.03) 1px, transparent 1px),
    var(--bg);
  background-size:
    auto,
    32px 32px,
    32px 32px,
    auto;
  padding: 32px;
}
.lg-c {
  width: 100%;
  max-width: 364px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px);
  border: 1px solid var(--card-b);
  border-radius: 18px;
  padding: 28px;
  box-shadow: var(--s2);
}
.lg-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.lg-logo {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--btn-p-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: var(--font-weight-bold);
  font-size: 13px;
  flex-shrink: 0;
  box-shadow: 0 4px 12px -4px var(--glow);
}
.lg-head__tx {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}
.lg-head__tx b {
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lg-head__tx i {
  font-style: normal;
  font-size: 11px;
  color: var(--t3);
}
.in-lb {
  display: block;
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  color: var(--t2);
  margin: 12px 0 6px;
}
.in {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid var(--card-b);
  border-radius: 10px;
  font-family: inherit;
  font-size: 13px;
  background: #fff;
  outline: none;
  transition: all 0.12s;
  color: var(--t1);
  box-sizing: border-box;
}
.in:focus {
  border-color: var(--pri);
  box-shadow: 0 0 0 3px var(--pri-bg);
}
.lg-err {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--err);
}
.lg-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 11px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  border: 1px solid transparent;
  font-family: inherit;
  transition: all 0.12s;
  margin-top: 14px;
}
.lg-btn--p {
  background: var(--btn-p-bg);
  color: #fff;
  box-shadow: var(--btn-p-shadow);
}
.lg-btn--p:hover:not(:disabled) {
  background: var(--btn-p-bg-h);
}
.lg-btn--p:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.lg-btn--g {
  background: rgba(255, 255, 255, 0.85);
  border-color: var(--card-b);
  color: var(--t2);
  margin-top: 10px;
}
.lg-btn--g:hover {
  color: var(--pri);
  border-color: var(--glow);
}
/* 演示账号区（左侧品牌区暗底样式，不占登录卡） */
.lg-demo {
  position: relative;
  margin-top: 40px;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lg-demo__group {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(147, 197, 253, 0.22);
  backdrop-filter: blur(6px);
}
.lg-demo__tt {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: var(--font-weight-semibold);
  color: #dbeafe;
  margin-bottom: 6px;
}
.lg-demo__tag {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(147, 197, 253, 0.16);
  border: 1px solid rgba(147, 197, 253, 0.35);
  color: #bfdbfe;
  font-weight: normal;
}
.lg-demo__tag--warn {
  background: rgba(251, 191, 36, 0.14);
  border-color: rgba(251, 191, 36, 0.4);
  color: #fde68a;
}
.lg-demo__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.lg-demo__row:hover {
  background: rgba(147, 197, 253, 0.12);
}
.lg-demo__role {
  font-size: 11.5px;
  color: rgba(191, 214, 255, 0.75);
  width: 44px;
  flex-shrink: 0;
}
.lg-demo__login {
  font-size: 12.5px;
  color: #93c5fd;
  font-family: var(--font-family-mono, monospace);
}
.lg-demo__pwd {
  margin-left: auto;
  font-size: 11.5px;
  color: rgba(191, 214, 255, 0.7);
  font-variant-numeric: tabular-nums;
}
.lg-demo__copy {
  font-size: 10.5px;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid rgba(147, 197, 253, 0.35);
  background: transparent;
  color: #bfdbfe;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
}
.lg-demo__copy:hover {
  background: rgba(147, 197, 253, 0.16);
  border-color: #93c5fd;
}
.lg-demo__tip {
  font-size: 11px;
  color: rgba(191, 214, 255, 0.6);
  line-height: 1.6;
}
/* 小屏提示（左侧品牌区隐藏时可见） */
.lg-demo-mini {
  display: none;
  margin-top: 12px;
  font-size: 11px;
  color: var(--t3);
  line-height: 1.6;
  text-align: center;
}
@media (max-width: 900px) {
  .lg-demo-mini {
    display: block;
  }
}
/* 试用咨询（克制的蓝白样式，非广告位） */
.lg-trial {
  margin-top: 18px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
}
.lg-trial__tt {
  font-size: 12.5px;
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
}
.lg-trial__ph {
  margin-top: 4px;
  font-size: 12px;
  color: var(--t2);
}
.lg-trial__ph b {
  color: var(--pri);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}
.lg-trial__ops {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.lg-btn--mini {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 7px 0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  border: 1px solid var(--pri-100);
  background: #fff;
  color: var(--pri);
  font-family: inherit;
  text-decoration: none;
  transition: all 0.12s;
}
.lg-btn--mini:hover {
  border-color: var(--pri);
  box-shadow: 0 0 0 3px var(--pri-bg);
}
@media (max-width: 900px) {
  .lg-l {
    display: none;
  }
  .lg-r {
    width: 100%;
  }
}
</style>
