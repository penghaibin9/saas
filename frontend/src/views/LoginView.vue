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
        <button class="lg-btn lg-btn--g" @click="enterDemo">进入演示环境</button>

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
      error: ''
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
        this.$router.push('/')
      } catch (e) {
        this.error = e.message || '登录失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    enterDemo() {
      this.$router.push('/')
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
