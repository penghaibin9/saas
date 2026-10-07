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
const requiredCountKeys=['high','critical','total']
const explicitCounts=validCounts&&requiredCountKeys.every(key=>Object.prototype.hasOwnProperty.call(counts,key))
const numericCounts=explicitCounts&&requiredCountKeys.every(key=>Number.isInteger(Number(counts[key]))&&Number(counts[key])>=0)

let countsConsistent=false
if(validVulnerabilities&&numericCounts){
  const rows=Object.values(vulnerabilities)
  const computedHigh=rows.filter(value=>String(value?.severity||'').toLowerCase()==='high').length
  const computedCritical=rows.filter(value=>String(value?.severity||'').toLowerCase()==='critical').length
  countsConsistent=Number(counts.high)===computedHigh&&Number(counts.critical)===computedCritical&&Number(counts.total)===rows.length
}

if(!validVersion||!validVulnerabilities||!validCounts||!numericCounts||!countsConsistent){
  console.error('enterprise-portal production audit report is incomplete or inconsistent; refusing to treat missing audit truth as zero vulnerabilities')
  process.exit(1)
}

console.log(`enterprise-portal audit report validated: high=${Number(counts.high)}, critical=${Number(counts.critical)}, total=${Number(counts.total)}`)
