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

"""The workflows snapshots api."""

from oslo_log import log as logging
from oslo_utils import strutils
import webob
from webob import exc

from waterfall.api import common
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _, _LI
from waterfall import utils
from waterfall import workflow


LOG = logging.getLogger(__name__)


def _translate_snapshot_detail_view(snapshot):
    """Maps keys for snapshots details view."""

    d = _translate_snapshot_summary_view(snapshot)

    # NOTE(gagupta): No additional data / lookups at the moment
    return d


def _translate_snapshot_summary_view(snapshot):
    """Maps keys for snapshots summary view."""
    d = {}

    d['id'] = snapshot['id']
    d['created_at'] = snapshot['created_at']
    d['display_name'] = snapshot['display_name']
    d['display_description'] = snapshot['display_description']
    d['workflow_id'] = snapshot['workflow_id']
    d['status'] = snapshot['status']
    d['size'] = snapshot['workflow_size']

    if snapshot.get('metadata') and isinstance(snapshot.get('metadata'),
                                               dict):
        d['metadata'] = snapshot['metadata']
    else:
        d['metadata'] = {}
    return d


def make_snapshot(elem):
    elem.set('id')
    elem.set('status')
    elem.set('size')
    elem.set('created_at')
    elem.set('display_name')
    elem.set('display_description')
    elem.set('workflow_id')
    elem.append(common.MetadataTemplate())


class SnapshotTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('snapshot', selector='snapshot')
        make_snapshot(root)
        return xmlutil.MasterTemplate(root, 1)


class SnapshotsTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('snapshots')
        elem = xmlutil.SubTemplateElement(root, 'snapshot',
                                          selector='snapshots')
        make_snapshot(elem)
        return xmlutil.MasterTemplate(root, 1)


class SnapshotsController(wsgi.Controller):
    """The Snapshots API controller for the OpenStack API."""

    def __init__(self, ext_mgr=None):
        self.workflow_api = workflow.API()
        self.ext_mgr = ext_mgr
        super(SnapshotsController, self).__init__()

    @wsgi.serializers(xml=SnapshotTemplate)
    def show(self, req, id):
        """Return data about the given snapshot."""
        context = req.environ['waterfall.context']

        try:
            snapshot = self.workflow_api.get_snapshot(context, id)
            req.cache_db_snapshot(snapshot)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        return {'snapshot': _translate_snapshot_detail_view(snapshot)}

    def delete(self, req, id):
        """Delete a snapshot."""
        context = req.environ['waterfall.context']

        LOG.info(_LI("Delete snapshot with id: %s"), id, context=context)

        try:
            snapshot = self.workflow_api.get_snapshot(context, id)
            self.workflow_api.delete_snapshot(context, snapshot)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)

    @wsgi.serializers(xml=SnapshotsTemplate)
    def index(self, req):
        """Returns a summary list of snapshots."""
        return self._items(req, entity_maker=_translate_snapshot_summary_view)

    @wsgi.serializers(xml=SnapshotsTemplate)
    def detail(self, req):
        """Returns a detailed list of snapshots."""
        return self._items(req, entity_maker=_translate_snapshot_detail_view)

    def _items(self, req, entity_maker):
        """Returns a list of snapshots, transformed through entity_maker."""
        context = req.environ['waterfall.context']

        # pop out limit and offset , they are not search_opts
        search_opts = req.GET.copy()
        search_opts.pop('limit', None)
        search_opts.pop('offset', None)

        # filter out invalid option
        allowed_search_options = ('status', 'workflow_id', 'display_name')
        utils.remove_invalid_filter_options(context, search_opts,
                                            allowed_search_options)

        snapshots = self.workflow_api.get_all_snapshots(context,
                                                      search_opts=search_opts)
        limited_list = common.limited(snapshots.objects, req)
        req.cache_db_snapshots(limited_list)
        res = [entity_maker(snapshot) for snapshot in limited_list]
        return {'snapshots': res}

    @wsgi.serializers(xml=SnapshotTemplate)
    def create(self, req, body):
        """Creates a new snapshot."""
        kwargs = {}
        context = req.environ['waterfall.context']

        if not self.is_valid_body(body, 'snapshot'):
            raise exc.HTTPUnprocessableEntity()

        snapshot = body['snapshot']
        kwargs['metadata'] = snapshot.get('metadata', None)

        try:
            workflow_id = snapshot['workflow_id']
        except KeyError:
            msg = _("'workflow_id' must be specified")
            raise exc.HTTPBadRequest(explanation=msg)

        try:
            workflow = self.workflow_api.get(context, workflow_id)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        force = snapshot.get('force', False)
        msg = _LI("Create snapshot from workflow %s")
        LOG.info(msg, workflow_id, context=context)

        if not utils.is_valid_boolstr(force):
            msg = _("Invalid value '%s' for force. ") % force
            raise exception.InvalidParameterValue(err=msg)

        if strutils.bool_from_string(force):
            new_snapshot = self.workflow_api.create_snapshot_force(
                context,
                workflow,
                snapshot.get('display_name'),
                snapshot.get('display_description'),
                **kwargs)
        else:
            new_snapshot = self.workflow_api.create_snapshot(
                context,
                workflow,
                snapshot.get('display_name'),
                snapshot.get('display_description'),
                **kwargs)
        req.cache_db_snapshot(new_snapshot)

        retval = _translate_snapshot_detail_view(new_snapshot)

        return {'snapshot': retval}

    @wsgi.serializers(xml=SnapshotTemplate)
    def update(self, req, id, body):
        """Update a snapshot."""
        context = req.environ['waterfall.context']

        if not body:
            raise exc.HTTPUnprocessableEntity()

        if 'snapshot' not in body:
            raise exc.HTTPUnprocessableEntity()

        snapshot = body['snapshot']
        update_dict = {}

        valid_update_keys = (
            'display_name',
            'display_description',
        )

        for key in valid_update_keys:
            if key in snapshot:
                update_dict[key] = snapshot[key]

        try:
            snapshot = self.workflow_api.get_snapshot(context, id)
            self.workflow_api.update_snapshot(context, snapshot, update_dict)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        snapshot.update(update_dict)
        req.cache_db_snapshot(snapshot)

        return {'snapshot': _translate_snapshot_detail_view(snapshot)}


def create_resource(ext_mgr):
    return wsgi.Resource(SnapshotsController(ext_mgr))
