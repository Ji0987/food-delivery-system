// 餐點外送系統｜外送員工作台邏輯
import {
  api,
  auth,
  ApiError,
  el,
  money,
  ORDER_STATUS_LABEL,
  toast,
} from "./api.js";

const POLL_MS = 5000;
const TRACKABLE_STATUSES = new Set(["picked_up", "delivering"]);
const ACTIVE_STATUSES = new Set(["ready_for_pickup", "picked_up", "delivering"]);

const state = {
  availableOrders: [],
  activeOrders: [],
  pollTimer: null,
  currentView: "auth",
  statusByOrderId: new Map(),
  watchId: null,
  locationReportTimer: null,
  lastPosition: null,
  lastLocationReportAt: 0,
  isReportingLocation: false,
};

const $ = (id) => document.getElementById(id);

function showView(name) {
  state.currentView = name;
  document
    .querySelectorAll(".view")
    .forEach((view) => view.classList.toggle("is-active", view.id === `view-${name}`));
  if (name !== "dispatch") stopPolling();
}

// ---------------- 認證 ----------------
let authMode = "login";

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === "register";
  document
    .querySelectorAll(".auth-tabs button")
    .forEach((button) =>
      button.classList.toggle("is-active", button.dataset.mode === mode),
    );
  $("nameField").hidden = !registering;
  $("f-name").required = registering;
  $("pwHint").hidden = !registering;
  $("authTitle").textContent = registering ? "建立外送員帳號" : "外送員登入";
  $("authSubmit").textContent = registering ? "註冊並登入" : "登入";
  $("f-password").setAttribute(
    "autocomplete",
    registering ? "new-password" : "current-password",
  );
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const email = $("f-email").value.trim();
  const password = $("f-password").value;
  const name = $("f-name").value.trim();
  const button = $("authSubmit");
  if (!email || !password || (authMode === "register" && !name)) {
    toast("請填寫所有必填欄位", "err");
    return;
  }

  button.disabled = true;
  try {
    let registeredUser = null;
    if (authMode === "register") {
      registeredUser = await api.register({
        email,
        password,
        role: "courier",
        name,
      });
    }
    const response = await api.login(email, password);
    const user = response.user || registeredUser;
    if (!user || user.role !== "courier") {
      auth.clear();
      throw new ApiError(403, "請使用外送員帳號登入外送員工作台");
    }
    auth.save(response.access_token, user);
    toast(authMode === "register" ? "註冊成功，已登入" : "登入成功", "ok");
    await enterApp();
  } catch (error) {
    toast(errorText(error), "err");
  } finally {
    button.disabled = false;
  }
}

function logout() {
  stopLocationTracking("已停止定位回報");
  stopPolling();
  auth.clear();
  state.availableOrders = [];
  state.activeOrders = [];
  state.statusByOrderId.clear();
  $("userLabel").textContent = "";
  $("dispatchBtn").hidden = true;
  $("logoutBtn").hidden = true;
  $("f-email").value = "";
  $("f-password").value = "";
  $("f-name").value = "";
  showView("auth");
}

async function enterApp() {
  const user = auth.user;
  if (!user || user.role !== "courier") {
    auth.clear();
    throw new ApiError(403, "請使用外送員帳號登入外送員工作台");
  }
  $("userLabel").textContent = user.name || user.email;
  $("dispatchBtn").hidden = false;
  $("logoutBtn").hidden = false;
  showView("dispatch");
  await refreshDashboard(false);
  if (state.currentView === "dispatch") startPolling();
}

// ---------------- 訂單列表、搶單與狀態 ----------------
async function refreshDashboard(fromPoll) {
  if (!fromPoll) {
    $("availableOrderList").replaceChildren(el("div", { class: "spinner" }));
    $("activeDeliveryList").replaceChildren(el("div", { class: "spinner" }));
  }
  try {
    const [available, courierOrders] = await Promise.all([
      api.listAvailableOrders(),
      api.listCourierOrders(),
    ]);
    state.availableOrders = available;
    state.activeOrders = courierOrders.filter((order) => ACTIVE_STATUSES.has(order.status));
    notifyStatusChanges(state.activeOrders, fromPoll);
    renderActiveOrders();
    renderAvailableOrders();
    updateLocationControls();
  } catch (error) {
    if (!fromPoll) {
      $("availableOrderList").replaceChildren(emptyState("⚠️", errorText(error)));
      $("activeDeliveryList").replaceChildren(emptyState("⚠️", errorText(error)));
    }
    handleAuthError(error);
  }
}

