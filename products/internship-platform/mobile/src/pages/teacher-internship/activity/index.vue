<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="我的实习工作" subtitle="本人签到 · 工作报告 · 紧急通知" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="card g16-card g16-batch">
          <view><text class="muted">当前批次</text><text class="title">{{ batches[batchIndex]?.name || '请选择批次' }}</text></view>
          <picker :range="batchLabels" :value="batchIndex" @change="onBatch"><text class="link">切换 ▾</text></picker>
        </view>

        <view class="card g16-card">
          <view class="row-between">
            <view><text class="eyebrow">01 · 本人签到</text><text class="title">{{ todayChecked ? '今天已签到' : '今天未签到' }}</text></view>
            <MobileStatusTag :type="todayChecked ? 'success' : 'warning'">{{ todayChecked ? '已完成' : '待完成' }}</MobileStatusTag>
          </view>
          <text v-if="todayChecked" class="muted">{{ todayChecked.checkedInAt }}</text>
          <button v-else class="btn btn-primary" :loading="checking" @click="checkin">本人签到</button>
          <view v-for="row in checkins.slice(0,5)" :key="row.id" class="list-row">
            <text>{{ row.localDate }}</text><text class="muted">{{ row.address || '已记录' }}</text>
          </view>
        </view>

        <view class="card g16-card">
          <view class="row-between">
            <view><text class="eyebrow">02 · 本人工作报告</text><text class="title">工作留痕</text></view>
            <text v-if="form.expectedVersion != null" class="link" @click="resetForm">取消修改</text>
          </view>
          <picker mode="date" :value="form.reportDate" @change="form.reportDate=$event.detail.value">
            <view class="field"><text>报告日期</text><text>{{ form.reportDate }} ▾</text></view>
          </picker>
          <textarea v-model="form.workContent" class="textarea" maxlength="8000" placeholder="今天完成了哪些实习指导工作（至少10字）" />
          <textarea v-model="form.issueContent" class="textarea small" maxlength="4000" placeholder="发现的问题（选填）" />
          <textarea v-model="form.nextPlan" class="textarea small" maxlength="4000" placeholder="下一步计划（选填）" />
          <input v-model="form.studentCount" class="input" type="number" placeholder="涉及学生人数（选填）" />
          <button class="btn btn-primary" :loading="saving" @click="saveReport">保存工作报告</button>
          <view v-for="row in reports" :key="row.id" class="report">
            <view class="row-between"><text class="strong">{{ row.reportDate }}</text><text class="link" @click="editReport(row)">编辑</text></view>
            <text class="body">{{ row.workContent }}</text>
            <text class="muted">版本 {{ row.version }}</text>
          </view>
        </view>

        <view class="card g16-card">
          <view><text class="eyebrow">03 · 紧急通知</text><text class="title">批次通知</text></view>
          <MobileInlineAlert type="info" description="通知来自服务端正式业务库，学生退出或重新登录后仍会重新读取。" />
          <view v-if="canPublish" class="notice-form">
            <input v-model="notice.title" class="input" maxlength="200" placeholder="紧急通知标题" />
            <textarea v-model="notice.content" class="textarea small" maxlength="5000" placeholder="紧急通知正文" />
            <button class="btn btn-danger" :loading="publishing" @click="publishNotice">校级发布</button>
          </view>
          <view v-for="row in notices" :key="row.id" class="report">
            <view class="row-between"><text class="strong">{{ row.title }}</text><MobileStatusTag :type="row.status==='PUBLISHED'?'danger':'default'">{{ row.status==='PUBLISHED'?'已发布':'已撤回' }}</MobileStatusTag></view>
            <text class="body">{{ row.content }}</text>
            <text class="muted">{{ row.senderName }} · {{ row.publishedAt }}</text>
          </view>
          <text v-if="!notices.length" class="muted">当前批次暂无紧急通知</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import teacherApi from '@/services/teacherApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

const today = () => {
  const d = new Date(), p = (v) => String(v).padStart(2, '0')
  return d.getFullYear() + '-' + p(d.getMonth()+1) + '-' + p(d.getDate())
}
const blank = () => ({ reportDate: today(), workContent: '', issueContent: '', nextPlan: '', studentCount: '', expectedVersion: null })

