/** 统一导航封装：容错处理，避免路径写错时白屏 */
export function go(url) {
  uni.navigateTo({
    url,
    fail() {
      uni.switchTab({ url, fail() { uni.reLaunch({ url }) } })
    }
  })
}
export function relaunch(url) {
  uni.reLaunch({ url })
}
export function back() {
  uni.navigateBack({ fail() { uni.reLaunch({ url: '/pages/login/index' }) } })
}
export function toast(title, icon = 'none') {
  uni.showToast({ title, icon })
}
export default { go, relaunch, back, toast }
