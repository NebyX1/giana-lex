from app.models import User


def test_create_admin_uses_sample_backend_positional_arguments(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "NebyX", "admin@example.test", "correct-password-123", "true"]
    )

    assert result.exit_code == 0
    assert "Super Admin NebyX created successfully." in result.output
    with app.app_context():
        user = User.query.filter_by(email="admin@example.test").one()
        assert user.display_name == "NebyX"
        assert user.is_superuser is True
        assert user.check_password("correct-password-123")


def test_create_admin_defaults_to_non_superuser(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "Admin", "admin@example.test", "correct-password-123"]
    )

    assert result.exit_code == 0
    with app.app_context():
        assert User.query.filter_by(email="admin@example.test").one().is_superuser is False
