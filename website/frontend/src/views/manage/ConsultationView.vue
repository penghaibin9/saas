<template>
  <main class="consultations">
    <header><div><p>官网超级管理员专用</p><h1>咨询受理</h1></div><button @click="refresh" :disabled="busy||loading">重新读取列表</button></header>
    <p class="policy">资料自登记起保存 90 天，到期停止查看并由任务清理。列表中的电话默认隐藏中间四位，打开详情会记录查看操作。跟进备注与预约资料一同到期。</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取咨询记录…</p>
    <section v-if="selected" class="detail">
      <div class="detail-heading"><h2>{{ selected.schoolName }}</h2><button @click="selected=null;notice=''" :disabled="busy">返回列表</button></div>
      <dl><dt>联系人</dt><dd>{{ selected.contactName||'未填写' }}</dd><dt>联系电话</dt><dd><a :href="'tel:'+selected.phone">{{ selected.phone }}</a></dd><dt>意向产品</dt><dd>{{ selected.interest }}</dd><dt>咨询需求</dt><dd class="preserve">{{ selected.message||'未填写' }}</dd><dt>登记时间</dt><dd>{{ date(selected.createdAt) }}</dd><dt>到期时间</dt><dd>{{ date(selected.expiresAt) }}</dd><dt>来源页面</dt><dd><a :href="selected.sourcePath">查看来源页面 ↗</a></dd></dl>
      <form @submit.prevent="save"><label>跟进备注<textarea v-model="draftNote" maxlength="1000" rows="5" :disabled="busy" placeholder="记录已沟通的需求和下一步安排，勿填写密码或学生个人资料"></textarea></label><div class="detail-actions"><button :disabled="busy||conflict" class="primary">{{ busy?'正在保存…':'保存跟进备注' }}</button><button type="button" @click="open(selected.id,true)" :disabled="busy">重新读取并保留输入</button></div><p v-if="conflict">请重新读取最新记录，核对保留的输入后再保存。</p></form>
    </section>
    <template v-else-if="!loading&&!error">
      <div class="records"><article v-for="item in items" :key="item.id"><div><h2>{{ item.schoolName }}</h2><p>{{ item.interest }}</p><p>{{ item.contactName||'联系人未填写' }} · {{ item.phone }}</p><small>登记 {{ date(item.createdAt) }} · 到期 {{ date(item.expiresAt) }}</small></div><button @click="open(item.id)" :disabled="busy">查看详情与跟进</button></article><p v-if="!items.length">暂无有效期内的咨询记录。登记入口尚未启用时，访客仍可直接电话联系。</p></div>
      <div class="pagination"><button :disabled="page<=1" @click="changePage(-1)">上一页</button><span>第 {{ page }} 页 · 共 {{ total }} 条</span><button :disabled="page*20>=total" @click="changePage(1)">下一页</button></div>
    </template>
  </main>
</template>
<script setup>
import {ref,onMounted,onBeforeUnmount} from 'vue'
import {request} from '@/services/http/client.js'
const items=ref([]),total=ref(0),page=ref(1),selected=ref(null),draftNote=ref(''),conflict=ref(false),error=ref(''),notice=ref(''),loading=ref(false),busy=ref(false)
let alive=true,generation=0
const date=value=>new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Shanghai'}).format(new Date(value))
async function refresh(){const n=++generation;loading.value=true;error.value='';try{const data=await request('/manage/consultations',{params:{page:page.value}});if(alive&&n===generation){items.value=data.items;total.value=data.total}}catch(e){if(alive&&n===generation)error.value=e.message}finally{if(alive&&n===generation)loading.value=false}}
async function open(id,keep=false){busy.value=true;error.value='';notice.value='';try{const data=await request('/manage/consultations/'+id);if(!alive)return;selected.value=data;if(!keep)draftNote.value=data.note;conflict.value=false;if(keep)notice.value='已重新读取当前记录，输入已保留，请核对后保存。'}catch(e){if(alive)error.value=e.message}finally{if(alive)busy.value=false}}
async function save(){if(busy.value||conflict.value)return;busy.value=true;error.value='';notice.value='';try{const data=await request('/manage/consultations/'+selected.value.id+'/note',{method:'PUT',body:{expectedVersion:selected.value.version,note:draftNote.value}});if(alive){selected.value.version=data.version;notice.value='跟进备注已保存。'}}catch(e){if(alive){error.value=e.message;if(e.message.includes('已被更新'))conflict.value=true}}finally{if(alive)busy.value=false}}
function changePage(delta){page.value+=delta;refresh()}
onMounted(refresh);onBeforeUnmount(()=>{alive=false;generation++})
</script>
<style scoped>
.consultations{max-width:1120px;margin:auto;padding:32px 28px;font:15px/1.8 "Microsoft YaHei",sans-serif;color:#20354e}.consultations header,.detail-heading,.records article,.pagination,.detail-actions{display:flex;align-items:center;justify-content:space-between;gap:20px}.consultations h1{font-size:30px;margin:2px 0}.consultations h2{font-size:21px;margin:4px 0}.consultations header p{margin:0;color:#62768e}.policy,.notice{background:#eaf2fc;padding:16px 20px;color:#325b83}.error{background:#fff0ef;color:#a63134;padding:16px;border-left:3px solid #b94449;overflow-wrap:anywhere}.records,.detail{background:white;border:1px solid #dce5ee}.records article{padding:22px 24px;border-bottom:1px solid #dce5ee}.records p{margin:6px 0}.records>p{padding:24px}.records small{color:#62768e}.detail{padding:24px}.detail dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:12px;margin:24px 0}.detail dd{margin:0;overflow-wrap:anywhere}.detail dt{color:#62768e}.preserve{white-space:pre-wrap}.consultations a{color:#2268df}.consultations button{font:inherit;border:1px solid #b9cadd;background:white;border-radius:6px;padding:10px 16px;min-height:44px;cursor:pointer;color:#23415f}.consultations button:disabled{opacity:.55;cursor:not-allowed}.consultations .primary{background:#2268df;color:white;border-color:#2268df}.consultations textarea{display:block;width:100%;box-sizing:border-box;margin:8px 0 16px;font:inherit;color:inherit;border:1px solid #b9cadd;border-radius:6px;padding:12px}.detail-actions{justify-content:flex-start;flex-wrap:wrap}.pagination{justify-content:flex-end;margin:20px 0}.consultations :focus-visible{outline:3px solid #85b1f5;outline-offset:3px}@media(max-width:640px){.consultations{padding:24px 16px}.consultations header,.detail-heading,.records article{align-items:start;flex-direction:column;gap:10px}.detail{padding:20px 16px}.detail dl{grid-template-columns:85px minmax(0,1fr);gap:10px}.records article{padding:20px 16px}.pagination{justify-content:space-between;flex-wrap:wrap}.consultations h1{font-size:26px}}
</style>
