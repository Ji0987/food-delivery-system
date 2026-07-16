// 餐點外送系統｜消費者頁面邏輯
import {
  api,
  auth,
  ApiError,
  money,
  toast,
  el,
  ORDER_STATUS_LABEL,
  PAYMENT_STATUS_LABEL,
} from "./api.js";

// 訂單主流程順序（不含終止態 rejected / cancelled）
const FLOW = [
  "pending",
  "accepted",
  "preparing",
  "ready_for_pickup",
  "picked_up",
  "delivering",
  "delivered",
  "completed",
];
const TERMINAL = new Set(["completed", "cancelled", "rejected"]);

const state = {
  cart: null,
  currentRestaurant: null,
  pollTimer: null,
  pollingOrderId: null,
  lastStatus: null,
  deliveryMap: null,
  deliveryMapOrderId: null,
};

const $ = (id) => document.getElementById(id);

function showView(name) {
  document
    .querySelectorAll(".view")
    .forEach((v) => v.classList.toggle("is-active", v.id === `view-${name}`));
  // 離開訂單詳情頁時停止輪詢
  if (name !== "order-detail") stopPolling();
}

// ---------------- 認證 ----------------
let authMode = "login";

function setAuthMode(mode) {
  authMode = mode;
  document
    .querySelectorAll(".auth-tabs button")
    .forEach((b) => b.classList.toggle("is-active", b.dataset.mode === mode));
  $("nameField").hidden = mode === "login";
  $("pwHint").hidden = mode === "login";
  $("authTitle").textContent = mode === "login" ? "歡迎回來" : "建立帳號";
  $("authSubmit").textContent = mode === "login" ? "登入" : "註冊並登入";
  $("f-password").setAttribute(
    "autocomplete",
    mode === "login" ? "current-password" : "new-password",
  );
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const email = $("f-email").value.trim();
  const password = $("f-password").value;
  const name = $("f-name").value.trim();
  const btn = $("authSubmit");

  if (!email || !password) {
    toast("請填寫 Email 與密碼", "err");
    return;
  }
  if (authMode === "register" && !name) {
    toast("請填寫姓名", "err");
    return;
  }

  btn.disabled = true;
  try {
    let registeredUser = null;
    if (authMode === "register") {
      registeredUser = await api.register({
        email,
        password,
        role: "consumer",
        name,
      });
    }
    const tokenRes = await api.login(email, password);
    const user = tokenRes.user || registeredUser;
    if (!user || user.role !== "consumer") {
      throw new ApiError(403, "請使用消費者帳號登入此頁面");
    }
    auth.save(tokenRes.access_token, user);
    toast(authMode === "register" ? "註冊成功，已登入" : "登入成功", "ok");
    await enterApp();
  } catch (err) {
    toast(err instanceof ApiError ? err.detail : String(err), "err");
  } finally {
    btn.disabled = false;
  }
}

function logout() {
  auth.clear();
  stopPolling();
  state.cart = null;
  $("userLabel").textContent = "";
  $("ordersBtn").hidden = true;
  $("logoutBtn").hidden = true;
  $("cartFab").hidden = true;
  $("f-email").value = "";
  $("f-password").value = "";
  $("f-name").value = "";
  showView("auth");
}

// ---------------- 進入 App ----------------
async function enterApp() {
  const user = auth.user;
  if (!user || user.role !== "consumer") {
    auth.clear();
    throw new ApiError(403, "請使用消費者帳號登入消費者頁面");
  }
  $("userLabel").textContent = user?.name ? `${user.name}` : user?.email || "";
  $("ordersBtn").hidden = false;
  $("logoutBtn").hidden = false;
  await refreshCart();
  if (!auth.isLoggedIn) return;
  await loadRestaurants();
  if (!auth.isLoggedIn) return;
  showView("restaurants");
}

