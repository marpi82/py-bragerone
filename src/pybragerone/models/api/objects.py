"""Object-related models for BragerOne API."""

from pydantic import BaseModel

from .common import Permission


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


class ObjectPermissionsResponse(BaseModel):
    """Response model for object permissions endpoint."""

    permissions: list[str]

    def get_permissions(self) -> list[Permission]:
        """Get permissions as Permission models."""
        return [Permission(name=perm) for perm in self.permissions]
