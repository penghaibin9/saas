<template>
  <ModulePageShell
    title="补考重修缓考免修 · 统计分析"
    subtitle="四类办理记录与结果，按学期和学院查询"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aamk-filter">
        <label class="aamk-filter__item">学期
          <AppTermCodePicker v-model="filters.term" placeholder="全部学期" />
        </label>
        <label class="aamk-filter__item">学院
          <AppCollegePicker v-model="filters.collegeId" :options="collegeOptions" placeholder="全部学院" />
        </label>
        <label class="aamk-filter__item">下钻维度
          <AppSelect v-model="filters.dimension" :options="dimensionOptions" />
        </label>
        <AppButton :loading="loading" @click="search">查询</AppButton>
        <AppButton variant="ghost" :disabled="loading || exporting || !stats" @click="openExport">导出 Excel</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="search" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <p class="aamk-stat-note">重修、免修和缓考比例反映审批结果；补考比例按已录入分数计算，正式成绩以发布台账为准。</p>
        <div class="aamk-cards">
          <AppMetricCard
            v-for="c in cards"
            :key="c.key"
            :title="c.title"
            :value="c.count"
            unit="条记录"
            :description="c.rateText"
            drillable
            :drill-target="c.key"
            @drill="onDrill"
          />
        </div>

        <div v-if="groups" class="aamk-groups">
          <AppSectionCard v-for="c in cards" :key="`g-${c.key}`" :title="`${c.title} · ${dimensionLabel}分布`">
            <EmptyState v-if="!(groups[c.key] || []).length" title="暂无分组数据" />
            <template v-else>
              <AppG2Chart :spec="groupChartSpec(groups[c.key])" :height="220" />
              <ul class="aamk-group-list">
                <li v-for="g in groups[c.key]" :key="g.key" class="aamk-group-item">
                  <span class="aamk-group-item__key">{{ g.key }}</span>
                  <span class="aamk-group-item__count">{{ g.count }}</span>
                </li>
              </ul>
            </template>
          </AppSectionCard>
        </div>

        <AppSectionCard v-if="drillLine" :title="`${drillLineLabel} · 明细`">
          <LoadingState v-if="detailLoading" /><EmptyState v-else-if="!detailRows.length" title="暂无数据" />
          <DataTable v-else :columns="detailColumns" :rows="detailRows" :pagination="pagination" @page-change="page => onDrill(drillLine,page)" row-key="rowKey"><template #cell-status="{row}">{{ academicStatusLabel(row.status) }}</template></DataTable>
        </AppSectionCard>
      </template>
    </div>

    <AppExportConfirm
      v-model:visible="exportVisible"
      module-name="补考重修缓考免修统计"
      :scope-label="ctx.dataScope.scopeName"
      :submitting="exporting"
      @confirm="doExport"
    />
  </ModulePageShell>
</template>

