#   Copyright 2012 OpenStack Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

"""The Workflow Image Metadata API extension."""
import webob

from oslo_log import log as logging

from waterfall.api import common
from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _
from waterfall import workflow


LOG = logging.getLogger(__name__)

authorize = extensions.soft_extension_authorizer('workflow',
                                                 'workflow_image_metadata')


class WorkflowImageMetadataController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(WorkflowImageMetadataController, self).__init__(*args, **kwargs)
        self.workflow_api = workflow.API()

    def _get_image_metadata(self, context, workflow_id):
        try:
            workflow = self.workflow_api.get(context, workflow_id)
            meta = self.workflow_api.get_workflow_image_metadata(context, workflow)
        except exception.WorkflowNotFound:
            msg = _('Workflow with workflow id %s does not exist.') % workflow_id
            raise webob.exc.HTTPNotFound(explanation=msg)
        return (workflow, meta)

    def _add_image_metadata(self, context, resp_workflow_list, image_metas=None):
        """Appends the image metadata to each of the given workflow.

        :param context: the request context
        :param resp_workflow_list: the response workflow list
        :param image_metas: The image metadata to append, if None is provided
                            it will be retrieved from the database. An empty
                            dict means there is no metadata and it should not
                            be retrieved from the db.
        """
        vol_id_list = []
        for vol in resp_workflow_list:
            vol_id_list.append(vol['id'])
        if image_metas is None:
            try:
                image_metas = self.workflow_api.get_list_workflows_image_metadata(
                    context, vol_id_list)
            except Exception as e:
                LOG.debug('Get image metadata error: %s', e)
                return
        if image_metas:
            for vol in resp_workflow_list:
                image_meta = image_metas.get(vol['id'], {})
                vol['workflow_image_metadata'] = dict(image_meta)

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowImageMetadataTemplate())
            self._add_image_metadata(context, [resp_obj.obj['workflow']])

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['waterfall.context']
        if authorize(context):
            resp_obj.attach(xml=WorkflowsImageMetadataTemplate())
            # Just get the image metadata of those workflows in response.
            workflows = list(resp_obj.obj.get('workflows', []))
            if workflows:
                self._add_image_metadata(context, workflows)

    @wsgi.action("os-set_image_metadata")
    @wsgi.serializers(xml=common.MetadataTemplate)
    @wsgi.deserializers(xml=common.MetadataDeserializer)
    def create(self, req, id, body):
        context = req.environ['waterfall.context']
        if authorize(context):
            try:
                metadata = body['os-set_image_metadata']['metadata']
            except (KeyError, TypeError):
                msg = _("Malformed request body.")
                raise webob.exc.HTTPBadRequest(explanation=msg)
            new_metadata = self._update_workflow_image_metadata(context,
                                                              id,
                                                              metadata,
                                                              delete=False)

            return {'metadata': new_metadata}

    def _update_workflow_image_metadata(self, context,
                                      workflow_id,
                                      metadata,
                                      delete=False):
        try:
            workflow = self.workflow_api.get(context, workflow_id)
            return self.workflow_api.update_workflow_metadata(
                context,
                workflow,
                metadata,
                delete=False,
                meta_type=common.METADATA_TYPES.image)
        except exception.WorkflowNotFound:
            msg = _('Workflow with workflow id %s does not exist.') % workflow_id
            raise webob.exc.HTTPNotFound(explanation=msg)
        except (ValueError, AttributeError):
            msg = _("Malformed request body.")
            raise webob.exc.HTTPBadRequest(explanation=msg)
        except exception.InvalidWorkflowMetadata as error:
            raise webob.exc.HTTPBadRequest(explanation=error.msg)
        except exception.InvalidWorkflowMetadataSize as error:
            raise webob.exc.HTTPRequestEntityTooLarge(explanation=error.msg)

    @wsgi.action("os-show_image_metadata")
    @wsgi.serializers(xml=common.MetadataTemplate)
    def index(self, req, id, body):
        context = req.environ['waterfall.context']
        return {'metadata': self._get_image_metadata(context, id)[1]}

    @wsgi.action("os-unset_image_metadata")
    def delete(self, req, id, body):
        """Deletes an existing image metadata."""
        context = req.environ['waterfall.context']
        if authorize(context):
            try:
                key = body['os-unset_image_metadata']['key']
            except (KeyError, TypeError):
                msg = _("Malformed request body.")
                raise webob.exc.HTTPBadRequest(explanation=msg)

            if key:
                vol, metadata = self._get_image_metadata(context, id)
                if key not in metadata:
                    msg = _("Metadata item was not found.")
                    raise webob.exc.HTTPNotFound(explanation=msg)

                self.workflow_api.delete_workflow_metadata(
                    context, vol, key,
                    meta_type=common.METADATA_TYPES.image)
            else:
                msg = _("The key cannot be None.")
                raise webob.exc.HTTPBadRequest(explanation=msg)

            return webob.Response(status_int=200)


class Workflow_image_metadata(extensions.ExtensionDescriptor):
    """Show image metadata associated with the workflow."""

    name = "WorkflowImageMetadata"
    alias = "os-vol-image-meta"
    namespace = ("http://docs.openstack.org/workflow/ext/"
                 "workflow_image_metadata/api/v1")
    updated = "2012-12-07T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowImageMetadataController()
        extension = extensions.ControllerExtension(self, 'workflows', controller)
        return [extension]


class WorkflowImageMetadataMetadataTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow_image_metadata',
                                       selector='workflow_image_metadata')
        elem = xmlutil.SubTemplateElement(root, 'meta',
                                          selector=xmlutil.get_items)
        elem.set('key', 0)
        elem.text = 1

        return xmlutil.MasterTemplate(root, 1)


class WorkflowImageMetadataTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflow', selector='workflow')
        root.append(WorkflowImageMetadataMetadataTemplate())

        alias = Workflow_image_metadata.alias
        namespace = Workflow_image_metadata.namespace

        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})


class WorkflowsImageMetadataTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('workflows')
        elem = xmlutil.SubTemplateElement(root, 'workflow', selector='workflow')
        elem.append(WorkflowImageMetadataMetadataTemplate())

        alias = Workflow_image_metadata.alias
        namespace = Workflow_image_metadata.namespace

        return xmlutil.SlaveTemplate(root, 1, nsmap={alias: namespace})
