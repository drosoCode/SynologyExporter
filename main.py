#!/usr/local/bin/python3

from datetime import datetime
import requests
import yaml
import json
import syslog
import time
from influxdb import InfluxDBClient
from gelfclient import UdpClient


class exporter:
    def __init__(self, file) -> None:
        with open(file) as f:
            config = yaml.full_load(f)
            print("Configuration loaded")

        self.__gelf = False
        self.__influx = False
        self.__interval = config["synology"]["update"]
        self.__addr = config["synology"]["address"]
        self.__session = self.__login(
            config["synology"]["username"], config["synology"]["password"]
        )
        self.__lastLogLine = ""

        if config["graylog"]["enabled"]:
            self.__gelf = UdpClient(
                config["graylog"]["address"],
                port=config["graylog"]["port"],
                source=config["graylog"]["source"],
            )
            print("graylog initialized")

        if config["influxdb"]["enabled"]:
            self.__influx = InfluxDBClient(
                host=config["influxdb"]["address"],
                port=config["influxdb"]["port"],
                username=config["influxdb"]["user"],
                password=config["influxdb"]["password"],
                database=config["influxdb"]["database"],
            )
            print("influxdb initialized")

    def __login(self, user, password):
        session = requests.Session()
        session.post(
            self.__addr + "/webman/login.cgi",
            data={"username": user, "passwd": password},
        )
        return session

    def __getSyslogLevel(self, txt):
        if txt == "info":
            return syslog.LOG_ERR
        elif txt == "warn":
            return syslog.LOG_WARNING
        elif txt == "err":
            return syslog.LOG_INFO

    def start(self):
        while True:
            try:
                if self.__gelf:
                    self.__updateGraylog()
                if self.__influx:
                    self.__updateInflux()
            except Exception as e:
                print(e)
            time.sleep(self.__interval)

    def __updateGraylog(self):
        data = self.__session.get(
            self.__addr + "/webman/modules/SystemInfoApp/LogViewer.cgi?limit=50"
        ).json()["items"]

        for line in data:
            if json.dumps(line) != self.__lastLogLine:
                print(line)
                self.__gelf.log(
                    line["descr"],
                    level=self.__getSyslogLevel(line["level"]),
                    _user=line["who"],
                    timestamp=datetime.timestamp(
                        datetime.strptime(line["time"], "%Y/%m/%d %H:%M:%S")
                    ),
                )
            else:
                break
        self.__lastLogLine = json.dumps(data[0])

    def __updateInflux(self):
        data = []

        res = self.__session.post(
            self.__addr + "/webman/modules/StorageManager/storagehandler.cgi",
            data={"action": "load_info"},
        ).json()

        ts = datetime.utcnow().isoformat()

        for i in res["disks"]:
            data.append(
                {
                    "measurement": "disk",
                    "tags": {
                        "device": i["device"],
                        "name": i["name"],
                        "id": i["id"],
                        "nas": i["container"]["str"],
                        "location": i["container"]["type"],
                        "model": i["model"],
                        "size": i["size_total"],
                    },
                    "time": ts,
                    "fields": {
                        "status": i["status"],
                        "temp": i["temp"],
                    },
                }
            )

        for i in res["pools"]:
            data.append(
                {
                    "measurement": "pool",
                    "tags": {
                        "id": i["id"],
                        "type": i["device_type"],
                        "location": i["container"],
                    },
                    "time": ts,
                    "fields": {
                        "total": i["size"]["total"],
                        "used": i["size"]["used"],
                        "disks": ";".join(i["disks"]),
                        "status": i["status"],
                    },
                }
            )

        for i in res["volumes"]:
            data.append(
                {
                    "measurement": "volume",
                    "tags": {
                        "id": i["id"],
                        "type": i["device_type"],
                        "location": i["container"],
                        "fs_type": i["fs_type"],
                    },
                    "time": ts,
                    "fields": {
                        "total_device": i["size"]["total_device"],
                        "total": i["size"]["total"],
                        "used": i["size"]["used"],
                        "disks": ";".join(i["disks"]),
                        "status": i["status"],
                    },
                }
            )

        metrics = self.__session.post(
            self.__addr + "/webman/modules/ResourceMonitor/rsrcmonitor.cgi",
            data={"action": "allget"},
        ).json()

        for i, v in enumerate(metrics["cpu"]["values"]):
            data.append(
                {
                    "measurement": "cpu",
                    "tags": {
                        "id": i,
                    },
                    "time": ts,
                    "fields": {"value": v},
                }
            )

        for i, v in enumerate(metrics["memory"]["values"]):
            data.append(
                {
                    "measurement": "memory",
                    "tags": {
                        "id": i,
                    },
                    "time": ts,
                    "fields": {"value": v},
                }
            )

        self.__influx.write_points(data)


exporter("config.yml").start()
