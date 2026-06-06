#!/usr/bin/env python3
"""Probe a Dreame MiOT property through the integration API.

Credentials are read from environment variables by default:
  DREAME_USERNAME, DREAME_PASSWORD, DREAME_COUNTRY
"""
from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "custom_components" / "dreame_airpurifier" / "api.py"

spec = importlib.util.spec_from_file_location("dreame_airpurifier_api", API_PATH)
if spec is None or spec.loader is None:
    print(f"Could not load {API_PATH}")
    sys.exit(2)
api_module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(api_module)
except ModuleNotFoundError as ex:
    if ex.name == "requests":
        print("Missing Python package: requests")
        print("Install it with: python3 -m pip install requests")
        print("Or run without installing: uv run --with requests python scripts/probe_property.py ...")
        sys.exit(2)
    raise
DreameCloudAPI = api_module.DreameCloudAPI
CANDIDATE_TOGGLES = getattr(
    api_module,
    "EXPERIMENTAL_TOGGLES",
    [
        {"id": 1, "name": "Toggle 1", "siid": 2, "piid": 6},
        {"id": 4, "name": "Toggle 4", "siid": 7, "piid": 7},
        {"id": 5, "name": "Toggle 5", "siid": 2, "piid": 6},
    ],
)
CANDIDATE_TOGGLE_POLL_BATCHES = getattr(
    api_module,
    "EXPERIMENTAL_TOGGLE_POLL_BATCHES",
    [[toggle] for toggle in CANDIDATE_TOGGLES],
)
CANDIDATE_TOGGLE_BY_ID = {toggle["id"]: toggle for toggle in CANDIDATE_TOGGLES}
CANDIDATE_TOGGLE_IDS = sorted(CANDIDATE_TOGGLE_BY_ID)
PAI_CANDIDATES = [
    {
        "name": "filter_life_percent",
        "siid": 4,
        "piid": 1,
        "type": "read-only",
        "comment": "Existing app percentage, for example around 80%.",
    },
    {
        "name": "filter_days_left",
        "siid": 4,
        "piid": 2,
        "type": "read-only",
        "comment": "Expected High Efficiency Composite Filter days-left value, for example 292.",
    },
    {
        "name": "device_location",
        "siid": 6,
        "piid": 3,
        "type": "read-only",
        "comment": "User-set device location, for example Munich.",
    },
    {
        "name": "negative_ion_uvc",
        "siid": 6,
        "piid": 7,
        "type": "toggle",
        "comment": "Confirmed Dreamehome Negative Ion + UVC switch.",
    },
    {
        "name": "fan_percent_read_only",
        "siid": 2,
        "piid": 5,
        "type": "known",
        "comment": "Read-only fan percentage on AP10; included because comparable MIOT layouts put anion nearby.",
    },
    {
        "name": "standard_anion_slot_conflict",
        "siid": 2,
        "piid": 6,
        "type": "known",
        "comment": "Comparable purifiers often use piid 5/6 for anion, but AP10 2/6 is LED color.",
    },
    {
        "name": "standard_uv_slot_conflict",
        "siid": 2,
        "piid": 7,
        "type": "known",
        "comment": "Comparable purifiers often place UV next to anion, but AP10 2/7 is keypress tone.",
    },
    {
        "name": "negative_ion_uv_candidate_7_5",
        "siid": 7,
        "piid": 5,
        "type": "candidate-toggle",
        "comment": "Adjacent to the remaining service-7 candidate; read first, then compare with app changes.",
    },
    {
        "name": "negative_ion_uv_candidate_7_6",
        "siid": 7,
        "piid": 6,
        "type": "candidate-toggle",
        "comment": "Adjacent to the remaining service-7 candidate; read first, then compare with app changes.",
    },
    {
        "name": "negative_ion_uv_candidate_7_7",
        "siid": 7,
        "piid": 7,
        "type": "candidate-toggle",
        "comment": "Current remaining experimental Toggle 4.",
    },
    {
        "name": "device_setting_candidate_6_9",
        "siid": 6,
        "piid": 9,
        "type": "candidate-toggle",
        "comment": "Nearby device-settings slot after timer.",
    },
    {
        "name": "device_setting_candidate_6_10",
        "siid": 6,
        "piid": 10,
        "type": "candidate-toggle",
        "comment": "Nearby device-settings slot after timer.",
    },
]


def parse_value(raw: str):
    lowered = raw.lower()
    if lowered in {"true", "on", "yes"}:
        return 1
    if lowered in {"false", "off", "no"}:
        return 0
    try:
        return int(raw)
    except ValueError:
        return raw


def read_candidate_toggles(api: DreameCloudAPI, did: str, host: str | None) -> dict:
    values = {}
    for batch in CANDIDATE_TOGGLE_POLL_BATCHES:
        values.update(api.get_properties(did, batch, host))
    return values


def parse_range(raw: str) -> tuple[int, int]:
    if "-" in raw:
        start_raw, end_raw = raw.split("-", 1)
        start = int(start_raw)
        end = int(end_raw)
    else:
        start = int(raw)
        end = start
    if start > end:
        raise ValueError(f"Invalid range {raw!r}: start is greater than end")
    return start, end


