/* PhishLab Web 邮箱举报：弹窗配置管理（chrome.storage.local）。 */
const CONFIG_KEY = 'phishlab_config';

const statusEl = document.getElementById('status');
const cfgEl = document.getElementById('cfg');

function renderStatus(cfg) {
  if (cfg && cfg.serverUrl && cfg.apiKey) {
    statusEl.className = 'status ok';
    statusEl.textContent = '已配置：' + cfg.serverUrl + '（允许域名：' + (cfg.allowedDomains || []).join('、') + '）';
  } else {
    statusEl.className = 'status empty';
    statusEl.textContent = '未配置：请导入管理员下发的引导配置 JSON';
  }
}

chrome.storage.local.get(CONFIG_KEY, (res) => {
  renderStatus(res[CONFIG_KEY]);
  if (res[CONFIG_KEY]) cfgEl.value = JSON.stringify(res[CONFIG_KEY], null, 2);
});

document.getElementById('save').addEventListener('click', () => {
  let cfg;
  try {
    cfg = JSON.parse(cfgEl.value);
  } catch (e) {
    statusEl.className = 'status empty';
    statusEl.textContent = 'JSON 解析失败，请粘贴完整文件内容';
    return;
  }
  if (!cfg || !cfg.serverUrl || !cfg.apiKey) {
    statusEl.className = 'status empty';
    statusEl.textContent = '配置缺少 serverUrl / apiKey 字段';
    return;
  }
  chrome.storage.local.set({ [CONFIG_KEY]: cfg }, () => renderStatus(cfg));
});

document.getElementById('clear').addEventListener('click', () => {
  chrome.storage.local.remove(CONFIG_KEY, () => {
    cfgEl.value = '';
    renderStatus(null);
  });
});
