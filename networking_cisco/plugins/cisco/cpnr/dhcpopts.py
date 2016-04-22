# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import binascii

from oslo_log import log as logging

from networking_cisco._i18n import _LW

LOG = logging.getLogger(__name__)


def format_for_options(name, value):
    name = name.strip()
    if type(value) is str:
        value = value.strip()
    LOG.debug('name = %s value %s', name, value)
    if name not in OPTIONS:
        LOG.warning(_LW("Unrecognized DHCP options: %s"), name)
        return
    code, datatype = OPTIONS[name]
    try:
        value = _format_value(datatype, value)
    except Exception:
        LOG.warning(_LW("Failed to parse DHCP option: %s"), name)
        return
    value = ':'.join(value[i:i + 2] for i in range(0, len(value), 2))
    LOG.debug('name = %s value %s', name, value)
    return value


def _format_value(datatype, value):
    datatype = datatype.strip()
    if ',' in datatype:
        t1, _, t2 = datatype.partition(',')
        v1, _, v2 = value.partition(' ')
        return _format_value(t1, v1) + _format_value(t2, v2)
    elif datatype.endswith('-list'):
        t = datatype[:-5]
        return ''.join([_format_value(t, v) for v in value.split(',')])
    elif datatype == 'none':
        return ''
    elif datatype == 'bool':
        if value in set([True, 'True', 'yes', 'on', '1']):
            return '01'
        else:
            return '00'
    elif datatype.startswith('int'):
        length = int(datatype[3:]) / 4
        return ('{:0{}x}'.format(int(value), int(length)))
    elif datatype == 'string':
        return (binascii.hexlify(value.encode('utf-8'))).decode('utf-8')
    elif datatype == 'ip':
        return ''.join(['{:02x}'.format(int(o)) for o in value.split('.')])
    elif datatype == 'route':
        dest, _, nexthop = value.partition(' ')
        return _format_value('ip', dest) + _format_value('ip', nexthop)


def format_for_pnr(name, value):
    name = name.strip()
    value = value.strip()
    if name not in OPTIONS:
        LOG.warning(_LW("Unrecognized DHCP options: %s"), name)
        return None
    code, datatype = OPTIONS[name]
    return {'number': str(code), 'value': value}


