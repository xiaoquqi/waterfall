# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Defines interface for DB access.

Functions in this module are imported into the waterfall.db namespace. Call these
functions from waterfall.db namespace, not the waterfall.db.api namespace.

All functions in this module return objects that implement a dictionary-like
interface. Currently, many of these objects are sqlalchemy objects that
implement a dictionary interface. However, a future goal is to have all of
these objects be simple dictionaries.


**Related Flags**

:connection:  string specifying the sqlalchemy connection to use, like:
              `sqlite:///var/lib/waterfall/waterfall.sqlite`.

:enable_new_services:  when adding a new service to the database, is it in the
                       pool of available hardware (Default: True)

"""

from oslo_config import cfg
from oslo_db import concurrency as db_concurrency
from oslo_db import options as db_options

from waterfall.api import common
from waterfall.common import constants
from waterfall.i18n import _

db_opts = [
    cfg.BoolOpt('enable_new_services',
                default=True,
                help='Services to be added to the available pool on create'),
    cfg.StrOpt('workflow_name_template',
               default='workflow-%s',
               help='Template string to be used to generate workflow names'),
    cfg.StrOpt('snapshot_name_template',
               default='snapshot-%s',
               help='Template string to be used to generate snapshot names'),
    cfg.StrOpt('backup_name_template',
               default='backup-%s',
               help='Template string to be used to generate backup names'), ]


CONF = cfg.CONF
CONF.register_opts(db_opts)
db_options.set_defaults(CONF)
CONF.set_default('sqlite_db', 'waterfall.sqlite', group='database')

_BACKEND_MAPPING = {'sqlalchemy': 'waterfall.db.sqlalchemy.api'}


IMPL = db_concurrency.TpoolDbapiWrapper(CONF, _BACKEND_MAPPING)

# The maximum value a signed INT type may have
MAX_INT = constants.DB_MAX_INT


###################

def dispose_engine():
    """Force the engine to establish new connections."""

    # FIXME(jdg): When using sqlite if we do the dispose
    # we seem to lose our DB here.  Adding this check
    # means we don't do the dispose, but we keep our sqlite DB
    # This likely isn't the best way to handle this

    if 'sqlite' not in IMPL.get_engine().name:
        return IMPL.dispose_engine()
    else:
        return


###################


class Condition(object):
    """Class for normal condition values for conditional_update."""
    def __init__(self, value, field=None):
        self.value = value
        # Field is optional and can be passed when getting the filter
        self.field = field

    def get_filter(self, model, field=None):
        return IMPL.condition_db_filter(model, self._get_field(field),
                                        self.value)

    def _get_field(self, field=None):
        # We must have a defined field on initialization or when called
        field = field or self.field
        if not field:
            raise ValueError(_('Condition has no field.'))
        return field


class Not(Condition):
    """Class for negated condition values for conditional_update.

    By default NULL values will be treated like Python treats None instead of
    how SQL treats it.

    So for example when values are (1, 2) it will evaluate to True when we have
    value 3 or NULL, instead of only with 3 like SQL does.
    """
    def __init__(self, value, field=None, auto_none=True):
        super(Not, self).__init__(value, field)
        self.auto_none = auto_none

    def get_filter(self, model, field=None):
        # If implementation has a specific method use it
        if hasattr(IMPL, 'condition_not_db_filter'):
            return IMPL.condition_not_db_filter(model, self._get_field(field),
                                                self.value, self.auto_none)

        # Otherwise non negated object must adming ~ operator for not
        return ~super(Not, self).get_filter(model, field)


class Case(object):
    """Class for conditional value selection for conditional_update."""
    def __init__(self, whens, value=None, else_=None):
        self.whens = whens
        self.value = value
        self.else_ = else_

def workflow_get_all(context, filters=None):
    """Get all workflows"""
    return IMPL.workflow_get_all(context, filters)
