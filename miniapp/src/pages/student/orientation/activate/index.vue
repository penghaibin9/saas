<template>
  <view class="activate-page">
    <view class="nav"><text class="back" @click="back">‹</text><text>新生自助激活</text><text /></view>

    <view class="hero">
      <text class="hero__eyebrow">扫码即办 · 无需学校逐人开户</text>
      <text class="hero__title">核验录取身份，直接开始迎新</text>
      <text class="hero__desc">录取号和身份证后六位仅用于本次身份核验，系统不会在激活凭证中保存证件尾号。</text>
    </view>

    <view class="steps">
      <view v-for="(label, index) in stepLabels" :key="label" :class="{ on: step >= index + 1 }">
        <text>{{ step > index + 1 ? '✓' : index + 1 }}</text><small>{{ label }}</small>
      </view>
    </view>

    <view v-if="step === 1" class="card">
      <view v-if="form.tenantCode && !editingTenant" class="school-chip">
        <view><small>已识别学校</small><strong>{{ form.tenantCode }}</strong></view>
        <text @click="editingTenant = true">更换</text>
      </view>
      <template v-else>
        <text class="field-label">学校代码</text>
        <input v-model.trim="form.tenantCode" class="field" placeholder="扫码后通常会自动带入" />
      </template>
      <text class="field-label">录取号</text>
      <input v-model.trim="form.admissionNo" class="field" maxlength="50" placeholder="请输入录取通知书上的录取号" />
      <text class="field-label">身份证后六位</text>
      <input v-model.trim="form.idCardLast6" class="field code-field" maxlength="6" placeholder="末位 X 可输入字母" />
      <view class="agreement" @click="agreed = !agreed">
        <text class="check" :class="{ checked: agreed }">{{ agreed ? '✓' : '' }}</text>
        <text>我确认由本人办理，并同意学校核验本次录取身份</text>
      </view>
      <button class="primary" :disabled="loading" @click="verifyIdentity">{{ loading ? '正在核验…' : '核验录取身份' }}</button>
      <text class="safe-note">连续输错将暂时限制核验，学校和其他学生无法查看你填写的证件尾号。</text>
    </view>

    <view v-else-if="step === 2" class="card">
      <view class="success-mark">✓</view>
      <text class="result-title">录取身份核验通过</text>
      <view class="candidate-grid">
        <view><small>姓名</small><strong>{{ candidate.name }}</strong></view>
        <view><small>学号</small><strong>{{ candidate.studentNo }}</strong></view>
        <view><small>录取号</small><strong>{{ candidate.admissionNo }}</strong></view>
        <view><small>院系专业</small><strong>{{ candidate.collegeName }} · {{ candidate.majorName }}</strong></view>
        <view><small>班级</small><strong>{{ candidate.className || '待学校确认' }}</strong></view>
        <view><small>迎新批次</small><strong>{{ candidate.batchName }}</strong></view>
      </view>
      <button class="primary" @click="step = 3">信息无误，设置登录密码</button>
      <button class="secondary" @click="restart">信息有误，返回重填</button>
    </view>

    <view v-else class="card">
      <text class="result-title left">设置你的登录密码</text>
      <text class="result-desc">以后可使用学号 {{ candidate.studentNo }} 登录；微信绑定成功后可直接一键登录。</text>
      <text class="field-label">登录密码</text>
      <input v-model="form.password" class="field" type="password" password maxlength="128" placeholder="至少 8 位" />
      <text class="field-label">再次输入密码</text>
      <input v-model="form.confirmPassword" class="field" type="password" password maxlength="128" placeholder="请再次输入" />
      <view class="wx-status" :class="{ ready: wxReady }">
        <text>{{ wxPreparing ? '…' : (wxReady ? '✓' : '!') }}</text>
        <view><strong>{{ wxReady ? wxReadyText : '微信身份尚未就绪' }}</strong><small>{{ wxStatusText }}</small></view>
      </view>
      <button class="primary" :disabled="loading || wxPreparing" @click="completeActivation">{{ loading ? '正在开通…' : '激活并进入迎新' }}</button>
      <text class="safe-note">账号、学生主档和微信绑定一次完成；重复点击不会重复创建账号。</text>
    </view>
  </view>
