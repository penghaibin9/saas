"""Retired school-owned website publisher. Never opens the school database."""
import sys


def run():
    print('学校系统内的官网新闻发布进程已退役。请使用 website/backend 的独立发布服务；迁移核验前不要启用新队列。', file=sys.stderr)
    raise SystemExit(78)


if __name__ == '__main__':
    run()
