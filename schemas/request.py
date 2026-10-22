"""schemas/request.py

The ONE request body used by every endpoint.

Rules:
  - EVERY key is required, except ayanamsa and house_system, which use their
    default when missing or empty. A missing key returns a 422 error naming it.
  - EVERY value must be filled in. An empty or blank value returns a 422 error,
    except the fields listed in ALLOW_EMPTY_VALUE (the key must still be sent).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from utils.date_utils import get_timezone_name

# keys that must be sent, but whose value may be empty (e.g. a user with no promo code)
ALLOW_EMPTY_VALUE = {"promo"}

# used when the frontend does not send these two
DEFAULT_AYANAMSA = "LAHIRI"
DEFAULT_HOUSE_SYSTEM = "WHOLE_SIGN"


class BirthDetailsRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # "  Daniel " -> "Daniel"

    name: str
    email: str
    gender: str
    date_of_birth: str = Field(..., examples=["2021-05-03T00:00:00"])
    city: str
    state: str
    country: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    ayanamsa: str = DEFAULT_AYANAMSA
    house_system: str = DEFAULT_HOUSE_SYSTEM
    promo: str = Field(..., max_length=50)    # sent by the frontend

    @field_validator("ayanamsa", "house_system", mode="before")
    @classmethod
    def _blank_uses_default(cls, value, info):
        """null or empty -> the default value."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("promo", mode="before")
    @classmethod
    def _null_promo_is_empty(cls, value):
        """promo: null -> "" (the key itself is still required)."""
        return "" if value is None else value

    @field_validator("date_of_birth")
    @classmethod
    def _validate_datetime(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            raise ValueError("date_of_birth must look like 2021-05-03T00:00:00")
        if parsed.tzinfo is not None:
            raise ValueError(
                "date_of_birth must be the local birth time, without a UTC offset"
            )
        return parsed.isoformat(timespec="seconds")

    @model_validator(mode="after")
    def _no_blank_values(self):
        blank = [
            field
            for field in type(self).model_fields
            if isinstance(getattr(self, field), str)
            and not getattr(self, field).strip()
            and field not in ALLOW_EMPTY_VALUE
        ]
        if blank:
            raise ValueError("These fields must have a value: " + ", ".join(blank))
        return self

    # ---------- values derived for the rest of the app ----------
    @property
    def timezone(self) -> str:
        """IANA timezone found from the birth latitude/longitude."""
        return get_timezone_name(self.latitude, self.longitude)

    @property
    def place_of_birth(self) -> str:
        parts = (self.city, self.state, self.country)
        return ", ".join(part for part in parts if part)

    # ---------- fixed chart settings (not in the body) ----------
    @property
    def altitude(self) -> float:
        return 0

    @property
    def include_outer_planets(self) -> bool:
        return False