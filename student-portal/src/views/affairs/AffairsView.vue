<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 请假销假 -->
      <div v-if="tab === 'leave'" class="two">
        <section class="sp-card">
          <div class="sp-panel__head">请假申请</div>
          <div class="sp-fieldlabel">请假类型</div>
          <div style="display:flex;gap:8px;margin-bottom:12px">
            <button v-for="lt in leaveTypes" :key="lt.k" class="seg" :class="{ on: leaveForm.leaveType === lt.k }" @click="leaveForm.leaveType = lt.k">{{ lt.t }}</button>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">
            <div><div class="sp-fieldlabel">开始时间</div><input v-model="leaveForm.startDate" type="date" class="sp-inp" /></div>
            <div><div class="sp-fieldlabel">结束时间</div><input v-model="leaveForm.endDate" type="date" class="sp-inp" /></div>
          </div>
          <div class="sp-fieldlabel">请假事由</div>
          <textarea v-model.trim="leaveForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明请假原因" />
          <div style="display:flex;gap:10px">
            <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="print('请假条')">打印请假条</button>
            <button class="sp-btn" :disabled="busy || !leaveForm.reason" @click="applyLeave">提交请假</button>
          </div>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">请假 / 销假记录</div>
          <StateBlock v-if="!(leave.items||[]).length" type="empty" text="暂无请假记录" />
          <div v-for="(lv, i) in (leave.items || [])" :key="lv.leaveId || lv.id || i" style="padding:12px 0;border-bottom:1px solid #F4F5F7">
            <div style="display:flex;justify-content:space-between;gap:8px">
              <div>
                <div style="font-size:14px;font-weight:600">{{ lv.leaveTypeLabel || lv.leaveType || '请假' }}</div>
                <div class="sp-muted" style="margin-top:4px">{{ lv.affairsStatusLabel || lv.statusLabel || lv.status || '' }}</div>
                <div v-if="lv.returnReason" class="sp-muted" style="margin-top:4px;color:#b45309">退回意见：{{ lv.returnReason }}</div>
                <button
                  v-if="lv.canResubmit"
                  class="sp-btn sp-btn--ghost"
                  style="margin-top:8px"
                  :disabled="busy"
                  @click="resubmitLeave(lv)"
                >按退回意见修改后重新提交</button>
                <button
                  v-if="lv.canCancel"
                  class="sp-btn"
                  style="margin-top:8px;margin-left:8px"
                  :disabled="busy"
                  @click="cancelLeave(lv)"
                >申请销假</button>
                <button
                  v-if="lv.canExtend"
                  class="sp-btn sp-btn--ghost"
                  style="margin-top:8px;margin-left:8px"
                  :disabled="busy"
                  @click="openExtend(lv)"
                >申请续假</button>
              </div>
              <StatusTag :text="lv.affairsStatusLabel || lv.statusLabel || lv.status || '—'" tone="default" />
            </div>
            <div v-if="extendId === (lv.leaveId || lv.id)" style="margin-top:10px;padding:12px;background:#F8FAFC;border-radius:8px">
              <div class="sp-fieldlabel">新结束日期</div>
              <input v-model="extendForm.newEndTime" type="date" class="sp-inp" style="margin-bottom:8px" />
              <div class="sp-fieldlabel">续假事由（≥5字）</div>
              <textarea v-model.trim="extendForm.reason" class="sp-inp" style="margin-bottom:8px" placeholder="说明续假原因" />
              <button class="sp-btn" :disabled="busy || !extendForm.newEndTime || !(extendForm.reason || '').trim()" @click="submitExtend(lv)">提交续假</button>
              <button class="sp-btn sp-btn--ghost" style="margin-left:8px" :disabled="busy" @click="extendId = ''">取消</button>
            </div>
          </div>
        </section>
      </div>

      <!-- 困难认定 -->
      <section v-else-if="tab === 'aid'" class="sp-card">
        <div class="sp-panel__head">家庭经济困难认定申请 <StatusTag :text="aid.currentLevel || '未认定'" :tone="aid.currentLevel ? 'success' : 'default'" /></div>
        <Wizard :steps="['填写信息', '上传材料', '签署承诺书']" :current="aidStep" style="margin-bottom:20px" />
        <template v-if="aidStep === 1">
          <StateBlock v-if="!aidBatches.length" type="empty" text="当前暂无开放的困难认定批次，请等待学校发布后再来申请" />
          <div v-else style="display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:640px">
            <div style="grid-column:1/3"><div class="sp-fieldlabel">认定批次</div>
              <select v-model="aidForm.batchId" class="sp-inp">
                <option v-for="b in aidBatches" :key="b.batchId" :value="b.batchId">{{ b.batchName || b.schoolYear }}（截止 {{ (b.applyEnd || '').slice(0, 10) || '不限' }}）</option>
              </select></div>
            <div><div class="sp-fieldlabel">困难类型</div>
              <select v-model="aidForm.level" class="sp-inp"><option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option></select></div>
            <div><div class="sp-fieldlabel">家庭年收入(元)</div><input v-model.number="aidForm.income" type="number" class="sp-inp" placeholder="家庭年收入" /></div>
            <div style="grid-column:1/3"><div class="sp-fieldlabel">困难情况说明（10-500字）</div><textarea v-model.trim="aidForm.reason" class="sp-inp" placeholder="请说明家庭经济困难的具体情况" /></div>
          </div>
          <button v-if="aidBatches.length" class="sp-btn" style="margin-top:18px" :disabled="!aidForm.batchId || aidForm.reason.length < 10" @click="aidStep = 2">下一步：上传材料</button>
        </template>
        <template v-else-if="aidStep === 2">
          <p class="sp-muted">佐证材料（低保证明 / 村委证明等）请在提交后按学校要求补交，或在学生小程序上传。</p>
          <div style="display:flex;gap:10px;margin-top:16px"><button class="sp-btn sp-btn--ghost" @click="aidStep = 1">上一步</button><button class="sp-btn" @click="aidStep = 3">下一步：签署承诺书</button></div>
        </template>
        <template v-else>
          <div class="promise">本人郑重承诺：以上所填家庭经济情况真实、准确，如有虚报将承担相应责任，并配合学校核查。</div>
          <label class="chk"><input v-model="aidForm.commit" type="checkbox" />我已阅读并同意以上承诺（电子签，将记录签署时间）</label>
          <div style="display:flex;gap:10px;margin-top:12px"><button class="sp-btn sp-btn--ghost" @click="aidStep = 2">上一步</button><button class="sp-btn" :disabled="busy || !aidForm.commit" @click="submitAid">提交认定申请</button></div>
        </template>
        <AutoTable :rows="aid.items" empty="暂无认定记录" title="认定记录" style="margin-top:16px" />
        <div v-for="it in (aid.items || [])" :key="'obj-' + it.applyId" style="margin-top:12px;padding:12px 0;border-bottom:1px solid #F4F5F7">
          <div class="sp-muted">{{ it.statusLabel || it.status }} · 申请等级 {{ it.applyLevel || '—' }}</div>
          <div v-if="it.returnReason" class="sp-muted" style="color:#b45309;margin-top:4px">意见：{{ it.returnReason }}</div>
          <template v-if="it.canObject">
            <textarea v-model.trim="aidObjectForms[it.applyId]" class="sp-inp" style="margin-top:8px" placeholder="对公示认定结果有异议，请填写理由（≥5字）" />
            <button class="sp-btn sp-btn--sm" style="margin-top:8px" :disabled="busy || !(aidObjectForms[it.applyId] || '').trim()" @click="submitAidObjection(it.applyId)">提交公示异议</button>
          </template>
          <div v-else-if="it.hasPendingObjection" class="sp-muted" style="margin-top:8px">异议处理中，请等待复核</div>
        </div>
      </section>

      <!-- 奖助（门户 V1：仅奖学金/助学金；勤工/贷款/减免请走 PC 学工工作台） -->
      <section v-else-if="tab === 'funding'">
        <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap">
          <button v-for="f in fundTypes" :key="f.k" class="sp-tab" :class="{ 'is-active': fundForm.type === f.k }" @click="fundForm.type = f.k">{{ f.t }}</button>
        </div>
        <p class="sp-muted" style="margin-bottom:16px">门户当前开放奖学金、助学金申请。勤工助学、助学贷款、临时补助、学费减免请使用学校 PC 端学工中心办理。</p>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ fundLabel }}申请</div>
            <StateBlock v-if="!fundBatchesForType.length" type="empty" :text="`当前暂无开放的${fundLabel}批次，请等待学校发布后再来申请`" />
            <template v-else>
              <div class="sp-fieldlabel">申请批次</div>
              <select v-model="fundForm.batchId" class="sp-inp" style="margin-bottom:12px">
                <option v-for="b in fundBatchesForType" :key="b.batchId" :value="b.batchId">{{ b.schoolYear }}（截止 {{ (b.applyEnd || '').slice(0, 10) || '不限' }}）</option>
              </select>
              <div class="sp-fieldlabel">申请理由</div>
              <textarea v-model.trim="fundForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明申请理由" />
              <label class="chk"><input v-model="fundForm.commit" type="checkbox" />电子签署诚信承诺书</label>
              <button class="sp-btn" style="margin-top:8px" :disabled="busy || !fundForm.batchId || !fundForm.reason || !fundForm.commit" @click="applyFunding">提交申请</button>
            </template>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">我的奖助记录</div>
            <StateBlock v-if="!(funding.items||[]).length" type="empty" text="暂无奖助记录" />
            <div v-for="it in (funding.items || [])" :key="it.applicationId" style="padding:12px 0;border-bottom:1px solid #F4F5F7">
              <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
                <div>
                  <div style="font-size:14px;font-weight:600">{{ fundTypeLabel(it.projectType) }}</div>
                  <div class="sp-muted" style="margin-top:4px">{{ it.statusLabel || it.status }}</div>
                  <div v-if="it.returnReason" class="sp-muted" style="margin-top:4px;color:#b45309">退回/驳回意见：{{ it.returnReason }}</div>
                </div>
                <StatusTag :text="it.hasPendingAppeal ? '申诉待复核' : (it.statusLabel || it.status)" :tone="it.hasPendingAppeal ? 'warn' : 'default'" />
              </div>
              <template v-if="it.canAppeal">
                <textarea v-model.trim="fundAppealForms[it.applicationId]" class="sp-inp" style="margin-top:10px" placeholder="对公示结果有异议，请填写申诉理由（至少5字）" />
                <button class="sp-btn sp-btn--sm" style="margin-top:8px" :disabled="busy || !(fundAppealForms[it.applicationId] || '').trim()" @click="submitFundingAppeal(it.applicationId)">提交公示申诉</button>
              </template>
              <div v-else-if="it.hasPendingAppeal" class="sp-muted" style="margin-top:8px">申诉处理中，请耐心等待复核结果</div>
            </div>
          </section>
        </div>
      </section>

      <!-- 宿舍只读 -->
      <section v-else-if="tab === 'dorm'" class="sp-card" style="max-width:640px">
        <div class="sp-panel__head">我的宿舍</div>
        <StateBlock v-if="!dorm.hasBed" type="empty" :text="dorm.studentNotice || '暂无入住床位信息，如需自选床位请使用学生小程序。'" />
        <template v-else>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div><div class="sp-muted">楼栋</div><div style="font-weight:600;margin-top:4px">{{ dorm.myBed?.building || '—' }}</div></div>
            <div><div class="sp-muted">房间</div><div style="font-weight:600;margin-top:4px">{{ dorm.myBed?.room || '—' }}</div></div>
            <div><div class="sp-muted">床位</div><div style="font-weight:600;margin-top:4px">{{ dorm.myBed?.bedNo || '—' }}</div></div>
            <div><div class="sp-muted">入住时间</div><div style="font-weight:600;margin-top:4px">{{ (dorm.myBed?.occupiedAt || '').slice(0, 10) || '—' }}</div></div>
          </div>
          <p class="sp-muted" style="margin-top:14px">调宿、退宿、自选床位请按学院通知办理；自选床位入口在学生小程序。</p>
        </template>
      </section>

      <!-- 违纪申诉 -->
      <section v-else-if="tab === 'discipline'">
        <section v-if="!discipline.activeCount" class="sp-card" style="max-width:640px;text-align:center;padding:30px">
          <span class="ok-ico"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4" /><circle cx="12" cy="12" r="9" /></svg></span>
          <div style="font-size:15px;font-weight:600;margin-top:14px">暂无违纪处分记录</div>
          <div class="sp-muted" style="margin-top:6px">如对处分决定有异议，可在收到处分决定书后 15 日内提交书面申辩。</div>
        </section>
        <template v-else>
          <section v-for="c in discipline.items" :key="c.caseId" class="sp-card" style="max-width:640px;margin-bottom:14px">
            <div class="sp-panel__head">{{ c.discTypeLabel || c.discType }} <StatusTag :text="(c.effectiveAt || '').slice(0, 10) + ' 生效'" tone="warn" /></div>
            <div v-if="c.appealStatus" style="margin-top:8px">
              <StatusTag :text="appealStatusText(c.appealStatus)" :tone="c.appealStatus === 'UPHELD' ? 'default' : 'success'" />
              <div v-if="c.appealReviewOpinion" class="sp-muted" style="margin-top:8px">复核意见：{{ c.appealReviewOpinion }}</div>
            </div>
            <template v-if="c.canAppeal">
              <textarea v-model.trim="appealForms[c.caseId]" class="sp-inp" style="margin-top:12px;text-align:left" placeholder="申辩 / 申诉理由（至少5字）" />
              <button class="sp-btn" style="margin-top:10px" :disabled="busy || !(appealForms[c.caseId] || '').trim()" @click="submitAppeal(c.caseId)">提交申辩</button>
            </template>
            <div v-else-if="c.appealStatus === 'SUBMITTED' || c.appealStatus === 'REVIEWING'" class="sp-muted" style="margin-top:8px">申诉处理中，请耐心等待复核结果</div>
            <div v-else-if="c.appealStatus" class="sp-muted" style="margin-top:8px">该处分申诉已结案（一案一诉）</div>
          </section>
        </template>
      </section>

      <!-- 心理自评 -->
      <div v-else-if="tab === 'psy'" class="two">
        <section class="sp-card">
          <div style="font-size:15px;font-weight:600">心理健康自评量表</div>
          <div class="sp-muted" style="margin:4px 0 14px">结果仅本人与心理中心可见，不影响学业评定</div>
          <StateBlock v-if="!(psy.questions||[]).length" type="empty" text="暂无自评问卷" />
          <div v-else>
            <div v-for="(q, qi) in psy.questions" :key="q.key" style="padding:10px 0;border-bottom:1px solid #F4F5F7">
              <div style="font-size:13.5px;color:var(--t1);margin-bottom:8px">{{ qi + 1 }}. {{ q.text }}</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <button v-for="(opt, oi) in q.options" :key="oi" class="opt" :class="{ on: psyAnswers[q.key] === oi }" @click="psyAnswers[q.key] = oi">{{ opt }}</button>
              </div>
            </div>
            <button class="sp-btn" style="margin-top:14px" :disabled="busy || !psyComplete" @click="submitPsy">提交测评</button>
          </div>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">历史测评</div>
          <AutoTable :rows="psyHistory.items" empty="暂无测评记录" />
        </section>
      </div>

      <!-- 活动二课 -->
      <section v-else-if="tab === 'activity'">
        <section class="sp-card" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
          <div><div style="font-size:15px;font-weight:600">我的第二课堂学分</div><div class="sp-muted" style="margin-top:4px">毕业要求 8 学分</div></div>
          <div style="font-size:26px;font-weight:700;color:var(--pri);font-variant-numeric:tabular-nums">{{ activityCredit }}<span class="sp-muted" style="font-size:13px"> / 8 学分</span></div>
        </section>
        <StateBlock v-if="!(activities.available||[]).length" type="empty" text="暂无可报名活动" />
        <div v-else class="act-grid">
          <div v-for="(a, i) in activities.available" :key="a.activityId || a.id || i" class="sp-card" style="padding:16px">
            <div style="font-size:14px;font-weight:600">{{ a.activityName || a.name || a.title }}</div>
            <div class="sp-muted" style="margin-top:5px">{{ (a.startAt || a.time || a.startTime || '').slice(0, 16) }} · {{ a.creditValue ?? a.credit ?? 0 }} 学分</div>
            <button class="sp-btn sp-btn--sm" style="margin-top:12px;width:100%" :disabled="busy || !(a.activityId || a.id)" @click="enroll(a.activityId || a.id)">报名</button>
          </div>
        </div>
        <AutoTable :rows="activities.mine" empty="暂无已报名活动" title="我报名的活动" style="margin-top:16px" />
      </section>

      <!-- 谈心谈话 -->
      <section v-else-if="tab === 'talk'" class="sp-card" style="max-width:720px">
        <div style="font-size:15px;font-weight:600">我的谈话记录</div>
        <div class="sp-muted" style="margin:4px 0 16px">仅展示时间、主题与状态摘要；谈话原文由辅导员侧保管</div>
        <StateBlock v-if="!(talk.items||[]).length" type="empty" text="暂无谈话记录" />
        <div v-for="t in (talk.items || [])" :key="t.talkId" style="padding:12px 0;border-bottom:1px solid #F4F5F7">
          <div style="display:flex;justify-content:space-between;gap:8px">
            <div>
              <div style="font-size:14px;font-weight:600">{{ t.talkTypeLabel || t.talkType || '谈心谈话' }}</div>
              <div class="sp-muted" style="margin-top:4px">{{ t.topic || '' }}</div>
              <div class="sp-muted" style="margin-top:4px">{{ (t.talkAt || '').slice(0, 16) || '时间待定' }}</div>
              <div v-if="t.needFollow" class="sp-muted" style="margin-top:4px;color:#b45309">需回访跟进</div>
            </div>
            <StatusTag :text="t.statusLabel || t.status || '—'" tone="default" />
          </div>
        </div>
        <div class="notebox" style="margin-top:12px">{{ talk.detailNote || '谈心谈话由辅导员登记后同步至此。' }}</div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import Wizard from '../../components/Wizard.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const tabs = [
  { key: 'leave', label: '请假申请' }, { key: 'aid', label: '困难认定' }, { key: 'funding', label: '奖助勤贷补' },
  { key: 'dorm', label: '我的宿舍' },
  { key: 'discipline', label: '违纪申诉' }, { key: 'psy', label: '心理自评' }, { key: 'activity', label: '活动二课' }, { key: 'talk', label: '谈心谈话' }
]
const tab = ref('leave')
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const leave = ref({})
const aid = ref({})
const funding = ref({})
const dorm = ref({})
const aidBatches = ref([])
const fundBatches = ref([])
const discipline = ref({})
const psy = ref({})
const psyHistory = ref({})
const activities = ref({})
const talk = ref({})
const aidObjectForms = reactive({})
const extendId = ref('')
const extendForm = reactive({ newEndTime: '', reason: '' })

