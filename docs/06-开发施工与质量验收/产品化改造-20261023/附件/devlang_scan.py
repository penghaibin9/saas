"""界面开发者语言普查：扫描 Vue 模板可见文字、脚本中文字面量、后端返回给用户的中文消息。
用法（在仓库根目录）: python devlang_scan.py . backend/app out.csv
只扫 frontend/src、student-portal/src、miniapp/src、enterprise-portal/src 与 backend/app。
"""
import csv, os, re, sys, json, collections

SRC, BE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CN = re.compile(r'[一-鿿]')

# (类别, 正则, 建议)
RULES = [
 # 一、工程术语
 ('工程术语', r'回读', '已保存 / 已更新'),
 ('工程术语', r'原命令|命令引用|重发命令|发送命令|命令编号', '上次提交'),
 ('工程术语', r'只读核对|只读查询|只读刷新|只读查看', '刷新查看结果'),
 ('工程术语', r'待核实|待核对|待解析|待治理|待核验', '暂未获取 / 未填写'),
 ('工程术语', r'正式事实|业务事实|事实来源|考勤事实|教学事实|同一事实|事实摘要|事实链|事实', '记录 / 信息'),
 ('工程术语', r'真值|唯一真值', '记录'),
 ('工程术语', r'幂等|重放|重放|自动重放|自动重发|不会重提|不会重发', '（删除，系统自动防重复）'),
 ('工程术语', r'门禁|闸门|原子|事务内|持久化|写链|写入链|主链|旁支|链路|闭环|兜底|降级', '（删除该说明）'),
 ('工程术语', r'投影|契约|合同测试|快照版本|版本号|记录版本|冻结名单|名单版本|方案版本|版本指纹|指纹', '（删除或改为“更新时间”）'),
 ('工程术语', r'生效策略|来源新鲜度|新鲜度|口径', '（删除或改为“统计范围”）'),
 ('工程术语', r'服务端|服务器端|后端|前端|接口|数据库|字段|枚举|权限码|令牌|缓存|注册表|配置项', '系统'),
 ('工程术语', r'责任队列|责任接力|责任方|下一责任|当前责任|责任工作区|责任链', '待办 / 下一步由谁办理'),
 ('工程术语', r'当前对象|来源对象|业务对象|核验对象|对象', '（用具体名称：课程/学生/申请）'),
 ('工程术语', r'权威导入|权威来源|权威|稳定课程身份|稳定.{0,4}身份|稳定教师工号', '（删除“权威/稳定”）'),
 ('工程术语', r'预检|预校验', '检查'),
 ('工程术语', r'证据链|证据包|审计证据|验收证据|证据', '材料 / 记录'),
 ('工程术语', r'阻断项|阻断', '必须先处理的问题'),
 ('工程术语', r'回执', '提交结果'),
 ('工程术语', r'台账', '记录（台账可保留在管理端）'),
 ('工程术语', r'特殊补录|管理员特殊补录', '补录'),
 # 二、施工/开发痕迹
 ('施工痕迹', r'待施工|施工中|施工|波次|原型|演示数据|假数据|mock|Mock|占位|TODO|开发中|预留', '（上线版不应出现）'),
 ('施工痕迹', r'\b[PWVRTU]\d{1,3}\b|阶段\s?\d+|第[一二三四五六七八九十]+轮', '（删除内部阶段编号）'),
 ('施工痕迹', r'兼容|旧版|旧接口|旧路径|旧入口|legacy|Legacy', '（不兼容旧模块，删除）'),
 # 三、过度防御说明
 ('过度说明', r'不承诺|不代表|不等于|不等同|不能证明|以.{0,6}为准|仅供审计|不会.{0,6}重复', '（删掉或改成一句正向提示）'),
]
RULES = [(c, re.compile(p), s) for c, p, s in RULES]

ENG_ALLOW = set('Excel PDF Word ZIP CSV XLSX xlsx PNG JPG QQ App APP app Logo logo VIP WiFi Wi-Fi Fi OK Email email E-mail URL PC H5 iOS Android AI GPS KPI Tab Enter Ctrl Shift Esc vs No'.split())
ENG = re.compile(r'(?<![A-Za-z0-9_$.@/#-])([A-Za-z][A-Za-z0-9_]{2,})(?![A-Za-z0-9_(])')
ENUM = re.compile(r'\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b')
CAMEL = re.compile(r'\b[a-z]+[A-Z][A-Za-z0-9]+\b')
IDSHOW = re.compile(r'(#\s*\{\{|ID\s*\{\{|编号\s*\{\{|\{\{\s*[\w.?]*?(?:Id|ID|_id)\s*\}\})')
HTTPCODE = re.compile(r'HTTP\s?\d{3}|(?:错误|状态|代码|码)\s?(?:401|403|404|409|422|500)|(?:401|403|404|409|422|500)\s?(?:错误|状态)')

