import argparse
import asyncio
import importlib
import json
import logging
import platform
import sys
import os
import time
import datetime
import pandas as pd
if sys.version_info[0] != 3:
    print("This script requires Python3")
    exit(0)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
interop_connectivity = importlib.import_module("py-json.interop_connectivity")
lf_kpi_csv = importlib.import_module("py-scripts.lf_kpi_csv")
lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_report_pdf = importlib.import_module("py-scripts.lf_report")
lf_cleanup = importlib.import_module("py-scripts.lf_cleanup")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
lf_base_interop_profile = importlib.import_module("py-scripts.lf_base_interop_profile")
qos_test = importlib.import_module("py-scripts.lf_interop_qos")
logger = logging.getLogger(__name__)
from lf_report import lf_report
class l3_throughput(Realm):
    def __init__(self,
                 host="localhost",
                 port=8080,
                #  inputs for wifi config
                 real_client_list="",
                 available_real_clent_list="",
                 multiple_groups=False,
                 ssid_input = "",
                 passwd_input = "",
                 enc_input = "",
                 eap_method_input ="",
                 eap_identity_input ="",
                 upstream_port_ip = "",
                #  inputs for qos test
                 upstream_port = "",
                 test_duration = "",
                 traffic_type = "lf_udp",
                 tos = "BE",
                 dowebgui = "False",
                 result_dir = "",
                 test_name = "",
                 path = "",
                 download = 10000,
                 upload = 10000,
                 wait_time = 60,
                 debug=False):
        super().__init__(lfclient_host=host,
                         lfclient_port=port)
        self.host = host
        self.port = port
        self.report_path = None
        self.upstream_port=upstream_port    
        self.real_client_list=real_client_list
        self.available_real_clent_list=available_real_clent_list
        self.multiple_groups = multiple_groups
        self.path = path
        self.data = {}
        self.cleanup = lf_cleanup.lf_clean(host=self.host, port=self.port, resource='all')
        self.ssid_input = ssid_input
        self.passwd_input = passwd_input
        self.enc_input = enc_input
        self.eap_method_input = eap_method_input
        self.eap_identity_input = eap_identity_input
        self.start_time = ""
        self.end_time = ""
        self.user_query = []
        self.wait_time = wait_time
        self.upstream_port_ip = upstream_port_ip
        
        self.dowebgui = dowebgui
        
        self.tos = tos
        self.traffic_type = traffic_type
        self.result_dir = result_dir
        self.test_name = test_name
        self.test_duration=test_duration
        self.download = download
        self.upload = upload
        
    def precleanup(self):
        self.cleanup.cxs_clean()
        self.cleanup.layer3_endp_clean()
        
    def selecting_devices_from_available(self):
        selected_serial_list = self.base_interop_profile.query_all_devices_to_configure_wifi()
        logger.info(f"Selected Serial List: {selected_serial_list}")
        return selected_serial_list
    
    def creating_user_querry(self,user_query_list):
        for index, sublist in enumerate(user_query_list):
            new_sublist = []
            for item in sublist:
                if index == 0:
                    if '.wlan0' not in item and '.wlan1' not in item and '.en0' not in item and '.sta0' not in item:
                        item += '.wlan0'
                elif index == 1:
                    item = item.replace('.wlan0', '').replace('.en0', '').replace('.sta0', '').replace('wlan1', '')
                new_sublist.append(item)
            self.user_query.append(new_sublist)

        print("UPDATE: Query Result: {}".format(self.user_query))
        # fetching window's list
        return self.user_query
    
    def generate_report(self,test_obj, data, input_setup_info, report_path='', result_dir_name='Qos_Test_report',
                        selected_real_clients_names=None):
        # getting ssid list for devices, on which the test ran
        test_obj.ssid_list = test_obj.get_ssid_list(test_obj.input_devices_list)

        if selected_real_clients_names is not None:
            test_obj.num_stations = selected_real_clients_names
        data_set, load, res = test_obj.generate_graph_data_set(data)
        report = lf_report(_output_pdf="interop_qos.pdf", _output_html="interop_qos.html", _path=report_path,
                           _results_dir_name=result_dir_name)
        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()
        print("path: {}".format(report_path))
        print("path_date_time: {}".format(report_path_date_time))
        report.set_title("Throughput Test")
        report.build_banner()
        # objective title and description
        report.set_obj_html(_obj_title="Objective",
                            _obj="The LANforge Interop Throughput Test is designed "
                               "to measure the performance of an Access Point when handling different types of real "
                               "clients. The test allows the user to increase the number of stations in user defined "
                               "steps for each test iteration  and measure the per station and the overall throughput,"
                               " signal and link rates for each "
                               "trial. The expected behaviour is for the AP to be able to handle several stations "
                               "(within the limitations of the AP specs) and make sure all stations get a fair amount "
                               "of upstream and downstream throughput. An AP that scales well will not show a "
                               "significant over-all throughput decrease as more stations are added.")
        report.build_objective()
        android_count = 0
        mac_count = 0
        win_count = 0
        lin_count = 0
        for dev in test_obj.real_client_list:
            if " android " in dev:
                android_count+=1
            elif " Apple " in dev:
                mac_count +=1
            elif " Lin " in dev:
                lin_count +=1
            elif " Win " in dev:
                win_count +=1
        device_string = f"Total( {len(test_obj.real_client_list)} ):Android( {android_count} ),Windows( {win_count} ),Linux( {lin_count} ),Mac( {mac_count} )"
        test_setup_info = {
        "Number of Stations" : device_string,
        "AP Model": test_obj.ap_name,
        "SSID": list(set(test_obj.ssid)),
        "Traffic Duration" : f'{round(int(test_obj.test_duration)/60,2)} minutes' ,
        "Security" : list(set(test_obj.security)),
        "Protocol" : (test_obj.traffic_type.strip("lf_")).upper(),
        "Traffic Direction" : test_obj.direction,
        "TOS" : test_obj.tos,
        "Wait Time" : f'{self.wait_time} Seconds',
        "Per TOS Load in Mbps" : load
        }
        print(res["throughput_table_df"])

        report.test_setup_table(test_setup_data=test_setup_info, value="Test Configuration")
        report.set_table_title(
            f"Overall {test_obj.direction} Throughput for all TOS i.e BK | BE | Video (VI) | Voice (VO)")
        report.build_table_title()
        df_throughput = pd.DataFrame(res["throughput_table_df"])
        report.set_table_dataframe(df_throughput)
        report.build_table()
        for key in res["graph_df"]:
            report.set_obj_html(
                _obj_title=f"Overall {test_obj.direction} throughput for {len(test_obj.input_devices_list)} clients with different TOS.",
                _obj=f"The below graph represents overall {test_obj.direction} throughput for all "
                     "connected stations running BK, BE, VO, VI traffic with different "
                     f"intended loads{load} per tos")
        report.build_objective()
        #print("data set",data_set)
        graph = lf_graph.lf_bar_graph(_data_set=data_set,
                                _xaxis_name="Load per Type of Service",
                                _yaxis_name="Throughput (Mbps)",
                                _xaxis_categories=["BK,BE,VI,VO"],
                                _xaxis_label=['1 Mbps', '2 Mbps', '3 Mbps', '4 Mbps', '5 Mbps'],
                                _graph_image_name=f"tos_download_{key}Hz",
                                _label=["BK", "BE", "VI", "VO"],
                                _xaxis_step=1,
                                _graph_title=f"Overall {test_obj.direction} throughput – BK,BE,VO,VI traffic streams",
                                _title_size=16,
                                _color=['orange', 'lightcoral', 'steelblue', 'lightgrey'],
                                _color_edge='black',
                                _bar_width=0.15,
                                _figsize=(18, 6),
                                _legend_loc="best",
                                _legend_box=(1.0, 1.0),
                                _dpi=96,
                                _show_bar_value=True,
                                _enable_csv=True,
                                _color_name=['orange', 'lightcoral', 'steelblue', 'lightgrey'])
        graph_png = graph.build_bar_graph()
        print("graph name {}".format(graph_png))
        report.set_graph_image(graph_png)
        # need to move the graph image to the results directory
        report.move_graph_image()
        report.set_csv_filename(graph_png)
        report.move_csv_file()
        report.build_graph()
        test_obj.generate_individual_graph(res, report)
        report.test_setup_table(test_setup_data=input_setup_info, value="Information")
        report.build_custom()
        report.build_footer()
        report.write_html()
        report.write_pdf()
        
    def performing_qos(self):
        test_results = {'test_results': []}
        print(self.test_duration,type(self.test_duration))
        
        self.qos_test_obj = qos_test.ThroughputQOS(host=self.host,
                                                port=self.port,
                                                upstream=self.upstream_port,
                                                ssid=self.ssid_input,
                                                password=self.passwd_input,
                                                security=self.enc_input,
                                                number_template="0000",
                                                ap_name="ap_name",
                                                name_prefix="TOS-",
                                                test_duration=self.test_duration,
                                                use_ht160=False,
                                                side_a_min_rate=self.upload,
                                                side_b_min_rate=self.download,
                                                side_a_max_rate=0,
                                                side_b_max_rate=0,
                                                traffic_type=self.traffic_type,
                                                _debug_on=False,
                                                dowebgui=self.dowebgui,
                                                test_name=self.test_name,
                                                result_dir=self.result_dir,
                                                ip=self.host,
                                                tos=self.tos
                                                )
        self.qos_test_obj.input_devices_list = self.user_query[0]
        self.qos_test_obj.real_client_list = self.user_query[1]
        self.qos_test_obj.real_client_list1 = self.user_query[1]
        self.qos_test_obj.mac_id_list = self.user_query[2]
        print(self.qos_test_obj.input_devices_list)
        print(self.qos_test_obj.real_client_list)
        print(self.qos_test_obj.real_client_list1)
        print(self.qos_test_obj.mac_id_list)
        print()
        self.qos_test_obj.build()
        self.qos_test_obj.start()
        time.sleep(10)
        connections_download, connections_upload, drop_a_per, drop_b_per = self.qos_test_obj.monitor()
        self.qos_test_obj.stop()
        time.sleep(5)
        test_results['test_results'].append(
            self.qos_test_obj.evaluate_qos(connections_download, connections_upload, drop_a_per, drop_b_per))
        self.data.update(test_results)
        test_end_time = datetime.datetime.now().strftime("%Y %d %H:%M:%S")
        logger.info("QOS Test ended at: {}".format(test_end_time))


        self.qos_test_obj.cleanup()
        print("Data", self.data)
        
        self.generate_report(data=self.data,test_obj=self.qos_test_obj,
                                            input_setup_info={"contact": "support@candelatech.com"},
                                            report_path=self.result_dir,
                                            result_dir_name=f"Qos_Test_report")

        self.qos_test_obj.generate_graph_data_set(self.data)
        if self.dowebgui == "True":
            last_entry = self.qos_test_obj.overall[len(self.qos_test_obj.overall) - 1]
            last_entry["status"] = "Stopped"
            last_entry["timestamp"] = datetime.datetime.now().strftime("%d/%m %I:%M:%S %p")
            last_entry["remaining_time"] = "0"
            last_entry["end_time"] = last_entry["timestamp"]
            self.qos_test_obj.overall.append(
                last_entry
            )
            df1 = pd.DataFrame(self.qos_test_obj.overall)
            df1.to_csv('{}/overall_throughput.csv'.format(self.qos_test_obj.result_dir ), index=False)

    def updating_webui_runningjson(self,obj):
        data = {}
        with open(self.result_dir + "/../../Running_instances/{}_{}_running.json".format(self.host, self.test_name),
                          'r') as file:
            data = json.load(file)
            for key in obj:
                data[key]=obj[key]
        with open(self.result_dir + "/../../Running_instances/{}_{}_running.json".format(self.host, self.test_name),
                          'w') as file:
            json.dump(data, file, indent=4)
            
            
