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

import ast

from oslo_log import log as logging
from oslo_utils import uuidutils
import webob
from webob import exc

from waterfall.api import common
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _, _LI
from waterfall import utils
from waterfall import workflow as waterfall_workflow
from waterfall.workflow import utils as workflow_utils
from waterfall.workflow import workflow_types


LOG = logging.getLogger(__name__)


def _translate_attachment_detail_view(_context, vol):
    """Maps keys for attachment details view."""

    d = _translate_attachment_summary_view(_context, vol)

    # No additional data / lookups at the moment

    return d


def _translate_attachment_summary_view(_context, vol):
    """Maps keys for attachment summary view."""
    d = []
    attachments = vol.workflow_attachment
    for attachment in attachments:
        if attachment.get('attach_status') == 'attached':
            a = {'id': attachment.get('workflow_id'),
                 'attachment_id': attachment.get('id'),
                 'workflow_id': attachment.get('workflow_id'),
                 'server_id': attachment.get('instance_uuid'),
                 'host_name': attachment.get('attached_host'),
                 'device': attachment.get('mountpoint'),
                 }
            d.append(a)

    return d


def _translate_workflow_detail_view(context, vol, image_id=None):
    """Maps keys for workflows details view."""

    d = _translate_workflow_summary_view(context, vol, image_id)

    # No additional data / lookups at the moment

    return d


def _translate_workflow_summary_view(context, vol, image_id=None):
    """Maps keys for workflows summary view."""
    d = {}

    d['id'] = vol['id']
    d['status'] = vol['status']
    d['size'] = vol['size']
    d['availability_zone'] = vol['availability_zone']
    d['created_at'] = vol['created_at']

    # Need to form the string true/false explicitly here to
    # maintain our API contract
    if vol['bootable']:
        d['bootable'] = 'true'
    else:
        d['bootable'] = 'false'

    if vol['multiattach']:
        d['multiattach'] = 'true'
    else:
        d['multiattach'] = 'false'

    d['attachments'] = []
    if vol['attach_status'] == 'attached':
        d['attachments'] = _translate_attachment_detail_view(context, vol)

    d['display_name'] = vol['display_name']
    d['display_description'] = vol['display_description']

    if vol['workflow_type_id'] and vol.get('workflow_type'):
        d['workflow_type'] = vol['workflow_type']['name']
    else:
        d['workflow_type'] = vol['workflow_type_id']

    d['snapshot_id'] = vol['snapshot_id']
    d['source_volid'] = vol['source_volid']

    d['encrypted'] = vol['encryption_key_id'] is not None

    if image_id:
        d['image_id'] = image_id

    LOG.info(_LI("vol=%s"), vol, context=context)

    if vol.metadata:
        d['metadata'] = vol.metadata
    else:
        d['metadata'] = {}

    return d


def make_attachment(elem):
    elem.set('id')
    elem.set('server_id')
    elem.set('host_name')
    elem.set('workflow_id')
    elem.set('device')


def make_workflow(elem):
    elem.set('id')
    elem.set('status')
    elem.set('size')
    elem.set('availability_zone')
    elem.set('created_at')
    elem.set('display_name')
    elem.set('bootable')
    elem.set('display_description')
    elem.set('workflow_type')
    elem.set('snapshot_id')
    elem.set('source_volid')
    elem.set('multiattach')

    attachments = xmlutil.SubTemplateElement(elem, 'attachments')
    attachment = xmlutil.SubTemplateElement(attachments, 'attachment',
                                            selector='attachments')
    make_attachment(attachment)

    # Attach metadata node
    elem.append(common.MetadataTemplate())


workflow_nsmap = {None: xmlutil.XMLNS_WORKFLOW_V1, 'atom': xmlutil.XMLNS_ATOM}


class WorkflowTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow', selector='workflow')
        make_workflow(root)
        return xmlutil.MasterTemplate(root, 1, nsmap=workflow_nsmap)


class WorkflowsTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflows')
        elem = xmlutil.SubTemplateElement(root, 'workflow', selector='workflows')
        make_workflow(elem)
        return xmlutil.MasterTemplate(root, 1, nsmap=workflow_nsmap)