// ---------------- 餐廳 ----------------
async function loadRestaurants() {
  const host = $("restaurantList");
  host.innerHTML = "";
  host.appendChild(el("div", { class: "spinner" }));
  try {
    const list = await api.listRestaurants();
    host.innerHTML = "";
    if (!list.length) {
      host.appendChild(emptyState("🍽️", "目前沒有可瀏覽的餐廳"));
      return;
    }
    for (const r of list) {
      host.appendChild(
        el("button", { class: "rcard", onClick: () => openMenu(r.id) }, [
          el("div", { class: "rcard__name", text: r.name }),
          el("div", {
            class: "rcard__desc",
            text: r.description || "　",
          }),
          el("div", {
            class: "rcard__meta",
            text: r.address ? `📍 ${r.address}` : "點擊查看菜單",
          }),
        ]),
      );
    }
  } catch (err) {
    host.innerHTML = "";
    host.appendChild(emptyState("⚠️", errText(err)));
    handleAuthError(err);
  }
}

// ---------------- 菜單 ----------------
async function openMenu(restaurantId) {
  showView("menu");
  const host = $("menuList");
  host.innerHTML = "";
  host.appendChild(el("div", { class: "spinner" }));
  try {
    const data = await api.getMenu(restaurantId);
    state.currentRestaurant = data.restaurant;
    $("menuRestaurantName").textContent = data.restaurant.name;
    $("menuRestaurantDesc").textContent = data.restaurant.description || "";

    host.innerHTML = "";
    if (!data.items.length) {
      host.appendChild(emptyState("📭", "這間餐廳還沒有餐點"));
      return;
    }
    const card = el("div", { class: "card" });
    for (const item of data.items) {
      card.appendChild(renderMenuItem(item));
    }
    host.appendChild(card);
  } catch (err) {
    host.innerHTML = "";
    host.appendChild(emptyState("⚠️", errText(err)));
    handleAuthError(err);
  }
}

function renderMenuItem(item) {
  const soldOut = item.is_sold_out;
  const right = soldOut
    ? el("span", { class: "badge badge--soldout", text: "已售罄" })
    : el(
        "button",
        {
          class: "btn btn--primary btn--sm",
          onClick: (e) => addToCart(item, e.currentTarget),
        },
        "加入",
      );

  return el(
    "div",
    { class: `menu-item${soldOut ? " is-soldout" : ""}` },
    [
      el("div", { class: "menu-item__body" }, [
        el("div", { class: "menu-item__name" }, [item.name]),
        item.description
          ? el("div", { class: "menu-item__desc", text: item.description })
          : null,
      ]),
      el("div", { class: "menu-item__price", text: money(item.price) }),
      right,
    ],
  );
}

async function addToCart(item, btn) {
  btn.disabled = true;
  try {
    state.cart = await api.addToCart(item.id, 1);
    renderCart();
    toast(`已加入「${item.name}」`, "ok", 1600);
    bumpCartFab();
  } catch (err) {
    toast(errText(err), "err");
    handleAuthError(err);
  } finally {
    btn.disabled = false;
  }
}

// ---------------- 購物車 ----------------
async function refreshCart() {
  try {
    state.cart = await api.getCart();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleAuthError(err);
    state.cart = { items: [], total_amount: "0.00" };
  }
  renderCart();
}

function cartItemCount() {
  if (!state.cart) return 0;
  return state.cart.items.reduce((sum, i) => sum + i.quantity, 0);
}

function renderCart() {
  const count = cartItemCount();
  $("cartFab").hidden = count === 0 && !isCartOpen();
  $("cartCount").textContent = count;

  const body = $("cartBody");
  body.innerHTML = "";
  if (!state.cart || !state.cart.items.length) {
    body.appendChild(emptyState("🛒", "購物車是空的"));
    $("cartTotal").textContent = "NT$ 0.00";
    $("checkoutBtn").disabled = true;
    return;
  }
  $("checkoutBtn").disabled = false;

  for (const line of state.cart.items) {
    body.appendChild(renderCartLine(line));
  }
  $("cartTotal").textContent = money(state.cart.total_amount);
}

