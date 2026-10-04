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
            <view><text class="eyebrow">01 · 本人签到</text><text class="title">{{ todayChecked ? (checkinTone(todayChecked.result)==='warning' ? '今天已记录，待核实' : '今天已签到') : '今天未签到' }}</text></view>
            <MobileStatusTag :type="todayChecked ? checkinTone(todayChecked.result) : 'warning'" :label="todayChecked ? checkinResultLabel(todayChecked.result) : '待完成'" />
          </view>
          <text v-if="todayChecked" class="muted">签到当地时间：{{ todayChecked.localCheckedInAt || '待核实' }} · {{ checkinResultLabel(todayChecked.result) }}</text>
          <text v-if="todayChecked?.countryRegion" class="muted">国家或地区：{{ todayChecked.countryRegion }}</text>
          <text v-if="todayChecked?.accuracyM != null" class="muted">定位精度约 {{ Math.round(todayChecked.accuracyM) }} 米 · {{ coordinateLabel(todayChecked.coordinateSystem) }}</text>
          <text v-if="todayChecked?.distanceM != null" class="muted">距允许地点中心约 {{ Math.round(todayChecked.distanceM) }} 米</text>
          <text v-if="todayChecked && !todayChecked.address" class="muted">未取得地图地址，已保留定位事实供核对。</text>
          <text class="muted">{{ checkinRule?.configured ? '学校已配置 '+checkinRule.locations.length+' 个允许签到地点，服务端核验距离和定位精度。' : '学校未配置教师签到范围，本次仅作留痕，不判定围栏内正常。' }}</text>
          <text v-if="checkinRule?.canCheckin===false" class="muted">{{ checkinRule.unavailableReason }}</text>
          <view v-if="!todayChecked" class="teacher-location-policy">
            <view class="row-between"><text>境外签到</text><switch :checked="checkinOverseas" :disabled="checking" @change="checkinOverseas=$event.detail.value" /></view>
            <input v-if="checkinOverseas" v-model.trim="checkinCountryRegion" class="field" maxlength="100" placeholder="国家或地区（选填）" :disabled="checking" />
            <text class="muted">浏览器和境外定位使用国际通用坐标；坐标系不一致时保留记录，待学校核实。</text>
          </view>
          <view v-if="todayChecked?.photoFileId || todayChecked?.watermarkedFileId" class="row-between">
            <text v-if="todayChecked?.photoFileId" class="link" @click="openCheckinEvidence(todayChecked, true)">查看现场原图</text>
            <text v-if="todayChecked?.watermarkedFileId" class="link" @click="openCheckinEvidence(todayChecked)">查看服务端水印照片</text>
          </view>
          <text v-if="todayChecked?.note" class="muted">签到备注：{{ todayChecked.note }}</text>
          <textarea v-if="!todayChecked" v-model.trim="checkinNote" class="textarea small" maxlength="500" placeholder="签到备注（选填，例如：企业现场巡访、学生集中指导）" />
          <view v-if="!todayChecked" class="teacher-checkin-evidence">
            <view>
              <text class="strong">现场照片（建议）</text>
              <text class="muted">{{ checkinPhotoName || '现场拍照后保留原图，自动生成包含教师姓名、时间与位置的水印照片。' }}</text>
            </view>
            <button class="btn btn-ghost" :disabled="checkinPhotoUploading || checking" @click="captureCheckinPhoto">
              {{ checkinPhotoUploading ? '上传中…' : (checkinPhotoFileId ? '重新拍摄' : '现场拍照') }}
            </button>
          </view>
          <button v-if="!todayChecked" class="btn btn-primary" :loading="checking" :disabled="checkinPhotoUploading || checkinRule?.canCheckin===false" @click="checkin">本人签到</button>
          <view class="teacher-calendar">
            <view class="row-between">
              <view><text class="strong">完整签到日历</text><text class="muted">按月查看本人全部历史签到与补签事实</text></view>
              <picker mode="date" fields="month" :value="calendarMonth" @change="onCalendarMonth">
                <text class="link">{{ calendarMonth }} ▾</text>
              </picker>
            </view>
            <text v-if="calendarState==='loading'" class="muted">正在读取所选月份…</text>
            <view v-else-if="calendarState==='error'" class="row-between"><text class="muted">{{ calendarError }}</text><text class="link" @click="loadCalendar">重新读取日历</text></view>
            <view v-if="calendarState==='ready'" class="teacher-calendar-week">
              <text v-for="item in calendarWeekdays" :key="item">{{ item }}</text>
            </view>
            <view v-if="calendarState==='ready'" class="teacher-calendar-grid">
              <view v-for="cell in calendarCells" :key="cell.key" class="teacher-calendar-day" :class="{ 'has-record': !!cell.row }">
                <text>{{ cell.day || '' }}</text>
                <text v-if="cell.row" class="teacher-calendar-mark">{{ checkinResultShort(cell.row.result) }}</text>
              </view>
            </view>
            <view v-for="row in monthCheckins" :key="'month-'+row.id" class="list-row">
              <view><text>{{ row.localDate }}</text><text v-if="row.note" class="muted">{{ row.note }}</text></view>
              <text class="muted">{{ checkinResultLabel(row.result) }} · {{ row.address || '已记录' }}</text>
              <view class="row-between">
                <text v-if="row.photoFileId" class="link" @click="openCheckinEvidence(row, true)">原图</text>
                <text v-if="row.watermarkedFileId" class="link" @click="openCheckinEvidence(row)">水印</text>
              </view>
            </view>
            <text v-if="calendarState==='ready' && !monthCheckins.length" class="muted">当前月份暂无签到记录</text>
          </view>
          <ReportFilePreview ref="checkinPreview" />
        </view>

        <view class="card g16-card">
          <view class="row-between">
            <view><text class="eyebrow">02 · 本人补签</text><text class="title">缺卡申请补签</text></view>
            <MobileStatusTag type="default" :label="makeups.length + ' 条'" />
          </view>
          <MobileInlineAlert type="info" description="补签必须提交原因，由校级岗位实习管理员审核；审批通过后才会生成正式补签记录。" />
          <picker mode="date" :value="makeupForm.localDate" :end="todayValue" @change="makeupForm.localDate=$event.detail.value">
            <view class="field"><text>补签日期</text><text>{{ makeupForm.localDate || '请选择' }} ▾</text></view>
          </picker>
          <textarea v-model="makeupForm.reason" class="textarea small" maxlength="500" placeholder="补签原因（至少5字）" />
          <view class="teacher-checkin-evidence">
            <view>
              <text class="strong">佐证材料（选填）</text>
              <text class="muted">{{ makeupEvidenceName || '可上传图片、PDF、Word 等正式佐证文件' }}</text>
            </view>
            <button class="btn btn-ghost" :disabled="makeupEvidenceUploading || makeupSubmitting" @click="pickMakeupEvidence">
              {{ makeupEvidenceUploading ? '上传中…' : (makeupForm.evidenceFileId ? '更换佐证' : '上传佐证') }}
            </button>
          </view>
          <button class="btn btn-primary" :loading="makeupSubmitting" :disabled="makeupEvidenceUploading" @click="submitMakeup">提交补签申请</button>
          <view v-for="row in makeups" :key="row.id" class="report">
            <view class="row-between">
              <text class="strong">{{ row.localDate }}</text>
              <MobileStatusTag :type="makeupStatusTone(row.status)" :label="makeupStatusLabel(row.status)" />
            </view>
            <text class="body">{{ row.reason }}</text>
            <text v-if="row.reviewComment" class="muted">审核意见：{{ row.reviewComment }}</text>
            <view class="row-between">
              <text v-if="row.evidenceFileId" class="link" @click="openMakeupEvidence(row)">查看佐证</text>
              <text v-if="row.status==='PENDING'" class="link danger-link" @click="withdrawMakeup(row)">撤回</text>
            </view>
          </view>
          <text v-if="!makeups.length" class="muted">当前批次暂无教师补签申请</text>
        </view>

        <view class="card g16-card">
          <view class="row-between">
            <view><text class="eyebrow">03 · 本人工作报告</text><text class="title">工作留痕</text></view>
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
            <view><text class="eyebrow">04 · 周报 / 月报 / 总结</text><text class="title">教师本人周期报告</text></view>
            <text v-if="periodForm.expectedVersion != null" class="link" @click="resetPeriodForm">取消修改</text>
          </view>
          <picker :range="periodLabels" :value="periodTypeIndex" @change="onPeriodType">
            <view class="field"><text>报告类型</text><text>{{ periodLabels[periodTypeIndex] }} ▾</text></view>
          </picker>
          <text v-if="periodForm.reportType==='SUMMARY'" class="field">实习总结</text><input v-else v-model="periodForm.periodKey" class="input" :placeholder="periodKeyHint" />
          <textarea v-model="periodForm.content" class="textarea" :maxlength="periodMaximum" :placeholder="periodContentHint" />
          <textarea v-model="periodForm.issueContent" class="textarea small" maxlength="4000" placeholder="本周期问题与风险（选填）" />
          <textarea v-model="periodForm.nextPlan" class="textarea small" maxlength="4000" placeholder="下一周期计划（选填）" />
          <input v-model="periodForm.studentCount" class="input" type="number" placeholder="涉及学生人数（选填）" />
          <view class="period-attachments">
            <view class="row-between"><text class="strong">照片 / 附件</text><text class="muted">{{ periodForm.attachments.length }}/9</text></view>
            <view v-for="(file,index) in periodForm.attachments" :key="file.fileId" class="notice-file">
              <text class="notice-file-name" @click="openPeriodAttachment(file)">{{ file.fileName }}</text>
              <text class="notice-remove" @click="removePeriodAttachment(index)">移除</text>
            </view>
            <button v-if="periodForm.attachments.length<9" class="btn btn-ghost" :loading="periodAttachmentUploading" :disabled="periodSaving" @click="addPeriodAttachment">
              {{ periodAttachmentUploading ? '上传中…' : '添加照片 / 附件' }}
            </button>
            <text class="muted">移动端可上传照片或业务附件；保存时与当前周次、月份或总结版本一起留痕。</text>
          </view>
          <button class="btn btn-primary" :loading="periodSaving" :disabled="periodAttachmentUploading" @click="savePeriodReport">保存周期报告</button>
          <view v-if="periodError" class="period-save-error">
            <text>{{ periodError }}</text>
            <button class="btn btn-ghost" :disabled="periodSaving||periodAttachmentUploading" @click="load()">重新读取报告列表</button>
          </view>
          <view v-for="row in periodReports" :key="row.id" class="report">
            <view class="row-between">
              <text class="strong">{{ periodTypeLabel(row.reportType) }} · {{ periodLabel(row.reportType, row.periodKey) }}</text>
              <text class="link" @click="editPeriodReport(row)">编辑</text>
            </view>
            <text class="body">{{ row.content }}</text>
            <text class="muted">第{{ Number(row.version||0)+1 }}版 · {{ formatDateTime(row.submittedAt) }}</text>
          </view>
          <text v-if="!periodReports.length" class="muted">当前批次暂无教师周报、月报或总结</text>
        </view>

        <view class="card g16-card">
          <view><text class="eyebrow">05 · 紧急通知</text><text class="title">批次通知</text></view>
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
            <view class="row-between"><text class="strong">{{ row.title }}</text><MobileStatusTag :type="row.status==='PUBLISHED'?(row.urgency==='URGENT'?'danger':'warning'):'default'" :label="row.status==='PUBLISHED'?noticeUrgencyLabel(row.urgency):'已撤回'" /></view>
            <text class="muted">{{ noticeTypeLabel(row.noticeType) }} · {{ row.senderName }} · {{ formatDateTime(row.publishedAt) }}</text>
            <text v-if="row.validFrom||row.validUntil" class="muted">有效期 {{ noticeDate(row.validFrom) }} 至 {{ noticeDate(row.validUntil) }}</text>
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
          <MobileStatusTag :type="activeNotice.urgency==='URGENT'?'danger':'warning'" :label="noticeUrgencyLabel(activeNotice.urgency)" />
        </view>
        <text class="muted">{{ noticeTypeLabel(activeNotice.noticeType) }} · {{ activeNotice.senderName || '学校' }} · {{ formatDateTime(activeNotice.publishedAt) }}</text>
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
        <MobileInlineAlert v-if="noticeError" type="warning" title="通知操作未完成" :description="noticeError" />
        <button v-if="noticeError" class="btn btn-ghost" @click="load()">重新读取通知</button>
        <button class="btn btn-primary" :loading="acknowledgingNotice" :disabled="acknowledgingNotice || state==='loading'" @click="acknowledgeActiveNotice">我已知悉</button>
      </view>
    </view>
  </view>
