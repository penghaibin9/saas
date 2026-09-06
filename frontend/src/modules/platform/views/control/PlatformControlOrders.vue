<template>
  <ModulePageShell title="合同订单与授权" subtitle="核对学校订单，分别处理支付入账与授权激活" :role-name="roleName" data-scope-name="当前查询范围">
    <template #actions><AppButton v-if="can('platform.order.manage') && !work" variant="primary" @click="startCreate">录入订单</AppButton></template>
    <div v-if="pendingNavigation" class="pcod__warning" role="alert"><strong>本次办理尚未结束</strong><p>离开会清除本页草稿或核验记录，不会撤销已经发送的请求。</p><button type="button" @click="pendingNavigation = null">继续办理</button><button type="button" :disabled="busy || leaving" @click="leave">确认离开</button></div>
    <section v-if="work" class="pcod__workspace" aria-labelledby="order-workspace-title">
      <header class="pcod__heading"><div><h3 id="order-workspace-title">{{ workTitle }}</h3><p>{{ work.schoolName }}<span v-if="work.row"> · {{ work.row.orderNo }}</span></p></div><span class="pcod__phase">{{ phaseLabel }}</span></header>
      <p v-if="workError" class="pcod__error" role="alert">{{ workError }}</p>
      <LoadingState v-if="optionsLoading" text="正在读取可选学校和套餐…" />
      <form v-else-if="phase === 'edit'" class="pcod__form" @submit.prevent="review">
        <template v-if="work.kind === 'create'">
          <div class="pcod__form-grid">
            <label>学校<select id="order-school" v-model="form.tenantId" required><option value="" disabled>请选择学校</option><option v-for="school in tenants" :key="school.tenantId" :value="school.tenantId">{{ school.tenantName }} · {{ school.tenantCode }}</option></select></label>
            <label>正式套餐<select id="order-package" v-model="form.packageCode" required @change="choosePackage"><option value="" disabled>请选择套餐</option><option v-for="plan in packages" :key="plan.packageCode" :value="plan.packageCode">{{ plan.packageName }}</option></select></label>
            <label>订单类型<select id="order-type" v-model="form.orderType"><option value="NEW">新购</option><option value="RENEW">续费</option><option value="UPGRADE">升级</option></select></label>
            <label>服务期（天）<input id="order-days" v-model="form.durationDays" inputmode="numeric" required /></label>
            <label>合同金额（元）<input id="order-amount" v-model="form.amount" inputmode="decimal" required placeholder="以实际合同约定为准" /></label>
          </div>
          <label>订单备注<textarea v-model="form.remark" rows="2" maxlength="500" /></label>
          <p class="pcod__note">录单只创建未支付订单，不会授予正式权限。请核对实际合同金额与服务期。</p>
        </template>
        <template v-else>
          <dl class="pcod__facts"><div><dt>学校</dt><dd>{{ work.row.tenantName }}</dd></div><div><dt>合同金额</dt><dd>{{ moneyLabel(work.row.amount) }}</dd></div><div><dt>当前状态</dt><dd>{{ orderStatus(work.row).label }}</dd></div><div><dt>订单版本</dt><dd>{{ work.row.version }}</dd></div></dl>
          <p class="pcod__note">{{ actionNote(work.action) }}</p>
          <label>变更原因<textarea v-model="reason" rows="3" minlength="5" maxlength="500" required placeholder="填写 5–500 个字符的原因" /></label>
        </template>
        <div class="pcod__ops"><button type="submit" class="pcod__primary" :disabled="busy || !can('platform.order.manage')">核对提交内容</button><button type="button" :disabled="busy" @click="askClose = true">返回订单清单</button></div>
      </form>
      <section v-else-if="phase === 'review' && prepared" class="pcod__review">
        <h4>核对本次办理对象</h4>
        <dl class="pcod__facts"><div><dt>学校</dt><dd>{{ prepared.schoolName }}</dd></div><div><dt>本次操作</dt><dd>{{ workTitle }}</dd></div><div v-if="work.kind === 'create'"><dt>金额 / 服务期</dt><dd>{{ moneyLabel(prepared.request.amount) }} / {{ prepared.request.durationDays }} 天</dd></div><div v-else><dt>订单与版本</dt><dd>{{ prepared.request.orderNo }} · {{ prepared.request.expectedVersion }}</dd></div></dl>
        <p class="pcod__note">这是提交内容核对，不是后端预演。{{ work.kind === 'create' ? '保存后仍需核实支付事实。' : actionNote(work.action) }}</p>
        <label>输入{{ work.kind === 'create' ? '学校编码' : '订单号' }} <strong>{{ prepared.confirmation }}</strong> 确认<input v-model="confirmation" autocomplete="off" spellcheck="false" /></label>
        <div class="pcod__ops"><button type="button" class="pcod__primary" :disabled="busy || confirmation !== prepared.confirmation || !can('platform.order.manage')" @click="submitPrepared">确认{{ work.kind === 'create' ? '创建未支付订单' : actionLabel(work.action) }}</button><button type="button" :disabled="busy" @click="phase = 'edit'; prepared = null; confirmation = ''">返回修改</button></div>
      </section>
      <LoadingState v-else-if="phase === 'saving'" text="正在提交，请勿重复操作…" />
      <section v-if="receipt" class="pcod__receipt" role="status" aria-live="polite"><h4>{{ receiptLabel }}</h4><p>订单 {{ receipt.orderNo }} · 版本 {{ receipt.version }}</p><p v-if="receipt.result === 'paid-pending'">支付事实已经入账。请刷新订单后仅执行“修复激活”，不要再次标记支付。</p><p v-else-if="receipt.result === 'created'">未支付订单已创建并核对学校归属，尚未授予正式权限。</p><button type="button" :disabled="busy" @click="finish">返回并刷新订单清单</button></section>
      <section v-if="phase === 'uncertain' || phase === 'conflict'" class="pcod__warning" role="alert"><h4>{{ phase === 'conflict' ? '版本已变化，停止本次提交' : '尚未取得可信执行回执' }}</h4><p>先重新读取订单并核对支付与审计记录。本页不会自动重试，也不会把读取结果冒充本次操作成功。</p><button type="button" :disabled="busy" @click="inspectOutcome">只读取订单状态</button><p v-if="readback">{{ readback }}</p><button v-if="readback" type="button" :disabled="busy" @click="askClose = true">已核对，关闭本次记录</button></section>
      <div v-if="askClose" class="pcod__warning" role="alert">清除本页草稿或核验记录不会撤销服务器变更。<button type="button" :disabled="busy" @click="closeWork">确认返回</button><button type="button" @click="askClose = false">继续办理</button></div>
    </section>
    <section v-else class="pcod__workspace" aria-label="订单查询与对账">
      <form class="pcod__toolbar" role="search" @submit.prevent="searchOrders"><label>学校名称或订单号<input v-model="keywordInput" placeholder="搜索学校名称 / 订单号" maxlength="100" /></label><label>支付状态<select v-model="statusInput"><option value="">全部</option><option value="unpaid">待支付</option><option value="paid">已支付</option><option value="cancelled">已取消</option><option value="refunded">已退款</option></select></label><button type="submit" class="pcod__primary">查询</button><button type="button" :disabled="loading" @click="load">刷新</button><button v-if="scope.tenantId || scope.status || scope.keyword" type="button" @click="clearScope">清除筛选</button></form>
      <p v-if="scope.tenantId" class="pcod__note">学校范围：{{ rows[0]?.tenantName || '当前选定学校' }} · 本页仅展示该校订单</p><div class="pcod__summary" role="status" aria-live="polite"><template v-if="!loading && !error"><span>当前结果 <b>{{ filteredRows.length }}</b> 笔</span><span>待支付 <b>{{ filteredRows.filter(row => row.status === 'unpaid').length }}</b> 笔</span><span>激活待修复 <b>{{ filteredRows.filter(row => row.status === 'paid' && row.repairTaskRequired === true).length }}</b> 笔</span><small>本次读取 {{ loadedAt }}</small></template><span v-else>{{ loading ? '正在读取订单' : '本次读取失败，未展示旧结果' }}</span></div>
      <LoadingState v-if="loading" text="正在加载订单…" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!filteredRows.length" text="当前条件下没有订单" />
      <template v-else><div class="pcod__table" tabindex="0" role="region" aria-label="合同订单，可横向滚动"><DataTable :columns="columns" :rows="visibleRows" row-key="orderNo"><template #cell-tenantName="{ row }"><strong>{{ row.tenantName || '学校名称未取得' }}</strong><small>{{ row.tenantId }}</small></template><template #cell-packageCode="{ row }">{{ packageLabel(row.packageCode) }}</template><template #cell-amount="{ row }">{{ moneyLabel(row.amount) }}</template><template #cell-status="{ row }"><StatusTag :type="orderStatus(row).tone" :label="orderStatus(row).label" /></template><template #cell-endAt="{ row }">{{ dateLabel(row.endAt) }}</template><template #cell-actions="{ row }"><div class="pcod__ops"><button v-for="action in can('platform.order.manage') ? orderActions(row) : []" :key="action" type="button" @click="openAction(row, action)">{{ actionLabel(action) }}</button><span v-if="!can('platform.order.manage') || !orderActions(row).length" class="pcod__muted">只读核对</span></div></template></DataTable></div><nav class="pcod__pagination" aria-label="订单分页"><span>每页 20 笔 · 第 {{ page }} / {{ pageCount }} 页</span><button type="button" :disabled="page <= 1" @click="page--">上一页</button><button type="button" :disabled="page >= pageCount" @click="page++">下一页</button></nav></template>
    </section>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { canEnterRoute, getPermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'
import { toPlatformUiContext } from '@/security/platformAccessGate'
import { platformRoleLabel } from '@/modules/platform/constants/platform-display.constants'
import { dateLabel } from '@/modules/platform/utils/tenantWorkspace.mjs'
import { orderScope, orderRows, orderId, orderStatus, orderActions, moneyLabel, createOrderDraft, actionDraft, orderReceipt } from '@/modules/platform/utils/orderWorkspace.mjs'

export default {
  name: 'PlatformControlOrders',
  components: { AppButton, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  data() { return { loading: true, error: '', rows: [], loadedAt: '', page: 1, epoch: 0, workEpoch: 0,
    scope: { tenantId: '', status: '', keyword: '' }, keywordInput: '', statusInput: '', work: null, phase: 'edit', workError: '',
    busy: false, optionsLoading: false, tenants: [], packages: [], form: {}, reason: '', confirmation: '', prepared: null,
    receipt: null, readback: '', askClose: false, pendingNavigation: null, leaving: false,
    columns: [{ key: 'tenantName', title: '学校', width: '190px' }, { key: 'orderNo', title: '订单号', width: '210px' },
      { key: 'packageCode', title: '套餐', width: '110px' }, { key: 'amount', title: '合同金额', width: '130px' },
      { key: 'status', title: '支付 / 激活', width: '190px' }, { key: 'endAt', title: '服务期至', width: '120px' }, { key: 'actions', title: '办理入口', width: '220px' }] } },
  computed: {
    roleName() { return platformRoleLabel(toPlatformUiContext()?.currentRole?.roleCode || 'PLATFORM') },
    filteredRows() { const keyword = this.scope.keyword.toLocaleLowerCase(); return keyword ? this.rows.filter(row => `${row.tenantName || ''} ${row.orderNo}`.toLocaleLowerCase().includes(keyword)) : this.rows },
    pageCount() { return Math.max(1, Math.ceil(this.filteredRows.length / 20)) },
    visibleRows() { return this.filteredRows.slice((this.page - 1) * 20, this.page * 20) },
    protectNavigation() { return Boolean(this.work && !this.receipt) || this.busy },
    workTitle() { return this.work?.kind === 'create' ? '录入合同订单' : this.actionLabel(this.work?.action) },
    phaseLabel() { return ({ edit: '填写资料', review: '核对内容', saving: '正在提交', saved: '执行回执', uncertain: '待核验', conflict: '版本冲突' })[this.phase] || '待核验' },
    receiptLabel() { return ({ created: '未支付订单已创建', activated: '支付已入账，授权已激活', 'paid-pending': '支付已入账，授权激活待修复', cancelled: '订单已取消' })[this.receipt?.result] || '待核验' }
  },
  watch: { '$route.fullPath'() { this.closeWork(false); this.load() } },
  created() { this.load() },
  mounted() { window.addEventListener('beforeunload', this.beforeUnload) },
  beforeUnmount() { this.epoch++; this.workEpoch++; window.removeEventListener('beforeunload', this.beforeUnload); this.work = null; this.prepared = null },
  beforeRouteUpdate(to) { return this.guardNavigation(to.fullPath) },
  beforeRouteLeave(to) { return this.guardNavigation(to.fullPath) },
  methods: {
    orderStatus, orderActions, moneyLabel, dateLabel,
    can(key) { return Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() && canEnterRoute({ moduleCode: 'PLATFORM', permissionKey: key }) },
    packageLabel(code) { return ({ basic: '基础版', standard: '标准版', professional: '专业版', private: '私有化版', trial: '试用版' })[code] || '套餐未取得' },
    actionLabel(action) { return ({ 'mark-paid': '标记已支付', cancel: '取消订单', 'repair-activation': '修复激活' })[action] || '订单办理' },
    actionNote(action) { return ({ 'mark-paid': '请先核实实际收款。确认后写入支付事实并尝试激活套餐；支付成功与激活成功分别展示。', cancel: '只取消尚未支付的订单，保留原订单和审计记录。', 'repair-activation': '仅修复这笔已支付订单的授权激活，不重复入账。' })[action] || '' },
    async load() {
      const epoch = ++this.epoch
      this.loading = true; this.error = ''; this.rows = []; this.loadedAt = ''; this.page = 1
      try {
        const scope = orderScope(this.$route.query)
        this.scope = scope; this.keywordInput = scope.keyword; this.statusInput = scope.status
        const result = await platformControlApi.listOrders(Object.fromEntries(Object.entries(scope).filter(([key, value]) => key !== 'keyword' && value)))
        if (epoch !== this.epoch) return
        if (result?.code !== 0) throw new Error(result?.message || '订单读取失败')
        this.rows = orderRows(result.data, scope); this.loadedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      } catch (error) { if (epoch === this.epoch) this.error = error?.message || '订单读取失败，请重试' }
      finally { if (epoch === this.epoch) this.loading = false }
    },
    searchOrders() {
      try { const scope = orderScope({ tenantId: this.scope.tenantId, status: this.statusInput, keyword: this.keywordInput }); this.$router.replace({ path: this.$route.path, query: Object.fromEntries(Object.entries(scope).filter(([, value]) => value)) }) }
      catch (error) { this.rows = []; this.loadedAt = ''; this.error = error.message }
    },
    clearScope() { this.$router.replace({ path: this.$route.path, query: {} }) },
    async startCreate() {
      if (this.work || !this.can('platform.order.manage')) return
      this.work = { kind: 'create', schoolName: '' }; this.phase = 'edit'; this.optionsLoading = true; this.workError = ''; this.tenants = []; this.packages = []
      this.form = { tenantId: this.scope.tenantId, packageCode: '', orderType: 'NEW', durationDays: '', amount: '', remark: '' }
      const epoch = ++this.workEpoch
      try {
        if (!this.can('platform.tenant.view') || !this.can('platform.commercial.view')) throw new Error('缺少选择学校或查看套餐的权限，请由具备相应职责的人员办理')
        const [schools, plans] = await Promise.all([platformControlApi.listTenants(), platformControlApi.listPackages()])
        if (epoch !== this.workEpoch) return
        if (schools?.code !== 0 || plans?.code !== 0) throw new Error(schools?.code !== 0 ? schools?.message || '学校清单未取得' : plans?.message || '套餐未取得')
        if (!Array.isArray(schools.data?.list) || schools.data.list.some(row => !orderId(row?.tenantId) || typeof row.tenantCode !== 'string' || !row.tenantCode) || !Array.isArray(plans.data?.list)) throw new Error('学校或套餐数据格式异常')
        this.tenants = schools.data.list; this.packages = plans.data.list.filter(row => row && typeof row.packageCode === 'string' && row.packageCode !== 'trial' && row.enabled !== false)
      } catch (error) { if (epoch === this.workEpoch) this.workError = error?.message || '录单资料读取失败' }
      finally { if (epoch === this.workEpoch) this.optionsLoading = false }
    },
    choosePackage() { const plan = this.packages.find(item => item.packageCode === this.form.packageCode); this.form.amount = plan?.price == null ? '' : String(plan.price); this.form.durationDays = plan?.durationDays == null ? '' : String(plan.durationDays) },
    openAction(row, action) {
      if (this.work || !this.can('platform.order.manage') || !this.rows.some(item => item.orderNo === row.orderNo && item.tenantId === row.tenantId && item.version === row.version) || !orderActions(row).includes(action)) return
      this.work = { kind: 'action', action, row: Object.freeze({ ...row }), schoolName: row.tenantName || '学校名称未取得' }; this.reason = ''; this.phase = 'edit'; this.workError = ''; this.receipt = null; this.readback = ''
    },
    review() {
      if (!this.work || this.phase !== 'edit' || this.busy || this.optionsLoading || !this.can('platform.order.manage')) return
      this.workError = ''
      try {
        const create = this.work.kind === 'create'
        const request = create ? createOrderDraft(this.form, this.tenants, this.packages) : actionDraft(this.work.row, this.work.action, this.reason)
        const school = create ? this.tenants.find(item => item.tenantId === request.tenantId) : null
        this.prepared = Object.freeze({ kind: this.work.kind, request, confirmation: create ? school.tenantCode : request.orderNo, schoolName: create ? school.tenantName : this.work.schoolName })
        this.confirmation = ''; this.phase = 'review'
      } catch (error) { this.workError = error.message }
    },
    async submitPrepared() {
      if (this.busy || this.phase !== 'review' || !this.prepared || !this.work || this.confirmation !== this.prepared.confirmation || !this.can('platform.order.manage')) return
      const prepared = this.prepared, request = prepared.request, epoch = ++this.workEpoch
      try {
        const fresh = prepared.kind === 'create' ? createOrderDraft(this.form, this.tenants, this.packages) : actionDraft(this.work.row, this.work.action, this.reason)
        if (JSON.stringify(fresh) !== JSON.stringify(request)) throw new Error('内容已变化，请重新核对')
      } catch (error) { this.phase = 'edit'; this.prepared = null; this.workError = error.message; return }
      this.busy = true; this.phase = 'saving'; this.workError = ''; this.readback = ''
      try {
        const result = prepared.kind === 'create' ? await platformControlApi.createOrder({ ...request }) : await platformControlApi.orderAction(request.orderNo, request.action, { expectedVersion: request.expectedVersion, reason: request.reason })
        if (epoch !== this.workEpoch) return
        if (result?.code !== 0) { this.phase = result?.bizCode === 'DATA_CONFLICT' || result?.code === 409 ? 'conflict' : 'uncertain'; this.workError = result?.message || '尚未取得执行结果'; return }
        const receipt = orderReceipt(result.data, prepared)
        if (prepared.kind === 'create') {
          const check = await platformControlApi.listOrders({ tenantId: request.tenantId })
          if (epoch !== this.workEpoch) return
          if (check?.code !== 0 || !orderRows(check.data, { tenantId: request.tenantId }).some(row => row.orderNo === receipt.orderNo && row.orderId === receipt.orderId)) throw new Error('订单已返回编号，但学校归属未完成核验；请先核对清单，不要重复录单')
        }
        this.receipt = receipt; this.phase = 'saved'
      } catch (error) { if (epoch === this.workEpoch) { this.phase = 'uncertain'; this.workError = error?.message || '请求中断，请先核对订单' } }
      finally { if (epoch === this.workEpoch) this.busy = false }
    },
    async inspectOutcome() {
      if (this.busy || !this.prepared || !['uncertain', 'conflict'].includes(this.phase)) return
      const request = this.prepared.request, epoch = ++this.workEpoch
      this.busy = true; this.readback = ''; this.workError = ''
      try {
        const result = await platformControlApi.listOrders({ tenantId: request.tenantId })
        if (epoch !== this.workEpoch) return
        if (result?.code !== 0) throw new Error(result?.message || '订单读取失败')
        const rows = orderRows(result.data, { tenantId: request.tenantId }), row = rows.find(item => item.orderNo === request.orderNo)
        this.readback = row ? `${row.orderNo}：${orderStatus(row).label}。这是当前状态，不代表本次操作回执。` : request.orderNo ? '本次查询没有找到该订单，请继续核对审计，不能据此重复执行。' : `已读取该校 ${rows.length} 笔订单。创建结果未确认，请在清单和审计中核对，避免重复录单。`
      } catch (error) { if (epoch === this.workEpoch) this.workError = error?.message || '核验读取失败' }
      finally { if (epoch === this.workEpoch) this.busy = false }
    },
    closeWork(refresh = true) { if (this.busy) return; this.workEpoch++; this.work = null; this.prepared = null; this.receipt = null; this.reason = ''; this.confirmation = ''; this.form = {}; this.workError = ''; this.readback = ''; this.askClose = false; this.optionsLoading = false; this.pendingNavigation = null; if (refresh) this.load() },
    finish() { if (this.receipt && !this.busy) this.closeWork() },
    guardNavigation(destination) { if (this.leaving || !this.protectNavigation) return true; this.pendingNavigation = destination; return false },
    async leave() { if (this.busy || this.leaving || !this.pendingNavigation) return; this.leaving = true; try { const failure = await this.$router.push(this.pendingNavigation); if (!failure) this.pendingNavigation = null } catch (error) { this.workError = error?.message || '暂未离开，本页办理记录仍保留' } finally { this.leaving = false } },
    beforeUnload(event) { if (this.protectNavigation) { event.preventDefault(); event.returnValue = '' } }
  }
}
</script>

<style scoped>
.pcod__workspace{background:var(--bg-card,#fff);border:1px solid var(--card-b,#e5eaf2);border-radius:14px;overflow:hidden;min-width:0;padding:20px}.pcod__heading,.pcod__toolbar,.pcod__summary,.pcod__pagination,.pcod__ops{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.pcod__heading{justify-content:space-between;align-items:flex-start}.pcod__heading h3,.pcod__review h4,.pcod__receipt h4{margin:0;color:var(--t1,#1c2844);font-size:17px}.pcod__heading p{margin:7px 0;color:var(--text-secondary,#65758b);font-size:13px}.pcod__phase{background:var(--pri-bg,#edf1ff);padding:5px 10px;border-radius:7px;color:var(--pri,#3c5cdb);font-size:12px}.pcod__toolbar{align-items:flex-end}.pcod__workspace label{display:block;font-size:13px;color:var(--t2,#526176);line-height:1.8}.pcod__workspace input,.pcod__workspace select,.pcod__workspace textarea{box-sizing:border-box;display:block;width:100%;margin-top:4px;padding:8px 11px;border:1px solid var(--card-b,#dde4ee);border-radius:8px;background:var(--bg-input,#fff);color:var(--t1,#1c2844);font:inherit;font-size:13px}.pcod__workspace textarea{resize:vertical}.pcod__workspace button,.pcod__warning button{font:inherit;font-size:13px;border:1px solid var(--card-b,#dde4ee);border-radius:8px;padding:8px 12px;cursor:pointer;background:var(--bg-card,#fff);color:var(--t1,#1c2844)}.pcod__workspace .pcod__primary{background:var(--pri,#3c5cdb);border-color:transparent;color:#fff}.pcod__workspace :disabled,.pcod__warning :disabled{opacity:.55;cursor:not-allowed}.pcod__workspace :is(button,input,select,textarea):focus-visible,.pcod__warning button:focus-visible{outline:2px solid var(--pri,#3c5cdb);outline-offset:3px}.pcod__summary{font-size:13px;color:var(--t2,#526176);margin:20px 0}.pcod__summary small{margin-left:auto}.pcod__summary b{color:var(--t1,#1c2844);font-size:17px}.pcod__table{overflow:auto;min-width:0}.pcod__table small{display:block;font-size:12px;color:var(--text-secondary,#728098);margin-top:5px}.pcod__pagination{justify-content:flex-end;border-top:1px solid var(--card-b,#e5eaf2);padding-top:16px;font-size:13px;color:var(--t2,#526176)}.pcod__pagination span{margin-right:auto}.pcod__form,.pcod__review{max-width:900px;margin-top:20px;display:flex;flex-direction:column;gap:18px}.pcod__form-grid,.pcod__facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.pcod__facts{margin:0}.pcod__facts dt{font-size:12px;color:var(--text-secondary,#728098)}.pcod__facts dd{margin:7px 0 0;font-size:14px;color:var(--t1,#1c2844);overflow-wrap:anywhere}.pcod__note,.pcod__warning,.pcod__receipt{padding:13px 16px;border-radius:9px;background:var(--pri-bg,#f2f5ff);font-size:13px;line-height:1.7;color:var(--t2,#526176)}.pcod__warning{background:var(--warn-l,#fff5e5);margin:14px 0}.pcod__warning button{margin:7px 8px 0 0}.pcod__receipt{margin-top:20px;border-left:3px solid var(--pri,#3c5cdb)}.pcod__error{font-size:13px;color:var(--danger-600,#b42318)}.pcod__muted{font-size:12px;color:var(--text-secondary,#728098)}@media(max-width:700px){.pcod__workspace{padding:14px}.pcod__form-grid,.pcod__facts{grid-template-columns:1fr}.pcod__summary small{margin-left:0}}
</style>
