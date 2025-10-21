New API Models Summary
======================

This document summarizes the new Pydantic models implementation for the BragerOne API.

Completed Models
----------------

ModuleCard Model
~~~~~~~~~~~~~~~~

The :class:`~pybragerone.models.api.modules.ModuleCard` model contains detailed information about a module card along with client data:

.. code-block:: python

    from pybragerone.models.api import ModuleCard

    # Get module card
    module_card: ModuleCard = await client.get_module_card("FTTCTBSLCE")

    # Access data
    print(f"Module ID: {module_card.moduleId}")
    print(f"Client: {module_card.clientFullName}")
    print(f"Phone: {module_card.clientPhoneNumber}")
    print(f"Address: {module_card.clientAddressStreetAndNumber}")
    print(f"City: {module_card.clientAddressCity} {module_card.clientAddressPostalCode}")
    print(f"Created: {module_card.createdAt}")
    print(f"Updated: {module_card.updatedAt}")

**Model Fields:**

- ``id: int`` - Card ID
- ``moduleId: int`` - Module ID  
- ``clientFullName: str`` - Full client name
- ``clientPhoneNumber: str`` - Phone number
- ``clientAddressStreetAndNumber: str`` - Street and number
- ``clientAddressPostalCode: str`` - Postal code
- ``clientAddressCity: str`` - City
- ``createdAt: datetime`` - Creation date (automatic parsing)
- ``updatedAt: datetime`` - Last update date (automatic parsing)

SystemVersion Model  
~~~~~~~~~~~~~~~~~~~

The :class:`~pybragerone.models.api.system.SystemVersion` model contains system version information:

.. code-block:: python

    from pybragerone.models.api import SystemVersion

    # Get system version (no authentication required)
    version: SystemVersion = await client.get_system_version()

    # Access data
    print(f"Version: {version.version.version}")
    print(f"Development mode: {version.version.devMode}")

**Model Structure:**

- ``version: VersionInfo`` - Nested version information
  - ``version: str`` - Version number (e.g., "1.0.2501310630")
  - ``devMode: bool`` - Whether development mode is enabled

Real Data Examples
------------------

ModuleCard Response
~~~~~~~~~~~~~~~~~~~

.. code-block:: json

    {
      "id": 175,
      "moduleId": 302,
      "clientFullName": "Jan Kowalski",
      "clientPhoneNumber": "+48123456789",
      "clientAddressStreetAndNumber": "Kwiatowa 15",
      "clientAddressPostalCode": "00-123",
      "clientAddressCity": "Warszawa",
      "createdAt": "2024-01-15T10:30:00.000+00:00",
      "updatedAt": "2024-01-15T11:45:00.000+00:00"
    }

SystemVersion Response
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

    {
      "version": {
        "version": "1.0.2501310630",
        "devMode": false
      }
    }

Complete Usage Example
----------------------

.. code-block:: python

    import asyncio
    import os
    from pybragerone.api.client import BragerOneApiClient
    from pybragerone.models.api import ModuleCard, SystemVersion, Module

    async def demo_new_models():
        def creds_provider():
            return (os.getenv("PYBO_EMAIL"), os.getenv("PYBO_PASSWORD"))
        
        client = BragerOneApiClient(creds_provider=creds_provider)
        
        try:
            await client.ensure_auth(os.getenv("PYBO_EMAIL"), os.getenv("PYBO_PASSWORD"))
            
            # System version (available without authentication)
            version: SystemVersion = await client.get_system_version()
            print(f"🖥️  System: {version.version.version} (dev: {version.version.devMode})")
            
            # Modules and their cards
            objects = await client.get_objects()
            if objects:
                modules: list[Module] = await client.get_modules(objects[0].id)
                for module in modules:
                    print(f"\\n📡 Module: {module.name} ({module.devid})")
                    
                    try:
                        card: ModuleCard = await client.get_module_card(module.devid)
                        print(f"   👤 Client: {card.clientFullName}")
                        print(f"   📍 Address: {card.clientAddressStreetAndNumber}")
                        print(f"   🏙️  City: {card.clientAddressCity} {card.clientAddressPostalCode}")
                        print(f"   📞 Phone: {card.clientPhoneNumber}")
                        print(f"   📅 Created: {card.createdAt}")
                        print(f"   🔄 Updated: {card.updatedAt}")
                    except Exception as e:
                        print(f"   ⚠️  Card not available: {e}")
        
        finally:
            await client.close()

    # Run the demo
    asyncio.run(demo_new_models())

Implementation Status
---------------------

- ✅ **ModuleCard**: Complete model with automatic date parsing
- ✅ **SystemVersion**: Complete model with nested VersionInfo structure  
- ✅ **API Client**: Methods return Pydantic models instead of dict
- ✅ **Tests**: All models tested and working
- ✅ **Type Safety**: Full type support in IDE and runtime
- ✅ **Validation**: Automatic validation of API structures

The :class:`~pybragerone.models.api.modules.ModuleCard` and :class:`~pybragerone.models.api.system.SystemVersion` models are now fully functional and ready for use!