function renderCartLine(line) {
  const soldOut = line.is_sold_out;
  return el("div", { class: "cart-line" }, [
    el("div", { class: "cart-line__body" }, [
      el("div", { class: "cart-line__name" }, [
        line.name,
        soldOut
          ? el("span", {
              class: "badge badge--soldout",
              text: "已售罄",
              style: "margin-left:6px",
            })
          : null,
      ]),
      el("div", { class: "muted small", text: money(line.unit_price) }),
    ]),
    el("div", { class: "qty" }, [
      el("button", {
        text: "−",
        onClick: () => changeQty(line, line.quantity - 1),
      }),
      el("span", { text: String(line.quantity) }),
      el("button", {
        text: "+",
        onClick: () => changeQty(line, line.quantity + 1),
      }),
    ]),
    el("div", {
      class: "menu-item__price",
      text: money(line.subtotal),
      style: "min-width:76px;text-align:right",
    }),
  ]);
}

async function changeQty(line, nextQty) {
  try {
    if (nextQty <= 0) {
      state.cart = await api.removeCartItem(line.id);
    } else {
      state.cart = await api.updateCartItem(line.id, nextQty);
    }
    renderCart();
  } catch (err) {
    toast(errText(err), "err");
    handleAuthError(err);
  }
}

function openCart() {
  $("cartBackdrop").classList.add("is-open");
  $("cartDrawer").classList.add("is-open");
  $("cartFab").hidden = true;
}
function closeCart() {
  $("cartBackdrop").classList.remove("is-open");
  $("cartDrawer").classList.remove("is-open");
  renderCart();
}
function isCartOpen() {
  return $("cartDrawer").classList.contains("is-open");
}
function bumpCartFab() {
  const fab = $("cartFab");
  fab.classList.remove("pulse");
  void fab.offsetWidth;
  fab.classList.add("pulse");
}

// ---------------- 下單 ----------------
async function checkout() {
  const btn = $("checkoutBtn");
  btn.disabled = true;
  try {
    const order = await api.createOrder();
    toast("訂單已建立，付款完成（模擬）", "ok");
    state.cart = { items: [], total_amount: "0.00" };
    renderCart();
    closeCart();
    openOrderDetail(order.id);
  } catch (err) {
    toast(errText(err), "err");
    handleAuthError(err);
  } finally {
    btn.disabled = false;
  }
}

// ---------------- 訂單列表 ----------------
async function loadOrders() {
  showView("orders");
  const host = $("orderList");
  host.innerHTML = "";
  host.appendChild(el("div", { class: "spinner" }));
  try {
    const orders = await api.listOrders();
    host.innerHTML = "";
    if (!orders.length) {
      host.appendChild(emptyState("🧾", "還沒有任何訂單"));
      return;
    }
    for (const o of orders) {
      host.appendChild(
        el("button", { class: "order-row", onClick: () => openOrderDetail(o.id) }, [
          el("div", { style: "flex:1" }, [
            el("div", { class: "order-row__id", text: `訂單 #${o.id}` }),
            el("div", {
              class: "order-row__meta",
              text: `${o.items.length} 項餐點・${money(o.total_amount)}`,
            }),
          ]),
          statusBadge(o.status),
        ]),
      );
    }
  } catch (err) {
    host.innerHTML = "";
    host.appendChild(emptyState("⚠️", errText(err)));
    handleAuthError(err);
  }
}

// ---------------- 訂單詳情 + 輪詢 ----------------
async function openOrderDetail(orderId) {
  showView("order-detail");
  stopPolling();
  state.pollingOrderId = orderId;
  state.lastStatus = null;
  const host = $("orderDetail");
  host.innerHTML = "";
  host.appendChild(el("div", { class: "spinner" }));

  const order = await fetchAndRenderOrder(orderId, host, true);
  if (order && !TERMINAL.has(order.status)) startPolling(orderId);
}

