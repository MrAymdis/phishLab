/* PhishLab 网页邮箱合成 EML 构建器（纯函数，无 DOM/浏览器依赖，Node 可单测）。
   输出 message/rfc822 字节：头字段 RFC 2047 encoded-word、正文/附件 base64、附件名 RFC 2231。
   设计稿：docs/举报插件网页邮箱EML合成方案.md */
(function (global) {
  'use strict';

  var CRLF = '\r\n';

  function utf8(s) { return new TextEncoder().encode(s); }

  /* Uint8Array → base64（分块 fromCharCode，防大数组栈溢出） */
  function toBase64(bytes) {
    var chunk = 0x8000, out = '';
    for (var i = 0; i < bytes.length; i += chunk) {
      out += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(out);
  }

  /* RFC 2047 B 编码：超长按 48 字符切段（必须为 4 的倍数，保持 base64 分组完整） */
  function encWord(text) {
    var b64 = toBase64(utf8(text));
    var chunks = [];
    for (var i = 0; i < b64.length; i += 48) chunks.push(b64.slice(i, i + 48));
    return chunks.map(function (c) { return '=?UTF-8?B?' + c + '?='; }).join(' ');
  }

  /* 纯 ASCII 直出；含非 ASCII 整串编码 */
  function headValue(text) {
    if (!text) return '';
    return /[^\x00-\x7f]/.test(text) ? encWord(text) : text;
  }

  /* 地址头：分离「显示名 <地址>」，只编码显示名；其余按 headValue */
  function addressValue(text) {
    if (!text) return '';
    var m = /^\s*(.*?)\s*<([^<>]*)>\s*$/.exec(text.trim());
    if (m) {
      var name = m[1], addr = m[2];
      if (!addr) return headValue(text);
      if (/[^\x00-\x7f]/.test(name)) name = encWord(name);
      return name ? name + ' <' + addr + '>' : addr;
    }
    return headValue(text);
  }

  /* 头折行：只在空格处折（encoded-word 段间天然有空格，不会拦腰截断） */
  function foldHeader(name, value) {
    var first = name + ': ' + value;
    if (first.length <= 78) return first;
    var words = first.split(' ');
    var lines = [], cur = '';
    words.forEach(function (w) {
      var limit = lines.length ? 74 : 78;
      if (cur && cur.length + 1 + w.length > limit) {
        lines.push(cur);
        cur = w;
      } else {
        cur = cur ? cur + ' ' + w : w;
      }
    });
    if (cur) lines.push(cur);
    return lines.join(CRLF + ' ');
  }

  /* RFC 5987/2231 文件名编码：encodeURIComponent 后补 !'()* 的百分号化 */
  function pctEncode(name) {
    return encodeURIComponent(name).replace(/[!'()*]/g, function (c) {
      return '%' + c.charCodeAt(0).toString(16).toUpperCase();
    });
  }

  function randHex(n) {
    var bytes = new Uint8Array(n);
    var cryptoObj = globalThis.crypto
      || (typeof require === 'function' ? require('crypto').webcrypto : null); // Node 18 无 crypto 全局
    if (!cryptoObj) throw new Error('crypto unavailable');
    cryptoObj.getRandomValues(bytes);
    var hex = '';
    for (var i = 0; i < n; i++) hex += bytes[i].toString(16).padStart(2, '0');
    return hex;
  }

  /**
   * 合成一封 multipart/mixed 邮件。
   * opts: { from, to, cc, subject, date, bodyHtml, attachments: [{ name, mime, data: Uint8Array }] }
   * 返回 Uint8Array（RFC822 字节，CRLF 行尾）。
   */
  function buildEml(opts) {
    var boundary = '=pl.' + randHex(16); // 16 位随机足够唯一；再长则 Content-Type 行超 78 字节
    var head = [
      foldHeader('From', addressValue(opts.from || 'unknown@unknown.invalid')),
      foldHeader('To', addressValue(opts.to || 'undisclosed-recipients:;')),
    ];
    if (opts.cc) head.push(foldHeader('Cc', addressValue(opts.cc)));
    head.push(foldHeader('Subject', headValue(opts.subject || '')));
    head.push(foldHeader('Date', opts.date || new Date().toUTCString()));
    head.push('X-PhishLab-Source: webmail-synthesis');
    head.push('MIME-Version: 1.0');
    head.push('Content-Type: multipart/mixed; boundary="' + boundary + '"');

    var parts = [];
    if (opts.bodyHtml) {
      parts.push(
        '--' + boundary + CRLF +
        'Content-Type: text/html; charset="utf-8"' + CRLF +
        'Content-Transfer-Encoding: base64' + CRLF + CRLF +
        toBase64(utf8(opts.bodyHtml)) + CRLF
      );
    }
    (opts.attachments || []).forEach(function (att) {
      var name = att.name || 'attachment';
      var mime = att.mime || 'application/octet-stream';
      /* ASCII 名走 filename="..."；非 ASCII 只发 filename*（RFC 2231/6266）。
         注意：同时带 filename 与 filename* 时 Python email（平台预览）会优先取 filename，
         故非 ASCII 名不附带 plain filename。 */
      var plain = /[^\x00-\x7f]/.test(name) ? null : name.replace(/["\\\r\n]/g, '_');
      var disp = plain !== null
        ? 'attachment; filename="' + plain + '"'
        : 'attachment; filename*=utf-8\'\'' + pctEncode(name);
      parts.push(
        '--' + boundary + CRLF +
        'Content-Type: ' + mime + CRLF +
        'Content-Transfer-Encoding: base64' + CRLF +
        'Content-Disposition: ' + disp + CRLF +
        CRLF +
        toBase64(att.data || new Uint8Array(0)) + CRLF
      );
    });

    var text = head.join(CRLF) + CRLF + CRLF + parts.join('') + '--' + boundary + '--' + CRLF;
    return utf8(text);
  }

  var api = {
    buildEml: buildEml,
    toBase64: toBase64,
    encWord: encWord,
    addressValue: addressValue,
    foldHeader: foldHeader,
    pctEncode: pctEncode,
  };
  global.PhishLabEml = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
