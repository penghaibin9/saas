<template>
  <view class="mobile-page mobile-student page-wrap">
    <MobileNavBar title="消息通知" show-back fallback-url="/pages/student-internship/index">
      <template #right><button class="mobile-control messages-refresh" @click="load(page)">刷新</button></template>
    </MobileNavBar>
    <view class="page-pad stack">
      <view class="message-filters"><button v-for="filter in [{value:'',label:'全部消息'},{value:'UNREAD',label:'未读'},{value:'READ',label:'已读'}]" :key="filter.value" class="mobile-control btn" :class="readFilter===filter.value ? 'btn-primary' : 'btn-ghost'" :aria-pressed="readFilter===filter.value" @click="selectReadFilter(filter.value)">{{ filter.label }}</button></view>
      <text v-if="items.length || detail" class="messages-hint">已读不代表业务办结。</text>
      <MobileGlobalState :state="state" :description="error" @retry="load(page)">
        <view class="stack">
          <button v-for="row in items" :key="row.messageId" class="mobile-control card message-item" @click="openMessage(row.messageId)">
            <text class="t-bold">{{ row.title || '学校消息' }}</text>
            <text class="message-content message-summary">{{ row.summary }}</text>
            <text>{{ row.readStatus === 'READ' ? '已读' : '未读' }}</text>
          </button>
          <MobileGlobalState v-if="!items.length" state="empty" title="暂无消息通知" description="收到学校或教师消息后会显示在这里。" />
          <view v-if="page > 1 || hasMore" class="message-pages"><button class="mobile-control" :disabled="page<=1" @click="load(page-1)">上一页</button><text>共{{ total }}条，第{{ page }}页</text><button class="mobile-control" :disabled="!hasMore" @click="load(page+1)">下一页</button></view>
        </view>
      </MobileGlobalState>
      <view v-if="detailLoading || detailError || detail" class="card message-detail">
        <text v-if="detailLoading">正在读取消息正文…</text>
        <MobileInlineAlert v-else-if="detailError" type="danger" :description="detailError" />
        <template v-else-if="detail">
          <text class="t-md t-bold">{{ detail.title }}</text>
          <text class="message-content">{{ detail.contentPlain || detail.content || detail.summary || '暂无正文' }}</text>
          <text v-if="detail.withdrawn">该消息已撤回，请以学校最新通知为准。</text>
          <text v-if="detail.expired">该消息已过期。</text>
          <text v-if="detail.requireAck">本条需本人确认，请到原事项办理；标记已读不能代替确认。</text>
          <button v-if="messageAction" class="mobile-control btn btn-primary" @click="openBusiness">打开相关事项</button>
          <text v-else-if="detail.requireAck && !detail.withdrawn && !detail.expired">此消息未提供可用的办理链接，请从实习首页进入对应事项核对。</text>
          <MobileInlineAlert v-if="readError" type="danger" :description="readError" />
          <button v-if="detail.readStatus!=='READ'" class="mobile-control btn btn-primary" :disabled="readBusy" @click="markRead">{{ readBusy ? '正在保存…' : '标记已读' }}</button>
          <text v-else>这条消息已读</text>
        </template>
      </view>
    </view>
  </view>
