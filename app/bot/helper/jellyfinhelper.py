import requests
import random
import string

def add_user(jellyfin_url, jellyfin_api_key, username, password, jellyfin_libs):
    try:
        url = f"{jellyfin_url}/Users/New"

        querystring = {"api_key": jellyfin_api_key}
        payload = {
            "Name": username,
            "Password": password
        }
        headers = {"Content-Type": "application/json"}
        print(f"Creating Jellyfin user: {username} (password length: {len(password)})")
        response = requests.request("POST", url, json=payload, headers=headers, params=querystring)

        if response.status_code != 200:
            print(f"Error creating new Jellyfin user (HTTP {response.status_code}): {response.text}")
            return False

        # Parse user ID safely
        try:
            response_data = response.json()
            userId = response_data.get("Id")
            if not userId:
                print(f"Error: Jellyfin user created but no 'Id' in response: {response.text}")
                return False
        except Exception as json_err:
            print(f"Error parsing Jellyfin user creation response: {json_err}")
            print(f"Response body: {response.text}")
            return False

        # Grant access to User
        url = f"{jellyfin_url}/Users/{userId}/Policy"
        querystring = {"api_key": jellyfin_api_key}

        enabled_folders = []
        server_libs = get_libraries(jellyfin_url, jellyfin_api_key)

        if server_libs and jellyfin_libs[0] != "all":
            for lib in jellyfin_libs:
                found = False
                for server_lib in server_libs:
                    server_lib_name = server_lib.get('Name', '')
                    # Use casefold for Unicode-safe case-insensitive comparison
                    if lib.strip().casefold() == server_lib_name.strip().casefold():
                        enabled_folders.append(server_lib.get('ItemId'))
                        found = True
                if not found:
                    print(f"Couldn't find Jellyfin Library: {lib}")

        payload = {
            "IsAdministrator": False,
            "IsHidden": True,
            "IsDisabled": False,
            "BlockedTags": [],
            "EnableUserPreferenceAccess": True,
            "AccessSchedules": [],
            "BlockUnratedItems": [],
            "EnableRemoteControlOfOtherUsers": False,
            "EnableSharedDeviceControl": True,
            "EnableRemoteAccess": True,
            "EnableLiveTvManagement": True,
            "EnableLiveTvAccess": True,
            "EnableMediaPlayback": True,
            "EnableAudioPlaybackTranscoding": True,
            "EnableVideoPlaybackTranscoding": True,
            "EnablePlaybackRemuxing": True,
            "ForceRemoteSourceTranscoding": False,
            "EnableContentDeletion": False,
            "EnableContentDeletionFromFolders": [],
            "EnableContentDownloading": True,
            "EnableSyncTranscoding": True,
            "EnableMediaConversion": True,
            "EnabledDevices": [],
            "EnableAllDevices": True,
            "EnabledChannels": [],
            "EnableAllChannels": False,
            "EnabledFolders": enabled_folders,
            "EnableAllFolders": jellyfin_libs[0] == "all",
            "InvalidLoginAttemptCount": 0,
            "LoginAttemptsBeforeLockout": -1,
            "MaxActiveSessions": 0,
            "EnablePublicSharing": True,
            "BlockedMediaFolders": [],
            "BlockedChannels": [],
            "RemoteClientBitrateLimit": 0,
            "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
            "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider",
            "SyncPlayAccess": "CreateAndJoinGroups"
        }
        headers = {"content-type": "application/json"}

        response = requests.request("POST", url, json=payload, headers=headers, params=querystring)

        if response.status_code in (200, 204):
            return True
        else:
            print(f"Error setting user permissions (HTTP {response.status_code}): {response.text}")
            return False

    except Exception as e:
        print(f"Exception in add_user: {e}")
        return False

def get_libraries(jellyfin_url, jellyfin_api_key):
    try:
        url = f"{jellyfin_url}/Library/VirtualFolders"
        querystring = {"api_key": jellyfin_api_key}
        response = requests.request("GET", url, params=querystring)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting Jellyfin libraries (HTTP {response.status_code}): {response.text}")
            return []
    except Exception as e:
        print(f"Exception in get_libraries: {e}")
        return []
    

def verify_username(jellyfin_url, jellyfin_api_key, username):
    users = get_users(jellyfin_url, jellyfin_api_key)
    if users is None:
        # Could not contact server — allow the username to proceed; let the create call fail if needed
        return True
    for user in users:
        if user.get('Name') == username:
            return False
    return True

def remove_user(jellyfin_url, jellyfin_api_key, jellyfin_username):
    try:
        # Get User ID
        users = get_users(jellyfin_url, jellyfin_api_key)
        if users is None:
            print(f"Error removing user {jellyfin_username}: Could not fetch user list from Jellyfin.")
            return False

        userId = None
        for user in users:
            if user.get('Name', '').lower() == jellyfin_username.lower():
                userId = user.get('Id')
                break
        
        if userId is None:
            print(f"Error removing user {jellyfin_username} from Jellyfin: Could not find user.")
            return False
        
        # Delete User
        url = f"{jellyfin_url}/Users/{userId}"
        querystring = {"api_key": jellyfin_api_key}
        response = requests.request("DELETE", url, params=querystring)

        if response.status_code in (200, 204):
            return True
        else:
            print(f"Error deleting Jellyfin user (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"Exception in remove_user: {e}")
        return False

def get_users(jellyfin_url, jellyfin_api_key):
    try:
        url = f"{jellyfin_url}/Users"
        querystring = {"api_key": jellyfin_api_key}
        response = requests.request("GET", url, params=querystring)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting Jellyfin users (HTTP {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"Exception in get_users: {e}")
        return None

def generate_password(length, lower=True, upper=True, numbers=True, symbols=False):
    """Generate a password. Symbols are disabled by default to avoid Jellyfin API issues."""
    character_list = []
    if not (lower or upper or numbers or symbols):
        raise ValueError("At least one character type must be provided")
        
    if lower:
        character_list += string.ascii_lowercase
    if upper:
        character_list += string.ascii_uppercase
    if numbers:
        character_list += string.digits
    if symbols:
        # Only use safe symbols that won't cause JSON/API issues
        character_list += "!@#$%^&*_-+="

    return "".join(random.choice(character_list) for i in range(length))

def get_config(jellyfin_url, jellyfin_api_key):
    try:
        url = f"{jellyfin_url}/System/Configuration"
        querystring = {"api_key": jellyfin_api_key}
        response = requests.request("GET", url, params=querystring, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting Jellyfin config (HTTP {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"Exception in get_config: {e}")
        return None

def get_status(jellyfin_url, jellyfin_api_key):
    url = f"{jellyfin_url}/System/Configuration"

    querystring = {"api_key":jellyfin_api_key}
    response = requests.request("GET", url, params=querystring, timeout=5)
    return response.status_code