</template>

<script>
import teacherApi from '@/services/teacherApi'
import { chooseSingleFile, uploadBusinessFile, openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'
import { reportTypeLabel, reportPeriodLabel, makeupStatusLabel as localizedMakeupStatus } from '@/services/weeklyReportPresentation.mjs'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import { checkinLocationPolicy } from '@/services/checkinPresentation.mjs'

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
const blankPeriod = (type='WEEKLY') => ({ reportType:type, periodKey:defaultPeriodKey(type), content:'', issueContent:'', nextPlan:'', studentCount:'', attachmentFileIds:[], attachments:[], expectedVersion:null })

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
  components: { ReportFilePreview },
  data() { return { hidden:false, loadSequence:0, generation:currentSessionGeneration(), noticeError:'', state:'loading', batches:[], batchId:'', batchIndex:0, checkins:[], checkinRule:null, checkinOverseas:false, checkinCountryRegion:'', makeups:[], reports:[], periodReports:[], periodRules:{}, periodError:'', notices:[], pendingNotices:[], activeNotice:null, acknowledgingNotice:false, checking:false, checkinPhotoFileId:'', checkinPhotoName:'', checkinPhotoUploading:false, checkinNote:'', checkinTimezoneName:this.detectTimezone(), calendarMonth:today().slice(0,7), calendarCheckins:[], calendarState:'idle', calendarError:'', calendarSequence:0, calendarWeekdays:['一','二','三','四','五','六','日'], makeupForm:{localDate:'',reason:'',evidenceFileId:''}, makeupEvidenceName:'', makeupEvidenceUploading:false, makeupSubmitting:false, saving:false, periodSaving:false, periodAttachmentUploading:false, publishing:false, form:blank(), periodForm:blankPeriod(), notice:blankNotice(), noticeUploading:false, noticeWithdrawingId:'' } },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => b.name || ('批次 '+b.id)) },
    periodLabels() { return periodOptions.map((x) => x.label) },
    periodTypeIndex() { return Math.max(0, periodOptions.findIndex((x) => x.code === this.periodForm.reportType)) },
    periodKeyHint() { return this.periodForm.reportType === 'WEEKLY' ? '例如 2026-W39' : (this.periodForm.reportType === 'MONTHLY' ? '例如 2026-09' : '实习总结') },
    periodMaximum() { return this.periodRules[{WEEKLY:'weeklyMaxWords',MONTHLY:'monthlyMaxWords',SUMMARY:'summaryMaxWords'}[this.periodForm.reportType]]||12000 },
    periodContentHint() { return this.periodForm.reportType === 'SUMMARY' ? '实习指导总结（至少300字）' : (this.periodForm.reportType === 'MONTHLY' ? '本月指导工作（至少100字）' : '本周指导工作（至少30字）') },
    noticeTypeLabels() { return noticeTypeOptions.map((x) => x.label) },
    noticeUrgencyLabels() { return noticeUrgencyOptions.map((x) => x.label) },
    noticeTypeIndex() { return Math.max(0, noticeTypeOptions.findIndex((x) => x.code === this.notice.noticeType)) },
    noticeUrgencyIndex() { return Math.max(0, noticeUrgencyOptions.findIndex((x) => x.code === this.notice.urgency)) },
    todayChecked() { return this.checkins.find((x) => x.localDate === today()) || null },
    todayValue() { return today() },
    monthCheckins() {
      const prefix=String(this.calendarMonth||'')
      return (this.calendarCheckins||[]).filter((row)=>String(row.localDate||'').startsWith(prefix)).slice().sort((a,b)=>String(b.localDate||'').localeCompare(String(a.localDate||'')))
    },
    calendarCells() {
      const [year,month]=String(this.calendarMonth||'').split('-').map(Number)
      if(!year||!month||month<1||month>12) return []
      const first=new Date(year,month-1,1)
      const leading=(first.getDay()+6)%7
      const days=new Date(year,month,0).getDate()
      const byDate=new Map((this.calendarCheckins||[]).map((row)=>[String(row.localDate||''),row]))
      const cells=[]
      for(let i=0;i<leading;i+=1) cells.push({key:'blank-before-'+i,day:'',row:null})
      for(let day=1;day<=days;day+=1){
        const dateKey=String(year)+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0')
        cells.push({key:dateKey,day,row:byDate.get(dateKey)||null})
      }
      while(cells.length%7) cells.push({key:'blank-after-'+cells.length,day:'',row:null})
      return cells
    },
    canPublish() { return this.context.can('internship.communication.manage') && /ADMIN/i.test(this.context.roleCode || '') }
  },
  onLoad() { this.load() },
  onShow() {
    const reload=this.hidden || this.generation!==currentSessionGeneration()
    this.hidden=false
    if(reload) this.load()
  },
  onHide() { this.hidden=true; this.loadSequence++; this.acknowledgingNotice=false; this.checking=false; this.checkinPhotoUploading=false; this.$refs?.checkinPreview?.reset() },
  onUnload() { this.hidden=true; this.loadSequence++; this.checking=false; this.checkinPhotoUploading=false; this.$refs?.checkinPreview?.reset() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    formatDateTime,
    readCurrent(sequence,generation,batchId=this.batchId) { return !this.hidden && sequence===this.loadSequence && generation===currentSessionGeneration() && String(batchId)===String(this.batchId) },
    clearAccountContext() {
      this.calendarSequence++; this.calendarCheckins=[]; this.calendarError=''; this.calendarState='idle'
      this.$refs?.checkinPreview?.reset()
      this.batches=[]; this.batchId=''; this.checkins=[]; this.makeups=[]; this.reports=[]; this.periodReports=[]; this.notices=[]
      this.pendingNotices=[]; this.activeNotice=null; this.acknowledgingNotice=false; this.noticeError=''
      this.form=blank(); this.periodForm=blankPeriod(); this.periodRules={}; this.periodError=''; this.periodSaving=false; this.periodAttachmentUploading=false; this.notice=blankNotice()
      this.checkinRule=null; this.checkinOverseas=false; this.checkinCountryRegion=''; this.checkinPhotoFileId=''; this.checkinPhotoName=''; this.checkinNote=''; this.makeupForm={localDate:'',reason:'',evidenceFileId:''}; this.makeupEvidenceName=''
      this.checking=false; this.checkinPhotoUploading=false
      this.generation=currentSessionGeneration()
    },
    async load(done) {
      this.calendarSequence++; this.calendarCheckins=[]; this.calendarState='loading'; this.calendarError=''
      this.$refs?.checkinPreview?.reset()
      this.checkinPhotoUploading=false
      if(this.generation!==currentSessionGeneration()) this.clearAccountContext()
      const sequence=++this.loadSequence,generation=currentSessionGeneration()
      this.state='loading'
      try {
        this.context.restore(); await this.context.load(true)
        if(!this.readCurrent(sequence,generation)) return
        this.batches=this.context.batches||[]; this.batchId=this.context.selectedBatchId||''
        this.batchIndex=Math.max(0,this.batches.findIndex((b)=>String(b.id)===String(this.batchId)))
        if (!this.batchId) { this.state='ready'; return }
        const batchId=this.batchId
        const [a,m,b,p,c,n,rule]=await Promise.all([
          teacherApi.getMyInternshipCheckins(this.batchId,31,today().slice(0,7)),
          teacherApi.getMyInternshipMakeups(this.batchId),
          teacherApi.getMyInternshipWorkReports(this.batchId,1,20),
          teacherApi.getMyInternshipPeriodReports(this.batchId,1,20),
          teacherApi.getInternshipEmergencyNotices(this.batchId,true),
          teacherApi.getPendingInternshipEmergencyNotices(this.batchId),
          teacherApi.getMyInternshipCheckinRule(this.batchId)
        ])
        if(!this.readCurrent(sequence,generation,batchId)) return
        this.checkins=a||[]
        this.checkinRule=rule
        this.makeups=m?.items||[]
        this.reports=b?.items||[]
        this.periodReports=p?.items||[]
        this.periodRules=p?.rules||{}
        this.notices=c||[]
        this.pendingNotices=Array.isArray(n)?n:[]
        this.activeNotice=this.pendingNotices[0]||null
        this.noticeError=''
        this.state='ready'
        if(this.calendarMonth===today().slice(0,7)) { this.calendarCheckins=this.checkins; this.calendarState='ready' }
        else await this.loadCalendar()
      } catch(e) { if(this.readCurrent(sequence,generation)) { this.state='error'; this.noticeError='读取未完成，请重新读取；已有重要通知会保留。'; toast(normalizeError(e).text) } }
      finally { if(typeof done==='function') done() }
    },
    async onBatch(e) {
      this.batchIndex=Number(e.detail.value)||0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId=this.context.selectedBatchId; this.resetForm(); this.resetPeriodForm(); this.notice=blankNotice(); this.pendingNotices=[]; this.activeNotice=null; this.acknowledgingNotice=false; this.checkinRule=null; this.checkinOverseas=false; this.checkinCountryRegion=''; this.checkinPhotoFileId=''; this.checkinPhotoName=''; this.checkinNote=''; this.calendarMonth=today().slice(0,7); this.makeupForm={localDate:'',reason:'',evidenceFileId:''}; this.makeupEvidenceName=''; await this.load()
    },
    async onCalendarMonth(e) {
      this.calendarMonth=e.detail.value
      await this.loadCalendar()
    },
    async loadCalendar() {
      const sequence=++this.calendarSequence, generation=currentSessionGeneration(), batchId=String(this.batchId), month=this.calendarMonth, load=this.loadSequence
      const current=()=>!this.hidden && sequence===this.calendarSequence && month===this.calendarMonth && this.readCurrent(load,generation,batchId)
      this.$refs?.checkinPreview?.reset()
      this.calendarCheckins=[]; this.calendarError=''; this.calendarState='loading'
      if(!this.batchId || !current()) { this.calendarState='idle'; return }
      try {
        const rows=await teacherApi.getMyInternshipCheckins(batchId,31,month)
        if(!current()) return
        if(!Array.isArray(rows)) throw new Error('日历记录未能确认')
        this.calendarCheckins=rows; this.calendarState='ready'
      } catch(e) {
        if(current()) { this.calendarState='error'; this.calendarError='该月签到记录读取失败，请重新读取，不代表没有签到。' }
      }
    },
    detectTimezone() {
      try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai' }
      catch (e) { return 'Asia/Shanghai' }
    },
    checkinResultLabel(value) {
      const map={NORMAL:'正常签到',RECORDED:'仅作留痕',OUT_OF_RANGE:'超出范围待核实',NO_LOCATION:'无定位待核实',LOW_ACCURACY:'定位精度不足',LOCATION_UNCERTAIN:'定位待核实',MOCK_LOCATION:'设备风险待核实',MAKEUP:'补签'}
      return map[String(value||'').toUpperCase()] || '状态待确认'
    },
    checkinResultShort(value) {
      const map={NORMAL:'签',RECORDED:'签',OUT_OF_RANGE:'核',NO_LOCATION:'核',LOW_ACCURACY:'核',LOCATION_UNCERTAIN:'核',MOCK_LOCATION:'核',MAKEUP:'补'}
      return map[String(value||'').toUpperCase()] || '核'
    },
    checkinTone(value) { return ['NORMAL','MAKEUP'].includes(value) ? 'success' : value==='RECORDED' ? 'default' : 'warning' },
    coordinateLabel(value) { return {WGS84:'国际通用坐标',GCJ02:'国内地图坐标'}[value] || '坐标系待确认'
    },
    captureCheckinPhoto() {
      if (this.checkinPhotoUploading || this.checking || this.state!=='ready' || !this.readCurrent(this.loadSequence,this.generation)) return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId
      const current=()=>this.readCurrent(sequence,generation,batchId)
      this.checkinPhotoUploading=true
      uni.chooseImage({
        count:1,
        sourceType:['camera'],
        sizeType:['original'],
        success: async (res) => {
          try {
            const path=(res.tempFilePaths||[])[0]
            const source=(res.tempFiles||[])[0]||{}
            if(!path || !current()) return
            const uploaded=await uploadBusinessFile({
              path,
              name:source.name||`teacher-checkin-${Date.now()}.jpg`,
              size:source.size||0
            }, { bizType:'INTERNSHIP_TEACHER_CHECKIN_PHOTO' })
            if(!current()) return
            if(!uploaded?.fileId) throw new Error('现场照片上传结果不完整')
            this.checkinPhotoFileId=String(uploaded.fileId)
            this.checkinPhotoName=uploaded.fileName||'现场照片已上传'
            toast('原图已上传，签到后由服务器生成可信水印')
          } catch(e) { if(current()) toast(normalizeError(e).text) }
          finally { if(current()) this.checkinPhotoUploading=false }
        },
        fail:()=>{ if(current()) this.checkinPhotoUploading=false }
      })
    },
    async openCheckinEvidence(row, original=false) {
      if(this.state!=='ready' || !this.readCurrent(this.loadSequence,this.generation)) return
      const current=[...this.checkins,...this.calendarCheckins].find(item=>String(item.id)===String(row?.id) && String(item.batchId)===String(this.batchId))
      const fileId=current && (original ? current.photoFileId : current.watermarkedFileId)
      if(!fileId) return
      await this.$refs?.checkinPreview?.open({fileId:String(fileId),fileName:`教师签到-${current.localDate}-${original?'原图':'水印'}.jpg`})
    },
    checkin() {
      if (!this.batchId || this.checking || this.checkinPhotoUploading || this.checkinRule?.canCheckin===false || this.state!=='ready' || !this.readCurrent(this.loadSequence,this.generation)) return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId
      uni.showModal({
        title:'教师本人签到',
        confirmText:'确认签到', cancelText:'取消',
        content:this.checkinPhotoFileId
          ? '将采集一次当前位置，服务端写入教师姓名、服务器时间和位置水印。确认签到？'
          : '将采集一次当前位置并登记本人签到。未拍现场照片时可在定位失败后留痕为“无定位待核实”。确认签到？',
        success:(r)=>{ if(r.confirm && this.readCurrent(sequence,generation,batchId)) this.beginTeacherCheckin() }
      })
    },
    beginTeacherCheckin() {
      if(this.checking || this.checkinRule?.canCheckin===false || this.state!=='ready' || !this.batchId || !this.readCurrent(this.loadSequence,this.generation)) return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=String(this.batchId)
      const current=()=>this.readCurrent(sequence,generation,batchId)
      const locationPolicy=checkinLocationPolicy(this.checkinOverseas)
      const input={batchId,timezoneName:this.checkinTimezoneName,countryRegion:this.checkinCountryRegion.trim()||undefined,note:this.checkinNote.trim()||undefined,photoFileId:this.checkinPhotoFileId||undefined}
      this.checking=true
      const submit=async (loc={})=>{
        if(!current()) return
        try {
          const result=await teacherApi.createMyInternshipCheckin({
            ...input,
            coordinateSystem:loc.latitude!=null?locationPolicy.coordinateSystem:undefined,
            locationProvider:loc.latitude!=null?locationPolicy.locationProvider:undefined,
            ...loc
          })
          if(!current()) return
          this.checkinPhotoFileId=''
          this.checkinPhotoName=''
          this.checkinNote=''
          toast('教师签到已记录：'+this.checkinResultLabel(result?.result)+(result?.evidenceAvailable?'，水印照片已留存':''))
          this.checking=false
          await this.load()
        } catch(e) { if(current()) toast(normalizeError(e).text) }
        finally { if(current()) this.checking=false }
      }
      uni.getLocation({
        type:locationPolicy.type,
        success:(p)=>submit({
          latitude:p.latitude,
          longitude:p.longitude,
          accuracyM:p.accuracy,
          address:p.address||p.name||''
        }),
        fail:()=>{
          if(!current()) return
          if(input.photoFileId){
            this.checking=false
            toast('已拍现场照片时必须取得位置，才能生成带位置的水印')
            return
          }
          submit({})
        }
      })
    },
    makeupStatusLabel(value) {
      return localizedMakeupStatus(value)
    },
    makeupStatusTone(value) {
      return {APPROVED:'success',REJECTED:'danger',PENDING:'warning'}[String(value||'').toUpperCase()] || 'default'
    },
    async pickMakeupEvidence() {
      if(this.makeupEvidenceUploading || this.makeupSubmitting) return
      this.makeupEvidenceUploading=true
      try {
        const file=await chooseSingleFile()
        if(!file) return
        const uploaded=await uploadBusinessFile(file,{bizType:'INTERNSHIP_TEACHER_MAKEUP'})
        if(!uploaded?.fileId) throw new Error('佐证上传结果不完整')
        this.makeupForm.evidenceFileId=String(uploaded.fileId)
        this.makeupEvidenceName=uploaded.fileName||file.name||'补签佐证'
        toast('补签佐证已上传')
      } catch(e) { toast(normalizeError(e).text) }
      finally { this.makeupEvidenceUploading=false }
    },
    async openMakeupEvidence(row) {
      if(!row?.evidenceFileId) return
      try { await openBusinessFile(row.evidenceFileId,row.evidence?.fileName||'教师补签佐证') }
      catch(e) { toast(normalizeError(e).text) }
    },
    async submitMakeup() {
      if(!this.batchId || this.makeupSubmitting || this.makeupEvidenceUploading) return
      if(!this.makeupForm.localDate) return toast('请选择补签日期')
      if((this.makeupForm.reason||'').trim().length<5) return toast('补签原因至少填写5个字')
      this.makeupSubmitting=true
      try {
        await teacherApi.applyMyInternshipMakeup({
          batchId:Number(this.batchId),
          localDate:this.makeupForm.localDate,
          reason:this.makeupForm.reason.trim(),
          evidenceFileId:this.makeupForm.evidenceFileId||undefined
        })
        this.makeupForm={localDate:'',reason:'',evidenceFileId:''}
        this.makeupEvidenceName=''
        toast('补签申请已提交，等待校级管理员审核')
        await this.load()
      } catch(e) { toast(normalizeError(e).text) }
      finally { this.makeupSubmitting=false }
    },
    async withdrawMakeup(row) {
      if(!row?.id || row.status!=='PENDING') return
      try {
        await teacherApi.withdrawMyInternshipMakeup(row.id)
        toast('补签申请已撤回')
        await this.load()
      } catch(e) { toast(normalizeError(e).text) }
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
      } catch(e) { toast(normalizeError(e).text) } finally { this.saving=false }
    },
    periodTypeLabel: reportTypeLabel,
    periodLabel: reportPeriodLabel,
    resetPeriodForm(type='WEEKLY') { this.periodForm=blankPeriod(type); this.periodError='' },
    onPeriodType(e) {
      const type=periodOptions[Number(e.detail.value)||0]?.code||'WEEKLY'
      this.resetPeriodForm(type)
    },
    editPeriodReport(row) {
      this.periodError=''
      const ids=Array.isArray(row.attachmentFileIds)?row.attachmentFileIds.map((value)=>String(value)):[]
      this.periodForm={
        reportType:row.reportType,
        periodKey:row.periodKey,
        content:row.content||'',
        issueContent:row.issueContent||'',
        nextPlan:row.nextPlan||'',
        studentCount:row.studentCount==null?'':String(row.studentCount),
        attachmentFileIds:ids,
        attachments:ids.map((fileId,index)=>({fileId,fileName:'已上传附件 '+(index+1)})),
        expectedVersion:Number(row.version||0)
      }
    },
    async addPeriodAttachment() {
      if(this.periodAttachmentUploading||this.periodSaving||this.periodForm.attachments.length>=9) return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId,form=this.periodForm
      const current=()=>this.readCurrent(sequence,generation,batchId) && this.periodForm===form
      this.periodAttachmentUploading=true
      try {
        const file=await chooseSingleFile()
        if(!file || !current()) return
        const uploaded=await uploadBusinessFile(file,{bizType:'INTERNSHIP_REPORT'})
        if(!current()) return
        if(!uploaded?.fileId) throw new Error('周期报告附件上传结果不完整')
        const fileId=String(uploaded.fileId)
        if(!this.periodForm.attachmentFileIds.includes(fileId)){
          this.periodForm.attachmentFileIds.push(fileId)
          this.periodForm.attachments.push({fileId,fileName:uploaded.fileName||file.name||'周期报告附件'})
        }
        toast('周期报告附件已上传')
      } catch(e) { if(current()) toast(normalizeError(e).text) }
      finally { if(current()) this.periodAttachmentUploading=false }
    },
    removePeriodAttachment(index) {
      if(this.periodAttachmentUploading||this.periodSaving) return
      this.periodForm.attachmentFileIds.splice(index,1)
      this.periodForm.attachments.splice(index,1)
    },
    async openPeriodAttachment(file) {
      if(!file?.fileId) return
      try { await openBusinessFile(file.fileId,file.fileName||'周期报告附件') }
      catch(e) { toast(normalizeError(e).text) }
    },
    async savePeriodReport() {
      if (!this.batchId || this.periodSaving) return
      const min=this.periodForm.reportType==='SUMMARY'?300:(this.periodForm.reportType==='MONTHLY'?100:30)
      if ((this.periodForm.content||'').trim().length<min) return toast(`当前报告至少填写${min}个字`)
      if (Array.from((this.periodForm.content||'').trim()).length>this.periodMaximum) return toast(`当前批次报告最多填写${this.periodMaximum}个字`)
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId,form=this.periodForm
      const current=()=>this.readCurrent(sequence,generation,batchId) && this.periodForm===form
      this.periodSaving=true
      this.periodError=''
      try {
        const body={
          batchId:String(batchId),
          reportType:this.periodForm.reportType,
          periodKey:this.periodForm.periodKey,
          content:this.periodForm.content,
          issueContent:this.periodForm.issueContent,
          nextPlan:this.periodForm.nextPlan,
          attachmentFileIds:[...this.periodForm.attachmentFileIds]
        }
        if(String(this.periodForm.studentCount).trim()) body.studentCount=Number(this.periodForm.studentCount)
        if(this.periodForm.expectedVersion!=null) body.expectedVersion=this.periodForm.expectedVersion
        await teacherApi.saveMyInternshipPeriodReport(body)
        if(!current()) return
        this.periodSaving=false
        toast('教师周期报告已保存')
        this.resetPeriodForm(this.periodForm.reportType)
        await this.load()
      } catch(e) {
        if(current()) {
          this.periodError=e?.biz && e?.bizCode==='DATA_CONFLICT' && Number(e.httpStatus)===400
            ? '这份报告已在其他页面更新，当前输入已保留。请重新读取列表，打开最新报告后核对修改。'
            : normalizeError(e).text
          toast(this.periodError)
        }
      } finally { if(current()) this.periodSaving=false }
    },
    async acknowledgeActiveNotice() {
      const row=this.activeNotice
      if (!row?.id || !this.batchId || this.acknowledgingNotice || this.hidden || this.state==='loading') return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId
      const current=()=>this.readCurrent(sequence,generation,batchId) && this.activeNotice===row
      this.acknowledgingNotice=true
      try {
        await teacherApi.acknowledgeInternshipEmergencyNotice(row.id,batchId)
        if(!current()) return
        this.acknowledgingNotice=false; this.noticeError=''
        this.pendingNotices=this.pendingNotices.filter((item)=>String(item.id)!==String(row.id))
        this.activeNotice=this.pendingNotices[0]||null
        if (!this.activeNotice) toast('重要通知已确认')
      } catch(e) {
        if(current()) { this.noticeError=normalizeError(e).text; toast(this.noticeError) }
      } finally {
        if(current()) this.acknowledgingNotice=false
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
      } catch(e) { toast(normalizeError(e).text) }
      finally { this.noticeUploading=false }
    },
    removeNoticeAttachment(index) {
      if (this.noticeUploading || this.publishing) return
      this.notice.attachmentFileIds.splice(index,1)
      this.notice.attachments.splice(index,1)
    },
    async openNoticeAttachment(file) {
      try { await openBusinessFile(file.fileId, file.fileName || '通知附件') }
      catch(e) { toast(normalizeError(e).text) }
    },
    noticeTypeLabel(value) {
      return noticeTypeOptions.find((x)=>x.code===String(value||'').toUpperCase())?.label || '通知公告'
    },
    noticeUrgencyLabel(value) {
      return noticeUrgencyOptions.find((x)=>x.code===String(value||'').toUpperCase())?.label || '普通'
    },
    noticeDate(value) { return value ? formatDateTime(value).slice(0,10) : '不限' },
    async withdrawNotice(row) {
      if (!row?.id || this.noticeWithdrawingId || row.status !== 'PUBLISHED') return
      this.noticeWithdrawingId=String(row.id)
      try {
        await teacherApi.withdrawInternshipEmergencyNotice(row.id,'发布人主动撤回')
        toast('通知已撤回')
        await this.load()
      } catch(e) { toast(normalizeError(e).text) }
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
          validFrom:this.notice.validFrom ? new Date(this.notice.validFrom + 'T00:00:00').toISOString() : null,
          validUntil:this.notice.validUntil ? new Date(this.notice.validUntil + 'T23:59:59').toISOString() : null,
          attachmentFileIds:this.notice.attachmentFileIds
        })
        this.notice=blankNotice()
        toast('通知已发布')
        await this.load()
      } catch(e) { toast(normalizeError(e).text) }
      finally { this.publishing=false }
    }
  }
}
</script>

