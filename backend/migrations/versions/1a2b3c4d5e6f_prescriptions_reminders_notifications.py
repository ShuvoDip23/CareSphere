"""Add prescriptions, medication reminders and notifications."""
from alembic import op
import sqlalchemy as sa

revision = "1a2b3c4d5e6f"
down_revision = "ffbbb7f7ae96"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_prescriptions_patient_id", "prescriptions", ["patient_id"])
    op.create_table("medication_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id"), nullable=True),
        sa.Column("medicine_name", sa.String(160), nullable=False),
        sa.Column("dosage", sa.String(120), nullable=False),
        sa.Column("frequency", sa.String(120), nullable=False),
        sa.Column("times", sa.JSON(), nullable=False),
        sa.Column("instructions", sa.String(500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_medication_reminders_patient_id", "medication_reminders", ["patient_id"])
    op.create_table("medication_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("medication_reminders.id"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("reminder_id", "scheduled_for", name="uq_med_log_slot"))
    op.create_index("ix_medication_logs_reminder_id", "medication_logs", ["reminder_id"])
    op.create_index("ix_medication_logs_patient_id", "medication_logs", ["patient_id"])
    op.create_index("ix_medication_logs_scheduled_for", "medication_logs", ["scheduled_for"])
    op.create_table("notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("dedupe_key", sa.String(180), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_notifications_patient_id", "notifications", ["patient_id"])


def downgrade():
    op.drop_table("notifications")
    op.drop_table("medication_logs")
    op.drop_table("medication_reminders")
    op.drop_table("prescriptions")
