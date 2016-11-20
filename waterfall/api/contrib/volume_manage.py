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
from oslo_utils import uuidutils
from webob import exc

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api.v2.views import workflows as workflow_views
from waterfall.api.v2 import workflows
from waterfall import exception
from waterfall.i18n import _
from waterfall import utils
from waterfall import workflow as waterfall_workflow
from waterfall.workflow import workflow_types

LOG = logging.getLogger(__name__)
authorize = extensions.extension_authorizer('workflow', 'workflow_manage')


class WorkflowManageController(wsgi.Controller):
    """The /os-workflow-manage controller for the OpenStack API."""

    _view_builder_class = workflow_views.ViewBuilder

    def __init__(self, *args, **kwargs):
        super(WorkflowManageController, self).__init__(*args, **kwargs)
        self.workflow_api = waterfall_workflow.API()

    @wsgi.response(202)
    @wsgi.serializers(xml=workflows.WorkflowTemplate)
    @wsgi.deserializers(xml=workflows.CreateDeserializer)
    def create(self, req, body):
        """Instruct Waterfall to manage a storage object.

        Manages an existing backend storage object (e.g. a Linux logical
        workflow or a SAN disk) by creating the Waterfall objects required to manage
        it, and possibly renaming the backend storage object
        (driver dependent)

        From an API perspective, this operation behaves very much like a
        workflow creation operation, except that properties such as image,
        snapshot and workflow references don't make sense, because we are taking
        an existing storage object into Waterfall management.

        Required HTTP Body:

        {
         'workflow':
          {
           'host': <Waterfall host on which the existing storage resides>,
           'ref':  <Driver-specific reference to the existing storage object>,
          }
        }

        See the appropriate Waterfall drivers' implementations of the
        manage_workflow method to find out the accepted format of 'ref'.

        This API call will return with an error if any of the above elements
        are missing from the request, or if the 'host' element refers to a
        waterfall host that is not registered.

        The workflow will later enter the error state if it is discovered that
        'ref' is bad.

        Optional elements to 'workflow' are:
            name               A name for the new workflow.
            description        A description for the new workflow.
            workflow_type        ID or name of a workflow type to associate with
                               the new Waterfall workflow.  Does not necessarily
                               guarantee that the managed workflow will have the
                               properties described in the workflow_type.  The
                               driver may choose to fail if it identifies that
                               the specified workflow_type is not compatible with
                               the backend storage object.
            metadata           Key/value pairs to be associated with the new
                               workflow.
            availability_zone  The availability zone to associate with the new
                               workflow.
            bootable           If set to True, marks the workflow as bootable.
        """
        context = req.environ['waterfall.context']
        authorize(context)

        self.assert_valid_body(body, 'workflow')

        workflow = body['workflow']
        self.validate_name_and_description(workflow)

        # Check that the required keys are present, return an error if they
        # are not.
        required_keys = set(['ref', 'host'])
        missing_keys = list(required_keys - set(workflow.keys()))

        if missing_keys:
            msg = _("The following elements are required: %s") % \
                ', '.join(missing_keys)
            raise exc.HTTPBadRequest(explanation=msg)

        LOG.debug('Manage workflow request body: %s', body)

        kwargs = {}
        req_workflow_type = workflow.get('workflow_type', None)
        if req_workflow_type:
            try:
                if not uuidutils.is_uuid_like(req_workflow_type):
                    kwargs['workflow_type'] = \
                        workflow_types.get_workflow_type_by_name(
                            context, req_workflow_type)
                else:
                    kwargs['workflow_type'] = workflow_types.get_workflow_type(
                        context, req_workflow_type)
            except exception.WorkflowTypeNotFound as error:
                raise exc.HTTPNotFound(explanation=error.msg)
        else:
            kwargs['workflow_type'] = {}

        kwargs['name'] = workflow.get('name', None)
        kwargs['description'] = workflow.get('description', None)
        kwargs['metadata'] = workflow.get('metadata', None)
        kwargs['availability_zone'] = workflow.get('availability_zone', None)
        kwargs['bootable'] = workflow.get('bootable', False)
        try:
            new_workflow = self.workflow_api.manage_existing(context,
                                                         workflow['host'],
                                                         workflow['ref'],
                                                         **kwargs)
        except exception.ServiceNotFound as error:
            raise exc.HTTPNotFound(explanation=error.msg)

        utils.add_visible_admin_metadata(new_workflow)

        return self._view_builder.detail(req, new_workflow)


class Workflow_manage(extensions.ExtensionDescriptor):
    """Allows existing backend storage to be 'managed' by Waterfall."""

    name = 'WorkflowManage'
    alias = 'os-workflow-manage'
    namespace = ('http://docs.openstack.org/workflow/ext/'
                 'os-workflow-manage/api/v1')
    updated = '2014-02-10T00:00:00+00:00'

    def get_resources(self):
        controller = WorkflowManageController()
        res = extensions.ResourceExtension(Workflow_manage.alias,
                                           controller)
        return [res]
