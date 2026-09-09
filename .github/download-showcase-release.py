#!/usr/bin/env python3
"""Resolve an approved public share and accept only the exact owner-approved ZIP."""
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import urllib.parse
import urllib.request


def check_url(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.port not in (None, 443):
        raise ValueError('A public HTTPS artifact URL is required')
    addresses = socket.getaddrinfo(url.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Private, reserved and local artifact addresses are not allowed')
    return value


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'a' and values.get('href'):
            self.links.append((values['href'], 'download' in values))
        if tag == 'script' and values.get('src'):
            self.scripts.append(values['src'])


def output(name, value):
    target = os.environ.get('GITHUB_OUTPUT')
    if target:
        with open(target, 'a', encoding='utf8') as f:
            f.write(f'{name}={value}\n')


def main():
    config = json.loads(Path('.github/official-showcase-release.json').read_text(encoding='utf8'))
    url = config.get('artifact_url')
    if not url:
        print('WAITING: approved binary upload is not configured; existing homepage remains unchanged.')
        output('ready', 'false')
        return
    expected, size = config['sha256'], config['bytes']
    if not re.fullmatch('[a-f0-9]{64}', expected):
        raise ValueError('Invalid SHA256')
    if not isinstance(size, int) or not 0 < size <= 80_000_000:
        raise ValueError('Invalid archive size')
    target = Path(os.environ['RUNNER_TEMP']) / 'showcase-release.zip'
    opener = urllib.request.build_opener(Redirects())

    def fetch(address, limit):
        check_url(address)
        req = urllib.request.Request(address, headers={'User-Agent': 'Yueke-Approved-Website-Importer/1.0'})
        with opener.open(req, timeout=45) as response:
            check_url(response.geturl())
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Response exceeds approved size limit')
            return response.geturl(), response.headers.get_content_type(), data

    final_url, mime, data = fetch(url, size)
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
        # Public share pages are not ZIP files. Only consider download links
        # actually emitted by the service; never guess a storage object URL.
        if mime not in ('text/html', 'application/xhtml+xml'):
            raise ValueError('Downloaded bytes do not match the approved release')
        if urllib.parse.urlsplit(final_url).hostname != 'firestorage.ai':
            raise ValueError('Unexpected public share host')
        page = data.decode('utf-8', errors='replace')
        parsed = PublicLinks()
        parsed.feed(page)
        print('Public share page loaded; resolving the archive link.')
        candidates = [urllib.parse.urljoin(final_url, href) for href, download in parsed.links
                      if download or '.zip' in href.lower() or 'download' in href.lower()]
        for candidate in candidates[:8]:
            candidate_url, candidate_mime, candidate_data = fetch(candidate, size)
            if len(candidate_data) == size and hashlib.sha256(candidate_data).hexdigest() == expected:
                final_url, mime, data = candidate_url, candidate_mime, candidate_data
                break
        else:
            print('PUBLIC_SHARE_LINKS:', json.dumps(parsed.links[:30], ensure_ascii=False))
            print('PUBLIC_SHARE_SCRIPTS:', json.dumps(parsed.scripts[:30], ensure_ascii=False))
            # Limited excerpts from the approved public page aid link resolution.
            for match in list(re.finditer(r'download|/api/|01a0856b|rOz0tcz', page, re.I))[:16]:
                print('PUBLIC_SHARE_EXCERPT:', html.unescape(page[max(0, match.start()-120):match.end()+300]))
            # Inspect only same-site public JavaScript, without executing it.
            for script in parsed.scripts[:8]:
                address = urllib.parse.urljoin(final_url, script)
                if urllib.parse.urlsplit(address).hostname != 'firestorage.ai':
                    continue
                _, _, body = fetch(address, 3_000_000)
                text = body.decode('utf8', errors='replace')
                for match in list(re.finditer(r'/api/[^\s\"\x27`]+|downloadUrl|download_url', text))[:20]:
                    print('PUBLIC_SCRIPT_EXCERPT:', text[max(0, match.start()-100):match.end()+240])
            raise RuntimeError('Share upload verified; a service-issued file download link is still required')
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Final ZIP SHA256 or size mismatch')
    target.write_bytes(data)
    print(f'Approved artifact verified: {len(data)} bytes; SHA256 {expected}')
    output('ready', 'true')
    output('sha256', expected)


if __name__ == '__main__':
    main()
