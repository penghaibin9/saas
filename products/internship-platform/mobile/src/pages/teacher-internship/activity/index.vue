<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-activity">
    <MobileNavBar variant="teacher" title="我的实习工作" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view class="activity-sections" role="group" aria-label="选择本人工作事项"><button v-for="section in [{key:'checkin',label:'签到与补签'},{key:'work',label:'工作记录'},{key:'period',label:'周期报告'},{key:'notices',label:'批次通知'}]" :key="section.key" class="mobile-control" :class="{'is-on':activeSection === section.key}" :aria-pressed="activeSection === section.key" @click="activeSection=section.key">{{ section.label }}</button></view>
        <view v-if="batches.length" class="g16-card g16-batch">
          <text class="title">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          <picker class="mobile-picker" v-if="batches.length > 1" :range="batchLabels" :value="batchIndex" @change="onBatch"><text class="link">切换批次</text></picker>
        </view>

        <view v-show="activeSection === 'checkin'" class="card g16-card">
          <view class="row-between">
            <view><text class="eyebrow">本人签到</text><text class="title">{{ todayChecked ? (checkinTone(todayChecked.result)==='warning' ? '今天已记录，待核实' : '今天已签到') : '今天未签到' }}</text></view>
            <MobileStatusTag :type="todayChecked ? checkinTone(todayChecked.result) : 'warning'" :label="todayChecked ? checkinResultLabel(todayChecked.result) : '待完成'" />
          </view>
          <text v-if="todayChecked" class="muted">签到当地时间：{{ todayChecked.localCheckedInAt || '待核实' }} · {{ checkinResultLabel(todayChecked.result) }}</text>
          <text v-if="todayChecked?.countryRegion" class="muted">国家或地区：{{ todayChecked.countryRegion }}</text>
          <text v-if="todayChecked?.accuracyM != null" class="muted">定位精度约 {{ Math.round(todayChecked.accuracyM) }} 米</text>
          <text v-if="todayChecked?.distanceM != null" class="muted">距允许地点中心约 {{ Math.round(todayChecked.distanceM) }} 米</text>
          <text v-if="todayChecked && !todayChecked.address" class="muted">未取得地址，定位待核实。</text>
          <text class="muted">{{ checkinRule?.configured ? '请在学校允许的签到地点如实签到。' : '学校尚未配置签到范围，本次记录需核实，不会判为正常签到。' }}</text>
          <text v-if="checkinRule?.canCheckin===false" class="muted">{{ checkinRule.unavailableReason }}</text>
          <view v-if="!todayChecked" class="teacher-location-policy">
            <view class="row-between"><text>境外签到</text><switch :checked="checkinOverseas" :disabled="checking" @change="checkinOverseas=$event.detail.value" /></view>
            <input v-if="checkinOverseas" v-model.trim="checkinCountryRegion" class="mobile-input field" maxlength="100" placeholder="国家或地区（选填）" :disabled="checking" />
            <text class="muted">境外定位与学校范围无法匹配时，需学校核实。</text>
          </view>
          <view v-if="todayChecked?.photoFileId || todayChecked?.watermarkedFileId" class="row-between">
            <text v-if="todayChecked?.photoFileId" class="link" @click="openCheckinEvidence(todayChecked, true)">查看现场原图</text>
            <text v-if="todayChecked?.watermarkedFileId" class="link" @click="openCheckinEvidence(todayChecked)">查看水印照片</text>
          </view>
          <text v-if="todayChecked?.note" class="muted">签到备注：{{ todayChecked.note }}</text>
          <textarea v-if="!todayChecked" v-model.trim="checkinNote" class="mobile-textarea textarea small" maxlength="500" placeholder="签到备注（选填，例如：企业现场巡访、学生集中指导）" />
          <view v-if="!todayChecked" class="teacher-checkin-evidence">
            <view>
              <text class="strong">现场照片（建议）</text>
              <text class="muted">{{ checkinPhotoName || '请现场拍摄；照片将标注姓名、时间和位置。' }}</text>
            </view>
            <button class="mobile-control btn btn-ghost" :disabled="checkinPhotoUploading || checking" @click="captureCheckinPhoto">
              {{ checkinPhotoUploading ? '上传中…' : (checkinPhotoFileId ? '重新拍摄' : '现场拍照') }}
            </button>
          </view>
          <button v-if="!todayChecked" class="mobile-control btn btn-primary" :loading="checking" :disabled="checkinPhotoUploading || checkinRule?.canCheckin===false" @click="checkin">本人签到</button>
          <view class="teacher-calendar">
            <view class="row-between">
              <button class="mobile-control link g16-toggle" :aria-expanded="calendarExpanded" @click="calendarExpanded=!calendarExpanded">{{ calendarExpanded ? '收起签到日历' : '签到日历' }}</button>
              <picker class="mobile-picker" v-show="calendarExpanded" mode="date" fields="month" :value="calendarMonth" @change="onCalendarMonth">
                <text class="link">{{ calendarMonth }} ▾</text>
              </picker>
            </view>
            <view v-show="calendarExpanded">
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
          </view>
          <ReportFilePreview ref="checkinPreview" />
        </view>

        <view v-show="activeSection === 'checkin'" class="card g16-card">
          <view class="row-between">
            <text class="title">补签申请</text>
            <button class="mobile-control link g16-toggle" :aria-expanded="makeupExpanded" @click="makeupExpanded=!makeupExpanded">{{ makeupExpanded ? '收起' : '展开' }}</button>
          </view>
          <view v-show="makeupExpanded" class="stack">
          <MobileInlineAlert type="info" description="请说明补签原因，学校审核通过后补签生效。" />
          <picker class="mobile-picker" mode="date" :value="makeupForm.localDate" :end="todayValue" @change="makeupForm.localDate=$event.detail.value">
            <view class="field"><text>补签日期</text><text>{{ makeupForm.localDate || '请选择' }} ▾</text></view>
          </picker>
          <textarea v-model="makeupForm.reason" class="mobile-textarea textarea small" maxlength="500" placeholder="补签原因（至少5字）" />
          <view class="teacher-checkin-evidence">
            <view>
              <text class="strong">佐证材料（选填）</text>
              <text class="muted">{{ makeupEvidenceName || '可上传图片、PDF、Word 等正式佐证文件' }}</text>
            </view>
            <button class="mobile-control btn btn-ghost" :disabled="makeupEvidenceUploading || makeupSubmitting" @click="pickMakeupEvidence">
              {{ makeupEvidenceUploading ? '上传中…' : (makeupForm.evidenceFileId ? '更换佐证' : '上传佐证') }}
            </button>
          </view>
          <button class="mobile-control btn btn-primary" :loading="makeupSubmitting" :disabled="makeupEvidenceUploading" @click="submitMakeup">提交补签申请</button>
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
        </view>

        <view v-show="activeSection === 'work'" class="card g16-card">
          <view class="row-between">
            <text class="title">工作报告</text>
            <text v-if="form.expectedVersion != null" class="link" @click="resetForm">取消修改</text>
          </view>
          <picker class="mobile-picker" mode="date" :value="form.reportDate" @change="form.reportDate=$event.detail.value">
            <view class="field"><text>报告日期</text><text>{{ form.reportDate }} ▾</text></view>
          </picker>
          <textarea v-model="form.workContent" class="mobile-textarea textarea" maxlength="8000" placeholder="今天完成了哪些实习指导工作（至少10字）" />
          <textarea v-model="form.issueContent" class="mobile-textarea textarea small" maxlength="4000" placeholder="发现的问题（选填）" />
          <textarea v-model="form.nextPlan" class="mobile-textarea textarea small" maxlength="4000" placeholder="下一步计划（选填）" />
          <input v-model="form.studentCount" class="mobile-input input" type="number" placeholder="涉及学生人数（选填）" />
          <button class="mobile-control btn btn-primary" :loading="saving" @click="saveReport">保存工作报告</button>
          <view v-for="row in reports" :key="row.id" class="report">
            <view class="row-between"><text class="strong">{{ row.reportDate }}</text><text class="link" @click="editReport(row)">编辑</text></view>
            <text class="body">{{ row.workContent }}</text>
            <text class="muted">版本 {{ row.version }}</text>
          </view>
        </view>

        <view v-show="activeSection === 'period'" class="card g16-card">
          <view class="row-between">
            <view><text class="title">本人周期报告</text></view>
            <text v-if="canManagePeriodReports && periodForm.expectedVersion != null && !periodBusy" class="link" @click="resetPeriodForm(periodForm.reportType)">取消修改</text>
          </view>
          <text v-if="!batchId" class="muted">当前身份没有可用实习批次，暂不能填写或保存报告，请联系学校核对批次安排。</text>
          <text v-else-if="!canManagePeriodReports" class="muted">当前身份仅可查看本人报告，填写和修改需要指导维护权限。</text>
          <picker class="mobile-picker" :range="periodLabels" :value="periodTypeIndex" :disabled="!batchId || !canManagePeriodReports || periodBusy" @change="onPeriodType">
            <view class="field"><text>报告类型</text><text>{{ periodLabels[periodTypeIndex] }} ▾</text></view>
          </picker>
          <text v-if="periodForm.reportType==='SUMMARY'" class="field">实习总结</text><input v-else v-model="periodForm.periodKey" :disabled="!batchId || !canManagePeriodReports || periodBusy" class="mobile-input input" :placeholder="periodKeyHint" />
          <textarea v-model="periodForm.content" :disabled="!batchId || !canManagePeriodReports || periodBusy" class="mobile-textarea textarea" :maxlength="periodMaximum" :placeholder="periodContentHint" />
          <textarea v-model="periodForm.issueContent" :disabled="!batchId || !canManagePeriodReports || periodBusy" class="mobile-textarea textarea small" maxlength="4000" placeholder="本周期问题与风险（选填）" />
          <textarea v-model="periodForm.nextPlan" :disabled="!batchId || !canManagePeriodReports || periodBusy" class="mobile-textarea textarea small" maxlength="4000" placeholder="下一周期计划（选填）" />
          <input v-model="periodForm.studentCount" :disabled="!batchId || !canManagePeriodReports || periodBusy" class="mobile-input input" type="number" placeholder="涉及学生人数（选填）" />
          <view class="period-attachments">
            <view class="row-between"><text class="strong">照片 / 附件</text><text class="muted">{{ periodForm.attachments.length }}/9</text></view>
            <view v-for="(file,index) in periodForm.attachments" :key="file.fileId" class="notice-file">
              <text class="notice-file-name" @click="openPeriodAttachment(file)">{{ file.fileName }}</text>
              <text>{{ file.statusText || '文件状态待确认' }}</text>
              <text v-if="canManagePeriodReports && batchId && !periodBusy" class="notice-remove" @click="removePeriodAttachment(index)">移除</text>
            </view>
            <button v-if="canManagePeriodReports && periodForm.attachments.length<9" class="mobile-control btn btn-ghost" :loading="periodAttachmentUploading" :disabled="!batchId || periodBusy" @click="addPeriodAttachment">
              {{ periodAttachmentUploading ? '上传中…' : '添加照片 / 附件' }}
            </button>
            <button v-if="periodForm.attachments.length" class="mobile-control btn btn-ghost" :disabled="periodBusy" @click="refreshPeriodAttachments">{{ periodScanning ? '正在读取扫描结果…' : '刷新附件安全状态' }}</button>
            <text v-if="!periodAttachmentsReady" class="muted">附件尚未全部安全可用，请刷新安全状态后再保存；正文和附件会保留。</text>
          </view>
          <button v-if="canManagePeriodReports" class="mobile-control btn btn-primary" :loading="periodSaving" :disabled="!batchId || periodBusy || !periodAttachmentsReady" @click="savePeriodReport">保存周期报告</button>
          <view v-if="periodError" class="period-save-error">
            <text>{{ periodError }}</text>
            <button class="mobile-control btn btn-ghost" :disabled="periodBusy" @click="loadPeriodReports(periodPage)">重新读取报告列表</button>
          </view>
          <view v-for="row in periodReports" :key="row.id" class="report">
            <view class="row-between">
              <text class="strong">{{ periodTypeLabel(row.reportType) }} · {{ periodLabel(row.reportType, row.periodKey) }}</text>
              <text class="link" @click="editPeriodReport(row)">{{ canManagePeriodReports ? '编辑' : '查看' }}</text>
            </view>
            <text class="body">{{ row.content }}</text>
            <text class="muted">第{{ Number(row.version||0)+1 }}版 · {{ formatDateTime(row.submittedAt) }}</text>
          </view>
          <text v-if="!periodReports.length" class="muted">当前批次暂无教师周报、月报或总结</text>
          <view v-if="periodListError" class="period-save-error"><text>{{ periodListError }}</text><button class="mobile-control" :disabled="periodBusy || periodLoading" @click="loadPeriodReports(periodRequestedPage)">重试读取报告</button></view>
          <view v-if="periodTotal > 0 || periodLoading" class="row-between">
            <button class="mobile-control" :disabled="periodBusy || periodLoading || periodPage<=1" @click="loadPeriodReports(periodPage-1)">上一页报告</button>
            <text>{{ periodLoading ? '正在读取…' : '第'+periodPage+'页 · 共'+periodTotal+'份' }}</text>
            <button class="mobile-control" :disabled="periodBusy || periodLoading || periodPage*20>=periodTotal" @click="loadPeriodReports(periodPage+1)">下一页报告</button>
          </view>
        </view>

        <view v-show="activeSection === 'notices'" class="card g16-card">
          <text class="title">批次通知</text>
          <view v-if="canPublish" class="notice-form">
            <picker class="mobile-picker" :range="noticeTypeLabels" :value="noticeTypeIndex" @change="onNoticeType">
              <view class="field"><text>公告类型</text><text>{{ noticeTypeLabels[noticeTypeIndex] }} ▾</text></view>
            </picker>
            <picker class="mobile-picker" :range="noticeUrgencyLabels" :value="noticeUrgencyIndex" @change="onNoticeUrgency">
              <view class="field"><text>紧急程度</text><text>{{ noticeUrgencyLabels[noticeUrgencyIndex] }} ▾</text></view>
            </picker>
            <input v-model="notice.title" class="mobile-input input" maxlength="200" placeholder="通知标题" />
            <textarea v-model="notice.content" class="mobile-textarea textarea small" maxlength="5000" placeholder="通知正文" />
            <view class="notice-dates">
              <picker class="mobile-picker" mode="date" :value="notice.validFrom" @change="notice.validFrom=$event.detail.value">
                <view class="field"><text>有效期开始</text><text>{{ notice.validFrom || '不限' }} ▾</text></view>
              </picker>
              <picker class="mobile-picker" mode="date" :value="notice.validUntil" @change="notice.validUntil=$event.detail.value">
                <view class="field"><text>有效期结束</text><text>{{ notice.validUntil || '不限' }} ▾</text></view>
              </picker>
            </view>
            <view class="notice-attachments">
              <view class="row-between"><text class="strong">附件</text><text class="muted">{{ notice.attachments.length }}/9</text></view>
              <view v-for="(file,index) in notice.attachments" :key="file.fileId" class="notice-file">
                <text class="notice-file-name" @click="openNoticeAttachment(file)">{{ file.fileName }}</text>
                <text class="notice-remove" @click="removeNoticeAttachment(index)">移除</text>
              </view>
              <button v-if="notice.attachments.length<9" class="mobile-control btn btn-ghost" :loading="noticeUploading" :disabled="publishing" @click="addNoticeAttachment">添加附件</button>
            </view>
            <MobileInlineAlert v-if="notice.urgency!=='NORMAL'" type="warning" description="重要/紧急通知会在学生端强制弹框，学生点击“我已知悉”后才记录确认回执。" />
            <button class="mobile-control btn btn-danger" :loading="publishing" :disabled="noticeUploading" @click="publishNotice">校级发布</button>
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
            <button v-if="canPublish && row.status==='PUBLISHED'" class="mobile-control btn btn-ghost" :loading="noticeWithdrawingId===String(row.id)" @click="withdrawNotice(row)">撤回通知</button>
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
        <MobileInlineAlert type="warning" description="请阅读通知后点击“我已知悉”。" />
        <MobileInlineAlert v-if="noticeError" type="warning" title="通知操作未完成" :description="noticeError" />
        <button v-if="noticeError" class="mobile-control btn btn-ghost" @click="load()">重新读取通知</button>
        <button class="mobile-control btn btn-primary" :loading="acknowledgingNotice" :disabled="acknowledgingNotice || state==='loading'" @click="acknowledgeActiveNotice">我已知悉</button>
      </view>
    </view>
  </view>