const leaveTypes = [{ k: 'PERSONAL', t: '事假' }, { k: 'SICK', t: '病假' }, { k: 'OTHER', t: '其他' }]
const fundTypes = [
  { k: 'SCHOLARSHIP', t: '奖学金' }, { k: 'GRANT', t: '助学金' }
]
const leaveForm = reactive({ leaveType: 'PERSONAL', startDate: '', endDate: '', reason: '' })
const aidStep = ref(1)
const aidForm = reactive({ batchId: '', level: 'GENERAL', income: null, reason: '', commit: false })
const fundForm = reactive({ type: 'SCHOLARSHIP', batchId: '', reason: '', commit: false })
const fundAppealForms = reactive({})
const appealForms = reactive({})
const psyAnswers = reactive({})
const APPEAL_L = { SUBMITTED: '申诉已提交，等待复核', REVIEWING: '复核中',
  UPHELD: '复核结果：维持原处分', REVISED: '复核结果：处分已变更', REVOKED: '复核结果：处分已撤销' }
function appealStatusText(s) { return APPEAL_L[s] || s }

const fundLabel = computed(() => (fundTypes.find((f) => f.k === fundForm.type) || {}).t || '')
const fundBatchesForType = computed(() => (fundBatches.value || []).filter((b) => b.projectType === fundForm.type))
const psyComplete = computed(() => (psy.value.questions || []).every((q) => psyAnswers[q.key] != null))
const activityCredit = computed(() => (activities.value.mine || []).reduce((a, x) => a + (Number(x.creditValue ?? x.credit) || 0), 0))

