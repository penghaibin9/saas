#!/usr/bin/env python3
"""Download the owner-approved site ZIP only when its exact SHA256 is configured."""
import hashlib, ipaddress, json, os, socket, urllib.parse, urllib.request
from pathlib import Path

def check_url(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.port not in (None,443):
        raise ValueError('A public HTTPS artifact URL is required')
    addresses = socket.getaddrinfo(url.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Private, reserved and local artifact addresses are not allowed')
    return value

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        check_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def output(name,value):
    target = os.environ.get('GITHUB_OUTPUT')
    if target:
        with open(target,'a',encoding='utf8') as f: f.write(f'{name}={value}\n')

config=json.loads(Path('.github/official-showcase-release.json').read_text(encoding='utf8'))
url=config.get('artifact_url')
if not url:
    print('WAITING: approved binary upload is not configured; existing homepage remains unchanged.')
    output('ready','false')
else:
    check_url(url)
    expected=config['sha256']
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected): raise ValueError('Invalid SHA256')
    size=config['bytes']
    if not isinstance(size,int) or not 0<size<=80_000_000: raise ValueError('Invalid archive size')
    target=Path(os.environ['RUNNER_TEMP'])/'showcase-release.zip'
    digest=hashlib.sha256(); received=0
    opener=urllib.request.build_opener(Redirects())
    with opener.open(urllib.request.Request(url,headers={'User-Agent':'Yueke-Approved-Website-Importer/1.0'}),timeout=45) as response, target.open('wb') as result:
        check_url(response.geturl())
        while chunk:=response.read(1_048_576):
            received+=len(chunk)
            if received>size: raise ValueError('Archive exceeds approved size')
            digest.update(chunk);result.write(chunk)
    if received!=size or digest.hexdigest()!=expected:
        target.unlink(missing_ok=True)
        raise ValueError('Downloaded ZIP does not match the approved release')
    print('Approved artifact size and SHA256 verified.')
    output('ready','true')
    output('sha256',expected)
