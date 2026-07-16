"""管理員平台治理 API 的請求與回應 schema。"""

from pydantic import Field

from backend.schemas.common import ORMModel


class RestaurantActivationUpdate(ORMModel):
    """管理員啟用或停權餐廳。"""

    is_active: bool


class AdminMenuCategoryCreate(ORMModel):
    """由管理員為指定餐廳建立分類。"""

    restaurant_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=50)
    sort_order: int = 0


class RestaurantOverview(ORMModel):
    total: int
    active: int
    suspended: int


class OrderOverview(ORMModel):
    total: int
    by_status: dict[str, int]


class AdminOverviewResponse(ORMModel):
    restaurants: RestaurantOverview
    orders: OrderOverview
