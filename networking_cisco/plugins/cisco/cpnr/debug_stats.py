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
#


class PacketStats(object):

    def __init__(self, net_id):
        self.net_id = net_id
        self.pkts_from_client = 0
        self.pkts_to_server = 0
        self.pkts_from_server = 0
        self.pkts_to_client = 0

    def write_to_file(self, f):
        f.write('%(net_id)s: from_client %(pkts_from_client)d,'
                'to_server %(pkts_to_server)d, from_server '
                '%(pkts_from_server)d, to_client %(pkts_to_client)d\n' %
                {'net_id': self.net_id,
                 'pkts_from_client': self.pkts_from_client,
                 'pkts_to_server': self.pkts_to_server,
                 'pkts_from_server': self.pkts_from_server,
                 'pkts_to_client': self.pkts_to_client})


class DebugStats(object):

    def __init__(self, stats_type):
        self.stats_filename = '/tmp/' + stats_type + '_dbg_stats.txt'
        self.total_stats = PacketStats('Total ' +
                                stats_type.upper() + ' Stats')
        self.per_network_stats = {}

    def write_stats_to_file(self):
        with open(self.stats_filename, 'w') as f:
            self.total_stats.write_to_file(f)
            for net_id, stats in self.per_network_stats.items():
                stats.write_to_file(f)

    def add_network_stats(self, net_id):
        if net_id in self.per_network_stats:
            del self.per_network_stats[net_id]
        self.per_network_stats[net_id] = PacketStats(net_id)

    def del_network_stats(self, net_id):
        del self.per_network_stats[net_id]

    def increment_pkts_from_client(self, net_id):
        self.total_stats.pkts_from_client += 1
        if net_id in self.per_network_stats:
            self.per_network_stats[net_id].pkts_from_client += 1

    def increment_pkts_to_server(self, net_id):
        self.total_stats.pkts_to_server += 1
        if net_id in self.per_network_stats:
            self.per_network_stats[net_id].pkts_to_server += 1

    def increment_pkts_from_server(self, net_id):
        self.total_stats.pkts_from_server += 1
        if net_id in self.per_network_stats:
            self.per_network_stats[net_id].pkts_from_server += 1

    def increment_pkts_to_client(self, net_id):
        self.total_stats.pkts_to_client += 1
        if net_id in self.per_network_stats:
            self.per_network_stats[net_id].pkts_to_client += 1
