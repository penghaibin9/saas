<template>
  <ModulePageShell
    title="系统管理中心"
    :subtitle="ctx.tenantBrandConfig.schoolName + ' · 先看结论，再进入账号、权限、组织、配置与审计工作区'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions><ModuleToolbar :actions="toolbarActions" @action="onToolbar" /></template>
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <ModuleHero
          :title="ctx.tenantBrandConfig.schoolName + ' · 系统运行总览'"
          :subtitle="'当前角色 ' + ctx.currentRole.roleName + ' · 数据范围 ' + ctx.dataScope.scopeName + ' · 运行事实来自服务端'"
          :stats="summary.stats"
        />

        <section v-if="quickTasks.length" class="sd-quick">
          <button v-for="task in quickTasks" :key="task.path" type="button" class="sd-quick__item" @click="$router.push(task.path)">
            <span class="sd-quick__kind">{{ task.kind }}</span><strong>{{ task.label }}</strong><small>{{ task.hint }}</small><span class="sd-quick__go">进入办理 →</span>
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
              <div v-else class="sd-clear"><strong>当前没有服务端返回的待处理项</strong><p>这只表示本次总览检查没有返回待办，不替代上线验收、真实角色测试或业务中心自己的阻断检查。</p></div>
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
              <div v-else class="sd-clear"><strong>当前没有服务端返回的安全提醒</strong><p>安全变更、访问拒绝和异常登录仍应通过对应治理页与审计记录核对。</p></div>
            </div>
          </section>
        </div>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">最近系统操作</span><span class="mp-note">审计日志不可删除；查看与导出继续受权限、脱敏和水印控制</span></header>
          <div class="mp-card__body" style="padding-top:0">
            <table v-if="summary.recentOps.length" class="mp-audit"><thead><tr><th style="width:220px">操作人</th><th>动作</th><th style="width:140px">时间</th></tr></thead>
              <tbody><tr v-for="r in summary.recentOps" :key="r.id"><td class="is-who">{{ r.who }}</td><td>{{ auditActionLabel(r) }}</td><td>{{ r.time }}</td></tr></tbody></table>
            <div v-else class="sd-clear sd-clear--compact"><strong>暂无最近操作回执</strong><p>空记录不等于审计服务异常；需要进一步确认时进入操作日志查看完整查询状态。</p></div>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, ModuleHero, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
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
  name:'SystemDashboardView',components:{ ModulePageShell,ModuleToolbar,ModuleHero,StatusTag,RiskTag,LoadingState,ErrorState },props:{ ctx:{ type:Object,required:true } },
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
.sd-quick{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-3)}.sd-quick__item{min-width:0;padding:16px;border:1px solid var(--border-light);border-radius:12px;background:var(--bg-card);color:var(--text-primary);text-align:left;cursor:pointer;transition:border-color .15s,box-shadow .15s,transform .15s}.sd-quick__item:hover{border-color:var(--primary-200);box-shadow:0 6px 18px rgba(36,63,128,.07);transform:translateY(-1px)}.sd-quick__kind{display:inline-flex;padding:2px 7px;border-radius:999px;background:var(--primary-50);color:var(--primary-700);font-size:10px;font-weight:650}.sd-quick__item strong,.sd-quick__item small{display:block}.sd-quick__item strong{margin-top:10px;font-size:14px}.sd-quick__item small{min-height:38px;margin-top:5px;color:var(--text-secondary);font-size:11px;line-height:1.65}.sd-quick__go{display:block;margin-top:10px;color:var(--primary-700);font-size:11px;font-weight:600}.sd-todo{display:flex;width:100%;align-items:center;gap:var(--space-3);padding:11px 0;border:0;border-bottom:1px dashed var(--border-light);background:transparent;color:inherit;text-align:left;cursor:pointer}.sd-todo:last-child{border-bottom:none}.sd-todo__main{flex:1;min-width:0}.sd-todo__main>span{display:block}.sd-clear{padding:20px 4px;color:var(--text-secondary);font-size:12px;line-height:1.75}.sd-clear strong{color:var(--text-primary)}.sd-clear p{margin:6px 0 0}.sd-clear--compact{padding-block:14px}@media(max-width:1080px){.sd-quick{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.sd-quick{grid-template-columns:1fr}}
</style>
