<template>
  <view class="page-wrap">
    <!-- 工作台（列表模式）：顶部分区 tab + 各分区队列/列表 -->
    <template v-if="mode === 'list'">
      <view class="gg__tabs">
        <text v-for="t in tabs" :key="t.key" class="gg__tab" :class="{ 'is-active': tab === t.key }"
              @click="switchTab(t.key)">{{ t.label }}<text v-if="t.count" class="gg__tab-badge">{{ t.count }}</text></text>
      </view>

      <MobileGlobalState :state="state" @retry="load">
        <view class="page-pad" v-if="data">
          <!-- 批阅：开题 + 成果 队列 + 指导学生 -->
          <template v-if="tab === 'review'">
            <view class="gg__hub">
              <text class="gg__hub-link" @click="goPage('/pages/teacher/graduation-topics/index')">选题审核</text>
              <text class="gg__hub-sep">·</text>
              <text class="gg__hub-link" @click="goPage('/pages/teacher/graduation-taskbook/index')">任务书</text>
              <text class="gg__hub-sep">·</text>
              <text class="gg__hub-link" @click="goPage('/pages/teacher/defense-score/index')">答辩评分</text>
            </view>
            <view v-if="reviewQueue.length" class="gg__queue card" @click="enterReview('proposal', reviewQueue, 0)">
              <view class="row-between"><text class="t-md t-bold">开题待批阅</text><text class="gg__qc">{{ reviewQueue.length }} 条</text></view>
              <text class="gg__qh">逐条看背景/方案/成果，处理后自动下一条</text>
              <button class="gg__go" @click.stop="enterReview('proposal', reviewQueue, 0)">开始批阅开题</button>
            </view>
            <view v-if="finalQueue.length" class="gg__queue card" @click="enterReview('final', finalQueue, 0)">
              <view class="row-between"><text class="t-md t-bold">成果待批阅</text><text class="gg__qc">{{ finalQueue.length }} 条</text></view>
              <text class="gg__qh">逐条看论文类型/版本/查重/附件，查重超标不可通过</text>
              <button class="gg__go" @click.stop="enterReview('final', finalQueue, 0)">开始批阅成果</button>
            </view>
            <view class="gg__filters">
              <text class="gg__filter" :class="{ 'is-active': f === 'all' }" @click="f = 'all'">全部 {{ data.list.length }}</text>
              <text class="gg__filter" :class="{ 'is-active': f === 'review' }" @click="f = 'review'">待批阅 {{ pendingReviewCount }}</text>
              <text class="gg__filter" :class="{ 'is-active': f === 'overdue' }" @click="f = 'overdue'">已逾期 {{ overdueCount }}</text>
            </view>
            <view v-if="!filtered.length" class="gg__empty"><text>暂无指导学生</text></view>
            <view class="stack">
              <view v-for="g in filtered" :key="g.id" class="gg card">
                <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ g.name }}</text><text class="gg__cls">{{ g.className }}</text></view><MobileStatusTag :status="g.status" /></view>
                <text class="gg__topic">{{ g.topic }}</text>
                <view class="gg__meta"><text class="gg__node">当前节点 · {{ g.node }}</text><text class="gg__dl" :class="{ 'is-overdue': g.status === 'OVERDUE' }">截止 {{ g.deadline || '未设置' }}</text></view>
                <view class="gg__actions">
                  <button v-if="pIndexOf(g) >= 0" class="gg__go sm" @click.stop="enterReview('proposal', reviewQueue, pIndexOf(g))">去批阅开题</button>
                  <button v-if="fIndexOf(g) >= 0" class="gg__go sm" @click.stop="enterReview('final', finalQueue, fIndexOf(g))">去批阅成果</button>
                  <button class="btn btn-ghost" @click.stop="addGuidance(g)">记录指导</button>
                </view>
              </view>
            </view>
          </template>

          <!-- 中期检查队列 -->
          <template v-else-if="tab === 'midterm'">
            <view v-if="midtermError" class="gg__empty"><text>{{ midtermError }}</text></view>
            <view v-else-if="!midtermQueue.length" class="gg__empty"><text>暂无待检查/待复核整改</text></view>
            <view class="stack">
              <view v-for="(m, i) in midtermQueue" :key="m.gdStudentId" class="gg card" @click="enterReview('midterm', midtermQueue, i)">
                <view class="row-between"><text class="t-md t-bold">{{ m.studentName }}</text><text class="gg__st">{{ m.statusLabel }}</text></view>
                <text class="gg__cls">{{ m.studentNo }}</text>
                <button class="gg__go sm" @click.stop="enterReview('midterm', midtermQueue, i)">去处理</button>
              </view>
            </view>
          </template>

          <!-- 评阅任务 -->
          <template v-else-if="tab === 'peer'">
            <view v-if="reviewsError" class="gg__empty"><text>{{ reviewsError }}</text></view>
            <view v-else-if="!reviews.length" class="gg__empty"><text>暂无待评阅任务</text></view>
            <view class="stack">
              <view v-for="(r, i) in reviews" :key="r.id" class="gg card" @click="enterReview('peer', reviews, i)">
                <view class="row-between"><text class="t-md t-bold">{{ r.studentName }}</text><text class="gg__st">{{ r.statusLabel }}</text></view>
                <text class="gg__cls">{{ r.studentNo }} · 评阅人 {{ r.reviewerName }}</text>
                <button class="gg__go sm" @click.stop="enterReview('peer', reviews, i)">去评阅</button>
              </view>
            </view>
          </template>

          <!-- 答辩安排（只读）+ 评分入口 -->
          <template v-else-if="tab === 'defense'">
            <view v-if="defenseScorePending > 0" class="gg__queue card" @click="goPage('/pages/teacher/defense-score/index')">
              <view class="row-between"><text class="t-md t-bold">待录入答辩评分</text><text class="gg__qc">{{ defenseScorePending }} 条</text></view>
              <text class="gg__qh">本人担任评委的已发布答辩组学生，点此录入/更新评分</text>
              <button class="gg__go" @click.stop="goPage('/pages/teacher/defense-score/index')">去答辩评分</button>
            </view>
            <view v-if="defenseError" class="gg__empty"><text>{{ defenseError }}</text></view>
            <view v-else-if="!defense.length" class="gg__empty"><text>暂无答辩安排</text></view>
            <view class="stack">
              <view v-for="a in defense" :key="a.gdStudentId" class="gg card">
                <view class="row-between"><text class="t-md t-bold">{{ a.studentName }}</text><MobileStatusTag :status="a.published ? 'PUBLISHED' : 'PROCESSING'" /></view>
                <text class="gg__cls">{{ a.className }} · {{ a.topicTitle }}</text>
                <template v-if="a.published">
                  <text class="gg__di">{{ a.groupName }} · {{ a.date || '待定' }} · {{ a.location || '待定' }}</text>
                  <text class="gg__di">组长 {{ a.chair || '—' }} · 秘书 {{ a.secretary || '—' }}</text>
                  <text class="gg__di">评委 {{ (a.members || []).join('、') || '待安排' }}</text>
                </template>
                <text v-else class="gg__di gg__di--muted">{{ a.message || '答辩编制中，发布后可见时间地点评委' }}</text>
              </view>
            </view>
          </template>

          <!-- 成绩待复核队列 -->
          <template v-else-if="tab === 'grade'">
            <view v-if="gradeError" class="gg__empty"><text>{{ gradeError }}</text></view>
            <view v-else-if="!gradeQueue.length" class="gg__empty"><text>暂无待复核成绩</text></view>
            <view class="stack">
              <view v-for="(gr, i) in gradeQueue" :key="gr.gdStudentId" class="gg card" @click="enterReview('grade', gradeQueue, i)">
                <view class="row-between"><text class="t-md t-bold">{{ gr.studentName }}</text><text class="gg__st">{{ gr.statusLabel }}</text></view>
                <text class="gg__cls">{{ gr.studentNo }} · 综合 {{ gr.totalScore }} 分（{{ gr.gradeLevel || '—' }}）</text>
                <button class="gg__go sm" @click.stop="enterReview('grade', gradeQueue, i)">去复核</button>
              </view>
            </view>
          </template>
        </view>
      </MobileGlobalState>
    </template>

    <!-- 单页队列处理（开题/成果/中期/评阅/成绩） -->
    <view v-else class="rv">
      <view class="rv__head">
        <text class="rv__back" @click="exitReview">‹ 返回</text>
        <text class="rv__progress">{{ kindLabel }} · 第 {{ queueIndex + 1 }} / {{ queue.length }} 条</text>
        <text class="rv__side"></text>
      </view>
      <scroll-view scroll-y class="rv__body">
        <MobileGlobalState :state="detailState" @retry="loadDetail">
          <view v-if="detail" class="rv__content">
            <text class="rv__stu">{{ detail.studentName }}<text v-if="detail.className"> · {{ detail.className }}</text></text>
            <text v-if="detail.topicTitle" class="rv__topic">{{ detail.topicTitle }}</text>

            <!-- 开题 -->
            <template v-if="reviewKind === 'proposal'">
              <view class="rv__tags"><text class="rv__tag">版本 {{ detail.version || '—' }}</text><text v-if="detail.isResubmit" class="rv__tag rv__tag--warn">重交</text><text class="rv__tag">提交 {{ detail.submitAt || '—' }}</text></view>
              <view class="rv__block"><text class="rv__label">选题背景</text><text class="rv__text">{{ detail.background || '（未填写）' }}</text></view>
              <view class="rv__block"><text class="rv__label">研究方案与进度</text><text class="rv__text">{{ detail.plan || '（未填写）' }}</text></view>
              <view class="rv__block"><text class="rv__label">预期成果</text><text class="rv__text">{{ detail.outcome || '（未填写）' }}</text></view>
            </template>

            <!-- 成果 -->
            <template v-else-if="reviewKind === 'final'">
              <view class="rv__tags"><text class="rv__tag">{{ detail.type }} {{ detail.version }}</text><text class="rv__tag" :class="detail.plagiarismTone === 'danger' ? 'rv__tag--warn' : ''">查重 {{ detail.plagiarismRate }}</text><text class="rv__tag">提交 {{ detail.submitAt || '—' }}</text></view>
              <view class="rv__block"><text class="rv__label">查重状态</text><text class="rv__text">{{ detail.plagiarismStatus }}<text v-if="detail.plagiarismTone === 'danger'" class="rv__warn"> · 超标，须退回修改（GD-R09）</text></text></view>
            </template>

            <!-- 中期 -->
            <template v-else-if="reviewKind === 'midterm'">
              <view class="rv__tags"><text class="rv__tag">{{ detail.statusLabel }}</text><text v-if="detail.conclusionLabel" class="rv__tag">{{ detail.conclusionLabel }}</text></view>
              <view v-if="detail.checkComment" class="rv__block"><text class="rv__label">上次检查意见</text><text class="rv__text">{{ detail.checkComment }}</text></view>
              <view v-if="detail.rectifyContent" class="rv__block"><text class="rv__label">学生整改内容</text><text class="rv__text">{{ detail.rectifyContent }}</text></view>
              <view v-if="detail.rectifyDeadline" class="rv__block"><text class="rv__label">整改截止</text><text class="rv__text">{{ detail.rectifyDeadline }}</text></view>
            </template>

            <!-- 评阅：内联评分 + 意见 -->
            <template v-else-if="reviewKind === 'peer'">
              <view class="rv__tags"><text class="rv__tag">{{ detail.statusLabel }}</text><text v-if="detail.score != null" class="rv__tag">原评分 {{ detail.score }}</text></view>
              <view class="rv__block"><text class="rv__label">评分（0-100）</text><input class="rv__input" type="number" v-model="peerScore" placeholder="请输入评分" /></view>
              <view class="rv__block">
                <text class="rv__label">评阅意见（≥5字）</text>
                <textarea class="rv__ta" v-model="peerOpinion" :maxlength="2000" placeholder="填写评阅意见" placeholder-class="rv__ph" />
                <view class="rv__chips">
                  <view v-for="(t, i) in PEER_OPINION_CHIPS" :key="i" class="rv__chip" @click="pickPeerOpinionChip(t)"><text>{{ t }}</text></view>
                </view>
              </view>
            </template>

            <!-- 成绩：三段构成 -->
            <template v-else-if="reviewKind === 'grade'">
              <view class="rv__tags"><text class="rv__tag">{{ detail.statusLabel }}</text><text class="rv__tag">{{ detail.gradeLevel || '—' }}</text></view>
              <view class="rv__grade">
                <view class="rv__gcell"><text class="rv__gnum">{{ fmt(detail.advisorScore) }}</text><text class="rv__glab">导师</text></view>
                <view class="rv__gcell"><text class="rv__gnum">{{ fmt(detail.reviewerScore) }}</text><text class="rv__glab">评阅</text></view>
                <view class="rv__gcell"><text class="rv__gnum">{{ fmt(detail.defenseScore) }}</text><text class="rv__glab">答辩</text></view>
                <view class="rv__gcell rv__gcell--total"><text class="rv__gnum">{{ fmt(detail.totalScore) }}</text><text class="rv__glab">综合</text></view>
              </view>
            </template>

            <!-- 通用：上次意见 + 历史版本 + 真实附件 -->
            <view v-if="detail.reviewComment" class="rv__block"><text class="rv__label">上次批阅/退回意见</text><text class="rv__text rv__text--warn">{{ detail.reviewComment }}</text></view>
            <view v-if="detail.versions && detail.versions.length > 1" class="rv__block"><text class="rv__label">历史版本</text><text v-for="(v, i) in detail.versions" :key="i" class="rv__ver">· {{ v.title }}<text v-if="v.desc"> — {{ v.desc }}</text></text></view>
            <view v-if="detail.attachmentsList && detail.attachmentsList.length" class="rv__block">
              <text class="rv__label">材料附件（点击下载）</text>
              <view v-for="a in detail.attachmentsList" :key="a.fileId" class="rv__att" @click="downloadAtt(a)"><text class="rv__att-name">📎 {{ a.fileName }}</text><text class="rv__att-dl">下载</text></view>
            </view>
          </view>
        </MobileGlobalState>
      </scroll-view>

      <!-- 底部固定操作区（按 kind + 状态动态） -->
      <view class="rv__foot">
        <button class="rv__nav" :disabled="queueIndex <= 0 || acting" @click="prev">上一条</button>
        <template v-if="reviewKind === 'proposal' || reviewKind === 'final'">
          <button class="rv__act rv__return" :disabled="!canAct" @click="doReview('reject')">退回</button>
          <button class="rv__act rv__pass" :disabled="!canAct" @click="doReview('pass')">通过</button>
        </template>
        <template v-else-if="reviewKind === 'midterm'">
          <template v-if="detail && detail.status === 'PENDING'">
            <button class="rv__act rv__return" :disabled="!canAct" @click="midterm('FAIL')">不通过</button>
            <button class="rv__act rv__warn2" :disabled="!canAct" @click="midterm('RECTIFY')">需整改</button>
            <button class="rv__act rv__pass" :disabled="!canAct" @click="midterm('PASS')">通过</button>
          </template>
          <template v-else-if="detail && detail.status === 'RECTIFY_SUBMITTED'">
            <button class="rv__act rv__return" :disabled="!canAct" @click="midtermRectify('FAIL')">整改不通过</button>
            <button class="rv__act rv__pass" :disabled="!canAct" @click="midtermRectify('PASS')">整改通过</button>
          </template>
          <text v-else class="rv__readonly">当前状态无需处理</text>
        </template>
        <template v-else-if="reviewKind === 'peer'">
          <button class="rv__act rv__pass" :disabled="acting || detailState !== 'ready'" @click="submitPeer">提交评阅</button>
        </template>
        <template v-else-if="reviewKind === 'grade'">
          <button class="rv__act rv__return" :disabled="!canAct" @click="gradeReview('RETURN')">退回</button>
          <button class="rv__act rv__pass" :disabled="!canAct" @click="gradeReview('APPROVE')">复核通过</button>
        </template>
        <button class="rv__nav" :disabled="queueIndex >= queue.length - 1 || acting" @click="next">下一条</button>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { go, toast } from '@/utils/nav'
