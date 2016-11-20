# Copyright 2012 Red Hat, Inc.
# Copyright 2015 Intel Corporation
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

from waterfall.api import common


class ViewBuilder(common.ViewBuilder):

    def show(self, request, workflow_type, brief=False):
        """Trim away extraneous workflow type attributes."""
        context = request.environ['waterfall.context']
        trimmed = dict(id=workflow_type.get('id'),
                       name=workflow_type.get('name'),
                       is_public=workflow_type.get('is_public'),
                       description=workflow_type.get('description'))
        if common.validate_policy(
           context,
           'workflow_extension:access_types_extra_specs'):
            trimmed['extra_specs'] = workflow_type.get('extra_specs')
        if common.validate_policy(
           context,
           'workflow_extension:access_types_qos_specs_id'):
            trimmed['qos_specs_id'] = workflow_type.get('qos_specs_id')
        return trimmed if brief else dict(workflow_type=trimmed)

    def index(self, request, workflow_types):
        """Index over trimmed workflow types."""
        workflow_types_list = [self.show(request, workflow_type, True)
                             for workflow_type in workflow_types]
        workflow_type_links = self._get_collection_links(request, workflow_types,
                                                       'types')
        workflow_types_dict = dict(workflow_types=workflow_types_list)
        if workflow_type_links:
            workflow_types_dict['workflow_type_links'] = workflow_type_links
        return workflow_types_dict
