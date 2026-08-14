<script setup>
import { computed } from 'vue'
const props=defineProps({ material:{type:Object,default:()=>({})} })
const profile=computed(()=>props.material.profile||{})
const groups=computed(()=>[
  ['skillEvidence','技能证明'],
  ['projects','项目经历'],
  ['practices','实践经历'],
  ['certificates','证书'],
  ['awards','获奖经历'],
  ['portfolio','作品'],
])
const expectedLocations=computed(()=>Array.isArray(profile.value.expectedLocations)?profile.value.expectedLocations:[])
</script>
<template><div class="material"><section><h3>岗位申请说明</h3><p>{{ material.application_statement || material.applicationStatement || '未填写' }}</p></section><section v-if="profile.headline||profile.selfIntro||profile.strengths||expectedLocations.length"><h3>实习档案摘要</h3><p v-if="profile.headline"><b>{{ profile.headline }}</b></p><p v-if="profile.selfIntro">{{ profile.selfIntro }}</p><p v-if="profile.strengths"><span class="label">优势：</span>{{ profile.strengths }}</p><p v-if="expectedLocations.length"><span class="label">期望地点：</span>{{ expectedLocations.join('、') }}</p></section><section><h3>技能标签</h3><div class="tags"><span v-for="tag in (material.skill_tags || material.skillTags || [])" :key="tag" class="ep-tag">{{ tag }}</span><span v-if="!(material.skill_tags||material.skillTags||[]).length" class="ep-muted">暂无</span></div></section><section v-for="group in groups" :key="group[0]"><h3>{{ group[1] }}</h3><div v-if="!(material[group[0]]||[]).length" class="ep-muted">暂无</div><article v-for="item in (material[group[0]]||[])" :key="item.id||item.title" class="item"><div><b>{{ item.title }}</b><span v-if="item.verification_status==='VERIFIED' || item.verificationStatus==='VERIFIED'" class="ep-tag ok">学校已核验</span><span v-else class="ep-tag">学生自填</span></div><p>{{ item.description || item.organization || '' }}</p></article></section><section v-if="material.snapshotHash"><h3>投递快照</h3><p class="ep-muted">当前展示来自本次提交冻结的 ApplicationMaterialSnapshot；学生后续修改实习档案不会反向改写这份投递证据。</p></section><section v-if="material.generated_profile_pdf_file_id || material.generatedProfilePdfFileId"><h3>实习申请简历</h3><p class="ep-muted">PDF 仅为本次 Snapshot 的派生文件，不是第二套简历真值。</p><button class="ep-btn" type="button" disabled>查看 PDF（等待 File Center facade）</button></section></div></template>
<style scoped>.material section{padding:18px 0;border-bottom:1px solid var(--line)}.material section:first-child{padding-top:0}.material h3{font-size:14px;margin:0 0 10px}.material p{line-height:1.7;margin:6px 0;color:var(--t2)}.material p b{color:var(--t1)}.label{color:var(--t3)}.tags{display:flex;gap:8px;flex-wrap:wrap}.item{padding:10px 0}.item>div{display:flex;align-items:center;gap:8px}.item p{font-size:13px;color:var(--t3)}</style>
