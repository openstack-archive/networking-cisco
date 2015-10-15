# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from sqlalchemy import orm

from networking_cisco.plugins.ml2.drivers.cisco.ucsm import ucsm_model
from neutron.db import api as db_api


class UcsmDbModel(object):
    def __init__(self):
        self.session = db_api.get_session()

    def is_port_profile_created(self, vlan_id, device_id):
        """Indicates if port profile has been created on UCS Manager."""
        entry = self.session.query(ucsm_model.PortProfile).filter_by(
            vlan_id=vlan_id, device_id=device_id).first()
        return entry and entry.created_on_ucs

    def get_port_profile_for_vlan(self, vlan_id, device_id):
        """Returns Vlan id associated with the port profile."""
        entry = self.session.query(ucsm_model.PortProfile).filter_by(
            vlan_id=vlan_id, device_id=device_id).first()
        return entry.profile_id if entry else None

    def add_port_profile(self, profile_name, vlan_id, device_id):
        """Adds a port profile and its vlan_id to the table."""
        if not self.get_port_profile_for_vlan(vlan_id, device_id):
            port_profile = ucsm_model.PortProfile(profile_id=profile_name,
                                                  vlan_id=vlan_id,
                                                  device_id=device_id,
                                                  created_on_ucs=False)
            with self.session.begin(subtransactions=True):
                self.session.add(port_profile)
            return port_profile

    def set_port_profile_created(self, vlan_id, profile_name, device_id):
        """Sets created_on_ucs flag to True."""
        with self.session.begin(subtransactions=True):
            port_profile = self.session.query(
                ucsm_model.PortProfile).filter_by(
                    vlan_id=vlan_id, profile_id=profile_name,
                    device_id=device_id).first()
            if port_profile:
                port_profile.created_on_ucs = True
                self.session.merge(port_profile)
            else:
                new_profile = ucsm_model.PortProfile(profile_id=profile_name,
                                          vlan_id=vlan_id,
                                          device_id=device_id,
                                          created_on_ucs=True)
                self.session.add(new_profile)

    def delete_vlan_entry(self, vlan_id):
        """Deletes entry for a vlan_id if it exists."""
        with self.session.begin(subtransactions=True):
            try:
                self.session.query(ucsm_model.PortProfile).filter_by(
                    vlan_id=vlan_id).delete()
            except orm.exc.NoResultFound:
                return
