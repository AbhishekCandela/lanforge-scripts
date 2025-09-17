#!/usr/bin/env python3

"""
NAME: qc_test.py

PURPOSE:
          ->  This script creates variable number of stations with individual cross-connects and endpoints.
              Stations are set to UP state, but cross-connections remain stopped.

          ->  This script support Batch-create Functionality.

EXAMPLE:
        Default configuration:
            Endpoint A: List of stations (default: 2 stations, unless specified with --num_stations)
            Endpoint B: eth1

        * Creating specified number of station names and Layer-3 CX :

            ./qc_test.py --mgr localhost --num_stations 5 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * Creating stations with specified start ID (--num_template) and Layer-3 CX :

            ./qc_test.py --mgr localhost --number_template 007 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * Creating stations with specified names and Layer-3 CX :

            ./qc_test.py --mgr localhost --station_list sta00,sta01 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * For creating stations and layer-3 cx creation on particular specified AP mac & mode:

            ./qc_test.py --mgr localhost --radio wiphy0 --ssid SSID --password Password@123 --security wpa2 --ap "00:0e:8e:78:e1:76"
            --mode 13

        * For creating specified number of stations and layer-3 cx creation (Customise the traffic and upstream port):

            ./qc_test.py --mgr localhost --station_list sta00  --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
             --upstream_port eth2 --min_rate_a 6200000 --min_rate_b 6200000

        * For Batch-Create :

            ./qc_test.py --mgr 192.168.200.93 --endp_a 1.1.eth2 --endp_b 1.1.sta0002 --min_rate_a 6200000 --min_rate_b 6200000
            --batch_create --batch_quantity 8 --endp_a_increment 0 --endp_b_increment 0 --min_ip_port_a 1000 --min_ip_port_b 2000
            --ip_port_increment_a 1 --ip_port_increment_b 1 --multi_conn_a 1 --multi_conn_b 1

      Generic command layout:

        python3 ./qc_test.py
            --upstream_port eth1
            --radio wiphy0
            --num_stations 32
            --security {open|wep|wpa|wpa2|wpa3}
            --ssid netgear
            --password admin123
            --min_rate_a 1000
            --min_rate_b 1000
            --ap "00:0e:8e:78:e1:76"
            --number_template 0000
            --mode   1
                {"auto"   : "0",
                "a"      : "1",
                "b"      : "2",
                "g"      : "3",
                "abg"    : "4",
                "abgn"   : "5",
                "bgn"    : "6",
                "bg"     : "7",
                "abgnAC" : "8",
                "anAC"   : "9",
                "an"     : "10",
                "bgnAC"  : "11",
                "abgnAX" : "12",
                "bgnAX"  : "13",
            --debug

SCRIPT_CLASSIFICATION:  Creation

SCRIPT_CATEGORIES:   Functional

NOTES:
        Create Layer-3 Cross Connection Using LANforge JSON API : https://www.candelatech.com/cookbook.php?vol=fire&book=scripted+layer-3+test
        Written by Candela Technologies Inc.

        * Supports creating of stations and creates Layer-3 cross-connection with the endpoint_A as stations created and endpoint_B as upstream port.
        * Supports regression testing for QA

STATUS: Functional

VERIFIED_ON:   27-JUN-2023,
             Build Version:  5.4.6
             Kernel Version: 6.2.14+

LICENSE:
          Free to distribute and modify. LANforge systems must be licensed.
          Copyright 2023 Candela Technologies Inc

INCLUDE_IN_README: False
"""
import datetime
import sys
import os
import importlib
import argparse
import logging
import time
import shutil
import numpy as np
import csv
import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

LANforge = importlib.import_module("py-json.LANforge")
lfcli_base = importlib.import_module("py-json.LANforge.lfcli_base")
LFCliBase = lfcli_base.LFCliBase
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
from lf_report import lf_report
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")