def main():
    help_summary = '''\
    The Interop QoS test is designed to measure performance of an Access Point 
    while running traffic with different types of services like voice, video, best effort, background.
    The test allows the user to run layer3 traffic for different ToS in upload, download and bi-direction scenarios between AP and real devices.
    Throughputs for all the ToS are reported for individual devices along with the overall throughput for each ToS.
    The expected behavior is for the AP to be able to prioritize the ToS in an order of voice,video,best effort and background.
    
    The test will create stations, create CX traffic between upstream port and stations, run traffic and generate a report.
    '''
    parser = argparse.ArgumentParser(
        prog='throughput.webgui.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            Provides the available devices list and allows user to run the qos traffic
            with particular tos on particular devices in upload, download directions.
            ''',
        description='''\
        
        

        License: Free to distribute and modify. LANforge systems must be licensed.
        Copyright 2023 Candela Technologies Inc.

''')
    
    required = parser.add_argument_group('Required arguments to run lf_interop_qos.py')
    optional = parser.add_argument_group('Optional arguments to run lf_interop_qos.py')
    optional.add_argument('--device_list',
                          help='Enter the devices on which the test should be run', default=[])
    optional.add_argument('--test_name',
                          help='Specify test name to store the runtime csv results', default=None)
    optional.add_argument('--result_dir',
                          help='Specify the result dir to store the runtime logs', default='')
    required.add_argument('--mgr',
                              '--lfmgr',
                              default='localhost',
                              help='hostname for where LANforge GUI is running')
    required.add_argument('--mgr_port',
                            '--port',
                            default=8080,
                            help='port LANforge GUI HTTP service is running on')
    required.add_argument('--upstream_port',
                          '-u',
                            default='eth1',
                            help='non-station port that generates traffic: <resource>.<port>, e.g: 1.eth1')
    required.add_argument('--upstream_port_ip',
                            default='',
                            help='non-station port that generates traffic: <resource>.<port>, e.g: 1.eth1')
    required.add_argument('--enc_list',
                            default="",
                            help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >')
    required.add_argument('--ssid_list',
                            help='WiFi SSID for script objects to associate to',default="")
    required.add_argument('--eap_list',
                            help='WiFi SSID for script objects to associate to',default="")
    required.add_argument('--identity_list',
                            help='WiFi SSID for script objects to associate to',default="")
    required.add_argument('--passwd_list',
                            '--password',
                            '--key',
                            default="",
                            help='WiFi passphrase/password/key')
    required.add_argument('--traffic_type', help='Select the Traffic Type [lf_udp, lf_tcp]', required=False)
    required.add_argument('--upload', help='--upload traffic load per connection (upload rate)')
    required.add_argument('--download', help='--download traffic load per connection (download rate)')
    required.add_argument('--test_duration', help='--test_duration sets the duration of the test', default="2m")
    required.add_argument('--wait_time', help='--wait_time sets the duration of the test wait time for configuration', default="60")
    required.add_argument('--ap_name', help="AP Model Name", default="Test-AP")
    required.add_argument('--tos', help='Enter the tos. Example1 : "BK,BE,VI,VO" , Example2 : "BK,VO", Example3 : "VI" ')
    required.add_argument('--dowebgui', help="If true will execute script for webgui", default=False)
    optional.add_argument('-d',
                              '--debug',
                              action="store_true",
                              help='Enable debugging')
    parser.add_argument('--help_summary', help='Show summary of what this script does', default=None,
                        action="store_true")

    args = parser.parse_args()

    # help summary
    if args.help_summary:
        print(help_summary)
        exit(0)
    print("--------------------------------------------")
    print(args)
    print("--------------------------------------------")
    # set up logger
    logger_config = lf_logger_config.lf_logger_config()


    
    if args.test_duration.endswith('s') or args.test_duration.endswith('S'):
        args.test_duration = int(args.test_duration[0:-1])
    elif args.test_duration.endswith('m') or args.test_duration.endswith('M'):
        args.test_duration = int(args.test_duration[0:-1]) * 60
    elif args.test_duration.endswith('h') or args.test_duration.endswith('H'):
        args.test_duration = int(args.test_duration[0:-1]) * 60 * 60
    elif args.test_duration.endswith(''):
        args.test_duration = int(args.test_duration)
    print(args.device_list)
    ssid_input=args.ssid_list.split(',')
    passwd_input=args.passwd_list.split(',')
    enc_input=args.enc_list.split(',')
    eap_method_input=args.eap_list.split(',')
    eap_identity_input=args.identity_list.split(',')
    
    eap_method_input = [None if method == "" or method == "NA" else method for method in eap_method_input]
    eap_identity_input = [None if identity == "" or identity == "NA" else identity for identity in eap_method_input]
    run_obj = l3_throughput(host = args.mgr,port=args.mgr_port,real_client_list=args.device_list.split(','),
                            ssid_input=ssid_input,
                            passwd_input=passwd_input,
                            enc_input=enc_input,
                            eap_method_input=eap_method_input,
                            eap_identity_input=eap_identity_input,
                            upstream_port=args.upstream_port,
                            test_duration=args.test_duration,
                            download=args.download,
                            upload=args.upload,
                            traffic_type=args.traffic_type,
                            tos=args.tos,dowebgui=args.dowebgui,
                            result_dir=args.result_dir,
                            test_name=args.test_name,
                            wait_time=args.wait_time,
                            upstream_port_ip=args.upstream_port_ip)
    
    real_devices=lf_base_interop_profile.RealDevice(manager_ip=run_obj.host,server_ip = run_obj.host,groups=True)
    all_devices=real_devices.query_all_devices_to_configure_wifi(device_list=run_obj.real_client_list)
    print("configuring....")
    configuring_devices = asyncio.run(real_devices.configure_wifi_groups(select_serials=all_devices[1],serials_input = run_obj.real_client_list
                                        , ssid_input=run_obj.ssid_input,passwd_input=run_obj.passwd_input,enc_input=run_obj.enc_input,
                                        eap_method_input=run_obj.eap_method_input,eap_identity_input=run_obj.eap_identity_input))
    print(f"wait time is {run_obj.wait_time} seconds")
    time.sleep(int(run_obj.wait_time))
    last_data=real_devices.monitor_connection(configuring_devices[0].copy(),configuring_devices[1].copy())
    run_obj.creating_user_querry(last_data)
    if len(run_obj.user_query[0]) == 0:
        print("No device is available to run the test")
        obj = {
            "status":"Stopped",
            "configuration_status":"configured"
        }
        run_obj.updating_webui_runningjson(obj)
        return
    else:
        obj = {
            "configured_devices":run_obj.user_query[1],
            "configuration_status":"configured"
        }
        run_obj.updating_webui_runningjson(obj)
    print(run_obj.user_query)
    
    run_obj.performing_qos()
if __name__ == "__main__":
    main()