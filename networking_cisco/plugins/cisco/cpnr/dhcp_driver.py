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

import abc
import eventlet
import os
import shutil
import time

from neutron.agent.linux import dhcp
from neutron.agent.linux import ip_lib
from neutron.agent.linux import utils
from oslo_config import cfg
from oslo_log import log as logging

from networking_cisco.plugins.cisco.cpnr import model
from networking_cisco._i18n import _, _LE, _LW

LOG = logging.getLogger(__name__)
GREENPOOL_SIZE = 10

OPTS = [
    cfg.StrOpt('http_server',
               default="localhost:8080",
               help=_('External HTTP server, should conform to '
                      '<server_name:port> format.')),
    cfg.StrOpt('http_username',
               default='cpnradmin',
               help=_('HTTP server username.')),
    cfg.StrOpt('http_password',
               default='cpnradmin',
               secret=True,
               help=_('HTTP server password.')),
    cfg.BoolOpt('insecure',
                default=False,
                help=_('Indicate if insecure mode is used. When set to '
                       'true, SSL certificates are not verified.')),
    cfg.ListOpt('upstream_dns_servers',
                default=[],
                help=_('Comma-separated list of the DNS servers '
                       'which will be used as forwarders.')),
    cfg.StrOpt('admin_email',
               default='test@example.com',
               help=_('Email address of admin for internal DNS domain.')),
    cfg.ListOpt('dhcp_log_settings',
                default=['default', 'incoming-packets', 'missing-options',
                         'activity-summary', 'leasequery',
                         'ldap-update-detail', 'ldap-create-detail'],
                help=_('Comma-separated list of DHCP log settings in CPNR.')),
    cfg.ListOpt('dns_log_settings',
                default=['config', 'ddns', 'xfr-in', 'xfr-out', 'notify',
                         'scp', 'datastore', 'scavenge', 'server-operations',
                         'tsig', 'activity-summary', 'query-errors',
                         'ha-details', 'query-packets', 'xfr-in-packets',
                         'xfr-out-packets'],
                help=_('Comma-separated list of DNS log settings in CPNR.')),
    cfg.IntOpt('sync_interval',
               default=180,
               help=_('Interval in seconds for periodic sync with CPNR.'))

]
cfg.CONF.register_opts(OPTS, 'cisco_pnr')

_devices = {}
_networks = {}
_queue = eventlet.queue.LightQueue()
_locks = {}
last_activity = time.time()


