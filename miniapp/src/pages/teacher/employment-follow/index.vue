<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data" class="page-pad stack">
        <view class="ef__stats card">
          <view class="ef__stat"><text class="ef__stat-val">{{ data.stats.total || 0 }}</text><text class="ef__stat-label">就业台账</text></view>
          <view class="ef__stat"><text class="ef__stat-val is-warn">{{ data.stats.unemployed || 0 }}</text><text class="ef__stat-label">未就业</text></view>
          <view class="ef__stat"><text class="ef__stat-val">{{ data.stats.pendingVerification || 0 }}</text><text class="ef__stat-label">待核验</text></view>
          <view class="ef__stat"><text class="ef__stat-val is-good">{{ data.stats.verified || 0 }}</text><text class="ef__stat-label">已核验</text></view>
        </view>

        <MobileSegmented :items="data.tabs || []" v-model="tab" />

        <MobileGlobalState v-if="!filtered.length" state="empty" title="暂无学生" description="切换其他分类查看。" />
        <view v-else class="stack-sm">
          <view v-for="s in pagedSlice(filtered)" :key="s.id" class="ef card">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ s.name }}</text>
                <text class="ef__class">{{ s.className || '—' }}</text>
              </view>
              <MobileStatusTag :label="s.verifyLabel || s.destinationLabel" />
            </view>
            <view class="ef__info">
              <text class="ef__info-item">{{ s.destinationLabel || '待就业' }}</text>
              <text v-if="s.companyName" class="ef__info-item">{{ s.companyName }}</text>
              <text v-if="s.jobTitle" class="ef__info-item">{{ s.jobTitle }}</text>
            </view>
            <view class="ef__last">
              <text class="ef__last-label">跟进 {{ s.followUpCount || 0 }} 次</text>
              <text class="ef__last-text flex-1">{{ s.lastFollowUpTime ? s.lastFollowUpTime.slice(0, 10) : '暂无最近跟进' }}</text>
            </view>
            <view class="ef__actions">
              <text class="ef__btn" @click="contact(s)">跟进联系</text>
              <text v-if="s.group === 'unemployed'"
                    class="ef__btn" :class="{ 'is-primary': canAct(s, 'recommend'), 'is-disabled': !canAct(s, 'recommend') }"
                    @click="recommend(s)">推荐岗位</text>
              <text v-if="s.group === 'verify'"
                    class="ef__btn" :class="{ 'is-primary': canAct(s, 'verify'), 'is-disabled': !canAct(s, 'verify') }"
                    @click="openVerification(s)">去向核验</text>
            </view>
          </view>
          <view v-if="pagedFooter(filtered) === 'more'" class="ef__paging" @click="pagedLoadMore">上拉加载更多</view>
          <view v-else-if="pagedFooter(filtered) === 'end'" class="ef__paging is-end">没有更多了</view>
        </view>

        <view v-if="verification" class="verify card">
          <view class="row-between">
            <view>
              <text class="t-lg t-bold">去向核验 · {{ verification.student.name }}</text>
              <text class="verify__sub">版本 {{ verification.version }} · {{ verifyLabel(verification.status) }}</text>
            </view>
            <text class="verify__close" @click="closeVerification">关闭</text>
          </view>

          <view class="verify__dest">
            <text class="t-md t-bold">{{ verification.destination.companyName || '未登记单位' }}</text>
            <text class="verify__sub">{{ verification.destination.jobTitle || verification.destination.type || '—' }}</text>
          </view>

          <view class="section-head"><text class="section-head__title">核验材料</text></view>
          <view v-if="verification.materials && verification.materials.length" class="stack-sm">
            <view v-for="m in verification.materials" :key="m.id" class="material">
              <view class="row-between">
                <view class="flex-1">
                  <text class="t-md">{{ materialLabel(m.materialType) }}</text>
                  <text class="verify__sub">{{ m.fileName || '尚未绑定正式文件' }} · {{ m.status }}</text>
                </view>
                <MobileStatusTag :label="m.formalEvidence ? '正式证据' : '缺正式证据'" :type="m.formalEvidence ? 'success' : 'warning'" />
              </view>
              <text v-if="m.legacyFileNameOnly" class="material__warn">历史文件名仅供识别，不能作为核验依据。</text>
              <view v-if="m.formalEvidence && m.file" class="ef__actions">
                <text class="ef__btn" @click="previewMaterial(m)">安全预览</text>
              </view>
              <view v-else class="material__picker">
                <MobileAttachmentPicker
                  :file-ids="pendingEvidenceIds[String(m.id)] || []"
                  biz-purpose="EMPLOYMENT_MATERIAL"
                  label="上传正式核验材料"
                  :max-count="1"
                  :max-size-mb="10"
                  :disabled="acting || bindingMaterialId === String(m.id)"
                  @update:fileIds="setEvidenceFileIds(m, $event)"
                  @update:ready="setEvidenceReady(m, $event)"
                  @error="attachmentError"
                />
                <text class="verify__sub">上传只产生 TEMP_PRIVATE；扫描通过后由就业材料命令按当前版本创建正式 FileBinding。</text>
                <text v-if="bindingMaterialId === String(m.id)" class="verify__sub">正在绑定正式材料证据…</text>
              </view>
            </view>
          </view>
          <MobileGlobalState v-else state="empty" title="暂无就业材料" description="没有材料时不能核验通过。" />

          <view v-if="verification.history && verification.history.length">
            <view class="section-head"><text class="section-head__title">核验历史</text></view>
            <view class="stack-sm">
              <view v-for="h in verification.history" :key="h.id" class="history">
                <text class="t-sm t-bold">{{ h.action }}</text>
                <text class="verify__sub">{{ h.detail || '无补充意见' }} · {{ h.operator || '系统' }}</text>
              </view>
            </view>
          </view>

          <view class="verify__actions">
            <text class="verify__btn is-return" @click="reviewVerification('RETURN')">退回补正</text>
            <text class="verify__btn is-verify" :class="{ 'is-disabled': !verification.allowedActions.verify }"
                  @click="reviewVerification('VERIFY')">核验通过</text>
          </view>
          <text v-if="!verification.allowedActions.verify && verification.disabledReason" class="material__warn">{{ verification.disabledReason }}</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { teacherEmploymentV3Api } from '@/services/teacherEmploymentV3Api'
