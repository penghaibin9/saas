<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="groupId ? '编辑答辩组' : '新增答辩组'"
    subtitle="分组 / 时间 / 地点 / 评委 · 编辑时可分配学生"
    back-to="/admin/graduation/defense"
  >
    <form class="ie-form" @submit.prevent="save">
      <label class="ie-fld ie-fld--full"><span class="ie-lbl">答辩组名称 <i>*</i></span>
        <input v-model.trim="form.groupName" class="ie-in" placeholder="如 软件工程专业第一答辩组" />
        <AppTemplateChips :options="GROUP_NAME_CHIPS" @pick="(t) => (form.groupName = t)" />
      </label>
      <AppDateTimePicker v-model="form.defenseDate" class="ie-fld" label="答辩时间" hint="建议提前一周排期" />
      <label class="ie-fld"><span class="ie-lbl">答辩地点</span><input v-model.trim="form.location" class="ie-in" placeholder="如 实训楼 A301" /></label>
      <div class="ie-fld"><span class="ie-lbl">答辩组长（副高+）</span>
        <AppGraduationMentorPicker v-model="form.chairMentorId" :query="{ valueMode: 'id' }" placeholder="按姓名 / 工号搜索组长" />
        <p v-if="!form.chairMentorId && form.chairName" class="ie-hint">当前快照：{{ form.chairName }}（请重新选择以绑定工号身份）</p>
      </div>
      <div class="ie-fld"><span class="ie-lbl">答辩秘书</span>
        <AppGraduationMentorPicker v-model="form.secretaryMentorId" :query="{ valueMode: 'id' }" placeholder="按姓名 / 工号搜索秘书" />
        <p v-if="!form.secretaryMentorId && form.secretaryName" class="ie-hint">当前快照：{{ form.secretaryName }}（请重新选择以绑定工号身份）</p>
      </div>
      <div class="ie-fld ie-fld--full"><span class="ie-lbl">评委名单（建议≥5人，可搜索添加）</span>
        <AppGraduationMentorPicker v-model="form.memberMentorIds" multiple :query="{ valueMode: 'id' }" placeholder="按姓名 / 工号搜索并添加评委" />
        <p v-if="form.legacyMemberNames.length" class="ie-hint">历史评委快照（未绑 ID）：{{ form.legacyMemberNames.join('、') }} · 请在上方重新选择以绑定身份，保存时会保留未改动的快照</p>
      </div>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template v-if="groupId">
      <div class="dg-sec">
        <div class="dg-sec__head"><span>已分配学生（{{ assigned.length }}/30）</span><span class="dg-capacity">剩余 {{ Math.max(0, 30 - assigned.length) }} 个名额</span></div>
        <EmptyState v-if="!assigned.length" title="暂未分配学生" description="从下方候选学生中勾选分配" />
        <div v-for="s in assigned" :key="s.id" class="dg-row">
          <div>
            <div class="dg-row__main">{{ s.name }} · {{ s.className }}</div>
            <div class="dg-row__sub" :style="s.conflict ? 'color:var(--danger-600)' : ''">
              {{ s.topicTitle }} · 导师 {{ s.advisorName }}{{ s.conflict ? '（与评委冲突，须回避）' : '' }}
            </div>
          </div>
          <button type="button" class="mp-link mp-link--danger" @click="unassign(s)">移出</button>
        </div>
      </div>
      <div class="dg-sec">
        <div class="dg-sec__head">
          候选学生
          <input v-model.trim="eligKeyword" class="ie-in dg-search" placeholder="搜索姓名" @input="loadEligible" />
        </div>
        <EmptyState v-if="!eligibleFree.length" title="暂无可分配学生" />
        <div v-for="s in eligibleFree" :key="s.id" class="dg-row dg-row--pick" tabindex="0" role="checkbox" :aria-checked="picked.includes(s.id)" @click="togglePick(s.id)" @keydown.enter.prevent="togglePick(s.id)" @keydown.space.prevent="togglePick(s.id)">
          <div>
            <div class="dg-row__main">
              <input type="checkbox" :checked="picked.includes(s.id)" @click.stop="togglePick(s.id)" /> {{ s.name }} · {{ s.className }}
            </div>
            <div class="dg-row__sub">{{ s.topicTitle }} · 导师 {{ s.advisorName }}</div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/defense')">取消</button>
      <button v-if="groupId && eligibleFree.length" type="button" class="mp-btn" :disabled="!picked.length || submitting" @click="assign">分配所选（{{ picked.length }}）</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="save">{{ groupId ? '保存' : '创建' }}</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { EmptyState } from '@/components/business'
