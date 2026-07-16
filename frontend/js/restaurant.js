// 餐點外送系統｜餐廳工作台邏輯
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
const TERMINAL = new Set(["completed", "cancelled", "rejected"]);

const state = {
  restaurant: null,
  menu: null,
  orderPollTimer: null,
  lastOrderStatuses: new Map(),
  currentView: "auth",
};

const $ = (id) => document.getElementById(id);

function showView(name) {
  state.currentView = name;
  document
    .querySelectorAll(".view")
    .forEach((view) => view.classList.toggle("is-active", view.id === `view-${name}`));
  if (name !== "orders") stopOrderPolling();
}

// ---------------- 認證 ----------------
let authMode = "login";

function setAuthMode(mode) {
  authMode = mode;
  document
    .querySelectorAll(".auth-tabs button")
    .forEach((button) =>
      button.classList.toggle("is-active", button.dataset.mode === mode),
    );
  const registering = mode === "register";
  $("nameField").hidden = !registering;
  $("f-name").required = registering;
  $("pwHint").hidden = !registering;
  $("authTitle").textContent = registering ? "建立餐廳夥伴帳號" : "餐廳夥伴登入";
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
        role: "restaurant",
        name,
      });
    }
    const tokenResponse = await api.login(email, password);
    const user = tokenResponse.user || registeredUser;
    if (!user || user.role !== "restaurant") {
      auth.clear();
      throw new ApiError(403, "請使用餐廳角色帳號登入餐廳工作台");
    }
    auth.save(tokenResponse.access_token, user);
    toast(authMode === "register" ? "註冊成功，已登入" : "登入成功", "ok");
    await enterApp();
  } catch (error) {
    if (error instanceof ApiError && [401, 403].includes(error.status)) {
      auth.clear();
      setAppActionsVisible(false);
      showView("auth");
    }
    toast(errorText(error), "err");
  } finally {
    button.disabled = false;
  }
}

function logout() {
  auth.clear();
  stopOrderPolling();
  state.restaurant = null;
  state.menu = null;
  state.lastOrderStatuses.clear();
  $("userLabel").textContent = "";
  setAppActionsVisible(false);
  $("f-email").value = "";
  $("f-password").value = "";
  $("f-name").value = "";
  showView("auth");
}

function setAppActionsVisible(visible) {
  $("menuBtn").hidden = !visible;
  $("ordersBtn").hidden = !visible;
  $("logoutBtn").hidden = !visible;
}

async function enterApp() {
  const cachedUser = auth.user;
  if (cachedUser?.role && cachedUser.role !== "restaurant") {
    auth.clear();
    throw new ApiError(403, "請使用餐廳角色帳號登入餐廳工作台");
  }

  $("userLabel").textContent = cachedUser?.name || cachedUser?.email || "";
  $("logoutBtn").hidden = false;
  try {
    state.restaurant = await api.getMyRestaurant();
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      $("setupStatus").textContent = "尚未建立餐廳，完成資料後即可開始上架餐點。";
      showView("setup");
      return;
    }
    throw error;
  }

  openWorkspace();
  await loadMenu();
}

function openWorkspace() {
  $("menuRestaurantName").textContent = state.restaurant.name;
  $("menuRestaurantDesc").textContent = state.restaurant.description || "尚未填寫餐廳簡介";
  setAppActionsVisible(true);
  showView("menu");
}

