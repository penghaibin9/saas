<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="岗位实习教师工作台" subtitle="指导、审核、评价与统计">
      <template #right><text class="tw-logout" @click="logout">退出</text></template>
    </MobileNavBar>
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="card tw-hero">
          <view><text class="tw-eyebrow">当前实习批次</text><text class="tw-title">{{ context.selectedBatch?.name || context.selectedBatch?.batchName || '暂无可用批次' }}</text></view>
          <picker v-if="context.batches.length" :range="batchLabels" :value="batchIndex" @change="changeBatch"><text class="tw-switch">切换 ▾</text></picker>
        </view>
        <view class="section-head"><text class="section-head__title">常用工作</text><text class="section-head__more">按权限显示</text></view>
        <view class="card tw-grid">
          <view v-for="item in visibleItems" :key="item.path" class="tw-item" @click="open(item)">
            <text class="tw-icon">{{ item.icon }}</text><text class="tw-label">{{ item.label }}</text>
          </view>
        </view>
        <MobileInlineAlert v-if="!visibleItems.length" type="warning" title="暂无岗位实习操作权限" description="请联系学校管理员确认当前教师角色和数据范围。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { logoutMobile } from '@/services/mobileAuth'
import { go, relaunch } from '@/utils/nav'
export default {
  data:()=>({state:'loading',error:'',items:[
    {label:'实习学生',icon:'👥',permission:'internship.student.view',path:'/pages/teacher-internship/internship-students/index'},
    {label:'岗位核对',icon:'🏢',permission:'internship.position.view',path:'/pages/teacher-internship/internship-positions/index'},
    {label:'实习申请',icon:'📋',permission:'internship.application.view',path:'/pages/teacher-internship/internship-application/index'},
    {label:'过程报告',icon:'📝',permission:'internship.report.review',path:'/pages/teacher-internship/process-report-review/index'},
    {label:'材料审核',icon:'📁',permission:'internship.material.review',path:'/pages/teacher-internship/material-review/index'},
    {label:'工资单审核',icon:'💴',permission:'internship.payroll.review',path:'/pages/teacher-internship/payroll-review/index'},
    {label:'企业评价',icon:'⭐',permission:'internship.evaluation.view',path:'/pages/teacher-internship/enterprise-eval/index'},
    {label:'校级统计',icon:'📊',permission:'internship.stats.view',path:'/pages/teacher-internship/school-stats/index'},
    {label:'教师工作记录',icon:'🧭',permission:'internship.student.view',path:'/pages/teacher-internship/activity/index'}
  ]}),
  computed:{
    context(){return useInternshipContextStore()},
    batchLabels(){return this.context.batches.map(b=>b.name||b.batchName||'实习批次')},
    batchIndex(){return Math.max(0,this.context.batches.findIndex(b=>String(b.id)===String(this.context.selectedBatchId)))},
    visibleItems(){return this.items.filter(item=>this.context.can(item.permission))}
  },
  onShow(){this.load()},
  methods:{
    async load(){this.state='loading';this.error='';try{await this.context.load(true);this.state='ready'}catch(e){this.error=e?.message||'教师工作台加载失败';this.state='error'}},
    changeBatch(e){const b=this.context.batches[Number(e.detail.value)];if(b&&this.context.selectBatch(b.id))this.load()},
    open(item){const batch=this.context.selectedBatchId;go(item.path+(batch?'?batchId='+encodeURIComponent(batch):''))},
    async logout(){await logoutMobile();this.context.clear();relaunch('/pages/login/index?entry=teacher')}
  }
}
</script>

<style scoped>
.tw-logout{font-size:12px;color:#fff}.tw-hero{display:flex;align-items:center;justify-content:space-between;gap:12px}.tw-eyebrow{display:block;font-size:11px;color:var(--text-tertiary)}.tw-title{display:block;margin-top:5px;font-size:16px;font-weight:600}.tw-switch{color:var(--brand-primary);font-size:13px}
.tw-grid{display:flex;flex-wrap:wrap;padding:8px}.tw-item{width:33.33%;min-height:92px;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px}.tw-icon{font-size:25px}.tw-label{font-size:12px;color:var(--text-secondary)}
</style>
