<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="分配冲突检测"
    :subtitle="pageSubtitle"
    :back-to="safeReturnTo"
  >
    <section class="mc-summary" aria-label="导师分配冲突结论">
      <div>
        <span>检测结论</span>
        <strong>{{ conclusion }}</strong>
        <small>这里只展示服务端返回的三类真实冲突，并提供精确修复入口；页面不会自动改导师分配。</small>
      </div>
      <div class="mc-summary__facts">
        <div><b>{{ conflictCount('overCapacity') }}</b><span>导师超容量</span></div>
        <div><b>{{ conflictCount('advancedNoMentor') }}</b><span>进阶段无导师</span></div>
        <div><b>{{ conflictCount('unqualifiedMentor') }}</b><span>导师未认证</span></div>
      </div>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="loading" @click="load">{{ loading ? '检测中…' : '重新检测' }}</button>
    </section>

    <p class="mc-scope-note">
      检测接口当前按角色数据范围返回，不支持 batchId 服务端过滤；顶部批次仅作为修复深链与返回上下文保留，页面不在浏览器端抓全量数据伪造批次统计。
    </p>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState
      v-else-if="!conflicts || conflicts.total === 0"
      title="当前数据范围未检出导师分配冲突"
      description="本次结果来自服务端冲突检测；后续分配或导师资格变化后可重新检测。"
    />
    <div v-else class="mc-grid">
      <section class="mc-card is-danger" aria-label="导师超容量冲突">
        <div class="mc-card__head">
          <div><span>冲突 01</span><strong>导师超容量</strong></div>
          <b>{{ conflicts.overCapacity.length }}</b>
        </div>
        <p>服务端按有效分配数与导师容量比较。这里只跳转详情，容量或分配调整仍由原页面和服务端校验。</p>
        <EmptyState v-if="!conflicts.overCapacity.length" title="无超容量导师" />
        <ul v-else class="mc-list">
          <li v-for="mentor in conflicts.overCapacity" :key="mentor.mentorId">
            <div>
              <strong>{{ mentor.teacherName }}</strong>
              <span>当前 {{ mentor.current }} / 容量 {{ mentor.capacity }} · 超出 {{ Math.max(0, Number(mentor.current) - Number(mentor.capacity)) }}</span>
            </div>
            <button type="button" class="mp-link" @click="goMentor(mentor)">查看导师与工作量 →</button>
          </li>
        </ul>
      </section>

      <section class="mc-card is-warning" aria-label="进入指导阶段却无导师冲突">
        <div class="mc-card__head">
          <div><span>冲突 02</span><strong>进入指导阶段却无导师</strong></div>
          <b>{{ conflicts.advancedNoMentor.length }}</b>
        </div>
        <p>学生已经进入指导及后续阶段，但服务端主档没有有效导师关系。进入原分配页后再选择合格导师。</p>
        <EmptyState v-if="!conflicts.advancedNoMentor.length" title="无此类学生" />
        <ul v-else class="mc-list">
          <li v-for="student in conflicts.advancedNoMentor" :key="student.gdStudentId">
            <div>
              <strong>{{ student.name }}</strong>
              <span>{{ student.className || '班级未维护' }} · {{ stageLabel(student.stage) }}</span>
            </div>
            <button type="button" class="mp-link" @click="goAssign(student)">去分配合格导师 →</button>
          </li>
        </ul>
      </section>

      <section class="mc-card is-info" aria-label="学生导师未认证冲突">
        <div class="mc-card__head">
          <div><span>冲突 03</span><strong>学生导师不是“已认证”</strong></div>
          <b>{{ conflicts.unqualifiedMentor.length }}</b>
        </div>
        <p>学生已有导师关系，但导师资格不满足分配条件。进入原分配页处理，前端不自动换导师。</p>
        <EmptyState v-if="!conflicts.unqualifiedMentor.length" title="无此类学生" />
        <ul v-else class="mc-list">
          <li v-for="student in conflicts.unqualifiedMentor" :key="student.gdStudentId">
            <div>
              <strong>{{ student.name }}</strong>
              <span>{{ student.mentorName }} · {{ graduationMentorStatusLabel(student.mentorStatus) }}</span>
            </div>
            <button type="button" class="mp-link" @click="goAssign(student)">调整导师关系 →</button>
          </li>
        </ul>
      </section>
    </div>

    <template #footer>
      <button type="button" class="mp-btn" @click="goBack">返回导师与分配</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { GD_STAGE } from '@/modules/graduation/constants/graduation-student.constants'
