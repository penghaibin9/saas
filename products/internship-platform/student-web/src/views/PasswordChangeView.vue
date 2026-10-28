<template>
  <main class="password-page"><form @submit.prevent="save">
    <h1>设置本人登录密码</h1><p>首次开户或管理员重置后，请先替换临时密码。修改后需重新登录。</p>
    <label>当前临时密码<input v-model="current" type="password" autocomplete="current-password" required /></label>
    <label>新密码<input v-model="next" type="password" autocomplete="new-password" minlength="10" maxlength="128" required /></label>
    <p>至少10位，同时包含大写字母、小写字母、数字和特殊字符。</p>
    <label>再次输入新密码<input v-model="confirm" type="password" autocomplete="new-password" required /></label>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="done" role="status">密码已修改，请使用新密码重新登录。</p>
    <button v-if="!done" class="sp-btn" :disabled="busy">{{ busy ? '正在保存…' : '修改密码' }}</button>
    <router-link v-else to="/login">返回登录</router-link>
  </form></main>
</template>
<script setup>
import { ref } from 'vue'
import { request } from '../services/request'
import { useSessionStore } from '../stores/session'
const current=ref(''),next=ref(''),confirm=ref(''),error=ref(''),busy=ref(false),done=ref(false),session=useSessionStore()
async function save(){
  if(busy.value)return
  error.value=''
  if(next.value!==confirm.value){error.value='两次输入的新密码不一致';return}
  busy.value=true
  try { await request('/auth/change-password',{method:'POST',body:{currentPassword:current.value,newPassword:next.value}});current.value=next.value=confirm.value='';await session.logout();done.value=true }
  catch(e){error.value=e.message||'密码修改失败，请重试'}finally{busy.value=false}
}
</script>
<style scoped>
.password-page{min-height:100vh;display:grid;place-items:center;padding:24px;background:#eef5ff}.password-page form{width:min(440px,100%);padding:30px;background:white;border:1px solid #dbe5f4;border-radius:16px}.password-page label{display:grid;gap:6px;margin:16px 0}.password-page input{padding:10px;border:1px solid #ccd6e5;border-radius:7px;font:inherit}.password-page p{font-size:14px;color:#52647a}.password-page [role=alert]{color:#b42318}
</style>
