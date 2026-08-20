from app.extensions import mail
from app.services.mail_service import send_login_code


def test_login_code_email_has_html_and_plain_text(app):
    with app.app_context(), mail.record_messages() as outbox:
        send_login_code("persona@example.test", "Persona Jurídica", "558190")

    assert len(outbox) == 1
    message = outbox[0]
    assert message.subject == "Código de acceso a Giana-Lex"
    assert message.recipients == ["persona@example.test"]
    assert "Tu código de acceso es: 558190" in message.body
    assert "558190" in message.html
    assert "Código de un solo uso" in message.html
    assert "Válido durante 10 minutos" in message.html
    assert "GIANA-LEX" in message.html


def test_login_code_email_escapes_display_name(app):
    with app.app_context(), mail.record_messages() as outbox:
        send_login_code("persona@example.test", "<script>alert(1)</script>", "123456")

    assert "<script>" not in outbox[0].html
    assert "&lt;script&gt;" in outbox[0].html
