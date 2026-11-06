# -*- coding: utf-8 -*-
"""简单访问鉴权：密码登录 → 内存 token"""
import secrets

from fastapi import HTTPException, Request

from .config import CONFIG

_tokens = set()


def login(password):
    if password != CONFIG.get("password", ""):
        return None
    t = secrets.token_hex(16)
    _tokens.add(t)
    return t


def logout(token):
    _tokens.discard(token)


def verify(request: Request):
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.query_params.get("token", "")
    if token not in _tokens:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return token


def valid(token):
    return token in _tokens
