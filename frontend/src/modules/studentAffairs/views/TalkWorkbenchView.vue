<template>
  <ModulePageShell
    title="谈心谈话工作台"
    subtitle="发起谈话 · 谈话记录 · 跟进 / 办结 / 转风险 / 转家校"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="谈心谈话"
  >
    <div class="tk-brief" :class="{ 'is-degraded': !!listError }" aria-label="谈话任务概况">
      <span>待处理 <strong>{{ pendingCount ?? '—' }}</strong></span>
      <span v-if="stats">完成率 <strong>{{ Math.round((stats.completionRate || 0) * 100) }}%</strong></span>
      <span v-if="studentFilterLabel">{{ studentFilterLabel }} <button type="button" @click="clearStudentFilter">清除</button></span>
      <span v-else-if="taskFilterSummary">{{ taskFilterSummary }} <button type="button" @click="clearTaskFilters">清除</button></span>
      <span v-if="listError" class="tk-brief__error">列表加载异常</span>
    </div>

    <div class="tk-toolbar">
      <div class="tk-filters">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          type="button"
          class="tk-chip"
          :class="{ 'is-on': activeStatus === f.key }"
          @click="setStatusFilter(f.key)"
        >
          {{ f.label }}<em>{{ f.count }}</em>
        </button>
      </div>
      <div class="tk-tools">
        <AppSelect v-model="typeFilter" class="tk-input" title="按类型筛选"
                   :options="[{ value: '', label: '全部类型' }, ...talkTypes]" />
        <AppPermissionButton :allowed="canBtn('studentAffairs.talk.create')" code="studentAffairs.talk.create" variant="primary" size="sm" @click="openCreate">发起谈话</AppPermissionButton>
      </div>
    </div>

    <div class="tk-workspace">
      <div class="tk-list">
        <LoadingState v-if="loading" text="正在加载谈话…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadList" />
        <div v-else-if="!filteredList.length && pagination.total === 0" class="tk-empty"><strong>暂无谈话记录</strong><span>可发起谈话，或调整筛选条件</span></div>
        <ul v-else class="tk-queue">
          <li
            v-for="it in filteredList"
            :key="it.talkId"
            class="tk-qitem"
            :class="{ 'is-active': selected && selected.talkId === it.talkId }"
            @click="select(it)"
          >
            <div class="tk-qitem__top">
              <span class="tk-qitem__name">{{ it.realName || ('学生#' + it.studentId) }}</span>
              <StatusTag :type="statusType(it.status)" :label="it.statusLabel" dot />
            </div>
            <div class="tk-qitem__mid">
              {{ talkTypeLabel(it.talkType) }} · {{ it.topic }}
              <span v-if="it.psyMasked" class="tk-lock">内容受限</span>
            </div>
          </li>
        </ul>
        <AppPagination
          v-if="pagination.total > pagination.pageSize"
          v-model:page="pagination.page"
          v-model:pageSize="pagination.pageSize"
          :total="pagination.total"
          @change="loadList"
        />
      </div>

      <div class="tk-detail">
        <div v-if="!selected" class="tk-empty tk-empty--detail"><strong>请从左侧选择一条谈话</strong><span>可填写记录、跟进、办结或转办</span></div>
        <template v-else>
          <div class="tk-dhead">
            <div>
              <h3 class="tk-dname">{{ selected.realName || ('学生#' + selected.studentId) }}</h3>
              <StatusTag :type="statusType(selected.status)" :label="selected.statusLabel" dot />
            </div>
            <button type="button" class="tk-refresh" title="刷新详情" @click="reloadDetail">↻</button>
          </div>

          <dl class="tk-kv">
            <div><dt>谈话类型</dt><dd>{{ talkTypeLabel(selected.talkType) }}</dd></div>
            <div><dt>谈话主题</dt><dd>{{ selected.topic || '—' }}</dd></div>
            <div><dt>谈话时间</dt><dd><AppDateDisplay :value="selected.talkAt" mode="datetime" empty-text="未记录" /></dd></div>
            <div><dt>是否需跟进</dt><dd>{{ selected.needFollow ? '是' : '否' }}</dd></div>
          </dl>

          <div v-if="canRecord" class="tk-record-prompt">
            <div><strong>待补谈话记录</strong><span>提交后写入学生 360</span></div>
            <AppPermissionButton :allowed="canBtn('studentAffairs.talk.create')" code="studentAffairs.talk.create" variant="primary" size="sm" @click="openRecord">填写记录</AppPermissionButton>
          </div>

          <!-- 已谈话内容 + 跟进动作 -->
          <template v-else>
            <section class="tk-content">
              <div class="tk-content__title">谈话内容</div>
              <p class="tk-content__body" :class="{ 'tk-masked': selected.psyMasked }">{{ selected.content || '（无）' }}</p>
              <p v-if="selected.result" class="tk-content__result">小结：{{ selected.result }}</p>
              <button v-if="selected.relatedRiskId" type="button" class="tk-linked" @click="goRelatedRisk">已转风险单 #{{ selected.relatedRiskId }} → 查看风险处置</button>
              <button v-if="selected.relatedContactId" type="button" class="tk-linked" @click="goRelatedFamily">已转家校联系 #{{ selected.relatedContactId }} → 查看联系记录</button>
            </section>
            <div v-if="detailActions.length" class="tk-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.talk.create')"
                v-for="a in detailActions"
                :key="a.key"
                code="studentAffairs.talk.create"
                :variant="a.tone === 'primary' ? 'primary' : 'secondary'"
                size="sm"
                :loading="acting"
                @click="onAction(a.key)"
              >
                {{ a.label }}
              </AppPermissionButton>
            </div>
            <p v-else class="tk-terminal">该谈话已办结，仅可查看。</p>
          </template>
        </template>
      </div>
    </div>

    <!-- 跟进/办结/转风险/转家校 确认 -->
    <AppConfirmDialog
      v-model:visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :type="dialog.type"
      :confirm-text="dialog.confirmText"
      :require-reason="dialog.requireReason"
      :reason-label="dialog.reasonLabel"
      :reason-placeholder="dialog.reasonPlaceholder"
      :phrase-scene-key="dialog.phraseSceneKey"
      :submitting="acting"
      @confirm="onDialogConfirm"
    />

    <AppDrawer v-model:visible="recordDrawerVisible" :title="`填写谈话记录 · ${selected?.realName || '该生'}`" mode="modal" size="medium">
      <AppFormItem label="谈话内容（不少于 20 字）" required>
        <AppQuickPhrases scene-key="sa.talk.content" :group="selected?.talkType" @pick="onPickContent" />
        <AppTextarea ref="contentTa" v-model="recordForm.content" :rows="5" :maxlength="2000" placeholder="客观记录谈话过程与主要内容" />
      </AppFormItem>
      <AppFormItem label="谈话小结">
        <AppQuickPhrases scene-key="sa.talk.result" @pick="onPickResult" />
        <AppTextInput ref="resultInput" v-model="recordForm.result" placeholder="结论或后续安排（选填）" />
      </AppFormItem>
      <label class="tk-check"><input v-model="recordForm.needFollowUp" type="checkbox" /> 需要持续跟进</label>
      <AppInlineAlert v-if="recordForm.error" type="danger" :description="recordForm.error" />
      <template #footer>
        <button type="button" class="tk-btn" :disabled="acting" @click="recordDrawerVisible = false">取消</button>
        <button type="button" class="tk-btn tk-btn--primary" :disabled="acting" @click="submitRecord">提交记录</button>
      </template>
    </AppDrawer>

    <!-- 发起谈话 drawer（批量圈定学生） -->
    <AppDrawer v-model:visible="createModal.visible" title="发起谈话计划" mode="modal" size="medium">
      <AppFormItem label="谈话类型" required>
        <AppSelect v-model="createModal.talkType" :options="talkTypes" />
      </AppFormItem>
      <AppFormItem label="谈话主题" required>
        <AppTextInput v-model="createModal.topic" placeholder="如：期中学业情况谈话" />
      </AppFormItem>
      <AppFormItem label="圈定学生（可多选）" required>
        <AppStudentPicker v-model="createModal.studentIds" multiple placeholder="按姓名 / 学号搜索添加学生" />
      </AppFormItem>
      <AppDateTimePicker v-model="createModal.scheduledAt" label="计划时间" />
      <AppInlineAlert v-if="createModal.error" type="danger" :description="createModal.error" />
      <template #footer>
        <button type="button" class="tk-btn" @click="createModal.visible = false">取消</button>
        <button type="button" class="tk-btn tk-btn--primary" :disabled="acting" @click="submitCreate">发起</button>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 谈心谈话工作台（/admin/student-affairs/talks）—— 13A P6。
 * 真实对接 /api/v1/student-affairs/talks/*：批量发起 → 填记录(≥20字，进360) → 跟进/办结/转风险/转家校。
 * 心理(PSYCHOLOGY)类谈话内容对非授权角色脱敏。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import {
  AppConfirmDialog, AppDateDisplay, AppDateTimePicker, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton,
  AppQuickPhrases, AppSelect, AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { resolveTodoStatus, readStudentFilter } from '@/modules/studentAffairs/utils/todoFilterSemantics'


const STATUS_TYPE = {
  PLANNED: 'warning', SCHEDULED: 'processing', COMPLETED: 'success',
  FOLLOW_UP: 'processing', CLOSED: 'default', CANCELLED: 'default'
}
const TALK_TYPE = {
  DAILY: '日常谈话', ACADEMIC: '学业帮扶', PSYCHOLOGY: '心理疏导', DISCIPLINE: '违纪教育',
  EMPLOYMENT: '就业指导', INTERNSHIP: '实习指导', AID: '资助谈话', DORM: '宿舍问题'
}

export default {
  name: 'TalkWorkbenchView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppConfirmDialog,
    AppDateDisplay, AppDateTimePicker, AppDrawer, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton,
    AppQuickPhrases, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, listError: '', list: [], statusCounts: null, stats: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      selected: null, acting: false, recordDrawerVisible: false,
      activeStatus: 'ALL', typeFilter: '',
      studentFilter: { studentId: '', studentNo: '', studentName: '' },
      statusMatch: null,
      recordForm: { content: '', result: '', needFollowUp: false, error: '' },
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '', reasonPlaceholder: '' },
      createModal: { visible: false, talkType: 'DAILY', topic: '', studentIds: [], scheduledAt: '', error: '' },
      routeIntentConsumed: false,
      talkTypes: Object.entries(TALK_TYPE).map(([value, label]) => ({ value, label }))
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    pendingCount() {
      if (!this.statusCounts) return null
      return ['PLANNED', 'SCHEDULED', 'FOLLOW_UP'].reduce((total, key) => total + Number(this.statusCounts[key] || 0), 0)
    },
    taskFilterSummary() {
      return this.studentFilterLabel || (this.activeStatus !== 'ALL' ? `状态：${this.activeStatus}` : (this.typeFilter ? `类型：${this.typeFilter}` : ''))
    },
    canRecord() {
      return this.selected && ['PLANNED', 'SCHEDULED'].includes(this.selected.status)
    },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      let name = f.studentName || ''
      let no = f.studentNo || ''
      const id = f.studentId || ''
      if ((!name || !no) && id && this.list && this.list.length) {
        const hit = this.list.find((x) => String(x.studentId) === String(id))
        if (hit) {
          if (!name) name = hit.realName || ''
          if (!no) no = hit.studentNo || ''
        }
      }
      if (name || no) return `当前学生筛选：${name || '学生'}${no ? ` / ${no}` : ''}`
      return `当前学生筛选：#${id}`
    },
    statusFilters() {
      const c = (arr) => this.statusCounts === null ? '—' : arr.reduce((total, key) => total + (this.statusCounts[key] || 0), 0)
      return [
        { key: 'ALL', label: '全部', count: this.statusCounts === null ? '—' : (this.statusCounts.ALL || 0) },
        { key: 'PLANNED', label: '待谈', count: c(['PLANNED', 'SCHEDULED']) },
        { key: 'COMPLETED', label: '已谈话', count: c(['COMPLETED']) },
        { key: 'FOLLOW_UP', label: '跟进中', count: c(['FOLLOW_UP']) },
        { key: 'CLOSED', label: '已办结', count: c(['CLOSED']) }
      ]
    },
    filteredList() {
      let arr = this.list.filter((x) => this._matchStudent(x))
      if (this.statusMatch && this.statusMatch.length) {
        arr = arr.filter((x) => this.statusMatch.includes(x.status))
      } else if (this.activeStatus === 'PLANNED') {
        arr = arr.filter((x) => ['PLANNED', 'SCHEDULED'].includes(x.status))
      } else if (this.activeStatus !== 'ALL') {
        arr = arr.filter((x) => x.status === this.activeStatus)
      }
      if (this.typeFilter) arr = arr.filter((x) => x.talkType === this.typeFilter)
      return arr
    },
    detailActions() {
      const s = this.selected && this.selected.status
      if (['COMPLETED', 'FOLLOW_UP'].includes(s)) {
        return [
          { key: 'follow', label: '转持续跟进', tone: 'primary' },
          { key: 'close', label: '办结', tone: 'default' },
          { key: 'toRisk', label: '转风险', tone: 'default' },
          { key: 'toHomeSchool', label: '转家校', tone: 'default' }
        ]
      }
      return []
    }
  },
  created() {
    this.applyRouteFilters()
    this.loadList()
    this.loadStats()
    this.consumeRouteIntent()
  },
  watch: {
    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.loadList() },
    typeFilter() { this.pagination.page = 1; this.loadList() }
  },
  methods: {
    clearTaskFilters() {
      this.activeStatus = 'ALL'
      this.typeFilter = ''
      this.clearStudentFilter()
    },
    canBtn(code) { return canCode(this.ctx, code) },
    consumeRouteIntent() {
      if (this.routeIntentConsumed || this.$route.query?.intent !== 'create') return
      const sid = this.studentFilter?.studentId
      if (!sid || !this.canBtn('studentAffairs.talk.create')) return
      this.routeIntentConsumed = true
      this.openCreate()
    },
    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      if (!q.status) {
        this.activeStatus = 'ALL'
        this.statusMatch = null
        return
      }
      const resolved = resolveTodoStatus('talk', q.status)
      this.activeStatus = resolved.activeKey
      this.statusMatch = resolved.matchStatuses
    },
    _matchStudent(row) {
      const id = this.studentFilter && this.studentFilter.studentId
      if (!id) return true
      return String(row.studentId) === String(id)
    },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      const q = { ...this.$route.query }
      delete q.studentId
      delete q.studentNo
      delete q.studentName
      this.$router.replace({ query: q })
    },
    setStatusFilter(key) {
      this.activeStatus = key
      if (key === 'ALL') this.statusMatch = null
      else if (key === 'PLANNED') this.statusMatch = ['PLANNED', 'SCHEDULED']
      else this.statusMatch = [key]
      this.pagination.page = 1
      const q = { ...this.$route.query }
      if (key === 'ALL') delete q.status
      else q.status = key
      this.$router.replace({ query: q }).catch(() => {})
    },
    talkTypeLabel(t) {
      return TALK_TYPE[t] || (t ? '类型待确认' : '—')
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    async loadList() {
      this.loading = true
      this.listError = ''
      this.statusCounts = null
      const sid = this.studentFilter && this.studentFilter.studentId
      const res = await studentAffairsApi.getTalks({
        page: this.pagination.page,
        pageSize: this.pagination.pageSize,
        talkType: this.typeFilter,
        status: this.statusMatch && this.statusMatch.length ? this.statusMatch.join(',') : '',
        studentId: sid || ''
      })
      this.loading = false
      if (res.code === 0 && res.data) {
        this.list = res.data.items || []
        this.statusCounts = res.data.statusCounts || null
        this.pagination.total = res.data.total != null ? res.data.total : this.list.length
        const targetId = this.$route.query?.talkId
        if (targetId) {
          const hit = this.list.find((x) => String(x.talkId) === String(targetId))
          if (hit) this.select(hit)
          else {
            const detail = await studentAffairsApi.getTalkDetail(String(targetId))
            if (String(this.$route.query?.talkId) !== String(targetId)) return
            if (detail.code === 0 && detail.data) this.select(detail.data)
            else { this.selected = null; this.listError = detail.message || '无法读取指定谈话' }
          }
        } else if (this.selected) {
          const hit = this.list.find((x) => x.talkId === this.selected.talkId)
          if (hit) this.selected = hit
        }
      } else {
        this.listError = res.message || '加载失败'
      }
    },
    async loadStats() {
      const res = await studentAffairsApi.getTalkStats('TYPE')
      if (res.code === 0) this.stats = res.data
    },
    select(it) {
      this.selected = it
      this.recordDrawerVisible = false
      this.recordForm = { content: '', result: '', needFollowUp: false, error: '' }
    },
    openRecord() {
      this.recordForm.error = ''
      this.recordDrawerVisible = true
    },
    onPickContent(text) {
      const ref = this.$refs.contentTa
      const el = ref?.$refs?.el || ref
      const { value, selStart, selEnd } = insertAtCursor(el, this.recordForm.content, text)
      this.recordForm.content = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickResult(text) {
      const ref = this.$refs.resultInput
      const el = ref?.$refs?.input || ref
      const { value, selStart, selEnd } = insertAtCursor(el, this.recordForm.result, text)
      this.recordForm.result = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async reloadDetail() {
      if (!this.selected) return
      const res = await studentAffairsApi.getTalkDetail(this.selected.talkId)
      if (res.code === 0 && res.data) this.selected = res.data
      else toast.error(res.message || '刷新详情失败')
    },
    async submitRecord() {
      if (!this.recordForm.content || this.recordForm.content.length < 20) { this.recordForm.error = '谈话内容不少于 20 字'; return }
      const ok = await this.runAction(
        () => studentAffairsApi.recordTalk(
          this.selected.talkId,
          this.recordForm.content,
          this.recordForm.result,
          this.recordForm.needFollowUp,
          this.selected.version
        ),
        '谈话记录已提交（已进 360）'
      )
      if (ok) this.recordDrawerVisible = false
      else this.recordForm.error = this._lastErr || '提交失败'
    },
    goRelatedRisk() {
      if (!this.selected?.relatedRiskId) return
      this.$router.push({ name: 'student-affairs-risk-detail', params: { riskId: String(this.selected.relatedRiskId) }, query: { studentId: String(this.selected.studentId || ''), from: 'talk', talkId: String(this.selected.talkId || '') } })
    },
    goRelatedFamily() {
      if (!this.selected?.relatedContactId || !this.selected?.studentId) return
      this.$router.push({ path: '/admin/student-affairs/family', query: { studentId: String(this.selected.studentId), contactId: String(this.selected.relatedContactId), from: 'talk', talkId: String(this.selected.talkId || '') } })
    },
    onAction(key) {
      const map = {
        follow: { action: 'follow', title: '转持续跟进', message: '将该谈话转入持续跟进。', type: 'primary', confirmText: '转跟进', requireReason: true, reasonLabel: '跟进说明', reasonPlaceholder: '填写本次跟进情况和下一步安排', phraseSceneKey: 'sa.talk.result' },
        close: { action: 'close', title: '办结谈话', message: '办结后该谈话闭环，写入学生 360。', type: 'primary', confirmText: '办结', requireReason: true, reasonLabel: '办结结论', reasonPlaceholder: '填写办结依据和结论', phraseSceneKey: 'sa.talk.result' },
        toRisk: { action: 'toRisk', title: '转风险单', message: '据本次谈话生成风险记录，进入风险处置流程。', type: 'warning', confirmText: '转风险', requireReason: true, reasonLabel: '转风险依据', reasonPlaceholder: '填写观察到的风险信号和处置要求', phraseSceneKey: 'sa.risk.handle' },
        toHomeSchool: { action: 'toHomeSchool', title: '转家校联系', message: '据本次谈话生成家校联系记录。', type: 'primary', confirmText: '转家校', requireReason: true, reasonLabel: '家校联系说明', reasonPlaceholder: '填写需与家长沟通的事项和下一步安排', phraseSceneKey: 'sa.family.result' }
      }
      const d = map[key]
      if (!d) return
      this.dialog = { visible: true, reasonLabel: '说明', reasonPlaceholder: '', ...d }
    },
    async onDialogConfirm(payload) {
      const content = (payload && payload.reason) || ''
      const id = this.selected.talkId
      const map = { follow: 'FOLLOW', close: 'CLOSE', toRisk: 'TO_RISK', toHomeSchool: 'TO_HOME_SCHOOL' }
      const backendAction = map[this.dialog.action]
      if (!backendAction) return
      await this.runAction(
        () => studentAffairsApi.followUpTalk(id, backendAction, content, this.selected.version),
        { follow: '已转跟进', close: '已办结', toRisk: '已转风险单', toHomeSchool: '已转家校联系' }[this.dialog.action]
      )
      this.dialog.visible = false
    },
    openCreate() {
      const sid = this.studentFilter?.studentId
      this.createModal = { visible: true, talkType: 'DAILY', topic: '', studentIds: sid ? [String(sid)] : [], scheduledAt: '', error: '' }
    },
    async submitCreate() {
      const m = this.createModal
      const topic = (m.topic || '').trim()
      if (!topic) { m.error = '请填写谈话主题'; return }
      const ids = Array.isArray(m.studentIds) ? m.studentIds : (m.studentIds ? [m.studentIds] : [])
      if (!ids.length) { m.error = '请至少圈定一名学生'; return }
      const body = {
        studentIds: ids.map(String), talkType: m.talkType, topic,
        scheduledAt: m.scheduledAt ? m.scheduledAt.replace('T', ' ') + ':00' : null
      }
      this.acting = true
      const res = await studentAffairsApi.createTalk(body)
      this.acting = false
      if (res.code === 0) {
        toast.success(`已发起谈话（${(res.data.talkIds || []).length} 名学生）`)
        this.createModal.visible = false
        this.loadList()
        this.loadStats()
      } else {
        m.error = res.message || '发起失败'
        toast.error(m.error)
      }
    },
    async runAction(call, okMsg) {
      this.acting = true
      this._lastErr = ''
      const res = await call()
      if (res.code === 0) {
        toast.success(okMsg)
        if (res.data && res.data.talkId) this.selected = res.data
        else await this.reloadDetail()
        await this.loadList()
        this.loadStats()
        this.acting = false
        return true
      }
      this._lastErr = res.message || '操作失败'
      toast.error(this._lastErr)
      this.acting = false
      return false
    }
  }
}
</script>

<style scoped>
.tk-brief { display:flex;align-items:center;gap:8px 18px;min-height:34px;padding-bottom:10px;border-bottom:1px solid var(--line,var(--border-light));color:var(--text-secondary);font-size:var(--font-size-xs);flex-wrap:wrap }
.tk-brief strong { margin-left:4px;color:var(--text-primary);font-size:14px }
.tk-brief button { border:0;padding:0;background:transparent;color:var(--primary-600);cursor:pointer }
.tk-brief__error { color:var(--danger-600) }
.tk-brief.is-degraded { border-bottom-color:var(--warning-300,#fcd34d) }
.tk-toolbar { display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);flex-wrap:wrap;margin-bottom:var(--space-3) }
.tk-filters,.tk-tools,.tk-actions { display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap }
.tk-chip { display:inline-flex;align-items:center;gap:var(--space-1);height:30px;padding:0 var(--space-3);border:0;border-radius:0;background:transparent;color:var(--text-secondary);font-size:var(--font-size-sm);cursor:pointer }
.tk-chip.is-on { color:var(--primary-700);box-shadow:inset 0 -2px var(--primary-500) }
.tk-chip em { font-style:normal;font-size:var(--font-size-xs);color:var(--text-tertiary) }
.tk-btn { height:32px;padding:0 var(--space-3);border:1px solid var(--border-base);border-radius:var(--radius-base);background:var(--bg-card);color:var(--text-primary);font-size:var(--font-size-sm);cursor:pointer }
.tk-btn:disabled { opacity:.55;cursor:not-allowed }
.tk-btn--primary { background:var(--primary-600);border-color:var(--primary-600);color:#fff }
.tk-workspace { display:grid;grid-template-columns:minmax(280px,340px) minmax(0,1fr);gap:0;align-items:start;min-height:360px }
.tk-list { min-height:360px;padding-right:12px;border-right:1px solid var(--border-base);background:transparent }
.tk-empty { display:grid;gap:6px;padding:42px 16px;text-align:center;color:var(--text-tertiary);font-size:var(--font-size-xs) }
.tk-empty strong { color:var(--text-primary);font-size:var(--font-size-sm) }
.tk-empty--detail { padding-top:72px }
.tk-queue { list-style:none;margin:0;padding:0;display:flex;flex-direction:column }
.tk-qitem { padding:10px 12px;border-bottom:1px solid var(--border-light);cursor:pointer }
.tk-qitem:hover { background:var(--bg-soft,var(--primary-50)) }
.tk-qitem.is-active { background:var(--primary-50);box-shadow:inset 3px 0 var(--primary-500) }
.tk-qitem__top { display:flex;align-items:center;justify-content:space-between;gap:var(--space-2) }
.tk-qitem__name { font-weight:600;color:var(--text-primary) }
.tk-qitem__mid { margin-top:var(--space-1);font-size:var(--font-size-sm);color:var(--text-secondary) }
.tk-lock { margin-left:var(--space-2);color:var(--danger-600,#dc2626);font-size:var(--font-size-xs) }
.tk-detail { min-height:360px;padding:4px 0 0 20px;background:transparent }
.tk-dhead { display:flex;align-items:flex-start;justify-content:space-between;gap:var(--space-3);margin-bottom:var(--space-3) }
.tk-dname { margin:0 0 var(--space-2);font-size:var(--font-size-lg);color:var(--text-primary) }
.tk-refresh { width:28px;height:28px;border:1px solid var(--border-base);border-radius:var(--radius-base);background:var(--bg-card);color:var(--text-secondary);cursor:pointer }
.tk-kv { display:grid;grid-template-columns:1fr 1fr;gap:var(--space-2) var(--space-4);margin:0 0 var(--space-4) }
.tk-kv>div { display:flex;flex-direction:column;gap:2px }
.tk-kv dt { color:var(--text-tertiary);font-size:var(--font-size-xs) }
.tk-kv dd { margin:0;color:var(--text-primary);font-size:var(--font-size-sm) }
.tk-content,.tk-record-prompt,.tk-actions,.tk-terminal { padding-top:var(--space-3);border-top:1px solid var(--border-base) }
.tk-content__title { margin-bottom:var(--space-2);color:var(--text-primary);font-size:var(--font-size-sm);font-weight:600 }
.tk-content__body { margin:0 0 var(--space-2);color:var(--text-primary);font-size:var(--font-size-sm);white-space:pre-wrap }
.tk-content__result { margin:0 0 var(--space-2);color:var(--text-secondary);font-size:var(--font-size-sm) }
.tk-masked,.tk-terminal { color:var(--text-tertiary);font-size:var(--font-size-sm) }
.tk-masked { font-style:italic }
.tk-linked { display:block;margin:0 0 var(--space-1);padding:0;border:0;background:transparent;color:var(--primary-600);font:inherit;font-size:var(--font-size-xs);text-align:left;cursor:pointer }
.tk-linked:hover { text-decoration:underline }
.tk-record-prompt { display:flex;align-items:center;justify-content:space-between;gap:var(--space-3) }
.tk-record-prompt>div { display:grid;gap:2px }
.tk-record-prompt strong { color:var(--text-primary);font-size:var(--font-size-sm) }
.tk-record-prompt span { color:var(--text-tertiary);font-size:var(--font-size-xs) }
.tk-check { display:flex;align-items:center;gap:var(--space-1);color:var(--text-secondary);font-size:var(--font-size-sm);white-space:nowrap }
.tk-input { padding:var(--space-2);border:1px solid var(--border-base);border-radius:var(--radius-base);background:var(--bg-card);color:var(--text-primary);font-size:var(--font-size-sm);outline:none }
@media(max-width:720px){.tk-workspace{grid-template-columns:1fr}.tk-list{min-height:220px;padding:0 0 12px;border-right:0;border-bottom:1px solid var(--border-base)}.tk-detail{min-height:260px;padding:16px 0 0}.tk-tools{width:100%}.tk-input{flex:1;min-width:0}}
</style>
