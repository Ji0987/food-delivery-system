"""可由 API 層轉成明確 HTTP 狀態碼的業務例外。"""


class BusinessRuleError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PermissionRuleError(BusinessRuleError):
    pass


class ConflictRuleError(BusinessRuleError):
    pass


class NotFoundRuleError(BusinessRuleError):
    pass