import { ENV } from '@/config/env'
import { getToken } from '@/services/request'

const KIND_LABEL = { proposal: '开题批阅', final: '成果批阅', midterm: '中期检查', peer: '评阅', grade: '成绩复核' }
const TAB_KEYS = ['review', 'midterm', 'peer', 'defense', 'grade']
const PEER_OPINION_CHIPS = ['格式不符合毕业设计课程标准', '内容深度不足，需修改', '疑似抄袭，建议复核查重']

export default {
  data() {
    return {
      PEER_OPINION_CHIPS,
      data: null, state: 'loading', f: 'all', acting: false,
      reviewQueue: [], finalQueue: [],
      tab: 'review', midtermQueue: [], reviews: [], defense: [], gradeQueue: [],
      midtermError: '', reviewsError: '', defenseError: '', gradeError: '',
      defenseScorePending: 0,
      loaded: { midterm: false, peer: false, defense: false, grade: false },
      mode: 'list', reviewKind: '', queue: [], queueIndex: 0, detail: null, detailState: 'loading',
      peerScore: '', peerOpinion: '',
      _bootKind: '' // onLoad ?kind=proposal|final → 数据就绪后自动进入对应批阅队列
    }
  },
  onLoad(options) {
    const tab = String((options && options.tab) || '').toLowerCase()
    if (TAB_KEYS.includes(tab)) this.tab = tab
    const kind = String((options && options.kind) || '').toLowerCase()
    if (kind === 'proposal' || kind === 'final') this._bootKind = kind
    this.load()
    if (this.tab !== 'review') this.switchTab(this.tab)
  },
  onShow() { if (this._entered) { if (this.mode === 'list') this.reloadTab() } this._entered = true },
  onPullDownRefresh() {
    if (this.state === 'loading' || this.mode !== 'list') { uni.stopPullDownRefresh(); return }
    this.reloadTab(() => uni.stopPullDownRefresh())
  },
  computed: {
    tabs() {
      return [
        { key: 'review', label: '批阅', count: this.pendingReviewCount },
        { key: 'midterm', label: '中期', count: this.midtermQueue.length },
        { key: 'peer', label: '评阅', count: this.reviews.length },
        { key: 'defense', label: '答辩', count: this.defenseScorePending },
        { key: 'grade', label: '成绩', count: this.gradeQueue.length }
      ]
    },
    pendingReviewCount() { return this.reviewQueue.length + this.finalQueue.length },
    filtered() {
      if (!this.data) return []
      if (this.f === 'review') {
        const ids = new Set([
          ...this.reviewQueue.map((q) => q.gdStudentId),
          ...this.finalQueue.map((q) => q.gdStudentId)
        ])
        return this.data.list.filter((g) => ids.has(g.id))
      }
      if (this.f === 'overdue') return this.data.list.filter((g) => g.status === 'OVERDUE')
      return this.data.list
    },
    overdueCount() { return this.data ? this.data.list.filter((g) => g.status === 'OVERDUE').length : 0 },
    current() { return this.queue[this.queueIndex] || null },
    kindLabel() { return KIND_LABEL[this.reviewKind] || '处理' },
    canAct() { return !this.acting && !!this.detail && this.detailState === 'ready' }
  },
  methods: {
    toast,
    goPage(url) { go(url) },
    load(done) {
      if (!this.data) this.state = 'loading'
      teacherApi.getGdStudents().then((d) => {
        this.data = d
        this.reviewQueue = (d && d.reviewQueue) || []
        this.finalQueue = (d && d.finalQueue) || []
        this.state = 'ready'
        // 预取各分区待办计数，让 tab 徽标准确（静默失败，不阻塞主界面）
        this.loadMidterm(); this.loadReviews(); this.loadGrade(); this.loadDefenseScorePending()
        this._maybeBootReview()
      }).catch(() => { if (!this.data) this.state = 'error' }).finally(() => { if (done) done() })
    },
    _maybeBootReview() {
      const kind = this._bootKind
      if (!kind || this.mode !== 'list') return
      this._bootKind = ''
      const q = kind === 'final' ? this.finalQueue : this.reviewQueue
      if (q && q.length) this.enterReview(kind, q, 0)
    },
    switchTab(k) {
      this.tab = k
      if (k === 'midterm' && !this.loaded.midterm) this.loadMidterm()
      else if (k === 'peer' && !this.loaded.peer) this.loadReviews()
      else if (k === 'defense' && !this.loaded.defense) this.loadDefense()
      else if (k === 'grade' && !this.loaded.grade) this.loadGrade()
    },
    reloadTab(done) {
      // 返回/下拉：刷新当前 tab 数据（批阅始终刷 getGdStudents）
      this.load()
      const map = { midterm: this.loadMidterm, peer: this.loadReviews, defense: this.loadDefense, grade: this.loadGrade }
      if (map[this.tab]) map[this.tab].call(this, done)
      else if (done) done()
    },
    loadMidterm(done) {
      teacherApi.getGraduationMidtermQueue().then((r) => {
        this.midtermQueue = r || []; this.loaded.midterm = true; this.midtermError = ''
      }).catch(() => { this.midtermError = '中期队列加载失败' }).finally(() => done && done())
    },
    loadReviews(done) {
      teacherApi.getGraduationMyReviews().then((r) => {
        this.reviews = r || []; this.loaded.peer = true; this.reviewsError = ''
      }).catch(() => { this.reviewsError = '评阅队列加载失败' }).finally(() => done && done())
    },
    loadDefense(done) {
      teacherApi.getGraduationDefenseArrangements().then((r) => {
        this.defense = r || []; this.loaded.defense = true; this.defenseError = ''
      }).catch(() => { this.defenseError = '答辩安排加载失败' }).finally(() => {
        this.loadDefenseScorePending(done)
      })
    },
    loadDefenseScorePending(done) {
      teacherApi.getGraduationDefenseScorePending().then((r) => {
        const list = r || []
        this.defenseScorePending = list.filter((x) => x.myStatus === 'PENDING').length
      }).catch(() => { /* 非评委身份常见，不挡主流程 */ }).finally(() => done && done())
    },
    loadGrade(done) {
      teacherApi.getGraduationGradeQueue().then((r) => {
        this.gradeQueue = r || []; this.loaded.grade = true; this.gradeError = ''
      }).catch(() => { this.gradeError = '成绩队列加载失败' }).finally(() => done && done())
    },
    pIndexOf(g) { return this.reviewQueue.findIndex((q) => q.gdStudentId === g.id) },
    fIndexOf(g) { return this.finalQueue.findIndex((q) => q.gdStudentId === g.id) },
    enterReview(kind, queueArr, index) {
      if (!queueArr || !queueArr.length) { toast('暂无待处理项'); return }
      this.reviewKind = kind
      this.queue = queueArr
      this.queueIndex = Math.max(0, Math.min(index, queueArr.length - 1))
      this.mode = 'review'
      this.loadDetail()
    },
    exitReview() {
      this.mode = 'list'; this.detail = null; this.detailState = 'loading'
      this.peerScore = ''; this.peerOpinion = ''
      this.reloadTab()
    },
    pickPeerOpinionChip(t) {
      this.peerOpinion = this.peerOpinion ? this.peerOpinion + '\n' + t : t
    },
    curId() {
      const it = this.current || {}
      if (this.reviewKind === 'proposal') return it.proposalId
      if (this.reviewKind === 'final') return it.finalId
      return it.gdStudentId // midterm / grade
    },
    loadDetail() {
      const it = this.current
      if (!it) { this.detailState = 'empty'; return }
      this.peerScore = ''; this.peerOpinion = ''
      // 评阅任务：列表行即详情（含 score/opinion），无独立详情接口
      if (this.reviewKind === 'peer') {
        this.detail = { ...it }
        if (it.status === 'RETURNED') { this.peerScore = it.score != null ? String(it.score) : ''; this.peerOpinion = it.opinion || '' }
        this.detailState = 'ready'
        return
      }
      this.detailState = 'loading'; this.detail = null
      const api = {
        proposal: () => teacherApi.getGraduationProposalDetail(it.proposalId),
        final: () => teacherApi.getGraduationFinalDetail(it.finalId),
        midterm: () => teacherApi.getGraduationMidtermDetail(it.gdStudentId),
        grade: () => teacherApi.getGraduationGradeDetail(it.gdStudentId)
      }[this.reviewKind]
      api().then((d) => { this.detail = d; this.detailState = 'ready' })
        .catch((e) => { this.detailState = 'error'; toast(normalizeError(e).text) })
    },
    prev() { if (this.queueIndex > 0) { this.queueIndex--; this.loadDetail() } },
    next() { if (this.queueIndex < this.queue.length - 1) { this.queueIndex++; this.loadDetail() } },
    afterAction() {
      this.queue.splice(this.queueIndex, 1)
      // 同步移除对应外层队列引用（queue 就是外层数组引用，splice 已同步）
      if (!this.queue.length) { this.exitReview(); return }
      if (this.queueIndex > this.queue.length - 1) this.queueIndex = this.queue.length - 1
      this.loadDetail()
    },
    _confirm(title, placeholder, minLen, fn) {
      uni.showModal({ title, editable: true, placeholderText: placeholder, success: (r) => {
        if (!r.confirm || this.acting) return
        const c = (r.content || '').trim()
        if (minLen && c.length < minLen) { toast(`需填写至少 ${minLen} 字`); return }
        this.acting = true
        fn(c).then(() => { this.afterAction() })
          .catch((e) => {
            if (String(e && e.code).startsWith('409')) { toast('该项已处理，正在刷新'); this.afterAction() }
            else { toast(normalizeError(e).text) }
          }).finally(() => { this.acting = false })
      } })
    },
    doReview(type) {
      if (!this.canAct) return
      const id = this.curId()
      const submit = (c) => this.reviewKind === 'final'
        ? teacherApi.reviewFinal(id, type === 'pass' ? 'APPROVE' : 'REJECT', c)
        : teacherApi.reviewProposal(id, type === 'pass' ? 'APPROVE' : 'REJECT', c)
      if (type === 'pass') {
        this.acting = true
        submit('').then(() => { toast('已通过'); this.afterAction() })
          .catch((e) => { toast(normalizeError(e).text) }).finally(() => { this.acting = false })
      } else {
        this._confirm('退回', '请填写退回意见（至少 5 字）', 5, (c) => submit(c).then(() => toast('已退回')))
      }
    },
    midterm(conclusion) {
      if (!this.canAct) return
      const id = this.curId()
      const need = conclusion !== 'PASS' ? 5 : 0
      this._confirm(conclusion === 'PASS' ? '中期通过' : conclusion === 'RECTIFY' ? '要求整改' : '中期不通过',
        conclusion === 'PASS' ? '可填写意见（选填）' : '请填写意见（至少 5 字）', need,
        (c) => teacherApi.midtermCheck(id, conclusion, c).then(() => toast('已提交')))
    },
    midtermRectify(action) {
      if (!this.canAct) return
      const id = this.curId()
      this._confirm(action === 'PASS' ? '整改通过' : '整改不通过',
        action === 'PASS' ? '可填写意见（选填）' : '请填写意见（至少 5 字）', action === 'PASS' ? 0 : 5,
        (c) => teacherApi.midtermRectifyReview(id, action, c).then(() => toast('复核完成')))
    },
    gradeReview(action) {
      if (!this.canAct) return
      const id = this.curId()
      if (action === 'APPROVE') {
        this.acting = true
        teacherApi.reviewGrade(id, 'APPROVE', '').then(() => { toast('复核通过'); this.afterAction() })
          .catch((e) => { toast(normalizeError(e).text) }).finally(() => { this.acting = false })
      } else {
        this._confirm('退回成绩', '请填写退回原因（至少 5 字）', 5, (c) => teacherApi.reviewGrade(id, 'RETURN', c).then(() => toast('已退回')))
      }
    },
    submitPeer() {
      if (this.acting || this.detailState !== 'ready') return
      const it = this.current
      const score = Number(this.peerScore)
      if (!(score >= 0 && score <= 100)) { toast('评分须为 0-100'); return }
      if (this.peerOpinion.trim().length < 5) { toast('评阅意见至少 5 字'); return }
      this.acting = true
      teacherApi.submitReview(it.id, Math.round(score), this.peerOpinion.trim())
        .then(() => { toast('评阅已提交'); this.afterAction() })
        .catch((e) => { toast(normalizeError(e).text) }).finally(() => { this.acting = false })
    },
    downloadAtt(a) {
      const url = ENV.apiBaseUrl + ENV.apiPrefix + a.downloadUrl.replace(ENV.apiPrefix, '')
      const token = getToken()
      uni.showLoading({ title: '下载中' })
      uni.downloadFile({
        url, header: token ? { Authorization: 'Bearer ' + token } : {},
        success: (res) => {
          uni.hideLoading()
          if (res.statusCode !== 200) { toast('下载失败或无权限'); return }
          // #ifdef H5
          try { const link = document.createElement('a'); link.href = res.tempFilePath; link.download = a.fileName; link.click() } catch (e) { toast('已下载') }
          // #endif
          // #ifndef H5
          uni.openDocument({ filePath: res.tempFilePath, showMenu: true, fail: () => toast('已下载，暂无法预览此类型') })
          // #endif
        },
        fail: () => { uni.hideLoading(); toast('下载失败，请检查网络') }
      })
    },
    addGuidance(g) {
      if (this.acting) return
      if (!/^\d+$/.test(String(g.id))) { toast('当前为离线数据，无法记录指导'); return }
      uni.showModal({ title: '记录指导', editable: true, placeholderText: '填写本次指导内容', success: (r) => {
        if (!r.confirm || this.acting) return
        if (!r.content || r.content.trim().length < 2) { toast('指导内容至少 2 字'); return }
        this.acting = true
        teacherApi.createGuidance(g.id, { content: r.content.trim(), method: 'ONLINE' })
          .then(() => { toast('已记录') }).catch((e) => { toast(normalizeError(e).text) }).finally(() => { this.acting = false })
      } })
    },
    fmt(v) { return (v == null || v === '') ? '—' : v }
  }
}
</script>

