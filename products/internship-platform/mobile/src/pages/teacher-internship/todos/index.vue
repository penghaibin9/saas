<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-todos internship-flow">
    <MobileNavBar variant="teacher" title="分类待办" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <text class="td-meta">本人全部批次的待处理事项</text>
        <view class="td-filter-row"><button v-for="f in visibleFilters" :key="f.key" class="mobile-control td-filter" :class="{on:group===f.key}" @click="selectGroup(f.key)">{{ f.label }} {{ counts[f.key] ?? '—' }}</button><button v-if="visibleFilters.length < filters.length || allFiltersOpen" class="mobile-control td-filter" :aria-expanded="allFiltersOpen" @click="allFiltersOpen=!allFiltersOpen">{{ allFiltersOpen ? '收起零待办分类' : '全部分类' }}</button></view>
        <view v-for="row in items" :key="row.todoId" class="card td-item">
          <view class="row-between"><view class="td-copy"><text class="td-title">{{ row.title }}</text><text class="td-meta">{{ row.groupLabel }} · {{ row.typeLabel }}</text></view><MobileStatusTag :status="row.status" :label="row.status==='PENDING'?'待处理':'已处理'" /></view>
          <text v-if="row.dueAt" class="td-meta">截止：{{ row.dueAt }}</text>
          <button v-if="row.actionPath && row.status==='PENDING'" class="mobile-control btn btn-primary" @click="openTodo(row)">去处理</button>
          <text v-else-if="row.status==='PENDING'" class="td-meta">该事项当前无法直接打开，请刷新待办或联系实习管理员核对。</text>
        </view>
        <MobileGlobalState v-if="!items.length" class="td-empty" state="empty" :title="counts.ALL === 0 ? '暂无待办' : '当前分类暂无待办'" :description="counts.ALL === 0 ? undefined : '可查看有待办的其他分类，或展开全部分类。'" />
        <MobileInlineAlert v-if="loadMoreError" type="warning" :description="loadMoreError" />
        <button v-if="hasMore" class="mobile-control btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore?'加载中…':'加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import teacherApi from '@/services/teacherApi'
import { go } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
export default {
  data:()=>({state:'loading',error:'',items:[],counts:{},labels:{},group:'ALL',page:1,pageSize:30,hasMore:false,loadingMore:false,allFiltersOpen:false,loadMoreError:'',sequence:0,hidden:false}),
  computed:{filters(){const o=['ALL','REPORT','ATTENDANCE','APPLICATION','LEAVE','CHANGE','VISIT','OTHER'];const d={ALL:'全部',REPORT:'报告批阅',ATTENDANCE:'考勤',APPLICATION:'岗位申请',LEAVE:'请假与返岗',CHANGE:'变更',VISIT:'巡访',OTHER:'其他'};return o.map(key=>({key,label:this.labels[key]||d[key]}))},visibleFilters(){return this.filters.filter(f=>this.allFiltersOpen || f.key==='ALL' || f.key===this.group || this.counts[f.key]>0)}},
  onLoad(options={}){if(this.filters.some(item=>item.key===options.group))this.group=options.group},
  onShow(){this.hidden=false;return this.load()},onHide(){this.hidden=true;this.sequence++;this.items=[];this.counts={};this.labels={}},onUnload(){this.hidden=true;this.sequence++},onPullDownRefresh(){this.load().finally(()=>uni.stopPullDownRefresh())},
  methods:{
    selectGroup(key){if(key===this.group)return;this.group=key;this.load()},
    current(sequence,generation,group){return !this.hidden && sequence===this.sequence && generation===currentSessionGeneration() && group===this.group},
    async load(){const sequence=++this.sequence,generation=currentSessionGeneration(),group=this.group;this.state='loading';this.error='';this.loadMoreError='';this.loadingMore=false;this.page=1;this.items=[];this.counts={};try{const d=await teacherApi.getInternshipWorkbenchTodos({status:'PENDING',group,page:1,pageSize:this.pageSize});if(!this.current(sequence,generation,group))return;if(!Array.isArray(d?.items)||!d.groupCounts)throw Error('待办读取未完整返回，请重新读取');this.items=d.items;this.counts=d.groupCounts;this.labels=d.groupLabels||{};this.hasMore=d.hasMore===true;this.state='ready'}catch(e){if(this.current(sequence,generation,group)){this.error=e?.message||'分类待办加载失败';this.state='error'}}},
    async loadMore(){if(this.loadingMore||!this.hasMore||this.state!=='ready')return;const sequence=this.sequence,generation=currentSessionGeneration(),group=this.group;this.loadingMore=true;this.loadMoreError='';try{const n=this.page+1,d=await teacherApi.getInternshipWorkbenchTodos({status:'PENDING',group,page:n,pageSize:this.pageSize});if(!this.current(sequence,generation,group))return;if(!Array.isArray(d?.items))throw Error('待办读取未完整返回');this.items=[...this.items,...d.items];this.page=n;this.hasMore=d.hasMore===true}catch(e){if(this.current(sequence,generation,group))this.loadMoreError=e?.message||'后续待办读取失败，请重试'}finally{if(this.current(sequence,generation,group))this.loadingMore=false}},
    openTodo(row){if(row?.actionPath)go(row.actionPath)}
  }
}
</script>
<style scoped>
.td-empty :deep(.mgs-desc){display:none}
.td-filters{width:100%;white-space:nowrap}.td-filter-row{display:inline-flex;gap:8px;padding-bottom:4px}.td-filter{margin:0;padding:0 12px;min-height:34px;line-height:34px;border-radius:18px;background:var(--gray-100);font-size:12px;color:var(--text-secondary)}.td-filter::after{border:0}.td-filter.on{background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-weight:650}.td-item{display:flex;flex-direction:column;gap:10px;padding:14px}.td-copy{min-width:0;flex:1}.td-title{display:block;font-size:14px;font-weight:650;color:var(--text-primary);line-height:1.5}.td-meta{display:block;margin-top:3px;font-size:11px;color:var(--text-tertiary)}
.teacher-todos :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-todos .card{border-radius:8px;box-shadow:none}.td-filter{min-height:44px;line-height:44px;font-size:14px;border-radius:8px}.td-title{font-size:16px;line-height:24px}.td-meta{font-size:14px;line-height:22px}.teacher-todos .btn{min-height:44px;font-size:15px}.td-copy{overflow-wrap:anywhere}
.td-filter-row{display:flex;flex-wrap:wrap;gap:8px;white-space:normal}
</style>
