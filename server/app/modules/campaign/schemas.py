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
    domain_id: int | None = None
    target_mode: Literal["dept", "tag", "csv", "mix"] = "dept"
    target_snapshot: dict = Field(default_factory=dict, description="部门/分组/标签/CSV 圈选快照")
    schedule_type: Literal["now", "timed"] = "now"
    schedule_at: datetime | None = None
    ended_at: datetime | None = Field(None, description="演练结束时间（追踪期截止），留空按投递后 7 天")
    batch_count: int = Field(1, ge=1)
    batch_interval_min: int = Field(0, ge=0)
    randomize_content: bool = False
    time_jitter_sec: int = Field(0, ge=0)
    pixel_degrade: bool = False
    training_policy: Literal["redirect", "popup", "none", "url"] = "none"
    training_redirect_url: str | None = Field(None, max_length=512, description="url 模式跳转目标")
    attachment_ids: list[int] = Field(default_factory=list, description="附件载荷（直发模式）")
    course_ids: list[int] = Field(default_factory=list)
    force_training_rules: list[dict] = Field(default_factory=list)
    auth_confirmed: bool = Field(description="授权确认勾选，必须为 true 才可提交")


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
