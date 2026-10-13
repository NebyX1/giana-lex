from datetime import datetime, timezone, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask_login import UserMixin

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


password_hasher = PasswordHasher()
RBAC_ROLES = frozenset({
    "legal_user", "legal_drafter", "legal_reviewer", "corpus_curator",
    "auditor", "technical_admin", "superuser",
})


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_superuser = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    last_login_at = db.Column(db.DateTime)
    otp_codes = db.relationship("EmailOtpCode", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    roles = db.relationship(
        "Role", secondary="user_roles", back_populates="users", lazy="selectin",
        primaryjoin="User.id == UserRole.user_id", secondaryjoin="Role.id == UserRole.role_id",
        foreign_keys="[UserRole.user_id, UserRole.role_id]",
    )

    def has_role(self, role: str) -> bool:
        return self.is_superuser or any(item.name == role for item in self.roles)

    @property
    def role_names(self) -> set[str]:
        return set(RBAC_ROLES) if self.is_superuser else {item.name for item in self.roles}

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


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False, unique=True, index=True)
    users = db.relationship(
        "User", secondary="user_roles", back_populates="roles",
        primaryjoin="Role.id == UserRole.role_id", secondaryjoin="User.id == UserRole.user_id",
        foreign_keys="[UserRole.user_id, UserRole.role_id]",
    )


class UserRole(db.Model):
    __tablename__ = "user_roles"
    __table_args__ = (db.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    granted_at = db.Column(db.DateTime, nullable=False, default=utc_now)


class EmailOtpCode(db.Model):
    __tablename__ = "email_otp_codes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    user = db.relationship("User", back_populates="otp_codes")

    @classmethod
    def create(cls, user_id: int, code: str, ttl_minutes: int):
        return cls(user_id=user_id, code_hash=password_hasher.hash(code), expires_at=utc_now() + timedelta(minutes=ttl_minutes))

    def verify(self, code: str, max_attempts: int) -> bool:
        if self.consumed_at or utc_now() >= self.expires_at or self.attempts >= max_attempts:
            return False
        self.attempts += 1
        try:
            valid = password_hasher.verify(self.code_hash, code)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            valid = False
        if valid:
            self.consumed_at = utc_now()
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
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
