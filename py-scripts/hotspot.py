import uiautomator2 as u2
import subprocess
import time
import argparse

def open_hotspot_toggle_screen(d):
    print("Locating 'Wi-Fi hotspot'...")
    try:
        if d(textContains="Not sharing internet").exists:
            print("Clicking on 'Wi-Fi hotspot' setting")
            d(textContains="Not sharing internet").click()
            time.sleep(2)

        if d(textContains="device connected").exists:
            print("Clicking on 'Wi-Fi hotspot' setting")
            d(textContains="device connected").click()
            time.sleep(2)

        if d(textContains="devices connected").exists:
            print("Clicking on 'Wi-Fi hotspot' setting")
            d(textContains="devices connected").click()
            time.sleep(2)

    except Exception as e:
        print(f"[ERROR] While scrolling to 'Wi-Fi hotspot': {e}")


def toggle_hotspot(d, disable):
    open_hotspot_toggle_screen(d)

    # Fallback method to grab the first switch on the Hotspot screen
    toggles = d(className="android.widget.Switch")
    if toggles.exists:
        toggle = toggles[0] 
        current_state = toggle.info["checked"]
        print(f"[{d.serial}] Hotspot is currently: {'ON' if current_state else 'OFF'}")
        if disable:
            if current_state:
                toggle.click()
                return                 
        if not current_state:
            toggle.click()
    else:
        print(f"[{d.serial}] No toggle switches found on screen.")


def process_device(serial, disable):
    print(f"\nProcessing device: {serial}")

    # Step 1: Launch Tether Settings
    subprocess.run([
        "adb", "-s", serial, "shell", "am", "start", "-n",
        "com.android.settings/.TetherSettings"
    ])
    time.sleep(2)

    # Step 2: Connect with uiautomator2
    try:
        d = u2.connect_usb(serial)
        d.serial = serial  # attach serial info for logging
        toggle_hotspot(d, disable)
    except Exception as e:
        print(f"[{serial}] Failed to connect or toggle hotspot: {e}")
    
    # # Step 3: Close the Settings app
    # subprocess.run([
    #     "adb", "-s", serial, "shell", "am", "force-stop",
    #     "com.android.settings"
    # ])
    # time.sleep(1)
    
    # adb -s 0B151JEC202377 shell am start -n com.android.settings/.TetherSettings
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Toggle Wi-Fi hotspot on Android devices via ADB and uiautomator2")
    parser.add_argument("--serial", required=True, help="Comma-separated list of ADB device serials")
    parser.add_argument("--disable", action='store_true', help="to Disable hotspot")
    args = parser.parse_args()

    serial_list = [s.strip() for s in args.serial.split(",") if s.strip()]
    for serial in serial_list:
        process_device(serial,args.disable)
