<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="分类待办" subtitle="岗位实习真实业务待办" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <scroll-view scroll-x class="td-filters"><view class="td-filter-row"><button v-for="f in filters" :key="f.key" class="td-filter" :class="{on:group===f.key}" @click="selectGroup(f.key)">{{ f.label }} {{ counts[f.key] || 0 }}</button></view></scroll-view>
        <MobileInlineAlert type="info" description="待办必须进入对应业务页面完成真实审核/处置；本页不提供脱离业务事实的直接完成按钮。" />
        <view v-for="row in items" :key="row.todoId" class="card td-item">
          <view class="row-between"><view class="td-copy"><text class="td-title">{{ row.title }}</text><text class="td-meta">{{ row.groupLabel }} · {{ row.typeLabel }}</text></view><MobileStatusTag :status="row.status" :label="row.status==='PENDING'?'待处理':'已处理'" /></view>
          <text v-if="row.dueAt" class="td-meta">截止：{{ row.dueAt }}</text>
          <button v-if="row.actionPath && row.status==='PENDING'" class="btn btn-primary" @click="openTodo(row)">进入真实业务办理</button>
          <text v-else-if="row.status==='PENDING'" class="td-meta">该历史待办暂无移动端办理映射，请在教师 PC 端处理。</text>
        </view>
        <MobileGlobalState v-if="!items.length" state="empty" title="当前分类暂无待办" description="新的岗位实习审核或处置任务生成后会自动进入这里。" />
        <button v-if="hasMore" class="btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore?'加载中…':'加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import teacherApi from '@/services/teacherApi'
import { go } from '@/utils/nav'
export default {
  data:()=>({state:'loading',error:'',items:[],counts:{},labels:{},group:'ALL',page:1,pageSize:30,hasMore:false,loadingMore:false}),
  computed:{filters(){const o=['ALL','REPORT','ATTENDANCE','APPLICATION','LEAVE','CHANGE','VISIT','OTHER'];const d={ALL:'全部',REPORT:'报告批阅',ATTENDANCE:'考勤',APPLICATION:'岗位申请',LEAVE:'请假',CHANGE:'变更',VISIT:'巡访',OTHER:'其他'};return o.map(key=>({key,label:this.labels[key]||d[key]||key}))}},
  onLoad(){this.load()},onPullDownRefresh(){this.load().finally(()=>uni.stopPullDownRefresh())},
  methods:{
    selectGroup(key){if(key===this.group)return;this.group=key;this.load()},
    async load(){this.state='loading';this.error='';this.page=1;try{const d=await teacherApi.getInternshipWorkbenchTodos({status:'PENDING',group:this.group,page:1,pageSize:this.pageSize});this.items=d?.items||[];this.counts=d?.groupCounts||{};this.labels=d?.groupLabels||{};this.hasMore=!!d?.hasMore;this.state='ready'}catch(e){this.error=e?.message||'分类待办加载失败';this.state='error'}},
    async loadMore(){if(this.loadingMore||!this.hasMore)return;this.loadingMore=true;try{const n=this.page+1,d=await teacherApi.getInternshipWorkbenchTodos({status:'PENDING',group:this.group,page:n,pageSize:this.pageSize});this.items=[...this.items,...(d?.items||[])];this.page=n;this.hasMore=!!d?.hasMore}finally{this.loadingMore=false}},
    openTodo(row){if(row?.actionPath)go(row.actionPath)}
  }
}
</script>
<style scoped>
.td-filters{width:100%;white-space:nowrap}.td-filter-row{display:inline-flex;gap:8px;padding-bottom:4px}.td-filter{margin:0;padding:0 12px;min-height:34px;line-height:34px;border-radius:18px;background:var(--gray-100);font-size:12px;color:var(--text-secondary)}.td-filter::after{border:0}.td-filter.on{background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-weight:650}.td-item{display:flex;flex-direction:column;gap:10px;padding:14px}.td-copy{min-width:0;flex:1}.td-title{display:block;font-size:14px;font-weight:650;color:var(--text-primary);line-height:1.5}.td-meta{display:block;margin-top:3px;font-size:11px;color:var(--text-tertiary)}
</style>