OPTIONS = {
    'subnet-mask': (1, 'ip'),
    'time-offset': (2, 'int32'),
    'routers': (3, 'ip-list'),
    'time-servers': (4, 'ip-list'),
    'name-servers': (5, 'ip-list'),
    'domain-name-servers': (6, 'ip-list'),
    'log-servers': (7, 'ip-list'),
    'quote-servers': (8, 'ip-list'),
    'lpr-servers': (9, 'ip-list'),
    'impress-servers': (10, 'ip-list'),
    'resource-location-servers': (11, 'ip-list'),
    'host-name': (12, 'string'),
    'boot-size': (13, 'int16'),
    'merit-dump': (14, 'string'),
    'domain-name': (15, 'string'),
    'swap-server': (16, 'ip'),
    'root-path': (17, 'string'),
    'extension-path': (18, 'string'),
    'ip-forwarding': (19, 'bool'),
    'non-local-source-routing': (20, 'bool'),
    'policy-filter': (21, 'ip-list'),
    'max-dgram-reassembly': (22, 'int16'),
    'default-ip-ttl': (23, 'int8'),
    'path-mtu-aging-timeout': (24, 'int32'),
    'path-mtu-plateau-table': (25, 'int16-list'),
    'interface-mtu': (26, 'int16'),
    'all-subnets-local': (27, 'bool'),
    'broadcast-address': (28, 'ip'),
    'perform-mask-discovery': (29, 'bool'),
    'mask-supplier': (30, 'bool'),
    'router-discovery': (31, 'bool'),
    'router-solicitation-address': (32, 'ip'),
    'static-routes': (33, 'ip-list'),
    'trailer-encapsulation': (34, 'bool'),
    'arp-cache-timeout': (35, 'int32'),
    'ieee802-3-encapsulation': (36, 'bool'),
    'default-tcp-ttl': (37, 'int8'),
    'tcp-keepalive-interval': (38, 'int32'),
    'tcp-keepalive-garbage': (39, 'bool'),
    'nis-domain': (40, 'string'),
    'nis-servers': (41, 'ip-list'),
    'ntp-servers': (42, 'ip-list'),
    'vendor-encapsulated-options': (43, 'string'),
    'netbios-name-servers': (44, 'ip-list'),
    'netbios-dd-server': (45, 'ip-list'),
    'netbios-node-type': (46, 'int8'),
    'netbios-scope': (47, 'string'),
    'font-servers': (48, 'ip-list'),
    'x-display-manager': (49, 'ip-list'),
    'dhcp-requested-address': (50, 'ip'),
    'dhcp-lease-time': (51, 'int32'),
    'dhcp-option-overload': (52, 'int8'),
    'dhcp-message-type': (53, 'int8'),
    'dhcp-server-identifier': (54, 'ip'),
    'dhcp-parameter-request-list': (55, 'string'),
    'dhcp-message': (56, 'string'),
    'dhcp-max-message-size': (57, 'int16'),
    'dhcp-renewal-time': (58, 'int32'),
    'dhcp-rebinding-time': (59, 'int32'),
    'class-id': (60, 'string'),
    'dhcp-client-identifier': (61, 'string'),
    'nwip-domain': (62, 'string'),
    'nwip-suboptions': (63, 'string'),
    'nisplus-domain': (64, 'string'),
    'nisplus-servers': (65, 'ip-list'),
    'tftp-server-name': (66, 'string'),
    'bootfile-name': (67, 'string'),
    'mobile-ip-home-agent': (68, 'ip-list'),
    'smtp-server': (69, 'ip-list'),
    'pop-server': (70, 'ip-list'),
    'nntp-server': (71, 'ip-list'),
    'www-server': (72, 'ip-list'),
    'finger-server': (73, 'ip-list'),
    'irc-server': (74, 'ip-list'),
    'streettalk-server': (75, 'ip-list'),
    'streettalk-directory-assistance-server': (76, 'ip-list'),
    'user-class': (77, 'string'),
    'slp-directory-agent': (78, 'int8,ip-list'),
    'slp-service-scope': (79, 'int8,string'),
    'rapid-commit': (80, 'none'),
    'client-fqdn': (81, 'string'),
    'storage-ns': (83, 'string'),
    'nds-servers': (85, 'ip-list'),
    'nds-tree-name': (86, 'string'),
    'nds-context': (87, 'string'),
    'bcms-controller-names': (88, 'string'),
    'bcms-controller-address': (89, 'string'),
    'dhcp-auth': (90, 'string'),
    'dhcp-client-last-time': (91, 'int32'),
    'associated-ip': (92, 'ip-list'),
    'system-architecture': (93, 'int16'),
    'interface-id': (94, 'string'),
    'ldap-servers': (95, 'ip-list'),
    'machine-id': (97, 'string'),
    'user-auth': (98, 'string'),
    'geoconf-civic': (99, 'string'),
    'ieee-1003-1-tz': (100, 'string'),
    'ref-tz-db': (101, 'string'),
    'netinfo-server-address': (112, 'string'),
    'netinfo-server-tag': (113, 'ip-list'),
    'default-url': (114, 'string'),
    'auto-configure': (116, 'bool'),
    'name-search': (117, 'int16-list'),
    'subnet-selection': (118, 'ip'),
    'domain-search': (119, 'string-list'),
    'sip-servers': (120, 'string'),
    'classless-static-routes': (121, 'route-list'),
    'dhcp-ccc': (122, 'string'),
    'dhcp-geoconf': (123, 'string'),
    'vendor-class-identifier': (124, 'string'),
    'vivso': (125, 'string'),
    'tftp-server': (128, 'ip-list'),
    'pxe-vendor-specific-129': (129, 'string'),
    'pxe-vendor-specific-130': (130, 'string'),
    'pxe-vendor-specific-131': (131, 'string'),
    'pxe-vendor-specific-132': (132, 'string'),
    'pxe-vendor-specific-133': (133, 'string'),
    'pxe-vendor-specific-134': (134, 'string'),
    'pxe-vendor-specific-135': (135, 'string'),
    'pana-agent': (136, 'ip-list'),
    'lost-server': (137, 'string'),
    'capwap-ac-v4': (138, 'ip-list'),
    'dhcp-mos': (139, 'string'),
    'dhcp-fqdn-mos': (140, 'string'),
    'sip-ua-config-domain': (141, 'string'),
    'andsf-servers': (142, 'ip-list'),
    'dhcp-geoloc': (144, 'string'),
    'force-renew-nonce-cap': (145, 'string'),
    'rdnss-selection': (146, 'string'),
    'tftp-server-address': (150, 'ip-list'),
    'status-code': (151, 'int8,string'),
    'dhcp-base-time': (152, 'int32'),
    'dhcp-state-start-time': (153, 'int32'),
    'dhcp-query-start-time': (154, 'int32'),
    'dhcp-query-end-time': (155, 'int32'),
    'dhcp-state': (156, 'int8'),
    'data-source': (157, 'int8'),
    'pcp-server': (158, 'string'),
    'dhcp-pxe-magic': (208, 'int32'),
    'config-file': (209, 'string'),
    'path-prefix': (210, 'string'),
    'reboot-time': (211, 'int32'),
    'dhcp-6rd': (212, 'string'),
    'dhcp-access-domain': (213, 'string'),
    'subnet-allocation': (220, 'string'),
    'dhcp-vss': (221, 'int8,string')}
