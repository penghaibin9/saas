// 历史导入路径兼容层：所有能力已迁移到统一 File SDK。
export {
  FILE_STATUS_TEXT,
  chooseSingleFile,
  normalizeFile,
  openBusinessFile,
  fileSdk
} from './fileSdk'

import { fileSdk } from './fileSdk'

export function uploadBusinessFile(file, options = {}) {
  return fileSdk.upload(file, options)
}

export default fileSdk
