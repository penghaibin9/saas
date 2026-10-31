<template>
  <view class="internship-surface mobile-page mobile-teacher page-wrap teacher-home internship-flow">
    <MobileNavBar variant="teacher" title="实习工作台" show-back fallback-url="/pages/teacher/workbench/index" :subtitle="state === 'forbidden' ? roleName : ''">
      <template #right><view class="tw-nav-actions"><button v-if="canSwitchRole" class="mobile-control tw-nav-action" aria-label="切换身份" @click="openRoleSwitch">身份</button><button class="mobile-control tw-nav-action" @click="logout">退出</button></view></template>
    </MobileNavBar>
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad tw-content">
        <view class="tw-context">
          <view class="tw-context-copy"><text v-if="roleName" class="tw-role">{{ roleName }}</text><text class="tw-batch-name">{{ context.selectedBatch?.name || context.selectedBatch?.batchName || '暂无可用批次' }}</text></view>
          <picker class="mobile-picker" v-if="context.batches.length > 1" :range="batchLabels" :value="batchIndex" @change="changeBatch"><view class="tw-switch" role="button" aria-label="切换实习批次">切换批次</view></picker>
        </view>
        <view v-if="context.can('internship.dashboard.view')" class="card tw-todos">
          <view class="row-between"><text class="tw-section-title">待我处理</text><text v-if="todoState === 'ready'" class="tw-total">共 {{ todoTotal }} 项</text></view>
          <text class="tw-scope">本人全部批次的分类待办</text>
          <text v-if="todoState === 'loading'" class="tw-copy">正在读取待办…</text>
          <view v-else-if="todoState === 'error'" class="tw-count-error"><text>待办读取未完成，不能确认当前数量。</text><button class="mobile-control" @click="load">重新读取待办</button></view>
          <template v-else>
            <text v-if="priorityTodos.length" class="tw-copy">优先处理（按截止时间，逾期优先）</text>
            <button v-for="item in priorityTodos" :key="item.todoId" class="mobile-control tw-todo flow-priority" @click="openPriority(item)"><MobileShellIcon name="file-text" tone="teal" /><view class="flex-1"><text class="tw-todo-title">{{ item.title }}</text></view><text class="flow-task-action">去处理</text></button>
            <text v-if="todoTotal > priorityTodos.length" class="tw-copy">另有 {{ todoTotal - priorityTodos.length }} 项待办，可按下方分类查看。</text>
            <button v-for="group in todoGroups" :key="group.key" class="mobile-control tw-todo" @click="openTodoGroup(group.key)"><MobileShellIcon :name="group.icon" tone="teal" /><view class="flex-1"><text class="tw-todo-title">{{ group.label }}</text><text class="tw-copy">{{ group.count }} 项待处理</text></view><MobileShellIcon name="chevron-right" tone="teal" plain /></button>
            <text v-if="!todoTotal" class="tw-copy tw-empty">暂无待办。</text>
            <button class="mobile-control tw-all-todos" @click="openTodoGroup('ALL')">查看全部分类待办</button>
          </template>
        </view>
        <view v-if="materialEntry" class="card tw-material-entry"><MobileShellIcon name="folder" tone="teal" /><view class="flex-1"><text class="tw-todo-title">材料审核</text><text class="tw-copy">按当前批次核对收件与补正</text></view><button class="mobile-control tw-main-action" @click="open(materialEntry)">去审核</button></view>
        <text v-if="shortcutItems.length" class="tw-section-title">常用办理</text>
        <view v-if="shortcutItems.length" class="tw-shortcuts">
          <button v-for="item in shortcutItems" :key="item.path" class="mobile-control tw-shortcut" @click="open(item)"><MobileShellIcon :name="itemIcon(item)" tone="teal" /><view class="flex-1"><text class="tw-todo-title">{{ item.label }}</text></view></button>
        </view>
        <button v-if="messageEntry" class="mobile-control tw-messages" @click="open(messageEntry)"><MobileShellIcon name="message-dots" tone="teal" /><view class="flex-1"><text class="tw-todo-title">站内信</text></view><MobileShellIcon name="chevron-right" tone="teal" plain /></button>
        <view v-if="otherItems.length" class="tw-more">
          <button class="mobile-control tw-more-toggle" :aria-expanded="moreExpanded" @click="moreExpanded = !moreExpanded"><text>更多办理</text><text>{{ moreExpanded ? '收起' : '展开' }}</text></button>
          <view v-if="moreExpanded" class="tw-grid">
            <button v-for="item in otherItems" :key="item.path" class="mobile-control tw-item tw-more-item" @click="open(item)"><MobileShellIcon :name="itemIcon(item)" tone="teal" /><text class="tw-label">{{ item.label }}</text></button>
          </view>
        </view>
        <MobileInlineAlert v-if="!visibleItems.length && !visibleMoreItems.length" type="warning" title="暂无岗位实习操作权限" description="请联系学校管理员确认当前教师角色和数据范围。" />
      </view>
    </MobileGlobalState>
    <view class="tw-help"></view>
    <TeacherNoticeInbox ref="importantNotices" :batch-id="String(context.selectedBatchId || '')" />
  </view>
