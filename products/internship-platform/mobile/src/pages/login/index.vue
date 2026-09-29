<template>
  <view class="login-page">
    <view class="login-card">
      <text class="login-brand">跃科岗位实习管理平台</text>
      <text class="login-title">{{ mode==='STUDENT_MINI'?'学生移动端':'教师移动端' }}</text>
      <text class="login-sub">使用学校分配的账号密码登录，只进入岗位实习业务。</text>

      <view class="login-switch">
        <button :class="{on:mode==='STUDENT_MINI'}" @click="mode='STUDENT_MINI'">学生</button>
        <button :class="{on:mode==='TEACHER_MINI'}" @click="mode='TEACHER_MINI'">教师</button>
      </view>

      <view class="login-form">
        <label><text>学校编码</text><input v-model.trim="tenantCode" placeholder="例如 YIYANG" /></label>
        <label><text>{{ mode==='STUDENT_MINI'?'学号 / 登录账号':'工号 / 登录账号' }}</text><input v-model.trim="loginName" /></label>
        <label><text>密码</text><input v-model="password" password /></label>
        <MobileInlineAlert v-if="error" type="danger" title="登录失败" :description="error" />
        <button class="btn btn-primary" :disabled="loading" @click="submit">{{ loading?'登录中…':'登录' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import { loginMobile } from '@/services/mobileAuth'
import { useSessionStore } from '@/stores/session'
import { relaunch } from '@/utils/nav'
import { FORCE_PASSWORD_CHANGE_ROUTE } from '@/security/passwordChangeGate'

export default {
  data:()=>({mode:'STUDENT_MINI',tenantCode:'',loginName:'',password:'',loading:false,error:''}),
  onLoad(query={}) {
    if(String(query.entry||'').toLowerCase()==='teacher') this.mode='TEACHER_MINI'
  },
  methods:{
    async submit(){
      if(this.loading)return
      if(!this.loginName||!this.password){this.error='请输入登录账号和密码';return}
      this.loading=true;this.error=''
      try{
        const result=await loginMobile({
          tenantCode:this.tenantCode,loginName:this.loginName,password:this.password,clientType:this.mode
        })
        useSessionStore().setIdentity(result.identity)
        relaunch(result.data.mustChangePassword?FORCE_PASSWORD_CHANGE_ROUTE:result.home)
      }catch(e){
        this.error=e?.message||'登录失败，请核对学校编码、账号和密码'
      }finally{this.loading=false}
    }
  }
}
</script>

<style scoped>
.login-page{min-height:100vh;box-sizing:border-box;padding:56px 22px;background:#f4f7fb;display:flex;align-items:center;justify-content:center}
.login-card{width:100%;max-width:480px;background:#fff;border:1px solid #e5eaf1;border-radius:18px;padding:28px;box-sizing:border-box;box-shadow:0 18px 48px rgba(15,23,42,.08)}
.login-brand{display:block;color:var(--brand-primary);font-size:13px;font-weight:600}.login-title{display:block;margin-top:8px;font-size:26px;font-weight:700;color:var(--text-primary)}
.login-sub{display:block;margin-top:8px;color:var(--text-tertiary);font-size:13px;line-height:1.7}.login-switch{display:flex;gap:8px;margin:24px 0 18px;padding:4px;background:#f1f5f9;border-radius:10px}
.login-switch button{flex:1;margin:0;background:transparent;font-size:14px;color:var(--text-secondary)}.login-switch button::after{border:0}.login-switch button.on{background:#fff;color:var(--brand-primary);font-weight:600;box-shadow:0 2px 8px rgba(15,23,42,.06)}
.login-form{display:flex;flex-direction:column;gap:15px}.login-form label text{display:block;margin-bottom:6px;font-size:13px;color:var(--text-secondary)}
.login-form input{height:44px;border:1px solid #dbe3ec;border-radius:9px;padding:0 12px;box-sizing:border-box;background:#fff}.login-form .btn{width:100%;margin-top:4px}
</style>
