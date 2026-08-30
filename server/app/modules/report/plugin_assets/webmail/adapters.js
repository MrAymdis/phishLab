/* PhishLab 网页邮箱采集适配器：URL 匹配 → 选择器链提取 → 附件抓取 → 合成 EML。
   分级降级（设计稿 §5）：
     L1 完整 EML（正文+附件 ≤8MB）
     L2 仅正文 EML（附件抓取失败/总体积超限）
     L3 纯元数据（页面未匹配/结构未命中/正文亦超限）
   选择器需按厂商真实环境校准（Coremail P0；Gmail/163 后续补）。 */
(function (global) {
  'use strict';

  var EML_LIMIT = 8 * 1024 * 1024;        // 与服务端 _EML_MAX_BYTES 一致（解码后）
  var ATT_LIMIT = 6 * 1024 * 1024;        // 单个附件抓取上限（防巨文件拖垮内存）
  var COLLECT_TIMEOUT_MS = 15000;

  /* ---------- 选择器链 ----------
     spec 格式：
       'css:SELECTOR'            → 第一个命中元素的文本
       'css:SELECTOR|attr:NAME'  → 第一个命中元素的属性
       'cssall:SELECTOR|attr:NAME' → 所有命中元素中首个非空值（跳过空值探测）
       'attr:NAME'               → itemEl 的属性（附件上下文）
       'title'                   → document.title
     数组 = 兜底链：逐个尝试，返回首个非空值。 */
  function _evalSpec(spec, doc, itemEl) {
    if (spec === 'title') return (doc.title || '').trim();
    if (spec.startsWith('attr:')) return (itemEl && itemEl.getAttribute(spec.slice(5)) || '').trim();
    var m = /^css(?:all)?:(.+?)(?:\|(?:attr|text):(.+))?$/.exec(spec);
    if (!m) return '';
    var sel = m[1], attr = m[2] || null, all = spec.startsWith('cssall:');
    var el = all ? null : doc.querySelector(sel);
    if (all) {
      var els = Array.from(doc.querySelectorAll(sel));
      for (var i = 0; i < els.length; i++) {
        var v = _pick(els[i], attr);
        if (v) return v;
      }
      return '';
    }
    return el ? _pick(el, attr) : '';
  }

  function _pick(el, attr) {
    if (!el) return '';
    if (attr) return (el.getAttribute(attr) || '').trim();
    return (el.textContent || '').trim();
  }

  function resolveChain(specs, doc, itemEl) {
    for (var i = 0; i < specs.length; i++) {
      var v = _evalSpec(specs[i], doc, itemEl);
      if (v) return v;
    }
    return '';
  }

  /* ---------- 厂商适配器 ---------- */
  var ADAPTERS = [
    {
      id: 'coremail',
      name: 'Coremail（论客 XT）',
      match: { url: ['/coremail/'] },
      /* Coremail XT 读信页通用结构；历史版本类名有差异，选择器链已带兜底。
         拿到客户真实 webmail 环境后校准（设计稿 §8-3）。 */
      fields: {
        from: ['css:#senderinfo', 'css:.senderinfo', 'css:.mail-from .value', 'css:.from-addr'],
        to: ['css:#receiverinfo', 'css:.receiverinfo', 'css:.mail-to .value'],
        cc: ['css:#ccinfo', 'css:.mail-cc .value'],
        subject: ['css:#subject', 'css:.subject', 'css:.mail-subject', 'title'],
        date: ['css:#mailinfo_date', 'css:.mailinfo_date', 'css:.mail-date'],
        bodyHtml: ['css:#contentDiv', 'css:.mailContent', 'css:.mail-content', 'css:#mailContent'],
      },
      attachments: {
        list: ['css:.attch-list .att-item', 'css:.att-list .att-item', 'css:.att-list li', 'css:.attachment-list .att-item'],
        name: ['css:.att-name', 'css:.file-name', 'css:a'],
        url: ['css:a|attr:href', 'attr:href'],
      },
    },
  ];

  function findAdapter() {
    var url = location.href;
    for (var i = 0; i < ADAPTERS.length; i++) {
      if (ADAPTERS[i].match.url.some(function (u) { return url.includes(u); })) return ADAPTERS[i];
    }
    return null;
  }

  /* ---------- 附件抓取（三态 URL） ----------
     同源 http(s)：content script 直抓（同源策略放行 + 自带登录态）
     跨域 http(s)：service worker 抓（host_permissions 豁免 CORS；token 通常在 URL 里）
     blob:：页面创建的 origin 内 URL，content script 可读 */
  async function fetchAttachment(url) {
    try {
      var resp;
      if (url.startsWith('blob:')) {
        resp = await fetch(url);
        if (!resp.ok) return null;
        var buf = new Uint8Array(await resp.arrayBuffer());
        if (buf.length > ATT_LIMIT) return null;
        return { bytes: buf, mime: (resp.headers.get('content-type') || '').split(';')[0].trim() };
      }
      var u = new URL(url);
      if (u.origin === location.origin) {
        resp = await fetch(url, { credentials: 'include' });
        if (!resp.ok) return null;
        var len = parseInt(resp.headers.get('content-length') || '0', 10);
        if (len && len > ATT_LIMIT) return null;
        var data = new Uint8Array(await resp.arrayBuffer());
        if (data.length > ATT_LIMIT) return null;
        return { bytes: data, mime: (resp.headers.get('content-type') || '').split(';')[0].trim() };
      }
      var res = await chrome.runtime.sendMessage({ type: 'phishlabFetch', url: url });
      if (!res || !res.ok) return null;
      var bin = atob(res.base64);
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      return { bytes: bytes, mime: (res.contentType || '').split(';')[0].trim() };
    } catch (e) {
      return null;
    }
  }

  /* ---------- 采集主流程 ---------- */
  async function collectCurrentMail() {
    var adapter = findAdapter();
    if (!adapter) return { level: 'L3', fields: {}, eml: null, warnings: ['页面未匹配邮件适配器（' + location.hostname + '）'] };

    var doc = document;
    var fields = {};
    var keys = Object.keys(adapter.fields);
    for (var k = 0; k < keys.length; k++) {
      fields[keys[k]] = resolveChain(adapter.fields[keys[k]], doc, null);
    }
    var bodyHtml = fields.bodyHtml || '';
    delete fields.bodyHtml;

    /* 附件列表：list 选择器链取首个非空集合 */
    var items = [];
    for (var s = 0; s < adapter.attachments.list.length; s++) {
      items = Array.from(doc.querySelectorAll(adapter.attachments.list[s]));
      if (items.length) break;
    }

    var attachments = [];
    var warnings = [];
    for (var i = 0; i < items.length; i++) {
      var name = resolveChain(adapter.attachments.name, doc, items[i]);
      var url = resolveChain(adapter.attachments.url, doc, items[i]);
      if (!url) { warnings.push('附件链接缺失'); continue; }
      if (!url.startsWith('blob:')) {
        try { url = new URL(url, location.href).href; } catch (e) { warnings.push('附件链接无效'); continue; }
      }
      var got = await fetchAttachment(url);
      if (!got) { warnings.push('附件抓取失败：' + (name || url.slice(0, 40))); continue; }
      attachments.push({ name: name || 'attachment', mime: got.mime, data: got.bytes });
    }

    var matched = fields.from || fields.subject || bodyHtml || attachments.length;
    if (!matched) {
      return { level: 'L3', fields: fields, eml: null, warnings: ['页面结构未命中（可能已改版），已按元数据上报'] };
    }

    var full = PhishLabEml.buildEml({
      from: fields.from, to: fields.to, cc: fields.cc,
      subject: fields.subject, date: fields.date,
      bodyHtml: bodyHtml, attachments: attachments,
    });
    if (full.length <= EML_LIMIT) {
      return { level: 'L1', fields: fields, eml: full, warnings: warnings };
    }
    /* L2：体积超限 → 剔除附件只传正文 */
    if (bodyHtml) {
      var bodyOnly = PhishLabEml.buildEml({
        from: fields.from, to: fields.to, cc: fields.cc,
        subject: fields.subject, date: fields.date, bodyHtml: bodyHtml,
      });
      if (bodyOnly.length <= EML_LIMIT) {
        warnings.push('体积超限（' + formatSize(full.length) + ' > 8MB），附件未归档');
        return { level: 'L2', fields: fields, eml: bodyOnly, warnings: warnings };
      }
      warnings.push('正文亦超 8MB，已按元数据上报');
    }
    return { level: 'L3', fields: fields, eml: null, warnings: warnings };
  }

  function formatSize(n) {
    if (n < 1024) return n + 'B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + 'KB';
    return (n / 1024 / 1024).toFixed(1) + 'MB';
  }

  var api = {
    ADAPTERS: ADAPTERS,
    EML_LIMIT: EML_LIMIT,
    ATT_LIMIT: ATT_LIMIT,
    COLLECT_TIMEOUT_MS: COLLECT_TIMEOUT_MS,
    findAdapter: findAdapter,
    collectCurrentMail: collectCurrentMail,
    resolveChain: resolveChain,
    _evalSpec: _evalSpec,
  };
  global.PhishLabAdapters = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
