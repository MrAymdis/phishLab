"""LLM Provider 适配层：统一客户端协议 + OpenAI 兼容 / Anthropic 实现 + 用量统计。

- 类型映射：openai/tongyi/local → OpenAI 兼容协议（endpoint 为 base URL，如
  https://api.openai.com/v1、DashScope 兼容端点、vLLM/Ollama/one-api）；
  claude → Anthropic Messages API；wenxin（百度千帆需 AK/SK 换取 access_token）暂不接入。
- 红线 2：API Key AES-GCM 加密入库（api_key_enc），本层运行时解密调用，绝不落日志。
- 数据外发约束：data_outbound=0（仅本地模型）时拒绝调用非 local 类型 provider。
- 用量：每次调用累计到 ai_usage_stat（provider×日期唯一），并回填 AiMessage。
"""
import json
import logging
from datetime import date
from typing import AsyncIterator, Protocol

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.core.security import decrypt_secret

from .models import AiProvider, AiUsageStat

logger = logging.getLogger("phishlab.llm")

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
_ANTHROPIC_VERSION = "2023-06-01"

# type → 适配客户端类
_CLIENT_CLASSES: dict[str, type] = {}


def _register(cls):
    _CLIENT_CLASSES[cls.type] = cls
    return cls


class LLMClient(Protocol):
    """统一 Provider 客户端协议（chat 非流式 / stream 流式，均返回用量）。"""

    type: str

    def __init__(self, provider: AiProvider, api_key: str): ...

    async def chat(self, messages: list[dict], *, system_prompt: str | None = None,
                   temperature: float, max_tokens: int) -> dict:
        """返回 {"content": str, "tokens_in": int|None, "tokens_out": int|None}。"""

    async def stream(self, messages: list[dict], *, system_prompt: str | None = None,
                     temperature: float, max_tokens: int) -> AsyncIterator[dict]:
        """yield {"type": "token", "content": str}；结尾 yield {"type": "usage", ...}。"""


def _mk_http(provider: AiProvider, api_key: str) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return httpx.AsyncClient(timeout=_TIMEOUT, headers=headers)


