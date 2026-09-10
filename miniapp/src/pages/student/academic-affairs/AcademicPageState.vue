<template>
  <MobileGlobalState v-bind="$attrs" @retry="$emit('retry')" @back="back" @contact="contact"><slot /></MobileGlobalState>
</template>
<script>
import { back } from '@/utils/nav'
export default {
  inheritAttrs: false,
  emits: ['retry'],
  methods: {
    back,
    contact() { uni.showModal({ title: '联系学校核对', content: '请联系辅导员或教务处，说明当前页面和需要办理的事项，由学校核对权限与办理条件。', showCancel: false }) }
  }
}
</script>
