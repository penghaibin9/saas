<template>
  <section v-if="conflict" class="conflict-review" role="alert">
    <h3>记录已有新版本，您的输入已保留</h3>
    <p>请比较当前记录与本次输入，再决定是否继续。核对按钮只更新编辑版本，不会自动保存。</p>
    <table><thead><tr><th>核对项目</th><th>当前记录</th><th>本次输入</th></tr></thead><tbody>
      <tr v-for="row in rows" :key="row.key"><th>{{ row.label }}</th><td>{{ row.current }}</td><td>{{ row.input }}</td></tr>
    </tbody></table>
    <p v-if="!rows.length">可见字段一致，但记录的版本或关联关系已经变化；请同时核对该对象的责任关系和成员。</p>
    <button type="button" @click="$emit('reviewed', conflict.version)">已核对差异，继续编辑</button>
  </section>
</template>
<script setup>
import { computed } from 'vue'
const props=defineProps({conflict:Object,input:{type:Object,required:true},permissionNames:{type:Object,default:()=>({})}})
defineEmits(['reviewed'])
const labels={approvalSteps:'审批顺序与责任身份',name:'名称',code:'编号',status:'状态',parentId:'上级组织编号',collegeId:'院系编号',classId:'班级编号',departmentId:'部门编号',
  grade:'年级',educationYears:'学制',trainingLevel:'培养层次',nationalCode:'国家专业代码',expiresAt:'有效期',permissions:'功能权限',
  userId:'负责人编号',scopeType:'负责类型',refId:'负责对象编号',schoolName:'学校全称',shortName:'学校简称',platformName:'平台名称',
  subtitle:'副标题',contactPhone:'咨询电话',supervisionPhone:'监督电话',logoFileId:'校徽文件编号',announcementCategories:'公告分类',
  aliases:'组织匹配别名',responsibleUserId:'承办人编号',reminderText:'提醒附言',faq:'常见问题',title:'资料名称',source:'来源',notes:'核对说明',
  ownerUserId:'资料责任人编号',fileIds:'附件编号',expectedPeople:'来源人员数',actualPeople:'迁入人员数',expectedRecords:'来源业务数',
  actualRecords:'迁入业务数',expectedFiles:'来源附件数',actualFiles:'迁入附件数',continuationChecked:'接续办理检查',
  mappingRules:'迁移映射规则',identityMapping:'组织与人员对应关系',exceptionResolution:'异常及处理结果'}
const states={ACTIVE:'启用',DISABLED:'停用',LOCKED:'锁定',PENDING:'待处理',REVIEW:'待核对',VERIFIED:'学校登记已核验',
  COLLEGE:'院系',MAJOR:'专业',CLASS:'班级',SECONDARY:'中职',HIGHER:'高职专科',FIVE_YEAR:'五年一贯制'}
function text(key,value){
  if(key==='expiresAt')return value ? new Date(value).toLocaleString('zh-CN') : '长期有效'
  if(value===null || value===undefined || value==='')return '未填写'
  if(key==='permissions')return value.map(code=>props.permissionNames[code] || '历史授权').join('、') || '无权限'
  if(key==='aliases')return value.map(item=>`${item.alias} → ${item.code}`).join('；') || '无'
  if(key==='faq')return value.map(item=>`${item.question}：${item.answer}`).join('；') || '无'
  if(Array.isArray(value))return value.join('、') || '无'
  if(typeof value==='boolean')return value?'已确认':'未确认'
  return states[value] || String(value)
}
const rows=computed(()=>Object.entries(props.conflict?.current || {}).filter(([key,value])=>key in labels && key in props.input &&
  (key==='expiresAt' ? (value ? new Date(value).getTime() : null)!==(props.input[key] ? new Date(props.input[key]).getTime() : null) :
  JSON.stringify(value)!==JSON.stringify(props.input[key]))).map(([key,value])=>({key,label:labels[key],current:text(key,value),input:text(key,props.input[key])})))
</script>
<style scoped>
.conflict-review{padding:16px;border:1px solid #c77b12;background:#fff9ed;color:#553705;margin:16px 0;border-radius:8px}
h3{font-size:16px;margin:0}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{padding:8px;text-align:left;border-bottom:1px solid #e7d4b5;overflow-wrap:anywhere;font-size:13px}button{margin-top:14px;padding:9px 16px;border:1px solid #9e6616;border-radius:6px;background:white;color:inherit;cursor:pointer}
</style>