// ---------------- 餐廳建立 ----------------
async function createRestaurant(event) {
  event.preventDefault();
  const name = $("r-name").value.trim();
  const button = $("restaurantSubmit");
  if (!name) {
    toast("請填寫餐廳名稱", "err");
    return;
  }

  button.disabled = true;
  $("setupStatus").textContent = "建立中…";
  try {
    state.restaurant = await api.createRestaurant({
      name,
      description: nullIfBlank($("r-description").value),
      address: nullIfBlank($("r-address").value),
      phone: nullIfBlank($("r-phone").value),
    });
    toast("餐廳已建立", "ok");
    $("setupStatus").textContent = "";
    openWorkspace();
    await loadMenu();
  } catch (error) {
    $("setupStatus").textContent = errorText(error);
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

// ---------------- 菜單管理 ----------------
async function loadMenu() {
  const host = $("menuList");
  host.replaceChildren(el("div", { class: "spinner" }));
  try {
    state.menu = await api.getMenu(state.restaurant.id);
    renderCategoryOptions();
    renderMenu();
  } catch (error) {
    host.replaceChildren(emptyState("⚠️", errorText(error)));
    handleAuthError(error);
  }
}

function renderCategoryOptions() {
  const select = $("itemCategory");
  const selected = select.value;
  select.replaceChildren(el("option", { value: "", text: "未分類" }));
  for (const category of state.menu.categories) {
    select.appendChild(
      el("option", { value: String(category.id), text: category.name }),
    );
  }
  if ([...select.options].some((option) => option.value === selected)) {
    select.value = selected;
  }
}

function renderMenu() {
  const host = $("menuList");
  host.replaceChildren();
  if (!state.menu.items.length) {
    host.appendChild(emptyState("🍽️", "尚未建立餐點，請先從上方新增"));
    return;
  }

  const categories = [
    ...state.menu.categories.map((category) => ({
      id: category.id,
      name: category.name,
    })),
    { id: null, name: "未分類" },
  ];

  for (const category of categories) {
    const items = state.menu.items.filter(
      (item) => item.category_id === category.id,
    );
    if (!items.length) continue;

    host.appendChild(
      el("div", { class: "section-head", style: "margin-top:18px" }, [
        el("h3", { text: category.name, style: "font-size:17px" }),
        el("span", { class: "muted small", text: `${items.length} 項` }),
      ]),
    );
    const card = el("div", { class: "card" });
    for (const item of items) card.appendChild(renderMenuItem(item));
    host.appendChild(card);
  }
}

function renderMenuItem(item) {
  const soldOut = item.is_sold_out;
  return el(
    "div",
    { class: `menu-item${soldOut ? " is-soldout" : ""}` },
    [
      el("div", { class: "menu-item__body" }, [
        el("div", { class: "menu-item__name" }, [
          item.name,
          soldOut
            ? el("span", { class: "badge badge--soldout", text: "已售罄" })
            : null,
        ]),
        item.description
          ? el("div", { class: "menu-item__desc", text: item.description })
          : null,
      ]),
      el("div", { class: "menu-item__price", text: money(item.price) }),
      el("div", { class: "row-gap" }, [
        el(
          "button",
          {
            class: `btn ${soldOut ? "btn--ghost" : "btn--danger"} btn--sm`,
            onClick: () => toggleSoldOut(item),
          },
          soldOut ? "恢復供應" : "設為售罄",
        ),
        el(
          "button",
          { class: "btn btn--ghost btn--sm", onClick: () => beginItemEdit(item) },
          "編輯",
        ),
      ]),
    ],
  );
}

async function createCategory(event) {
  event.preventDefault();
  const name = $("categoryName").value.trim();
  const sortOrder = Number.parseInt($("categoryOrder").value || "0", 10);
  const button = $("categorySubmit");
  if (!name || !Number.isInteger(sortOrder)) {
    toast("請填寫分類名稱與整數排序", "err");
    return;
  }

  button.disabled = true;
  try {
    await api.createMenuCategory(state.restaurant.id, {
      name,
      sort_order: sortOrder,
    });
    $("categoryForm").reset();
    $("categoryOrder").value = "0";
    toast(`已新增分類「${name}」`, "ok");
    await loadMenu();
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

async function saveMenuItem(event) {
  event.preventDefault();
  const id = $("itemId").value;
  const name = $("itemName").value.trim();
  const price = $("itemPrice").value;
  const categoryId = $("itemCategory").value;
  const button = $("itemSubmit");
  if (!name || price === "") {
    toast("請填寫餐點名稱與價格", "err");
    return;
  }

  const payload = {
    name,
    description: nullIfBlank($("itemDescription").value),
    price,
    category_id: categoryId ? Number(categoryId) : null,
    is_sold_out: $("itemSoldOut").checked,
  };

  button.disabled = true;
  try {
    if (id) {
      await api.updateMenuItem(id, payload);
      toast(`已更新餐點「${name}」`, "ok");
    } else {
      await api.createMenuItem(state.restaurant.id, payload);
      toast(`已新增餐點「${name}」`, "ok");
    }
    resetItemForm();
    await loadMenu();
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

function beginItemEdit(item) {
  $("itemId").value = String(item.id);
  $("itemName").value = item.name;
  $("itemDescription").value = item.description || "";
  $("itemPrice").value = item.price;
  $("itemCategory").value = item.category_id == null ? "" : String(item.category_id);
  $("itemSoldOut").checked = item.is_sold_out;
  $("itemFormTitle").textContent = `編輯「${item.name}」`;
  $("itemSubmit").textContent = "儲存變更";
  $("cancelItemEdit").hidden = false;
  $("itemName").focus();
  $("itemForm").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetItemForm() {
  $("itemForm").reset();
  $("itemId").value = "";
  $("itemFormTitle").textContent = "新增餐點";
  $("itemSubmit").textContent = "新增餐點";
  $("cancelItemEdit").hidden = true;
}

async function toggleSoldOut(item) {
  try {
    await api.updateMenuItem(item.id, {
      is_sold_out: !item.is_sold_out,
    });
    toast(item.is_sold_out ? "餐點已恢復供應" : "餐點已標記售罄", "ok");
    await loadMenu();
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  }
}

// ---------------- 訂單管理與輪詢 ----------------
async function openOrders() {
  showView("orders");
  await loadOrders(false);
  if (state.currentView === "orders") startOrderPolling();
}

async function loadOrders(fromPoll = false) {
  const host = $("orderList");
  if (!fromPoll) host.replaceChildren(el("div", { class: "spinner" }));
  try {
    const orders = await api.listOrders();
    notifyOrderChanges(orders, fromPoll);
    renderOrders(orders);
  } catch (error) {
    if (!fromPoll) host.replaceChildren(emptyState("⚠️", errorText(error)));
    handleAuthError(error);
  }
}

function notifyOrderChanges(orders, shouldNotify) {
  for (const order of orders) {
    const previous = state.lastOrderStatuses.get(order.id);
    if (shouldNotify && previous && previous !== order.status) {
      toast(
        `訂單 #${order.id} 更新為「${ORDER_STATUS_LABEL[order.status] || order.status}」`,
        "info",
        3200,
      );
    }
    state.lastOrderStatuses.set(order.id, order.status);
  }
}

function renderOrders(orders) {
  const host = $("orderList");
  host.replaceChildren();
  if (!orders.length) {
    host.appendChild(emptyState("🧾", "目前還沒有訂單"));
    return;
  }

  for (const order of orders) {
    const card = el("div", { class: "card", style: "margin-bottom:14px" });
    card.appendChild(
      el("div", { class: "order-head" }, [
        el("div", { style: "flex:1" }, [
          el("div", { class: "order-head__id", text: `訂單 #${order.id}` }),
          el("div", {
            class: "muted small",
            text: `${formatTime(order.created_at)}・顧客 #${order.consumer_user_id}`,
          }),
        ]),
        statusBadge(order.status),
      ]),
    );

    const details = el("div", { style: "padding:12px 18px" });
    for (const item of order.items) {
      details.appendChild(
        el("div", { class: "order-line" }, [
          el("span", { text: `${item.item_name_snapshot} × ${item.quantity}` }),
          el("span", { text: money(item.subtotal) }),
        ]),
      );
    }
    details.appendChild(
      el("div", { class: "summary-row", style: "margin:12px 0 0" }, [
        el("span", { class: "muted", text: "總計" }),
        el("span", { class: "total", text: money(order.total_amount) }),
      ]),
    );
    card.appendChild(details);

    const actions = renderOrderActions(order);
    if (actions) card.appendChild(actions);
    host.appendChild(card);
  }
}

function renderOrderActions(order) {
  const actionsByStatus = {
    pending: [{ target: "accepted", label: "接受訂單", className: "btn--primary" }],
    accepted: [
      { target: "preparing", label: "開始製作", className: "btn--primary" },
      { target: "rejected", label: "拒絕訂單", className: "btn--danger" },
    ],
    preparing: [
      {
        target: "ready_for_pickup",
        label: "餐點完成，等待取餐",
        className: "btn--primary",
      },
    ],
  };
  const actions = actionsByStatus[order.status];
  if (!actions || TERMINAL.has(order.status)) return null;

  return el(
    "div",
    {
      class: "row-gap",
      style: "padding:14px 18px;border-top:1px solid var(--border)",
    },
    actions.map((action) =>
      el(
        "button",
        {
          class: `btn ${action.className}`,
          onClick: (event) =>
            transitionOrder(order.id, action.target, action.label, event.currentTarget),
        },
        action.label,
      ),
    ),
  );
}

async function transitionOrder(orderId, target, label, button) {
  button.disabled = true;
  try {
    await api.updateOrderStatus(orderId, target);
    toast(`訂單 #${orderId}：${label}成功`, "ok");
    await loadOrders(false);
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

function startOrderPolling() {
  stopOrderPolling();
  $("pollHint").textContent = "● 每 5 秒更新";
  state.orderPollTimer = setInterval(() => {
    if (state.currentView === "orders") loadOrders(true);
  }, POLL_MS);
}

function stopOrderPolling() {
  if (state.orderPollTimer) {
    clearInterval(state.orderPollTimer);
    state.orderPollTimer = null;
  }
  $("pollHint").textContent = "";
}

// ---------------- 共用工具 ----------------
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

function nullIfBlank(value) {
  const trimmed = value.trim();
  return trimmed || null;
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

// ---------------- 事件綁定與啟動 ----------------
function bind() {
  document
    .querySelectorAll(".auth-tabs button")
    .forEach((button) =>
      button.addEventListener("click", () => setAuthMode(button.dataset.mode)),
    );
  $("authForm").addEventListener("submit", handleAuthSubmit);
  $("restaurantForm").addEventListener("submit", createRestaurant);
  $("categoryForm").addEventListener("submit", createCategory);
  $("itemForm").addEventListener("submit", saveMenuItem);
  $("cancelItemEdit").addEventListener("click", resetItemForm);
  $("logoutBtn").addEventListener("click", logout);
  $("menuBtn").addEventListener("click", async () => {
    showView("menu");
    await loadMenu();
  });
  $("ordersBtn").addEventListener("click", openOrders);
  $("refreshMenuBtn").addEventListener("click", loadMenu);
  $("refreshOrdersBtn").addEventListener("click", () => loadOrders(false));
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
