<template>
  <section class="role-scope-editor">
    <div class="role-scope-editor__heading">
      <div>
        <strong>角色身份与授权范围</strong>
        <p>每个角色单独配置可管理的学校、学院、专业、班级或学生。</p>
      </div>
      <span>{{ selectedRoleCodes.length }} 个角色</span>
    </div>

    <AppCheckboxGroup
      :model-value="selectedRoleCodes"
      :options="roleOptions"
      :disabled="disabled"
      @update:model-value="onRolesChange"
    />

    <div v-if="loading" class="role-scope-editor__state">正在加载组织范围…</div>
    <div v-else-if="!selectedAssignments.length" class="role-scope-editor__empty">
      请先选择至少一个角色
    </div>
    <div v-else class="role-scope-editor__cards">
      <article
        v-for="assignment in selectedAssignments"
        :key="assignment.roleCode"
        class="role-scope-card"
        :class="{ 'is-missing': needsScope(assignment) && !assignment.scopeIds.length }"
      >
        <header class="role-scope-card__header">
          <div>
            <strong>{{ assignment.roleName }}</strong>
            <code>{{ assignment.roleCode }}</code>
          </div>
          <span class="role-scope-card__badge">{{ scopeBadge(assignment) }}</span>
        </header>

        <div v-if="assignment.scopeMode === 'AUTO'" class="role-scope-card__auto">
          <strong>范围自动确定</strong>
          <span>{{ assignment.scopePolicyLabel }}</span>
        </div>

        <div v-else-if="assignment.scopeType === 'SCHOOL'" class="role-scope-card__school">
          <span class="role-scope-card__school-dot" />
          <div><strong>全校范围</strong><small>覆盖本校全部学院、专业、班级和学生</small></div>
        </div>

        <template v-else>
          <div v-if="assignment.scopeMode === 'FLEX'" class="role-scope-card__field">
            <label>授权层级</label>
            <AppSelect
              :model-value="assignment.scopeType"
              :options="scopeTypeOptions(assignment)"
              :disabled="disabled"
              @update:model-value="setScopeType(assignment.roleCode, $event)"
            />
          </div>

          <div class="role-scope-card__field">
            <label>{{ scopeFieldLabel(assignment.scopeType) }}</label>
            <AppRemoteSelect
              v-if="assignment.scopeType === 'STUDENT'"
              :model-value="assignment.scopeIds"
              multiple
              :max="100"
              :remote-search="studentSearch"
              :resolve-by-value="studentResolve"
              placeholder="按姓名或学号搜索并选择学生"
              search-placeholder="输入姓名或学号"
              data-scope-hint="只保存明确选中的学生，不向班级或专业扩大"
              :disabled="disabled"
              @update:model-value="setScopeIds(assignment.roleCode, $event)"
            />
            <AppMultiSelect
              v-else
              :model-value="assignment.scopeIds"
              :options="scopeOptions(assignment.scopeType)"
              searchable
              :max="20"
              :placeholder="`选择${scopeFieldLabel(assignment.scopeType)}`"
              :disabled="disabled"
              @update:model-value="setScopeIds(assignment.roleCode, $event)"
            />
            <small v-if="needsScope(assignment) && !assignment.scopeIds.length" class="role-scope-card__error">
              必须选择具体范围，空范围不会自动解释为全校
            </small>
            <small v-else class="role-scope-card__hint">{{ scopeHint(assignment) }}</small>
          </div>
        </template>
      </article>
    </div>
  </section>
</template>

<script>
import { AppCheckboxGroup, AppMultiSelect, AppRemoteSelect, AppSelect } from '@/components/common'

const TYPE_LABELS = {
  SCHOOL: '学校',
  COLLEGE: '学院',
  MAJOR: '专业',
  CLASS: '班级',
  STUDENT: '学生'
}

