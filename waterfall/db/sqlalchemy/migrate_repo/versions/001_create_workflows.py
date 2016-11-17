#    Copyright 2013 Cloudscaling Group, Inc
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

from sqlalchemy import Column, MetaData
from sqlalchemy import PrimaryKeyConstraint, String, Table, Text
from sqlalchemy import UniqueConstraint


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    workflows = Table('workflows', meta,
        Column("id", String(length=30)),
        Column("project_id", String(length=255)),
        Column("user_id", String(length=255)),
        Column("resource_type", String(length=255)),
        Column("payload", Text()),
        PrimaryKeyConstraint('id'),
        mysql_engine="InnoDB",
        mysql_charset="utf8"
    )
    workflows.create()

    if migrate_engine.name == "mysql":
        # In Folsom we explicitly converted migrate_version to UTF8.
        sql = "ALTER TABLE migrate_version CONVERT TO CHARACTER SET utf8;"
        # Set default DB charset to UTF8.
        sql += ("ALTER DATABASE %s DEFAULT CHARACTER SET utf8;" %
                migrate_engine.url.database)
        migrate_engine.execute(sql)


def downgrade(migrate_engine):
    raise NotImplementedError("Downgrade is unsupported.")