async def _sse_tokens(lines) -> AsyncIterator[str]:
    """解析 OpenAI 兼容 SSE 行，产出 content 增量。"""
    async for line in lines:
        line = (line or "").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        choice = (payload.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        text = delta.get("content")
        if text:
            yield str(text)
        # stream_options.include_usage 时最后一个 chunk 带 usage（标准在顶层，
        # 部分兼容端点放在 choice 内，两层都取）
        usage = payload.get("usage") or choice.get("usage") or {}
        if usage.get("prompt_tokens") is not None or usage.get("input_tokens") is not None:
            yield json.dumps({"__usage": {
                "in": usage.get("prompt_tokens") or usage.get("input_tokens"),
                "out": usage.get("completion_tokens") or usage.get("output_tokens"),
            }})


@_register
class OpenAICompatClient:
    """OpenAI 兼容协议（openai/tongyi/local 共用，endpoint 为 base URL）。"""

    type = "openai"

    def __init__(self, provider: AiProvider, api_key: str):
        self.provider = provider
        self.base = (provider.endpoint or "https://api.openai.com/v1").rstrip("/")
        self.http = _mk_http(provider, api_key)

    def _body(self, messages, system_prompt, temperature, max_tokens, stream: bool) -> dict:
        msgs = [{"role": "system", "content": system_prompt}] if system_prompt else []
        msgs += messages
        return {
            "model": self.provider.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    async def _post(self, payload: dict):
        resp = await self.http.post(f"{self.base}/chat/completions", json=payload)
        if resp.status_code >= 400:
            raise BizError(ErrorCode.AI_PROVIDER_ERROR,
                           f"LLM 调用失败（{self.provider.name} HTTP {resp.status_code}）："
                           f"{resp.text[:200]}")
        return resp

    async def chat(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048) -> dict:
        resp = await self._post(self._body(messages, system_prompt, temperature, max_tokens, False))
        data = resp.json()
        usage = data.get("usage") or {}
        msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
        return {
            "content": msg.get("content") or "",
            # 推理型模型（deepseek-reasoner 类）思考过程：内容被 max_tokens 截断时
            # content 可能为空，调用方可用 reasoning_content 兜底提取
            "reasoning_content": msg.get("reasoning_content") or "",
            "tokens_in": usage.get("prompt_tokens"),
            "tokens_out": usage.get("completion_tokens"),
        }

    async def stream(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048) -> AsyncIterator[dict]:
        body = self._body(messages, system_prompt, temperature, max_tokens, True)
        body["stream_options"] = {"include_usage": True}  # 部分端点不支持，忽略
        async with self.http.stream("POST", f"{self.base}/chat/completions", json=body) as resp:
            if resp.status_code >= 400:
                text = (await resp.aread()).decode("utf-8", "ignore")[:200]
                raise BizError(ErrorCode.AI_PROVIDER_ERROR,
                               f"LLM 调用失败（{self.provider.name} HTTP {resp.status_code}）：{text}")
            tokens_in = tokens_out = None
            async for chunk in _sse_tokens(resp.aiter_lines()):
                if chunk.startswith('{"__usage"'):
                    try:
                        u = json.loads(chunk)["__usage"]
                        tokens_in, tokens_out = u["in"], u["out"]
                    except (KeyError, ValueError):
                        pass
                    continue
                yield {"type": "token", "content": chunk}
        yield {"type": "usage", "tokens_in": tokens_in, "tokens_out": tokens_out}


@_register
class AnthropicClient:
    """Anthropic Messages API（type=claude）。"""

    type = "claude"

    def __init__(self, provider: AiProvider, api_key: str):
        self.provider = provider
        self.base = (provider.endpoint or "https://api.anthropic.com/v1").rstrip("/")
        self.http = httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers={
                "x-api-key": api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
        )

    def _payload(self, messages, system_prompt, temperature, max_tokens, stream: bool) -> dict:
        # Anthropic 要求 user/assistant 严格交替且末条为 user：合并连续同角色，尾部补 user
        merged: list[dict] = []
        for m in messages:
            role = m.get("role") if m.get("role") in ("user", "assistant") else "user"
            content = str(m.get("content", ""))
            if merged and merged[-1]["role"] == role:
                merged[-1]["content"] += "\n" + content
            else:
                merged.append({"role": role, "content": content})
        if merged and merged[-1]["role"] == "assistant":
            merged.append({"role": "user", "content": "（继续）"})
        return {
            "model": self.provider.model,
            "system": system_prompt or "",
            "messages": merged,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

    async def _check(self, resp: httpx.Response):
        if resp.status_code >= 400:
            raise BizError(ErrorCode.AI_PROVIDER_ERROR,
                           f"LLM 调用失败（{self.provider.name} HTTP {resp.status_code}）："
                           f"{resp.text[:200]}")

    async def chat(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048) -> dict:
        resp = await self.http.post(f"{self.base}/messages",
                                    json=self._payload(messages, system_prompt, temperature, max_tokens, False))
        await self._check(resp)
        data = resp.json()
        usage = data.get("usage") or {}
        return {
            "content": "".join(b.get("text", "") for b in data.get("content") or []),
            "tokens_in": usage.get("input_tokens"),
            "tokens_out": usage.get("output_tokens"),
        }

    async def stream(self, messages, *, system_prompt=None, temperature=0.7, max_tokens=2048) -> AsyncIterator[dict]:
        async with self.http.stream("POST", f"{self.base}/messages",
                                    json=self._payload(messages, system_prompt, temperature, max_tokens, True)) as resp:
            if resp.status_code >= 400:
                text = (await resp.aread()).decode("utf-8", "ignore")[:200]
                raise BizError(ErrorCode.AI_PROVIDER_ERROR,
                               f"LLM 调用失败（{self.provider.name} HTTP {resp.status_code}）：{text}")
            tokens_in = tokens_out = None
            async for line in resp.aiter_lines():
                line = (line or "").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "message_start":
                    u = (evt.get("message") or {}).get("usage") or {}
                    tokens_in = u.get("input_tokens")
                elif evt.get("type") == "content_block_delta":
                    delta = evt.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield {"type": "token", "content": delta["text"]}
                elif evt.get("type") == "message_delta":
                    u = evt.get("usage") or {}
                    tokens_out = u.get("output_tokens")
        yield {"type": "usage", "tokens_in": tokens_in, "tokens_out": tokens_out}


def get_provider(db: Session, provider_id: int | None = None,
                 prefer_type: str | None = None) -> AiProvider | None:
    """取启用中的 Provider：指定 id / 指定类型 / 第一个启用。无可用返回 None。"""
    if provider_id:
        p = db.get(AiProvider, provider_id)
        return p if p and p.enabled == 1 else None
    stmt = select(AiProvider).where(AiProvider.enabled == 1).order_by(AiProvider.id)
    rows = db.scalars(stmt).all()
    if prefer_type:
        for p in rows:
            if p.type == prefer_type:
                return p
    return rows[0] if rows else None


def get_client(db: Session, provider: AiProvider) -> LLMClient:
    """构建适配客户端；数据外发约束校验（红线：敏感数据不外发）。"""
    if provider.type not in _CLIENT_CLASSES:
        raise BizError(ErrorCode.AI_PROVIDER_ERROR,
                       f"Provider 类型 {provider.type} 暂未接入"
                       + ("（文心千帆需 AK/SK 换取 access_token）" if provider.type == "wenxin" else ""))
    if provider.data_outbound == 0 and provider.type != "local":
        raise BizError(ErrorCode.AI_PROVIDER_ERROR,
                       f"Provider {provider.name} 标记为数据不外发，仅允许本地模型调用")
    api_key = ""
    if provider.api_key_enc:
        try:
            api_key = decrypt_secret(provider.api_key_enc)
        except Exception:
            logger.exception("provider api_key 解密失败 provider=%s", provider.id)
            raise BizError(ErrorCode.AI_PROVIDER_ERROR, f"Provider {provider.name} API Key 解密失败")
    return _CLIENT_CLASSES[provider.type](provider, api_key)


def record_usage(db: Session, provider: AiProvider, tokens_in: int | None, tokens_out: int | None) -> None:
    """用量按 provider×日期累加（幂等 upsert）。"""
    tokens_in = int(tokens_in or 0)
    tokens_out = int(tokens_out or 0)
    if not provider:
        return
    today = date.today()
    row = db.scalar(
        select(AiUsageStat).where(AiUsageStat.provider_id == provider.id,
                                  AiUsageStat.stat_date == today)
    )
    if row is None:
        db.add(AiUsageStat(provider_id=provider.id, stat_date=today,
                           call_count=1, tokens_in=tokens_in, tokens_out=tokens_out))
    else:
        row.call_count = (row.call_count or 0) + 1
        row.tokens_in = (row.tokens_in or 0) + tokens_in
        row.tokens_out = (row.tokens_out or 0) + tokens_out
    db.commit()