function notifyStatusChanges(orders, shouldNotify) {
  const activeIds = new Set();
  for (const order of orders) {
    activeIds.add(order.id);
    const previous = state.statusByOrderId.get(order.id);
    if (shouldNotify && previous && previous !== order.status) {
      toast(
        `訂單 #${order.id} 更新為「${ORDER_STATUS_LABEL[order.status] || order.status}」`,
        "info",
        3200,
      );
    }
    state.statusByOrderId.set(order.id, order.status);
  }
  for (const id of state.statusByOrderId.keys()) {
    if (!activeIds.has(id)) state.statusByOrderId.delete(id);
  }
}

function renderAvailableOrders() {
  const host = $("availableOrderList");
  host.replaceChildren();
  if (!state.availableOrders.length) {
    host.appendChild(emptyState("📭", "目前沒有可搶的訂單"));
    return;
  }
  for (const order of state.availableOrders) {
    const card = orderCard(order);
    const action = el("div", {
      class: "row-gap",
      style: "padding:14px 18px;border-top:1px solid var(--border)",
    }, [
      el(
        "button",
        {
          class: "btn btn--primary",
          onClick: (event) => claimOrder(order.id, event.currentTarget),
        },
        "搶單",
      ),
    ]);
    card.appendChild(action);
    host.appendChild(card);
  }
}

function renderActiveOrders() {
  const host = $("activeDeliveryList");
  host.replaceChildren();
  $("activeCount").textContent = state.activeOrders.length
    ? `${state.activeOrders.length} 筆處理中`
    : "尚無進行中的配送";
  if (!state.activeOrders.length) {
    host.appendChild(emptyState("🛵", "搶單後，配送任務會出現在這裡"));
    return;
  }
  for (const order of state.activeOrders) {
    const card = orderCard(order);
    const action = courierAction(order);
    if (action) card.appendChild(action);
    host.appendChild(card);
  }
}

function orderCard(order) {
  const card = el("div", { class: "card delivery-card" }, [
    el("div", { class: "order-head" }, [
      el("div", { style: "flex:1" }, [
        el("div", { class: "order-head__id", text: `訂單 #${order.id}` }),
        el("div", {
          class: "muted small",
          text: `${formatTime(order.created_at)}・餐廳 #${order.restaurant_id}`,
        }),
      ]),
      statusBadge(order.status),
    ]),
  ]);
  const details = el("div", { style: "padding:12px 18px" });
  for (const item of order.items || []) {
    details.appendChild(
      el("div", { class: "order-line" }, [
        el("span", { text: `${item.item_name_snapshot} × ${item.quantity}` }),
        el("span", { text: money(item.subtotal) }),
      ]),
    );
  }
  details.appendChild(
    el("div", { class: "summary-row", style: "margin:12px 0 0" }, [
      el("span", { class: "muted", text: "訂單金額" }),
      el("span", { class: "total", text: money(order.total_amount) }),
    ]),
  );
  card.appendChild(details);
  return card;
}

function courierAction(order) {
  const actionsByStatus = {
    ready_for_pickup: { status: "picked_up", label: "已取餐" },
    picked_up: { status: "delivering", label: "開始配送" },
    delivering: { status: "delivered", label: "標記已送達" },
  };
  const action = actionsByStatus[order.status];
  if (!action) return null;
  return el("div", {
    class: "row-gap",
    style: "padding:14px 18px;border-top:1px solid var(--border)",
  }, [
    el(
      "button",
      {
        class: "btn btn--primary",
        onClick: (event) =>
          updateDeliveryStatus(order.id, action.status, action.label, event.currentTarget),
      },
      action.label,
    ),
  ]);
}

