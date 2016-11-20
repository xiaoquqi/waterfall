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

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil


authorize = extensions.soft_extension_authorizer('workflow',
                                                 'workflow_tenant_attribute')


class WorkflowTenantAttributeController(wsgi.Controller):
    def _add_workflow_tenant_attribute(self, req, resp_workflow):
        db_workflow = req.get_db_workflow(resp_workflow['id'])
        key = "%s:tenant_id" % Workflow_tenant_attribute.alias
        resp_workflow[key] = db_workflow['project_id']

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowTenantAttributeTemplate())
            workflow = resp_obj.obj['workflow']
            self._add_workflow_tenant_attribute(req, workflow)

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowListTenantAttributeTemplate())
            for vol in list(resp_obj.obj['workflows']):
                self._add_workflow_tenant_attribute(req, vol)


class Workflow_tenant_attribute(extensions.ExtensionDescriptor):
    """Expose the internal project_id as an attribute of a workflow."""

    name = "WorkflowTenantAttribute"
    alias = "os-vol-tenant-attr"
    namespace = ("http://docs.openstack.org/workflow/ext/"
                 "workflow_tenant_attribute/api/v2")
    updated = "2011-11-03T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowTenantAttributeController()
        extension = extensions.ControllerExtension(self, 'workflows', controller)
        return [extension]


def make_workflow(elem):
    elem.set('{%s}tenant_id' % Workflow_tenant_attribute.namespace,
             '%s:tenant_id' % Workflow_tenant_attribute.alias)


class WorkflowTenantAttributeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow', selector='workflow')
        make_workflow(root)
        alias = Workflow_tenant_attribute.alias
        namespace = Workflow_tenant_attribute.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})


class WorkflowListTenantAttributeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflows')
        elem = xmlutil.SubTemplateElement(root, 'workflow', selector='workflows')
        make_workflow(elem)
        alias = Workflow_tenant_attribute.alias
        namespace = Workflow_tenant_attribute.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})
