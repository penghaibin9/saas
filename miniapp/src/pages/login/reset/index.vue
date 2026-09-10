<template>
  <view class="page">
    <view class="nav"><text class="back" @click="back">‹</text><text>短信重置密码</text><text /></view>
    <view class="card">
      <text class="eyebrow">{{ isTeacher ? '教师自助找回' : '学生自助找回' }}</text>
      <text class="title">{{ titles[step - 1] }}</text>
      <text class="desc">仅支持本人已验证的独立登录手机号。联系方式、家长号码和 Excel 登记号码不能直接找回密码；不符合条件请联系学校独立核验。</text>
      <view class="steps"><text v-for="i in 3" :key="i" :class="{ on: step >= i }">{{ i }}</text></view>

      <view v-if="step === 1">
        <picker :range="['已验证手机号', '原学号 / 工号 / 账号']" :disabled="loading" @change="changeType"><view class="field">{{ form.identifierType === 'PHONE' ? '已验证手机号' : '原学号 / 工号 / 账号' }} · 切换</view></picker>
        <input v-model="form.loginName" :disabled="loading" class="field" :placeholder="form.identifierType === 'PHONE' ? '本人已验证手机号' : (isTeacher ? '工号 / 登录账号' : '学号 / 登录账号')" />
        <input v-model="form.tenantCode" :disabled="loading" class="field" placeholder="学校编码（多校同账号时填写）" />
        <view class="captcha-row">
          <input v-model="captcha.code" class="field captcha-input" type="number" maxlength="6" placeholder="图形验证码" />
          <image class="captcha-image" :src="captcha.image" mode="aspectFill" @click="loadCaptcha" />
        </view>
        <button class="primary" :disabled="loading" @click="requestCode">{{ loading ? '发送中…' : '发送短信验证码' }}</button>
      </view>

      <view v-else-if="step === 2">
        <input v-model="form.smsCode" class="field code" type="number" maxlength="6" placeholder="6 位短信验证码" />
        <text class="note">若账号存在且已绑定手机号，短信会在几分钟内送达。</text>
        <button class="primary" :disabled="loading" @click="verifyCode">{{ loading ? '验证中…' : '验证并继续' }}</button>
        <button class="secondary" :disabled="countdown > 0 || loading" @click="restart">{{ countdown > 0 ? `${countdown} 秒后可重新发送` : '重新获取验证码' }}</button>
        <view class="fallback"><text>一直收不到？</text><text>先确认本人{{ isTeacher ? '工号' : '学号' }}和档案手机号；多次尝试仍失败，再联系学校管理员人工核验。</text></view>
      </view>

      <view v-else-if="step === 3">
        <input v-model="form.newPassword" class="field" type="password" password maxlength="128" placeholder="新密码（至少 8 位）" />
        <input v-model="form.confirmPassword" class="field" type="password" password maxlength="128" placeholder="再次输入新密码" />
        <text class="note">成功后其他设备上的旧登录会失效，请使用新密码重新登录。</text>
        <button class="primary" :disabled="loading" @click="confirmReset">{{ loading ? '重置中…' : '确认重置密码' }}</button>
      </view>
      <view v-else>
        <text class="note">{{ state.note }}</text>
        <button v-if="step === 4" class="primary" :disabled="loading" @click="checkResult">查询原重置结果</button>
        <button v-else class="primary" @click="back">返回登录</button>
      </view>
      <text v-if="state.error" class="note" role="alert">{{ state.error }}</text>
    </view>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { getLastTenantCode } from '@/utils/tenantPreference'
import { createResetFlow, resetFlowState } from '../../../../../shared/passwordResetFlow.mjs'