class RemoteServerDriver(dhcp.DhcpBase):

    def __init__(self, conf, network, root_helper='sudo',
                 version=None, plugin=None):
        super(RemoteServerDriver, self).__init__(conf, network, root_helper,
                                                 version, plugin)

    def enable(self):
        """Setup DHCP.

        Enables DHCP for this network by updating the remote server
        and then sets up a local device for relaying DHCP requests.
        """
        self.update_server()
        self.update_device()

    def disable(self, retain_port=False):
        """Teardown DHCP.

        Disable DHCP for this network by updating the remote server
        and then destroying any local device and namespace.
        """
        self.update_server(disabled=True)
        if retain_port:
            return
        self.update_device(disabled=True)
        if self.conf.dhcp_delete_namespaces and self.network.namespace:
            ns_ip = ip_lib.IPWrapper(self.root_helper,
                                     self.network.namespace)
            try:
                ns_ip.netns.delete(self.network.namespace)
            except RuntimeError:
                msg = _('Failed trying to delete namespace: %s')
                LOG.exception(msg, self.network.namespace)

    def restart(self):
        """Restart DHCP.

        Restart DHCP for this network by updating remote server
        and re-establishing local device if necessary.
        """
        self.update_server()
        self.update_device()

    def reload_allocations(self):
        """Reload DHCP.

        Reload DHCP for this network by updating remote server
        and updating local device, if subnets have changed.
        """
        self.update_server()
        self.update_device()

    @property
    def active(self):
        raise NotImplementedError

    @classmethod
    def check_version(cls):
        cls.recover_devices()

    @classmethod
    def get_isolated_subnets(cls, network):
        """Return a indicator whether or not a subnet is isolated."""
        return dhcp.Dnsmasq.get_isolated_subnets(network)

    @classmethod
    def should_enable_metadata(cls, conf, network):
        """Determine whether the metadata proxy is needed for a network."""
        return dhcp.Dnsmasq.should_enable_metadata(conf, network)

    @classmethod
    def existing_dhcp_networks(cls, conf):
        """Return a list of existing networks ids that we have configs for."""
        global _devices
        return _devices.keys()

    @classmethod
    def recover_devices(cls):
        """Track devices.

        Creates global dict to track device names across driver invocations
        and populates based on current devices configured on the system.
        """

        if "_devices" in globals():
            return

        global _devices
        confs_dir = os.path.abspath(os.path.normpath(cfg.CONF.dhcp_confs))
        for netid in os.listdir(confs_dir):
            conf_dir = os.path.join(confs_dir, netid)
            intf_filename = os.path.join(conf_dir, 'interface')
            try:
                with open(intf_filename, 'r') as f:
                    ifname = f.read()
                _devices[netid] = ifname
            except IOError:
                LOG.error(_LE('Unable to read interface file: %s'),
                          intf_filename)
            LOG.debug("Recovered device %s for network %s'",
                      ifname, netid)

    def update_device(self, disabled=False):
        try:
            self._unsafe_update_device(disabled)
        except Exception:
            LOG.exception(_LE("Failed to update device for network: %s"),
                          self.network.id)

    def _unsafe_update_device(self, disabled=False):
        global _devices
        if self.network.id not in _devices:
            if disabled:
                return
            LOG.debug("Setting up device for network: %s",
                      self.network.id)
            ifname = self.device_manager.setup(self.network)
            _devices[self.network.id] = ifname
            self._write_intf_file()
        elif disabled:
            ifname = _devices[self.network.id]
            self.device_manager.destroy(self.network, ifname)
            del _devices[self.network.id]
            self._delete_intf_file()
        else:
            ifname = _devices[self.network.id]
            try:
                self.device_manager.update(self.network, ifname)
            except Exception:
                LOG.error(_LE("Failed to update device for network: %s"),
                          self.network.id)
                del _devices[self.network.id]
                self._unsafe_update_device()

    def _write_intf_file(self):
        global _devices
        confs_dir = os.path.abspath(os.path.normpath(self.conf.dhcp_confs))
        conf_dir = os.path.join(confs_dir, self.network.id)
        if not os.path.isdir(conf_dir):
            os.makedirs(conf_dir, 0o755)
        intf_filename = os.path.join(conf_dir, 'interface')
        if self.network.id not in _devices:
            return
        ifname = _devices[self.network.id]
        utils.replace_file(intf_filename, ifname)

    def _delete_intf_file(self):
        confs_dir = os.path.abspath(os.path.normpath(self.conf.dhcp_confs))
        conf_dir = os.path.join(confs_dir, self.network.id)
        shutil.rmtree(conf_dir, ignore_errors=True)

    @abc.abstractmethod
    def update_server(self, disabled=False):
        pass

    @classmethod
    def recover_networks(cls):
        """Track Network Objects.

        Creates global dict to track network objects across driver
        invocations and populates using the model module.
        """

        if "_networks" in globals():
            return

        global _networks
        _networks = model.recover_networks()


class SimpleCpnrDriver(RemoteServerDriver):

    MIN_VERSION = 8.3

    def __init__(self, conf, network, root_helper='sudo',
                 version=None, plugin=None):
        super(SimpleCpnrDriver, self).__init__(conf, network, root_helper,
                                               version, plugin)

    @classmethod
    def check_version(cls):
        """Checks server version against minimum required version."""
        super(SimpleCpnrDriver, cls).check_version()
        model.configure_pnr()
        cls.recover_networks()
        ver = model.get_version()
        if ver < cls.MIN_VERSION:
            LOG.warning(_LW("CPNR version does not meet minimum requirements, "
                     "expected: %(ever)f, actual: %(rver)f"),
                     {'ever': cls.MIN_VERSION, 'rver': ver})
        return ver

    @classmethod
    def existing_dhcp_networks(cls, conf):
        """Return a list of existing networks ids that we have configs for."""
        global _networks
        sup = super(SimpleCpnrDriver, cls)
        superkeys = sup.existing_dhcp_networks(conf)
        return set(_networks.keys()) & set(superkeys)

    def update_server(self, disabled=False):
        try:
            self._unsafe_update_server(disabled)
            model.reload_server()
        except Exception:
            LOG.exception(_LE("Failed to update PNR for network: %s"),
                          self.network.id)

    def _unsafe_update_server(self, disabled=False):
        """Update server with latest network configuration."""
        id = self.network.id
        net = model.Network.from_neutron(self.network)
        if id not in _networks:
            if disabled:
                return
            _networks[id] = net
            _networks[id].create()
        elif disabled:
            _networks[id].delete()
            del _networks[id]
        else:
            _networks[id].update(net)
            _networks[id] = net


