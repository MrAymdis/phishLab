"""统一响应包装：{code, message, data}；分页 {list, total, page, pageSize}。"""
from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def page(items: list, total: int, page: int, page_size: int) -> dict:
    return ok({"list": items, "total": total, "page": page, "pageSize": page_size})