async function fetchAndRenderOrder(orderId, host, first = false) {
  try {
    const order = await api.getOrder(orderId);
    // 狀態變化時的網頁內即時提醒（對應已確認決策）
    if (!first && state.lastStatus && state.lastStatus !== order.status) {
      toast(`訂單狀態更新：${ORDER_STATUS_LABEL[order.status]}`, "info", 3200);
    }
    state.lastStatus = order.status;
    renderOrderDetail(order, host);
    if (TERMINAL.has(order.status)) stopPolling();
    return order;
  } catch (err) {
    if (first) {
      host.innerHTML = "";
      host.appendChild(emptyState("⚠️", errText(err)));
    }
    handleAuthError(err);
    return null;
  }
}

function renderOrderDetail(order, host) {
  destroyDeliveryMap();
  host.innerHTML = "";

  host.appendChild(
    el("div", { class: "order-head" }, [
      el("div", { style: "flex:1" }, [
        el("div", { class: "order-head__id", text: `訂單 #${order.id}` }),
        el("div", {
          class: "muted small",
          text: `建立於 ${formatTime(order.created_at)}`,
        }),
      ]),
      statusBadge(order.status),
    ]),
  );

  // 付款狀態
  const pay = order.payment;
  const paymentBadgeKind =
    pay.status === "paid" ? "paid" : pay.status === "refunded" ? "refunded" : "unpaid";
  host.appendChild(
    el(
      "div",
      { style: "padding:14px 18px;border-bottom:1px solid var(--border)" },
      [
        el("div", { class: "row-gap" }, [
          el("span", { class: "muted small", text: "付款狀態" }),
          el("span", {
            class: `badge badge--${paymentBadgeKind}`,
            text: PAYMENT_STATUS_LABEL[pay.status] || pay.status,
          }),
          el("span", {
            class: "muted small",
            text: money(pay.amount),
            style: "margin-left:auto",
          }),
        ]),
      ],
    ),
  );

  if (pay.status === "refunded" && pay.refunded_at) {
    host.appendChild(
      el("div", {
        class: "payment-note",
        text: `模擬退款完成於 ${formatTime(pay.refunded_at)}`,
      }),
    );
  }

  // 狀態時間軸（終止態特別處理）
  host.appendChild(renderTimeline(order.status));

  // 訂單明細
  const itemsWrap = el("div", { style: "padding:14px 18px" }, [
    el("div", {
      class: "muted small",
      text: "訂單明細",
      style: "margin-bottom:8px",
    }),
  ]);
  for (const it of order.items) {
    itemsWrap.appendChild(
      el("div", { class: "order-line" }, [
        el("span", {}, [`${it.item_name_snapshot} × ${it.quantity}`]),
        el("span", {
          style: "font-variant-numeric:tabular-nums",
          text: money(it.subtotal),
        }),
      ]),
    );
  }
  itemsWrap.appendChild(
    el(
      "div",
      { class: "summary-row", style: "margin-top:12px" },
      [
        el("span", { class: "muted", text: "總計" }),
        el("span", { class: "total", text: money(order.total_amount) }),
      ],
    ),
  );
  host.appendChild(itemsWrap);

  // 僅在配送中顯示地圖；定位資料仍由 API 權限與訂單狀態雙重保護。
  if (order.status === "delivering") {
    host.appendChild(renderDeliveryTracking(order.id));
    void refreshDeliveryMap(order.id);
  }

  // 消費者可執行的動作
  const actions = consumerActions(order);
  if (actions) host.appendChild(actions);
}

