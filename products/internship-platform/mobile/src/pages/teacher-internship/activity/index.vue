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
          <text v-if="todayChecked" class="muted">{{ todayChecked.checkedInAt }} · {{ checkinResultLabel(todayChecked.result) }}</text>
          <text v-if="todayChecked?.accuracyM != null" class="muted">定位精度约 {{ Math.round(todayChecked.accuracyM) }} 米 · {{ todayChecked.coordinateSystem || 'GCJ02' }}</text>
          <text v-if="todayChecked?.watermarkedFileId" class="link" @click="openCheckinEvidence(todayChecked)">查看服务端水印照片</text>
          <view v-if="!todayChecked" class="teacher-checkin-evidence">
            <view>
              <text class="strong">现场照片（建议）</text>
              <text class="muted">{{ checkinPhotoName || '仅现场相机；原图保留，服务器写入教师姓名、时间、位置水印并计算双哈希。' }}</text>
            </view>
            <button class="btn btn-ghost" :disabled="checkinPhotoUploading || checking" @click="captureCheckinPhoto">
              {{ checkinPhotoUploading ? '上传中…' : (checkinPhotoFileId ? '重新拍摄' : '现场拍照') }}
            </button>
          </view>
          <button v-if="!todayChecked" class="btn btn-primary" :loading="checking" :disabled="checkinPhotoUploading" @click="checkin">本人签到</button>
          <view v-for="row in checkins.slice(0,5)" :key="row.id" class="list-row">
            <text>{{ row.localDate }}</text><text class="muted">{{ checkinResultLabel(row.result) }} · {{ row.address || '已记录' }}</text>
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
          <view class="row-between">
            <view><text class="eyebrow">03 · 周报 / 月报 / 总结</text><text class="title">教师本人周期报告</text></view>
            <text v-if="periodForm.expectedVersion != null" class="link" @click="resetPeriodForm">取消修改</text>
          </view>
          <picker :range="periodLabels" :value="periodTypeIndex" @change="onPeriodType">
            <view class="field"><text>报告类型</text><text>{{ periodLabels[periodTypeIndex] }} ▾</text></view>
          </picker>
          <input v-model="periodForm.periodKey" class="input" :placeholder="periodKeyHint" :disabled="periodForm.reportType==='SUMMARY'" />
          <textarea v-model="periodForm.content" class="textarea" maxlength="12000" :placeholder="periodContentHint" />
          <textarea v-model="periodForm.issueContent" class="textarea small" maxlength="4000" placeholder="本周期问题与风险（选填）" />
          <textarea v-model="periodForm.nextPlan" class="textarea small" maxlength="4000" placeholder="下一周期计划（选填）" />
          <input v-model="periodForm.studentCount" class="input" type="number" placeholder="涉及学生人数（选填）" />
          <button class="btn btn-primary" :loading="periodSaving" @click="savePeriodReport">保存周期报告</button>
          <view v-for="row in periodReports" :key="row.id" class="report">
            <view class="row-between">
              <text class="strong">{{ periodTypeLabel(row.reportType) }} · {{ row.periodKey }}</text>
              <text class="link" @click="editPeriodReport(row)">编辑</text>
            </view>
            <text class="body">{{ row.content }}</text>
            <text class="muted">版本 {{ row.version }} · {{ row.submittedAt }}</text>
          </view>
          <text v-if="!periodReports.length" class="muted">当前批次暂无教师周报、月报或总结</text>
        </view>

        <view class="card g16-card">
          <view><text class="eyebrow">04 · 紧急通知</text><text class="title">批次通知</text></view>
          <MobileInlineAlert type="info" description="通知来自服务端正式业务库，学生退出或重新登录后仍会重新读取。" />
          <view v-if="canPublish" class="notice-form">
            <picker :range="noticeTypeLabels" :value="noticeTypeIndex" @change="onNoticeType">
              <view class="field"><text>公告类型</text><text>{{ noticeTypeLabels[noticeTypeIndex] }} ▾</text></view>
            </picker>
            <picker :range="noticeUrgencyLabels" :value="noticeUrgencyIndex" @change="onNoticeUrgency">
              <view class="field"><text>紧急程度</text><text>{{ noticeUrgencyLabels[noticeUrgencyIndex] }} ▾</text></view>
            </picker>
            <input v-model="notice.title" class="input" maxlength="200" placeholder="通知标题" />
            <textarea v-model="notice.content" class="textarea small" maxlength="5000" placeholder="通知正文" />
            <view class="notice-dates">
              <picker mode="date" :value="notice.validFrom" @change="notice.validFrom=$event.detail.value">
                <view class="field"><text>有效期开始</text><text>{{ notice.validFrom || '不限' }} ▾</text></view>
              </picker>
              <picker mode="date" :value="notice.validUntil" @change="notice.validUntil=$event.detail.value">
                <view class="field"><text>有效期结束</text><text>{{ notice.validUntil || '不限' }} ▾</text></view>
              </picker>
            </view>
            <view class="notice-attachments">
              <view class="row-between"><text class="strong">附件</text><text class="muted">{{ notice.attachments.length }}/9</text></view>
              <view v-for="(file,index) in notice.attachments" :key="file.fileId" class="notice-file">
                <text class="notice-file-name" @click="openNoticeAttachment(file)">{{ file.fileName }}</text>
                <text class="notice-remove" @click="removeNoticeAttachment(index)">移除</text>
              </view>
              <button v-if="notice.attachments.length<9" class="btn btn-ghost" :loading="noticeUploading" :disabled="publishing" @click="addNoticeAttachment">添加附件</button>
            </view>
            <MobileInlineAlert v-if="notice.urgency!=='NORMAL'" type="warning" description="重要/紧急通知会在学生端强制弹框，学生点击“我已知悉”后才记录确认回执。" />
            <button class="btn btn-danger" :loading="publishing" :disabled="noticeUploading" @click="publishNotice">校级发布</button>
          </view>
          <view v-for="row in notices" :key="row.id" class="report">
            <view class="row-between"><text class="strong">{{ row.title }}</text><MobileStatusTag :type="row.status==='PUBLISHED'?(row.urgency==='URGENT'?'danger':'warning'):'default'">{{ row.status==='PUBLISHED'?noticeUrgencyLabel(row.urgency):'已撤回' }}</MobileStatusTag></view>
            <text class="muted">{{ noticeTypeLabel(row.noticeType) }} · {{ row.senderName }} · {{ row.publishedAt }}</text>
            <text v-if="row.validFrom||row.validUntil" class="muted">有效期 {{ (row.validFrom||'不限').slice(0,10) }} ~ {{ (row.validUntil||'不限').slice(0,10) }}</text>
            <text class="body">{{ row.content }}</text>
            <view v-if="row.attachments?.length" class="notice-attachments">
              <view v-for="file in row.attachments" :key="file.fileId" class="notice-file">
                <text class="notice-file-name" @click="openNoticeAttachment(file)">{{ file.fileName || '通知附件' }}</text>
                <text class="link" @click="openNoticeAttachment(file)">查看</text>
              </view>
            </view>
            <button v-if="canPublish && row.status==='PUBLISHED'" class="btn btn-ghost" :loading="noticeWithdrawingId===String(row.id)" @click="withdrawNotice(row)">撤回通知</button>
          </view>
          <text v-if="!notices.length" class="muted">当前批次暂无紧急通知</text>
        </view>
      </view>
    </MobileGlobalState>

    <view v-if="activeNotice" class="g16-notice-mask">
      <view class="g16-notice-dialog">
        <view class="row-between">
          <view class="flex-1">
            <text class="eyebrow">重要通知</text>
            <text class="title">{{ activeNotice.title }}</text>
          </view>
          <MobileStatusTag :type="activeNotice.urgency==='URGENT'?'danger':'warning'">{{ noticeUrgencyLabel(activeNotice.urgency) }}</MobileStatusTag>
        </view>
        <text class="muted">{{ noticeTypeLabel(activeNotice.noticeType) }} · {{ activeNotice.senderName || '学校' }} · {{ activeNotice.publishedAt }}</text>
        <scroll-view scroll-y class="g16-notice-body">
          <text class="body">{{ activeNotice.content }}</text>
          <view v-if="activeNotice.attachments?.length" class="notice-attachments">
            <view v-for="file in activeNotice.attachments" :key="file.fileId" class="notice-file">
              <text class="notice-file-name" @click="openNoticeAttachment(file)">{{ file.fileName || '通知附件' }}</text>
              <text class="link" @click="openNoticeAttachment(file)">查看</text>
            </view>
          </view>
        </scroll-view>
        <MobileInlineAlert type="warning" description="只有点击“我已知悉”并成功写入回执后，这条重要通知才不会再次强弹。" />
        <button class="btn btn-primary" :loading="acknowledgingNotice" @click="acknowledgeActiveNotice">我已知悉</button>
      </view>
    </view>
  </view>
