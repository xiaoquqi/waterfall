# Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
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

"""
Workflow manager manages volume workflows.

Volume Workflows are full copies of persistent volumes stored in a workflow
store e.g. an object store or any other workflow store if and when support is
added. They are usable without the original object being available. A
volume workflow can be restored to the original volume it was created from or
any other available volume with a minimum size of the original volume.
Volume workflows can be created, restored, deleted and listed.

**Related Flags**

:workflow_topic:  What :mod:`rpc` topic to listen to (default:
                        `waterfall-workflow`).
:workflow_manager:  The module name of a class derived from
                          :class:`manager.Manager` (default:
                          :class:`waterfall.workflow.manager.Manager`).

"""

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_service import periodic_task
from oslo_utils import excutils
from oslo_utils import importutils
import six

from waterfall.workflow import driver
from waterfall.workflow import rpcapi as workflow_rpcapi
from waterfall import context
from waterfall import exception
from waterfall.i18n import _, _LE, _LI, _LW
from waterfall import manager
from waterfall import objects
from waterfall.objects import fields
from waterfall import quota
from waterfall import rpc
from waterfall import utils

LOG = logging.getLogger(__name__)

workflow_manager_opts = [
    cfg.StrOpt('workflow_driver',
               default='waterfall.workflow.drivers.simple.SimpleDriver',
               help='Driver to use for workflows.',),
]


CONF = cfg.CONF
CONF.register_opts(workflow_manager_opts)


class WorkflowManager(manager.SchedulerDependentManager):
    """Manages workflow of block storage devices."""

    RPC_API_VERSION = '1.0'

    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, service_name=None, *args, **kwargs):
        self.service = importutils.import_object(self.driver_name)
        self.workflow_rpcapi = workflow_rpcapi.WorkflowAPI()
        super(WorkflowManager, self).__init__(service_name='workflow',
                                            *args, **kwargs)

    @property
    def driver_name(self):
        """This function maps old workflow services to workflow drivers."""

        return CONF.workflow_driver

    @periodic_task.periodic_task(spacing=60)
    def period_test(self, context):
        LOG.debug("period task debuging")

    def apply(self, context, workflow):
        """Apply resource"""
        LOG.debug(workflow)
        LOG.debug("apply is called")
        LOG.debug(self.service)
        self.service.apply()
