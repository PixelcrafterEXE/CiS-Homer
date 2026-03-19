import subprocess
import json
import csv
import datetime
import os
import threading
import time

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

def export_data(sensor: Sensor) -> None:
    if not _target_part:
        return
        
    try:
        # Check if it is already mounted
        out = subprocess.check_output(['lsblk', '-o', 'MOUNTPOINT', '-n', _target_part], text=True).strip()
        already_mounted = bool(out)
        mount_point = out
        
        if not already_mounted:
            # Mount using udisksctl (handles permissions securely)
            try:
                mount_out = subprocess.check_output(['udisksctl', 'mount', '-b', _target_part], text=True, stderr=subprocess.STDOUT)
                # Extract mount point from output: "Mounted /dev/sdX1 at /media/user/DRIVE."
                if " at " in mount_out:
                    mount_point = mount_out.split(" at ")[1].strip().rstrip('.')
                else:
                    # Fallback: check lsblk
                    mount_point = subprocess.check_output(['lsblk', '-o', 'MOUNTPOINT', '-n', _target_part], text=True).strip()
            except subprocess.CalledProcessError as e:
                print(f"Error mounting: {e.output}")
                return
            
        if not mount_point:
            print("Could not determine mount point.")
            return

        # Fetch the most recent measurement
        try:
            raw_data = sensor.getRaw()
        except Exception as e:
            print(f"Error reading from sensor: {e}")
            return # Let the OS handle the mount since we had trouble reading data

        # Save to CSV
        filename = datetime.datetime.now().strftime("Measurement_%Y%m%d_%H%M%S.csv")
        filepath = os.path.join(mount_point, filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Raw Data"])
            for val in raw_data:
                writer.writerow([val])
                
        # Only unmount if we mounted it in this session. If the user already mounted it before, don't unmount it
        if not already_mounted:
            # Some OS-level automounters or our tight loop might hold locks. Wait briefly.
            time.sleep(1)
            subprocess.run(['udisksctl', 'unmount', '-b', _target_part])
        
    except Exception as e:
        print(f"Export failed: {e}")
