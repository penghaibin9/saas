<template>
  <div class="work-study-student">
    <section class="sp-card ws-summary">
      <div>
        <span class="ws-eyebrow">勤工助学</span>
        <h2>从找岗位到补贴到账，都在这里查看</h2>
        <p class="sp-muted">按自己的课余时间自愿申请。录用后先完成协议核验，再开始排班和月度考核。</p>
      </div>
      <div class="ws-summary__metrics" aria-label="我的勤工概览">
        <button type="button" :class="{ active: tab === 'posts' }" @click="tab = 'posts'">
          <strong>{{ postTotal }}</strong><span>开放岗位</span>
        </button>
        <button type="button" :class="{ active: tab === 'mine' }" @click="tab = 'mine'">
          <strong>{{ records.length }}</strong><span>我的申请</span>
        </button>
        <div><strong>{{ onboardCount }}</strong><span>当前在岗</span></div>
      </div>
    </section>

    <div v-if="error" class="ws-error" role="alert">
      <div><strong>勤工助学数据暂时无法读取</strong><span>{{ error }}</span></div>
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </div>
    <StateBlock v-else-if="loading" type="loading" text="正在同步岗位与申请进度…" />

    <template v-else>
      <section v-if="tab === 'posts'" class="sp-card ws-panel">
        <div class="ws-panel__head">
          <div><strong>开放岗位</strong><span class="sp-muted">只显示仍在申请期内的岗位</span></div>
          <form class="ws-search" @submit.prevent="searchPosts">
            <input v-model.trim="keyword" class="sp-inp" maxlength="100" placeholder="搜索岗位、部门或地点" />
            <button class="sp-btn sp-btn--ghost" type="submit" :disabled="loadingPosts">查询</button>
          </form>
        </div>
        <StateBlock v-if="!posts.length" type="empty" text="当前没有匹配的开放岗位" />
        <div v-else class="ws-posts">
          <article v-for="post in posts" :key="post.postId" class="ws-post">
            <header>
              <div><span class="ws-dept">{{ post.deptName }}</span><h3>{{ post.postName }}</h3></div>
              <StatusTag :text="post.myRecord ? statusLabel(post.myRecord.status) : '可申请'" :tone="post.myRecord ? statusTone(post.myRecord.status) : 'success'" />
            </header>
            <dl>
              <div><dt>工作地点</dt><dd>{{ post.workLocation || '录用后通知' }}</dd></div>
              <div><dt>工作时段</dt><dd>{{ post.scheduleText || '与用人部门协商' }}</dd></div>
              <div><dt>计酬标准</dt><dd>{{ money(post.salary) }}</dd></div>
              <div><dt>剩余名额</dt><dd>{{ post.remainingHeadcount }} / {{ post.headcount }}</dd></div>
              <div><dt>月工时上限</dt><dd>{{ numberText(post.monthlyHoursLimit, 40) }} 小时</dd></div>
              <div><dt>申请截止</dt><dd>{{ dateTime(post.applyEnd) || '招满即止' }}</dd></div>
            </dl>
            <p v-if="post.requirement" class="ws-requirement">{{ post.requirement }}</p>
            <footer>
              <span class="sp-muted">{{ post.agreementRequired ? '上岗前需核验勤工助学协议' : '录用后按岗位安排上岗' }}</span>
              <button v-if="!post.myRecord" class="sp-btn" type="button" :disabled="!!busyId || post.remainingHeadcount <= 0" @click="openApply(post)">
                {{ post.remainingHeadcount > 0 ? '申请岗位' : '名额已满' }}
              </button>
              <button v-else class="sp-btn sp-btn--ghost" type="button" @click="tab = 'mine'">查看申请</button>
            </footer>
          </article>
        </div>
        <button v-if="posts.length < postTotal" class="sp-btn sp-btn--ghost ws-more" type="button" :disabled="loadingPosts" @click="loadMore">加载更多</button>
      </section>

      <section v-else class="sp-card ws-panel">
        <div class="ws-panel__head">
          <div><strong>我的申请与在岗记录</strong><span class="sp-muted">老师处理后，PC 与小程序会同步显示</span></div>
          <button class="sp-btn sp-btn--ghost" type="button" :disabled="loadingRecords" @click="loadRecords">刷新进度</button>
        </div>
        <StateBlock v-if="!records.length" type="empty" text="还没有勤工助学申请" />
        <article v-for="record in records" :key="record.recordId" class="ws-record">
          <header>
            <div><span class="ws-dept">{{ record.post?.deptName }}</span><h3>{{ record.post?.postName || `岗位 ${record.postId}` }}</h3></div>
            <StatusTag :text="statusLabel(record.status)" :tone="statusTone(record.status)" />
          </header>
          <div class="ws-progress" aria-label="办理进度">
            <span class="done">提交申请</span><span :class="{ done: passed(record.status, 'APPROVED') }">录用审核</span>
            <span :class="{ done: passed(record.status, 'ONBOARD') }">协议与上岗</span><span :class="{ done: record.status === 'TERMINATED' }">岗位结束</span>
          </div>
          <p v-if="record.reason" class="ws-reason">处理意见：{{ record.reason }}</p>
          <div class="ws-record__meta">
            <span>申请说明：{{ record.applyStatement || '未填写' }}</span>
            <span>可工作时段：{{ record.availability || '与用人部门协商' }}</span>
            <span>累计补贴：{{ money(record.subsidyTotal, '¥0.00') }}</span>
          </div>
          <details v-if="record.monthly?.length" class="ws-monthly">
            <summary>月度考核与补贴（{{ record.monthly.length }}）</summary>
            <div v-for="item in record.monthly" :key="item.monthlyId" class="ws-monthly__row">
              <span>{{ item.monthCode }}</span><span>{{ numberText(item.workHours, 0) }} 小时</span>
              <span>{{ ratingLabel(item.rating) }}</span><strong>{{ money(item.subsidyAmount, '¥0.00') }}</strong>
            </div>
          </details>
          <footer v-if="record.allowedActions?.includes('WITHDRAW')">
            <button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busyId" @click="withdrawTarget = record">撤回申请</button>
          </footer>
        </article>
      </section>
    </template>

    <div v-if="applyTarget" class="ws-mask" @click.self="closeApply">
      <section class="sp-card ws-dialog" role="dialog" aria-modal="true" aria-labelledby="ws-apply-title">
        <header><div><span class="ws-dept">{{ applyTarget.deptName }}</span><h3 id="ws-apply-title">申请 {{ applyTarget.postName }}</h3></div><button class="ws-close" type="button" aria-label="关闭" @click="closeApply">×</button></header>
        <label><span>申请说明（5-1000字）</span><textarea v-model.trim="form.statement" class="sp-inp" maxlength="1000" placeholder="说明申请意愿、相关经验或适合这个岗位的原因" /></label>
        <label><span>可工作时段（2-200字）</span><input v-model.trim="form.availability" class="sp-inp" maxlength="200" placeholder="如：周一至周五 16:30 后，周末全天" /></label>
        <label class="ws-confirm"><input v-model="form.confirmed" type="checkbox" />我已核对岗位地点、时段和月工时上限，确认自愿申请。</label>
        <p v-if="formError" class="field-error">{{ formError }}</p>
        <footer><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busyId" @click="closeApply">取消</button><button class="sp-btn" type="button" :disabled="!!busyId || !formValid" @click="submitApply">{{ busyId ? '正在提交…' : '确认申请' }}</button></footer>
      </section>
    </div>

    <div v-if="withdrawTarget" class="ws-mask" @click.self="withdrawTarget = null">
      <section class="sp-card ws-dialog ws-dialog--small" role="alertdialog" aria-modal="true" aria-labelledby="ws-withdraw-title">
        <h3 id="ws-withdraw-title">确认撤回申请？</h3>
        <p class="sp-muted">将撤回“{{ withdrawTarget.post?.postName || '勤工岗位' }}”申请。已录用或已上岗的记录不能在学生端撤回。</p>
        <footer><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busyId" @click="withdrawTarget = null">继续保留</button><button class="sp-btn" type="button" :disabled="!!busyId" @click="submitWithdraw">确认撤回</button></footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const tab = ref('posts')
