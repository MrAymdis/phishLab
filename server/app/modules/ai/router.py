import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core import response as resp
from app.core.deps import get_current_account, require_perm
from app.db.session import get_db

from . import service

ai = APIRouter(prefix="/api/v1/ai", tags=["智能助手"], dependencies=[Depends(get_current_account), Depends(require_perm("menu:/ai"))])
routers = [ai]


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str
    page_context: dict | None = None


class GenerateTemplateRequest(BaseModel):
    scene: str
    audience: str | None = None
    tone: str | None = None
    language: str = "zh"
    difficulty: int = 2


class AnalysisRequest(BaseModel):
    kind: str  # campaign_effect/dept_risk/trend_forecast/training_recommend
    target: dict = {}


class ChatbiRequest(BaseModel):
    question: str


class ProviderPayload(BaseModel):
    name: str
    type: str  # openai/claude/wenxin/tongyi/local
    endpoint: str | None = None
    api_key: str | None = None  # 更新时留空 = 不更换 Key
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str | None = None
    enabled: bool = True
    data_outbound: bool = True  # False = 仅本地模型可调用


@ai.get("/providers", summary="LLM Provider 列表（Key 掩码回显）",
        dependencies=[Depends(require_perm("ai:manage"))])
def list_providers(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_providers(db))


@ai.post("/providers", summary="创建 LLM Provider（API Key AES-GCM 加密入库）",
         dependencies=[Depends(require_perm("ai:manage"))])
def create_provider(req: ProviderPayload, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.create_provider(db, account, req.model_dump()))


@ai.put("/providers/{pid}", summary="更新 Provider（api_key 留空不更换）",
        dependencies=[Depends(require_perm("ai:manage"))])
def update_provider(pid: int, req: ProviderPayload, account=Depends(get_current_account),
                    db: Session = Depends(get_db)):
    return resp.ok(service.update_provider(db, account, pid, req.model_dump()))


@ai.delete("/providers/{pid}", summary="删除 Provider",
           dependencies=[Depends(require_perm("ai:manage"))])
def delete_provider(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.delete_provider(db, account, pid))


@ai.post("/providers/{pid}/test", summary="连通性测试（最小 chat 请求）",
         dependencies=[Depends(require_perm("ai:manage"))])
async def test_provider(pid: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(await service.test_provider(db, pid))


@ai.post("/chatbi", summary="ChatBI 问数（红线 5：只读 + 表白名单 + 校验 + 权限注入 + 审计）")
async def chatbi(req: ChatbiRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    from . import chatbi as chatbi_svc

    return resp.ok(await chatbi_svc.ask_question(db, account, req.question))


@ai.get("/sessions", summary="会话列表")
def sessions(account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_sessions(db, account))


@ai.post("/chat/stream", summary="Copilot 对话（SSE 流式）")
async def chat_stream(req: ChatRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    # 注意：service.chat_stream 在生成器开始前完成 DB 持久化，不跨 SSE 持有请求 session
    return EventSourceResponse(service.chat_stream(db, account, req.model_dump()))


@ai.post("/templates/generate", summary="AI 模板生成（进草稿审核）")
async def gen_template(req: GenerateTemplateRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"draft_id": await service.generate_template(db, account, req.model_dump())})


@ai.post("/analysis/generate", summary="智能分析报告（进草稿审核）")
async def gen_analysis(req: AnalysisRequest, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok({"draft_id": await service.generate_analysis(db, account, req.kind, req.target)})


@ai.get("/drafts", summary="AI 草稿列表")
def drafts(status: str | None = None, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.list_drafts(db, account, status))


@ai.post("/drafts/{did}/approve", summary="确认入库（记录审核人/时间）", dependencies=[Depends(require_perm("ai:review"))])
def approve(did: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.approve_draft(db, account, did))


@ai.post("/drafts/{did}/discard", summary="丢弃草稿", dependencies=[Depends(require_perm("ai:review"))])
def discard(did: int, account=Depends(get_current_account), db: Session = Depends(get_db)):
    return resp.ok(service.discard_draft(db, account, did))
