import { ENV } from '@/config/env'
import { getToken, realRequest } from './request'

/** 选择单个文件；微信小程序优先 chooseMessageFile，H5/App 回退 chooseImage。 */
export function chooseSingleFile({ count = 1 } = {}) {
  return new Promise((resolve, reject) => {
    if (typeof uni.chooseMessageFile === 'function') {
      uni.chooseMessageFile({
        count,
        type: 'file',
        success: (res) => resolve((res.tempFiles || [])[0] || null),
        fail: reject
      })
      return
    }
    uni.chooseImage({
      count,
      sizeType: ['compressed', 'original'],
      success: (res) => resolve({
        path: (res.tempFilePaths || [])[0],
        name: 'attachment.jpg',
        size: (res.tempFiles || [])[0]?.size || 0
      }),
      fail: reject
    })
  })
}

/** 上传到正式文件中心，返回 {fileId,fileName,size,mimeType,hash}。 */
export function uploadBusinessFile(file, { bizType = 'ATTACHMENT', bizId = '' } = {}) {
  const filePath = file?.path || file?.tempFilePath
  if (!filePath) return Promise.reject({ code: 'FILE_REQUIRED', biz: true, message: '请选择要上传的文件' })
  const token = getToken()
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: ENV.apiBaseUrl + ENV.apiPrefix + '/files',
      filePath,
      name: 'file',
      header: token ? { Authorization: 'Bearer ' + token } : {},
      formData: { bizType, bizId: String(bizId || '') },
      timeout: ENV.requestTimeout,
      success: (res) => {
        let body
        try { body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data } catch (e) {
          reject({ code: 'BAD_RESPONSE', message: '文件上传响应解析失败' }); return
        }
        if (!body || body.code !== 0) {
          reject({ code: body?.code || 'UPLOAD_FAILED', biz: true, message: body?.message || '文件上传失败' }); return
        }
        resolve(body.data)
      },
      fail: (err) => reject({ code: 'NETWORK', message: err?.errMsg || '文件上传失败' })
    })
  })
}

function absoluteUrl(path) {
  const value = String(path || '')
  if (/^https?:\/\//i.test(value)) return value
  const base = String(ENV.apiBaseUrl || '').replace(/\/$/, '')
  return `${base}${value.startsWith('/') ? '' : '/'}${value}`
}

function fileExtension(fileName) {
  const name = String(fileName || '').toLowerCase()
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index + 1) : ''
}

/**
 * 获取对象级授权下载地址并在小程序内打开。
 * 图片走 previewImage，文档走 openDocument；不向页面暴露内部存储路径。
 */
export async function openBusinessFile(fileId) {
  const id = String(fileId || '').trim()
  if (!id) throw { code: 'FILE_REQUIRED', biz: true, message: '附件不存在' }
  const meta = await realRequest(`/files/${encodeURIComponent(id)}/url`)
  const token = getToken()
  return new Promise((resolve, reject) => {
    uni.downloadFile({
      url: absoluteUrl(meta?.url),
      header: token ? { Authorization: 'Bearer ' + token } : {},
      timeout: ENV.requestTimeout,
      success: (res) => {
        if (Number(res.statusCode || 0) !== 200 || !res.tempFilePath) {
          reject({ code: 'DOWNLOAD_FAILED', biz: true, message: '附件下载失败或已失效' })
          return
        }
        const ext = fileExtension(meta?.fileName)
        if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
          uni.previewImage({
            urls: [res.tempFilePath],
            current: res.tempFilePath,
            success: () => resolve(meta),
            fail: (error) => reject({ code: 'PREVIEW_FAILED', message: error?.errMsg || '图片预览失败' })
          })
          return
        }
        uni.openDocument({
          filePath: res.tempFilePath,
          fileType: ext || undefined,
          showMenu: true,
          success: () => resolve(meta),
          fail: (error) => reject({ code: 'PREVIEW_FAILED', message: error?.errMsg || '当前文件无法预览，请在管理端下载查看' })
        })
      },
      fail: (error) => reject({ code: 'NETWORK', message: error?.errMsg || '附件下载失败' })
    })
  })
}
