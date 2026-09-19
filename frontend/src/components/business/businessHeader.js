import { computed, provide, ref, markRaw } from 'vue'

// A layout supplies its existing selector; only the outer page shell hosts it.
export function provideBusinessHeader(component) {
  const hosts = ref(0)
  provide('businessHeader', {
    component: markRaw(component),
    register() { hosts.value += 1; return () => { hosts.value -= 1 } }
  })
  return computed(() => hosts.value > 0)
}
