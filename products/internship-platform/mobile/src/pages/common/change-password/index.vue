<template>
  <view class="page-wrap">
    <MobileNavBar title="首次修改密码" subtitle="临时密码必须先更换" />
    <view class="page-pad">
      <view class="card cp-card">
        <MobileInlineAlert type="warning" title="请先完成密码修改" description="为了保护账号安全，修改成功后需要使用新密码重新登录。" />
        <label><text>当前临时密码</text><input v-model="currentPassword" password /></label>
        <label><text>新密码</text><input v-model="newPassword" password placeholder="至少10位，含大小写字母、数字和特殊字符" /></label>
        <label><text>确认新密码</text><input v-model="confirmPassword" password /></label>
        <MobileInlineAlert v-if="error" type="danger" :description="error" />
        <button class="btn btn-primary" :disabled="loading" @click="submit">{{ loading?'修改中…':'修改密码' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { logoutMobile } from '@/services/mobileAuth'
import { relaunch } from '@/utils/nav'

export default {
  data:()=>({currentPassword:'',newPassword:'',confirmPassword:'',loading:false,error:''}),
  methods:{
    async submit(){
      if(this.loading)return
      if(this.newPassword!==this.confirmPassword){this.error='两次输入的新密码不一致';return}
      this.loading=true;this.error=''
      try{
        await realRequest('/auth/change-password',{
          method:'POST',data:{currentPassword:this.currentPassword,newPassword:this.newPassword}
        })
        await logoutMobile()
        uni.showToast({title:'密码已修改，请重新登录',icon:'none'})
        setTimeout(()=>relaunch('/pages/login/index'),350)
      }catch(e){this.error=e?.message||'密码修改失败，请重试'}
      finally{this.loading=false}
    }
  }
}
</script>

<style scoped>
.cp-card{display:flex;flex-direction:column;gap:16px}.cp-card label text{display:block;font-size:13px;color:var(--text-secondary);margin-bottom:6px}
.cp-card input{height:44px;border:1px solid var(--border-light);border-radius:9px;padding:0 12px;box-sizing:border-box}.cp-card .btn{width:100%}
</style>
