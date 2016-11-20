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


from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_utils import encodeutils
from oslo_utils import strutils
import six
import webob

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall.api import xmlutil
from waterfall import exception
from waterfall.i18n import _
from waterfall.image import image_utils
from waterfall import utils
from waterfall import workflow


LOG = logging.getLogger(__name__)


def authorize(context, action_name):
    action = 'workflow_actions:%s' % action_name
    extensions.extension_authorizer('workflow', action)(context)


class WorkflowToImageSerializer(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('os-workflow_upload_image',
                                       selector='os-workflow_upload_image')
        root.set('id')
        root.set('updated_at')
        root.set('status')
        root.set('display_description')
        root.set('size')
        root.set('workflow_type')
        root.set('image_id')
        root.set('container_format')
        root.set('disk_format')
        root.set('image_name')
        return xmlutil.MasterTemplate(root, 1)


class WorkflowToImageDeserializer(wsgi.XMLDeserializer):
    """Deserializer to handle xml-formatted requests."""
    def default(self, string):
        dom = utils.safe_minidom_parse_string(string)
        action_node = dom.childNodes[0]
        action_name = action_node.tagName

        action_data = {}
        attributes = ["force", "image_name", "container_format", "disk_format"]
        for attr in attributes:
            if action_node.hasAttribute(attr):
                action_data[attr] = action_node.getAttribute(attr)
        if 'force' in action_data and action_data['force'] == 'True':
            action_data['force'] = True
        return {'body': {action_name: action_data}}


class WorkflowActionsController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(WorkflowActionsController, self).__init__(*args, **kwargs)
        self.workflow_api = workflow.API()

    @wsgi.action('os-attach')
    def _attach(self, req, id, body):
        """Add attachment metadata."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        # instance uuid is an option now
        instance_uuid = None
        if 'instance_uuid' in body['os-attach']:
            instance_uuid = body['os-attach']['instance_uuid']
        host_name = None
        # Keep API backward compatibility
        if 'host_name' in body['os-attach']:
            host_name = body['os-attach']['host_name']
        mountpoint = body['os-attach']['mountpoint']
        if 'mode' in body['os-attach']:
            mode = body['os-attach']['mode']
        else:
            mode = 'rw'

        if instance_uuid is None and host_name is None:
            msg = _("Invalid request to attach workflow to an invalid target")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        if mode not in ('rw', 'ro'):
            msg = _("Invalid request to attach workflow with an invalid mode. "
                    "Attaching mode should be 'rw' or 'ro'")
            raise webob.exc.HTTPBadRequest(explanation=msg)
        try:
            self.workflow_api.attach(context, workflow,
                                   instance_uuid, host_name, mountpoint, mode)
        except messaging.RemoteError as error:
            if error.exc_type in ['InvalidWorkflow', 'InvalidUUID',
                                  'InvalidWorkflowAttachMode']:
                msg = "Error attaching workflow - %(err_type)s: %(err_msg)s" % {
                      'err_type': error.exc_type, 'err_msg': error.value}
                raise webob.exc.HTTPBadRequest(explanation=msg)
            else:
                # There are also few cases where attach call could fail due to
                # db or workflow driver errors. These errors shouldn't be exposed
                # to the user and in such cases it should raise 500 error.
                raise

        return webob.Response(status_int=202)

    @wsgi.action('os-detach')
    def _detach(self, req, id, body):
        """Clear attachment metadata."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        attachment_id = None
        if body['os-detach']:
            attachment_id = body['os-detach'].get('attachment_id', None)

        try:
            self.workflow_api.detach(context, workflow, attachment_id)
        except messaging.RemoteError as error:
            if error.exc_type in ['WorkflowAttachmentNotFound', 'InvalidWorkflow']:
                msg = "Error detaching workflow - %(err_type)s: %(err_msg)s" % \
                      {'err_type': error.exc_type, 'err_msg': error.value}
                raise webob.exc.HTTPBadRequest(explanation=msg)
            else:
                # There are also few cases where detach call could fail due to
                # db or workflow driver errors. These errors shouldn't be exposed
                # to the user and in such cases it should raise 500 error.
                raise

        return webob.Response(status_int=202)

    @wsgi.action('os-reserve')
    def _reserve(self, req, id, body):
        """Mark workflow as reserved."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        self.workflow_api.reserve_workflow(context, workflow)
        return webob.Response(status_int=202)

    @wsgi.action('os-unreserve')
    def _unreserve(self, req, id, body):
        """Unmark workflow as reserved."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        self.workflow_api.unreserve_workflow(context, workflow)
        return webob.Response(status_int=202)

    @wsgi.action('os-begin_detaching')
    def _begin_detaching(self, req, id, body):
        """Update workflow status to 'detaching'."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        self.workflow_api.begin_detaching(context, workflow)
        return webob.Response(status_int=202)

    @wsgi.action('os-roll_detaching')
    def _roll_detaching(self, req, id, body):
        """Roll back workflow status to 'in-use'."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        self.workflow_api.roll_detaching(context, workflow)
        return webob.Response(status_int=202)

    @wsgi.action('os-initialize_connection')
    def _initialize_connection(self, req, id, body):
        """Initialize workflow attachment."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)
        try:
            connector = body['os-initialize_connection']['connector']
        except KeyError:
            raise webob.exc.HTTPBadRequest(
                explanation=_("Must specify 'connector'"))
        try:
            info = self.workflow_api.initialize_connection(context,
                                                         workflow,
                                                         connector)
        except exception.InvalidInput as err:
            raise webob.exc.HTTPBadRequest(
                explanation=err)
        except exception.WorkflowBackendAPIException as error:
            msg = _("Unable to fetch connection information from backend.")
            raise webob.exc.HTTPInternalServerError(explanation=msg)

        return {'connection_info': info}

    @wsgi.action('os-terminate_connection')
    def _terminate_connection(self, req, id, body):
        """Terminate workflow attachment."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)
        try:
            connector = body['os-terminate_connection']['connector']
        except KeyError:
            raise webob.exc.HTTPBadRequest(
                explanation=_("Must specify 'connector'"))
        try:
            self.workflow_api.terminate_connection(context, workflow, connector)
        except exception.WorkflowBackendAPIException as error:
            msg = _("Unable to terminate workflow connection from backend.")
            raise webob.exc.HTTPInternalServerError(explanation=msg)
        return webob.Response(status_int=202)

    @wsgi.response(202)
    @wsgi.action('os-workflow_upload_image')
    @wsgi.serializers(xml=WorkflowToImageSerializer)
    @wsgi.deserializers(xml=WorkflowToImageDeserializer)
    def _workflow_upload_image(self, req, id, body):
        """Uploads the specified workflow to image service."""
        context = req.environ['waterfall.context']
        params = body['os-workflow_upload_image']
        if not params.get("image_name"):
            msg = _("No image_name was specified in request.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        force = params.get('force', 'False')
        try:
            force = strutils.bool_from_string(force, strict=True)
        except ValueError as error:
            err_msg = encodeutils.exception_to_unicode(error)
            msg = _("Invalid value for 'force': '%s'") % err_msg
            raise webob.exc.HTTPBadRequest(explanation=msg)

        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        authorize(context, "upload_image")
        # check for valid disk-format
        disk_format = params.get("disk_format", "raw")
        if not image_utils.validate_disk_format(disk_format):
            msg = _("Invalid disk-format '%(disk_format)s' is specified. "
                    "Allowed disk-formats are %(allowed_disk_formats)s.") % {
                "disk_format": disk_format,
                "allowed_disk_formats": ", ".join(
                    image_utils.VALID_DISK_FORMATS)
            }
            raise webob.exc.HTTPBadRequest(explanation=msg)

        image_metadata = {"container_format": params.get(
            "container_format", "bare"),
            "disk_format": disk_format,
            "name": params["image_name"]}

        try:
            response = self.workflow_api.copy_workflow_to_image(context,
                                                            workflow,
                                                            image_metadata,
                                                            force)
        except exception.InvalidWorkflow as error:
            raise webob.exc.HTTPBadRequest(explanation=error.msg)
        except ValueError as error:
            raise webob.exc.HTTPBadRequest(explanation=six.text_type(error))
        except messaging.RemoteError as error:
            msg = "%(err_type)s: %(err_msg)s" % {'err_type': error.exc_type,
                                                 'err_msg': error.value}
            raise webob.exc.HTTPBadRequest(explanation=msg)
        except Exception as error:
            raise webob.exc.HTTPBadRequest(explanation=six.text_type(error))
        return {'os-workflow_upload_image': response}

    @wsgi.action('os-extend')
    def _extend(self, req, id, body):
        """Extend size of workflow."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        try:
            int(body['os-extend']['new_size'])
        except (KeyError, ValueError, TypeError):
            msg = _("New workflow size must be specified as an integer.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        size = int(body['os-extend']['new_size'])
        try:
            self.workflow_api.extend(context, workflow, size)
        except exception.InvalidWorkflow as error:
            raise webob.exc.HTTPBadRequest(explanation=error.msg)

        return webob.Response(status_int=202)

    @wsgi.action('os-update_readonly_flag')
    def _workflow_readonly_update(self, req, id, body):
        """Update workflow readonly flag."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        try:
            readonly_flag = body['os-update_readonly_flag']['readonly']
        except KeyError:
            msg = _("Must specify readonly in request.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        try:
            readonly_flag = strutils.bool_from_string(readonly_flag,
                                                      strict=True)
        except ValueError as error:
            err_msg = encodeutils.exception_to_unicode(error)
            msg = _("Invalid value for 'readonly': '%s'") % err_msg
            raise webob.exc.HTTPBadRequest(explanation=msg)

        self.workflow_api.update_readonly_flag(context, workflow, readonly_flag)
        return webob.Response(status_int=202)

    @wsgi.action('os-retype')
    def _retype(self, req, id, body):
        """Change type of existing workflow."""
        context = req.environ['waterfall.context']
        workflow = self.workflow_api.get(context, id)
        try:
            new_type = body['os-retype']['new_type']
        except KeyError:
            msg = _("New workflow type must be specified.")
            raise webob.exc.HTTPBadRequest(explanation=msg)
        policy = body['os-retype'].get('migration_policy')

        self.workflow_api.retype(context, workflow, new_type, policy)
        return webob.Response(status_int=202)

    @wsgi.action('os-set_bootable')
    def _set_bootable(self, req, id, body):
        """Update bootable status of a workflow."""
        context = req.environ['waterfall.context']
        try:
            workflow = self.workflow_api.get(context, id)
        except exception.WorkflowNotFound as error:
            raise webob.exc.HTTPNotFound(explanation=error.msg)

        try:
            bootable = body['os-set_bootable']['bootable']
        except KeyError:
            msg = _("Must specify bootable in request.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        try:
            bootable = strutils.bool_from_string(bootable,
                                                 strict=True)
        except ValueError as error:
            err_msg = encodeutils.exception_to_unicode(error)
            msg = _("Invalid value for 'bootable': '%s'") % err_msg
            raise webob.exc.HTTPBadRequest(explanation=msg)

        update_dict = {'bootable': bootable}

        self.workflow_api.update(context, workflow, update_dict)
        return webob.Response(status_int=200)


class Workflow_actions(extensions.ExtensionDescriptor):
    """Enable workflow actions."""

    name = "WorkflowActions"
    alias = "os-workflow-actions"
    namespace = "http://docs.openstack.org/workflow/ext/workflow-actions/api/v1.1"
    updated = "2012-05-31T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = WorkflowActionsController()
        extension = extensions.ControllerExtension(self, 'workflows', controller)
        return [extension]
