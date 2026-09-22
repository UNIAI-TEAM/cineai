# -*- coding: utf-8 -*-
"""ValueError → HTTP 异常映射。"""
from __future__ import annotations

from fastapi import HTTPException

from app.errors import AppError


def http_exception_for_value_error(exc: ValueError) -> HTTPException | AppError:
    """AppError 原样交给全局处理器（保留 code / 状态码，余额不足即 402）；其余 ValueError → 400。"""
    if isinstance(exc, AppError):
        return exc.clone()
    return HTTPException(status_code=400, detail=str(exc))
