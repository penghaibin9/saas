/** Licensed local music; loaded only after explicit user action. */
export const TOUR_DURATION = 32
export const SCORE = Object.freeze({ title: 'Discovery · 校园导览', duration: 32, author: 'Scott Buckley', license: 'CC BY 4.0', source: 'https://www.scottbuckley.com.au/library/discovery/' })
function deadline(promise, ms) {
  let timer
  return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('配乐准备超时，请继续静音浏览。')), ms) })]).finally(() => clearTimeout(timer))
}
export async function renderSoundtrack(context, signal) {
  const response = await fetch('/official-site/news-media/discovery-campus-32.mp3', { signal, credentials: 'omit' })
  if (!response.ok) throw new Error('配乐暂不可用，请继续静音导览。')
  const buffer = await context.decodeAudioData(await response.arrayBuffer())
  if (buffer.duration < 31.9 || buffer.duration > 32.2) throw new Error('配乐长度不符')
  return buffer
}

export class TourSoundtrack {
  constructor({ onStatus = () => {}, Context, OfflineContext } = {}) {
    this.Context = Context || globalThis.AudioContext || globalThis.webkitAudioContext
    this.OfflineContext = OfflineContext
    this.loadAbort = null
    this.onStatus = onStatus
    this.context = null
    this.buffer = null
    this.pending = null
    this.source = null
    this.master = null
    this.enabled = false
    this.disposed = false
    this.generation = 0
    this.volume = 0.32
  }
  async unlock() {
    if (this.disposed || !this.Context) throw new Error('当前浏览器暂不支持配乐，可继续静音浏览。')
    if (!this.context) {
      this.context = new this.Context()
      this.master = this.context.createGain()
      this.master.gain.value = this.volume
      this.master.connect(this.context.destination)
    }
    // Invoke in the click stack. Never rely on automatic playback permission.
    if (this.context.state === 'suspended') await deadline(this.context.resume(), 2500)
    if (!this.pending) {
      this.loadAbort = new AbortController()
      this.pending = renderSoundtrack(this.context, this.loadAbort.signal).then(buffer => (this.buffer = buffer)).catch(error => {
        this.pending = null
        throw error
      })
    }
    return deadline(this.pending, 8000)
  }
  setEnabled(enabled) {
    this.enabled = Boolean(enabled)
    if (!this.enabled) this.pause()
  }
  setVolume(value) {
    this.volume = Math.max(0, Math.min(0.6, Number(value) || 0))
    if (this.master && !this.disposed) this.master.gain.setTargetAtTime(this.volume, this.context.currentTime, 0.04)
  }
  async playAt(readOffset) {
    if (!this.enabled || this.disposed) return false
    this.pause()
    const generation = this.generation
    this.onStatus('loading')
    try {
      const buffer = await this.unlock()
      if (this.disposed || !this.enabled || this.generation !== generation) return false
      const offset = Math.max(0, Math.min(TOUR_DURATION, typeof readOffset === 'function' ? readOffset() : Number(readOffset) || 0))
      if (offset >= TOUR_DURATION) return false
      const source = this.context.createBufferSource()
      source.buffer = buffer
      const fade = this.context.createGain()
      fade.gain.setValueAtTime(0, this.context.currentTime)
      fade.gain.linearRampToValueAtTime(1, this.context.currentTime + 0.12)
      source.connect(fade).connect(this.master)
      this.source = source
      source.onended = () => { source.disconnect(); fade.disconnect(); if (this.source === source) this.source = null }
      source.start(0, offset)
      this.onStatus('playing')
      return true
    } catch (error) {
      if (!this.disposed && generation === this.generation) {
        this.enabled = false
        this.onStatus('unavailable', error)
      }
      return false
    }
  }
  pause() {
    this.generation += 1
    const source = this.source
    this.source = null
    if (source) { try { source.stop() } catch { /* Already ended. */ } }
    if (!this.disposed) this.onStatus('paused')
  }
  destroy() {
    this.pause()
    this.enabled = false
    this.disposed = true
    if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {})
    this.master?.disconnect()
    this.loadAbort?.abort()
    this.buffer = null
  }
}