</template>

<script>
import teacherApi from '@/services/teacherApi'
import { chooseSingleFile, uploadBusinessFile, openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

const today = () => {
  const d = new Date(), p = (v) => String(v).padStart(2, '0')
  return d.getFullYear() + '-' + p(d.getMonth()+1) + '-' + p(d.getDate())
}
const blank = () => ({ reportDate: today(), workContent: '', issueContent: '', nextPlan: '', studentCount: '', expectedVersion: null })
const periodOptions = [
  { code:'WEEKLY', label:'周报' },
  { code:'MONTHLY', label:'月报' },
  { code:'SUMMARY', label:'总结' }
]
const currentMonth = () => today().slice(0,7)
const currentIsoWeek = () => {
  const d = new Date(), t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const day = t.getUTCDay() || 7
  t.setUTCDate(t.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  const week = Math.ceil((((t - yearStart) / 86400000) + 1) / 7)
  return t.getUTCFullYear() + '-W' + String(week).padStart(2,'0')
}
const defaultPeriodKey = (type) => type === 'WEEKLY' ? currentIsoWeek() : (type === 'MONTHLY' ? currentMonth() : 'SUMMARY')
const blankPeriod = (type='WEEKLY') => ({ reportType:type, periodKey:defaultPeriodKey(type), content:'', issueContent:'', nextPlan:'', studentCount:'', expectedVersion:null })

const noticeTypeOptions = [
  { code:'AGREEMENT', label:'实习协议' },
  { code:'TRAINING', label:'岗前培训' },
  { code:'SAFETY', label:'安全条例' },
  { code:'NOTICE', label:'通知公告' },
  { code:'OTHER', label:'其他' }
]
const noticeUrgencyOptions = [
  { code:'NORMAL', label:'普通' },
  { code:'IMPORTANT', label:'重要' },
  { code:'URGENT', label:'紧急' }
]
const blankNotice = () => ({
  title:'', content:'', noticeType:'NOTICE', urgency:'IMPORTANT',
  validFrom:'', validUntil:'', attachmentFileIds:[], attachments:[]
})

export default {
  data() { return { state:'loading', batches:[], batchId:'', batchIndex:0, checkins:[], reports:[], periodReports:[], notices:[], pendingNotices:[], activeNotice:null, acknowledgingNotice:false, checking:false, checkinPhotoFileId:'', checkinPhotoName:'', checkinPhotoUploading:false, checkinTimezoneName:this.detectTimezone(), saving:false, periodSaving:false, publishing:false, form:blank(), periodForm:blankPeriod(), notice:blankNotice(), noticeUploading:false, noticeWithdrawingId:'' } },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => b.name || ('批次 '+b.id)) },
    periodLabels() { return periodOptions.map((x) => x.label) },
    periodTypeIndex() { return Math.max(0, periodOptions.findIndex((x) => x.code === this.periodForm.reportType)) },
    periodKeyHint() { return this.periodForm.reportType === 'WEEKLY' ? '例如 2026-W39' : (this.periodForm.reportType === 'MONTHLY' ? '例如 2026-09' : 'SUMMARY') },
    periodContentHint() { return this.periodForm.reportType === 'SUMMARY' ? '实习指导总结（至少300字）' : (this.periodForm.reportType === 'MONTHLY' ? '本月指导工作（至少100字）' : '本周指导工作（至少30字）') },
    noticeTypeLabels() { return noticeTypeOptions.map((x) => x.label) },
    noticeUrgencyLabels() { return noticeUrgencyOptions.map((x) => x.label) },
    noticeTypeIndex() { return Math.max(0, noticeTypeOptions.findIndex((x) => x.code === this.notice.noticeType)) },
    noticeUrgencyIndex() { return Math.max(0, noticeUrgencyOptions.findIndex((x) => x.code === this.notice.urgency)) },
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
        const [a,b,p,c,n]=await Promise.all([
          teacherApi.getMyInternshipCheckins(this.batchId),
          teacherApi.getMyInternshipWorkReports(this.batchId,1,20),
          teacherApi.getMyInternshipPeriodReports(this.batchId,1,20),
          teacherApi.getInternshipEmergencyNotices(this.batchId,true),
          teacherApi.getPendingInternshipEmergencyNotices(this.batchId)
        ])
        this.checkins=a||[]
        this.reports=b?.items||[]
        this.periodReports=p?.items||[]
        this.notices=c||[]
        this.pendingNotices=Array.isArray(n)?n:[]
        if (!this.activeNotice) this.activeNotice=this.pendingNotices[0]||null
        this.state='ready'
      } catch(e) { this.state='error'; toast(e?.message||'教师实习工作加载失败') }
      finally { if(done) done() }
    },
    async onBatch(e) {
      this.batchIndex=Number(e.detail.value)||0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId=this.context.selectedBatchId; this.resetForm(); this.resetPeriodForm(); this.notice=blankNotice(); this.pendingNotices=[]; this.activeNotice=null; this.acknowledgingNotice=false; this.checkinPhotoFileId=''; this.checkinPhotoName=''; await this.load()
    },
    detectTimezone() {
      try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai' }
      catch (e) { return 'Asia/Shanghai' }
    },
    checkinResultLabel(value) {
      const map={NORMAL:'正常签到',RECORDED:'已记录',NO_LOCATION:'无定位待核实',LOW_ACCURACY:'定位精度不足',LOCATION_UNCERTAIN:'定位待核实',MAKEUP:'补签'}
      return map[String(value||'').toUpperCase()] || '已记录'
    },
    captureCheckinPhoto() {
      if (this.checkinPhotoUploading || this.checking) return
      this.checkinPhotoUploading=true
      uni.chooseImage({
        count:1,
        sourceType:['camera'],
        sizeType:['original'],
        success: async (res) => {
          try {
            const path=(res.tempFilePaths||[])[0]
            const source=(res.tempFiles||[])[0]||{}
            if(!path) return
            const uploaded=await uploadBusinessFile({
              path,
              name:source.name||`teacher-checkin-${Date.now()}.jpg`,
              size:source.size||0
            }, { bizType:'INTERNSHIP_TEACHER_CHECKIN_PHOTO' })
            if(!uploaded?.fileId) throw new Error('现场照片上传结果不完整')
            this.checkinPhotoFileId=String(uploaded.fileId)
            this.checkinPhotoName=uploaded.fileName||'现场照片已上传'
            toast('原图已上传，签到后由服务器生成可信水印')
          } catch(e) { toast(e?.message||'现场照片上传失败') }
          finally { this.checkinPhotoUploading=false }
        },
        fail:()=>{ this.checkinPhotoUploading=false }
      })
    },
    async openCheckinEvidence(row) {
      if(!row?.watermarkedFileId) return
      try { await openBusinessFile(row.watermarkedFileId, `教师签到-${row.localDate || '现场'}-水印.jpg`) }
      catch(e) { toast(e?.message||'水印照片暂时无法打开') }
    },
    checkin() {
      if (!this.batchId || this.checking || this.checkinPhotoUploading) return
      uni.showModal({
        title:'教师本人签到',
        content:this.checkinPhotoFileId
          ? '将采集一次当前位置，服务端写入教师姓名、服务器时间和位置水印。确认签到？'
          : '将采集一次当前位置并登记本人签到。未拍现场照片时可在定位失败后留痕为“无定位待核实”。确认签到？',
        success:(r)=>{ if(r.confirm) this.beginTeacherCheckin() }
      })
    },
    beginTeacherCheckin() {
      if(this.checking) return
      this.checking=true
      const submit=async (loc={})=>{
        try {
          const result=await teacherApi.createMyInternshipCheckin({
            batchId:Number(this.batchId),
            timezoneName:this.checkinTimezoneName,
            photoFileId:this.checkinPhotoFileId||undefined,
            coordinateSystem:loc.latitude!=null?'GCJ02':undefined,
            locationProvider:loc.latitude!=null?'UNI_GCJ02':undefined,
            ...loc
          })
          this.checkinPhotoFileId=''
          this.checkinPhotoName=''
          toast(result?.evidenceAvailable?'教师签到成功，水印证据已留存':'教师签到已记录')
          await this.load()
        } catch(e) { toast(e?.message||'签到失败') }
        finally { this.checking=false }
      }
      uni.getLocation({
        type:'gcj02',
        success:(p)=>submit({
          latitude:p.latitude,
          longitude:p.longitude,
          accuracyM:p.accuracy,
          address:p.address||p.name||''
        }),
        fail:()=>{
          if(this.checkinPhotoFileId){
            this.checking=false
            toast('已拍现场照片时必须取得位置，才能生成可信位置水印')
            return
          }
          submit({})
        }
      })
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
    periodTypeLabel(type) { return periodOptions.find((x)=>x.code===type)?.label || type },
    resetPeriodForm(type='WEEKLY') { this.periodForm=blankPeriod(type) },
    onPeriodType(e) {
      const type=periodOptions[Number(e.detail.value)||0]?.code||'WEEKLY'
      this.resetPeriodForm(type)
    },
    editPeriodReport(row) {
      this.periodForm={
        reportType:row.reportType,
        periodKey:row.periodKey,
        content:row.content||'',
        issueContent:row.issueContent||'',
        nextPlan:row.nextPlan||'',
        studentCount:row.studentCount==null?'':String(row.studentCount),
        expectedVersion:Number(row.version||0)
      }
    },
    async savePeriodReport() {
      if (!this.batchId || this.periodSaving) return
      const min=this.periodForm.reportType==='SUMMARY'?300:(this.periodForm.reportType==='MONTHLY'?100:30)
      if ((this.periodForm.content||'').trim().length<min) return toast(`当前报告至少填写${min}个字`)
      this.periodSaving=true
      try {
        const body={
          batchId:Number(this.batchId),
          reportType:this.periodForm.reportType,
          periodKey:this.periodForm.periodKey,
          content:this.periodForm.content,
          issueContent:this.periodForm.issueContent,
          nextPlan:this.periodForm.nextPlan
        }
        if(String(this.periodForm.studentCount).trim()) body.studentCount=Number(this.periodForm.studentCount)
        if(this.periodForm.expectedVersion!=null) body.expectedVersion=this.periodForm.expectedVersion
        await teacherApi.saveMyInternshipPeriodReport(body)
        toast('教师周期报告已保存')
        this.resetPeriodForm(this.periodForm.reportType)
        await this.load()
      } catch(e) { toast(e?.message||'周期报告保存失败') } finally { this.periodSaving=false }
    },
    async acknowledgeActiveNotice() {
      const row=this.activeNotice
      if (!row?.id || !this.batchId || this.acknowledgingNotice) return
      this.acknowledgingNotice=true
      try {
        await teacherApi.acknowledgeInternshipEmergencyNotice(row.id,this.batchId)
        this.pendingNotices=this.pendingNotices.filter((item)=>String(item.id)!==String(row.id))
        this.activeNotice=this.pendingNotices[0]||null
        if (!this.activeNotice) toast('重要通知已确认')
      } catch(e) {
        toast(e?.message || '知悉回执提交失败，通知仍会保留')
      } finally {
        this.acknowledgingNotice=false
      }
    },
    onNoticeType(e) {
      this.notice.noticeType = noticeTypeOptions[Number(e.detail.value)||0]?.code || 'NOTICE'
    },
    onNoticeUrgency(e) {
      this.notice.urgency = noticeUrgencyOptions[Number(e.detail.value)||0]?.code || 'IMPORTANT'
    },
    async addNoticeAttachment() {
      if (this.noticeUploading || this.publishing || this.notice.attachments.length >= 9) return
      this.noticeUploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const uploaded = await uploadBusinessFile(file, { bizType:'INTERNSHIP_NOTICE' })
        if (!uploaded?.fileId) throw new Error('附件上传结果不完整')
        if (!this.notice.attachmentFileIds.includes(String(uploaded.fileId))) {
          this.notice.attachmentFileIds.push(String(uploaded.fileId))
          this.notice.attachments.push({
            fileId:String(uploaded.fileId),
            fileName:uploaded.fileName || file.name || '通知附件'
          })
        }
        toast('通知附件上传成功')
      } catch(e) { toast(e?.message || '通知附件上传失败') }
      finally { this.noticeUploading=false }
    },
    removeNoticeAttachment(index) {
      if (this.noticeUploading || this.publishing) return
      this.notice.attachmentFileIds.splice(index,1)
      this.notice.attachments.splice(index,1)
    },
    async openNoticeAttachment(file) {
      try { await openBusinessFile(file.fileId, file.fileName || '通知附件') }
      catch(e) { toast(e?.message || '附件暂时无法打开') }
    },
    noticeTypeLabel(value) {
      return noticeTypeOptions.find((x)=>x.code===String(value||'').toUpperCase())?.label || '通知公告'
    },
    noticeUrgencyLabel(value) {
      return noticeUrgencyOptions.find((x)=>x.code===String(value||'').toUpperCase())?.label || '普通'
    },
    async withdrawNotice(row) {
      if (!row?.id || this.noticeWithdrawingId || row.status !== 'PUBLISHED') return
      this.noticeWithdrawingId=String(row.id)
      try {
        await teacherApi.withdrawInternshipEmergencyNotice(row.id,'发布人主动撤回')
        toast('通知已撤回')
        await this.load()
      } catch(e) { toast(e?.message || '通知撤回失败') }
      finally { this.noticeWithdrawingId='' }
    },
    async publishNotice() {
      if (!this.batchId || this.publishing || this.noticeUploading) return
      if ((this.notice.title||'').trim().length<2 || (this.notice.content||'').trim().length<5) return toast('请完整填写通知')
      if (this.notice.validFrom && this.notice.validUntil && this.notice.validFrom > this.notice.validUntil) return toast('有效期结束日期不能早于开始日期')
      this.publishing=true
      try {
        await teacherApi.publishInternshipEmergencyNotice({
          batchId:Number(this.batchId),
          title:this.notice.title.trim(),
          content:this.notice.content.trim(),
          noticeType:this.notice.noticeType,
          urgency:this.notice.urgency,
          validFrom:this.notice.validFrom ? this.notice.validFrom + 'T00:00:00' : null,
          validUntil:this.notice.validUntil ? this.notice.validUntil + 'T23:59:59' : null,
          attachmentFileIds:this.notice.attachmentFileIds
        })
        this.notice=blankNotice()
        toast('通知已发布')
        await this.load()
      } catch(e) { toast(e?.message||'发布失败') }
      finally { this.publishing=false }
    }
  }
}
</script>