import { graduationMentorStatusLabel } from '@/modules/graduation/constants/graduation-material.constants'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const STAGE_LABELS = Object.fromEntries(GD_STAGE.map((item) => [item.value, item.label]))
const EMPTY_CONFLICTS = () => ({ overCapacity: [], advancedNoMentor: [], unqualifiedMentor: [], total: 0 })

export default {
  name: 'GraduationMentorConflictsView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true,
      error: '',
      conflicts: EMPTY_CONFLICTS(),
      loadToken: 0
    }
  },
  computed: {
    safeReturnTo() {
      const value = this.routeText(this.$route.query.returnTo)
      return value.startsWith('/admin/graduation/') ? value : '/admin/graduation/mentors?panel=list'
    },
    pageSubtitle() {
      const batch = this.batchStore.selectedBatchName || this.routeText(this.$route.query.batchId)
      return `${batch ? `${batch} · ` : ''}服务端三类冲突检测 · 只提供修复深链`
    },
    conclusion() {
      const total = Number(this.conflicts?.total) || 0
      if (this.loading) return '正在读取服务端冲突检测结果。'
      if (this.error) return '检测暂不可用，请按错误信息重试。'
      return total ? `共检出 ${total} 项真实分配冲突，先处理超容量和进阶段无导师。` : '当前数据范围未检出三类导师分配冲突。'
    }
  },
  created() {
    this.syncContextQuery()
    this.load()
  },
  beforeUnmount() {
    ++this.loadToken
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.syncContextQuery()
    }
  },
  methods: {
    graduationMentorStatusLabel,
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    stageLabel(value) { return STAGE_LABELS[value] || '其他毕业设计阶段' },
    conflictCount(key) { return Array.isArray(this.conflicts?.[key]) ? this.conflicts[key].length : 0 },
    currentReturnTo() {
      return this.$router.resolve({
        name: 'graduation-mentor-conflicts',
        query: {
          batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
          returnTo: this.safeReturnTo
        }
      }).fullPath
    },
    syncContextQuery() {
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        returnTo: this.safeReturnTo
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      this.$router.replace({ query }).catch(() => {})
    },
    goMentor(mentor) {
      if (!mentor?.mentorId) return
      this.$router.push({
        name: 'graduation-mentor-detail',
        params: { id: String(mentor.mentorId) },
        query: {
          batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
          returnTo: this.currentReturnTo(),
          source: 'mentor-conflicts'
        }
      })
    },
    goAssign(student) {
      if (!student?.gdStudentId) return
      this.$router.push({
        name: 'graduation-mentor-assign',
        params: { studentId: String(student.gdStudentId) },
        query: {
          batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
          returnTo: this.currentReturnTo(),
          source: 'mentor-conflicts'
        }
      })
    },
    goBack() {
      this.$router.push(this.safeReturnTo)
    },
    async load() {
      const token = ++this.loadToken
      this.loading = true
      this.error = ''
      try {
        const res = await graduationMentorApi.getConflicts()
        if (token !== this.loadToken) return false
        if (res.code === 0) {
          const data = res.data || {}
          const next = {
            overCapacity: Array.isArray(data.overCapacity) ? data.overCapacity : [],
            advancedNoMentor: Array.isArray(data.advancedNoMentor) ? data.advancedNoMentor : [],
            unqualifiedMentor: Array.isArray(data.unqualifiedMentor) ? data.unqualifiedMentor : []
          }
          next.total = next.overCapacity.length + next.advancedNoMentor.length + next.unqualifiedMentor.length
          this.conflicts = next
          return true
        }
        this.conflicts = EMPTY_CONFLICTS()
        this.error = res.message || '导师分配冲突检测失败'
      } catch (error) {
        if (token === this.loadToken) {
          this.conflicts = EMPTY_CONFLICTS()
          this.error = error?.message || '导师分配冲突检测失败'
        }
      } finally {
        if (token === this.loadToken) this.loading = false
      }
      return false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mc-summary { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: var(--space-4); align-items: center; margin-bottom: var(--space-3); padding: 12px 14px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-lg, 12px); background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--bg-card, #fff) 76%); }
.mc-summary > div:first-child { display: grid; min-width: 0; gap: 2px; }
.mc-summary > div:first-child > span { color: var(--primary-600, #2563eb); font-size: 10px; font-weight: 700; letter-spacing: .08em; }
.mc-summary strong { color: var(--text-primary, #0f172a); font-size: 14px; }
.mc-summary small { color: var(--text-tertiary, #64748b); font-size: 10px; line-height: 1.5; }
.mc-summary__facts { display: flex; align-items: stretch; }
.mc-summary__facts div { display: grid; min-width: 90px; gap: 1px; padding: 2px 12px; border-left: 1px solid var(--primary-100, #dbeafe); }
.mc-summary__facts b { color: var(--text-primary, #0f172a); font-size: 18px; }
.mc-summary__facts span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.mc-scope-note { margin: 0 0 var(--space-3); padding: 8px 10px; border-left: 3px solid var(--warning-400, #fbbf24); background: var(--warning-50, #fffbeb); color: var(--text-secondary, #475569); font-size: 11px; line-height: 1.55; }
.mc-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.mc-card { min-width: 0; padding: 12px; border: 1px solid var(--border-light, #e2e8f0); border-top: 3px solid var(--primary-400, #60a5fa); border-radius: var(--radius-lg, 10px); background: var(--bg-card, #fff); }
.mc-card.is-danger { border-top-color: var(--danger-500, #ef4444); }
.mc-card.is-warning { border-top-color: var(--warning-500, #f59e0b); }
.mc-card.is-info { border-top-color: var(--info-500, #0ea5e9); }
.mc-card__head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.mc-card__head > div { display: grid; gap: 2px; }
.mc-card__head span { color: var(--text-tertiary, #64748b); font-size: 9px; font-weight: 700; letter-spacing: .08em; }
.mc-card__head strong { color: var(--text-primary, #0f172a); font-size: 13px; }
.mc-card__head b { display: grid; min-width: 30px; height: 30px; place-items: center; border-radius: 999px; background: var(--bg-subtle, #f1f5f9); color: var(--text-primary, #0f172a); }
.mc-card > p { min-height: 48px; color: var(--text-secondary, #475569); font-size: 10px; line-height: 1.6; }
.mc-list { display: grid; gap: 6px; max-height: 430px; margin: 0; padding: 0; overflow-y: auto; list-style: none; }
.mc-list li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 8px; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--bg-subtle, #f8fafc); }
.mc-list li > div { display: grid; min-width: 0; gap: 2px; }
.mc-list strong, .mc-list span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mc-list strong { color: var(--text-primary, #0f172a); font-size: 11px; }
.mc-list span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.mp-link { border: 0; background: transparent; color: var(--primary-600, #2563eb); font-size: 10px; cursor: pointer; white-space: nowrap; }
.mp-btn { padding: 7px 14px; border: 1px solid var(--border-light, #d9dee8); border-radius: 8px; background: var(--bg-card, #fff); color: var(--text-primary, #0f172a); cursor: pointer; font-size: 12px; }
.mp-btn--primary { border-color: var(--primary-600, #2563eb); background: var(--primary-600, #2563eb); color: #fff; }
.mp-btn:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 1100px) { .mc-summary { grid-template-columns: 1fr; } .mc-summary__facts div:first-child { border-left: 0; padding-left: 0; } .mc-grid { grid-template-columns: 1fr; } .mc-card > p { min-height: 0; } }
</style>
