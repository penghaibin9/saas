<template>
  <svg
    class="app-icon"
    :class="`app-icon--${name}`"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path :d="path" :stroke="color" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script>
const ICONS = {
  overview: 'M4 6h16M4 12h16M4 18h10',
  lifecycle: 'M12 3v18M3 12h18',
  kpi: 'M12 7v10M7 12h10',
  risk: 'M12 9v4M12 17h.01M10.3 4.5h3.4L20 19H4L10.3 4.5z',
  workbench: 'M9 11l2 2 4-4M5 5h14v14H5z',
  students: 'M12 12a3 3 0 100-6 3 3 0 000 6zM5 19a7 7 0 0114 0',
  topics: 'M4 5h16M4 10h16M4 15h10M4 20h7',
  records: 'M8 6h8M8 10h8M8 14h5M6 4h12v16H6z',
  enrollment: 'M12 3l9 5-9 5-9-5 9-5zM3 12l9 5 9-5',
  reports: 'M6 4h9l3 3v13H6zM9 13h6M9 17h4',
  settings: 'M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM19.4 15a1.8 1.8 0 00.3 2l.1.1a2 2 0 01-2.8 2.8l-.1-.1a1.8 1.8 0 00-2-.3 1.8 1.8 0 00-1.1 1.6V22a2 2 0 01-4 0v-.2A1.8 1.8 0 007 20.1a1.8 1.8 0 00-2 .3l-.1.1a2 2 0 01-2.8-2.8l.1-.1a1.8 1.8 0 00.3-2 1.8 1.8 0 00-1.6-1.1H2a2 2 0 010-4h.2A1.8 1.8 0 004.9 9a1.8 1.8 0 00-.3-2l-.1-.1a2 2 0 012.8-2.8l.1.1A1.8 1.8 0 007 4.9a1.8 1.8 0 001.1-1.6V3a2 2 0 014 0v.2A1.8 1.8 0 0017 4.9a1.8 1.8 0 002-.3l.1-.1a2 2 0 012.8 2.8l-.1.1a1.8 1.8 0 00-.3 2 1.8 1.8 0 001.6 1.1H22a2 2 0 010 4h-.2a1.8 1.8 0 00-1.6 1.1z'
}

export default {
  name: 'AppIcon',
  props: {
    name: { type: String, required: true },
    size: { type: [Number, String], default: 18 },
    color: { type: String, default: 'currentColor' }
  },
  computed: {
    path() {
      return ICONS[this.name] || ICONS.overview
    }
  }
}
</script>

<style scoped>
.app-icon {
  display: inline-block;
  flex-shrink: 0;
  vertical-align: middle;
}
</style>
