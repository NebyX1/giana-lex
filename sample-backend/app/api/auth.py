import secrets
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf

from ..audit import record_event
from ..extensions import db, limiter
from ..models import EmailOtpCode, User
from ..services.mail_service import send_login_code


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
CAPTCHA_SESSION_KEY = "login_captcha_result"


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def _user_json(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "roles": sorted(user.role_names),
    }


def _clear_session_preserving_csrf() -> None:
    csrf_token = session.get("csrf_token")
    session.clear()
    if csrf_token:
        session["csrf_token"] = csrf_token


def _issue_captcha() -> dict[str, str]:
    left = secrets.randbelow(10) + 1
    right = secrets.randbelow(10) + 1
    session[CAPTCHA_SESSION_KEY] = left + right
    return {"question": f"{left} + {right}"}


@auth_bp.get("/csrf")
def csrf_token():
    return jsonify(csrf_token=generate_csrf())


@auth_bp.get("/captcha")
@limiter.limit("30 per minute")
def captcha():
    return jsonify(captcha=_issue_captcha())


@auth_bp.post("/login")
@limiter.limit("5 per minute")
def login():
    data = _payload()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    captcha_answer = str(data.get("captcha", "")).strip()
    expected_captcha = session.pop(CAPTCHA_SESSION_KEY, None)

    # The challenge is single-use, including failed attempts. This prevents a
    # captured answer from being replayed against multiple credential guesses.
    if expected_captcha is None or captcha_answer != str(expected_captcha):
        record_event("auth.captcha", "denied")
        db.session.commit()
        return jsonify(
            error="invalid_captcha",
            message="La verificación de seguridad es incorrecta.",
        ), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.is_active or not user.check_password(password):
        record_event("auth.password", "denied", user.id if user else None)
        db.session.commit()
        return jsonify(error="invalid_credentials", message="Credenciales inválidas."), 401

    EmailOtpCode.query.filter_by(user_id=user.id, consumed_at=None).update(
        {EmailOtpCode.consumed_at: datetime.utcnow()}
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = EmailOtpCode.create(user.id, code, current_app.config["OTP_TTL_MINUTES"])
    db.session.add(otp)
    record_event("auth.password", "accepted", user.id)
    db.session.commit()

    try:
        send_login_code(user.email, user.display_name, code)
    except Exception:
        current_app.logger.exception("Could not deliver login code for user %s", user.id)
        otp.consumed_at = datetime.utcnow()
        record_event("auth.otp_delivery", "failed", user.id)
        db.session.commit()
        return jsonify(error="otp_delivery_failed", message="No se pudo enviar el codigo de acceso."), 503

    _clear_session_preserving_csrf()
    session["pending_otp_user_id"] = user.id
    session["pending_otp_id"] = otp.id
    session.permanent = True
    return jsonify(status="verification_required", method="email_otp"), 202


@auth_bp.post("/verify")
@limiter.limit("10 per minute")
def verify():
    user_id = session.get("pending_otp_user_id")
    otp_id = session.get("pending_otp_id")
    code = str(_payload().get("code", "")).strip()
    if not user_id or not otp_id or len(code) != 6 or not code.isdigit():
        return jsonify(error="invalid_verification", message="Codigo de verificacion invalido."), 400

    user = db.session.get(User, user_id)
    otp = db.session.get(EmailOtpCode, otp_id)
    if not user or not user.is_active or not otp or otp.user_id != user.id:
        _clear_session_preserving_csrf()
        return jsonify(error="invalid_verification", message="Verificacion no disponible."), 401

    if not otp.verify(code, current_app.config["OTP_MAX_ATTEMPTS"]):
        record_event("auth.email_otp", "denied", user.id)
        db.session.commit()
        return jsonify(error="invalid_verification", message="Codigo incorrecto o vencido."), 401

    user.last_login_at = datetime.utcnow()
    record_event("auth.email_otp", "accepted", user.id)
    db.session.commit()
    _clear_session_preserving_csrf()
    login_user(user)
    session.permanent = True
    return jsonify(user=_user_json(user))


@auth_bp.get("/me")
@login_required
def me():
    return jsonify(user=_user_json(current_user))


@auth_bp.post("/logout")
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    _clear_session_preserving_csrf()
    record_event("auth.logout", "completed", user_id)
    db.session.commit()
    return "", 204