</template>

<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { useSessionStore } from '@/stores/session'
import { go, relaunch } from '@/utils/nav'
import TeacherNoticeInbox from '@/components/TeacherNoticeInbox.vue'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import teacherApi from '@/services/teacherApi'
import { normalizeError } from '@/services/request'

// 中文兜底沿用 system_authorization.ROLE_NAMES，仅用于展示，不参与身份或权限判断。
const ROLE_NAMES = {
  SYSTEM_ADMIN:'学校系统管理员',SCHOOL_ADMIN:'校级实习管理员',COLLEGE_ADMIN:'院系实习管理员',
  PROFESSIONAL_LEADER:'专业负责人',MAJOR_LEADER:'专业负责人',COUNSELOR:'班主任／辅导员',
  INTERN_MENTOR:'实习指导教师',LEADER:'督导／领导',SECURITY_AUDITOR:'安全审计员',STUDENT:'学生'
}
export default {
  components:{TeacherNoticeInbox},
  data:()=>({requestedBatchId:'',state:'loading',error:'',roleName:'',todoState:'loading',todoTotal:0,todoCounts:{},loadSequence:0,hidden:false,generation:currentSessionGeneration(),items:[
    {label:'分类待办',icon:'✅',permission:'internship.dashboard.view',path:'/pages/teacher-internship/todos/index',primary:true},
    {label:'站内信',icon:'💬',permission:'internship.dashboard.view',path:'/pages/teacher-internship/messages/index',primary:true},
    {label:'实习学生',icon:'👥',permission:'internship.student.view',path:'/pages/teacher-internship/internship-students/index'},
    {label:'岗位核对',icon:'🏢',permission:'internship.position.view',path:'/pages/teacher-internship/internship-positions/index'},
    {label:'实习申请',icon:'📋',permission:'internship.application.view',path:'/pages/teacher-internship/internship-application/index'},
    {label:'实习变更',icon:'🔄',permission:'internship.change.view',path:'/pages/teacher-internship/internship-change/index'},
    {label:'巡访任务',icon:'📍',permission:'internship.visit.view',path:'/pages/teacher-internship/internship-review/index?tab=visit'},
    {label:'报告批阅',icon:'📝',permission:'internship.report.view',path:'/pages/teacher-internship/process-report-review/index',reportGateway:true},
    {label:'材料审核',icon:'📁',permission:'internship.report.review',path:'/pages/teacher-internship/material-review/index'},
    {label:'工资单审核',icon:'💴',permission:'internship.payroll.review',path:'/pages/teacher-internship/payroll-review/index'},
    {label:'企业评价',icon:'⭐',permission:'internship.evaluation.view',path:'/pages/teacher-internship/enterprise-eval/index'},
    {label:'校级统计',icon:'📊',permission:'internship.stats.view',path:'/pages/teacher-internship/school-stats/index'},
    {label:'教师工作记录',icon:'🧭',permission:'internship.student.view',path:'/pages/teacher-internship/activity/index'}
    ,{label:'就业上报审核',icon:'🎓',permission:'internship.employment.view',path:'/pages/teacher-internship/employment/index'}
  ],priorityTodos:[],moreExpanded:false,moreItems:[
    {label:'风险处置',icon:'⚠️',permissions:['internship.risk.view'],path:'/pages/teacher-internship/internship-risk/index'},
    {label:'实习成绩',icon:'📊',permissions:['internship.score.view'],path:'/pages/teacher-internship/internship-score/index'},
    {label:'三方协议进度',icon:'📄',permissions:['internship.agreement.view'],path:'/pages/teacher-internship/agreement-confirm/index'},
    {label:'保险核验',icon:'🛡️',permissions:['internship.insurance.view'],path:'/pages/teacher-internship/insurance-verify/index'},
    {label:'计划任务确认',icon:'📌',permissions:['internship.task.view'],path:'/pages/teacher-internship/plan-task-review/index'},
    {label:'学生鉴定',icon:'📋',permissions:['internship.eval.self.view'],path:'/pages/teacher-internship/student-eval/index'},
    {label:'指导记录',icon:'📝',permissions:['internship.guidance.manage','internship.student.view'],path:'/pages/teacher-internship/internship-guidance/index'}
  ]}),
  computed:{
    context(){return useInternshipContextStore()},
    batchLabels(){return this.context.batches.map(b=>b.name||b.batchName||'实习批次')},
    batchIndex(){return Math.max(0,this.context.batches.findIndex(b=>String(b.id)===String(this.context.selectedBatchId)))},
    visibleItems(){return this.items.filter(item=>this.context.can(item.permission))},
    visibleMoreItems(){return this.moreItems.filter(item=>item.permissions.every(permission=>this.context.can(permission)))},
    primaryItems(){return this.visibleItems.filter(item=>item.primary)},
    workItems(){return this.visibleItems.filter(item=>!item.primary)},
    materialEntry(){return this.visibleItems.find(item=>item.path.includes('/material-review/'))},
    messageEntry(){return this.primaryItems.find(item=>item.path.includes('/messages/'))},
    shortcutItems(){const items=this.workItems.filter(item=>['实习学生','巡访任务','报告批阅'].includes(item.label));const guidance=this.visibleMoreItems.find(item=>item.path.includes('/internship-guidance/'));if(guidance)items.splice(Math.min(1,items.length),0,{...guidance,label:'新增指导'});return items},
    otherItems(){const shown=new Set(this.shortcutItems.map(item=>item.path));if(this.materialEntry)shown.add(this.materialEntry.path);return [...this.workItems,...this.visibleMoreItems].filter(item=>!shown.has(item.path))},
    todoGroups(){const labels={LEAVE:'请假与返岗',REPORT:'报告批阅',ATTENDANCE:'考勤办理',APPLICATION:'岗位申请',CHANGE:'实习变更',VISIT:'巡访整改',OTHER:'其他待办'};return Object.keys(labels).filter(key=>Number.isInteger(this.todoCounts[key])&&this.todoCounts[key]>0).map(key=>({key,label:labels[key],count:this.todoCounts[key],icon:key==='LEAVE'?'calendar':key==='ATTENDANCE'?'map-pin':'file-text'}))},
    canSwitchRole(){
      const roles=useSessionStore().availableContexts||[]
      return roles.filter((item)=>String(item.roleCode||'').toUpperCase()!=='STUDENT').length>1
    }
  },
  onLoad(query={}){this.requestedBatchId=String(query.batchId||'')},
  onShow(){this.hidden=false;this.roleName=this.displayRoleName(useSessionStore().identity);if(this.generation!==currentSessionGeneration()){this.moreExpanded=false;this.$refs.importantNotices?.reset();this.generation=currentSessionGeneration()}this.load()},
  onHide(){this.hidden=true;this.loadSequence++;this.$refs.importantNotices?.pause()},
  onUnload(){this.hidden=true;this.loadSequence++;this.$refs.importantNotices?.pause()},
  methods:{
    displayRoleName(identity={}) {
      const code=String(identity?.roleCode||'').trim().toUpperCase()
      const candidates=[identity?.roleName,...(identity?.availableRoles||[])
        .filter(role=>String(role.roleCode||'').trim().toUpperCase()===code).map(role=>role.roleName)]
      const name=candidates.find(value=>typeof value==='string' && /[\u3400-\u9fff]/.test(value) && (!code || !value.toUpperCase().includes(code)))
      return name?.trim() || ROLE_NAMES[code] || '当前工作身份'
    },
    async load(){const sequence=++this.loadSequence,generation=currentSessionGeneration(),current=()=>!this.hidden && sequence===this.loadSequence && generation===currentSessionGeneration();this.state='loading';this.error='';this.todoState='loading';this.priorityTodos=[];this.todoCounts={};this.todoTotal=0;try{await this.context.load(true);if(!current())return;if(this.requestedBatchId){if(!this.context.selectBatch(this.requestedBatchId))throw {httpStatus:403,message:'当前批次不在授权范围'};this.requestedBatchId=''};this.state='ready';await this.$nextTick();if(current())await Promise.all([this.loadTodoCounts(sequence,generation),this.$refs.importantNotices?.refresh()])}catch(e){if(current()){const shown=normalizeError(e);this.error=shown.pageState==='forbidden'?'当前身份没有岗位实习工作台权限，可切换到已有的业务身份。':shown.text;this.state=shown.pageState||'error'}}},
    async loadTodoCounts(sequence,generation){if(!this.context.can('internship.dashboard.view'))return;const current=()=>!this.hidden&&sequence===this.loadSequence&&generation===currentSessionGeneration();try{const data=await teacherApi.getInternshipWorkbenchTodos({status:'PENDING',group:'ALL',page:1,pageSize:3});if(!current())return;if(!Number.isInteger(data?.total)||data.total<0||!data.groupCounts)throw new Error('待办统计未完整返回');this.priorityTodos=Array.isArray(data.items)?data.items:[];this.todoTotal=data.total;this.todoCounts=data.groupCounts;this.todoState='ready'}catch{if(current()){this.todoState='error';this.priorityTodos=[];this.todoCounts={};this.todoTotal=0}}},
    changeBatch(e){const b=this.context.batches[Number(e.detail.value)];if(b&&this.context.selectBatch(b.id)){this.moreExpanded=false;this.load()}},
    open(item){
      if(!item?.path)return
      if(item.reportGateway){
        if(!this.context.can('internship.report.view'))return
        const sequence=this.loadSequence,generation=currentSessionGeneration()
        uni.showActionSheet({itemList:['周报批阅','日报、月报、总结批阅'],success:result=>{
          if(![0,1].includes(result.tapIndex)||this.hidden||sequence!==this.loadSequence||generation!==currentSessionGeneration()||!this.context.can('internship.report.view'))return
          this.open({path:result.tapIndex===0?'/pages/teacher-internship/internship-review/index?tab=weekly':item.path})
        }})
        return
      }
      const batch=this.context.selectedBatchId
      go(item.path+(batch?(item.path.includes('?')?'&':'?')+'batchId='+encodeURIComponent(batch):''))
    },
    openPriority(item){if(item.actionPath?.startsWith('/pages/teacher-internship/'))go(item.actionPath);else this.openTodoGroup(item.group||'ALL')},
    openTodoGroup(group){go('/pages/teacher-internship/todos/index?group='+encodeURIComponent(group))},
    itemIcon(item){if(/学生/.test(item.label))return'user';if(/巡访|考勤/.test(item.label))return'map-pin';if(/指导|报告/.test(item.label))return'file-text';if(/申请|任务/.test(item.label))return'clipboard-check';if(/风险|保险/.test(item.label))return'shield-exclamation';return'folder'},
    openRoleSwitch(){go('/pages/role-switch/index')},
    async logout(){try{await useSessionStore().logoutCurrentSession();this.context.clear();relaunch('/pages/login/index')}catch{this.error='退出失败，请重试'}}
  }
}
</script>

