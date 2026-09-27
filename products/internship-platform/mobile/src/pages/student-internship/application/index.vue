<template>
  <view class="page-wrap app">
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card">
          <text class="card-title">正式实习申请</text>
          <text class="app__hint">选择学校已发布岗位，或提交自主实习单位及真实证明材料。无需手填岗位ID或文件ID。</text>
        </view>
        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看申请记录，不可新增、提交或撤回。" />
        <MobileInlineAlert v-if="editableApplication?.status === 'REJECTED'" type="warning" title="申请已驳回" :description="editableApplication.reviewComment || '请修改后重新提交。'" />

        <view v-if="!historyMode" class="card stack">
          <view class="app__field">
            <text class="app__label">申请类型</text>
            <picker mode="selector" :range="typeLabels" :value="typeIndex" @change="onTypePick">
              <view class="app__picker">{{ typeLabels[typeIndex] }}</view>
            </picker>
          </view>
          <view v-if="isPosition" class="app__field">
            <text class="app__label">实习岗位 <text class="app__req">*</text></text>
            <picker mode="selector" :range="positionLabels" :value="positionIndex" @change="onPositionPick">
              <view class="app__picker">{{ positionLabels[positionIndex] || '请选择学校已发布岗位' }}</view>
            </picker>
            <text v-if="selectedPosition" class="app__desc">{{ selectedPosition.companyName }} · {{ selectedPosition.workLocation || '地点待定' }} · 剩余 {{ selectedPosition.remaining }} 人</text>
          </view>
          <template v-else>
            <MobileInlineAlert
              type="info"
              title="企业登记核验"
              :description="registryHint"
            />
            <view class="app__section-title">企业信息</view>
            <view class="app__field"><text class="app__label">企业名称 <text class="app__req">*</text></text><input v-model.trim="form.companyName" class="app__input" placeholder="请输入企业全称" /></view>
            <view class="app__field"><text class="app__label">统一社会信用代码 <text class="app__req">*</text></text><input v-model.trim="form.companyCreditCode" class="app__input" maxlength="18" placeholder="18位统一社会信用代码" /></view>
            <view class="app__field"><text class="app__label">企业负责人 <text class="app__req">*</text></text><input v-model.trim="form.companyPrincipal" class="app__input" placeholder="负责人姓名" /></view>
            <view class="app__field"><text class="app__label">企业规模 <text class="app__req">*</text></text><picker mode="selector" :range="companyScaleOptions" :value="companyScaleIndex" @change="onCompanyScalePick"><view class="app__picker">{{ form.companyScale || '请选择企业规模' }}</view></picker></view>
            <view class="app__field"><text class="app__label">企业联系电话 <text class="app__req">*</text></text><input v-model.trim="form.companyPhone" class="app__input" placeholder="企业联系电话" /></view>
            <view class="app__field"><text class="app__label">企业邮箱 <text class="app__req">*</text></text><input v-model.trim="form.companyEmail" class="app__input" placeholder="name@example.com" /></view>
            <view class="app__field"><text class="app__label">单位性质 <text class="app__req">*</text></text><picker mode="selector" :range="companyNatureOptions" :value="companyNatureIndex" @change="onCompanyNaturePick"><view class="app__picker">{{ form.companyNature || '请选择单位性质' }}</view></picker></view>
            <view class="app__field"><text class="app__label">所属行业 <text class="app__req">*</text></text><picker mode="selector" :range="industryOptions" :value="industryIndex" @change="onIndustryPick"><view class="app__picker">{{ form.companyIndustry || '请选择所属行业' }}</view></picker></view>
            <view class="app__field"><text class="app__label">单位所在地区 <text class="app__req">*</text></text><picker mode="region" @change="onCompanyRegionPick"><view class="app__picker">{{ companyRegionText || '请选择省 / 市 / 区县' }}</view></picker></view>
            <view class="app__field"><text class="app__label">单位注册地址 <text class="app__req">*</text></text><input v-model.trim="form.companyRegisteredAddress" class="app__input" placeholder="请输入详细注册地址" /></view>
            <view class="app__field"><text class="app__label">邮编</text><input v-model.trim="form.companyPostalCode" class="app__input" placeholder="企业邮编（可选）" /></view>
            <view class="app__field"><text class="app__label">单位联系人 <text class="app__req">*</text></text><input v-model.trim="form.contactName" class="app__input" placeholder="联系人姓名" /></view>
            <view class="app__field"><text class="app__label">联系人电话 <text class="app__req">*</text></text><input v-model.trim="form.contactPhone" class="app__input" placeholder="联系人电话" /></view>

            <view class="app__section-title">岗位与实习信息</view>
            <view class="app__field"><text class="app__label">实习部门 <text class="app__req">*</text></text><input v-model.trim="form.internshipDepartment" class="app__input" placeholder="所属科室 / 部门" /></view>
            <view class="app__field"><text class="app__label">岗位名称 <text class="app__req">*</text></text><input v-model.trim="form.positionName" class="app__input" placeholder="实习岗位名称" /></view>
            <view class="app__field"><text class="app__label">岗位类别 <text class="app__req">*</text></text><picker mode="selector" :range="positionCategoryOptions" :value="positionCategoryIndex" @change="onPositionCategoryPick"><view class="app__picker">{{ form.positionCategory || '请选择岗位类别' }}</view></picker></view>
            <view class="app__field"><text class="app__label">工作内容 <text class="app__req">*</text></text><textarea v-model="form.workContent" class="app__textarea" maxlength="4000" placeholder="简要说明主要工作内容" /></view>
            <view class="app__field"><text class="app__label">企业老师 <text class="app__req">*</text></text><input v-model.trim="form.enterpriseMentorName" class="app__input" placeholder="企业带教老师姓名" /></view>
            <view class="app__field"><text class="app__label">企业老师电话 <text class="app__req">*</text></text><input v-model.trim="form.enterpriseMentorPhone" class="app__input" placeholder="企业老师联系电话" /></view>
            <view class="app__field"><text class="app__label">实习国家（地区）</text><input v-model.trim="form.workCountry" class="app__input" placeholder="默认中国" /></view>
            <view class="app__field"><text class="app__label">岗位所在地区 <text class="app__req">*</text></text><picker mode="region" @change="onWorkRegionPick"><view class="app__picker">{{ workRegionText || '请选择省 / 市 / 区县' }}</view></picker></view>
            <view class="app__field"><text class="app__label">岗位详细地址 <text class="app__req">*</text></text><input v-model.trim="form.workAddress" class="app__input" placeholder="请输入实习岗位详细地址" /></view>
            <view class="app__grid">
              <view class="app__field"><text class="app__label">开始日期 <text class="app__req">*</text></text><picker mode="date" :value="form.internshipStartDate" @change="form.internshipStartDate = $event.detail.value"><view class="app__picker">{{ form.internshipStartDate || '请选择' }}</view></picker></view>
              <view class="app__field"><text class="app__label">结束日期 <text class="app__req">*</text></text><picker mode="date" :value="form.internshipEndDate" @change="form.internshipEndDate = $event.detail.value"><view class="app__picker">{{ form.internshipEndDate || '请选择' }}</view></picker></view>
            </view>
            <view class="app__field"><text class="app__label">实习方式 <text class="app__req">*</text></text><picker mode="selector" :range="internshipModeOptions" :value="internshipModeIndex" @change="onInternshipModePick"><view class="app__picker">{{ form.internshipMode || '请选择实习方式' }}</view></picker></view>
            <view class="app__field"><text class="app__label">是否专业对口 <text class="app__req">*</text></text><picker mode="selector" :range="majorMatchOptions" :value="majorMatchIndex" @change="onMajorMatchPick"><view class="app__picker">{{ majorMatchText }}</view></picker></view>
            <view class="app__field"><text class="app__label">约定实习薪资（元/月） <text class="app__req">*</text></text><input v-model.trim="form.agreedSalary" class="app__input" type="digit" placeholder="例如 2500" /></view>

            <view class="app__file">
              <view class="flex-1"><text class="app__label">自主实习证明 <text class="app__req">*</text></text><text class="app__desc">{{ evidenceFileName || (form.evidenceFileId ? '已上传证明材料' : '请上传企业接收函、协议或盖章证明') }}</text></view>
              <button class="btn btn-ghost" :disabled="uploading" @click="pickEvidence">{{ uploading ? '上传中…' : (form.evidenceFileId ? '重新上传' : '选择文件') }}</button>
            </view>
            <view class="app__file">
              <view class="flex-1"><text class="app__label">三方协议照片</text><text class="app__desc">{{ form.agreementFileIds.length ? ('已上传 ' + form.agreementFileIds.length + ' 份') : '可上传协议照片或扫描件，最多9份' }}</text></view>
              <button class="btn btn-ghost" :disabled="uploading" @click="pickAgreement">{{ uploading ? '上传中…' : '添加协议' }}</button>
            </view>
          </template>
          <view class="app__field"><text class="app__label">申请说明 <text class="app__req">*</text></text><textarea v-model="form.applicationNote" class="app__textarea" maxlength="500" placeholder="说明申请原因和岗位匹配情况（至少5字）" /></view>
        </view>

        <view v-if="history.length" class="card">
          <text class="card-title">我的申请</text>
          <view v-for="item in history" :key="item.id" class="app__hist">
            <view class="row-between">
              <view class="flex-1"><text>{{ item.applicationTypeLabel }} · {{ item.statusLabel }}</text><text class="app__hist-note">{{ item.positionName || item.companyName || item.applicationNote || '' }}</text></view>
              <button v-if="item.status === 'PENDING_REVIEW' && !historyMode" class="btn btn-ghost app__wd" :disabled="submitting" @click="withdraw(item)">撤回</button>
            </view>
            <text v-if="item.reviewComment" class="app__review">审核意见：{{ item.reviewComment }}</text>
            <text class="app__version">版本 {{ item.version }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="pageState === 'ready' && !historyMode && !pendingApplication">
      <button class="btn btn-ghost flex-1" :disabled="submitting || uploading" @click="saveDraft">保存草稿</button>
      <button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : '提交审核' }}</button>
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
import { toast } from '@/utils/nav'

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
  data() {
    return {
      pageState: 'loading', submitting: false, uploading: false, historyMode: false,
      context: {},
      typeIndex: 0, typeLabels: TYPES.map((x) => x.label), positions: [], positionIndex: 0,
      evidenceFileName: '', history: [], editableApplication: null,
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
    isPosition() { return TYPES[this.typeIndex].value === 'POSITION' },
    positionLabels() { return this.positions.map((x) => `${x.title} · ${x.companyName} · 剩余${x.remaining}人`) },
    selectedPosition() { return this.positions[this.positionIndex] || null },
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
  onLoad() { this.load() },
  methods: {
    onTypePick(e) { this.typeIndex = Number(e.detail.value) || 0; this.editableApplication = null },
    onPositionPick(e) { this.positionIndex = Number(e.detail.value) || 0 },
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
      this.pageState = 'loading'
      try {
        const [rows, library, dashboard] = await Promise.all([
          studentInternshipApplications(), studentApi.getInternshipEnterprises(), studentApi.getInternship()
        ])
        this.history = Array.isArray(rows) ? rows : rows?.items || []
        this.context = {
          batchId: dashboard?.batchId || '',
          internshipId: dashboard?.recordId || dashboard?.internshipId || ''
        }
        this.positions = (library?.items || []).filter((x) => Number(x.remaining || 0) > 0)
        this.historyMode = !!dashboard?.historyMode
        const editable = this.history.find((x) => ['DRAFT', 'REJECTED', 'WITHDRAWN'].includes(x.status)) || null
        this.editableApplication = editable
        if (editable) this.fillEditable(editable)
        this.pageState = 'ready'
      } catch (e) { this.pageState = 'error' }
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
        const positionIndex = this.positions.findIndex((x) => String(x.id) === String(item.positionId))
        if (positionIndex >= 0) this.positionIndex = positionIndex
      }
      this.evidenceFileName = item.evidenceFileId ? '已上传证明材料' : ''
    },
    async pickEvidence() {
      if (this.uploading) return
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
      if (this.uploading) return
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
      if (this.isPosition) return this.selectedPosition ? '' : '请选择实习岗位'
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
    async saveDraft() {
      if (this.submitting) return
      this.submitting = true
      try {
        await studentInternshipApplicationSave(this.payload())
        toast('草稿已保存')
        await this.load()
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') { toast('申请版本已变化，正在刷新'); await this.load() }
        else toast(e?.message || '保存失败')
      } finally { this.submitting = false }
    },
    async submit() {
      if (this.submitting) return
      const error = this.validate()
      if (error) return toast(error)
      this.submitting = true
      try {
        const saved = await studentInternshipApplicationSave(this.payload())
        await studentInternshipApplicationSubmit(saved.id, {
          ...this.context,
          expectedVersion: saved.version
        })
        toast('申请已提交审核')
        await this.load()
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') { toast('申请状态已变化，正在刷新'); await this.load() }
        else toast(e?.message || '提交失败')
      } finally { this.submitting = false }
    },
    withdraw(item) {
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
.app__hint,.app__desc,.app__version { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:var(--space-2); }
.app__section-title { margin:6px 0 2px;font-size:var(--font-size-md);font-weight:600;color:var(--text-primary); }
.app__field { display:flex;flex-direction:column;gap:6px;margin-bottom:var(--space-3); }
.app__grid { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-2); }
.app__label { font-size:var(--font-size-sm);color:var(--text-secondary); }
.app__req { color:var(--danger-500); }
.app__input,.app__picker { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-sm); }
.app__textarea { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;min-height:90px;width:100%;box-sizing:border-box;font-size:var(--font-size-sm); }
.app__file { display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3); }
.app__hist { padding:var(--space-2) 0;border-bottom:1px solid var(--border-light);font-size:var(--font-size-sm); }
.app__hist-note,.app__review { display:block;margin-top:4px;color:var(--text-tertiary);font-size:var(--font-size-xs); }
.app__review { color:var(--warning-700); }
.app__wd { margin-left:8px;font-size:12px;padding:4px 10px; }
</style>
