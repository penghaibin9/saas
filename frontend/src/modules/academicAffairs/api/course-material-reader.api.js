import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import fileSdk from '@/services/file/fileSdk'

function abortError() {
  const error = new DOMException('预览已切换', 'AbortError')
  error.code = 'PREVIEW_ABORTED'
  return error
}

function raceAbort(promise, signal) {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(abortError())
  return new Promise((resolve, reject) => {
    const onAbort = () => reject(abortError())
    signal.addEventListener('abort', onAbort, { once: true })
    Promise.resolve(promise).then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

function unavailableMaterial(material, message = '附件当前不可预览') {
  return {
    ...material,
    fileId: String(material.fileId || ''),
    fileName: material.fileName || material.title || '课程材料',
    scanStatus: 'ERROR',
    statusText: message,
    readyForBusiness: false,
    allowedActions: [],
    canPreview: false,
    canDownload: false
  }
}

/**
 * 教务课程材料 Reader adapter。
 * 课程业务页只负责“读哪份材料”；文件元数据、扫描态、allowedActions 与字节授权仍由 File Center 决定。
 */
export const courseMaterialReaderApi = {
  async list(courseId) {
    const res = await academicAffairsApi.getCourseMaterials(courseId)
    if (res.code !== 0) throw Object.assign(new Error(res.message || '课程材料加载失败'), { code: res.code })

    const materials = (res.data?.list || []).filter((item) => item.fileId)
    return Promise.all(materials.map(async (material) => {
      try {
        const meta = await fileSdk.metadata(material.fileId)
        return {
          ...meta,
          materialId: material.id,
          materialType: material.materialType,
          materialTypeLabel: material.materialTypeLabel,
          title: material.title,
          remark: material.remark,
          uploader: material.uploader,
          createdAt: material.createdAt,
          fileId: String(material.fileId),
          fileName: material.fileName || meta.fileName || material.title || '课程材料'
        }
      } catch (error) {
        return unavailableMaterial(material, error?.message || '附件当前不可预览')
      }
    }))
  },

  createPreviewProvider() {
    return {
      async fetchBytes(descriptor, { signal } = {}) {
        if (signal?.aborted) throw abortError()
        return raceAbort(fileSdk.blob(descriptor.fileId), signal)
      },
      dispose() {}
    }
  }
}

export default courseMaterialReaderApi
