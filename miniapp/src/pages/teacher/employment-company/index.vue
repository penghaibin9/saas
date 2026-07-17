<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="企业岗位库" subtitle="企业 · 岗位维护" show-back />

    <view class="ec__tabs">
      <view class="ec__tab" :class="{ 'is-on': tab === 'company' }" @click="switchTab('company')">
        企业<text v-if="companies.length" class="ec__tab-badge">{{ companies.length }}</text>
        <text v-if="tab === 'company'" class="ec__tab-u" />
      </view>
      <view class="ec__tab" :class="{ 'is-on': tab === 'job' }" @click="switchTab('job')">
        岗位<text v-if="jobs && jobs.length" class="ec__tab-badge">{{ jobs.length }}</text>
        <text v-if="tab === 'job'" class="ec__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 企业 -->
      <view class="page-pad" v-if="tab === 'company'">
        <view class="section-head">
          <text class="section-head__title">企业列表</text>
          <text class="section-head__more" @click="showCompanyForm = !showCompanyForm">{{ showCompanyForm ? '收起' : '+ 新增企业' }}</text>
        </view>

        <view v-if="showCompanyForm" class="card ec__form">
          <view class="ec__row"><text class="ec__row-k">企业名称</text><input class="ec__input" v-model="cf.name" placeholder="必填" /></view>
          <view class="ec__row"><text class="ec__row-k">信用代码</text><input class="ec__input" v-model="cf.creditCode" placeholder="必填，统一社会信用代码" /></view>
          <view class="ec__row"><text class="ec__row-k">所属行业</text><input class="ec__input" v-model="cf.industry" placeholder="可选" /></view>
          <view class="ec__row"><text class="ec__row-k">所在城市</text><input class="ec__input" v-model="cf.city" placeholder="可选" /></view>
          <view class="ec__btns">
            <button class="ec__btn-ghost" :disabled="submitting" @click="showCompanyForm = false">取消</button>
            <button class="ec__btn-primary" :disabled="submitting" @click="submitCompany">{{ submitting ? '提交中…' : '确认新增' }}</button>
          </view>
        </view>

        <MobileGlobalState v-if="!showCompanyForm && !companies.length" state="empty" title="暂无企业" description="点击「+ 新增企业」登记合作企业。" />
        <view v-else-if="!showCompanyForm" class="stack">
          <view v-for="c in companies" :key="c.id" class="card ec">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ c.name }}</text>
                <text class="ec__sub">{{ c.industry || '行业未填' }} · {{ c.city || '城市未填' }} · 在招{{ c.jobCount || 0 }}岗</text>
              </view>
              <MobileStatusTag :label="c.statusLabel || c.status" :type="c.status === 'ACTIVE' ? 'success' : 'default'" />
            </view>
            <view v-if="c.status === 'ACTIVE'" class="ec__actions">
              <button class="ec__btn-danger flex-1" :disabled="acting" @click="disableCompany(c)">停用</button>
            </view>
          </view>
        </view>
      </view>

      <!-- 岗位 -->
      <view class="page-pad" v-if="tab === 'job'">
        <view class="section-head">
          <text class="section-head__title">岗位列表</text>
          <text class="section-head__more" @click="openJobForm">{{ showJobForm ? '收起' : '+ 新增岗位' }}</text>
        </view>

        <view v-if="showJobForm" class="card ec__form">
          <view class="ec__row">
            <text class="ec__row-k">所属企业</text>
            <picker class="ec__picker" mode="selector" :range="companyLabels" :value="jf.companyIndex" @change="(e) => jf.companyIndex = Number(e.detail.value)">
              <view class="ec__pick-val">{{ companyLabels[jf.companyIndex] || '请选择' }}<text class="ec__arrow">▾</text></view>
            </picker>
          </view>
          <view class="ec__row"><text class="ec__row-k">岗位名称</text><input class="ec__input" v-model="jf.title" placeholder="必填" /></view>
          <view class="ec__row"><text class="ec__row-k">薪资范围</text><input class="ec__input" v-model="jf.salaryRange" placeholder="可选，如 6-8K" /></view>
          <view class="ec__row"><text class="ec__row-k">招聘人数</text><input class="ec__input" type="number" v-model="jf.headcount" placeholder="默认1" /></view>
          <view class="ec__btns">
            <button class="ec__btn-ghost" :disabled="submitting" @click="showJobForm = false">取消</button>
            <button class="ec__btn-primary" :disabled="submitting" @click="submitJob">{{ submitting ? '提交中…' : '确认新增' }}</button>
          </view>
        </view>

        <MobileGlobalState v-if="!showJobForm && jobs && !jobs.length" state="empty" title="暂无岗位" description="点击「+ 新增岗位」发布招聘岗位。" />
        <view v-else-if="!showJobForm && jobs" class="stack">
          <view v-for="j in jobs" :key="j.id" class="card ec">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ j.title }}</text>
                <text class="ec__sub">{{ j.companyName }} · {{ j.salaryRange || '面议' }} · 招{{ j.headcount || 1 }}人</text>
              </view>
              <MobileStatusTag :label="j.statusLabel || j.status" :type="j.status === 'OPEN' ? 'success' : 'default'" />
            </view>
            <view v-if="j.status === 'OPEN'" class="ec__actions">
              <button class="ec__btn-danger flex-1" :disabled="acting" @click="disableJob(j)">停用</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      tab: 'company', state: 'loading', companies: [], jobs: null, acting: false, submitting: false,
      showCompanyForm: false, cf: { name: '', creditCode: '', industry: '', city: '' },
      showJobForm: false, jf: { companyIndex: 0, title: '', salaryRange: '', headcount: '' }
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    companyLabels() { return this.companies.map((c) => c.name) }
  },
  methods: {
    switchTab(t) {
      this.tab = t
      if (t === 'job' && !this.jobs) this.loadJobs()
    },
    load(done) {
      this.state = 'loading'
      teacherApi.getEmploymentCompanies().then((d) => {
        this.companies = (d && d.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    loadJobs() {
      teacherApi.getEmploymentJobs().then((d) => { this.jobs = (d && d.list) || [] }).catch(() => { this.jobs = [] })
    },
    submitCompany() {
      if (this.submitting) return
      if (!this.cf.name.trim() || !this.cf.creditCode.trim()) { toast('企业名称与信用代码必填'); return }
      this.submitting = true
      teacherApi.createEmploymentCompany({
        name: this.cf.name.trim(), creditCode: this.cf.creditCode.trim(),
        industry: this.cf.industry.trim() || null, city: this.cf.city.trim() || null
      }).then(() => {
        toast('已新增'); this.showCompanyForm = false
        this.cf = { name: '', creditCode: '', industry: '', city: '' }
        this.load()
      }).catch((e) => toast((e && e.message) || '新增失败，请重试'))
        .finally(() => { this.submitting = false })
    },
    disableCompany(c) {
      if (this.acting) return
      uni.showModal({
        title: '停用企业', editable: true, placeholderText: '请填写停用原因（≥5字，将级联关闭其岗位）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('停用原因至少 5 个字'); return }
          this.acting = true
          teacherApi.disableEmploymentCompany(c.id, reason)
            .then(() => { toast('已停用'); this.load(); this.jobs = null })
            .catch((e) => toast((e && e.message) || '停用失败，请重试'))
            .finally(() => { this.acting = false })
        }
      })
    },
    openJobForm() {
      this.showJobForm = !this.showJobForm
      if (this.showJobForm && !this.companies.length) {
        teacherApi.getEmploymentCompanies('ACTIVE').then((d) => { this.companies = (d && d.list) || [] }).catch(() => {})
      }
    },
    submitJob() {
      if (this.submitting) return
      const company = this.companies[this.jf.companyIndex]
      if (!company) { toast('请先选择所属企业'); return }
      if (!this.jf.title.trim()) { toast('请填写岗位名称'); return }
      this.submitting = true
      teacherApi.createEmploymentJob({
        companyId: company.id, title: this.jf.title.trim(),
        salaryRange: this.jf.salaryRange.trim() || null,
        headcount: this.jf.headcount ? Number(this.jf.headcount) : 1
      }).then(() => {
        toast('已新增'); this.showJobForm = false
        this.jf = { companyIndex: 0, title: '', salaryRange: '', headcount: '' }
        this.loadJobs()
      }).catch((e) => toast((e && e.message) || '新增失败，请重试'))
        .finally(() => { this.submitting = false })
    },
    disableJob(j) {
      if (this.acting) return
      uni.showModal({
        title: '停用岗位', editable: true, placeholderText: '请填写停用原因（≥5字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('停用原因至少 5 个字'); return }
          this.acting = true
          teacherApi.disableEmploymentJob(j.id, reason)
            .then(() => { toast('已停用'); this.loadJobs() })
            .catch((e) => toast((e && e.message) || '停用失败，请重试'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ec__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ec__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ec__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ec__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ec__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--teacher-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ec { display: flex; flex-direction: column; gap: var(--space-2); }
.ec__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ec__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ec__btn-danger { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ec__btn-danger::after { border: none; }
.ec__form { display: flex; flex-direction: column; }
.ec__row { display: flex; align-items: center; gap: var(--space-3); min-height: 44px; border-bottom: 1px solid var(--border-light); }
.ec__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 64px; flex-shrink: 0; }
.ec__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ec__picker { flex: 1; }
.ec__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ec__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.ec__btns { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.ec__btn-ghost { flex: 1; min-height: var(--touch-target-min); border-radius: var(--radius-md); border: 1px solid var(--border-default); background: var(--bg-card); color: var(--text-secondary); }
.ec__btn-ghost::after { border: none; }
.ec__btn-primary { flex: 1; min-height: var(--touch-target-min); border-radius: var(--radius-md); border: none; background: var(--teacher-600); color: #fff; }
.ec__btn-primary::after { border: none; }
</style>
