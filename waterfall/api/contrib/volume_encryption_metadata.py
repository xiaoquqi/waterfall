# Copyright (c) 2013 The Johns Hopkins University/Applied Physics Laboratory
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

"""The workflow encryption metadata extension."""

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import db

authorize = extensions.extension_authorizer('workflow',
                                            'workflow_encryption_metadata')


class WorkflowEncryptionMetadataTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.make_flat_dict('encryption', selector='encryption')
        return xmlutil.MasterTemplate(root, 1)


class WorkflowEncryptionMetadataController(wsgi.Controller):
    """The workflow encryption metadata API extension."""

    @wsgi.serializers(xml=WorkflowEncryptionMetadataTemplate)
    def index(self, req, workflow_id):
        """Returns the encryption metadata for a given workflow."""
        context = req.environ['waterfall.context']
        authorize(context)
        return db.workflow_encryption_metadata_get(context, workflow_id)

    @wsgi.serializers(xml=WorkflowEncryptionMetadataTemplate)
    def show(self, req, workflow_id, id):
        """Return a single encryption item."""
        encryption_item = self.index(req, workflow_id)
        if encryption_item is not None:
            return encryption_item[id]
        else:
            return None


class Workflow_encryption_metadata(extensions.ExtensionDescriptor):
    """Workflow encryption metadata retrieval support."""

    name = "WorkflowEncryptionMetadata"
    alias = "os-workflow-encryption-metadata"
    namespace = ("http://docs.openstack.org/workflow/ext/"
                 "os-workflow-encryption-metadata/api/v1")
    updated = "2013-07-10T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
            'encryption', WorkflowEncryptionMetadataController(),
            parent=dict(member_name='workflow', collection_name='workflows'))
        resources.append(res)
        return resources
