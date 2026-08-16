"""分页参数依赖：GET 列表统一使用。"""
from fastapi import Query


def page_params(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="每页条数"),
) -> tuple[int, int]:
    return page, page_size
