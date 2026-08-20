from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask_login import UserMixin

from .extensions import db


password_hasher = PasswordHasher()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_superuser = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    otp_codes = db.relationship(
        "EmailOtpCode", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    roles = db.relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
        primaryjoin="User.id == UserRole.user_id",
        secondaryjoin="Role.id == UserRole.role_id",
        foreign_keys="[UserRole.user_id, UserRole.role_id]",
    )

    def has_role(self, role: str) -> bool:
        return self.is_superuser or any(item.name == role for item in self.roles)

    @property
    def role_names(self) -> set[str]:
        if self.is_superuser:
            return set(RBAC_ROLES)
        return {item.name for item in self.roles}

    def set_password(self, password: str) -> None:
        self.password_hash = password_hasher.hash(password)

    def check_password(self, password: str) -> bool:
        try:
            valid = password_hasher.verify(self.password_hash, password)
            if valid and password_hasher.check_needs_rehash(self.password_hash):
                self.set_password(password)
            return valid
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


RBAC_ROLES = frozenset({
    "legal_user",
    "legal_drafter",
    "legal_reviewer",
    "corpus_curator",
    "auditor",
    "technical_admin",
    "superuser",
})


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False, unique=True, index=True)
    users = db.relationship(
        "User", secondary="user_roles", back_populates="roles",
        primaryjoin="Role.id == UserRole.role_id",
        secondaryjoin="User.id == UserRole.user_id",
        foreign_keys="[UserRole.user_id, UserRole.role_id]",
    )


class UserRole(db.Model):
    __tablename__ = "user_roles"
    __table_args__ = (db.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    granted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class EmailOtpCode(db.Model):
    __tablename__ = "email_otp_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="otp_codes")

    @classmethod
    def create(cls, user_id: int, code: str, ttl_minutes: int) -> "EmailOtpCode":
        return cls(
            user_id=user_id,
            code_hash=password_hasher.hash(code),
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        )

    def verify(self, code: str, max_attempts: int) -> bool:
        if self.consumed_at or datetime.utcnow() >= self.expires_at or self.attempts >= max_attempts:
            return False
        self.attempts += 1
        try:
            valid = password_hasher.verify(self.code_hash, code)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            valid = False
        if valid:
            self.consumed_at = datetime.utcnow()
        return valid


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    event = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False)
    subject_type = db.Column(db.String(40), index=True)
    subject_id = db.Column(db.String(64), index=True)
    details = db.Column(db.Text)
    request_id = db.Column(db.String(36))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class ProviderConnection(db.Model):
    __tablename__ = "provider_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider = db.Column(db.String(40), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    auth_mode = db.Column(db.String(20), nullable=False)
    base_url = db.Column(db.String(500), nullable=False)
    default_model = db.Column(db.String(200), nullable=True)

    access_token_ciphertext = db.Column(db.Text, nullable=True)
    refresh_token_ciphertext = db.Column(db.Text, nullable=True)
    api_key_ciphertext = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    encryption_key_id = db.Column(db.String(60), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", backref="provider_connections")

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "auth_mode": self.auth_mode,
            "base_url": self.base_url,
            "default_model": self.default_model,
            "has_credentials": bool(
                self.api_key_ciphertext or self.access_token_ciphertext
            ),
        }


class AgentSession(db.Model):
    __tablename__ = "agent_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="SET NULL"), index=True)
    provider_connection_id = db.Column(
        db.Integer,
        db.ForeignKey("provider_connections.id"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False, default="Nueva conversacion")
    status = db.Column(db.String(32), nullable=False, default="ready", index=True)
    model = db.Column(db.String(200))
    active_skills = db.Column(db.Text, nullable=False, default="[]")
    pending_question = db.Column(db.Text)
    archived_at = db.Column(db.DateTime, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    user = db.relationship("User", backref="agent_sessions")
    provider_connection = db.relationship("ProviderConnection")
    messages = db.relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )
    tool_calls = db.relationship(
        "ToolCall",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def to_json(self, include_messages: bool = False) -> dict:
        data = {
            "id": self.id,
            "case_id": self.case_id,
            "title": self.title,
            "status": self.status,
            "provider_connection_id": self.provider_connection_id,
            "model": self.model,
            "active_skills": self.active_skills,
            "pending_question": self.pending_question,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_messages:
            data["messages"] = [message.to_json() for message in self.messages]
            data["tool_calls"] = [call.to_json() for call in self.tool_calls]
        return data


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(db.String(16), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False, default="")
    tool_call_id = db.Column(db.String(128), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    session = db.relationship("AgentSession", back_populates="messages")

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "tool_call_id": self.tool_call_id,
            "created_at": self.created_at.isoformat(),
        }


class ToolCall(db.Model):
    __tablename__ = "tool_calls"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id", ondelete="SET NULL"), index=True)
    call_id = db.Column(db.String(128), nullable=False, unique=True, index=True)
    tool_name = db.Column(db.String(120), nullable=False, index=True)
    arguments = db.Column(db.Text, nullable=False, default="{}")
    result = db.Column(db.Text)
    sources = db.Column(db.Text, nullable=False, default="[]")
    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    error = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)

    session = db.relationship("AgentSession", back_populates="tool_calls")
    message = db.relationship("Message")

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "call_id": self.call_id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "sources": self.sources,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class UploadedDocument(db.Model):
    __tablename__ = "uploaded_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="SET NULL"), index=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)
    mime_type = db.Column(db.String(120), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    session = db.relationship("AgentSession", backref=db.backref("uploaded_documents", cascade="all, delete-orphan"))

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "session_id": self.session_id,
            "filename": self.original_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat(),
        }
