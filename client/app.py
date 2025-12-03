#!/usr/bin/env python3
"""
Vaulty Client Application
Provides a simple interface to get device token and register devices
"""

import sys
import os
import json
import requests
from .device_token import get_device_id, get_device_token
from .register import register_device
from .status import check_device_status, list_devices
from .secrets import get_secret, list_secrets, check_secret_exists
from .project import get_project_name as get_project_name_from_api
from .config import get_api_url, save_api_url


def has_json_flag():
    """Check if --json flag is present in command line arguments"""
    return '--json' in sys.argv


def output_json(data, exit_code=0):
    """Output data as JSON and exit"""
    print(json.dumps(data, indent=2))
    if exit_code != 0:
        sys.exit(exit_code)


def get_default_api_url():
    """Get default API URL from environment, config file, or default"""
    # Priority: environment variable > config file > default
    api_url = os.environ.get('VAULTY_API_URL')
    if api_url:
        return api_url
    
    api_url = get_api_url()
    if api_url:
        return api_url
    
    return 'http://localhost:8000'


def parse_common_options(start_idx=2, save_url=False):
    """
    Parse common options (--api-url, --json) and return them
    
    Args:
        start_idx: Starting index in sys.argv to parse from
        save_url: If True, save --api-url to config file
    
    Returns:
        Tuple of (api_url, json_output, next_index)
    """
    api_url = get_default_api_url()
    json_output = False
    
    i = start_idx
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            if save_url:
                save_api_url(api_url)
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            break
    
    return api_url, json_output, i


def print_help():
    """Print help message"""
    print("Vaulty Client - Device Management")
    print("\nCommands:")
    print("  token                    # Get device_token only")
    print("  id                       # Get device_id only")
    print("  register <project> [name]  # Register device in project (name auto-generated if not provided)")
    print("                             # Use --path to specify working directory instead of current directory")
    print("  device-status [--name NAME]  # Check current device registration status")
    print("  list-devices [--status STATUS]  # List all devices in project")
    print("  get-secret <key>  # Get secret value by key")
    print("  list-secrets  # List all secrets in project (keys only)")
    print("  check-secret <key>  # Check if secret exists")
    print("  create-secret <key>  # Create/update secret with auto-generated value")
    print("  delete-secret <key>  # Delete a secret from project")
    print("  list-projects  # List all projects")
    print("  list-tokens  # List all project tokens")
    print("  get-project  # Get project information")
    print("  get-docs  # Get API and MCP documentation")
    print("  list-activities [--limit N] [--offset N] [--method METHOD] [--exclude-ui]  # List activity history")
    print("\nGlobal Options:")
    print("  --json                    # Output results in JSON format")
    print("\nRegister Options:")
    print("  --api-url URL            # Vaulty API URL (default: http://localhost:8000)")
    print("  --path PATH              # Working directory path (default: current directory)")
    print("  --tags TAG1,TAG2        # Comma-separated tags")
    print("  --description TEXT      # Device description")
    print("  --auth-token TOKEN      # Auth token for activity logging and auto-rejection")
    print("  --timeout SECONDS       # Max wait time for authorization (default: 300)")
    print("  --quiet                  # Suppress status messages")
    print("\nStatus Options:")
    print("  --api-url URL            # Vaulty API URL (default: http://localhost:8000)")
    print("  --name NAME              # Check device by name")
    print("\nList Options:")
    print("  --api-url URL            # Vaulty API URL (default: http://localhost:8000)")
    print("  --status STATUS          # Filter by status: pending, authorized, rejected")
    print("\nNote: All commands automatically use device_token for authentication")
    print("\nEnvironment Variables:")
    print("  VAULTY_DEVICE_ID         # Override device_id")
    print("  VAULTY_API_URL          # Default API URL")
    print("\nExamples:")
    print("  python -m client.app token")
    print("  python -m client.app id")
    print("  python -m client.app register hello")
    print("  python -m client.app register hello my-device")
    print("  python -m client.app status")
    print("  python -m client.app status --name my-device")
    print("  python -m client.app list")
    print("  python -m client.app secret api_key")
    print("  python -m client.app secrets")
    print("  python -m client.app secret-exists api_key")


