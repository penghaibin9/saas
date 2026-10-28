<template>
  <form
    class="app-form"
    :class="[`is-${layout}`, `is-${size}`]"
    :style="layout === 'horizontal' ? { '--app-form-label-w': labelWidth } : null"
    novalidate
    @submit.prevent="onSubmit"
  >
    <slot />
  </form>
</template>

<script>
/**
 * AppForm — 通用表单容器（提供布局/密度/禁用/只读上下文 + 轻量校验，不绑定任何业务接口）。
 *
 * 校验：传 model + rules，调用 ref.validate() 返回 Promise<{ valid, errors }>；
 *      rules 结构：{ 字段名: [{ required?, message?, min?, max?, pattern?, validator? }] }
 *      validator(value, model) 返回 true/字符串(错误信息)/Promise。
 *
 * Props:
 *  - model: 表单数据对象（校验时读取字段值）
 *  - rules: 校验规则
 *  - layout: horizontal | vertical | inline
 *  - labelWidth: 水平布局下 label 宽度（默认 96px）
 *  - labelAlign: left | right
 *  - size: normal | compact（密度）
 *  - disabled / readonly: 统一下发给所有子控件（子控件读取上下文）
 * Emits: submit(model)（回车或提交按钮触发，已 preventDefault）
 * 暴露方法：validate() / validateField(prop) / clearValidate(prop?)
 */
export default {
  name: 'AppForm',
  provide() {
    return { appForm: this }
  },
  props: {
    model: { type: Object, default: () => ({}) },
    rules: { type: Object, default: () => ({}) },
    layout: {
      type: String,
      default: 'horizontal',
      validator: (v) => ['horizontal', 'vertical', 'inline'].includes(v)
    },
    labelWidth: { type: String, default: '96px' },
    labelAlign: {
      type: String,
      default: 'right',
      validator: (v) => ['left', 'right'].includes(v)
    },
    size: {
      type: String,
      default: 'normal',
      validator: (v) => ['normal', 'compact'].includes(v)
    },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false }
  },
  emits: ['submit'],
  data() {
    return { fieldErrors: {} }
  },
  methods: {
    async runFieldRules(prop) {
      const rules = this.rules[prop]
      if (!rules || !rules.length) return ''
      const value = this.model ? this.model[prop] : undefined
      for (const r of rules) {
        if (r.required && (value === undefined || value === null || value === '' ||
            (Array.isArray(value) && !value.length))) {
          return r.message || '此项为必填'
        }
        if (value === undefined || value === null || value === '') continue
        if (r.min != null && String(value).length < r.min) return r.message || `不少于 ${r.min} 个字`
        if (r.max != null && String(value).length > r.max) return r.message || `不超过 ${r.max} 个字`
        if (r.pattern && !r.pattern.test(String(value))) return r.message || '格式不正确'
        if (typeof r.validator === 'function') {
          const res = await r.validator(value, this.model)
          if (res === false) return r.message || '校验未通过'
          if (typeof res === 'string') return res
        }
      }
      return ''
    },
    async validateField(prop) {
      const msg = await this.runFieldRules(prop)
      this.fieldErrors = { ...this.fieldErrors, [prop]: msg }
      return !msg
    },
    async validate() {
      const props = Object.keys(this.rules)
      const results = await Promise.all(props.map((p) => this.runFieldRules(p)))
      const errors = {}
      props.forEach((p, i) => { errors[p] = results[i] })
      this.fieldErrors = errors
      const invalid = props.filter((p) => errors[p])
      return { valid: invalid.length === 0, errors, firstInvalid: invalid[0] || '' }
    },
    clearValidate(prop) {
      if (prop) {
        this.fieldErrors = { ...this.fieldErrors, [prop]: '' }
      } else {
        this.fieldErrors = {}
      }
    },
    async onSubmit() {
      const { valid } = await this.validate()
      if (valid) this.$emit('submit', this.model)
    }
  }
}
</script>

<style scoped>
.app-form {
  display: block;
}
.app-form.is-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-3) var(--space-4);
}
</style>
