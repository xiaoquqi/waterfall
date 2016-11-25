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


class WorkflowController(wsgi.Controller):
    """The Workflows API controller for the OpenStack API."""

    _view_builder_class = workflow_views.ViewBuilder

    def __init__(self, ext_mgr):
        self.workflow_api = workflow_api.API()
        self.ext_mgr = ext_mgr
        super(WorkflowController, self).__init__()

    def index(self, req):
        """Returns a summary list of workflows."""
        context = req.environ['waterfall.context']
        workflows = self.workflow_api.workflow_get_all(context)
        return self._view_builder.detail_list(req, workflows)

    @wsgi.response(202)
    def create(self, req, body):
        context = req.environ['waterfall.context']
        workflow = body['workflow']

        resource_type = workflow.get("resource_type")
        payload = workflow.get("payload")
        workflow = self.workflow_api.workflow_create(
                context, resource_type, payload)
        retval = self._view_builder.detail(req, workflow)
        from waterfall.workflow import rpcapi
        workflow_rpcapi = rpcapi.WorkflowAPI()
        workflow_rpcapi.apply_workflow(context, workflow)

        return retval

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
