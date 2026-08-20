import click
from flask.cli import with_appcontext
from hashlib import sha256
from pathlib import Path

from .extensions import db
from .models import RBAC_ROLES, Role, User


@click.group("examples")
def examples_group() -> None:
    """Manage the local SQL/filesystem precedent index."""


@examples_group.command("diagnose")
@with_appcontext
def examples_diagnose() -> None:
    from legal.infrastructure.models import ExampleProfileRecord, ExampleVersionRecord
    from legal.precedents.service import EXAMPLES_ROOT, validate_profiles

    reports = validate_profiles(EXAMPLES_ROOT)
    versions = ExampleVersionRecord.query.join(
        ExampleProfileRecord, ExampleProfileRecord.id == ExampleVersionRecord.example_id
    ).filter(ExampleVersionRecord.version == ExampleProfileRecord.current_version).all()
    counts = {}
    for item in versions:
        key = (item.act_subtype, item.validation_status)
        counts[key] = counts.get(key, 0) + 1
    for (subtype, status), count in sorted(counts.items()):
        click.echo(f"{subtype}\t{status}\t{count}")
    drift = 0
    for item in versions:
        path = Path(item.source_path)
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != item.source_checksum:
            drift += 1
    click.echo(
        f"files={len(reports)} valid_files={sum(item['valid'] for item in reports)} "
        f"indexed={len(versions)} drift={drift} collection=sql_filesystem"
    )


@examples_group.command("compile")
@with_appcontext
def examples_compile() -> None:
    from legal.precedents.service import compile_examples

    versions = compile_examples()
    db.session.commit()
    click.echo(f"compiled={len(versions)} index=sql_filesystem")


@examples_group.command("reindex")
@with_appcontext
def examples_reindex() -> None:
    from legal.precedents.service import compile_examples

    versions = compile_examples()
    db.session.commit()
    click.echo(f"reindexed={len(versions)} backend=sql_filesystem qdrant=not_used")


@examples_group.command("validate")
@with_appcontext
def examples_validate() -> None:
    from legal.precedents.service import validate_profiles

    reports = validate_profiles()
    invalid = [item for item in reports if not item["valid"]]
    for item in invalid:
        click.echo(f"invalid={item['path']} errors={','.join(item['errors'])}")
    click.echo(f"validated={len(reports)} invalid={len(invalid)} approvals_changed=0")
    if invalid:
        raise click.ClickException("One or more example profiles are incomplete")


@click.command("create-user")
@click.option("--email", prompt=True)
@click.option("--display-name", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--superuser", is_flag=True)
@with_appcontext
def create_user(email: str, display_name: str, password: str, superuser: bool) -> None:
    email = email.strip().lower()
    if len(password) < 12:
        raise click.ClickException("Password must contain at least 12 characters")
    if User.query.filter_by(email=email).first():
        raise click.ClickException("A user with that email already exists")
    user = User(email=email, display_name=display_name.strip(), is_superuser=superuser)
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
def create_admin(username: str, email: str, password: str, is_superuser: str) -> None:
    """Create an administrator using the sample-backend positional interface."""
    email = email.strip().lower()
    username = username.strip()
    if not username:
        raise click.ClickException("Username cannot be empty")
    if len(password) < 12:
        raise click.ClickException("Password must contain at least 12 characters")
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
