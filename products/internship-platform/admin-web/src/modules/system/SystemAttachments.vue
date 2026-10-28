<template>
  <section>
    <FileUploader v-if="editable && modelValue.length<limit" :biz-type="purpose" :upload-path="'/files?bizType='+purpose" :accept="accept" button-text="上传资料附件" @progress="uploadStarted" @uploaded="uploaded" @error="uploadFailed" @cancelled="uploadCancelled" />
    <p v-if="error" role="alert">{{ error }}</p>
    <SecureFileList v-if="modelValue.length" :items="files" :loading="loading" @refresh="load" @preview="open($event,true)" @download="open($event,false)"/>
    <p v-if="files.some(f=>!f.readyForBusiness)">附件尚未通过安全检查，请等待后刷新文件状态；通过后才能保存为正式资料。</p>
    <button v-if="editable && modelValue.length" type="button" @click="$emit('update:modelValue',[])">清除本次附件选择</button>
  </section>
</template>
<script setup>
import { ref,watch,onBeforeUnmount } from 'vue'
import FileUploader from '@/components/file/FileUploader.vue'
import SecureFileList from '@/components/file/SecureFileList.vue'
import { fileSdk } from '@/services/file/fileSdk'
const props=defineProps({modelValue:{type:Array,default:()=>[]},purpose:{type:String,required:true},editable:Boolean,limit:{type:Number,default:20},accept:{type:String,default:'.pdf,.doc,.docx,.xlsx,.png,.jpg,.jpeg'}})
const emit=defineEmits(['update:modelValue','ready'])
const files=ref([]),loading=ref(false),uploading=ref(false),error=ref('');let sequence=0
function failure(e){error.value=e?.message || '附件操作失败，请重试'}
function readiness(){emit('ready',!uploading.value && !loading.value && files.value.length===props.modelValue.length && files.value.every(f=>f.readyForBusiness))}
function uploadStarted(){uploading.value=true;emit('ready',false)}
function uploadCancelled(){uploading.value=false;readiness()}
function uploadFailed(e){failure(e);uploadCancelled()}
async function load(){const run=++sequence;loading.value=true;error.value='';emit('ready',false);try{const result=await Promise.all(props.modelValue.map(id=>fileSdk.metadata(id)));if(run===sequence)files.value=result}catch(e){if(run===sequence){files.value=[];failure(e)}}finally{if(run===sequence){loading.value=false;readiness()}}}
function uploaded(file){uploading.value=false;emit('update:modelValue',[...props.modelValue,String(file.fileId || file.id)].slice(0,props.limit))}
async function open(file,preview){try{await fileSdk[preview?'preview':'download'](file.fileId,file.fileName)}catch(e){failure(e)}}
watch(()=>props.modelValue,load,{immediate:true,deep:true});onBeforeUnmount(()=>{++sequence})
</script>
