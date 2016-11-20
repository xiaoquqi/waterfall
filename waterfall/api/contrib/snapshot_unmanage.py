#   Copyright 2015 Huawei Technologies Co., Ltd.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

from oslo_log import log as logging
import webob
from webob import exc

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall import exception
from waterfall.i18n import _LI
from waterfall import workflow

LOG = logging.getLogger(__name__)
authorize = extensions.extension_authorizer('snapshot', 'snapshot_unmanage')


class SnapshotUnmanageController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(SnapshotUnmanageController, self).__init__(*args, **kwargs)
        self.workflow_api = workflow.API()

    @wsgi.response(202)
    @wsgi.action('os-unmanage')
    def unmanage(self, req, id, body):
        """Stop managing a snapshot.

        This action is very much like a delete, except that a different
        method (unmanage) is called on the Waterfall driver.  This has the effect
        of removing the snapshot from Waterfall management without actually
        removing the backend storage object associated with it.

        There are no required parameters.

        A Not Found error is returned if the specified snapshot does not exist.
        """
        context = req.environ['waterfall.context']
        authorize(context)

        LOG.info(_LI("Unmanage snapshot with id: %s"), id, context=context)

        try:
            snapshot = self.workflow_api.get_snapshot(context, id)
            self.workflow_api.delete_snapshot(context, snapshot,
                                            unmanage_only=True)
        except exception.SnapshotNotFound as ex:
            raise exc.HTTPNotFound(explanation=ex.msg)
        except exception.InvalidSnapshot as ex:
            raise exc.HTTPBadRequest(explanation=ex.msg)
        return webob.Response(status_int=202)


class Snapshot_unmanage(extensions.ExtensionDescriptor):
    """Enable workflow unmanage operation."""

    name = "SnapshotUnmanage"
    alias = "os-snapshot-unmanage"
    namespace = ('http://docs.openstack.org/snapshot/ext/snapshot-unmanage'
                 '/api/v1')
    updated = "2014-12-31T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = SnapshotUnmanageController()
        extension = extensions.ControllerExtension(self, 'snapshots',
                                                   controller)
        return [extension]
