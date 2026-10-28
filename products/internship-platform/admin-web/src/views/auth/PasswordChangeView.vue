<template>
  <main class="sl-page"><section class="sl-card"><h1>修改本人登录密码</h1><p>修改成功后，请使用新密码重新登录。</p>
    <form @submit.prevent="save"><label>当前密码<input v-model="current" type="password" autocomplete="current-password" required /></label>
      <label>新密码<input v-model="next" type="password" autocomplete="new-password" minlength="10" maxlength="128" required /></label>
      <p>至少10位，同时包含大写字母、小写字母、数字和特殊字符。</p>
      <label>再次输入新密码<input v-model="confirm" type="password" autocomplete="new-password" required /></label>
      <div v-if="error" class="sl-error" role="alert">{{ error }}</div><p v-if="done" role="status">密码已修改，请使用新密码重新登录。</p>
      <button v-if="!done" :disabled="busy">{{ busy?'正在保存…':'修改密码' }}</button><router-link v-else to="/login">返回登录</router-link>
    </form></section></main>
</template>
<script setup>
import { ref } from 'vue'
import { request, logoutRemote } from '@/services/http/client'
import { clearPermissionPatterns } from '@/security/permissionGate'
const current=ref(''),next=ref(''),confirm=ref(''),busy=ref(false),done=ref(false),error=ref('')
async function save(){
  if(busy.value)return
  error.value=''
  if(next.value!==confirm.value){error.value='两次输入的新密码不一致';return}
  busy.value=true
  try{await request('/auth/change-password',{method:'POST',body:{currentPassword:current.value,newPassword:next.value}});current.value=next.value=confirm.value='';await logoutRemote();clearPermissionPatterns();done.value=true}
  catch(e){error.value=e.message||'密码修改失败，请重试'}finally{busy.value=false}
}
</script>
