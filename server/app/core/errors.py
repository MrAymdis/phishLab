"""统一错误码与业务异常。

分段：1xxx 通用 / 2xxx 认证权限 / 3xxx 参数 / 4xxx 业务 / 5xxx 集成 / 9xxx AI。
前端契约：code=40101 → 跳转登录；code=40301 → 提示数据权限不足。
"""


class ErrorCode:
    # 1xxx 通用
    INTERNAL = 10000
    PARAM_INVALID = 10001
    NOT_IMPLEMENTED = 10002
    NOT_FOUND = 10404
    # 2xxx/4xxx 认证与权限（40101/40301 为前端约定的具体码）
    UNAUTHORIZED = 40101
    TOKEN_EXPIRED = 40102
    ACCOUNT_DISABLED = 40103
    DATA_SCOPE_DENIED = 40301
    PERM_DENIED = 40302
    # 4xxx 业务
    CAMPAIGN_STATE_INVALID = 41001
    CHANNEL_TEST_FAILED = 41101
    BIZ_CONFLICT = 41002
    SYSTEM_INITIALIZED = 41003
    LICENSE_EXCEEDED = 42901
    RATE_LIMIT_EXCEEDED = 42902
    LICENSE_INVALID = 42903
    # 5xxx 集成
    INTEGRATION_ERROR = 50001
    # 9xxx AI
    AI_PROVIDER_ERROR = 90001


_DEFAULT_MSG = {
    ErrorCode.INTERNAL: "服务器内部错误",
    ErrorCode.PARAM_INVALID: "参数校验失败",
    ErrorCode.NOT_IMPLEMENTED: "功能尚未实现（脚手架占位）",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.TOKEN_EXPIRED: "登录已过期，请重新登录",
    ErrorCode.ACCOUNT_DISABLED: "账号已被禁用",
    ErrorCode.DATA_SCOPE_DENIED: "数据权限不足",
    ErrorCode.PERM_DENIED: "无操作权限",
    ErrorCode.LICENSE_EXCEEDED: "授权配额已用尽",
    ErrorCode.LICENSE_INVALID: "授权已失效",
    ErrorCode.RATE_LIMIT_EXCEEDED: "调用频率超限",
    ErrorCode.BIZ_CONFLICT: "业务状态冲突",
    ErrorCode.SYSTEM_INITIALIZED: "系统已初始化",
}

_HTTP_STATUS = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.ACCOUNT_DISABLED: 401,
    ErrorCode.DATA_SCOPE_DENIED: 403,
    ErrorCode.PERM_DENIED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
}


class BizError(Exception):
    """业务异常：统一由全局 handler 转为 {code, message, data} 响应。"""

    def __init__(self, code: int, message: str | None = None):
        self.code = code
        self.message = message or _DEFAULT_MSG.get(code, "业务错误")
        self.http_status = _HTTP_STATUS.get(code, 200)
        super().__init__(self.message)
