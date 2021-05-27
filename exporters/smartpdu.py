#!/usr/local/bin/python
import argparse
import json
import logging
import os
import time

import requests
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

LOG = logging.getLogger('darkbay')
LOG.setLevel(logging.WARNING)
LOG.addHandler(logging.StreamHandler())
LOG.handlers[-1].setFormatter(logging.Formatter(logging.BASIC_FORMAT))

PROXIES = 'PROXIES'
DEFAULT_PROTOCOL = 'http'
DEFAULT_PORT = 9091
__version__ = '0.1.0'

class SmartPDUCollector(object):
    _baseurl = "%s://%s:8080/api/getcurrentpduvalues"

    def __init__(self, host, proxies=None, protocol=DEFAULT_PROTOCOL):
        self.host = host
        self.proxies = proxies
        self.baseurl = self._baseurl % (protocol, host)

    def get(self):
        return requests.get(self.baseurl, proxies=self.proxies).json()

    def collect(self):
        smart_pdu_voltage = GaugeMetricFamily("smart_pdu_voltage", 'Voltage from smartPDU',
                                      labels=['name', 'phase'])
        smart_pdu_current = GaugeMetricFamily("smart_pdu_current", 'Amperage from smartPDU',
                                      labels=['name', 'phase'])
        smart_pdu_frequency = GaugeMetricFamily("smart_pdu_frequency", 'Frequency from smartPDU',
                                              labels=['name'])
        exporter_version = GaugeMetricFamily("smart_pdu_exporter_version", 'Frequency from smartPDU',
                                              labels=['version'])

        data = self.get()
        name = data['smartPDU']['config']['name']
        for key, value in data['smartPDU']['mainInputValues'][0].items():
            if key[-1] == 'V':
                    smart_pdu_voltage.add_metric([name, key], value[0])
            elif key[-1] == 'I':
                    smart_pdu_current.add_metric([name, key], value[0])
        value = data['smartPDU']['mainInputValues'][0]['freq'][0]
        smart_pdu_frequency.add_metric([name], value)
        exporter_version.add_metric([__version__], 1)

        yield smart_pdu_voltage
        yield smart_pdu_current
        yield smart_pdu_frequency
        yield exporter_version


def parse_args():
    parser = argparse.ArgumentParser(description='SmartPDU exporter')
    parser.add_argument('host', help='IP or name of smartPDU')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help='port to server metrics (default: %s' % DEFAULT_PORT)
    parser.add_argument('--protocol', default=DEFAULT_PROTOCOL,
                        help='Smart PDU protocol (default: %s)' % DEFAULT_PROTOCOL)
    return parser.parse_args()


def main():
    args = parse_args()
    start_http_server(args.port)
    proxies = None
    if PROXIES in os.environ:
        proxies = json.loads(os.environ[PROXIES])
        LOG.info("Using proxies from Environment: %s", proxies)
    REGISTRY.register(SmartPDUCollector(args.processor, proxies, args.protocol))
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
