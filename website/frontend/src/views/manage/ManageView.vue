<template>
  <div class="manager">
    <header class="manager-header"><a href="/">跃科官网</a><strong>内容管理后台</strong><template v-if="user"><span>{{ user.displayName }}</span><button @click="logout" :disabled="busy">退出登录</button></template></header>
    <p v-if="checking" class="login-status" role="status">正在核验官网管理身份…</p>
    <form v-else-if="!user" class="login-panel" @submit.prevent="login">
      <p class="eyebrow">官网内容管理</p><h1>登录网站后台</h1><p>使用独立的官网管理账号。新闻审核与发布按账号权限办理，咨询资料仅官网超级管理员可查看。</p>
      <label>账号<input v-model.trim="username" autocomplete="username" required maxlength="80"></label>
      <label>密码<input v-model="password" type="password" autocomplete="current-password" required maxlength="256"></label>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <button class="primary" :disabled="busy">{{ busy ? '正在登录…' : '登录官网后台' }}</button>
    </form>
    <template v-else><p v-if="error" class="error" role="alert">{{ error }}</p><nav v-if="user.role==='superadmin'" class="manager-sections" aria-label="官网管理范围"><button :aria-current="area==='news'?'page':undefined" @click="switchArea('news')">新闻运营</button><button :aria-current="area==='consultations'?'page':undefined" @click="switchArea('consultations')">咨询受理</button></nav><ConsultationView v-if="user.role==='superadmin'&&area==='consultations'"/><NewsView v-else :can-publish="['publisher','superadmin'].includes(user.role)" /></template>
    <dialog ref="dialog" class="manager-dialog" @cancel.prevent="finishSystemDialog(false)">
      <h2>{{ state.title }}</h2><p>{{ state.message }}</p><footer><button v-if="state.mode !== 'alert'" @click="finishSystemDialog(false)">{{ state.cancelText }}</button><button @click="finishSystemDialog(true)">{{ state.confirmText }}</button></footer>
    </dialog>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NewsView from './NewsView.vue'
import ConsultationView from './ConsultationView.vue'
import { request, setCsrfToken } from '@/services/http/client.js'
import { systemDialogState as state, finishSystemDialog } from '@/services/systemDialog.js'
const user = ref(null), checking = ref(true), busy = ref(false), error = ref(''), username = ref(''), password = ref(''), dialog = ref(null)
const route=useRoute(),router=useRouter()
const area = computed(()=>route.query.area==='consultations'?'consultations':'news')
function switchArea(value){const query={...route.query};if(value==='consultations')query.area=value;else delete query.area;router.replace({query})}
function acceptSession(session) { user.value = session.user; setCsrfToken(session.csrfToken) }
function expired() { user.value = null; setCsrfToken(''); error.value = '登录已失效，请重新登录。' }
async function login() {
  busy.value = true; error.value = ''
  try { acceptSession(await request('/auth/login', { method: 'POST', body: { username: username.value, password: password.value } })); password.value = '' }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
async function logout() {
  busy.value = true
  try { await request('/auth/logout', { method: 'POST' }); user.value = null; setCsrfToken('') }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
watch(() => state.visible, async visible => { await nextTick(); if (visible) dialog.value?.showModal(); else dialog.value?.close() })
onMounted(async () => {
  window.addEventListener('website-session-expired', expired)
  try { acceptSession(await request('/auth/session')) } catch (e) { error.value = e.message.includes('请登录') ? '' : e.message } finally { checking.value = false }
})
onBeforeUnmount(() => { window.removeEventListener('website-session-expired', expired); finishSystemDialog(false) })
</script>
<style scoped>
.manager{min-height:100vh;background:#f3f6fa;color:#20324b}.manager-header{display:flex;align-items:center;gap:24px;padding:20px 5%;background:#071d30;color:white}.manager-header a{color:inherit;text-decoration:none}.manager-header span{margin-left:auto}.manager button{font:inherit;cursor:pointer;border:1px solid #c6d3e2;border-radius:8px;padding:10px 18px;background:white;color:#183857}.manager button:disabled{opacity:.6}.login-panel{max-width:440px;margin:8vh auto;padding:36px;background:white;border:1px solid #dce4ee;border-radius:16px}.login-panel h1{font-size:28px}.login-panel p{line-height:1.8;color:#62738a}.login-panel label{display:block;margin:24px 0}.login-panel input{display:block;width:100%;margin-top:8px;padding:12px;border:1px solid #b4c5da;border-radius:8px;font:inherit}.login-panel .primary{width:100%;background:#1763dc;color:white}.error{color:#af2c35!important}.login-status{text-align:center;padding:60px}.manager-dialog{border:1px solid #d6e1ee;border-radius:14px;max-width:500px;padding:28px}.manager-dialog::backdrop{background:#071d3080}.manager-dialog p{line-height:1.8}.manager-dialog footer{display:flex;justify-content:flex-end;gap:12px}.eyebrow{font-size:13px}@media(max-width:600px){.login-panel{margin:32px 16px;padding:24px}.manager-header{gap:12px;flex-wrap:wrap}}
</style>
<style scoped>.manager-sections{display:flex;gap:12px;padding:18px 5%;background:white;border-bottom:1px solid #dce5ee}.manager-sections button[aria-current]{background:#1763dc;color:white;border-color:#1763dc}</style>
