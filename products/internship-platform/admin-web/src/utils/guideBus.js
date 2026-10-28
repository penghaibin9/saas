/**
 * 新手引导事件总线（极简，不引第三方库）。
 *
 * 用途：顶栏「?」按钮与业务页内的 AppPageGuide 相隔一层布局、无父子关系，
 * 用它把「重看本页引导」的点击传给当前页已挂载的引导组件。
 *
 * guideCount 是响应式的：顶栏据此判断当前页登记了引导没有，
 * 没有就把「重看本页引导」置灰，而不是给个点了没反应的死按钮。
 *
 * 约定：一页一引导。replay 不带 key，由当前挂载的组件自己响应。
 */
import { ref } from 'vue'

const listeners = new Set()

/** 当前页已登记的引导数量（响应式）。 */
export const guideCount = ref(0)

/** 订阅重看请求；返回取消订阅函数（组件 unmounted 时务必调用，防止路由切换后泄漏）。 */
export function onGuideReplay(fn) {
  listeners.add(fn)
  guideCount.value = listeners.size
  return () => {
    listeners.delete(fn)
    guideCount.value = listeners.size
  }
}

/** 请求重看当前页引导。 */
export function replayGuide() {
  listeners.forEach((fn) => fn())
}