import { fileSdk } from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { listPaging } from '@/utils/listPaging'
import { toast } from '@/utils/nav'

const MATERIAL_LABEL = {
  AGREEMENT: '就业协议', CONTRACT: '劳动合同', OFFER: '录用通知', STUDY_PROOF: '升学证明',
  ENLIST_PROOF: '入伍证明', STARTUP_PROOF: '创业证明', OTHER: '其他材料'
}
const VERIFY_LABEL = { PENDING_VERIFY: '待核验', VERIFIED: '已核验', RETURNED: '已退回补正' }
const TAB_KEYS = new Set(['unemployed', 'following', 'verify', 'done'])

export default {
  mixins: [listPaging(20)],
  data() {
    return {
      data: null,
      state: 'loading',
      tab: 'unemployed',
      acting: false,
      verification: null,
      verificationStudentId: '',
      pendingEvidenceIds: {},
      pendingEvidenceReady: {},
      bindingMaterialId: '',
      prefillPending: false,
      prefillStudent: null,
      fromStudent360: false
    }
  },
  onLoad(q) {
    const requestedTab = String((q && q.tab) || '').trim()
    if (TAB_KEYS.has(requestedTab)) this.tab = requestedTab
    const employmentStudentId = q && q.mode === 'follow' ? String(q.employmentStudentId || '').trim() : ''
    if (employmentStudentId) {
      this.prefillStudent = { id: employmentStudentId, name: q.studentName ? decodeURIComponent(q.studentName) : '当前学生' }
      this.prefillPending = true
      this.fromStudent360 = true
    }
    this.load()
  },
  onReachBottom() { this.pagedReachBottom() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  watch: { tab() { this.pagedReset() } },
  computed: {
    filtered() {
      if (!this.data) return []
      return (this.data.list || []).filter((s) => s.group === this.tab)
    }
  },
  methods: {
    pagingList() { return this.filtered },
    materialLabel(type) { return MATERIAL_LABEL[type] || type || '就业材料' },
    verifyLabel(status) { return VERIFY_LABEL[status] || status || '待核验' },
    canAct(student, action) { return Boolean(student && student.allowedActions && student.allowedActions[action]) },
    disabledReason(student, action) {
      return (student && student.disabledReason && student.disabledReason[action]) || '当前状态不可执行'
    },
    load(done) {
      this.state = 'loading'
      this.pagedReset()
      teacherEmploymentV3Api.overview().then((d) => {
        this.data = d
        this.state = 'ready'
        if (this.prefillPending && this.prefillStudent) {
          const target = ((d && d.list) || []).find((item) => String(item.id) === String(this.prefillStudent.id)) || this.prefillStudent
          this.prefillPending = false
          setTimeout(() => this.contact(target), 80)
        }
      }).catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    handleError(e, refreshVerification = false) {
      const n = normalizeError(e)
      toast(n.text)
      if (n.kind === 'conflict') {
        this.load()
        if (refreshVerification && this.verificationStudentId) this.fetchVerification(this.verificationStudentId)
      }
    },
    contact(s) {
      if (this.acting) return
      uni.showModal({
        title: '记录跟进 · ' + (s.name || '学生'), editable: true,
        placeholderText: '填写本次联系内容',
        success: (r) => {
          if (!r.confirm || this.acting) return
          const content = String(r.content || '').trim()
          if (content.length < 2) { toast('请填写跟进内容'); return }
          if (!/^\d+$/.test(String(s.id || ''))) { toast('当前学生缺少真实就业记录'); return }
          this.acting = true
          teacherApi.createFollowup({ studentId: s.id, way: 'PHONE', content })
            .then(() => {
              toast('跟进已记录')
              return this.load()
            })
            .then(() => {
              if (this.fromStudent360) setTimeout(() => uni.navigateBack(), 300)
            })
            .catch((e) => this.handleError(e))
            .finally(() => { this.acting = false })
        }
      })
    },
    recommend(s) {
      if (this.acting) return
      if (!this.canAct(s, 'recommend')) { toast(this.disabledReason(s, 'recommend')); return }
      const jobs = (this.data && this.data.jobs) || []
      if (!jobs.length) { toast('暂无可推荐在招岗位'); return }
      uni.showActionSheet({
        itemList: jobs.map((j) => `${j.companyName || '企业'} · ${j.title}`),
        success: ({ tapIndex }) => {
          const job = jobs[tapIndex]
          if (!job) return
          uni.showModal({
            title: `推荐 ${job.title}`, editable: true,
            placeholderText: '推荐理由（至少5字）',
            success: (r) => {
              if (!r.confirm || this.acting) return
              const reason = String(r.content || '').trim()
              if (reason.length < 5) { toast('推荐理由至少 5 字'); return }
              this.acting = true
              teacherEmploymentV3Api.recommend(s.id, {
                jobId: Number(job.id),
                reason,
                note: '',
                expectedStudentVersion: Number(s.version || 0)
              }).then(() => {
                toast('岗位推荐已记录')
                return this.load()
              }).catch((e) => this.handleError(e))
                .finally(() => { this.acting = false })
            }
          })
        }
      })
    },
    fetchVerification(studentId) {
      this.verificationStudentId = String(studentId || '')
      return teacherEmploymentV3Api.verification(studentId).then((d) => {
        this.verification = d
        return d
      }).catch((e) => {
        this.handleError(e)
        throw e
      })
    },
    openVerification(s) {
      if (!this.canAct(s, 'verify')) { toast(this.disabledReason(s, 'verify')); return }
      this.pendingEvidenceIds = {}
      this.pendingEvidenceReady = {}
      this.bindingMaterialId = ''
      this.fetchVerification(s.id).catch(() => {})
    },
    closeVerification() {
      this.verification = null
      this.verificationStudentId = ''
      this.pendingEvidenceIds = {}
      this.pendingEvidenceReady = {}
      this.bindingMaterialId = ''
    },
    previewMaterial(m) {
      if (!m || !m.file || !m.file.fileId) { toast('当前材料没有可预览的正式证据'); return }
      fileSdk.open(m.file.fileId).catch((e) => this.handleError(e))
    },
    attachmentError(e) { this.handleError(e, true) },
    setEvidenceFileIds(m, ids) {
      const key = String(m && m.id || '')
      if (!key) return
      this.pendingEvidenceIds = {
        ...this.pendingEvidenceIds,
        [key]: (Array.isArray(ids) ? ids : []).map((id) => String(id)).filter(Boolean).slice(0, 1)
      }
      this.maybeBindEvidence(m)
    },
    setEvidenceReady(m, ready) {
      const key = String(m && m.id || '')
      if (!key) return
      this.pendingEvidenceReady = { ...this.pendingEvidenceReady, [key]: !!ready }
      this.maybeBindEvidence(m)
    },
    maybeBindEvidence(m) {
      const key = String(m && m.id || '')
      const ids = this.pendingEvidenceIds[key] || []
      if (!key || !ids.length || !this.pendingEvidenceReady[key]) return
      if (this.acting || this.bindingMaterialId) return
      this.bindingMaterialId = key
      this.acting = true
      teacherEmploymentV3Api.bindMaterialEvidence(m.id, {
        fileId: String(ids[0]),
        expectedVersion: Number(m.version || 0)
      }).then(() => {
        toast('正式材料证据已绑定')
        const nextIds = { ...this.pendingEvidenceIds }
        const nextReady = { ...this.pendingEvidenceReady }
        delete nextIds[key]
        delete nextReady[key]
        this.pendingEvidenceIds = nextIds
        this.pendingEvidenceReady = nextReady
        return this.fetchVerification(this.verificationStudentId)
      }).then(() => this.load())
        .catch((e) => this.handleError(e, true))
        .finally(() => {
          this.acting = false
          this.bindingMaterialId = ''
        })
    },
    reviewVerification(action) {
      if (!this.verification || this.acting) return
      if (action === 'VERIFY' && !this.verification.allowedActions.verify) {
        toast(this.verification.disabledReason || '当前材料不足以核验通过')
        return
      }
      const submit = (comment) => {
        this.acting = true
        teacherEmploymentV3Api.reviewVerification(this.verification.verificationId, {
          action,
          comment: String(comment || '').trim(),
          expectedVersion: Number(this.verification.version || 0)
        }).then(() => {
          toast(action === 'VERIFY' ? '去向已核验' : '已退回补正')
          return this.fetchVerification(this.verificationStudentId)
        }).then(() => this.load())
          .catch((e) => this.handleError(e, true))
          .finally(() => { this.acting = false })
      }
      if (action === 'RETURN') {
        uni.showModal({
          title: '退回补正', editable: true,
          placeholderText: '填写可执行补正意见（至少5字）',
          success: (r) => {
            if (!r.confirm) return
            const comment = String(r.content || '').trim()
            if (comment.length < 5) { toast('补正意见至少 5 字'); return }
            submit(comment)
          }
        })
        return
      }
      uni.showModal({ title: '确认核验通过？', content: '将按当前正式 FileBinding 材料确认学生去向。', success: (r) => { if (r.confirm) submit('') } })
    }
  }
}
</script>

<style scoped>
.ef__stats { display: flex; }
.ef__stat { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; }
.ef__stat-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); }
.ef__stat-val.is-warn { color: var(--warning-600); }
.ef__stat-val.is-good { color: var(--success-600); }
.ef__stat-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ef__class { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ef__info { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.ef__info-item { font-size: var(--font-size-sm); color: var(--text-secondary); background: var(--gray-100); padding: 2px 8px; border-radius: var(--radius-full); }
.ef__last { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.ef__last-label { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.ef__last-text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ef__actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); flex-wrap: wrap; }
.ef__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.ef__btn.is-primary { color: #fff; background: var(--teacher-600); border-color: var(--teacher-600); }
.is-disabled { opacity: .45; }
.ef__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.ef__paging.is-end { color: var(--text-tertiary); }
.verify { border: 1px solid var(--teacher-100); }
.verify__sub { display: block; margin-top: 3px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.verify__close { font-size: var(--font-size-sm); color: var(--teacher-700); padding: 6px; }
.verify__dest { padding: var(--space-3); margin-top: var(--space-3); background: var(--gray-50); border-radius: var(--radius-md); }
.material { padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); }
.material__picker { margin-top: var(--space-3); }
.material__warn { display: block; margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--warning-700); }
.history { padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.verify__actions { display: flex; gap: var(--space-3); margin-top: var(--space-4); }
.verify__btn { flex: 1; text-align: center; border-radius: var(--radius-md); padding: 10px 8px; font-size: var(--font-size-sm); }
.verify__btn.is-return { border: 1px solid var(--warning-400); color: var(--warning-700); }
.verify__btn.is-verify { background: var(--teacher-600); color: #fff; }
</style>