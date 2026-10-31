import * as config from '../config/portalConfig.js'
export const PORTAL_LINKS = Object.freeze({ teacher: config.TEACHER_LOGIN_URL, student: config.STUDENT_LOGIN_URL,
  enterprise: config.ENTERPRISE_LOGIN_URL, humanResources: config.HR_LOGIN_URL,
  teacherH5: config.TEACHER_H5_LOGIN_URL, studentH5: config.STUDENT_H5_LOGIN_URL,
  teacherMiniQr: config.TEACHER_MINIPROGRAM_QR, studentMiniQr: config.STUDENT_MINIPROGRAM_QR,
  privacy: config.PRIVACY_URL, terms: config.TERMS_URL })
const escape = text => String(text).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')
// Only trusted repository markup is transformed, never API or user HTML.
export function portalMarkup(markup, links = PORTAL_LINKS) {
  return markup.replace(/<a\b([^>]*\bdata-entry="([^"]+)"[^>]*)>([\s\S]*?)<\/a>/g, (_, attributes, key, body) => {
    if (!(key in links)) throw new Error('Unknown portal entry: ' + key)
    const url = links[key]
    attributes = attributes.replace(/\s(?:href|target|aria-disabled)="[^"]*"/g, '').replace(/\sclass="is-pending"/g, '')
    if (!url) return `<a${attributes} aria-disabled="true" class="is-pending">${body}</a>`
    const label = attributes.match(/data-entry-ready-label="([^"]+)"/)?.[1]
    if (label) body = body.replace(/(<em\b[^>]*data-entry-action[^>]*>)[\s\S]*?(<\/em>)/, '$1' + label + '$2')
    return `<a${attributes} href="${escape(url)}">${body}</a>`
  })
}
