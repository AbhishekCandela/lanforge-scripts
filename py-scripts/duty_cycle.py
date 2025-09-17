#!/usr/bin/env python3

import sys
import os
import logging
import importlib
import argparse
import datetime
import time
from datetime import datetime
import pandas as pd
import paramiko
import random
from dateutil import parser
import json
import shutil
import subprocess
import pyshark
if sys.version_info[0] != 3:
    logging.critical("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
sniff_radio = importlib.import_module("py-scripts.lf_sniff_radio")
sta_connect = importlib.import_module("py-scripts.sta_connect2")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
lf_clean = importlib.import_module("py-scripts.lf_cleanup")
cv_test_reports = importlib.import_module("py-json.cv_test_reports")
lf_report = cv_test_reports.lanforge_reports
lf_report_pdf = importlib.import_module("py-scripts.lf_report")
lf_pcap = importlib.import_module("py-scripts.lf_pcap")
lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_modify_radio = importlib.import_module("py-scripts.lf_modify_radio")
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

logger = logging.getLogger(__name__)
class DfsTest(Realm):
    def __init__(self,
                 testname=None,
                 starttime=None,
                 ui_report_dir=None,
                 host=None,
                 port=None,
                 ssid=None,
                 passwd=None,
                 security=None,
                 radio=None,
                 upstream=None,
                 channel=None,
                 sniff_radio=None,
                 static=None,
                 static_ip=None,
                 ip_mask=None,
                 gateway_ip=None,
                 time_int=None,
                 ssh_password=None,
                 ssh_username=None,
                 traffic_type=None,
                 bandwidth=None,
                 ap_name=None,
                 side_a_min_rate=None,
                 side_a_max_rate=None,
                 side_b_min_rate=None,
                 side_b_max_rate=None,
                 side_a_min_pdu=None,
                 side_b_min_pdu=None,
                 if_gain=None,
                 sniff_duration=None
                 ):
        super().__init__(lfclient_host=host,
                         lfclient_port=port)
        self.testname = testname
        self.starttime = starttime
        self.ui_report_dir = ui_report_dir
        self.host = host
        self.port = port
        self.ssid = ssid
        self.passwd = passwd
        self.security = security
        self.radio = radio
        self.upstream = upstream
        self.channel = channel
        self.sniff_radio = sniff_radio
        self.static = static
        self.static_ip = static_ip
        self.ip_mask = ip_mask
        self.gateway_ip = gateway_ip
        self.time_int = time_int
        self.ssh_password = ssh_password
        self.ssh_username = ssh_username
        self.bandwidth = bandwidth
        self.traffic_type = traffic_type
        self.ap_name = ap_name
        self.pcap_name = None
        self.pcap_obj_2 = None
        self.staConnect = sta_connect.StaConnect2(self.host, self.port, outfile="staconnect2.csv")
        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.pcap_obj = lf_pcap.LfPcap()
        self.cx_profile = self.new_l3_cx_profile()  # create CX profile object
        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.side_a_min_bps = side_a_min_rate
        self.cx_profile.side_a_max_bps = side_a_max_rate
        self.cx_profile.side_b_min_bps = side_b_min_rate
        self.cx_profile.side_b_max_bps = side_b_max_rate
        self.cx_profile.side_a_min_pdu = side_a_min_pdu
        self.cx_profile.side_b_min_pdu = side_b_min_pdu
        self.if_gain = if_gain
        self.sniff_duration = sniff_duration
        self.bandwidth = bandwidth
        logging.basicConfig(filename='dpt.log', filemode='w', level=logging.INFO, force=True)

    def create_webui_logs(self):
        if (self.starttime is not None and self.testname is not None):
            result = {
                'starttime': self.starttime,
                'status': 'Aborted'
            }
            try:
                with open(self.ui_report_dir + 'dfs_result.json', 'r') as f:
                    data = json.load(f)

                data[self.testname] = result

                with open(self.ui_report_dir + 'dfs_result.json', 'w') as f:
                    json.dump(data, f, indent=4)
            except:
                new_data = {
                    self.testname: result
                }
                with open(self.ui_report_dir + 'dfs_result.json', 'w') as f:
                    json.dump(new_data, f, indent=4)
    #webgui
    def check_abort(self):
        if (self.starttime is not None and self.testname is not None):
            # try:
            with open(self.ui_report_dir + 'dfs_result.json', 'r') as f:
                data = json.load(f)

            if (self.testname not in data.keys()):
                return

            if ('status' not in data[self.testname].keys()):
                return

            if (data[self.testname]['status'] == 'Aborting'):
                data[self.testname]['status'] = 'Aborted'

                with open(self.ui_report_dir + 'dfs_result.json', 'w') as f:
                    json.dump(data, f, indent=4)

                logging.info('Test Aborted')
                exit(1)
    # get station list
    def get_station_list(self):
        sta = self.staConnect.station_list()
        if sta == "no response":
            return "no response"
        sta_list = []
        for i in sta:
            for j in i:
                sta_list.append(j)
        return sta_list

    # set channel to parent radio and start sniffing
    def start_sniffer(self, radio_channel=None, radio=None, test_name="dfs_csa_", duration=12):
        self.pcap_name = test_name + str(datetime.now().strftime("%Y-%m-%d-%H-%M")).replace(':', '-') + ".pcap"
        self.pcap_obj_2 = sniff_radio.SniffRadio(lfclient_host=self.host, lfclient_port=self.port,
                                                    radio=self.sniff_radio, channel=radio_channel,
                                                    monitor_name="monitor", channel_bw='20')
        print("RADIO:",self.radio)
        print("CHANNEL:",self.channel)

        self.pcap_obj_2.setup(0, 0, 0)
        self.pcap_obj_2.monitor.admin_up()
        print("Waiting until ports appear...")
        x = LFUtils.wait_until_ports_appear(base_url=f"http://{self.host}:{self.port}", port_list="monitor",
                                            debug=True, timeout=300)
        if x is True:
            # print("monitor is up ")
            # print("start sniffing")
            monitor = "monitor"
            self.filter="wlan type mgt"
            pcap_name="/home/lanforge/"+self.pcap_name
            c = f"tshark -i {monitor} -a duration:{duration} -w {self.pcap_name}"
            # print(c, "command line")
            # p = paramiko.SSHClient()
            # p.set_missing_host_key_policy(
            #     paramiko.AutoAddPolicy())  # This script doesn't work for me unless this line is added!
            # p.connect(self.host, port=22, username=self.ssh_username, password=self.ssh_password)
            # p.get_transport()
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                # Connect to the remote host
                client.connect(self.host, port=22, username=self.ssh_username, password=self.ssh_password)

                # Open a session and execute the command
                stdin, stdout, stderr = client.exec_command(c)

                # Optionally, you can wait a bit to ensure the command starts
                time.sleep(1)

                # You can print or log the command output if necessary
                print(stdout.read().decode())
                print(stderr.read().decode())

                # print(f"Started tshark on {hostname}. Capturing packets for {duration} seconds.")
                
            finally:
                # Close the connection
                client.close()
        else:
            print("some problem with monitor not being up")
            self.create_webui_logs()
            exit()

    # query station data like channel etc
    def station_data_query(self, station_name="wlan0", query="channel"):
        sta = station_name.split(".")
        url = f"/port/{sta[0]}/{sta[1]}/{sta[2]}?fields={query}"
        response = self.local_realm.json_get(_req_url=url)
        if (response is None) or ("interface" not in response):
            print("station_list: incomplete response:")
            logging.info("station_list: incomplete response:")
            self.create_webui_logs()
            exit(1)
        y = response["interface"][query]
        return y

    def pre_cleanup(self):
        # self.cx_profile.cleanup()
        # self.cx_profile.cleanup_prefix()
        self.cx_profile.cleanup()
        self.cx_profile.cleanup_prefix()
        lf_clean_obj = lf_clean.lf_clean(host=self.host)
        lf_clean_obj.resource = 'all'
        lf_clean_obj.sta_clean()
    # create a layer3 connection
    def create_layer3(self, traffic_type, sta_list):
        # checked
        logging.info("station list : " + str(sta_list))

        # create
        print("Creating endpoints")
        logging.info("Creating endpoints")
        self.cx_profile.create(endp_type=traffic_type, side_a=self.upstream,
                               side_b=sta_list, sleep_time=0)
        
        self.cx_profile.start_cx()

    def stop_l3(self):
        self.cx_profile.stop_cx()

    # create client
    def create_client_(self, start_id=0, sta_prefix="wlan", num_sta=1):
        local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        station_profile = local_realm.new_station_profile()
        sta_list = self.get_station_list()
        if not sta_list:
            print("no stations on lanforge")
            logging.info("no stations on lanforge")
        else:
            print("clean existing station")
            logging.info("clean existing station")
            station_profile.cleanup(sta_list, delay=1)
            LFUtils.wait_until_ports_disappear(base_url=local_realm.lfclient_url,
                                               port_list=sta_list,
                                               debug=True)
            print("pre cleanup done")
            logging.info("pre cleanup done")
        station_list = LFUtils.portNameSeries(prefix_=sta_prefix, start_id_=start_id,
                                              end_id_=num_sta - 1, padding_number_=10000,
                                              radio=self.radio)

        # Setting up static mac
        # https://candelatech.atlassian.net/browse/DFS-161
        station_profile.add_sta_data["mac"] = "a4:6b:b6:40:2f:54"

        station_profile.use_security(self.security, self.ssid, self.passwd)
        station_profile.set_number_template("00")
        print("Bandwidth",self.bandwidth)
        if self.bandwidth=="160":
            station_profile.set_command_flag("add_sta", "create_admin_down", 1)
            station_profile.set_command_flag("add_sta", "ht160_enable", 1)
        else:
            station_profile.set_command_flag("add_sta", "create_admin_down", 1)

        station_profile.set_command_flag("set_port", "rpt_timer", 1)
        print("Creating stations.")
        logging.info("Creating stations.")
        
        station_profile.create(radio=self.radio, sta_names_=station_list)

        print("Waiting for ports to appear")
        logging.info("Waiting for ports to appear")
        local_realm.wait_until_ports_appear(sta_list=station_list)
        station_profile.admin_up()
        print("Waiting for ports to admin up")
        logging.info("Waiting for ports to admin up")
        print(self.static)
        sta_list = self.get_station_list()

        if self.static == "True":
            port = self.station_data_query(station_name=sta_list[0], query="port")
            port_ = port.split(".")
            set_port = {
                "shelf": port_[0],
                "resource": port_[1],
                "port": port_[2],
                "ip_addr": self.static_ip,
                "netmask": self.ip_mask,
                "gateway": self.gateway_ip,
                "cmd_flags": "NA",
                "current_flags": "NA",
                "mac": "NA",
                "mtu": "NA",
                "tx_queue_len": "NA",
                "alias": "NA",
                "interest": "8552366108"
            }
            self.local_realm.json_post("/cli-json/set_port", set_port)
        print("wait for ip")
        logging.info("wait for ip")
        if local_realm.wait_for_ip(station_list):
            print("All stations got IPs")
            logging.info("All stations got IPs")
            logging.info("create layer3 traffic")
            print(sta_list)
            self.create_layer3(sta_list=sta_list, traffic_type=self.traffic_type)
        else:
            print("Stations failed to get IPs")
            logging.error("Stations failed to get IPs")
            self.create_webui_logs()
            exit(1)

    # stop sniffing
    def stop_sniffer(self):
        print("Stop_sniffer")
        logging.info("Stop_sniffer")
        directory = None
        directory_name = "dut_cycle_pcap"
        if directory_name:
            directory = os.path.join("", str(directory_name))
        try:
            if not os.path.exists(directory):
                print("Report Directory does'nt exists")
                os.mkdir(directory)
        except Exception as x:
            print(x)
            print("Exception in stop sniffer")
            logging.warning(str(x))

        # self.pcap_obj_2.monitor.admin_down()
        # self.pcap_obj_2.cleanup()
        print("Pcap Name: ",self.pcap_name)
        lf_report.pull_reports(hostname=self.host, port=22, username=self.ssh_username,
                               password=self.ssh_password,
                               report_location="/home/lanforge/" + self.pcap_name,
                               report_dir="dut_cycle_pcap")
        return self.pcap_name

    # a function used for certain value calculation search for its use
    def select_values(self, n, fcc):
        if fcc == "etsi5":
            while True:
                prf_1 = random.randint(300, 400)
                prf_2 = prf_1 + random.randint(20, 50)
                prf_3 = prf_2 + random.randint(20, 50)
                diff_1 = prf_2 - prf_1
                diff_2 = prf_3 - prf_2
                diff_3 = prf_3 - prf_1
                if n == 3:
                    if (300 <= prf_2 <= 400) and (diff_1 in range(20, 50)):
                        if (300 <= prf_3 <= 400) and (diff_2 in range(20, 50)) and (diff_3 in range(20, 50)):
                            return prf_1, prf_2, prf_3
                elif n == 2:
                    if 300 <= prf_2 <= 400:
                        return prf_1, prf_2
        if fcc == "etsi6":
            while True:
                prf_1 = random.randint(400, 1200)
                prf_2 = prf_1 + random.randint(80, 400)
                prf_3 = prf_2 + random.randint(80, 400)
                diff_1 = prf_2 - prf_1
                diff_2 = prf_3 - prf_2
                diff_3 = prf_3 - prf_1
                if n == 3:
                    if (400 <= prf_2 <= 1200) and (diff_1 in range(80, 400)):
                        if (400 <= prf_3 <= 1200) and (diff_2 in range(80, 400)) and (diff_3 in range(80, 400)):
                            return prf_1, prf_2, prf_3
                elif n == 2:
                    if 400 <= prf_2 <= 1200:
                        return prf_1, prf_2
    def calculate_airtime(self,file=None):
        pcap_file = file
        print("pcap file is:", pcap_file)
        all_packets = pyshark.FileCapture(pcap_file)
        duration = []  
        time_stamps = [] 
        qbss = []
        for packet in all_packets:
            try:
                if "wlan_radio" in packet:
                    x = packet["wlan_radio"].Duration
                    duration.append(float(x))
                    # print("x is :", x)
                    y = packet.frame_info.time
                    time_stamps.append(y)
                else:
                    print("wlan_radio layer not found in packet, skipping...")
                    duration.append(0)
            except AttributeError:
                # print("Duration not found in packet, skipping...")
                duration.append(0)
        
        first_time = time_stamps[0]
        print("first_time_stamp", first_time) 
        first_time_stamp = str(first_time)[:-7]
        print("first_time_stamp", first_time_stamp)    
        t1_H = datetime.strptime(first_time_stamp, '%b %d, %Y %H:%M:%S.%f') 
        last_time = time_stamps[-1]
        last_time_stamp = str(last_time)[:-7]
        print("last_time_stamp",last_time_stamp)
        t2_H = datetime.strptime(last_time_stamp, '%b %d, %Y %H:%M:%S.%f')
        time_difference = t2_H - t1_H
        print("time difference is:", time_difference)
        total_microseconds = time_difference.total_seconds() * 10**6
        print("total time in Microseocnds =", total_microseconds)
        print("sum of duration:", sum(duration))
        a = sum(duration)/total_microseconds
        print("Duty cycle(%):",a * 100)

    # main logic used for passing correct value to run hackrf function with respect to regulations
    def main_logic(self, bssid=None):
        duration = self.sniff_duration
        self.start_sniffer(radio_channel=self.channel, radio=self.sniff_radio,
                        test_name="dfs_DUT_CYCLE_channel" + str(
                            self.channel) + "_", duration=duration)
        print("Stop sniffer",duration)
        time.sleep(duration)
        file_name_ = self.stop_sniffer()
        file_name = "./dut_cycle_pcap/" + str(file_name_)
        print("pcap file name", file_name)
        logging.info("pcap file name" + str(file_name))
        self.calculate_airtime(file=file_name)

        return

    # this is called first
    def run(self):
        print("Test Started on sniff radio: "+ str(self.sniff_radio)+"\nchannel: " +str(self.channel)+"\nBandwidth: "+str(self.bandwidth)+"\nSSID: "+str(self.ssid)+"\nSecurity: "+str(self.security)+"\nPassword: "+str(self.passwd)+"\nRadio: "+str(self.radio)+"\nTraffic Type: "+str(self.traffic_type)+"\nUpstream: "+str(self.upstream)+"\nSniff duration: "+str(self.sniff_duration))
        print("Running Duty Cycle")
        if self.sniff_duration<1 or self.sniff_duration>60:
            print("Duty Cycle Sniffing time range should be in 15-60 seconds")
            logging.info("Duty Cycle Sniffing time range should be in 15-60 seconds")
            exit()
        url = f"/resource/1/1"
        response1 = self.local_realm.json_get(_req_url=url)
        
        print(f"Updating the radio channel : {self.radio}")
        radio_eid = self.name_to_eid(eid=self.radio)
        modify_radio = lf_modify_radio.lf_modify_radio(lf_mgr=self.host)
        modify_radio.set_wifi_radio(_resource=radio_eid[1], _radio=radio_eid[2], _shelf=radio_eid[0],
                                    _channel=self.channel)
        print("clean all stations before the test")
        logging.info("clean all stations before the test")
        self.pre_cleanup()

        print("create client")
        logging.info("create client")
        self.create_client_()
        # time.sleep(15)
        cx_data = self.json_get("/cx/all")
        # print(cx_data,"HHHHHHHHHHHHHHHHHHHHHH")
        # for key, value in cx_data.items():
        #     if isinstance(value, dict) and 'state' in value:
        #         state = value['state']
        tx_rates = []
        # print(datetime.now())
        while not tx_rates:
            # Retrieve cross-connect data
            cx_data = self.json_get("/cx/all")

            # Iterate over each cross-connect item in the cx_data
            for cx_id, cx_info in cx_data.items():
                if isinstance(cx_info, dict) and 'state' in cx_info:
                    state = cx_info['state']

                    # Get the tx rates and rx rates
                    tx_rate_a = cx_info.get('bps rx a', 0)
                    tx_rate_b = cx_info.get('bps rx b', 0)

                    # Ensure either tx rate is greater than 0
                    if tx_rate_a > 0 or tx_rate_b > 0:
                        tx_rates.append({
                            'cx_id': cx_id,
                            'state': state,
                            'tx_rate_a': tx_rate_a,
                            'tx_rate_b': tx_rate_b
                        })
                    # time.sleep(0.5)
        # print(datetime.now())
        print("TX/Rx",tx_rates)
        # print("State of cx is in "+state+" state")
        # if state!="Run":
        #     print("Create CX is not in UP state")
        #     exit()
        print("Sleeping for 20 sec after CX in run state check")
        time.sleep(20)
        print("check if station is at expected channel")
        logging.info("check if station is at expected channel")
        sta_list = self.get_station_list()
        channel = self.station_data_query(station_name=sta_list[0], query="channel")
        bssid = self.station_data_query(station_name=sta_list[0], query="ap")
        print(bssid)
        logging.info(str(bssid))
        # channel = self.station_data_query(station_name="wlan0000", query="channel")
        if channel == self.channel:
            print("station is at expected channel")
            logging.info("station is at expected channel")
        else:
            print("station is not at expected channel")
            logging.error("station is not at expected channel")
            self.create_webui_logs()
            exit(1)

        test_time = datetime.now()
        test_time = test_time.strftime("%b %d %H:%M:%S")
        
        main = self.main_logic(bssid=bssid)

        test_end = datetime.now()
        test_end = test_end.strftime("%b %d %H:%M:%S")
        print("Test ended at ", test_end)
        logging.info("Test ended at " + str(test_end))
        logging.info("Test ended at " + test_end)
        s1 = test_time
        s2 = test_end  # for example
        FMT = '%b %d %H:%M:%S'
        test_duration = datetime.strptime(s2, FMT) - datetime.strptime(s1, FMT)
        logging.info("test duration" + str(test_duration))
        if (self.starttime is not None and self.testname is not None):
            main['starttime'] = self.starttime
            try:
                with open(self.ui_report_dir + 'dfs_result.json', 'r') as f:
                    data = json.load(f)

                data[self.testname] = main

                with open(self.ui_report_dir + 'dfs_result.json', 'w') as f:
                    json.dump(data, f, indent=4)
            except:
                with open(self.ui_report_dir + 'dfs_result.json', 'w') as f:
                    json.dump({self.testname: main}, f, indent=4)
        self.stop_l3()
    
def main():
    description = """
    """
    parser = argparse.ArgumentParser(
        prog='duty_cycle.py',
        formatter_class=argparse.RawTextHelpFormatter,
        description=description)
    

    parser.add_argument("--host", help='specify the GUI ip to connect to', default='192.168.1.31')
    parser.add_argument("--port", help='specify scripting port of LANforge', default=8080)
    parser.add_argument('--ssid', type=str, help='ssid for client')
    parser.add_argument('--passwd', type=str, help='password to connect to ssid', default='[BLANK]')
    parser.add_argument('--security', type=str, help='security', default='open')
    parser.add_argument('--bandwidth', type=str, help='security', default='20')
    parser.add_argument('--radio', type=str, help='radio at which client will be connected', default='1.1.wiphy1')
    parser.add_argument("--sniff_radio", help='radio at which wireshark will be started', default="1.1.wiphy0")
    parser.add_argument("--static", help='True if client will be created with static ip', default=True)
    parser.add_argument("--static_ip", help='if static option is True provide static ip to client',
                        default="192.168.2.100")
    parser.add_argument("--ip_mask", help='if static is true provide ip mask to client', default="255.255.255.0")
    parser.add_argument("--gateway_ip", help='if static is true provide gateway ip', default="192.168.2.50")
    parser.add_argument('--upstream', type=str, help='provide eth1/eth2', default='eth1')
    parser.add_argument('--channel', type=str,
                        help='channel options need to be tested 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124 ,128, 132, 136, 140',
                        default="100")
    parser.add_argument("--time_int", help='provide time interval in seconds between each trials', default="0")
    parser.add_argument("--ssh_username", help='provide username for doing ssh into LANforge', default="lanforge")
    parser.add_argument("--ssh_password", help='provide password for doing ssh into LANforge', default="lanforge")
    parser.add_argument("--traffic_type", help='mention the traffic type you want to run eg lf_udp', default="lf_udp")
    parser.add_argument("--ap_name", help='provide model of dut', default="Test_AP")
    parser.add_argument("--tx_power", help='manually provide tx power of radar sent')
    parser.add_argument("--side_a_min_rate", type=int, help='for layer3 provide side a min tx rate', default=1000000)
    parser.add_argument("--side_a_max_rate", type=int, help='for layer3 provide side a max tx rate', default=0)
    parser.add_argument("--side_b_min_rate", type=int, help='for layer3 provide side b min tx rate', default=1000000)
    parser.add_argument("--side_b_max_rate", type=int, help='for layer3 provide side b max tx rate', default=0)
    parser.add_argument("--side_a_min_pdu", type=int, help='for layer3 provide side a min pdu size', default=1250)
    parser.add_argument("--side_b_min_pdu", type=int, help='for layer3 provide side b min pdu size', default=1250)
    parser.add_argument("--postcleanup", action='store_true')
    parser.add_argument("--testname", help='specify a name for the test')
    parser.add_argument("--starttime", type=str, help="--starttime YYYY-MM-DDThh:mm")
    parser.add_argument("--ui_report_dir", help='add path for webUI results dir to copy the pdf and other files')
    parser.add_argument("--if_gain", help='to specify user defined default gain value for hackrf', default=27)
    parser.add_argument("--sniff_duration", type=int, help='To specify the user defined sniff time to get CSA frame non FCC5', default=15)
    
    args = parser.parse_args()

    # restricting the --channel arg for Japan-W53 & W56
    japan_w53_channel_list = ["52", "56", "60", "64"]
    japan_w56_channel_list = ["100", "104", "108", "112", "116", "120", "124", "128", "132", "136", "140", "144"]
    DFS_Object = DfsTest(host=args.host,
                         port=args.port,
                         testname=args.testname,
                         starttime=args.starttime,
                         ui_report_dir=args.ui_report_dir,
                         ssid=args.ssid,
                         passwd=args.passwd,
                         security=args.security,
                         radio=args.radio,
                         upstream=args.upstream,
                         channel=args.channel,
                         sniff_radio=args.sniff_radio,
                         static=args.static,
                         static_ip=args.static_ip,
                         ip_mask=args.ip_mask,
                         gateway_ip=args.gateway_ip,
                         time_int=args.time_int,
                         ssh_username=args.ssh_username,
                         ssh_password=args.ssh_password,
                         traffic_type=args.traffic_type,
                         ap_name=args.ap_name,
                         side_a_min_rate=args.side_a_min_rate,
                         side_a_max_rate=args.side_a_max_rate,
                         side_b_min_rate=args.side_b_min_rate,
                         side_b_max_rate=args.side_b_max_rate,
                         side_a_min_pdu=args.side_a_min_pdu,
                         side_b_min_pdu=args.side_b_min_pdu,
                         if_gain=args.if_gain,
                         sniff_duration=args.sniff_duration,
                         bandwidth=args.bandwidth
                         )

    DFS_Object.run()

    # if args.postcleanup:
        # DFS_Object.pre_cleanup()


if __name__ == '__main__':
    main()