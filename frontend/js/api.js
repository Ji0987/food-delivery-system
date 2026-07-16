// 餐點外送系統｜共用 API client
// 純瀏覽器 fetch，無外部依賴。前後端同源，API 用絕對路徑。

const TOKEN_KEY = "fd_token";
const USER_KEY = "fd_user";

export const auth = {
  get token() {
    return localStorage.getItem(TOKEN_KEY);
  },
  get user() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      // 舊版或手動寫入的 localStorage 不應讓整個頁面無法啟動。
      localStorage.removeItem(USER_KEY);
      return null;
    }
  },
  save(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  get isLoggedIn() {
    return Boolean(this.token);
  },
};

// 統一錯誤型別，攜帶 HTTP 狀態碼與後端 detail 訊息
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `請求失敗（HTTP ${status}）`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, body, { authed = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authed && auth.token) headers["Authorization"] = `Bearer ${auth.token}`;

  let res;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkError) {
    throw new ApiError(0, "無法連線到伺服器，請確認後端是否啟動。");
  }

  if (res.status === 401 && authed) {
    // 登入憑證失效：清除並讓頁面層決定導回登入
    auth.clear();
  }

  if (res.status === 204) return null;

  let payload = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const detail = extractDetail(payload) || `請求失敗（HTTP ${res.status}）`;
    throw new ApiError(res.status, detail);
  }
  return payload;
}

// FastAPI 驗證錯誤 detail 可能是字串或陣列，統一取出可讀訊息
function extractDetail(payload) {
  if (!payload) return null;
  if (typeof payload === "string") return payload;
  const d = payload.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) {
    return d.map((e) => e.msg || JSON.stringify(e)).join("；");
  }
  return null;
}

export const api = {
  // ---- 認證 ----
  register: (data) => request("POST", "/auth/register", data, { authed: false }),
  login: (email, password) =>
    request("POST", "/auth/login", { email, password }, { authed: false }),

  // ---- 餐廳 / 菜單 ----
  listRestaurants: () => request("GET", "/restaurants"),
  getMenu: (restaurantId) => request("GET", `/restaurants/${restaurantId}/menu`),
  getMyRestaurant: () => request("GET", "/restaurants/me"),
  createRestaurant: (data) => request("POST", "/restaurants", data),
  createMenuCategory: (restaurantId, data) =>
    request("POST", `/restaurants/${restaurantId}/categories`, data),
  updateMenuCategory: (categoryId, data) =>
    request("PATCH", `/menu-categories/${categoryId}`, data),
  deleteMenuCategory: (categoryId) =>
    request("DELETE", `/menu-categories/${categoryId}`),
  createMenuItem: (restaurantId, data) =>
    request("POST", `/restaurants/${restaurantId}/menu-items`, data),
  updateMenuItem: (menuItemId, data) =>
    request("PATCH", `/menu-items/${menuItemId}`, data),
  deleteMenuItem: (menuItemId) =>
    request("DELETE", `/menu-items/${menuItemId}`),

  // ---- 管理員 ----
  listAdminRestaurants: () => request("GET", "/admin/restaurants"),
  setRestaurantActivation: (restaurantId, isActive) =>
    request("PATCH", `/admin/restaurants/${restaurantId}`, {
      is_active: isActive,
    }),
  getAdminOverview: () => request("GET", "/admin/overview"),
  listAdminMenuCategories: (restaurantId) => {
    const query = restaurantId ? `?restaurant_id=${restaurantId}` : "";
    return request("GET", `/admin/menu-categories${query}`);
  },
  createAdminMenuCategory: (data) =>
    request("POST", "/admin/menu-categories", data),
  updateAdminMenuCategory: (categoryId, data) =>
    request("PATCH", `/admin/menu-categories/${categoryId}`, data),
  deleteAdminMenuCategory: (categoryId) =>
    request("DELETE", `/admin/menu-categories/${categoryId}`),

  // ---- 購物車 ----
  getCart: () => request("GET", "/cart"),
  addToCart: (menuItemId, quantity) =>
    request("POST", "/cart/items", { menu_item_id: menuItemId, quantity }),
  updateCartItem: (cartItemId, quantity) =>
    request("PATCH", `/cart/items/${cartItemId}`, { quantity }),
  removeCartItem: (cartItemId) =>
    request("DELETE", `/cart/items/${cartItemId}`),

  // ---- 訂單 ----
  createOrder: () => request("POST", "/orders", {}),
  listOrders: () => request("GET", "/orders"),
  getOrder: (orderId) => request("GET", `/orders/${orderId}`),
  updateOrderStatus: (orderId, status) =>
    request("PATCH", `/orders/${orderId}/status`, { status }),

  // ---- 配送 ----
  listAvailableOrders: () => request("GET", "/orders/available"),
  listCourierOrders: () => request("GET", "/orders?role=courier"),
  claimOrder: (orderId) => request("POST", `/orders/${orderId}/claim`, {}),
  reportDeliveryLocation: (orderId, latitude, longitude) =>
    request("POST", `/orders/${orderId}/locations`, { latitude, longitude }),
  getDeliveryLatest: (orderId) =>
    request("GET", `/orders/${orderId}/locations/latest`),
  getDeliveryLocations: (orderId) => request("GET", `/orders/${orderId}/locations`),
};

// ---- 共用顯示工具 ----
export function money(value) {
  // 後端金額為字串（Decimal 序列化），前端僅加貨幣符號、不重新計算
  return `NT$ ${value}`;
}

export const ORDER_STATUS_LABEL = {
  pending: "待餐廳確認",
  accepted: "餐廳已接單",
  rejected: "餐廳已拒單",
  preparing: "製作中",
  ready_for_pickup: "等待外送員取餐",
  picked_up: "外送員已取餐",
  delivering: "配送中",
  delivered: "已送達",
  completed: "已完成",
  cancelled: "已取消",
};

export const PAYMENT_STATUS_LABEL = {
  unpaid: "未付款",
  paid: "已付款",
  refunded: "已退款",
};

// ---- Toast ----
let toastHost = null;
export function toast(message, kind = "info", ms = 2600) {
  if (!toastHost) {
    toastHost = document.createElement("div");
    toastHost.className = "toast-host";
    document.body.appendChild(toastHost);
  }
  const el = document.createElement("div");
  el.className = `toast toast--${kind}`;
  el.textContent = message;
  toastHost.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity .3s ease";
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, ms);
}

// 小工具：安全地建立帶文字的元素，避免 innerHTML 注入
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v !== null && v !== undefined) {
      node.setAttribute(k, v);
    }
  }
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.appendChild(
      typeof child === "string" ? document.createTextNode(child) : child,
    );
  }
  return node;
}
