"""Object-related models for BragerOne API."""

from pydantic import BaseModel


class BragerObject(BaseModel):
    """Brager object (building/house) model."""

    id: int
    name: str
    addressCountry: str
    addressCity: str | None = None
    addressPostCode: str | None = None
    addressStreet: str | None = None
    addressHouseNumber: str | None = None


class ObjectDetails(BaseModel):
    """Object details with operational status.

    Note: The 'status' field here is the object's operational status
    (e.g., "SUCCESS", "OFFLINE"), NOT an HTTP status code.
    """

    object: BragerObject
    status: str