<style scoped>
.period-save-error{display:flex;flex-direction:column;gap:8px;color:var(--danger-600);font-size:13px;line-height:1.6}.g16-card{padding:14px;display:flex;flex-direction:column;gap:12px}.danger-link{color:var(--danger-600)}.teacher-checkin-evidence{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px;border:1px solid var(--border-light);border-radius:10px;background:var(--gray-50)}.teacher-calendar{display:flex;flex-direction:column;gap:8px;padding-top:4px}.teacher-calendar-week,.teacher-calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px}.teacher-calendar-week text{text-align:center;font-size:10px;color:var(--text-tertiary)}.teacher-calendar-day{min-height:42px;border:1px solid var(--border-light);border-radius:7px;padding:5px;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;font-size:11px;color:var(--text-tertiary);background:var(--gray-50)}.teacher-calendar-day.has-record{border-color:var(--teacher-300,#93c5fd);background:var(--teacher-50,#eff6ff);color:var(--text-primary)}.teacher-calendar-mark{font-size:9px;color:var(--teacher-700);font-weight:700}.period-attachments{display:flex;flex-direction:column;gap:7px;padding:10px;border:1px solid var(--border-light);border-radius:10px;background:var(--gray-50)}.notice-dates{display:grid;grid-template-columns:1fr 1fr;gap:8px}.notice-attachments{display:flex;flex-direction:column;gap:7px}.notice-file{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border-radius:8px;background:var(--gray-50);font-size:12px}.notice-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--teacher-700)}.notice-remove{flex:0 0 auto;color:var(--danger-600)}.g16-batch{flex-direction:row;align-items:center;justify-content:space-between}.eyebrow,.muted{display:block;font-size:11px;color:var(--text-tertiary);line-height:1.6}.eyebrow{color:var(--teacher-700);font-weight:700}.title{display:block;font-size:17px;font-weight:700}.strong{font-weight:600}.link{font-size:12px;color:var(--teacher-700)}.list-row,.field{display:flex;justify-content:space-between;padding:10px;border-top:1px solid var(--border-light);font-size:12px}.field{border:1px solid var(--border-light);border-radius:8px}.input,.textarea{width:100%;box-sizing:border-box;border:1px solid var(--border-light);border-radius:8px;padding:10px;font-size:13px}.textarea{height:120px}.textarea.small{height:80px}.report{display:flex;flex-direction:column;gap:6px;padding:10px;border-radius:8px;background:var(--gray-50)}.body{font-size:13px;line-height:1.65;white-space:pre-wrap}.notice-form{display:flex;flex-direction:column;gap:8px}
.g16-notice-mask{position:fixed;z-index:9999;inset:0;background:rgba(15,23,42,.68);display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box}.g16-notice-dialog{width:100%;max-width:560px;max-height:82vh;background:var(--bg-card);border-radius:16px;padding:18px;box-sizing:border-box;display:flex;flex-direction:column;gap:12px}.g16-notice-body{max-height:42vh;padding:12px;border:1px solid var(--border-light);border-radius:10px;background:var(--gray-50);box-sizing:border-box}
</style>
