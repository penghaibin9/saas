<template>
  <view class="mobile-page mobile-shared login-page" :class="{ 'is-teacher': mode === 'TEACHER_MINI' }">
    <view class="login-card">
      <text class="login-title">{{ mode==='STUDENT_MINI'?'学生登录':'教师登录' }}</text>

      <view class="login-switch">
        <button class="mobile-control" :class="{on:mode==='STUDENT_MINI'}" @click="mode='STUDENT_MINI'">学生</button>
        <button class="mobile-control" :class="{on:mode==='TEACHER_MINI'}" @click="mode='TEACHER_MINI'">教师</button>
      </view>

      <view class="login-form">
        <label><text>学校编码</text><input class="mobile-input" id="mobile-login-school" v-model.trim="tenantCode" placeholder="请输入学校编码" /><text class="login-help">学校编码请向学校获取。</text></label>
        <label><text>{{ mode==='STUDENT_MINI'?'学号 / 登录账号':'工号 / 登录账号' }}</text><input class="mobile-input" id="mobile-login-account" v-model.trim="loginName" /></label>
        <label><text>密码</text><input class="mobile-input" id="mobile-login-password" v-model="password" password /></label>
        <MobileInlineAlert v-if="error" type="danger" title="登录失败" :description="error" />
        <button class="mobile-control btn btn-primary" aria-label="登录" data-testid="mobile-login-submit" :disabled="loading" @click="submit">{{ loading?'登录中…':'登录' }}</button>
        <text class="login-help">账号或密码问题请联系学校管理员；首次使用临时密码须本人修改。</text>
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
.login-page{--login-accent:var(--brand-primary);min-height:100vh;box-sizing:border-box;padding:40px 22px;background:#f4f7fb;display:flex;align-items:center;justify-content:center}.login-page.is-teacher{--login-accent:var(--teacher-600)}
.login-card{width:100%;max-width:480px;background:#fff;border:1px solid #e5eaf1;border-radius:18px;padding:28px;box-sizing:border-box;box-shadow:0 18px 48px rgba(15,23,42,.08)}
.login-title{display:block;font-size:var(--font-size-xl);font-weight:700;color:var(--text-primary)}
.login-switch{display:flex;gap:8px;margin:20px 0;padding:4px;background:#f1f5f9;border-radius:10px}
.login-switch button{flex:1;min-height:44px;margin:0;background:transparent;font-size:var(--font-size-md);color:var(--text-secondary)}.login-switch button::after{border:0}.login-switch button.on{background:#fff;color:var(--login-accent);font-weight:600;box-shadow:0 2px 8px rgba(15,23,42,.06)}
.login-form{display:flex;flex-direction:column;gap:16px}.login-form label text{display:block;margin-bottom:6px;font-size:var(--font-size-base);color:var(--text-secondary)}
.login-form input{height:44px;font-size:var(--font-size-md);border:1px solid #dbe3ec;border-radius:9px;padding:0 12px;box-sizing:border-box;background:#fff}.login-form .btn{width:100%;min-height:44px;margin-top:4px;background:var(--login-accent);font-size:var(--font-size-md)}
.login-page{align-items:flex-start;padding-top:max(24px,6vh);padding-bottom:32px}.login-help{display:block;font-size:var(--font-size-sm)!important;line-height:1.7;color:var(--text-secondary)!important;overflow-wrap:anywhere}.login-form label .login-help{margin:6px 0 0}
</style>
