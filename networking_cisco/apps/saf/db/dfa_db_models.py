# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved.
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


import sqlalchemy as sa
import sqlalchemy.orm.exc as orm_exc

from networking_cisco._i18n import _LE, _LI

from networking_cisco.apps.saf.common import dfa_logger as logging
from networking_cisco.apps.saf.db import dfa_db_api as db

LOG = logging.getLogger(__name__)


class DfaNetwork(db.Base):

    """Represents DFA network."""

    __tablename__ = 'networks'

    network_id = sa.Column(sa.String(36), primary_key=True)
    name = sa.Column(sa.String(255))
    config_profile = sa.Column(sa.String(255))
    segmentation_id = sa.Column(sa.Integer)
    tenant_id = sa.Column(sa.String(36))
    fwd_mod = sa.Column(sa.String(16))
    vlan = sa.Column(sa.Integer)
    source = sa.Column(sa.String(16))
    result = sa.Column(sa.String(16))


class DfaTenants(db.Base):

    """Represents DFA tenants."""

    __tablename__ = 'tenants'

    id = sa.Column(sa.String(36), primary_key=True)
    name = sa.Column(sa.String(255), primary_key=True)
    dci_id = sa.Column(sa.Integer)
    result = sa.Column(sa.String(16))


class DfaVmInfo(db.Base):

    """Represents VM info."""

    __tablename__ = 'instances'

    port_id = sa.Column(sa.String(36), primary_key=True)
    name = sa.Column(sa.String(255))
    mac = sa.Column(sa.String(17))
    status = sa.Column(sa.String(8))
    network_id = sa.Column(sa.String(36))
    instance_id = sa.Column(sa.String(36))
    ip = sa.Column(sa.String(16))
    segmentation_id = sa.Column(sa.Integer)
    fwd_mod = sa.Column(sa.String(16))
    gw_mac = sa.Column(sa.String(17))
    host = sa.Column(sa.String(255))
    result = sa.Column(sa.String(16))


class DfaAgentsDb(db.Base):

    """Represents DFA agent."""

    __tablename__ = 'agents'

    host = sa.Column(sa.String(255), primary_key=True)
    created = sa.Column(sa.DateTime)
    heartbeat = sa.Column(sa.DateTime)
    configurations = sa.Column(sa.String(4095))


