import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Provider(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "providers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str | None] = mapped_column(String(50))
    specialty: Mapped[str | None] = mapped_column(String(255))
    npi: Mapped[str | None] = mapped_column(String(20), unique=True)
    license_number: Mapped[str | None] = mapped_column(String(100))
    license_state: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