watch(() => fundForm.type, () => { fundForm.batchId = '' })
watch(fundBatchesForType, (list) => { if (!list.some((b) => b.batchId === fundForm.batchId)) fundForm.batchId = list[0]?.batchId || '' })
watch(aidBatches, (list) => { if (!list.some((b) => b.batchId === aidForm.batchId)) aidForm.batchId = list[0]?.batchId || '' })

async function reload() {
  loading.value = true; error.value = ''
  try {
    const [lv, ad, fd, dc, pq, ph, ac, ab, fb, tk, dm] = await Promise.allSettled([
      portalApi.affairsLeave(), portalApi.affairsAid(), portalApi.affairsFunding(), portalApi.affairsDiscipline(),
      portalApi.affairsPsyQuestions(), portalApi.affairsPsyHistory(), portalApi.affairsActivitiesMy(),
      portalApi.affairsAidBatches(), portalApi.affairsFundingBatches(), portalApi.affairsTalk(),
      portalApi.affairsDorm()
    ])
    const failed = [lv, ad, fd, dc, pq, ph, ac, ab, fb, tk, dm].filter((r) => r.status === 'rejected')
    const val = (r, d) => (r.status === 'fulfilled' ? (r.value ?? d) : d)
    leave.value = val(lv, {}); aid.value = val(ad, {}); funding.value = val(fd, {}); discipline.value = val(dc, {})
    psy.value = val(pq, {}); psyHistory.value = val(ph, {}); activities.value = val(ac, {})
    aidBatches.value = val(ab, {}).items || []; fundBatches.value = val(fb, {}).items || []
    talk.value = val(tk, {}); dorm.value = val(dm, {})
    if (failed.length === 11) {
      error.value = failed[0].reason?.message || '学工数据加载失败'
    } else if (failed.length) {
      ui.notify(`${failed.length} 个学工接口加载失败，已显示其余可用数据`)
    }
  } catch (e) { error.value = e?.message || '学工数据加载失败' } finally { loading.value = false }
}
async function applyLeave() {
  busy.value = true
  try {
    await portalApi.affairsLeaveApply({reason: leaveForm.reason, leaveType: leaveForm.leaveType,
      startTime: leaveForm.startDate, endTime: leaveForm.endDate
    })
    ui.notify('请假申请已提交，等待辅导员审批'); leaveForm.reason = ''; leaveForm.startDate = ''; leaveForm.endDate = ''; reload()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function resubmitLeave(lv) {
  const leaveId = lv.leaveId || lv.id
  if (!leaveId) return
  busy.value = true
  try {
    await portalApi.affairsLeaveResubmit(leaveId, { reason: lv.reason || leaveForm.reason || '', version: lv.version })
    ui.notify('已重新提交，等待审批')
    reload()
  } catch (e) { ui.notify(e?.message || '重新提交失败') } finally { busy.value = false }
}
async function cancelLeave(lv) {
  const leaveId = lv.leaveId || lv.id
  if (!leaveId) return
  busy.value = true
  try {
    await portalApi.affairsLeaveCancel(leaveId, { proofNote: '学生本人申请销假', version: lv.version })
    ui.notify('销假已提交，等待辅导员确认')
    reload()
  } catch (e) { ui.notify(e?.message || '销假提交失败') } finally { busy.value = false }
}
function openExtend(lv) {
  extendId.value = lv.leaveId || lv.id || ''
  extendForm.newEndTime = (lv.endTime || '').slice(0, 10)
  extendForm.reason = ''
}
async function submitExtend(lv) {
  const leaveId = lv.leaveId || lv.id
  if (!leaveId) return
  if ((extendForm.reason || '').trim().length < 5) {
    ui.notify('续假事由至少5字'); return
  }
  busy.value = true
  try {
    await portalApi.affairsLeaveExtend(leaveId, {
      newEndTime: extendForm.newEndTime,
      reason: extendForm.reason.trim(),
      version: lv.version
    })
    ui.notify('续假已提交，等待辅导员审批')
    extendId.value = ''
    reload()
  } catch (e) { ui.notify(e?.message || '续假提交失败') } finally { busy.value = false }
}
async function submitAidObjection(applyId) {
  busy.value = true
  try {
    await portalApi.affairsAidObjection({ applyId, reason: aidObjectForms[applyId] })
    ui.notify('公示异议已提交')
    aidObjectForms[applyId] = ''
    reload()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitAid() {
  busy.value = true
  try {
    await portalApi.affairsAidApply({
      batchId: aidForm.batchId, applyLevel: aidForm.level, annualIncome: aidForm.income,
      statement: aidForm.reason, confirm: true
    })
    ui.notify('困难认定申请已提交，等待审核'); aidStep.value = 1; aidForm.reason = ''; aidForm.commit = false; reload()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function applyFunding() {
  busy.value = true
  try {
    await portalApi.affairsFundingApply({ batchId: fundForm.batchId, statement: fundForm.reason, confirm: true })
    ui.notify('奖助申请已提交，等待审核'); fundForm.reason = ''; fundForm.commit = false; reload()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitFundingAppeal(applicationId) {
  busy.value = true
  try {
    await portalApi.affairsFundingAppeal({ applicationId, reason: fundAppealForms[applicationId] })
    ui.notify('公示申诉已提交，等待复核'); fundAppealForms[applicationId] = ''; reload()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
function fundTypeLabel(t) {
  return (fundTypes.find((f) => f.k === t) || {}).t || t || '奖助'
}
async function submitAppeal(caseId) {
  busy.value = true
  try {
    await portalApi.affairsDisciplineAppeal({ caseId, reason: appealForms[caseId] })
    ui.notify('申辩已提交，等待复核'); appealForms[caseId] = ''; reload()
  } catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function submitPsy() {
  busy.value = true
  try { await portalApi.affairsPsySubmit({ answers: (psy.value.questions || []).map((q) => ({ qKey: q.key, score: psyAnswers[q.key] })) }); ui.notify('测评已提交，结果仅本人与心理中心可见'); reload() }
  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }
}
async function enroll(id) {
  busy.value = true
  try { await portalApi.affairsActivityEnroll(id); ui.notify('报名成功'); reload() }
  catch (e) { ui.notify(e?.message || '报名失败') } finally { busy.value = false }
}
async function print(name) {
  busy.value = true
  try {
    await portalApi.affairsPrint({ bizType: 'LEAVE', docName: name || '请假条' })
    ui.notify('已生成' + (name || '请假条') + '打印留痕')
  } catch (e) { ui.notify(e?.message || '打印失败') } finally { busy.value = false }
}
watch(tab, () => { aidStep.value = 1 })
onMounted(reload)
</script>

<style scoped>
.two { display: grid; grid-template-columns: 1fr 1.15fr; gap: 18px; align-items: start; }
.seg { all: unset; box-sizing: border-box; cursor: pointer; flex: 1; text-align: center; padding: 8px; border-radius: 8px; background: #F5F7FA; color: var(--t3); font-size: 13px; }
.seg.on { background: var(--pri-50); color: var(--pri); font-weight: 600; border: 1px solid var(--pri-100); }
.chk { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--t2); cursor: pointer; }
.promise { max-width: 560px; padding: 16px; border: 1px solid var(--line); border-radius: 10px; font-size: 13px; color: var(--t2); line-height: 1.8; margin-bottom: 14px; }
.ok-ico { display: inline-flex; width: 48px; height: 48px; border-radius: 50%; background: var(--ok-bg); color: var(--ok-fg); align-items: center; justify-content: center; }
.opt { all: unset; cursor: pointer; padding: 7px 13px; border-radius: 8px; background: #F5F7FA; color: var(--t2); font-size: 12.5px; }
.opt.on { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.act-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.notebox { margin-top: 14px; padding: 12px 16px; background: #F2F7FF; border-radius: 10px; font-size: 12.5px; color: var(--t2); line-height: 1.6; }
@media (max-width: 900px) { .two { grid-template-columns: 1fr; } .act-grid { grid-template-columns: 1fr 1fr; } }
</style>
