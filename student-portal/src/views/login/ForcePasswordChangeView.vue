<template>
  <main class="force-page">
    <section class="force-card" aria-labelledby="student-force-title">
      <div class="mark">盾</div>
      <p class="eyebrow">ACCOUNT SECURITY</p>
      <h1 id="student-force-title">首次登录，请先修改初始密码</h1>
      <p class="intro">完成改密前，服务端不会开放成绩、课表、申请、实习、毕设等学生业务。直接输入业务地址也不能绕过。</p>

      <form @submit.prevent="submit">
        <label for="sp-old-password">当前密码</label>
        <input id="sp-old-password" v-model="form.oldPassword" type="password" autocomplete="current-password" placeholder="请输入当前初始密码">
        <label for="sp-new-password">新密码</label>
        <input id="sp-new-password" v-model="form.newPassword" type="password" autocomplete="new-password" placeholder="至少 8 位，不能与当前密码相同">
        <label for="sp-confirm-password">确认新密码</label>
        <input id="sp-confirm-password" v-model="form.confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入新密码">

        <ul class="rules">
          <li :class="{ ok: form.newPassword.length >= 8 }">至少 8 位字符</li>
          <li :class="{ ok: form.newPassword && form.newPassword !== form.oldPassword }">不能与当前密码相同</li>
          <li :class="{ ok: form.confirmPassword && form.confirmPassword === form.newPassword }">两次新密码输入一致</li>
        </ul>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" type="submit" :disabled="loading">{{ loading ? '正在修改…' : '修改密码并重新登录' }}</button>
        <button class="secondary" type="button" :disabled="loading" @click="leave">退出当前账号</button>
      </form>
      <p class="footnote">不知道当前初始密码时，请联系辅导员或学校管理员重置。不要把密码发送给技术支持人员。</p>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { request } from '../../services/request'
import { useSessionStore } from '../../stores/session'

const router = useRouter()
const session = useSessionStore()
const loading = ref(false)
const error = ref('')
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

async function submit() {
  error.value = ''
  if (!form.oldPassword) { error.value = '请输入当前密码'; return }
  if (form.newPassword.length < 8) { error.value = '新密码至少 8 位'; return }
  if (form.newPassword === form.oldPassword) { error.value = '新密码不能与当前密码相同'; return }
  if (form.newPassword !== form.confirmPassword) { error.value = '两次输入的新密码不一致'; return }
  loading.value = true
  try {
    const data = await request('/auth/change-password', {
      method: 'POST', body: { oldPassword: form.oldPassword, newPassword: form.newPassword }
    })
    if (!data?.success) throw new Error('修改密码未成功，请稍后重试')
    // 后端提升账号版本并吊销 refresh；学生门户主动清理旧 access，必须重新登录。
    session.logout()
    await router.replace('/login')
  } catch (e) {
    error.value = e?.message || '修改密码失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function leave() {
  session.logout()
  await router.replace('/login')
}
</script>

<style scoped>
* { box-sizing: border-box; }
.force-page { min-height: 100vh; display: grid; place-items: center; padding: 28px 18px; color: #10233f; background: radial-gradient(circle at 50% 0, #eaf8f5 0, transparent 42%), #f4f7fb; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
.force-card { width: min(520px, 100%); padding: 38px 42px 34px; border: 1px solid #dfe8ea; border-radius: 22px; background: #fff; box-shadow: 0 28px 80px -42px rgba(16,35,63,.38); }
.mark { display: grid; place-items: center; width: 48px; height: 48px; margin-bottom: 20px; border-radius: 15px; color: #fff; background: linear-gradient(135deg, #15948b, #0f766e); font-size: 18px; font-weight: 800; }
.eyebrow { margin: 0 0 8px; color: #0f766e; font-size: 11px; font-weight: 800; letter-spacing: .14em; }
h1 { margin: 0; font-size: 28px; line-height: 1.35; letter-spacing: -.02em; }.intro { margin: 14px 0 24px; color: #64748b; font-size: 13px; line-height: 1.8; }
label { display: block; margin: 15px 0 7px; color: #34465f; font-size: 12px; font-weight: 700; }input { width: 100%; height: 46px; padding: 0 13px; border: 1px solid #d9e2ec; border-radius: 10px; outline: none; color: #10233f; font: inherit; }input:focus { border-color: #15948b; box-shadow: 0 0 0 3px rgba(21,148,139,.12); }
.rules { display: grid; gap: 6px; margin: 16px 0 0; padding: 0; list-style: none; color: #8492a6; font-size: 11px; }.rules li::before { content: '○'; margin-right: 7px; }.rules li.ok { color: #176b42; }.rules li.ok::before { content: '✓'; }
.error { margin: 15px 0 0; padding: 10px 12px; border-radius: 9px; color: #b42318; background: #fff1f0; font-size: 12px; }button { width: 100%; height: 46px; border-radius: 10px; font: inherit; font-size: 13px; font-weight: 750; cursor: pointer; }.primary { margin-top: 18px; border: 0; color: #fff; background: linear-gradient(135deg, #15948b, #0f766e); }.secondary { margin-top: 10px; border: 1px solid #dce4ee; color: #536780; background: #fff; }button:disabled { opacity: .6; cursor: wait; }.footnote { margin: 20px 0 0; padding-top: 18px; border-top: 1px solid #edf1f5; color: #8795a8; font-size: 11px; line-height: 1.65; }
@media (max-width: 560px) { .force-card { padding: 28px 22px 26px; border-radius: 17px; }h1 { font-size: 24px; } }
</style>
