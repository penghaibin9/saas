<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="切换工作身份" subtitle="同一账号 · 不退出系统" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <MobileInlineAlert type="info" description="只展示学校已真实分配给当前账号的教师身份；切换后权限、数据范围和实习批次会重新从服务端加载。" />
        <view v-for="role in roles" :key="role.roleCode" class="card rs-item" :class="{current:role.roleCode===currentRole}" @click="pick(role)">
          <view class="rs-copy"><text class="rs-title">{{ role.roleName || role.roleCode }}</text><text class="rs-code">{{ role.roleCode }}</text></view>
          <MobileStatusTag v-if="role.roleCode===currentRole" type="success" label="当前身份" />
          <text v-else class="rs-arrow">切换 ›</text>
        </view>
        <MobileInlineAlert v-if="roles.length<2" type="warning" description="当前账号只有一个教师身份，无需切换；如岗位职责不完整，请由学校管理员调整角色授权。" />
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { currentMobileSession, switchMobileRole } from '@/services/mobileAuth'
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { relaunch, toast } from '@/utils/nav'
export default {
  data:()=>({state:'loading',error:'',roles:[],currentRole:'',switching:false}),
  onShow(){this.load()},
  methods:{
    load(){try{const i=currentMobileSession()?.identity||{};this.currentRole=String(i.roleCode||'').toUpperCase();this.roles=(i.availableRoles||[]).filter(r=>String(r.roleCode||'').toUpperCase()!=='STUDENT');this.state='ready'}catch(e){this.error=e?.message||'身份列表加载失败';this.state='error'}},
    async pick(role){const code=String(role?.roleCode||'').toUpperCase();if(!code||code===this.currentRole||this.switching)return;this.switching=true;try{const result=await switchMobileRole(code);useSessionStore().setIdentity(result.identity);useInternshipContextStore().clear();toast('已切换为'+(role.roleName||code));relaunch('/pages/teacher-internship/index')}catch(e){toast(e?.message||'身份切换失败，请重试')}finally{this.switching=false}}
  }
}
</script>
<style scoped>
.rs-item{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px}.rs-item.current{border:1px solid var(--teacher-500,#3b82f6);background:var(--teacher-50,#eff6ff)}.rs-copy{min-width:0}.rs-title{display:block;font-size:15px;font-weight:650;color:var(--text-primary)}.rs-code{display:block;margin-top:4px;font-size:11px;color:var(--text-tertiary)}.rs-arrow{font-size:13px;color:var(--teacher-700)}
</style>