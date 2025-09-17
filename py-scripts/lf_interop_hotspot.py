
import sys
import os
import csv
import time
import shutil
import importlib
import logging
import datetime
import argparse
import threading
import subprocess
import pandas as pd
import numpy as np
import uiautomator2 as u2
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

if sys.version_info[0] != 3:
    print("This script requires Python3")
    exit()

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
Realm = realm.Realm
from lf_report import lf_report
from lf_graph import lf_line_graph

interop_connectivity = importlib.import_module("py-json.interop_connectivity")


class Hotspot(Realm):
    def __init__(self,
                 manager_ip=None,
                 resources=None,
                 port=8080,
                 instance="Hotspot",
                 iteration=1,
                 radio='1.1.wiphy0',
                 direction='download',
                 side_a_min_rate=1000000,
                 side_b_min_rate=1000000,
                 duration=120,
                 delay=20,
                 tos='BE',
                 type='lf_tcp',
                 _debug_on=False):
        super().__init__(lfclient_host=manager_ip,
                        debug_=_debug_on)
        self.manager_ip = manager_ip
        self.manager_port = port
        self.resources=resources
        self.instance = instance
        self.iteration = iteration
        self.duration=duration
        self.delay=delay
        self.devices_data = {}
        self.station_profile = self.new_station_profile()
        self.result_json = {}
        self.stop_time = None
        self.start_time = None
        self.device_info = {}
        self.direction = direction
        self.radio = radio
        self.tos = tos 
        self.type = type
        self.side_a_min_rate = side_a_min_rate
        self.side_b_min_rate = side_b_min_rate        
        self.sta_list = []
        
        #reporting variable
        self.file_path = "hotspot_traffic_data.csv"
        if not hasattr(self, 'traffic_data'):
                self.traffic_data = {}
        self.start_id = 1
        self.csv_details = {}
        self.all_device_details = {}
        self.selected_device_type = set()
        self.selected_resources = None
        self.ip_hostname = {}
        self.result_dict = {
                            'ip':[],
                            'hostname':[],
                            'download_speed':[],
                            'upload_speed':[],
                            'download_lat':[],
                            'upload_lat':[]
                        }
        self.iteration_dict = {}

    def get_port_data(self, serial):
        # Get ports
        ports = self.json_get('/ports/all')['interfaces']
        for port_data_dict in ports:
            port_name = list(port_data_dict.keys())[0]
            port_info = port_data_dict[port_name]
            if port_name.startswith(serial) and port_name.split('.')[-1] != 'wlan0' and port_name.split('.')[-1] != 'rmnet0':
                if port_info.get('ip') not in ["0.0.0.0", None, ""]:
                    return port_name


    def get_rssi_data(self):
        self.rssi_data = {}
        ports_data = self.json_get('/ports/all').get('interfaces', [])

        port_signals = {}
        for port_entry in ports_data:
            for port_name, port_info in port_entry.items():
                signal = port_info.get("signal", "-100")
                if isinstance(signal, str) and "dBm" in signal:
                    signal = signal.split()[0]
                elif isinstance(signal, str) and "dBm" not in signal:
                    signal = signal
                port_signals[port_name] = signal

        for sta in self.sta_list:
            try:
                res, card, sta_name = sta.split('.')
                for port_key in port_signals:
                    if port_key.endswith(sta_name):
                        self.rssi_data[sta] = port_signals[port_key]
                        break
                else:
                    self.rssi_data[sta] = "NA"
            except Exception as e:
                print(f"[ERROR] parsing RSSI for {sta}: {e}")
                self.rssi_data[sta] = "NA"

    def check_phantom(self, target_serial: str):
        import json
        """
        Returns:
        True  -> device is phantom
        False -> device is valid (non-phantom)
        None  -> device not found
        """
        is_phantom = None
        raw = self.json_get("/adb/all")
        adb_data = raw.get("devices", [])
        print(type(adb_data), "devices-type ===================DATA====================")

        # Normalize adb_data -> iterable of dicts called `entries`
        if isinstance(adb_data, dict):
            # Sometimes keys are serials, values are dicts
            # Try key match first (fast path), then fall back to values scan
            for k, v in adb_data.items():
                if isinstance(k, str) and (k == target_serial or k.endswith(target_serial)):
                    if isinstance(v, str):
                        try:
                            v = json.loads(v)
                        except Exception:
                            v = {}
                    if isinstance(v, dict):
                        return bool(v.get("phantom", False))
                    # if it's not a dict after all, just break to scan values
                    break
            entries = adb_data.values()
        elif isinstance(adb_data, list):
            entries = adb_data
        elif isinstance(adb_data, str):
            # Occasionally APIs return JSON as a string
            try:
                parsed = json.loads(adb_data)
            except json.JSONDecodeError:
                print("devices is a plain string; cannot parse JSON")
                return None
            if isinstance(parsed, dict):
                entries = parsed.values()
            elif isinstance(parsed, list):
                entries = parsed
            else:
                return None
        else:
            print(f"Unexpected type for devices: {type(adb_data)}")
            return None

        # Scan entries safely
        for idx, device_entry in enumerate(entries):
            # Convert JSON strings to dicts if needed; skip other junk
            if isinstance(device_entry, str):
                try:
                    device_entry = json.loads(device_entry)
                except Exception:
                    # Not JSON; skip
                    continue
            if not isinstance(device_entry, dict):
                continue

            name = str(device_entry.get("name", ""))
            link_tail = str(device_entry.get("_links", "")).rstrip("/").split("/")[-1]

            # Match by name suffix or by _links tail
            if name.endswith(target_serial) or link_tail == target_serial:
                print(f"Matched entry #{idx}: name={name} link_tail={link_tail}")
                is_phantom = bool(device_entry.get("phantom", False))
                break

        if is_phantom is None:
            print(f"Device {target_serial} not found in /adb/all")
        elif is_phantom:
            print(f"Device {target_serial} is a PHANTOM device")
        else:
            print(f"Device {target_serial} is a VALID (non-phantom) device")

        return is_phantom



    def cleanup(self):
        print('===========================')
        print('CLEANING ALL STATIONS')
        print(self.sta_list)
        print('===========================')
        self.station_profile.cleanup(self.sta_list, delay=1)
        self.sta_list = []

    def clean_cxs(self):
        self.cx_profile.cleanup_prefix()
        self.cx_profile.cleanup()
        for sta in self.sta_list:
            self.rm_port(sta, check_exists=True)

    def create_clients(self, device_info):
        self.station_profile = self.new_station_profile()
        self.sta_list = LFUtils.portNameSeries(
            prefix_="sta", start_id_= self.start_id, end_id_= self.start_id + int(device_info["Max_Clients_Supported"]) - 1, padding_number_=10000, radio=self.radio)
        self.start_id = self.start_id + int(device_info["Max_Clients_Supported"])
        self.station_profile.use_security(device_info['Security_Type'], device_info['Hotspot_Name'], device_info['Hotspot_Password'])
        self.station_profile.set_number_template("00")

        print("Creating  Virtual Stations...")
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)

        if self.station_profile.create(radio=self.radio, sta_names_=self.sta_list, debug=self.debug):
            self._pass("Stations created.")
        else:
            self._fail("Stations not properly created.")

        self.station_profile.admin_up()

        logger.info("Waiting to get IP for all stations...")
        time.sleep(5)

        if Realm.wait_for_ip(self=self, station_list=self.sta_list, timeout_sec=-1):
            self._pass("All stations got IPs", print_=True)
            self._pass("Station build finished", print_=True)
        else:
            self._fail("Stations failed to get IPs", print_=True)
            logger.info("Please re-check the configuration applied")

    @staticmethod
    def get_data_from_csv(csv_name, selected_resource_ids=None):
        device_details = {}
        selected_set = set(selected_resource_ids) if selected_resource_ids else None

        with open(csv_name, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                resource_id = row['Resource_Id'].strip()
                if selected_set and resource_id not in selected_set:
                    continue

                full_serial = row['Device_serial'].strip()
                serial = full_serial.split('.')[-1]
                device_details[full_serial] = row
        return device_details

    def run_remote_toggle(self, serial, disable=False, remote_script_path="hotspot.py"):
        remote_cmd = f"python3 {remote_script_path} --serial {serial.split('.')[-1]}"

        try:
            if self.manager_ip in ["localhost", "127.0.0.1"]:
                # Run locally if manager_ip is localhost
                disable = '--disable' if disable else ''
                remote_cmd = f"python3 /home/lanforge/{remote_script_path} --serial {serial.split('.')[-1]} {disable} "
                subprocess.run(remote_cmd, shell=True, check=True)
                time.sleep(6)
            else:
                subprocess.run([
                    "sshpass", "-p", "lanforge",
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    f"lanforge@{self.manager_ip}", remote_cmd
                ], check=True)
            print("Remote toggle executed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] SSH command failed: {e}")

        print("Waiting for device toggling to complete...")
    
    def enable_hotsport(self, DEVICE_SERIAL):
        subprocess.run([
            "adb", "-s", DEVICE_SERIAL, "shell", "am", "start", "-n",
            "com.android.settings/.TetherSettings"
        ])
        time.sleep(2)

        d = u2.connect_usb(DEVICE_SERIAL)

        # Click "Wi-Fi hotspot"
        def open_hotspot_toggle_screen():
            if d(textContains="hotspot").exists:
                d(textContains="hotspot").click()
                time.sleep(2)
            else:
                print("Wi-Fi hotspot option not found.")

        # Toggle the hotspot switch
        def toggle_hotspot():
            open_hotspot_toggle_screen()

            toggle = d(className="android.widget.Switch")
            if toggle.exists:
                current_state = toggle.info["checked"]
                print(f"Hotspot is currently: {'ON' if current_state else 'OFF'}")
                if not current_state:
                    toggle.click()
            else:
                print("Toggle switch not found.")

        toggle_hotspot() 

    def create_cx(self, upstream):
        print()
        self.cx_profile = self.new_l3_cx_profile()
        self.cx_profile.host = self.manager_ip
        self.cx_profile.port = self.manager_port
        if self.direction == 'download' and self.side_b_min_rate !=0 and self.side_a_min_rate == 0 :
            self.cx_profile.name_prefix = 'layer3-DL-'
            self.cx_profile.side_a_min_bps = 0
            self.cx_profile.side_a_max_bps = 0
            self.cx_profile.side_b_min_bps = self.side_b_min_rate
            self.cx_profile.side_b_max_bps = 0
        elif self.direction == 'upload' and self.side_a_min_rate !=0 and self.side_b_min_rate == 0 :
            self.cx_profile.name_prefix = 'layer3-UL-'
            self.cx_profile.side_a_min_bps = self.side_a_min_rate
            self.cx_profile.side_a_max_bps = 0
            self.cx_profile.side_b_min_bps = 0
            self.cx_profile.side_b_max_bps = 0
        elif self.direction == 'bidirectional' and self.side_b_min_rate !=0 and self.side_a_min_rate != 0 :
            self.cx_profile.name_prefix = 'layer3-BI-'
            self.cx_profile.side_a_min_bps = self.side_a_min_rate
            self.cx_profile.side_a_max_bps = 0
            self.cx_profile.side_b_min_bps = self.side_b_min_rate
            self.cx_profile.side_b_max_bps = 0

        self.cx_profile.create(endp_type=self.type,
                                side_a=self.sta_list,
                                tos=self.tos,
                                side_b=upstream)

    def start_cx(self):
        self.cx_profile.start_cx()
        time.sleep(3)

    def stop_cx(self):
        for name in self.cx_profile.created_cx.keys():
            print(f"Stopping CX: {name}")
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "ALL",
                "cx_name": name,
                "cx_state": "STOPPED"
            }, debug_=self.debug)
        time.sleep(5)  # Wait for a while to ensure all CXs are stopped

    def cleanup_stations(self):
        logger.info('Cleaning up the stations if exists')
        self.station_profile.cleanup(self.sta_list, delay=1)
        self.wait_until_ports_disappear(sta_list=self.sta_list,
                                        debug_=True)
        logger.info('All stations got removed. Aborting...')

    def stop_start_app(self, DEVICE_SERIAL):
        device_serial = DEVICE_SERIAL.split('.')[-1]
        print(f'adb -s {device_serial} shell am force-stop com.candela.wecan')
        subprocess.run([
            "adb", "-s", device_serial, "shell", "am", "force-stop", 
            "com.candela.wecan"
        ])
        print(f'adb -s {device_serial} shell am start -n com.candela.wecan/com.candela.wecan.StartupActivity --es auto_start 1')
        subprocess.run([
            "adb", "-s", device_serial, "shell", "am", "start","-n", 
            "com.candela.wecan/com.candela.wecan.StartupActivity","--es",
            "auto_start","1"
        ])
        time.sleep(5)

        # adb -s 13301JEC205162 shell am force-stop com.candela.wecan
        # adb -s 13301JEC205162 shell am start -n com.candela.wecan/com.candela.wecan.StartupActivity --es auto_start 1


    def run_hotspot(self):
        resource_ids = [r.strip() for r in self.resources.split(",")]
        self.all_device_details = self.get_data_from_csv(csv_name="hotspot_details.csv", selected_resource_ids=resource_ids)
    
        print(self.all_device_details)
        for itr in range(self.iteration):
            for serial in self.all_device_details:
                print()
                print(f'========================= ITERATION {itr+1} - {serial} =========================')
                print()
                if not self.check_phantom(serial):
                    self.run_remote_toggle(serial)

                    if itr != 0:
                        self.stop_start_app(serial)
                    self.create_clients(self.all_device_details[serial])
                    self.get_rssi_data()

                    upstream_port = self.get_port_data(self.all_device_details[serial]['Resource_Id'])
                    print(f"Upstream port: {upstream_port}")
                    self.create_cx(upstream_port)

                    self.start_cx()
                    self.record_traffic_data(itr, serial)
                    self.stop_cx()
                    
                    self.run_remote_toggle(serial, disable=True)
                    self.clean_cxs()
                    self.cleanup()
                    
            

    def record_traffic_data(self, itr, serial):
        start_time = time.time()
        # self.file_path = "hotspot_traffic_data.csv"
        
        # Open the file in append mode
        with open(self.file_path, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Only write the header row if the file is empty
            if csvfile.tell() == 0:
                writer.writerow(['cx_name', 'Time_Stamp', 'Bps_Rx_A', 'Bps_Rx_B', 'Rx_drop_%A', 'Rx_drop_%B', 'RSSI'])


            start_time = time.time()
            
            # if not hasattr(self, 'traffic_data'):
            #     self.traffic_data = {}

            self.traffic_data.setdefault(itr, {})
            self.traffic_data[itr].setdefault(serial, [])

            while time.time() < start_time + self.duration:
                current_time = time.time()
                dt = datetime.datetime.fromtimestamp(current_time)
                time_string = f"{dt.hour:02}:{dt.minute:02}:{dt.second:02}"

                try:
                    all_cx_data = self.json_get('/cx/all/')
                except Exception as e:
                    print(f"Failtitleed to get CX data: {e}")
                    time.sleep(1)
                    continue

                for cx_name, cx_info in all_cx_data.items():
                    if cx_name not in self.cx_profile.created_cx:
                        continue
                    self.get_rssi_data()
                    rssi = None

                    for sta in self.rssi_data:
                        if sta.split('.')[-1] in cx_name:
                            rssi = self.rssi_data[sta]

                    self.traffic_data[itr][serial].append({
                        'Time_Stamp': time_string,
                        'CX': cx_name,
                        'RSSI': rssi,
                        'Bps_Rx_A': cx_info.get('bps rx a', 0),
                        'Bps_Rx_B': cx_info.get('bps rx b', 0),
                        'Rx_drop_%A': cx_info.get('rx drop % a', 0),
                        'Rx_drop_%B': cx_info.get('rx drop % b', 0)
                    })

                    writer.writerow([cx_name, time_string, cx_info.get('bps rx a', 0), cx_info.get('bps rx b', 0),cx_info.get('rx drop % a', 0), cx_info.get('rx drop % b', 0), rssi])
                time.sleep(1)

    def build_line_plot(self, report_obj):

        logging.info(f"Current working directory: {os.getcwd()}")
        logging.info(f"Report directory: {report_obj.path_date_time}")
        
        timestamp_set = set()
        cx_names = list(self.traffic_data.keys())

        bps_rx_a_dict = {cx: {} for cx in cx_names}
        bps_rx_b_dict = {cx: {} for cx in cx_names}

        for cx, entries in self.traffic_data.items():
            for row in entries:
                if not isinstance(row, dict) or 'Time_Stamp' not in row:
                    continue  # skip malformed rows
                timestamp = row['Time_Stamp']
                timestamp_set.add(timestamp)
                bps_rx_a_dict[cx][timestamp] = round(row['Bps_Rx_A'] / 1_000_000, 3)  # Mbps
                bps_rx_b_dict[cx][timestamp] = round(row['Bps_Rx_B'] / 1_000_000, 3)  # Mbps

        timestamps = sorted(timestamp_set)
        fig = go.Figure()

        # 2. Add lines for each CX
        all_traces = []
        for cx in cx_names:
            y_a = [bps_rx_a_dict[cx].get(ts, 0) for ts in timestamps]
            y_b = [bps_rx_b_dict[cx].get(ts, 0) for ts in timestamps]

            trace_a = go.Scatter(x=timestamps, y=y_a, mode='lines', name=f'{cx} - Rx A')
            trace_b = go.Scatter(x=timestamps, y=y_b, mode='lines', name=f'{cx} - Rx B')
            fig.add_trace(trace_a)
            fig.add_trace(trace_b)
            all_traces.extend([trace_a, trace_b])

        # 3. Dropdown to toggle stations
        dropdown_buttons = [
            {
                "label": "All",
                "method": "update",
                "args": [{"visible": [True] * len(all_traces)}, {"showlegend": True}]
            },
            {
                "label": "None",
                "method": "update",
                "args": [{"visible": [False] * len(all_traces)}, {"showlegend": True}]
            }
        ]

        for i, cx in enumerate(cx_names):
            visibility = [False] * len(all_traces)
            visibility[i * 2] = True  # Rx A
            visibility[i * 2 + 1] = True  # Rx B
            dropdown_buttons.append({
                "label": cx,
                "method": "update",
                "args": [{"visible": visibility}, {"showlegend": True}]
            })

        fig.update_layout(
            title="Traffic per Station (in Mbps)",
            xaxis_title="Time",
            yaxis_title="Traffic (in Mbps)",
            xaxis=dict(tickangle=45,
                       showline=True,
                       linecolor='black',
                       linewidth=2),
            updatemenus=[{
                "buttons": dropdown_buttons,
                "direction": "down",
                "x": 1.05,
                "xanchor": "left",
                "y": 1.2,
                "yanchor": "top"
            }],
            height=600,
            plot_bgcolor="white",
            paper_bgcolor="white"
        )
        os.makedirs(report_obj.path_date_time, exist_ok=True)
            
        # Define paths using absolute paths
        html_path = os.path.abspath(f"{report_obj.path_date_time}/interactive_traffic_graph.html")
        png_path = os.path.abspath(f"{report_obj.path_date_time}/interactive_traffic_graph.png")

        try:
            # Save files directly to report directory
            fig.write_html(html_path, include_plotlyjs="inline")
            fig.write_image(png_path, format="png", width=1200, height=600, scale=2)
            
            # Verify files were created
            if not os.path.exists(png_path):
                logging.error(f"Graph image not created at {png_path}")
                return False
                
            # Tell report object about the file (using relative path)
            report_obj.set_graph_image("interactive_traffic_graph.png")
            return True
            
        except Exception as e:
            logging.error(f"Error saving interactive graph: {str(e)}")
            return False

    def generate_report(self):

        report = lf_report(_output_pdf="hotspot.pdf", _output_html="hotspot.html",
                        _results_dir_name="Hotspot_test")

        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()
        logger.info("path: {}".format(report_path))
        logger.info("path_date_time: {}".format(report_path_date_time))

        # Move hotspot.csv to the report path_date_time directory
        dst_csv = os.path.join(report_path_date_time, 'hotspot_traffic_data.csv')
        if os.path.exists(self.file_path):
            shutil.move(self.file_path, dst_csv)
            logger.info(f"Moved {self.file_path} to {dst_csv}")
        else:
            logger.warning(f"{self.file_path} does not exist, cannot move.")

        report.set_title("Android Hotspot Automation Test")
        report.build_banner()

        # === OBJECTIVE ===
        report.set_obj_html(
            _obj_title="Objective",
            _obj="The objective of the Android Hotspot automation test is to validate the functionality, reliability, and performance of Android devices operating as Soft Access Points (Soft APs)."
                " By automating hotspot enable/disable operations, client association, and traffic generation over multiple iterations,"
                " this test aims to assess the ability of these Soft APs to support concurrent virtual station connections, sustain traffic loads, and maintain stable performance."
        )
        report.build_objective()

        # === INPUT PARAMETERS ===
        security = [v["Security_Type"] for v in self.all_device_details.values()]
        ssids = [v["Hotspot_Name"] for v in self.all_device_details.values()]
        formatted_ssids = [
            f"{v['Hotspot_Name']} ({v['Max_Clients_Supported']})"
            for v in self.all_device_details.values()
        ]

        input_params = {
            "Test name": "Android Hotspot automation test",
            "SSID": ",".join(ssids),
            "Test Duration": f'{self.duration} sec',
            "Test Delay": f'{self.delay} sec',
            "Security": ",".join(security),
            "Number of Iterations": self.iteration,
            "Traffic Direction": self.direction,
            "Download Rate": f'{int(self.side_b_min_rate)//1_000_000 if self.side_b_min_rate else 0} Mbps',
            "Upload Rate": f'{int(self.side_a_min_rate)//1_000_000 if self.side_a_min_rate else 0} Mbps',
            "TOS": self.tos,
            "Maximum Clients for each device": ", ".join(formatted_ssids)
        }
        report.test_setup_table(test_setup_data=input_params, value="Test Configuration")

        # === HOTSPOT ITERATION SUMMARY TABLE ===
        iteration_summary_rows = []

        for itr in sorted(self.traffic_data.keys()):
            for serial in self.traffic_data[itr]:
                device_info = self.all_device_details.get(serial, {})
                device_name = device_info.get("Device_name", "Unknown")
                client_count = int(device_info.get("Max_Clients_Supported", 0))

                # Extract traffic samples
                samples = self.traffic_data[itr][serial]

                # Determine Hotspot Status
                hotspot_status = "Enabled" if samples else "Disabled"

                # Check if traffic was actually present
                traffic_present = any(
                    (entry.get("Bps_Rx_A", 0) > 0 or entry.get("Bps_Rx_B", 0) > 0)
                    for entry in samples
                )
                traffic_status = "Executed" if traffic_present else "No Traffic"

                # Decide overall status (example logic: hotspot ON and traffic > 0)
                overall_status = "PASS" if hotspot_status == "Enabled" and traffic_present else "FAIL"

                iteration_summary_rows.append({
                    "Iteration": itr + 1,
                    "Soft AP (SAP) Device": device_name,
                    "Hotspot Status": hotspot_status,
                    "Number of Clients Connected": client_count,
                    "Traffic Status": traffic_status,
                    "Overall Status": overall_status
                })

        if iteration_summary_rows:
            df_summary = pd.DataFrame(iteration_summary_rows)
            report.set_table_title("<b>Hotspot Iteration Summary</b>")
            report.build_table_title()
            report.set_table_dataframe(df_summary)
            report.build_table()


        for itr in self.traffic_data:
            for serial in self.traffic_data[itr]:
                samples = self.traffic_data[itr][serial]
                if not samples:
                    continue

                device_info = self.all_device_details[serial]
                device_name = device_info["Device_name"]
                ssid = device_info["Hotspot_Name"]
                traffic_dir = self.direction.capitalize()

                # === TOTAL REAL-TIME LINE PLOT ===
                throughput_by_time_a = {}
                throughput_by_time_b = {}
                timestamp_set = set()

                for s in samples:
                    ts = s["Time_Stamp"]
                    timestamp_set.add(ts)
                    throughput_by_time_a.setdefault(ts, 0)
                    throughput_by_time_b.setdefault(ts, 0)
                    throughput_by_time_a[ts] += s.get("Bps_Rx_A", 0)
                    throughput_by_time_b[ts] += s.get("Bps_Rx_B", 0)

                timestamps = sorted(timestamp_set)
                line_mbps_a = [round(throughput_by_time_a[ts] / 1e6, 3) for ts in timestamps]
                line_mbps_b = [round(throughput_by_time_b[ts] / 1e6, 3) for ts in timestamps]

                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(x=timestamps, y=line_mbps_a, mode='lines', name='Download - Rx A'))
                fig_line.add_trace(go.Scatter(x=timestamps, y=line_mbps_b, mode='lines', name='Upload - Rx B'))

                fig_line.update_layout(
                    title={
                        'text': "Overall Real Time Throughput - {device_name}",
                        'x': 0.5,
                        'xanchor': 'center'
                    },
                    xaxis_title="Time",
                    yaxis_title="Throughput (Mbps)",
                    height=500,
                    plot_bgcolor="white",
                    paper_bgcolor="white"
                )

                summary_png_path = os.path.join(report.get_path_date_time(), f"summary_throughput_{serial}_itr{itr+1}.png")
                fig_line.write_image(summary_png_path, width=1200, height=600, scale=2)

                # report.set_table_title(f"<b>(Iteration {itr + 1}) - Per-Client Throughput Summary ({traffic_dir})</b>")
                if os.path.exists(summary_png_path):
                    report.set_table_title(f"<b>Iteration {itr + 1}: Overall Real Time Throughput Graph [{device_name}] - {traffic_dir}</b>")
                    report.build_table_title()
                    report.set_graph_image(os.path.basename(summary_png_path))
                    report.build_graph()

                # === PER CLIENT AVG BAR PLOT & TABLE ===
                cx_map = {}
                for s in samples:
                    cx_map.setdefault(s["CX"], []).append(s)

                client_names, avg_rx_a, avg_rx_b, drop_a, drop_b, avg_rssi = [], [], [], [], [], []

                for cx, cx_samples in cx_map.items():
                    rx_a_vals = [e.get("Bps_Rx_A", 0) for e in cx_samples if e.get("Bps_Rx_A", 0) > 0]
                    rx_b_vals = [e.get("Bps_Rx_B", 0) for e in cx_samples if e.get("Bps_Rx_B", 0) > 0]
                    drop_vals_a = [e.get("Rx_drop_%A", 0) for e in cx_samples]
                    drop_vals_b = [e.get("Rx_drop_%B", 0) for e in cx_samples]

                    rssi_vals = []
                    for e in cx_samples:
                        try:
                            rssi_val = int(e.get("RSSI", 'NA'))
                        except ValueError:
                            rssi_val = 'NA'
                        rssi_vals.append(rssi_val)
        
                    client_names.append(cx)
                    avg_rx_a.append(round(np.mean(rx_a_vals) / 1e6, 3))
                    avg_rx_b.append(round(np.mean(rx_b_vals) / 1e6, 3))
                    drop_a.append(round(np.mean(drop_vals_a), 2))
                    drop_b.append(round(np.mean(drop_vals_b), 2))
                    avg_rssi.append(int(round(np.mean(rssi_vals), 0)))

                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=client_names, y=avg_rx_a, name='Download (Rx A)'))
                fig_bar.add_trace(go.Bar(x=client_names, y=avg_rx_b, name='Upload (Rx B)'))

                fig_bar.update_layout(
                    barmode='group',
                    title={
                        'text':f"Average Throughput per Client - {device_name}" ,
                        'x': 0.5,
                        'xanchor': 'center'
                    },
                    xaxis_title="Client Name",
                    yaxis_title="Throughput (Mbps)",
                    height=500,
                    plot_bgcolor="white"
                )

                bar_png_path = os.path.join(report.get_path_date_time(), f"avg_throughput_bar_{serial}_itr{itr+1}.png")
                fig_bar.write_image(bar_png_path, width=1000, height=500, scale=2)

                if os.path.exists(bar_png_path):
                    report.set_table_title(f"<b>Iteration {itr + 1}: Per Client Average Throughput [{device_name}] - {traffic_dir}</b>")
                    report.build_table_title()
                    report.set_graph_image(os.path.basename(bar_png_path))
                    report.build_graph()

                df = pd.DataFrame({
                    "Client Name": client_names,
                    "SSID": [ssid] * len(client_names),
                    "Avg RSSI (dBm)": avg_rssi,
                    "Upload Throughput (Mbps)": avg_rx_a,
                    "Download Throughput (Mbps)": avg_rx_b,
                    "Rx Drop A (%)": drop_a,
                    "Rx Drop B (%)": drop_b
                })


                report.build_table_title()
                report.set_table_dataframe(df)
                report.build_table()

        report.build_footer()
        report.write_html()
        report.write_pdf(_orientation="Landscape")


