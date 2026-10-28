<template>
  <el-select :model-value="modelValue" filterable remote clearable :remote-method="search" :loading="loading" :aria-label="label" :placeholder="label" @update:model-value="$emit('update:modelValue', $event || '')" @visible-change="visible => visible && openOptions()">
    <el-option v-if="selected && !items.some(item => item.id === selected.id)" :key="selected.id" :value="selected.id" :label="optionLabel(selected)" />
    <el-option v-for="item in items" :key="item.id" :value="item.id" :label="optionLabel(item)"><span>{{ item.name || item.loginName }}</span><small v-if="item.code || item.loginName"> · {{ item.code || item.loginName }}</small></el-option>
    <template #footer><el-button text :disabled="loading" @click.stop="load(true)">刷新选项</el-button><el-button v-if="items.length < total" text :loading="loading" @click.stop="load(false)">加载更多</el-button><p v-if="error" role="alert">{{ error }}</p></template>
  </el-select>
</template>
<script setup>
import { ElButton, ElOption, ElSelect } from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/select/style/css'

import { ref, watch } from 'vue'
import { get } from './systemApi'
const props = defineProps({ modelValue: { type: String, default: '' }, path: { type: String, required: true }, label: { type: String, required: true } })
defineEmits(['update:modelValue'])
const items = ref([]), total = ref(0), page = ref(1), keyword = ref(''), loading = ref(false), error = ref('')
const selected=ref(null)
const loaded=ref(false)
function optionLabel(item) { const name=item.name || item.loginName || item.code || '未登记名称',code=item.code || item.loginName;return code && code!==name ? `${name}（${code}）` : name }
let sequence = 0
async function load(reset) {
  const run = ++sequence; if (reset) { loaded.value=false;page.value = 1;items.value=[];total.value=0 }
  loading.value = true; error.value = ''
  try { const value = await get(props.path, { page: page.value, pageSize: 50, keyword: keyword.value }); if (run !== sequence) return; items.value = reset ? value.items : [...items.value, ...value.items]; total.value = value.total; page.value++;loaded.value=true }
  catch (e) { if (run === sequence) error.value = e.message || '选项读取失败' }
  finally { if (run === sequence) loading.value = false }
}
function openOptions(){if(!loaded.value && !loading.value)return load(true)}
function search(value) { if(value===keyword.value && (loading.value || loaded.value))return;keyword.value = value; return load(true) }
watch(() => props.path, () => { keyword.value = ''; return load(true) })
watch(()=>[props.modelValue,props.path],async ([identifier,path],_,onCleanup)=>{
  let active=true;onCleanup(()=>{active=false});selected.value=null
  if(!identifier)return
  try{const result=await get('/selection',{kind:path.split('/').pop(),identifier});if(active)selected.value=result}
  catch(e){if(active){selected.value={id:identifier,name:'原对象不可见，请重新核对'};error.value=e.message}}
},{immediate:true})
</script>
