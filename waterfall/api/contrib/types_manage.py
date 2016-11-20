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

"""The workflow types manage extension."""

import six
import webob

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api.v1 import types
from waterfall.api.views import types as views_types
from waterfall import exception
from waterfall.i18n import _
from waterfall import rpc
from waterfall import utils
from waterfall.workflow import workflow_types


authorize = extensions.extension_authorizer('workflow', 'types_manage')


class WorkflowTypesManageController(wsgi.Controller):
    """The workflow types API controller for the OpenStack API."""

    _view_builder_class = views_types.ViewBuilder

    def _notify_workflow_type_error(self, context, method, err,
                                  workflow_type=None, id=None, name=None):
        payload = dict(
            workflow_types=workflow_type, name=name, id=id, error_message=err)
        rpc.get_notifier('workflowType').error(context, method, payload)

    def _notify_workflow_type_info(self, context, method, workflow_type):
        payload = dict(workflow_types=workflow_type)
        rpc.get_notifier('workflowType').info(context, method, payload)

    @wsgi.action("create")
    @wsgi.serializers(xml=types.WorkflowTypeTemplate)
    def _create(self, req, body):
        """Creates a new workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)

        self.assert_valid_body(body, 'workflow_type')

        vol_type = body['workflow_type']
        name = vol_type.get('name', None)
        description = vol_type.get('description')
        specs = vol_type.get('extra_specs', {})
        is_public = vol_type.get('os-workflow-type-access:is_public', True)

        if name is None or len(name.strip()) == 0:
            msg = _("Workflow type name can not be empty.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        utils.check_string_length(name, 'Type name',
                                  min_length=1, max_length=255)

        if description is not None:
            utils.check_string_length(description, 'Type description',
                                      min_length=0, max_length=255)

        if not utils.is_valid_boolstr(is_public):
            msg = _("Invalid value '%s' for is_public. Accepted values: "
                    "True or False.") % is_public
            raise webob.exc.HTTPBadRequest(explanation=msg)

        try:
            workflow_types.create(context,
                                name,
                                specs,
                                is_public,
                                description=description)
            vol_type = workflow_types.get_workflow_type_by_name(context, name)
            req.cache_resource(vol_type, name='types')
            self._notify_workflow_type_info(
                context, 'workflow_type.create', vol_type)

        except exception.WorkflowTypeExists as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.create', err, workflow_type=vol_type)
            raise webob.exc.HTTPConflict(explanation=six.text_type(err))
        except exception.WorkflowTypeNotFoundByName as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.create', err, name=name)
            raise webob.exc.HTTPNotFound(explanation=err.msg)

        return self._view_builder.show(req, vol_type)

    @wsgi.action("update")
    @wsgi.serializers(xml=types.WorkflowTypeTemplate)
    def _update(self, req, id, body):
        # Update description for a given workflow type.
        context = req.environ['waterfall.context']
        authorize(context)

        self.assert_valid_body(body, 'workflow_type')

        vol_type = body['workflow_type']
        description = vol_type.get('description')
        name = vol_type.get('name')
        is_public = vol_type.get('is_public')

        # Name and description can not be both None.
        # If name specified, name can not be empty.
        if name and len(name.strip()) == 0:
            msg = _("Workflow type name can not be empty.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        if name is None and description is None and is_public is None:
            msg = _("Specify workflow type name, description, is_public or "
                    "a combination thereof.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        if is_public is not None and not utils.is_valid_boolstr(is_public):
            msg = _("Invalid value '%s' for is_public. Accepted values: "
                    "True or False.") % is_public
            raise webob.exc.HTTPBadRequest(explanation=msg)

        if name:
            utils.check_string_length(name, 'Type name',
                                      min_length=1, max_length=255)

        if description is not None:
            utils.check_string_length(description, 'Type description',
                                      min_length=0, max_length=255)

        try:
            workflow_types.update(context, id, name, description,
                                is_public=is_public)
            # Get the updated
            vol_type = workflow_types.get_workflow_type(context, id)
            req.cache_resource(vol_type, name='types')
            self._notify_workflow_type_info(
                context, 'workflow_type.update', vol_type)

        except exception.WorkflowTypeNotFound as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.update', err, id=id)
            raise webob.exc.HTTPNotFound(explanation=six.text_type(err))
        except exception.WorkflowTypeExists as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.update', err, workflow_type=vol_type)
            raise webob.exc.HTTPConflict(explanation=six.text_type(err))
        except exception.WorkflowTypeUpdateFailed as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.update', err, workflow_type=vol_type)
            raise webob.exc.HTTPInternalServerError(
                explanation=six.text_type(err))

        return self._view_builder.show(req, vol_type)

    @wsgi.action("delete")
    def _delete(self, req, id):
        """Deletes an existing workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)

        try:
            vol_type = workflow_types.get_workflow_type(context, id)
            workflow_types.destroy(context, vol_type['id'])
            self._notify_workflow_type_info(
                context, 'workflow_type.delete', vol_type)
        except exception.WorkflowTypeInUse as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.delete', err, workflow_type=vol_type)
            msg = _('Target workflow type is still in use.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        except exception.WorkflowTypeNotFound as err:
            self._notify_workflow_type_error(
                context, 'workflow_type.delete', err, id=id)
            raise webob.exc.HTTPNotFound(explanation=err.msg)

        return webob.Response(status_int=202)


class Types_manage(extensions.ExtensionDescriptor):
    """Types manage support."""

    name = "TypesManage"
    alias = "os-types-manage"
    namespace = "http://docs.openstack.org/workflow/ext/types-manage/api/v1"
    updated = "2011-08-24T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowTypesManageController()
        extension = extensions.ControllerExtension(self, 'types', controller)
        return [extension]
