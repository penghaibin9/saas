/**
 * 一路相连 — a newly composed 32-second ambient cue for the campus tour.
 * All tones are synthesized from this score. No third-party recording/samples.
 * Silence is the default; AudioContext is created only after an explicit gesture.
 */
export const TOUR_DURATION = 32
export const SCORE = Object.freeze({
  title: '一路相连 · 校园导览', bpm: 75, duration: TOUR_DURATION,
  chords: [[48,55,59,64,74],[43,50,57,59,64],[45,52,55,60,71],[41,48,57,64,67],[48,55,60,64,74]],
  melody: [[64,67,71,74,76,74,71,67],[59,62,67,69,71,69,67,62],[64,67,69,72,71,69,67,64],[65,69,72,76,74,72,69,67],[64,67,72,71,67,64,62,60]]
})
const frequency = midi => 440 * 2 ** ((midi - 69) / 12)
function deadline(promise, ms) {
  let timer
  return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('配乐准备超时，请继续静音浏览。')), ms) })]).finally(() => clearTimeout(timer))
}

export async function renderSoundtrack(OfflineContext = globalThis.OfflineAudioContext || globalThis.webkitOfflineAudioContext) {
  if (!OfflineContext) throw new Error('当前浏览器不支持配乐合成，请继续静音导览。')
  const sampleRate = 32000
  const offline = new OfflineContext(2, sampleRate * TOUR_DURATION, sampleRate)
  const output = offline.createGain()
  output.gain.setValueAtTime(0, 0)
  output.gain.linearRampToValueAtTime(0.65, 1.25)
  output.gain.setValueAtTime(0.65, 29.2)
  output.gain.linearRampToValueAtTime(0, 31.95)
  const compressor = offline.createDynamicsCompressor()
  compressor.threshold.value = -15
  compressor.knee.value = 12
  compressor.ratio.value = 3
  compressor.attack.value = 0.02
  compressor.release.value = 0.25
  output.connect(compressor).connect(offline.destination)
  const delay = offline.createDelay(1)
  const wet = offline.createGain()
  delay.delayTime.value = 0.36
  wet.gain.value = 0.17
  delay.connect(wet).connect(output)

  function tone(midi, start, duration, level, kind, pan) {
    const gain = offline.createGain()
    const panner = offline.createStereoPanner()
    panner.pan.value = pan
    const attack = kind === 'pad' ? 0.7 : 0.012
    const end = Math.min(31.95, start + duration)
    if (end <= start + attack) return
    gain.gain.setValueAtTime(0, start)
    gain.gain.linearRampToValueAtTime(level, start + attack)
    if (kind === 'pad') {
      gain.gain.setValueAtTime(level * 0.75, Math.max(start + attack, end - 1.1))
      gain.gain.linearRampToValueAtTime(0, end)
    } else {
      gain.gain.exponentialRampToValueAtTime(0.0001, end)
    }
    gain.connect(panner).connect(output)
    if (kind !== 'bass') panner.connect(delay)
    const partials = kind === 'pad' ? [[1,1],[2,0.11]] : kind === 'bass' ? [[1,1]] : [[1,1],[2,0.24],[3,0.055]]
    for (const [harmonic, amplitude] of partials) {
      const oscillator = offline.createOscillator()
      const harmonicGain = offline.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.value = frequency(midi) * harmonic
      harmonicGain.gain.value = amplitude
      oscillator.connect(harmonicGain).connect(gain)
      oscillator.start(start)
      oscillator.stop(end)
    }
  }
  SCORE.chords.forEach((chord, chapter) => {
    const at = chapter * 6.4
    chord.forEach((note, i) => tone(note, at + i * 0.045, 7.0, 0.019, 'pad', (i - 2) * 0.3))
    tone(chord[0] - 12, at + 0.1, 3.15, 0.041, 'bass', 0)
    if (chapter !== 4) tone(chord[0] - 12, at + 3.3, 3.0, 0.027, 'bass', 0)
    SCORE.melody[chapter].forEach((note, beat) => {
      tone(note, at + beat * 0.8 + 0.15, beat === 7 ? 2.4 : 1.8, beat % 4 === 0 ? 0.095 : 0.068, 'piano', (beat % 3 - 1) * 0.25)
    })
  })
  const buffer = await offline.startRendering()
  let peak = 0
  for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
    const samples = buffer.getChannelData(channel)
    for (let i = 0; i < samples.length; i++) peak = Math.max(peak, Math.abs(samples[i]))
  }
  const gain = peak > 0 ? Math.min(8, 0.6 / peak) : 1
  for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
    const samples = buffer.getChannelData(channel)
    for (let i = 0; i < samples.length; i++) samples[i] *= gain
  }
  return buffer
}

export class TourSoundtrack {
  constructor({ onStatus = () => {}, Context, OfflineContext } = {}) {
    this.Context = Context || globalThis.AudioContext || globalThis.webkitAudioContext
    this.OfflineContext = OfflineContext
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
      this.pending = renderSoundtrack(this.OfflineContext).then(buffer => (this.buffer = buffer)).catch(error => {
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
    this.buffer = null
  }
}
