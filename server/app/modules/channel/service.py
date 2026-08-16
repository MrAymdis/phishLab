"""发送配置服务：通道适配器工厂 + 占位实现。

通道适配器接口（一期实现）：

    class ChannelAdapter(Protocol):
        def validate(self, config) -> TestResult: ...
        def test_send(self, config, to: str) -> TestResult: ...
        async def send(self, config, msg: PhishMessage) -> SendResult: ...

实现：SmtpAdapter(aiosmtplib) / EwsAdapter(exchangelib) / SmsAdapter(云SDK/httpx/pyserial)
"""
from app.core.errors import BizError, ErrorCode

# ---------- 通道 ----------

def list_channels(db, account):
    """列表：密码类字段只回显掩码。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_channel(db, account, payload: dict) -> int:
    """敏感字段 encrypt_secret 入库；保存前强制连通测试。TODO(一期)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def test_channel(db, account, channel_id: int, to: str | None = None) -> dict:
    """连通性 + 鉴权测试，结果写 last_test_result。TODO(一期)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


# ---------- 域名 DNS ----------

def list_domains(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def add_domain(db, account, payload: dict) -> int:
    """录入域名 → 生成 DKIM 密钥对 → 输出 SPF/DMARC 推荐记录。TODO(一期)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def check_dns(db, account, domain_id: int) -> dict:
    """dnspython 巡检 SPF/DKIM/DMARC/MX → 状态 + 送达评分(0-100) + 修复指引。TODO(一期)。"""
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


# ---------- 伪装发件人 ----------

def list_sender_profiles(db, account):
    raise BizError(ErrorCode.NOT_IMPLEMENTED)


def create_sender_profile(db, account, payload: dict) -> int:
    raise BizError(ErrorCode.NOT_IMPLEMENTED)
