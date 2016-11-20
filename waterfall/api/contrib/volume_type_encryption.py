# Copyright (c) 2013 The Johns Hopkins University/Applied Physics Laboratory
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

"""The workflow types encryption extension."""

import webob

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import db
from waterfall import exception
from waterfall.i18n import _
from waterfall import rpc
from waterfall import utils
from waterfall.workflow import workflow_types

authorize = extensions.extension_authorizer('workflow',
                                            'workflow_type_encryption')

CONTROL_LOCATION = ['front-end', 'back-end']


class WorkflowTypeEncryptionTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.make_flat_dict('encryption', selector='encryption')
        return xmlutil.MasterTemplate(root, 1)


class WorkflowTypeEncryptionController(wsgi.Controller):
    """The workflow type encryption API controller for the OpenStack API."""

    def _get_workflow_type_encryption(self, context, type_id):
        encryption_ref = db.workflow_type_encryption_get(context, type_id)
        encryption_specs = {}
        if not encryption_ref:
            return encryption_specs
        for key, value in encryption_ref.items():
            encryption_specs[key] = value
        return encryption_specs

    def _check_type(self, context, type_id):
        try:
            workflow_types.get_workflow_type(context, type_id)
        except exception.WorkflowTypeNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.msg)

    def _check_encryption_input(self, encryption, create=True):
        if encryption.get('key_size') is not None:
            encryption['key_size'] = utils.validate_integer(
                encryption['key_size'], 'key_size',
                min_value=0, max_value=db.MAX_INT)

        if create:
            msg = None
            if 'provider' not in encryption.keys():
                msg = _('provider must be defined')
            elif 'control_location' not in encryption.keys():
                msg = _('control_location must be defined')

            if msg is not None:
                raise exception.InvalidInput(reason=msg)

        # Check control location
        if 'control_location' in encryption.keys():
            if encryption['control_location'] not in CONTROL_LOCATION:
                msg = _("Valid control location are: %s") % CONTROL_LOCATION
                raise exception.InvalidInput(reason=msg)

    def _encrypted_type_in_use(self, context, workflow_type_id):
        workflow_list = db.workflow_type_encryption_workflow_get(context,
                                                           workflow_type_id)
        # If there is at least one workflow in the list
        # returned, this type is in use by a workflow.
        if len(workflow_list) > 0:
            return True
        else:
            return False

    @wsgi.serializers(xml=WorkflowTypeEncryptionTemplate)
    def index(self, req, type_id):
        """Returns the encryption specs for a given workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)
        self._check_type(context, type_id)
        return self._get_workflow_type_encryption(context, type_id)

    @wsgi.serializers(xml=WorkflowTypeEncryptionTemplate)
    def create(self, req, type_id, body=None):
        """Create encryption specs for an existing workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)

        if self._encrypted_type_in_use(context, type_id):
            expl = _('Cannot create encryption specs. Workflow type in use.')
            raise webob.exc.HTTPBadRequest(explanation=expl)

        self.assert_valid_body(body, 'encryption')

        self._check_type(context, type_id)

        encryption_specs = self._get_workflow_type_encryption(context, type_id)
        if encryption_specs:
            raise exception.WorkflowTypeEncryptionExists(type_id=type_id)

        encryption_specs = body['encryption']

        self._check_encryption_input(encryption_specs)

        db.workflow_type_encryption_create(context, type_id, encryption_specs)
        notifier_info = dict(type_id=type_id, specs=encryption_specs)
        notifier = rpc.get_notifier('workflowTypeEncryption')
        notifier.info(context, 'workflow_type_encryption.create', notifier_info)
        return body

    @wsgi.serializers(xml=WorkflowTypeEncryptionTemplate)
    def update(self, req, type_id, id, body=None):
        """Update encryption specs for a given workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)

        self.assert_valid_body(body, 'encryption')

        if len(body) > 1:
            expl = _('Request body contains too many items.')
            raise webob.exc.HTTPBadRequest(explanation=expl)

        self._check_type(context, type_id)

        if self._encrypted_type_in_use(context, type_id):
            expl = _('Cannot update encryption specs. Workflow type in use.')
            raise webob.exc.HTTPBadRequest(explanation=expl)

        encryption_specs = body['encryption']
        self._check_encryption_input(encryption_specs, create=False)

        db.workflow_type_encryption_update(context, type_id, encryption_specs)
        notifier_info = dict(type_id=type_id, id=id)
        notifier = rpc.get_notifier('workflowTypeEncryption')
        notifier.info(context, 'workflow_type_encryption.update', notifier_info)

        return body

    @wsgi.serializers(xml=WorkflowTypeEncryptionTemplate)
    def show(self, req, type_id, id):
        """Return a single encryption item."""
        context = req.environ['waterfall.context']
        authorize(context)

        self._check_type(context, type_id)

        encryption_specs = self._get_workflow_type_encryption(context, type_id)

        if id not in encryption_specs:
            raise webob.exc.HTTPNotFound()

        return {id: encryption_specs[id]}

    def delete(self, req, type_id, id):
        """Delete encryption specs for a given workflow type."""
        context = req.environ['waterfall.context']
        authorize(context)

        if self._encrypted_type_in_use(context, type_id):
            expl = _('Cannot delete encryption specs. Workflow type in use.')
            raise webob.exc.HTTPBadRequest(explanation=expl)
        else:
            try:
                db.workflow_type_encryption_delete(context, type_id)
            except exception.WorkflowTypeEncryptionNotFound as ex:
                raise webob.exc.HTTPNotFound(explanation=ex.msg)

        return webob.Response(status_int=202)


class Workflow_type_encryption(extensions.ExtensionDescriptor):
    """Encryption support for workflow types."""

    name = "WorkflowTypeEncryption"
    alias = "encryption"
    namespace = ("http://docs.openstack.org/workflow/ext/"
                 "workflow-type-encryption/api/v1")
    updated = "2013-07-01T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
            Workflow_type_encryption.alias,
            WorkflowTypeEncryptionController(),
            parent=dict(member_name='type', collection_name='types'))
        resources.append(res)
        return resources

    def get_controller_extensions(self):
        controller = WorkflowTypeEncryptionController()
        extension = extensions.ControllerExtension(self, 'types', controller)
        return [extension]