<style scoped>
.teacher-home{--brand-primary:var(--teacher-600);font-size:var(--font-size-md);padding-bottom:var(--space-6)}
.tw-content{display:flex;flex-direction:column;gap:var(--space-4);width:100%;max-width:760px;box-sizing:border-box;margin:0 auto}
.tw-context{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-1) 0}
.tw-context-copy{min-width:0;flex:1}.tw-role{display:block;margin-bottom:var(--space-1);font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.5}
.tw-batch-name{display:block;font-size:var(--font-size-xl);font-weight:var(--font-weight-semibold);line-height:1.5;color:var(--text-primary);overflow-wrap:anywhere}
.tw-switch{display:flex;align-items:center;min-height:44px;color:var(--teacher-700);font-size:var(--font-size-base)}
.tw-nav-actions{display:flex;align-items:center;flex-shrink:0}.tw-nav-action{min-height:44px;flex:none;white-space:nowrap;margin:0;padding:0 var(--space-2);background:transparent;border:0;color:var(--text-inverse);font-size:var(--font-size-base)}
.tw-nav-action::after,.tw-todo::after,.tw-all-todos::after,.tw-messages::after,.tw-main-action::after,.tw-shortcuts>button::after,.tw-more-toggle::after,.tw-item::after{border:0}
.tw-section-title{font-size:var(--font-size-xl);line-height:1.5;font-weight:var(--font-weight-semibold);color:var(--text-primary)}
.tw-total,.tw-scope{font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.6}.tw-scope{display:block;margin-top:var(--space-1)}
.tw-copy{display:block;font-size:var(--font-size-base);line-height:1.6;color:var(--text-secondary);font-weight:400;overflow-wrap:anywhere}
.tw-todos{padding:var(--space-4)}.tw-todo{display:flex;align-items:center;gap:var(--space-3);width:100%;margin:0;padding:var(--space-4) 0;border:0;border-bottom:1px solid var(--border-light);border-radius:0;background:transparent;text-align:left;line-height:1.5}
.tw-todo-title{display:block;font-size:var(--font-size-lg);font-weight:var(--font-weight-semibold);line-height:1.5;color:var(--text-primary);overflow-wrap:anywhere}
.tw-empty{padding:var(--space-4) 0}.tw-all-todos{width:100%;min-height:44px;margin:var(--space-2) 0 0;padding:0;border:0;background:transparent;color:var(--teacher-700);font-size:var(--font-size-md)}
.tw-material-entry{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-4);background:var(--teacher-50);border:1px solid var(--border-light)}
.tw-main-action{flex-shrink:0;min-height:44px;margin:0;padding:0 var(--space-3);line-height:44px;border:0;border-radius:var(--radius-md);background:var(--teacher-600);color:var(--text-inverse);font-size:var(--font-size-md)}
.tw-shortcuts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-radius:var(--radius-lg);overflow:hidden;background:var(--border-light);gap:1px}
.tw-shortcuts>button{display:flex;align-items:center;gap:var(--space-2);min-height:90px;width:100%;margin:0;padding:var(--space-3);background:var(--bg-card);border:0;border-radius:0;text-align:left;font-size:var(--font-size-md);line-height:1.5}
.tw-shortcuts .tw-todo-title{font-size:var(--font-size-md)}.tw-shortcuts .tw-copy{font-size:var(--font-size-sm)}
.tw-messages{display:flex;align-items:center;gap:var(--space-3);width:100%;min-height:80px;margin:0;padding:var(--space-4);border:0;border-radius:var(--radius-lg);background:var(--bg-card);text-align:left;line-height:1.5;box-sizing:border-box}
.tw-more-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:44px;margin:0;padding:var(--space-2) 0;border:0;background:transparent;color:var(--text-primary);font-size:var(--font-size-md);line-height:1.5;text-align:left}
.tw-more-toggle>text:last-child{color:var(--teacher-700)}.tw-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-3);margin-top:var(--space-2)}
.tw-item{display:flex;align-items:center;gap:var(--space-2);min-height:76px;width:100%;margin:0;padding:var(--space-3);border:0;border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-base);line-height:1.5;text-align:left;box-sizing:border-box}
.tw-label{min-width:0;overflow-wrap:anywhere;color:var(--text-primary)}.tw-help{max-width:760px;margin:auto}.tw-count-error{display:flex;flex-direction:column;gap:var(--space-2);padding-top:var(--space-3);font-size:var(--font-size-base);line-height:1.6;color:var(--warning-700)}
.tw-count-error>button{min-height:44px;margin:0;border:1px solid var(--teacher-600);background:transparent;color:var(--teacher-700);font-size:var(--font-size-base)}
button:focus-visible{outline:2px solid var(--teacher-600);outline-offset:-2px}
</style>
