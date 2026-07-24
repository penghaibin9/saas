<template>
  <div class="aud">
    <div class="aud__scopes">
      <button
        v-for="s in allowedScopes"
        :key="s.key"
        type="button"
        class="aud__chip"
        :class="{ 'is-on': scope === s.key }"
        @click="setScope(s.key)"
      >
        {{ s.label }}
      </button>
    </div>

    <div v-if="scope === 'CLASS'" class="aud__pick">
      <AppClassPicker
        v-model="classIds"
        multiple
        data-scope-hint="仅显示你负责或授权范围内的班级"
        placeholder="选择一个或多个班级"
        @change="emitChange"
      />
    </div>
    <div v-else-if="scope === 'COLLEGE'" class="aud__pick">
      <AppCollegePicker
        v-model="collegeIds"
        multiple
        data-scope-hint="仅显示你授权学院"
        placeholder="选择学院"
        @change="emitChange"
      />
    </div>
    <div v-else class="aud__pick aud__hint">
      {{ scopeHint }}
    </div>
  </div>
</template>

<script>
/**
 * 受众范围选择：本班 / 本学院 / 全校学生 / 全校教职工 / 全校师生。
 * 具体可见项由后端 audience-options + 权限码决定，前端不放大范围。
 */
import { AppClassPicker, AppCollegePicker } from '@/components/common'

const ALL_SCOPES = [
  { key: 'CLASS', label: '指定班级', need: 'workbench.message.class.publish' },
  { key: 'COLLEGE', label: '指定学院', need: 'workbench.message.college.publish' },
  { key: 'ALL_STUDENT', label: '全校学生', need: 'workbench.message.schoolStudent.publish' },
  { key: 'ALL_STAFF', label: '全校教职工', need: 'workbench.message.schoolStaff.publish' },
  { key: 'ALL_USERS', label: '全校师生', need: 'workbench.message.schoolAll.publish' }
]

function matchPerm(patterns, code) {
  if (!patterns) return true
  if (patterns.includes('*')) return true
  if (patterns.includes(code)) return true
  return patterns.some((p) => typeof p === 'string' && p.endsWith('.*') && code.startsWith(p.slice(0, -1)))
}

export default {
  name: 'AudienceSelector',
  components: { AppClassPicker, AppCollegePicker },
  props: {
    modelValue: { type: Array, default: () => [] },
    permissionPatterns: { type: Array, default: null }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return {
      scope: 'CLASS',
      classIds: [],
      collegeIds: []
    }
  },
  computed: {
    allowedScopes() {
      const patterns = this.permissionPatterns
      const hasPublish = matchPerm(patterns, 'workbench.message.publish')
        || ALL_SCOPES.some((s) => matchPerm(patterns, s.need))
      return ALL_SCOPES.filter((s) => {
        if (matchPerm(patterns, s.need)) return true
        // 有通用 publish 时至少开放本班（辅导员）
        if (s.key === 'CLASS' && hasPublish) return true
        // schoolAll 覆盖全校学生/教职工入口
        if ((s.key === 'ALL_STUDENT' || s.key === 'ALL_STAFF') && matchPerm(patterns, 'workbench.message.schoolAll.publish')) {
          return true
        }
        return false
      })
    },
    scopeHint() {
      const map = {
        ALL_STUDENT: '将发送给本校全部在籍且已开通账号的学生（排除毕业/停用等）。',
        ALL_STAFF: '将发送给本校全部在职教职工账号。',
        ALL_USERS: '将发送给本校全部学生与教职工账号。'
      }
      return map[this.scope] || ''
    }
  },
  watch: {
    allowedScopes: {
      immediate: true,
      handler(list) {
        if (!list.length) return
        if (!list.some((s) => s.key === this.scope)) {
          this.scope = list[0].key
          this.emitChange()
        }
      }
    }
  },
  methods: {
    setScope(key) {
      this.scope = key
      this.emitChange()
    },
    buildAudiences() {
      if (this.scope === 'CLASS') {
        const ids = (Array.isArray(this.classIds) ? this.classIds : [this.classIds])
          .map((x) => Number(x)).filter(Boolean)
        return ids.length
          ? [{ type: 'CLASS', includeOrExclude: 'INCLUDE', targetIds: ids }]
          : []
      }
      if (this.scope === 'COLLEGE') {
        const ids = (Array.isArray(this.collegeIds) ? this.collegeIds : [this.collegeIds])
          .map((x) => Number(x)).filter(Boolean)
        return ids.length
          ? [{ type: 'COLLEGE', includeOrExclude: 'INCLUDE', targetIds: ids }]
          : []
      }
      return [{ type: this.scope, includeOrExclude: 'INCLUDE', targetIds: [] }]
    },
    emitChange() {
      const audiences = this.buildAudiences()
      this.$emit('update:modelValue', audiences)
      this.$emit('change', audiences)
    }
  }
}
</script>

<style scoped>
.aud__scopes { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.aud__chip {
  height: 30px; padding: 0 12px; border-radius: 999px;
  border: 1px solid var(--border-base); background: var(--bg-card);
  color: var(--text-secondary); cursor: pointer; font-size: var(--font-size-sm);
}
.aud__chip.is-on {
  border-color: var(--primary-500); background: var(--primary-50, #eff6ff);
  color: var(--primary-700); font-weight: 600;
}
.aud__hint { font-size: var(--font-size-sm); color: var(--text-tertiary); line-height: 1.6; }
</style>
