<template>
  <div class="security-mask" @click.self="close">
    <section
      ref="dialog"
      class="security-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="account-security-title"
      @keydown.esc="close"
    >
      <button class="security-close" type="button" aria-label="关闭账号安全窗口" :disabled="loading" @click="close">×</button>

      <div class="security-heading">
        <span class="security-shield" aria-hidden="true">盾</span>
        <div>
          <p class="security-eyebrow">ACCOUNT SECURITY</p>
          <h2 id="account-security-title">修改登录密码</h2>
          <p>验证当前密码后设置新密码。完成后需使用新密码重新登录。</p>
        </div>
      </div>

      <div class="security-account" aria-label="当前账号">
        <span class="security-account__avatar">{{ (user.realName || user.loginName || '用').slice(0, 1) }}</span>
        <span>
          <strong>{{ user.realName || '当前用户' }}</strong>
          <small>{{ user.loginName || '登录账号未识别' }}<template v-if="tenantName"> · {{ tenantName }}</template></small>
        </span>
      </div>

      <form novalidate @submit.prevent="submit">
        <label for="account-current-password">当前密码</label>
        <div class="security-password-field">
          <input
            id="account-current-password"
            ref="oldPasswordInput"
            v-model="form.oldPassword"
            :type="visible.old ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="请输入当前登录密码"
          >
          <button type="button" :aria-label="visible.old ? '隐藏当前密码' : '显示当前密码'" @click="visible.old = !visible.old">
            {{ visible.old ? '隐藏' : '显示' }}
          </button>
        </div>

        <label for="account-new-password">新密码</label>
        <div class="security-password-field">
          <input
            id="account-new-password"
            v-model="form.newPassword"
            :type="visible.next ? 'text' : 'password'"
            autocomplete="new-password"
            maxlength="128"
            placeholder="至少 8 位，请勿与当前密码相同"
          >
          <button type="button" :aria-label="visible.next ? '隐藏新密码' : '显示新密码'" @click="visible.next = !visible.next">
            {{ visible.next ? '隐藏' : '显示' }}
          </button>
        </div>

        <label for="account-confirm-password">确认新密码</label>
        <div class="security-password-field">
          <input
            id="account-confirm-password"
            v-model="form.confirmPassword"
            :type="visible.confirm ? 'text' : 'password'"
            autocomplete="new-password"
            maxlength="128"
            placeholder="请再次输入新密码"
          >
          <button type="button" :aria-label="visible.confirm ? '隐藏确认密码' : '显示确认密码'" @click="visible.confirm = !visible.confirm">
            {{ visible.confirm ? '隐藏' : '显示' }}
          </button>
        </div>

        <ul class="security-rules" aria-label="密码要求">
          <li :class="{ ok: form.newPassword.length >= 8 }">至少 8 位字符</li>
          <li :class="{ ok: form.newPassword && form.newPassword !== form.oldPassword }">不能与当前密码相同</li>
          <li :class="{ ok: form.confirmPassword && form.confirmPassword === form.newPassword }">两次新密码输入一致</li>
        </ul>

        <p v-if="error" class="security-error" role="alert">{{ error }}</p>
        <p class="security-note">修改后当前会话将退出，其他设备上的旧会话也会失效。不要将密码告诉他人。
        </p>

        <div class="security-actions">
          <button class="security-cancel" type="button" :disabled="loading" @click="close">取消</button>
          <button class="security-submit" type="submit" :disabled="loading">
            {{ loading ? '正在修改…' : '修改密码并重新登录' }}
          </button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { request } from '@/services/http/client'

defineProps({
  user: { type: Object, default: () => ({}) },
  tenantName: { type: String, default: '' }
})
const emit = defineEmits(['close', 'changed'])

const dialog = ref(null)
const oldPasswordInput = ref(null)
const loading = ref(false)
const error = ref('')
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })
const visible = reactive({ old: false, next: false, confirm: false })

function close() {
  if (!loading.value) emit('close')
}

function onDocumentKeydown(event) {
  if (event.key === 'Escape') close()
}

async function submit() {
  error.value = ''
  if (!form.oldPassword) {
    error.value = '请输入当前密码'
    return
  }
  if (form.newPassword.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }
  if (form.newPassword === form.oldPassword) {
    error.value = '新密码不能与当前密码相同'
    return
  }
  if (form.newPassword !== form.confirmPassword) {
    error.value = '两次输入的新密码不一致'
    return
  }

  loading.value = true
  try {
    const result = await request('/auth/change-password', {
      method: 'POST',
      body: { oldPassword: form.oldPassword, newPassword: form.newPassword }
    })
    if (!result?.success) throw new Error('修改密码未成功，请稍后重试')
    emit('changed')
  } catch (e) {
    error.value = e?.message || '修改密码失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  document.addEventListener('keydown', onDocumentKeydown)
  await nextTick()
  oldPasswordInput.value?.focus()
})
onBeforeUnmount(() => document.removeEventListener('keydown', onDocumentKeydown))
</script>