function renderTimeline(status) {
  const wrap = el("div", { class: "timeline" });

  if (status === "cancelled" || status === "rejected") {
    wrap.appendChild(
      el("div", { class: "timeline__step is-current" }, [
        el("div", { class: "timeline__dot" }),
        el("div", {}, [
          el("div", {
            class: "timeline__label",
            text: ORDER_STATUS_LABEL[status],
          }),
          el("div", {
            class: "muted small",
            text: status === "cancelled" ? "訂單已取消" : "餐廳已拒單",
          }),
        ]),
      ]),
    );
    return wrap;
  }

  const currentIdx = FLOW.indexOf(status);
  FLOW.forEach((s, idx) => {
    let cls = "timeline__step is-pending";
    if (idx < currentIdx) cls = "timeline__step is-done";
    else if (idx === currentIdx) cls = "timeline__step is-current";
    wrap.appendChild(
      el("div", { class: cls }, [
        el("div", { class: "timeline__dot" }),
        el("div", {}, [
          el("div", { class: "timeline__label", text: ORDER_STATUS_LABEL[s] }),
        ]),
      ]),
    );
  });
  return wrap;
}

function consumerActions(order) {
  const wrap = el("div", {
    style: "padding:14px 18px;border-top:1px solid var(--border)",
  });
  let has = false;

  if (order.status === "pending") {
    has = true;
    wrap.appendChild(
      el(
        "button",
        {
          class: "btn btn--danger btn--block",
          onClick: () =>
            transitionOrder(order.id, "cancelled", "取消訂單成功，退款已完成（模擬）"),
        },
        "取消訂單",
      ),
    );
  } else if (order.status === "delivered") {
    has = true;
    wrap.appendChild(
      el(
        "button",
        {
          class: "btn btn--primary btn--block",
          onClick: () => transitionOrder(order.id, "completed", "已確認收貨"),
        },
        "確認收貨",
      ),
    );
  }
  return has ? wrap : null;
}

async function transitionOrder(orderId, status, okMsg) {
  try {
    await api.updateOrderStatus(orderId, status);
    toast(okMsg, "ok");
    await fetchAndRenderOrder(orderId, $("orderDetail"));
  } catch (err) {
    toast(errText(err), "err");
    handleAuthError(err);
  }
}

function startPolling(orderId) {
  stopPolling();
  state.pollingOrderId = orderId;
  $("pollHint").textContent = "● 即時更新中";
  state.pollTimer = setInterval(() => {
    if (state.pollingOrderId === orderId) {
      fetchAndRenderOrder(orderId, $("orderDetail"));
    }
  }, 5000);
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  state.pollingOrderId = null;
  $("pollHint").textContent = "";
  destroyDeliveryMap();
}

// ---------------- 配送位置地圖 ----------------
function renderDeliveryTracking(orderId) {
  return el("section", { class: "delivery-map-card" }, [
    el("div", { class: "delivery-map-card__head" }, [
      el("div", {}, [
        el("h3", { text: "配送追蹤" }),
        el("p", { class: "muted small", text: "每 5 秒更新外送員最新位置" }),
      ]),
      el("span", { class: "status status--delivering", text: "配送中" }),
    ]),
    el("div", { id: "deliveryMap", class: "delivery-map" }),
    el("p", {
      id: "deliveryLocationStatus",
      class: "muted small delivery-map-card__status",
      text: "正在取得外送員最新位置…",
    }),
    el("p", {
      class: "muted small delivery-map-card__attribution",
      text: `訂單 #${orderId} 的位置僅供本筆訂單追蹤使用。`,
    }),
  ]);
}

