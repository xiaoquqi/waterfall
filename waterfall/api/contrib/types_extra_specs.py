# Copyright (c) 2011 Zadara Storage Inc.
# Copyright (c) 2011 OpenStack Foundation
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

"""The workflow types extra specs extension"""

import webob

from waterfall.api import common
from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import db
from waterfall import exception
from waterfall.i18n import _
from waterfall import rpc
from waterfall.workflow import workflow_types

authorize = extensions.extension_authorizer('workflow', 'types_extra_specs')


class WorkflowTypeExtraSpecsTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.make_flat_dict('extra_specs', selector='extra_specs')
        return xmlutil.MasterTemplate(root, 1)


class WorkflowTypeExtraSpecTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        tagname = xmlutil.Selector('key')

        def extraspec_sel(obj, do_raise=False):
            # Have to extract the key and value for later use...
            key, value = list(obj.items())[0]
            return dict(key=key, value=value)

        root = xmlutil.TemplateElement(tagname, selector=extraspec_sel)
        root.text = 'value'
        return xmlutil.MasterTemplate(root, 1)


class WorkflowTypeExtraSpecsController(wsgi.Controller):
    """The workflow type extra specs API controller for the OpenStack API."""

    def _get_extra_specs(self, context, type_id):
        extra_specs = db.workflow_type_extra_specs_get(context, type_id)
        specs_dict = {}
        for key, value in extra_specs.items():
            specs_dict[key] = value
        return dict(extra_specs=specs_dict)

    def _check_type(self, context, type_id):
        try:
            workflow_types.get_workflow_type(context, type_id)
        except exception.WorkflowTypeNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.msg)

    @wsgi.serializers(xml=WorkflowTypeExtraSpecsTemplate)
    def index(self, req, type_id):
        """Returns the list of extra specs for a given workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)
        self._check_type(context, type_id)
        return self._get_extra_specs(context, type_id)

    def _validate_extra_specs(self, specs):
        """Validating key and value of extra specs."""
        for key, value in specs.items():
            if key is not None:
                self.validate_string_length(key, 'Key "%s"' % key,
                                            min_length=1, max_length=255)

            if value is not None:
                self.validate_string_length(value, 'Value for key "%s"' % key,
                                            min_length=0, max_length=255)

    @wsgi.serializers(xml=WorkflowTypeExtraSpecsTemplate)
    def create(self, req, type_id, body=None):
        context = req.environ['waterfall.context']
        authorize(context)

        self.assert_valid_body(body, 'extra_specs')

        self._check_type(context, type_id)
        specs = body['extra_specs']
        self._check_key_names(specs.keys())
        self._validate_extra_specs(specs)

        db.workflow_type_extra_specs_update_or_create(context,
                                                    type_id,
                                                    specs)
        notifier_info = dict(type_id=type_id, specs=specs)
        notifier = rpc.get_notifier('workflowTypeExtraSpecs')
        notifier.info(context, 'workflow_type_extra_specs.create',
                      notifier_info)
        return body

    @wsgi.serializers(xml=WorkflowTypeExtraSpecTemplate)
    def update(self, req, type_id, id, body=None):
        context = req.environ['waterfall.context']
        authorize(context)
        if not body:
            expl = _('Request body empty')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        self._check_type(context, type_id)
        if id not in body:
            expl = _('Request body and URI mismatch')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        if len(body) > 1:
            expl = _('Request body contains too many items')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        self._check_key_names(body.keys())
        self._validate_extra_specs(body)

        db.workflow_type_extra_specs_update_or_create(context,
                                                    type_id,
                                                    body)
        notifier_info = dict(type_id=type_id, id=id)
        notifier = rpc.get_notifier('workflowTypeExtraSpecs')
        notifier.info(context,
                      'workflow_type_extra_specs.update',
                      notifier_info)
        return body

    @wsgi.serializers(xml=WorkflowTypeExtraSpecTemplate)
    def show(self, req, type_id, id):
        """Return a single extra spec item."""
        context = req.environ['waterfall.context']
        authorize(context)
        self._check_type(context, type_id)
        specs = self._get_extra_specs(context, type_id)
        if id in specs['extra_specs']:
            return {id: specs['extra_specs'][id]}
        else:
            msg = _("Workflow Type %(type_id)s has no extra spec with key "
                    "%(id)s.") % ({'type_id': type_id, 'id': id})
            raise webob.exc.HTTPNotFound(explanation=msg)

    def delete(self, req, type_id, id):
        """Deletes an existing extra spec."""
        context = req.environ['waterfall.context']
        self._check_type(context, type_id)
        authorize(context)

        try:
            db.workflow_type_extra_specs_delete(context, type_id, id)
        except exception.WorkflowTypeExtraSpecsNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        notifier_info = dict(type_id=type_id, id=id)
        notifier = rpc.get_notifier('workflowTypeExtraSpecs')
        notifier.info(context,
                      'workflow_type_extra_specs.delete',
                      notifier_info)
        return webob.Response(status_int=202)

    def _check_key_names(self, keys):
        if not common.validate_key_names(keys):
            expl = _('Key names can only contain alphanumeric characters, '
                     'underscores, periods, colons and hyphens.')

            raise webob.exc.HTTPBadRequest(explanation=expl)


class Types_extra_specs(extensions.ExtensionDescriptor):
    """Type extra specs support."""

    name = "TypesExtraSpecs"
    alias = "os-types-extra-specs"
    namespace = "http://docs.openstack.org/workflow/ext/types-extra-specs/api/v1"
    updated = "2011-08-24T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension('extra_specs',
                                           WorkflowTypeExtraSpecsController(),
                                           parent=dict(member_name='type',
                                                       collection_name='types')
                                           )
        resources.append(res)

        return resources
