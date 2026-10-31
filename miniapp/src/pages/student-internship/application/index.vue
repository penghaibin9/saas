<template>
  <view class="internship-surface mobile-page mobile-student page-wrap app">
    <MobileNavBar title="实习申请" show-back :fallback-url="applicationReturnUrl" />
    <MobilePrivacyGate />
    <MobileInlineAlert v-if="loadError" type="warning" title="申请或岗位读取失败" :description="loadError" />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="historyMode" type="info" description="历史实习申请仅供查阅。" />
        <view v-if="conflict" class="card stack">
          <MobileInlineAlert type="warning" title="申请已变化，填写内容已保留" :description="conflict.error" />
          <button class="mobile-control btn btn-ghost" :disabled="conflictReading" @click="rereadConflict">读取最新原单</button>
          <template v-if="conflict.latest">
            <text>最新原单：第{{ conflict.latest.version }}版 · {{ conflict.latest.statusLabel || '请核对申请状态' }}</text>
            <text>{{ conflict.latest.companyName || conflict.latest.positionName || '学校岗位申请' }}</text>
            <text>{{ conflict.latest.applicationNote || '未填写申请说明' }}</text>
            <text>{{ conflict.latest.reviewComment || '' }}</text>
            <button class="mobile-control btn btn-ghost" :disabled="conflictReading" @click="adoptLatestApplication">已核对原单，保留填写内容继续</button>
            <button v-if="conflict.positionsMore" class="mobile-control btn btn-ghost" :disabled="positionsLoading" @click="loadMorePositions">继续核对后续岗位</button>
          </template>
        </view>

        <view v-if="showApplicationResult" class="card stack app__result">
          <view class="row-between app__result-head">
            <text class="card-title">{{ displayApplication ? '原申请及办理结果' : '暂无申请记录' }}</text>
            <MobileStatusTag v-if="displayApplication" :status="displayApplication.status" :label="displayApplication.statusLabel || applicationStatusLabel(displayApplication.status)" />
          </view>
          <template v-if="displayApplication">
            <text class="app__version">申请 {{ displayApplication.id }} · 第{{ displayApplication.version }}版</text>
            <view class="app__summary"><view v-for="item in applicationSummaryItems" :key="item.label" class="app__summary-row"><text class="app__label">{{ item.label }}</text><text class="app__value">{{ item.value }}</text></view></view>
            <MobileInlineAlert v-if="displayApplication.reviewComment || displayApplication.status === 'REJECTED'" :type="displayApplication.status === 'REJECTED' ? 'warning' : 'info'" :title="displayApplication.status === 'REJECTED' ? '退回原因' : '审核意见'" :description="displayApplication.reviewComment || '请修改后重新提交。'" />
            <button v-if="displayApplication.status === 'PENDING_REVIEW' && recordAllowsApplication" class="mobile-control btn btn-ghost" :disabled="submitting" @click="withdraw(displayApplication)">撤回申请</button>
          </template>
          <text v-if="!canWriteApplication && !historyMode" class="app__hint">{{ readOnlyNextStep }}</text><view v-if="!canWriteApplication && !historyMode && destinationType !== 'EXEMPTED' && (['ASSIGNED','SELF_ARRANGED'].includes(destinationType) || displayApplication?.status === 'APPROVED')" class="stack"><button class="mobile-control btn btn-primary" @click="continuePlacement('/pages/student-internship/agreement/index')">继续办理三方协议</button><button class="mobile-control btn btn-ghost" @click="continuePlacement('/pages/student-internship/insurance/index')">查看与办理实习保险</button></view>
          <template v-if="!canWriteApplication">
          <template v-if="displayApplication">
            <button class="mobile-control app__details-toggle" :aria-expanded="applicationDetailsExpanded" @click="expandedApplicationScope = applicationDetailsExpanded ? '' : applicationFileScope">{{ applicationDetailsExpanded ? '收起申请详情' : '申请详情' }} <text>{{ applicationDetailsExpanded ? '▴' : '▾' }}</text></button>
            <view v-if="applicationDetailsExpanded" class="app__details"><view v-for="item in applicationDetailItems" :key="item.label" class="app__field"><text class="app__label">{{ item.label }}</text><text class="app__value">{{ item.value }}</text></view></view>
          </template>
          <text v-if="applicationMaterials.length" class="app__section-title">申请材料</text>
          <view v-for="file in applicationMaterials" :key="file.fileId" class="app__file">
            <text class="flex-1">{{ file.fileName }}</text>
            <button class="mobile-control btn btn-ghost" :disabled="materialOpening" @click="openApplicationMaterial(file.fileId)">查看材料</button>
          </view>
          <text v-if="materialError" class="app__hint">{{ materialError }}</text>
          <ReportFilePreview ref="applicationMaterialPreview" :key="applicationFileScope" />
          </template>
        </view>
        <view v-if="canWriteApplication" class="card stack">
          <view class="app__field">
            <text class="app__label">申请类型</text>
            <picker class="mobile-picker" mode="selector" :range="typeLabels" :value="typeIndex" @change="onTypePick">
              <view class="app__picker">{{ typeLabels[typeIndex] }}</view>
            </picker>
          </view>
          <view v-if="isPosition" class="app__field">
            <text class="app__label">实习岗位 <text class="app__req">*</text></text>
            <picker class="mobile-picker" mode="selector" :range="positionLabels" :value="positionIndex" @change="onPositionPick">
              <view class="app__picker">{{ selectedPosition ? positionLabels[positionIndex] : '请选择学校已发布岗位（原岗位未读到时请继续加载）' }}</view>
            </picker>
            <text v-if="selectedPosition" class="app__desc">{{ selectedPosition.companyName }} · {{ selectedPosition.workLocation || '地点待定' }} · 剩余 {{ selectedPosition.remaining }} 人</text>
            <text v-if="selectedPosition?.canSelect === false" class="app__desc">{{ selectedPosition.selectionReason || '该岗位当前不可申请，请联系学校核实' }}</text>
            <text class="app__desc">已读取 {{ positions.length }} / {{ positionsTotal }} 个当前批次岗位</text>
            <button v-if="positionsMore" class="mobile-control btn btn-ghost" :disabled="positionsLoading || submitting" @click="loadMorePositions">{{ positionsLoading ? '正在读取…' : '继续加载岗位' }}</button>
          </view>
          <template v-else>
            <MobileInlineAlert
              type="info"
              title="企业登记核验"
              :description="registryHint"
            />
            <view class="app__section-title">企业信息</view>
            <view class="app__field"><text class="app__label">企业名称 <text class="app__req">*</text></text><input v-model.trim="form.companyName" class="mobile-input app__input" placeholder="请输入企业全称" /></view>
            <view class="app__field"><text class="app__label">统一社会信用代码 <text class="app__req">*</text></text><input v-model.trim="form.companyCreditCode" class="mobile-input app__input" maxlength="18" placeholder="18位统一社会信用代码" /></view>
            <view class="app__field"><text class="app__label">企业负责人 <text class="app__req">*</text></text><input v-model.trim="form.companyPrincipal" class="mobile-input app__input" placeholder="负责人姓名" /></view>
            <view class="app__field"><text class="app__label">企业规模 <text class="app__req">*</text></text><picker class="mobile-picker" mode="selector" :range="companyScaleOptions" :value="companyScaleIndex" @change="onCompanyScalePick"><view class="app__picker">{{ form.companyScale || '请选择企业规模' }}</view></picker></view>
            <view class="app__field"><text class="app__label">企业联系电话 <text class="app__req">*</text></text><input v-model.trim="form.companyPhone" class="mobile-input app__input" placeholder="企业联系电话" /></view>
            <view class="app__field"><text class="app__label">企业邮箱 <text class="app__req">*</text></text><input v-model.trim="form.companyEmail" class="mobile-input app__input" placeholder="name@example.com" /></view>
            <view class="app__field"><text class="app__label">单位性质 <text class="app__req">*</text></text><picker class="mobile-picker" mode="selector" :range="companyNatureOptions" :value="companyNatureIndex" @change="onCompanyNaturePick"><view class="app__picker">{{ form.companyNature || '请选择单位性质' }}</view></picker></view>
            <view class="app__field"><text class="app__label">所属行业 <text class="app__req">*</text></text><picker class="mobile-picker" mode="selector" :range="industryOptions" :value="industryIndex" @change="onIndustryPick"><view class="app__picker">{{ form.companyIndustry || '请选择所属行业' }}</view></picker></view>
            <view class="app__field"><text class="app__label">单位所在地区 <text class="app__req">*</text></text><picker class="mobile-picker" mode="region" @change="onCompanyRegionPick"><view class="app__picker">{{ companyRegionText || '请选择省 / 市 / 区县' }}</view></picker></view>
            <view class="app__field"><text class="app__label">单位注册地址 <text class="app__req">*</text></text><input v-model.trim="form.companyRegisteredAddress" class="mobile-input app__input" placeholder="请输入详细注册地址" /></view>
            <view class="app__field"><text class="app__label">邮编</text><input v-model.trim="form.companyPostalCode" class="mobile-input app__input" placeholder="企业邮编（可选）" /></view>
            <view class="app__field"><text class="app__label">单位联系人 <text class="app__req">*</text></text><input v-model.trim="form.contactName" class="mobile-input app__input" placeholder="联系人姓名" /></view>
            <view class="app__field"><text class="app__label">联系人电话 <text class="app__req">*</text></text><input v-model.trim="form.contactPhone" class="mobile-input app__input" placeholder="联系人电话" /></view>

            <view class="app__section-title">岗位与实习信息</view>
            <view class="app__field"><text class="app__label">实习部门 <text class="app__req">*</text></text><input v-model.trim="form.internshipDepartment" class="mobile-input app__input" placeholder="所属科室 / 部门" /></view>
            <view class="app__field"><text class="app__label">岗位名称 <text class="app__req">*</text></text><input v-model.trim="form.positionName" class="mobile-input app__input" placeholder="实习岗位名称" /></view>
            <view class="app__field"><text class="app__label">岗位类别 <text class="app__req">*</text></text><picker class="mobile-picker" mode="selector" :range="positionCategoryOptions" :value="positionCategoryIndex" @change="onPositionCategoryPick"><view class="app__picker">{{ form.positionCategory || '请选择岗位类别' }}</view></picker></view>
            <view class="app__field"><text class="app__label">工作内容 <text class="app__req">*</text></text><textarea v-model="form.workContent" class="mobile-textarea app__textarea" maxlength="4000" placeholder="简要说明主要工作内容" /></view>
            <view class="app__field"><text class="app__label">企业老师 <text class="app__req">*</text></text><input v-model.trim="form.enterpriseMentorName" class="mobile-input app__input" placeholder="企业带教老师姓名" /></view>
            <view class="app__field"><text class="app__label">企业老师电话 <text class="app__req">*</text></text><input v-model.trim="form.enterpriseMentorPhone" class="mobile-input app__input" placeholder="企业老师联系电话" /></view>
            <view class="app__field"><text class="app__label">实习国家（地区）</text><input v-model.trim="form.workCountry" class="mobile-input app__input" placeholder="默认中国" /></view>
            <view class="app__field"><text class="app__label">岗位所在地区 <text class="app__req">*</text></text><picker class="mobile-picker" mode="region" @change="onWorkRegionPick"><view class="app__picker">{{ workRegionText || '请选择省 / 市 / 区县' }}</view></picker></view>
            <view class="app__field"><text class="app__label">岗位详细地址 <text class="app__req">*</text></text><input v-model.trim="form.workAddress" class="mobile-input app__input" placeholder="请输入实习岗位详细地址" /></view>
            <view class="app__grid">
              <view class="app__field"><text class="app__label">开始日期 <text class="app__req">*</text></text><picker class="mobile-picker" mode="date" :value="form.internshipStartDate" @change="form.internshipStartDate = $event.detail.value"><view class="app__picker">{{ form.internshipStartDate || '请选择' }}</view></picker></view>
              <view class="app__field"><text class="app__label">结束日期 <text class="app__req">*</text></text><picker class="mobile-picker" mode="date" :value="form.internshipEndDate" @change="form.internshipEndDate = $event.detail.value"><view class="app__picker">{{ form.internshipEndDate || '请选择' }}</view></picker></view>
            </view>
            <view class="app__field"><text class="app__label">实习方式 <text class="app__req">*</text></text><picker class="mobile-picker" mode="selector" :range="internshipModeOptions" :value="internshipModeIndex" @change="onInternshipModePick"><view class="app__picker">{{ form.internshipMode || '请选择实习方式' }}</view></picker></view>
            <view class="app__field"><text class="app__label">是否专业对口 <text class="app__req">*</text></text><picker class="mobile-picker" mode="selector" :range="majorMatchOptions" :value="majorMatchIndex" @change="onMajorMatchPick"><view class="app__picker">{{ majorMatchText }}</view></picker></view>
            <view class="app__field"><text class="app__label">约定实习薪资（元/月） <text class="app__req">*</text></text><input v-model.trim="form.agreedSalary" class="mobile-input app__input" type="digit" placeholder="例如 2500" /></view>

            <view class="app__file">
              <view class="flex-1"><text class="app__label">自主实习证明 <text class="app__req">*</text></text><text class="app__desc">{{ evidenceFileName || (form.evidenceFileId ? '已上传证明材料' : '请上传企业接收函、协议或盖章证明') }}</text></view>
              <button class="mobile-control btn btn-ghost" :disabled="uploading" @click="pickEvidence">{{ uploading ? '上传中…' : (form.evidenceFileId ? '重新上传' : '选择文件') }}</button>
            </view>
            <view class="app__file">
              <view class="flex-1"><text class="app__label">三方协议照片</text><text class="app__desc">{{ form.agreementFileIds.length ? ('已上传 ' + form.agreementFileIds.length + ' 份') : '可上传协议照片或扫描件，最多9份' }}</text></view>
              <button class="mobile-control btn btn-ghost" :disabled="uploading" @click="pickAgreement">{{ uploading ? '上传中…' : '添加协议' }}</button>
            </view>
          </template>
          <view class="app__field"><text class="app__label">申请说明 <text class="app__req">*</text></text><textarea v-model="form.applicationNote" class="mobile-textarea app__textarea" maxlength="500" placeholder="说明申请原因和岗位匹配情况（至少5字）" /></view>
        </view>

        <view v-if="otherApplications.length" class="card">
          <text class="card-title">历史申请</text>
          <view v-for="item in otherApplications" :key="item.id" class="app__hist">
            <view class="row-between">
              <view class="flex-1"><text>{{ item.applicationTypeLabel }} · {{ item.statusLabel }}</text><text class="app__hist-note">{{ item.positionName || item.companyName || item.applicationNote || '' }}</text></view>
              <button v-if="item.status === 'PENDING_REVIEW' && recordAllowsApplication" class="mobile-control btn btn-ghost app__wd" :disabled="submitting" @click="withdraw(item)">撤回</button>
            </view>
            <text v-if="item.reviewComment" class="app__review">审核意见：{{ item.reviewComment }}</text>
            <text class="app__version">版本 {{ item.version }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="canWriteApplication">
      <button class="mobile-control btn btn-ghost flex-1" :disabled="submitting || uploading" @click="saveDraft">保存草稿</button>
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : '提交审核' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import {
  studentInternshipApplications,
  studentInternshipApplicationSave,
  studentInternshipApplicationSubmit,
  studentInternshipApplicationWithdraw
} from '@/services/internshipApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import { toast, go } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

const TYPES = [
  { value: 'POSITION', label: '学校岗位志愿' },
  { value: 'SELF_ARRANGED', label: '自主实习' }
]
const COMPANY_SCALE_OPTIONS = ['微型', '小型', '中型', '大型', '其他']
const COMPANY_NATURE_OPTIONS = ['国有企业', '民营企业', '外商投资企业', '港澳台投资企业', '集体企业', '事业单位', '社会组织', '其他']
const INDUSTRY_OPTIONS = ['农林牧渔', '制造业', '建筑业', '信息传输/软件/信息技术', '批发和零售', '交通运输/仓储/邮政', '住宿和餐饮', '金融业', '教育', '卫生和社会工作', '文化/体育/娱乐', '公共管理/社会保障', '其他']
const POSITION_CATEGORY_OPTIONS = ['生产操作', '技术研发', '工程技术', '信息技术', '运营', '管理', '市场销售', '客户服务', '行政支持', '教育教学', '其他']
const INTERNSHIP_MODE_OPTIONS = ['集中实习', '自主实习', '认识实习', '岗位实习', '其他']
const MAJOR_MATCH_OPTIONS = ['请选择', '是', '否']

function emptySelfForm() {
  return {
    companyName: '', companyCreditCode: '', companyPrincipal: '', companyScale: '',
    companyPhone: '', companyEmail: '', companyNature: '', companyIndustry: '',
    companyRegisteredAddress: '', companyPostalCode: '', companyProvince: '', companyCity: '', companyDistrict: '',
    contactName: '', contactPhone: '',
    internshipDepartment: '', positionName: '', positionCategory: '', workContent: '',
    enterpriseMentorName: '', enterpriseMentorPhone: '',
    workCountry: '中国', workProvince: '', workCity: '', workDistrict: '', workAddress: '',
    internshipStartDate: '', internshipEndDate: '', internshipMode: '自主实习',
    majorMatch: null, agreedSalary: '',
    evidenceFileId: '', agreementFileIds: [], applicationNote: ''
  }
}

export default {
  components: { ReportFilePreview },
  data() {
    return {
      pageState: 'loading', submitting: false, uploading: false, historyMode: false,
      context: {}, requestedBatchId: '', loadSequence: 0, loadError: '', pausedLoad: false, recordStatus: '', destinationType: '',
      positionsPage: 1, positionsMore: false, positionsTotal: 0, positionsLoading: false, selectedPositionId: '',
      typeIndex: 0, typeLabels: TYPES.map((x) => x.label), positions: [], positionIndex: 0,
      evidenceFileName: '', history: [], editableApplication: null,
      materialOpening: false, materialError: '', materialSequence: 0, expandedApplicationScope: '',
      conflict: null, conflictReading: false, conflictReadSeq: 0,
      generation: currentSessionGeneration(), hidden: false, writeSeq: 0,
      companyScaleOptions: COMPANY_SCALE_OPTIONS,
      companyNatureOptions: COMPANY_NATURE_OPTIONS,
      industryOptions: INDUSTRY_OPTIONS,
      positionCategoryOptions: POSITION_CATEGORY_OPTIONS,
      internshipModeOptions: INTERNSHIP_MODE_OPTIONS,
      majorMatchOptions: MAJOR_MATCH_OPTIONS,
      form: emptySelfForm()
    }
  },
  computed: {
    recordAllowsApplication() { return !this.historyMode && ['PREPARING','READY'].includes(this.recordStatus) && !['ASSIGNED','SELF_ARRANGED','EXEMPTED'].includes(this.destinationType) },
    canWriteApplication() { return this.pageState === 'ready' && !this.hidden && this.recordAllowsApplication && !this.pendingApplication && !this.history.some(row=>row.status==='APPROVED') && (!this.editableApplication || ['DRAFT','REJECTED','WITHDRAWN'].includes(this.editableApplication.status)) },
    displayApplication() { return this.history.find(row=>row.status==='APPROVED') || this.editableApplication || this.history.find(row=>row.status==='PENDING_REVIEW') || this.history[0] || null },
    applicationFileScope() { return [this.generation, this.context.batchId, this.context.internshipId, this.displayApplication?.id, this.displayApplication?.version].join(':') },
    applicationReturnUrl() { return '/pages/student-internship/index' + (this.context.batchId ? '?batchId=' + encodeURIComponent(this.context.batchId) : '') },
    showApplicationResult() { return !this.canWriteApplication || ['APPROVED','PENDING_REVIEW','REJECTED'].includes(this.displayApplication?.status) },
    applicationDetailsExpanded() { return this.expandedApplicationScope === this.applicationFileScope },
    applicationSummaryItems() { return this.readOnlyItems.filter(item=>['企业名称','实习岗位','实习开始日期','实习结束日期','约定实习薪资'].includes(item.label)) },
    applicationDetailItems() { return this.readOnlyItems.filter(item=>!['企业名称','实习岗位','实习开始日期','实习结束日期','约定实习薪资','审核意见'].includes(item.label)) },
    otherApplications() { return this.showApplicationResult && this.displayApplication ? this.history.filter(row=>String(row.id)!==String(this.displayApplication.id)) : this.history },
    applicationMaterials() {
      const row = this.displayApplication || {}, files = []
      if (row.evidenceFileId) files.push({ fileId: String(row.evidenceFileId), fileName: '申请佐证材料' })
      for (const [index, id] of (row.agreementFileIds || []).entries()) {
        if (id && !files.some(file => file.fileId === String(id))) files.push({ fileId: String(id), fileName: `三方协议材料 ${index + 1}` })
      }
      return files
    },
    readOnlyNextStep() { if(this.historyMode)return '这是历史实习原单，仅供查询。';if(['ASSIGNED','SELF_ARRANGED','EXEMPTED'].includes(this.destinationType) || this.displayApplication?.status==='APPROVED')return '去向已落实，协议与保险可从首页继续办理。';if(this.pendingApplication)return '等待审核；需要修改时可先撤回。';return '当前不可新增或修改，请联系指导教师。' },
    readOnlyItems() {
      const row=this.displayApplication || {}
      const fields=[['companyName','企业名称'],['companyCreditCode','统一社会信用代码'],['companyPrincipal','企业负责人'],['companyScale','企业规模'],['companyPhone','企业联系电话'],['companyEmail','企业邮箱'],['companyNature','单位性质'],['companyIndustry','所属行业'],['companyProvince','单位所在省'],['companyCity','单位所在市'],['companyDistrict','单位所在区县'],['companyRegisteredAddress','单位注册地址'],['companyPostalCode','邮编'],['contactName','单位联系人'],['contactPhone','联系人电话'],['internshipDepartment','实习部门'],['positionName','实习岗位'],['positionCategory','岗位类别'],['workContent','工作内容'],['enterpriseMentorName','企业带教老师'],['enterpriseMentorPhone','企业老师电话'],['workCountry','实习国家或地区'],['workProvince','岗位所在省'],['workCity','岗位所在市'],['workDistrict','岗位所在区县'],['workAddress','岗位地址'],['internshipStartDate','实习开始日期'],['internshipEndDate','实习结束日期'],['internshipMode','实习方式'],['applicationNote','申请说明'],['reviewComment','审核意见']]
      return [...fields.map(([key,label])=>({label,value:row[key]===null || row[key]===undefined || row[key]===''?'未填写':row[key]})),
        {label:'专业是否对口',value:row.majorMatch===true?'是':row.majorMatch===false?'否':'未填写'},
        {label:'企业登记核验',value:row.companyRegistryVerified?'已通过授权数据源核验':'尚未通过授权数据源核验'},
        {label:'约定实习薪资',value:row.agreedSalary==null?'未填写':`${row.agreedSalary} 元/月`},
        {label:'佐证材料',value:row.evidenceFileId?'已保留原单佐证材料':'未上传'},
        {label:'三方协议材料',value:`已保留 ${(row.agreementFileIds||[]).length} 份`},
        {label:'提交时间',value:formatDateTime(row.submittedAt)},{label:'审核时间',value:formatDateTime(row.reviewedAt)},{label:'审核人',value:row.reviewedBy||'未审核'}]
    },
    isPosition() { return TYPES[this.typeIndex].value === 'POSITION' },
    positionLabels() { return this.positions.map((x) => `${x.title} · ${x.companyName} · 剩余${x.remaining}人`) },
    selectedPosition() { return this.positions.find(row => String(row.id) === this.selectedPositionId) || null },
    pendingApplication() { return this.history.some((x) => x.status === 'PENDING_REVIEW') },
    companyScaleIndex() { return Math.max(0, COMPANY_SCALE_OPTIONS.indexOf(this.form.companyScale)) },
    companyNatureIndex() { return Math.max(0, COMPANY_NATURE_OPTIONS.indexOf(this.form.companyNature)) },
    industryIndex() { return Math.max(0, INDUSTRY_OPTIONS.indexOf(this.form.companyIndustry)) },
    positionCategoryIndex() { return Math.max(0, POSITION_CATEGORY_OPTIONS.indexOf(this.form.positionCategory)) },
    internshipModeIndex() { return Math.max(0, INTERNSHIP_MODE_OPTIONS.indexOf(this.form.internshipMode)) },
    majorMatchIndex() { return this.form.majorMatch === true ? 1 : (this.form.majorMatch === false ? 2 : 0) },
    majorMatchText() { return this.form.majorMatch === true ? '是' : (this.form.majorMatch === false ? '否' : '请选择') },
    companyRegionText() { return [this.form.companyProvince, this.form.companyCity, this.form.companyDistrict].filter(Boolean).join(' / ') },
    workRegionText() { return [this.form.workProvince, this.form.workCity, this.form.workDistrict].filter(Boolean).join(' / ') },
    registryHint() {
      if (this.editableApplication?.companyRegistryVerified) {
        return `已由 ${this.editableApplication.companyRegistryProvider || '授权企业登记数据源'} 核验。`
      }
      return '当前仅保存学生申报信息。未接入采购方认可的企业登记数据源前，系统不会显示“已认证/已核验”。'
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.load() },
  watch: { applicationFileScope() { this.resetApplicationMaterial() } },
  onHide() { this.resetApplicationMaterial(); this.pausedLoad = this.pageState === 'loading'; this.hidden = true; this.loadSequence++; this.conflictReadSeq++; this.writeSeq++; this.conflictReading = false; this.submitting = false; this.positionsLoading = false },
  onUnload() { this.resetApplicationMaterial(); this.hidden = true; this.loadSequence++; this.conflictReadSeq++ },
  onShow() {
    this.hidden = false
    if (this.generation !== currentSessionGeneration()) {
      this.resetApplicationMaterial()
      this.generation = currentSessionGeneration(); this.conflict = null; this.form = emptySelfForm()
      this.editableApplication = null; this.evidenceFileName = ''; this.requestedBatchId = ''; this.context = {}; this.positions = []; this.history = []; this.load()
    } else if (this.pausedLoad) { this.pausedLoad = false; this.load() }
  },
  methods: {
    continuePlacement(path) { if(this.hidden || this.historyMode || this.generation!==currentSessionGeneration() || !['/pages/student-internship/agreement/index','/pages/student-internship/insurance/index'].includes(path))return;go(path + (this.context.batchId ? '?batchId=' + encodeURIComponent(this.context.batchId) : '')) },
    resetApplicationMaterial() { this.materialSequence++; this.materialOpening = false; this.materialError = ''; this.$refs.applicationMaterialPreview?.reset() },
    async openApplicationMaterial(fileId) {
      if (this.hidden || this.pageState !== 'ready' || this.materialOpening || this.generation !== currentSessionGeneration()) return
      const file = this.applicationMaterials.find(item => item.fileId === String(fileId))
      if (!file || String(this.displayApplication?.recordId) !== String(this.context.internshipId)) { this.materialError = '材料不属于当前原单，请重新读取申请'; return }
      const preview = this.$refs.applicationMaterialPreview
      if (!preview) return
      const sequence = ++this.materialSequence, scope = this.applicationFileScope
      this.materialOpening = true; this.materialError = ''
      try {
        await preview.open(file)
        if (sequence === this.materialSequence && preview.state === 'error') this.materialError = '材料读取未完成，请确认材料仍存在、有查看权限且安全扫描已通过后重试。'
      }
      catch (error) { if (sequence === this.materialSequence) this.materialError = normalizeError(error).text || '材料读取失败，请重试' }
      finally {
        if (sequence === this.materialSequence) {
          this.materialOpening = false
          if (this.hidden || scope !== this.applicationFileScope || this.generation !== currentSessionGeneration()) this.resetApplicationMaterial()
        }
      }
    },
    applicationStatusLabel(status) { return ({DRAFT:'草稿',PENDING_REVIEW:'待审核',REJECTED:'已退回',APPROVED:'已通过',WITHDRAWN:'已撤回',CANCELLED:'已取消'})[status] || '状态待核实' },
    onTypePick(e) { if (!this.canWriteApplication || this.conflict || this.submitting) return; this.typeIndex = Number(e.detail.value) || 0; this.editableApplication = null },
    onPositionPick(e) { if (!this.conflict && !this.submitting) { this.positionIndex = Number(e.detail.value) || 0; this.selectedPositionId = String(this.positions[this.positionIndex]?.id || '') } },
    onCompanyScalePick(e) { this.form.companyScale = COMPANY_SCALE_OPTIONS[Number(e.detail.value) || 0] || '' },
    onCompanyNaturePick(e) { this.form.companyNature = COMPANY_NATURE_OPTIONS[Number(e.detail.value) || 0] || '' },
    onIndustryPick(e) { this.form.companyIndustry = INDUSTRY_OPTIONS[Number(e.detail.value) || 0] || '' },
    onPositionCategoryPick(e) { this.form.positionCategory = POSITION_CATEGORY_OPTIONS[Number(e.detail.value) || 0] || '' },
    onInternshipModePick(e) { this.form.internshipMode = INTERNSHIP_MODE_OPTIONS[Number(e.detail.value) || 0] || '' },
    onMajorMatchPick(e) {
      const index = Number(e.detail.value) || 0
      this.form.majorMatch = index === 1 ? true : (index === 2 ? false : null)
    },
    onCompanyRegionPick(e) {
      const values = e?.detail?.value || []
      this.form.companyProvince = values[0] || ''
      this.form.companyCity = values[1] || ''
      this.form.companyDistrict = values[2] || ''
    },
    onWorkRegionPick(e) {
      const values = e?.detail?.value || []
      this.form.workProvince = values[0] || ''
      this.form.workCity = values[1] || ''
      this.form.workDistrict = values[2] || ''
    },
    async load() {
      this.resetApplicationMaterial()
      if (this.conflict) return this.rereadConflict()
      const sequence = ++this.loadSequence, generation = currentSessionGeneration(), requested = this.requestedBatchId
      const current = () => !this.hidden && sequence === this.loadSequence && generation === currentSessionGeneration() && requested === this.requestedBatchId
      this.pageState = 'loading'; this.loadError = ''
      try {
        const dashboard = await studentApi.getInternship(requested)
        if (!current()) return
        const batchId = String(dashboard?.batchId || ''), internshipId = String(dashboard?.recordId || dashboard?.internshipId || '')
        if (!batchId || !internshipId) { this.context = {}; this.positions = []; this.history = []; this.pageState = 'empty'; return }
        const [rows, library] = await Promise.all([
          studentInternshipApplications(batchId, internshipId), studentApi.getInternshipApplicationPositions(batchId, internshipId)
        ])
        if (!current()) return
        if (String(library.batchId) !== batchId || String(library.internshipId) !== internshipId) throw new Error('岗位库不属于当前实习记录，请重新读取')
        this.history = Array.isArray(rows) ? rows : rows?.items || []
        this.context = { batchId, internshipId }
        this.recordStatus = dashboard.statusText || ''; this.destinationType = dashboard.destinationType || ''
        this.positions = library.items || []; this.positionsPage = 1; this.positionsMore = !!library.hasMore; this.positionsTotal = library.total
        this.selectedPositionId = ''
        this.historyMode = !!dashboard?.historyMode
        const editable = this.history.find((x) => ['POSITION', 'SELF_ARRANGED'].includes(x.applicationType) && ['DRAFT', 'REJECTED', 'WITHDRAWN'].includes(x.status)) || null
        this.editableApplication = editable
        if (editable) this.fillEditable(editable)
        this.pageState = 'ready'
      } catch (e) { if (current()) { this.pageState = 'error'; this.loadError = e?.message || '申请或岗位读取失败，请重试'; this.positions = []; this.history = [] } }
    },
    async loadMorePositions() {
      const conflict = this.conflict
      if (!(conflict ? conflict.positionsMore : this.positionsMore) || this.positionsLoading || this.hidden) return
      const sequence = this.loadSequence, generation = currentSessionGeneration(), { batchId, internshipId } = this.context, page = (conflict ? conflict.positionsPage : this.positionsPage) + 1
      const current = () => !this.hidden && conflict === this.conflict && sequence === this.loadSequence && generation === currentSessionGeneration() && batchId === this.context.batchId && internshipId === this.context.internshipId
      this.positionsLoading = true; this.loadError = ''
      try { const data = await studentApi.getInternshipApplicationPositions(batchId, internshipId, page); if (!current()) return
        if (String(data.batchId) !== String(batchId) || String(data.internshipId) !== String(internshipId)) throw new Error('后续岗位不属于当前实习记录')
        const rows = conflict ? conflict.positions : this.positions
        const seen = new Set(rows.map(row => String(row.id))); rows.push(...(data.items || []).filter(row => !seen.has(String(row.id))))
        if (conflict) { conflict.positionsPage = page; conflict.positionsMore = !!data.hasMore }
        else { this.positionsPage = page; this.positionsMore = !!data.hasMore; this.positionsTotal = data.total }
        const index = this.positions.findIndex(row => String(row.id) === this.selectedPositionId); if (index >= 0) this.positionIndex = index
      } catch (e) { if (current()) this.loadError = e?.message || '后续岗位读取失败，已加载岗位和选择已保留' }
      finally { if (current()) this.positionsLoading = false }
    },
    fillEditable(item) {
      const index = TYPES.findIndex((x) => x.value === item.applicationType)
      if (index >= 0) this.typeIndex = index
      this.form = {
        ...emptySelfForm(),
        companyName: item.companyName || '',
        companyCreditCode: item.companyCreditCode || '',
        companyPrincipal: item.companyPrincipal || '',
        companyScale: item.companyScale || '',
        companyPhone: item.companyPhone || '',
        companyEmail: item.companyEmail || '',
        companyNature: item.companyNature || '',
        companyIndustry: item.companyIndustry || '',
        companyRegisteredAddress: item.companyRegisteredAddress || '',
        companyPostalCode: item.companyPostalCode || '',
        companyProvince: item.companyProvince || '',
        companyCity: item.companyCity || '',
        companyDistrict: item.companyDistrict || '',
        contactName: item.contactName || '',
        contactPhone: item.contactPhone || '',
        internshipDepartment: item.internshipDepartment || '',
        positionName: item.positionName || '',
        positionCategory: item.positionCategory || '',
        workContent: item.workContent || '',
        enterpriseMentorName: item.enterpriseMentorName || '',
        enterpriseMentorPhone: item.enterpriseMentorPhone || '',
        workCountry: item.workCountry || '中国',
        workProvince: item.workProvince || '',
        workCity: item.workCity || '',
        workDistrict: item.workDistrict || '',
        workAddress: item.workAddress || '',
        internshipStartDate: item.internshipStartDate || '',
        internshipEndDate: item.internshipEndDate || '',
        internshipMode: item.internshipMode || '自主实习',
        majorMatch: typeof item.majorMatch === 'boolean' ? item.majorMatch : null,
        agreedSalary: item.agreedSalary == null ? '' : String(item.agreedSalary),
        evidenceFileId: item.evidenceFileId || '',
        agreementFileIds: Array.isArray(item.agreementFileIds) ? [...item.agreementFileIds] : [],
        applicationNote: item.applicationNote || ''
      }
      if (item.positionId) {
        this.selectedPositionId = String(item.positionId)
        const positionIndex = this.positions.findIndex((x) => String(x.id) === String(item.positionId))
        if (positionIndex >= 0) this.positionIndex = positionIndex
      }
      this.evidenceFileName = item.evidenceFileId ? '已上传证明材料' : ''
    },
    async pickEvidence() {
      if (!this.canWriteApplication || this.uploading) return
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_APPLICATION' })
        this.form.evidenceFileId = result.fileId
        this.evidenceFileName = result.fileName || file.name || '证明材料'
        toast('证明材料已上传')
      } catch (e) { toast(e?.message || '文件上传失败') }
      finally { this.uploading = false }
    },
    async pickAgreement() {
      if (!this.canWriteApplication || this.uploading) return
      if ((this.form.agreementFileIds || []).length >= 9) return toast('三方协议最多上传9份')
      this.uploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_APPLICATION' })
        if (result?.fileId && !this.form.agreementFileIds.includes(result.fileId)) {
          this.form.agreementFileIds.push(result.fileId)
        }
        toast('三方协议材料已添加')
      } catch (e) { toast(e?.message || '协议材料上传失败') }
      finally { this.uploading = false }
    },
    payload() {
      const applicationType = TYPES[this.typeIndex].value
      const body = {
        ...this.context,
        applicationType,
        applicationNote: String(this.form.applicationNote || '').trim()
      }
      if (this.editableApplication) {
        body.id = this.editableApplication.id
        body.expectedVersion = this.editableApplication.version
      }
      if (applicationType === 'POSITION') body.positionId = this.selectedPosition?.id || ''
      else Object.assign(body, this.form)
      return body
    },
    validate() {
      if (String(this.form.applicationNote || '').trim().length < 5) return '申请说明不少于5字'
      if (this.isPosition) return this.selectedPosition?.canSelect === true ? '' : (this.selectedPosition?.selectionReason || '请选择当前可申请的实习岗位')
      if (String(this.form.companyName || '').trim().length < 2) return '请填写企业名称'
      if (!/^[0-9A-HJ-NPQRTUWXY]{18}$/i.test(String(this.form.companyCreditCode || '').trim())) return '请填写18位统一社会信用代码'
      if (String(this.form.companyPrincipal || '').trim().length < 2) return '请填写企业负责人'
      if (!this.form.companyScale) return '请选择企业规模'
      if (!String(this.form.companyPhone || '').trim()) return '请填写企业联系电话'
      if (!/^\S+@\S+\.\S+$/.test(String(this.form.companyEmail || '').trim())) return '请填写正确的企业邮箱'
      if (!this.form.companyNature) return '请选择单位性质'
      if (!this.form.companyIndustry) return '请选择所属行业'
      if (!this.form.companyProvince || !this.form.companyCity || !this.form.companyDistrict) return '请选择单位所在省市区'
      if (String(this.form.companyRegisteredAddress || '').trim().length < 5) return '请填写单位注册地址'
      if (String(this.form.contactName || '').trim().length < 2) return '请填写单位联系人'
      if (!String(this.form.contactPhone || '').trim()) return '请填写联系人电话'
      if (!this.form.internshipDepartment) return '请填写实习部门'
      if (String(this.form.positionName || '').trim().length < 2) return '请填写岗位名称'
      if (!this.form.positionCategory) return '请选择岗位类别'
      if (String(this.form.workContent || '').trim().length < 5) return '请填写工作内容'
      if (String(this.form.enterpriseMentorName || '').trim().length < 2) return '请填写企业老师'
      if (!String(this.form.enterpriseMentorPhone || '').trim()) return '请填写企业老师电话'
      if (!this.form.workProvince || !this.form.workCity || !this.form.workDistrict) return '请选择岗位所在省市区'
      if (String(this.form.workAddress || '').trim().length < 5) return '请填写岗位详细地址'
      if (!this.form.internshipStartDate || !this.form.internshipEndDate) return '请选择实习起止日期'
      if (this.form.internshipStartDate > this.form.internshipEndDate) return '实习结束日期不能早于开始日期'
      if (!this.form.internshipMode) return '请选择实习方式'
      if (typeof this.form.majorMatch !== 'boolean') return '请选择岗位是否专业对口'
      if (this.form.agreedSalary === '' || Number(this.form.agreedSalary) < 0) return '请填写实习薪资'
      if (!this.form.evidenceFileId) return '请上传自主实习证明材料'
      return ''
    },
    beginConflict(body, base) {
      this.conflict = { base, batchId: String(body.batchId), internshipId: String(body.internshipId),
        positionId: String(body.positionId || ''), applicationType: body.applicationType,
        generation: currentSessionGeneration(), latest: null, positions: [],
        error: '申请或岗位已变化，原版本、填写内容和附件已保留；请读取并核对最新原单。' }
    },
    async rereadConflict() {
      const c = this.conflict
      if (!c || this.conflictReading) return
      const sequence = ++this.conflictReadSeq
      const current = () => !this.hidden && c === this.conflict && sequence === this.conflictReadSeq && c.generation === currentSessionGeneration() &&
        c.batchId === String(this.context.batchId) && c.internshipId === String(this.context.internshipId)
      if (!current()) return
      this.conflictReading = true; c.latest = null
      try {
        const dashboard = await studentApi.getInternship(c.batchId)
        if (!current()) return
        if (String(dashboard?.batchId) !== c.batchId || String(dashboard?.recordId || dashboard?.internshipId) !== c.internshipId) throw new Error('当前实习记录已变化，请重新进入本人申请')
        if (dashboard.historyMode) throw new Error('当前实习记录已转为历史只读，草稿保留，不能继续写入')
        const [rows, library] = await Promise.all([
          studentInternshipApplications(c.batchId, c.internshipId), studentApi.getInternshipApplicationPositions(c.batchId, c.internshipId)
        ])
        if (!current()) return
        if (String(library.batchId) !== c.batchId || String(library.internshipId) !== c.internshipId) throw new Error('岗位读取上下文已变化，原草稿保留')
        const latest = (Array.isArray(rows) ? rows : rows?.items || []).find(row => String(row.id) === c.base?.id)
        if (!latest || String(latest.recordId) !== c.internshipId || !Number.isInteger(latest.version) || latest.version < 0) throw new Error('未确认精确原单，填写内容仍保留，请核对本人申请记录')
        c.latest = latest; c.positions = library.items || []; c.positionsPage = 1; c.positionsMore = !!library.hasMore; c.error = '请核对最新原单及岗位情况，确认后才更新办理依据；不会自动重提。'
      } catch (e) { if (current()) c.error = e?.message || '读取原单失败，填写内容已保留' }
      finally { if (sequence === this.conflictReadSeq) this.conflictReading = false }
    },
    adoptLatestApplication() {
      const c = this.conflict, latest = c?.latest
      if (!latest || !this.recordAllowsApplication || this.hidden || this.conflictReading || this.submitting || this.uploading || c.generation !== currentSessionGeneration()) return
      if (String(latest.id) !== c.base?.id || String(latest.recordId) !== c.internshipId || c.batchId !== String(this.context.batchId) || c.internshipId !== String(this.context.internshipId)) return
      if (!['DRAFT', 'REJECTED', 'WITHDRAWN'].includes(latest.status)) { c.error = '原单已进入审核或已办结，当前填写内容保留，不能覆盖'; return }
      if (c.applicationType === 'POSITION') {
        const index = c.positions.findIndex(row => String(row.id) === c.positionId && Number(row.remaining) > 0 && row.canSelect === true)
        if (index < 0) { c.error = '原岗位已下架或名额已满，原选择和草稿保留，不能改投另一岗位'; return }
        this.positions = c.positions; this.positionIndex = index; this.selectedPositionId = c.positionId; this.positionsPage = c.positionsPage; this.positionsMore = c.positionsMore
      }
      this.editableApplication = { ...latest }; this.conflict = null
    },
    async saveDraft() {
      if (!this.canWriteApplication || this.submitting || this.uploading || this.conflict) return
      const body = this.payload()
      const generation = currentSessionGeneration(), context = this.context, form = this.form, operation = ++this.writeSeq
      const current = () => !this.hidden && operation === this.writeSeq && generation === currentSessionGeneration() && context === this.context && form === this.form
      this.submitting = true
      try {
        await studentInternshipApplicationSave(body)
        if (!current()) return
        toast('草稿已保存')
        await this.load()
      } catch (e) {
        if (!current()) return
        if (normalizeError(e).kind === 'conflict') this.beginConflict(body, body.id ? { id: String(body.id), version: body.expectedVersion } : null)
        else toast(e?.message || '保存失败')
      } finally { if (!this.hidden && operation === this.writeSeq && generation === currentSessionGeneration()) this.submitting = false }
    },
    async submit() {
      if (!this.canWriteApplication || this.submitting || this.uploading || this.conflict) return
      const error = this.validate()
      if (error) return toast(error)
      const body = this.payload()
      let base = body.id ? { id: String(body.id), version: body.expectedVersion } : null
      const generation = currentSessionGeneration(), context = this.context, form = this.form, operation = ++this.writeSeq
      const current = () => !this.hidden && operation === this.writeSeq && generation === currentSessionGeneration() && context === this.context && form === this.form
      this.submitting = true
      try {
        const saved = await studentInternshipApplicationSave(body)
        if (!current()) return
        base = { id: String(saved.id), version: saved.version }
        await studentInternshipApplicationSubmit(saved.id, {
          ...this.context,
          expectedVersion: saved.version
        })
        if (!current()) return
        toast('申请已提交审核')
        await this.load()
      } catch (e) {
        if (!current()) return
        if (normalizeError(e).kind === 'conflict') this.beginConflict(body, base)
        else toast(e?.message || '提交失败')
      } finally { if (!this.hidden && operation === this.writeSeq && generation === currentSessionGeneration()) this.submitting = false }
    },
    withdraw(item) {
      if (!this.recordAllowsApplication || this.hidden || item?.status!=='PENDING_REVIEW' || this.conflict || this.submitting) return
      uni.showModal({
        title: '撤回申请', content: '确认撤回该待审核申请？',
        success: async (result) => {
          if (!result.confirm) return
          this.submitting = true
          try {
            await studentInternshipApplicationWithdraw(item.id, {
              ...this.context,
              expectedVersion: item.version
            })
            toast('已撤回')
            await this.load()
          }
          catch (e) { toast(e?.message || '撤回失败'); await this.load() }
          finally { this.submitting = false }
        }
      })
    }
  }
}
</script>