def side_of(path):
    p = path.replace('\\', '/')
    if p.startswith('./frontend') or p.startswith('frontend'):
        m = re.search(r'modules/([^/]+)/', p)
        return '管理/教师PC', (m.group(1) if m else ('config' if '/config/' in p else 'common'))
    if 'student-portal' in p:
        m = re.search(r'views/([^/]+)/', p); return '学生PC', (m.group(1) if m else 'common')
    if 'miniapp' in p:
        m = re.search(r'pages/([^/]+)/([^/]+)/?', p)
        return '移动端', (m.group(1) + '/' + m.group(2) if m else 'common')
    if 'enterprise-portal' in p: return '企业门户', 'common'
    if 'backend' in p or p.startswith('./app') or '/app/' in p:
        m = re.search(r'modules/([^/]+)/', p); return '后端返回文案', (m.group(1) if m else 'core')
    return '其他', ''

rows = []
def emit(path, ln, src, seg):
    seg = seg.strip()
    if not seg: return
    hits = []
    for cat, rx, sug in RULES:
        m = rx.search(seg)
        if m: hits.append((cat, m.group(0), sug))
    raw = seg
    for mm in re.finditer(r'\$\{([^}]*)\}', raw):
        ex = mm.group(1)
        if re.search(r'[A-Za-z]*(?:Id|ID)\s*(?:\)|\|\||\?\?|$)|(?:^|\.)id\s*(?:\|\||\?\?|$)', ex) and not re.search(r'Name|Label|No\b|Code', ex):
            hits.append(('内部ID外露', '${' + ex[:50] + '}', '用名称描述对象，ID 不上屏'))
    seg = re.sub(r'\$\{[^}]*\}', ' ', seg)
    if CN.search(seg) or src == '模板文字':
        for m in ENUM.finditer(seg): hits.append(('英文/代码外露', m.group(0), '换成中文状态名'))
        for m in CAMEL.finditer(seg):
            if m.group(0) not in ENG_ALLOW: hits.append(('英文/代码外露', m.group(0), '换成中文'))
        for m in HTTPCODE.finditer(seg): hits.append(('英文/代码外露', m.group(0), '换成原因说明'))
        if src != '脚本文案' and src != '后端返回文案':
            for m in ENG.finditer(re.sub(r'\{\{.*?\}\}', '', seg)):
                w = m.group(1)
                if w in ENG_ALLOW or w.lower() in {x.lower() for x in ENG_ALLOW}: continue
                if re.fullmatch(r'[a-z]+', w) and len(w) <= 3: continue
                hits.append(('英文/代码外露', w, '换成中文'))
    if src in ('模板文字', '模板属性/表达式'):
        for m in IDSHOW.finditer(seg): hits.append(('内部ID外露', m.group(0), '用名称描述对象，ID 不上屏'))
    side, mod = side_of(path)
    seen = set()
    for cat, word, sug in hits:
        k = (cat, word)
        if k in seen: continue
        seen.add(k)
        rows.append([side, mod, path.lstrip('./'), ln, src, cat, word, raw[:220], sug])

QSTR = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"|`((?:[^`\\]|\\.)*)`")

def scan_vue(path, text):
    lines = text.split('\n')
    sstart = next((i for i, l in enumerate(lines) if l.lstrip().startswith('<script')), len(lines))
    m = re.search(r'^<template[^>]*>', text, re.M)
    if m:
        # 找与之匹配的最后一个顶格 </template>
        ends = [x.start() for x in re.finditer(r'^</template>', text, re.M)]
        blocks = [x.start() for x in re.finditer(r'^\s*<(?:script|style)\b', text, re.M) if x.start() > m.end()]
        nxt = min(blocks) if blocks else len(text)
        cand = [e for e in ends if m.end() < e <= nxt] or [x.start() for x in re.finditer(r'</template>', text) if m.end() < x.start() <= nxt]
        tend = max(cand) if cand else nxt
        scan_template(path, text, m.end(), tend)
    for i, l in enumerate(lines):
        if i > sstart and not l.lstrip().startswith('<style'):
            if l.lstrip().startswith('</script>'): break
            scan_script_line(path, i + 1, l)

