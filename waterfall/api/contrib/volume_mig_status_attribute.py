#   Copyright 2013 IBM Corp.
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
                                                 'workflow_mig_status_attribute')


class WorkflowMigStatusAttributeController(wsgi.Controller):
    def _add_workflow_mig_status_attribute(self, req, resp_workflow):
        db_workflow = req.get_db_workflow(resp_workflow['id'])
        key = "%s:migstat" % Workflow_mig_status_attribute.alias
        resp_workflow[key] = db_workflow['migration_status']
        key = "%s:name_id" % Workflow_mig_status_attribute.alias
        resp_workflow[key] = db_workflow['_name_id']

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowMigStatusAttributeTemplate())
            self._add_workflow_mig_status_attribute(req, resp_obj.obj['workflow'])

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowListMigStatusAttributeTemplate())
            for vol in list(resp_obj.obj['workflows']):
                self._add_workflow_mig_status_attribute(req, vol)


class Workflow_mig_status_attribute(extensions.ExtensionDescriptor):
    """Expose migration_status as an attribute of a workflow."""

    name = "WorkflowMigStatusAttribute"
    alias = "os-vol-mig-status-attr"
    namespace = ("http://docs.openstack.org/workflow/ext/"
                 "workflow_mig_status_attribute/api/v1")
    updated = "2013-08-08T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowMigStatusAttributeController()
        extension = extensions.ControllerExtension(self, 'workflows', controller)
        return [extension]


def make_workflow(elem):
    elem.set('{%s}migstat' % Workflow_mig_status_attribute.namespace,
             '%s:migstat' % Workflow_mig_status_attribute.alias)
    elem.set('{%s}name_id' % Workflow_mig_status_attribute.namespace,
             '%s:name_id' % Workflow_mig_status_attribute.alias)


class WorkflowMigStatusAttributeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow', selector='workflow')
        make_workflow(root)
        alias = Workflow_mig_status_attribute.alias
        namespace = Workflow_mig_status_attribute.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})


class WorkflowListMigStatusAttributeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflows')
        elem = xmlutil.SubTemplateElement(root, 'workflow', selector='workflows')
        make_workflow(elem)
        alias = Workflow_mig_status_attribute.alias
        namespace = Workflow_mig_status_attribute.namespace
        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})