const loading = ref(true)
const loadingPosts = ref(false)
const loadingRecords = ref(false)
const error = ref('')
const posts = ref([])
const records = ref([])
const postTotal = ref(0)
const page = ref(1)
const keyword = ref('')
const appliedKeyword = ref('')
const busyId = ref('')
const applyTarget = ref(null)
const withdrawTarget = ref(null)
const formError = ref('')
const form = reactive({ statement: '', availability: '', confirmed: false })

const onboardCount = computed(() => records.value.filter((item) => item.status === 'ONBOARD').length)
const formValid = computed(() => form.statement.length >= 5 && form.statement.length <= 1000 && form.availability.length >= 2 && form.availability.length <= 200 && form.confirmed)
const statusLabel = (status) => ({ APPLIED: '待审核', APPROVED: '已录用', ONBOARD: '在岗', REJECTED: '未录用', WITHDRAWN: '已撤回', TERMINATED: '已结束' })[status] || '状态待确认'
const statusTone = (status) => ({ APPLIED: 'warn', APPROVED: 'success', ONBOARD: 'success', REJECTED: 'danger', WITHDRAWN: 'default', TERMINATED: 'default' })[status] || 'default'
const ratingLabel = (rating) => ({ GOOD: '优秀', PASS: '合格', FAIL: '不合格' })[rating] || '待确认'
const dateTime = (value) => value ? String(value).replace('T', ' ').slice(0, 16) : ''
const numberText = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback
const money = (value, fallback = '面议') => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? fallback : `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const passed = (status, step) => ({ APPLIED: 0, APPROVED: 1, ONBOARD: 2, TERMINATED: 3 }[status] || 0) >= ({ APPROVED: 1, ONBOARD: 2 }[step] || 0)

async function loadPosts({ more = false } = {}) {
  loadingPosts.value = true
  try {
    const targetPage = more ? page.value + 1 : 1
    const data = await portalApi.affairsWorkStudyPosts({ page: targetPage, pageSize: 12, keyword: appliedKeyword.value })
    const rows = data?.items || []
    posts.value = more ? [...posts.value, ...rows] : rows
    postTotal.value = Number(data?.total || rows.length)
    page.value = targetPage
  } finally { loadingPosts.value = false }
}
async function loadRecords() {
  loadingRecords.value = true
  try { const data = await portalApi.affairsWorkStudyMy(); records.value = data?.items || [] }
  finally { loadingRecords.value = false }
}
async function load() {
  loading.value = true; error.value = ''
  try { await Promise.all([loadPosts(), loadRecords()]) }
  catch (e) { error.value = e?.message || '请稍后重试' }
  finally { loading.value = false }
}
function searchPosts() { appliedKeyword.value = keyword.value; return loadPosts() }
function loadMore() { return loadPosts({ more: true }) }
function openApply(post) { applyTarget.value = post; Object.assign(form, { statement: '', availability: '', confirmed: false }); formError.value = '' }
function closeApply() { if (!busyId.value) applyTarget.value = null }
async function submitApply() {
  if (!formValid.value || !applyTarget.value) { formError.value = '请填写5-1000字申请说明、2-200字可工作时段，并完成本人确认'; return }
  busyId.value = `apply-${applyTarget.value.postId}`; formError.value = ''
  try {
    await portalApi.affairsWorkStudyApply(applyTarget.value.postId, { statement: form.statement, availability: form.availability, confirm: true })
    ui.notify('申请已提交，老师处理后会同步更新进度')
    applyTarget.value = null; tab.value = 'mine'; await Promise.all([loadPosts(), loadRecords()])
  } catch (e) { formError.value = e?.message || '申请提交失败，请重试' }
  finally { busyId.value = '' }
}
async function submitWithdraw() {
  const record = withdrawTarget.value
  if (!record) return
  busyId.value = `withdraw-${record.recordId}`
  try { await portalApi.affairsWorkStudyWithdraw(record.recordId, record.version); ui.notify('申请已撤回'); withdrawTarget.value = null; await Promise.all([loadPosts(), loadRecords()]) }
  catch (e) { ui.notify(e?.message || '撤回失败，请刷新后重试') }
  finally { busyId.value = '' }
}

const registerWorkspaceForm = inject('registerWorkspaceForm', null)
const unregister = registerWorkspaceForm?.(() => !!applyTarget.value && (!!form.statement || !!form.availability || form.confirmed), () => !!busyId.value)
onMounted(load)
onBeforeUnmount(() => unregister?.())
</script>

<style scoped>
.work-study-student { display: grid; gap: 14px; }.ws-summary { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: center; padding: 18px 22px; }.ws-eyebrow,.ws-dept { color: var(--pri); font-size: 12px; font-weight: 700; }.ws-summary h2 { margin: 4px 0 5px; color: var(--t1); font-size: 20px; }.ws-summary p { margin: 0; }.ws-summary__metrics { display: flex; gap: 4px; padding: 4px; border-radius: 12px; background: var(--bg); }.ws-summary__metrics button,.ws-summary__metrics div { min-width: 88px; padding: 8px 12px; border: 0; border-radius: 9px; color: var(--t2); background: transparent; text-align: center; cursor: pointer; }.ws-summary__metrics button.active { color: var(--pri); background: #fff; box-shadow: 0 2px 8px rgba(16,24,40,.08); }.ws-summary__metrics strong,.ws-summary__metrics span { display: block; }.ws-summary__metrics strong { color: inherit; font-size: 17px; }.ws-summary__metrics span { margin-top: 2px; font-size: 11px; }.ws-error { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 14px 16px; border: 1px solid #f1b9b9; border-radius: 12px; color: #9a2929; background: #fff7f7; }.ws-error span { display: block; margin-top: 3px; font-size: 12px; }.ws-panel { padding: 16px; }.ws-panel__head { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 14px; }.ws-panel__head strong,.ws-panel__head span { display: block; }.ws-panel__head strong { color: var(--t1); font-size: 16px; }.ws-search { display: flex; gap: 8px; width: min(440px, 50%); }.ws-posts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }.ws-post,.ws-record { padding: 15px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }.ws-post header,.ws-record header,.ws-post footer,.ws-record footer { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }.ws-post h3,.ws-record h3,.ws-dialog h3 { margin: 3px 0 0; color: var(--t1); font-size: 16px; }.ws-post dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px 18px; margin: 14px 0; }.ws-post dl div { min-width: 0; }.ws-post dt { color: var(--t3); font-size: 11px; }.ws-post dd { overflow: hidden; margin: 2px 0 0; color: var(--t2); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.ws-requirement { min-height: 40px; margin: 0 0 12px; color: var(--t2); font-size: 12px; line-height: 1.6; }.ws-post footer { align-items: center; padding-top: 12px; border-top: 1px solid var(--line); }.ws-more { justify-self: center; margin-top: 14px; }.ws-record + .ws-record { margin-top: 10px; }.ws-record__meta { display: grid; gap: 4px; margin: 10px 0; color: var(--t2); font-size: 12px; }.ws-progress { display: grid; grid-template-columns: repeat(4, 1fr); margin: 16px 0 10px; }.ws-progress span { position: relative; padding-top: 12px; color: var(--t3); font-size: 11px; text-align: center; border-top: 2px solid var(--line); }.ws-progress span::before { position: absolute; top: -5px; left: 50%; width: 8px; height: 8px; border: 2px solid #fff; border-radius: 50%; background: var(--line); content: ''; transform: translateX(-50%); }.ws-progress span.done { color: var(--pri); border-color: var(--pri); }.ws-progress span.done::before { background: var(--pri); }.ws-reason { padding: 8px 10px; border-radius: 8px; color: #8a3d20; background: #fff5ed; font-size: 12px; }.ws-monthly { margin-top: 10px; color: var(--t2); font-size: 12px; }.ws-monthly summary { cursor: pointer; }.ws-monthly__row { display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--line); }.ws-record footer { justify-content: flex-end; margin-top: 10px; }.ws-mask { position: fixed; z-index: 2200; inset: 0; display: grid; place-items: center; padding: 20px; background: rgba(13,18,28,.52); }.ws-dialog { width: min(560px, 100%); }.ws-dialog--small { width: min(440px, 100%); }.ws-dialog > header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }.ws-dialog > label { display: grid; gap: 6px; margin-top: 12px; color: var(--t2); font-size: 13px; }.ws-close { width: 34px; height: 34px; border: 0; border-radius: 8px; color: var(--t2); background: var(--bg); font-size: 22px; cursor: pointer; }.ws-confirm { display: flex !important; grid-template-columns: auto 1fr; align-items: flex-start; line-height: 1.5; }.ws-dialog > footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
@media (max-width: 900px) { .ws-summary { grid-template-columns: 1fr; }.ws-summary__metrics { width: 100%; }.ws-summary__metrics > * { flex: 1; }.ws-posts { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .ws-panel__head { align-items: stretch; flex-direction: column; }.ws-search { width: 100%; }.ws-post dl { grid-template-columns: 1fr; }.ws-summary__metrics button,.ws-summary__metrics div { min-width: 0; padding-inline: 6px; } }
</style>