async function claimOrder(orderId, button) {
  button.disabled = true;
  try {
    await api.claimOrder(orderId);
    toast(`已成功搶下訂單 #${orderId}`, "ok");
    await refreshDashboard(false);
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

async function updateDeliveryStatus(orderId, status, label, button) {
  button.disabled = true;
  try {
    await api.updateOrderStatus(orderId, status);
    toast(`訂單 #${orderId}：${label}成功`, "ok");
    await refreshDashboard(false);
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

function startPolling() {
  stopPolling();
  $("pollHint").textContent = "● 每 5 秒更新";
  state.pollTimer = setInterval(() => {
    if (state.currentView === "dispatch") refreshDashboard(true);
  }, POLL_MS);
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  $("pollHint").textContent = "";
}

// ---------------- 瀏覽器定位 ----------------
function trackableOrders() {
  return state.activeOrders.filter((order) => TRACKABLE_STATUSES.has(order.status));
}

function updateLocationControls() {
  const active = trackableOrders();
  const button = $("locationToggleBtn");
  if (!active.length) {
    if (state.watchId !== null) stopLocationTracking("沒有可回報位置的配送訂單，已停止定位。");
    button.disabled = true;
    button.textContent = "啟動定位";
    if (state.watchId === null) {
      $("locationStatus").textContent = "搶單後，在「已取餐」或「配送中」階段可啟動定位回報。";
    }
    return;
  }
  button.disabled = false;
  button.textContent = state.watchId === null ? "啟動定位" : "停止定位";
  if (state.watchId === null) {
    $("locationStatus").textContent = `可回報 ${active.length} 筆配送訂單的位置。請在使用者啟動後授權定位。`;
  }
}

function toggleLocationTracking() {
  if (state.watchId !== null) {
    stopLocationTracking("已停止定位回報");
    return;
  }
  startLocationTracking();
}

function startLocationTracking() {
  if (!navigator.geolocation) {
    $("locationStatus").textContent = "此瀏覽器不支援 Geolocation API，無法回報位置。";
    toast("此瀏覽器不支援定位功能", "err");
    return;
  }
  if (!trackableOrders().length) {
    toast("請先將已搶訂單更新為「已取餐」或「配送中」", "err");
    updateLocationControls();
    return;
  }

  $("locationStatus").textContent = "正在要求定位權限…";
  state.watchId = navigator.geolocation.watchPosition(
    onPosition,
    onPositionError,
    {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 15000,
    },
  );
  state.locationReportTimer = setInterval(() => {
    if (state.lastPosition) void reportCurrentPosition(state.lastPosition);
  }, POLL_MS);
  $("locationToggleBtn").textContent = "停止定位";
}

function onPosition(position) {
  state.lastPosition = position;
  void reportCurrentPosition(position);
}

async function reportCurrentPosition(position) {
  const active = trackableOrders();
  if (!active.length) {
    stopLocationTracking("沒有可回報位置的配送訂單，已停止定位。");
    return;
  }
  const now = Date.now();
  if (state.isReportingLocation || now - state.lastLocationReportAt < POLL_MS - 100) return;

  state.isReportingLocation = true;
  const latitude = position.coords.latitude;
  const longitude = position.coords.longitude;
  try {
    await Promise.all(
      active.map((order) => api.reportDeliveryLocation(order.id, latitude, longitude)),
    );
    state.lastLocationReportAt = now;
    $("locationStatus").textContent = `已於 ${formatTime(new Date().toISOString())} 回報位置（${active.length} 筆配送）。`;
  } catch (error) {
    $("locationStatus").textContent = `位置回報失敗：${errorText(error)}`;
    toast(`位置回報失敗：${errorText(error)}`, "err");
    handleAuthError(error);
  } finally {
    state.isReportingLocation = false;
  }
}

function onPositionError(error) {
  const messages = {
    1: "你已拒絕定位權限，請在瀏覽器設定中允許後再試。",
    2: "目前無法取得位置，請確認定位服務與網路是否可用。",
    3: "取得位置逾時，請移到訊號較佳處後再試。",
  };
  stopLocationTracking(messages[error.code] || "無法取得位置。");
  toast(messages[error.code] || "無法取得位置", "err");
}

function stopLocationTracking(message) {
  if (state.watchId !== null && navigator.geolocation) {
    navigator.geolocation.clearWatch(state.watchId);
  }
  state.watchId = null;
  if (state.locationReportTimer) {
    clearInterval(state.locationReportTimer);
    state.locationReportTimer = null;
  }
  state.lastPosition = null;
  state.lastLocationReportAt = 0;
  $("locationToggleBtn").textContent = "啟動定位";
  if (message) $("locationStatus").textContent = message;
  updateLocationControls();
}

// ---------------- 共用 ----------------
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

function errorText(error) {
  return error instanceof ApiError ? error.detail : "發生未預期的錯誤";
}

function handleAuthError(error) {
  if (error instanceof ApiError && error.status === 401) {
    toast("登入已失效，請重新登入", "err");
    logout();
  }
}

function formatTime(iso) {
  if (!iso) return "";
  const hasTimezone = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso);
  const date = new Date(hasTimezone ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function bind() {
  document
    .querySelectorAll(".auth-tabs button")
    .forEach((button) =>
      button.addEventListener("click", () => setAuthMode(button.dataset.mode)),
    );
  $("authForm").addEventListener("submit", handleAuthSubmit);
  $("logoutBtn").addEventListener("click", logout);
  $("dispatchBtn").addEventListener("click", async () => {
    showView("dispatch");
    await refreshDashboard(false);
    startPolling();
  });
  $("refreshBtn").addEventListener("click", () => refreshDashboard(false));
  $("locationToggleBtn").addEventListener("click", toggleLocationTracking);
}

async function boot() {
  bind();
  setAuthMode("login");
  if (!auth.isLoggedIn) {
    showView("auth");
    return;
  }
  try {
    await enterApp();
  } catch (error) {
    auth.clear();
    toast(errorText(error), "err");
    showView("auth");
  }
}

boot();
