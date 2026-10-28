<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-role-switch">
    <MobileNavBar variant="teacher" title="切换工作身份" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack"><MobileInlineAlert v-if="switching" type="info" description="正在切换身份，成功后再显示新身份的数据范围。" /><MobileInlineAlert v-if="error && state === 'ready'" type="warning" :description="error" />
        <view v-for="role in roles" :key="role.roleCode" class="card rs-item" :class="{current:role.roleCode===currentRole}" @click="pick(role)">
          <view class="rs-copy"><text class="rs-title">{{ displayRoleName(role) }}</text></view>
          <MobileStatusTag v-if="role.roleCode===currentRole" type="success" label="当前身份" />
          <text v-else class="rs-arrow">切换 ›</text>
        </view>

        <MobileInlineAlert v-if="!roles.length" type="warning" title="暂无可用身份" description="请联系学校管理员核对身份授权。" />
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { currentMobileSession, switchMobileRole } from '@/services/mobileAuth'
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { relaunch, toast } from '@/utils/nav'
// 沿用首页及 system_authorization.ROLE_NAMES 的中文展示，不参与授权。
const ROLE_NAMES={SYSTEM_ADMIN:'学校系统管理员',SCHOOL_ADMIN:'校级实习管理员',COLLEGE_ADMIN:'院系实习管理员',PROFESSIONAL_LEADER:'专业负责人',MAJOR_LEADER:'专业负责人',COUNSELOR:'班主任／辅导员',INTERN_MENTOR:'实习指导教师',LEADER:'督导／领导',SECURITY_AUDITOR:'安全审计员',STUDENT:'学生'}
export default {
  data:()=>({state:'loading',error:'',roles:[],currentRole:'',switching:false}),
  onShow(){this.load()},
  methods:{
    displayRoleName(role={}) {
      const identity=currentMobileSession()?.identity||{},code=String(role.roleCode||'').trim().toUpperCase()
      const names=[role.roleName,...(String(identity.roleCode||'').toUpperCase()===code?[identity.roleName]:[]),...(identity.availableRoles||[]).filter(item=>String(item.roleCode||'').toUpperCase()===code).map(item=>item.roleName)]
      return names.find(value=>typeof value==='string' && /[\u3400-\u9fff]/.test(value) && (!code || !value.toUpperCase().includes(code)))?.trim() || ROLE_NAMES[code] || '当前工作身份'
    },
    load(){try{const i=currentMobileSession()?.identity||{};this.currentRole=String(i.roleCode||'').toUpperCase();this.roles=(i.availableRoles||[]).filter(r=>String(r.roleCode||'').toUpperCase()!=='STUDENT');this.state='ready'}catch(e){this.error=e?.message||'身份列表加载失败';this.state='error'}},
    async pick(role){const code=String(role?.roleCode||'').toUpperCase();if(!code||code===this.currentRole||this.switching)return;this.switching=true;this.error='';try{const result=await switchMobileRole(code);useSessionStore().setIdentity(result.identity);useInternshipContextStore().clear();toast('已切换为'+this.displayRoleName(role));relaunch('/pages/teacher-internship/index')}catch(e){this.error=e?.message||'身份切换失败，请重试';toast(this.error)}finally{this.switching=false}}
  }
}
</script>
<style scoped>
.rs-item{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px}.rs-item.current{border:1px solid var(--teacher-500,#3b82f6);background:var(--teacher-50,#eff6ff)}.rs-copy{min-width:0}.rs-title{display:block;font-size:15px;font-weight:650;color:var(--text-primary)}.rs-code{display:block;margin-top:4px;font-size:11px;color:var(--text-tertiary)}.rs-arrow{font-size:13px;color:var(--teacher-700)}
.teacher-role-switch :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-role-switch .card{border-radius:8px;box-shadow:none}.rs-item{min-height:60px;box-sizing:border-box}.rs-title{font-size:16px;line-height:24px;overflow-wrap:anywhere}.rs-arrow{font-size:14px;line-height:22px}
</style>
