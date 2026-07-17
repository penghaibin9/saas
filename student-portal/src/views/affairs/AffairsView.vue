<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">在校服务</p>
        <h1>学工事务</h1>
        <p class="sp-hero__sub">请假、奖助勤贷、困难认定、违纪申诉、心理自评、二课活动——一站办理与查询。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="reload">刷新</button>
    </section>

    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 总览 -->
      <section v-show="tab === 'overview'">
        <div class="sp-kpis">
          <div class="sp-kpi"><div class="sp-kpi__label">请假次数</div><div class="sp-kpi__value">{{ overview.leaveCount ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">已获资助</div><div class="sp-kpi__value">{{ overview.fundingGranted ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">困难认定通过</div><div class="sp-kpi__value">{{ overview.aidApproved ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">有效处分</div><div class="sp-kpi__value">{{ overview.disciplineActive ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">未闭环预警</div><div class="sp-kpi__value">{{ overview.riskOpen ?? 0 }}</div></div>
          <div class="sp-kpi"><div class="sp-kpi__label">谈话记录</div><div class="sp-kpi__value">{{ overview.talkCount ?? 0 }}</div></div>
        </div>
      </section>

      <!-- 我的申请 -->
      <section v-show="tab === 'applications'" class="sp-panel">
        <div class="sp-panel__head">我的申请</div>
        <StateBlock v-if="!(applications.applications || []).length" type="empty" text="暂无申请记录" />
        <div v-else class="sp-cardlist">
          <article v-for="a in applications.applications" :key="a.id" class="sp-card">
            <div class="sp-card__head">
              <h3 class="sp-card__title">{{ a.name }}</h3>
              <StatusTag :text="a.statusText || a.status" :tone="groupTone(a.group)" />
            </div>
            <p class="sp-card__meta">单号 {{ a.no }} · {{ a.dept }} · 提交于 {{ fmtTime(a.applyTime) }} · 经办：{{ a.handler || '待分配' }}</p>
            <p v-if="a.lastOpinion" class="sp-card__body">意见：{{ a.lastOpinion }}</p>
          </article>
        </div>
      </section>

      <!-- 请假 -->
      <section v-show="tab === 'leave'" class="sp-panel">
        <div class="sp-panel__head">
          我的请假
          <button class="sp-btn sp-btn--sm" :disabled="busy" @click="forms.leave = !forms.leave">发起请假</button>
        </div>
        <div v-if="forms.leave" class="sp-form">
          <label>请假类型
            <select v-model="leaveForm.leaveType">
              <option value="PERSONAL">事假</option><option value="SICK">病假</option><option value="OTHER">其他</option>
            </select>
          </label>
          <label>天数<input v-model.number="leaveForm.days" type="number" min="1" placeholder="请假天数" /></label>
          <label class="sp-form__full">事由<textarea v-model.trim="leaveForm.reason" placeholder="请假事由" /></label>
          <button class="sp-btn" :disabled="busy || !leaveForm.reason" @click="applyLeave">提交请假</button>
        </div>
        <AutoTable :rows="leave.items" empty="暂无请假记录" />
      </section>

      <!-- 奖助勤贷 -->
      <section v-show="tab === 'funding'" class="sp-panel">
        <div class="sp-panel__head">
          奖助勤贷补
          <button class="sp-btn sp-btn--sm" :disabled="busy" @click="forms.funding = !forms.funding">发起申请</button>
        </div>
        <div v-if="forms.funding" class="sp-form">
          <label>申请类型
            <select v-model="fundingForm.type">
              <option value="SCHOLARSHIP">奖学金</option><option value="GRANT">助学金</option>
              <option value="WORKSTUDY">勤工助学</option><option value="LOAN">助学贷款</option><option value="SUBSIDY">临时补助</option>
            </select>
          </label>
          <label class="sp-form__full">申请说明<textarea v-model.trim="fundingForm.reason" placeholder="申请理由" /></label>
          <label class="sp-form__full"><input v-model="fundingForm.commit" type="checkbox" style="width:auto;margin-right:6px;display:inline-block" />本人承诺所填信息真实（承诺书）</label>
          <button class="sp-btn" :disabled="busy || !fundingForm.reason || !fundingForm.commit" @click="applyFunding">提交申请</button>
        </div>
        <AutoTable :rows="funding.items" empty="暂无奖助记录" />
      </section>

      <!-- 困难认定 -->
      <section v-show="tab === 'aid'" class="sp-panel">
        <div class="sp-panel__head">
          困难认定
          <button class="sp-btn sp-btn--sm" :disabled="busy" @click="forms.aid = !forms.aid">申请认定</button>
        </div>
        <p class="sp-muted">当前认定等级：<StatusTag :text="aid.currentLevel || '未认定'" :tone="aid.currentLevel ? 'success' : 'default'" /></p>
        <div v-if="forms.aid" class="sp-form">
          <label>困难类型
            <select v-model="aidForm.level">
              <option value="GENERAL">一般困难</option><option value="DIFFICULT">困难</option><option value="SPECIAL">特别困难</option>
            </select>
          </label>
          <label>家庭年收入(元)<input v-model.number="aidForm.income" type="number" min="0" placeholder="家庭年收入" /></label>
          <label class="sp-form__full">家庭情况说明<textarea v-model.trim="aidForm.reason" placeholder="家庭经济情况" /></label>
          <label class="sp-form__full"><input v-model="aidForm.commit" type="checkbox" style="width:auto;margin-right:6px;display:inline-block" />本人承诺所填信息真实（承诺书）</label>
          <button class="sp-btn" :disabled="busy || !aidForm.reason || !aidForm.commit" @click="applyAid">提交认定申请</button>
        </div>
        <AutoTable :rows="aid.items" empty="暂无认定记录" />
      </section>

      <!-- 违纪 -->
      <section v-show="tab === 'discipline'" class="sp-panel">
        <div class="sp-panel__head">违纪处分</div>
        <p class="sp-muted">当前有效处分：{{ discipline.activeCount ?? 0 }} 项</p>
        <p class="sp-muted">{{ discipline.detailNote || '' }}</p>
        <div class="sp-actions" style="margin-top:12px">
          <button class="sp-btn sp-btn--ghost sp-btn--sm" :disabled="busy" @click="forms.appeal = !forms.appeal">提交申辩/申诉</button>
        </div>
        <div v-if="forms.appeal" class="sp-form">
          <label class="sp-form__full">申辩/申诉理由<textarea v-model.trim="appealForm.reason" placeholder="请说明申辩或申诉理由" /></label>
          <button class="sp-btn" :disabled="busy || !appealForm.reason" @click="submitAppeal">提交</button>
        </div>
      </section>

      <!-- 心理自评 -->
      <section v-show="tab === 'psy'" class="sp-panel">
        <div class="sp-panel__head">心理自评</div>
        <StateBlock v-if="!(psy.questions || []).length" type="empty" text="暂无自评问卷" />
        <div v-else>
          <div v-for="qn in psy.questions" :key="qn.key" class="sp-psy-q">
            <div class="sp-psy-q__text">{{ qn.text }}</div>
            <div class="sp-psy-q__opts">
              <label v-for="(opt, i) in qn.options" :key="i" class="sp-psy-opt">
                <input type="radio" :name="qn.key" :value="i" v-model="psyAnswers[qn.key]" /> {{ opt }}
              </label>
            </div>
          </div>
          <button class="sp-btn" :disabled="busy || !psyComplete" @click="submitPsy">提交自评</button>
        </div>
        <AutoTable :rows="psyHistory.items" empty="暂无自评历史" title="历史记录" />
      </section>

      <!-- 二课活动 -->
      <section v-show="tab === 'activities'" class="sp-panel">
        <div class="sp-panel__head">二课 / 社团活动</div>
        <StateBlock v-if="!(activities.available || []).length" type="empty" text="暂无可报名活动" />
        <div v-else class="sp-cardlist">
          <article v-for="(a, i) in activities.available" :key="a.id || i" class="sp-card">
            <div class="sp-card__head">
              <h3 class="sp-card__title">{{ a.name || a.title }}</h3>
              <button class="sp-btn sp-btn--sm" :disabled="busy || !a.id" @click="enroll(a.id)">报名</button>
            </div>
            <p class="sp-card__meta">{{ a.time || a.startTime || '' }} · {{ a.location || '' }}</p>
          </article>
        </div>
        <AutoTable :rows="activities.mine" empty="暂无已报名活动" title="我报名的活动" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const tabs = [
  { key: 'overview', label: '总览' }, { key: 'applications', label: '我的申请' },
  { key: 'leave', label: '请假' }, { key: 'funding', label: '奖助勤贷' },
  { key: 'aid', label: '困难认定' }, { key: 'discipline', label: '违纪' },
  { key: 'psy', label: '心理自评' }, { key: 'activities', label: '二课活动' }
]
const tab = ref('overview')
const loading = ref(true)
const busy = ref(false)
const error = ref('')

const overview = ref({})
const applications = ref({})
const leave = ref({})
const funding = ref({})
const aid = ref({})
const discipline = ref({})
const psy = ref({})
const psyHistory = ref({})
const activities = ref({})

const forms = reactive({ leave: false, funding: false, aid: false, appeal: false })
const leaveForm = reactive({ leaveType: 'PERSONAL', days: 1, reason: '' })
const fundingForm = reactive({ type: 'SCHOLARSHIP', reason: '', commit: false })
const aidForm = reactive({ level: 'GENERAL', income: null, reason: '', commit: false })
const appealForm = reactive({ reason: '' })
const psyAnswers = reactive({})

const psyComplete = computed(() => (psy.value.questions || []).every((q) => psyAnswers[q.key] != null))

function groupTone(g) { return g === 'approved' || g === 'done' ? 'success' : g === 'rejected' ? 'danger' : 'warn' }
function fmtTime(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '—' }

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [ov, app, lv, fd, ad, dc, pq, ph, ac] = await Promise.all([
      portalApi.affairsOverview(), portalApi.affairsApplications(), portalApi.affairsLeave(),
      portalApi.affairsFunding(), portalApi.affairsAid(), portalApi.affairsDiscipline(),
      portalApi.affairsPsyQuestions(), portalApi.affairsPsyHistory(), portalApi.affairsActivitiesMy()
    ])
    overview.value = ov || {}; applications.value = app || {}; leave.value = lv || {}
    funding.value = fd || {}; aid.value = ad || {}; discipline.value = dc || {}
    psy.value = pq || {}; psyHistory.value = ph || {}; activities.value = ac || {}
  } catch (e) { error.value = e?.message || '学工数据加载失败' }
  finally { loading.value = false }
}

async function applyLeave() {
  busy.value = true
  try { await portalApi.affairsServiceApply({ category: 'LEAVE', ...leaveForm }); ui.notify('请假申请已提交'); forms.leave = false; leaveForm.reason = ''; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function applyFunding() {
  busy.value = true
  try { await portalApi.affairsFundingApply({ type: fundingForm.type, reason: fundingForm.reason, committed: true }); ui.notify('奖助申请已提交'); forms.funding = false; fundingForm.reason = ''; fundingForm.commit = false; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function applyAid() {
  busy.value = true
  try { await portalApi.affairsAidApply({ level: aidForm.level, income: aidForm.income, reason: aidForm.reason, committed: true }); ui.notify('困难认定申请已提交'); forms.aid = false; aidForm.reason = ''; aidForm.commit = false; reload() }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitAppeal() {
  busy.value = true
  try { await portalApi.affairsDisciplineAppeal({ reason: appealForm.reason }); ui.notify('申辩/申诉已提交'); forms.appeal = false; appealForm.reason = '' }
  catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function submitPsy() {
  busy.value = true
  try {
    const answers = (psy.value.questions || []).map((q) => ({ key: q.key, score: psyAnswers[q.key] }))
    await portalApi.affairsPsySubmit({ answers }); ui.notify('心理自评已提交'); reload()
  } catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function enroll(id) {
  busy.value = true
  try { await portalApi.affairsActivityEnroll(id); ui.notify('报名成功'); reload() }
  catch (e) { ui.notify(e?.message || '报名失败（演示租户为只读）') } finally { busy.value = false }
}

onMounted(reload)
watch(tab, () => { Object.keys(forms).forEach((k) => { forms[k] = false }) })
</script>

<style scoped>
.sp-psy-q { padding: 10px 0; border-bottom: 1px solid #f4f5f7; }
.sp-psy-q__text { font-size: 14px; color: #1d2129; margin-bottom: 8px; }
.sp-psy-q__opts { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.sp-psy-opt { font-size: 13px; color: #4e5969; }
</style>
