# Copyright 2011 OpenStack Foundation
# Copyright 2011 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""
WSGI middleware for OpenStack Workflow API.
"""

from oslo_log import log as logging

from waterfall.api import extensions
import waterfall.api.openstack
from waterfall.api.v1 import limits
from waterfall.api.v1 import snapshot_metadata
from waterfall.api.v1 import snapshots
from waterfall.api.v1 import types
from waterfall.api.v1 import workflow_metadata
from waterfall.api.v1 import workflows
from waterfall.api import versions


LOG = logging.getLogger(__name__)


class APIRouter(waterfall.api.openstack.APIRouter):
    """Routes requests on the API to the appropriate controller and method."""
    ExtensionManager = extensions.ExtensionManager

    def _setup_routes(self, mapper, ext_mgr):
        self.resources['versions'] = versions.create_resource()
        mapper.connect("versions", "/",
                       controller=self.resources['versions'],
                       action='index')

        mapper.redirect("", "/")

        self.resources['workflows'] = workflows.create_resource(ext_mgr)
        mapper.resource("workflow", "workflows",
                        controller=self.resources['workflows'],
                        collection={'detail': 'GET'},
                        member={'action': 'POST'})

        self.resources['types'] = types.create_resource()
        mapper.resource("type", "types",
                        controller=self.resources['types'])

        self.resources['snapshots'] = snapshots.create_resource(ext_mgr)
        mapper.resource("snapshot", "snapshots",
                        controller=self.resources['snapshots'],
                        collection={'detail': 'GET'},
                        member={'action': 'POST'})

        self.resources['snapshot_metadata'] = \
            snapshot_metadata.create_resource()
        snapshot_metadata_controller = self.resources['snapshot_metadata']

        mapper.resource("snapshot_metadata", "metadata",
                        controller=snapshot_metadata_controller,
                        parent_resource=dict(member_name='snapshot',
                                             collection_name='snapshots'))

        mapper.connect("metadata",
                       "/{project_id}/snapshots/{snapshot_id}/metadata",
                       controller=snapshot_metadata_controller,
                       action='update_all',
                       conditions={"method": ['PUT']})

        self.resources['limits'] = limits.create_resource()
        mapper.resource("limit", "limits",
                        controller=self.resources['limits'])
        self.resources['workflow_metadata'] = \
            workflow_metadata.create_resource()
        workflow_metadata_controller = self.resources['workflow_metadata']

        mapper.resource("workflow_metadata", "metadata",
                        controller=workflow_metadata_controller,
                        parent_resource=dict(member_name='workflow',
                                             collection_name='workflows'))

        mapper.connect("metadata",
                       "/{project_id}/workflows/{workflow_id}/metadata",
                       controller=workflow_metadata_controller,
                       action='update_all',
                       conditions={"method": ['PUT']})
