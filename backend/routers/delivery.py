"""外送員搶單與訂單配送位置 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import CurrentUser, DatabaseSession, require_role
from backend.models.delivery import DeliveryAssignment, DeliveryLocation
from backend.models.enums import UserRole
from backend.models.order import Order
from backend.models.user import User
from backend.schemas.delivery import (
    AvailableOrderResponse,
    DeliveryAssignmentResponse,
    DeliveryLocationCreate,
    DeliveryLocationResponse,
)
from backend.services.delivery_service import (
    claim_order,
    get_latest_location,
    get_location_history,
    list_available_orders,
    record_location,
)
from backend.services.exceptions import (
    ConflictRuleError,
    NotFoundRuleError,
    PermissionRuleError,
)


router = APIRouter(prefix="/orders", tags=["delivery"])
CourierActor = Annotated[User, Depends(require_role(UserRole.COURIER))]


def _to_http_error(error: Exception) -> HTTPException:
    if isinstance(error, NotFoundRuleError):
        return HTTPException(status_code=404, detail=error.detail)
    if isinstance(error, PermissionRuleError):
        return HTTPException(status_code=403, detail=error.detail)
    if isinstance(error, ConflictRuleError):
        return HTTPException(status_code=409, detail=error.detail)
    return HTTPException(status_code=500, detail="配送操作失敗")


@router.get("/available", response_model=list[AvailableOrderResponse])
def read_available_orders(db: DatabaseSession, _actor: CourierActor) -> list[Order]:
    return list_available_orders(db)


@router.post(
    "/{order_id}/claim",
    response_model=DeliveryAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def claim_available_order(
    order_id: int, db: DatabaseSession, actor: CourierActor
) -> DeliveryAssignment:
    try:
        return claim_order(db, order_id, actor)
    except (NotFoundRuleError, PermissionRuleError, ConflictRuleError) as error:
        db.rollback()
        raise _to_http_error(error) from error


@router.post(
    "/{order_id}/locations",
    response_model=DeliveryLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    order_id: int,
    payload: DeliveryLocationCreate,
    db: DatabaseSession,
    actor: CourierActor,
) -> DeliveryLocation:
    try:
        return record_location(
            db,
            order_id,
            actor,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
    except (NotFoundRuleError, PermissionRuleError, ConflictRuleError) as error:
        db.rollback()
        raise _to_http_error(error) from error


@router.get("/{order_id}/locations/latest", response_model=DeliveryLocationResponse)
def read_latest_location(
    order_id: int, db: DatabaseSession, actor: CurrentUser
) -> DeliveryLocation:
    try:
        return get_latest_location(db, order_id, actor)
    except (NotFoundRuleError, PermissionRuleError) as error:
        raise _to_http_error(error) from error


@router.get("/{order_id}/locations", response_model=list[DeliveryLocationResponse])
def read_location_history(
    order_id: int, db: DatabaseSession, actor: CurrentUser
) -> list[DeliveryLocation]:
    try:
        return get_location_history(db, order_id, actor)
    except (NotFoundRuleError, PermissionRuleError) as error:
        raise _to_http_error(error) from error
