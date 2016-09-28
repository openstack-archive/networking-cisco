# Copyright 2016 Cisco Systems, Inc.
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

    def get_sp_template_vlan_entry(self, vlan_id, sp_template, ucsm_ip):
        return self.session.query(
            ucsm_model.ServiceProfileTemplate).filter_by(
                vlan_id=vlan_id,
                sp_template=sp_template,
                device_id=ucsm_ip).first()

    def add_service_profile_template(self, vlan_id, sp_template, ucsm_ip):
        """Adds an entry for a vlan_id on a SP template to the table."""
        if not self.get_sp_template_vlan_entry(vlan_id, sp_template, ucsm_ip):
            entry = ucsm_model.ServiceProfileTemplate(vlan_id=vlan_id,
                                                      sp_template=sp_template,
                                                      device_id=ucsm_ip,
                                                      updated_on_ucs=False)
            self.session.add(entry)

    def set_sp_template_updated(self, vlan_id, sp_template, device_id):
        """Sets update_on_ucs flag to True."""
        entry = self.get_sp_template_vlan_entry(vlan_id,
                                                sp_template,
                                                device_id)
        if entry:
            entry.updated_on_ucs = True
            self.session.merge(entry)
            return entry
        else:
            return False

    def delete_sp_template_for_vlan(self, vlan_id):
        """Deletes SP Template for a vlan_id if it exists."""
        with self.session.begin(subtransactions=True):
            try:
                self.session.query(
                    ucsm_model.ServiceProfileTemplate).filter_by(
                    vlan_id=vlan_id).delete()
            except orm.exc.NoResultFound:
                return

    def get_vnic_template_vlan_entry(self, vlan_id, vnic_template, ucsm_ip,
                                     physnet):
        return self.session.query(
            ucsm_model.VnicTemplate).filter_by(
                vlan_id=vlan_id,
                vnic_template=vnic_template,
                device_id=ucsm_ip,
                physnet=physnet).first()

    def add_vnic_template(self, vlan_id, ucsm_ip, vnic_template, physnet):
        """Adds an entry for a vlan_id on a SP template to the table."""
        if not self.get_vnic_template_vlan_entry(vlan_id, vnic_template,
            ucsm_ip, physnet):
            vnic_t = ucsm_model.VnicTemplate(vlan_id=vlan_id,
                                             vnic_template=vnic_template,
                                             device_id=ucsm_ip,
                                             physnet=physnet,
                                             updated_on_ucs=False)
            with self.session.begin(subtransactions=True):
                self.session.add(vnic_t)
            return vnic_t

    def set_vnic_template_updated(self, vlan_id, ucsm_ip, vnic_template,
                                  physnet):
        """Sets update_on_ucs flag to True for a Vnic Template entry."""
        with self.session.begin(subtransactions=True):
            entry = self.get_vnic_template_vlan_entry(vlan_id, vnic_template,
                        ucsm_ip, physnet)
            if entry:
                entry.updated_on_ucs = True
                self.session.merge(entry)
                return entry

    def delete_vnic_template_for_vlan(self, vlan_id):
        """Deletes VNIC Template for a vlan_id and physnet if it exists."""
        with self.session.begin(subtransactions=True):
            try:
                self.session.query(ucsm_model.VnicTemplate).filter_by(
                    vlan_id=vlan_id).delete()
            except orm.exc.NoResultFound:
                return
