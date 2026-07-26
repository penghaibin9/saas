<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="item in tabs" :key="item.key" class="sp-tab" :class="{ 'is-active': tab === item.key }" @click="tab = item.key">{{ item.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="学工数据加载中…" />
    <template v-else>
      <div v-if="tabError" class="domain-error"><strong>当前业务暂不可用</strong><span>{{ tabError }}</span><button class="sp-btn sp-btn--ghost" @click="reload">重新加载</button></div>

      <div v-if="tab === 'leave'" class="two">
        <section class="sp-card">
          <div class="sp-panel__head">请假申请</div>
          <div class="form-grid">
            <label><span>请假类型</span><select v-model="leaveForm.leaveType" class="sp-inp"><option value="PERSONAL">事假</option><option value="SICK">病假</option><option value="HOME">探亲假</option><option value="HOSPITAL">住院假</option><option value="GOOUT">外出</option><option value="OTHER">其他</option></select></label>
            <label><span>开始日期</span><input v-model="leaveForm.startTime" type="date" class="sp-inp" :min="today" /></label>
            <label><span>结束日期</span><input v-model="leaveForm.endTime" type="date" class="sp-inp" :min="leaveForm.startTime || today" /></label>
            <label class="wide"><span>请假事由（5-300字）</span><textarea v-model.trim="leaveForm.reason" maxlength="300" class="sp-inp" placeholder="请客观填写请假事由" /></label>
          </div>
          <p v-if="leaveForm.startTime && leaveForm.endTime && leaveForm.endTime < leaveForm.startTime" class="field-error">结束日期不能早于开始日期</p>
          <button class="sp-btn" :disabled="busy || !validLeave" @click="applyLeave">提交请假</button>
        </section>

        <section class="sp-card">
          <div class="sp-panel__head">请假 / 销假 / 续假记录</div>
          <StateBlock v-if="!(leave.items || []).length" type="empty" text="暂无请假记录" />
          <article v-for="item in (leave.items || [])" :key="item.leaveId" class="record">
            <div class="record-head"><div><strong>{{ item.leaveTypeLabel || item.leaveType }}</strong><div class="sp-muted">{{ fmt(item.startTime) }} 至 {{ fmt(item.endTime) }} · {{ item.days }}天</div><div v-if="item.returnReason" class="warn">退回意见：{{ item.returnReason }}</div></div><StatusTag :text="item.affairsStatusLabel || item.statusLabel || item.status" tone="default" /></div>
            <div class="actions"><button v-if="item.canResubmit" class="sp-btn sp-btn--ghost" :disabled="busy" @click="editLeave(item)">修改后重提</button><button v-if="item.canCancel" class="sp-btn" :disabled="busy" @click="cancelLeave(item)">申请销假</button><button v-if="item.canExtend" class="sp-btn sp-btn--ghost" :disabled="busy" @click="openExtend(item)">申请续假</button></div>
            <div v-if="extendId === item.leaveId" class="inline-form">
              <label><span>原结束日期</span><strong>{{ fmt(item.endTime) }}</strong></label>
              <label><span>新结束日期</span><input v-model="extendForm.newEndTime" type="date" class="sp-inp" :min="dayAfter(fmt(item.endTime))" /></label>
              <label><span>续假事由（5-300字）</span><textarea v-model.trim="extendForm.reason" maxlength="300" class="sp-inp" /></label>
              <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="extendId = ''">取消</button><button class="sp-btn" :disabled="busy || !validExtend(item)" @click="submitExtend(item)">提交续假</button></div>
            </div>
          </article>
        </section>
      </div>

      <section v-else-if="tab === 'aid'" class="sp-card">
        <div class="sp-panel__head">家庭经济困难认定 <StatusTag :text="aid.currentLevel || '未认定'" :tone="aid.currentLevel ? 'success' : 'default'" /></div>
        <p class="sp-muted">PC与小程序采用同一材料合同：家庭人数、年收入、债务、特殊情况和困难说明共同进入审批。</p>
        <div class="form-grid compact">
          <label class="wide"><span>开放批次</span><select v-model="aidForm.batchId" class="sp-inp"><option value="">请选择</option><option v-for="b in aidBatches" :key="b.batchId" :value="b.batchId">{{ b.batchName || b.schoolYear }}（截止 {{ fmt(b.applyEnd) || '不限' }}）</option></select></label>
          <label><span>申请等级</span><select v-model="aidForm.applyLevel" class="sp-inp"><option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option></select></label>
          <label><span>家庭成员数（1-30）</span><input v-model.number="aidForm.memberCount" type="number" min="1" max="30" step="1" class="sp-inp" /></label>
          <label><span>家庭年收入（元）</span><input v-model.number="aidForm.annualIncome" type="number" min="0" step="0.01" class="sp-inp" /></label>
          <label><span>家庭债务（元）</span><input v-model.number="aidForm.debt" type="number" min="0" step="0.01" class="sp-inp" /></label>
          <label class="wide"><span>特殊情况标签</span><input v-model.trim="aidForm.specialTags" maxlength="200" class="sp-inp" placeholder="低保、孤残、重大疾病等，用逗号分隔" /></label>
          <label class="wide"><span>困难情况说明（10-500字）</span><textarea v-model.trim="aidForm.statement" maxlength="500" class="sp-inp" /></label>
        </div>
        <p v-if="aidValidationError" class="field-error">{{ aidValidationError }}</p>
        <label class="check"><input v-model="aidForm.confirm" type="checkbox" />本人确认上述信息真实，系统将记录内容哈希、确认人和时间；该留痕不等同于持牌电子签名。</label>
        <button class="sp-btn" :disabled="busy || !validAid" @click="submitAid">提交认定申请</button>
        <div class="section-title">认定记录</div>
        <StateBlock v-if="!(aid.items || []).length" type="empty" text="暂无认定记录" />
        <article v-for="item in (aid.items || [])" :key="item.applyId" class="record">
          <div class="record-head"><div><strong>申请等级：{{ item.applyLevel }}</strong><div class="sp-muted">{{ item.statusLabel || item.status }}</div><div v-if="item.returnReason" class="warn">意见：{{ item.returnReason }}</div></div><StatusTag :text="item.statusLabel || item.status" tone="default" /></div>
          <div class="actions"><button v-if="item.canResubmit" class="sp-btn sp-btn--ghost" :disabled="busy" @click="editAid(item)">修改后重提</button></div>
          <div v-if="item.canObject" class="inline-form"><textarea v-model.trim="aidObjections[item.applyId]" maxlength="500" class="sp-inp" placeholder="公示异议理由（5-500字）" /><button class="sp-btn" :disabled="busy || !validReason(aidObjections[item.applyId], 5, 500)" @click="submitAidObjection(item)">提交异议</button></div>
          <div v-if="item.hasPendingObjection" class="sp-muted">异议已进入具体老师待办，等待复核。</div>
        </article>
      </section>

      <section v-else-if="tab === 'funding'" class="sp-card">
        <div class="sp-panel__head">奖学金与助学金</div>
        <p class="sp-muted">本入口只开放学生可直接申请的奖学金、助学金。勤工助学、贷款、减免与临时补助由学校按项目另行开放。</p>
        <div class="form-grid compact"><label><span>类型</span><select v-model="fundForm.projectType" class="sp-inp"><option value="SCHOLARSHIP">奖学金</option><option value="GRANT">助学金</option></select></label><label><span>开放批次</span><select v-model="fundForm.batchId" class="sp-inp"><option value="">请选择</option><option v-for="b in filteredFundingBatches" :key="b.batchId" :value="b.batchId">{{ b.batchName || b.schoolYear }}</option></select></label><label class="wide"><span>申请理由（5-1000字）</span><textarea v-model.trim="fundForm.statement" maxlength="1000" class="sp-inp" /></label></div>
        <label class="check"><input v-model="fundForm.confirm" type="checkbox" />本人确认申请信息真实，系统将记录内容哈希、确认人和时间。</label>
        <button class="sp-btn" :disabled="busy || !validFunding" @click="submitFunding">提交申请</button>
        <div class="section-title">我的奖助记录</div>
        <StateBlock v-if="!(funding.items || []).length" type="empty" text="暂无奖助记录" />
        <article v-for="item in (funding.items || [])" :key="item.applicationId" class="record"><div class="record-head"><div><strong>{{ fundingLabel(item.projectType) }}</strong><div class="sp-muted">{{ item.statusLabel || item.status }}</div><div v-if="item.returnReason" class="warn">意见：{{ item.returnReason }}</div></div><StatusTag :text="item.hasPendingAppeal ? '申诉待复核' : (item.statusLabel || item.status)" :tone="item.hasPendingAppeal ? 'warn' : 'default'" /></div><div class="actions"><button v-if="item.canResubmit" class="sp-btn sp-btn--ghost" :disabled="busy" @click="editFunding(item)">修改后重提</button></div><div v-if="item.canAppeal" class="inline-form"><textarea v-model.trim="fundAppeals[item.applicationId]" maxlength="1000" class="sp-inp" placeholder="公示申诉理由（5-1000字）" /><button class="sp-btn" :disabled="busy || !validReason(fundAppeals[item.applicationId], 5, 1000)" @click="submitFundingAppeal(item)">提交申诉</button></div></article>
      </section>

      <section v-else-if="tab === 'dorm'" class="sp-card">
        <div class="sp-panel__head">我的宿舍</div>
        <StateBlock v-if="!dorm.hasBed" type="empty" :text="dorm.studentNotice || '暂无入住床位'" />
        <template v-else>
          <div class="bed-grid"><div><span>楼栋</span><strong>{{ dorm.myBed?.building }}</strong></div><div><span>房间</span><strong>{{ dorm.myBed?.room }}</strong></div><div><span>床位</span><strong>{{ dorm.myBed?.bedNo }}</strong></div><div><span>入住时间</span><strong>{{ fmt(dorm.myBed?.occupiedAt) }}</strong></div></div>
          <p class="sp-muted">已有床位时只能提交正式调宿申请；审批完成前原床保持不变。</p>
          <p v-if="pendingDormTransfer" class="warn">已有调宿申请处理中：{{ pendingDormTransfer.statusLabel || pendingDormTransfer.status || pendingDormTransfer.currentNode }}</p>
          <button v-else class="sp-btn sp-btn--ghost" :disabled="busy" @click="loadDormOptions">申请调宿</button>
        </template>
        <div v-if="dormForm.visible" class="inline-form dorm-form">
          <select v-model="dormForm.buildingId" class="sp-inp" @change="loadRooms"><option value="">选择目标楼栋</option><option v-for="b in dormBuildings" :key="b.buildingId" :value="b.buildingId">{{ b.buildingName }}（空{{ b.vacantBeds }}）</option></select>
          <select v-model="dormForm.roomId" class="sp-inp" :disabled="!dormForm.buildingId" @change="loadBeds"><option value="">选择房间</option><option v-for="r in dormRooms" :key="r.roomId" :value="r.roomId">{{ r.floorNo }}层 {{ r.roomNo }}（空{{ r.vacantBeds }}）</option></select>
          <select v-model="dormForm.bedId" class="sp-inp" :disabled="!dormForm.roomId"><option value="">选择床位</option><option v-for="b in availableDormBeds" :key="b.bedId" :value="b.bedId">{{ b.bedNo }}</option></select>
          <p v-if="dormForm.bedId" class="selected-target">目标床位：{{ selectedDormTarget }}</p>
          <textarea v-model.trim="dormForm.reason" maxlength="300" class="sp-inp" placeholder="调宿原因（5-300字）" />
          <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="closeDormForm">取消</button><button class="sp-btn" :disabled="busy || !validDormTransfer" @click="submitDormTransfer">核对并提交调宿</button></div>
        </div>
        <div class="section-title">调宿申请记录</div><AutoTable :rows="dormTransfers" empty="暂无调宿申请" />
      </section>

      <section v-else-if="tab === 'discipline'" class="sp-card">
        <div class="sp-panel__head">处分申诉</div><p class="sp-muted">本入口用于处分生效后的申诉，不冒充处分决定前的陈述申辩。具体期限以学校处分决定书与规章为准。</p>
        <StateBlock v-if="!discipline.activeCount" type="empty" text="暂无生效处分记录" />
        <article v-for="item in (discipline.items || [])" :key="item.caseId" class="record"><div class="record-head"><div><strong>{{ item.discTypeLabel || item.discType }}</strong><div class="sp-muted">{{ fmt(item.effectiveAt) }} 生效</div><div v-if="item.appealReviewOpinion" class="sp-muted">复核意见：{{ item.appealReviewOpinion }}</div></div><StatusTag :text="appealLabel(item.appealStatus)" tone="default" /></div><div v-if="item.canAppeal" class="inline-form"><textarea v-model.trim="disciplineAppeals[item.caseId]" maxlength="1000" class="sp-inp" placeholder="处分申诉理由（5-1000字）" /><button class="sp-btn" :disabled="busy || !validReason(disciplineAppeals[item.caseId], 5, 1000)" @click="submitDisciplineAppeal(item)">提交处分申诉</button></div></article>
      </section>

      <div v-else-if="tab === 'psy'" class="two"><section class="sp-card"><div class="sp-panel__head">心理健康自评</div><p class="sp-muted">结果仅本人与心理中心按授权查看，系统不作自动诊断。</p><StateBlock v-if="!(psy.questions || []).length" type="empty" text="暂无自评问卷" /><div v-for="(q, index) in (psy.questions || [])" :key="q.key" class="question"><strong>{{ index + 1 }}. {{ q.text }}</strong><div class="options"><button v-for="(option, oi) in q.options" :key="oi" class="seg" :class="{ on: psyAnswers[q.key] === oi }" @click="psyAnswers[q.key] = oi">{{ option }}</button></div></div><button class="sp-btn" :disabled="busy || !psyComplete" @click="submitPsy">提交自评</button></section><section class="sp-card"><div class="sp-panel__head">历史测评</div><AutoTable :rows="psyHistory.items || []" empty="暂无测评记录" /></section></div>

      <section v-else-if="tab === 'activity'">
        <div class="score-card sp-card"><div><strong>正式第二课堂成绩单</strong><p class="sp-muted">仅统计老师确认后已入账流水，不使用活动配置值自行估算。</p></div><div class="score"><span>原始 {{ secondClass.rawTotal || 0 }}</span><span>加权 {{ secondClass.weightedTotal || 0 }}</span></div></div>
        <div class="two"><section class="sp-card"><div class="sp-panel__head">可报名活动</div><StateBlock v-if="!(activities.available || []).length" type="empty" text="暂无可报名活动" /><article v-for="item in (activities.available || [])" :key="item.activityId" class="record"><div class="record-head"><div><strong>{{ item.activityName }}</strong><div class="sp-muted">{{ fmt(item.startAt) }} · {{ item.location || '未填写地点' }}</div></div><button v-if="!item.mySignupStatus || item.mySignupStatus === 'CANCELLED'" class="sp-btn" :disabled="busy" @click="enroll(item)">报名</button><StatusTag v-else :text="item.mySignupStatus" tone="default" /></div></article></section><section class="sp-card"><div class="sp-panel__head">入账明细</div><StateBlock v-if="!(secondClass.items || []).length" type="empty" text="暂无已确认入账记录" /><article v-for="item in (secondClass.items || [])" :key="`${item.activityId}-${item.grantedAt}`" class="record"><div class="record-head"><div><strong>{{ item.remark || '第二课堂记录' }}</strong><div class="sp-muted">{{ creditLabel(item.creditType) }} · {{ fmt(item.grantedAt) }}</div></div><div><strong>+{{ item.creditValue }}</strong><button class="link" @click="openCreditAppeal(item)">记错申诉</button></div></div></article><button class="sp-btn sp-btn--ghost" @click="openCreditAppeal(null)">有活动缺记？提交缺记申诉</button></section></div>
        <section class="sp-card" style="margin-top:16px"><div class="sp-panel__head">我的积分申诉</div><AutoTable :rows="creditAppeals" empty="暂无积分申诉" /></section>
      </section>

      <section v-else-if="tab === 'talk'" class="sp-card"><div class="sp-panel__head">我的谈心谈话摘要</div><p class="sp-muted">学生端只展示时间、主题、状态和是否需回访，不显示老师内部记录或心理明细。</p><StateBlock v-if="!(talk.items || []).length" type="empty" text="暂无谈话记录" /><article v-for="item in (talk.items || [])" :key="item.talkId" class="record"><div class="record-head"><div><strong>{{ item.talkTypeLabel || item.talkType }}</strong><div class="sp-muted">{{ item.topic }} · {{ fmt(item.talkAt) || '时间待定' }}</div><div v-if="item.needFollow" class="warn">需要后续回访</div></div><StatusTag :text="item.statusLabel || item.status" tone="default" /></div></article></section>
    </template>

    <div v-if="modal.type" class="mask" @click.self="closeModal">
      <section class="sp-card modal">
        <div class="sp-panel__head">{{ modal.title }}</div><p v-if="modal.notice" class="warn">{{ modal.notice }}</p>
        <template v-if="modal.type === 'leave'"><div class="form-grid"><label><span>类型</span><select v-model="modal.form.leaveType" class="sp-inp"><option value="PERSONAL">事假</option><option value="SICK">病假</option><option value="HOME">探亲假</option><option value="HOSPITAL">住院假</option><option value="GOOUT">外出</option><option value="OTHER">其他</option></select></label><label><span>开始日期</span><input v-model="modal.form.startTime" type="date" class="sp-inp" /></label><label><span>结束日期</span><input v-model="modal.form.endTime" type="date" class="sp-inp" :min="modal.form.startTime" /></label><label class="wide"><span>事由（5-300字）</span><textarea v-model.trim="modal.form.reason" maxlength="300" class="sp-inp" /></label></div></template>
        <template v-else-if="modal.type === 'aid'"><div class="form-grid"><label><span>等级</span><select v-model="modal.form.applyLevel" class="sp-inp"><option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option></select></label><label><span>成员数（1-30）</span><input v-model.number="modal.form.memberCount" type="number" min="1" max="30" step="1" class="sp-inp" /></label><label><span>年收入</span><input v-model.number="modal.form.annualIncome" type="number" min="0" step="0.01" class="sp-inp" /></label><label><span>债务</span><input v-model.number="modal.form.debt" type="number" min="0" step="0.01" class="sp-inp" /></label><label class="wide"><span>特殊情况标签</span><input v-model.trim="modal.form.specialTags" maxlength="200" class="sp-inp" /></label><label class="wide"><span>情况说明（10-500字）</span><textarea v-model.trim="modal.form.statement" maxlength="500" class="sp-inp" /></label></div></template>
        <template v-else-if="modal.type === 'funding'"><label><span>申请理由（5-1000字）</span><textarea v-model.trim="modal.form.statement" maxlength="1000" class="sp-inp" /></label></template>
        <template v-else-if="modal.type === 'credit'"><p class="sp-muted">{{ modal.form.activityName ? `涉及活动：${modal.form.activityName}` : '缺记申诉可不指定活动' }}</p><select v-model="modal.form.claimCreditType" class="sp-inp"><option value="SECOND_CLASS">第二课堂</option><option value="MORAL">德育积分</option><option value="VOLUNTEER_HOUR">志愿时长</option></select><input v-model="modal.form.claimValue" type="number" min="0.01" max="9999.99" step="0.01" class="sp-inp" placeholder="主张数值（必填，0.01-9999.99）" /><p v-if="creditClaimError" class="field-error">{{ creditClaimError }}</p><textarea v-model.trim="modal.form.reason" maxlength="1000" class="sp-inp" placeholder="申诉理由（5-1000字）" /></template>
        <p v-if="modalValidationError" class="field-error">{{ modalValidationError }}</p>
        <div class="actions"><button class="sp-btn sp-btn--ghost" :disabled="busy" @click="closeModal">取消</button><button class="sp-btn" :disabled="busy || !modalValid" @click="submitModal">保存并提交</button></div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const tabs = [{ key: 'leave', label: '请假销假' }, { key: 'aid', label: '困难认定' }, { key: 'funding', label: '奖学金与助学金' }, { key: 'dorm', label: '我的宿舍' }, { key: 'discipline', label: '处分申诉' }, { key: 'psy', label: '心理自评' }, { key: 'activity', label: '活动与第二课堂' }, { key: 'talk', label: '谈心谈话' }]
const tab = ref('leave'); const loading = ref(true); const busy = ref(false); const errors = reactive({}); const tabError = computed(() => errors[tab.value] || '')
const leave = ref({ items: [] }); const aid = ref({ items: [] }); const funding = ref({ items: [] }); const dorm = ref({}); const discipline = ref({ items: [] }); const psy = ref({ questions: [] }); const psyHistory = ref({ items: [] }); const activities = ref({ available: [], mine: [] }); const talk = ref({ items: [] }); const aidBatches = ref([]); const fundingBatches = ref([]); const secondClass = ref({ items: [], byType: [] }); const creditAppeals = ref([]); const dormTransfers = ref([])
const leaveForm = reactive({ leaveType: 'PERSONAL', startTime: '', endTime: '', reason: '' }); const extendId = ref(''); const extendForm = reactive({ newEndTime: '', reason: '' }); const aidForm = reactive({ batchId: '', applyLevel: 'GENERAL', memberCount: null, annualIncome: null, debt: null, specialTags: '', statement: '', confirm: false }); const fundForm = reactive({ projectType: 'SCHOLARSHIP', batchId: '', statement: '', confirm: false }); const aidObjections = reactive({}); const fundAppeals = reactive({}); const disciplineAppeals = reactive({}); const psyAnswers = reactive({}); const dormBuildings = ref([]); const dormRooms = ref([]); const dormBeds = ref([]); const dormForm = reactive({ visible: false, buildingId: '', roomId: '', bedId: '', reason: '' }); const modal = reactive({ type: '', title: '', notice: '', item: null, form: {} })

const dateText = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const today = dateText()
const fmt = (value) => (value || '').slice(0, 10)
const dayAfter = (value) => { if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return ''; const d = new Date(`${value}T00:00:00`); if (Number.isNaN(d.getTime())) return ''; d.setDate(d.getDate() + 1); return dateText(d) }
const validReason = (value, min, max) => { const n = String(value || '').trim().length; return n >= min && n <= max }
const nonNegativeOrBlank = (value) => value === '' || value === null || value === undefined || (Number.isFinite(Number(value)) && Number(value) >= 0)
const aidValidationError = computed(() => { if (!Number.isInteger(Number(aidForm.memberCount)) || Number(aidForm.memberCount) < 1 || Number(aidForm.memberCount) > 30) return '家庭成员数应为1-30人的整数'; if (!nonNegativeOrBlank(aidForm.annualIncome)) return '家庭年收入不得为负数'; if (!nonNegativeOrBlank(aidForm.debt)) return '家庭债务不得为负数'; if (!validReason(aidForm.statement, 10, 500)) return '困难情况说明需10-500字'; return '' })
const validLeave = computed(() => !!leaveForm.startTime && !!leaveForm.endTime && leaveForm.endTime >= leaveForm.startTime && validReason(leaveForm.reason, 5, 300))
const validAid = computed(() => !!aidForm.batchId && !aidValidationError.value && aidForm.confirm)
const validFunding = computed(() => !!fundForm.batchId && validReason(fundForm.statement, 5, 1000) && fundForm.confirm)
const filteredFundingBatches = computed(() => fundingBatches.value.filter((x) => x.projectType === fundForm.projectType))
const psyComplete = computed(() => (psy.value.questions || []).length > 0 && (psy.value.questions || []).every((q) => psyAnswers[q.key] != null))
const pendingDormTransfer = computed(() => dormTransfers.value.find((x) => ['SUBMITTED', 'COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'DORM_REVIEW', 'PENDING'].includes(x.status || x.currentNode)) || null)
const availableDormBeds = computed(() => dormBeds.value.filter((x) => x.status === 'VACANT' && !x.isCurrent))
const selectedDormTarget = computed(() => { const b = dormBuildings.value.find((x) => String(x.buildingId) === String(dormForm.buildingId)) || {}; const r = dormRooms.value.find((x) => String(x.roomId) === String(dormForm.roomId)) || {}; const bd = dormBeds.value.find((x) => String(x.bedId) === String(dormForm.bedId)) || {}; return [b.buildingName, r.roomNo && `${r.roomNo}室`, bd.bedNo && `${bd.bedNo}床`].filter(Boolean).join(' / ') || `床位 #${dormForm.bedId}` })
const validDormTransfer = computed(() => !!dormForm.bedId && validReason(dormForm.reason, 5, 300) && !pendingDormTransfer.value)
const creditClaimError = computed(() => { if (modal.type !== 'credit') return ''; const value = Number(modal.form.claimValue); if (!Number.isFinite(value) || value <= 0) return '主张数值必须大于0'; if (value > 9999.99) return '主张数值不得超过9999.99'; if (Math.abs(Math.round(value * 100) - value * 100) > 1e-8) return '主张数值最多保留2位小数'; return '' })
const modalValidationError = computed(() => { const f = modal.form || {}; if (modal.type === 'leave') return (!f.startTime || !f.endTime || f.endTime < f.startTime || !validReason(f.reason, 5, 300)) ? '请填写有效起止日期和5-300字事由' : ''; if (modal.type === 'aid') { if (!Number.isInteger(Number(f.memberCount)) || Number(f.memberCount) < 1 || Number(f.memberCount) > 30) return '家庭成员数应为1-30人的整数'; if (!nonNegativeOrBlank(f.annualIncome) || !nonNegativeOrBlank(f.debt)) return '年收入和债务不得为负数'; return validReason(f.statement, 10, 500) ? '' : '困难情况说明需10-500字' } if (modal.type === 'funding') return validReason(f.statement, 5, 1000) ? '' : '申请理由需5-1000字'; if (modal.type === 'credit') return creditClaimError.value || (validReason(f.reason, 5, 1000) ? '' : '申诉理由需5-1000字'); return '' })
const modalValid = computed(() => !!modal.type && !modalValidationError.value)

watch(filteredFundingBatches, (list) => { if (!list.some((x) => x.batchId === fundForm.batchId)) fundForm.batchId = list[0]?.batchId || '' })
watch(aidBatches, (list) => { if (!list.some((x) => x.batchId === aidForm.batchId)) aidForm.batchId = list[0]?.batchId || '' })

const fundingLabel = (type) => ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', TUITION_REDUCTION: '学费减免', TEMPORARY_AID: '临时补助' }[type] || type)
const appealLabel = (status) => ({ SUBMITTED: '申诉已提交', REVIEWING: '复核中', UPHELD: '维持原处分', REVISED: '处分已变更', REVOKED: '处分已撤销' }[status] || status || '未申诉')
const creditLabel = (type) => ({ SECOND_CLASS: '第二课堂', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }[type] || type)
const notifyError = (e, fallback) => ui.notify(e?.message || fallback)

async function reload() {
  loading.value = true; Object.keys(errors).forEach((key) => delete errors[key])
  const tasks = { leave: portalApi.affairsLeave(), aid: portalApi.affairsAid(), funding: portalApi.affairsFunding(), discipline: portalApi.affairsDiscipline(), psy: portalApi.affairsPsyQuestions(), psyHistory: portalApi.affairsPsyHistory(), activities: portalApi.affairsActivitiesMy(), aidBatches: portalApi.affairsAidBatches(), fundingBatches: portalApi.affairsFundingBatches(), talk: portalApi.affairsTalk(), dorm: portalApi.affairsDorm(), secondClass: affairsFourEndApi.secondClassReport(), creditAppeals: affairsFourEndApi.myCreditAppeals(), dormTransfers: affairsFourEndApi.myDormTransfers() }
  const entries = Object.entries(tasks); const results = await Promise.allSettled(entries.map(([, task]) => task))
  results.forEach((result, index) => {
    const key = entries[index][0]
    if (result.status === 'rejected') errors[key === 'psyHistory' ? 'psy' : key === 'aidBatches' ? 'aid' : key === 'fundingBatches' ? 'funding' : key === 'secondClass' || key === 'creditAppeals' ? 'activity' : key === 'dormTransfers' ? 'dorm' : key] = result.reason?.message || '数据加载失败'
    else {
      const value = result.value || {}
      if (key === 'leave') leave.value = value; else if (key === 'aid') aid.value = value; else if (key === 'funding') funding.value = value; else if (key === 'discipline') discipline.value = value; else if (key === 'psy') psy.value = value; else if (key === 'psyHistory') psyHistory.value = value; else if (key === 'activities') activities.value = value; else if (key === 'aidBatches') aidBatches.value = value.items || []; else if (key === 'fundingBatches') fundingBatches.value = value.items || []; else if (key === 'talk') talk.value = value; else if (key === 'dorm') dorm.value = value; else if (key === 'secondClass') secondClass.value = { items: [], byType: [], ...value }; else if (key === 'creditAppeals') creditAppeals.value = value.items || []; else if (key === 'dormTransfers') dormTransfers.value = value.items || []
    }
  })
  loading.value = false
}

async function run(task, success, fallback) { busy.value = true; try { const data = await task(); ui.notify(success); await reload(); return { ok: true, data } } catch (e) { notifyError(e, fallback); return { ok: false, error: e } } finally { busy.value = false } }
async function applyLeave() { if (!validLeave.value) return ui.notify('请填写有效日期和5-300字事由'); const result = await run(() => portalApi.affairsServiceApply({ serviceKey: 'LEAVE', ...leaveForm }), '请假已提交', '请假提交失败'); if (result.ok) leaveForm.reason = '' }
async function cancelLeave(item) { if (!window.confirm('确认已返校或请假事项已结束，并提交销假申请？')) return; await run(() => affairsFourEndApi.cancelLeave(item.leaveId, item.version, '学生本人申请销假'), '销假申请已提交', '销假提交失败') }
function openExtend(item) { extendId.value = item.leaveId; extendForm.newEndTime = dayAfter(fmt(item.endTime)); extendForm.reason = '' }
function validExtend(item) { return !!extendForm.newEndTime && extendForm.newEndTime > fmt(item.endTime) && validReason(extendForm.reason, 5, 300) }
async function submitExtend(item) { if (!validExtend(item)) return ui.notify('新结束日期必须晚于原结束日期，续假事由需5-300字'); const result = await run(() => affairsFourEndApi.extendLeave(item.leaveId, item.version, extendForm.newEndTime, extendForm.reason), '续假申请已提交', '续假提交失败'); if (result.ok) extendId.value = '' }
async function editLeave(item) { busy.value = true; try { const data = await affairsFourEndApi.getReturnedLeave(item.leaveId); Object.assign(modal, { type: 'leave', title: '修改退回请假', notice: data.returnReason || item.returnReason, item: data, form: { leaveType: data.leaveType, startTime: fmt(data.startTime), endTime: fmt(data.endTime), reason: data.reason || '' } }) } catch (e) { notifyError(e, '加载失败') } finally { busy.value = false } }
async function submitAid() { if (!validAid.value) return ui.notify(aidValidationError.value || '请完成本人确认'); const body = { batchId: aidForm.batchId, applyLevel: aidForm.applyLevel, memberCount: Number(aidForm.memberCount), annualIncome: aidForm.annualIncome === '' || aidForm.annualIncome == null ? null : Number(aidForm.annualIncome), debt: aidForm.debt === '' || aidForm.debt == null ? null : Number(aidForm.debt), specialTags: aidForm.specialTags.split(/[,，]/).map((x) => x.trim()).filter(Boolean), statement: aidForm.statement, confirm: true }; const result = await run(() => portalApi.affairsAidApply(body), '困难认定申请已提交', '提交失败'); if (result.ok) { aidForm.statement = ''; aidForm.confirm = false } }
async function editAid(item) { busy.value = true; try { const data = await affairsFourEndApi.getReturnedAid(item.applyId); Object.assign(modal, { type: 'aid', title: '修改退回认定申请', notice: item.returnReason, item: data, form: { applyLevel: data.applyLevel, memberCount: data.memberCount, annualIncome: data.annualIncome, debt: data.debt, specialTags: Array.isArray(data.specialTags) ? data.specialTags.join('，') : '', statement: data.statement || '' } }) } catch (e) { notifyError(e, '加载失败') } finally { busy.value = false } }
async function submitAidObjection(item) { if (!validReason(aidObjections[item.applyId], 5, 500)) return ui.notify('异议理由需5-500字'); const result = await run(() => portalApi.affairsAidObjection({ applyId: item.applyId, reason: aidObjections[item.applyId] }), '异议已提交并进入老师待办', '异议提交失败'); if (result.ok) aidObjections[item.applyId] = '' }
async function submitFunding() { if (!validFunding.value) return ui.notify('请选择批次、填写5-1000字申请理由并确认'); const result = await run(() => portalApi.affairsFundingApply({ batchId: fundForm.batchId, statement: fundForm.statement, confirm: true }), '奖助申请已提交', '提交失败'); if (result.ok) { fundForm.statement = ''; fundForm.confirm = false } }
async function editFunding(item) { busy.value = true; try { const data = await affairsFourEndApi.getReturnedFunding(item.applicationId); Object.assign(modal, { type: 'funding', title: '修改退回奖助申请', notice: item.returnReason, item: data, form: { statement: data.statement || '' } }) } catch (e) { notifyError(e, '加载失败') } finally { busy.value = false } }
async function submitFundingAppeal(item) { if (!validReason(fundAppeals[item.applicationId], 5, 1000)) return ui.notify('申诉理由需5-1000字'); const result = await run(() => portalApi.affairsFundingAppeal({ applicationId: item.applicationId, reason: fundAppeals[item.applicationId] }), '申诉已提交并进入老师待办', '申诉提交失败'); if (result.ok) fundAppeals[item.applicationId] = '' }
async function loadDormOptions() { if (pendingDormTransfer.value) return ui.notify('已有调宿申请处理中，不能重复提交'); busy.value = true; try { const data = await affairsFourEndApi.dormTransferOptions(); dormBuildings.value = data.items || []; dormForm.visible = true } catch (e) { notifyError(e, '调宿选项加载失败') } finally { busy.value = false } }
async function loadRooms() { dormForm.roomId = ''; dormForm.bedId = ''; dormRooms.value = []; dormBeds.value = []; if (!dormForm.buildingId) return; try { const data = await affairsFourEndApi.dormTransferRooms(dormForm.buildingId); dormRooms.value = data.items || [] } catch (e) { notifyError(e, '房间加载失败') } }
async function loadBeds() { dormForm.bedId = ''; dormBeds.value = []; if (!dormForm.roomId) return; try { const data = await affairsFourEndApi.dormTransferBeds(dormForm.roomId); dormBeds.value = data.items || [] } catch (e) { notifyError(e, '床位加载失败') } }
function closeDormForm() { if (!busy.value) Object.assign(dormForm, { visible: false, buildingId: '', roomId: '', bedId: '', reason: '' }) }
async function submitDormTransfer() { if (!validDormTransfer.value) return ui.notify('请选择目标床位并填写5-300字调宿原因'); if (!window.confirm(`确认提交调宿？\n目标：${selectedDormTarget.value}\n审批完成前原床保持不变。`)) return; const result = await run(() => affairsFourEndApi.submitDormTransfer(dormForm.bedId, dormForm.reason), '调宿申请已提交', '调宿提交失败'); if (result.ok) closeDormForm() }
async function submitDisciplineAppeal(item) { if (!validReason(disciplineAppeals[item.caseId], 5, 1000)) return ui.notify('处分申诉理由需5-1000字'); const result = await run(() => portalApi.affairsDisciplineAppeal({ caseId: item.caseId, reason: disciplineAppeals[item.caseId] }), '处分申诉已提交', '申诉提交失败'); if (result.ok) disciplineAppeals[item.caseId] = '' }
async function submitPsy() { const answers = (psy.value.questions || []).map((q) => ({ qKey: q.key, score: psyAnswers[q.key] })); await run(() => portalApi.affairsPsySubmit({ answers }), '心理自评已提交', '自评提交失败') }
async function enroll(item) { await run(() => portalApi.affairsActivityEnroll(item.activityId), '报名成功', '报名失败') }
function openCreditAppeal(item) { Object.assign(modal, { type: 'credit', title: item ? '第二课堂记错申诉' : '第二课堂缺记申诉', notice: '', item, form: { appealType: item ? 'WRONG' : 'MISSING', activityId: item?.activityId || '', activityName: item?.remark || '', claimCreditType: item?.creditType || 'SECOND_CLASS', claimValue: item?.creditValue == null ? '' : String(item.creditValue), reason: '' } }) }
function closeModal() { if (!busy.value) Object.assign(modal, { type: '', title: '', notice: '', item: null, form: {} }) }
async function submitUpdatedAndResubmit({ update, resubmit, success }) { busy.value = true; try { const updated = await update(); modal.item = { ...(modal.item || {}), ...(updated || {}), version: updated?.version ?? modal.item?.version }; try { await resubmit(modal.item.version) } catch (e) { modal.notice = `修改已保存，但重新提交失败：${e?.message || '请保留当前内容后重试'}`; notifyError(e, '重新提交失败'); return false } ui.notify(success); await reload(); setTimeout(() => closeModal(), 0); return true } catch (e) { notifyError(e, '保存修改失败'); return false } finally { busy.value = false } }
async function submitModal() {
  if (!modalValid.value) return ui.notify(modalValidationError.value)
  if (modal.type === 'leave') { const id = modal.item.leaveId || modal.item.id; await submitUpdatedAndResubmit({ update: () => affairsFourEndApi.updateReturnedLeave(id, { ...modal.form, version: modal.item.version }), resubmit: (version) => affairsFourEndApi.resubmitLeave(id, version), success: '请假已修改并重新提交' }) }
  else if (modal.type === 'aid') { const id = modal.item.applyId; const body = { ...modal.form, memberCount: Number(modal.form.memberCount), annualIncome: modal.form.annualIncome === '' || modal.form.annualIncome == null ? null : Number(modal.form.annualIncome), debt: modal.form.debt === '' || modal.form.debt == null ? null : Number(modal.form.debt), specialTags: String(modal.form.specialTags || '').split(/[,，]/).map((x) => x.trim()).filter(Boolean), version: modal.item.version }; await submitUpdatedAndResubmit({ update: () => affairsFourEndApi.updateReturnedAid(id, body), resubmit: (version) => affairsFourEndApi.resubmitAid(id, version), success: '认定申请已修改并重新提交' }) }
  else if (modal.type === 'funding') { const id = modal.item.applicationId; await submitUpdatedAndResubmit({ update: () => affairsFourEndApi.updateReturnedFunding(id, { ...modal.form, version: modal.item.version }), resubmit: (version) => affairsFourEndApi.resubmitFunding(id, version), success: '奖助申请已修改并重新提交' }) }
  else if (modal.type === 'credit') { const result = await run(() => affairsFourEndApi.submitCreditAppeal({ ...modal.form, claimValue: Number(modal.form.claimValue) }), '积分申诉已提交', '申诉提交失败'); if (result.ok) setTimeout(() => closeModal(), 0) }
}

onMounted(reload)
</script>

<style scoped>
.two { display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start }.form-grid { display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px }.form-grid.compact { max-width:760px }.form-grid label span,.inline-form label span { display:block;font-size:12px;color:var(--t3);margin-bottom:5px }.wide { grid-column:1/-1 }.record { padding:13px 0;border-bottom:1px solid #edf0f4 }.record-head { display:flex;justify-content:space-between;align-items:flex-start;gap:12px }.actions { display:flex;gap:8px;flex-wrap:wrap;margin-top:10px }.inline-form { margin-top:10px;padding:12px;background:#f8fafc;border-radius:10px;display:grid;gap:9px }.check { display:flex;align-items:flex-start;gap:8px;font-size:12.5px;color:var(--t2);margin:10px 0 }.warn { color:#b45309;font-size:12.5px;margin-top:5px }.field-error { color:#dc2626;font-size:12.5px;margin:5px 0 }.selected-target { padding:9px 11px;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-weight:600 }.section-title { font-size:15px;font-weight:650;margin:24px 0 8px }.domain-error { display:flex;gap:12px;align-items:center;padding:12px 16px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;color:#9a3412;margin-bottom:16px }.bed-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0 }.bed-grid div { background:#f8fafc;padding:12px;border-radius:9px }.bed-grid span,.bed-grid strong { display:block }.bed-grid span { font-size:12px;color:var(--t3);margin-bottom:4px }.question { padding:12px 0;border-bottom:1px solid #edf0f4 }.options { display:flex;gap:8px;flex-wrap:wrap;margin-top:8px }.seg { all:unset;cursor:pointer;padding:7px 12px;border-radius:8px;background:#f1f5f9;font-size:12.5px }.seg.on { background:var(--pri-50);color:var(--pri);font-weight:600 }.score-card { display:flex;justify-content:space-between;align-items:center;margin-bottom:16px }.score { display:flex;gap:18px;font-size:18px;font-weight:700;color:var(--pri) }.link { all:unset;display:block;cursor:pointer;color:var(--pri);font-size:12px;margin-top:5px }.mask { position:fixed;inset:0;background:rgba(15,23,42,.5);z-index:1000;display:flex;align-items:center;justify-content:center;padding:24px }.modal { width:min(680px,100%);max-height:88vh;overflow:auto }.dorm-form { max-width:700px }
@media(max-width:900px){.two,.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}.bed-grid{grid-template-columns:1fr 1fr}.score-card{align-items:flex-start;gap:14px;flex-direction:column}}
</style>