export default {
  name: 'RoleScopeEditor',
  components: { AppCheckboxGroup, AppMultiSelect, AppRemoteSelect, AppSelect },
  props: {
    modelValue: { type: Array, default: () => [] },
    roleOptions: { type: Array, default: () => [] },
    orgTree: { type: Array, default: () => [] },
    studentSearch: { type: Function, default: null },
    studentResolve: { type: Function, default: null },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue'],
  computed: {
    selectedRoleCodes() {
      return this.modelValue.map((item) => item.roleCode)
    },
    selectedAssignments() {
      const order = new Map(this.roleOptions.map((role, index) => [role.value, index]))
      return [...this.modelValue].sort(
        (a, b) => (order.get(a.roleCode) ?? 999) - (order.get(b.roleCode) ?? 999)
      )
    }
  },
  methods: {
    optionOf(roleCode) {
      return this.roleOptions.find((option) => option.value === roleCode) || {
        value: roleCode,
        label: roleCode,
        scopeMode: 'FLEX',
        scopeType: 'COLLEGE',
        allowedScopeTypes: ['COLLEGE', 'MAJOR', 'CLASS', 'STUDENT'],
        scopePolicyLabel: '按指定范围授权'
      }
    },
    makeAssignment(option) {
      const scopeType = option.scopeType || 'COLLEGE'
      return {
        roleCode: option.value,
        roleName: option.label,
        roleScopeCode: option.roleScopeCode || scopeType,
        scopeMode: option.scopeMode || 'FLEX',
        scopeType,
        allowedScopeTypes: option.allowedScopeTypes || ['COLLEGE', 'MAJOR', 'CLASS', 'STUDENT'],
        scopePolicyLabel: option.scopePolicyLabel || '按指定范围授权',
        scopeIds: scopeType === 'SCHOOL' ? ['0'] : []
      }
    },
    emit(next) {
      this.$emit('update:modelValue', next.map((item) => ({ ...item, scopeIds: [...(item.scopeIds || [])] })))
    },
    onRolesChange(roleCodes) {
      const current = new Map(this.modelValue.map((item) => [item.roleCode, item]))
      this.emit(roleCodes.map((code) => current.get(code) || this.makeAssignment(this.optionOf(code))))
    },
    updateRole(roleCode, patch) {
      this.emit(this.modelValue.map((item) => (item.roleCode === roleCode ? { ...item, ...patch } : item)))
    },
    setScopeType(roleCode, scopeType) {
      this.updateRole(roleCode, { scopeType, scopeIds: scopeType === 'SCHOOL' ? ['0'] : [] })
    },
    setScopeIds(roleCode, scopeIds) {
      this.updateRole(roleCode, { scopeIds: (scopeIds || []).map(String) })
    },
    needsScope(assignment) {
      return assignment.scopeMode !== 'AUTO' && assignment.scopeType !== 'SCHOOL'
    },
    scopeBadge(assignment) {
      if (assignment.scopeMode === 'AUTO') return '业务关系'
      return TYPE_LABELS[assignment.scopeType] || assignment.scopeType
    },
    scopeFieldLabel(scopeType) {
      return `授权${TYPE_LABELS[scopeType] || '范围'}`
    },
    scopeTypeOptions(assignment) {
      return (assignment.allowedScopeTypes || []).map((value) => ({ value, label: TYPE_LABELS[value] || value }))
    },
    scopeOptions(scopeType) {
      const options = []
      const walk = (nodes, path = []) => {
        ;(nodes || []).forEach((node) => {
          const currentPath = [...path, node.name]
          if (node.type === scopeType) {
            options.push({
              value: String(node.id),
              label: currentPath.join(' / '),
              disabled: node.status && node.status !== 'ENABLED'
            })
          }
          walk(node.children, currentPath)
        })
      }
      walk(this.orgTree)
      return options
    },
    scopeHint(assignment) {
      const count = assignment.scopeIds.length
      const type = TYPE_LABELS[assignment.scopeType] || '范围'
      if (!count) return assignment.scopePolicyLabel
      const suffix = assignment.scopeType === 'COLLEGE'
        ? '，自动覆盖其下专业、班级和学生'
        : assignment.scopeType === 'MAJOR'
          ? '，自动覆盖其下班级和学生'
          : assignment.scopeType === 'CLASS'
            ? '，自动覆盖班内学生'
            : '，仅覆盖选中学生'
      return `已选择 ${count} 个${type}${suffix}`
    }
  }
}
</script>

<style scoped>
.role-scope-editor {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-4);
}
.role-scope-editor__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}
.role-scope-editor__heading strong { font-size: var(--font-size-sm); }
.role-scope-editor__heading p {
  margin: var(--space-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.role-scope-editor__heading > span {
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  padding: 2px var(--space-2);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}
.role-scope-editor__state,
.role-scope-editor__empty {
  padding: var(--space-4);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}
.role-scope-editor__cards { display: grid; gap: var(--space-3); }
.role-scope-card {
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}
.role-scope-card.is-missing { border-color: var(--warning-400); background: var(--warning-50); }
.role-scope-card__header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.role-scope-card__header > div { display: flex; align-items: center; gap: var(--space-2); }
.role-scope-card__header strong { font-size: var(--font-size-sm); }
.role-scope-card__header code { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.role-scope-card__badge {
  align-self: flex-start;
  color: var(--primary-700);
  background: var(--primary-50);
  border-radius: var(--radius-full);
  padding: 2px var(--space-2);
  font-size: var(--font-size-xs);
}
.role-scope-card__field { display: grid; grid-template-columns: 88px minmax(0, 1fr); gap: var(--space-2) var(--space-3); align-items: start; }
.role-scope-card__field + .role-scope-card__field { margin-top: var(--space-2); }
.role-scope-card__field > label { padding-top: 7px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.role-scope-card__field > small { grid-column: 2; font-size: var(--font-size-xs); }
.role-scope-card__error { color: var(--danger-600); }
.role-scope-card__hint { color: var(--text-tertiary); }
.role-scope-card__auto,
.role-scope-card__school {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  font-size: var(--font-size-sm);
}
.role-scope-card__auto { justify-content: space-between; }
.role-scope-card__auto span { color: var(--text-tertiary); }
.role-scope-card__school-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success-500); }
.role-scope-card__school div { display: grid; gap: 2px; }
.role-scope-card__school small { color: var(--text-tertiary); }
</style>
