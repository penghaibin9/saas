<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-messages">
    <MobileNavBar variant="teacher" title="站内信" :subtitle="'未读 '+unread+' 条'" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="msg-tabs"><button class="mobile-control msg-tab" :class="{on:!onlyUnread}" @click="setUnread(false)">全部消息</button><button class="mobile-control msg-tab" :class="{on:onlyUnread}" @click="setUnread(true)">未读消息</button></view>
        <text class="msg-meta">阅读后记为已读，事项仍需进入原单办理。</text>
        <view class="msg-tabs"><button v-for="tab in tabs" :key="tab.key" class="mobile-control msg-tab" :class="{on:category===tab.key}" @click="selectCategory(tab.key)">{{ tab.label }}</button></view>
        <view v-for="row in items" :key="row.messageId" class="card msg-item" :class="{unread:row.readStatus==='UNREAD'}" role="button" :aria-expanded="expanded===row.messageId" @click="openMessage(row)">
          <view class="row-between"><text class="msg-title">{{ row.title }}</text><MobileStatusTag v-if="row.readStatus==='UNREAD'" status="UNREAD" label="未读" /></view>
          <text class="msg-summary" :class="{'is-expanded':expanded===row.messageId}">{{ expanded===row.messageId ? row.content : row.summary }}</text>
          <view class="msg-foot"><text class="msg-meta">{{ categoryLabel(row.category) }} · {{ row.createdAt ? formatDateTime(row.createdAt) : '时间待确认' }}</text><text class="msg-toggle">{{ expanded===row.messageId ? '收起' : '展开全文' }}</text></view>
          <button v-if="row.hasBusinessTarget" class="mobile-control btn btn-ghost" :disabled="!!openingTarget" @click.stop="openBusiness(row)">{{ openingTarget===row.messageId ? '正在打开…' : '查看志愿原单' }}</button>
          <MobileInlineAlert v-if="targetMessageId===row.messageId && targetError" type="warning" :description="targetError" />
          <button v-if="expanded===row.messageId && !row.hasBusinessTarget && (['BUSINESS','TODO'].includes(row.category) || row.sourceModule==='internship' && row.sourceBizId)" class="mobile-control btn btn-ghost" @click.stop="openTodos">查看本人分类待办</button>
        </view>
        <MobileGlobalState v-if="!items.length" state="empty" title="暂无站内信" description="可切换其他分类查看。" />
        <MobileInlineAlert v-if="loadMoreError" type="warning" :description="loadMoreError" />
        <button v-if="hasMore" class="mobile-control btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore?'加载中…':'加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import teacherApi from '@/services/teacherApi'
