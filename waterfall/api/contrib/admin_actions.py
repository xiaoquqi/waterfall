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
import webob
from webob import exc

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
from waterfall import backup
from waterfall import db
from waterfall import exception
from waterfall.i18n import _
from waterfall import objects
from waterfall import rpc
from waterfall import utils
from waterfall import workflow


LOG = logging.getLogger(__name__)


class AdminController(wsgi.Controller):
    """Abstract base class for AdminControllers."""

    collection = None  # api collection to extend

    # FIXME(clayg): this will be hard to keep up-to-date
    # Concrete classes can expand or over-ride
    valid_status = set(['creating',
                        'available',
                        'deleting',
                        'error',
                        'error_deleting', ])

    def __init__(self, *args, **kwargs):
        super(AdminController, self).__init__(*args, **kwargs)
        # singular name of the resource
        self.resource_name = self.collection.rstrip('s')
        self.workflow_api = workflow.API()
        self.backup_api = backup.API()

    def _update(self, *args, **kwargs):
        raise NotImplementedError()

    def _get(self, *args, **kwargs):
        raise NotImplementedError()

    def _delete(self, *args, **kwargs):
        raise NotImplementedError()

    def validate_update(self, body):
        update = {}
        try:
            update['status'] = body['status'].lower()
        except (TypeError, KeyError):
            raise exc.HTTPBadRequest(explanation=_("Must specify 'status'"))
        if update['status'] not in self.valid_status:
            raise exc.HTTPBadRequest(
                explanation=_("Must specify a valid status"))
        return update

    def authorize(self, context, action_name):
        # e.g. "snapshot_admin_actions:reset_status"
        action = '%s_admin_actions:%s' % (self.resource_name, action_name)
        extensions.extension_authorizer('workflow', action)(context)

    @wsgi.action('os-reset_status')
    def _reset_status(self, req, id, body):
        """Reset status on the resource."""

        def _clean_workflow_attachment(context, id):
            attachments = (
                db.workflow_attachment_get_used_by_workflow_id(context, id))
            for attachment in attachments:
                db.workflow_detached(context, id, attachment.id)
            db.workflow_admin_metadata_delete(context, id,
                                            'attached_mode')

        context = req.environ['waterfall.context']
        self.authorize(context, 'reset_status')
        update = self.validate_update(body['os-reset_status'])
        msg = "Updating %(resource)s '%(id)s' with '%(update)r'"
        LOG.debug(msg, {'resource': self.resource_name, 'id': id,
                        'update': update})

        notifier_info = dict(id=id, update=update)
        notifier = rpc.get_notifier('workflowStatusUpdate')
        notifier.info(context, self.collection + '.reset_status.start',
                      notifier_info)

        try:
            self._update(context, id, update)
            if update.get('attach_status') == 'detached':
                _clean_workflow_attachment(context, id)
        except exception.WorkflowNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)

        notifier.info(context, self.collection + '.reset_status.end',
                      notifier_info)

        return webob.Response(status_int=202)

    @wsgi.action('os-force_delete')
    def _force_delete(self, req, id, body):
        """Delete a resource, bypassing the check that it must be available."""
        context = req.environ['waterfall.context']
        self.authorize(context, 'force_delete')
        try:
            resource = self._get(context, id)
        except exception.WorkflowNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        self._delete(context, resource, force=True)
        return webob.Response(status_int=202)


