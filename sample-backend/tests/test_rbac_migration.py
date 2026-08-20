from pathlib import Path

from flask_migrate import upgrade
from sqlalchemy import create_engine, text

from app import create_app
from app.config import TestingConfig


def test_rbac_migration_backfills_active_and_superusers(tmp_path, monkeypatch):
    database = tmp_path / "rbac-migration.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", url)
    application = create_app("testing")
    migrations = str(Path(__file__).resolve().parents[1] / "migrations")
    with application.app_context():
        upgrade(directory=migrations, revision="f5e0a1b2c3d4")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users "
            "(email, display_name, password_hash, is_active, is_superuser, created_at) VALUES "
            "('active@test', 'Active', 'x', 1, 0, CURRENT_TIMESTAMP), "
            "('super@test', 'Super', 'x', 1, 1, CURRENT_TIMESTAMP), "
            "('inactive@test', 'Inactive', 'x', 0, 0, CURRENT_TIMESTAMP)"
        ))
    with application.app_context():
        upgrade(directory=migrations, revision="head")
    with engine.connect() as connection:
        assignments = connection.execute(text(
            "SELECT users.email, roles.name FROM user_roles "
            "JOIN users ON users.id = user_roles.user_id "
            "JOIN roles ON roles.id = user_roles.role_id"
        )).all()
    by_user = {}
    for email, role in assignments:
        by_user.setdefault(email, set()).add(role)
    assert by_user["active@test"] == {"legal_user"}
    assert by_user["super@test"] == {
        "legal_user", "legal_drafter", "legal_reviewer", "corpus_curator",
        "auditor", "technical_admin", "superuser",
    }
    assert "inactive@test" not in by_user
