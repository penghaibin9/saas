<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="站内信" :subtitle="'岗位实习消息 · 未读 '+unread" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="msg-tabs"><button v-for="tab in tabs" :key="tab.key" class="msg-tab" :class="{on:category===tab.key}" @click="selectCategory(tab.key)">{{ tab.label }}</button></view>
        <view v-for="row in items" :key="row.messageId" class="card msg-item" :class="{unread:row.readStatus==='UNREAD'}" @click="openMessage(row)">
          <view class="row-between"><text class="msg-title">{{ row.title }}</text><MobileStatusTag v-if="row.readStatus==='UNREAD'" type="warning">未读</MobileStatusTag></view>
          <text class="msg-summary">{{ expanded===row.messageId ? row.content : row.summary }}</text><text class="msg-meta">{{ categoryLabel(row.category) }} · {{ row.createdAt || '时间待确认' }}</text>
        </view>
        <MobileGlobalState v-if="!items.length" state="empty" title="暂无站内信" description="岗位实习业务消息、提醒和系统通知会显示在这里。" />
        <button v-if="hasMore" class="btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore?'加载中…':'加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import teacherApi from '@/services/teacherApi'
import { toast } from '@/utils/nav'
export default {
  data:()=>({state:'loading',error:'',items:[],category:'ALL',page:1,pageSize:20,hasMore:false,unread:0,expanded:'',loadingMore:false,tabs:[{key:'ALL',label:'全部'},{key:'ANNOUNCEMENT',label:'公告'},{key:'BUSINESS',label:'业务'},{key:'TODO',label:'待办'},{key:'SYSTEM',label:'系统'}]}),
  onLoad(){this.load()},onPullDownRefresh(){this.load().finally(()=>uni.stopPullDownRefresh())},
  methods:{
    categoryLabel(v){return ({ANNOUNCEMENT:'公告',BUSINESS:'业务',TODO:'待办',SYSTEM:'系统',EMERGENCY:'紧急'}[String(v||'').toUpperCase()]||'消息')},
    selectCategory(k){if(k===this.category)return;this.category=k;this.load()},
    async load(){this.state='loading';this.error='';this.page=1;try{const d=await teacherApi.getInternshipWorkbenchMessages({category:this.category,page:1,pageSize:this.pageSize});this.items=d?.items||[];this.hasMore=!!d?.hasMore;this.unread=Number(d?.unread||0);this.state='ready'}catch(e){this.error=e?.message||'站内信加载失败';this.state='error'}},
    async loadMore(){if(this.loadingMore||!this.hasMore)return;this.loadingMore=true;try{const n=this.page+1,d=await teacherApi.getInternshipWorkbenchMessages({category:this.category,page:n,pageSize:this.pageSize});this.items=[...this.items,...(d?.items||[])];this.page=n;this.hasMore=!!d?.hasMore;this.unread=Number(d?.unread||this.unread)}finally{this.loadingMore=false}},
    async openMessage(row){this.expanded=this.expanded===row.messageId?'':row.messageId;if(row.readStatus!=='UNREAD')return;try{const u=await teacherApi.readInternshipWorkbenchMessage(row.messageId);row.readStatus=u?.readStatus||'READ';row.readAt=u?.readAt||row.readAt;this.unread=Math.max(0,this.unread-1)}catch(e){toast(e?.message||'消息已读状态更新失败')}}
  }
}
</script>
<style scoped>
.msg-tabs{display:flex;gap:7px;overflow-x:auto}.msg-tab{margin:0;padding:0 11px;min-height:34px;line-height:34px;border-radius:18px;background:var(--gray-100);font-size:12px;color:var(--text-secondary)}.msg-tab::after{border:0}.msg-tab.on{background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-weight:650}.msg-item{display:flex;flex-direction:column;gap:8px;padding:14px;border-left:3px solid transparent}.msg-item.unread{border-left-color:var(--teacher-500,#3b82f6)}.msg-title{font-size:14px;font-weight:650;color:var(--text-primary);line-height:1.5}.msg-summary{font-size:12px;color:var(--text-secondary);line-height:1.65;white-space:pre-wrap}.msg-meta{font-size:11px;color:var(--text-tertiary)}
</style>