def scan_template(path, text, a, b):
    i = a
    def line_of(pos): return text.count('\n', 0, pos) + 1
    while i < b:
        if text.startswith('<!--', i):
            j = text.find('-->', i); i = (j + 3) if j >= 0 else b; continue
        if text[i] == '<':
            # 解析标签
            j = i + 1; q = None
            while j < b:
                ch = text[j]
                if q:
                    if ch == q: q = None
                elif ch in '"\'':
                    q = ch
                elif ch == '>':
                    break
                j += 1
            tag = text[i:j + 1]
            for m in re.finditer(r'(\s[:@#]?[\w.:-]+)\s*=\s*"([^"]*)"', tag):
                name, val = m.group(1).strip(), m.group(2)
                ln = line_of(i + m.start(2))
                if name[0] in ':@#' or name.startswith('v-'):
                    for qm in re.finditer(r"'((?:[^'\\]|\\.)*)'|`([^`]*)`", val):
                        v = qm.group(1) if qm.group(1) is not None else (qm.group(2) or '')
                        if CN.search(v): emit(path, ln, '模板属性/表达式', v)
                elif name in ('class', 'style', 'src', 'href', 'to', 'key', 'id', 'name', 'type', 'mode', 'variant', 'size', 'ref', 'slot', 'role'):
                    continue
                elif CN.search(val):
                    emit(path, ln, '模板属性/表达式', val)
            i = j + 1; continue
        j = text.find('<', i)
        if j < 0 or j > b: j = b
        seg = text[i:j]
        if seg.strip():
            base = i
            exprs = re.findall(r'\{\{(.*?)\}\}', seg, re.S)
            for expr in exprs:
                for qm in QSTR.finditer(expr):
                    v = next(g for g in qm.groups() if g is not None)
                    if CN.search(v): emit(path, line_of(i + seg.find(expr)), '模板属性/表达式', v)
            for mm in re.finditer(r'\{\{\s*(.*?)\s*\}\}', seg, re.S):
                ex = mm.group(1)
                if re.search(r'(?:^|[.\s(])[A-Za-z]*(?:Id|ID)\s*(?:\)|\|\||\?\?|$)|(?:^|\.)id\s*(?:\|\||\?\?|$)', ex) and not re.search(r'Name|Label|No\b|Code', ex):
                    side, mod = side_of(path)
                    ctx = seg[max(0, mm.start()-30):mm.end()+5].strip().replace('\n', ' ')
                    rows.append([side, mod, path.lstrip('./'), line_of(i + mm.start()), '模板文字', '内部ID外露', '{{ ' + ex[:60] + ' }}', ctx[:220], '用名称描述对象，ID 不上屏'])
            masked = re.sub(r'\{\{.*?\}\}', lambda m: '{{}}' + '\n' * m.group(0).count('\n'), seg, flags=re.S)
            for k, part in enumerate(masked.split('\n')):
                ln = line_of(base) + k
                core = re.sub(r'\{\{.*?\}\}', ' ', part)
                if CN.search(core) or ENG.search(core):
                    emit(path, ln, '模板文字', part)
                pass
        i = j

block = {'on': False}
def scan_script_line(path, ln, l):
    s = l.strip()
    if block['on']:
        if '*/' in s: block['on'] = False
        return
    if s.startswith('/*'):
        if '*/' not in s: block['on'] = True
        return
    if s.startswith('//') or s.startswith('*') or s.startswith('#'):
        return
    s = re.sub(r'//.*$', '', s) if "'" not in s.split('//')[-1] else s
    if 'console.' in s: return
    for m in QSTR.finditer(s):
        v = next(g for g in m.groups() if g is not None)
        if CN.search(v): emit(path, ln, '脚本文案', v)

def scan_js(path, text):
    block['on'] = False
    for i, l in enumerate(text.split('\n')):
        scan_script_line(path, i + 1, l)

# 只跳过测试与 mock；路径含 preview 的正式组件（文件预览、导入预览等）照常扫描，两个开发预览页由 DOC3 归为 L。
SKIP = re.compile(r'(/mock|/mocks/|__tests__|\.test\.|\.spec\.|/test/|/tests/|\.check\.mjs|/dev/)')
for root, _, files in (w for d in ('frontend/src','student-portal/src','miniapp/src','enterprise-portal/src') for w in os.walk(os.path.join(SRC, d))):
    for f in files:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, SRC)
        if SKIP.search('/' + rel.replace('\\', '/')): continue
        if rel.startswith('shared'): continue
        try: text = open(p, encoding='utf-8').read()
        except Exception: continue
        block['on'] = False
        if f.endswith('.vue'): scan_vue(rel, text)
        elif f.endswith(('.js', '.mjs', '.ts')):
            if '/api/' in rel.replace('\\', '/') and 'Error' not in text: continue
            scan_js(rel, text)

