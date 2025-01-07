import os
import json
import base64
from datetime import datetime, timezone
import plistlib
import glob
from typing import Dict, List, Union


class TitleManager:
    def __init__(self, app_name: str, base_path: str = "/Applications", patch_only: bool = False):
        self.app_name = app_name.rstrip(".app") if app_name.endswith(".app") else app_name
        self.base_path = base_path
        self.patch_only = patch_only
        self.app_path = self.find_application(app_name)

    def find_application(self, app_name: str) -> str:
        search_pattern = os.path.join(self.base_path, self.app_name)
        matches = glob.glob(search_pattern)

        if not matches:
            raise ValueError(f"Application '{app_name}' not found in {self.base_path}.")
        return matches[0]

    def load_plist(self) -> Dict[str, Union[str, List[str]]]:
        plist_path = os.path.join(self.app_path, "Contents", "Info.plist")
        try:
            with open(plist_path, "rb") as f:
                return plistlib.load(f)
        except Exception as e:
            raise RuntimeError(f"Error reading plist file at {plist_path}. Details: {e}")

    def extract_app_info(self) -> Dict[str, str]:
        """Extract app metadata from the plist file."""
        plist_data = self.load_plist()

        app_name = plist_data.get(
            "CFBundleName", os.path.basename(self.app_path).replace(".app", "")
        )
        app_id = app_name.replace(" ", "")
        app_bundle_id = plist_data.get("CFBundleIdentifier", "unknown.bundle.id")
        app_version = plist_data.get("CFBundleShortVersionString", "0.0.0")
        app_min_os = plist_data.get("LSMinimumSystemVersion", "10.9")

        app_last_modified = datetime.now(timezone.utc).isoformat() + "Z"
        app_timestamp = datetime.fromtimestamp(os.path.getmtime(self.app_path), timezone.utc).isoformat() + "Z"

        return {
            "app_name": app_name,
            "app_id": app_id,
            "app_bundle_id": app_bundle_id,
            "app_version": app_version,
            "app_min_os": app_min_os,
            "app_last_modified": app_last_modified,
            "app_timestamp": app_timestamp,
        }

    def create_patch(self, app_info: Dict) -> Dict:
        """Create a patch definition."""
        return {
            "version": app_info["app_version"],
            "releaseDate": app_info["app_timestamp"],
            "standalone": True,
            "minimumOperatingSystem": app_info["app_min_os"],
            "reboot": False,
            "killApps": [{"bundleId": app_info["app_bundle_id"], "appName": app_info["app_name"]}],
            "components": [
                {
                    "name": app_info["app_name"],
                    "version": app_info["app_version"],
                    "criteria": [
                        {
                            "name": "Application Bundle ID",
                            "operator": "is",
                            "value": app_info["app_bundle_id"],
                            "type": "recon",
                        },
                        {
                            "name": "Application Version",
                            "operator": "is",
                            "value": app_info["app_version"],
                            "type": "recon",
                        },
                    ],
                }
            ],
            "capabilities": [
                {
                    "name": "Operating System Version",
                    "operator": "greater than or equal",
                    "value": app_info["app_min_os"],
                    "type": "recon",
                }
            ],
            "dependencies": [],
        }

    def create_full_definition(self, app_info: Dict[str, str], patch: Dict) -> Dict:
        """Create a full patch definition."""
        return {
            "id": app_info["app_id"],
            "name": app_info["app_name"],
            "publisher": app_info["app_name"],  # Default publisher to app name
            "appName": f"{app_info['app_name']}.app",
            "bundleId": app_info["app_bundle_id"],
            "lastModified": app_info["app_last_modified"],
            "currentVersion": app_info["app_version"],
            "requirements": [
                {
                    "name": "Application Bundle ID",
                    "operator": "is",
                    "value": app_info["app_bundle_id"],
                    "type": "recon",
                }
            ],
            "patches": [patch],
            "extensionAttributes": [],
        }

    def generate(self, pretty_print: bool = False) -> Union[str, Dict]:
        """Generate the patch definition or full definition."""
        app_info = self.extract_app_info()
        patch = self.create_patch(app_info)

        output = patch if self.patch_only else self.create_full_definition(app_info, patch)
        if pretty_print:
            return json.dumps(output, indent=4)
        return output


if __name__ == "__main__":
    manager = TitleManager("Rectangle.app")
    output = manager.generate(pretty_print=True)

    print(output)
