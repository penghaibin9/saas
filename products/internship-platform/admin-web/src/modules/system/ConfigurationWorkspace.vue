<template>
  <section v-loading="loading">
    <el-alert v-if="error && !form" :title="error" type="error" :closable="false"/>
    <el-alert v-if="receipt && !form" :title="receipt" type="success" :closable="false"/>
    <el-form v-if="form" label-position="top" :disabled="!canEdit" @submit.prevent="submit">
      <template v-if="category === 'brand'"><div class="config-grid"><el-form-item label="学校全称" required><el-input v-model="form.schoolName" maxlength="100"/></el-form-item><el-form-item label="学校简称"><el-input v-model="form.shortName" maxlength="100"/></el-form-item><el-form-item label="平台显示名称" required><el-input v-model="form.platformName" maxlength="100"/></el-form-item><el-form-item label="平台副标题"><el-input v-model="form.subtitle" maxlength="200"/></el-form-item><el-form-item label="联系咨询电话"><el-input v-model="form.contactPhone" maxlength="50"/></el-form-item><el-form-item label="监督咨询电话"><el-input v-model="form.supervisionPhone" maxlength="50"/></el-form-item></div><h2>学校校徽</h2><SystemAttachments :model-value="logoFiles" purpose="SYSTEM_BRAND" :editable="canEdit" :limit="1" accept=".png,.jpg,.jpeg,.gif" @update:model-value="form.logoFileId=$event[0] || ''" @ready="filesReady=$event"/><div class="brand-preview"><span>学校品牌展示预览</span><div class="brand-preview-heading"><img v-if="logoUrl" :src="logoUrl" alt="学校校徽预览" @error="logoFailed"/><h2>{{ form.platformName }}</h2></div><p>{{ form.schoolName }} · {{ form.subtitle }}</p><p v-if="logoError" role="alert">{{ logoError }}</p></div><p>学校身份编码由安装时确定，不能在这里修改。</p></template>
      <template v-else-if="category === 'dictionary'"><h2>标准字典来源与版本</h2><table class="standard-dictionaries"><thead><tr><th>字典</th><th>当前来源</th><th>版本及状态</th></tr></thead><tbody><tr><td>地区</td><td>现有省市区数据包</td><td>数据包版本 {{ areaVersion }}；{{ referenceSummary('area') }}</td></tr><tr><td>行业</td><td>实习企业页面内置的 {{ industryCount }} 项行业选项</td><td>随应用版本发布；{{ referenceSummary('industry') }}</td></tr><tr><td>企业性质</td><td>企业资料当前登记内容</td><td>{{ referenceSummary('enterpriseNature') }}</td></tr><tr><td>专业代码</td><td>组织架构中的国家专业目录代码</td><td>由学校对照所用目录维护；{{ referenceSummary('major') }}</td></tr></tbody></table><h3>学校所用标准目录登记</h3><p>请对照实际采用的目录同时填写来源和版本。此登记保留变更记录，不会替换业务字典，也不代表已通过标准符合性核验。</p><div v-for="item in form.standardReferences" :key="item.kind" class="standard-reference"><strong>{{ standardNames[item.kind] }}</strong><el-input v-model="item.source" :ref="el=>standardInputs[item.kind+'Source']=el" :aria-label="standardNames[item.kind]+'字典来源'" placeholder="未确认来源时留空" maxlength="200"/><el-input v-model="item.edition" :ref="el=>standardInputs[item.kind+'Edition']=el" :aria-label="standardNames[item.kind]+'字典版本'" placeholder="与来源配套的版本或发布日期" maxlength="100"/><span>{{ item.source && item.edition ? '学校登记，待对照实际目录核验' : '尚未登记完整来源与版本' }}</span></div><h2>学校公告分类</h2><p>只维护学校展示分类，不改变业务状态、审批结果和法定类别。</p><div class="editable-row" v-for="(_,index) in form.announcementCategories" :key="index"><el-input v-model="form.announcementCategories[index]" maxlength="50" aria-label="公告分类名称"/><el-button v-if="canEdit" @click="form.announcementCategories.splice(index,1)">移除</el-button></div><el-button v-if="canEdit" @click="form.announcementCategories.push('')">增加分类</el-button><h2>组织导入匹配别名</h2><p>别名必须明确对应组织代码，出现多候选时仍须核对。</p><div class="editable-row" v-for="(item,index) in form.aliases" :key="index"><el-input v-model="item.alias" aria-label="组织别名" placeholder="学校常用名称" maxlength="100"/><el-input v-model="item.code" aria-label="对应组织代码" placeholder="对应组织代码" maxlength="50"/><el-button v-if="canEdit" @click="form.aliases.splice(index,1)">移除</el-button></div><el-button v-if="canEdit" @click="form.aliases.push({alias:'',code:''})">增加匹配别名</el-button><el-alert type="info" :closable="false" title="地区、行业、企业性质及专业标准代码沿用现有业务标准。学校不能在此变更标准含义。"/></template>
      <template v-else><el-form-item label="咨询电话"><el-input v-model="form.contactPhone" maxlength="50"/></el-form-item><el-form-item label="服务承办人"><SystemObjectSelect v-if="canEdit" v-model="form.responsibleUserId" path="/accounts" label="选择服务承办人"/><span v-else>{{ responsibleName || '学校尚未指定有效承办人' }}</span></el-form-item><el-alert v-if="canEdit && invalidResponsibleId && form.responsibleUserId===invalidResponsibleId" type="warning" :closable="false" title="原服务承办人的资料或账号已失效，请重新指定在职承办人；原配置及记录保留。"/><el-form-item label="普通提醒附言模板" required><el-input v-model="form.reminderText" maxlength="200"/></el-form-item><h2>常见问题</h2><div v-for="(item,index) in form.faq" :key="index" class="faq"><el-input v-model="item.question" placeholder="问题" aria-label="常见问题" maxlength="100"/><el-input v-model="item.answer" type="textarea" placeholder="办理说明" aria-label="问题解答" maxlength="1000"/><el-button v-if="canEdit" @click="form.faq.splice(index,1)">移除问题</el-button></div><el-button v-if="canEdit" @click="form.faq.push({question:'',answer:''})">增加问题</el-button><el-alert type="info" :closable="false" title="紧急告知和关键业务回执保持启用；外部消息渠道状态在外部服务与对接页面查看。"/></template>
      <el-form-item v-if="canEdit" label="变更原因" required><el-input v-model="form.reason" type="textarea" maxlength="500"/></el-form-item>
      <el-alert v-if="error" :title="error" type="error" :closable="false"/><el-alert v-if="receipt" :title="receipt" type="success" :closable="false"/>
      <ConflictReview :conflict="conflict" :input="form" @reviewed="form.expectedVersion=$event;conflict=null;error=''"/><el-button v-if="canEdit" type="primary" native-type="submit" :loading="saving" :disabled="!filesReady || !!conflict">保存学校配置</el-button>
    </el-form>
  </section>
