#!/usr/bin/env python3
"""Download the one owner-approved public archive through its actual share UI."""
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout


@lru_cache(maxsize=128)
def public_host(host):
    try:
        rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(rows) and all(ipaddress.ip_address(row[4][0]).is_global for row in rows)
    except OSError:
        return False


def main():
    config = json.loads(Path('.github/official-showcase-release.json').read_text())
    url = config['share_url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'firestorage.ai' or not re.fullmatch(r'/ja/f/[A-Za-z0-9]+', parsed.path):
        raise ValueError('Unexpected share URL')
    expected_name = '跃科官网-已施工源码与配乐完整包-20260909.zip'
    size, sha = config['bytes'], config['sha256']
    if size != 15142223 or sha != '7d28688802e96621f969320c908947f6b869c20cb5fef7d4beba07c76c1d4f51':
        raise ValueError('This transfer is locked to the existing approved archive')
    destination = Path(os.environ['RUNNER_TEMP']) / 'showcase-release.zip'
    downloads = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={'width':1366,'height':900}, locale='ja-JP')
        def route_request(route):
            address = urlsplit(route.request.url)
            if address.scheme == 'https' and address.hostname and not address.username and address.port in (None,443) and public_host(address.hostname):
                route.continue_()
            else:
                route.abort()
        context.route('**/*', route_request)
        context.on('page', lambda page: page.on('download', lambda item: downloads.append(item)))
        page = context.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        try:
            page.get_by_text(expected_name, exact=False).first.wait_for(state='visible', timeout=45000)
        except BrowserTimeout:
            print('PUBLIC SHARE VISIBLE TEXT:', page.locator('body').inner_text()[:4000])
            raise RuntimeError('Approved file not visible in the share; authentication/challenges are not bypassed')
        print('The approved archive is visible in the public share.')
        clicked = set()
        for attempt in range(6):
            buttons = page.locator('button, a[download], a[href]')
            candidates = []
            for i in range(buttons.count()):
                control = buttons.nth(i)
                if not control.is_visible() or not control.is_enabled():
                    continue
                label = ' '.join([control.inner_text() or '', control.get_attribute('aria-label') or '', control.get_attribute('title') or '']).strip()
                is_download = bool(re.search(r'ダウンロード|download|下载', label, re.I)) or control.get_attribute('download') is not None
                if is_download and label not in clicked:
                    all_files = bool(re.search(r'まとめ|一括|すべて|all files', label, re.I))
                    candidates.append((all_files, label, control))
            candidates.sort(key=lambda row: row[0])
            if not candidates:
                if 'file-title' in clicked:
                    print('PUBLIC SHARE VISIBLE TEXT:', page.locator('body').inner_text()[:4000])
                    print('PUBLIC SHARE CONTROLS:', buttons.all_text_contents()[:25])
                    raise RuntimeError('No public download control found for the approved file')
                clicked.add('file-title')
                page.get_by_text(expected_name, exact=False).first.click()
            else:
                _, label, control = candidates[0]
                clicked.add(label)
                print('Using service-provided download control:', label[:150])
                control.click(timeout=10000)
            for tick in range(24):
                page.wait_for_timeout(500)
                if downloads:
                    item = downloads.pop(0)
                    source = Path(item.path())
                    data = source.read_bytes()
                    if len(data) == size and hashlib.sha256(data).hexdigest() == sha:
                        shutil.copyfile(source, destination)
                        print('PUBLIC_SHARE_ARCHIVE_VERIFIED:', size, sha)
                        browser.close()
                        return
                    print('Rejected a download that was not the approved ZIP:', item.suggested_filename, len(data))
                    item.delete()
            print('Download not yet available; inspecting the updated share view.')
        raise RuntimeError('The approved archive was not downloaded; original website remains unchanged')


if __name__ == '__main__':
    main()
