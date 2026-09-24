<template>
  <ModulePageShell
    title="系统管理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template v-if="summary" #summary>
      <div class="sd-summary" aria-label="系统运行摘要">
        <span v-for="item in summary.stats" :key="item.label"><strong>{{ item.value }}</strong>{{ item.label }}</span>
      </div>
    </template>
    <template #actions><ModuleToolbar :actions="toolbarActions" @action="onToolbar" /></template>
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <div v-else-if="loading" class="sd-loading" role="status">正在读取待办与异常…</div>
      <template v-else>
        <section v-if="quickTasks.length" class="sd-quick">
          <button v-for="task in quickTasks" :key="task.path" type="button" class="sd-quick__item" :title="task.hint" @click="$router.push(task.path)">
            <span class="sd-quick__kind">{{ task.kind }}</span><strong>{{ task.label }}</strong><span class="sd-quick__go" aria-hidden="true">→</span>
          </button>
        </section>

        <div class="mp-grid-2">
          <section class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">现在需要处理</span><button class="mp-link" @click="$router.push('/admin/system/implementation/overview')">实施与验收 →</button></header>
            <div class="mp-card__body">
              <div v-if="summary.todos.length">
                <button v-for="t in summary.todos" :key="t.id" type="button" class="sd-todo" @click="$router.push(t.route)">
                  <StatusTag :type="t.tone" :label="t.count + ' 项'" />
                  <span class="sd-todo__main"><span class="mp-cell-main">{{ t.label }}</span><span class="mp-cell-sub">{{ t.hint }}</span></span>
                  <span class="mp-link">去处理 →</span>
                </button>
              </div>
              <div v-else class="sd-clear">暂无待处理事项</div>
            </div>
          </section>

          <section class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">安全提醒</span><button class="mp-link" @click="$router.push('/admin/system/logs?tab=login')">登录日志 →</button></header>
            <div class="mp-card__body">
              <ul v-if="summary.securityAlerts.length" class="mp-timeline">
                <li v-for="a in summary.securityAlerts" :key="a.id" class="mp-timeline__item" :class="a.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                  <div class="mp-timeline__title">{{ a.title }} <RiskTag :level="a.level" /></div><div class="mp-timeline__desc">{{ a.detail }}</div><div class="mp-timeline__time">{{ a.time }}</div>
                </li>
              </ul>
              <div v-else class="sd-clear">暂无安全提醒</div>
            </div>
          </section>
        </div>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">最近系统操作</span><button class="mp-link" @click="$router.push('/admin/system/logs?tab=operation')">查看全部 →</button></header>
          <div class="mp-card__body" style="padding-top:0">
            <table v-if="summary.recentOps.length" class="mp-audit"><thead><tr><th style="width:220px">操作人</th><th>动作</th><th style="width:140px">时间</th></tr></thead>
              <tbody><tr v-for="r in summary.recentOps" :key="r.id"><td class="is-who">{{ r.who }}</td><td>{{ auditActionLabel(r) }}</td><td>{{ r.time }}</td></tr></tbody></table>
            <div v-else class="sd-clear sd-clear--compact">暂无最近操作</div>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, ErrorState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'
import { presentAuditRecord } from '@/utils/presentationSafety'
import { matchPermission } from '@/config/navPlan.js'

