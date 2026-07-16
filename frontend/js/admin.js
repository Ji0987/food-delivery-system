// 餐點外送系統｜管理員工作台邏輯
import {
  api,
  auth,
  ApiError,
  el,
  ORDER_STATUS_LABEL,
  toast,
} from "./api.js";

const state = {
  restaurants: [],
  categories: [],
};

const $ = (id) => document.getElementById(id);

function showView(name) {
  document
    .querySelectorAll(".view")
    .forEach((view) => view.classList.toggle("is-active", view.id === `view-${name}`));
}

function setNavigationVisible(visible) {
  ["overviewBtn", "restaurantsBtn", "categoriesBtn", "logoutBtn"].forEach((id) => {
    $(id).hidden = !visible;
  });
}

// ---------------- 認證 ----------------
async function handleAuthSubmit(event) {
  event.preventDefault();
  const email = $("f-email").value.trim();
  const password = $("f-password").value;
  const button = $("authSubmit");
  if (!email || !password) {
    toast("請填寫 Email 與密碼", "err");
    return;
  }

  button.disabled = true;
  try {
    const response = await api.login(email, password);
    if (!response.user || response.user.role !== "admin") {
      auth.clear();
      throw new ApiError(403, "請使用管理員帳號登入管理員工作台");
    }
    auth.save(response.access_token, response.user);
    toast("登入成功", "ok");
    await enterApp();
  } catch (error) {
    toast(errorText(error), "err");
  } finally {
    button.disabled = false;
  }
}

function logout() {
  auth.clear();
  state.restaurants = [];
  state.categories = [];
  $("userLabel").textContent = "";
  $("f-email").value = "";
  $("f-password").value = "";
  resetCategoryForm();
  setNavigationVisible(false);
  showView("auth");
}

async function enterApp() {
  const user = auth.user;
  if (!user || user.role !== "admin") {
    auth.clear();
    throw new ApiError(403, "請使用管理員帳號登入管理員工作台");
  }
  $("userLabel").textContent = user.name || user.email;
  setNavigationVisible(true);
  await openOverview();
}

// ---------------- 營運總覽 ----------------
async function openOverview() {
  showView("overview");
  const host = $("overviewContent");
  host.replaceChildren(el("div", { class: "spinner" }));
  try {
    const overview = await api.getAdminOverview();
    renderOverview(overview);
  } catch (error) {
    host.replaceChildren(emptyState("⚠️", errorText(error)));
    handleAuthError(error);
  }
}

function renderOverview(overview) {
  const host = $("overviewContent");
  host.replaceChildren();
  const restaurant = overview.restaurants;
  const orders = overview.orders;

  host.appendChild(
    el("div", { class: "metrics-grid" }, [
      metricCard("餐廳總數", restaurant.total, "🏪"),
      metricCard("啟用餐廳", restaurant.active, "✅"),
      metricCard("已停權餐廳", restaurant.suspended, "⏸️"),
      metricCard("累計訂單", orders.total, "🧾"),
    ]),
  );

  const statusCard = el("div", { class: "card compact-card", style: "margin-top:16px" }, [
    el("h3", { text: "訂單狀態分布" }),
  ]);
  const entries = Object.entries(orders.by_status || {});
  if (!entries.length) {
    statusCard.appendChild(el("p", { class: "muted small", text: "尚無訂單資料" }));
  } else {
    const grid = el("div", { class: "status-summary" });
    for (const [status, count] of entries) {
      grid.appendChild(
        el("div", { class: "status-summary__item" }, [
          el("span", { class: `status status--${status}`, text: ORDER_STATUS_LABEL[status] || status }),
          el("strong", { text: String(count) }),
        ]),
      );
    }
    statusCard.appendChild(grid);
  }
  host.appendChild(statusCard);
}

function metricCard(label, value, icon) {
  return el("div", { class: "card metric-card" }, [
    el("div", { class: "metric-card__icon", text: icon }),
    el("div", {}, [
      el("div", { class: "metric-card__value", text: String(value) }),
      el("div", { class: "muted small", text: label }),
    ]),
  ]);
}

