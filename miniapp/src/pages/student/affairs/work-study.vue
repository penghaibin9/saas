<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="勤工助学" subtitle="找岗位、申请与查补贴" back />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="state === 'ready'" class="page-pad stack">
        <view class="ws__summary card">
          <view><text class="ws__eyebrow">我的勤工进度</text><text class="ws__headline">{{ pendingCount }} 笔办理中 · {{ onboardCount }} 个在岗</text></view>
          <text class="hint">录用后先核验协议，再按实际工时登记月度考核和补贴。</text>
        </view>

        <view class="seg">
          <button class="seg__btn" :class="{ on: tab === 'posts' }" @click="tab = 'posts'">开放岗位 {{ total }}</button>
          <button class="seg__btn" :class="{ on: tab === 'mine' }" @click="tab = 'mine'">我的申请 {{ records.length }}</button>
        </view>

        <template v-if="tab === 'posts'">
          <view class="ws__search"><input v-model.trim="keyword" class="input" maxlength="100" placeholder="搜索岗位、部门或地点" confirm-type="search" @confirm="search" /><button class="btn btn-secondary" :disabled="refreshing" @click="search">查询</button></view>
          <view v-if="posts.length" class="stack">
            <view v-for="post in posts" :key="post.postId" class="card ws__post">
              <view class="row-between"><view class="flex-1"><text class="ws__dept">{{ post.deptName }}</text><text class="card-title">{{ post.postName }}</text></view><MobileStatusTag :status="post.myRecord?.status" :label="post.myRecord ? statusLabel(post.myRecord.status) : '可申请'" /></view>
              <view class="ws__facts">
                <text>地点：{{ post.workLocation || '录用后通知' }}</text><text>时段：{{ post.scheduleText || '与用人部门协商' }}</text>
                <text>计酬：{{ money(post.salary) }}</text><text>名额：剩余 {{ post.remainingHeadcount }} / {{ post.headcount }}</text>
                <text>月工时：最多 {{ numberText(post.monthlyHoursLimit, 40) }} 小时</text><text>截止：{{ dateText(post.applyEnd) || '招满即止' }}</text>
              </view>
              <text v-if="post.requirement" class="hint ws__requirement">{{ post.requirement }}</text>
              <button v-if="!post.myRecord" class="btn" :disabled="!!busy || post.remainingHeadcount <= 0" @click="openApply(post)">{{ post.remainingHeadcount > 0 ? '申请这个岗位' : '名额已满' }}</button>
              <button v-else class="btn btn-secondary" @click="tab = 'mine'">查看我的申请</button>
            </view>
            <button v-if="posts.length < total" class="btn btn-secondary" :disabled="refreshing" @click="loadPosts(true)">加载更多</button>
          </view>
          <MobileGlobalState v-else state="empty" title="暂无开放岗位" description="可以修改搜索条件，或等待学校发布新岗位。" />
        </template>

        <template v-else>
          <view class="section-head"><text class="section-head__title">申请与在岗记录</text><text class="link" @click="loadRecords">刷新</text></view>
          <view v-if="records.length" class="stack">
            <view v-for="record in records" :key="record.recordId" class="card ws__record">
              <view class="row-between"><view class="flex-1"><text class="ws__dept">{{ record.post?.deptName }}</text><text class="card-title">{{ record.post?.postName || '勤工岗位' }}</text></view><MobileStatusTag :status="record.status" :label="statusLabel(record.status)" /></view>
              <view class="ws__flow"><text class="done">提交</text><text :class="{ done: passed(record.status, 1) }">录用</text><text :class="{ done: passed(record.status, 2) }">上岗</text><text :class="{ done: record.status === 'TERMINATED' }">结束</text></view>
              <text v-if="record.reason" class="ws__notice">处理意见：{{ record.reason }}</text>
              <text class="hint">可工作时段：{{ record.availability || '与用人部门协商' }}</text>
              <text class="hint">累计补贴：{{ money(record.subsidyTotal, '¥0.00') }}</text>
              <view v-if="record.monthly?.length" class="ws__months">
                <text class="ws__months-title">月度考核与补贴</text>
                <view v-for="item in record.monthly" :key="item.monthlyId" class="ws__month"><text>{{ item.monthCode }} · {{ item.workHours }}小时 · {{ ratingLabel(item.rating) }}</text><text>{{ money(item.subsidyAmount, '¥0.00') }}</text></view>
              </view>
              <button v-if="record.allowedActions?.includes('WITHDRAW')" class="btn btn-secondary" :disabled="!!busy" @click="confirmWithdraw(record)">撤回申请</button>
            </view>
          </view>
          <MobileGlobalState v-else state="empty" title="还没有勤工助学申请" description="切换到开放岗位，选择适合课余时间的岗位。" />
        </template>
      </view>
    </MobileGlobalState>

    <view v-if="applyTarget" class="ws__mask" @click.self="closeApply">
      <view class="card ws__sheet">
        <text class="ws__dept">{{ applyTarget.deptName }}</text><text class="card-title">申请 {{ applyTarget.postName }}</text>
        <view class="fld"><text class="lbl">申请说明（5–1000字）</text><textarea v-model.trim="form.statement" class="ta" maxlength="1000" placeholder="说明申请意愿或相关经验" /></view>
        <view class="fld"><text class="lbl">可工作时段（2–200字）</text><input v-model.trim="form.availability" class="input" maxlength="200" placeholder="如：工作日16:30后" /></view>
        <label class="ws__check" @click="form.confirmed = !form.confirmed"><text class="ws__box">{{ form.confirmed ? '✓' : '' }}</text><text>我已核对岗位地点、时段和月工时上限，确认自愿申请。</text></label>
        <text v-if="formError" class="ws__error">{{ formError }}</text>
        <view class="ws__actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeApply">取消</button><button class="btn flex-1" :disabled="!!busy || !formValid" @click="submitApply">{{ busy ? '提交中…' : '确认申请' }}</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() { return { state: 'loading', tab: 'posts', posts: [], records: [], total: 0, page: 1, keyword: '', appliedKeyword: '', refreshing: false, busy: '', applyTarget: null, formError: '', form: { statement: '', availability: '', confirmed: false } } },
  computed: {
    pendingCount() { return this.records.filter(x => ['APPLIED', 'APPROVED'].includes(x.status)).length },
    onboardCount() { return this.records.filter(x => x.status === 'ONBOARD').length },
    formValid() { return this.form.statement.length >= 5 && this.form.statement.length <= 1000 && this.form.availability.length >= 2 && this.form.availability.length <= 200 && this.form.confirmed }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) },
  onBackPress() { if (this.applyTarget) { this.closeApply(); return true } return false },
  methods: {
    statusLabel(s) { return ({ APPLIED: '待审核', APPROVED: '已录用', ONBOARD: '在岗', REJECTED: '未录用', WITHDRAWN: '已撤回', TERMINATED: '已结束' })[s] || '状态待确认' },
    ratingLabel(s) { return ({ GOOD: '优秀', PASS: '合格', FAIL: '不合格' })[s] || '待确认' },
    numberText(v, fallback) { return Number.isFinite(Number(v)) ? Number(v) : fallback },
    money(v, fallback = '面议') { return v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? fallback : `¥${Number(v).toFixed(2)}` },
    dateText(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' },
    passed(status, step) { return ({ APPLIED: 0, APPROVED: 1, ONBOARD: 2, TERMINATED: 3 }[status] || 0) >= step },
    async load() { this.state = 'loading'; try { await Promise.all([this.loadPosts(), this.loadRecords()]); this.state = 'ready' } catch (e) { this.state = 'error'; toast(normalizeError(e).text || '勤工助学数据加载失败') } },
    async loadPosts(more = false) { this.refreshing = true; try { const next = more ? this.page + 1 : 1; const d = await studentApi.getWorkStudyPosts({ page: next, pageSize: 10, keyword: this.appliedKeyword }); this.posts = more ? [...this.posts, ...(d.items || [])] : (d.items || []); this.total = Number(d.total || 0); this.page = next } finally { this.refreshing = false } },
    async loadRecords() { const d = await studentApi.getMyWorkStudy(); this.records = d.items || [] },
    search() { this.appliedKeyword = this.keyword.trim(); return this.loadPosts() },
    openApply(post) { this.applyTarget = post; this.form = { statement: '', availability: '', confirmed: false }; this.formError = '' },
    closeApply() { if (!this.busy) this.applyTarget = null },
    async submitApply() { if (!this.formValid || !this.applyTarget) { this.formError = '请完整填写申请说明、可工作时段并确认'; return } this.busy = 'apply'; try { await studentApi.applyWorkStudy(this.applyTarget.postId, { statement: this.form.statement, availability: this.form.availability, confirm: true }); toast('申请已提交'); this.applyTarget = null; this.tab = 'mine'; await Promise.all([this.loadPosts(), this.loadRecords()]) } catch (e) { this.formError = normalizeError(e).text || '申请失败，请重试' } finally { this.busy = '' } },
    confirmWithdraw(record) { uni.showModal({ title: '确认撤回申请？', content: `撤回“${record.post?.postName || '勤工岗位'}”申请后，本次流程结束。`, confirmText: '确认撤回', success: (res) => { if (res.confirm) this.withdraw(record) } }) },
    async withdraw(record) { this.busy = 'withdraw'; try { await studentApi.withdrawWorkStudy(record.recordId, record.version); toast('申请已撤回'); await Promise.all([this.loadPosts(), this.loadRecords()]) } catch (e) { toast(normalizeError(e).text || '撤回失败') } finally { this.busy = '' } }
  }
}
</script>

