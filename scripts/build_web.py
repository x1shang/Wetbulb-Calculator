# -*- coding: utf-8 -*-
"""build_web.py — 把 web/src/ 下的源码组装成单文件 web/index.html。

【为什么要"源码分文件 + 组装成单文件"这两步】
    交付物必须是**一个 .html**：双击就能开、能发群里、能直接丢到 GitHub Pages，
    不需要服务器、不需要联网、不需要 Python。这是产品约束。

    但开发时不能真去维护一个 4000 行的单文件：CSS 与 JS 混在一起没法单独语法检查，
    而 web/src/core.js 还必须能被 Node 直接 require 来做与 core.py 的逐点对拍。
    所以：源码按职责分成 4 份，构建时内联成一个文件。这与仓库里
    WetBulbCalculator.spec + build.ps1 的关系是同一个套路。

【用法】
    python scripts/build_web.py            # 组装 web/index.html
    python scripts/build_web.py --check    # 只检查是否与源码一致（CI 用），不写盘

【组装方式】
    shell.html 里有四个占位标记，逐个替换成对应文件的全文：
        /*__APP_CSS__*/  ← web/src/app.css
        /*__VECTORS__*/  ← web/src/vectors.js   （由 scripts/export_vectors.py 生成）
        /*__CORE__*/     ← web/src/core.js
        /*__UI__*/       ← web/src/ui.js
    任何标记在组装后仍存在，都视为构建失败 —— 否则会出现"改了源码但页面没变"。
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'web', 'src')
OUT = os.path.join(ROOT, 'web', 'index.html')

BANNER = (
    '<!-- =====================================================================\n'
    '     湿球计算器 网页版 · 单文件构建产物 —— **请勿直接编辑本文件**。\n'
    '     源码在 web/src/ 下（app.css / shell.html / vectors.js / core.js / ui.js），\n'
    '     改完执行：python scripts/build_web.py\n'
    '     数值内核 core.js 是 src/core.py 的移植，改动后必须跑：\n'
    '         python -m pytest tests/test_web_parity.py -q\n'
    '     ===================================================================== -->\n'
)

PARTS = {
    '/*__APP_CSS__*/': 'app.css',
    '/*__VECTORS__*/': 'vectors.js',
    '/*__CORE__*/': 'core.js',
    '/*__UI__*/': 'ui.js',
}


def read(name):
    with open(os.path.join(SRC, name), encoding='utf-8') as f:
        return f.read()


def build():
    shell = read('shell.html')
    # 先做一次占位检查：漏掉任何一个都会让页面少一块功能，而且不报错
    for marker in PARTS:
        if shell.count(marker) != 1:
            raise SystemExit(f'[构建失败] {marker} 在 shell.html 里出现了 {shell.count(marker)} 次，应恰好 1 次')
    for marker, name in PARTS.items():
        text = read(name)
        # 内容里若出现占位标记会互相污染（例如说明文字里顺手写了一句），这里直接拦下
        for other in PARTS:
            if other in text:
                raise SystemExit(f'[构建失败] {name} 里出现了占位标记 {other}')
        shell = shell.replace(marker, text)
    for marker in PARTS:
        if marker in shell:
            raise SystemExit(f'[构建失败] 组装后仍残留占位标记 {marker}')
    head = '<!DOCTYPE html>\n'
    if not shell.startswith(head):
        raise SystemExit('[构建失败] shell.html 必须以 <!DOCTYPE html> 开头')
    # 注释放在 DOCTYPE 与 <html> 之间是合法的，不会触发怪异模式
    return shell.replace(head, head + BANNER, 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description='组装单文件网页版')
    parser.add_argument('--check', action='store_true', help='只检查是否与源码一致，不写盘')
    args = parser.parse_args(argv)

    text = build()
    if args.check:
        if not os.path.exists(OUT):
            print(f'[过期] {OUT} 不存在，请运行 python scripts/build_web.py', file=sys.stderr)
            return 1
        with open(OUT, encoding='utf-8') as f:
            old = f.read()
        if old != text:
            print('[过期] web/index.html 与 web/src/ 不一致，'
                  '请运行 python scripts/build_web.py', file=sys.stderr)
            return 1
        print(f'[最新] web/index.html 与源码一致（{len(text) / 1024:.1f} KB）')
        return 0

    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print(f'已写出 {os.path.relpath(OUT, ROOT)}：{len(text) / 1024:.1f} KB（{text.count(chr(10)) + 1} 行）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
