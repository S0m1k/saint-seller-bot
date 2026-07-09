(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) {
    tg.ready();
    tg.expand();
    try { tg.setHeaderColor("bg_color"); } catch (e) {}
  }
  const INIT_DATA = tg ? tg.initData : "";

  // ------------------------------- API ------------------------------------
  async function api(path, opts = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-Telegram-Init-Data": INIT_DATA },
      opts.headers || {}
    );
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    if (!res.ok) {
      let msg = "Ошибка запроса";
      try { msg = (await res.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // ------------------------------ State -----------------------------------
  const state = {
    tab: "catalog",
    categories: [],
    brands: [],
    categoryId: null,
    brand: null,
    search: "",
    cartCount: 0,
  };

  const el = {
    view: document.getElementById("view"),
    chips: document.getElementById("category-chips"),
    search: document.getElementById("search-input"),
    searchRow: document.getElementById("search-row"),
    brandBtn: document.getElementById("brand-btn"),
    cartBadge: document.getElementById("cart-badge"),
    modal: document.getElementById("modal"),
    modalCard: document.getElementById("modal-card"),
    sheet: document.getElementById("sheet"),
    sheetCard: document.getElementById("sheet-card"),
    toast: document.getElementById("toast"),
    accountBtn: document.getElementById("account-btn"),
  };

  // ---------------------------- Helpers -----------------------------------
  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }
  function price(v) {
    if (v == null) return "по запросу";
    return `${Number(v).toLocaleString("ru-RU")} <span class="cur">₽</span>`;
  }
  function haptic(type = "light") {
    try { tg && tg.HapticFeedback.impactOccurred(type); } catch (e) {}
  }
  let toastTimer;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.add("hidden"), 1800);
  }
  function placeholder(p) {
    return (p.photos && p.photos[0]) ||
      "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='400'><rect width='100%' height='100%' fill='%23000'/></svg>";
  }

  // --------------------------- Catalog ------------------------------------
  async function loadFilters() {
    try {
      const [cats, brands] = await Promise.all([
        api("/api/categories"),
        api("/api/brands"),
      ]);
      state.categories = cats;
      state.brands = brands;
      renderChips();
    } catch (e) {
      renderAuthError(e);
      throw e;
    }
  }

  function renderChips() {
    const chips = [`<button class="chip ${state.categoryId === null ? "active" : ""}" data-cat="all">Все</button>`];
    for (const c of state.categories) {
      chips.push(
        `<button class="chip ${state.categoryId === c.id ? "active" : ""}" data-cat="${c.id}">${esc(c.name)} <span style="opacity:.6">${c.product_count}</span></button>`
      );
    }
    el.chips.innerHTML = chips.join("");
    el.chips.querySelectorAll("[data-cat]").forEach((b) => {
      b.onclick = () => {
        state.categoryId = b.dataset.cat === "all" ? null : Number(b.dataset.cat);
        renderChips();
        loadCatalog();
      };
    });
    el.brandBtn.textContent = state.brand ? `${state.brand} ✕` : "Бренд ▾";
    el.brandBtn.classList.toggle("active", !!state.brand);
  }

  function productCardHTML(p) {
    return `
      <article class="card" data-id="${p.id}">
        <div class="card-img">
          <img loading="lazy" src="${esc(placeholder(p))}" alt="${esc(p.name)}" />
          <button class="card-fav ${p.is_favorite ? "on" : ""}" data-fav="${p.id}" aria-label="В избранное">${p.is_favorite ? "❤️" : "🤍"}</button>
        </div>
        <div class="card-body">
          ${p.brand ? `<span class="card-brand">${esc(p.brand)}</span>` : ""}
          <span class="card-name">${esc(p.name)}</span>
          <span class="card-meta">${[p.size ? "р. " + esc(p.size) : "", esc(p.condition || "")].filter(Boolean).join(" · ")}</span>
          <span class="card-price">${price(p.price)}</span>
        </div>
      </article>`;
  }

  function bindProductCards(container) {
    container.querySelectorAll(".card").forEach((c) => {
      c.querySelector(".card-img img").onclick = () => openProduct(Number(c.dataset.id));
      c.querySelector(".card-name").onclick = () => openProduct(Number(c.dataset.id));
    });
    container.querySelectorAll("[data-fav]").forEach((b) => {
      b.onclick = (ev) => { ev.stopPropagation(); toggleFavorite(Number(b.dataset.fav), b); };
    });
  }

  async function loadCatalog() {
    el.view.innerHTML = `<div class="grid">${'<div class="skeleton"></div>'.repeat(6)}</div>`;
    const params = new URLSearchParams();
    if (state.categoryId !== null) params.set("category_id", state.categoryId);
    if (state.brand) params.set("brand", state.brand);
    if (state.search) params.set("search", state.search);
    try {
      const products = await api(`/api/products?${params.toString()}`);
      if (!products.length) {
        el.view.innerHTML = emptyHTML("🧦", "Ничего не найдено", "Попробуйте изменить фильтры или загляните позже.");
        return;
      }
      el.view.innerHTML = `<div class="grid">${products.map(productCardHTML).join("")}</div>`;
      bindProductCards(el.view);
    } catch (e) {
      renderAuthError(e);
    }
  }

  function emptyHTML(emoji, title, sub) {
    return `<div class="empty"><span class="emoji">${emoji}</span><h3>${esc(title)}</h3><p>${esc(sub || "")}</p></div>`;
  }

  function renderAuthError(e) {
    el.view.innerHTML = emptyHTML("🔒", "Требуется Telegram",
      (e && e.message) ? e.message : "Откройте приложение через кнопку в боте.");
  }

  // --------------------------- Product modal ------------------------------
  async function openProduct(id) {
    haptic();
    openModal(`<div class="modal-handle"></div><div style="padding:40px;text-align:center;color:var(--muted)">Загрузка…</div>`);
    try {
      const p = await api(`/api/products/${id}`);
      const gallery = (p.photos.length ? p.photos : [placeholder(p)])
        .map((u) => `<img src="${esc(u)}" alt="${esc(p.name)}" />`).join("");
      const specs = [
        p.brand && ["Бренд", p.brand],
        p.size && ["Размер", p.size],
        p.condition && ["Состояние", p.condition],
      ].filter(Boolean).map(([k, v]) => `<div class="spec"><b>${esc(k)}</b>${esc(v)}</div>`).join("");

      el.modalCard.innerHTML = `
        <div class="modal-handle"></div>
        <div class="gallery">${gallery}</div>
        <div class="modal-body">
          ${p.brand ? `<div class="modal-brand">${esc(p.brand)}</div>` : ""}
          <h2 class="modal-title">${esc(p.name)}</h2>
          <div class="modal-price">${price(p.price)}</div>
          <div class="spec-list">${specs}</div>
          ${p.description ? `<div class="modal-desc">${esc(p.description)}</div>` : ""}
          <div class="modal-actions">
            <button class="btn fav-toggle ${p.is_favorite ? "on" : ""}" id="m-fav">${p.is_favorite ? "❤️" : "🤍"}</button>
            <button class="btn btn-primary" id="m-cart">${p.in_cart ? "✓ В корзине" : "В корзину"}</button>
          </div>
        </div>`;

      const favBtn = document.getElementById("m-fav");
      favBtn.classList.add("btn-ghost");
      favBtn.onclick = () => toggleFavorite(p.id, favBtn);
      document.getElementById("m-cart").onclick = async (ev) => {
        await addToCart(p.id);
        ev.target.textContent = "✓ В корзине";
      };
    } catch (e) {
      el.modalCard.innerHTML = `<div class="modal-handle"></div>${emptyHTML("😕", "Не удалось загрузить", e.message)}`;
    }
  }

  function openModal(html) {
    el.modalCard.innerHTML = html;
    el.modal.classList.remove("hidden");
  }
  function closeModal() { el.modal.classList.add("hidden"); }

  // ---------------------------- Favorites ---------------------------------
  async function toggleFavorite(id, btn) {
    haptic();
    const isOn = btn.classList.contains("on") || btn.textContent.includes("❤");
    try {
      if (isOn) {
        await api(`/api/favorites/${id}`, { method: "DELETE" });
      } else {
        await api(`/api/favorites/${id}`, { method: "POST" });
      }
      // Обновить все элементы этого товара на экране
      document.querySelectorAll(`[data-fav="${id}"]`).forEach((b) => {
        b.classList.toggle("on", !isOn);
        b.textContent = !isOn ? "❤️" : "🤍";
      });
      const mFav = document.getElementById("m-fav");
      if (mFav) { mFav.classList.toggle("on", !isOn); mFav.textContent = !isOn ? "❤️" : "🤍"; }
      toast(!isOn ? "Добавлено в избранное" : "Убрано из избранного");
      if (state.tab === "favorites") loadFavorites();
    } catch (e) { toast(e.message); }
  }

  async function loadFavorites() {
    el.view.innerHTML = `<h2 class="section-title">Избранное</h2><div class="grid">${'<div class="skeleton"></div>'.repeat(4)}</div>`;
    try {
      const products = await api("/api/favorites");
      if (!products.length) {
        el.view.innerHTML = `<h2 class="section-title">Избранное</h2>` +
          emptyHTML("🤍", "Пока пусто", "Отмечайте товары сердечком — они появятся здесь.");
        return;
      }
      el.view.innerHTML = `<h2 class="section-title">Избранное</h2><div class="grid">${products.map(productCardHTML).join("")}</div>`;
      bindProductCards(el.view);
    } catch (e) { renderAuthError(e); }
  }

  // ------------------------------- Cart -----------------------------------
  function updateCartBadge(count) {
    state.cartCount = count;
    if (count > 0) {
      el.cartBadge.textContent = count;
      el.cartBadge.classList.remove("hidden");
    } else {
      el.cartBadge.classList.add("hidden");
    }
  }

  async function refreshCartCount() {
    try {
      const cart = await api("/api/cart");
      updateCartBadge(cart.items.reduce((s, i) => s + i.quantity, 0));
    } catch (e) {}
  }

  async function addToCart(id) {
    haptic("medium");
    try {
      const cart = await api(`/api/cart/${id}`, { method: "POST" });
      updateCartBadge(cart.items.reduce((s, i) => s + i.quantity, 0));
      toast("Добавлено в корзину");
    } catch (e) { toast(e.message); }
  }

  function cartRowHTML(item) {
    const p = item.product;
    return `
      <div class="cart-row" data-id="${p.id}">
        <img class="cart-thumb" src="${esc(placeholder(p))}" alt="${esc(p.name)}" />
        <div class="cart-info">
          ${p.brand ? `<span class="card-brand">${esc(p.brand)}</span>` : ""}
          <span class="card-name">${esc(p.name)}</span>
          <span class="card-price">${price(p.price)}</span>
          <div class="qty">
            <button data-dec="${p.id}">−</button>
            <span>${item.quantity}</span>
            <button data-inc="${p.id}">+</button>
          </div>
          <button class="cart-remove" data-rm="${p.id}">Удалить</button>
        </div>
      </div>`;
  }

  function renderCart(cart) {
    if (!cart.items.length) {
      el.view.innerHTML = `<h2 class="section-title">Корзина</h2>` +
        emptyHTML("🛒", "Корзина пуста", "Добавьте товары из каталога.");
      return;
    }
    el.view.innerHTML =
      `<h2 class="section-title">Корзина</h2>${cart.items.map(cartRowHTML).join("")}
       <div class="summary">
         <div class="summary-total"><span>Итого</span><b>${price(cart.total)}</b></div>
         <button class="btn btn-primary" id="checkout">Оформить заказ</button>
       </div>`;

    el.view.querySelectorAll("[data-inc]").forEach((b) => b.onclick = () => changeQty(Number(b.dataset.inc), +1));
    el.view.querySelectorAll("[data-dec]").forEach((b) => b.onclick = () => changeQty(Number(b.dataset.dec), -1));
    el.view.querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => removeFromCart(Number(b.dataset.rm)));
    document.getElementById("checkout").onclick = openCheckout;
  }

  async function loadCart() {
    el.view.innerHTML = `<h2 class="section-title">Корзина</h2><p style="color:var(--muted)">Загрузка…</p>`;
    try {
      const cart = await api("/api/cart");
      updateCartBadge(cart.items.reduce((s, i) => s + i.quantity, 0));
      renderCart(cart);
    } catch (e) { renderAuthError(e); }
  }

  let cartCache = null;
  async function changeQty(id, delta) {
    haptic();
    const row = el.view.querySelector(`.cart-row[data-id="${id}"] .qty span`);
    const current = row ? Number(row.textContent) : 1;
    const next = current + delta;
    try {
      const cart = await api(`/api/cart/${id}`, { method: "PATCH", body: JSON.stringify({ quantity: next }) });
      updateCartBadge(cart.items.reduce((s, i) => s + i.quantity, 0));
      renderCart(cart);
    } catch (e) { toast(e.message); }
  }

  async function removeFromCart(id) {
    haptic();
    try {
      const cart = await api(`/api/cart/${id}`, { method: "DELETE" });
      updateCartBadge(cart.items.reduce((s, i) => s + i.quantity, 0));
      renderCart(cart);
    } catch (e) { toast(e.message); }
  }

  // ---------------------------- Checkout ----------------------------------
  async function openCheckout() {
    const me = await api("/api/me").catch(() => ({}));
    openSheet(`
      <div class="sheet-title">Оформление заказа</div>
      <div class="field">
        <label>Контакт для связи (телефон или @username)</label>
        <input id="co-contact" type="text" value="${esc(me.phone || "")}" placeholder="+7 999 000-00-00" />
      </div>
      <div class="field">
        <label>Комментарий к заказу (необязательно)</label>
        <textarea id="co-comment" placeholder="Пожелания, вопросы по размеру и т.д."></textarea>
      </div>
      <button class="btn btn-primary" id="co-submit">Отправить заказ</button>
      <p style="color:var(--muted);font-size:12px;text-align:center;margin-top:12px">
        После отправки продавец свяжется с вами для подтверждения.
      </p>
    `);
    document.getElementById("co-submit").onclick = submitOrder;
  }

  async function submitOrder() {
    const btn = document.getElementById("co-submit");
    btn.disabled = true;
    btn.textContent = "Отправка…";
    const contact = document.getElementById("co-contact").value.trim();
    const comment = document.getElementById("co-comment").value.trim();
    try {
      await api("/api/orders", { method: "POST", body: JSON.stringify({ contact, comment }) });
      closeSheet();
      updateCartBadge(0);
      haptic("heavy");
      try { tg && tg.HapticFeedback.notificationOccurred("success"); } catch (e) {}
      switchTab("orders");
      toast("Заказ отправлен! 🎉");
    } catch (e) {
      btn.disabled = false;
      btn.textContent = "Отправить заказ";
      toast(e.message);
    }
  }

  // ----------------------------- Orders -----------------------------------
  async function loadOrders() {
    el.view.innerHTML = `<h2 class="section-title">Мои заказы</h2><p style="color:var(--muted)">Загрузка…</p>`;
    try {
      const orders = await api("/api/orders");
      if (!orders.length) {
        el.view.innerHTML = `<h2 class="section-title">Мои заказы</h2>` +
          emptyHTML("🧾", "Заказов пока нет", "Оформите первый заказ из корзины.");
        return;
      }
      const html = orders.map((o) => `
        <div class="order">
          <div class="order-head">
            <span class="order-id">Заказ #${o.id}</span>
            <span class="order-status">${esc(o.status_label)}</span>
          </div>
          ${o.items.map((it) => `<div class="order-item">${esc(it.product_name)}${it.size ? " · р." + esc(it.size) : ""} ×${it.quantity}</div>`).join("")}
          <div class="order-total">Итого: ${price(o.total)}</div>
          <div class="order-item" style="margin-top:6px">${new Date(o.created_at).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</div>
        </div>`).join("");
      el.view.innerHTML = `<h2 class="section-title">Мои заказы</h2>${html}`;
    } catch (e) { renderAuthError(e); }
  }

  // --------------------------- Account sheet ------------------------------
  async function openAccount() {
    const me = await api("/api/me").catch(() => ({}));
    const name = [me.first_name, me.last_name].filter(Boolean).join(" ") || "Гость";
    openSheet(`
      <div class="sheet-title">Профиль</div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <div class="brand-mark" style="width:48px;height:48px;font-size:18px">${esc((me.first_name || "S")[0])}</div>
        <div>
          <div style="font-weight:800;font-size:17px">${esc(name)}</div>
          <div style="color:var(--muted);font-size:13px">${me.username ? "@" + esc(me.username) : "id " + esc(me.telegram_id || "—")}</div>
        </div>
      </div>
      <div class="field">
        <label>Телефон (сохранится для заказов)</label>
        <input id="acc-phone" type="tel" value="${esc(me.phone || "")}" placeholder="+7 999 000-00-00" />
      </div>
      <button class="btn btn-primary" id="acc-save">Сохранить</button>
    `);
    document.getElementById("acc-save").onclick = async () => {
      const phone = document.getElementById("acc-phone").value.trim();
      try {
        await api("/api/me", { method: "PATCH", body: JSON.stringify({ phone }) });
        closeSheet();
        toast("Сохранено");
      } catch (e) { toast(e.message); }
    };
  }

  // ---------------------------- Brand sheet -------------------------------
  function openBrandFilter() {
    if (state.brand) { // если бренд выбран — клик по кнопке сбрасывает
      state.brand = null; renderChips(); loadCatalog(); return;
    }
    if (!state.brands.length) { toast("Брендов пока нет"); return; }
    const options = [`<button class="brand-option ${!state.brand ? "active" : ""}" data-brand="">Все бренды</button>`]
      .concat(state.brands.map((b) => `<button class="brand-option ${state.brand === b ? "active" : ""}" data-brand="${esc(b)}">${esc(b)}</button>`));
    openSheet(`<div class="sheet-title">Фильтр по бренду</div>${options.join("")}`);
    el.sheetCard.querySelectorAll("[data-brand]").forEach((b) => {
      b.onclick = () => {
        state.brand = b.dataset.brand || null;
        closeSheet(); renderChips(); loadCatalog();
      };
    });
  }

  // ------------------------- Sheet / modal ctrl ---------------------------
  function openSheet(html) { el.sheetCard.innerHTML = html; el.sheet.classList.remove("hidden"); }
  function closeSheet() { el.sheet.classList.add("hidden"); }

  document.querySelectorAll("[data-close]").forEach((b) => b.onclick = closeModal);
  document.querySelectorAll("[data-close-sheet]").forEach((b) => b.onclick = closeSheet);

  // ------------------------------ Tabs ------------------------------------
  function switchTab(tab) {
    state.tab = tab;
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
    const showCatalogControls = tab === "catalog";
    el.searchRow.classList.toggle("hidden", !showCatalogControls);
    el.chips.classList.toggle("hidden", !showCatalogControls);
    window.scrollTo(0, 0);
    if (tab === "catalog") loadCatalog();
    else if (tab === "favorites") loadFavorites();
    else if (tab === "cart") loadCart();
    else if (tab === "orders") loadOrders();
  }

  document.querySelectorAll(".tab").forEach((t) => t.onclick = () => { haptic(); switchTab(t.dataset.tab); });
  el.brandBtn.onclick = openBrandFilter;
  el.accountBtn.onclick = openAccount;

  let searchTimer;
  el.search.oninput = () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = el.search.value.trim(); loadCatalog(); }, 350);
  };

  // ------------------------------ Boot ------------------------------------
  (async function boot() {
    try {
      await loadFilters();
      await loadCatalog();
      refreshCartCount();
    } catch (e) {
      // ошибка авторизации уже показана
    }
  })();
})();
