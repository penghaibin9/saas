// 从项目根目录运行；仅调用页面方法和内存替身，不访问网络或数据库。
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
const { page, deferred } = await import(pathToFileURL(resolve('frontend/tests/academic-pc-parallel-b-harness.mjs')))
const constants = await import(pathToFileURL(resolve('frontend/src/modules/academicAffairs/constants/course-program.js')))
const pendingA = deferred()
const { state } = page('AaCourseConsoleView', { ...constants, academicAffairsApi: {
  getCourseMaterials: async id => id === 'A' ? pendingA.promise : { code: 0, data: { list: [{ title: 'B材料' }] } }
} }, { ctx: {} })
state.materialPanel = { course: { courseId: 'A' }, lockedType: '', items: [] }
const requestA = state.loadMaterials()
state.materialPanel = { course: { courseId: 'B' }, lockedType: '', items: [] }
await state.loadMaterials()
pendingA.resolve({ code: 0, data: { list: [{ title: 'A材料' }] } })
await requestA
const materialResult = { selectedCourse: state.materialPanel.course.courseId, displayedMaterial: state.materialPanel.items[0].title }
const pendingSave = deferred()
let requests = 0
const second = page('AaCourseConsoleView', constants, { ctx: {} }).state
second.dimForm = { row: { courseId: 'C' }, dim: 'category', value: 'MAJOR_CORE' }
second.putCourse = async () => { requests++; return pendingSave.promise }
const firstSave = second.submitDimForm()
const secondSave = second.submitDimForm()
pendingSave.resolve({ code: 409, message: '内存替身拒绝写入' })
await Promise.all([firstSave, secondSave])
console.log(JSON.stringify({ evidence: 'isolated-page-methods', materialResult, consecutiveSaveRequests: requests, realNetworkOrDatabaseWrites: false }, null, 2))