def cmd_token():
    """Handle token command - outputs only the device_token"""
    json_output = has_json_flag()
    device_id = get_device_id()
    device_token = get_device_token(device_id)
    
    if json_output:
        output_json({
            "success": True,
            "device_id": device_id,
            "device_token": device_token
        })
    else:
        print(device_token)


def cmd_id():
    """Handle id command - outputs only the device_id"""
    json_output = has_json_flag()
    device_id = get_device_id()
    
    if json_output:
        output_json({
            "success": True,
            "device_id": device_id
        })
    else:
        print(device_id)


def cmd_register():
    """Handle register command"""
    if len(sys.argv) < 3:
        print("Error: register command requires project name")
        print("Usage: python -m client.app register <project> [name] [options]")
        sys.exit(1)
    
    project_name = sys.argv[2]
    device_name = None  # Optional - will be auto-generated if not provided
    
    # Check if next argument is device name or an option
    if len(sys.argv) >= 4 and not sys.argv[3].startswith('--'):
        device_name = sys.argv[3]
        arg_start = 4
    else:
        arg_start = 3
    
    # Parse options
    api_url = get_default_api_url()
    tags = None
    description = None
    auth_token = None
    timeout = 300
    verbose = True
    working_directory = None  # Optional path parameter
    
    i = arg_start
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--tags' and i + 1 < len(sys.argv):
            tags_str = sys.argv[i + 1]
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            i += 2
        elif arg == '--description' and i + 1 < len(sys.argv):
            description = sys.argv[i + 1]
            i += 2
        elif arg == '--auth-token' and i + 1 < len(sys.argv):
            auth_token = sys.argv[i + 1]
            i += 2
        elif arg == '--timeout' and i + 1 < len(sys.argv):
            try:
                timeout = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: Invalid timeout value: {sys.argv[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg in ['--path', '--working-dir', '--working-directory'] and i + 1 < len(sys.argv):
            working_directory = os.path.abspath(sys.argv[i + 1])
            if not os.path.isdir(working_directory):
                print(f"Error: Path does not exist or is not a directory: {working_directory}")
                sys.exit(1)
            i += 2
        elif arg == '--quiet':
            verbose = False
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # If working_directory is specified, change to it temporarily to generate correct device_id
    original_cwd = os.getcwd()
    if working_directory:
        os.chdir(working_directory)
    
    try:
        # Register device
        result = register_device(
            api_url=api_url,
            project_name=project_name,
            name=device_name,
            tags=tags,
            description=description,
            auth_token=auth_token,
            working_directory=working_directory,
            max_wait_time=timeout,
            verbose=verbose
        )
    finally:
        # Restore original directory
        if working_directory:
            os.chdir(original_cwd)
    
    # Print result
    if verbose:
        print()
    
    if result.get('success'):
        print(f"✓ {result.get('message')}")
        if 'device' in result:
            device = result['device']
            print(f"  Device ID: {device.get('id')}")
            print(f"  Status: {device.get('status')}")
            if device.get('authorized_at'):
                print(f"  Authorized at: {device.get('authorized_at')}")
        if 'wait_time_seconds' in result:
            print(f"  Wait time: {result['wait_time_seconds']} seconds")
        
        # Show device_token info (use working_directory if specified)
        if working_directory:
            original_cwd_for_token = os.getcwd()
            os.chdir(working_directory)
            try:
                device_id = get_device_id()
                device_token = get_device_token()
            finally:
                os.chdir(original_cwd_for_token)
        else:
            device_id = get_device_id()
            device_token = get_device_token()
        print(f"\nDevice Token: {device_token}")
        print(f"Use this in Authorization header: Bearer {device_token}")
    else:
        print(f"✗ {result.get('message', result.get('error', 'Registration failed'))}")
        if 'note' in result:
            print(f"  {result['note']}")
        sys.exit(1)


def cmd_status():
    """Handle status command"""
    # Parse options
    api_url = get_default_api_url()
    device_name = None
    json_output = False
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--name' and i + 1 < len(sys.argv):
            device_name = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        print("Error: Could not determine project. Device may not be registered or authorized.")
        print("Please register a device first: python -m client.app register <project> <name>")
        sys.exit(1)
    
    # Check device status (automatically uses device_token)
    result = check_device_status(
        api_url=api_url,
        project_name=project_name,
        device_name=device_name
    )
    
    # Print result
    if json_output:
        if result.get('success'):
            output_json(result)
        else:
            output_json({
                "success": False,
                "error": result.get('message', result.get('error', 'Status check failed'))
            }, exit_code=1)
    else:
        if result.get('success'):
            device = result.get('device', {})
            status = result.get('status', 'unknown')
            
            print(f"✓ {result.get('message')}")
            print(f"  Device ID: {device.get('id')}")
            print(f"  Name: {device.get('name')}")
            print(f"  Status: {status}")
            print(f"  Created: {device.get('created_at')}")
            
            if status == 'authorized':
                print(f"  Authorized at: {device.get('authorized_at')}")
                print(f"  Authorized by: {device.get('authorized_by')}")
            elif status == 'rejected':
                print(f"  Rejected at: {device.get('rejected_at')}")
                print(f"  Rejected by: {device.get('rejected_by')}")
            elif status == 'pending':
                print(f"  ⏳ Waiting for authorization...")
        else:
            print(f"✗ {result.get('message', result.get('error', 'Status check failed'))}")
            sys.exit(1)


def cmd_list():
    """Handle list command"""
    # Parse options
    api_url = get_default_api_url()
    status_filter = None
    json_output = False
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--status' and i + 1 < len(sys.argv):
            status_filter = sys.argv[i + 1]
            if status_filter not in ['pending', 'authorized', 'rejected']:
                print(f"Error: Invalid status filter. Must be: pending, authorized, or rejected")
                sys.exit(1)
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        print("Error: Could not determine project. Device may not be registered or authorized.")
        print("Please register a device first: python -m client.app register <project> <name>")
        sys.exit(1)
    
    # List devices (automatically uses device_token)
    result = list_devices(
        api_url=api_url,
        project_name=project_name,
        status_filter=status_filter
    )
    
    # Print result
    if json_output:
        if result.get('success'):
            output_json(result)
        else:
            output_json({
                "success": False,
                "error": result.get('message', result.get('error', 'List failed'))
            }, exit_code=1)
    else:
        if result.get('success'):
            devices = result.get('devices', [])
            count = result.get('count', 0)
            
            print(f"✓ {result.get('message')}")
            if status_filter:
                print(f"  Filter: {status_filter}")
            print()
            
            if count == 0:
                print("  No devices found")
            else:
                for device in devices:
                    status = device.get('status', 'unknown')
                    status_icon = {
                        'authorized': '✓',
                        'pending': '⏳',
                        'rejected': '✗'
                    }.get(status, '?')
                    
                    print(f"  {status_icon} {device.get('name')} (ID: {device.get('id')})")
                    print(f"     Status: {status}")
                    print(f"     Created: {device.get('created_at')}")
                    if status == 'authorized':
                        print(f"     Authorized: {device.get('authorized_at')}")
                    print()
        else:
            print(f"✗ {result.get('message', result.get('error', 'List failed'))}")
            sys.exit(1)


def cmd_secret():
    """Handle secret command"""
    if len(sys.argv) < 3:
        print("Error: secret command requires secret key")
        print("Usage: python -m client.app secret <key> [options]")
        sys.exit(1)
    
    secret_key = sys.argv[2]
    
    # Parse options
    api_url = get_default_api_url()
    json_output = False
    
    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        error_msg = "Error: Could not determine project. Device may not be registered or authorized."
        if json_output:
            output_json({"success": False, "error": error_msg}, exit_code=1)
        else:
            print(error_msg)
            print("Please register a device first: python -m client.app register <project> <name>")
            sys.exit(1)
    
    # Get secret (automatically uses device_token)
    result = get_secret(
        api_url=api_url,
        project_name=project_name,
        key=secret_key
    )
    
    # Print result
    if json_output:
        if result.get('success'):
            output_json(result)
        else:
            output_json({
                "success": False,
                "error": result.get('message', result.get('error', 'Failed to get secret'))
            }, exit_code=1)
    else:
        if result.get('success'):
            print(f"✓ {result.get('message')}")
            print(f"  Key: {result.get('key')}")
            print(f"  Value: {result.get('value')}")
            print(f"  Created: {result.get('created_at')}")
            print(f"  Updated: {result.get('updated_at')}")
        else:
            print(f"✗ {result.get('message', result.get('error', 'Failed to get secret'))}")
            sys.exit(1)


def cmd_secrets():
    """Handle secrets command"""
    # Parse options (save_url=True to persist API URL)
    api_url, json_output, i = parse_common_options(2, save_url=True)
    
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        error_msg = "Error: Could not determine project. Device may not be registered or authorized."
        if json_output:
            output_json({"success": False, "error": error_msg}, exit_code=1)
        else:
            print(error_msg)
            print("Please register a device first: python -m client.app register <project> <name>")
            sys.exit(1)
    
    # List secrets (automatically uses device_token)
    result = list_secrets(
        api_url=api_url,
        project_name=project_name
    )
    
    # Print result
    if json_output:
        if result.get('success'):
            output_json(result)
        else:
            output_json({
                "success": False,
                "error": result.get('message', result.get('error', 'Failed to list secrets'))
            }, exit_code=1)
    else:
        if result.get('success'):
            secrets = result.get('secrets', [])
            count = result.get('count', 0)
            
            print(f"✓ {result.get('message')}")
            print()
            
            if count == 0:
                print("  No secrets found")
            else:
                for secret in secrets:
                    print(f"  • {secret.get('key')}")
                    print(f"    Created: {secret.get('created_at')}")
                    print(f"    Updated: {secret.get('updated_at')}")
                    print()
        else:
            print(f"✗ {result.get('message', result.get('error', 'Failed to list secrets'))}")
            sys.exit(1)


def cmd_secret_exists():
    """Handle secret-exists command"""
    if len(sys.argv) < 3:
        print("Error: secret-exists command requires secret key")
        print("Usage: python -m client.app secret-exists <key> [options]")
        sys.exit(1)
    
    secret_key = sys.argv[2]
    
    # Parse options
    api_url = get_default_api_url()
    json_output = False
    
    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        error_msg = "Error: Could not determine project. Device may not be registered or authorized."
        if json_output:
            output_json({"success": False, "error": error_msg}, exit_code=1)
        else:
            print(error_msg)
            print("Please register a device first: python -m client.app register <project> <name>")
            sys.exit(1)
    
    # Check secret existence (automatically uses device_token)
    result = check_secret_exists(
        api_url=api_url,
        project_name=project_name,
        key=secret_key
    )
    
    # Print result
    if json_output:
        if result.get('success'):
            output_json(result)
        else:
            output_json({
                "success": False,
                "error": result.get('message', result.get('error', 'Failed to check secret'))
            }, exit_code=1)
    else:
        if result.get('success'):
            exists = result.get('exists', False)
            if exists:
                print(f"✓ {result.get('message')}")
                sys.exit(0)
            else:
                print(f"✗ {result.get('message')}")
                sys.exit(1)
        else:
            print(f"✗ {result.get('message', result.get('error', 'Failed to check secret'))}")
            sys.exit(1)


def cmd_create_secret():
    """Handle create-secret command"""
    if len(sys.argv) < 3:
        print("Error: create-secret command requires secret key")
        print("Usage: python -m client.app create-secret <key> [options]")
        sys.exit(1)
    
    secret_key = sys.argv[2]
    
    # Parse options
    api_url = get_default_api_url()
    value_format = 'random_string'
    json_output = False
    
    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--format' and i + 1 < len(sys.argv):
            value_format = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        print("Error: Could not determine project. Device may not be registered or authorized.")
        sys.exit(1)
    
    # Generate secret value based on format
    import secrets
    import string
    import uuid
    
    if value_format == 'uuid':
        secret_value = str(uuid.uuid4())
    elif value_format == 'random_string':
        secret_value = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    elif value_format == 'token':
        secret_value = secrets.token_urlsafe(32)
    elif value_format == 'hex':
        secret_value = secrets.token_hex(32)
    elif value_format == 'base64':
        secret_value = secrets.token_urlsafe(32)
    elif value_format == 'lowercase':
        secret_value = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(32))
    elif value_format == 'uppercase':
        secret_value = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(32))
    elif value_format == 'numeric':
        secret_value = ''.join(secrets.choice(string.digits) for _ in range(32))
    elif value_format == 'alphanumeric_lower':
        secret_value = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(32))
    else:
        secret_value = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # Create secret
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.post(
            f"{api_url}/api/projects/{project_name}/secrets",
            json={"key": secret_key, "value": secret_value},
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            response_data = response.json() if response.content else {}
            if json_output:
                output_json({
                    "success": True,
                    "message": f"Secret '{secret_key}' created successfully",
                    "key": secret_key,
                    "created_at": response_data.get("created_at"),
                    "updated_at": response_data.get("updated_at")
                })
            else:
                print(f"✓ Secret '{secret_key}' created successfully")
                print("  Note: Secret value is auto-generated and not returned for security")
        else:
            error_detail = response.json() if response.content else {"detail": "Unknown error"}
            error_msg = error_detail.get('detail', 'Unknown error')
            if json_output:
                output_json({
                    "success": False,
                    "error": f"Failed to create secret: {error_msg}"
                }, exit_code=1)
            else:
                print(f"✗ Failed to create secret: {error_msg}")
                sys.exit(1)
    except requests.exceptions.RequestException as e:
        if json_output:
            output_json({
                "success": False,
                "error": f"Failed to connect to API: {str(e)}"
            }, exit_code=1)
        else:
            print(f"✗ Failed to connect to API: {str(e)}")
            sys.exit(1)


def cmd_delete_secret():
    """Handle delete-secret command"""
    if len(sys.argv) < 3:
        print("Error: delete-secret command requires secret key")
        print("Usage: python -m client.app delete-secret <key> [options]")
        sys.exit(1)
    
    secret_key = sys.argv[2]
    
    # Parse options
    api_url = get_default_api_url()
    json_output = False
    
    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        error_msg = "Error: Could not determine project. Device may not be registered or authorized."
        if json_output:
            output_json({"success": False, "error": error_msg}, exit_code=1)
        else:
            print(error_msg)
            sys.exit(1)
    
    # Delete secret
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.delete(
            f"{api_url}/api/projects/{project_name}/secrets/{secret_key}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            if json_output:
                output_json({
                    "success": True,
                    "message": f"Secret '{secret_key}' deleted successfully",
                    "key": secret_key
                })
            else:
                print(f"✓ Secret '{secret_key}' deleted successfully")
        else:
            error_detail = response.json() if response.content else {"detail": "Unknown error"}
            error_msg = error_detail.get('detail', 'Unknown error')
            if json_output:
                output_json({
                    "success": False,
                    "error": f"Failed to delete secret: {error_msg}"
                }, exit_code=1)
            else:
                print(f"✗ Failed to delete secret: {error_msg}")
                sys.exit(1)
    except requests.exceptions.RequestException as e:
        if json_output:
            output_json({
                "success": False,
                "error": f"Failed to connect to API: {str(e)}"
            }, exit_code=1)
        else:
            print(f"✗ Failed to connect to API: {str(e)}")
            sys.exit(1)


def cmd_list_projects():
    """Handle list-projects command"""
    # Parse options (save_url=True to persist API URL)
    api_url, json_output, i = parse_common_options(2, save_url=True)
    
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # List projects
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.get(
            f"{api_url}/api/projects",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            projects = response.json()
            if json_output:
                output_json({
                    "success": True,
                    "count": len(projects),
                    "projects": projects
                })
            else:
                print(f"✓ Found {len(projects)} project(s)")
                print()
                for project in projects:
                    print(f"  • {project.get('name')}")
                    if project.get('description'):
                        print(f"    {project.get('description')}")
                    print()
        else:
            error_detail = response.json() if response.content else {"detail": "Unknown error"}
            error_msg = error_detail.get('detail', 'Unknown error')
            if json_output:
                output_json({
                    "success": False,
                    "error": f"Failed to list projects: {error_msg}"
                }, exit_code=1)
            else:
                print(f"✗ Failed to list projects: {error_msg}")
                sys.exit(1)
    except requests.exceptions.RequestException as e:
        if json_output:
            output_json({
                "success": False,
                "error": f"Failed to connect to API: {str(e)}"
            }, exit_code=1)
        else:
            print(f"✗ Failed to connect to API: {str(e)}")
            sys.exit(1)


def cmd_list_tokens():
    """Handle list-tokens command"""
    # Parse options (save_url=True to persist API URL)
    api_url, json_output, i = parse_common_options(2, save_url=True)
    
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        error_msg = "Error: Could not determine project. Device may not be registered or authorized."
        if json_output:
            output_json({"success": False, "error": error_msg}, exit_code=1)
        else:
            print(error_msg)
            sys.exit(1)
    
    # List tokens
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    try:
        response = requests.get(
            f"{api_url}/api/projects/{project_name}/tokens",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            tokens = response.json()
            if json_output:
                output_json({
                    "success": True,
                    "project_name": project_name,
                    "count": len(tokens),
                    "tokens": tokens
                })
            else:
                print(f"✓ Found {len(tokens)} token(s) in project '{project_name}'")
                print()
                for token in tokens:
                    print(f"  • {token.get('name', 'Unnamed')} (ID: {token.get('id')})")
                    if token.get('description'):
                        print(f"    {token.get('description')}")
                    print(f"    Created: {token.get('created_at')}")
                    print()
        else:
            error_detail = response.json() if response.content else {"detail": "Unknown error"}
            error_msg = error_detail.get('detail', 'Unknown error')
            if json_output:
                output_json({
                    "success": False,
                    "error": f"Failed to list tokens: {error_msg}"
                }, exit_code=1)
            else:
                print(f"✗ Failed to list tokens: {error_msg}")
                sys.exit(1)
    except requests.exceptions.RequestException as e:
        if json_output:
            output_json({
                "success": False,
                "error": f"Failed to connect to API: {str(e)}"
            }, exit_code=1)
        else:
            print(f"✗ Failed to connect to API: {str(e)}")
            sys.exit(1)


def cmd_project_info():
    """Handle project-info command"""
    # Parse options (save_url=True to persist API URL)
    api_url, json_output, i = parse_common_options(2, save_url=True)
    
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project info
    from .project import get_project_info
    result = get_project_info(api_url)
    
    if json_output:
        if result.get('success'):
            output_json(result)
        else:
            output_json({
                "success": False,
                "error": result.get('message', result.get('error', 'Failed to get project info'))
            }, exit_code=1)
    else:
        if result.get('success'):
            project = result.get('project', {})
            stats = project.get('stats', {})
            print(f"✓ {result.get('message')}")
            print()
            print(f"  Name: {project.get('name')}")
            if project.get('description'):
                print(f"  Description: {project.get('description')}")
            print(f"  ID: {project.get('id')}")
            print(f"  Created: {project.get('created_at')}")
            print()
            print(f"  Stats:")
            print(f"    Secrets: {stats.get('secrets_count', 0)}")
            print(f"    Tokens: {stats.get('tokens_count', 0)}")
            print(f"    Devices: {stats.get('devices_count', 0)}")
        else:
            print(f"✗ {result.get('message', result.get('error', 'Failed to get project info'))}")
            sys.exit(1)


def cmd_documentation():
    """Handle documentation command"""
    # Parse options (save_url=True to persist API URL)
    api_url, json_output, i = parse_common_options(2, save_url=True)
    
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            i += 2
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get documentation (always outputs JSON, but --json flag for consistency)
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"} if device_token else {}
    
    try:
        response = requests.get(
            f"{api_url}/api/docs",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            doc = response.json()
            # Documentation is always JSON, but wrap it for consistency
            if json_output:
                output_json({
                    "success": True,
                    "documentation": doc
                })
            else:
                print(json.dumps(doc, indent=2))
        else:
            error_detail = response.json() if response.content else {"detail": "Unknown error"}
            error_msg = error_detail.get('detail', 'Unknown error')
            if json_output:
                output_json({
                    "success": False,
                    "error": f"Failed to get documentation: {error_msg}"
                }, exit_code=1)
            else:
                print(f"✗ Failed to get documentation: {error_msg}")
                sys.exit(1)
    except requests.exceptions.RequestException as e:
        if json_output:
            output_json({
                "success": False,
                "error": f"Failed to connect to API: {str(e)}"
            }, exit_code=1)
        else:
            print(f"✗ Failed to connect to API: {str(e)}")
            sys.exit(1)


def cmd_list_activities():
    """Handle list-activities command"""
    # Parse options
    api_url = get_default_api_url()
    limit = 25
    offset = 0
    method = None
    exclude_ui = False
    json_output = False
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--api-url' and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
            save_api_url(api_url)  # Save to config
            i += 2
        elif arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif arg == '--offset' and i + 1 < len(sys.argv):
            offset = int(sys.argv[i + 1])
            i += 2
        elif arg == '--method' and i + 1 < len(sys.argv):
            method = sys.argv[i + 1]
            i += 2
        elif arg == '--exclude-ui':
            exclude_ui = True
            i += 1
        elif arg == '--json':
            json_output = True
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)
    
    # Get project name from API using device_token
    project_name = get_project_name_from_api(api_url)
    if not project_name:
        error_msg = "Error: Could not determine project. Device may not be registered or authorized."
        if json_output:
            output_json({"success": False, "error": error_msg}, exit_code=1)
        else:
            print(error_msg)
            sys.exit(1)
    
    # List activities
    device_token = get_device_token()
    headers = {"Authorization": f"Bearer {device_token}"}
    
    params = {
        "limit": limit,
        "offset": offset,
        "exclude_ui": exclude_ui
    }
    if method:
        params["method"] = method
    
    try:
        response = requests.get(
            f"{api_url}/api/projects/{project_name}/activities",
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if json_output:
                output_json({
                    "success": True,
                    **data
                })
            else:
                activities = data.get("activities", [])
                total = data.get("total", 0)
                has_more = data.get("has_more", False)
                
                print(f"✓ Found {total} activity/activities (showing {len(activities)})")
                if has_more:
                    print(f"  (More activities available - use --offset {offset + limit} to see next page)")
                print()
                
                if not activities:
                    print("  No activities found")
                else:
                    for activity in activities:
                        method_str = activity.get("method", "?")
                        action = activity.get("action", "?")
                        path = activity.get("path", "?")
                        status_code = activity.get("status_code", "?")
                        created_at = activity.get("created_at", "?")
                        exec_time = activity.get("execution_time_ms")
                        
                        # Format timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            time_str = created_at
                        
                        status_icon = "✓" if 200 <= status_code < 300 else "✗"
                        exec_str = f" ({exec_time}ms)" if exec_time else ""
                        
                        print(f"  {status_icon} [{method_str}] {action}")
                        print(f"     Path: {path}")
                        print(f"     Status: {status_code}{exec_str}")
                        print(f"     Time: {time_str}")
                        print()
        else:
            error_detail = response.json() if response.content else {"detail": "Unknown error"}
            error_msg = error_detail.get('detail', 'Unknown error')
            if json_output:
                output_json({
                    "success": False,
                    "error": f"Failed to list activities: {error_msg}"
                }, exit_code=1)
            else:
                print(f"✗ Failed to list activities: {error_msg}")
                sys.exit(1)
    except requests.exceptions.RequestException as e:
        if json_output:
            output_json({
                "success": False,
                "error": f"Failed to connect to API: {str(e)}"
            }, exit_code=1)
        else:
            print(f"✗ Failed to connect to API: {str(e)}")
            sys.exit(1)


def main():
    """Main entry point for the client app"""
    if len(sys.argv) == 1 or sys.argv[1] in ['-h', '--help', 'help']:
        print_help()
        return
    
    command = sys.argv[1]
    
    if command == 'token':
        cmd_token()
    elif command == 'id':
        cmd_id()
    elif command == 'register':
        cmd_register()
    elif command == 'device-status':
        cmd_status()
    elif command == 'list-devices':
        cmd_list()
    elif command == 'get-secret':
        cmd_secret()
    elif command == 'list-secrets':
        cmd_secrets()
    elif command == 'check-secret':
        cmd_secret_exists()
    elif command == 'create-secret':
        cmd_create_secret()
    elif command == 'delete-secret':
        cmd_delete_secret()
    elif command == 'list-projects':
        cmd_list_projects()
    elif command == 'list-tokens':
        cmd_list_tokens()
    elif command == 'get-project':
        cmd_project_info()
    elif command == 'get-docs':
        cmd_documentation()
    elif command == 'list-activities':
        cmd_list_activities()
    # Backward compatibility aliases
    elif command == 'get-token':
        cmd_token()
    elif command == 'get-id':
        cmd_id()
    elif command == 'status':
        cmd_status()
    elif command == 'list':
        cmd_list()
    elif command == 'secret':
        cmd_secret()
    elif command == 'secrets':
        cmd_secrets()
    elif command == 'secret-exists':
        cmd_secret_exists()
    elif command == 'project-info':
        cmd_project_info()
    elif command == 'documentation' or command == 'get-documentation':
        cmd_documentation()
    else:
        print(f"Error: Unknown command: {command}")
        print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

