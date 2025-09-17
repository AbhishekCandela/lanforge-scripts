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
from datetime import timedelta
import pandas as pd
from lf_graph import lf_bar_graph
if sys.version_info[0] != 3:
    print("This script requires Python3")
    exit(0)
if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
interop_connectivity = importlib.import_module("py-json.interop_connectivity")
lf_cleanup = importlib.import_module("py-scripts.lf_cleanup")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
lf_base_interop_profile = importlib.import_module("py-scripts.lf_base_interop_profile")
from lf_report import lf_report
from lf_graph import lf_bar_graph
from lf_graph import lf_bar_graph_horizontal
logger = logging.getLogger(__name__)
class BasicConnectivity(Realm):
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
                 path="",
                 dowebgui=None,
                 result_dir = "",
                 test_name = "",
                 single_group = None,
                 wificonfig=None,
                 test_duration = 120,
                 debug=False
                 ):
        super().__init__(lfclient_host=host,
                         lfclient_port=port)
        self.host = host
        self.port = port
        self.report_path = None
        self.upstream_port=upstream_port_ip    
        self.real_client_list=real_client_list
        self.available_real_clent_list=available_real_clent_list
        self.multiple_groups = multiple_groups
        self.path = path
        self.ssid_input = ssid_input
        self.passwd_input = passwd_input
        self.enc_input = enc_input
        self.eap_method_input = eap_method_input
        self.eap_identity_input = eap_identity_input
        self.start_time = ""
        self.end_time = ""
        self.remaining_time = ""
        self.user_query = []
        self.upstream_port_ip = upstream_port_ip
        self.dowebgui = dowebgui
        self.test_name=test_name
        self.result_dir=result_dir
        self.single_group=single_group
        self.wificonfig=wificonfig
        self.test_duration = test_duration
    
    def creating_user_querry(self,user_query_list):
        self.user_query = []
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

    def getting_webui_runningjson(self):
        with open(self.result_dir + "/../../Running_instances/{}_{}_running.json".format(self.host, self.test_name),
                          'r') as file:
            data = json.load(file)
            if not self.wificonfig:
                self.wificonfig =  data["test_values"]["wificonfig"]
                groups_name = self.wificonfig["groups_name"]
                group_devices = self.wificonfig["group_devices"]
                profiles = self.wificonfig["profile"]
                usernames = self.wificonfig["device_usernames"]

                # Create the new structure
                
                new_structure = {
                    "status":"Running",
                    "wificonfig": {},
                    "iteration":0,
                    "start_time":self.start_time,
                    "end_time":self.end_time
                }

                # Populate the new structure
                if len(profiles) == len(groups_name):
                    for group_name, devices, profile,username in zip(groups_name, group_devices, profiles, usernames):
                        devices_list = devices.split(',')
                        user_list = username.split(',')
                        ssid_profile = profile[next(iter(profile))]
                        group_info = {
                            "profile": [ssid_profile],
                            "devices": [device_id for device_id in devices_list],
                            "usernames": [user_names for user_names in user_list]
                        }
                        new_structure["wificonfig"][group_name] = group_info
                elif len(profiles) > len(groups_name):
                    for group_name, devices, username in zip(groups_name, group_devices, usernames):
                        devices_list = devices.split(',')
                        user_list = username.split(',')
                        ssid_profile = [pro[next(iter(pro))] for pro in profiles]
                        group_info = {
                            "profile": ssid_profile,
                            "devices": [device_id for device_id in devices_list],
                            "usernames": [user_names for user_names in user_list]
                        }
                        new_structure["wificonfig"][group_name] = group_info
                self.wificonfig = new_structure
        return data

    def updating_running_json(self,data,increment,status = "Running"):
        try:
            for group, group_data in self.wificonfig['wificonfig'].items():
                for device in group_data['usernames']:
                    if len(data)>2 and data[3].count(device) > 0:
                        index = data[3].index(device)
                        if device not in group_data["profile"][self.wificonfig["iteration"]][6]:
                            group_data["profile"][self.wificonfig["iteration"]][6].append(device)
                            group_data["profile"][self.wificonfig["iteration"]][7].append(data[2][index])
                            group_data["profile"][self.wificonfig["iteration"]][8].append(data[4][index])
                            group_data["profile"][self.wificonfig["iteration"]][9].append(data[5][index])
                            
            self.wificonfig["iteration"] = increment
            self.wificonfig["status"] = status
            self.wificonfig["start_time"] = ""
            self.wificonfig["end_time"] = ""
            with open(self.result_dir+"/real_time.json",'w+') as file:
                print(self.wificonfig)
                json.dump(self.wificonfig,file,indent=4)
        except Exception as e:
            print(e,"execption when updating running json")
        pass
    
    def generate_report(self, data,input_setup_info,report_path='',result_dir_name='Connectivity_Test_report',
                        selected_real_client_names=None,date=str(datetime.datetime.now()).split(",")[0].replace(" ", "-").split(".")[0],device_details=None):
        logging.info("Creating Reports")
        report = lf_report(_results_dir_name = "connectivity_test",_output_html="connectivity_test.html",
                           _output_pdf="connectivity_test.pdf",_path=self.result_dir)
        report.set_title("Multi-SSID Test")
        report.set_date(date)
        report.build_banner()
        report.set_obj_html("Objective", "The purpose of the Multi SSID Test is to configure a set of clients of different OS types to a specifi set of SSID's for executing furter test on those devices.")
        report.build_objective()
        report.set_table_title("Test Setup Information")
        report.build_table_title()
        report.test_setup_table(value="Test Setup Information", test_setup_data=input_setup_info)
        print(data)
        

        for group in data["wificonfig"]:
            if len(data["wificonfig"][group]["profile"])<2:
                dataset=[]
                x_axis=[]
                connection_dataset = []
                Disconnection_data = []
                connection_dataset.append(len(data["wificonfig"][group]["profile"][0][6]))
                Disconnection_data.append(len(data["wificonfig"][group]["devices"])-len(data["wificonfig"][group]["profile"][0][6]))
                dataset.append(connection_dataset)
                dataset.append(Disconnection_data)
                color=["Green","Red"]
                labels=["Connections","Disconnections"]
                x_axis.append(group)
                report.set_table_title(
                    f'Connection/Disconnections vs Groups for {group} -> {data["wificonfig"][group]["profile"][0][0]}')
                report.build_table_title()
                graph = lf_bar_graph(_data_set=dataset,
                                      _xaxis_name="Connection Status",
                                      _yaxis_name="Device Count",
                                      _xaxis_categories=x_axis,
                                      _label=labels,
                                      _graph_image_name=group+data["wificonfig"][group]["profile"][0][0],
                                      _figsize=(18, 6),
                                      _color=color,
                                      _show_bar_value=False,
                                      _xaxis_step=None,
                                      _color_edge=None,
                                      _text_rotation=40,
                                      _legend_loc="upper right",
                                      _enable_csv=True)

                graph_png = graph.build_bar_graph()

                logger.info("graph name {}".format(graph_png))

                report.set_graph_image(graph_png)
                # need to move the graph image to the results
                report.move_graph_image()
                report.set_csv_filename(graph_png)
                report.move_csv_file()

                report.build_graph()
                
                
                report.set_table_title("Group Result")
                report.build_table_title()
                report.test_setup_table(value=data["wificonfig"][group]["profile"][0][0], test_setup_data={
                    "SSID":data["wificonfig"][group]["profile"][0][1],
                    "Encryption" : data["wificonfig"][group]["profile"][0][2],
                    "Password" : data["wificonfig"][group]["profile"][0][3],
                    "EAP-METHOD" : data["wificonfig"][group]["profile"][0][4] if data["wificonfig"][group]["profile"][0][4] != "" else "-",
                    "EAP-IDENTITY" : data["wificonfig"][group]["profile"][0][5] if data["wificonfig"][group]["profile"][0][5] != "" else "-"
                })
                device_list = data["wificonfig"][group]["usernames"]
                connected_list = data["wificonfig"][group]["profile"][0][6]
                mac_address_list = data["wificonfig"][group]["profile"][0][7]
                rssi_list = data["wificonfig"][group]["profile"][0][8]
                channel_list = data["wificonfig"][group]["profile"][0][9]
                os_type_list=[]
                for dev in  data["wificonfig"][group]["devices"]:
                    found = False
                    for item in device_details:
                        if dev in device_details[item]["username"]:
                            os_type_list.append(device_details[item]["os"])
                            found = True
                            break
                    if not found:
                        os_type_list.append("-")
                dataframe ={
                        " Devices": device_list,
                        "OS": os_type_list,
                        " Connection Status": ["Connected" if dev in connected_list else "Not Connected" for dev in device_list],
                        "Mac Address" :  [mac_address_list[connected_list.index(dev)] if dev in connected_list else "-" for dev in device_list],
                        "RSSI" : [rssi_list[connected_list.index(dev)] if dev in connected_list else "-" for dev in device_list],
                        "Channel": [channel_list[connected_list.index(dev)] if dev in connected_list else "-" for dev in device_list]
                    }
                print(dataframe)
                print(str(dataframe))
                dataframe1 = pd.DataFrame(dataframe)
                report.set_table_dataframe(dataframe1)
                report.build_table()
                                 
                
            else:
                for profile in data["wificonfig"][group]["profile"]:
                    dataset=[]
                    x_axis=[]
                    connection_dataset = []
                    Disconnection_data = []
                    connection_dataset.append(len(profile[6]))
                    Disconnection_data.append(len(data["wificonfig"][group]["devices"])-len(profile[6]))
                    dataset.append(connection_dataset)
                    dataset.append(Disconnection_data)
                    color=["Green","Red"]
                    labels=["Connections","Disconnections"]
                    x_axis.append(group)
                    report.set_table_title(
                        f'Connection/Disconnections vs Groups for {group} -> {profile[0]}')
                    report.build_table_title()
                    graph = lf_bar_graph(_data_set=dataset,
                                        _xaxis_name="Connection Status",
                                        _yaxis_name="Device Count",
                                        _xaxis_categories=x_axis,
                                        _label=labels,
                                        _graph_image_name=group+profile[0],
                                        _figsize=(18, 6),
                                        _color=color,
                                        _show_bar_value=False,
                                        _xaxis_step=None,
                                        _color_edge=None,
                                        _text_rotation=40,
                                        _legend_loc="upper right",
                                        _enable_csv=True)

                    graph_png = graph.build_bar_graph()

                    logger.info("graph name {}".format(graph_png))

                    report.set_graph_image(graph_png)
                    # need to move the graph image to the results
                    report.move_graph_image()
                    report.set_csv_filename(graph_png)
                    report.move_csv_file()

                    report.build_graph()
                    
                    report.set_table_title("Group Result")
                    report.build_table_title()
                    report.test_setup_table(value=profile[0], test_setup_data={
                    "SSID":profile[1],
                    "Encryption" : profile[2],
                    "Password" : profile[3],
                    "EAP-METHOD" : profile[4] if profile[4] != "" else "-",
                    "EAP-IDENTITY" : profile[5]  if profile[5] != "" else "-"
                    })
                    device_list = data["wificonfig"][group]["usernames"]
                    connected_list = profile[6]
                    mac_address_list = profile[7]
                    rssi_list = profile[8]
                    channel_list = profile[9]
                    os_type_list=[]
                    for dev in  data["wificonfig"][group]["devices"]:
                        found = False
                        for item in device_details:
                            if dev in device_details[item]["username"]:
                                os_type_list.append(device_details[item]["os"])
                                found = True
                                break
                        if not found:
                            os_type_list.append("-")
                    dataframe ={
                            " Devices": device_list,
                            "OS": os_type_list,
                            " Connection Status": ["Connected" if dev in connected_list else "Not Connected" for dev in device_list], 
                            "Mac Address" :  [mac_address_list[connected_list.index(dev)] if dev in connected_list else "-" for dev in device_list],
                            "RSSI" : [rssi_list[connected_list.index(dev)] if dev in connected_list else "-" for dev in device_list],
                            "Channel": [channel_list[connected_list.index(dev)] if dev in connected_list else "-" for dev in device_list]
                        }
                    print(dataframe)
                    print(str(dataframe))
                    dataframe1 = pd.DataFrame(dataframe)
                    report.set_table_dataframe(dataframe1)
                    report.build_table()

        report.build_footer()
        html_file = report.write_html()
        report.write_pdf()
        

