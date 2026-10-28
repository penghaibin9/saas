import { attachmentKind, reportFileState } from './weeklyReportPresentation.mjs'

export function releasePreview(url) {
  if (String(url || '').startsWith('blob:') && typeof URL !== 'undefined') URL.revokeObjectURL(url)
}

export async function loadReportMedia(file, sdk, isCurrent = () => true) {
  const id = String(file?.fileId || '')
  const meta = reportFileState(await sdk.metadata(id))
  if (String(meta.fileId) !== id || !meta.readyForBusiness || !meta.allowedActions?.includes('download')) {
    throw { biz: true, code: 404001, message: '附件不存在、无权访问或尚未通过安全扫描' }
  }
  if (!isCurrent()) return null
  const downloaded = await sdk.download(id)
  if (!isCurrent()) { releasePreview(downloaded?.tempFilePath); return null }
  return { file: meta, kind: attachmentKind(meta), url: downloaded.tempFilePath }
}
