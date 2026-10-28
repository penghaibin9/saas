<template>
  <div class="app-avatar-group" :class="`is-${size}`">
    <span
      v-for="(a, i) in shown"
      :key="a.id || a.name || i"
      class="app-avatar-group__item"
      :style="{ background: a.src ? 'transparent' : colorOf(a), zIndex: shown.length - i }"
      :title="a.name || ''"
    >
      <img v-if="a.src" class="app-avatar-group__img" :src="a.src" :alt="a.name || ''" />
      <span v-else class="app-avatar-group__initials">{{ initials(a.name) }}</span>
    </span>
    <span v-if="overflow > 0" class="app-avatar-group__item app-avatar-group__more" :title="moreTitle">
      +{{ overflow }}
    </span>
  </div>
</template>

<script>
/**
 * AppAvatarGroup — 头像组（答辩组成员、导师团队、协作人员叠加展示）。
 * Props:
 *  - avatars: [{ id?, name, src? }]（无 src 用姓名首字，自动配色）
 *  - max: 最多展示几个，其余折叠为 +N
 *  - size: sm | md | lg
 * 无业务逻辑；姓名脱敏由调用方决定（敏感场景传脱敏后的名字）。
 */
const PALETTE = ['#2563eb', '#0891b2', '#7c3aed', '#db2777', '#ea580c', '#16a34a', '#ca8a04']
export default {
  name: 'AppAvatarGroup',
  props: {
    avatars: { type: Array, default: () => [] },
    max: { type: Number, default: 5 },
    size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg'].includes(v) }
  },
  computed: {
    shown() { return this.avatars.slice(0, this.max) },
    overflow() { return Math.max(0, this.avatars.length - this.max) },
    moreTitle() { return this.avatars.slice(this.max).map((a) => a.name).filter(Boolean).join('、') }
  },
  methods: {
    initials(name) {
      if (!name) return '?'
      const s = String(name).trim()
      // 中文取末一字（姓名习惯），英文取首字母
      return /[一-龥]/.test(s) ? s.slice(-1) : s.slice(0, 1).toUpperCase()
    },
    colorOf(a) {
      const key = String(a.name || a.id || '')
      let h = 0
      for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0
      return PALETTE[h % PALETTE.length]
    }
  }
}
</script>

<style scoped>
.app-avatar-group { display: inline-flex; align-items: center; }
.app-avatar-group__item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  border: 2px solid var(--bg-card);
  color: #fff;
  font-weight: var(--font-weight-medium);
  overflow: hidden;
  margin-left: -8px;
  flex-shrink: 0;
}
.app-avatar-group__item:first-child { margin-left: 0; }
.is-sm .app-avatar-group__item { width: 24px; height: 24px; font-size: 10px; margin-left: -6px; }
.is-md .app-avatar-group__item { width: 32px; height: 32px; font-size: var(--font-size-xs); }
.is-lg .app-avatar-group__item { width: 40px; height: 40px; font-size: var(--font-size-sm); }
.app-avatar-group__img { width: 100%; height: 100%; object-fit: cover; }
.app-avatar-group__more { background: var(--gray-400); }
</style>