</template>

<script>
import teacherApi from '@/services/teacherApi'
import { chooseSingleFile, uploadBusinessFile, openBusinessFile, fileSdk } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { currentMobileSession } from '@/services/mobileAuth'
import { formatDateTime } from '@/utils/format'
import { reportTypeLabel, reportPeriodLabel, makeupStatusLabel as localizedMakeupStatus, reportFileState, reportFilesReady, refreshReportFiles } from '@/services/weeklyReportPresentation.mjs'
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
  data() { return { requestedBatchId:'', activeSection:'checkin', calendarExpanded:false, makeupExpanded:false, periodPage:1, periodRequestedPage:1, periodTotal:0, periodLoading:false, periodListError:'', periodListSequence:0, periodScanning:false, hidden:false, loadSequence:0, generation:currentSessionGeneration(), noticeError:'', state:'loading', batches:[], batchId:'', batchIndex:0, checkins:[], checkinRule:null, checkinOverseas:false, checkinCountryRegion:'', makeups:[], reports:[], periodReports:[], periodRules:{}, periodError:'', notices:[], pendingNotices:[], activeNotice:null, acknowledgingNotice:false, checking:false, checkinPhotoFileId:'', checkinPhotoName:'', checkinPhotoUploading:false, checkinNote:'', checkinTimezoneName:this.detectTimezone(), calendarMonth:today().slice(0,7), calendarCheckins:[], calendarState:'idle', calendarError:'', calendarSequence:0, calendarWeekdays:['一','二','三','四','五','六','日'], makeupForm:{localDate:'',reason:'',evidenceFileId:''}, makeupEvidenceName:'', makeupEvidenceUploading:false, makeupSubmitting:false, saving:false, periodSaving:false, periodAttachmentUploading:false, publishing:false, form:blank(), periodForm:blankPeriod(), notice:blankNotice(), noticeUploading:false, noticeWithdrawingId:'' } },
  computed: {
    canManagePeriodReports() { return this.context.can('internship.guidance.manage') },
    periodBusy() { return this.periodSaving || this.periodAttachmentUploading || this.periodScanning },
    periodAttachmentsReady() { return reportFilesReady(this.periodForm.attachments) },
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
  onLoad(query = {}) { this.requestedBatchId = String(query.batchId || ''); this.load() },
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
      this.activeSection='checkin'
      this.periodListSequence++; this.periodPage=1; this.periodRequestedPage=1; this.periodTotal=0; this.periodLoading=false; this.periodListError=''; this.periodScanning=false
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
      this.periodListSequence++; this.periodLoading=false; this.periodListError=''; this.periodScanning=false; this.periodAttachmentUploading=false
      this.calendarSequence++; this.calendarCheckins=[]; this.calendarState='loading'; this.calendarError=''
      this.$refs?.checkinPreview?.reset()
      this.checkinPhotoUploading=false
      if(this.generation!==currentSessionGeneration()) this.clearAccountContext()
      const sequence=++this.loadSequence,generation=currentSessionGeneration()
      this.state='loading'
      try {
        this.context.restore(); await this.context.load(true)
        if(!this.readCurrent(sequence,generation)) return
        if (this.requestedBatchId) {
          if (!this.context.selectBatch(this.requestedBatchId)) throw { httpStatus: 403, message: '当前批次不在授权范围' }
          this.requestedBatchId = ''
        }
        this.batches=this.context.batches||[]; this.batchId=this.context.selectedBatchId||''
        this.batchIndex=Math.max(0,this.batches.findIndex((b)=>String(b.id)===String(this.batchId)))
        if (!this.batchId) { this.state='ready'; return }
        this.periodPage=this.restorePeriodPage()
        const batchId=this.batchId
        const [a,m,b,p,c,n,rule]=await Promise.all([
          teacherApi.getMyInternshipCheckins(this.batchId,31,today().slice(0,7)),
          teacherApi.getMyInternshipMakeups(this.batchId),
          teacherApi.getMyInternshipWorkReports(this.batchId,1,20),
          teacherApi.getMyInternshipPeriodReports(this.batchId,this.periodPage,20),
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
        this.periodTotal=p?.total||0
        this.persistPeriodPage()
        this.periodRules=p?.rules||{}
        this.notices=c||[]
        this.pendingNotices=Array.isArray(n)?n:[]
        this.activeNotice=this.pendingNotices[0]||null
        this.noticeError=''
        this.state='ready'
        if(this.calendarMonth===today().slice(0,7)) { this.calendarCheckins=this.checkins; this.calendarState='ready' }
        else await this.loadCalendar()
      } catch(e) { if(this.readCurrent(sequence,generation)) { const error=normalizeError(e);this.state=error.pageState || 'error'; this.noticeError='读取未完成，请重新读取；已有重要通知会保留。'; toast(error.text) } }
      finally { if(typeof done==='function') done() }
    },
    async onBatch(e) {
      this.periodPage=1; this.periodTotal=0; this.periodReports=[]
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
    periodPageScope(session) {
      const identity=session.identity||{}
      if(!session.logged || !session.isTeacher || !identity.tenantId || !identity.userId || !identity.roleCode || !this.batchId) return ''
      return JSON.stringify([String(identity.tenantId),String(identity.userId),identity.roleCode,identity.activeContextId||'',String(this.batchId)])
    },
    restorePeriodPage() {
      const session=currentMobileSession(),scope=this.periodPageScope(session),saved=session.teacherPeriodReportPage
      return scope && saved?.scope===scope && Number.isSafeInteger(saved.page) && saved.page>=1 && Number.isSafeInteger(saved.total) && saved.total>=0 && saved.page<=Math.max(1,Math.ceil(saved.total/20)) ? saved.page : 1
    },
    persistPeriodPage() {
      const session=currentMobileSession(),scope=this.periodPageScope(session)
      if(!scope || this.generation!==currentSessionGeneration()) return
      try {
        session.teacherPeriodReportPage={scope,page:this.periodPage,total:this.periodTotal}
        uni.setStorageSync('gx_session_v1',session)
      } catch {}
    },
    async loadPeriodReports(page=this.periodPage) {
      if (!this.batchId || this.periodBusy || this.periodLoading || this.state!=='ready' || !this.readCurrent(this.loadSequence,this.generation) || !this.context.can('internship.guidance.view')) return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId,request=++this.periodListSequence
      const current=()=>request===this.periodListSequence && this.readCurrent(sequence,generation,batchId)
      this.periodLoading=true; this.periodListError=''; this.periodRequestedPage=page
      try {
        const result=await teacherApi.getMyInternshipPeriodReports(batchId,page,20)
        if(!current()) return
        if(!Array.isArray(result?.items)||!Number.isInteger(result.total)||result.total<0||result.page!==page) throw Error('invalid report page')
        this.periodReports=result.items; this.periodPage=page; this.periodTotal=result.total; this.periodRules=result.rules||{}
        this.persistPeriodPage()
      } catch(e) { if(current()) this.periodListError='报告列表读取失败，当前页和填写内容已保留，请重试。' }
      finally { if(current()) this.periodLoading=false }
    },
    async refreshPeriodAttachments() {
      if (this.periodBusy || this.hidden || !this.context.can('internship.guidance.view')) return
      const sequence=this.loadSequence,generation=currentSessionGeneration(),batchId=this.batchId,form=this.periodForm,files=form.attachments
      const current=()=>this.readCurrent(sequence,generation,batchId) && this.periodForm===form && form.attachments===files
      this.periodScanning=true; this.periodError=''
      try {
        const updated=await refreshReportFiles(files,id=>fileSdk.metadata(id),current)
        if(updated) form.attachments=updated
      } catch(e) { if(current()) this.periodError='附件安全状态读取失败，正文和附件已保留，请重试。' }
      finally { if(this.readCurrent(sequence,generation,batchId) && this.periodForm===form) this.periodScanning=false }
    },
    resetPeriodForm(type='WEEKLY') { this.periodForm=blankPeriod(type); this.periodError='' },
    onPeriodType(e) {
      if (!this.batchId || !this.canManagePeriodReports || this.periodBusy) return
      const type=periodOptions[Number(e.detail.value)||0]?.code||'WEEKLY'
      this.resetPeriodForm(type)
    },
    editPeriodReport(row) {
      if (this.periodBusy || !this.context.can('internship.guidance.view')) return
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
        attachments:ids.map((fileId,index)=>reportFileState({fileId,fileName:'已上传附件 '+(index+1),...(row.attachments||[]).find(file=>String(file.fileId)===fileId)})),
        expectedVersion:Number(row.version||0)
      }
    },
    async addPeriodAttachment() {
      if(!this.batchId || !this.canManagePeriodReports || this.periodBusy || this.hidden || this.state!=='ready' || this.periodForm.attachments.length>=9) return
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
          this.periodForm.attachments.push(reportFileState({...uploaded,fileId,fileName:uploaded.fileName||file.name||'周期报告附件'}))
        }
        toast(this.periodAttachmentsReady ? '周期报告附件安全可用' : '附件已上传，等待安全扫描；正文已保留')
      } catch(e) { if(current()) toast(normalizeError(e).text) }
      finally { if(current()) this.periodAttachmentUploading=false }
    },
    removePeriodAttachment(index) {
      if(!this.batchId || !this.canManagePeriodReports || this.periodBusy || this.hidden) return
      this.periodForm.attachmentFileIds.splice(index,1)
      this.periodForm.attachments.splice(index,1)
    },
    async openPeriodAttachment(file) {
      if(!file?.fileId) return
      if(!file.readyForBusiness) return toast('附件尚未安全可用，请刷新安全状态')
      try { await openBusinessFile(file.fileId,file.fileName||'周期报告附件') }
      catch(e) { toast(normalizeError(e).text) }
    },
    async savePeriodReport() {
      if (!this.canManagePeriodReports || !this.batchId || this.periodBusy || this.hidden || this.state!=='ready' || !this.readCurrent(this.loadSequence,this.generation)) return
      if (!this.periodAttachmentsReady) { this.periodError='附件尚未全部安全可用，请刷新安全状态；正文和附件已保留。'; return }
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
.teacher-activity :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-activity .card{border-radius:8px;box-shadow:none}.teacher-activity .title{font-size:16px;line-height:24px}.teacher-activity .muted,.teacher-activity .eyebrow,.teacher-activity .body,.teacher-activity .link,.teacher-activity .field,.teacher-activity .notice-file{font-size:14px;line-height:22px}.teacher-activity button,.teacher-activity .input,.teacher-activity .field{min-height:44px;font-size:15px;box-sizing:border-box}.teacher-activity .input{height:44px}.teacher-activity .textarea{font-size:15px;line-height:22px}.teacher-activity .link{display:inline-flex;align-items:center;min-height:44px}.teacher-activity .g16-toggle{margin:0;padding:0 8px;border:0;background:transparent;line-height:44px}.g16-toggle::after{border:0}.teacher-activity .g16-batch{padding:4px 0 12px;border-bottom:1px solid var(--border-light)}.teacher-activity .g16-batch .title{min-width:0;overflow-wrap:anywhere}.teacher-activity .g16-batch picker{flex-shrink:0}
.activity-sections{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.activity-sections>button{margin:0;padding:8px;line-height:1.6;border:1px solid var(--border-base);background:var(--bg-card);font-size:15px;color:var(--text-secondary)}.activity-sections>button.is-on{border-color:var(--teacher-600);background:var(--teacher-50);color:var(--teacher-700)}.teacher-checkin-evidence{flex-wrap:wrap}.teacher-checkin-evidence>.btn{flex-shrink:0;min-width:100px;line-height:1.5}
</style>