class CreateL3(Realm):
    def __init__(
            self,
            ssid,
            security,
            password,
            sta_list,
            name_prefix,
            upstream,
            radio="1.1.wiphy0",
            host="localhost",
            port=8080,
            mode=0,
            ap=None,
            tos='BE',
            num_sta=1,
            duration='5m',
            side_a_min_rate=56,
            side_a_max_rate=0,
            side_b_min_rate=56,
            side_b_max_rate=0,
            number_template="00000",
            use_ht160=False,
            _debug_on=False,
            _exit_on_error=False,
            _exit_on_fail=False,
            _endp_a=None,
            _endp_b=None,
            _batch_create=False,
            _quantity=None,
            _endp_a_increment=None,
            _endp_b_increment=None,
            _ip_port_increment_a=None,
            _ip_port_increment_b=None,
            _min_ip_port_a=None,
            _min_ip_port_b=None,
            _multi_conn_a=None,
            _multi_conn_b=None):
        super().__init__(host, port)
        self.upstream = upstream
        self.host = host
        self.port = port
        self.ssid = ssid
        self.sta_list = sta_list
        self.security = security
        self.password = password
        self.radio = radio
        self.mode = mode
        self.ap = ap
        self.number_template = number_template
        self.num_stations = num_sta
        self.duration = duration
        self.debug = _debug_on
        self.name_prefix = name_prefix
        self.endp_a = _endp_a
        self.endp_b = _endp_b
        self.station_profile = self.new_station_profile()
        self.cx_profile = self.new_l3_cx_profile()
        self.station_profile.lfclient_url = self.lfclient_url
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.password
        self.station_profile.security = self.security
        self.station_profile.number_template_ = self.number_template
        self.station_profile.debug = self.debug
        self.station_profile.use_ht160 = use_ht160
        if self.station_profile.use_ht160:
            self.station_profile.mode = 9
        self.station_profile.mode = mode
        if self.ap is not None:
            self.station_profile.set_command_param("add_sta", "ap", self.ap)
        # self.station_list= LFUtils.portNameSeries(prefix_="sta", start_id_=0,
        # end_id_=2, padding_number_=10000, radio='wiphy0') #Make radio a user
        # defined variable from terminal.
        self.tos = tos
        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.name_prefix = self.name_prefix
        self.cx_profile.side_a_min_bps = side_a_min_rate
        self.cx_profile.side_a_max_bps = side_a_max_rate
        self.cx_profile.side_b_min_bps = side_b_min_rate
        self.cx_profile.side_b_max_bps = side_b_max_rate
        self.cx_profile.mconn_A = _multi_conn_a
        self.cx_profile.mconn_B = _multi_conn_b
        # for batch creation window automation attributes
        self.batch_create = _batch_create
        self.batch_quantity = _quantity
        self.port_increment_a = _endp_a_increment
        self.port_increment_b = _endp_b_increment
        self.ip_port_increment_a = _ip_port_increment_a
        self.ip_port_increment_b = _ip_port_increment_b
        self.min_ip_port_a = _min_ip_port_a
        self.min_ip_port_b = _min_ip_port_b

    def pre_cleanup(self):
        logger.info('pre_cleanup')
        self.cx_profile.cleanup_prefix()
        for sta in self.sta_list:
            self.rm_port(sta, check_exists=True, debug_=False)

    def build(self):
        if self.batch_create:  # Batch Create Functionality
            if self.cx_profile.create(endp_type="lf_udp",
                                      side_a=self.endp_a,
                                      side_b=self.endp_b,
                                      sleep_time=0,
                                      ip_port_a=self.min_ip_port_a,
                                      ip_port_b=self.min_ip_port_b,
                                      batch_quantity=self.batch_quantity,
                                      port_increment_a=self.port_increment_a,
                                      port_increment_b=self.port_increment_b,
                                      ip_port_increment_a=self.ip_port_increment_a,
                                      ip_port_increment_b=self.ip_port_increment_b
                                      ):
                self._pass("Cross-connect build finished")
            else:
                self._fail("Cross-connect build did not succeed.")
        else:  # Creating Stations along with Cross-connects
            self.station_profile.use_security(security_type=self.security,
                                              ssid=self.ssid,
                                              passwd=self.password)
            self.station_profile.set_number_template(self.number_template)
            logger.info("Creating stations")
            self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
            self.station_profile.set_command_param(
                "set_port", "report_timer", 1500)
            self.station_profile.set_command_flag("set_port", "rpt_timer", 1)

            sta_timeout = 300
            # sta_timeout=3 # expect this to fail

            if self.station_profile.create(radio=self.radio,
                                             sta_names_=self.sta_list,
                                             debug=self.debug,
                                             timeout=sta_timeout):
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

            logger.info("Station creation succeeded.")
            self.ports_up()
            cx_timeout = 300
            # cx_timeout=0 # expect this to fail
            if len(self.sta_list) % 2 != 0:
                logger.error("L3 endpoints need even number of stations to be created to create traffic between side A and side B")
                exit(1)
            else:
                for i in range(0, len(self.sta_list), 2):
                    rv =  self.cx_profile.create(endp_type="lf_udp",
                                                side_a=[self.sta_list[i]],
                                                side_b=self.sta_list[i+1],
                                                sleep_time=0,
                                                tos=self.tos,
                                                timeout=cx_timeout)
                    if rv:
                        logger.info(f"CX created between {self.sta_list[i]} and {self.sta_list[i+1]} .")
                    else:
                        logger.error("failed: could not create all cx/endpoints.")
                        exit(1)
                            

    def ports_up(self):
        logger.info("Bringing up stations")
        self.admin_up(self.upstream)
        for sta in self.station_profile.station_names:
            logger.info("Bringing up station %s" % sta)
            self.admin_up(sta)

    def ports_down(self):
        logger.info("Bringing down stations")
        # self.admin_up(self.upstream)
        for sta in self.station_profile.station_names:
            logger.info("Bringing down station %s" % sta)
            self.admin_down(sta)

    def start_cx(self):
        for cx_name in self.cx_profile.created_cx.keys():
            print("cx-name: {cx_name}".format(cx_name=cx_name))
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "default_tm",
                "cx_name": cx_name,
                "cx_state": "RUNNING"
            }, debug_=self.debug)

    def stop_cx(self):
        for name in self.cx_profile.created_cx.keys():
            logger.info(f"Stopping CX: {name}")
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "ALL",
                "cx_name": name,
                "cx_state": "STOPPED"
            }, debug_=self.debug)
        time.sleep(5)  # Wait for a while to ensure all CXs are stopped

    def cleanup(self):
        logger.info("Clean up stations")
        self.cx_profile.cleanup_prefix()
        for sta in self.sta_list:
            self.rm_port(sta, check_exists=True, debug_=False)

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


    def record_traffic_data(self):
        start_time = time.time()
        self.file_path = "traffic_data.csv"
        
        # Open the file in append mode
        with open(self.file_path, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Only write the header row if the file is empty
            if csvfile.tell() == 0:
                writer.writerow(['cx_name', 'Time_Stamp', 'Bps_Rx_A', 'Bps_Rx_B', 'Rx_drop_%A', 'Rx_drop_%B', 'RSSI'])

            start_time = time.time()
            
            if not hasattr(self, 'traffic_data'):
                self.traffic_data = {}

            # self.traffic_data.setdefault(iteration, [])

            while time.time() < start_time + self.duration:
                current_time = time.time()
                dt = datetime.datetime.fromtimestamp(current_time)
                time_string = f"{dt.hour:02}:{dt.minute:02}:{dt.second:02}"

                try:
                    all_cx_data = self.json_get('/cx/all/')
                except Exception as e:
                    print(f"Failed to get CX data: {e}")
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

                    self.traffic_data.append({
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

    def run_test(self, test_duration=60, stop_interval=30, stop_delay=5):
        start_time = time.time()
        end_time = start_time + test_duration
        next_interval = start_time + stop_interval
        self.start_cx()

        #start recording Traffic
        self.record_traffic_data()

        while time.time() < end_time:
            current_time = time.time()
            if current_time >= next_interval:
                logger.info(f"Interval reached at {int(current_time - start_time)}s: sleeping for {stop_delay}s")
                self.stop_cx()
                time.sleep(stop_delay)
                self.start_cx()
                next_interval += stop_interval

            time.sleep(0.2)
        self.stop_cx()
        logger.info("Test completed.")


    def generate_report(self,test_duration, stop_interval, stop_delay):

        report = lf_report(_output_pdf="Group_traffic.pdf", _output_html="Group_traffic.html",
                        _results_dir_name="Group_traffic_test")

        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()
        logger.info("path: {}".format(report_path))
        logger.info("path_date_time: {}".format(report_path_date_time))

        # Move Group_traffic.csv to the report path_date_time directory
        dst_csv = os.path.join(report_path_date_time, 'Group_traffic_traffic_data.csv')
        try:
            if os.path.exists(self.file_path):
                shutil.move(self.file_path, dst_csv)
                logger.info(f"Moved {self.file_path} to {dst_csv}")
            else:
                logger.warning(f"{self.file_path} does not exist, cannot move.")
        except:
            pass
        report.set_title("Android Group traffic Automation Test")
        report.build_banner()

        # === OBJECTIVE ===
        report.set_obj_html(
            _obj_title="Objective",
            _obj="The objective of the Android Group traffic automation test is to validate the functionality, reliability, and performance of Android devices operating as Soft Access Points (Soft APs)."
                " By automating Group_traffic enable/disable operations, client association, and traffic generation over multiple iterations,"
                " this test aims to assess the ability of these Soft APs to support concurrent virtual station connections, sustain traffic loads, and maintain stable performance."
        )
        report.build_objective()

        # === INPUT PARAMETERS ===

        input_params = {
            "Test name": "Android Group_traffic automation test",
            "SSID": self.ssid,
            "Test Duration": f'{test_duration} sec',
            "Stop Interval": f'{stop_interval} sec',
            "Stop Delay": f'{stop_delay} sec',
            "Security": self.security,
            # "Number of Iterations": iteration,
            # "Traffic Direction": self.direction,
            "Download Rate": f'{int(self.cx_profile.side_b_min_bps)//1_000_000 } Mbps',
            "Upload Rate": f'{int(self.cx_profile.side_a_min_bps)//1_000_000 } Mbps',
            "TOS": self.tos,
            "Number of Stations": self.num_stations
        }
        report.test_setup_table(test_setup_data=input_params, value="Test Configuration")


        for itr in self.traffic_data:
            samples = self.traffic_data[itr]
            if not samples:
                continue

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
                    'text': f"Overall Real Time Throughput",
                    'x': 0.5,
                    'xanchor': 'center'
                },
                xaxis_title="Time",
                yaxis_title="Throughput (Mbps)",
                height=500,
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgrey',
                    griddash='dot'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgrey',
                    griddash='dot'
                )
            )

            summary_png_path = os.path.join(report.get_path_date_time(), f"summary_throughput_itr{itr+1}.png")
            fig_line.write_image(summary_png_path, width=1200, height=600, scale=2)

            # report.set_table_title(f"<b>(Iteration {itr + 1}) - Per-Client Throughput Summary ({traffic_dir})</b>")
            if os.path.exists(summary_png_path):
                report.set_table_title(f"<b>Iteration {itr + 1}: Overall Real Time Throughput Graph </b>")
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
                    rssi_val = e.get("RSSI")
                    if rssi_val not in [None, '', 'NA']:
                        rssi_vals.append(int(rssi_val))
    
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
                    'text':f"Average Throughput per Client " ,
                    'x': 0.5,
                    'xanchor': 'center'
                },
                xaxis_title="Client Name",
                yaxis_title="Throughput (Mbps)",
                height=500,
                plot_bgcolor="white",
                xaxis=dict(
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgrey',
                    griddash='dot'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgrey',
                    griddash='dot'
                )
            )

            bar_png_path = os.path.join(report.get_path_date_time(), f"avg_throughput_bar_itr{itr+1}.png")
            fig_bar.write_image(bar_png_path, width=1000, height=500, scale=2)

            if os.path.exists(bar_png_path):
                report.set_table_title(f"<b>Iteration {itr + 1}: Per Client Average Throughput </b>")
                report.build_table_title()
                report.set_graph_image(os.path.basename(bar_png_path))
                report.build_graph()

            df = pd.DataFrame({
                "Client Name": client_names,
                "SSID": [self.ssid] * len(client_names),
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

def parse_time(time_str):
    if time_str.endswith(('s', 'S')):
        return int(time_str[:-1])
    elif time_str.endswith(('m', 'M')):
        return int(time_str[:-1]) * 60
    elif time_str.endswith(('h', 'H')):
        return int(time_str[:-1]) * 3600
    else:
        return int(time_str)

def main():
    help_summary = '''\
    This script creates a variable number of stations with individual cross-connects and endpoints.
    The stations are initially set to the UP state, but the cross-connections are kept in a stopped state. It also
    supports batch creation functionality, making it convenient to generate multiple stations at once.

    The script will creates stations & CX only, will not run/start traffic and will not generate any report.
        '''
    parser = LFCliBase.create_basic_argparse(
        prog='qc_test.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            Create stations to test connection and traffic on VAPs of varying security types (WEP, WPA, WPA2, WPA3, Open)
            ''',

        description='''\
"""
NAME: qc_test.py

PURPOSE:
          ->  This script creates variable number of stations with individual cross-connects and endpoints.
              Stations are set to UP state, but cross-connections remain stopped.

          ->  This script support Batch-create Functionality.

EXAMPLE:
        Default configuration:
            Endpoint A: List of stations (default: 2 stations, unless specified with --num_stations)
            Endpoint B: eth1

        * Creating specified number of station names and Layer-3 CX :

            ./qc_test.py --mgr localhost --num_stations 5 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * Creating stations with specified start ID (--num_template) and Layer-3 CX :

            ./qc_test.py --mgr localhost --number_template 007 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * Creating stations with specified names and Layer-3 CX :

            ./qc_test.py --mgr localhost --station_list sta00,sta01 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * For creating stations and layer-3 cx creation on particular specified AP mac & mode:

            ./qc_test.py --mgr localhost --radio wiphy0 --ssid SSID --password Password@123 --security wpa2 --ap "00:0e:8e:78:e1:76"
            --mode 13

        * For creating specified number of stations and layer-3 cx creation (Customise the traffic and upstream port):

            ./qc_test.py --mgr localhost --station_list sta00  --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
             --upstream_port eth2 --min_rate_a 6200000 --min_rate_b 6200000

        * For Batch-Create :

            ./qc_test.py --mgr 192.168.200.93 --endp_a 1.1.eth2 --endp_b 1.1.sta0002 --min_rate_a 6200000 --min_rate_b 6200000
            --batch_create --batch_quantity 8 --endp_a_increment 0 --endp_b_increment 0 --min_ip_port_a 1000 --min_ip_port_b 2000
            --ip_port_increment_a 1 --ip_port_increment_b 1 --multi_conn_a 1 --multi_conn_b 1

      Generic command layout:

        python3 ./qc_test.py
            --upstream_port eth1
            --radio wiphy0
            --num_stations 32
            --security {open|wep|wpa|wpa2|wpa3}
            --ssid netgear
            --password admin123
            --min_rate_a 1000
            --min_rate_b 1000
            --ap "00:0e:8e:78:e1:76"
            --number_template 0000
            --mode   1
                {"auto"   : "0",
                "a"      : "1",
                "b"      : "2",
                "g"      : "3",
                "abg"    : "4",
                "abgn"   : "5",
                "bgn"    : "6",
                "bg"     : "7",
                "abgnAC" : "8",
                "anAC"   : "9",
                "an"     : "10",
                "bgnAC"  : "11",
                "abgnAX" : "12",
                "bgnAX"  : "13",
            --debug

SCRIPT_CLASSIFICATION:  Creation

SCRIPT_CATEGORIES:   Functional

NOTES:
        Create Layer-3 Cross Connection Using LANforge JSON API : https://www.candelatech.com/cookbook.php?vol=fire&book=scripted+layer-3+test
        Written by Candela Technologies Inc.

        * Supports creating of stations and creates Layer-3 cross-connection with the endpoint_A as stations created and endpoint_B as upstream port.
        * Supports regression testing for QA

STATUS: Functional

VERIFIED_ON:   27-JUN-2023,
             Build Version:  5.4.6
             Kernel Version: 6.2.14+

LICENSE:
          Free to distribute and modify. LANforge systems must be licensed.
          Copyright 2023 Candela Technologies Inc

INCLUDE_IN_README: False

''')

    parser.add_argument(
        '--min_rate_a',
        type=int,
        help='--min_rate_a bps rate minimum for side_a',
        default=10000000)
    parser.add_argument(
        '--min_rate_b',
        type=int,
        help='--min_rate_b bps rate minimum for side_b',
        default=10000000)
    parser.add_argument(
        '--mode', help='Used to force mode of stations')
    parser.add_argument(
        '--ap', help='Used to force a connection to a particular AP')
    parser.add_argument(
        '--number_template',
        help='Start the station numbering with a particular number. Default is 0000',
        default=0000)
    parser.add_argument(
        '--station_list',
        help='Optional: User defined station names, can be a comma or space separated list',
        nargs='+',
        default=None)
    # For batch_create
    parser.add_argument('--batch_create', help='To enable batch create functionality', action='store_true')
    parser.add_argument('--batch_quantity', help='No of cx endpoints to batch-create', default=1)
    parser.add_argument('--endp_a', help='--endp_a station list', default=[], action="append")
    parser.add_argument('--endp_b', help='--upstream port', default="eth2")
    parser.add_argument('--multi_conn_a', help='Modify multi connection endpoint-a for cx', default=0, type=int)
    parser.add_argument('--multi_conn_b', help='Modify multi connection endpoint-b for cx', default=0, type=int)
    parser.add_argument('--min_ip_port_a', help='Min ip port range for endp-a', default=-1)
    parser.add_argument('--min_ip_port_b', help='Min ip port range for endp-b', default=-1)
    parser.add_argument('--endp_a_increment', help='End point - A port increment', default=0)
    parser.add_argument('--endp_b_increment', help='End point - B port increment', default=0)
    parser.add_argument('--ip_port_increment_a', help='Ip port increment for endp-a', default=1)
    parser.add_argument('--ip_port_increment_b', help='Ip port increment for endp-b', default=1)
    parser.add_argument('--test_duration', help='Duration of test', type=str, default="3m")
    parser.add_argument('--stop_interval', help='Duration to stop test intermittently', default="1m")
    parser.add_argument('--stop_delay', help='Duration to stop test intermittently', default="30s")
    parser.add_argument('--tos', help='Mention TOS',choices=["BE","BK","VI","VO"], default="BE")
    parser.add_argument('--iterations', help='Mention Number of iterations', default=1, type=int)
    parser.add_argument('--resource_ids', help='Comma-separated list of Resource IDs to use from CSV', type=str, required=True)

    #parser.add_argument('--no_cleanup', help="pass to avoid pre clean up of existing stations and cross connections", default=None)

    args = parser.parse_args()

    test_duration = parse_time(args.test_duration)
    stop_interval = parse_time(args.stop_interval)
    stop_delay = parse_time(args.stop_delay)

    resource_ids = [r.strip() for r in args.resource_ids.split(',')]
    print(resource_ids)
    hotspot_df = pd.read_csv("hotspot_details.csv")
    print(hotspot_df)
    matched_rows = hotspot_df[hotspot_df['Resource_Id'].astype(str).isin(resource_ids)]

    if matched_rows.empty:
        print("No matching Resource_Id found.")
        return

    all_traffic_data = {}

    for idx, row in matched_rows.iterrows():
        ssid = row['Hotspot_Name']
        passwd = row['Hotspot_Password']
        security = row['Security_Type']
        dev_name = row['Device_name']
        resource_id = row['Resource_Id']

        station_list = LFUtils.portNameSeries(
            prefix_="sta", start_id_=1000 + idx * 10, end_id_=1000 + idx * 10 + 1,
            padding_number_=10000, radio=args.radio)

        qc_test = CreateL3(
            host=args.mgr, port=args.mgr_port, number_template=str(args.number_template),
            sta_list=station_list, name_prefix=f"{dev_name}_",
            upstream=args.upstream_port, ssid=ssid, password=passwd, radio=args.radio,
            security=security, side_a_min_rate=args.min_rate_a, side_b_min_rate=args.min_rate_b,
            mode=args.mode, ap=args.ap, _debug_on=args.debug, duration=test_duration,
            _batch_create=args.batch_create, _endp_a=args.endp_a, _endp_b=args.endp_b,
            _quantity=args.batch_quantity, _endp_a_increment=args.endp_a_increment,
            _endp_b_increment=args.endp_b_increment, _ip_port_increment_a=args.ip_port_increment_a,
            _ip_port_increment_b=args.ip_port_increment_b, _min_ip_port_a=args.min_ip_port_a,
            _min_ip_port_b=args.min_ip_port_b, tos=args.tos, num_sta=len(station_list),
            _multi_conn_a=args.multi_conn_a, _multi_conn_b=args.multi_conn_b
        )

        if not args.no_cleanup:
            qc_test.pre_cleanup()

        qc_test.build()
        qc_test.run_test(test_duration=test_duration,
                            stop_interval=stop_interval,
                            stop_delay=stop_delay,
                            )

        if hasattr(qc_test, 'traffic_data'):
            # all_traffic_data.setdefault(itr, [])
            for tsample in qc_test.traffic_data:
                tsample['Resource_Id'] = resource_id
                tsample['Device_Name'] = dev_name
                # all_traffic_data[itr].append(tsample)

    qc_test.generate_report(test_duration=test_duration,
                             stop_interval=stop_interval,
                             stop_delay=stop_delay,
                             iteration=args.iterations)

if __name__ == "__main__":
    main()