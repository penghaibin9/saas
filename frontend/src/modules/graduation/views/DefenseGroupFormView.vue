<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="groupId ? '编辑答辩组' : '新增答辩组'"
    :subtitle="groupId ? '核对排期、人员与学生分组，保存后回到答辩安排继续发布前检查。' : '先建立答辩组和人员安排，创建后再分配符合条件的学生。'"
    eyebrow="答辩与成绩"
    purpose="答辩组必须同时具备时间、地点、组长、秘书、评委和学生；本页做明显缺口预检，最终发布仍由服务端状态机裁决。"
    :status-text="statusText"
    :status-tone="obviousReady ? 'success' : 'warning'"
    back-label="返回答辩安排"
    back-to="/admin/graduation/defense"
    :busy="submitting"
  >
    <template #context>
      <div class="defense-context">
        <span>当前批次</span>
        <strong>{{ batchStore.selectedBatchName || activeBatchId || '未选择' }}</strong>
      </div>
      <div class="defense-context">
        <span>答辩时间</span>
        <strong>{{ form.defenseDate || '待安排' }}</strong>
      </div>
      <div class="defense-context">
        <span>已分配学生</span>
        <strong>{{ assigned.length }}/30</strong>
      </div>
      <div class="defense-context">
        <span>明显缺口</span>
        <strong>{{ preflightGaps.length }} 项</strong>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="loadError" :description="loadError" @retry="load" />
    <template v-else>
      <form class="ie-form" @submit.prevent="save">
        <section class="gd-form-section">
          <header class="gd-form-section__head">
            <div>
              <span>01 · 分组与排期</span>
              <strong>先确定答辩组身份、时间和地点</strong>
              <small>创建只是建立编排对象，不会自动发布给学生；编辑已发布分组后仍需重新发布。</small>
            </div>
          </header>

          <label class="ie-fld ie-fld--full">
            <span class="ie-lbl">答辩组名称 <i>*</i></span>
            <input v-model.trim="form.groupName" class="ie-in" placeholder="如 软件工程专业第一答辩组" autocomplete="off" />
            <AppTemplateChips :options="GROUP_NAME_CHIPS" @pick="(text) => (form.groupName = text)" />
          </label>
          <AppDateTimePicker v-model="form.defenseDate" class="ie-fld" label="答辩时间" hint="建议至少提前一周完成编排" />
          <label class="ie-fld">
            <span class="ie-lbl">答辩地点</span>
            <input v-model.trim="form.location" class="ie-in" placeholder="如 实训楼 A301" autocomplete="off" />
            <small class="ie-hint">发布前必须是可到达的真实地点，不能保留“待定”。</small>
          </label>
        </section>

        <section class="gd-form-section">
          <header class="gd-form-section__head">
            <div>
              <span>02 · 答辩职责</span>
              <strong>绑定组长、秘书和评委的真实教师身份</strong>
              <small>姓名快照只用于兼容历史数据；新配置优先绑定工号身份，回避冲突由服务端最终校验。</small>
            </div>
          </header>

          <div class="ie-fld">
            <span class="ie-lbl">答辩组长（副高及以上）</span>
            <AppGraduationMentorPicker v-model="form.chairMentorId" :query="{ valueMode: 'id' }" placeholder="按姓名 / 工号搜索组长" />
            <p v-if="!form.chairMentorId && form.chairName" class="ie-hint">历史快照：{{ form.chairName }}。重新选择后将绑定真实教师身份。</p>
          </div>
          <div class="ie-fld">
            <span class="ie-lbl">答辩秘书</span>
            <AppGraduationMentorPicker v-model="form.secretaryMentorId" :query="{ valueMode: 'id' }" placeholder="按姓名 / 工号搜索秘书" />
            <p v-if="!form.secretaryMentorId && form.secretaryName" class="ie-hint">历史快照：{{ form.secretaryName }}。重新选择后将绑定真实教师身份。</p>
          </div>
          <div class="ie-fld ie-fld--full">
            <span class="ie-lbl">评委名单（建议不少于 5 人）</span>
            <AppGraduationMentorPicker v-model="form.memberMentorIds" multiple :query="{ valueMode: 'id' }" placeholder="按姓名 / 工号搜索并添加评委" />
            <p v-if="form.legacyMemberNames.length" class="ie-hint">尚未绑定 ID 的历史评委：{{ form.legacyMemberNames.join('、') }}。未重新选择时保存仍保留原快照。</p>
          </div>
        </section>

        <p v-if="formError" class="ie-err" role="alert">{{ formError }}</p>
      </form>

      <section v-if="groupId" class="student-assignment" aria-label="答辩学生分配">
        <header class="student-assignment__head">
          <div>
            <span>03 · 学生分配</span>
            <strong>把已进入成果检查及以后阶段的学生分入本组</strong>
            <small>同批次、阶段准入、容量与师生回避关系均以服务端返回为准。</small>
          </div>
          <div class="student-assignment__stats">
            <b>{{ assigned.length }}</b><span>已分配</span>
            <b>{{ Math.max(0, 30 - assigned.length) }}</b><span>剩余名额</span>
            <b :class="{ 'is-danger': conflictCount > 0 }">{{ conflictCount }}</b><span>回避冲突</span>
          </div>
        </header>

        <div class="student-assignment__grid">
          <section class="dg-sec">
            <div class="dg-sec__head">
              <div><span>本组学生</span><strong>{{ assigned.length }} 人</strong></div>
              <span class="dg-capacity">上限 30 人</span>
            </div>
            <EmptyState v-if="!assigned.length" title="暂未分配学生" description="从右侧候选学生中勾选，保存编排关系后才进入本组。" />
            <div v-else class="dg-list">
              <article v-for="student in assigned" :key="student.id" class="dg-row">
                <div>
                  <div class="dg-row__main">{{ student.name }} · {{ student.className }}</div>
                  <div class="dg-row__sub" :class="{ 'is-danger': student.conflict }">
                    {{ student.topicTitle }} · 导师 {{ student.advisorName }}{{ student.conflict ? ' · 与评委存在回避冲突' : '' }}
                  </div>
                </div>
                <button type="button" class="mp-link mp-link--danger" :disabled="submitting" @click="unassign(student)">移出</button>
              </article>
            </div>
          </section>

          <section class="dg-sec">
            <div class="dg-sec__head dg-sec__head--search">
              <div><span>可分配学生</span><strong>{{ eligibleFree.length }} 人</strong></div>
              <input v-model.trim="eligKeyword" class="ie-in dg-search" placeholder="搜索姓名 / 学号" :disabled="submitting" @input="loadEligible" />
            </div>
            <ErrorState v-if="eligibleError" :description="eligibleError" @retry="loadEligible" />
            <LoadingState v-else-if="eligibleLoading" />
            <EmptyState v-else-if="!eligibleFree.length" title="暂无可分配学生" description="当前批次没有符合阶段和数据范围条件的候选学生。" />
            <div v-else class="dg-list">
              <article
                v-for="student in eligibleFree"
                :key="student.id"
                class="dg-row dg-row--pick"
                :class="{ 'is-picked': picked.includes(student.id) }"
                :tabindex="submitting ? -1 : 0"
                role="checkbox"
                :aria-checked="picked.includes(student.id)"
                :aria-disabled="submitting"
                @click="togglePick(student.id)"
                @keydown.enter.prevent="togglePick(student.id)"
                @keydown.space.prevent="togglePick(student.id)"
              >
                <div>
                  <div class="dg-row__main">
                    <input type="checkbox" :checked="picked.includes(student.id)" :disabled="submitting" @click.stop="togglePick(student.id)" />
                    {{ student.name }} · {{ student.className }}
                  </div>
                  <div class="dg-row__sub">{{ student.topicTitle }} · 导师 {{ student.advisorName }}</div>
                </div>
              </article>
            </div>
          </section>
        </div>
      </section>

      <section v-else class="create-next-step">
        <span>创建后的下一步</span>
        <strong>系统会进入本答辩组编辑页，再从真实候选学生中完成分组。</strong>
        <p>未创建分组前不展示候选学生，避免把尚未存在的答辩组当成正式业务对象。</p>
      </section>
    </template>

    <template #aside>
      <section class="gd-form-aside-card">
        <span>发布前明显缺口</span>
        <strong>{{ obviousReady ? '页面初检已通过' : `仍有 ${preflightGaps.length} 项待补` }}</strong>
        <ul class="gd-form-checklist">
          <li :class="{ 'is-ready': Boolean(form.groupName) }">答辩组名称已确定</li>
          <li :class="{ 'is-ready': Boolean(form.defenseDate) }">答辩时间已安排</li>
          <li :class="{ 'is-ready': Boolean(form.location) }">答辩地点已安排</li>
          <li :class="{ 'is-ready': Boolean(form.chairMentorId || form.chairName) }">答辩组长已绑定</li>
          <li :class="{ 'is-ready': Boolean(form.secretaryMentorId || form.secretaryName) }">答辩秘书已绑定</li>
          <li :class="{ 'is-ready': panelMemberCount > 0 }">至少已安排一名评委</li>
          <li :class="{ 'is-ready': assigned.length > 0 }">至少已分配一名学生</li>
          <li :class="{ 'is-ready': conflictCount === 0 }">当前列表无明显回避冲突</li>
        </ul>
      </section>
      <section class="gd-form-aside-card">
        <span>职责分离</span>
        <strong>评委评分与秘书确认不能互相代替</strong>
        <p>发布后，评委只能提交本人评分；秘书只能确认服务端判定为完整的评分轮次。</p>
      </section>
      <section class="gd-form-aside-card">
        <span>正式发布</span>
        <strong>保存编排不等于学生已收到通知</strong>
        <p>返回“答辩安排”后还要执行服务端发布前检查，再由授权角色发布并发送通知。</p>
      </section>
    </template>

    <template #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button v-if="groupId && eligibleFree.length" type="button" class="mp-btn" :disabled="!picked.length || submitting" @click="assign">
        {{ submitting ? '处理中…' : `分配所选（${picked.length}）` }}
      </button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || loading" @click="save">
        {{ submitting ? '保存中…' : groupId ? '保存编排' : '创建答辩组' }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { EmptyState, ErrorState, LoadingState } from '@/components/business'
import { AppDateTimePicker } from '@/components/common/date'
import { AppGraduationMentorPicker, AppTemplateChips } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'
import { toDateTimeInputValue, addDays } from '@/utils/dateUtils'

const GROUP_NAME_CHIPS = ['答辩第 1 组', '答辩第 2 组', '答辩第 3 组', '补答辩组', '优秀论文答辩组']
const SAFE_PREFIX = '/admin/graduation/'
const freezeSnapshot = (value) => Object.freeze({ ...value })

const EMPTY_FORM = () => ({
  groupName: '',
  defenseDate: toDateTimeInputValue(addDays(new Date(), 7)),
  location: '',
  chairMentorId: '',
  chairName: '',
  secretaryMentorId: '',
  secretaryName: '',
  memberMentorIds: [],
  legacyMemberNames: []
})

export default {
  name: 'DefenseGroupFormView',
  components: {
    GraduationFormPageShell,
    AppDateTimePicker,
    EmptyState,
    ErrorState,
    LoadingState,
    AppGraduationMentorPicker,
    AppTemplateChips
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      GROUP_NAME_CHIPS,
      batchStore: useGraduationBatchStore(),
      groupId: null,
      groupBatchId: '',
      loading: false,
      loadError: '',
      submitting: false,
      commandSnapshot: null,
      form: EMPTY_FORM(),
      formError: '',
      assigned: [],
      eligible: [],
      picked: [],
      eligKeyword: '',
      eligibleLoading: false,
      eligibleError: '',
      eligibleRequestToken: 0
    }
  },
  computed: {
    eligibleFree() {
      return this.eligible.filter((student) => !student.assignedHere)
    },
    hasBatch() {
      return Boolean(this.activeBatchId)
    },
    activeBatchId() {
      return String(this.groupBatchId || this.batchStore.selectedBatchId || this.$route.query.batchId || '')
    },
    panelMemberCount() {
      return (this.form.memberMentorIds || []).filter(Boolean).length + (this.form.legacyMemberNames || []).filter(Boolean).length
    },
    conflictCount() {
      return this.assigned.filter((student) => Boolean(student.conflict)).length
    },
    preflightGaps() {
      const gaps = []
      if (!this.form.groupName) gaps.push('答辩组名称')
      if (!this.form.defenseDate) gaps.push('答辩时间')
      if (!this.form.location) gaps.push('答辩地点')
      if (!(this.form.chairMentorId || this.form.chairName)) gaps.push('答辩组长')
      if (!(this.form.secretaryMentorId || this.form.secretaryName)) gaps.push('答辩秘书')
      if (this.panelMemberCount < 1) gaps.push('评委名单')
      if (this.groupId && this.assigned.length < 1) gaps.push('答辩学生')
      if (this.conflictCount > 0) gaps.push('回避冲突')
      return gaps
    },
    obviousReady() {
      return this.preflightGaps.length === 0
    },
    statusText() {
      if (!this.groupId) return '新建编排'
      return this.obviousReady ? '可进入发布前检查' : '编排待完善'
    },
    listTarget() {
      const raw = Array.isArray(this.$route.query.returnTo)
        ? this.$route.query.returnTo[0]
        : this.$route.query.returnTo
      const safe = String(raw || '').trim()
      if (safe.startsWith(SAFE_PREFIX)) return safe
      return this.$router.resolve({
        name: 'graduation-defense',
        query: {
          batchId: this.activeBatchId || undefined,
          groupId: this.groupId || undefined
        }
      }).fullPath
    }
  },
  created() {
    this.load()
  },
  beforeUnmount() {
    ++this.eligibleRequestToken
  },
  beforeRouteLeave(to, from, next) {
    if (this.submitting) {
      toast.info('答辩编排正在提交，请等待服务器回执后再离开')
      next(false)
      return
    }
    next()
  },
  methods: {
    cancel() {
      if (!this.submitting) this.$router.push(this.listTarget)
    },
    async load() {
      const id = this.$route.params.id
      if (!id) {
        this.form = EMPTY_FORM()
        return
      }
      this.groupId = String(id)
      this.loading = true
      this.loadError = ''
      try {
        const response = await graduationApi.getDefenseGroupDetail(this.groupId)
        if (response.code !== 0 || !response.data) {
          this.loadError = response.message || '答辩组详情加载失败'
          return
        }
        const row = response.data
        this.groupBatchId = String(row.batchId || this.$route.query.batchId || '')
        this.form.groupName = row.groupName === '待指定' ? '' : (row.groupName || '')
        this.form.defenseDate = row.date === '待定' ? '' : toDateTimeInputValue(row.date)
        this.form.location = row.location === '待定' ? '' : (row.location || '')
        this._applyGroupPeople(row)
        this.assigned = Array.isArray(row.students) ? row.students : []
        await this.loadEligible()
      } catch (error) {
        this.loadError = error?.message || '答辩组详情加载失败'
      } finally {
        this.loading = false
      }
    },
    _formBody(batchId = this.activeBatchId) {
      const body = {
        groupName: this.form.groupName,
        defenseDate: this.form.defenseDate,
        location: this.form.location,
        chairMentorId: this.form.chairMentorId ? Number(this.form.chairMentorId) : null,
        secretaryMentorId: this.form.secretaryMentorId ? Number(this.form.secretaryMentorId) : null,
        chair: this.form.chairMentorId ? undefined : (this.form.chairName || undefined),
        secretary: this.form.secretaryMentorId ? undefined : (this.form.secretaryName || undefined)
      }
      const memberIds = (this.form.memberMentorIds || []).map((value) => Number(value)).filter(Boolean)
      const legacyNames = (this.form.legacyMemberNames || []).map((value) => String(value || '').trim()).filter(Boolean)
      if (memberIds.length) {
        body.memberMentorIds = memberIds
        if (legacyNames.length) body.members = legacyNames
      } else if (legacyNames.length) {
        body.members = legacyNames
      }
      if (!this.groupId) body.batchId = batchId
      return body
    },
    _applyGroupPeople(row) {
      const members = Array.isArray(row.members) ? row.members : []
      const memberIds = []
      const legacyNames = []
      members.forEach((member) => {
        if (member && typeof member === 'object' && member.mentorId) memberIds.push(member.mentorId)
        else if (typeof member === 'string' && member.trim()) legacyNames.push(member.trim())
        else if (member && typeof member === 'object' && member.name && !member.mentorId) legacyNames.push(String(member.name).trim())
      })
      this.form.chairMentorId = row.chairMentorId || ''
      this.form.chairName = row.chair === '待指定' ? '' : (row.chair || '')
      this.form.secretaryMentorId = row.secretaryMentorId || ''
      this.form.secretaryName = row.secretary === '待指定' ? '' : (row.secretary || '')
      this.form.memberMentorIds = memberIds
      this.form.legacyMemberNames = legacyNames
    },
    async reloadDetail() {
      if (!this.groupId) return false
      const response = await graduationApi.getDefenseGroupDetail(this.groupId)
      if (response.code !== 0) return false
      const row = response.data || {}
      this.groupBatchId = String(row.batchId || this.groupBatchId || '')
      this.assigned = Array.isArray(row.students) ? row.students : []
      this._applyGroupPeople(row)
      return true
    },
    async loadEligible() {
      if (!this.groupId) return
      const token = ++this.eligibleRequestToken
      this.eligibleLoading = true
      this.eligibleError = ''
      try {
        const response = await graduationApi.getDefenseEligibleStudents(this.groupId, this.eligKeyword)
        if (token !== this.eligibleRequestToken) return
        if (response.code === 0) {
          this.eligible = Array.isArray(response.data?.list) ? response.data.list : []
          const visibleIds = new Set(this.eligible.map((student) => student.id))
          this.picked = this.picked.filter((id) => visibleIds.has(id))
        } else {
          this.eligible = []
          this.picked = []
          this.eligibleError = response.message || '候选学生加载失败'
        }
      } catch (error) {
        if (token === this.eligibleRequestToken) {
          this.eligible = []
          this.picked = []
          this.eligibleError = error?.message || '候选学生加载失败'
        }
      } finally {
        if (token === this.eligibleRequestToken) this.eligibleLoading = false
      }
    },
    togglePick(id) {
      if (this.submitting) return
      const index = this.picked.indexOf(id)
      if (index >= 0) this.picked.splice(index, 1)
      else this.picked.push(id)
    },
    validateSave() {
      if (!this.form.groupName) return '答辩组名称必填'
      if (!this.groupId && !this.hasBatch) return '请先在顶部选择毕业设计批次'
      return ''
    },
    async save() {
      if (this.submitting) return
      this.formError = this.validateSave()
      if (this.formError) return

      const snapshot = freezeSnapshot({
        action: this.groupId ? 'UPDATE_GROUP' : 'CREATE_GROUP',
        groupId: this.groupId,
        batchId: this.activeBatchId,
        body: freezeSnapshot(this._formBody(this.activeBatchId)),
        routeQuery: freezeSnapshot({ ...this.$route.query, batchId: this.activeBatchId || undefined })
      })
      this.commandSnapshot = snapshot
      this.submitting = true
      let createdId = ''
      try {
        const response = snapshot.groupId
          ? await graduationApi.updateDefenseGroup(snapshot.groupId, snapshot.body)
          : await graduationApi.createDefenseGroup(snapshot.body)
        if (response.code !== 0) {
          this.formError = response.message || '答辩编排保存失败'
          return
        }
        if (!snapshot.groupId) {
          createdId = String(response.data?.id || '')
          if (!createdId) {
            this.formError = '服务器未返回新建答辩组编号，请返回列表核对'
            return
          }
        } else {
          const row = response.data || {}
          this.assigned = Array.isArray(row.students) ? row.students : this.assigned
          this._applyGroupPeople(row)
        }
        toast.success(snapshot.groupId ? '答辩编排已保存，发布前仍需重新检查' : '答辩组已创建，下一步分配学生')
      } catch (error) {
        this.formError = error?.message || '答辩编排保存失败'
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }

      if (createdId) {
        this.groupId = createdId
        this.groupBatchId = snapshot.batchId
        await this.$router.replace({
          name: 'graduation-defense-group-edit',
          params: { id: createdId },
          query: snapshot.routeQuery
        })
        await this.reloadDetail()
        await this.loadEligible()
      }
    },
    async assign() {
      if (!this.picked.length || this.submitting || !this.groupId) return
      const snapshot = freezeSnapshot({
        action: 'ASSIGN_STUDENTS',
        groupId: String(this.groupId),
        studentIds: Object.freeze([...this.picked])
      })
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        const response = await graduationApi.assignDefenseStudents(snapshot.groupId, snapshot.studentIds)
        if (response.code !== 0) {
          toast.error(response.message || '学生分配失败')
          return
        }
        this.assigned = Array.isArray(response.data?.students) ? response.data.students : []
        this.picked = []
        await this.loadEligible()
        toast.success('所选学生已分配，服务器最新分组已回读')
      } catch (error) {
        toast.error(error?.message || '学生分配失败')
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
    },
    async unassign(student) {
      if (!student?.id || this.submitting || !this.groupId) return
      const snapshot = freezeSnapshot({ action: 'UNASSIGN_STUDENT', groupId: String(this.groupId), studentId: student.id })
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        const response = await graduationApi.unassignDefenseStudents(snapshot.groupId, [snapshot.studentId])
        if (response.code !== 0) {
          toast.error(response.message || '移出失败')
          return
        }
        this.assigned = Array.isArray(response.data?.students) ? response.data.students : []
        await this.loadEligible()
        toast.success('学生已移出本组，服务器最新分组已回读')
      } catch (error) {
        toast.error(error?.message || '移出失败')
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.defense-context {
  display: grid;
  flex: 0 0 auto;
  min-width: 142px;
  max-width: 240px;
  gap: 2px;
  padding: 7px 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-card, #fff);
}

.defense-context span {
  color: var(--text-tertiary, #64748b);
  font-size: 10px;
}

.defense-context strong {
  overflow: hidden;
  color: var(--text-primary, #0f172a);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.student-assignment {
  display: grid;
  min-width: 0;
  gap: 14px;
  margin-top: 16px;
  padding: 16px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 12px;
  background: var(--bg-card, #fff);
}

.student-assignment__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-light, #edf1f7);
}

.student-assignment__head > div:first-child {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.student-assignment__head > div:first-child > span {
  color: var(--primary-600, #2563eb);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: .06em;
}

.student-assignment__head strong {
  color: var(--text-primary, #0f172a);
  font-size: 14px;
}

.student-assignment__head small {
  color: var(--text-tertiary, #64748b);
  font-size: 11px;
  line-height: 1.5;
}

.student-assignment__stats {
  display: grid;
  grid-template-columns: auto auto;
  align-items: baseline;
  gap: 2px 6px;
  flex: none;
}

.student-assignment__stats b {
  color: var(--text-primary, #0f172a);
  font-size: 17px;
  text-align: right;
}

.student-assignment__stats span {
  color: var(--text-tertiary, #64748b);
  font-size: 10px;
}

.student-assignment__stats b.is-danger,
.dg-row__sub.is-danger {
  color: var(--danger-600, #dc2626);
}

.student-assignment__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-width: 0;
  gap: 14px;
}

.dg-sec {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  background: var(--bg-card, #fff);
}

.dg-sec__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-bottom: 1px solid var(--border-light, #edf1f7);
  background: var(--bg-subtle, #f8fafc);
}

.dg-sec__head > div:first-child {
  display: grid;
  gap: 1px;
}

.dg-sec__head span {
  color: var(--text-tertiary, #64748b);
  font-size: 10px;
}

.dg-sec__head strong {
  color: var(--text-primary, #0f172a);
  font-size: 13px;
}

.dg-sec__head--search {
  align-items: end;
  justify-content: space-between;
}

.dg-capacity {
  margin-left: auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--gray-100, #f1f5f9);
  color: var(--text-secondary, #475569);
  font-size: 10px;
  white-space: nowrap;
}

.dg-search {
  max-width: 190px;
  min-height: 34px;
}

.dg-list {
  max-height: 430px;
  overflow-y: auto;
}

.dg-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light, #edf1f7);
}

.dg-row:last-child {
  border-bottom: 0;
}

.dg-row--pick {
  cursor: pointer;
  transition: background .12s ease, box-shadow .12s ease;
}

.dg-row--pick:hover,
.dg-row--pick.is-picked {
  background: var(--primary-50, #eff6ff);
}

.dg-row--pick.is-picked {
  box-shadow: inset 3px 0 0 var(--primary-600, #2563eb);
}

.dg-row--pick:focus-visible {
  outline: 2px solid var(--primary-400, #60a5fa);
  outline-offset: -2px;
}

.dg-row__main {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary, #0f172a);
  font-size: 12px;
  font-weight: 650;
}

.dg-row__sub {
  margin-top: 3px;
  color: var(--text-tertiary, #64748b);
  font-size: 11px;
  line-height: 1.45;
}

.create-next-step {
  display: grid;
  gap: 3px;
  margin-top: 16px;
  padding: 14px;
  border: 1px dashed var(--primary-300, #93c5fd);
  border-radius: 10px;
  background: var(--primary-50, #eff6ff);
}

.create-next-step span {
  color: var(--primary-700, #1d4ed8);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: .06em;
}

.create-next-step strong {
  color: var(--text-primary, #0f172a);
  font-size: 13px;
}

.create-next-step p {
  margin: 0;
  color: var(--text-secondary, #64748b);
  font-size: 11px;
  line-height: 1.55;
}

.mp-btn {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--border-base, #d9dee8);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  cursor: pointer;
  font-size: 13px;
}

.mp-btn--primary {
  border-color: var(--primary-600, #2563eb);
  background: var(--primary-600, #2563eb);
  color: #fff;
}

.mp-btn:disabled,
.mp-link:disabled {
  cursor: not-allowed;
  opacity: .5;
}

.mp-link {
  flex: none;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--primary-600, #2563eb);
  cursor: pointer;
  font-size: 12px;
}

.mp-link--danger {
  color: var(--danger-600, #dc2626);
}

@media (max-width: 1100px) {
  .student-assignment__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .student-assignment__head {
    flex-direction: column;
  }

  .student-assignment__stats {
    grid-template-columns: repeat(6, auto);
  }

  .dg-sec__head--search {
    align-items: stretch;
    flex-direction: column;
  }

  .dg-search {
    max-width: none;
  }
}
</style>