class CommonDeserializer(wsgi.MetadataXMLDeserializer):
    """Common deserializer to handle xml-formatted workflow requests.

       Handles standard workflow attributes as well as the optional metadata
       attribute
    """

    metadata_deserializer = common.MetadataXMLDeserializer()

    def _extract_workflow(self, node):
        """Marshal the workflow attribute of a parsed request."""
        workflow = {}
        workflow_node = self.find_first_child_named(node, 'workflow')

        attributes = ['display_name', 'display_description', 'size',
                      'workflow_type', 'availability_zone', 'imageRef',
                      'snapshot_id', 'source_volid']
        for attr in attributes:
            if workflow_node.getAttribute(attr):
                workflow[attr] = workflow_node.getAttribute(attr)

        metadata_node = self.find_first_child_named(workflow_node, 'metadata')
        if metadata_node is not None:
            workflow['metadata'] = self.extract_metadata(metadata_node)

        return workflow


class CreateDeserializer(CommonDeserializer):
    """Deserializer to handle xml-formatted create workflow requests.

       Handles standard workflow attributes as well as the optional metadata
       attribute
    """

    def default(self, string):
        """Deserialize an xml-formatted workflow create request."""
        dom = utils.safe_minidom_parse_string(string)
        workflow = self._extract_workflow(dom)
        return {'body': {'workflow': workflow}}


