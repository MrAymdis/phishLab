/* PhishLab 举报任务窗格：配置存 roamingSettings（随账号漫游）+ localStorage/Cookie 兜底，
   举报走 XHR POST /report/v1/mail。Outlook 2016 独立版 webview 为 IE11：全程 ES5 + XHR。
   设计原则：
   - 会话级配置（memCfg）立即生效——所有持久化通道都失败时，本次窗口内仍可举报；
   - 所有失败路径显示到页面上（含存储自检），按钮「点不了」必须能看出原因；
   - 不用 window.confirm（部分 webview 被策略屏蔽会静默返回 false），按钮二次点击确认。 */
(function () {
  'use strict';
  var API_SUFFIX = '/report/v1/mail';
  var LS_SERVER = 'phishlabServerUrl';
  var LS_KEY = 'phishlabApiKey';
  var COOKIE_NAME = 'phishlabCfg';

  var memCfg = null; // 会话内配置：存储全不可用时本次会话仍可举报

  var el = {
    server: document.getElementById('serverLabel'),
    report: document.getElementById('btnReport'),
    hint: document.getElementById('btnHint'),
    diag: document.getElementById('diag'),
    result: document.getElementById('result'),
    cfgJson: document.getElementById('cfgJson'),
    saveCfg: document.getElementById('btnSaveCfg'),
  };

  function showResult(ok, msg) {
    el.result.className = 'result ' + (ok ? 'ok' : 'err');
    el.result.textContent = msg;
  }

  // ---------- 持久化通道（逐一 try-catch，互不影响） ----------

  function getRoaming() {
    try {
      var s = Office.context.roamingSettings;
      return s ? { serverUrl: s.get(LS_SERVER) || '', apiKey: s.get(LS_KEY) || '' }
               : { serverUrl: '', apiKey: '' };
    } catch (e) { return { serverUrl: '', apiKey: '' }; }
  }

  function getLocal() {
    try {
      return { serverUrl: window.localStorage.getItem(LS_SERVER) || '',
               apiKey: window.localStorage.getItem(LS_KEY) || '' };
    } catch (e) { return { serverUrl: '', apiKey: '' }; }
  }

  function getCookie() {
    try {
      var m = new RegExp('(?:^|; )' + COOKIE_NAME + '=([^;]*)').exec(document.cookie);
      if (!m) return { serverUrl: '', apiKey: '' };
      var c = JSON.parse(decodeURIComponent(m[1]));
      return { serverUrl: c.serverUrl || '', apiKey: c.apiKey || '' };
    } catch (e) { return { serverUrl: '', apiKey: '' }; }
  }

  function loadConfig() {
    if (memCfg && memCfg.serverUrl && memCfg.apiKey) return memCfg;
    var r = getRoaming();
    if (r.serverUrl && r.apiKey) return r;
    var l = getLocal();
    if (l.serverUrl && l.apiKey) return l;
    var c = getCookie();
    if (c.serverUrl && c.apiKey) return c;
    return { serverUrl: '', apiKey: '' };
  }

  function writeLocal(serverUrl, apiKey) {
    try {
      window.localStorage.setItem(LS_SERVER, serverUrl);
      window.localStorage.setItem(LS_KEY, apiKey);
      return true;
    } catch (e) { return false; }
  }

  function writeCookie(serverUrl, apiKey) {
    try {
      document.cookie = COOKIE_NAME + '=' +
        encodeURIComponent(JSON.stringify({ serverUrl: serverUrl, apiKey: apiKey })) +
        ';max-age=15552000;path=/';
      return true;
    } catch (e) { return false; }
  }

  function storageDiag() {
    var localOk = false;
    try {
      window.localStorage.setItem('phishlabDiag', '1');
      window.localStorage.removeItem('phishlabDiag');
      localOk = true;
    } catch (e) { /* 被禁 */ }
    var cookieOk = false;
    try {
      document.cookie = 'phishlabDiag=1;path=/';
      cookieOk = new RegExp('(?:^|; )phishlabDiag=1').test(document.cookie);
    } catch (e) { /* 被禁 */ }
    var roamingOk = false;
    try { roamingOk = !!Office.context.roamingSettings; } catch (e) { /* 被禁 */ }
    return '本地存储:' + (localOk ? '√' : '×') +
           ' Cookie:' + (cookieOk ? '√' : '×') +
           ' 漫游:' + (roamingOk ? '√' : '×');
  }

  // ---------- 状态与配置 ----------

  function refreshStatus() {
    try {
      var cfg = loadConfig();
      if (cfg.serverUrl && cfg.apiKey) {
        el.server.textContent = cfg.serverUrl;
        el.report.disabled = false;
        if (el.hint) el.hint.textContent = '点击按钮两次确认后提交';
      } else {
        el.server.textContent = '未配置';
        el.report.disabled = true;
        if (el.hint) el.hint.textContent = '请在下方粘贴管理员下发的引导配置 JSON，点「保存配置」后按钮即可使用';
      }
      if (el.diag) el.diag.textContent = '存储自检：' + storageDiag();
    } catch (e) {
      showResult(false, '状态读取异常：' + (e && e.message ? e.message : e));
    }
  }

  function saveConfig() {
    var cfg;
    try {
      cfg = JSON.parse(el.cfgJson.value);
    } catch (e) {
      showResult(false, '配置 JSON 解析失败，请粘贴完整文件内容');
      return;
    }
    if (!cfg || !cfg.serverUrl || !cfg.apiKey) {
      showResult(false, '配置缺少 serverUrl / apiKey 字段');
      return;
    }
    var serverUrl = String(cfg.serverUrl).replace(/\/+$/, '');
    var apiKey = String(cfg.apiKey);
    memCfg = { serverUrl: serverUrl, apiKey: apiKey }; // 会话级：立即生效，不依赖任何存储
    var note = [];
    note.push(writeLocal(serverUrl, apiKey) ? '本地已存' : '本地存储不可用');
    writeCookie(serverUrl, apiKey); // 尽力而为，不报错
    try {
      var s = Office.context.roamingSettings;
      if (s) {
        s.set(LS_SERVER, serverUrl);
        s.set(LS_KEY, apiKey);
        s.saveAsync(function (res) {
          if (res.status !== Office.AsyncResultStatus.Succeeded) {
            showResult(false, '云端漫游保存失败（本次会话仍可用）：' +
              ((res.error && res.error.message) || '未知错误'));
          }
        });
        note.push('漫游同步已提交');
      } else {
        note.push('漫游不可用');
      }
    } catch (e) { note.push('漫游不可用'); }
    refreshStatus();
    showResult(true, '配置已保存，服务器：' + serverUrl + '（' + note.join('；') + '）');
  }

  // ---------- 举报 ----------

  function postReport(payload) {
    var cfg = loadConfig();
    el.report.disabled = true;
    el.report.textContent = '提交中…';
    var xhr = new XMLHttpRequest();
    xhr.open('POST', cfg.serverUrl + API_SUFFIX, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-Api-Key', cfg.apiKey);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      el.report.disabled = false;
      el.report.textContent = '举报当前邮件';
      var msg = '举报提交失败，请稍后重试';
      var ok = false;
      try {
        var body = JSON.parse(xhr.responseText || '{}');
        if (body && typeof body.code === 'number') {
          ok = body.code === 0;
          msg = body.message || (ok ? '举报成功，感谢您的反馈' : '提交失败');
        } else if (xhr.status === 200) {
          ok = true;
          msg = '举报成功，感谢您的反馈';
        }
      } catch (e) { /* 非 JSON 响应按失败处理 */ }
      showResult(ok, msg);
    };
    xhr.onerror = function () {
      el.report.disabled = false;
      el.report.textContent = '举报当前邮件';
      showResult(false, '网络错误，无法连接平台服务器');
    };
    xhr.send(JSON.stringify(payload));
  }

  function reportCurrentMail() {
    var item;
    try { item = Office.context.mailbox.item; } catch (e) { item = null; }
    if (!item) {
      showResult(false, '未获取到当前邮件：请先选中一封邮件，再打开「举报可疑邮件」');
      return;
    }
    var payload = {
      channel: 'outlook_plugin',
      reporter_email: null,
      message_id: item.internetMessageId || null,
      from_addr: (item.from && item.from.emailAddress) || null,
      subject: item.subject || null,
    };
    try {
      var profile = Office.context.mailbox.userProfile;
      if (profile && profile.emailAddress) payload.reporter_email = profile.emailAddress;
    } catch (e) { /* 老客户端无 profile，域名白名单校验时以其他字段兜底 */ }
    // 邮件头需 ReadWriteMailbox 权限：尝试获取，失败静默跳过（EML 归档会服务端回填）
    if (item.getAllInternetHeadersAsync) {
      item.getAllInternetHeadersAsync(function (r) {
        if (r.status === Office.AsyncResultStatus.Succeeded) payload.headers = r.value;
        attachEml(payload);
      });
    } else {
      attachEml(payload);
    }
  }

  function attachEml(payload) {
    // getAsFileAsync：Mailbox 1.14+（新版 Microsoft 365）；老客户端无此方法/失败 → 元数据上报
    var item = Office.context.mailbox.item;
    if (item.getAsFileAsync) {
      item.getAsFileAsync(function (r) {
        if (r.status === Office.AsyncResultStatus.Succeeded && r.value &&
            r.value.length < 11 * 1024 * 1024) {
          payload.eml_base64 = r.value; // 服务端解码上限 8MB（base64 约 10.7MB），留余量
        }
        postReport(payload);
      });
    } else {
      postReport(payload);
    }
  }

  // 不用 window.confirm（部分 webview 被策略屏蔽会静默返回 false）：按钮二次点击确认，5 秒超时复位
  var confirmArmed = false;
  var confirmTimer = null;

  function handleReportClick() {
    if (!confirmArmed) {
      confirmArmed = true;
      el.report.textContent = '再点一次确认提交';
      showResult(true, '确认举报：请在 5 秒内再次点击按钮提交');
      confirmTimer = setTimeout(function () {
        confirmArmed = false;
        el.report.textContent = '举报当前邮件';
      }, 5000);
      return;
    }
    confirmArmed = false;
    clearTimeout(confirmTimer);
    el.report.textContent = '举报当前邮件';
    reportCurrentMail();
  }

  // ---------- 初始化 ----------

  function bindUI() {
    el.report.onclick = handleReportClick;
    el.saveCfg.onclick = saveConfig;
    refreshStatus();
  }

  var officeReady = false;
  // Office.js 初始化可能因网络（appsforoffice.microsoft.com 不可达）长时间不完成：8 秒兜底提示
  setTimeout(function () {
    if (!officeReady) {
      showResult(false, 'Office 初始化超时：请确认本机可访问 appsforoffice.microsoft.com 后重开任务窗格');
    }
  }, 8000);

  Office.onReady(function (info) {
    officeReady = true;
    if (info.host !== Office.HostType.Outlook) {
      showResult(false, '该加载项仅支持 Outlook 客户端');
      return;
    }
    bindUI();
  });
})();
