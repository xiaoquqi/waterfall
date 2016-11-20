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

"""The workflow type access extension."""

from oslo_utils import uuidutils
import six
import webob

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _
from waterfall.workflow import workflow_types


soft_authorize = extensions.soft_extension_authorizer('workflow',
                                                      'workflow_type_access')
authorize = extensions.extension_authorizer('workflow', 'workflow_type_access')


def make_workflow_type(elem):
    elem.set('{%s}is_public' % Workflow_type_access.namespace,
             '%s:is_public' % Workflow_type_access.alias)


def make_workflow_type_access(elem):
    elem.set('workflow_type_id')
    elem.set('project_id')


class WorkflowTypeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow_type', selector='workflow_type')
        make_workflow_type(root)
        alias = Workflow_type_access.alias
        namespace = Workflow_type_access.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})


class WorkflowTypesTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow_types')
        elem = xmlutil.SubTemplateElement(
            root, 'workflow_type', selector='workflow_types')
        make_workflow_type(elem)
        alias = Workflow_type_access.alias
        namespace = Workflow_type_access.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})


class WorkflowTypeAccessTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow_type_access')
        elem = xmlutil.SubTemplateElement(root, 'access',
                                          selector='workflow_type_access')
        make_workflow_type_access(elem)
        return xmlutil.MasterTemplate(root, 1)


def _marshall_workflow_type_access(vol_type):
    rval = []
    for project_id in vol_type['projects']:
        rval.append({'workflow_type_id': vol_type['id'],
                     'project_id': project_id})

    return {'workflow_type_access': rval}


class WorkflowTypeAccessController(object):
    """The workflow type access API controller for the OpenStack API."""

    def __init__(self):
        super(WorkflowTypeAccessController, self).__init__()

    @wsgi.serializers(xml=WorkflowTypeAccessTemplate)
    def index(self, req, type_id):
        context = req.environ['waterfall.context']
        authorize(context)

        try:
            vol_type = workflow_types.get_workflow_type(
                context, type_id, expected_fields=['projects'])
        except exception.WorkflowTypeNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        if vol_type['is_public']:
            expl = _("Access list not available for public workflow types.")
            raise webob.exc.HTTPNotFound(explanation=expl)

        return _marshall_workflow_type_access(vol_type)


class WorkflowTypeActionController(wsgi.Controller):
    """The workflow type access API controller for the OpenStack API."""

    def _check_body(self, body, action_name):
        self.assert_valid_body(body, action_name)
        access = body[action_name]
        project = access.get('project')
        if not uuidutils.is_uuid_like(project):
            msg = _("Bad project format: "
                    "project is not in proper format (%s)") % project
            raise webob.exc.HTTPBadRequest(explanation=msg)

    def _extend_vol_type(self, vol_type_rval, vol_type_ref):
        if vol_type_ref:
            key = "%s:is_public" % (Workflow_type_access.alias)
            vol_type_rval[key] = vol_type_ref.get('is_public', True)

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['waterfall.context']
        if soft_authorize(context):
            # Attach our slave template to the response object
            resp_obj.attach(xml=WorkflowTypeTemplate())
            vol_type = req.cached_resource_by_id(id, name='types')
            self._extend_vol_type(resp_obj.obj['workflow_type'], vol_type)

    @wsgi.extends
    def index(self, req, resp_obj):
        context = req.environ['waterfall.context']
        if soft_authorize(context):
            # Attach our slave template to the response object
            resp_obj.attach(xml=WorkflowTypesTemplate())
            for vol_type_rval in list(resp_obj.obj['workflow_types']):
                type_id = vol_type_rval['id']
                vol_type = req.cached_resource_by_id(type_id, name='types')
                self._extend_vol_type(vol_type_rval, vol_type)

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['waterfall.context']
        if soft_authorize(context):
            # Attach our slave template to the response object
            resp_obj.attach(xml=WorkflowTypesTemplate())
            for vol_type_rval in list(resp_obj.obj['workflow_types']):
                type_id = vol_type_rval['id']
                vol_type = req.cached_resource_by_id(type_id, name='types')
                self._extend_vol_type(vol_type_rval, vol_type)

    @wsgi.extends(action='create')
    def create(self, req, body, resp_obj):
        context = req.environ['waterfall.context']
        if soft_authorize(context):
            # Attach our slave template to the response object
            resp_obj.attach(xml=WorkflowTypeTemplate())
            type_id = resp_obj.obj['workflow_type']['id']
            vol_type = req.cached_resource_by_id(type_id, name='types')
            self._extend_vol_type(resp_obj.obj['workflow_type'], vol_type)

    @wsgi.action('addProjectAccess')
    def _addProjectAccess(self, req, id, body):
        context = req.environ['waterfall.context']
        authorize(context, action="addProjectAccess")
        self._check_body(body, 'addProjectAccess')
        project = body['addProjectAccess']['project']

        try:
            workflow_types.add_workflow_type_access(context, id, project)
        except exception.WorkflowTypeAccessExists as err:
            raise webob.exc.HTTPConflict(explanation=six.text_type(err))
        except exception.WorkflowTypeNotFound as err:
            raise webob.exc.HTTPNotFound(explanation=six.text_type(err))
        return webob.Response(status_int=202)

    @wsgi.action('removeProjectAccess')
    def _removeProjectAccess(self, req, id, body):
        context = req.environ['waterfall.context']
        authorize(context, action="removeProjectAccess")
        self._check_body(body, 'removeProjectAccess')
        project = body['removeProjectAccess']['project']

        try:
            workflow_types.remove_workflow_type_access(context, id, project)
        except (exception.WorkflowTypeNotFound,
                exception.WorkflowTypeAccessNotFound) as err:
            raise webob.exc.HTTPNotFound(explanation=six.text_type(err))
        return webob.Response(status_int=202)


class Workflow_type_access(extensions.ExtensionDescriptor):
    """Workflow type access support."""

    name = "WorkflowTypeAccess"
    alias = "os-workflow-type-access"
    namespace = ("http://docs.openstack.org/workflow/"
                 "ext/os-workflow-type-access/api/v1")
    updated = "2014-06-26T00:00:00Z"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
            Workflow_type_access.alias,
            WorkflowTypeAccessController(),
            parent=dict(member_name='type', collection_name='types'))
        resources.append(res)
        return resources

    def get_controller_extensions(self):
        controller = WorkflowTypeActionController()
        extension = extensions.ControllerExtension(self, 'types', controller)
        return [extension]
