import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.assessment import Assessment


class BiologicalSex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Patient(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "patients"

    # Identity
    mrn: Mapped[str | None] = mapped_column(String(100), index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    biological_sex: Mapped[BiologicalSex | None] = mapped_column(
        Enum(BiologicalSex, values_callable=lambda x: [e.value for e in x], create_type=False)
    )
    gender_identity: Mapped[str | None] = mapped_column(String(100))

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)

    # Medical background (pre-filled from intake)
    allergies: Mapped[list] = mapped_column(JSONB, default=list)
    chronic_conditions: Mapped[list] = mapped_column(JSONB, default=list)
    current_medications: Mapped[list] = mapped_column(JSONB, default=list)
    past_surgeries: Mapped[list] = mapped_column(JSONB, default=list)

    # Lifestyle
    smoker: Mapped[bool | None] = mapped_column(Boolean)
    alcohol_use: Mapped[str | None] = mapped_column(String(50))
    exercise_frequency: Mapped[str | None] = mapped_column(String(50))
    is_pregnant: Mapped[bool | None] = mapped_column(Boolean)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization: Mapped["Organization"] = relationship("Organization", back_populates="patients")

    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment", back_populates="patient", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        from datetime import date
        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )
