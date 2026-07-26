<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? '转介详情' : '心理关注'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <MobileInlineAlert type="info" title="明细受限"
          description="列表仅显示等级与关注状态；查看明细必须填写原因并成功写入敏感访问审计。" />

        <view class="section-head">
          <text class="section-head__title">关注名单</text>
          <text class="section-head__more" @click="toggleForm">{{ showForm ? '收起' : '+ 登记转介' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <picker mode="selector" :range="students" range-key="label" @change="onStudentChange">
            <view class="mt__input">{{ selectedStudentLabel }}</view>
          </picker>
          <picker mode="selector" :range="levelOptions" range-key="label" @change="onLevelChange">
            <view class="mt__input">{{ levelLabel }}</view>
          </picker>
          <textarea class="mt__textarea" v-model="form.reasonSummary" :maxlength="200"
                    placeholder="转介事由摘要（必填，不少于5字，不含诊断结论）" placeholder-class="mt__ph" />
          <button class="btn btn-primary" :disabled="creating || !canCreate" @click="createReferral">
            {{ creating ? '登记中…' : '登记转介' }}
          </button>
          <text class="mt__hint">系统不做自动诊断，等级与事由均由授权人员人工登记。</text>
        </view>

        <MobileGlobalState v-if="!list.length" state="empty" title="暂无关注名单" description="当前授权范围内暂无心理关注记录。" />
        <view class="list-group" v-else>
          <view v-for="r in list" :key="r.referralId" class="list-row" @click="openDetail(r)">
            <view class="flex-1">
              <text class="t-md">{{ r.realName }}</text>
              <text class="mt__sub">{{ r.studentNo }}</text>
            </view>
            <text class="mt__level" :class="'is-' + (r.level || 'GENERAL').toLowerCase()">{{ r.levelLabel }}</text>
            <MobileStatusTag :label="r.statusLabel" :type="statusTag(r.status)" />
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="active">
        <text class="mt__back" @click="active = null">‹ 返回列表</text>
        <view class="card">
          <view class="row-between">
            <text class="t-lg t-bold">{{ active.realName }}</text>
            <text class="mt__level" :class="'is-' + (active.level || 'GENERAL').toLowerCase()">{{ active.levelLabel }}</text>
          </view>
          <text class="mt__sub">{{ active.studentNo }} · {{ active.statusLabel }}</text>
        </view>

        <template v-if="active.noteMasked">
          <view class="section-head"><text class="section-head__title">查看明细需填写原因</text></view>
          <view class="card stack-sm">
            <input class="mt__input" v-model="viewReason" placeholder="查看原因（≥5字，将被审计留痕）" placeholder-class="mt__ph" />
            <button class="btn btn-primary" :disabled="viewReason.trim().length < 5" @click="revealDetail">查看明细</button>
          </view>
        </template>
        <template v-else>
          <view class="section-head"><text class="section-head__title">转介事由</text></view>
          <view class="card"><text class="mt__text">{{ active.reasonSummary }}</text></view>
          <view class="section-head"><text class="section-head__title">明细记录</text></view>
          <view class="card"><text class="mt__text">{{ active.note || '（无附加明细）' }}</text></view>

          <template v-if="active.status !== 'CLOSED'">
            <view class="section-head"><text class="section-head__title">处理</text></view>
            <view class="card stack-sm">
              <textarea class="mt__textarea" v-model="actionContent" :maxlength="300" placeholder="记录内容（回访/升级/结论）" placeholder-class="mt__ph" />
              <button class="btn btn-ghost" :disabled="acting || actionContent.trim().length < 5" @click="doFollow">回访（≥5字）</button>
              <button class="btn btn-ghost mt__danger" :disabled="acting" @click="doEscalate">升级为危机（接入风险中枢）</button>
              <button class="btn btn-ghost" :disabled="acting || actionContent.trim().length < 5" @click="doClose">关闭（结论≥5字）</button>
            </view>
          </template>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const LEVEL_OPTS = [{ value: 'GENERAL', label: '一般关注' }, { value: 'FOCUS', label: '重点关注' }, { value: 'CRISIS', label: '危机' }]
const STATUS_TAG = { REFERRED: 'warning', FOLLOWING: 'processing', ESCALATED: 'danger', CLOSED: 'success' }

export default {
  data() {
    return {
      state: 'loading', loaded: false, all: [], showForm: false, creating: false,
      form: { studentId: '', level: 'FOCUS', reasonSummary: '' }, students: [],
      active: null, viewReason: '', actionContent: '', acting: false, levelOptions: LEVEL_OPTS
    }
  },
  computed: {
    list() { return this.all },
    levelLabel() {
      const o = LEVEL_OPTS.find((x) => x.value === this.form.level)
      return o ? o.label : '选择等级'
    },
    selectedStudentLabel() {
      const s = this.students.find((x) => String(x.studentId) === String(this.form.studentId))
      return s ? s.label : '选择授权范围内学生'
    },
    canCreate() { return this.form.studentId && this.form.reasonSummary.trim().length >= 5 }
  },
  onLoad() { this.load() },
  methods: {
    statusTag(s) { return STATUS_TAG[s] || 'default' },
    showError(e, fallback) {
      const n = normalizeError(e)
      toast(n.text || (e && e.message) || fallback)
      if (n.kind === 'conflict') this.reloadActive()
    },
    toggleForm() {
      this.showForm = !this.showForm
      if (this.showForm && !this.students.length) this.loadCandidates()
    },
    loadCandidates() {
      affairsContractApi.getStudentCandidates('MENTAL').then((d) => {
        this.students = ((d && d.items) || []).map((x) => ({ ...x, label: `${x.name} · ${x.className || x.studentNo}` }))
        if (!this.students.length) toast('当前心理专项授权范围内暂无学生')
      }).catch((e) => this.showError(e, '候选学生加载失败'))
    },
    onStudentChange(e) {
      const s = this.students[Number(e.detail.value)]
      this.form.studentId = s ? s.studentId : ''
    },
    onLevelChange(e) { this.form.level = LEVEL_OPTS[e.detail.value].value },
    load() {
      this.state = 'loading'
      teacherApi.getMentalList().then((d) => {
        this.all = (d && d.items) || []
        this.loaded = true
        this.state = 'ready'
      }).catch((e) => {
        this.state = 'error'
        this.showError(e, '心理关注加载失败')
      })
    },
    createReferral() {
      if (this.creating || !this.canCreate) return
      this.creating = true
      teacherApi.createMentalReferral({
        studentId: this.form.studentId, level: this.form.level, reasonSummary: this.form.reasonSummary.trim()
      }).then(() => {
        toast('转介已登记')
        this.showForm = false
        this.form = { studentId: '', level: 'FOCUS', reasonSummary: '' }
        this.load()
      }).catch((e) => this.showError(e, '登记失败'))
        .finally(() => { this.creating = false })
    },
    openDetail(r) {
      this.viewReason = ''
      this.actionContent = ''
      teacherApi.getMentalDetail(r.referralId).then((d) => { this.active = d })
        .catch((e) => this.showError(e, '详情加载失败'))
    },
    reloadActive() {
      if (!this.active || !this.active.referralId) return this.load()
      teacherApi.getMentalDetail(this.active.referralId).then((d) => { this.active = d }).catch(() => this.load())
    },
    revealDetail() {
      if (this.viewReason.trim().length < 5) return
      teacherApi.getMentalDetail(this.active.referralId, this.viewReason.trim())
        .then((d) => { this.active = d })
        .catch((e) => this.showError(e, '查看失败'))
    },
    version() {
      if (this.active.version === undefined || this.active.version === null) {
        toast('记录缺少版本号，请重新打开详情')
        return null
      }
      return this.active.version
    },
    doFollow() {
      if (this.acting || this.actionContent.trim().length < 5) return
      const version = this.version()
      if (version === null) return
      this.acting = true
      affairsContractApi.followMental(this.active.referralId, this.actionContent.trim(), version).then((d) => {
        toast('回访已记录')
        this.active = d
        this.actionContent = ''
      }).catch((e) => this.showError(e, '操作失败'))
        .finally(() => { this.acting = false })
    },
    doEscalate() {
      if (this.acting) return
      const version = this.version()
      if (version === null) return
      uni.showModal({
        title: '确认升级为危机', content: '将接入风险中枢并生成危机记录，请谨慎操作', success: (r) => {
          if (!r.confirm) return
          this.acting = true
          affairsContractApi.escalateMental(this.active.referralId, this.actionContent.trim(), version).then((d) => {
            toast('已升级')
            this.active = d
          }).catch((e) => this.showError(e, '操作失败'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doClose() {
      if (this.acting || this.actionContent.trim().length < 5) return
      const version = this.version()
      if (version === null) return
      this.acting = true
      affairsContractApi.closeMental(this.active.referralId, this.actionContent.trim(), version).then((d) => {
        toast('已关闭')
        this.active = d
      }).catch((e) => this.showError(e, '操作失败'))
        .finally(() => { this.acting = false })
    }
  }
}
</script>

<style scoped>
.mt__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.mt__level { flex-shrink: 0; font-size: var(--font-size-xs); font-weight: 700; padding: 2px 10px; border-radius: var(--radius-full); margin-right: var(--space-2); color: #fff; }
.mt__level.is-general { background: var(--gray-400); }
.mt__level.is-focus { background: #f97316; }
.mt__level.is-crisis { background: var(--danger-600); }
.mt__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.mt__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.mt__ph { color: var(--text-tertiary); }
.mt__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.mt__back { display: inline-block; font-size: var(--font-size-sm); color: var(--teacher-700); margin-bottom: var(--space-3); }
.mt__text { display: block; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.mt__danger { color: var(--danger-600); border-color: var(--danger-600); }
</style>