export default {
  data() {
    return { entry: 'student', state: resetFlowState({ tenantCode: getLastTenantCode() }),
      titles: ['验证本人账号', '输入短信验证码', '设置新密码', '查询办理结果', '密码已重置'] }
  },
  computed: {
    isTeacher() { return this.entry === 'teacher' },
    step() { return this.state.step }, loading() { return this.state.loading },
    form() { return this.state.form }, captcha() { return this.state.captcha }, countdown() { return this.state.countdown }
  },
  watch: {
    'state.form.loginName'() { this.flow?.identityChanged() },
    'state.form.tenantCode'() { this.flow?.identityChanged() },
    'state.form.identifierType'() { this.flow?.identityChanged() }
  },
  onLoad(options) {
    this.entry = options?.entry === 'teacher' ? 'teacher' : 'student'
    this.state.form.identifierType = options?.identifierType === 'PHONE' ? 'PHONE' : 'ACCOUNT'
  },
  onShow() {
    this.flow?.dispose()
    this.state = resetFlowState({ tenantCode: getLastTenantCode(), identifierType: this.state.form.identifierType })
    this.flow = createResetFlow(this.state, {
      request: (path, options) => realRequest(path, { method: options.method, auth: false, data: options.body }),
      clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI'
    })
    this.timer = setInterval(() => this.flow.tick(), 1000)
  },
  onHide() { this.clearFlow() },
  onUnload() { this.clearFlow() },
  methods: {
    clearFlow() { clearInterval(this.timer); this.flow?.dispose() },
    loginPage() { return this.isTeacher ? '/pages/login/teacher/index' : '/pages/login/student/index' },
    back() { uni.navigateBack({ fail: () => uni.reLaunch({ url: this.loginPage() }) }) },
    loadCaptcha() { return this.flow.loadCaptcha() },
    requestCode() { return this.flow.requestCode() },
    verifyCode() { return this.flow.verifyCode() },
    confirmReset() { return this.flow.confirmReset() },
    restart() { return this.flow.restart() },
    checkResult() { return this.flow.checkResult() },
    changeType(event) { this.form.identifierType = Number(event.detail.value) === 0 ? 'PHONE' : 'ACCOUNT' }
  }
}
</script>

<style scoped>
.page{min-height:100vh;padding-bottom:calc(30rpx + env(safe-area-inset-bottom));color:#10233f;background:linear-gradient(180deg,#eaf8f5,#f4f7fb 36%)}.nav{display:grid;grid-template-columns:60rpx 1fr 60rpx;align-items:center;padding:calc(24rpx + env(safe-area-inset-top)) 28rpx 24rpx;text-align:center;font-size:30rpx;font-weight:650}.back{font-size:54rpx;font-weight:300;text-align:left}.card{margin:24rpx 28rpx;padding:42rpx 34rpx;border:1rpx solid #e2e8f0;border-radius:36rpx;background:#fff;box-shadow:0 28rpx 70rpx -45rpx rgba(16,35,63,.4)}.eyebrow,.title,.desc,.note{display:block}.eyebrow{color:#0f766e;font-size:20rpx;font-weight:700;letter-spacing:3rpx}.title{margin-top:12rpx;font-size:42rpx;font-weight:700}.desc{margin-top:16rpx;color:#718096;font-size:23rpx;line-height:1.7}.steps{display:flex;justify-content:center;gap:62rpx;margin:34rpx 0}.steps text{display:flex;align-items:center;justify-content:center;width:42rpx;height:42rpx;border-radius:50%;color:#94a3b8;background:#edf2f7;font-size:21rpx}.steps text.on{color:#fff;background:#15948b}.field{box-sizing:border-box;width:100%;height:92rpx;margin-top:20rpx;padding:0 24rpx;border:1rpx solid #dbe3ed;border-radius:18rpx;background:#f9fbfd;font-size:26rpx}.captcha-row{display:flex;align-items:center;gap:16rpx;margin-top:20rpx}.captcha-input{flex:1;margin:0}.captcha-image{width:260rpx;height:92rpx;border:1rpx solid #dbe3ed;border-radius:16rpx;background:#f8fafc}.primary,.secondary{display:flex;align-items:center;justify-content:center;height:92rpx;margin-top:30rpx;border:0;border-radius:19rpx;font-size:27rpx}.primary{color:#fff;background:linear-gradient(135deg,#15948b,#0f766e);font-weight:700}.secondary{margin-top:18rpx;border:1rpx solid #ccd7e4;color:#40536d;background:#fff}.note{margin-top:22rpx;padding:20rpx;border-radius:16rpx;color:#536780;background:#f4f7fb;font-size:22rpx;line-height:1.6}.fallback{display:flex;flex-direction:column;margin-top:28rpx;padding-top:24rpx;border-top:1rpx solid #edf1f5;color:#8290a3;font-size:21rpx;line-height:1.65}.fallback text:first-child{color:#536780;font-weight:650}.code{text-align:center;font-size:36rpx;letter-spacing:12rpx}
</style>