<style scoped>
* { box-sizing: border-box; }
.security-mask { position: fixed; z-index: 4000; inset: 0; display: grid; place-items: center; padding: 20px; background: rgba(15, 35, 62, .54); backdrop-filter: blur(4px); }
.security-dialog { width: min(500px, 100%); max-height: calc(100vh - 40px); overflow: auto; position: relative; padding: 30px; border: 1px solid #dfe7f1; border-radius: 20px; color: #10233f; background: #fff; box-shadow: 0 28px 80px rgba(15, 35, 62, .3); }
.security-close { position: absolute; top: 12px; right: 15px; width: 36px; height: 36px; border: 0; color: #718096; background: transparent; font-size: 25px; cursor: pointer; }
.security-close:disabled { opacity: .45; cursor: wait; }
.security-heading { display: flex; gap: 14px; padding-right: 28px; }
.security-shield { display: grid; place-items: center; flex: 0 0 auto; width: 44px; height: 44px; border-radius: 14px; color: #fff; background: linear-gradient(135deg, #2f70ea, #1749b2); font-size: 16px; font-weight: 800; box-shadow: 0 10px 24px rgba(37, 99, 235, .22); }
.security-eyebrow { margin: 0 0 5px; color: #2f70ea; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.security-heading h2 { margin: 0; font-size: 23px; line-height: 1.3; }
.security-heading p:last-child { margin: 7px 0 0; color: #718096; font-size: 12px; line-height: 1.65; }
.security-account { display: flex; align-items: center; gap: 10px; margin: 20px 0 18px; padding: 11px 12px; border: 1px solid #e5ebf3; border-radius: 11px; background: #f7f9fc; }
.security-account__avatar { display: grid; place-items: center; width: 34px; height: 34px; flex: 0 0 auto; border-radius: 10px; color: #1f56c9; background: #e6efff; font-weight: 750; }
.security-account > span:last-child { display: grid; min-width: 0; gap: 2px; }
.security-account strong { font-size: 13px; }.security-account small { overflow: hidden; color: #7d8ca2; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
form > label { display: block; margin: 14px 0 7px; color: #34465f; font-size: 12px; font-weight: 700; }
.security-password-field { position: relative; }
.security-password-field input { width: 100%; height: 45px; padding: 0 68px 0 13px; border: 1px solid #d9e2ec; border-radius: 10px; outline: none; color: #10233f; font: inherit; }
.security-password-field input:focus { border-color: #2f70ea; box-shadow: 0 0 0 3px rgba(47, 112, 234, .12); }
.security-password-field button { position: absolute; top: 0; right: 0; height: 45px; padding: 0 13px; border: 0; color: #3566c4; background: transparent; font-size: 11px; cursor: pointer; }
.security-rules { display: grid; gap: 6px; margin: 14px 0 0; padding: 0; list-style: none; color: #8492a6; font-size: 11px; }
.security-rules li::before { content: '○'; display: inline-block; width: 18px; }.security-rules li.ok { color: #176b42; }.security-rules li.ok::before { content: '✓'; }
.security-error { margin: 14px 0 0; padding: 10px 12px; border-radius: 9px; color: #b42318; background: #fff1f0; font-size: 12px; line-height: 1.55; }
.security-note { margin: 15px 0 0; padding: 10px 12px; border-radius: 9px; color: #607089; background: #f4f7fb; font-size: 11px; line-height: 1.6; }
.security-actions { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 10px; margin-top: 18px; }
.security-actions button { height: 44px; border-radius: 10px; font: inherit; font-size: 12px; font-weight: 750; cursor: pointer; }
.security-cancel { border: 1px solid #d9e2ec; color: #536780; background: #fff; }.security-submit { border: 0; color: #fff; background: linear-gradient(135deg, #2f70ea, #1f56c9); }
.security-actions button:disabled { opacity: .6; cursor: wait; }
@media (max-width: 540px) { .security-mask { align-items: end; padding: 0; }.security-dialog { width: 100%; max-height: 94vh; padding: 25px 21px calc(22px + env(safe-area-inset-bottom)); border-radius: 22px 22px 0 0; }.security-actions { grid-template-columns: 1fr; }.security-cancel { order: 2; } }
</style>
