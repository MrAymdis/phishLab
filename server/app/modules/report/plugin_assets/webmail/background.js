/* PhishLab Web 邮箱举报 service worker（MV3）：
   举报请求在后台发起——host_permissions 覆盖平台域名，豁免页面 CORS 限制。 */
const CONFIG_KEY = 'phishlab_config';
const API_SUFFIX = '/report/v1/mail';

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === 'phishlabReport') {
    doReport(msg.payload).then(sendResponse);
    return true; // 异步响应
  }
});

async function doReport(payload) {
  const stored = await chrome.storage.local.get(CONFIG_KEY);
  const cfg = stored[CONFIG_KEY];
  if (!cfg || !cfg.serverUrl || !cfg.apiKey) {
    return { ok: false, message: '扩展未配置：请点击工具栏 PhishLab 图标，导入管理员下发的引导配置 JSON' };
  }
  try {
    const r = await fetch(String(cfg.serverUrl).replace(/\/+$/, '') + API_SUFFIX, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Api-Key': String(cfg.apiKey) },
      body: JSON.stringify(payload),
    });
    const body = await r.json().catch(() => ({}));
    // 业务码约定：HTTP 200 且 code=0 才算成功；域名白名单/重复上报等以 code≠0 返回
    const ok = r.ok && body.code === 0;
    return { ok, message: body.message || (ok ? '举报成功，感谢您的反馈' : '举报提交失败') };
  } catch (e) {
    return { ok: false, message: '无法连接平台服务器：' + e.message };
  }
}
