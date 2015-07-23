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


from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


DFA_db_session = None

Base = declarative_base()


def configure_db(cfg):
    global DFA_db_session

    if DFA_db_session:
        return

    connection = cfg.dfa_mysql.connection
    engine = create_engine(connection, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=True)
    DFA_db_session = Session()


def get_session():
    return DFA_db_session