class CpnrDriver(SimpleCpnrDriver):

    def __init__(self, conf, network, root_helper='sudo',
                 version=None, plugin=None):
        super(CpnrDriver, self).__init__(conf, network, root_helper,
                                         version, plugin)

    @classmethod
    def check_version(cls):
        ver = super(CpnrDriver, cls).check_version()
        cls.start_threads()
        return ver

    def enable(self):
        self._enqueue(super(CpnrDriver, self).enable)

    def disable(self, retain_port=False):
        self._enqueue(super(CpnrDriver, self).disable, retain_port)

    def restart(self):
        self._enqueue(super(CpnrDriver, self).restart)

    def reload_allocations(self):
        self._enqueue(super(CpnrDriver, self).reload_allocations)

    def update_server(self, disabled=False):
        try:
            lock = _locks.setdefault(self.network.id,
                                     eventlet.semaphore.Semaphore())
            with lock:
                self._unsafe_update_server(disabled)
        except Exception:
            LOG.exception(_LE('Failed to update PNR for network: %s'),
                          self.network.id)

    def update_device(self, disabled=False):
        try:
            lock = _locks.setdefault(self.network.id,
                                     eventlet.semaphore.Semaphore())
            with lock:
                self._unsafe_update_device(disabled)
        except Exception:
            LOG.exception(_LE("Failed to update device for network: %s"),
                          self.network.id)

    @classmethod
    def start_threads(cls):
        global _queue, _locks
        _queue = eventlet.queue.LightQueue()
        _locks = {}
        eventlet.spawn_n(cls._process_queue)
        eventlet.spawn_n(cls._synchronize_cpnr)

    @classmethod
    def _enqueue(cls, func, *args, **kwargs):
        _queue.put((func, args, kwargs))

    @classmethod
    def _process_queue(cls):
        global last_activity
        last_activity = time.time()
        pool = eventlet.greenpool.GreenPool(size=GREENPOOL_SIZE)
        while True:
            try:
                funcall = _queue.get(timeout=1)
            except eventlet.queue.Empty:
                funcall = None
            if funcall:
                pool.spawn_n(funcall[0], *funcall[1], **funcall[2])
                last_activity = time.time()
            if model.reload_needed() and time.time() - last_activity > 1:
                pool.waitall()
                model.reload_server()
                last_activity = time.time()

    @classmethod
    def _synchronize_cpnr(cls):
        global last_activity
        while True:
            eventlet.sleep(cfg.CONF.cisco_pnr.sync_interval)
            if ((time.time() - last_activity) <
               cfg.CONF.cisco_pnr.sync_interval):
                    continue
            pnr_networks = model.recover_networks()
            # Delete stale VPNs in CPNR
            deleted_keys = set(pnr_networks.keys()) - set(
                               _networks.keys())
            for key in deleted_keys:
                deleted = pnr_networks[key]
                try:
                    lock = _locks.setdefault(deleted.vpn.data['name'],
                                             eventlet.semaphore.Semaphore())
                    with lock:
                        deleted.delete()
                except Exception:
                    LOG.exception(_LE('Failed to delete network %s in CPNR '
                                    'during sync:'), key)

            # Create VPNs in CPNR if not already present
            created_keys = set(_networks.keys()) - set(
                               pnr_networks.keys())
            for key in created_keys:
                created = _networks[key]
                try:
                    lock = _locks.setdefault(created.vpn.data['name'],
                                             eventlet.semaphore.Semaphore())
                    with lock:
                        created.create()
                except Exception:
                    LOG.exception(_LE('Failed to create network %s in CPNR '
                                    'during sync'), key)

            # Update VPNs in CPNR if normal update has been unsuccessful
            updated_keys = set(_networks.keys()) & set(
                               pnr_networks.keys())
            for key in updated_keys:
                updated = _networks[key]
                try:
                    lock = _locks.setdefault(updated.vpn.data['name'],
                                             eventlet.semaphore.Semaphore())
                    with lock:
                        pnr_networks[key].update(updated)
                except Exception:
                    LOG.exception(_LE('Failed to update network %s in CPNR '
                                    'during sync'), key)
