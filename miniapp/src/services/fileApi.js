import { ENV } from '@/config/env'
import { getToken } from './request'

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
