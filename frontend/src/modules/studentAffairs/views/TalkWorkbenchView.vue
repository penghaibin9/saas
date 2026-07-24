<template>
  <ModulePageShell
    title="谈心谈话工作台"
    subtitle="发起谈话 · 谈话记录 · 跟进 / 办结 / 转风险 / 转家校"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="谈心谈话"
  >
    <div v-if="studentFilterLabel" class="tk-student-filter">
      <span>{{ studentFilterLabel }}</span>
      <button type="button" class="tk-chip" @click="clearStudentFilter">清除筛选</button>
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
        <span v-if="stats" class="tk-stat">完成率 {{ Math.round((stats.completionRate || 0) * 100) }}%（{{ stats.completed }}/{{ stats.total }}）</span>
        <AppPermissionButton :allowed="canBtn('studentAffairs.talk.create')" code="studentAffairs.talk.create" variant="primary" size="sm" @click="openCreate">发起谈话</AppPermissionButton>
      </div>
    </div>

    <div class="tk-workspace">
      <div class="tk-list">
        <LoadingState v-if="loading" text="正在加载谈话…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadList" />
        <EmptyState v-else-if="!filteredList.length && pagination.total === 0" title="暂无谈话记录" description="可点「发起谈话」圈定学生，或调整筛选条件" />
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
              <span v-if="it.psyMasked" class="tk-lock">🔒 涉密</span>
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
        <EmptyState v-if="!selected" title="请从左侧选择一条谈话" description="填写谈话记录或进行跟进 / 办结 / 转风险 / 转家校" />
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

          <!-- 待谈：内联记录表单 -->
          <section v-if="canRecord" class="tk-record">
            <div class="tk-record__title">填写谈话记录</div>
            <AppQuickPhrases scene-key="sa.talk.content" :group="selected.talkType" @pick="onPickContent" />
            <textarea ref="contentTa" v-model.trim="recordForm.content" class="tk-textarea" rows="4" placeholder="记录谈话过程与内容，不少于 20 字" />
            <AppQuickPhrases scene-key="sa.talk.result" @pick="onPickResult" />
            <div class="tk-record__row">
              <input ref="resultInput" v-model.trim="recordForm.result" class="tk-input tk-input--grow" placeholder="谈话小结（选填）" />
              <label class="tk-check"><input v-model="recordForm.needFollowUp" type="checkbox" /> 需持续跟进</label>
            </div>
            <p v-if="recordForm.error" class="tk-err">{{ recordForm.error }}</p>
            <AppPermissionButton :allowed="canBtn('studentAffairs.talk.create')" code="studentAffairs.talk.create" variant="primary" size="sm" :loading="acting" @click="submitRecord">提交记录（进 360）</AppPermissionButton>
          </section>

          <!-- 已谈话内容 + 跟进动作 -->
          <template v-else>
            <section class="tk-content">
              <div class="tk-content__title">谈话内容</div>
              <p class="tk-content__body" :class="{ 'tk-masked': selected.psyMasked }">{{ selected.content || '（无）' }}</p>
              <p v-if="selected.result" class="tk-content__result">小结：{{ selected.result }}</p>
              <p v-if="selected.relatedRiskId" class="tk-linked">已转风险单 #{{ selected.relatedRiskId }}</p>
              <p v-if="selected.relatedContactId" class="tk-linked">已转家校联系 #{{ selected.relatedContactId }}</p>
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
      :submitting="acting"
      @confirm="onDialogConfirm"
    />

    <!-- 发起谈话 drawer（批量圈定学生） -->
    <AppDrawer v-model:visible="createModal.visible" title="发起谈话计划">
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
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import {
  AppConfirmDialog, AppDateDisplay, AppDateTimePicker, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton,
  AppQuickPhrases, AppSelect, AppStatusTag, AppStudentPicker, AppTextInput
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
    ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog,
    AppDateDisplay, AppDateTimePicker, AppDrawer, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton,
    AppQuickPhrases, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, listError: '', list: [], statusCounts: null, stats: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      selected: null, acting: false,
      activeStatus: 'ALL', typeFilter: '',
      studentFilter: { studentId: '', studentNo: '', studentName: '' },
      statusMatch: null,
      recordForm: { content: '', result: '', needFollowUp: false, error: '' },
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '', reasonPlaceholder: '' },
      createModal: { visible: false, talkType: 'DAILY', topic: '', studentIds: [], scheduledAt: '', error: '' },
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
  },
  watch: {
    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.loadList() },
    typeFilter() { this.pagination.page = 1; this.loadList() }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
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
      return TALK_TYPE[t] || t || '—'
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
        if (this.selected) {
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
      this.recordForm = { content: '', result: '', needFollowUp: false, error: '' }
    },
    onPickContent(text) {
      const el = this.$refs.contentTa
      const { value, selStart, selEnd } = insertAtCursor(el, this.recordForm.content, text)
      this.recordForm.content = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickResult(text) {
      const el = this.$refs.resultInput
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
      if (!ok) this.recordForm.error = this._lastErr || '提交失败'
    },
    onAction(key) {
      const map = {
        follow: { action: 'follow', title: '转持续跟进', message: '将该谈话转入持续跟进。', type: 'primary', confirmText: '转跟进', requireReason: false, reasonLabel: '跟进说明', reasonPlaceholder: '选填' },
        close: { action: 'close', title: '办结谈话', message: '办结后该谈话闭环，写入学生 360。', type: 'primary', confirmText: '办结', requireReason: false },
        toRisk: { action: 'toRisk', title: '转风险单', message: '据本次谈话生成风险记录，进入风险处置流程。', type: 'warning', confirmText: '转风险', requireReason: false, reasonLabel: '风险说明', reasonPlaceholder: '选填，将写入风险明细' },
        toHomeSchool: { action: 'toHomeSchool', title: '转家校联系', message: '据本次谈话生成家校联系记录。', type: 'primary', confirmText: '转家校', requireReason: false, reasonLabel: '联系说明', reasonPlaceholder: '选填' }
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
      this.createModal = { visible: true, talkType: 'DAILY', topic: '', studentIds: [], scheduledAt: '', error: '' }
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
.tk-student-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--warning-50, #fffbeb);
  border: 1px solid var(--warning-200, #fde68a);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.tk-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
.tk-filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.tk-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.tk-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.tk-chip em {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.tk-tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.tk-stat {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.tk-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.tk-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.tk-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.tk-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 380px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.tk-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-2);
}
.tk-queue {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.tk-qitem {
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.tk-qitem:hover {
  border-color: var(--primary-300);
}
.tk-qitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.tk-qitem__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.tk-qitem__name {
  font-weight: 600;
  color: var(--text-primary);
}
.tk-qitem__mid {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.tk-lock {
  font-size: var(--font-size-xs);
  color: var(--danger-600, #dc2626);
  margin-left: var(--space-2);
}
.tk-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.tk-dhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.tk-dname {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.tk-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.tk-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0 0 var(--space-4);
}
.tk-kv > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tk-kv dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.tk-kv dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.tk-record,
.tk-content {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.tk-record__title,
.tk-content__title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.tk-record__row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-2) 0;
}
.tk-check {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
.tk-content__body {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  white-space: pre-wrap;
  margin: 0 0 var(--space-2);
}
.tk-masked {
  color: var(--text-tertiary);
  font-style: italic;
}
.tk-content__result {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--space-2);
}
.tk-linked {
  font-size: var(--font-size-xs);
  color: var(--primary-600);
  margin: 0 0 var(--space-1);
}
.tk-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.tk-terminal {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.tk-input {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.tk-input--grow {
  flex: 1;
}
.tk-textarea {
  width: 100%;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
  resize: vertical;
  box-sizing: border-box;
}
.tk-err {
  margin: var(--space-1) 0;
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
</style>