def main():
    parser = argparse.ArgumentParser(
        prog='lf_interop_hotspot.py',
        formatter_class=argparse.RawTextHelpFormatter)

    # required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # optional arguments
    optional.add_argument('--mgr',
                           type=str,
                           help='hostname where LANforge GUI is running',
                           default='localhost')

    optional.add_argument('--iteration',
                           type=int,
                           default=1,
                           help='Mention number of iterations for the test.',
                          )

    optional.add_argument('--result_dir',
                           type=str,
                           default='results',
                           help='Directory to store test results')

    optional.add_argument('--delay',
                           type=int,
                           default=10,
                           help='dealy in b/w iteration gap in seconds')

    optional.add_argument('--duration',
                           type=int,
                           default=60,
                           help='duration to run traffic in seconds')

    optional.add_argument('--resources',
                           type=str,
                           help='Mention resources')

    optional.add_argument('--tos',
                           type=str,
                           choices=['BE','BK','VI','VO'],
                           default='BE',
                           help='Mention Type of service ')

    optional.add_argument('--direction',
                          choices=['download', 'upload', 'bidirectional'],
                          default='download',
                          help='Type of traffic direction to perform ex: (download, upload, bidirectional)')

    optional.add_argument('--side_a_min_rate', help='--upload traffic load per connection (upload rate)', default='0')

    optional.add_argument('--side_b_min_rate', help='--download traffic load per connection (download rate)', default='0')

    optional.add_argument('--radio',
                          help='Mention radio by default wiphy0')

    optional.add_argument('--cleanup',
                           action='store_true',
                           help='cleans up generic cx after completion of the test')
    
    optional.add_argument('--type',
                            type=str,
                            choices=['lf_tcp','lf_udp'],
                            help='Type of traffic to run',
                            default='lf_tcp')

    parser.add_argument('--help_summary', default=None, action="store_true", help='Show summary of what this script does')

    args = parser.parse_args()

    if args.help_summary:
        exit(0)

    hotspot_obj = Hotspot(manager_ip=args.mgr,
                            resources=args.resources,
                            iteration=args.iteration,
                            duration=args.duration,
                            delay=args.delay,
                            radio=args.radio,
                            tos=args.tos,
                            type=args.type,
                            side_a_min_rate=args.side_a_min_rate,
                            side_b_min_rate=args.side_b_min_rate,
                            direction=args.direction)

    hotspot_obj.run_hotspot()

    hotspot_obj.generate_report()

if __name__ == "__main__":
    main()
