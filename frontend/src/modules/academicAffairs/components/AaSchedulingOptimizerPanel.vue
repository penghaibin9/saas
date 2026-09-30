<template>
  <section class="optimizer-panel" aria-labelledby="optimizer-title">
    <header><h3 id="optimizer-title">{{ text.title }}</h3><p>{{ text.boundary }}</p></header>
    <button type="button" :disabled="!batchId || loading || state.busy" @click="load">{{ loading ? text.loading : text.read }}</button>
    <p v-if="state.error" role="alert">{{ errorText }}</p>
    <p v-if="state.storageBlocked" role="alert">{{ text.storage }}</p>
    <ul v-if="state.context?.blockers?.length"><li v-for="(block, i) in state.context.blockers" :key="i">{{ optimizerLabel(block.code) }}</li></ul>
    <div v-if="state.context?.summary" class="optimizer-metrics"><span>待排课程 {{ state.context.sourceRevision ? tasks.length : state.context.summary.taskCount }}</span><span>教师 {{ state.context.summary.teacherCount }}</span><span>教学班 {{ state.context.summary.classCount }}</span><span>可用教室 {{ state.context.summary.roomCount }}</span><span>已有课位 {{ state.context.summary.existingCount }}</span><span>缺少连排规则 {{ state.context.sourceRevision ? tasks.filter(t => !patterns[t.id]).length : '待检查' }}</span><span>缺少人数 {{ state.context.summary.missingHeadcount }}</span><span>缺少正式名单 {{ state.context.summary.missingRoster }}</span></div>
    <template v-if="state.context?.sourceRevision">
      <p class="optimizer-warning">{{ text.confirmation }}</p>
      <label class="optimizer-confirm"><input v-model="replaceAuto" type="checkbox" :disabled="state.busy" />重排本批次已有自动课位（保留人工、导入和锁定课位）</label><div class="optimizer-settings">
        <label>{{ text.anchor }}<input v-model="anchor" type="date" :disabled="state.busy" /></label>
        <label v-if="state.context.rooms.some(room => !room.campus)">{{ text.campus }}<input v-model.trim="defaultCampus" :disabled="state.busy" /></label>
        <label>{{ text.profile }}<select v-model="profile" :disabled="state.busy"><option value="BALANCED">{{ text.balanced }}</option><option value="STUDENT_FRIENDLY">{{ text.student }}</option><option value="TEACHER_COMPACT">{{ text.teacher }}</option></select></label>
      </div>
      <details class="optimizer-clock-settings"><summary>核对连排时段（来自学校作息，跨午休不可连排）</summary><div v-for="campus in campuses" :key="campus" class="optimizer-slots">
        <strong>{{ campus }} · {{ text.blocks }}</strong>
        <label v-for="slot in campusSlots(campus)" :key="slot.id">{{ slot.slot_no }} / {{ slot.start_time }}–{{ slot.end_time }}
          <input :value="blocks[campus]?.[String(slot.slot_no)] || ''" @input="setBlock(campus,slot.slot_no,$event.target.value)" :disabled="state.busy" :aria-label="campus + ':' + slot.slot_no" />
        </label>
      </div></details>
      <table class="optimizer-table"><thead><tr><th>{{ text.course }}</th><th>{{ text.remaining }}</th><th>上课周</th><th>{{ text.pattern }}</th><th>{{ text.gap }}</th></tr></thead>
        <tbody><tr v-for="task in visibleTasks" :key="task.id"><td>{{ task.course_name || task.id }}<small>{{ task.teaching_class_name }} · {{ task.teacher_name }}</small></td><td>{{ task.remainingPeriods }}</td>
          <td><select v-model="parities[task.id]" :disabled="state.busy"><option value="ALL">每周</option><option value="ODD">单周</option><option value="EVEN">双周</option></select></td><td><input v-model="patterns[task.id]" :disabled="state.busy" :aria-label="text.pattern + task.course_name" placeholder="2+2" /></td>
          <td><input v-model.number="gaps[task.id]" type="number" min="0" max="6" :disabled="state.busy" :aria-label="text.gap + task.course_name" /></td></tr></tbody></table>
      <div class="optimizer-actions"><button :disabled="page <= 0" @click="page--">{{ text.previous }}</button><span>{{ page + 1 }} / {{ Math.max(1, Math.ceil(tasks.length / 20)) }}</span><button :disabled="(page+1)*20 >= tasks.length" @click="page++">{{ text.next }}</button></div>
      <label>{{ text.reason }}<input v-model.trim="reason" minlength="5" maxlength="500" :disabled="state.busy" /></label>
      <label class="optimizer-confirm"><input v-model="confirmed" type="checkbox" :disabled="state.busy" />{{ text.confirm }}</label>
      <div class="optimizer-actions">
        <button class="optimizer-primary" :disabled="!canGenerate" @click="generate">{{ state.busy ? text.processing : text.generate }}</button>
        <button :disabled="state.busy" @click="recover">{{ text.recover }}</button>
        <button v-if="state.job && !isTerminal" :disabled="state.busy" @click="cancel">{{ text.cancel }}</button>
      </div>
      <p v-if="!state.context.canGenerate" class="optimizer-warning">{{ text.disabled }}</p>
    </template>
    <template v-if="state.job">
      <h4>{{ text.job }} {{ state.job.jobId }} · {{ optimizerLabel(state.job.state) }}</h4>
      <p>计算耗时 {{ state.job.result?.elapsedSeconds ?? '—' }} 秒 · 已排课程 {{ state.job.result?.quality?.assignedCourses ?? 0 }} · 未排课程 {{ state.job.result?.quality ? state.job.result.quality.requiredCourses-state.job.result.quality.assignedCourses : tasks.length }} · 硬冲突 {{ ['SUCCEEDED','APPLIED'].includes(state.job.state) ? 0 : '待检查' }} · 使用教室 {{ state.job.result?.quality?.usedRoomCount ?? '—' }} 间</p>
      <p v-if="state.unknown" role="status">{{ text.unknown }}</p>
      <ul><li v-for="(diagnostic,i) in state.job.result?.diagnostics || []" :key="i">{{ diagnosticTask(diagnostic) }}：{{ diagnosticLabels(diagnostic) }}</li></ul>
      <dl v-if="state.job.result?.quality" class="optimizer-metrics"><template v-for="(label,key) in metricLabels" :key="key"><dt>{{ label }}</dt><dd>{{ state.job.result.quality[key] ?? '—' }}</dd></template></dl>
      <template v-if="state.job.state === 'SUCCEEDED'">
        <div class="optimizer-actions"><label>{{ text.course }}<select v-model="previewTask" @change="preview"><option value="">全部课程</option><option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.course_name || task.id }} / {{ task.teaching_class_name }}</option></select></label>
          <label>{{ text.week }}<select v-model="previewWeek" @change="preview"><option v-for="n in state.context?.term?.teaching_weeks || 0" :key="n" :value="'W'+String(n).padStart(2,'0')">{{ n }}</option></select></label></div>
        <div class="optimizer-actions"><label>查看方式<select aria-label="查看方式" v-model="viewBy" @change="viewObject=''"><option value="className">按班级看</option><option value="teacherName">按教师看</option><option value="classroom">按教室看</option></select></label><label>查看对象<select aria-label="查看对象" v-model="viewObject"><option value="">全部</option><option v-for="value in viewObjects" :key="value.id" :value="value.id">{{ value.label }}</option></select></label></div>
        <AaScheduleGrid :items="visibleRows" :slots="previewSlots" :editable="false" />
        <p>{{ text.previewWarning }}</p><button class="optimizer-primary" :disabled="state.busy || !state.job.canApply" @click="apply">采用此方案</button>
      </template>
    </template>
    <div v-if="state.application || state.job?.state === 'APPLIED'" role="status"><p>方案已写入原课表草稿。可继续人工调整、冲突检查、预发布和正式发布。</p><div class="optimizer-actions"><router-link :to="{path:'/admin/academic-affairs/schedule/'+batchId+'/edit',query:{classId:state.context?.tasks?.[0]?.class_id,taskId:state.context?.tasks?.[0]?.id,termId:state.context?.scope?.termId}}">人工调整课表</router-link><router-link :to="{path:'/admin/academic-affairs/scheduling',query:{tab:'conflict',batchId,termId:state.context?.scope?.termId}}">检查课表冲突</router-link><router-link :to="{path:'/admin/academic-affairs/schedule/publish',query:{batchId}}">预发布与正式发布</router-link></div></div><footer>{{ text.publishBoundary }}</footer>
  </section>
