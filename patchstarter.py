import argparse
import base64
import json
import os
from datetime import datetime, timezone
import plistlib


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate patch definitions from macOS application bundles.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("path", help="Path to the application bundle", type=str)
    parser.add_argument("-o", "--output", help="Directory to save JSON file", type=str)
    parser.add_argument("-p", "--publisher", help="Publisher name", type=str, default="")
    parser.add_argument("-n", "--name", help="Display name", type=str, default="")
    parser.add_argument(
        "-e",
        "--extension-attribute",
        help="Path to script(s) for extension attributes",
        action="append",
    )
    parser.add_argument("--app-version", help="Override app version", type=str)
    parser.add_argument("--min-sys-version", help="Override minimum macOS version", type=str)
    parser.add_argument(
        "--patch-only", help="Create only a patch, not a full definition", action="store_true"
    )

    return parser.parse_args()


def load_plist(plist_path):
    """Load a plist file."""
    try:
        with open(plist_path, "rb") as f:
            return plistlib.load(f)
    except Exception as e:
        raise SystemExit(f"Error reading plist: {e}")


def get_app_info(args):
    """Extract app metadata from the Info.plist."""
    plist_path = os.path.join(args.path, "Contents", "Info.plist")
    info = load_plist(plist_path)

    app_name = args.name or info.get(
        "CFBundleName", os.path.basename(args.path).replace(".app", "")
    )
    app_id = app_name.replace(" ", "")
    app_bundle_id = info.get("CFBundleIdentifier", "unknown.bundle.id")
    app_version = args.app_version or info.get("CFBundleShortVersionString", "0.0.0")
    app_min_os = args.min_sys_version or info.get("LSMinimumSystemVersion", "10.9")

    app_last_modified = datetime.now(timezone.utc).isoformat() + "Z"
    app_timestamp = (
        datetime.fromtimestamp(os.path.getmtime(args.path), timezone.utc).isoformat() + "Z"
    )

    return {
        "app_name": app_name,
        "app_id": app_id,
        "app_bundle_id": app_bundle_id,
        "app_version": app_version,
        "app_min_os": app_min_os,
        "app_last_modified": app_last_modified,
        "app_timestamp": app_timestamp,
    }


def create_patch(info):
    """Create a patch definition."""
    return {
        "version": info["app_version"],
        "releaseDate": info["app_timestamp"],
        "standalone": True,
        "minimumOperatingSystem": info["app_min_os"],
        "reboot": False,
        "killApps": [{"bundleId": info["app_bundle_id"], "appName": info["app_name"]}],
        "components": [
            {
                "name": info["app_name"],
                "version": info["app_version"],
                "criteria": [
                    {
                        "name": "Application Bundle ID",
                        "operator": "is",
                        "value": info["app_bundle_id"],
                        "type": "recon",
                    },
                    {
                        "name": "Application Version",
                        "operator": "is",
                        "value": info["app_version"],
                        "type": "recon",
                    },
                ],
            }
        ],
        "capabilities": [
            {
                "name": "Operating System Version",
                "operator": "greater than or equal",
                "value": info["app_min_os"],
                "type": "recon",
            }
        ],
        "dependencies": [],
    }


def create_patch_definition(info, patch, args):
    """Create a full patch definition."""
    definition = {
        "id": info["app_id"],
        "name": info["app_name"],
        "publisher": args.publisher or info["app_name"],
        "appName": f"{info['app_name']}.app",
        "bundleId": info["app_bundle_id"],
        "lastModified": info["app_last_modified"],
        "currentVersion": info["app_version"],
        "requirements": [
            {
                "name": "Application Bundle ID",
                "operator": "is",
                "value": info["app_bundle_id"],
                "type": "recon",
            }
        ],
        "patches": [patch],
        "extensionAttributes": [],
    }

    # Add extension attributes if provided
    if args.extension_attribute:
        for ext_path in args.extension_attribute:
            try:
                with open(ext_path, "rb") as f:
                    ext_content = base64.b64encode(f.read()).decode("utf-8")
                definition["extensionAttributes"].append(
                    {
                        "key": info["app_name"].lower().replace(" ", "-"),
                        "value": ext_content,
                        "displayName": info["app_name"],
                    }
                )
            except IOError as e:
                raise SystemExit(f"Error reading extension attribute: {e}")

    return definition


def save_output(output, app_id, args):
    """Save output to a file or print to console."""
    filename = f"{app_id}-patch.json" if args.patch_only else f"{app_id}.json"
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        file_path = os.path.join(args.output, filename)
        with open(file_path, "w") as f:
            json.dump(output, f, indent=4)
        print(f"Saved patch definition to {file_path}")
    else:
        print(json.dumps(output, indent=4))


def main():
    args = parse_arguments()
    app_info = get_app_info(args)
    patch = create_patch(app_info)

    if args.patch_only:
        output = patch
    else:
        output = create_patch_definition(app_info, patch, args)

    save_output(output, app_info["app_id"], args)


if __name__ == "__main__":
    main()
