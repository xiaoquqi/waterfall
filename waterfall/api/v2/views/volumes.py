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
                'name': workflow['display_name'],
                'links': self._get_links(request,
                                         workflow['id']),
            },
        }

    def detail(self, request, workflow):
        """Detailed view of a single workflow."""
        workflow_ref = {
            'workflow': {
                'id': workflow.get('id'),
                'status': workflow.get('status'),
                'size': workflow.get('size'),
                'availability_zone': workflow.get('availability_zone'),
                'created_at': workflow.get('created_at'),
                'updated_at': workflow.get('updated_at'),
                'attachments': self._get_attachments(workflow),
                'name': workflow.get('display_name'),
                'description': workflow.get('display_description'),
                'workflow_type': self._get_workflow_type(workflow),
                'snapshot_id': workflow.get('snapshot_id'),
                'source_volid': workflow.get('source_volid'),
                'metadata': self._get_workflow_metadata(workflow),
                'links': self._get_links(request, workflow['id']),
                'user_id': workflow.get('user_id'),
                'bootable': six.text_type(workflow.get('bootable')).lower(),
                'encrypted': self._is_workflow_encrypted(workflow),
                'replication_status': workflow.get('replication_status'),
                'consistencygroup_id': workflow.get('consistencygroup_id'),
                'multiattach': workflow.get('multiattach'),
            }
        }
        if request.environ['waterfall.context'].is_admin:
            workflow_ref['workflow']['migration_status'] = (
                workflow.get('migration_status'))
        return workflow_ref

    def _is_workflow_encrypted(self, workflow):
        """Determine if workflow is encrypted."""
        return workflow.get('encryption_key_id') is not None

    def _get_attachments(self, workflow):
        """Retrieve the attachments of the workflow object."""
        attachments = []

        if workflow['attach_status'] == 'attached':
            attaches = workflow.workflow_attachment
            for attachment in attaches:
                if attachment.get('attach_status') == 'attached':
                    a = {'id': attachment.get('workflow_id'),
                         'attachment_id': attachment.get('id'),
                         'workflow_id': attachment.get('workflow_id'),
                         'server_id': attachment.get('instance_uuid'),
                         'host_name': attachment.get('attached_host'),
                         'device': attachment.get('mountpoint'),
                         'attached_at': attachment.get('attach_time'),
                         }
                    attachments.append(a)

        return attachments

    def _get_workflow_metadata(self, workflow):
        """Retrieve the metadata of the workflow object."""
        return workflow.metadata

    def _get_workflow_type(self, workflow):
        """Retrieve the type the workflow object."""
        if workflow['workflow_type_id'] and workflow.get('workflow_type'):
            return workflow['workflow_type']['name']
        else:
            return workflow['workflow_type_id']

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