export default {
  data() { return { state:'loading', batches:[], batchId:'', batchIndex:0, checkins:[], reports:[], notices:[], checking:false, saving:false, publishing:false, form:blank(), notice:{title:'',content:''} } },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => b.name || ('批次 '+b.id)) },
    todayChecked() { return this.checkins.find((x) => x.localDate === today()) || null },
    canPublish() { return this.context.can('internship.communication.manage') && /ADMIN/i.test(this.context.roleCode || '') }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      this.state='loading'
      try {
        this.context.restore(); await this.context.load(true)
        this.batches=this.context.batches||[]; this.batchId=this.context.selectedBatchId||''
        this.batchIndex=Math.max(0,this.batches.findIndex((b)=>String(b.id)===String(this.batchId)))
        if (!this.batchId) { this.state='ready'; return }
        const [a,b,c]=await Promise.all([
          teacherApi.getMyInternshipCheckins(this.batchId),
          teacherApi.getMyInternshipWorkReports(this.batchId,1,20),
          teacherApi.getInternshipEmergencyNotices(this.batchId,true)
        ])
        this.checkins=a||[]; this.reports=b?.items||[]; this.notices=c||[]; this.state='ready'
      } catch(e) { this.state='error'; toast(e?.message||'教师实习工作加载失败') }
      finally { if(done) done() }
    },
    async onBatch(e) {
      this.batchIndex=Number(e.detail.value)||0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId=this.context.selectedBatchId; this.resetForm(); await this.load()
    },
    async checkin() {
      if (!this.batchId || this.checking) return
      this.checking=true
      try { await teacherApi.createMyInternshipCheckin({batchId:Number(this.batchId),timezoneName:'Asia/Shanghai'}); toast('教师签到已记录'); await this.load() }
      catch(e) { toast(e?.message||'签到失败') } finally { this.checking=false }
    },
    resetForm() { this.form=blank() },
    editReport(row) { this.form={reportDate:row.reportDate,workContent:row.workContent||'',issueContent:row.issueContent||'',nextPlan:row.nextPlan||'',studentCount:row.studentCount==null?'':String(row.studentCount),expectedVersion:Number(row.version||0)} },
    async saveReport() {
      if (!this.batchId || this.saving) return
      if ((this.form.workContent||'').trim().length<10) return toast('工作内容至少填写10个字')
      this.saving=true
      try {
        const body={batchId:Number(this.batchId),reportDate:this.form.reportDate,workContent:this.form.workContent,issueContent:this.form.issueContent,nextPlan:this.form.nextPlan}
        if(String(this.form.studentCount).trim()) body.studentCount=Number(this.form.studentCount)
        if(this.form.expectedVersion!=null) body.expectedVersion=this.form.expectedVersion
        await teacherApi.saveMyInternshipWorkReport(body); toast('工作报告已保存'); this.resetForm(); await this.load()
      } catch(e) { toast(e?.message||'工作报告保存失败') } finally { this.saving=false }
    },
    async publishNotice() {
      if (!this.batchId || this.publishing) return
      if ((this.notice.title||'').trim().length<2 || (this.notice.content||'').trim().length<5) return toast('请完整填写通知')
      this.publishing=true
      try { await teacherApi.publishInternshipEmergencyNotice({batchId:Number(this.batchId),title:this.notice.title,content:this.notice.content}); this.notice={title:'',content:''}; toast('紧急通知已发布'); await this.load() }
      catch(e) { toast(e?.message||'发布失败') } finally { this.publishing=false }
    }
  }
}
</script>

<style scoped>
.g16-card{padding:14px;display:flex;flex-direction:column;gap:12px}.g16-batch{flex-direction:row;align-items:center;justify-content:space-between}.eyebrow,.muted{display:block;font-size:11px;color:var(--text-tertiary);line-height:1.6}.eyebrow{color:var(--teacher-700);font-weight:700}.title{display:block;font-size:17px;font-weight:700}.strong{font-weight:600}.link{font-size:12px;color:var(--teacher-700)}.list-row,.field{display:flex;justify-content:space-between;padding:10px;border-top:1px solid var(--border-light);font-size:12px}.field{border:1px solid var(--border-light);border-radius:8px}.input,.textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-light);border-radius:8px;padding:10px;font-size:13px}.textarea{height:120px}.textarea.small{height:80px}.report{display:flex;flex-direction:column;gap:6px;padding:10px;border-radius:8px;background:var(--gray-50)}.body{font-size:13px;line-height:1.65;white-space:pre-wrap}.notice-form{display:flex;flex-direction:column;gap:8px}
</style>