<style scoped>
.g16-card{padding:14px;display:flex;flex-direction:column;gap:12px}.teacher-checkin-evidence{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px;border:1px solid var(--border-light);border-radius:10px;background:var(--gray-50)}.notice-dates{display:grid;grid-template-columns:1fr 1fr;gap:8px}.notice-attachments{display:flex;flex-direction:column;gap:7px}.notice-file{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border-radius:8px;background:var(--gray-50);font-size:12px}.notice-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--teacher-700)}.notice-remove{flex:0 0 auto;color:var(--danger-600)}.g16-batch{flex-direction:row;align-items:center;justify-content:space-between}.eyebrow,.muted{display:block;font-size:11px;color:var(--text-tertiary);line-height:1.6}.eyebrow{color:var(--teacher-700);font-weight:700}.title{display:block;font-size:17px;font-weight:700}.strong{font-weight:600}.link{font-size:12px;color:var(--teacher-700)}.list-row,.field{display:flex;justify-content:space-between;padding:10px;border-top:1px solid var(--border-light);font-size:12px}.field{border:1px solid var(--border-light);border-radius:8px}.input,.textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-light);border-radius:8px;padding:10px;font-size:13px}.textarea{height:120px}.textarea.small{height:80px}.report{display:flex;flex-direction:column;gap:6px;padding:10px;border-radius:8px;background:var(--gray-50)}.body{font-size:13px;line-height:1.65;white-space:pre-wrap}.notice-form{display:flex;flex-direction:column;gap:8px}
.g16-notice-mask{position:fixed;z-index:9999;inset:0;background:rgba(15,23,42,.68);display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box}.g16-notice-dialog{width:100%;max-width:560px;max-height:82vh;background:var(--bg-card);border-radius:16px;padding:18px;box-sizing:border-box;display:flex;flex-direction:column;gap:12px}.g16-notice-body{max-height:42vh;padding:12px;border:1px solid var(--border-light);border-radius:10px;background:var(--gray-50);box-sizing:border-box}
</style>
