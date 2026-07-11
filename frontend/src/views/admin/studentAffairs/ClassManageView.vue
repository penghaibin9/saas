<template>
  <ModulePageShell
    title="班级管理"
    subtitle="班级台账 · 班干部任免（按数据范围）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="班级管理"
  >
    <div class="cl-workspace">
      <!-- 左：班级列表 -->
      <div class="cl-list">
        <div class="cl-list__head">我的班级<span v-if="classes.length" class="cl-list__count">{{ classes.length }}</span></div>
        <LoadingState v-if="loading" text="正在加载班级…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadClasses" />
        <EmptyState v-else-if="!classes.length" title="暂无班级" description="你的数据范围内没有可管理的班级" />
        <ul v-else class="cl-classes">
          <li
            v-for="c in classes"
            :key="c.classId"
            class="cl-citem"
            :class="{ 'is-active': selected && selected.classId === c.classId }"
            @click="select(c)"
          >
            <span class="cl-citem__name">{{ c.className }}</span>
            <span class="cl-citem__grade">{{ c.grade || '' }}</span>
          </li>
        </ul>
      </div>

      <!-- 右：班干部 -->
      <div class="cl-detail">
        <EmptyState v-if="!selected" title="请从左侧选择班级" description="查看并维护该班班干部" />
        <template v-else>
          <div class="cl-dhead">
            <h3 class="cl-dname">{{ selected.className }} · 班干部</h3>
            <button type="button" class="cl-btn cl-btn--primary" @click="openAppoint">任命班干部</button>
          </div>

          <LoadingState v-if="cadreLoading" text="正在加载班干部…" />
          <EmptyState v-else-if="!activeCadres.length" title="暂无在任班干部" description="点「任命班干部」为该班任命" />
          <ul v-else class="cl-cadres">
            <li v-for="c in activeCadres" :key="c.cadreId" class="cl-cadre">
              <div>
                <span class="cl-cadre__pos">{{ positionLabel(c.position) }}</span>
                <span class="cl-cadre__stu">学生#{{ c.studentId }}</span>
                <span v-if="c.termCode" class="cl-cadre__term">{{ c.termCode }}</span>
              </div>
              <button type="button" class="cl-btn cl-btn--danger" :disabled="acting" @click="onDismiss(c)">免去</button>
            </li>
          </ul>

          <div v-if="removedCadres.length" class="cl-history">
            <div class="cl-history__title">历史（已免去 {{ removedCadres.length }}）</div>
            <div v-for="c in removedCadres" :key="c.cadreId" class="cl-history__row">
              {{ positionLabel(c.position) }} · 学生#{{ c.studentId }} · 已免去
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 任命 modal -->
    <div v-if="appointModal.visible" class="cl-mask" @click.self="appointModal.visible = false">
      <div class="cl-modal">
        <h3 class="cl-modal__title">任命班干部 · {{ selected && selected.className }}</h3>
        <label class="cl-field"><span>职务 <i>*</i></span>
          <select v-model="appointModal.position" class="cl-input">
            <option v-for="p in positions" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </label>
        <div class="cl-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="appointModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索本班学生" />
        </div>
        <label class="cl-field"><span>学年学期</span>
          <input v-model.trim="appointModal.termCode" class="cl-input" placeholder="选填，如 2025-2026-1" />
        </label>
        <p class="cl-modal__hint">同一班级同一职务只能有一名在任班干部，重复任命将被拒绝。</p>
        <p v-if="appointModal.error" class="cl-err">{{ appointModal.error }}</p>
        <div class="cl-modal__foot">
          <button type="button" class="cl-btn" @click="appointModal.visible = false">取消</button>
          <button type="button" class="cl-btn cl-btn--primary" :disabled="acting" @click="submitAppoint">任命</button>
        </div>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="dismissDialog.visible"
      title="免去班干部"
      :message="dismissDialog.message"
      type="danger"
      confirm-text="确认免去"
      :submitting="acting"
      @confirm="confirmDismiss"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 班级管理（/admin/student-affairs/classes）—— 13A 班级台账 + 班干部任免。
 * 真实对接 /api/v1/student-affairs/classes（按数据范围）+ /classes/{id}/cadres（增删，越权 403，同职务重复 409）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const POSITION = {
  MONITOR: '班长', VICE_MONITOR: '副班长', LEAGUE_SECRETARY: '团支书',
  STUDY_COMMITTEE: '学习委员', LIFE_COMMITTEE: '生活委员', PSYCH_COMMITTEE: '心理委员',
  SPORTS_ART_COMMITTEE: '文体委员', ORG_COMMITTEE: '组织委员', PUBLICITY_COMMITTEE: '宣传委员'
}