// ---------------- 餐廳帳號 ----------------
async function openRestaurants() {
  showView("restaurants");
  await loadRestaurants(true);
}

async function loadRestaurants(render = true) {
  const host = $("restaurantList");
  if (render) host.replaceChildren(el("div", { class: "spinner" }));
  try {
    state.restaurants = await api.listAdminRestaurants();
    renderRestaurantOptions();
    if (render) renderRestaurants();
  } catch (error) {
    if (render) host.replaceChildren(emptyState("⚠️", errorText(error)));
    handleAuthError(error);
  }
}

function renderRestaurants() {
  const host = $("restaurantList");
  host.replaceChildren();
  if (!state.restaurants.length) {
    host.appendChild(emptyState("🏪", "目前沒有餐廳帳號"));
    return;
  }

  for (const restaurant of state.restaurants) {
    const card = el("div", { class: "card list-card" }, [
      el("div", { class: "list-card__body" }, [
        el("div", { class: "list-card__title", text: restaurant.name }),
        el("div", {
          class: "muted small",
          text: restaurant.address || restaurant.description || "未填寫地址或簡介",
        }),
        el("div", {
          class: "muted small",
          text: `餐廳 #${restaurant.id}`,
          style: "margin-top:4px",
        }),
      ]),
      el("div", { class: "list-card__actions" }, [
        el("span", {
          class: `badge ${restaurant.is_active ? "badge--paid" : "badge--refunded"}`,
          text: restaurant.is_active ? "啟用中" : "已停權",
        }),
        el(
          "button",
          {
            class: `btn ${restaurant.is_active ? "btn--danger" : "btn--primary"} btn--sm`,
            onClick: (event) =>
              changeRestaurantActivation(restaurant, event.currentTarget),
          },
          restaurant.is_active ? "停權" : "重新啟用",
        ),
      ]),
    ]);
    host.appendChild(card);
  }
}

