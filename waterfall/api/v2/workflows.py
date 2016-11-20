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


from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import uuidutils
import webob
from webob import exc

from waterfall.api import common
from waterfall.api.openstack import wsgi
from waterfall.api.v2.views import workflows as workflow_views
#from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _, _LI
from waterfall import utils
from waterfall.workflow import api as workflow_api

CONF = cfg.CONF

LOG = logging.getLogger(__name__)
#SCHEDULER_HINTS_NAMESPACE =\
#    "http://docs.openstack.org/block-service/ext/scheduler-hints/api/v2"


#def make_attachment(elem):
#    elem.set('id')
#    elem.set('attachment_id')
#    elem.set('server_id')
#    elem.set('host_name')
#    elem.set('workflow_id')
#    elem.set('device')


#def make_workflow(elem):
#    elem.set('id')
#    elem.set('status')
#    elem.set('size')
#    elem.set('availability_zone')
#    elem.set('created_at')
#    elem.set('name')
#    elem.set('bootable')
#    elem.set('description')
#    elem.set('workflow_type')
#    elem.set('snapshot_id')
#    elem.set('source_volid')
#    elem.set('consistencygroup_id')
#    elem.set('multiattach')
#
#    attachments = xmlutil.SubTemplateElement(elem, 'attachments')
#    attachment = xmlutil.SubTemplateElement(attachments, 'attachment',
#                                            selector='attachments')
#    make_attachment(attachment)
#
#    # Attach metadata node
#    elem.append(common.MetadataTemplate())


#workflow_nsmap = {None: xmlutil.XMLNS_WORKFLOW_V2, 'atom': xmlutil.XMLNS_ATOM}


#class WorkflowTemplate(xmlutil.TemplateBuilder):
#    def construct(self):
#        root = xmlutil.TemplateElement('workflow', selector='workflow')
#        make_workflow(root)
#        return xmlutil.MasterTemplate(root, 1, nsmap=workflow_nsmap)
#
#
#class WorkflowsTemplate(xmlutil.TemplateBuilder):
#    def construct(self):
#        root = xmlutil.TemplateElement('workflows')
#        elem = xmlutil.SubTemplateElement(root, 'workflow', selector='workflows')
#        make_workflow(elem)
#        return xmlutil.MasterTemplate(root, 1, nsmap=workflow_nsmap)
#
#
#class CommonDeserializer(wsgi.MetadataXMLDeserializer):
#    """Common deserializer to handle xml-formatted workflow requests.
#
#       Handles standard workflow attributes as well as the optional metadata
#       attribute
#    """
#
#    metadata_deserializer = common.MetadataXMLDeserializer()
#
#    def _extract_scheduler_hints(self, workflow_node):
#        """Marshal the scheduler hints attribute of a parsed request."""
#        node =\
#            self.find_first_child_named_in_namespace(workflow_node,
#                                                     SCHEDULER_HINTS_NAMESPACE,
#                                                     "scheduler_hints")
#        if node:
#            scheduler_hints = {}
#            for child in self.extract_elements(node):
#                scheduler_hints.setdefault(child.nodeName, [])
#                value = self.extract_text(child).strip()
#                scheduler_hints[child.nodeName].append(value)
#            return scheduler_hints
#        else:
#            return None
#
#    def _extract_workflow(self, node):
#        """Marshal the workflow attribute of a parsed request."""
#        workflow = {}
#        workflow_node = self.find_first_child_named(node, 'workflow')
#
#        attributes = ['name', 'description', 'size',
#                      'workflow_type', 'availability_zone', 'imageRef',
#                      'image_id', 'snapshot_id', 'source_volid',
#                      'consistencygroup_id']
#        for attr in attributes:
#            if workflow_node.getAttribute(attr):
#                workflow[attr] = workflow_node.getAttribute(attr)
#
#        metadata_node = self.find_first_child_named(workflow_node, 'metadata')
#        if metadata_node is not None:
#            workflow['metadata'] = self.extract_metadata(metadata_node)
#
#        scheduler_hints = self._extract_scheduler_hints(workflow_node)
#        if scheduler_hints:
#            workflow['scheduler_hints'] = scheduler_hints
#
#        return workflow


#class CreateDeserializer(CommonDeserializer):
#    """Deserializer to handle xml-formatted create workflow requests.
#
#       Handles standard workflow attributes as well as the optional metadata
#       attribute
#    """
#
#    def default(self, string):
#        """Deserialize an xml-formatted workflow create request."""
#        dom = utils.safe_minidom_parse_string(string)
#        workflow = self._extract_workflow(dom)
#        return {'body': {'workflow': workflow}}


