"""
会话管理 —— 记住多轮对话的上下文。

【为什么需要】
    用户问「那他们的成绩呢？」，助手得知道「他们」是谁。
    所以每一轮都要把最近的问答带进上下文。

【存储方式】
    内存（进程内 dict）。不落盘、不进数据库 —— 教务数据不外传，
    重启服务就清空也符合「临时问答」的定位。

【为什么要限制轮数】
    上下文越长 token 越贵，也越容易让模型跑偏。
    只保留最近 N 轮（默认 8 轮），并在超长时【截断单条内容】，
    避免某一条特别长的回答把整个上下文撑爆。
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class Turn:
    """一轮对话。"""

    role: str
    content: str
    at: float = field(default_factory=time.time)


@dataclass
class Session:
    """一个会话。"""

    session_id: str
    turns: list[Turn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add(self, role: str, content: str) -> None:
        self.turns.append(Turn(role=role, content=content))
        self.updated_at = time.time()

    def history(self, max_turns: int) -> list[dict[str, str]]:
        """
        取最近 max_turns 轮，转成 Messages API 的格式。

        单条内容超过 2000 字就截断 —— 防止某条超长回答把上下文撑爆。
        """
        recent = self.turns[-max_turns * 2:]
        result: list[dict[str, str]] = []
        for turn in recent:
            content = turn.content
            if len(content) > 2000:
                content = content[:2000] + ' …（内容过长已截断）'
            result.append({'role': turn.role, 'content': content})
        return result


class SessionStore:
    """
    内存会话仓库。

    用 OrderedDict + LRU 淘汰：超过上限就把最久没用的会话踢掉，
    防止长时间运行后内存无限增长。
    """

    def __init__(self, max_sessions: int = 200) -> None:
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._max_sessions = max_sessions

    def get_or_create(self, session_id: str | None) -> Session:
        """取会话；没有就新建一个。"""
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            self._sessions.move_to_end(session_id)
            return session

        new_id = session_id or uuid.uuid4().hex
        session = Session(session_id=new_id)
        self._sessions[new_id] = session
        self._sessions.move_to_end(new_id)
        self._evict()
        return session

    def clear(self, session_id: str) -> bool:
        """清空一个会话的上下文。"""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.turns.clear()
        session.updated_at = time.time()
        return True

    def delete(self, session_id: str) -> bool:
        """彻底删掉一个会话。"""
        return self._sessions.pop(session_id, None) is not None

    def _evict(self) -> None:
        """超出容量上限时淘汰最久未使用的会话。"""
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)


sessions = SessionStore()
