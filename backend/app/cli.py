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
            "{windows} availability windows, {donors} blood donors.".format(**created)
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

    @app.cli.command("link-doctor")
    @click.argument("email")
    @click.argument("doctor_id", type=int)
    def link_doctor(email: str, doctor_id: int):
        """Attach an existing user account to a doctor profile.

        A stopgap until doctors register themselves (PORTING.md row 11). That
        flow will create the user and the profile together and is where the
        one-account-per-profile rule belongs as a database constraint - here a
        single admin runs one command at a time, so there is no race to lose.
        """
        from .models.doctor import Doctor
        from .models.user import User

        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None:
            raise click.ClickException(f"No account found for {email}")

        doctor = db.session.get(Doctor, doctor_id)
        if doctor is None:
            raise click.ClickException(f"No doctor profile with id {doctor_id}")

        if doctor.user_id and doctor.user_id != user.id:
            raise click.ClickException(
                f"{doctor.name} is already linked to another account (user {doctor.user_id})"
            )
        existing = Doctor.query.filter(Doctor.user_id == user.id, Doctor.id != doctor.id).first()
        if existing is not None:
            raise click.ClickException(
                f"{email} is already linked to {existing.name} (doctor {existing.id})"
            )

        doctor.user_id = user.id
        user.role = User.ROLE_DOCTOR
        db.session.commit()
        click.echo(f"Linked {email} to {doctor.name} (doctor {doctor.id})")