</template>
<script>
import { studentApi } from '@/services/studentApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
import { go } from '@/utils/nav'
export default {
  data:()=>({generation:currentSessionGeneration(),readFilter:'',state:'loading',error:'',items:[],page:1,total:0,hasMore:false,detail:null,detailLoading:false,detailError:'',readBusy:false,readError:'',sequence:0,detailSequence:0,hidden:false}),
  computed:{messageAction(){const row=this.detail;if(!row || row.withdrawn || row.expired)return null;const actions={
    'student.internship.volunteer-result':['/pages/student-internship/volunteer-result/index',['groupId','groupVersion']],
    'student.internship.weekly-report':['/pages/student/weekly-report/index',['reportId','batchId','internshipId','weekNo']],
    'student.internship.employment-registration':['/pages/student-internship/employment/index',['registrationId','batchId','internshipId']]};const action=actions[row.actionKey];if(!action || !row.actionParams || action[1].some(key=>!/^(0|[1-9]\d*)$/.test(String(row.actionParams[key] ?? '')) || (!['weekNo','groupVersion'].includes(key) && String(row.actionParams[key])==='0')))return null;return {path:action[0]+'?'+action[1].map(key=>key+'='+encodeURIComponent(String(row.actionParams[key]))).join('&')}}},
  onShow(){this.hidden=false;if(this.generation!==currentSessionGeneration()){this.generation=currentSessionGeneration();this.page=1;this.readFilter=''}this.load(this.page)},
  onHide(){this.pause()},onUnload(){this.pause()},
  methods:{
    openBusiness(){if(!this.hidden && this.messageAction)go(this.messageAction.path)},
    selectReadFilter(value){if(!['','UNREAD','READ'].includes(value)||this.readFilter===value)return;this.readFilter=value;this.load(1)},
    clearDetail(){this.detailSequence++;this.detail=null;this.detailLoading=false;this.detailError='';this.readBusy=false;this.readError=''},
    pause(){this.hidden=true;this.sequence++;this.items=[];this.total=0;this.hasMore=false;this.clearDetail()},
    current(sequence,generation){return !this.hidden && sequence===this.sequence && generation===currentSessionGeneration()},
    async load(page=1){
      const seq=++this.sequence,generation=currentSessionGeneration();this.clearDetail();this.items=[];this.total=0;this.hasMore=false;this.state='loading';this.error='';
      try{const result=await studentApi.getMessages(page,this.readFilter);if(!this.current(seq,generation))return;
        if(!Array.isArray(result?.items)||!Number.isInteger(result.total)||result.total<0||result.page!==page)throw Error('invalid response');
        this.items=result.items;this.total=result.total;this.hasMore=result.hasMore===true;this.page=page;this.state='ready';
      }catch(e){if(this.current(seq,generation)){const err=normalizeError(e);this.state=err.pageState||'error';this.error=err.text}}
    },
    async openMessage(id){
      this.clearDetail();const seq=this.sequence,generation=currentSessionGeneration(),detailSeq=this.detailSequence,messageId=String(id);this.detailLoading=true;
      const current=()=>this.current(seq,generation)&&detailSeq===this.detailSequence;
      try{const result=await studentApi.getMessage(messageId);if(!current())return;if(String(result?.messageId)!==messageId)throw Error('invalid response');this.detail=result;
      }catch(e){if(current())this.detailError=normalizeError(e).text}finally{if(current()){this.detailLoading=false;await this.$nextTick();if(current())uni.pageScrollTo({selector:'.message-detail',duration:200})}}
    },
    async markRead(){
      if(this.hidden||!this.detail||this.detail.readStatus==='READ'||this.readBusy)return;
      const seq=this.sequence,generation=currentSessionGeneration(),detailSeq=this.detailSequence,id=String(this.detail.messageId);
      const current=()=>this.current(seq,generation)&&detailSeq===this.detailSequence;this.readBusy=true;this.readError='';
      try{const result=await studentApi.readMessage(id);if(!current())return;if(String(result?.messageId)!==id||result.readStatus!=='READ')throw Error('invalid response');
        this.detail={...this.detail,...result};this.items=this.items.map(row=>String(row.messageId)===id?{...row,readStatus:'READ'}:row);
      }catch(e){if(current())this.readError=normalizeError(e).text}finally{if(current())this.readBusy=false}
    }
  }
}
</script>
<style scoped>
.message-summary{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.messages-refresh{margin:0;padding:0 6px;min-height:var(--touch-target-min);background:transparent;color:var(--brand-primary);font-size:var(--font-size-base)}.messages-refresh::after{border:0}.messages-hint{color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.6}
.message-item,.message-detail{display:flex;flex-direction:column;gap:10px;padding:16px;text-align:left;width:100%;box-sizing:border-box;font-size:14px;line-height:1.6;color:var(--text-primary)}.message-item::after{border:0}.message-content{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--text-secondary)}.message-pages{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:var(--font-size-base)}.message-pages button{margin:0;min-height:var(--touch-target-min);font-size:var(--font-size-base)}
.message-filters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.message-filters>button{width:100%;margin:0;padding:0 8px}
</style>
