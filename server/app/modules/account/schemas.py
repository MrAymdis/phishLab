from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    account_id: int
    username: str
    real_name: str


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    status: int


class AccountCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, description="登录名，唯一")
    real_name: str = Field(min_length=1, max_length=64, description="真实姓名")
    password: str = Field(min_length=8, max_length=64, description="初始密码")
    role_ids: list[int] = Field(default_factory=list, description="分配角色")


class AccountUpdate(BaseModel):
    real_name: str = Field(min_length=1, max_length=64)
    role_ids: list[int] = Field(default_factory=list, description="覆盖式分配角色")
    status: int = Field(1, ge=0, le=1, description="1启用 0禁用")


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=64)


class ProfileUpdate(BaseModel):
    """个人中心：修改本人资料（无需管理员权限）。"""

    real_name: str = Field(min_length=1, max_length=64)


class PasswordChange(BaseModel):
    """个人中心：修改本人密码（需验证旧密码）。"""

    old_password: str
    new_password: str = Field(min_length=8, max_length=64)


class InitRequest(BaseModel):
    """首启初始化：创建超级管理员（仅系统无任何账号时可用）。"""

    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=64, description="初始密码，首次登录后请修改")
    real_name: str | None = Field(None, max_length=64)
