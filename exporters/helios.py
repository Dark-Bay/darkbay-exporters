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
LOG.setLevel(logging.INFO)
LOG.addHandler(logging.StreamHandler())
LOG.handlers[-1].setFormatter(logging.Formatter(logging.BASIC_FORMAT))

PROXIES = 'PROXIES'
DEFAULT_PROTOCOL = 'http'
DEFAULT_PORT = 9091
_name_ = 'Helios Exporter'
__version__ = '0.1.3'

class HeliosCollector(object):
    _baseurl = "%s://%s/api/v1/data/"

    def __init__(self, host, proxies=None, protocol=DEFAULT_PROTOCOL):
        self.host = host
        self.proxies = proxies
        self.baseurl = self._baseurl % (protocol, host)
        self.ldms = {}
        self.ldm_swaps = 0

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
                "helios_reboots", 'Reboots',
                labels=['processor']),
            'swaps': CounterMetricFamily(
                "helios_ldm_swaps", 'Changes in LDMs',
                labels=['processor']),
            'exporter_version': GaugeMetricFamily(
                "helios_exporter_version", 'Current Exporter Version',
                labels=['version']
            )
        }
        data = self.get()
        for mac, details in data['dev']['receivers'].items():
            for part, val in details['temps'].items():
                metrics['receiver_temp'].add_metric([self.host, mac, part], val)

            prev_ldms = self.ldms.get(mac)
            ldms = set()
            for ldm_id, ldm_info in details['ldms'].items():
                ldms.add(ldm_info['info']['serial'])
            new_swaps = 0
            if prev_ldms:
                for _ in ldms:
                    if _ not in prev_ldms:
                        new_swaps += 1
                        LOG.info("LDM (%s) is new to %s", _, mac)
            if new_swaps == 0 and prev_ldms:
                new_swaps = len(ldms - prev_ldms)
                if new_swaps > 0:
                    LOG.info('See a change in LDM len by %s', new_swaps)

            self.ldm_swaps += new_swaps
            self.ldms[mac] = ldms

        for part, val in data['dev']['ingest']['temps'].items():
            metrics['temp'].add_metric([self.host, part], val)

        for part, val in data['dev']['ingest']['volts'].items():
            metrics['volts'].add_metric([self.host, part], val)

        metrics['reboots'].add_metric([self.host], data['dev']['ingest']['counters']['reboots'])
        metrics['swaps'].add_metric([self.host], self.ldm_swaps)
        metrics['version'].add_metric([self.host, data['sys']['info']['version']['app']], 1)
        metrics['exporter_version'].add_metric([__version__], 1)
        metrics['test_pattern_enabled'].add_metric(
            [self.host, data['dev']['ingest']['testPattern']['type']],
            int(data['dev']['ingest']['testPattern']['enabled'])
        )
        for metric in metrics.values():
            yield metric


def parse_args():
    parser = argparse.ArgumentParser(description='Helios exporter')
    parser.add_argument('processor', help='IP or name of helios processor')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help='port to server metrics (default: %s' % DEFAULT_PORT)
    parser.add_argument('--protocol', default=DEFAULT_PROTOCOL,
                        help='Helios api protocol (default: %s)' % DEFAULT_PROTOCOL)
    return parser.parse_args()


def main():
    args = parse_args()
    LOG.info('Starting %s (v%s) on port %s', _name_, __version__, args.port)
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

