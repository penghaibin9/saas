<template>
  <div v-if="visible" class="login-captcha">
    <label :for="inputId">图形验证码</label>
    <div class="login-captcha__row">
      <input :id="inputId" :value="modelValue" inputmode="numeric" maxlength="6" autocomplete="off"
             placeholder="请输入图中 6 位数字" @input="$emit('update:modelValue', $event.target.value.replace(/\D/g, '').slice(0, 6))">
      <button type="button" class="login-captcha__image" :disabled="loading" title="点击换一张" @click="$emit('refresh')">
        <img v-if="image" :src="image" alt="图形验证码，点击刷新"><span v-else>{{ loading ? '加载中…' : '换一张' }}</span>
      </button>
    </div>
    <small>看不清可点击图片刷新；验证码 2 分钟内、单次有效。</small>
  </div>
</template>
<script>
export default {
  name: 'LoginCaptcha',
  props: { visible: Boolean, modelValue: { type: String, default: '' }, image: { type: String, default: '' }, loading: Boolean, inputId: { type: String, default: 'login-captcha' } },
  emits: ['update:modelValue', 'refresh']
}
</script>
<style scoped>
.login-captcha { margin-top: 14px; }.login-captcha label { display: block; margin-bottom: 7px; color: #34465f; font-size: 12px; font-weight: 650; }
.login-captcha__row { display: grid; grid-template-columns: 1fr 154px; gap: 9px; }.login-captcha__row input { width: 100%; height: 44px; box-sizing: border-box; padding: 0 13px; border: 1px solid #dbe3ed; border-radius: 9px; outline: none; }
.login-captcha__image { height: 44px; overflow: hidden; padding: 0; border: 1px solid #dbe3ed; border-radius: 9px; background: #f8fafc; cursor: pointer; }.login-captcha__image img { display: block; width: 100%; height: 100%; object-fit: cover; }.login-captcha__image span { color: #536780; font-size: 12px; }
.login-captcha small { display: block; margin-top: 6px; color: #8290a3; font-size: 11px; }@media (max-width: 420px) { .login-captcha__row { grid-template-columns: 1fr 132px; } }
</style>
