(() => {
  'use strict';
  const api = '/api/v1';
  let csrf = '';
  let accountDialog = null;
  let accountDialogContent = null;
  let accountInvoker = null;
  let accountParentPath = '';
  let accountCurrentUrl = '';
  const money = fen => `¥${(fen / 100).toFixed(2)}`;
  async function request(path, data, headers = {}) {
    const response = await fetch(api + path, {method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin',
      headers: {'Accept': 'application/json', ...(data === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRFToken': csrf}), ...headers},
      ...(data === undefined ? {} : {body: JSON.stringify(data)})});
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload) throw new Error(payload?.error?.message || '服务暂不可用，请稍后重试。');
    return payload;
  }
  async function session() { const state = await request('/session/'); csrf = state.csrf_token; window.dispatchEvent(new CustomEvent('tongjian-session', {detail: state})); return state; }
  function message(root, text, error = false) {
    const element = root.querySelector('.commerce-message');
    if (element) { element.textContent = text; element.classList.toggle('error', error); }
  }
  function busy(button, value) { if (button) button.disabled = value; }
  function loginUrl(next) { return '/account/login/?next=' + encodeURIComponent(next); }
  function supportsAccountDialog() {
    return window.parent === window && typeof HTMLDialogElement !== 'undefined' &&
      typeof HTMLDialogElement.prototype.showModal === 'function';
  }
  function ensureAccountDialog() {
    if (!supportsAccountDialog()) return null;
    if (accountDialog) return accountDialog;
    accountDialog = document.createElement('dialog');
    accountDialog.className = 'account-dialog';
    accountDialog.setAttribute('aria-labelledby', 'accountDialogTitle');
    accountDialog.innerHTML = '<div class="account-dialog-heading"><strong id="accountDialogTitle">资治通鉴账号</strong><button type="button" class="account-dialog-close" aria-label="关闭登录框">×</button></div><div class="account-dialog-content" aria-live="polite"><p class="account-dialog-loading">正在打开登录…</p></div>';
    document.body.appendChild(accountDialog);
    accountDialogContent = accountDialog.querySelector('.account-dialog-content');
    accountDialog.querySelector('.account-dialog-close').addEventListener('click', () => accountDialog.close());
    accountDialog.addEventListener('click', event => { if (event.target === accountDialog) accountDialog.close(); });
    accountDialog.addEventListener('close', () => {
      if (accountInvoker?.isConnected) accountInvoker.focus();
      accountInvoker = null;
    });
    accountDialog.addEventListener('click', event => {
      const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
      if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      let url;
      try { url = new URL(link.href, location.href); } catch { return; }
      if (url.origin !== location.origin || !/^\/account\//.test(url.pathname)) return;
      event.preventDefault();
      loadAccountPage(url.href);
    });
    accountDialog.addEventListener('submit', event => submitAccountForm(event));
    return accountDialog;
  }
  function closeAccountDialog() {
    accountDialog?.close();
    setupAccountNavigation();
  }
  function renderAccountPage(html, responseUrl) {
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    const main = parsed.querySelector('main');
    const panel = main?.querySelector('.account-panel');
    const content = panel || main;
    if (!content) throw new Error('登录页面暂时无法显示，请稍后重试。');
    for (const form of content.querySelectorAll('form')) {
      if (!form.hasAttribute('action')) form.setAttribute('action', responseUrl);
    }
    accountDialogContent.replaceChildren(content.cloneNode(true));
    accountCurrentUrl = responseUrl;
    accountDialogContent.scrollTop = 0;
    accountDialogContent.querySelector('input:not([type=hidden])')?.focus({preventScroll: true});
  }
  async function loadAccountPage(href, method = 'GET', body) {
    const target = new URL(href, location.href);
    if (target.origin !== location.origin) return;
    accountDialogContent.innerHTML = '<p class="account-dialog-loading">正在打开账号页面…</p>';
    try {
      const response = await fetch(target.href, {method, body, credentials: 'same-origin',
        headers: {'Accept': 'text/html'}, redirect: 'follow'});
      const html = await response.text();
      const finalUrl = new URL(response.url || target.href, location.href);
      if (response.redirected && (finalUrl.pathname === accountParentPath || finalUrl.pathname === '/account/')) {
        closeAccountDialog();
        return;
      }
      if (!response.headers.get('content-type')?.includes('text/html')) throw new Error('账号页面暂时无法显示，请稍后重试。');
      renderAccountPage(html, finalUrl.href);
    } catch (error) {
      const notice = document.createElement('p');
      notice.className = 'account-dialog-error';
      notice.setAttribute('role', 'alert');
      notice.textContent = error.message || '账号服务暂不可用，请稍后重试。';
      accountDialogContent.replaceChildren(notice);
    }
  }
  async function submitAccountForm(event) {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form || !accountDialogContent.contains(form)) return;
    event.preventDefault();
    const data = new FormData(form);
    if (event.submitter?.name) data.set(event.submitter.name, event.submitter.value);
    await loadAccountPage(form.action || accountCurrentUrl, (form.method || 'POST').toUpperCase(), data);
  }
  function openAccountModal(href, invoker) {
    const dialog = ensureAccountDialog();
    if (!dialog) { window.location.assign(href); return; }
    accountInvoker = invoker || document.activeElement;
    accountParentPath = location.pathname;
    if (!dialog.open) dialog.showModal();
    loadAccountPage(href);
  }
  function installAccountModalLinks() {
    if (!supportsAccountDialog()) return;
    document.addEventListener('click', event => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
      if (!link) return;
      let url;
      try { url = new URL(link.href, location.href); } catch { return; }
      if (url.origin !== location.origin || !/^\/account\/(?:login|register)\//.test(url.pathname)) return;
      event.preventDefault();
      openAccountModal(url.pathname + url.search + url.hash, link);
    });
  }
  function anchor(slug) { return sessionStorage.getItem(`article-anchor:${slug}`) || ''; }
  function clearKeys() {
    for (const key of Object.keys(sessionStorage)) if (key.startsWith('order-key:')) sessionStorage.removeItem(key);
  }
  async function setupAccountNavigation() {
    const links = document.querySelectorAll('[data-account-link]');
    const registerLinks = document.querySelectorAll('[data-register-link]');
    const panel = document.querySelector('[data-account-entry]');
    if (!links.length && !panel) return;
    try {
      const state = await session();
      const current = location.pathname + location.search + location.hash;
      const destination = !panel && current.startsWith('/') ? current : '/account/';
      const href = state.authenticated ? '/account/' : loginUrl(destination);
      links.forEach(link => {
        link.href = href;
        link.textContent = state.authenticated ? '我的账号' : '登录';
      });
      registerLinks.forEach(link => {
        link.href = '/account/register/?next=' + encodeURIComponent(destination);
        link.hidden = state.authenticated;
      });
      if (panel) {
        const button = panel.querySelector('[data-account-open]');
        button.href = href;
        button.hidden = false;
        button.textContent = state.authenticated ? '进入我的账号' : '登录';
        const register = panel.querySelector('[data-account-register]');
        if (register) register.hidden = state.authenticated;
        message(panel, state.authenticated ? '你已登录，可以管理账号或继续阅读。' : '通过邮箱验证码注册，以后使用邮箱和密码登录。');
      }
    } catch (error) {
      if (panel) {
        message(panel, '当前页面未连接账号与购买服务。年表、原文和免费试读仍可阅读。');
        if (['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)) {
          panel.querySelector('[data-local-service]').hidden = false;
        }
      }
    }
  }
  async function setupProduct(root) {
    const slug = root.dataset.product;
    const buy = root.querySelector('[data-buy]');
    try {
      const [product, state] = await Promise.all([request(`/products/${slug}/`), session()]);
      root.querySelector('.product-price').textContent = product.price_confirmed ? `${product.price_label ? product.price_label + ' ' : ''}${money(product.price_fen)} · 全文与 PDF` : '正式价格待公布 · 全文与 PDF';
      if (state.authenticated) {
        const owned = await request('/me/purchases/');
        if (owned.items.some(item => item.slug === slug)) {
          buy.textContent = '继续阅读全文'; buy.href = `/article/${slug}/` + window.location.hash;
          root.querySelector('[data-accept-terms]').closest('label').hidden = true;
          return;
        }
      }
      if (!product.sales_enabled && !state.verification_allowed) {
        buy.textContent = state.authenticated ? '查看我的购买' : '登录 / 注册';
        buy.href = state.authenticated ? '/account/purchases/' : loginUrl('/truth.html');
        message(root, '新购买暂未开放，仍可登录查看已购内容。');
        return;
      }
      buy.textContent = state.authenticated ? '购买完整专题' : '登录后购买';
      if (state.verification_allowed && !product.sales_enabled) message(root, '仅此账号开放商户验收，将实际扣款。');
      buy.addEventListener('click', async event => {
        event.preventDefault();
        sessionStorage.setItem(`article-anchor:${slug}`, window.location.hash);
        if (!state.authenticated) { openAccountModal(loginUrl('/truth.html' + window.location.hash), buy); return; }
        if (!root.querySelector('[data-accept-terms]').checked) { message(root, '请先阅读并同意购买说明。', true); return; }
        const ua = navigator.userAgent.toLowerCase();
        if (ua.includes('micromessenger')) { message(root, '请在系统浏览器中打开后购买。', true); return; }
        const scene = /android|iphone|ipad|mobile/.test(ua) ? 'h5' : 'native';
        if (!product.scenes.includes(scene)) { message(root, '当前设备暂不支持付款，请使用已支持的设备。', true); return; }
        const keyName = `order-key:${slug}:${product.revision}:${scene}`;
        const key = sessionStorage.getItem(keyName) || crypto.randomUUID(); sessionStorage.setItem(keyName, key);
        buy.setAttribute('aria-disabled', 'true');
        try {
          const order = await request('/orders/', {product: slug, revision: product.revision, scene, accept_terms: true}, {'Idempotency-Key': key});
          window.location.assign(order.checkout_url);
        } catch (error) { message(root, error.message, true); buy.removeAttribute('aria-disabled'); }
      });
    } catch (error) {
      root.querySelector('.product-price').textContent = '账号与购买服务未连接';
      buy.href = 'account.html';
      buy.textContent = '登录与购买说明';
      buy.removeAttribute('aria-disabled');
      message(root, '当前页面未连接账号与购买服务。点击上方按钮查看登录入口与服务状态，试读和原文阅读可以继续。');
    }
  }
  async function setupCheckout(root) {
    root.querySelector('[data-order-price]').textContent = money(Number(root.querySelector('[data-order-price]').dataset.fen));
    const id = root.dataset.orderId;
    let timer, count = 0;
    async function refresh() {
      try {
        const order = await request(`/orders/${id}/`);
        if (order.refund_status === 'succeeded') { clearTimeout(timer); clearKeys(); message(root, '退款已确认，此订单的阅读权益已撤销。'); return; }
        if (order.status === 'PAID') {
          clearTimeout(timer); clearKeys(); message(root, '付款已确认，可以继续阅读。');
          if (!root.querySelector('[data-read]')) {
            const link = document.createElement('a'); link.dataset.read = ''; link.className = 'purchase-button';
            link.href = order.article_url + anchor('truth'); link.textContent = '阅读全文'; root.appendChild(link);
          }
          return;
        }
        if (order.status === 'CLOSED') { clearTimeout(timer); clearKeys(); message(root, '订单已关闭。需要购买时请返回专题重新下单。'); return; }
        message(root, '正在等待渠道确认付款。');
        if (++count < 30) timer = setTimeout(refresh, 4000);
        else message(root, '暂未确认付款，可以稍后重新查询或到“我的购买”查看。');
      } catch (error) { message(root, error.message, true); }
    }
    root.querySelector('[data-refresh-order]').addEventListener('click', () => { clearTimeout(timer); count = 0; refresh(); });
    const simulate = root.querySelector('[data-simulate]');
    if (simulate) simulate.addEventListener('click', async () => {
      busy(simulate, true); try { await session(); await request(`/orders/${id}/simulate/`, {state: 'SUCCESS'}); clearTimeout(timer); await refresh(); }
      catch (error) { message(root, error.message, true); } finally { busy(simulate, false); }
    });
    window.addEventListener('pagehide', () => clearTimeout(timer));
    await refresh();
  }
  installAccountModalLinks();
  setupAccountNavigation();
  document.querySelectorAll('[data-captcha-refresh]').forEach(button => button.addEventListener('click', async event => {
    event.preventDefault();
    const form = button.closest('form');
    const status = form.querySelector('.captcha-status');
    const data = new URLSearchParams({captcha_id: form.elements.captcha_id.value});
    busy(button, true);
    status.textContent = '正在更换图片…';
    try {
      const response = await fetch(form.dataset.captchaRefreshUrl, {method: 'POST', credentials: 'same-origin',
        headers: {'X-CSRFToken': form.elements.csrfmiddlewaretoken.value, 'Accept': 'application/json'}, body: data});
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload) throw new Error(payload?.error?.message ||
        (response.status === 403 ? '页面验证已失效，请刷新页面后再试。' : '暂时无法更换图片，请稍后重试。'));
      form.elements.captcha_id.value = payload.id;
      form.elements.captcha.value = '';
      form.querySelector('[data-captcha-image]').src = payload.image_url;
      status.textContent = '图片已更换，请重新输入。';
      form.elements.captcha.focus();
    } catch (error) { status.textContent = error.message || '暂时无法更换图片，请稍后重试。'; }
    finally { busy(button, false); }
  }));
  window.addEventListener('pageshow', event => { if (event.persisted) setupAccountNavigation(); });
  document.querySelectorAll('[data-product]').forEach(setupProduct);
  document.querySelectorAll('[data-product-card]').forEach(async card => {
    try {
      const slug = card.dataset.productCard;
      const [product, state] = await Promise.all([request(`/products/${slug}/`), session()]);
      const label = card.querySelector('.commerce-label');
      label.textContent = product.price_confirmed ? `付费专题 · ${money(product.price_fen)} · 免费试读` : '付费专题 · 免费试读';
      if (state.authenticated) {
        const purchases = await request('/me/purchases/');
        if (purchases.items.some(item => item.slug === slug)) {
          label.textContent = '已购买 · 全文与 PDF'; card.href = `/article/${slug}/`;
          card.querySelector('.go').textContent = '继续阅读 →';
        }
      }
    } catch (error) { /* Public navigation stays usable when the buying service is offline. */ }
  });
  document.querySelectorAll('[data-checkout]').forEach(setupCheckout);
  document.querySelectorAll('[data-logout]').forEach(button => button.addEventListener('click', async () => {
    try { await session(); const result = await request('/auth/logout/', {}); window.location.assign(result.next); }
    catch (error) { message(document, error.message, true); }
  }));
})();
