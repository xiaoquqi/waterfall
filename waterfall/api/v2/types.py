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

"""The workflow type & workflow types extra specs extension."""

from oslo_utils import strutils
from webob import exc

from waterfall.api import common
from waterfall.api.openstack import wsgi
from waterfall.api.v2.views import types as views_types
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _
from waterfall import utils
from waterfall.workflow import workflow_types


def make_voltype(elem):
    elem.set('id')
    elem.set('name')
    elem.set('description')
    elem.set('qos_specs_id')
    extra_specs = xmlutil.make_flat_dict('extra_specs', selector='extra_specs')
    elem.append(extra_specs)


class WorkflowTypeTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow_type', selector='workflow_type')
        make_voltype(root)
        return xmlutil.MasterTemplate(root, 1)


class WorkflowTypesTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow_types')
        elem = xmlutil.SubTemplateElement(root, 'workflow_type',
                                          selector='workflow_types')
        make_voltype(elem)
        return xmlutil.MasterTemplate(root, 1)


class WorkflowTypesController(wsgi.Controller):
    """The workflow types API controller for the OpenStack API."""

    _view_builder_class = views_types.ViewBuilder

    @wsgi.serializers(xml=WorkflowTypesTemplate)
    def index(self, req):
        """Returns the list of workflow types."""
        limited_types = self._get_workflow_types(req)
        req.cache_resource(limited_types, name='types')
        return self._view_builder.index(req, limited_types)

    @wsgi.serializers(xml=WorkflowTypeTemplate)
    def show(self, req, id):
        """Return a single workflow type item."""
        context = req.environ['waterfall.context']

        # get default workflow type
        if id is not None and id == 'default':
            vol_type = workflow_types.get_default_workflow_type()
            if not vol_type:
                msg = _("Default workflow type can not be found.")
                raise exc.HTTPNotFound(explanation=msg)
            req.cache_resource(vol_type, name='types')
        else:
            try:
                vol_type = workflow_types.get_workflow_type(context, id)
                req.cache_resource(vol_type, name='types')
            except exception.WorkflowTypeNotFound as error:
                raise exc.HTTPNotFound(explanation=error.msg)

        return self._view_builder.show(req, vol_type)

    def _parse_is_public(self, is_public):
        """Parse is_public into something usable.

        * True: List public workflow types only
        * False: List private workflow types only
        * None: List both public and private workflow types
        """

        if is_public is None:
            # preserve default value of showing only public types
            return True
        elif utils.is_none_string(is_public):
            return None
        else:
            try:
                return strutils.bool_from_string(is_public, strict=True)
            except ValueError:
                msg = _('Invalid is_public filter [%s]') % is_public
                raise exc.HTTPBadRequest(explanation=msg)

    def _get_workflow_types(self, req):
        """Helper function that returns a list of type dicts."""
        params = req.params.copy()
        marker, limit, offset = common.get_pagination_params(params)
        sort_keys, sort_dirs = common.get_sort_params(params)
        # NOTE(wanghao): Currently, we still only support to filter by
        # is_public. If we want to filter by more args, we should set params
        # to filters.
        filters = {}
        context = req.environ['waterfall.context']
        if context.is_admin:
            # Only admin has query access to all workflow types
            filters['is_public'] = self._parse_is_public(
                req.params.get('is_public', None))
        else:
            filters['is_public'] = True
        utils.remove_invalid_filter_options(context,
                                            filters,
                                            self._get_vol_type_filter_options()
                                            )
        limited_types = workflow_types.get_all_types(context,
                                                   filters=filters,
                                                   marker=marker, limit=limit,
                                                   sort_keys=sort_keys,
                                                   sort_dirs=sort_dirs,
                                                   offset=offset,
                                                   list_result=True)
        return limited_types

    def _get_vol_type_filter_options(self):
        """Return workflow type search options allowed by non-admin."""
        return ['is_public']


def create_resource():
    return wsgi.Resource(WorkflowTypesController())
