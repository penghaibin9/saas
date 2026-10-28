<template>
  <view class="mobile-page mobile-shared page-wrap">
    <MobileNavBar title="修改密码" />
    <view class="page-pad">
      <view class="card cp-card">
        <text class="cp-hint">修改成功后，请使用新密码重新登录。</text>
        <label><text>当前密码</text><input class="mobile-input" v-model="currentPassword" password :focus="invalidField === 'current'" /></label>
        <label><text>新密码</text><input class="mobile-input" v-model="newPassword" password :focus="invalidField === 'new'" placeholder="请输入新密码" /><text class="cp-rule">至少10位，含大小写字母、数字和特殊字符。</text></label>
        <label><text>确认新密码</text><input class="mobile-input" v-model="confirmPassword" password :focus="invalidField === 'confirm'" /></label>
        <MobileInlineAlert v-if="error" type="danger" :description="error" />
        <button class="mobile-control btn btn-primary" :disabled="loading" @click="submit">{{ loading?'修改中…':'修改密码' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { logoutMobile } from '@/services/mobileAuth'
import { relaunch } from '@/utils/nav'

export default {
  data:()=>({currentPassword:'',newPassword:'',confirmPassword:'',loading:false,error:'',invalidField:''}),
  methods:{
    async submit(){
      if(this.loading)return
      this.invalidField=''
      if(!this.currentPassword){this.invalidField='current';this.error='请输入当前密码';return}
      if(!/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,128}$/.test(this.newPassword)){this.invalidField='new';this.error='新密码须为10至128位，并同时包含大小写字母、数字和特殊字符';return}
      if(this.newPassword===this.currentPassword){this.invalidField='new';this.error='新密码不能与当前密码相同';return}
      if(this.newPassword!==this.confirmPassword){this.invalidField='confirm';this.error='两次输入的新密码不一致';return}
      this.loading=true;this.error=''
      try{
        await realRequest('/auth/change-password',{
          method:'POST',data:{currentPassword:this.currentPassword,newPassword:this.newPassword}
        })
        if(!await logoutMobile())return
        uni.showToast({title:'密码已修改，请重新登录',icon:'none'})
        relaunch('/pages/login/index')
      }catch(e){this.error=e?.message||'密码修改失败，请重试'}
      finally{this.loading=false}
    }
  }
}
</script>

<style scoped>
.cp-card{display:flex;flex-direction:column;gap:16px}.cp-card label text{display:block;font-size:var(--font-size-base);color:var(--text-secondary);margin-bottom:6px}.cp-hint,.cp-card label .cp-rule{font-size:var(--font-size-base);line-height:1.6;color:var(--text-secondary);overflow-wrap:anywhere}.cp-card label .cp-rule{margin:6px 0 0}
.cp-card input{height:44px;width:100%;font-size:var(--font-size-md);border:1px solid var(--border-light);border-radius:9px;padding:0 12px;box-sizing:border-box}.cp-card .btn{width:100%;min-height:44px;font-size:var(--font-size-md)}
</style>
