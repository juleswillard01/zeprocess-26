"""Download a folder from MEGA using raw API (no mega.py dependency)."""

from __future__ import annotations

import json
import logging
import struct
import sys
from pathlib import Path

import requests
from Crypto.Cipher import AES
from Crypto.Util import Counter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

TARGET_PATH = "axel/seduction/ddp-garconniere"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"

API_URL = "https://g.api.mega.co.nz/cs"


def a32_to_str(a: list[int]) -> bytes:
    return struct.pack(">%dI" % len(a), *a)


def str_to_a32(s: bytes) -> list[int]:
    if len(s) % 4:
        s += b"\0" * (4 - len(s) % 4)
    return list(struct.unpack(">%dI" % (len(s) // 4), s))


def base64_url_decode(data: str) -> bytes:
    import base64

    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data)


def base64_url_encode(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def encrypt_key(a: list[int], key: list[int]) -> list[int]:
    result = []
    for i in range(0, len(a), 4):
        cipher = AES.new(a32_to_str(key), AES.MODE_ECB)
        result.extend(str_to_a32(cipher.encrypt(a32_to_str(a[i : i + 4]))))
    return result


def decrypt_key(a: list[int], key: list[int]) -> list[int]:
    result = []
    for i in range(0, len(a), 4):
        cipher = AES.new(a32_to_str(key), AES.MODE_ECB)
        result.extend(str_to_a32(cipher.decrypt(a32_to_str(a[i : i + 4]))))
    return result


def prepare_key(password: str) -> list[int]:
    pw_bytes = password.encode("utf-8")
    pw_a32 = str_to_a32(pw_bytes)
    pkey = [0x93C467E3, 0x7DB0C7A4, 0xD1BE3F81, 0x0152CB56]
    for i in range(0, len(pw_a32), 4):
        key = [0, 0, 0, 0]
        for j in range(min(4, len(pw_a32) - i)):
            key[j] = pw_a32[i + j]
        pkey = encrypt_key(pkey, key)
    return pkey


def stringhash(s: str, aeskey: list[int]) -> str:
    s_bytes = s.lower().encode("utf-8")
    s32 = str_to_a32(s_bytes)
    h32 = [0, 0, 0, 0]
    for i in range(len(s32)):
        h32[i % 4] ^= s32[i]
    for _ in range(0x4000):
        cipher = AES.new(a32_to_str(aeskey), AES.MODE_ECB)
        h32 = str_to_a32(cipher.encrypt(a32_to_str(h32)))
    return base64_url_encode(a32_to_str([h32[0], h32[2]]))


def decrypt_attr(attr: bytes, key: list[int]) -> dict | None:
    cipher = AES.new(a32_to_str(key), AES.MODE_CBC, iv=b"\0" * 16)
    attr = cipher.decrypt(attr)
    try:
        attr = attr.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if attr[:6] == 'MEGA{"':
        return json.loads(attr[4:].split("}")[0] + "}")
    return None


class MegaClient:
    def __init__(self) -> None:
        self.sid: str | None = None
        self.master_key: list[int] = []
        self.seq_no = 0

    def api_request(self, data: list[dict]) -> list:
        params: dict = {"id": self.seq_no}
        self.seq_no += 1
        if self.sid:
            params["sid"] = self.sid
        resp = requests.post(API_URL, params=params, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def login(self, email: str, password: str) -> None:
        password_key = prepare_key(password)
        uh = stringhash(email, password_key)
        resp = self.api_request([{"a": "us", "user": email, "uh": uh}])
        if isinstance(resp[0], int):
            if resp[0] == -9:
                logger.error("Login failed: wrong email or password")
            else:
                logger.error("Login failed with error code: %d", resp[0])
            sys.exit(1)

        enc_master_key = base64_url_decode(resp[0]["k"])
        self.master_key = decrypt_key(str_to_a32(enc_master_key), password_key)

        enc_private_key = base64_url_decode(resp[0]["privk"])

        if "csid" in resp[0]:
            enc_sid = base64_url_decode(resp[0]["csid"])
            # RSA decrypt session ID

            privk = decrypt_key(str_to_a32(enc_private_key), self.master_key)
            privk_bytes = a32_to_str(privk)

            # Parse MPI components
            def get_mpi(data: bytes, offset: int) -> tuple[int, int]:
                length = (struct.unpack(">H", data[offset : offset + 2])[0] + 7) // 8
                return (
                    int.from_bytes(data[offset + 2 : offset + 2 + length], "big"),
                    offset + 2 + length,
                )

            p, o = get_mpi(privk_bytes, 0)
            q, o = get_mpi(privk_bytes, o)
            d, o = get_mpi(privk_bytes, o)
            u, o = get_mpi(privk_bytes, o)

            # Decrypt session ID using RSA
            n = p * q
            sid_int = int.from_bytes(enc_sid, "big")
            decrypted = pow(sid_int, d, n)
            dec_bytes = decrypted.to_bytes((decrypted.bit_length() + 7) // 8, "big")
            self.sid = base64_url_encode(dec_bytes[:43])

        logger.info("Login successful")

    def get_files(self) -> dict:
        resp = self.api_request([{"a": "f", "c": 1, "r": 1}])
        files = {}
        for item in resp[0]["f"]:
            node_id = item["h"]
            parent = item.get("p")
            node_type = item["t"]

            if node_type in (0, 1) and "k" in item:
                # Decrypt node key and attributes
                key_str = item["k"]
                try:
                    # Format: owner:key_data
                    key_data = base64_url_decode(key_str.split(":")[1])
                    key_a32 = str_to_a32(key_data)
                    decrypted_key = decrypt_key(key_a32, self.master_key)

                    if node_type == 0:  # file
                        file_key = [
                            decrypted_key[0] ^ decrypted_key[4],
                            decrypted_key[1] ^ decrypted_key[5],
                            decrypted_key[2] ^ decrypted_key[6],
                            decrypted_key[3] ^ decrypted_key[7],
                        ]
                    else:  # folder
                        file_key = decrypted_key[:4]

                    attr_data = base64_url_decode(item["a"])
                    attrs = decrypt_attr(attr_data, file_key)

                    files[node_id] = {
                        "t": node_type,
                        "p": parent,
                        "a": attrs,
                        "s": item.get("s", 0),
                        "key": decrypted_key,
                    }
                except Exception:
                    pass
            elif node_type in (2, 3, 4):
                files[node_id] = {
                    "t": node_type,
                    "p": parent,
                    "a": None,
                    "s": 0,
                    "key": [],
                }

        return files

    def download_file(self, node_id: str, node: dict, dest: Path) -> Path:
        """Download and decrypt a single file."""
        resp = self.api_request([{"a": "g", "g": 1, "n": node_id}])
        dl_url = resp[0]["g"]
        file_size = resp[0]["s"]
        key = node["key"]

        # Build AES-CTR key and IV
        k = [key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7]]
        iv = key[4:6] + [0, 0]

        file_name = node["a"]["n"]
        out_path = dest / file_name
        dest.mkdir(parents=True, exist_ok=True)

        logger.info("  Downloading: %s (%.1f MB)", file_name, file_size / 1024 / 1024)

        # Stream download and decrypt
        ctr = Counter.new(128, initial_value=int.from_bytes(a32_to_str(iv), "big"))
        cipher = AES.new(a32_to_str(k), AES.MODE_CTR, counter=ctr)

        with requests.get(dl_url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(cipher.decrypt(chunk))

        logger.info("  Done: %s", file_name)
        return out_path


def find_folder(files: dict, target_path: str) -> str | None:
    """Navigate folder tree to find target folder ID."""
    parts = target_path.strip("/").split("/")
    current_parent = None

    for part in parts:
        found = False
        for node_id, node in files.items():
            if node["t"] == 1 and node["a"] and node["a"].get("n") == part:
                if current_parent is None or node.get("p") == current_parent:
                    current_parent = node_id
                    found = True
                    logger.info("Found folder: %s -> %s", part, node_id)
                    break
        if not found:
            logger.error("Folder '%s' not found", part)
            return None
    return current_parent


def download_folder_recursive(
    client: MegaClient, files: dict, folder_id: str, dest: Path
) -> list[Path]:
    """Download all files from a folder recursively."""
    downloaded = []

    # Download files in this folder
    for node_id, node in files.items():
        if node.get("p") == folder_id and node["t"] == 0:
            path = client.download_file(node_id, node, dest)
            downloaded.append(path)

    # Recurse into subfolders
    for node_id, node in files.items():
        if node.get("p") == folder_id and node["t"] == 1:
            sub_name = node["a"]["n"] if node["a"] else "unknown"
            downloaded.extend(
                download_folder_recursive(client, files, node_id, dest / sub_name)
            )

    return downloaded


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else None
    password = sys.argv[2] if len(sys.argv) > 2 else None

    if not email or not password:
        logger.error("Usage: python mega_download.py <email> <password>")
        sys.exit(1)

    client = MegaClient()
    logger.info("Logging in as %s...", email)
    client.login(email, password)

    logger.info("Fetching file tree...")
    files = client.get_files()
    logger.info("Got %d nodes", len(files))

    folder_id = find_folder(files, TARGET_PATH)
    if not folder_id:
        # List root folders to help debug
        logger.info("Root folders:")
        for nid, n in files.items():
            if (
                n["t"] == 1
                and n["a"]
                and n.get("p") in [nid2 for nid2, n2 in files.items() if n2["t"] == 2]
            ):
                logger.info("  /%s", n["a"]["n"])
        sys.exit(1)

    logger.info("Downloading folder to %s ...", OUTPUT_DIR)
    downloaded = download_folder_recursive(client, files, folder_id, OUTPUT_DIR)

    logger.info("=== Download complete: %d files ===", len(downloaded))
    total = sum(f.stat().st_size for f in downloaded)
    logger.info("Total size: %.1f MB", total / 1024 / 1024)
    for f in downloaded:
        logger.info(
            "  %s (%.1f MB)", f.relative_to(OUTPUT_DIR), f.stat().st_size / 1024 / 1024
        )


if __name__ == "__main__":
    main()