const QUICK_TASKS = Object.freeze([
  { kind:'账号',label:'教职工账号',hint:'核对身份、账号状态与角色来源',path:'/admin/system/accounts/staff',permissionKey:'systemAdmin.user.view' },
  { kind:'权限',label:'学校角色与权限',hint:'按角色连续核对权限、成员与数据范围',path:'/admin/system/iam?surface=roles',permissionKey:'systemAdmin.role.view' },
  { kind:'范围',label:'数据范围',hint:'先选规则，再核对角色引用与显式禁止',path:'/admin/system/scopes',permissionKey:'systemAdmin.scope.view' },
  { kind:'组织',label:'组织与班级',hint:'维护当前组织，未来版本与任职关系分开处理',path:'/admin/system/org',permissionKey:'systemAdmin.org.view' },
  { kind:'配置',label:'模块与业务开关',hint:'区分平台授权、学校开关与运行就绪',path:'/admin/system/module-entitlements',permissionKey:'systemAdmin.config.feature.view' },
  { kind:'审计',label:'操作审计',hint:'按对象和结果定位一次真实操作及证据',path:'/admin/system/logs?tab=operation',permissionKey:'systemAdmin.audit.view' }
])
export default {
  name:'SystemDashboardView',components:{ ModulePageShell,ModuleToolbar,StatusTag,RiskTag,ErrorState },props:{ ctx:{ type:Object,required:true } },
  data(){ return { loading:true,error:'',summary:null } },
  computed:{
    toolbarActions(){ const pa=this.ctx.permissionActions; return [{key:'importUsers',label:'学生导入与账号开通'},{key:'viewOperationLogs',label:'≡ 操作日志'}].filter(a=>pa[a.key]&&pa[a.key].visible).map(a=>({...a,disabled:!pa[a.key].allowed,disabledReason:pa[a.key].reason})) },
    quickTasks(){ const patterns=this.ctx.permissionPatterns; return Array.isArray(patterns)?QUICK_TASKS.filter(t=>matchPermission(patterns,t.permissionKey)):[] }
  },
  created(){ this.load() },
  methods:{
    auditActionLabel(row){ return presentAuditRecord(row).displayAction },
    onToolbar(key){ if(key==='importUsers')this.$router.push('/admin/system/identity-import/students'); if(key==='viewOperationLogs')this.$router.push('/admin/system/logs') },
    async load(){ this.loading=true;this.error='';const res=await systemApi.getDashboardSummary();if(res.code===0)this.summary=res.data;else{this.error=res.message;toast.error(res.message)}this.loading=false }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sd-summary{display:flex;align-items:center;gap:0;overflow-x:auto;scrollbar-width:none}.sd-summary::-webkit-scrollbar,.sd-quick::-webkit-scrollbar{display:none}.sd-summary span{display:flex;align-items:baseline;gap:5px;padding:0 14px;border-right:1px solid var(--line,#dce5f3);color:var(--text-secondary);font-size:12px;white-space:nowrap}.sd-summary span:first-child{padding-left:0}.sd-summary span:last-child{border-right:0}.sd-summary strong{color:var(--text-primary);font-size:18px;font-variant-numeric:tabular-nums}.sd-loading{min-height:44px;display:flex;align-items:center;padding:0 14px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);color:var(--text-secondary);font-size:12px}.sd-quick{display:flex;align-items:stretch;gap:8px;overflow-x:auto;scrollbar-width:none}.sd-quick__item{display:flex;flex:1 0 145px;align-items:center;gap:8px;min-height:42px;padding:7px 10px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);color:var(--text-primary);text-align:left;cursor:pointer}.sd-quick__item:hover{border-color:var(--primary-200);background:var(--primary-50)}.sd-quick__kind{display:inline-flex;padding:2px 6px;border-radius:5px;background:var(--primary-50);color:var(--primary-700);font-size:10px;font-weight:650}.sd-quick__item strong{flex:1;font-size:13px;white-space:nowrap}.sd-quick__go{color:var(--primary-700);font-size:13px;font-weight:600}.sd-todo{display:flex;width:100%;align-items:center;gap:var(--space-3);padding:11px 0;border:0;border-bottom:1px dashed var(--border-light);background:transparent;color:inherit;text-align:left;cursor:pointer}.sd-todo:last-child{border-bottom:none}.sd-todo__main{flex:1;min-width:0}.sd-todo__main>span{display:block}.sd-clear{padding:18px 4px;color:var(--text-secondary);font-size:12px}.sd-clear--compact{padding-block:14px}@media(max-width:700px){.sd-summary span{padding-inline:9px}.sd-quick__item{flex-basis:132px}}
</style>
