# Copyright 2011 Justin Santa Barbara
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

"""The workflows api."""


from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import uuidutils
import webob
from webob import exc

from waterfall.api import common
from waterfall.api.openstack import wsgi
from waterfall.api.v2.views import workflows as workflow_views
from waterfall import exception
from waterfall.i18n import _, _LI
from waterfall import utils
from waterfall.workflow import api as workflow_api

CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class WorkflowController(wsgi.Controller):
    """The Workflows API controller for the OpenStack API."""

    _view_builder_class = workflow_views.ViewBuilder

    def __init__(self, ext_mgr):
        self.workflow_api = workflow_api.API()
        self.ext_mgr = ext_mgr
        super(WorkflowController, self).__init__()

    def index(self, req):
        """Returns a summary list of workflows."""
        context = req.environ['waterfall.context']
        workflows = self.workflow_api.workflow_get_all(context)
        return self._view_builder.detail_list(req, workflows)

    @wsgi.response(202)
    def create(self, req, body):
        context = req.environ['waterfall.context']
        workflow = body['workflow']

        resource_type = workflow.get("resource_type")
        payload = workflow.get("payload")
        workflow = self.workflow_api.workflow_create(
                context, resource_type, payload)
        retval = self._view_builder.detail(req, workflow)
        return retval


def create_resource(ext_mgr):
    return wsgi.Resource(WorkflowController(ext_mgr))
