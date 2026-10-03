<template>
  <router-view />
  <SystemDialogHost />
  <AppToast />
</template>

<script setup>
import AppToast from '@/components/common/AppToast.vue'
import SystemDialogHost from '@/components/common/SystemDialogHost.vue'
</script>
