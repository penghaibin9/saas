import fs from 'node:fs'

const reportPath=process.argv[2]
if(!reportPath){
  console.error('usage: node scripts/check-production-audit-report.mjs <audit.json>')
  process.exit(2)
}

let report
try{
  report=JSON.parse(fs.readFileSync(reportPath,'utf8'))
}catch(error){
  console.error(`enterprise-portal production audit report is unreadable: ${error.message}`)
  process.exit(1)
}

const vulnerabilities=report?.vulnerabilities
const counts=report?.metadata?.vulnerabilities
const validVersion=report?.auditReportVersion===2
const validVulnerabilities=vulnerabilities&&typeof vulnerabilities==='object'&&!Array.isArray(vulnerabilities)
const validCounts=counts&&typeof counts==='object'&&!Array.isArray(counts)
const numericCounts=validCounts&&['high','critical','total'].every(key=>Number.isFinite(Number(counts[key]??0)))

if(!validVersion||!validVulnerabilities||!validCounts||!numericCounts){
  console.error('enterprise-portal production audit report is incomplete; refusing to treat missing audit truth as zero vulnerabilities')
  process.exit(1)
}

console.log(`enterprise-portal audit report validated: high=${Number(counts.high||0)}, critical=${Number(counts.critical||0)}, total=${Number(counts.total||0)}`)
