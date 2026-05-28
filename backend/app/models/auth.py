from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.models.database import Base


class AppUser(Base):
    """站内用户账号。闲鱼授权独立绑定，不直接等同于站内登录态。"""

    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login_at = Column(DateTime, nullable=True)


class AppSession(Base):
    """站内会话。每个账号有自己的 token，不与闲鱼 cookie 混用。"""

    __tablename__ = "app_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class XianyuAuthBinding(Base):
    """站内账号绑定的闲鱼授权态。多个站内账号可以绑定同一个闲鱼账号。"""

    __tablename__ = "xianyu_auth_bindings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), unique=True, nullable=False, index=True)
    provider = Column(String(64), default="playwright_storage_state")
    xianyu_account_label = Column(String(128), nullable=True)
    storage_state_path = Column(String(1024), nullable=False)
    status = Column(String(32), default="unverified", index=True)
    last_verified_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
