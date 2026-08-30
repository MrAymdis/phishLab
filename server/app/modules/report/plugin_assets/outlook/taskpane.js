/* PhishLab 举报任务窗格：配置存 roamingSettings（随账号漫游），举报走 XHR POST /report/v1/mail。
   Outlook 2016 独立版 webview 为 IE11：全程 ES5 + XHR，无 Promise/箭头函数。 */
(function () {
  'use strict';
  var API_SUFFIX = '/report/v1/mail';

  var el = {
    server: document.getElementById('serverLabel'),
    report: document.getElementById('btnReport'),
    result: document.getElementById('result'),
    cfgJson: document.getElementById('cfgJson'),
    saveCfg: document.getElementById('btnSaveCfg'),
  };

  function showResult(ok, msg) {
    el.result.className = 'result ' + (ok ? 'ok' : 'err');
    el.result.textContent = msg;
  }

  function loadConfig() {
    var s = Office.context.roamingSettings;
    return {
      serverUrl: s.get('phishlabServerUrl') || '',
      apiKey: s.get('phishlabApiKey') || '',
    };
  }

  function refreshStatus() {
    var cfg = loadConfig();
    if (cfg.serverUrl && cfg.apiKey) {
      el.server.textContent = cfg.serverUrl;
      el.report.disabled = false;
    } else {
      el.server.textContent = '未配置';
      el.report.disabled = true;
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
    var s = Office.context.roamingSettings;
    s.set('phishlabServerUrl', String(cfg.serverUrl).replace(/\/+$/, ''));
    s.set('phishlabApiKey', String(cfg.apiKey));
    s.saveAsync(function (res) {
      if (res.status === Office.AsyncResultStatus.Succeeded) {
        showResult(true, '配置已保存');
        refreshStatus();
      } else {
        showResult(false, '配置保存失败：' + ((res.error && res.error.message) || '未知错误'));
      }
    });
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
    var item = Office.context.mailbox.item;
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
    // 邮件头需 ReadWriteMailbox 权限：尝试获取，失败静默跳过（headers 仅辅助溯源）
    if (item.getAllInternetHeadersAsync) {
      item.getAllInternetHeadersAsync(function (r) {
        if (r.status === Office.AsyncResultStatus.Succeeded) payload.headers = r.value;
        postReport(payload);
      });
    } else {
      postReport(payload);
    }
  }

  Office.onReady(function (info) {
    if (info.host !== Office.HostType.Outlook) return;
    refreshStatus();
    el.report.onclick = reportCurrentMail;
    el.saveCfg.onclick = saveConfig;
  });
})();
