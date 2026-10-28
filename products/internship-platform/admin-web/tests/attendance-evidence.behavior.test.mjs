import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { shiftTypeText, shiftTypeValue } from '../src/modules/internship/constants/position.constants.js'

test('定位坐标类型来自原记录，不把不兼容坐标误说成围栏边界',()=>{
  const source=fs.readFileSync(new URL('../src/modules/internship/views/AttendanceExceptionDetailView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const names=['ModulePageShell','LoadingState','ErrorState','EmptyState','AppStatusTag','AppAuditTrail','AppInlineAlert','AppButton','ReviewQueueBar','ActionReceipt','formatDateTime']
  const component=new Function(...names,script)(...names.map(()=>({})))
  const vm={evidence:{available:true,checkinLat:28.6,checkinLng:112.3,coordinateSystem:'WGS84',fenceCoordinateSystem:'GCJ02',result:'LOCATION_UNCERTAIN'},coordinateLabel:component.methods.coordinateLabel}
  assert.match(component.computed.coordinateText.call(vm),/卫星定位坐标/)
  assert.match(component.computed.evidenceConclusion.call(vm),/坐标类型不同/)
  assert.doesNotMatch(component.computed.evidenceConclusion.call(vm),/围栏边界/)
  vm.evidence.coordinateSystem=null
  assert.match(component.computed.evidenceConclusion.call(vm),/尚未完整记录/)
})

test('岗位班次中文展示仍保持原机器值，自定义班次不被改写',()=>{
  for(const code of ['DAY','NIGHT','ROTATING','FLEXIBLE'])assert.equal(shiftTypeValue(shiftTypeText(code)),code)
  assert.equal(shiftTypeText('DAY'),'白班')
  assert.equal(shiftTypeValue('按项目灵活安排'),'按项目灵活安排')
})
