/* PhishLab Web 邮箱举报 content script：
   页面右下角悬浮「举报」按钮 → 弹层确认（主题预填 document.title）→ 后台 service worker 提交。
   全部 UI 走 Shadow DOM，隔离邮箱页面样式。 */
(() => {
  const CONFIG_KEY = 'phishlab_config';
  const EMAIL_KEY = 'phishlab_reporter_email';
  let reporterEmail = '';

  chrome.storage.local.get([CONFIG_KEY, EMAIL_KEY], (res) => {
    const cfg = res[CONFIG_KEY];
    if (cfg && cfg.serverUrl && cfg.apiKey) {
      reporterEmail = res[EMAIL_KEY] || '';
      injectButton();
    }
  });

  function injectButton() {
    if (document.getElementById('pl_report_root')) return;
    const host = document.createElement('div');
    host.id = 'pl_report_root';
    host.style.cssText = 'position:fixed;right:22px;bottom:140px;z-index:2147483647;';
    const shadow = host.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        button {
          display:flex;align-items:center;gap:6px;padding:10px 16px;font-size:14px;color:#fff;
          background:#378ADD;border:none;border-radius:24px;cursor:pointer;
          box-shadow:0 4px 14px rgba(55,138,221,.45);font-family:inherit;
        }
        button:hover { background:#2f77c0; }
        button:disabled { background:#a5c8e8; cursor:not-allowed; }
      </style>
      <button id="btn" title="将当前邮件提交至 PhishLab 平台">🚩 举报</button>
    `;
    document.documentElement.appendChild(host);
    shadow.getElementById('btn').addEventListener('click', () => openDialog(shadow));
  }

  function toast(shadow, ok, text) {
    const t = document.createElement('div');
    t.textContent = text;
    t.style.cssText = `position:fixed;right:22px;bottom:${ok ? '196px' : '196px'};z-index:2147483647;
      padding:10px 16px;border-radius:8px;font-size:13px;color:#fff;
      background:${ok ? '#0e9f6e' : '#e02424'};box-shadow:0 4px 14px rgba(0,0,0,.25);`;
    shadow.appendChild(t);
    setTimeout(() => t.remove(), 5000);
  }

  function openDialog(shadow) {
    if (shadow.getElementById('dialog')) return;
    const subject = (document.title || '').trim();
    const overlay = document.createElement('div');
    overlay.id = 'dialog';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483646;background:rgba(15,23,42,.45);display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = `
      <style>
        .card { width:400px;max-width:92vw;background:#fff;border-radius:12px;padding:18px;font-family:"Microsoft YaHei",sans-serif;color:#1f2937; }
        h3 { margin:0 0 4px;font-size:15px; }
        .sub { font-size:12px;color:#6b7280;margin-bottom:12px; }
        label { display:block;font-size:12px;color:#374151;margin:10px 0 4px; }
        input { width:100%;padding:8px 10px;font-size:13px;border:1px solid #d1d5db;border-radius:6px;box-sizing:border-box; }
        .row { display:flex;gap:10px;margin-top:14px; }
        .ok { flex:1;padding:9px 0;font-size:13px;color:#fff;background:#378ADD;border:none;border-radius:6px;cursor:pointer; }
        .ok:disabled { background:#a5c8e8;cursor:not-allowed; }
        .cancel { padding:9px 16px;font-size:13px;color:#6b7280;background:#f3f4f6;border:none;border-radius:6px;cursor:pointer; }
      </style>
      <div class="card">
        <h3>举报可疑邮件</h3>
        <div class="sub">提交后由安全团队研判：演练邮件可获积分，真实钓鱼即时告警</div>
        <label>举报人邮箱（必填）</label>
        <input id="f_email" placeholder="yourname@company.com"/>
        <label>发件人（选填）</label>
        <input id="f_from" placeholder="如 hr-department@phishing.com"/>
        <label>主题</label>
        <input id="f_subject"/>
        <div class="row">
          <button class="ok" id="f_ok">确认举报</button>
          <button class="cancel" id="f_cancel">取消</button>
        </div>
      </div>
    `;
    shadow.appendChild(overlay);

    const email = overlay.querySelector('#f_email');
    const from = overlay.querySelector('#f_from');
    const subjectIn = overlay.querySelector('#f_subject');
    const ok = overlay.querySelector('#f_ok');
    email.value = reporterEmail;
    subjectIn.value = subject;
    email.focus();

    const close = () => overlay.remove();
    overlay.querySelector('#f_cancel').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

    ok.addEventListener('click', () => {
      const em = email.value.trim();
      if (!em || !em.includes('@')) {
        toast(shadow, false, '请填写举报人邮箱');
        email.focus();
        return;
      }
      reporterEmail = em;
      chrome.storage.local.set({ [EMAIL_KEY]: em });
      ok.disabled = true;
      ok.textContent = '提交中…';
      chrome.runtime.sendMessage({
        type: 'phishlabReport',
        payload: {
          channel: 'webmail',
          reporter_email: em,
          from_addr: from.value.trim() || null,
          subject: subjectIn.value.trim() || null,
          message_id: null, // Web 页面取不到邮件头，精确匹配由平台二期支持
        },
      }, (res) => {
        ok.disabled = false;
        ok.textContent = '确认举报';
        const r = res || { ok: false, message: '扩展后台无响应，请刷新页面重试' };
        toast(shadow, r.ok, r.message);
        if (r.ok) close();
      });
    });
  }
})();
