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
          <AutoTable :rows="leave.items" empty="暂无请假记录" />
        </section>
      </div>

      <!-- 困难认定 -->
      <section v-else-if="tab === 'aid'" class="sp-card">
        <div class="sp-panel__head">家庭经济困难认定申请 <StatusTag :text="aid.currentLevel || '未认定'" :tone="aid.currentLevel ? 'success' : 'default'" /></div>
        <Wizard :steps="['填写信息', '上传材料', '签署承诺书']" :current="aidStep" style="margin-bottom:20px" />
        <template v-if="aidStep === 1">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:640px">
            <div><div class="sp-fieldlabel">困难类型</div>
              <select v-model="aidForm.level" class="sp-inp"><option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option></select></div>
            <div><div class="sp-fieldlabel">家庭年收入(元)</div><input v-model.number="aidForm.income" type="number" class="sp-inp" placeholder="家庭年收入" /></div>
            <div style="grid-column:1/3"><div class="sp-fieldlabel">困难情况说明</div><textarea v-model.trim="aidForm.reason" class="sp-inp" placeholder="请说明家庭经济困难的具体情况" /></div>
          </div>
          <button class="sp-btn" style="margin-top:18px" :disabled="!aidForm.reason" @click="aidStep = 2">下一步：上传材料</button>
        </template>
        <template v-else-if="aidStep === 2">
          <p class="sp-muted">佐证材料（低保证明 / 村委证明等）请在提交后按学校要求补交，或在学生小程序上传。</p>
          <div style="display:flex;gap:10px;margin-top:16px"><button class="sp-btn sp-btn--ghost" @click="aidStep = 1">上一步</button><button class="sp-btn" @click="aidStep = 3">下一步：签署承诺书</button></div>
        </template>
        <template v-else>
          <div class="promise">本人郑重承诺：以上所填家庭经济情况真实、准确，如有虚报将承担相应责任，并配合学校核查。</div>
          <label class="chk"><input v-model="aidForm.commit" type="checkbox" />我已阅读并同意以上承诺（电子签，将记录签署时间）</label>
          <p class="sp-muted" style="margin-top:8px">提交需学校已开放困难认定批次；若暂无开放批次，请等待学校发布后办理。</p>
          <div style="display:flex;gap:10px;margin-top:12px"><button class="sp-btn sp-btn--ghost" @click="aidStep = 2">上一步</button><button class="sp-btn" :disabled="busy || !aidForm.commit" @click="submitAid">提交认定申请</button></div>
        </template>
        <AutoTable :rows="aid.items" empty="暂无认定记录" title="认定记录" style="margin-top:16px" />
      </section>

      <!-- 奖助勤贷补 -->
      <section v-else-if="tab === 'funding'">
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <button v-for="f in fundTypes" :key="f.k" class="sp-tab" :class="{ 'is-active': fundForm.type === f.k }" @click="fundForm.type = f.k">{{ f.t }}</button>
        </div>
        <div class="two">
          <section class="sp-card">
            <div class="sp-panel__head">{{ fundLabel }}申请</div>
            <div class="sp-fieldlabel">申请理由</div>
            <textarea v-model.trim="fundForm.reason" class="sp-inp" style="margin-bottom:12px" placeholder="请说明申请理由" />
            <label class="chk"><input v-model="fundForm.commit" type="checkbox" />电子签署诚信承诺书</label>
            <p class="sp-muted" style="margin-top:8px">提交需学校已开放对应资助批次；若暂无开放批次，请等待学校发布后办理。</p>
            <button class="sp-btn" style="margin-top:8px" :disabled="busy || !fundForm.reason || !fundForm.commit" @click="applyFunding">提交申请</button>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">发放台账</div>
            <AutoTable :rows="funding.items" empty="暂无奖助记录" />
          </section>
        </div>
      </section>

      <!-- 违纪申诉 -->
      <section v-else-if="tab === 'discipline'" class="sp-card" style="max-width:640px;text-align:center;padding:30px">
        <template v-if="!discipline.activeCount">
          <span class="ok-ico"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4" /><circle cx="12" cy="12" r="9" /></svg></span>
          <div style="font-size:15px;font-weight:600;margin-top:14px">暂无违纪处分记录</div>
          <div class="sp-muted" style="margin-top:6px">如对处分决定有异议，可在收到处分决定书后 15 日内提交书面申辩。</div>
        </template>
        <template v-else>
          <div style="font-size:15px;font-weight:600">当前有效处分：{{ discipline.activeCount }} 项</div>
          <div class="sp-muted" style="margin-top:6px">{{ discipline.detailNote }}</div>
          <textarea v-model.trim="appealReason" class="sp-inp" style="margin-top:14px;text-align:left" placeholder="申辩 / 申诉理由" />
          <button class="sp-btn" style="margin-top:12px" :disabled="busy || !appealReason" @click="submitAppeal">提交申辩</button>
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
          <div v-for="(a, i) in activities.available" :key="a.id || i" class="sp-card" style="padding:16px">
            <div style="font-size:14px;font-weight:600">{{ a.name || a.title }}</div>
            <div class="sp-muted" style="margin-top:5px">{{ a.time || a.startTime || '' }} · {{ a.credit ?? 0 }} 学分</div>
            <button class="sp-btn sp-btn--sm" style="margin-top:12px;width:100%" :disabled="busy || !a.id" @click="enroll(a.id)">报名</button>
          </div>
        </div>
        <AutoTable :rows="activities.mine" empty="暂无已报名活动" title="我报名的活动" style="margin-top:16px" />
      </section>

      <!-- 谈心谈话 -->
      <section v-else-if="tab === 'talk'" class="sp-card" style="max-width:720px">
        <div style="font-size:15px;font-weight:600">我的谈话记录</div>
        <div class="sp-muted" style="margin:4px 0 16px">仅展示辅导员 / 导师与你的谈话摘要，只读</div>
        <StateBlock type="empty" text="暂无谈话记录" />
        <div class="notebox">谈心谈话记录由辅导员在学工系统登记后同步至此；如需回执确认将在此显示按钮。</div>
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
  { key: 'leave', label: '请假销假' }, { key: 'aid', label: '困难认定' }, { key: 'funding', label: '奖助勤贷补' },
  { key: 'discipline', label: '违纪申诉' }, { key: 'psy', label: '心理自评' }, { key: 'activity', label: '活动二课' }, { key: 'talk', label: '谈心谈话' }
]
const tab = ref('leave')
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const leave = ref({})
const aid = ref({})
const funding = ref({})
const discipline = ref({})
const psy = ref({})
const psyHistory = ref({})
const activities = ref({})

