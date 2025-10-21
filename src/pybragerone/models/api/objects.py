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


class ObjectDetailsResponse(BaseModel):
    """Response model for object details endpoint."""

    object: BragerObject
    status: str


# Type alias for object permissions (list of permission strings)
ObjectPermissions = list[str]