def read_property_range(
    api: DreameCloudAPI,
    did: str,
    host: str | None,
    siid_start: int,
    siid_end: int,
    piid_start: int,
    piid_end: int,
) -> dict[tuple[int, int], dict]:
    values = {}
    for siid in range(siid_start, siid_end + 1):
        params = [
            {"did": did, "siid": siid, "piid": piid}
            for piid in range(piid_start, piid_end + 1)
        ]
        result = api.send_command(did, "get_properties", params, host)
        for item in result or []:
            if not isinstance(item, dict):
                continue
            key = (item.get("siid", siid), item.get("piid"))
            values[key] = {"code": item.get("code"), "value": item.get("value")}
    return values


def print_property_values(values: dict[tuple[int, int], dict], include_errors: bool = False) -> None:
    for siid, piid in sorted(values):
        item = values[(siid, piid)]
        code = item.get("code")
        value = item.get("value")
        if code == 0 or include_errors:
            print(f"  siid={siid} piid={piid}: code={code}, value={value!r}")


def print_property_diff(before: dict[tuple[int, int], dict], after: dict[tuple[int, int], dict]) -> None:
    changed = []
    for key in sorted(set(before) | set(after)):
        before_item = before.get(key, {})
        after_item = after.get(key, {})
        if before_item != after_item:
            changed.append((key, before_item, after_item))
    if not changed:
        print("No property changes detected in the scanned range.")
        return
    print("Changed properties:")
    for (siid, piid), before_item, after_item in changed:
        print(
            f"  siid={siid} piid={piid}: "
            f"code {before_item.get('code')!r}->{after_item.get('code')!r}, "
            f"value {before_item.get('value')!r}->{after_item.get('value')!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read or write one Dreame AP10 MiOT property."
    )
    parser.add_argument("--username", default=os.environ.get("DREAME_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("DREAME_PASSWORD"))
    parser.add_argument("--country", default=os.environ.get("DREAME_COUNTRY", "us"))
    parser.add_argument("--did", help="Device id. Defaults to the first air purifier.")
    parser.add_argument(
        "--device-info",
        action="store_true",
        help="Print discovered purifier metadata and exit.",
    )
    parser.add_argument("--host", help="bindDomain override. Defaults to discovered device bindDomain.")
    parser.add_argument("--siid", type=int, help="Service id to read or write.")
    parser.add_argument(
        "--scan-siids",
        help="Service id range for --scan-piids, for example 1-8. Defaults to --siid.",
    )
    parser.add_argument("--piid", type=int, help="Property id to read or write.")
    parser.add_argument(
        "--scan-piids",
        help="Read a piid range, for example 1-12. Does not write anything.",
    )
    parser.add_argument("--value", help="Value to write. Omit to read only.")
    parser.add_argument(
        "--toggle",
        action="store_true",
        help="Write 0 when the current value is truthy, otherwise write 1.",
    )
    parser.add_argument(
        "--list-toggles",
        action="store_true",
        help="List numbered candidate toggles and exit.",
    )
    parser.add_argument(
        "--toggle-id",
        type=int,
        choices=CANDIDATE_TOGGLE_IDS,
        metavar="N",
        help="Use a numbered candidate toggle instead of --siid/--piid.",
    )
    parser.add_argument(
        "--read-toggle-id",
        type=int,
        choices=CANDIDATE_TOGGLE_IDS,
        metavar="N",
        help="Read a numbered candidate toggle without writing.",
    )
    parser.add_argument(
        "--read-all-toggles",
        action="store_true",
        help="Read all numbered candidate toggles without writing.",
    )
    parser.add_argument(
        "--read-pai-candidates",
        action="store_true",
        help="Read focused candidates for filter days-left and Negative Ion + UVC probing.",
    )
    parser.add_argument(
        "--trace-app-change",
        action="store_true",
        help="Read a property range, wait for you to change the Dreamehome app setting, then print diffs.",
    )
    parser.add_argument(
        "--trace-siids",
        default="2-8",
        help="Service id range for --trace-app-change. Defaults to 2-8.",
    )
    parser.add_argument(
        "--trace-piids",
        default="1-12",
        help="Property id range for --trace-app-change. Defaults to 1-12.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait before the post-write read.",
    )
    args = parser.parse_args()

    if args.list_toggles:
        for toggle_id in CANDIDATE_TOGGLE_IDS:
            toggle = CANDIDATE_TOGGLE_BY_ID[toggle_id]
            print(f"{toggle_id}: {toggle['name']} siid={toggle['siid']} piid={toggle['piid']}")
        return 0

    selected_modes = sum(
        1
        for selected in (args.toggle_id, args.read_toggle_id, args.read_all_toggles)
        if selected is not None and selected is not False
    )
    if selected_modes > 1:
        print("Use only one of --toggle-id, --read-toggle-id, or --read-all-toggles.")
        return 2

    if args.toggle_id is not None or args.read_toggle_id is not None:
        toggle_id = args.toggle_id or args.read_toggle_id
        toggle = CANDIDATE_TOGGLE_BY_ID[toggle_id]
        args.siid = toggle["siid"]
        args.piid = toggle["piid"]
        if args.toggle_id is not None:
            args.toggle = args.toggle or args.value is None

    if not args.username:
        args.username = input("Dreame username: ").strip()
    if not args.password:
        args.password = getpass.getpass("Dreame password: ")
    if not args.username or not args.password:
        print("Missing Dreame username/password.")
        return 2

    api = DreameCloudAPI(args.username, args.password, args.country)
    if not api.login():
        print("Login failed.")
        return 1

    did = args.did
    host = args.host
    if not did:
        purifiers = api.get_purifiers()
        if not purifiers:
            print("No Dreame air purifiers found on this account.")
            return 1
        device = purifiers[0]
        if args.device_info:
            print(json.dumps(device, indent=2, sort_keys=True))
            return 0
        did = str(device["did"])
        host = host or device.get("bindDomain")
        name = device.get("customName") or device.get("deviceInfo", {}).get("displayName")
        print(f"Using device: {name or device.get('model', 'unknown')} ({device.get('model')})")

    if args.read_all_toggles:
        values = read_candidate_toggles(api, did, host)
        for toggle_id in CANDIDATE_TOGGLE_IDS:
            toggle = CANDIDATE_TOGGLE_BY_ID[toggle_id]
            value = values.get((toggle["siid"], toggle["piid"]))
            print(
                f"{toggle_id}: {toggle['name']} siid={toggle['siid']} "
                f"piid={toggle['piid']} value={value!r}"
            )
        return 0

    if args.read_pai_candidates:
        params = [
            {"did": did, "siid": candidate["siid"], "piid": candidate["piid"]}
            for candidate in PAI_CANDIDATES
        ]
        result = api.send_command(did, "get_properties", params, host)
        values = {}
        for item in result or []:
            if isinstance(item, dict):
                values[(item.get("siid"), item.get("piid"))] = item
        for candidate in PAI_CANDIDATES:
            item = values.get((candidate["siid"], candidate["piid"]), {})
            print(
                f"{candidate['name']}: siid={candidate['siid']} "
                f"piid={candidate['piid']} type={candidate['type']} "
                f"code={item.get('code')!r} value={item.get('value')!r} "
                f"comment={candidate['comment']}"
            )
        return 0

    if args.trace_app_change:
        try:
            siid_start, siid_end = parse_range(args.trace_siids)
            piid_start, piid_end = parse_range(args.trace_piids)
        except ValueError as ex:
            print(ex)
            return 2
        print(f"Reading baseline siid={siid_start}-{siid_end} piid={piid_start}-{piid_end}...")
        before = read_property_range(api, did, host, siid_start, siid_end, piid_start, piid_end)
        print("Readable baseline values:")
        print_property_values(before)
        input("Change the target control in the Dreamehome app, then press Enter to read again...")
        after = read_property_range(api, did, host, siid_start, siid_end, piid_start, piid_end)
        print_property_diff(before, after)
        return 0

    if args.scan_piids:
        if args.siid is None and not args.scan_siids:
            print("Either --siid or --scan-siids is required with --scan-piids.")
            return 2
        if args.scan_siids:
            siid_start, siid_end = parse_range(args.scan_siids)
        else:
            siid_start = args.siid
            siid_end = args.siid
        start, end = parse_range(args.scan_piids)
        print(f"Scan siid={siid_start}-{siid_end} piid={start}-{end}:")
        values = read_property_range(api, did, host, siid_start, siid_end, start, end)
        print_property_values(values, include_errors=True)
        return 0

    if args.siid is None or args.piid is None:
        print("Either --toggle-id, --scan-piids, --read-pai-candidates, --trace-app-change, or both --siid and --piid are required.")
        return 2

    prop = {"siid": args.siid, "piid": args.piid}
    if args.toggle_id is not None or args.read_toggle_id is not None:
        toggle_index = args.toggle_id or args.read_toggle_id
        toggle = CANDIDATE_TOGGLE_BY_ID[toggle_index]
        print(
            f"{toggle_index}: {toggle['name']} "
            f"siid={toggle['siid']} piid={toggle['piid']}"
        )
    before = api.get_properties(did, [prop], host).get((args.siid, args.piid))
    if before is None and (args.toggle_id is not None or args.read_toggle_id is not None):
        before = read_candidate_toggles(api, did, host).get((args.siid, args.piid))
    print(f"Before siid={args.siid} piid={args.piid}: {before!r}")

    if args.value is None and not args.toggle:
        return 0

    if args.toggle:
        value = 0 if before else 1
    else:
        value = parse_value(args.value)
    ok = api.set_property(did, args.siid, args.piid, value, host)
    print(f"Write value={value!r}: {'ok' if ok else 'failed'}")

    if args.delay > 0:
        time.sleep(args.delay)
    after = api.get_properties(did, [prop], host).get((args.siid, args.piid))
    if after is None and args.toggle_id is not None:
        after = read_candidate_toggles(api, did, host).get((args.siid, args.piid))
    print(f"After siid={args.siid} piid={args.piid}: {after!r}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