<style scoped>
.ws__summary { display:flex; flex-direction:column; gap:6px; }.ws__eyebrow,.ws__dept { display:block; color:var(--brand-primary); font-size:12px; font-weight:600; }.ws__headline { display:block; margin-top:3px; color:var(--text-primary); font-size:18px; font-weight:700; }.seg { display:flex; padding:3px; border-radius:10px; background:var(--bg-subtle); }.seg__btn { flex:1; padding:9px; border:0; border-radius:8px; color:var(--text-secondary); background:transparent; font-size:13px; }.seg__btn.on { color:var(--brand-primary); background:var(--bg-card); font-weight:600; }.ws__search { display:flex; gap:8px; }.ws__search .input { flex:1; }.ws__post,.ws__record { display:flex; flex-direction:column; gap:10px; }.ws__facts { display:grid; grid-template-columns:1fr 1fr; gap:7px 12px; color:var(--text-secondary); font-size:12px; line-height:1.45; }.ws__requirement { padding-top:8px; border-top:1px solid var(--border-light); }.ws__flow { display:grid; grid-template-columns:repeat(4,1fr); margin:4px 0; }.ws__flow text { padding:8px 0; border-top:2px solid var(--border-light); color:var(--text-tertiary); font-size:11px; text-align:center; }.ws__flow text.done { border-color:var(--brand-primary); color:var(--brand-primary); }.ws__notice { padding:8px; border-radius:8px; color:#9a4a23; background:#fff5ed; font-size:12px; }.ws__months { padding-top:8px; border-top:1px solid var(--border-light); }.ws__months-title { display:block; margin-bottom:4px; color:var(--text-primary); font-size:12px; font-weight:600; }.ws__month { display:flex; justify-content:space-between; padding:6px 0; color:var(--text-secondary); font-size:12px; }.ws__mask { position:fixed; z-index:1000; inset:0; display:flex; align-items:flex-end; background:rgba(15,23,42,.52); }.ws__sheet { width:100%; padding:18px; border-radius:18px 18px 0 0; }.fld { margin-top:12px; }.ws__check { display:flex; gap:8px; align-items:flex-start; margin-top:12px; color:var(--text-secondary); font-size:12px; line-height:1.5; }.ws__box { width:16px; height:16px; border:1px solid var(--border-strong); border-radius:4px; color:var(--brand-primary); text-align:center; line-height:16px; flex-shrink:0; }.ws__error { display:block; margin-top:8px; color:var(--danger); font-size:12px; }.ws__actions { display:flex; gap:10px; margin-top:14px; }
</style>
