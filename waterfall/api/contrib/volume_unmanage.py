#   Copyright 2014 IBM Corp.
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
authorize = extensions.extension_authorizer('workflow', 'workflow_unmanage')


class WorkflowUnmanageController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(WorkflowUnmanageController, self).__init__(*args, **kwargs)
        self.workflow_api = workflow.API()

    @wsgi.response(202)
    @wsgi.action('os-unmanage')
    def unmanage(self, req, id, body):
        """Stop managing a workflow.

        This action is very much like a delete, except that a different
        method (unmanage) is called on the Waterfall driver.  This has the effect
        of removing the workflow from Waterfall management without actually
        removing the backend storage object associated with it.

        There are no required parameters.

        A Not Found error is returned if the specified workflow does not exist.

        A Bad Request error is returned if the specified workflow is still
        attached to an instance.
        """
        context = req.environ['waterfall.context']
        authorize(context)

        LOG.info(_LI("Unmanage workflow with id: %s"), id, context=context)

        try:
            vol = self.workflow_api.get(context, id)
            self.workflow_api.delete(context, vol, unmanage_only=True)
        except exception.WorkflowNotFound as error:
            raise exc.HTTPNotFound(explanation=error.msg)
        return webob.Response(status_int=202)


class Workflow_unmanage(extensions.ExtensionDescriptor):
    """Enable workflow unmanage operation."""

    name = "WorkflowUnmanage"
    alias = "os-workflow-unmanage"
    namespace = "http://docs.openstack.org/workflow/ext/workflow-unmanage/api/v1.1"
    updated = "2012-05-31T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowUnmanageController()
        extension = extensions.ControllerExtension(self, 'workflows', controller)
        return [extension]
