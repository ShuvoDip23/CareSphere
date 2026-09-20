"""Custom Flask CLI commands."""

import click
from flask import Flask

from .extensions import db


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command():
        """Load demo specialties, doctors and consulting windows."""
        from .seeds import seed_demo_data

        created = seed_demo_data()
        click.echo(
            "Seeded {specialties} specialties, {doctors} doctors, "
            "{windows} availability windows.".format(**created)
        )

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.argument("name")
    @click.password_option()
    def create_admin(email: str, name: str, password: str):
        """Create an administrator account.

        Replaces the prototype's update_role.py, which hard-coded one email
        address and edited the database with raw SQL.
        """
        from .models.user import User

        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            raise click.ClickException(f"{email} is already registered")

        user = User(email=email, name=name, role=User.ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created administrator {email}")
