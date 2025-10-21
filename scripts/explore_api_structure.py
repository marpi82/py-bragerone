#!/usr/bin/env python3
"""API Structure Explorer for BragerOne.

This script logs into the BragerOne API and explores the structure of responses
from various endpoints to help create accurate Pydantic models.

Usage:
    # Using .env file (recommended)
    poetry run python scripts/explore_api_structure.py

    # Using command line arguments
    poetry run python scripts/explore_api_structure.py --username USER --password PASS

The script will output JSON structures that can be used to create dataclass models.

Environment variables (in .env file):
    PYBO_EMAIL - BragerOne username/email
    PYBO_PASSWORD - BragerOne password
    PYBO_OBJECT_ID - Specific object ID to explore (optional)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Import pybragerone directly (installed in editable mode)
from pybragerone.api.client import BragerOneApiClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


def pretty_json(data: Any, title: str = "") -> str:
    """Format data as pretty JSON with optional title."""
    # Convert Pydantic models to dict for JSON serialization
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
        data = [item.model_dump() for item in data]

    json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if title:
        return f"\n=== {title} ===\n{json_str}\n"
    return json_str


def analyze_structure(data: Any, level: int = 0) -> dict[str, Any]:
    """Analyze data structure recursively."""
    if level > 3:  # Prevent infinite recursion
        return {"type": "truncated", "reason": "max_depth"}

    if isinstance(data, dict):
        fields = {}
        for key, value in data.items():
            fields[key] = analyze_structure(value, level + 1)
        return {"type": "dict", "fields": fields}
    elif isinstance(data, list):
        if not data:
            return {"type": "list", "item_type": "unknown"}
        # Analyze first few items to determine structure
        item_types = []
        for item in data[:3]:
            item_types.append(analyze_structure(item, level + 1))
        return {"type": "list", "item_type": item_types[0] if len(set(str(t) for t in item_types)) == 1 else "mixed"}
    else:
        return {"type": type(data).__name__, "value": data if level < 2 else "..."}


def generate_pydantic_hints(structure: dict[str, Any], name: str) -> str:
    """Generate Pydantic model hints from structure analysis."""
    if structure.get("type") == "dict":
        lines = [f"class {name}(BaseModel):"]
        fields = structure.get("fields", {})
        if not fields:
            lines.append("    pass")
        else:
            for field_name, field_struct in fields.items():
                if field_struct.get("type") == "dict":
                    lines.append(f"    {field_name}: dict[str, Any]")
                elif field_struct.get("type") == "list":
                    lines.append(f"    {field_name}: list[Any]")
                else:
                    type_map = {"str": "str", "int": "int", "float": "float", "bool": "bool", "NoneType": "Optional[Any]"}
                    py_type = type_map.get(field_struct["type"], "Any")
                    lines.append(f"    {field_name}: {py_type}")
        return "\n".join(lines)
    return f"# {name}: {structure}"


async def explore_api_structure(username: str, password: str, object_id: int | None = None) -> None:
    """Main function to explore API structure."""
    log.info("Starting API structure exploration...")

    # Create client with credentials provider
    def creds_provider() -> tuple[str, str]:
        return (username, password)

    client = BragerOneApiClient(creds_provider=creds_provider)
    target_object_id = object_id

    try:
        # 1. Authentication
        log.info("=== AUTHENTICATION ===")
        auth_token = await client.ensure_auth(username, password)
        print(f"Authentication successful: Token type: {type(auth_token)}")

        # 2. User info
        log.info("=== USER INFO ===")
        user_response = await client.get_user()
        print(pretty_json(user_response, "User Info Response"))
        print(generate_pydantic_hints(analyze_structure(user_response), "UserInfo"))

        # 3. User permissions
        log.info("=== USER PERMISSIONS ===")
        try:
            user_perms = await client.get_user_permissions()
            print(pretty_json(user_perms, "User Permissions Response"))
            print(generate_pydantic_hints(analyze_structure(user_perms), "UserPermissions"))
        except Exception as e:
            log.warning(f"Failed to get user permissions: {e}")

        # 4. Objects list
        log.info("=== OBJECTS LIST ===")
        objects_response = await client.get_objects()
        print(pretty_json(objects_response, "Objects List Response"))
        print(generate_pydantic_hints(analyze_structure(objects_response), "ObjectsList"))

        # Use specific object or first available
        if target_object_id is None:
            if objects_response and len(objects_response) > 0:
                target_object_id = objects_response[0].id
            else:
                log.error("No objects found for user")
                return

        log.info(f"Using object ID: {target_object_id}")

        # 5. Object details
        log.info("=== OBJECT DETAILS ===")
        object_response = await client.get_object(target_object_id)
        print(pretty_json(object_response, "Object Details Response"))
        print(generate_pydantic_hints(analyze_structure(object_response), "ObjectDetails"))

        # 6. Object permissions
        log.info("=== OBJECT PERMISSIONS ===")
        try:
            object_perms = await client.get_object_permissions(target_object_id)
            print(pretty_json(object_perms, "Object Permissions Response"))
            print(generate_pydantic_hints(analyze_structure(object_perms), "ObjectPermissions"))
        except Exception as e:
            log.warning(f"Failed to get object permissions: {e}")

        # 7. Modules list
        log.info("=== MODULES LIST ===")
        modules_response = await client.get_modules(target_object_id)
        print(pretty_json(modules_response, "Modules List Response"))
        print(generate_pydantic_hints(analyze_structure(modules_response), "ModulesList"))

        # 8. Try some module operations if we have modules
        if modules_response and len(modules_response) > 0:
            module_ids = [module.id for module in modules_response[:3]]  # First 3 modules
            module_ids = [str(mid) for mid in module_ids if mid is not None]

            if module_ids:
                log.info("=== MODULE PARAMETERS ===")
                try:
                    params_result = await client.modules_parameters_prime(module_ids, return_data=True)
                    if isinstance(params_result, tuple):
                        status, params_data = params_result
                        print(f"Parameters Status: {status}")
                        print(pretty_json(params_data, "Module Parameters Response"))
                        print(generate_pydantic_hints(analyze_structure(params_data), "ModuleParameters"))
                    else:
                        print(f"Parameters result: {params_result}")
                except Exception as e:
                    log.warning(f"Failed to get module parameters: {e}")

                log.info("=== MODULE ACTIVITY ===")
                try:
                    activity_result = await client.modules_activity_quantity_prime(module_ids, return_data=True)
                    if isinstance(activity_result, tuple):
                        status, activity_data = activity_result
                        print(f"Activity Status: {status}")
                        print(pretty_json(activity_data, "Module Activity Response"))
                        print(generate_pydantic_hints(analyze_structure(activity_data), "ModuleActivity"))
                    else:
                        print(f"Activity result: {activity_result}")
                except Exception as e:
                    log.warning(f"Failed to get module activity: {e}")

                # 9. Module card for first module
                if modules_response:
                    first_module = modules_response[0]
                    log.info("=== MODULE CARD ===")
                    try:
                        module_card = await client.get_module_card(first_module.devid)
                        print(pretty_json(module_card, "Module Card Response"))
                        print(generate_pydantic_hints(analyze_structure(module_card), "ModuleCard"))
                    except Exception as e:
                        log.warning(f"Failed to get module card: {e}")

        # 10. System version
        log.info("=== SYSTEM VERSION ===")
        try:
            system_version = await client.get_system_version()
            print(pretty_json(system_version, "System Version Response"))
            print(generate_pydantic_hints(analyze_structure(system_version), "SystemVersion"))
        except Exception as e:
            log.warning(f"Failed to get system version: {e}")

    except Exception as e:
        log.error(f"Error during API exploration: {e}")
    finally:
        await client.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Explore BragerOne API structure")
    parser.add_argument("--username", help="BragerOne username (default: from PYBO_EMAIL env var)")
    parser.add_argument("--password", help="BragerOne password (default: from PYBO_PASSWORD env var)")
    parser.add_argument("--output", help="Output file for results (default: stdout)")
    parser.add_argument("--object-id", type=int, help="Specific object ID to explore (default: from PYBO_OBJECT_ID env var)")

    args = parser.parse_args()

    # Load environment variables from .env file
    if load_dotenv:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            log.info(f"Loaded environment variables from {env_file}")

    # Get credentials from args or environment
    username = args.username or os.getenv("PYBO_EMAIL")
    password = args.password or os.getenv("PYBO_PASSWORD")
    env_object_id = os.getenv("PYBO_OBJECT_ID")
    object_id = args.object_id or (int(env_object_id) if env_object_id else None)

    if not username or not password:
        if not username:
            print("Error: Username not provided. Set PYBO_EMAIL environment variable or use --username")
            sys.exit(1)
        if not password:
            print("Error: Password not provided. Set PYBO_PASSWORD environment variable or use --password")
            sys.exit(1)

    if args.output:
        import contextlib
        import io

        output_buffer = io.StringIO()
        with contextlib.redirect_stdout(output_buffer):
            asyncio.run(explore_api_structure(username, password, object_id))

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_buffer.getvalue())

        print(f"Results saved to {args.output}")
    else:
        asyncio.run(explore_api_structure(username, password, object_id))


if __name__ == "__main__":
    main()
