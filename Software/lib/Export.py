import subprocess
import json
import csv
import datetime
import os
import threading
import time

import numpy as np

from lib.Sensor import Sensor

_target_part = None
_usb_available = False

def _usb_check_loop() -> None:
    global _target_part, _usb_available
    while True:
        valid = False
        target_part = None
        
        try:
            # Check for block devices
            out = subprocess.check_output(['lsblk', '-o', 'NAME,TYPE,TRAN', '-J'], text=True)
            data = json.loads(out)
            
            # Find disks with USB transport
            usb_disks = [dev for dev in data.get('blockdevices', []) if dev.get('tran') == 'usb' and dev.get('type') == 'disk']
            
            # Find all mountable volumes (exactly one partition) across all USB sticks
            valid_parts = []
            for disk in usb_disks:
                children = disk.get('children', [])
                parts = [c for c in children if c.get('type') == 'part']
                if len(parts) == 1:
                    valid_parts.append(f"/dev/{parts[0]['name']}")
                    
            # We only allow exporting if there is exactly ONE unambiguous volume
            if len(usb_disks) == 1 and len(valid_parts) == 1:
                target_part = valid_parts[0]
                valid = True
        except Exception:
            pass
            
        _target_part = target_part
        _usb_available = valid
        time.sleep(2)

# Start background check for USB devices
threading.Thread(target=_usb_check_loop, daemon=True).start()

def is_usb_available() -> bool:
    return _usb_available

def export_data(sensor: Sensor, on_success=None, on_error=None) -> None:
    """Export a CSV measurement to the USB drive.

    Returns immediately; the actual I/O runs on a daemon thread.
    *on_success()* is called (from that thread) when the file is written.
    *on_error(msg: str)* is called on any failure.  Both are optional.
    """
    if not _target_part:
        if on_error:
            on_error("No USB storage detected.")
        return

    def _run() -> None:
        try:
            # ── Mount ────────────────────────────────────────────────────────
            out = subprocess.check_output(
                ['lsblk', '-o', 'MOUNTPOINT', '-n', _target_part], text=True
            ).strip()
            already_mounted = bool(out)
            mount_point = out

            if not already_mounted:
                try:
                    mount_out = subprocess.check_output(
                        ['udisksctl', 'mount', '-b', _target_part],
                        text=True, stderr=subprocess.STDOUT,
                    )
                    if " at " in mount_out:
                        mount_point = mount_out.split(" at ")[1].strip().rstrip('.')
                    else:
                        mount_point = subprocess.check_output(
                            ['lsblk', '-o', 'MOUNTPOINT', '-n', _target_part], text=True
                        ).strip()
                except subprocess.CalledProcessError as e:
                    if on_error:
                        on_error(f"USB mount failed: {e.output.strip()}")
                    return

            if not mount_point:
                if on_error:
                    on_error("Could not determine USB mount point.")
                return

            # ── Read sensor ──────────────────────────────────────────────────
            try:
                raw_data = sensor.getRaw()
            except Exception as e:
                if on_error:
                    on_error(f"Sensor read failed: {e}")
                return

            try:
                cal_data = sensor.getCalibrated()
            except Exception:
                cal_data = None   # non-fatal; export raw only

            # ── Write CSV ────────────────────────────────────────────────────
            filename = datetime.datetime.now().strftime("Measurement_%Y%m%d_%H%M%S.csv")
            filepath = os.path.join(mount_point, filename)

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                if cal_data is not None:
                    writer.writerow(["Channel", "Raw_ADC", "Irradiance_uW_per_mm2"])
                    for i, raw_val in enumerate(raw_data):
                        cal_val = cal_data[i]
                        irr_str = f"{cal_val:.4f}" if not np.isnan(cal_val) else ""
                        writer.writerow([i + 1, int(raw_val), irr_str])
                else:
                    writer.writerow(["Channel", "Raw_ADC"])
                    for i, raw_val in enumerate(raw_data):
                        writer.writerow([i + 1, int(raw_val)])

            # ── Unmount (only if we mounted) ─────────────────────────────────
            if not already_mounted:
                time.sleep(1)
                subprocess.run(['udisksctl', 'unmount', '-b', _target_part])

            if on_success:
                on_success()

        except Exception as e:
            if on_error:
                on_error(f"Export failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