</template>
<script>
import AaScheduleGrid from './AaScheduleGrid.vue'
import { schedulingOptimizerApi } from '../api/scheduling-optimizer.api.js'
import { createCandidateController } from '../optimizer/candidateController.mjs'
import { optimizerLabel, diagnosticLabels } from '../optimizer/presentation.mjs'
import { safeBusinessMessage } from '@/utils/presentationSafety'
import { matchPermission } from '@/config/navPlan'

const text = {
  title:'\u667a\u80fd\u5019\u9009\u65b9\u6848', boundary:'\u4ec5\u751f\u6210\u5019\u9009\uff0c\u4e0d\u6539\u5199\u6b63\u5f0f\u8bfe\u8868\u3002',
  loading:'\u8bfb\u53d6\u4e2d\u2026',read:'\u8bfb\u53d6\u5f53\u524d\u6279\u6b21\u51c6\u5907\u60c5\u51b5',source:'\u8f93\u5165\u7248\u672c',taskCount:'\u5f85\u6392\u4efb\u52a1',
  confirmation:'\u4e0b\u65b9\u8fde\u6392\u548c\u65f6\u6bb5\u662f\u5f85\u786e\u8ba4\u5efa\u8bae\uff0c\u4e0d\u4ee3\u8868\u5b66\u6821\u5df2\u6709\u89c4\u5219\u3002',
  anchor:'\u7b2c\u4e00\u6559\u5b66\u5468\u5468\u4e00',campus:'\u5386\u53f2\u7a7a\u6821\u533a\u786e\u8ba4\u540d\u79f0',profile:'\u4f18\u5316\u504f\u597d',
  balanced:'\u5747\u8861',student:'\u5b66\u751f\u5c11\u7a7a\u5802',teacher:'\u6559\u5e08\u5c11\u7a7a\u5802',room:'\u6559\u5ba4\u5229\u7528',
  blocks:'\u53ef\u8fde\u6392\u65f6\u6bb5\u7ec4\uff08\u5348\u4f11\u4e24\u4fa7\u8bf7\u4f7f\u7528\u4e0d\u540c\u7ec4\u540d\uff09',course:'\u8bfe\u7a0b',remaining:'\u5269\u4f59\u5468\u5b66\u65f6',
  pattern:'\u8fde\u6392\u6a21\u5f0f',gap:'\u6700\u5c0f\u95f4\u9694\u5929\u6570',previous:'\u4e0a\u4e00\u9875',next:'\u4e0b\u4e00\u9875',reason:'\u8bd5\u6392\u539f\u56e0',
  confirm:'\u5df2\u6838\u5bf9\u6559\u5b66\u5468\u3001\u6821\u533a\u3001\u8fde\u6392\u53ca\u65f6\u6bb5\u7ec4\u8bbe\u7f6e',processing:'\u63d0\u4ea4\u4e2d\u2026',generate:'\u751f\u6210\u53ea\u8bfb\u5019\u9009',
  recover:'\u6838\u5bf9\u4e0a\u6b21\u8bf7\u6c42',cancel:'\u53d6\u6d88\u8ba1\u7b97',job:'\u5019\u9009\u4efb\u52a1',attempts:'\u6267\u884c\u6b21\u6570',version:'\u7248\u672c',week:'\u6559\u5b66\u5468',
  disabled:'\u65b0\u5f15\u64ce\u9ed8\u8ba4\u5173\u95ed\uff1b\u771f\u5b9eMySQL\u4e0e\u5de5\u4f5c\u8fdb\u7a0b\u9a8c\u6536\u901a\u8fc7\u540e\u624d\u80fd\u5f00\u542f\u3002',
  unknown:'\u63d0\u4ea4\u7ed3\u679c\u5f85\u786e\u8ba4\uff0c\u8bf7\u5148\u6838\u5bf9\u65e7\u8bf7\u6c42\uff0c\u4e0d\u8981\u91cd\u590d\u65b0\u5efa\u4efb\u52a1\u3002',
  storage:'\u65e0\u6cd5\u4fdd\u5b58\u5b89\u5168\u56de\u6267\uff0c\u5df2\u963b\u6b62\u63d0\u4ea4\u3002',notMinimum:'\uff08\u5df2\u786e\u8ba4\u51b2\u7a81\u96c6\uff0c\u672a\u8bc1\u660e\u6700\u5c0f\uff09',
  previewWarning:'\u8fd9\u662f\u5355\u4efb\u52a1\u5019\u9009\u89c6\u56fe\uff0c\u4e0d\u662f\u6574\u4e2a\u5b66\u6821\u5df2\u53d1\u5e03\u8bfe\u8868\u3002\u8c03\u4f11\u4ee5\u5b9e\u9645\u65e5\u671f\u4e3a\u51c6\u3002',
  publishBoundary:'\u6b63\u5f0f\u5e94\u7528\u548c\u53d1\u5e03\u6682\u4e0d\u5f00\u653e\uff1b\u4ecd\u7531\u539f\u8bfe\u8868\u6743\u5a01\u4e0e\u8c03\u505c\u8bfe\u6d41\u7a0b\u7ba1\u7406\u3002'
}
Object.assign(text, { title:'自动排课', boundary:'检查学校数据，生成候选课表，确认后采用至原课表草稿。', read:'第一步：检查排课条件', confirmation:'请核对本次连排规则及可连续上课的时段组，已知校历和作息来自学校配置。', profile:'排课策略', balanced:'均衡排课（默认）', teacher:'教师更集中', generate:'第二步：智能试排', disabled:'当前条件尚未满足，请先处理阻断项。', previewWarning:'候选课表按实际校历日期展示，采用后仍需通过原课表发布流程。', publishBoundary:'师生只查看正式发布的课表。' })
export default {
  name:'AaSchedulingOptimizerPanel',components:{AaScheduleGrid},emits:['applied'],
  props:{batchId:{type:String,default:''},identityKey:{type:String,required:true},ctx:{type:Object,required:true}},
  data(){return {text,state:{},loading:false,anchor:'',defaultCampus:'',profile:'BALANCED',patterns:{},gaps:{},blocks:{},reason:'',confirmed:false,page:0,previewTask:'',previewWeek:'W01',pollCount:0,viewBy:'className',viewObject:'',replaceAuto:false,parities:{}}},
  computed:{
    visibleRows(){return this.state.rows?.filter(row=>!this.viewObject || this.rowObjects(row).some(v=>v.id===this.viewObject)) || []},
    viewObjects(){return [...new Map((this.state.rows || []).flatMap(r=>this.rowObjects(r)).map(v=>[v.id,v])).values()]},
    tasks(){return (this.state.context?.tasks || []).map(t=>({...t,remainingPeriods:t.remainingPeriods+(this.replaceAuto?t.autoPeriods:0)})).filter(t=>t.remainingPeriods>0)},visibleTasks(){return this.tasks.slice(this.page*20,this.page*20+20)},
    campuses(){return [...new Set((this.state.context?.rooms || []).map(r=>r.campus || this.defaultCampus).filter(Boolean))]},
    canGenerate(){return this.tasks.length>0 && this.confirmed && this.reason.length>=5 && this.anchor && !this.state.busy && !this.state.storageBlocked && !!this.state.context?.canGenerate && matchPermission(this.ctx.permissionPatterns || [],'academicAffairs.schedule.rule.manage')},
    isTerminal(){return this.controller?.isTerminal() || false},errorText(){return safeBusinessMessage(this.state.error,optimizerLabel(this.state.error))},
    metricLabels(){return {assignedActivities:'\u5df2\u6392\u6d3b\u52a8',scheduledPeriods:'\u5df2\u6392\u5b66\u65f6',teacherGapMinutes:'\u6559\u5e08\u7a7a\u5802\u5206\u949f',learnerGroupGapMinutes:'\u5b66\u751f\u7ec4\u7a7a\u5802\u5206\u949f',maxActorDayGapMinutes:'\u6700\u5927\u5355\u65e5\u7a7a\u5802\u5206\u949f'}},
    previewSlots(){const campus=this.state.rows[0]?.campus || this.campuses[0];return this.campusSlots(campus).map(s=>({slotNo:s.slot_no,startTime:s.start_time,endTime:s.end_time}))}
  },
  watch:{replaceAuto(){this.confirmed=false;this.patterns={}},batchId(){this.reset()},identityKey(){this.reset()},defaultCampus(){this.syncBlocks();this.confirmed=false}},
  created(){this.controller=createCandidateController({api:schedulingOptimizerApi,readIdentity:()=>this.identityKey,
    storage:{getItem:k=>window.sessionStorage.getItem(k),setItem:(k,v)=>window.sessionStorage.setItem(k,v)},state:this.state})},
  mounted(){this.reset()},beforeUnmount(){clearTimeout(this.timer);this.controller.dispose()},
  methods:{
    rowObjects(row){if(this.viewBy==='teacherName')return (row.teacherKeys || []).map(id=>({id,label:row.teacherLabels?.[id] || row.teacherName || id}));return [{id:this.viewBy==='className'?row.teachingClassId:row.classroomId,label:row[this.viewBy]}]},
    reset(){clearTimeout(this.timer);this.controller.setScope(this.batchId);this.loading=false;this.confirmed=false;this.patterns={};this.gaps={};this.blocks={};this.reason='';this.page=0;this.previewTask='';this.pollCount=0},
    async load(){const identity=this.identityKey,batch=this.batchId;this.loading=true;const context=await this.controller.load();if(identity!==this.identityKey || batch!==this.batchId)return;this.loading=false;if(!context?.sourceRevision)return;
      this.confirmed=false;this.parities=Object.fromEntries(this.tasks.map(t=>[t.id,'ALL']));this.patterns=Object.fromEntries(this.tasks.map(t=>[t.id,'']));this.gaps=Object.fromEntries(this.tasks.map(t=>[t.id,0]));
      const start=context.term?.start_date?.slice(0,10);if(start){const d=new Date(start+'T12:00:00');d.setDate(d.getDate()-(d.getDay()+6)%7);this.anchor=[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')}
      this.defaultCampus='';this.syncBlocks();this.previewTask='';await this.controller.recover();this.poll()},
    campusSlots(campus){const rows=this.state.context?.slots || [], exact=rows.filter(s=>s.campus_code===campus);return (exact.length?exact:rows.filter(s=>!s.campus_code)).filter(s=>s.enabled && s.status==='ENABLED').sort((a,b)=>a.slot_no-b.slot_no)},
    syncBlocks(){for(const campus of this.campuses){if(!this.blocks[campus])this.blocks[campus]={};for(const slot of this.campusSlots(campus))if(!this.blocks[campus][String(slot.slot_no)]){const hour=Number((slot.start_time || '').slice(0,2));this.blocks[campus][String(slot.slot_no)]=hour<12?'上午':hour<18?'下午':'晚间'}}},
    setBlock(campus,slot,value){if(!this.blocks[campus])this.blocks[campus]={};this.blocks[campus][String(slot)]=value;this.confirmed=false},
    async generate(){if(!this.canGenerate)return;try{const taskPatterns={};for(const task of this.tasks){const parts=String(this.patterns[task.id] || '').split('+').map(s=>s.trim());if(parts.some(p=>!/^\d+$/.test(p)))throw new Error('MEETING_PATTERN_INVALID');taskPatterns[task.id]=parts.map(Number)}
      await this.controller.submit({expectedSourceRevision:this.state.context.sourceRevision,reason:this.reason,
        plan:{version:1,replaceAuto:this.replaceAuto,week1Monday:this.anchor,defaultCampus:this.defaultCampus || this.campuses[0],slotBlocks:this.blocks,taskPatterns,taskParities:Object.fromEntries(this.tasks.map(t=>[t.id,this.parities[t.id] || 'ALL'])),minDayGap:Object.fromEntries(this.tasks.map(t=>[t.id,this.gaps[t.id] || 0]))},options:{profile:this.profile,time_limit:30,seed:0}});this.poll()
      }catch(error){this.state.error=error.message}},
    async recover(){this.pollCount=0;await this.controller.recover();this.poll()},
    async cancel(){await this.controller.cancel();this.poll()},
    poll(){clearTimeout(this.timer);if(this.pollCount>=120){this.state.error='CANDIDATE_POLL_LIMIT_REFRESH_MANUALLY';return}if(!this.state.job || this.isTerminal){if(this.state.job?.state==='SUCCEEDED')this.preview();return}this.timer=setTimeout(async()=>{this.pollCount++;await this.controller.refresh();this.poll()},2500)},
    optimizerLabel,diagnosticLabels,
    diagnosticTask(d){const ids=d.activityIds || d.activities || [d.activityId];return this.tasks.filter(t=>String(d.taskId || '')===t.id || ids.some(id=>String(id || '').startsWith(t.id+':'))).map(t=>t.course_name).join('、') || '排课条件'},
    async apply(){const result=await this.controller.apply();if(result)this.$emit('applied',result)},
    async preview(){await this.controller.preview(this.previewTask || undefined,this.previewWeek)}
  }
}
</script>
<style scoped>
.optimizer-panel{border:1px solid var(--border-200,#ddd);border-radius:12px;padding:18px;display:grid;gap:14px;background:var(--surface,#fff)}
.optimizer-panel header h3{margin:0}.optimizer-panel p,.optimizer-panel footer{line-height:1.7;margin:0}.optimizer-panel footer{font-size:13px}
.optimizer-warning,[role=alert]{color:var(--warning-700,#805000)}.optimizer-settings,.optimizer-actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.optimizer-panel label{display:grid;gap:6px}.optimizer-panel input,.optimizer-panel select,.optimizer-panel button{font:inherit;padding:8px;border:1px solid var(--border-200,#ddd);border-radius:6px}
.optimizer-panel button{cursor:pointer}.optimizer-panel button:disabled{opacity:.55;cursor:not-allowed}.optimizer-slots{display:flex;gap:10px;flex-wrap:wrap}.optimizer-slots strong{width:100%}.optimizer-slots input{width:70px}
.optimizer-panel .optimizer-primary{background:var(--primary-600,#2563eb);border-color:var(--primary-600,#2563eb);color:#fff;font-weight:600;justify-self:start;padding:10px 20px}.optimizer-clock-settings summary{cursor:pointer;padding:8px 0}.optimizer-clock-settings .optimizer-slots{padding-top:10px}
.optimizer-table{width:100%;border-collapse:collapse}.optimizer-table th,.optimizer-table td{text-align:left;padding:8px;border-bottom:1px solid var(--border-200,#ddd)}.optimizer-table small{display:block;font-weight:normal}
.optimizer-table input{width:100px}.optimizer-confirm{display:flex!important;align-items:center}.optimizer-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.optimizer-metrics dd{margin:0}
@media(max-width:720px){.optimizer-panel{padding:10px;overflow:auto}.optimizer-table{min-width:600px}}
</style>