class WorkflowController(wsgi.Controller):
    """The Workflows API controller for the OpenStack API."""

    def __init__(self, ext_mgr):
        self.workflow_api = waterfall_workflow.API()
        self.ext_mgr = ext_mgr
        super(WorkflowController, self).__init__()

    @wsgi.serializers(xml=WorkflowTemplate)
    def show(self, req, id):
        """Return data about the given workflow."""
        context = req.environ['waterfall.context']

        try:
            vol = self.workflow_api.get(context, id, viewable_admin_meta=True)
            req.cache_db_workflow(vol)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        utils.add_visible_admin_metadata(vol)

        return {'workflow': _translate_workflow_detail_view(context, vol)}

    def delete(self, req, id):
        """Delete a workflow."""
        context = req.environ['waterfall.context']

        LOG.info(_LI("Delete workflow with id: %s"), id, context=context)

        try:
            workflow = self.workflow_api.get(context, id)
            self.workflow_api.delete(context, workflow)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)

    @wsgi.serializers(xml=WorkflowsTemplate)
    def index(self, req):
        """Returns a summary list of workflows."""
        return self._items(req, entity_maker=_translate_workflow_summary_view)

    @wsgi.serializers(xml=WorkflowsTemplate)
    def detail(self, req):
        """Returns a detailed list of workflows."""
        return self._items(req, entity_maker=_translate_workflow_detail_view)

    def _items(self, req, entity_maker):
        """Returns a list of workflows, transformed through entity_maker."""

        # pop out limit and offset , they are not search_opts
        search_opts = req.GET.copy()
        search_opts.pop('limit', None)
        search_opts.pop('offset', None)

        for k, v in search_opts.items():
            try:
                search_opts[k] = ast.literal_eval(v)
            except (ValueError, SyntaxError):
                LOG.debug('Could not evaluate value %s, assuming string', v)

        context = req.environ['waterfall.context']
        utils.remove_invalid_filter_options(context,
                                            search_opts,
                                            self._get_workflow_search_options())

        workflows = self.workflow_api.get_all(context, marker=None, limit=None,
                                          sort_keys=['created_at'],
                                          sort_dirs=['desc'],
                                          filters=search_opts,
                                          viewable_admin_meta=True)

        for workflow in workflows:
            utils.add_visible_admin_metadata(workflow)

        limited_list = common.limited(workflows.objects, req)
        req.cache_db_workflows(limited_list)

        res = [entity_maker(context, vol) for vol in limited_list]
        return {'workflows': res}

    def _image_uuid_from_href(self, image_href):
        # If the image href was generated by nova api, strip image_href
        # down to an id.
        try:
            image_uuid = image_href.split('/').pop()
        except (TypeError, AttributeError):
            msg = _("Invalid imageRef provided.")
            raise exc.HTTPBadRequest(explanation=msg)

        if not uuidutils.is_uuid_like(image_uuid):
            msg = _("Invalid imageRef provided.")
            raise exc.HTTPBadRequest(explanation=msg)

        return image_uuid

    @wsgi.serializers(xml=WorkflowTemplate)
    @wsgi.deserializers(xml=CreateDeserializer)
    def create(self, req, body):
        """Creates a new workflow."""
        if not self.is_valid_body(body, 'workflow'):
            raise exc.HTTPUnprocessableEntity()

        LOG.debug('Create workflow request body: %s', body)
        context = req.environ['waterfall.context']
        workflow = body['workflow']

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
            except exception.WorkflowTypeNotFound:
                explanation = 'Workflow type not found.'
                raise exc.HTTPNotFound(explanation=explanation)

        kwargs['metadata'] = workflow.get('metadata', None)

        snapshot_id = workflow.get('snapshot_id')
        if snapshot_id is not None:
            try:
                kwargs['snapshot'] = self.workflow_api.get_snapshot(context,
                                                                  snapshot_id)
            except exception.NotFound:
                explanation = _('snapshot id:%s not found') % snapshot_id
                raise exc.HTTPNotFound(explanation=explanation)

        else:
            kwargs['snapshot'] = None

        source_volid = workflow.get('source_volid')
        if source_volid is not None:
            try:
                kwargs['source_workflow'] = \
                    self.workflow_api.get_workflow(context,
                                               source_volid)
            except exception.NotFound:
                explanation = _('source vol id:%s not found') % source_volid
                raise exc.HTTPNotFound(explanation=explanation)
        else:
            kwargs['source_workflow'] = None

        size = workflow.get('size', None)
        if size is None and kwargs['snapshot'] is not None:
            size = kwargs['snapshot']['workflow_size']
        elif size is None and kwargs['source_workflow'] is not None:
            size = kwargs['source_workflow']['size']

        LOG.info(_LI("Create workflow of %s GB"), size, context=context)
        multiattach = workflow.get('multiattach', False)
        kwargs['multiattach'] = multiattach

        image_href = None
        image_uuid = None
        if self.ext_mgr.is_loaded('os-image-create'):
            # NOTE(jdg): misleading name "imageRef" as it's an image-id
            image_href = workflow.get('imageRef')
            if image_href is not None:
                image_uuid = self._image_uuid_from_href(image_href)
                kwargs['image_id'] = image_uuid

        kwargs['availability_zone'] = workflow.get('availability_zone', None)

        new_workflow = self.workflow_api.create(context,
                                            size,
                                            workflow.get('display_name'),
                                            workflow.get('display_description'),
                                            **kwargs)

        retval = _translate_workflow_detail_view(context, new_workflow, image_uuid)

        return {'workflow': retval}

    def _get_workflow_search_options(self):
        """Return workflow search options allowed by non-admin."""
        return ('display_name', 'status', 'metadata')

    @wsgi.serializers(xml=WorkflowTemplate)
    def update(self, req, id, body):
        """Update a workflow."""
        context = req.environ['waterfall.context']

        if not body:
            raise exc.HTTPUnprocessableEntity()

        if 'workflow' not in body:
            raise exc.HTTPUnprocessableEntity()

        workflow = body['workflow']
        update_dict = {}

        valid_update_keys = (
            'display_name',
            'display_description',
            'metadata',
        )

        for key in valid_update_keys:
            if key in workflow:
                update_dict[key] = workflow[key]

        try:
            workflow = self.workflow_api.get(context, id, viewable_admin_meta=True)
            workflow_utils.notify_about_workflow_usage(context, workflow,
                                                   'update.start')
            self.workflow_api.update(context, workflow, update_dict)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        workflow.update(update_dict)

        utils.add_visible_admin_metadata(workflow)

        workflow_utils.notify_about_workflow_usage(context, workflow,
                                               'update.end')

        return {'workflow': _translate_workflow_detail_view(context, workflow)}


def create_resource(ext_mgr):
    return wsgi.Resource(WorkflowController(ext_mgr))