<style scoped>
.gg__tabs { display: flex; gap: 4px; padding: var(--space-2) var(--page-padding-mobile); background: var(--bg-card); border-bottom: 1px solid var(--border-light); overflow-x: auto; }
.gg__tab { flex-shrink: 0; padding: 6px 12px; border-radius: var(--radius-full); font-size: var(--font-size-sm); color: var(--text-secondary); }
.gg__tab.is-active { background: var(--teacher-600); color: #fff; }
.gg__tab-badge { margin-left: 4px; font-size: var(--font-size-xs); }
.gg__hub { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-bottom: var(--space-3); font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gg__hub-link { color: var(--teacher-700); }
.gg__hub-sep { color: var(--text-tertiary); }
.gg__queue { background: var(--teacher-50, var(--primary-50)); border: 1px solid var(--teacher-200, var(--primary-100)); }
.gg__qc { font-size: var(--font-size-sm); color: var(--teacher-700); font-weight: var(--font-weight-semibold); }
.gg__qh { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-2) 0 var(--space-3); }
.gg__filters { display: flex; gap: var(--space-2); margin: var(--space-4) 0; }
.gg__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.gg__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.gg__empty { padding: var(--space-6) 0; text-align: center; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gg__cls { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.gg__st { font-size: var(--font-size-sm); color: var(--teacher-700); }
.gg__topic { display: block; font-size: var(--font-size-base); color: var(--text-primary); margin: var(--space-2) 0; line-height: 1.4; }
.gg__meta { display: flex; justify-content: space-between; }
.gg__node { font-size: var(--font-size-sm); color: var(--teacher-700); }
.gg__dl { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gg__dl.is-overdue { color: var(--danger-600); }
.gg__di { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }
.gg__di--muted { color: var(--text-tertiary); }
.gg__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.gg__go { min-height: 40px; border-radius: var(--radius-md); border: none; background: var(--teacher-600); color: #fff; font-size: var(--font-size-md); padding: 0 var(--space-4); margin-top: var(--space-2); }
.gg__go.sm { min-height: 38px; margin-top: 0; }
.gg__go::after { border: none; }
.rv { position: fixed; inset: 0; background: var(--bg-page, var(--gray-50)); display: flex; flex-direction: column; z-index: var(--z-modal, 100); }
.rv__head { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; padding: calc(var(--space-3) + env(safe-area-inset-top)) var(--page-padding-mobile) var(--space-3); background: var(--bg-card); border-bottom: 1px solid var(--border-light); }
.rv__back { font-size: var(--font-size-base); color: var(--teacher-700); min-width: 56px; }
.rv__progress { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rv__side { min-width: 56px; }
.rv__body { flex: 1; overflow-y: auto; }
.rv__content { padding: var(--page-padding-mobile); }
.rv__stu { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rv__topic { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin: 6px 0 var(--space-3); line-height: 1.4; }
.rv__tags { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-4); }
.rv__tag { font-size: var(--font-size-xs); color: var(--text-secondary); background: var(--gray-100, var(--gray-50)); padding: 3px 10px; border-radius: var(--radius-full); }
.rv__tag--warn { color: var(--danger-600); background: var(--danger-50); }
.rv__block { background: var(--bg-card); border-radius: var(--radius-md); padding: var(--space-3); margin-bottom: var(--space-3); }
.rv__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: 4px; }
.rv__text { display: block; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; }
.rv__text--warn { color: var(--danger-600); }
.rv__warn { color: var(--danger-600); }
.rv__ver { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; line-height: 1.5; }
.rv__input { height: 44px; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); font-size: var(--font-size-base); box-sizing: border-box; }
.rv__ta { width: 100%; min-height: 80px; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); font-size: var(--font-size-base); box-sizing: border-box; }
.rv__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.rv__chip { border: 1px dashed var(--border-base); border-radius: var(--radius-full); padding: 4px var(--space-3); }
.rv__chip text { font-size: var(--font-size-xs); color: var(--text-secondary); }
.rv__att { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.rv__att:last-child { border-bottom: none; }
.rv__att-name { font-size: var(--font-size-base); color: var(--text-primary); }
.rv__att-dl { font-size: var(--font-size-sm); color: var(--teacher-600); }
.rv__grade { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.rv__gcell { flex: 1; background: var(--bg-card); border-radius: var(--radius-md); padding: var(--space-3) 0; text-align: center; }
.rv__gcell--total { background: var(--teacher-50, var(--primary-50)); }
.rv__gnum { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rv__glab { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.rv__foot { flex-shrink: 0; display: flex; gap: var(--space-2); align-items: center; padding: var(--space-3) var(--page-padding-mobile) calc(var(--space-3) + env(safe-area-inset-bottom)); background: var(--bg-card); border-top: 1px solid var(--border-light); }
.rv__nav { flex-shrink: 0; min-height: 42px; padding: 0 var(--space-3); border-radius: var(--radius-md); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-sm); }
.rv__nav::after { border: none; }
.rv__nav[disabled] { opacity: 0.4; }
.rv__act { flex: 1; min-height: 42px; border-radius: var(--radius-md); border: none; font-size: var(--font-size-md); }
.rv__act::after { border: none; }
.rv__return { background: var(--bg-card); color: var(--danger-600); border: 1px solid var(--danger-500); }
.rv__warn2 { background: var(--warning-50); color: var(--warning-700); border: 1px solid var(--warning-500); }
.rv__pass { background: var(--teacher-600); color: #fff; }
.rv__act[disabled] { opacity: 0.5; }
.rv__readonly { flex: 1; text-align: center; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.rv__ph { color: var(--text-placeholder, #9ca3af); }
</style>
