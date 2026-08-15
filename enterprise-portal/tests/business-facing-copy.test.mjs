import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../src')
const forbidden=[
  /\bA01\b/,
  /Authority/,
  /canonical/i,
  /facade/i,
  /\bRECRUITMENT\b/,
  /\bINTERNSHIP_COLLAB\b/,
  /\bGrant\b/,
  /InternshipApplication/,
  /ApplicationMaterialSnapshot/,
  /InternshipRecord/,
  /\bSnapshot\b/,
  /\bDecision\b/,
  /companyId/,
  /memberId/,
  /fail-closed/i,
  /\bmock\b/i,
  /ENTERPRISE_ONLINE/,
  /rights gate/i,
  /allowed=true/,
  /服务端/,
  /后端/,
  /前端/,
  /状态机/,
  /投影/,
  /真值/,
]

function vueFiles(dir){
  const result=[]
  for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
    const full=path.join(dir,entry.name)
    if(entry.isDirectory())result.push(...vueFiles(full))
    else if(entry.isFile()&&entry.name.endsWith('.vue'))result.push(full)
  }
  return result
}

function templateOf(source){return source.match(/<template>([\s\S]*?)<\/template>/)?.[1]||''}

test('enterprise visible templates never leak engineering or authority implementation jargon',()=>{
  for(const file of vueFiles(root)){
    const source=fs.readFileSync(file,'utf8')
    const template=templateOf(source)
    for(const pattern of forbidden){
      assert.doesNotMatch(template,pattern,`${path.relative(root,file)} leaks ${pattern}`)
    }
  }
})