class WorkflowAdminController(AdminController):
    """AdminController for Workflows."""

    collection = 'workflows'

    # FIXME(jdg): We're appending additional valid status
    # entries to the set we declare in the parent class
    # this doesn't make a ton of sense, we should probably
    # look at the structure of this whole process again
    # Perhaps we don't even want any definitions in the abstract
    # parent class?
    valid_status = AdminController.valid_status.union(
        ('attaching', 'in-use', 'detaching', 'maintenance'))

    valid_attach_status = ('detached', 'attached',)
    valid_migration_status = ('migrating', 'error',
                              'success', 'completing',
                              'none', 'starting',)

    def _update(self, *args, **kwargs):
        db.workflow_update(*args, **kwargs)

    def _get(self, *args, **kwargs):
        return self.workflow_api.get(*args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self.workflow_api.delete(*args, **kwargs)

    def validate_update(self, body):
        update = {}
        status = body.get('status', None)
        attach_status = body.get('attach_status', None)
        migration_status = body.get('migration_status', None)

        valid = False
        if status:
            valid = True
            update = super(WorkflowAdminController, self).validate_update(body)

        if attach_status:
            valid = True
            update['attach_status'] = attach_status.lower()
            if update['attach_status'] not in self.valid_attach_status:
                raise exc.HTTPBadRequest(
                    explanation=_("Must specify a valid attach status"))

        if migration_status:
            valid = True
            update['migration_status'] = migration_status.lower()
            if update['migration_status'] not in self.valid_migration_status:
                raise exc.HTTPBadRequest(
                    explanation=_("Must specify a valid migration status"))
            if update['migration_status'] == 'none':
                update['migration_status'] = None

        if not valid:
            raise exc.HTTPBadRequest(
                explanation=_("Must specify 'status', 'attach_status' "
                              "or 'migration_status' for update."))
        return update

    @wsgi.action('os-force_detach')
    def _force_detach(self, req, id, body):
        """Roll back a bad detach after the workflow been disconnected."""
        context = req.environ['waterfall.context']
        self.authorize(context, 'force_detach')
        try:
            workflow = self._get(context, id)
        except exception.WorkflowNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        try:
            connector = body['os-force_detach'].get('connector', None)
        except KeyError:
            raise webob.exc.HTTPBadRequest(
                explanation=_("Must specify 'connector'."))
        try:
            self.workflow_api.terminate_connection(context, workflow, connector)
        except exception.WorkflowBackendAPIException as error:
            msg = _("Unable to terminate workflow connection from backend.")
            raise webob.exc.HTTPInternalServerError(explanation=msg)

        attachment_id = body['os-force_detach'].get('attachment_id', None)

        try:
            self.workflow_api.detach(context, workflow, attachment_id)
        except messaging.RemoteError as error:
            if error.exc_type in ['WorkflowAttachmentNotFound',
                                  'InvalidWorkflow']:
                msg = "Error force detaching workflow - %(err_type)s: " \
                      "%(err_msg)s" % {'err_type': error.exc_type,
                                       'err_msg': error.value}
                raise webob.exc.HTTPBadRequest(explanation=msg)
            else:
                # There are also few cases where force-detach call could fail
                # due to db or workflow driver errors. These errors shouldn't
                # be exposed to the user and in such cases it should raise
                # 500 error.
                raise
        return webob.Response(status_int=202)

    @wsgi.action('os-migrate_workflow')
    def _migrate_workflow(self, req, id, body):
        """Migrate a workflow to the specified host."""
        context = req.environ['waterfall.context']
        self.authorize(context, 'migrate_workflow')
        try:
            workflow = self._get(context, id)
        except exception.WorkflowNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        params = body['os-migrate_workflow']
        try:
            host = params['host']
        except KeyError:
            raise exc.HTTPBadRequest(explanation=_("Must specify 'host'."))
        force_host_copy = utils.get_bool_param('force_host_copy', params)
        lock_workflow = utils.get_bool_param('lock_workflow', params)
        self.workflow_api.migrate_workflow(context, workflow, host, force_host_copy,
                                       lock_workflow)
        return webob.Response(status_int=202)

    @wsgi.action('os-migrate_workflow_completion')
    def _migrate_workflow_completion(self, req, id, body):
        """Complete an in-progress migration."""
        context = req.environ['waterfall.context']
        self.authorize(context, 'migrate_workflow_completion')
        try:
            workflow = self._get(context, id)
        except exception.WorkflowNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        params = body['os-migrate_workflow_completion']
        try:
            new_workflow_id = params['new_workflow']
        except KeyError:
            raise exc.HTTPBadRequest(
                explanation=_("Must specify 'new_workflow'"))
        try:
            new_workflow = self._get(context, new_workflow_id)
        except exception.WorkflowNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        error = params.get('error', False)
        ret = self.workflow_api.migrate_workflow_completion(context, workflow,
                                                        new_workflow, error)
        return {'save_workflow_id': ret}


class SnapshotAdminController(AdminController):
    """AdminController for Snapshots."""

    collection = 'snapshots'

    def _update(self, *args, **kwargs):
        context = args[0]
        snapshot_id = args[1]
        fields = args[2]
        snapshot = objects.Snapshot.get_by_id(context, snapshot_id)
        snapshot.update(fields)
        snapshot.save()

    def _get(self, *args, **kwargs):
        return self.workflow_api.get_snapshot(*args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self.workflow_api.delete_snapshot(*args, **kwargs)


class BackupAdminController(AdminController):
    """AdminController for Backups."""

    collection = 'backups'

    valid_status = set(['available',
                        'error'
                        ])

    def _get(self, *args, **kwargs):
        return self.backup_api.get(*args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self.backup_api.delete(*args, **kwargs)

    @wsgi.action('os-reset_status')
    def _reset_status(self, req, id, body):
        """Reset status on the resource."""
        context = req.environ['waterfall.context']
        self.authorize(context, 'reset_status')
        update = self.validate_update(body['os-reset_status'])
        msg = "Updating %(resource)s '%(id)s' with '%(update)r'"
        LOG.debug(msg, {'resource': self.resource_name, 'id': id,
                        'update': update})

        notifier_info = {'id': id, 'update': update}
        notifier = rpc.get_notifier('backupStatusUpdate')
        notifier.info(context, self.collection + '.reset_status.start',
                      notifier_info)

        try:
            self.backup_api.reset_status(context=context, backup_id=id,
                                         status=update['status'])
        except exception.BackupNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        return webob.Response(status_int=202)


class Admin_actions(extensions.ExtensionDescriptor):
    """Enable admin actions."""

    name = "AdminActions"
    alias = "os-admin-actions"
    namespace = "http://docs.openstack.org/workflow/ext/admin-actions/api/v1.1"
    updated = "2012-08-25T00:00:00+00:00"

    def get_controller_extensions(self):
        exts = []
        for class_ in (WorkflowAdminController, SnapshotAdminController,
                       BackupAdminController):
            controller = class_()
            extension = extensions.ControllerExtension(
                self, class_.collection, controller)
            exts.append(extension)
        return exts