# 后端：用户可见消息（AppException / HTTPException / message= / label 中文）
BE_MSG = re.compile(r'''(?:AppException\(|HTTPException\(|unauthorized\(|forbidden\(|bad_request\(|conflict\(|not_found\(|message\s*=|detail\s*=|"message"\s*:|"notice"\s*:|"hint"\s*:|"reason"\s*:|"label"\s*:|"title"\s*:|"description"\s*:)[^\n]*''')
for root, _, files in os.walk(BE):
    for f in files:
        if not f.endswith('.py'): continue
        p = os.path.join(root, f); rel = 'backend/app/' + os.path.relpath(p, BE).replace(os.sep, '/')
        if '/tests/' in rel or 'mock' in rel: continue
        try: lines = open(p, encoding='utf-8').read().split('\n')
        except Exception: continue
        in_doc = False
        for i, l in enumerate(lines):
            st = l.strip()
            if st.startswith('"""') or st.startswith("'''"):
                if not (len(st) > 3 and st.endswith(('"""', "'''"))): in_doc = not in_doc
                continue
            if in_doc or st.startswith('#'): continue
            if not BE_MSG.search(l): continue
            for m in QSTR.finditer(l):
                v = next(g for g in m.groups() if g is not None)
                if CN.search(v):
                    side, mod = side_of(rel)
                    before = len(rows)
                    emit(rel, i + 1, '后端返回文案', v)

S1 = re.compile(r'回读|原命令|命令|只读|事实|真值|幂等|重放|重发|重提|门禁|闸门|原子|事务|持久化|写链|写入链|主链|旁支|投影|契约|合同测试|服务端|服务器端|后端|前端|接口|数据库|权限码|令牌|枚举|缓存|注册表|生效策略|新鲜度|待治理|待解析|冻结名单|名单版本|记录版本|版本号|指纹')
DOC3 = re.compile(r'ComponentDevPreview|UiPreview|PortalLegacyView|constructionMap|PlannedPlaceholder|/mocks?/|\.mock\.|AcademicLegacySafeView|PortalLayoutV5|views/Academic(Credit|Dashboard|Grade|Makeup|Student|Warning)|AdminAcademicLayout|_legacy|_compat|mock_')
OKENG = {'DOCX','PPTX','Open','Meteo','CAD','PLC','SVG','JSON','HTTPS','HTTP','IP','OCR','QR','SMS'}
def level(cat, word, text, path):
    if cat == '英文/代码外露':
        if word in OKENG: return None
        if word in ('GPA', 'CNY', 'SLA', 'MFA'): return '建议改'
        if re.fullmatch(r'[A-Z]+', word) and not CN.search(text): return '建议改'
        return '必改'
    if cat in ('施工痕迹', '内部ID外露') or S1.search(word):
        if 'official' in path and word in ('接口', '数据库'): return '建议改'
        return '必改'
    if word in ('台账', '回执'): return '可保留'
    return '建议改'
def batch(f):
    if DOC3.search(f): return 'L（文档3删除）'
    if f.startswith('backend/'): return 'D1-H 后端返回文案'
    if f.startswith('miniapp/'): return 'D1-F 移动端'
    if f.startswith(('student-portal/', 'enterprise-portal/')): return 'D1-G 学生PC+企业门户'
    if '/modules/academicAffairs/' in f: return 'D1-B 教务PC'
    if '/config/' in f: return 'D1-C 帮助中心与配置'
    if re.search(r'/modules/(system|platform)/', f): return 'D1-D 系统与平台PC'
    if '/modules/' in f: return 'D1-E 学工/实习/毕设/就业/迎新等PC'
    return 'D1-A 公共组件与外壳'
final = []
for side, mod, path, ln, src, cat, word, text, sug in rows:
    lv = level(cat, word, text, path)
    if lv is None: continue
    if cat == '英文/代码外露' and lv == '建议改' and re.fullmatch(r'[A-Z]+', word) and not CN.search(text):
        sug = '英文装饰标题，建议改中文或删除'
    final.append([batch(path), lv, side, mod, path, ln, src, cat, word, text, sug])
final.sort(key=lambda r: (r[0], r[4], int(r[5])))
with open(OUT, 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['批次', '级别', '端', '模块', '文件', '行号', '来源', '类别', '命中词', '原文', '建议'])
    w.writerows(final)
print(len(final), collections.Counter(r[1] for r in final if not r[0].startswith('L')))
