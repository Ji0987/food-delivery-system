"""資料庫與 API 共用列舉。"""

from enum import Enum


class UserRole(str, Enum):
    CONSUMER = "consumer"
    RESTAURANT = "restaurant"
    COURIER = "courier"
    ADMIN = "admin"


class OrderStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PREPARING = "preparing"
    READY_FOR_PICKUP = "ready_for_pickup"
    PICKED_UP = "picked_up"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    REFUNDED = "refunded"