def main():
    help_summary = '''\
    Help in configuring devices from webui on the basis of groups
    '''
    parser = argparse.ArgumentParser(
        prog='connectivity.py',
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
    parser.add_argument('--test_duration', help='Duration that is available to connect to wifi config', default=120,type=int)
    parser.add_argument('--dowebgui', help='to run the tests with webgui',default=None,
                        action="store_true")
    parser.add_argument('--single_group', help='to run the tests with sinlge group multiple iterations',default=None,
                        action="store_true")
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
    
    # set up logger
    logger_config = lf_logger_config.lf_logger_config()  
    config_input = None
    overall_dataset = {}
    run_obj = None
    device_details = None
    ssid_input=args.ssid_list.split(',')
    passwd_input=args.passwd_list.split(',')
    enc_input=args.enc_list.split(',')
    eap_method_input=args.eap_list.split(',')
    eap_identity_input=args.identity_list.split(',')
    
    eap_method_input = [None if method == "" or method == "NA" else method for method in eap_method_input]
    eap_identity_input = [None if identity == "" or identity == "NA" else identity for identity in eap_method_input]
        
    print("starting the test")
    if args.single_group:
        last_config = None
        for idx in range(len(ssid_input)):
            run_obj = BasicConnectivity(host = args.mgr,port=args.mgr_port,real_client_list=args.device_list.split(','),
                            ssid_input=[ssid_input[idx]]*len(args.device_list.split(',')),
                            passwd_input=[passwd_input[idx]]*len(args.device_list.split(',')),
                            enc_input=[enc_input[idx]]*len(args.device_list.split(',')),
                            eap_method_input=[eap_method_input[idx]]*len(args.device_list.split(',')),
                            eap_identity_input=[eap_identity_input[idx]]*len(args.device_list.split(',')),
                            dowebgui=args.dowebgui,
                            result_dir=args.result_dir,
                            test_name=args.test_name,
                            test_duration=args.test_duration,
                            upstream_port_ip=args.upstream_port_ip,wificonfig=last_config)
            config_input=run_obj.getting_webui_runningjson()
            run_obj.updating_running_json([],increment=idx)
           
            
            real_devices=lf_base_interop_profile.RealDevice(manager_ip=run_obj.host,server_ip = run_obj.upstream_port_ip,groups=True)
            all_devices=real_devices.query_all_devices_to_configure_wifi(device_list=run_obj.real_client_list)
            print("configuring....")
            device_details=real_devices.all_devices
            configuring_devices = asyncio.run(real_devices.configure_wifi_groups(select_serials=all_devices[1],serials_input = run_obj.real_client_list
                                                , ssid_input=run_obj.ssid_input,passwd_input=run_obj.passwd_input,enc_input=run_obj.enc_input,
                                                eap_method_input=run_obj.eap_method_input,eap_identity_input=run_obj.eap_identity_input)) 
            run_obj.start_time = datetime.datetime.now() 
            run_obj.end_time = run_obj.start_time+timedelta(seconds=run_obj.test_duration)
            print(f"waiting for {run_obj.test_duration} seconds")
            while(datetime.datetime.now()<run_obj.end_time):
                real_time_data = real_devices.monitor_connection(configuring_devices[0].copy(),configuring_devices[1].copy())
                run_obj.creating_user_querry(real_time_data)
                run_obj.updating_running_json(run_obj.user_query,increment=idx)
                overall_dataset = run_obj.wificonfig
                time.sleep(5)
            real_time_data = real_devices.monitor_connection(configuring_devices[0].copy(),configuring_devices[1].copy())
            run_obj.creating_user_querry(real_time_data)
            run_obj.updating_running_json(run_obj.user_query,increment=idx)
            print(run_obj.user_query)
            last_config = run_obj.wificonfig
            overall_dataset = last_config

            
    else:
        run_obj = BasicConnectivity(host = args.mgr,port=args.mgr_port,real_client_list=args.device_list.split(','),
                                ssid_input=ssid_input,
                                passwd_input=passwd_input,
                                enc_input=enc_input,
                                eap_method_input=eap_method_input,
                                eap_identity_input=eap_identity_input,
                                dowebgui=args.dowebgui,
                                result_dir=args.result_dir,
                                test_name=args.test_name,
                                test_duration=args.test_duration,
                                upstream_port_ip=args.upstream_port_ip)
        config_input=run_obj.getting_webui_runningjson()
    
        run_obj.updating_running_json([],increment=0)
        real_devices=lf_base_interop_profile.RealDevice(manager_ip=run_obj.host,server_ip = run_obj.upstream_port_ip,groups=True)
        all_devices=real_devices.query_all_devices_to_configure_wifi(device_list=run_obj.real_client_list)
        print("configuring....",real_devices.all_devices)
        device_details=real_devices.all_devices
        configuring_devices = asyncio.run(real_devices.configure_wifi_groups(select_serials=all_devices[1],serials_input = run_obj.real_client_list
                                            , ssid_input=run_obj.ssid_input,passwd_input=run_obj.passwd_input,enc_input=run_obj.enc_input,
                                            eap_method_input=run_obj.eap_method_input,eap_identity_input=run_obj.eap_identity_input))
        run_obj.start_time = datetime.datetime.now() 
        run_obj.end_time = run_obj.start_time+timedelta(seconds=run_obj.test_duration)
        print(f"waiting for {run_obj.test_duration} seconds")
        while(datetime.datetime.now()<run_obj.end_time):
            real_time_data = real_devices.monitor_connection(configuring_devices[0].copy(),configuring_devices[1].copy())
            run_obj.creating_user_querry(real_time_data)
            run_obj.updating_running_json(run_obj.user_query,increment=0)
            overall_dataset = run_obj.wificonfig
            time.sleep(5)
        real_time_data = real_devices.monitor_connection(configuring_devices[0].copy(),configuring_devices[1].copy())
        run_obj.creating_user_querry(real_time_data)
        run_obj.updating_running_json(run_obj.user_query,increment=0)
        print(run_obj.user_query)
        overall_dataset = run_obj.wificonfig
    input_device_list = config_input["device_list"]
    android,linux,mac,windows=0,0,0,0
    for device in input_device_list:
        if "( Android )" in device:
            android+=1
        elif "( Windows )" in device:
            linux+=1
        elif "( MAC )" in device:
            mac+=1
        elif "( Linux )" in device:
            windows+=1
    
    input_setup_info = {
        "Testname":args.test_name,
        "Upstream":args.upstream_port_ip,
        "Wait Time":f'{run_obj.test_duration} seconds',
        "No of Devices":f'Total :{len(config_input["device_list"])} (A-{android}, L-{linux}, W-{windows}, M-{mac})',
        "Group and Profile Configuration":"<br/>".join([f"{group} --> {pro[0]}" for group, group_data in overall_dataset["wificonfig"].items() for pro in group_data["profile"]])
    }
    print(input_setup_info)
    run_obj.generate_report(data=overall_dataset,input_setup_info=input_setup_info,report_path=run_obj.result_dir,device_details=device_details)
    run_obj.updating_running_json(run_obj.user_query,overall_dataset["iteration"],status="Stopped")
    # run_obj.performing_qos()
if __name__ == "__main__":
    main()