</template>

<script>
import { roleKeyFromBackendRole } from '@/config'
import { studentApi } from '@/services/studentApi'
import { commitNewSessionTokens, realRequest } from '@/services/request'
import { useSessionStore } from '@/stores/session'
import { getLastTenantCode, saveLastTenantCode } from '@/utils/tenantPreference'
import { decodeQueryText, relaunch, toast } from '@/utils/nav'

function requestId() {
  return `orientation-activate-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function sceneTenant(scene) {
  const value = decodeQueryText(scene).trim()
  if (!value) return ''
  const pair = value.split('&').find((item) => /^(tenant|tenantCode)=/.test(item))
  return pair ? pair.split('=').slice(1).join('=') : value
}

export default {
  data() {
    return {
      step: 1,
      stepLabels: ['身份核验', '确认信息', '设置密码'],
      editingTenant: false,
      agreed: false,
      loading: false,
      wxPreparing: false,
      wxReady: false,
      wxToken: '',
      activationToken: '',
      candidate: {},
      nonce: `orientation-activation-${Date.now()}-${Math.random()}`,
      clientRequestId: requestId(),
      form: {
        tenantCode: getLastTenantCode(), admissionNo: '', idCardLast6: '',
        password: '', confirmPassword: ''
      }
    }
  },
  computed: {
    wxReadyText() {
      // #ifdef MP-WEIXIN
      return '激活后自动绑定当前微信'
      // #endif
      // #ifndef MP-WEIXIN
      return '本地体验环境已就绪'
      // #endif
    },
    wxStatusText() {
      // #ifdef MP-WEIXIN
      return this.wxReady ? '以后可微信一键登录，无需重复输入密码' : '请检查网络后重试'
      // #endif
      // #ifndef MP-WEIXIN
      return '正式微信小程序中会自动绑定当前微信'
      // #endif
    }
  },
  onLoad(options) {
    const tenant = String(options?.tenantCode || options?.tenant || sceneTenant(options?.scene) || '').trim()
    if (tenant) {
      this.form.tenantCode = tenant
      saveLastTenantCode(tenant)
    }
    this.prepareWechat()
  },
  methods: {
    back() { uni.navigateBack({ fail: () => relaunch('/pages/login/student/index') }) },
    prepareWechat() {
      // #ifdef MP-WEIXIN
      this.wxPreparing = true
      uni.login({
        provider: 'weixin',
        success: ({ code }) => {
          if (!code) { this.wxPreparing = false; return }
          realRequest('/auth/wx-login', { method: 'POST', auth: false, data: { code, bindAnother: true } })
            .then((data) => { this.wxToken = data.wxToken || ''; this.wxReady = !!this.wxToken })
            .catch((e) => toast(e?.message || '微信身份获取失败，请重试'))
            .finally(() => { this.wxPreparing = false })
        },
        fail: () => { this.wxPreparing = false; toast('微信身份获取失败，请重试') }
      })
      // #endif
      // #ifndef MP-WEIXIN
      this.wxReady = true
      // #endif
    },
    async verifyIdentity() {
      if (!this.agreed) { toast('请先确认由本人办理'); return }
      if (!this.form.tenantCode || !this.form.admissionNo || !/^[0-9Xx]{6}$/.test(this.form.idCardLast6)) {
        toast('请完整填写学校代码、录取号和身份证后六位'); return
      }
      this.loading = true
      try {
        const data = await realRequest('/auth/orientation-activation/verify', {
          method: 'POST', auth: false, data: {
            tenantCode: this.form.tenantCode.trim(), admissionNo: this.form.admissionNo.trim(),
            idCardLast6: this.form.idCardLast6.trim().toUpperCase(), clientNonce: this.nonce
          }
        })
        saveLastTenantCode(this.form.tenantCode)
        this.activationToken = data.activationToken
        this.candidate = data.candidate || {}
        this.step = 2
      } catch (e) {
        if (e?.details?.alreadyActivated) {
          toast(`该账号已激活，请使用 ${e.details.loginName || '学号'} 登录`)
          setTimeout(() => relaunch('/pages/login/student/index'), 900)
        } else toast(e?.message || '录取身份核验失败')
      } finally { this.loading = false }
    },
    restart() {
      this.step = 1
      this.activationToken = ''
      this.candidate = {}
      this.form.idCardLast6 = ''
      this.form.password = ''
      this.form.confirmPassword = ''
      this.clientRequestId = requestId()
    },
    async completeActivation() {
      if (this.form.password.length < 8) { toast('密码至少 8 位'); return }
      if (this.form.password !== this.form.confirmPassword) { toast('两次输入的密码不一致'); return }
      // #ifdef MP-WEIXIN
      if (!this.wxToken) { toast('微信身份尚未就绪，请稍后重试'); this.prepareWechat(); return }
      // #endif
      this.loading = true
      try {
        let clientType = 'STUDENT_H5'
        // #ifdef MP-WEIXIN
        clientType = 'STUDENT_MINI'
        // #endif
        const data = await realRequest('/auth/orientation-activation/complete', {
          method: 'POST', auth: false, data: {
            activationToken: this.activationToken, clientNonce: this.nonce,
            newPassword: this.form.password, confirmPassword: this.form.confirmPassword,
            wxToken: this.wxToken || undefined, clientRequestId: this.clientRequestId,
            clientType
          }
        })
        const roleCode = data.currentRole?.roleCode || 'STUDENT'
        const roleKey = roleKeyFromBackendRole(roleCode)
        if (!roleKey) throw new Error('学生角色未配置，请联系学校管理员')
        commitNewSessionTokens(data.accessToken, data.refreshToken || '')
        const session = useSessionStore()
        await session.login(roleKey, { skipRealLogin: true })
        session.applyRealUser(data)
        try {
          const profile = await studentApi.getProfile()
          session.hydrateStudentProfile(profile)
        } catch (_) { /* 首页会再次加载本人档案 */ }
        toast('账号激活成功，正在进入迎新')
        setTimeout(() => relaunch('/pages/student/orientation/index'), 500)
      } catch (e) {
        toast(e?.message || '账号激活失败，请稍后重试')
      } finally { this.loading = false }
    }
  }
}
</script>

<style scoped>
.activate-page{min-height:100vh;padding-bottom:calc(34rpx + env(safe-area-inset-bottom));color:#10233f;background:linear-gradient(180deg,#eaf8f5 0,#f4f7fb 38%)}
.nav{display:grid;grid-template-columns:70rpx 1fr 70rpx;align-items:center;padding:calc(22rpx + env(safe-area-inset-top)) 28rpx 18rpx;text-align:center;font-size:30rpx;font-weight:650}.back{font-size:56rpx;font-weight:300;text-align:left}
.hero{padding:28rpx 34rpx 36rpx}.hero text{display:block}.hero__eyebrow{color:#0f766e;font-size:20rpx;font-weight:700;letter-spacing:2rpx}.hero__title{margin-top:13rpx;font-size:40rpx;font-weight:750;line-height:1.35}.hero__desc{margin-top:14rpx;color:#60738a;font-size:23rpx;line-height:1.7}
.steps{display:grid;grid-template-columns:repeat(3,1fr);margin:0 28rpx 24rpx}.steps view{position:relative;display:flex;flex-direction:column;align-items:center;gap:8rpx;color:#94a3b8}.steps view:not(:last-child)::after{content:'';position:absolute;left:65%;right:-35%;top:21rpx;height:2rpx;background:#dbe4eb}.steps view.on:not(:last-child)::after{background:#62b8ac}.steps text{display:grid;place-items:center;width:42rpx;height:42rpx;border-radius:50%;background:#e2e8f0;font-size:20rpx}.steps .on text{color:#fff;background:#15948b}.steps small{font-size:20rpx}.steps .on small{color:#0f766e;font-weight:650}
.card{margin:0 28rpx;padding:34rpx 30rpx;border:1rpx solid #e1e8ef;border-radius:30rpx;background:#fff;box-shadow:0 26rpx 70rpx -48rpx rgba(16,35,63,.45)}
.school-chip{display:flex;align-items:center;justify-content:space-between;padding:20rpx 22rpx;border-radius:18rpx;background:#effaf7}.school-chip view{display:flex;flex-direction:column;gap:4rpx}.school-chip small{color:#718096;font-size:20rpx}.school-chip strong{font-size:26rpx}.school-chip>text{color:#0f766e;font-size:22rpx}
.field-label{display:block;margin-top:25rpx;color:#40536d;font-size:23rpx;font-weight:650}.field{box-sizing:border-box;width:100%;height:92rpx;margin-top:11rpx;padding:0 24rpx;border:1rpx solid #d9e3eb;border-radius:18rpx;background:#f9fbfd;font-size:27rpx}.code-field{letter-spacing:8rpx}
.agreement{display:flex;align-items:flex-start;gap:13rpx;margin-top:25rpx;color:#66788e;font-size:21rpx;line-height:1.55}.check{flex:none;display:grid;place-items:center;width:30rpx;height:30rpx;border:1rpx solid #ccd7e1;border-radius:7rpx;color:#fff}.check.checked{border-color:#15948b;background:#15948b}
.primary,.secondary{display:flex;align-items:center;justify-content:center;height:92rpx;margin-top:30rpx;border:0;border-radius:19rpx;font-size:27rpx}.primary{color:#fff;background:linear-gradient(135deg,#15948b,#0f766e);font-weight:700}.primary[disabled]{opacity:.62}.secondary{margin-top:16rpx;border:1rpx solid #ccd7e4;color:#40536d;background:#fff}.safe-note{display:block;margin-top:19rpx;color:#8a98a9;font-size:20rpx;line-height:1.6;text-align:center}
.success-mark{display:grid;place-items:center;width:78rpx;height:78rpx;margin:0 auto;border-radius:50%;color:#fff;background:#15948b;font-size:40rpx}.result-title{display:block;margin-top:19rpx;text-align:center;font-size:34rpx;font-weight:750}.result-title.left{text-align:left}.result-desc{display:block;margin-top:12rpx;color:#718096;font-size:23rpx;line-height:1.65}.candidate-grid{display:grid;gap:0;margin-top:28rpx;border-top:1rpx solid #edf1f5}.candidate-grid view{display:grid;grid-template-columns:150rpx 1fr;gap:16rpx;padding:20rpx 4rpx;border-bottom:1rpx solid #edf1f5}.candidate-grid small{color:#8795a7;font-size:21rpx}.candidate-grid strong{text-align:right;font-size:23rpx;font-weight:600}
.wx-status{display:flex;align-items:center;gap:16rpx;margin-top:26rpx;padding:19rpx 20rpx;border-radius:17rpx;background:#fff7ed}.wx-status>text{display:grid;place-items:center;width:38rpx;height:38rpx;border-radius:50%;color:#fff;background:#f59e0b}.wx-status view{display:flex;flex-direction:column;gap:4rpx}.wx-status strong{font-size:23rpx}.wx-status small{color:#7c8999;font-size:19rpx}.wx-status.ready{background:#effaf7}.wx-status.ready>text{background:#15948b}
</style>
