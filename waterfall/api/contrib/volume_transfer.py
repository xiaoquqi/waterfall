# Copyright 2011 OpenStack Foundation
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

from oslo_log import log as logging
import webob
from webob import exc

from waterfall.api import common
from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api.views import transfers as transfer_view
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _, _LI
from waterfall import transfer as transferAPI
from waterfall import utils

LOG = logging.getLogger(__name__)


def make_transfer(elem):
    elem.set('id')
    elem.set('workflow_id')
    elem.set('created_at')
    elem.set('name')
    elem.set('auth_key')


class TransferTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('transfer', selector='transfer')
        make_transfer(root)
        alias = Workflow_transfer.alias
        namespace = Workflow_transfer.namespace
        return xmlutil.MasterTemplate(root, 1, nsmap={alias: namespace})


class TransfersTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('transfers')
        elem = xmlutil.SubTemplateElement(root, 'transfer',
                                          selector='transfers')
        make_transfer(elem)
        alias = Workflow_transfer.alias
        namespace = Workflow_transfer.namespace
        return xmlutil.MasterTemplate(root, 1, nsmap={alias: namespace})


class CreateDeserializer(wsgi.MetadataXMLDeserializer):
    def default(self, string):
        dom = utils.safe_minidom_parse_string(string)
        transfer = self._extract_transfer(dom)
        return {'body': {'transfer': transfer}}

    def _extract_transfer(self, node):
        transfer = {}
        transfer_node = self.find_first_child_named(node, 'transfer')

        attributes = ['workflow_id', 'name']

        for attr in attributes:
            if transfer_node.getAttribute(attr):
                transfer[attr] = transfer_node.getAttribute(attr)
        return transfer


class AcceptDeserializer(wsgi.MetadataXMLDeserializer):
    def default(self, string):
        dom = utils.safe_minidom_parse_string(string)
        transfer = self._extract_transfer(dom)
        return {'body': {'accept': transfer}}

    def _extract_transfer(self, node):
        transfer = {}
        transfer_node = self.find_first_child_named(node, 'accept')

        attributes = ['auth_key']

        for attr in attributes:
            if transfer_node.getAttribute(attr):
                transfer[attr] = transfer_node.getAttribute(attr)
        return transfer


class WorkflowTransferController(wsgi.Controller):
    """The Workflow Transfer API controller for the OpenStack API."""

    _view_builder_class = transfer_view.ViewBuilder

    def __init__(self):
        self.transfer_api = transferAPI.API()
        super(WorkflowTransferController, self).__init__()

    @wsgi.serializers(xml=TransferTemplate)
    def show(self, req, id):
        """Return data about active transfers."""
        context = req.environ['waterfall.context']

        try:
            transfer = self.transfer_api.get(context, transfer_id=id)
        except exception.TransferNotFound as error:
            raise exc.HTTPNotFound(explanation=error.msg)

        return self._view_builder.detail(req, transfer)

    @wsgi.serializers(xml=TransfersTemplate)
    def index(self, req):
        """Returns a summary list of transfers."""
        return self._get_transfers(req, is_detail=False)

    @wsgi.serializers(xml=TransfersTemplate)
    def detail(self, req):
        """Returns a detailed list of transfers."""
        return self._get_transfers(req, is_detail=True)

    def _get_transfers(self, req, is_detail):
        """Returns a list of transfers, transformed through view builder."""
        context = req.environ['waterfall.context']
        filters = req.params.copy()
        LOG.debug('Listing workflow transfers')
        transfers = self.transfer_api.get_all(context, filters=filters)
        transfer_count = len(transfers)
        limited_list = common.limited(transfers, req)

        if is_detail:
            transfers = self._view_builder.detail_list(req, limited_list,
                                                       transfer_count)
        else:
            transfers = self._view_builder.summary_list(req, limited_list,
                                                        transfer_count)

        return transfers

    @wsgi.response(202)
    @wsgi.serializers(xml=TransferTemplate)
    @wsgi.deserializers(xml=CreateDeserializer)
    def create(self, req, body):
        """Create a new workflow transfer."""
        LOG.debug('Creating new workflow transfer %s', body)
        self.assert_valid_body(body, 'transfer')

        context = req.environ['waterfall.context']
        transfer = body['transfer']

        try:
            workflow_id = transfer['workflow_id']
        except KeyError:
            msg = _("Incorrect request body format")
            raise exc.HTTPBadRequest(explanation=msg)

        name = transfer.get('name', None)
        if name is not None:
            self.validate_string_length(name, 'Transfer name',
                                        min_length=1, max_length=255,
                                        remove_whitespaces=True)
            name = name.strip()

        LOG.info(_LI("Creating transfer of workflow %s"),
                 workflow_id,
                 context=context)

        try:
            new_transfer = self.transfer_api.create(context, workflow_id, name)
        except exception.InvalidWorkflow as error:
            raise exc.HTTPBadRequest(explanation=error.msg)
        except exception.WorkflowNotFound as error:
            raise exc.HTTPNotFound(explanation=error.msg)

        transfer = self._view_builder.create(req,
                                             dict(new_transfer))
        return transfer

    @wsgi.response(202)
    @wsgi.serializers(xml=TransferTemplate)
    @wsgi.deserializers(xml=AcceptDeserializer)
    def accept(self, req, id, body):
        """Accept a new workflow transfer."""
        transfer_id = id
        LOG.debug('Accepting workflow transfer %s', transfer_id)
        self.assert_valid_body(body, 'accept')

        context = req.environ['waterfall.context']
        accept = body['accept']

        try:
            auth_key = accept['auth_key']
        except KeyError:
            msg = _("Incorrect request body format")
            raise exc.HTTPBadRequest(explanation=msg)

        LOG.info(_LI("Accepting transfer %s"), transfer_id,
                 context=context)

        try:
            accepted_transfer = self.transfer_api.accept(context, transfer_id,
                                                         auth_key)
        except exception.WorkflowSizeExceedsAvailableQuota as error:
            raise exc.HTTPRequestEntityTooLarge(
                explanation=error.msg, headers={'Retry-After': '0'})
        except exception.InvalidWorkflow as error:
            raise exc.HTTPBadRequest(explanation=error.msg)

        transfer = \
            self._view_builder.summary(req,
                                       dict(accepted_transfer))
        return transfer

    def delete(self, req, id):
        """Delete a transfer."""
        context = req.environ['waterfall.context']

        LOG.info(_LI("Delete transfer with id: %s"), id, context=context)

        try:
            self.transfer_api.delete(context, transfer_id=id)
        except exception.TransferNotFound as error:
            raise exc.HTTPNotFound(explanation=error.msg)
        return webob.Response(status_int=202)


class Workflow_transfer(extensions.ExtensionDescriptor):
    """Workflow transfer management support."""

    name = "WorkflowTransfer"
    alias = "os-workflow-transfer"
    namespace = "http://docs.openstack.org/workflow/ext/workflow-transfer/" + \
                "api/v1.1"
    updated = "2013-05-29T00:00:00+00:00"

    def get_resources(self):
        resources = []

        res = extensions.ResourceExtension(Workflow_transfer.alias,
                                           WorkflowTransferController(),
                                           collection_actions={'detail':
                                                               'GET'},
                                           member_actions={'accept': 'POST'})
        resources.append(res)
        return resources
