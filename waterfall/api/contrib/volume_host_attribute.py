#   Copyright 2012 OpenStack Foundation
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

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil


LOG = logging.getLogger(__name__)
authorize = extensions.soft_extension_authorizer('workflow',
                                                 'workflow_host_attribute')


class WorkflowHostAttributeController(wsgi.Controller):
    def _add_workflow_host_attribute(self, req, resp_workflow):
        db_workflow = req.get_db_workflow(resp_workflow['id'])
        key = "%s:host" % Workflow_host_attribute.alias
        resp_workflow[key] = db_workflow['host']

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowHostAttributeTemplate())
            workflow = resp_obj.obj['workflow']
            self._add_workflow_host_attribute(req, workflow)

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowListHostAttributeTemplate())
            for vol in list(resp_obj.obj['workflows']):
                self._add_workflow_host_attribute(req, vol)


class Workflow_host_attribute(extensions.ExtensionDescriptor):
    """Expose host as an attribute of a workflow."""

    name = "WorkflowHostAttribute"
    alias = "os-vol-host-attr"
    namespace = ("http://docs.openstack.org/workflow/ext/"
                 "workflow_host_attribute/api/v2")
    updated = "2011-11-03T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowHostAttributeController()
        extension = extensions.ControllerExtension(self, 'workflows', controller)
        return [extension]


def make_workflow(elem):
    elem.set('{%s}host' % Workflow_host_attribute.namespace,
             '%s:host' % Workflow_host_attribute.alias)


class WorkflowHostAttributeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow', selector='workflow')
        make_workflow(root)
        alias = Workflow_host_attribute.alias
        namespace = Workflow_host_attribute.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})


class WorkflowListHostAttributeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflows')
        elem = xmlutil.SubTemplateElement(root, 'workflow', selector='workflows')
        make_workflow(elem)
        alias = Workflow_host_attribute.alias
        namespace = Workflow_host_attribute.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})