</template>
<script setup>
import { ElAlert, ElButton, ElForm, ElFormItem, ElInput, ElLoading } from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/loading/style/css'
const vLoading = ElLoading.directive

import { ref,watch,computed,onBeforeUnmount } from 'vue'
import areaPackage from '@vant/area-data/package.json'
import { statusOptions } from '@/modules/internship/constants/context.constants'
const areaVersion=areaPackage.version,industryCount=statusOptions.enterpriseIndustry.length
const standardInputs={}
const standardNames={area:'地区',industry:'行业',enterpriseNature:'企业性质',major:'专业代码'}
import { get,save } from './systemApi'
import { matchPermission } from '@/config/navPlan'
import { getPermissionPatterns } from '@/security/permissionGate'
import SystemObjectSelect from './SystemObjectSelect.vue'
import SystemAttachments from './SystemAttachments.vue'
import ConflictReview from './ConflictReview.vue'
import { fileSdk } from '@/services/file/fileSdk'
function referenceSummary(kind){const item=form.value?.standardReferences?.find(row=>row.kind===kind);return item?.source && item.edition ? `已登记：${item.source}，${item.edition}（学校登记）` : '标准目录来源与版本尚未登记'}
const conflict=ref(null)
const props=defineProps({category:{type:String,required:true}})
const filesReady=ref(true)
const logoFiles=computed(()=>form.value?.logoFileId ? [form.value.logoFileId] : [])
const form=ref(null),error=ref(''),receipt=ref(''),loading=ref(false),saving=ref(false),responsibleName=ref(''),invalidResponsibleId=ref('')
const canEdit=computed(()=>matchPermission(getPermissionPatterns(),`system.${props.category}.manage`))
const logoUrl=ref(''),logoError=ref('');let logoSequence=0
function clearLogo(){if(logoUrl.value)URL.revokeObjectURL(logoUrl.value);logoUrl.value=''}
function logoFailed(){clearLogo();logoError.value='校徽暂时无法预览，请刷新附件状态后重试。'}
async function loadLogo(){const run=++logoSequence;clearLogo();logoError.value='';const id=form.value?.logoFileId;if(!id)return;try{const blob=await fileSdk.blob(id);if(run===logoSequence)logoUrl.value=URL.createObjectURL(blob)}catch{if(run===logoSequence)logoFailed()}}
watch(()=>form.value?.logoFileId,loadLogo)
let sequence=0
onBeforeUnmount(()=>{sequence++;logoSequence++;clearLogo()})
async function load(){const run=++sequence;const category=props.category;loading.value=true;error.value='';responsibleName.value='';invalidResponsibleId.value='';try{const {version,schoolCode,responsibleName:ownerName,responsibleValid,...values}=await get(`/config/${category}`);if(run!==sequence)return;responsibleName.value=ownerName || '';invalidResponsibleId.value=responsibleValid===false ? values.responsibleUserId || '' : '';if(category==='dictionary')values.standardReferences=Object.keys(standardNames).map(kind=>({kind,source:'',edition:'',...(values.standardReferences || []).find(row=>row.kind===kind)}));form.value={...values,expectedVersion:version,reason:''}}catch(e){if(run===sequence){error.value=e.message;form.value=null}}finally{if(run===sequence)loading.value=false}}
async function submit(){if(saving.value || conflict.value || !filesReady.value || !canEdit.value)return;if(props.category==='dictionary'){const incomplete=form.value.standardReferences.find(row=>Boolean(row.source.trim())!==Boolean(row.edition.trim()));if(incomplete){error.value=standardNames[incomplete.kind]+'字典来源和版本须同时填写，未确认时请同时留空';standardInputs[incomplete.kind+(incomplete.source.trim() ? 'Edition' : 'Source')]?.focus();return}}const run=sequence;const category=props.category;saving.value=true;error.value='';receipt.value='';try{await save(`/config/${category}`,form.value,'PUT');if(run!==sequence)return;receipt.value='学校配置已保存，下次读取时使用新配置。';await load()}catch(e){if(run===sequence){error.value=e.message||'保存失败，输入已保留';conflict.value=e.details?.current ? e.details : null}}finally{saving.value=false}}
watch(()=>props.category,()=>{form.value=null;receipt.value='';conflict.value=null;filesReady.value=true;load()},{immediate:true})
</script>
<style scoped>.standard-reference{display:grid;grid-template-columns:80px 1fr 1fr;gap:12px;margin:16px 0}.standard-reference span{grid-column:2 / -1;color:var(--t3)}@media(max-width:700px){.standard-reference{grid-template-columns:1fr}.standard-reference span{grid-column:auto}}.standard-dictionaries{width:100%;border-collapse:collapse}.standard-dictionaries th,.standard-dictionaries td{text-align:left;padding:12px;border:1px solid var(--line);line-height:1.6}.config-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 24px;max-width:1000px}.brand-preview{padding:26px;border:1px solid var(--line);border-radius:12px;background:var(--surface);margin:15px 0}.brand-preview-heading{display:flex;align-items:center;gap:16px}.brand-preview-heading img{width:48px;height:48px;object-fit:contain;flex-shrink:0}.brand-preview span{color:var(--t3);font-size:12px}.editable-row{display:flex;gap:12px;max-width:760px;margin:12px 0}.faq{display:grid;gap:12px;max-width:850px;padding:16px;border:1px solid var(--line);border-radius:8px;margin:14px 0}.el-alert,.el-form-item{margin:18px 0}.el-form{max-width:1050px}.el-select{width:100%}h2{font-size:18px}@media(max-width:700px){.config-grid{grid-template-columns:1fr}}</style>