class WorkflowController(wsgi.Controller):
    """The Workflows API controller for the OpenStack API."""

    _view_builder_class = workflow_views.ViewBuilder

    def __init__(self, ext_mgr):
        self.workflow_api = workflow_api.API()
        self.ext_mgr = ext_mgr
        super(WorkflowController, self).__init__()

    #@wsgi.serializers(xml=WorkflowTemplate)
    #def show(self, req, id):
    #    """Return data about the given workflow."""
    #    context = req.environ['waterfall.context']

    #    try:
    #        vol = self.workflow_api.get(context, id, viewable_admin_meta=True)
    #        req.cache_db_workflow(vol)
    #    except exception.WorkflowNotFound as error:
    #        raise exc.HTTPNotFound(explanation=error.msg)

    #    utils.add_visible_admin_metadata(vol)

    #    return self._view_builder.detail(req, vol)

    #def delete(self, req, id):
    #    """Delete a workflow."""
    #    context = req.environ['waterfall.context']

    #    cascade = utils.get_bool_param('cascade', req.params)

    #    LOG.info(_LI("Delete workflow with id: %s"), id, context=context)

    #    try:
    #        workflow = self.workflow_api.get(context, id)
    #        self.workflow_api.delete(context, workflow, cascade=cascade)
    #    except exception.WorkflowNotFound as error:
    #        raise exc.HTTPNotFound(explanation=error.msg)
    #    return webob.Response(status_int=202)

    #@wsgi.serializers(xml=WorkflowsTemplate)
    def index(self, req):
        """Returns a summary list of workflows."""
        context = req.environ['waterfall.context']
        #LOG.debug(db_api.workflow_get_all(context))
        workflows = self.workflow_api.workflow_get_all(context)
        return self._view_builder.detail_list(req, workflows)

    #@wsgi.serializers(xml=WorkflowsTemplate)
    def detail(self, req):
        """Returns a detailed list of workflows."""
        return self._get_workflows(req, is_detail=True)

    def _get_workflows(self, req, is_detail):
        """Returns a list of workflows, transformed through view builder."""

        context = req.environ['waterfall.context']

        params = req.params.copy()
        marker, limit, offset = common.get_pagination_params(params)
        sort_keys, sort_dirs = common.get_sort_params(params)
        filters = params

        utils.remove_invalid_filter_options(context,
                                            filters,
                                            self._get_workflow_filter_options())

        # NOTE(thingee): v2 API allows name instead of display_name
        if 'name' in sort_keys:
            sort_keys[sort_keys.index('name')] = 'display_name'

        if 'name' in filters:
            filters['display_name'] = filters['name']
            del filters['name']

        self.workflow_api.check_workflow_filters(filters)
        workflows = self.workflow_api.get_all(context, marker, limit,
                                          sort_keys=sort_keys,
                                          sort_dirs=sort_dirs,
                                          filters=filters,
                                          viewable_admin_meta=True,
                                          offset=offset)

        for workflow in workflows:
            utils.add_visible_admin_metadata(workflow)

        req.cache_db_workflows(workflows.objects)

        if is_detail:
            workflows = self._view_builder.detail_list(req, workflows)
        else:
            workflows = self._view_builder.summary_list(req, workflows)
        return workflows

    #@wsgi.response(202)
    #@wsgi.serializers(xml=WorkflowTemplate)
    #@wsgi.deserializers(xml=CreateDeserializer)
    #def create(self, req, body):
    #    """Creates a new workflow."""
    #    self.assert_valid_body(body, 'workflow')

    #    LOG.debug('Create workflow request body: %s', body)
    #    context = req.environ['waterfall.context']
    #    workflow = body['workflow']

    #    kwargs = {}
    #    self.validate_name_and_description(workflow)

    #    # NOTE(thingee): v2 API allows name instead of display_name
    #    if 'name' in workflow:
    #        workflow['display_name'] = workflow.pop('name')

    #    # NOTE(thingee): v2 API allows description instead of
    #    #                display_description
    #    if 'description' in workflow:
    #        workflow['display_description'] = workflow.pop('description')

    #    if 'image_id' in workflow:
    #        workflow['imageRef'] = workflow.get('image_id')
    #        del workflow['image_id']

    #    req_workflow_type = workflow.get('workflow_type', None)
    #    if req_workflow_type:
    #        try:
    #            if not uuidutils.is_uuid_like(req_workflow_type):
    #                kwargs['workflow_type'] = \
    #                    workflow_types.get_workflow_type_by_name(
    #                        context, req_workflow_type)
    #            else:
    #                kwargs['workflow_type'] = workflow_types.get_workflow_type(
    #                    context, req_workflow_type)
    #        except exception.WorkflowTypeNotFound as error:
    #            raise exc.HTTPNotFound(explanation=error.msg)

    #    kwargs['metadata'] = workflow.get('metadata', None)

    #    snapshot_id = workflow.get('snapshot_id')
    #    if snapshot_id is not None:
    #        try:
    #            kwargs['snapshot'] = self.workflow_api.get_snapshot(context,
    #                                                              snapshot_id)
    #        except exception.SnapshotNotFound as error:
    #            raise exc.HTTPNotFound(explanation=error.msg)
    #    else:
    #        kwargs['snapshot'] = None

    #    source_volid = workflow.get('source_volid')
    #    if source_volid is not None:
    #        try:
    #            kwargs['source_workflow'] = \
    #                self.workflow_api.get_workflow(context,
    #                                           source_volid)
    #        except exception.WorkflowNotFound as error:
    #            raise exc.HTTPNotFound(explanation=error.msg)
    #    else:
    #        kwargs['source_workflow'] = None

    #    source_replica = workflow.get('source_replica')
    #    if source_replica is not None:
    #        try:
    #            src_vol = self.workflow_api.get_workflow(context,
    #                                                 source_replica)
    #            if src_vol['replication_status'] == 'disabled':
    #                explanation = _('source workflow id:%s is not'
    #                                ' replicated') % source_replica
    #                raise exc.HTTPBadRequest(explanation=explanation)
    #            kwargs['source_replica'] = src_vol
    #        except exception.WorkflowNotFound as error:
    #            raise exc.HTTPNotFound(explanation=error.msg)
    #    else:
    #        kwargs['source_replica'] = None

    #    consistencygroup_id = workflow.get('consistencygroup_id')
    #    if consistencygroup_id is not None:
    #        try:
    #            kwargs['consistencygroup'] = \
    #                self.consistencygroup_api.get(context,
    #                                              consistencygroup_id)
    #        except exception.ConsistencyGroupNotFound as error:
    #            raise exc.HTTPNotFound(explanation=error.msg)
    #    else:
    #        kwargs['consistencygroup'] = None

    #    size = workflow.get('size', None)
    #    if size is None and kwargs['snapshot'] is not None:
    #        size = kwargs['snapshot']['workflow_size']
    #    elif size is None and kwargs['source_workflow'] is not None:
    #        size = kwargs['source_workflow']['size']
    #    elif size is None and kwargs['source_replica'] is not None:
    #        size = kwargs['source_replica']['size']

    #    LOG.info(_LI("Create workflow of %s GB"), size, context=context)

    #    if self.ext_mgr.is_loaded('os-image-create'):
    #        image_ref = workflow.get('imageRef')
    #        if image_ref is not None:
    #            image_uuid = self._image_uuid_from_ref(image_ref, context)
    #            kwargs['image_id'] = image_uuid

    #    kwargs['availability_zone'] = workflow.get('availability_zone', None)
    #    kwargs['scheduler_hints'] = workflow.get('scheduler_hints', None)
    #    multiattach = workflow.get('multiattach', False)
    #    kwargs['multiattach'] = multiattach

    #    new_workflow = self.workflow_api.create(context,
    #                                        size,
    #                                        workflow.get('display_name'),
    #                                        workflow.get('display_description'),
    #                                        **kwargs)

    #    retval = self._view_builder.detail(req, new_workflow)

    #    return retval

    #def _get_workflow_filter_options(self):
    #    """Return workflow search options allowed by non-admin."""
    #    return CONF.query_workflow_filters

    #@wsgi.serializers(xml=WorkflowTemplate)
    #def update(self, req, id, body):
    #    """Update a workflow."""
    #    context = req.environ['waterfall.context']

    #    if not body:
    #        msg = _("Missing request body")
    #        raise exc.HTTPBadRequest(explanation=msg)

    #    if 'workflow' not in body:
    #        msg = _("Missing required element '%s' in request body") % 'workflow'
    #        raise exc.HTTPBadRequest(explanation=msg)

    #    workflow = body['workflow']
    #    update_dict = {}

    #    valid_update_keys = (
    #        'name',
    #        'description',
    #        'display_name',
    #        'display_description',
    #        'metadata',
    #    )

    #    for key in valid_update_keys:
    #        if key in workflow:
    #            update_dict[key] = workflow[key]

    #    self.validate_name_and_description(update_dict)

    #    # NOTE(thingee): v2 API allows name instead of display_name
    #    if 'name' in update_dict:
    #        update_dict['display_name'] = update_dict.pop('name')

    #    # NOTE(thingee): v2 API allows description instead of
    #    #                display_description
    #    if 'description' in update_dict:
    #        update_dict['display_description'] = update_dict.pop('description')

    #    try:
    #        workflow = self.workflow_api.get(context, id, viewable_admin_meta=True)
    #        workflow_utils.notify_about_workflow_usage(context, workflow,
    #                                               'update.start')
    #        self.workflow_api.update(context, workflow, update_dict)
    #    except exception.WorkflowNotFound as error:
    #        raise exc.HTTPNotFound(explanation=error.msg)

    #    workflow.update(update_dict)

    #    utils.add_visible_admin_metadata(workflow)

    #    workflow_utils.notify_about_workflow_usage(context, workflow,
    #                                           'update.end')

    #    return self._view_builder.detail(req, workflow)


def create_resource(ext_mgr):
    return wsgi.Resource(WorkflowController(ext_mgr))
