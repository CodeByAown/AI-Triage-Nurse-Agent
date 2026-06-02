import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from app.models.patient import BiologicalSex


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    biological_sex: BiologicalSex | None = None
    gender_identity: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    allergies: list[str] = []
    chronic_conditions: list[str] = []
    current_medications: list[dict] = []
    is_pregnant: bool | None = None


class PatientOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    mrn: str | None
    first_name: str
    last_name: str
    full_name: str
    age: int | None
    date_of_birth: date | None
    biological_sex: BiologicalSex | None
    email: str | None
    phone: str | None
    allergies: list
    chronic_conditions: list
    current_medications: list
    is_active: bool
    organization_id: uuid.UUID
    created_at: datetime


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    allergies: list[str] | None = None
    chronic_conditions: list[str] | None = None
    current_medications: list[dict] | None = None
    is_pregnant: bool | None = None
