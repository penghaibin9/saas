import { SHOWCASE } from './content.js'
import { mountNewsPreview } from './news-preview.js'
import { TourSoundtrack } from './tour-audio.js'

export const ASSET_BASE = '/official-site/showcase-20260909/'
export const INTERESTS = Object.freeze({
  'academic-affairs': '教务系统', 'student-affairs': '学工中心',
  graduation: '毕业设计', internship: '岗位实习', renshi: '高校人事系统',
  'wechat-academic': '教务与微信小程序', platform: '学生全生命周期平台',
  deployment: '私有化部署与系统集成', all: '整体解决方案'
})
export function consultationPath(interest) {
  const slug = Object.keys(INTERESTS).find(key => INTERESTS[key] === interest) || 'all'
  const params = new URLSearchParams({ product: slug, interest: INTERESTS[slug], source: 'official-showcase' })
  return `/contact?${params}`
}

/** Mount the approved, repository-authored markup. No prototype application is executed. */
export function mountShowcase(root, { contact, links = {}, navigate, consultBase = '', resolveAsset, loadModel = () => import('./campus-scene.js'), createSound = options => new TourSoundtrack(options) } = {}) {
  if (!root) throw new Error('Showcase root is required')
  const doc = root.ownerDocument
  const win = doc.defaultView
  const $ = selector => root.querySelector(selector)
  const $$ = selector => Array.from(root.querySelectorAll(selector))
  const data = SHOWCASE
  const state = { product: 'academic', hr: 0, mobile: 'teacher', board: 'academic', gallery: null, index: 0, scene: 'overview', model: false, playing: false, elapsed: 0 }
  const cleanup = [], frames = new Set(), openers = new WeakMap()
  cleanup.push(mountNewsPreview(root))
  let disposed = false, model = null, modelPending = null, audio = null, tickId = 0, lastTick = 0, toastTimer = 0, scrollLock = null, switching = false
  const reduced = win.matchMedia('(prefers-reduced-motion: reduce)')
  const asset = resolveAsset || (value => value.startsWith('assets/') ? ASSET_BASE + value.slice(7) : value)
  const listen = (target, type, handler, options) => {
    if (!target) return
    target.addEventListener(type, handler, options)
    cleanup.push(() => target.removeEventListener(type, handler, options))
  }
  const raf = callback => {
    const id = win.requestAnimationFrame(() => { frames.delete(id); if (!disposed) callback() })
    frames.add(id)
  }
  const text = (id, value) => { const node = $('#' + id); if (node) node.textContent = String(value) }
  const picture = (node, path, alt) => { if (node) { node.src = asset(path); if (alt) node.alt = alt } }
  function note(message) {
    text('toast', message)
    $('#toast').hidden = false
    win.clearTimeout(toastTimer)
    toastTimer = win.setTimeout(() => { if (!disposed) $('#toast').hidden = true }, 2800)
  }
  function closeDialog(dialog) {
    if (!dialog) return
    if (dialog.id === 'tour-dialog') {
      pauseTour(); model?.setEnabled(false); audio?.setEnabled(false)
      $('#tour-sound').setAttribute('aria-pressed', 'false'); text('tour-sound', '♫ 开启配乐')
    }
    dialog.close()
  }
  function releaseScroll() {
    if (!scrollLock) return
    doc.body.style.overflow = scrollLock.overflow
    doc.body.style.paddingRight = scrollLock.paddingRight
    scrollLock = null
    root.classList.remove('has-dialog')
  }
  function modal(id, opener = doc.activeElement) {
    const dialog = $('#' + id)
    if (!dialog || disposed) return
    if (!scrollLock) {
      scrollLock = { overflow: doc.body.style.overflow, paddingRight: doc.body.style.paddingRight }
      const gap = Math.max(0, win.innerWidth - doc.documentElement.clientWidth)
      if (gap) doc.body.style.paddingRight = `${gap}px`
    }
    switching = true
    $$('dialog[open]').filter(node => node !== dialog).forEach(node => closeDialog(node))
    const parentDialog = opener?.closest?.('dialog')
    openers.set(dialog, parentDialog ? openers.get(parentDialog) || opener : opener)
    try { if (!dialog.open) dialog.showModal() } catch { switching = false; releaseScroll(); note('浏览器暂不支持此预览，请使用产品介绍与电话咨询。'); return }
    switching = false
    root.classList.add('has-dialog')
    doc.body.style.overflow = 'hidden'
  }
  $$('dialog').forEach(dialog => {
    listen(dialog, 'close', () => {
      if (!switching && !disposed && !root.querySelector('dialog[open]')) {
        releaseScroll()
        const opener = openers.get(dialog)
        if (opener?.isConnected && !opener.closest('dialog:not([open])')) opener.focus({ preventScroll: true })
      }
    })
    listen(dialog, 'click', event => {
      if (event.target !== dialog) return
      const rect = dialog.getBoundingClientRect()
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeDialog(dialog)
    })
  })
  function selected(selector, key, attribute) {
    $$(selector).forEach(button => {
      const active = button.getAttribute(attribute) === String(key)
      button.setAttribute('aria-selected', String(active))
      button.tabIndex = active ? 0 : -1
    })
  }
  function tabs(selector, attribute, callback) {
    const group = $(selector)
    listen(group, 'click', event => {
      const button = event.target.closest(`button[${attribute}]`)
      if (button && group.contains(button)) callback(button.getAttribute(attribute))
    })
    listen(group, 'keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
      const items = Array.from(group.querySelectorAll(`button[${attribute}]`))
      const index = items.indexOf(doc.activeElement)
      if (index < 0) return
      event.preventDefault()
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length
      items[next].focus()
      callback(items[next].getAttribute(attribute))
    })
  }
  function product(key) {
    const entry = data.products[key]
    if (!entry) return
    state.product = key
    selected('.product-tabs button', key, 'data-product')
    $('#product-panel').setAttribute('aria-labelledby', 'p-' + key)
    text('product-tag', entry.tag); text('product-title', entry.headline); text('product-desc', entry.description)
    text('product-caption', entry.caption); text('product-consult', `咨询${entry.name}方案 ↗`)
    text('product-gallery-link', `查看${entry.name} 10 个 PC 经典页面 →`)
    picture($('#product-image'), entry.image, entry.caption + ' · 示例数据')
    $('#product-preview').setAttribute('aria-label', `查看${entry.name}经典画面`)
    for (const [id, values] of [['product-points', entry.points], ['product-steps', entry.steps]]) {
      $('#' + id).replaceChildren(...values.map(value => { const li = doc.createElement('li'); li.textContent = value; return li }))
    }
  }
  function hr(index) {
    const i = Number(index), slide = data.galleries.hr.slides[i]
    if (!Number.isInteger(i) || !slide) return
    state.hr = i
    selected('.hr-picks button', i, 'data-hr')
    picture($('#hr-image'), `assets/screens/${slide[0]}.webp`, slide[1] + ' · 示例数据')
    text('hr-screen-title', slide[1])
  }
  function mobile(role) {
    if (!['teacher', 'student'].includes(role)) return
    state.mobile = role
    const teacher = role === 'teacher'
    selected('.mobile-role button', role, 'data-mobile')
    text('mobile-title', teacher ? '老师打开，就看到今天的课。' : '学生打开，就知道现在要做什么。')
    text('mobile-desc', teacher ? '从当天课程进入点名、任务确认与成绩录入，把时间留给教学本身。' : '个人课表、学业待办与成绩查询集中呈现，让每个学习安排都更清楚。')
    text('mobile-gallery', `查看${teacher ? '教师' : '学生'}端 10 个经典页面 →`)
    $('#mobile-tags').replaceChildren(...data.galleries[role].slides.slice(0, 3).map(slide => { const span = doc.createElement('span'); span.textContent = slide[1]; return span }))
    picture($('#mobile-primary'), `assets/screens/${role}-home.webp`, `${teacher ? '教师今日教学' : '学生学业总览'}界面展示`)
    picture($('#mobile-secondary'), `assets/screens/${role}${teacher ? '-attendance' : '-schedule'}.webp`, '微信端精选界面展示')
  }
  function board(key) {
    if (!data.products[key]) return
    state.board = key
    selected('.board-tabs button', key, 'data-board')
    picture($('#board-image'), `assets/boards/${key}.webp`, data.products[key].name + '大屏展示图 · 非实时数据')
    text('board-consult', `了解${data.products[key].name}数据展示方案 ↗`)
  }
  const boardKeys = ['academic', 'affairs', 'internship', 'graduation']
  function galleryData() {
    if (state.gallery === 'boards') return { title: '学生业务运行大屏', board: true, slides: boardKeys.map(key => [key, data.products[key].name + '运行总览', '大屏中的校名、人数和比例为示意，不代表实际客户规模或实时运行情况。']) }
    return data.galleries[state.gallery]
  }
  function updateGallery() {
    const gallery = galleryData(), slide = gallery.slides[state.index]
    $('#gallery-dialog').classList.toggle('mobile-gallery', Boolean(gallery.mobile))
    text('gallery-title', gallery.title); text('gallery-slide-title', slide[1]); text('gallery-copy', slide[2]); text('gallery-count', `${state.index + 1} / ${gallery.slides.length}`)
    picture($('#gallery-image'), `assets/${gallery.board ? 'boards' : 'screens'}/${slide[0]}.webp`, slide[1] + ' · 精选界面、示例数据')
    const area = $('#gallery-image-area')
    area.classList.remove('zoomed'); area.scrollTo(0, 0)
    $('#gallery-fit').setAttribute('aria-pressed', 'false'); text('gallery-fit', '原尺寸')
    $('#gallery-picks').replaceChildren(...gallery.slides.map((item, index) => {
      const button = doc.createElement('button'), number = doc.createElement('b'), label = doc.createElement('span')
      number.textContent = String(index + 1).padStart(2, '0'); label.textContent = item[1]
      button.append(number, label); button.dataset.slideIndex = String(index)
      button.setAttribute('aria-current', String(index === state.index))
      return button
    }))
    $('#gallery-roles').hidden = !gallery.mobile
    $$('[data-gallery-role]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.galleryRole === state.gallery)))
    raf(() => {
      const list = $('#gallery-picks'), active = list.querySelector('[aria-current=true]')
      if (!active) return
      const a = active.getBoundingClientRect(), b = list.getBoundingClientRect()
      if (a.bottom > b.bottom) list.scrollTop += a.bottom - b.bottom
      if (a.top < b.top) list.scrollTop -= b.top - a.top
      if (a.right > b.right) list.scrollLeft += a.right - b.right
      if (a.left < b.left) list.scrollLeft -= b.left - a.left
    })
    $('#gallery-prev').disabled = gallery.slides.length < 2; $('#gallery-next').disabled = gallery.slides.length < 2
    text('gallery-note', gallery.board ? '大屏为示例展示，不作为学校实时数据、客户规模或指标验收结论。' : '精选产品界面 · 示例数据。完整流程、实际页面与交付范围在产品讲解中确认。')
  }
  function gallery(key, index = 0, trigger = doc.activeElement) {
    if (!data.galleries[key] && key !== 'boards') return
    state.gallery = key
    const size = key === 'boards' ? 4 : data.galleries[key].slides.length
    state.index = Math.max(0, Math.min(Math.trunc(Number(index) || 0), size - 1))
    pauseTour(); updateGallery(); modal('gallery-dialog', trigger)
  }
  function stepGallery(delta) {
    const size = galleryData().slides.length
    state.index = (state.index + delta + size) % size
    updateGallery()
  }
  function consult(interest, trigger = doc.activeElement) {
    pauseTour()
    const label = Object.values(INTERESTS).includes(interest) ? interest : '整体解决方案'
    text('consult-interest', label)
    $('#official-contact').href = consultBase + consultationPath(label)
    modal('consult-dialog', trigger)
  }
  function galleryConsult() { consult(state.gallery === 'boards' ? data.products[galleryData().slides[state.index][0]].interest : galleryData().interest) }
  const sceneKeys = ['overview', 'affairs', 'academic', 'internship', 'graduation']
  function scene(key, user = false) {
    if (!data.sceneNames[key]) return
    if (user) { pauseTour(); state.elapsed = sceneKeys.indexOf(key) * 6400; progress() }
    state.scene = key
    selected('#tour-tabs button', key, 'data-scene')
    picture($('#tour-image'), `assets/scenes/${key}.webp`, data.sceneNames[key] + ' · AI品牌场景，非校园实景')
    text('tour-headline', data.sceneWords[key][0]); text('tour-copy', data.sceneWords[key][1]); model?.setScene(key)
  }
  function progress() {
    const value = Math.min(100, state.elapsed / 320)
    $('#tour-progress').style.width = value + '%'
    $('.tour-progress').setAttribute('aria-valuenow', String(Math.round(value)))
    text('tour-time', state.elapsed ? `${Math.round(state.elapsed / 1000)} / 32 秒` : '32 秒')
  }
  function pauseTour() {
    state.playing = false
    win.cancelAnimationFrame(tickId)
    audio?.pause()
    text('tour-play', state.elapsed >= 32000 ? '↺ 重新播放' : state.elapsed > 0 ? '▶ 继续导览' : '▶ 播放导览')
    model?.setMotion(false)
  }
  function tick(now) {
    if (disposed || !state.playing) return
    state.elapsed = Math.min(32000, state.elapsed + Math.max(0, now - lastTick)); lastTick = now
    const key = sceneKeys[Math.min(4, Math.floor(state.elapsed / 6400))]
    if (state.scene !== key) scene(key)
    progress()
    if (state.elapsed >= 32000) { pauseTour(); return }
    tickId = win.requestAnimationFrame(tick)
  }
  function playTour() {
    if (state.playing) { pauseTour(); return }
    if (state.elapsed >= 32000) state.elapsed = 0
    state.playing = true; lastTick = win.performance.now(); text('tour-play', 'Ⅱ 暂停导览')
    if (!reduced.matches) model?.setMotion(true)
    tickId = win.requestAnimationFrame(tick)
    if (audio?.enabled) void audio.playAt(() => state.elapsed / 1000)
  }
  function openTour() {
    pauseTour(); state.elapsed = 0; scene('overview'); progress(); modal('tour-dialog')
    model?.setEnabled(state.model)
  }
  function getAudio() {
    if (!audio) audio = createSound({ onStatus: status => {
      if (disposed) return
      $('#tour-sound').setAttribute('aria-pressed', String(Boolean(audio?.enabled)))
      text('tour-sound', audio?.enabled ? '♫ 配乐已开启' : '♫ 开启配乐')
      text('tour-audio-status', status === 'loading' ? '正在准备配乐…' : status === 'playing' ? 'Discovery · 正在播放' : status === 'unavailable' ? '配乐暂不可用，仍可静音导览。' : '配乐仅在导览中播放')
    } })
    return audio
  }
  async function toggleSound() {
    const sound = getAudio()
    sound.setEnabled(!sound.enabled)
    $('#tour-sound').setAttribute('aria-pressed', String(sound.enabled))
    text('tour-sound', sound.enabled ? '♫ 配乐已开启' : '♫ 开启配乐')
    if (!sound.enabled) return
    if (state.playing) { void sound.playAt(() => state.elapsed / 1000); return }
    try { await sound.unlock() } catch { if (!disposed) { sound.setEnabled(false); $('#tour-sound').setAttribute('aria-pressed', 'false'); text('tour-sound', '♫ 开启配乐'); note('配乐暂不可用，仍可静音导览。') } }
  }
  async function toggleModel() {
    state.model = !state.model
    $('#tour-model').hidden = !state.model; $('#tour-image').hidden = state.model
    $('#model-toggle').setAttribute('aria-pressed', String(state.model)); text('model-toggle', state.model ? '彩色场景' : '空间示意')
    if (model) { model.setEnabled(state.model); return }
    if (!state.model) return
    try {
      if (!modelPending) modelPending = loadModel()
      const { CampusScene } = await modelPending
      if (disposed || model) return
      model = new CampusScene($('#tour-canvas'), { dark: true, hotspots: $('#tour-hotspots'), enabled: state.model && $('#tour-dialog').open })
      model.setScene(state.scene); model.setMotion(state.playing && !reduced.matches)
    } catch {
      modelPending = null
      if (disposed) return
      state.model = false; $('#tour-model').hidden = true; $('#tour-image').hidden = false
      $('#model-toggle').setAttribute('aria-pressed', 'false'); text('model-toggle', '空间示意')
      note('空间示意未能显示，仍可查看彩色场景。')
    }
  }
  listen(root, 'click', event => {
    const target = event.target.closest?.('button,a')
    if (!target || !root.contains(target)) return
    if (target.hasAttribute('data-close')) { closeDialog(target.closest('dialog')); return }
    if (target.hasAttribute('data-consult')) { consult(target.dataset.consult, target); return }
    if (target.hasAttribute('data-gallery')) { gallery(target.dataset.gallery, 0, target); return }
    if (target.hasAttribute('data-tour')) { openTour(); return }
    if (target.hasAttribute('data-login')) { modal('login-dialog'); return }
    if (target.hasAttribute('data-info')) { modal('info-dialog'); return }
    if (target.id === 'official-contact' && navigate && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); pauseTour(); navigate(target.getAttribute('href'))
    }
  })
  tabs('.product-tabs', 'data-product', product); tabs('.hr-picks', 'data-hr', hr); tabs('.mobile-role', 'data-mobile', mobile); tabs('.board-tabs', 'data-board', board); tabs('#tour-tabs', 'data-scene', key => scene(key, true))
  const actions = {
    'product-gallery-link': () => gallery(data.products[state.product].gallery),
    'product-consult': () => consult(data.products[state.product].interest),
    'product-preview': () => { const p = data.products[state.product]; gallery(p.gallery, Math.max(0, data.galleries[p.gallery].slides.findIndex(s => p.image.endsWith('/' + s[0] + '.webp')))) },
    'hr-preview': () => gallery('hr', state.hr), 'mobile-gallery': () => gallery(state.mobile), 'phone-preview': () => gallery(state.mobile),
    'board-open': () => gallery('boards', boardKeys.indexOf(state.board)), 'board-consult': () => consult(data.products[state.board].interest),
    'gallery-prev': () => stepGallery(-1), 'gallery-next': () => stepGallery(1),
    'gallery-consult': galleryConsult, 'gallery-consult-short': galleryConsult,
    'gallery-fit': () => { const zoom = $('#gallery-image-area').classList.toggle('zoomed'); $('#gallery-fit').setAttribute('aria-pressed', String(zoom)); text('gallery-fit', zoom ? '适应窗口' : '原尺寸') },
    'tour-play': playTour, 'tour-sound': toggleSound, 'model-toggle': toggleModel,
    'menu-toggle': () => { const open = $('#mobile-menu').hidden; $('#mobile-menu').hidden = !open; $('#menu-toggle').setAttribute('aria-expanded', String(open)) }
  }
  Object.entries(actions).forEach(([id, action]) => listen($('#' + id), 'click', action))
  listen($('#gallery-picks'), 'click', event => {
    const button = event.target.closest('[data-slide-index]')
    if (!button) return
    state.index = Number(button.dataset.slideIndex); updateGallery()
  })
  $$('[data-gallery-role]').forEach(button => listen(button, 'click', () => { state.gallery = button.dataset.galleryRole; state.index = 0; updateGallery() }))
  listen($('#gallery-dialog'), 'keydown', event => {
    if (event.defaultPrevented || event.target.closest('[role=tablist]') || $('#gallery-image-area').classList.contains('zoomed')) return
    if (['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); stepGallery(event.key === 'ArrowRight' ? 1 : -1) }
  })
  let swipe = null
  listen($('#gallery-image-area'), 'touchstart', event => { swipe = event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null }, { passive: true })
  listen($('#gallery-image-area'), 'touchcancel', () => { swipe = null }, { passive: true })
  listen($('#gallery-image-area'), 'touchend', event => {
    const start = swipe; swipe = null
    if (!start || event.changedTouches.length !== 1 || $('#gallery-image-area').classList.contains('zoomed')) return
    const dx = event.changedTouches[0].clientX - start.x, dy = event.changedTouches[0].clientY - start.y
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) stepGallery(dx < 0 ? 1 : -1)
  }, { passive: true })
  listen($('#copy-phone'), 'click', async () => {
    try {
      await win.navigator.clipboard.writeText(contact?.tel || data.contact.tel)
      if (!disposed) note('咨询号码已复制')
    } catch {
      if (disposed) return
      const range = doc.createRange(); range.selectNodeContents($('.consult-phone>a'))
      const selection = win.getSelection(); selection.removeAllRanges(); selection.addRange(range)
      note('请复制已选中的咨询号码')
    }
  })
  listen($('#tour-volume'), 'input', event => getAudio().setVolume(Number(event.target.value) / 100))
  listen($('#tour-canvas'), 'campusselect', event => scene(event.detail, true))
  listen($('#tour-dialog'), 'cancel', () => { pauseTour(); audio?.setEnabled(false) })
  listen($('#tour-dialog'), 'close', () => { pauseTour(); model?.setEnabled(false); audio?.setEnabled(false); $('#tour-sound').setAttribute('aria-pressed', 'false'); text('tour-sound', '♫ 开启配乐') })
  listen(doc, 'visibilitychange', () => { if (doc.hidden) { pauseTour(); model?.setEnabled(false) } else model?.setEnabled(state.model && $('#tour-dialog').open) })
  listen(win, 'pagehide', pauseTour)
  $$('img[data-asset]').forEach(node => picture(node, node.dataset.asset, node.alt))
  $$('a[data-entry]').forEach(node => { const value = links[node.dataset.entry]; if (value) node.href = value; else node.hidden = true })
  if (contact) {
    $$('[data-phone-text]').forEach(node => { node.textContent = contact.phone })
    $$('a[data-phone-link]').forEach(node => { node.href = contact.phoneHref })
  }
  $$('#mobile-menu a,#mobile-menu button').forEach(node => listen(node, 'click', () => { $('#mobile-menu').hidden = true; $('#menu-toggle').setAttribute('aria-expanded', 'false') }))
  function processHash(hash = win.location.hash) {
    if (hash === '#login') { modal('login-dialog'); return }
    const aliases = { '#products':'#students', '#lifecycle':'#solutions', '#platform':'#solutions', '#faq':'#faq' }
    if (aliases[hash]) $(aliases[hash])?.scrollIntoView({ behavior: 'auto' })
  }
  listen(win, 'hashchange', () => processHash())
  product('academic'); hr(0); mobile('teacher'); board('academic'); processHash()
  return Object.freeze({
    openGallery: gallery, openTour, openConsult: consult, navigateHash: processHash, getState: () => ({ ...state, soundEnabled: Boolean(audio?.enabled) }),
    destroy() {
      if (disposed) return
      pauseTour(); disposed = true
      win.clearTimeout(toastTimer)
      frames.forEach(id => win.cancelAnimationFrame(id)); frames.clear()
      model?.destroy(); audio?.destroy()
      cleanup.splice(0).reverse().forEach(remove => remove())
      $$('dialog[open]').forEach(dialog => dialog.close())
      releaseScroll()
    }
  })
}
