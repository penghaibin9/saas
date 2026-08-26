import { studentApi as baseStudentApi } from './studentApiBase'
import { latestRequest } from './latestRequest'

export const studentApi = {
  ...baseStudentApi,
  // 材料库原本直接 realRequest，单独纳入 latest-request-wins，避免旧 FileVersion/版本号覆盖提交后的新状态。
  getGraduationMaterialLibrary: () =>
    latestRequest('student:graduation:materials', () => baseStudentApi.getGraduationMaterialLibrary())
}

export default studentApi