<script>
/** 补考重修缓考免修 · 统计分析（三级施工卡 10）：/admin/academic-affairs/makeup/stats，独立页面（非 console tab）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppExportConfirm, AppG2Chart, AppTermCodePicker, AppCollegePicker, AppSelect } from '@/components/common'
import { academicAffairsApi, academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'

const _LINES = [
  { key: 'makeup', title: '补考' },
  { key: 'retake', title: '重修' },
  { key: 'deferred', title: '缓考' },
  { key: 'exemption', title: '免修' }
]
const _DIM_LABEL = { course: '课程', term: '学期', college: '学院' }
const _DETAIL_COLUMNS = {
  makeup: [{ key: 'courseName', title: '课程' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }, { key: 'finalScore', title: '最终成绩' }],
  retake: [{ key: 'studentName', title: '学生' }, { key: 'courseName', title: '课程' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }],
  exemption: [{ key: 'studentName', title: '学生' }, { key: 'courseName', title: '课程' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }],
  deferred: [{ key: 'studentName', title: '学生' }, { key: 'courseName', title: '课程' }, { key: 'status', title: '状态' }]
}

export default {
  name: 'AaMakeupStatsView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppMetricCard, AppSectionCard, AppExportConfirm, AppG2Chart, AppTermCodePicker, AppCollegePicker, AppSelect },
  props:{ctx:{type:Object,required:true}},
  data() {
    return {
      alive:true,seq:0,detailSeq:0,exportSeq:0,optsSeq:0,detailLoading:false,exportCommand:null,
      pagination:{page:1,pageSize:20,total:0},
      loading: true, error: '',
      filters: { term: '', collegeId: '', dimension: '' },
      opts: { terms: [], colleges: [] },
      stats: null, groups: null,
      drillLine: '', detailRows: [],
      exportVisible: false, exporting: false
    }
  },
  computed: {
    identityKey(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope])},
    queryKey(){return JSON.stringify(this.filters)},
    collegeOptions() {
      return [{ label: '全部学院', value: '' }, ...this.opts.colleges.map((c) => ({ label: c.label, value: c.id }))]
    },
    dimensionOptions() {
      return [
        { label: '不分组', value: '' }, { label: '按课程', value: 'course' },
        { label: '按学期', value: 'term' }, { label: '按学院', value: 'college' }
      ]
    },
    cards() {
      if (!this.stats) return _LINES.map((l) => ({ ...l, count: null, rateText: '暂无数据' }))
      return _LINES.map((l) => {
        const d = this.stats[l.key] || { count: null, passRate: null }
        const label = l.key === 'makeup' ? '已录分及格比例' : '审批通过比例'
        const rateText = d.passRate == null ? `${label}：暂无结果` : `${label}：${Math.round(d.passRate * 1000) / 10}%`
        return { ...l, count: d.count ?? null, rateText }
      })
    },
    dimensionLabel() { return _DIM_LABEL[this.filters.dimension] || '' },
    drillLineLabel() { return (_LINES.find((l) => l.key === this.drillLine) || {}).title || '' },
    detailColumns() { return _DETAIL_COLUMNS[this.drillLine] || [] }
  },
  created(){this.loadOptions();this.search()},
  watch:{identityKey(){this.invalidate();this.opts={terms:[],colleges:[]};this.loadOptions();this.search()},queryKey:{flush:'sync',handler(){this.invalidate()}}},
  beforeUnmount(){this.alive=false;this.invalidate()},
  methods: {
    academicStatusLabel,
    capture(){return {identity:this.identityKey,query:this.queryKey}},
    current(c){return this.alive&&c.identity===this.identityKey&&c.query===this.queryKey},
    invalidate(){this.seq++;this.detailSeq++;this.exportSeq++;this.stats=null;this.groups=null;this.detailRows=[];this.drillLine='';this.loading=false;this.detailLoading=false;this.exporting=false;this.exportVisible=false;this.exportCommand=null;this.pagination={page:1,pageSize:20,total:0};this.error=''},
    fail(err,fallback='读取失败，请重试。'){if(/403|FORBIDDEN|NO_PERMISSION/.test(String(err?.bizCode||err?.code||''))){this.invalidate();this.opts={terms:[],colleges:[]};this.optsSeq++}this.error=gradeError(err,fallback)},
    async loadOptions(){
      const identity=this.identityKey,seq=++this.optsSeq
      try{const res=await academicAffairsApi.getStatsFilters();if(!this.alive||identity!==this.identityKey||seq!==this.optsSeq)return;if(res?.code!==0)throw res;this.opts={terms:res.data?.terms||[],colleges:res.data?.colleges||[]}}
      catch(err){if(this.alive&&identity===this.identityKey&&seq===this.optsSeq)this.fail(err)}
    },
    groupChartSpec(rows) {
      return {
        type: 'interval',
        data: (rows || []).map((g) => ({ name: g.key, value: g.count })),
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    async search() {
      const c=this.capture(),seq=++this.seq,params={term:this.filters.term||undefined,collegeId:this.filters.collegeId||undefined,dimension:this.filters.dimension||undefined}
      const valid=()=>this.current(c)&&seq===this.seq
      this.loading=true;this.error='';this.stats=null;this.groups=null;this.drillLine='';this.detailRows=[];this.detailSeq++;this.detailLoading=false
      try{const res=await api.stats(params);if(!valid())return;if(res?.code!==0)throw res;this.stats=res.data;this.groups=res.data?.groups||null}
      catch(err){if(valid())this.fail(err)}finally{if(valid())this.loading=false}
    },
    async onDrill(line,page=1) {
      if(!_LINES.some(l=>l.key===line)||!this.stats||this.loading)return
      const c=this.capture(),seq=++this.detailSeq
      const valid=()=>this.current(c)&&seq===this.detailSeq&&this.drillLine===line
      this.drillLine=line;this.detailRows=[];this.detailLoading=true;this.pagination.page=page;this.pagination.total=0
      try{const res=await api.statsDetail({term:this.filters.term||undefined,collegeId:this.filters.collegeId||undefined,line,page,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.detailRows=(res.data?.list||[]).map((r,i)=>({...r,rowKey:r.makeupId||r.applyId||r.exemptionId||r.deferId||`${line}-${page}-${i}`}));this.pagination.total=res.data?.total??this.detailRows.length}
      catch(err){if(valid())this.fail(err)}finally{if(valid())this.detailLoading=false}
    },
    openExport(){if(this.loading||this.exporting||!this.stats)return;this.exportCommand={...this.capture(),term:this.filters.term||undefined,collegeId:this.filters.collegeId||undefined};this.exportVisible=true},
    async doExport({reason}) {
      const c=this.exportCommand;if(!c||!this.current(c)||this.exporting||!String(reason||'').trim())return
      const seq=++this.exportSeq,valid=()=>this.current(c)&&seq===this.exportSeq
      this.exporting=true
      try{
        const res=await api.exportStats({term:c.term,collegeId:c.collegeId,purpose:reason});if(!valid())return;if(res?.code!==0)throw res
        const href=URL.createObjectURL(res.data),a=document.createElement('a');a.href=href;a.download=`补考重修缓考免修统计-${Date.now()}.xlsx`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(href);this.exportVisible=false;this.exportCommand=null
      }catch(err){if(valid())this.fail(err,'导出失败，请重新核对查询范围。')}finally{if(valid())this.exporting=false}
    }
  }
}
</script>

<style scoped>
.aamk-filter { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.aamk-filter__item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary, #64748b); }
.aamk-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.aamk-groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.aamk-group-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aamk-group-item { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px dashed var(--border-color, #e5e7eb); }
.aamk-group-item__key { color: var(--text-secondary, #64748b); }
.aamk-group-item__count { font-weight: 600; }
</style>
