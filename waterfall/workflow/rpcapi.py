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
Client side of the volume workflow RPC API.
"""


from oslo_config import cfg
from oslo_log import log as logging

from waterfall import rpc


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class WorkflowAPI(rpc.RPCAPI):
    """Client side of the volume rpc API.

    API version history:

        1.0 - Initial version.
        1.1 - Changed methods to accept workflow objects instead of IDs.
        1.2 - A version that got in by mistake (without breaking anything).
        1.3 - Dummy version bump to mark start of having waterfall-workflow service
              decoupled from waterfall-volume.

        ... Mitaka supports messaging 1.3. Any changes to existing methods in
        1.x after this point should be done so that they can handle version cap
        set to 1.3.

        2.0 - Remove 1.x compatibility
    """

    RPC_API_VERSION = '1.3'
    TOPIC = CONF.workflow_topic
    BINARY = 'waterfall-workflow'

    def _compat_ver(self, current, legacy):
        if self.client.can_send_version(current):
            return current
        else:
            return legacy

    def create_workflow(self, ctxt, workflow):
        LOG.debug("create_workflow in rpcapi workflow_id %s", workflow.id)
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=workflow.host, version=version)
        cctxt.cast(ctxt, 'create_workflow', workflow=workflow)

    def restore_workflow(self, ctxt, volume_host, workflow, volume_id):
        LOG.debug("restore_workflow in rpcapi workflow_id %s", workflow.id)
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=volume_host, version=version)
        cctxt.cast(ctxt, 'restore_workflow', workflow=workflow,
                   volume_id=volume_id)

    def delete_workflow(self, ctxt, workflow):
        LOG.debug("delete_workflow  rpcapi workflow_id %s", workflow.id)
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=workflow.host, version=version)
        cctxt.cast(ctxt, 'delete_workflow', workflow=workflow)

    def export_record(self, ctxt, workflow):
        LOG.debug("export_record in rpcapi workflow_id %(id)s "
                  "on host %(host)s.",
                  {'id': workflow.id,
                   'host': workflow.host})
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=workflow.host, version=version)
        return cctxt.call(ctxt, 'export_record', workflow=workflow)

    def import_record(self,
                      ctxt,
                      host,
                      workflow,
                      workflow_service,
                      workflow_url,
                      workflow_hosts):
        LOG.debug("import_record rpcapi workflow id %(id)s "
                  "on host %(host)s for workflow_url %(url)s.",
                  {'id': workflow.id,
                   'host': host,
                   'url': workflow_url})
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=host, version=version)
        cctxt.cast(ctxt, 'import_record',
                   workflow=workflow,
                   workflow_service=workflow_service,
                   workflow_url=workflow_url,
                   workflow_hosts=workflow_hosts)

    def reset_status(self, ctxt, workflow, status):
        LOG.debug("reset_status in rpcapi workflow_id %(id)s "
                  "on host %(host)s.",
                  {'id': workflow.id,
                   'host': workflow.host})
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=workflow.host, version=version)
        return cctxt.cast(ctxt, 'reset_status', workflow=workflow, status=status)

    def check_support_to_force_delete(self, ctxt, host):
        LOG.debug("Check if workflow driver supports force delete "
                  "on host %(host)s.", {'host': host})
        version = self._compat_ver('2.0', '1.1')
        cctxt = self.client.prepare(server=host, version=version)
        return cctxt.call(ctxt, 'check_support_to_force_delete')