export default {
  name: 'ClassManageView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, listError: '', classes: [],
      selected: null, cadres: [], cadreLoading: false, acting: false,
      appointModal: { visible: false, position: 'MONITOR', studentId: '', termCode: '', error: '' },
      dismissDialog: { visible: false, message: '', cadre: null },
      positions: Object.entries(POSITION).map(([value, label]) => ({ value, label }))
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    activeCadres() {
      return this.cadres.filter((c) => c.status === 'ACTIVE')
    },
    removedCadres() {
      return this.cadres.filter((c) => c.status !== 'ACTIVE')
    }
  },
  created() {
    this.loadClasses()
  },
  methods: {
    positionLabel(p) {
      return POSITION[p] || p || '—'
    },
    async loadClasses() {
      this.loading = true
      this.listError = ''
      const res = await studentAffairsApi.getClasses()
      this.loading = false
      if (res.code === 0 && res.data) {
        this.classes = res.data.items || []
      } else {
        this.listError = res.message || '班级加载失败'
      }
    },
    async select(c) {
      this.selected = c
      await this.loadCadres()
    },
    async loadCadres() {
      if (!this.selected) return
      this.cadreLoading = true
      const res = await studentAffairsApi.getClassCadres(this.selected.classId)
      this.cadreLoading = false
      if (res.code === 0 && res.data) this.cadres = res.data.items || []
      else { this.cadres = []; toast.error(res.message || '班干部加载失败') }
    },
    openAppoint() {
      this.appointModal = { visible: true, position: 'MONITOR', studentId: '', termCode: '', error: '' }
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async submitAppoint() {
      const m = this.appointModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      this.acting = true
      const res = await studentAffairsApi.appointCadre(this.selected.classId, {
        studentId: String(m.studentId), position: m.position, termCode: m.termCode || null
      })
      this.acting = false
      if (res.code === 0) {
        toast.success('已任命')
        this.appointModal.visible = false
        this.loadCadres()
      } else {
        m.error = res.message || '任命失败'
        toast.error(m.error)
      }
    },
    onDismiss(cadre) {
      this.dismissDialog = { visible: true, cadre, message: `确认免去 ${this.positionLabel(cadre.position)}（学生#${cadre.studentId}）？` }
    },
    async confirmDismiss() {
      this.acting = true
      const res = await studentAffairsApi.dismissCadre(this.dismissDialog.cadre.cadreId)
      this.acting = false
      this.dismissDialog.visible = false
      if (res.code === 0) {
        toast.success('已免去')
        this.loadCadres()
      } else {
        toast.error(res.message || '免去失败')
      }
    }
  }
}
</script>

<style scoped>
.cl-workspace {
  display: grid;
  grid-template-columns: minmax(240px, 300px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.cl-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-3);
}
.cl-list__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}
.cl-list__count {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-weight: 400;
}
.cl-classes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.cl-citem {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-base);
  cursor: pointer;
}
.cl-citem:hover {
  background: var(--bg-hover, #f5f7fa);
}
.cl-citem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.cl-citem__name {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.cl-citem__grade {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.cl-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.cl-dhead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.cl-dname {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.cl-cadres {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.cl-cadre {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
}
.cl-cadre__pos {
  font-weight: 600;
  color: var(--primary-700);
  margin-right: var(--space-3);
}
.cl-cadre__stu {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.cl-cadre__term {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-left: var(--space-2);
}
.cl-history {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.cl-history__title {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.cl-history__row {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: 2px;
}
.cl-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.cl-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.cl-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.cl-btn--danger {
  border-color: var(--danger-300, #fca5a5);
  color: var(--danger-600, #dc2626);
}
.cl-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.cl-modal {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.cl-modal__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.cl-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.cl-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.cl-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.cl-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.cl-input {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.cl-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.cl-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
