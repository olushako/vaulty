"""
Device token generator for Vaulty client
Generates deterministic device_id and computes device_token for authentication
"""

import hashlib
import platform
import os
import socket
import uuid


def hash_string(value: str) -> str:
    """Hash a string and return 32-character hex string"""
    if not value:
        return '0' * 32  # Return zeros if value is None/empty
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]


def get_pwd_hash():
    """Get hash of current working directory"""
    try:
        pwd = os.getcwd()
        return hash_string(pwd)
    except:
        return '0' * 32


def get_hostname_hash():
    """Get hash of system hostname, normalized to lowercase"""
    try:
        hostname = socket.gethostname()
        # Normalize: lowercase, remove domain if present (optional)
        hostname = hostname.lower().split('.')[0]
        return hash_string(hostname)
    except:
        try:
            # Fallback to platform.node()
            hostname = platform.node().lower().split('.')[0]
            return hash_string(hostname)
        except:
            return '0' * 32


def get_mac_address():
    """
    Get MAC address from first network interface.
    Prioritizes physical interfaces over virtual ones.
    Returns MAC as lowercase hex string without colons.
    """
    try:
        # Method 1: Use uuid.getnode() - gets MAC from first interface
        mac_int = uuid.getnode()
        
        # Check if it's a valid MAC (not random)
        # Random MACs in uuid.getnode() are usually 0xffffffffffff or similar
        if mac_int and mac_int != 0xffffffffffff:
            # Convert to hex string without colons
            mac_hex = '{:012x}'.format(mac_int)
            return mac_hex.lower()
    except:
        pass
    
    # Method 2: Try to get MAC from network interfaces (platform-specific)
    try:
        import netifaces
        # Get all interfaces
        interfaces = netifaces.interfaces()
        
        # Prioritize physical interfaces (not loopback, not virtual)
        physical_interfaces = [
            iface for iface in interfaces
            if not iface.startswith('lo') and 
               not iface.startswith('docker') and
               not iface.startswith('veth') and
               not iface.startswith('br-')
        ]
        
        # Try physical interfaces first
        for iface in physical_interfaces:
            try:
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_LINK in addrs:
                    mac = addrs[netifaces.AF_LINK][0].get('addr')
                    if mac and mac != '00:00:00:00:00:00':
                        # Remove colons and normalize
                        return mac.replace(':', '').lower()
            except:
                continue
        
        # Fallback to any interface with MAC
        for iface in interfaces:
            try:
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_LINK in addrs:
                    mac = addrs[netifaces.AF_LINK][0].get('addr')
                    if mac and mac != '00:00:00:00:00:00':
                        return mac.replace(':', '').lower()
            except:
                continue
    except ImportError:
        # netifaces not available, use uuid.getnode() result
        pass
    except:
        pass
    
    return None


def generate_device_id():
    """
    Generate a deterministic device ID using:
    hash(pwd) + hash(hostname) + MAC
    
    All components are concatenated and hashed together.
    Returns a 32-character hex string (SHA256 hash).
    
    Strategy:
    1. Hash current working directory (pwd)
    2. Hash hostname (normalized)
    3. Get MAC address (first physical interface preferred)
    4. Concatenate all hashes + MAC
    5. Hash the concatenated string
    """
    # Get individual hashes
    pwd_hash = get_pwd_hash()
    hostname_hash = get_hostname_hash()
    mac = get_mac_address()
    
    # If MAC is None, use zeros as placeholder
    if not mac:
        mac = '0' * 12  # 12 hex chars for MAC (6 bytes)
    
    # Concatenate all components
    # Format: pwd_hash|hostname_hash|mac
    combined = f"{pwd_hash}|{hostname_hash}|{mac}"
    
    # Generate final deterministic hash (32 chars = 128 bits)
    device_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()[:32]
    
    return device_id.lower()


def get_device_id():
    """
    Get or generate device ID.
    
    Priority:
    1. Environment variable VAULTY_DEVICE_ID (user override)
    2. Generated from hash(pwd) + hash(hostname) + MAC
    
    Returns: 32-character lowercase hex string
    """
    # Allow override via environment variable
    env_device_id = os.environ.get('VAULTY_DEVICE_ID')
    if env_device_id:
        # Validate it's a valid hex string
        env_device_id = env_device_id.strip().lower()
        try:
            if len(env_device_id) == 32 and all(c in '0123456789abcdef' for c in env_device_id):
                return env_device_id
        except:
            pass
    
    return generate_device_id()


def get_device_token(device_id: str = None) -> str:
    """
    Get device_token (SHA256 hash of device_id) for use in Authorization header.
    
    Args:
        device_id: Optional device_id to hash. If None, generates device_id first.
    
    Returns: 64-character hex string (device_token = SHA256(device_id))
    
    Example:
        >>> device_id = get_device_id()
        >>> device_token = get_device_token(device_id)
        >>> # Use in Authorization header: Bearer {device_token}
    """
    if device_id is None:
        device_id = get_device_id()
    
    return hashlib.sha256(device_id.encode('utf-8')).hexdigest()


if __name__ == '__main__':
    # CLI tool to generate device ID and its token
    device_id = get_device_id()
    device_token = get_device_token(device_id)
    print(f"Device ID: {device_id}")
    print(f"Device Token (for Authorization): {device_token}")
    print(f"\nUse this in Authorization header: Bearer {device_token}")