async function refreshDeliveryMap(orderId) {
  const mapHost = $("deliveryMap");
  const statusHost = $("deliveryLocationStatus");
  if (!mapHost || state.pollingOrderId !== orderId) return;

  try {
    const response = await api.getDeliveryLatest(orderId);
    if (!isCurrentDeliveryMap(mapHost, orderId)) return;
    const location = response?.location || response?.latest || response;
    const latitude = Number(location?.latitude);
    const longitude = Number(location?.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      showDeliveryMapMessage(mapHost, "尚未收到外送員的位置回報。", false);
      return;
    }
    if (!window.L) {
      showDeliveryMapMessage(
        mapHost,
        "地圖元件載入失敗，請確認網路後重新整理頁面。",
        true,
      );
      return;
    }

    const map = window.L.map(mapHost, { scrollWheelZoom: false }).setView(
      [latitude, longitude],
      16,
    );
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    const marker = window.L.marker([latitude, longitude], {
      icon: window.L.divIcon({
        className: "courier-map-marker",
        html: "🛵",
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      }),
    }).addTo(map);
    marker.bindPopup("外送員目前位置");
    state.deliveryMap = map;
    state.deliveryMapOrderId = orderId;
    if (statusHost) {
      statusHost.textContent = location.recorded_at
        ? `最新位置回報：${formatTime(location.recorded_at)}`
        : "已更新外送員最新位置";
    }
  } catch (error) {
    if (!isCurrentDeliveryMap(mapHost, orderId)) return;
    if (error instanceof ApiError && error.status === 404) {
      showDeliveryMapMessage(mapHost, "尚未收到外送員的位置回報。", false);
      return;
    }
    showDeliveryMapMessage(mapHost, errorText(error), true);
    handleAuthError(error);
  }
}

function isCurrentDeliveryMap(mapHost, orderId) {
  return (
    mapHost.isConnected &&
    state.pollingOrderId === orderId &&
    $("deliveryMap") === mapHost
  );
}

function showDeliveryMapMessage(mapHost, message, isError) {
  const statusHost = $("deliveryLocationStatus");
  if (mapHost && mapHost.isConnected) {
    mapHost.replaceChildren(
      el("div", {
        class: `delivery-map__empty${isError ? " is-error" : ""}`,
        text: message,
      }),
    );
  }
  if (statusHost) statusHost.textContent = isError ? "位置資料暫時無法取得" : message;
}

function destroyDeliveryMap() {
  if (state.deliveryMap) {
    state.deliveryMap.remove();
    state.deliveryMap = null;
  }
  state.deliveryMapOrderId = null;
}

// ---------------- 共用小工具 ----------------
function statusBadge(status) {
  return el("span", {
    class: `status status--${status}`,
    text: ORDER_STATUS_LABEL[status] || status,
  });
}

function emptyState(icon, text) {
  return el("div", { class: "empty" }, [
    el("div", { class: "empty__icon", text: icon }),
    el("div", { text }),
  ]);
}

function errText(err) {
  return err instanceof ApiError ? err.detail : "發生未預期的錯誤";
}

function handleAuthError(err) {
  if (err instanceof ApiError && err.status === 401) {
    toast("登入已失效，請重新登入", "err");
    logout();
  }
}

function formatTime(iso) {
  try {
    // 對舊資料或非標準 API 回應保留防禦：若 ISO 字串無時區資訊，
    // 補上 Z 當作 UTC 解析，避免瀏覽器誤當本地時間。
    const hasTz = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso);
    const d = new Date(hasTz ? iso : `${iso}Z`);
    return d.toLocaleString("zh-TW", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ---------------- 事件綁定 ----------------
function bind() {
  document
    .querySelectorAll(".auth-tabs button")
    .forEach((b) => b.addEventListener("click", () => setAuthMode(b.dataset.mode)));
  $("authForm").addEventListener("submit", handleAuthSubmit);
  $("logoutBtn").addEventListener("click", logout);
  $("ordersBtn").addEventListener("click", loadOrders);
  $("backToRestaurants").addEventListener("click", () => showView("restaurants"));
  $("backFromOrders").addEventListener("click", () => showView("restaurants"));
  $("backFromDetail").addEventListener("click", () => {
    stopPolling();
    showView("restaurants");
  });
  $("cartFab").addEventListener("click", openCart);
  $("closeCart").addEventListener("click", closeCart);
  $("cartBackdrop").addEventListener("click", closeCart);
  $("checkoutBtn").addEventListener("click", checkout);
}

// ---------------- 啟動 ----------------
async function boot() {
  bind();
  setAuthMode("login");
  if (auth.isLoggedIn) {
    try {
      await enterApp();
    } catch (err) {
      toast(errText(err), "err");
      logout();
    }
  } else {
    showView("auth");
  }
}

boot();