import { toast, go } from '@/utils/nav'
import { formatDateTime } from '@/utils/format'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
export default {
  data:()=>({openingTarget:'',targetMessageId:'',targetError:'',onlyUnread:false,sequence:0,hidden:false,reading:{},loadMoreError:'',state:'loading',error:'',items:[],category:'ALL',page:1,pageSize:20,hasMore:false,unread:0,expanded:'',loadingMore:false,tabs:[{key:'ALL',label:'全部'},{key:'EMERGENCY',label:'紧急'},{key:'ANNOUNCEMENT',label:'公告'},{key:'BUSINESS',label:'业务'},{key:'TODO',label:'待办'},{key:'SYSTEM',label:'系统'}]}),
  onLoad(){this.load()},onShow(){if(this.hidden){this.hidden=false;this.load()}},onHide(){this.hidden=true;this.sequence++;this.openingTarget='';this.targetMessageId='';this.targetError='';this.items=[];this.unread=0;this.reading={};this.expanded=''},onUnload(){this.hidden=true;this.sequence++},onPullDownRefresh(){this.load().finally(()=>uni.stopPullDownRefresh())},
  methods:{
    formatDateTime,
    async openBusiness(row){
      if(this.openingTarget || !row.hasBusinessTarget || !this.items.includes(row))return
      const sequence=this.sequence,generation=currentSessionGeneration(),messageId=String(row.messageId)
      this.openingTarget=messageId;this.targetMessageId=messageId;this.targetError=''
      try{
        const target=await teacherApi.getInternshipMessageTarget(messageId)
        if(!this.current(sequence,generation)||this.targetMessageId!==messageId||!this.items.includes(row))return
        if(target?.messageId!==messageId || target.pageKey!=='TEACHER_INTERNSHIP_VOLUNTEERS' || !['batchId','campaignId','groupId'].every(key=>typeof target[key]==='string' && /^[1-9]\d*$/.test(target[key])))throw Error('原单链接无法确认，请从分类待办查看')
        go('/pages/teacher-internship/internship-volunteers/index?'+['batchId','campaignId','groupId'].map(key=>key+'='+encodeURIComponent(String(target[key]))).join('&')+'&from=messages')
      }catch(e){if(this.current(sequence,generation))this.targetError=normalizeError(e).text}
      finally{if(this.current(sequence,generation))this.openingTarget=''}
    },
    setUnread(value){if(this.onlyUnread===value)return;this.onlyUnread=value;this.load()},
    openTodos(){go('/pages/teacher-internship/todos/index?group=ALL')},
    current(sequence,generation){return !this.hidden && sequence===this.sequence && generation===currentSessionGeneration()},
    categoryLabel(v){return ({ANNOUNCEMENT:'公告',BUSINESS:'业务',TODO:'待办',SYSTEM:'系统',EMERGENCY:'紧急'}[String(v||'').toUpperCase()]||'消息')},
    selectCategory(k){if(k===this.category)return;this.category=k;this.load()},
    async load(){const sequence=++this.sequence,generation=currentSessionGeneration();this.state='loading';this.openingTarget='';this.targetMessageId='';this.targetError='';this.error='';this.loadMoreError='';this.loadingMore=false;this.page=1;this.items=[];this.expanded='';try{const d=await teacherApi.getInternshipWorkbenchMessages({category:this.category,readStatus:this.onlyUnread?'UNREAD':'',page:1,pageSize:this.pageSize});if(!this.current(sequence,generation))return;if(!Array.isArray(d?.items)||!Number.isInteger(d.unread)||d.unread<0)throw Error('消息读取未完整返回，请重试');this.items=d.items;this.hasMore=d.hasMore===true;this.unread=d.unread;this.state='ready'}catch(e){if(this.current(sequence,generation)){this.error=e?.message||'站内信加载失败';this.state='error'}}},
    async loadMore(){if(this.loadingMore||!this.hasMore||this.state!=='ready')return;const sequence=this.sequence,generation=currentSessionGeneration();this.loadingMore=true;this.loadMoreError='';try{const n=this.page+1,d=await teacherApi.getInternshipWorkbenchMessages({category:this.category,readStatus:this.onlyUnread?'UNREAD':'',page:n,pageSize:this.pageSize});if(!this.current(sequence,generation))return;if(!Array.isArray(d?.items)||!Number.isInteger(d.unread)||d.unread<0)throw Error('消息读取未完整返回');this.items=[...this.items,...d.items];this.page=n;this.hasMore=d.hasMore===true;this.unread=d.unread}catch(e){if(this.current(sequence,generation))this.loadMoreError=e?.message||'后续消息读取失败，请重试'}finally{if(this.current(sequence,generation))this.loadingMore=false}},
    async openMessage(row){this.expanded=this.expanded===row.messageId?'':row.messageId;if(row.readStatus!=='UNREAD'||this.reading[row.messageId])return;const sequence=this.sequence,generation=currentSessionGeneration();this.reading={...this.reading,[row.messageId]:true};try{const u=await teacherApi.readInternshipWorkbenchMessage(row.messageId);if(!this.current(sequence,generation)||!this.items.includes(row))return;if(String(u?.messageId)!==String(row.messageId)||u.readStatus!=='READ')throw Error('已读回执未确认，请重试');row.readStatus='READ';row.readAt=u.readAt||row.readAt;this.unread=Math.max(0,this.unread-1)}catch(e){if(this.current(sequence,generation))toast(e?.message||'消息已读状态更新失败')}finally{if(this.current(sequence,generation))this.reading={...this.reading,[row.messageId]:false}}}
  }
}
</script>
<style scoped>
.msg-tabs{display:flex;gap:7px;overflow-x:auto}.msg-tab{margin:0;padding:0 11px;min-height:34px;line-height:34px;border-radius:18px;background:var(--gray-100);font-size:12px;color:var(--text-secondary)}.msg-tab::after{border:0}.msg-tab.on{background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-weight:650}.msg-item{display:flex;flex-direction:column;gap:8px;padding:14px;border-left:3px solid transparent}.msg-item.unread{border-left-color:var(--teacher-500,#3b82f6)}.msg-title{font-size:14px;font-weight:650;color:var(--text-primary);line-height:1.5}.msg-summary{font-size:12px;color:var(--text-secondary);line-height:1.65;white-space:pre-wrap}.msg-meta{font-size:11px;color:var(--text-tertiary)}
.teacher-messages :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-messages .card{border-radius:8px;box-shadow:none}.msg-tab{min-height:44px;line-height:44px;font-size:14px;border-radius:8px;flex-shrink:0}.msg-title{font-size:16px;line-height:24px;overflow-wrap:anywhere}.msg-summary{font-size:14px;line-height:1.65;overflow-wrap:anywhere}.msg-summary:not(.is-expanded){display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.msg-foot{display:flex;justify-content:space-between;align-items:center;gap:12px}.msg-meta{font-size:14px;line-height:22px;min-width:0}.msg-toggle{display:flex;align-items:center;min-height:44px;flex-shrink:0;font-size:14px;color:var(--brand-primary)}.teacher-messages .btn{min-height:44px;font-size:15px}
</style>
