import click
from flask.cli import with_appcontext

from .extensions import db
from .models import RBAC_ROLES, Role, User


def _ensure_identity_schema() -> None:
    db.create_all()
    existing_roles = {role.name for role in Role.query.all()}
    for role_name in RBAC_ROLES - existing_roles:
        db.session.add(Role(name=role_name))
    db.session.commit()


@click.command("create-user")
@click.option("--email", prompt=True)
@click.option("--display-name", prompt=True)
@click.option(
    "--password", prompt=True, hide_input=True, confirmation_prompt=True
)
@click.option("--superuser", is_flag=True)
@with_appcontext
def create_user(
    email: str, display_name: str, password: str, superuser: bool
) -> None:
    _ensure_identity_schema()
    email = email.strip().lower()
    if len(password) < 12:
        raise click.ClickException(
            "Password must contain at least 12 characters"
        )
    if User.query.filter_by(email=email).first():
        raise click.ClickException("A user with that email already exists")
    user = User(
        email=email, display_name=display_name.strip(), is_superuser=superuser
    )
    user.set_password(password)
    db.session.add(user)
    role_names = RBAC_ROLES if superuser else {"legal_user"}
    user.roles = Role.query.filter(Role.name.in_(role_names)).all()
    db.session.commit()
    click.echo(f"Created user {email}")


@click.command("create-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
@click.argument("is_superuser", default="false")
@with_appcontext
def create_admin(
    username: str, email: str, password: str, is_superuser: str
) -> None:
    """Create an administrator using the sample-backend interface."""
    _ensure_identity_schema()
    email = email.strip().lower()
    username = username.strip()
    if not username:
        raise click.ClickException("Username cannot be empty")
    if len(password) < 12:
        raise click.ClickException(
            "Password must contain at least 12 characters"
        )
    if User.query.filter_by(email=email).first():
        raise click.ClickException(f"User {email} already exists")

    is_super = is_superuser.lower() == "true"
    user = User(email=email, display_name=username, is_superuser=is_super)
    user.set_password(password)
    db.session.add(user)
    role_names = RBAC_ROLES if is_super else {"legal_user"}
    user.roles = Role.query.filter(Role.name.in_(role_names)).all()
    db.session.commit()
    role = "Super Admin" if is_super else "Admin"
    click.secho(f"{role} {username} created successfully.", fg="green")