class DfaDBMixin(object):

    """Database API."""

    def __init__(self, cfg):
        # Configure database.
        db.configure_db(cfg)

    def add_project_db(self, pid, name, dci_id, result):
        proj = DfaTenants(id=pid, name=name, dci_id=dci_id, result=result)
        session = db.get_session()
        with session.begin(subtransactions=True):
            session.add(proj)

    def del_project_db(self, pid):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                ent = session.query(DfaTenants).filter_by(id=pid).one()
                session.delete(ent)
        except orm_exc.NoResultFound:
            LOG.info(_LI('Project %(id)s does not exist'), {'id': pid})
        except orm_exc.MultipleResultsFound:
            LOG.error(_LE('More than one enty found for project %(id)s.'),
                      {'id': pid})

    def get_project_name(self, pid):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                ent = session.query(DfaTenants).filter_by(id=pid).one()
            return ent and ent.name
        except orm_exc.NoResultFound:
            LOG.info(_LI('Project %(id)s does not exist'), {'id': pid})
        except orm_exc.MultipleResultsFound:
            LOG.error(_LE('More than one enty found for project %(id)s.'),
                      {'id': pid})

    def get_project_id(self, name):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                ent = session.query(DfaTenants).filter_by(name=name).one()
            return ent and ent.id
        except orm_exc.NoResultFound:
            LOG.info(_LI('Project %(name)s does not exist'), {'name': name})
        except orm_exc.MultipleResultsFound:
            LOG.error(_LE('More than one enty found for project %(name)s.'),
                      {'name': name})

    def get_all_projects(self):
        session = db.get_session()
        with session.begin(subtransactions=True):
            projs = session.query(DfaTenants).all()
        return projs

    def update_project_entry(self, pid, dci_id, result):
        session = db.get_session()
        with session.begin(subtransactions=True):
            session.query(DfaTenants).filter_by(id=pid).update(
                {'result': result, 'dci_id': dci_id})

    def add_network_db(self, net_id, net_data, source, result):
        session = db.get_session()
        with session.begin(subtransactions=True):
            net = DfaNetwork(network_id=net_id,
                             name=net_data.get('name'),
                             config_profile=net_data.get('config_profile'),
                             segmentation_id=net_data.get('segmentation_id'),
                             tenant_id=net_data.get('tenant_id'),
                             fwd_mod=net_data.get('fwd_mod'),
                             source=source,
                             result=result)
            session.add(net)

    def delete_network_db(self, net_id):
        session = db.get_session()
        with session.begin(subtransactions=True):
            net = session.query(DfaNetwork).filter_by(
                network_id=net_id).first()
            session.delete(net)

    def get_all_networks(self):
        session = db.get_session()
        with session.begin(subtransactions=True):
            nets = session.query(DfaNetwork).all()
        return nets

    def get_network(self, net_id):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                net = session.query(DfaNetwork).filter_by(
                    network_id=net_id).one()
            return net
        except orm_exc.NoResultFound:
            LOG.info(_LI('Network %(id)s does not exist'), {'id': net_id})
        except orm_exc.MultipleResultsFound:
            LOG.error(_LE('More than one enty found for network %(id)s.'),
                      {'id': net_id})

    def get_network_by_name(self, name):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                net = session.query(DfaNetwork).filter_by(name=name).all()
            return net
        except orm_exc.NoResultFound:
            LOG.info(_LI('Network %(name)s does not exist'), {'name': name})

    def get_network_by_segid(self, segid):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                net = session.query(DfaNetwork).filter_by(
                    segmentation_id=segid).one()
            return net
        except orm_exc.NoResultFound:
            LOG.info(_LI('Network %(segid)s does not exist'), {'segid': segid})
        except orm_exc.MultipleResultsFound:
            LOG.error(_LE('More than one enty found for seg-id %(id)s.'),
                      {'id': segid})

    def update_network_db(self, net_id, result):
        session = db.get_session()
        with session.begin(subtransactions=True):
            session.query(DfaNetwork).filter_by(
                network_id=net_id).update({"result": result})

    def update_network(self, net_id, **params):
        session = db.get_session()
        with session.begin(subtransactions=True):
            session.query(DfaNetwork).filter_by(
                network_id=net_id).update(params.get('columns'))

    def add_vms_db(self, vm_data, result):
        session = db.get_session()
        with session.begin(subtransactions=True):
            vm = DfaVmInfo(instance_id=vm_data['oui'].get('vm_uuid'),
                           name=vm_data['oui'].get('vm_name'),
                           status=vm_data.get('status'),
                           network_id=vm_data.get('net_uuid'),
                           port_id=vm_data.get('port_uuid'),
                           ip=vm_data['oui'].get('ip_addr'),
                           mac=vm_data.get('vm_mac'),
                           segmentation_id=vm_data.get('segmentation_id'),
                           fwd_mod=vm_data['oui'].get('fwd_mod'),
                           gw_mac=vm_data['oui'].get('gw_mac'),
                           host=vm_data.get('host'),
                           result=result)
            session.add(vm)

    def delete_vm_db(self, vm_uuid):
        session = db.get_session()
        with session.begin(subtransactions=True):
            vm = session.query(DfaVmInfo).filter_by(
                instance_id=vm_uuid).first()
            session.delete(vm)

    def update_vm_db(self, vm_port_id, **params):
        session = db.get_session()
        with session.begin(subtransactions=True):
            session.query(DfaVmInfo).filter_by(
                port_id=vm_port_id).update(params.get('columns'))

    def get_vm(self, port_id):
        session = db.get_session()
        try:
            with session.begin(subtransactions=True):
                port = session.query(DfaVmInfo).filter_by(
                    port_id=port_id).one()
            return port
        except orm_exc.NoResultFound:
            LOG.info(_LI('Port %(id)s does not exist'), {'id': port_id})
        except orm_exc.MultipleResultsFound:
            LOG.error(_LE('More than one enty found for Port %(id)s.'),
                      {'id': port_id})

    def get_vms(self):
        session = db.get_session()
        with session.begin(subtransactions=True):
            vms = session.query(DfaVmInfo).all()
        return vms

    def get_vms_for_this_req(self, **req):
        session = db.get_session()
        with session.begin(subtransactions=True):
            vms = session.query(DfaVmInfo).filter_by(**req).all()
        return vms

    def get_fialed_projects_entries(self, fail_res):
        session = db.get_session()
        with session.begin(subtransactions=True):
            ent = session.query(DfaTenants).filter_by(result=fail_res).all()
        return ent

    def update_agent_db(self, agent_info):
        session = db.get_session()
        host = agent_info.get('host')
        with session.begin(subtransactions=True):
            try:
                # Check if entry exists.
                session.query(DfaAgentsDb).filter_by(host=host).one()

                # Entry exist, only update the heartbeat and configurations.
                session.query(DfaAgentsDb).filter_by(host=host).update(
                    {'heartbeat': agent_info.get('timestamp')})
            except orm_exc.NoResultFound:
                LOG.info(_LI('Creating new entry for agent on %(host)s.'),
                         {'host': host})
                agent = DfaAgentsDb(host=host,
                                    created=agent_info.get('timestamp'),
                                    heartbeat=agent_info.get('timestamp'),
                                    configurations=agent_info.get('config'))
                session.add(agent)
            except orm_exc.MultipleResultsFound:
                LOG.error(_LE('More than one enty found for agent %(host)s.'),
                          {'host': host})

    def get_agent_configurations(self, host):
        session = db.get_session()
        with session.begin(subtransactions=True):
            try:
                ent = session.query(DfaAgentsDb).filter_by(host=host).one()
                return ent.configurations
            except orm_exc.NoResultFound:
                LOG.info(_LI('Agent %(host)s does not exist.'), {'host': host})
            except orm_exc.MultipleResultsFound:
                LOG.error(_LE('More than one enty found for agent %(host)s.'),
                          {'host': host})

    def update_agent_configurations(self, host, configs):
        session = db.get_session()
        with session.begin(subtransactions=True):
            # Update the configurations.
            return session.query(DfaAgentsDb).filter_by(host=host).update(
                {'configurations': configs})