<style scoped>
.app__hint,.app__desc,.app__version { display:block;font-size:var(--font-size-base);color:var(--text-secondary);margin-top:var(--space-2);line-height:1.6; }
.app__section-title { margin:6px 0 2px;font-size:var(--font-size-md);font-weight:600;color:var(--text-primary); }
.app__field { display:flex;flex-direction:column;gap:6px;margin-bottom:var(--space-3); }
.app__grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-2); }
.app__label { font-size:var(--font-size-base);color:var(--text-secondary); }
.app__req { color:var(--danger-500); }
.app__input,.app__picker { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-base); }
.app__textarea { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;min-height:90px;width:100%;box-sizing:border-box;font-size:var(--font-size-base); }
.app__file { display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3); }
.app__hist { padding:var(--space-2) 0;border-bottom:1px solid var(--border-light);font-size:var(--font-size-base); }
.app__hist-note,.app__review { display:block;margin-top:4px;color:var(--text-secondary);font-size:var(--font-size-base); }
.app__review { color:var(--warning-700); }
.app__wd { margin-left:8px;font-size:var(--font-size-base);padding:4px 10px; }
.app__result-head{gap:12px;flex-wrap:wrap}.app__result .app__version{margin:0}.app__summary{display:flex;flex-direction:column;gap:12px}.app__summary-row{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.app__summary-row .app__label{flex-shrink:0}.app__value{font-size:var(--font-size-md);color:var(--text-primary);line-height:1.6;word-break:break-word}.app__summary-row .app__value{text-align:right}.app__details-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:44px;margin:0;padding:0;background:transparent;border:0;border-top:1px solid var(--border-light);border-radius:0;color:var(--text-link);font-size:var(--font-size-base)}.app__details-toggle::after{border:0}.app__details{padding-top:4px}.app__file{flex-wrap:wrap}.app__file .flex-1{min-width:120px;font-size:var(--font-size-base);line-height:1.6}
</style>
