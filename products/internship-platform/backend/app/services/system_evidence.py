"""Read existing delivery-script receipts from a deployer-owned, per-school directory.

No web request supplies a path, runs a command, restores data, or promotes manual notes to evidence.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings


def read_receipts(tenant_id):
    if not settings.SYSTEM_EVIDENCE_DIR:
        return {'items':[], 'note':'尚未接入备份、恢复演练和迁移脚本回执目录'}
    base=Path(settings.SYSTEM_EVIDENCE_DIR).resolve()
    folder=(base/str(int(tenant_id))).resolve()
    if not folder.is_relative_to(base) or not folder.is_dir():
        return {'items':[], 'note':'当前学校尚无自动采集的脚本回执'}
    items=[]
    # ponytail: at most 100 small receipts; archive older receipts through the existing backup retention job.
    for path in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
        if path.is_symlink() or not path.resolve().is_relative_to(folder) or path.stat().st_size>1024*1024:
            continue
        receipt_kind={}
        try:
            content=path.read_bytes()
            value=json.loads(content)
            if not isinstance(value,dict): raise ValueError('回执必须是对象')
            if value.get('kind')=='EXTERNAL_SERVICE': receipt_kind={'kind':'INTEGRATION'}
            digest=hashlib.sha256(content).hexdigest()
            checksum=path.with_suffix(path.suffix+'.sha256')
            if not checksum.is_file() or checksum.is_symlink() or checksum.stat().st_size>1024:
                items.append({**receipt_kind,'title':path.name,'kindLabel':'脚本回执','statusLabel':'缺少校验文件，未验证'});continue
            if checksum.read_text(encoding='utf-8').split()[0].lower()!=digest:
                items.append({**receipt_kind,'title':path.name,'kindLabel':'脚本回执','statusLabel':'校验失败，禁止作为交付依据'});continue
            common={'title':path.name,'sha256':digest,'sourceCommit':str(value.get('sourceCommit') or ''),
                    'checkedAt':value.get('completedAtUtc') or value.get('createdAtUtc') or value.get('generatedAt')}
            if value.get('kind')=='EXTERNAL_SERVICE':
                # Only deployment-owned probe output, never school-entered delivery notes.
                if str(value.get('tenantId'))!=str(tenant_id): continue
                if value.get('service') not in ('MAP','ENTERPRISE') or value.get('outcome') not in ('PASSED','FAILED'):
                    raise ValueError('服务检测回执类型错误')
                checked=datetime.fromisoformat(str(value.get('completedAtUtc','')).replace('Z','+00:00'))
                if checked.tzinfo is None or checked > datetime.now(timezone.utc): raise ValueError('检测时间不合法')
                errors={'NOT_CONFIGURED':'服务尚未配置','TIMEOUT':'服务请求超时','CONNECTION_FAILED':'服务连接失败',
                    'AUTH_REJECTED':'服务凭据或访问权限被拒绝','INVALID_RESPONSE':'服务返回内容不符合预期'}
                passed=value['outcome']=='PASSED'
                if (passed and value.get('errorCode')) or (not passed and value.get('errorCode') not in errors):
                    raise ValueError('检测结果与失败原因不一致')
                items.append({**common,'kind':'INTEGRATION','service':value['service'],'passed':passed,
                    'checkedAt':checked.isoformat(),'kindLabel':'外部服务检测回执',
                    'statusLabel':'最近检测通过' if passed else '最近检测失败',
                    'failureReason':'' if passed else errors[value['errorCode']],
                    'detail':'实施检测回执已校验；仅证明该时刻的检测结果'})
            elif value.get('product')=='internship-standalone' and value.get('backupSetId'):
                valid=all(isinstance(value.get(k),dict) and isinstance(value[k].get('sha256'),str)
                    and re.fullmatch(r'[0-9a-fA-F]{64}',value[k]['sha256'])
                    and type(value[k].get('sizeBytes')) is int and value[k]['sizeBytes']>0 for k in ('database','files'))
                items.append({**common,'kind':'BACKUP','passed':bool(valid),'kindLabel':'备份脚本回执','statusLabel':'备份脚本已完成' if valid else '备份清单不完整',
                    'setId':str(value['backupSetId']),'detail':'回执校验通过；备份可恢复性以独立恢复演练为准'})
            elif value.get('gate')=='C09-RESTORE':
                counts=('tableCount','externalStorageObjects','localFileObjectsVerified','hashedFileObjectsVerified','restoreSeconds')
                passed=value.get('verdict')=='PASS' and all(type(value.get(k)) is int and value[k]>=0 for k in counts) \
                    and value['tableCount']>0 and value['externalStorageObjects']==0 \
                    and value['hashedFileObjectsVerified']<=value['localFileObjectsVerified']
                items.append({**common,'kind':'RESTORE','passed':passed,'kindLabel':'恢复演练回执','statusLabel':'恢复演练通过' if passed else '恢复演练尚未通过',
                    'setId':str(value.get('backupSetId') or ''),'schemaRevision':value.get('alembicRevision'),
                    'detail':f"已核验本地附件 {int(value.get('localFileObjectsVerified') or 0)} 个；演练用时 {int(value.get('restoreSeconds') or 0)} 秒"})
            elif value.get('gate')=='G19' and str(value.get('tenantId'))==str(tenant_id):
                verified=value.get('verification') or {}
                if not isinstance(verified,dict) or any(not isinstance(verified.get(k,[]),list)
                    for k in ('tableCounts','countMismatches','logicalOrphans')): raise ValueError('迁移对账明细格式错误')
                tables=verified.get('tableCounts') or []
                passed=value.get('verdict')=='PASS' and all(value.get(k) is True
                    for k in ('g19Qualified','databaseQualified','fileBytesQualified')) \
                    and bool(tables) and not verified.get('countMismatches') and not verified.get('logicalOrphans')
                items.append({**common,'kind':'MIGRATION','passed':bool(passed),'kindLabel':'历史迁移核对回执',
                    'statusLabel':'数据与附件核对通过，仍须师生办理验收' if passed else '迁移核对尚未通过',
                    'detail':f"对账表 {len(tables)} 张；数据核对{'通过' if value.get('databaseQualified') is True else '未通过'}；附件核对{'通过' if value.get('fileBytesQualified') is True else '未通过'}",
                    'tables':tables,'differenceCount':len(verified.get('countMismatches') or []),
                    'orphanCount':len(verified.get('logicalOrphans') or [])})
        except (ValueError,TypeError,OSError,KeyError,IndexError):
            items.append({**receipt_kind,'title':path.name,'kindLabel':'脚本回执','statusLabel':'回执无法读取，未验证'})
    return {'items':items,'note':'脚本回执按学校隔离并核对校验值；学校登记资料单独保存，不会改变脚本核验结论。'}


def backup_summary(evidence):
    receipts=[row for row in evidence['items'] if row.get('kind') in ('BACKUP','RESTORE') or not row.get('kind')]
    if not receipts: status='尚未取得备份与恢复演练回执'
    elif any(not row.get('passed') for row in receipts): status='存在失败或尚未核验的回执'
    elif not any(row.get('kind')=='BACKUP' for row in receipts): status='尚缺备份完成回执'
    elif not any(row.get('kind')=='RESTORE' for row in receipts): status='已有备份回执，尚缺恢复演练回执'
    else: status='已有备份与恢复回执，请核对时间和版本'
    return {'statusLabel':status,'note':evidence['note'],'path':'/admin/system/runtime'}
