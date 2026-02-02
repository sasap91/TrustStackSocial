#!/usr/bin/env python3
"""
Test script to verify httpx connectivity to Notion API independently.
This helps diagnose if connectivity issues are network-related or auth-related.
"""
import socket
import httpx
import sys

# Apply the same DNS patch as notion_client.py
socket.has_ipv6 = False
_current_getaddrinfo = socket.getaddrinfo

def getaddrinfo_ipv4(*args, **kwargs):
    """Force IPv4-only DNS resolution"""
    if len(args) >= 3:
        family = args[2]
        if family == socket.AF_UNSPEC:
            family = socket.AF_INET
        elif family == socket.AF_INET6:
            family = socket.AF_INET
        args = list(args)
        args[2] = family
        args = tuple(args)
    else:
        kwargs['family'] = socket.AF_INET
    
    return _current_getaddrinfo(*args, **kwargs)

socket.getaddrinfo = getaddrinfo_ipv4

def test_notion_connectivity():
    """Test httpx connectivity to Notion API"""
    print("Testing httpx connectivity to Notion API...")
    print("=" * 60)
    
    try:
        # Use same configuration as NotionClient
        with httpx.Client(
            transport=httpx.HTTPTransport(retries=3),
            trust_env=False,
            timeout=10.0,
            http2=False  # Force HTTP/1.1
        ) as client:
            # Make request to Notion API (without auth - should get 401)
            response = client.get(
                "https://api.notion.com/v1/users/me",
                headers={"Notion-Version": "2022-06-28"}
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Preview: {response.text[:200]}")
            print("=" * 60)
            
            if response.status_code == 401:
                print("✅ Networking works! (401 Unauthorized means connection succeeded)")
                print("   The issue is authentication - check your NOTION_API_KEY")
                return True
            elif response.status_code == 200:
                print("✅ Networking works! (200 OK - you're authenticated)")
                return True
            else:
                print(f"⚠️  Unexpected status code: {response.status_code}")
                return False
                
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: {e}")
        print("   This indicates a network connectivity issue")
        return False
    except httpx.TimeoutException as e:
        print(f"❌ Timeout Error: {e}")
        print("   The request timed out - check your network connection")
        return False
    except OSError as e:
        if "Operation not permitted" in str(e):
            print(f"❌ Operation not permitted: {e}")
            print("   This indicates httpx configuration/runtime issue")
            print("   Check firewall settings or network permissions")
        else:
            print(f"❌ OS Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_notion_connectivity()
    sys.exit(0 if success else 1)
