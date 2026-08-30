/* PhishLab 网页邮箱合成 EML 测试 harness：Node 侧构建产物，pytest 侧用 Python email 解析回环校验。
   用法：node webmail_eml_harness.js（cwd = plugin_assets/webmail），stdout 输出 JSON 结果。 */
'use strict';
const path = require('path');
const ASSETS = path.resolve(__dirname, '..', 'app/modules/report/plugin_assets/webmail');
const Eml = require(path.join(ASSETS, 'eml.js'));
const Adapters = require(path.join(ASSETS, 'adapters.js'));

const out = {};

/* ---- 1. 中文/附件完整回环 ---- */
const utf8 = (s) => new TextEncoder().encode(s);
const roundtrip = Eml.buildEml({
  from: '张三 <zhangsan@corp.com>',
  to: 'victim@corp.com',
  cc: '李四 <lisi@corp.com>',
  subject: '紧急：账号验证通知（八月）',
  date: 'Sat, 29 Aug 2026 09:00:00 +0800',
  bodyHtml: '<p>请点击<a href="http://evil.example">链接</a>验证。</p>',
  attachments: [
    { name: '八月工资单.xlsx', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', data: utf8('excel-bytes') },
    { name: '报告.txt', mime: 'text/plain', data: utf8('hello 附件') },
  ],
});
out.roundtrip = { emlB64: Eml.toBase64(roundtrip) };

/* ---- 2. 纯 ASCII 头字段不编码 ---- */
const ascii = Eml.buildEml({
  from: 'hr@corp.com', to: 'staff@corp.com', subject: 'Salary Slip',
  bodyHtml: '<p>plain ascii body</p>',
});
out.ascii = { emlB64: Eml.toBase64(ascii) };

/* ---- 3. 超长主题折行（每物理行 ≤ 78 字节）---- */
const LONG_SUBJECT = ('紧急通知' + '这是一段用于测试折行逻辑的重复文本').repeat(20); // 300 字符
const folded = Eml.buildEml({
  from: 'hr@corp.com', to: 'staff@corp.com', subject: LONG_SUBJECT, bodyHtml: '<p>x</p>',
});
out.fold = { emlB64: Eml.toBase64(folded), subject: LONG_SUBJECT };

/* ---- 4. 选择器链求值（fake DOM）---- */
const el = (text, attrs) => ({ textContent: text, getAttribute: (n) => (attrs || {})[n] || '' });
const fakeDoc = {
  title: '测试标题',
  querySelector: (sel) => {
    const map = {
      '.a': null,
      '.b': el('B text'),
      '.x': el('link', { href: 'http://x/a' }),
      '.empty1': el('   '),
    };
    return map[sel] || null;
  },
  querySelectorAll: (sel) => {
    const map = {
      '.m': [el('', { href: '' }), el('', { href: 'first-non-empty' })],
      '.none': [],
    };
    return map[sel] || [];
  },
};
const itemEl = el('item', { href: 'item-href' });
out.chain = {
  firstHit: Adapters.resolveChain(['css:.a', 'css:.b'], fakeDoc),
  attr: Adapters.resolveChain(['css:.x|attr:href'], fakeDoc),
  itemAttr: Adapters.resolveChain(['attr:href'], fakeDoc, itemEl),
  title: Adapters.resolveChain(['title'], fakeDoc),
  cssallFirst: Adapters.resolveChain(['cssall:.m|attr:href'], fakeDoc),
  blankSkip: Adapters.resolveChain(['css:.empty1', 'css:.b'], fakeDoc),
  empty: Adapters.resolveChain(['css:.none', 'cssall:.none|attr:href'], fakeDoc),
};

/* ---- 5. 附件无 mime 时回退 octet-stream / 非 ASCII 名 RFC2231 ---- */
const fallback = Eml.buildEml({
  from: 'a@b.com', to: 'c@d.com', subject: 'x', bodyHtml: '<p>x</p>',
  attachments: [{ name: '附件.bin', data: utf8('bin-data') }],
});
out.fallback = { emlB64: Eml.toBase64(fallback) };

process.stdout.write(JSON.stringify(out));
