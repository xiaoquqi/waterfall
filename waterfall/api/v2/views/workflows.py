# Copyright 2012 OpenStack Foundation
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
import six

from waterfall.api import common


LOG = logging.getLogger(__name__)


class ViewBuilder(common.ViewBuilder):
    """Model a server API response as a python dictionary."""

    _collection_name = "workflows"

    def __init__(self):
        """Initialize view builder."""
        super(ViewBuilder, self).__init__()

    def summary_list(self, request, workflows, workflow_count=None):
        """Show a list of workflows without many details."""
        return self._list_view(self.summary, request, workflows,
                               workflow_count)

    def detail_list(self, request, workflows, workflow_count=None):
        """Detailed view of a list of workflows."""
        return self._list_view(self.detail, request, workflows,
                               workflow_count,
                               self._collection_name + '/detail')

    def summary(self, request, workflow):
        """Generic, non-detailed view of a workflow."""
        return {
            'workflow': {
                'id': workflow['id'],
                'resource_type': workflow['resource_type'],
            },
        }

    def detail(self, request, workflow):
        """Detailed view of a single workflow."""
        workflow_ref = {
            'workflow': {
                'id': workflow.get('id'),
                'resource_type': workflow.get('resource_type'),
                'payload': workflow.get('payload'),
                'created_at': workflow.get('created_at'),
                'updated_at': workflow.get('updated_at'),
                'user_id': workflow.get('user_id'),
            }
        }
        if request.environ['waterfall.context'].is_admin:
            workflow_ref['workflow']['migration_status'] = (
                workflow.get('migration_status'))
        return workflow_ref

    def _list_view(self, func, request, workflows, workflow_count,
                   coll_name=_collection_name):
        """Provide a view for a list of workflows.

        :param func: Function used to format the workflow data
        :param request: API request
        :param workflows: List of workflows in dictionary format
        :param workflow_count: Length of the original list of workflows
        :param coll_name: Name of collection, used to generate the next link
                          for a pagination query
        :returns: Workflow data in dictionary format
        """
        workflows_list = [func(request, workflow)['workflow'] for workflow in workflows]
        workflows_links = self._get_collection_links(request,
                                                   workflows,
                                                   coll_name,
                                                   workflow_count)
        workflows_dict = dict(workflows=workflows_list)

        if workflows_links:
            workflows_dict['workflows_links'] = workflows_links

        return workflows_dict