async function changeRestaurantActivation(restaurant, button) {
  const nextActive = !restaurant.is_active;
  const label = nextActive ? "重新啟用" : "停權";
  if (!window.confirm(`確定要${label}「${restaurant.name}」嗎？`)) return;

  button.disabled = true;
  try {
    await api.setRestaurantActivation(restaurant.id, nextActive);
    toast(`已${label}「${restaurant.name}」`, "ok");
    await loadRestaurants(true);
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

// ---------------- 跨餐廳分類 ----------------
async function openCategories() {
  showView("categories");
  await loadRestaurants(false);
  await loadCategories();
}

function renderRestaurantOptions() {
  const select = $("categoryRestaurant");
  const selected = select.value;
  select.replaceChildren(el("option", { value: "", text: "請選擇餐廳" }));
  for (const restaurant of state.restaurants) {
    select.appendChild(
      el("option", {
        value: String(restaurant.id),
        text: `${restaurant.name}${restaurant.is_active ? "" : "（已停權）"}`,
      }),
    );
  }
  if ([...select.options].some((option) => option.value === selected)) {
    select.value = selected;
  }
}

async function loadCategories() {
  const host = $("categoryList");
  host.replaceChildren(el("div", { class: "spinner" }));
  try {
    state.categories = await api.listAdminMenuCategories();
    renderCategories();
  } catch (error) {
    host.replaceChildren(emptyState("⚠️", errorText(error)));
    handleAuthError(error);
  }
}

function renderCategories() {
  const host = $("categoryList");
  host.replaceChildren();
  if (!state.categories.length) {
    host.appendChild(emptyState("🏷️", "目前沒有餐點分類"));
    return;
  }
  const restaurantNames = new Map(
    state.restaurants.map((restaurant) => [restaurant.id, restaurant.name]),
  );
  const card = el("div", { class: "card" });
  for (const category of state.categories) {
    card.appendChild(
      el("div", { class: "list-card list-card--row" }, [
        el("div", { class: "list-card__body" }, [
          el("div", { class: "list-card__title", text: category.name }),
          el("div", {
            class: "muted small",
            text: `${restaurantNames.get(category.restaurant_id) || `餐廳 #${category.restaurant_id}`}・排序 ${category.sort_order}`,
          }),
        ]),
        el("div", { class: "list-card__actions" }, [
          el("button", {
            class: "btn btn--ghost btn--sm",
            text: "編輯",
            onClick: () => beginCategoryEdit(category),
          }),
          el("button", {
            class: "btn btn--danger btn--sm",
            text: "刪除",
            onClick: () => deleteCategory(category),
          }),
        ]),
      ]),
    );
  }
  host.appendChild(card);
}

async function saveCategory(event) {
  event.preventDefault();
  const id = $("categoryId").value;
  const restaurantId = Number($("categoryRestaurant").value);
  const name = $("categoryName").value.trim();
  const sortOrder = Number.parseInt($("categoryOrder").value, 10);
  const button = $("categorySubmit");
  if (!Number.isInteger(restaurantId) || restaurantId <= 0 || !name || !Number.isInteger(sortOrder)) {
    toast("請填妥餐廳、分類名稱與整數排序", "err");
    return;
  }

  button.disabled = true;
  try {
    if (id) {
      await api.updateAdminMenuCategory(id, { name, sort_order: sortOrder });
      toast(`已更新分類「${name}」`, "ok");
    } else {
      await api.createAdminMenuCategory({
        restaurant_id: restaurantId,
        name,
        sort_order: sortOrder,
      });
      toast(`已新增分類「${name}」`, "ok");
    }
    resetCategoryForm();
    await loadCategories();
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  } finally {
    button.disabled = false;
  }
}

function beginCategoryEdit(category) {
  $("categoryId").value = String(category.id);
  $("categoryRestaurant").value = String(category.restaurant_id);
  $("categoryRestaurant").disabled = true;
  $("categoryName").value = category.name;
  $("categoryOrder").value = String(category.sort_order);
  $("categoryFormTitle").textContent = `編輯「${category.name}」`;
  $("categorySubmit").textContent = "儲存變更";
  $("cancelCategoryEdit").hidden = false;
  $("categoryName").focus();
  $("categoryForm").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetCategoryForm() {
  $("categoryForm").reset();
  $("categoryId").value = "";
  $("categoryRestaurant").disabled = false;
  $("categoryOrder").value = "0";
  $("categoryFormTitle").textContent = "新增分類";
  $("categorySubmit").textContent = "新增分類";
  $("cancelCategoryEdit").hidden = true;
}

async function deleteCategory(category) {
  if (!window.confirm(`確定要刪除分類「${category.name}」嗎？`)) return;
  try {
    await api.deleteAdminMenuCategory(category.id);
    toast(`已刪除分類「${category.name}」`, "ok");
    if ($("categoryId").value === String(category.id)) resetCategoryForm();
    await loadCategories();
  } catch (error) {
    toast(errorText(error), "err");
    handleAuthError(error);
  }
}

// ---------------- 共用 ----------------
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

function bind() {
  $("authForm").addEventListener("submit", handleAuthSubmit);
  $("logoutBtn").addEventListener("click", logout);
  $("overviewBtn").addEventListener("click", openOverview);
  $("restaurantsBtn").addEventListener("click", openRestaurants);
  $("categoriesBtn").addEventListener("click", openCategories);
  $("refreshOverviewBtn").addEventListener("click", openOverview);
  $("refreshRestaurantsBtn").addEventListener("click", () => loadRestaurants(true));
  $("refreshCategoriesBtn").addEventListener("click", openCategories);
  $("categoryForm").addEventListener("submit", saveCategory);
  $("cancelCategoryEdit").addEventListener("click", resetCategoryForm);
}

async function boot() {
  bind();
  setNavigationVisible(false);
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