const leaveTypes = [{ k: 'PERSONAL', t: '事假' }, { k: 'SICK', t: '病假' }, { k: 'OTHER', t: '其他' }]
const fundTypes = [
  { k: 'SCHOLARSHIP', t: '奖学金' }, { k: 'GRANT', t: '助学金' }, { k: 'WORKSTUDY', t: '勤工助学' },
  { k: 'LOAN', t: '助学贷款' }, { k: 'SUBSIDY', t: '困难补助' }
]
const leaveForm = reactive({ leaveType: 'PERSONAL', startDate: '', endDate: '', reason: '' })
const aidStep = ref(1)
const aidForm = reactive({ level: 'GENERAL', income: null, reason: '', commit: false })
const fundForm = reactive({ type: 'SCHOLARSHIP', reason: '', commit: false })
const appealReason = ref('')
const psyAnswers = reactive({})

const fundLabel = computed(() => (fundTypes.find((f) => f.k === fundForm.type) || {}).t || '')
const psyComplete = computed(() => (psy.value.questions || []).every((q) => psyAnswers[q.key] != null))
const activityCredit = computed(() => (activities.value.mine || []).reduce((a, x) => a + (Number(x.credit) || 0), 0))

async function reload() {
  loading.value = true; error.value = ''
  try {
    const [lv, ad, fd, dc, pq, ph, ac] = await Promise.allSettled([
      portalApi.affairsLeave(), portalApi.affairsAid(), portalApi.affairsFunding(), portalApi.affairsDiscipline(),
      portalApi.affairsPsyQuestions(), portalApi.affairsPsyHistory(), portalApi.affairsActivitiesMy()
    ])
    const val = (r, d) => (r.status === 'fulfilled' ? (r.value ?? d) : d)
    leave.value = val(lv, {}); aid.value = val(ad, {}); funding.value = val(fd, {}); discipline.value = val(dc, {})
    psy.value = val(pq, {}); psyHistory.value = val(ph, {}); activities.value = val(ac, {})
  } catch (e) { error.value = e?.message || '学工数据加载失败' } finally { loading.value = false }
}
async function applyLeave() {
  busy.value = true
  try { await portalApi.affairsServiceApply({ serviceKey: 'LEAVE', reason: leaveForm.reason }); ui.notify('请假申请已提交'); leaveForm.reason = ''; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitAid() {
  busy.value = true
  try { await portalApi.affairsAidApply({ level: aidForm.level, income: aidForm.income, reason: aidForm.reason, committed: true }); ui.notify('困难认定申请已提交'); aidStep.value = 1; aidForm.reason = ''; aidForm.commit = false; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function applyFunding() {
  busy.value = true
  try { await portalApi.affairsFundingApply({ type: fundForm.type, reason: fundForm.reason, committed: true }); ui.notify('奖助申请已提交'); fundForm.reason = ''; fundForm.commit = false; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitAppeal() {
  busy.value = true
  try { await portalApi.affairsDisciplineAppeal({ reason: appealReason.value }); ui.notify('申辩已提交'); appealReason.value = '' }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitPsy() {
  busy.value = true
  try { await portalApi.affairsPsySubmit({ answers: (psy.value.questions || []).map((q) => ({ qKey: q.key, score: psyAnswers[q.key] })) }); ui.notify('测评已提交，结果仅本人与心理中心可见'); reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function enroll(id) {
  busy.value = true
  try { await portalApi.affairsActivityEnroll(id); ui.notify('报名成功'); reload() }
  catch (e) { ui.notify(e?.message || '报名失败（演示租户为只读）') } finally { busy.value = false }
}
function print(name) { ui.notify('已生成' + name + '打印留痕（演示）') }
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
