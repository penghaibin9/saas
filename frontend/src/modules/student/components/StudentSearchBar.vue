<template>
  <div class="stu-search">
    <input
      class="stu-search__input"
      :value="modelValue.keyword"
      placeholder="姓名 / 学号 / 手机号后四位"
      @input="update('keyword', $event.target.value)"
      @keyup.enter="$emit('search')"
    />
    <select :value="modelValue.collegeId" @change="onCollege($event.target.value)">
      <option value="">全部学院</option>
      <option v-for="c in options.colleges" :key="c.id" :value="c.id">{{ c.name }}</option>
    </select>
    <select :value="modelValue.majorId" @change="onMajor($event.target.value)">
      <option value="">全部专业</option>
      <option v-for="m in majorsFiltered" :key="m.id" :value="m.id">{{ m.name }}</option>
    </select>
    <select :value="modelValue.classId" @change="update('classId', $event.target.value)">
      <option value="">全部班级</option>
      <option v-for="c in classesFiltered" :key="c.id" :value="c.id">{{ c.name }}</option>
    </select>
    <select :value="modelValue.grade" @change="update('grade', $event.target.value)">
      <option value="">全部年级</option>
      <option v-for="g in options.grades" :key="g.id" :value="g.id">{{ g.name }}</option>
    </select>
    <select :value="modelValue.studentStatus" @change="update('studentStatus', $event.target.value)">
      <option value="">学生状态</option>
      <option v-for="(label, code) in statusLabels" :key="code" :value="code">{{ label }}</option>
    </select>
    <select :value="modelValue.identityVerifyStatus" @change="update('identityVerifyStatus', $event.target.value)">
      <option value="">认证状态</option>
      <option v-for="(label, code) in identityLabels" :key="code" :value="code">{{ label }}</option>
    </select>
    <select :value="modelValue.accountStatus" @change="update('accountStatus', $event.target.value)">
      <option value="">账号状态</option>
      <option v-for="(label, code) in accountLabels" :key="code" :value="code">{{ label }}</option>
    </select>
    <AppButton variant="secondary" @click="$emit('search')">查询</AppButton>
    <AppButton variant="ghost" @click="$emit('reset')">重置</AppButton>
  </div>
</template>

<script>
/**
 * StudentSearchBar — 学生筛选条。
 * 下拉数据全部来自 options 接口（字典），禁止硬编码；学院/专业/班级三级联动。
 */
import { AppButton } from '@/components/ui'
import {
  STUDENT_STATUS_LABELS,
  IDENTITY_VERIFY_STATUS_LABELS,
  ACCOUNT_STATUS_LABELS
} from '../constants/student.constants'

export default {
  name: 'StudentSearchBar',
  components: { AppButton },
  props: {
    modelValue: { type: Object, required: true },
    options: {
      type: Object,
      default: () => ({ colleges: [], majors: [], classes: [], grades: [] })
    }
  },
  emits: ['update:modelValue', 'search', 'reset'],
  computed: {
    statusLabels: () => STUDENT_STATUS_LABELS,
    identityLabels: () => IDENTITY_VERIFY_STATUS_LABELS,
    accountLabels: () => ACCOUNT_STATUS_LABELS,
    majorsFiltered() {
      const cid = this.modelValue.collegeId
      return cid ? this.options.majors.filter((m) => m.collegeId === cid) : this.options.majors
    },
    classesFiltered() {
      const mid = this.modelValue.majorId
      return mid ? this.options.classes.filter((c) => c.majorId === mid) : this.options.classes
    }
  },
  methods: {
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
    },
    onCollege(value) {
      this.$emit('update:modelValue', { ...this.modelValue, collegeId: value, majorId: '', classId: '' })
    },
    onMajor(value) {
      this.$emit('update:modelValue', { ...this.modelValue, majorId: value, classId: '' })
    }
  }
}
</script>

<style scoped>
.stu-search { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.stu-search__input,
.stu-search select {
  height: 32px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: 0 var(--space-3);
  font: inherit;
  color: var(--text-primary);
  background: var(--bg-card);
  box-sizing: border-box;
}
.stu-search__input { min-width: 200px; }
.stu-search__input:focus,
.stu-search select:focus { outline: none; border-color: var(--primary-500); }
</style>
