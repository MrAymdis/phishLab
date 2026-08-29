"""演练域请求/响应模型（7 步向导一次性提交或草稿暂存）。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str | None = None
    type: Literal["mail", "sms", "social", "usb"]
    template_id: int | None = None
    landing_page_id: int | None = None
    channel_id: int | None = None
    sender_profile_id: int | None = None
    track_base_url: str | None = Field(None, max_length=128, description="演练级追踪域覆盖，空=沿用全局设置")
    landing_base_url: str | None = Field(None, max_length=128, description="演练级落地域覆盖，空=沿用全局设置")
    target_mode: Literal["dept", "tag", "csv", "mix"] = "dept"
    target_snapshot: dict = Field(default_factory=dict, description="部门/分组/标签/CSV 圈选快照")
    schedule_type: Literal["now", "timed"] = "now"
    schedule_at: datetime | None = None
    ended_at: datetime | None = Field(None, description="演练结束时间（追踪期截止），留空按投递后 7 天")
    batch_count: int = Field(1, ge=1)
    batch_interval_min: int = Field(0, ge=0)
    randomize_content: bool = False
    time_jitter_sec: int = Field(0, ge=0, le=600, description="发送时刻抖动：两封之间随机 0~N 秒（0=关闭，封顶 600）")
    pixel_degrade: bool = False
    training_policy: Literal["redirect", "popup", "none", "url"] = "none"
    training_redirect_url: str | None = Field(None, max_length=512, description="url 模式跳转目标")
    attachment_ids: list[int] = Field(default_factory=list, description="附件载荷（直发模式）")
    course_ids: list[int] = Field(default_factory=list)
    force_training_rules: list[dict] = Field(default_factory=list)
    auth_confirmed: bool = Field(description="授权确认勾选，必须为 true 才可提交")
    auth_snapshot: list[str] = Field(
        default_factory=list,
        description="授权勾选项快照（企微演练须含 wecom:written_auth/wecom:domain_verified/wecom:internal_only，红线4）")
    wecom_template_id: int | None = Field(None, description="企微消息模板（social 演练用）")


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    type: str
    status: str
    creator_id: int
    target_count: int
    schedule_type: str
    schedule_at: datetime | None
    batch_count: int
    training_policy: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
