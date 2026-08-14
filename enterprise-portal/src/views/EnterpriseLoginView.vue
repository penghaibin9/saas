<script setup>
import { reactive,ref } from 'vue'
import { useRouter } from 'vue-router'
import { enterpriseAuthApi } from '../services/authApi'
import { getSelectedCampaignId } from '../services/request'
const router=useRouter(),loading=ref(false),error=ref('')
const form=reactive({tenantCode:'',loginName:'',password:''})
async function submit(){loading.value=true;error.value='';try{await enterpriseAuthApi.login(form);await router.push(getSelectedCampaignId()?'/home':'/campaign-select')}catch(e){error.value=e.message||'企业登录失败'}finally{loading.value=false}}
</script>
<template><main class="auth"><section class="ep-card card"><div class="logo">跃科</div><h1>企业协同中心</h1><p>企业账号必须绑定学校租户；不提供开放式企业自注册。</p><form @submit.prevent="submit"><label>学校编码<input v-model.trim="form.tenantCode" class="ep-input" autocomplete="organization" required></label><label>手机号或登录账号<input v-model.trim="form.loginName" class="ep-input" autocomplete="username" required></label><label>密码<input v-model="form.password" type="password" class="ep-input" autocomplete="current-password" required></label><div v-if="error" class="ep-error">{{ error }}</div><button class="ep-btn ep-btn-primary submit" :disabled="loading">{{ loading?'登录中…':'登录' }}</button></form><p class="invite">首次激活请使用学校发送的企业邀请链接。</p></section></main></template>
<style scoped>.auth{min-height:100vh;display:grid;place-items:center;padding:24px}.card{width:min(440px,100%);padding:34px}.logo{color:var(--pri);font-size:22px;font-weight:800}.card h1{margin:12px 0 8px}.card>p{color:var(--t3);line-height:1.7}form{margin-top:22px}label{display:flex;flex-direction:column;gap:7px;margin-bottom:14px;font-size:13px;color:var(--t2)}.ep-input,.submit{width:100%}.invite{font-size:12px;text-align:center;margin:18px 0 0}</style>
