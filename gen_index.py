#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描 bdat_html_<ver>/ 目录，生成分类索引页 index.html。

用法:
    python3 gen_index.py [目录名]      # 默认 bdat_html_2.2.0

产出:
    <目录>/index.html   —— 纯静态，无外部依赖，可直接发布

分组规则完全基于文件名前缀（BDAT 表名本身就有命名规范）。
数据以紧凑 JSON 内嵌，前端懒渲染，5000+ 条目也不卡。
"""

import datetime
import json
import os
import re
import sys

# ---------------------------------------------------------------- 分类规则

# 前缀 -> (一级名, 二级名)。顺序敏感，先匹配者优先
PREFIX_RULES = [
    (r'^BTL_',         ('战斗', 'BTL 战斗数据表')),
    (r'^FLD_',         ('地图与场景', 'FLD 字段表')),
    (r'^SYS_',         ('系统', 'SYS 系统表')),
    (r'^MNU_',         ('系统', 'MNU 菜单与 UI')),
    (r'^ITM_',         ('道具', 'ITM 道具表')),
    (r'^QST_',         ('任务', 'QST 任务表')),
    (r'^EVT_',         ('任务', 'EVT 事件表')),
    (r'^RSC_',         ('资源', 'RSC 资源表')),
    (r'^VO',           ('资源', 'VO 语音')),
    (r'^AMB_',         ('资源', 'AMB 环境')),
    (r'^CHR_',         ('角色', 'CHR 角色表')),
    (r'^Challenge',    ('角色', 'Challenge 挑战')),
    (r'^[Gg][Mm][Kk]', ('场景机关', 'GMK 机关')),
    (r'^gimmick',      ('场景机关', 'gimmick 机关')),
    (r'^ma\d+[a-z]',   ('地图与场景', None)),   # 二级名走区域规则
    (r'^ev\d',         ('任务', 'ev 事件脚本')),
]

# msg_* 子类型（下划线后的字母段）。含义为按命名惯例推测，页面上有标注。
MSG_SUBTYPES = [
    ('tlk', '对话 tlk'), ('nq', '任务 nq'), ('ev', '事件 ev'), ('tq', '对话 tq'),
    ('cq', '任务 cq'), ('sq', '任务 sq'), ('fev', '地图事件 fev'), ('ask', '委托 ask'),
    ('mnu', '菜单 mnu'), ('btl', '战斗 btl'), ('item', '道具 item'), ('mv', '过场 mv'),
    ('fld', '地图 fld'), ('qst', '任务 qst'), ('enemy', '敌人 enemy'), ('npc', 'NPC'),
    ('colony', '殖民地 colony'), ('comspot', '休息点 comspot'),
    ('autotalk', '自动对话 autotalk'),
]

HASH_RE = re.compile(r'^[0-9A-F]{8}$')
BIG_SIZE = 1024 * 1024   # 超过此值索引页上标红


def classify(name):
    """返回 (一级分类, 二级分类)"""
    if HASH_RE.match(name):
        return ('未识别', 'Hash 命名（需查 xb3_hashes.csv）')

    if name.startswith('msg_'):
        m = re.match(r'([a-z]+)', name[4:])
        if m:
            for sub, label in MSG_SUBTYPES:
                if m.group(1) == sub:
                    return ('台词与文本', label)
            return ('台词与文本', '其他 %s_*' % m.group(1))
        return ('台词与文本', '其他')

    for pattern, (parent, child) in PREFIX_RULES:
        if re.match(pattern, name):
            if child is None:
                m = re.match(r'^(ma\d+[a-z]?)', name)
                return ('地图与场景', '区域 %s' % m.group(1))
            return (parent, child)

    return ('其他', '未归类')


def human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.0f %s' % (n, unit) if unit == 'B' else '%.1f %s' % (n, unit)
        n /= 1024.0


# ---------------------------------------------------------------- 主流程

def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'bdat_html_2.2.0')
    if not os.path.isdir(root):
        sys.exit('目录不存在: %s' % root)

    rows = []
    newest = 0            # 表数据的最新修改时间
    for fn in os.listdir(root):
        if not fn.endswith('.html') or fn == 'index.html':
            continue
        st = os.stat(os.path.join(root, fn))
        rows.append((fn[:-5], st.st_size))
        newest = max(newest, st.st_mtime)
    rows.sort(key=lambda r: r[0].lower())

    cats, cat_list, tables = {}, [], []
    for name, size in rows:
        key = classify(name)
        if key not in cats:
            cats[key] = len(cat_list)
            cat_list.append([key[0], key[1], 0, 0])
        idx = cats[key]
        cat_list[idx][2] += 1
        cat_list[idx][3] += size
        tables.append([name, size, idx])

    total_bytes = sum(r[1] for r in rows)
    big_count = sum(1 for r in rows if r[1] >= BIG_SIZE)

    payload = {'cats': cat_list, 'tables': tables,
               'total': len(rows), 'bytes': total_bytes, 'big': big_count}

    fmt = '%Y-%m-%d %H:%M'
    built = datetime.datetime.now().strftime(fmt)
    updated = datetime.datetime.fromtimestamp(newest).strftime(fmt)

    html = (TEMPLATE
            .replace('/*__DATA__*/null',
                     json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
            .replace('__TOTAL__', str(len(rows)))
            .replace('__SIZE__', human_size(total_bytes))
            .replace('__BIG__', str(big_count))
            .replace('__BUILT__', built)
            .replace('__UPDATED__', updated))

    out = os.path.join(root, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    print('已生成 %s' % out)
    print('  %d 张表 / %s / %d 个超 1MB 大表 / %d 个分类'
          % (len(rows), human_size(total_bytes), big_count, len(cat_list)))


# ---------------------------------------------------------------- 页面模板

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Xenoblade 3 BDAT 表索引 · __TOTAL__ 张表</title>
<style>
  :root {
    --bg: #f6f6f4; --card: #fff; --line: #e2e0da;
    --text: #24231f; --muted: #6b6a63;
    --accent: #185fa5; --accent-soft: #e6f1fb;
    --warn: #a32d2d; --warn-soft: #fcebeb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI",
          "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  header {
    position: sticky; top: 0; z-index: 10; background: var(--card);
    border-bottom: 1px solid var(--line); padding: 16px 24px 12px;
  }
  .wrap, main { max-width: 1180px; margin: 0 auto; }
  h1 { font-size: 17px; font-weight: 600; margin: 0 0 2px; }
  .sub { color: var(--muted); font-size: 12.5px; margin: 0 0 3px; }
  .sub b { color: var(--text); font-weight: 600; }
  .build {
    color: var(--muted); font-size: 12px; margin: 0 0 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .build b { color: var(--text); font-weight: 600; }
  .searchbar { display: flex; gap: 10px; align-items: center; }
  #q {
    flex: 1; padding: 9px 12px; font-size: 14px; font-family: inherit;
    border: 1px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--text);
  }
  #q:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); background: #fff; }
  .hint { color: var(--muted); font-size: 12px; white-space: nowrap; }
  kbd {
    font: 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    border: 1px solid var(--line); border-bottom-width: 2px;
    border-radius: 4px; padding: 2px 4px; background: var(--bg);
  }
  main { padding: 20px 24px 80px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
  .cat { background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  .cat > summary {
    cursor: pointer; padding: 12px 14px; list-style: none;
    display: flex; flex-direction: column; gap: 2px;
  }
  .cat > summary::-webkit-details-marker { display: none; }
  .cat > summary:hover { background: var(--bg); }
  .cat-name { font-weight: 600; font-size: 13.5px; }
  .cat-meta { color: var(--muted); font-size: 12px; }
  .cat[open] > summary { border-bottom: 1px solid var(--line); background: var(--bg); }
  .cat ul { list-style: none; margin: 0; padding: 6px 0; max-height: 420px; overflow-y: auto; }
  .cat li { padding: 0 14px; }
  .cat li a, .results li a { display: flex; justify-content: space-between; gap: 10px; padding: 3px 0; font-size: 13px; }
  .sz { color: var(--muted); font-size: 11.5px; white-space: nowrap; }
  .more { padding: 8px 14px; font-size: 12px; color: var(--muted); }
  .big { color: var(--warn) !important; font-weight: 600; }
  .badge {
    background: var(--warn-soft); color: var(--warn); font-size: 11px;
    padding: 0 5px; border-radius: 4px; margin-left: 6px;
  }
  .results { background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  .results ul { list-style: none; margin: 0; padding: 6px 0; }
  .results li { padding: 0 16px; }
  .results .path { color: var(--muted); font-size: 11.5px; }
  .empty { padding: 28px 16px; text-align: center; color: var(--muted); }
  .notice { color: var(--muted); font-size: 12px; margin: 16px 0 0; }
  h2.group { font-size: 13px; margin: 24px 0 10px; color: var(--muted); font-weight: 600; }
  h2.group span { font-weight: 400; }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Xenoblade 3 · BDAT 数据表索引</h1>
    <p class="sub">共 <b>__TOTAL__</b> 张表 · <b>__SIZE__</b> · 其中 <b>__BIG__</b> 张超过 1 MB（打开会卡，已标红）</p>
    <p class="build">索引构建 <b>__BUILT__</b> · 表数据更新 <b>__UPDATED__</b></p>
    <div class="searchbar">
      <input id="q" type="search" placeholder="搜索表名，例如 EnemyData、msg_tlk0301、FLD_Condition" autocomplete="off">
      <span class="hint"><kbd>/</kbd> 聚焦</span>
    </div>
  </div>
</header>

<main>
  <div id="browse"></div>
  <div id="result" hidden></div>
  <p class="notice">分组依据 BDAT 表文件名前缀自动生成；<code>msg_*</code> 子类型含义为按命名惯例推测，仅供参考。Hash 命名的表需对照 <code>xb3_hashes.csv</code> 才能确定原名。</p>
</main>

<script>
const DATA = /*__DATA__*/null;
const BIG = 1048576;
const CATS = DATA.cats;
const T = DATA.tables;
const LIMIT = 300;

function human(n) {
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1048576).toFixed(1) + ' MB';
}

function itemHTML(t) {
  const big = t[1] >= BIG;
  return '<li><a href="' + encodeURIComponent(t[0]) + '.html">'
    + '<span>' + t[0] + (big ? '<span class="badge">大</span>' : '') + '</span>'
    + '<span class="sz' + (big ? ' big' : '') + '">' + human(t[1]) + '</span></a></li>';
}

function buildBrowse() {
  const groups = new Map();
  CATS.forEach((c, i) => {
    if (!groups.has(c[0])) groups.set(c[0], []);
    groups.get(c[0]).push({ idx: i, cat: c });
  });
  const order = [...groups.keys()].sort((a, b) => {
    const tail = x => (x === '未识别' || x === '其他') ? 1 : 0;
    if (tail(a) !== tail(b)) return tail(a) - tail(b);
    return sum(groups.get(b), 3) - sum(groups.get(a), 3);
  });
  function sum(list, i) { return list.reduce((s, x) => s + x.cat[i], 0); }

  let html = '';
  order.forEach(parent => {
    const subs = groups.get(parent);
    html += '<h2 class="group">' + parent + ' <span>· ' + sum(subs, 2)
      + ' 张 · ' + human(sum(subs, 3)) + '</span></h2><div class="grid">';
    subs.forEach(x => {
      html += '<details class="cat" data-cat="' + x.idx + '"><summary>'
        + '<span class="cat-name">' + x.cat[1] + '</span>'
        + '<span class="cat-meta">' + x.cat[2] + ' 张 · ' + human(x.cat[3]) + '</span>'
        + '</summary><ul></ul></details>';
    });
    html += '</div>';
  });

  const box = document.getElementById('browse');
  box.innerHTML = html;
  box.querySelectorAll('details.cat').forEach(d => {
    d.addEventListener('toggle', () => {
      if (!d.open) return;
      const ul = d.querySelector('ul');
      if (ul.dataset.loaded) return;
      ul.dataset.loaded = '1';
      const idx = +d.dataset.cat;
      const rows = T.filter(t => t[2] === idx).sort((a, b) => b[1] - a[1]);
      let h = rows.slice(0, LIMIT).map(itemHTML).join('');
      if (rows.length > LIMIT) {
        h += '<li class="more">仅显示最大的 ' + LIMIT + ' 条，共 ' + rows.length
          + ' 张 —— 用上方搜索按名字定位</li>';
      }
      ul.innerHTML = h;
    });
  });
}

const box = document.getElementById('result');
const input = document.getElementById('q');
let timer = null;

function runSearch() {
  const raw = input.value.trim();
  const browse = document.getElementById('browse');
  if (!raw) { box.hidden = true; browse.hidden = false; return; }
  browse.hidden = true;
  box.hidden = false;

  const terms = raw.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = T.filter(t => {
    const n = t[0].toLowerCase();
    return terms.every(k => n.indexOf(k) !== -1);
  }).sort((a, b) => {
    const ap = a[0].toLowerCase().startsWith(terms[0]) ? 0 : 1;
    const bp = b[0].toLowerCase().startsWith(terms[0]) ? 0 : 1;
    if (ap !== bp) return ap - bp;
    if (a[0].length !== b[0].length) return a[0].length - b[0].length;
    return b[1] - a[1];
  });

  if (!hits.length) {
    box.innerHTML = '<div class="results"><div class="empty">没有匹配 “'
      + raw.replace(/[<>&]/g, '') + '” 的表</div></div>';
    return;
  }
  let h = '<div class="results"><div class="more" style="border-bottom:1px solid var(--line)">'
    + '匹配 ' + hits.length + ' 张'
    + (hits.length > LIMIT ? '，显示前 ' + LIMIT + ' 条（按相关度排序）' : '') + '</div><ul>';
  h += hits.slice(0, LIMIT).map(t => {
    const c = CATS[t[2]];
    return '<li><a href="' + encodeURIComponent(t[0]) + '.html">'
      + '<span>' + t[0] + (t[1] >= BIG ? '<span class="badge">大</span>' : '')
      + ' <span class="path">' + c[0] + ' / ' + c[1] + '</span></span>'
      + '<span class="sz' + (t[1] >= BIG ? ' big' : '') + '">' + human(t[1]) + '</span></a></li>';
  }).join('');
  box.innerHTML = h + '</ul></div>';
}

input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(runSearch, 120); });
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); }
  if (e.key === 'Escape' && document.activeElement === input) {
    input.value = ''; runSearch(); input.blur();
  }
});

buildBrowse();
</script>
</body>
</html>
'''

if __name__ == '__main__':
    main()
