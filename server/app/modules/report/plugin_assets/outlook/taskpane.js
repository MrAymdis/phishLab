/* PhishLab 举报任务窗格：配置存 roamingSettings（随账号漫游）+ localStorage 兜底，举报走 XHR POST /report/v1/mail。
   Outlook 2016 独立版 webview 为 IE11：全程 ES5 + XHR，无 Promise/箭头函数。
   所有失败路径都显示到页面上——按钮「一直灰色」必须能看出原因。 */
(function () {
  'use strict';
  var API_SUFFIX = '/report/v1/mail';
  var LS_SERVER = 'phishlabServerUrl';
  var LS_KEY = 'phishlabApiKey';

  var el = {
    server: document.getElementById('serverLabel'),
    report: document.getElementById('btnReport'),
    hint: document.getElementById('btnHint'),
    result: document.getElementById('result'),
    cfgJson: document.getElementById('cfgJson'),
    saveCfg: document.getElementById('btnSaveCfg'),
  };

  function showResult(ok, msg) {
    el.result.className = 'result ' + (ok ? 'ok' : 'err');
    el.result.textContent = msg;
  }

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

  function loadConfig() {
    var r = getRoaming(), l = getLocal();
    return { serverUrl: r.serverUrl || l.serverUrl, apiKey: r.apiKey || l.apiKey };
  }

  function refreshStatus() {
    try {
      var cfg = loadConfig();
      if (cfg.serverUrl && cfg.apiKey) {
        el.server.textContent = cfg.serverUrl;
        el.report.disabled = false;
        if (el.hint) el.hint.textContent = '点击按钮将当前邮件提交至平台研判';
      } else {
        el.server.textContent = '未配置';
        el.report.disabled = true;
        if (el.hint) el.hint.textContent = '请在下方粘贴管理员下发的引导配置 JSON，点「保存配置」后按钮即可使用';
      }
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
    // 先落 localStorage（同步生效，按钮立即解锁）；roamingSettings 随账号漫游为增强项，失败不阻断
    try {
      window.localStorage.setItem(LS_SERVER, serverUrl);
      window.localStorage.setItem(LS_KEY, apiKey);
    } catch (e) { /* localStorage 不可用时仅靠 roamingSettings */ }
    try {
      var s = Office.context.roamingSettings;
      s.set(LS_SERVER, serverUrl);
      s.set(LS_KEY, apiKey);
      s.saveAsync(function (res) {
        if (res.status !== Office.AsyncResultStatus.Succeeded) {
          showResult(false, '云端配置同步失败（本次仍可用）：' + ((res.error && res.error.message) || '未知错误'));
        }
      });
    } catch (e) { /* roamingSettings 不可用：仅本地生效 */ }
    refreshStatus();
    showResult(true, '配置已保存，服务器：' + serverUrl);
  }

  function postReport(payload) {
    var cfg = loadConfig();
    if (!window.confirm('确认将当前邮件提交至 PhishLab 平台研判？')) return;
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

  function bindUI() {
    el.report.onclick = reportCurrentMail;
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
