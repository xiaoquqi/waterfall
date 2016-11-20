# Copyright 2012 Red Hat, Inc.
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
        trimmed = dict(id=workflow_type.get('id'),
                       name=workflow_type.get('name'),
                       is_public=workflow_type.get('is_public'),
                       extra_specs=workflow_type.get('extra_specs'),
                       description=workflow_type.get('description'))
        return trimmed if brief else dict(workflow_type=trimmed)

    def index(self, request, workflow_types):
        """Index over trimmed workflow types."""
        workflow_types_list = [self.show(request, workflow_type, True)
                             for workflow_type in workflow_types]
        return dict(workflow_types=workflow_types_list)
