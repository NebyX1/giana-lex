from flask import current_app, render_template
from flask_mail import Message

from .extensions import mail


def send_login_code(email: str, display_name: str, code: str) -> None:
    if not current_app.config.get("MAIL_DEFAULT_SENDER"):
        raise RuntimeError("MAIL_DEFAULT_SENDER is not configured")
    context = {"display_name": display_name, "code": code, "ttl": current_app.config["OTP_TTL_MINUTES"]}
    body = render_template("email/login_code.txt", **context)
    html = render_template("email/login_code.html", **context)
    mail.send(Message(subject="Código de acceso a Giana-Lex", recipients=[email], body=body, html=html))
