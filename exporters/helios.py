#!/usr/local/bin/python
""" Prometheus Exporter for Megapixel Helios Processors

Exports all receiver temperatures and some basics from the Helios.
Run one process per helios processor.

"""
import argparse
import json
import logging
import os
import time

import requests
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily

LOG = logging.getLogger('darkbay')
LOG.setLevel(logging.WARNING)
LOG.addHandler(logging.StreamHandler())
LOG.handlers[-1].setFormatter(logging.Formatter(logging.BASIC_FORMAT))

PROXIES = 'PROXIES'
DEFAULT_PROTOCOL = 'http'
DEFAULT_PORT = 9091


class HeliosCollector(object):
    _baseurl = "%s://%s/api/v1/data/"

    def __init__(self, host, proxies=None, protocol=DEFAULT_PROTOCOL):
        self.host = host
        self.proxies = proxies
        self.baseurl = self._baseurl % (protocol, host)

    def get(self):
        return requests.get(self.baseurl, proxies=self.proxies).json()

    def collect(self):
        metrics = {
            'receiver_temp': GaugeMetricFamily(
                "ruby_temp", 'Temperature from receivers',
                labels=['processor', 'receiver', 'part']),
            'temp': GaugeMetricFamily(
                "helios_temp", 'Temperature from helios processor',
                labels=['processor', 'part']),
            'volts': GaugeMetricFamily(
                "helios_volts", 'Volts reported by helios processor',
                labels=['processor', 'part']),
            'version': GaugeMetricFamily(
                "helios_version", 'Current app version as label',
                labels=['processor', 'version']),
            'test_pattern_enabled': GaugeMetricFamily(
                "helios_test_pattern", 'Test Pattern',
                labels=['processor', 'type']),
            'reboots': CounterMetricFamily(
                "helios_reboots", 'Help text',
                labels=['processor'])
        }
        data = self.get()
        for mac, details in data['dev']['receivers'].items():
            for part, val in details['temps'].items():
                metrics['receiver_temp'].add_metric([self.host, mac, part], val)

        for part, val in data['dev']['ingest']['temps'].items():
            metrics['temp'].add_metric([self.host, part], val)

        for part, val in data['dev']['ingest']['volts'].items():
            metrics['volts'].add_metric([self.host, part], val)

        metrics['reboots'].add_metric([self.host], data['dev']['ingest']['counters']['reboots'])
        metrics['version'].add_metric([self.host, data['sys']['info']['version']['app']], 1)
        metrics['test_pattern_enabled'].add_metric(
            [self.host, data['dev']['ingest']['testPattern']['type']],
            int(data['dev']['ingest']['testPattern']['enabled'])
        )
        for metric in metrics.values():
            yield metric


def parse_args():
    parser = argparse.ArgumentParser(description='Helios exporter')
    parser.add_argument('processor', help='IP or name of helios processor')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help='port to server metrics (default: %s' % DEFAULT_PORT)
    parser.add_argument('--protocol', default=DEFAULT_PROTOCOL,
                        help='Helios api protocol (default: %s)' % DEFAULT_PROTOCOL)
    return parser.parse_args()


def main():
    args = parse_args()
    start_http_server(args.port)
    proxies = None
    if PROXIES in os.environ:
        proxies = json.loads(os.environ[PROXIES])
        LOG.info("Using proxies from Environment: %s", proxies)
    REGISTRY.register(HeliosCollector(args.processor, proxies, args.protocol))
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()