import { AppDateTimePicker } from '@/components/common/date'
import { AppGraduationMentorPicker, AppTemplateChips } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'
import { toDateTimeInputValue, addDays } from '@/utils/dateUtils'

const GROUP_NAME_CHIPS = ['答辩第1组', '答辩第2组', '答辩第3组', '补答辩组', '优秀论文答辩组']

export default {
  name: 'DefenseGroupFormView',
  components: { GraduationFormPageShell, AppDateTimePicker, EmptyState, AppGraduationMentorPicker, AppTemplateChips },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      GROUP_NAME_CHIPS,
      batchStore: useGraduationBatchStore(),
      groupId: null, submitting: false,
      form: {
        groupName: '', defenseDate: '', location: '',
        chairMentorId: '', chairName: '',
        secretaryMentorId: '', secretaryName: '',
        memberMentorIds: [], legacyMemberNames: []
      },
      formError: '',
      assigned: [], eligible: [], picked: [], eligKeyword: ''
    }
  },
  computed: {
    eligibleFree() {
      return this.eligible.filter((s) => !s.assignedHere)
    },
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    }
  },
  async created() {
    const id = this.$route.params.id
    if (id) {
      this.groupId = id
      const res = await graduationApi.getDefenseGroupDetail(id)
      if (res.code === 0 && res.data) {
        const row = res.data
        this.form.groupName = row.groupName === '待指定' ? '' : row.groupName
        this.form.defenseDate = row.date === '待定' ? '' : toDateTimeInputValue(row.date)
        this.form.location = row.location === '待定' ? '' : row.location
        this._applyGroupPeople(row)
      }
      await this.reloadDetail()
      await this.loadEligible()
    } else {
      this.form = {
        groupName: '',
        defenseDate: toDateTimeInputValue(addDays(new Date(), 7)),
        location: '', chairMentorId: '', chairName: '',
        secretaryMentorId: '', secretaryName: '',
        memberMentorIds: [], legacyMemberNames: []
      }
    }
  },
  methods: {
    _formBody() {
      const body = {
        groupName: this.form.groupName,
        defenseDate: this.form.defenseDate,
        location: this.form.location,
        chairMentorId: this.form.chairMentorId ? Number(this.form.chairMentorId) : null,
        secretaryMentorId: this.form.secretaryMentorId ? Number(this.form.secretaryMentorId) : null,
        // 有 ID 时传 ID；无 ID 时传姓名快照，避免后端清空历史名单
        chair: this.form.chairMentorId ? undefined : (this.form.chairName || undefined),
        secretary: this.form.secretaryMentorId ? undefined : (this.form.secretaryName || undefined)
      }
      const mids = (this.form.memberMentorIds || []).map((x) => Number(x)).filter(Boolean)
      const legacy = (this.form.legacyMemberNames || []).filter((n) => n && String(n).trim())
      if (mids.length) {
        body.memberMentorIds = mids
        // 混合面板：ID 评委 + 仍未绑 ID 的姓名快照一并提交，避免保存时丢掉仅姓名席位
        if (legacy.length) body.members = legacy
      } else if (legacy.length) {
        body.members = legacy
      }
      // 都不传 → 后端 preserve 保留原成员
      if (!this.groupId) body.batchId = this.batchStore.selectedBatchId
      return body
    },
    _applyGroupPeople(row) {
      const members = row.members || []
      const memberIds = []
      const legacyNames = []
      members.forEach((m) => {
        if (m && typeof m === 'object' && m.mentorId) memberIds.push(m.mentorId)
        else if (typeof m === 'string' && m.trim()) legacyNames.push(m.trim())
        else if (m && typeof m === 'object' && m.name && !m.mentorId) legacyNames.push(String(m.name).trim())
      })
      this.form.chairMentorId = row.chairMentorId || ''
      this.form.chairName = row.chair === '待指定' ? '' : (row.chair || '')
      this.form.secretaryMentorId = row.secretaryMentorId || ''
      this.form.secretaryName = row.secretary === '待指定' ? '' : (row.secretary || '')
      this.form.memberMentorIds = memberIds
      this.form.legacyMemberNames = legacyNames
    },
    async reloadDetail() {
      const res = await graduationApi.getDefenseGroupDetail(this.groupId)
      if (res.code === 0) this.assigned = res.data.students || []
    },
    async loadEligible() {
      if (!this.groupId) return
      const res = await graduationApi.getDefenseEligibleStudents(this.groupId, this.eligKeyword)
      if (res.code === 0) this.eligible = res.data.list
    },
    togglePick(id) {
      const i = this.picked.indexOf(id)
      if (i >= 0) this.picked.splice(i, 1)
      else this.picked.push(id)
    },
    async save() {
      this.formError = ''
      if (!this.form.groupName) { this.formError = '答辩组名称必填'; return }
      if (!this.groupId && !this.hasBatch) {
        this.formError = '请先在顶部选择毕设批次'
        return
      }
      this.submitting = true
      const res = this.groupId
        ? await graduationApi.updateDefenseGroup(this.groupId, this._formBody())
        : await graduationApi.createDefenseGroup(this._formBody())
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.groupId ? '已保存（编辑后需重新发布）' : '答辩组已创建，可继续分配学生')
        if (!this.groupId) {
          this.groupId = res.data.id
          this.$router.replace(`/admin/graduation/defense/groups/${this.groupId}/edit`)
          await this.reloadDetail()
          await this.loadEligible()
        } else {
          this.assigned = res.data.students || []
          this._applyGroupPeople(res.data)
        }
      } else {
        this.formError = res.message || '保存失败'
      }
    },
    async assign() {
      if (!this.picked.length) return
      this.submitting = true
      const res = await graduationApi.assignDefenseStudents(this.groupId, this.picked)
      this.submitting = false
      if (res.code === 0) {
        toast.success('已分配')
        this.assigned = res.data.students || []
        this.picked = []
        await this.loadEligible()
      } else {
        toast.error(res.message || '分配失败')
      }
    },
    async unassign(s) {
      const res = await graduationApi.unassignDefenseStudents(this.groupId, [s.id])
      if (res.code === 0) {
        this.assigned = res.data.students || []
        await this.loadEligible()
      } else {
        toast.error(res.message || '移出失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dg-sec { margin-top: var(--space-4); padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); }
.dg-sec__head { font-weight: 600; margin-bottom: var(--space-2); display: flex; align-items: center; gap: var(--space-2); }
.dg-capacity { margin-left: auto; padding: 3px 8px; border-radius: var(--radius-full, 999px); color: var(--text-secondary); background: var(--gray-50, #f8fafc); font-size: var(--font-size-xs, 12px); font-weight: var(--font-weight-normal, 400); white-space: nowrap; }
.dg-search { max-width: 200px; }
.dg-row { display: flex; justify-content: space-between; align-items: center; padding: var(--space-2) 0; border-bottom: 1px dashed var(--line, #eef1f6); cursor: pointer; }
.dg-row--pick { padding-left: var(--space-2); padding-right: var(--space-2); border-radius: var(--radius-sm, 6px); transition: background .12s ease; }
.dg-row--pick:hover { background: var(--gray-50, #f8fafc); }
.dg-row--pick:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.dg-row__main { font-size: 13px; }
.dg-row__sub { font-size: 12px; color: var(--t3, #64748b); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.mp-link { color: var(--pri, #2563eb); background: none; border: none; cursor: pointer; font-size: 13px; }
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-hint { margin: 6px 0 0; font-size: 12px; color: var(--t3, #64748b); line-height: 1.4; }
</style>
