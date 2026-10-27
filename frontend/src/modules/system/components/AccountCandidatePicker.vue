<template>
  <section class="mp-stack" aria-label="选择本校人员">
    <label>姓名或工号
      <input v-model="keyword" class="mp-input" :disabled="disabled" @input="$emit('update:modelValue', null)" @keyup.enter="search(1)" />
    </label>
    <button type="button" class="mp-link" :disabled="disabled || loading" @click="search(1)">查询人员</button>
    <p v-if="modelValue" role="status">已选：{{ modelValue.name }} · {{ modelValue.userNo }} · {{ modelValue.orgName || '归属信息未提供' }}</p>
    <p v-if="loading" role="status">正在查询人员…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <template v-else-if="queried">
      <button v-for="person in rows" :key="person.id" type="button" class="mp-link" :disabled="disabled" @click="choose(person)">
        选择 {{ person.name }} · {{ person.userNo }} · {{ person.orgName || '归属信息未提供' }}
      </button>
      <p v-if="!rows.length">没有符合条件的在用账号，请调整姓名或工号。</p>
      <div>共 {{ total }} 人 · 第 {{ page }} 页
        <button type="button" class="mp-link" :disabled="disabled || page <= 1" @click="search(page - 1)">上一页人员</button>
        <button type="button" class="mp-link" :disabled="disabled || page * 10 >= total" @click="search(page + 1)">下一页人员</button>
      </div>
    </template>
  </section>
</template>
<script>
import { systemApi } from '../api/system.api'
import { contextFingerprint } from '../utils/workspaceContract'
export default {
  name: 'AccountCandidatePicker',
  props: { modelValue: { type: Object, default: null }, ctx: { type: Object, required: true }, disabled: Boolean, accountType: { type: String, default: '' }, searchAccounts: { type: Function, default: null } },
  emits: ['update:modelValue'],
  data: () => ({ keyword: '', rows: [], total: 0, page: 1, loading: false, error: '', sequence: 0, queried: false }),
  computed: { contextKey() { return contextFingerprint(this.ctx) } },
  watch: { contextKey() { this.sequence++; this.rows = []; this.loading = false; this.queried = false; this.$emit('update:modelValue', null) } },
  beforeUnmount() { this.sequence++ },
  methods: {
    choose(person) {
      if (this.disabled || this.loading || !this.rows.includes(person)) return
      this.$emit('update:modelValue', { ...person })
    },
    async search(page) {
      if (this.disabled || this.loading) return
      const sequence = ++this.sequence
      this.$emit('update:modelValue', null)
      this.loading = true; this.error = ''; this.rows = []
      const response = await (this.searchAccounts || systemApi.getAuthorizationCandidates)({ keyword: this.keyword.trim(), accountType: this.accountType || undefined, status: 'ACTIVE', page, pageSize: 10 })
      if (sequence !== this.sequence) return
      this.loading = false; this.queried = true
      if (response.code !== 0) { this.error = response.message; return }
      this.rows = response.data.list; this.total = response.data.total; this.page = page
    }
  }
}
</script>
