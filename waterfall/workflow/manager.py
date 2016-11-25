# Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
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
Workflow manager manages volume workflows.

Volume Workflows are full copies of persistent volumes stored in a workflow
store e.g. an object store or any other workflow store if and when support is
added. They are usable without the original object being available. A
volume workflow can be restored to the original volume it was created from or
any other available volume with a minimum size of the original volume.
Volume workflows can be created, restored, deleted and listed.

**Related Flags**

:workflow_topic:  What :mod:`rpc` topic to listen to (default:
                        `waterfall-workflow`).
:workflow_manager:  The module name of a class derived from
                          :class:`manager.Manager` (default:
                          :class:`waterfall.workflow.manager.Manager`).

"""

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_utils import excutils
from oslo_utils import importutils
import six

from waterfall.workflow import driver
from waterfall.workflow import rpcapi as workflow_rpcapi
from waterfall import context
from waterfall import exception
from waterfall.i18n import _, _LE, _LI, _LW
from waterfall import manager
from waterfall import objects
from waterfall.objects import fields
from waterfall import quota
from waterfall import rpc
from waterfall import utils
#from waterfall.volume import rpcapi as volume_rpcapi
#from waterfall.volume import utils as volume_utils

LOG = logging.getLogger(__name__)

workflow_manager_opts = [
    cfg.StrOpt('workflow_driver',
               default='waterfall.workflow.drivers.simple',
               help='Driver to use for workflows.',),
    cfg.BoolOpt('workflow_service_inithost_offload',
                default=False,
                help='Offload pending workflow delete during '
                     'workflow service startup.',),
]

# This map doesn't need to be extended in the future since it's only
# for old workflow services
mapper = {'waterfall.workflow.services.swift': 'waterfall.workflow.drivers.swift',
          'waterfall.workflow.services.ceph': 'waterfall.workflow.drivers.ceph'}

CONF = cfg.CONF
CONF.register_opts(workflow_manager_opts)
#CONF.import_opt('use_multipath_for_image_xfer', 'waterfall.volume.driver')
#CONF.import_opt('num_volume_device_scan_tries', 'waterfall.volume.driver')
QUOTAS = quota.QUOTAS


class WorkflowManager(manager.SchedulerDependentManager):
    """Manages workflow of block storage devices."""

    RPC_API_VERSION = '2.0'

    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, service_name=None, *args, **kwargs):
        self.service = importutils.import_module(self.driver_name)
        #self.az = CONF.storage_availability_zone
        self.volume_managers = {}
        # TODO(xyang): If workflow_use_same_host is True, we'll find
        # the volume backend on the workflow node. This allows us
        # to use a temp snapshot to workflow an in-use volume if the
        # driver supports it. This code should go away when we add
        # support for backing up in-use volume using a temp snapshot
        # on a remote node.
        #if CONF.workflow_use_same_host:
        #    self._setup_volume_drivers()
        self.workflow_rpcapi = workflow_rpcapi.WorkflowAPI()
        #self.volume_rpcapi = volume_rpcapi.VolumeAPI()
        super(WorkflowManager, self).__init__(service_name='workflow',
                                            *args, **kwargs)
        #self.additional_endpoints.append(_WorkflowV1Proxy(self))

    def _init_volume_driver(self, ctxt, driver):
        LOG.info(_LI("Starting volume driver %(driver_name)s (%(version)s)."),
                 {'driver_name': driver.__class__.__name__,
                  'version': driver.get_version()})
        try:
            driver.do_setup(ctxt)
            driver.check_for_setup_error()
        except Exception:
            LOG.exception(_LE("Error encountered during initialization of "
                              "driver: %(name)s."),
                          {'name': driver.__class__.__name__})
            # we don't want to continue since we failed
            # to initialize the driver correctly.
            return

        driver.set_initialized()

    def _get_volume_backend(self, host=None, allow_null_host=False):
        if host is None:
            if not allow_null_host:
                msg = _("NULL host not allowed for volume backend lookup.")
                raise exception.WorkflowFailedToGetVolumeBackend(msg)
        else:
            LOG.debug("Checking hostname '%s' for backend info.", host)
            # NOTE(xyang): If host='myhost@lvmdriver', backend='lvmdriver'
            # by the logic below. This is different from extract_host.
            # vol_utils.extract_host(host, 'backend')='myhost@lvmdriver'.
            part = host.partition('@')
            if (part[1] == '@') and (part[2] != ''):
                backend = part[2]
                LOG.debug("Got backend '%s'.", backend)
                return backend

        LOG.info(_LI("Backend not found in hostname (%s) so using default."),
                 host)

        if 'default' not in self.volume_managers:
            # For multi-backend we just pick the top of the list.
            return self.volume_managers.keys()[0]

        return 'default'

    def _get_manager(self, backend):
        LOG.debug("Manager requested for volume_backend '%s'.",
                  backend)
        if backend is None:
            LOG.debug("Fetching default backend.")
            backend = self._get_volume_backend(allow_null_host=True)
        if backend not in self.volume_managers:
            msg = (_("Volume manager for backend '%s' does not exist.") %
                   (backend))
            raise exception.WorkflowFailedToGetVolumeBackend(msg)
        return self.volume_managers[backend]

    def _get_driver(self, backend=None):
        LOG.debug("Driver requested for volume_backend '%s'.",
                  backend)
        if backend is None:
            LOG.debug("Fetching default backend.")
            backend = self._get_volume_backend(allow_null_host=True)
        mgr = self._get_manager(backend)
        mgr.driver.db = self.db
        return mgr.driver

    def _setup_volume_drivers(self):
        if CONF.enabled_backends:
            for backend in CONF.enabled_backends:
                host = "%s@%s" % (CONF.host, backend)
                mgr = importutils.import_object(CONF.volume_manager,
                                                host=host,
                                                service_name=backend)
                config = mgr.configuration
                backend_name = config.safe_get('volume_backend_name')
                LOG.debug("Registering backend %(backend)s (host=%(host)s "
                          "backend_name=%(backend_name)s).",
                          {'backend': backend, 'host': host,
                           'backend_name': backend_name})
                self.volume_managers[backend] = mgr
        else:
            default = importutils.import_object(CONF.volume_manager)
            LOG.debug("Registering default backend %s.", default)
            self.volume_managers['default'] = default

    @property
    def driver_name(self):
        """This function maps old workflow services to workflow drivers."""

        return self._map_service_to_driver(CONF.workflow_driver)

    def _map_service_to_driver(self, service):
        """Maps services to drivers."""

        if service in mapper:
            return mapper[service]
        return service

    def _update_workflow_error(self, workflow, context, err):
        workflow.status = fields.WorkflowStatus.ERROR
        workflow.fail_reason = err
        workflow.save()

    def init_host(self):
        """Run initialization needed for a standalone service."""
        pass
        #ctxt = context.get_admin_context()

        #for mgr in self.volume_managers.values():
        #    self._init_volume_driver(ctxt, mgr.driver)

        #try:
        #    self._cleanup_incomplete_workflow_operations(ctxt)
        #except Exception:
        #    # Don't block startup of the workflow service.
        #    LOG.exception(_LE("Problem cleaning incomplete workflow "
        #                      "operations."))

    def reset(self):
        super(WorkflowManager, self).reset()
        self.workflow_rpcapi = workflow_rpcapi.WorkflowAPI()
        self.volume_rpcapi = volume_rpcapi.VolumeAPI()

    def _cleanup_incomplete_workflow_operations(self, ctxt):
        LOG.info(_LI("Cleaning up incomplete workflow operations."))

        # TODO(smulcahy) implement full resume of workflow and restore
        # operations on restart (rather than simply resetting)
        workflows = objects.WorkflowList.get_all_by_host(ctxt, self.host)
        for workflow in workflows:
            try:
                self._cleanup_one_workflow(ctxt, workflow)
            except Exception:
                LOG.exception(_LE("Problem cleaning up workflow %(bkup)s."),
                              {'bkup': workflow['id']})
            try:
                self._cleanup_temp_volumes_snapshots_for_one_workflow(ctxt,
                                                                    workflow)
            except Exception:
                LOG.exception(_LE("Problem cleaning temp volumes and "
                                  "snapshots for workflow %(bkup)s."),
                              {'bkup': workflow['id']})

    def _cleanup_one_volume(self, ctxt, volume):
        if volume['status'] == 'backing-up':
            self._detach_all_attachments(ctxt, volume)
            LOG.info(_LI('Resetting volume %(vol_id)s to previous '
                         'status %(status)s (was backing-up).'),
                     {'vol_id': volume['id'],
                      'status': volume['previous_status']})
            self.db.volume_update(ctxt, volume['id'],
                                  {'status': volume['previous_status']})
        elif volume['status'] == 'restoring-workflow':
            self._detach_all_attachments(ctxt, volume)
            LOG.info(_LI('setting volume %s to error_restoring '
                         '(was restoring-workflow).'), volume['id'])
            self.db.volume_update(ctxt, volume['id'],
                                  {'status': 'error_restoring'})

    def _cleanup_one_workflow(self, ctxt, workflow):
        if workflow['status'] == fields.WorkflowStatus.CREATING:
            LOG.info(_LI('Resetting workflow %s to error (was creating).'),
                     workflow['id'])

            volume = objects.Volume.get_by_id(ctxt, workflow.volume_id)
            self._cleanup_one_volume(ctxt, volume)

            err = 'incomplete workflow reset on manager restart'
            self._update_workflow_error(workflow, ctxt, err)
        elif workflow['status'] == fields.WorkflowStatus.RESTORING:
            LOG.info(_LI('Resetting workflow %s to '
                         'available (was restoring).'),
                     workflow['id'])
            volume = objects.Volume.get_by_id(ctxt, workflow.restore_volume_id)
            self._cleanup_one_volume(ctxt, volume)

            workflow.status = fields.WorkflowStatus.AVAILABLE
            workflow.save()
        elif workflow['status'] == fields.WorkflowStatus.DELETING:
            LOG.info(_LI('Resuming delete on workflow: %s.'), workflow['id'])
            if CONF.workflow_service_inithost_offload:
                # Offload all the pending workflow delete operations to the
                # threadpool to prevent the main workflow service thread
                # from being blocked.
                self._add_to_threadpool(self.delete_workflow, ctxt, workflow)
            else:
                # By default, delete workflows sequentially
                self.delete_workflow(ctxt, workflow)

    def _detach_all_attachments(self, ctxt, volume):
        attachments = volume['volume_attachment'] or []
        for attachment in attachments:
            if (attachment['attached_host'] == self.host and
                    attachment['instance_uuid'] is None):
                try:
                    rpcapi = self.volume_rpcapi
                    rpcapi.detach_volume(ctxt, volume, attachment['id'])
                except Exception:
                    LOG.exception(_LE("Detach attachment %(attach_id)s"
                                      " failed."),
                                  {'attach_id': attachment['id']},
                                  resource=volume)

    def _delete_temp_volume(self, ctxt, workflow):
        try:
            temp_volume = objects.Volume.get_by_id(
                ctxt, workflow.temp_volume_id)
            self.volume_rpcapi.delete_volume(ctxt, temp_volume)
        except exception.VolumeNotFound:
            LOG.debug("Could not find temp volume %(vol)s to clean up "
                      "for workflow %(workflow)s.",
                      {'vol': workflow.temp_volume_id,
                       'workflow': workflow.id})
        workflow.temp_volume_id = None
        workflow.save()

    def _delete_temp_snapshot(self, ctxt, workflow):
        try:
            temp_snapshot = objects.Snapshot.get_by_id(
                ctxt, workflow.temp_snapshot_id)
            volume = objects.Volume.get_by_id(
                ctxt, workflow.volume_id)
            # The temp snapshot should be deleted directly thru the
            # volume driver, not thru the volume manager.
            self.volume_rpcapi.delete_snapshot(ctxt, temp_snapshot,
                                               volume.host)
        except exception.SnapshotNotFound:
            LOG.debug("Could not find temp snapshot %(snap)s to clean "
                      "up for workflow %(workflow)s.",
                      {'snap': workflow.temp_snapshot_id,
                       'workflow': workflow.id})
        workflow.temp_snapshot_id = None
        workflow.save()

    def _cleanup_temp_volumes_snapshots_for_one_workflow(self, ctxt, workflow):
        # NOTE(xyang): If the service crashes or gets restarted during the
        # workflow operation, there could be temporary volumes or snapshots
        # that are not deleted. Make sure any temporary volumes or snapshots
        # create by the workflow job are deleted when service is started.
        if (workflow.temp_volume_id
                and workflow.status == fields.WorkflowStatus.ERROR):
            self._delete_temp_volume(ctxt, workflow)

        if (workflow.temp_snapshot_id
                and workflow.status == fields.WorkflowStatus.ERROR):
            self._delete_temp_snapshot(ctxt, workflow)

    def _cleanup_temp_volumes_snapshots_when_workflow_created(
            self, ctxt, workflow):
        # Delete temp volumes or snapshots when workflow creation is completed.
        if workflow.temp_volume_id:
            self._delete_temp_volume(ctxt, workflow)

        if workflow.temp_snapshot_id:
            self._delete_temp_snapshot(ctxt, workflow)

    def create_workflow(self, context, workflow):
        """Create volume workflows using configured workflow service."""
        volume_id = workflow.volume_id
        volume = objects.Volume.get_by_id(context, volume_id)
        previous_status = volume.get('previous_status', None)
        LOG.info(_LI('Create workflow started, workflow: %(workflow_id)s '
                     'volume: %(volume_id)s.'),
                 {'workflow_id': workflow.id, 'volume_id': volume_id})

        self._notify_about_workflow_usage(context, workflow, "create.start")

        workflow.host = self.host
        workflow.service = self.driver_name
        workflow.availability_zone = self.az
        workflow.save()

        expected_status = 'backing-up'
        actual_status = volume['status']
        if actual_status != expected_status:
            err = _('Create workflow aborted, expected volume status '
                    '%(expected_status)s but got %(actual_status)s.') % {
                'expected_status': expected_status,
                'actual_status': actual_status,
            }
            self._update_workflow_error(workflow, context, err)
            raise exception.InvalidVolume(reason=err)

        expected_status = fields.WorkflowStatus.CREATING
        actual_status = workflow.status
        if actual_status != expected_status:
            err = _('Create workflow aborted, expected workflow status '
                    '%(expected_status)s but got %(actual_status)s.') % {
                'expected_status': expected_status,
                'actual_status': actual_status,
            }
            self._update_workflow_error(workflow, context, err)
            workflow.save()
            raise exception.InvalidWorkflow(reason=err)

        try:
            self._run_workflow(context, workflow, volume)
        except Exception as err:
            with excutils.save_and_reraise_exception():
                self.db.volume_update(context, volume_id,
                                      {'status': previous_status,
                                       'previous_status': 'error_backing-up'})
                self._update_workflow_error(workflow, context, six.text_type(err))

        # Restore the original status.
        self.db.volume_update(context, volume_id,
                              {'status': previous_status,
                               'previous_status': 'backing-up'})
        workflow.status = fields.WorkflowStatus.AVAILABLE
        workflow.size = volume['size']
        workflow.save()

        # Handle the num_dependent_workflows of parent workflow when child workflow
        # has created successfully.
        if workflow.parent_id:
            parent_workflow = objects.Workflow.get_by_id(context,
                                                     workflow.parent_id)
            parent_workflow.num_dependent_workflows += 1
            parent_workflow.save()
        LOG.info(_LI('Create workflow finished. workflow: %s.'), workflow.id)
        self._notify_about_workflow_usage(context, workflow, "create.end")

    def _run_workflow(self, context, workflow, volume):
        workflow_service = self.service.get_workflow_driver(context)

        properties = utils.brick_get_connector_properties()
        workflow_dic = self.volume_rpcapi.get_workflow_device(context,
                                                          workflow, volume)
        try:
            workflow_device = workflow_dic.get('workflow_device')
            is_snapshot = workflow_dic.get('is_snapshot')
            attach_info = self._attach_device(context, workflow_device,
                                              properties, is_snapshot)
            try:
                device_path = attach_info['device']['path']
                if isinstance(device_path, six.string_types):
                    if workflow_dic.get('secure_enabled', False):
                        with open(device_path) as device_file:
                            workflow_service.workflow(workflow, device_file)
                    else:
                        with utils.temporary_chown(device_path):
                            with open(device_path) as device_file:
                                workflow_service.workflow(workflow, device_file)
                else:
                    workflow_service.workflow(workflow, device_path)

            finally:
                self._detach_device(context, attach_info,
                                    workflow_device, properties,
                                    is_snapshot)
        finally:
            workflow = objects.Workflow.get_by_id(context, workflow.id)
            self._cleanup_temp_volumes_snapshots_when_workflow_created(
                context, workflow)

    def restore_workflow(self, context, workflow, volume_id):
        """Restore volume workflows from configured workflow service."""
        LOG.info(_LI('Restore workflow started, workflow: %(workflow_id)s '
                     'volume: %(volume_id)s.'),
                 {'workflow_id': workflow.id, 'volume_id': volume_id})

        volume = objects.Volume.get_by_id(context, volume_id)
        self._notify_about_workflow_usage(context, workflow, "restore.start")

        workflow.host = self.host
        workflow.save()

        expected_status = 'restoring-workflow'
        actual_status = volume['status']
        if actual_status != expected_status:
            err = (_('Restore workflow aborted, expected volume status '
                     '%(expected_status)s but got %(actual_status)s.') %
                   {'expected_status': expected_status,
                    'actual_status': actual_status})
            workflow.status = fields.WorkflowStatus.AVAILABLE
            workflow.save()
            raise exception.InvalidVolume(reason=err)

        expected_status = fields.WorkflowStatus.RESTORING
        actual_status = workflow['status']
        if actual_status != expected_status:
            err = (_('Restore workflow aborted: expected workflow status '
                     '%(expected_status)s but got %(actual_status)s.') %
                   {'expected_status': expected_status,
                    'actual_status': actual_status})
            self._update_workflow_error(workflow, context, err)
            self.db.volume_update(context, volume_id, {'status': 'error'})
            raise exception.InvalidWorkflow(reason=err)

        if volume['size'] > workflow['size']:
            LOG.info(_LI('Volume: %(vol_id)s, size: %(vol_size)d is '
                         'larger than workflow: %(workflow_id)s, '
                         'size: %(workflow_size)d, continuing with restore.'),
                     {'vol_id': volume['id'],
                      'vol_size': volume['size'],
                      'workflow_id': workflow['id'],
                      'workflow_size': workflow['size']})

        workflow_service = self._map_service_to_driver(workflow['service'])
        configured_service = self.driver_name
        if workflow_service != configured_service:
            err = _('Restore workflow aborted, the workflow service currently'
                    ' configured [%(configured_service)s] is not the'
                    ' workflow service that was used to create this'
                    ' workflow [%(workflow_service)s].') % {
                'configured_service': configured_service,
                'workflow_service': workflow_service,
            }
            workflow.status = fields.WorkflowStatus.AVAILABLE
            workflow.save()
            self.db.volume_update(context, volume_id, {'status': 'error'})
            raise exception.InvalidWorkflow(reason=err)

        try:
            self._run_restore(context, workflow, volume)
        except Exception:
            with excutils.save_and_reraise_exception():
                self.db.volume_update(context, volume_id,
                                      {'status': 'error_restoring'})
                workflow.status = fields.WorkflowStatus.AVAILABLE
                workflow.save()

        self.db.volume_update(context, volume_id, {'status': 'available'})
        workflow.status = fields.WorkflowStatus.AVAILABLE
        workflow.save()
        LOG.info(_LI('Restore workflow finished, workflow %(workflow_id)s restored'
                     ' to volume %(volume_id)s.'),
                 {'workflow_id': workflow.id, 'volume_id': volume_id})
        self._notify_about_workflow_usage(context, workflow, "restore.end")

    def _run_restore(self, context, workflow, volume):
        workflow_service = self.service.get_workflow_driver(context)

        properties = utils.brick_get_connector_properties()
        secure_enabled = (
            self.volume_rpcapi.secure_file_operations_enabled(context,
                                                              volume))
        attach_info = self._attach_device(context, volume, properties)
        try:
            device_path = attach_info['device']['path']
            if isinstance(device_path, six.string_types):
                if secure_enabled:
                    with open(device_path, 'wb') as device_file:
                        workflow_service.restore(workflow, volume.id, device_file)
                else:
                    with utils.temporary_chown(device_path):
                        with open(device_path, 'wb') as device_file:
                            workflow_service.restore(workflow, volume.id,
                                                   device_file)
            else:
                workflow_service.restore(workflow, volume.id, device_path)
        finally:
            self._detach_device(context, attach_info, volume, properties)

    def delete_workflow(self, context, workflow):
        """Delete volume workflow from configured workflow service."""
        LOG.info(_LI('Delete workflow started, workflow: %s.'), workflow.id)

        self._notify_about_workflow_usage(context, workflow, "delete.start")
        workflow.host = self.host
        workflow.save()

        expected_status = fields.WorkflowStatus.DELETING
        actual_status = workflow.status
        if actual_status != expected_status:
            err = _('Delete_workflow aborted, expected workflow status '
                    '%(expected_status)s but got %(actual_status)s.') \
                % {'expected_status': expected_status,
                   'actual_status': actual_status}
            self._update_workflow_error(workflow, context, err)
            raise exception.InvalidWorkflow(reason=err)

        workflow_service = self._map_service_to_driver(workflow['service'])
        if workflow_service is not None:
            configured_service = self.driver_name
            if workflow_service != configured_service:
                err = _('Delete workflow aborted, the workflow service currently'
                        ' configured [%(configured_service)s] is not the'
                        ' workflow service that was used to create this'
                        ' workflow [%(workflow_service)s].')\
                    % {'configured_service': configured_service,
                       'workflow_service': workflow_service}
                self._update_workflow_error(workflow, context, err)
                raise exception.InvalidWorkflow(reason=err)

            try:
                workflow_service = self.service.get_workflow_driver(context)
                workflow_service.delete(workflow)
            except Exception as err:
                with excutils.save_and_reraise_exception():
                    self._update_workflow_error(workflow, context,
                                              six.text_type(err))

        # Get reservations
        try:
            reserve_opts = {
                'workflows': -1,
                'workflow_gigabytes': -workflow.size,
            }
            reservations = QUOTAS.reserve(context,
                                          project_id=workflow.project_id,
                                          **reserve_opts)
        except Exception:
            reservations = None
            LOG.exception(_LE("Failed to update usages deleting workflow"))

        workflow.destroy()
        # If this workflow is incremental workflow, handle the
        # num_dependent_workflows of parent workflow
        if workflow.parent_id:
            parent_workflow = objects.Workflow.get_by_id(context,
                                                     workflow.parent_id)
            if parent_workflow.has_dependent_workflows:
                parent_workflow.num_dependent_workflows -= 1
                parent_workflow.save()
        # Commit the reservations
        if reservations:
            QUOTAS.commit(context, reservations,
                          project_id=workflow.project_id)

        LOG.info(_LI('Delete workflow finished, workflow %s deleted.'), workflow.id)
        self._notify_about_workflow_usage(context, workflow, "delete.end")

    def _notify_about_workflow_usage(self,
                                   context,
                                   workflow,
                                   event_suffix,
                                   extra_usage_info=None):
        pass
        #volume_utils.notify_about_workflow_usage(
        #    context, workflow, event_suffix,
        #    extra_usage_info=extra_usage_info,
        #    host=self.host)

    def export_record(self, context, workflow):
        """Export all volume workflow metadata details to allow clean import.

        Export workflow metadata so it could be re-imported into the database
        without any prerequisite in the workflow database.

        :param context: running context
        :param workflow: workflow object to export
        :returns: workflow_record - a description of how to import the workflow
        :returns: contains 'workflow_url' - how to import the workflow, and
        :returns: 'workflow_service' describing the needed driver.
        :raises: InvalidWorkflow
        """
        LOG.info(_LI('Export record started, workflow: %s.'), workflow.id)

        expected_status = fields.WorkflowStatus.AVAILABLE
        actual_status = workflow.status
        if actual_status != expected_status:
            err = (_('Export workflow aborted, expected workflow status '
                     '%(expected_status)s but got %(actual_status)s.') %
                   {'expected_status': expected_status,
                    'actual_status': actual_status})
            raise exception.InvalidWorkflow(reason=err)

        workflow_record = {}
        workflow_record['workflow_service'] = workflow.service
        workflow_service = self._map_service_to_driver(workflow.service)
        configured_service = self.driver_name
        if workflow_service != configured_service:
            err = (_('Export record aborted, the workflow service currently'
                     ' configured [%(configured_service)s] is not the'
                     ' workflow service that was used to create this'
                     ' workflow [%(workflow_service)s].') %
                   {'configured_service': configured_service,
                    'workflow_service': workflow_service})
            raise exception.InvalidWorkflow(reason=err)

        # Call driver to create workflow description string
        try:
            workflow_service = self.service.get_workflow_driver(context)
            driver_info = workflow_service.export_record(workflow)
            workflow_url = workflow.encode_record(driver_info=driver_info)
            workflow_record['workflow_url'] = workflow_url
        except Exception as err:
            msg = six.text_type(err)
            raise exception.InvalidWorkflow(reason=msg)

        LOG.info(_LI('Export record finished, workflow %s exported.'), workflow.id)
        return workflow_record

    def import_record(self,
                      context,
                      workflow,
                      workflow_service,
                      workflow_url,
                      workflow_hosts):
        """Import all volume workflow metadata details to the workflow db.

        :param context: running context
        :param workflow: The new workflow object for the import
        :param workflow_service: The needed workflow driver for import
        :param workflow_url: An identifier string to locate the workflow
        :param workflow_hosts: Potential hosts to execute the import
        :raises: InvalidWorkflow
        :raises: ServiceNotFound
        """
        LOG.info(_LI('Import record started, workflow_url: %s.'), workflow_url)

        # Can we import this workflow?
        if (workflow_service != self.driver_name):
            # No, are there additional potential workflow hosts in the list?
            if len(workflow_hosts) > 0:
                # try the next host on the list, maybe he can import
                first_host = workflow_hosts.pop()
                self.workflow_rpcapi.import_record(context,
                                                 first_host,
                                                 workflow,
                                                 workflow_service,
                                                 workflow_url,
                                                 workflow_hosts)
            else:
                # empty list - we are the last host on the list, fail
                err = _('Import record failed, cannot find workflow '
                        'service to perform the import. Request service '
                        '%(service)s') % {'service': workflow_service}
                self._update_workflow_error(workflow, context, err)
                raise exception.ServiceNotFound(service_id=workflow_service)
        else:
            # Yes...
            try:
                # Deserialize workflow record information
                workflow_options = workflow.decode_record(workflow_url)

                # Extract driver specific info and pass it to the driver
                driver_options = workflow_options.pop('driver_info', {})
                workflow_service = self.service.get_workflow_driver(context)
                workflow_service.import_record(workflow, driver_options)
            except Exception as err:
                msg = six.text_type(err)
                self._update_workflow_error(workflow, context, msg)
                raise exception.InvalidWorkflow(reason=msg)

            required_import_options = {
                'display_name',
                'display_description',
                'container',
                'size',
                'service_metadata',
                'service',
                'object_count',
                'id'
            }

            # Check for missing fields in imported data
            missing_opts = required_import_options - set(workflow_options)
            if missing_opts:
                msg = (_('Driver successfully decoded imported workflow data, '
                         'but there are missing fields (%s).') %
                       ', '.join(missing_opts))
                self._update_workflow_error(workflow, context, msg)
                raise exception.InvalidWorkflow(reason=msg)

            # Confirm the ID from the record in the DB is the right one
            workflow_id = workflow_options['id']
            if workflow_id != workflow.id:
                msg = (_('Trying to import workflow metadata from id %(meta_id)s'
                         ' into workflow %(id)s.') %
                       {'meta_id': workflow_id, 'id': workflow.id})
                self._update_workflow_error(workflow, context, msg)
                raise exception.InvalidWorkflow(reason=msg)

            # Overwrite some fields
            workflow_options['status'] = fields.WorkflowStatus.AVAILABLE
            workflow_options['service'] = self.driver_name
            workflow_options['availability_zone'] = self.az
            workflow_options['host'] = self.host

            # Remove some values which are not actual fields and some that
            # were set by the API node
            for key in ('name', 'user_id', 'project_id'):
                workflow_options.pop(key, None)

            # Update the database
            workflow.update(workflow_options)
            workflow.save()

            # Verify workflow
            try:
                if isinstance(workflow_service, driver.WorkflowDriverWithVerify):
                    workflow_service.verify(workflow.id)
                else:
                    LOG.warning(_LW('Workflow service %(service)s does not '
                                    'support verify. Workflow id %(id)s is '
                                    'not verified. Skipping verify.'),
                                {'service': self.driver_name,
                                 'id': workflow.id})
            except exception.InvalidWorkflow as err:
                with excutils.save_and_reraise_exception():
                    self._update_workflow_error(workflow, context,
                                              six.text_type(err))

            LOG.info(_LI('Import record id %s metadata from driver '
                         'finished.'), workflow.id)

    def reset_status(self, context, workflow, status):
        """Reset volume workflow status.

        :param context: running context
        :param workflow: The workflow object for reset status operation
        :param status: The status to be set
        :raises: InvalidWorkflow
        :raises: WorkflowVerifyUnsupportedDriver
        :raises: AttributeError
        """
        LOG.info(_LI('Reset workflow status started, workflow_id: '
                     '%(workflow_id)s, status: %(status)s.'),
                 {'workflow_id': workflow.id,
                  'status': status})

        workflow_service = self._map_service_to_driver(workflow.service)
        LOG.info(_LI('Workflow service: %s.'), workflow_service)
        if workflow_service is not None:
            configured_service = self.driver_name
            if workflow_service != configured_service:
                err = _('Reset workflow status aborted, the workflow service'
                        ' currently configured [%(configured_service)s] '
                        'is not the workflow service that was used to create'
                        ' this workflow [%(workflow_service)s].') % \
                    {'configured_service': configured_service,
                     'workflow_service': workflow_service}
                raise exception.InvalidWorkflow(reason=err)
            # Verify workflow
            try:
                # check whether the workflow is ok or not
                if (status == fields.WorkflowStatus.AVAILABLE
                        and workflow['status'] != fields.WorkflowStatus.RESTORING):
                    # check whether we could verify the workflow is ok or not
                    if isinstance(workflow_service,
                                  driver.WorkflowDriverWithVerify):
                        workflow_service.verify(workflow.id)
                        workflow.status = status
                        workflow.save()
                    # driver does not support verify function
                    else:
                        msg = (_('Workflow service %(configured_service)s '
                                 'does not support verify. Workflow id'
                                 ' %(id)s is not verified. '
                                 'Skipping verify.') %
                               {'configured_service': self.driver_name,
                                'id': workflow.id})
                        raise exception.WorkflowVerifyUnsupportedDriver(
                            reason=msg)
                # reset status to error or from restoring to available
                else:
                    if (status == fields.WorkflowStatus.ERROR or
                        (status == fields.WorkflowStatus.AVAILABLE and
                            workflow.status == fields.WorkflowStatus.RESTORING)):
                        workflow.status = status
                        workflow.save()
            except exception.InvalidWorkflow:
                with excutils.save_and_reraise_exception():
                    LOG.error(_LE("Workflow id %s is not invalid. "
                                  "Skipping reset."), workflow.id)
            except exception.WorkflowVerifyUnsupportedDriver:
                with excutils.save_and_reraise_exception():
                    LOG.error(_LE('Workflow service %(configured_service)s '
                                  'does not support verify. Workflow id '
                                  '%(id)s is not verified. '
                                  'Skipping verify.'),
                              {'configured_service': self.driver_name,
                               'id': workflow.id})
            except AttributeError:
                msg = (_('Workflow service %(service)s does not support '
                         'verify. Workflow id %(id)s is not verified. '
                         'Skipping reset.') %
                       {'service': self.driver_name,
                        'id': workflow.id})
                LOG.error(msg)
                raise exception.WorkflowVerifyUnsupportedDriver(
                    reason=msg)

            # Needs to clean temporary volumes and snapshots.
            try:
                self._cleanup_temp_volumes_snapshots_for_one_workflow(
                    context, workflow)
            except Exception:
                LOG.exception(_LE("Problem cleaning temp volumes and "
                                  "snapshots for workflow %(bkup)s."),
                              {'bkup': workflow.id})

            # send notification to ceilometer
            notifier_info = {'id': workflow.id, 'update': {'status': status}}
            notifier = rpc.get_notifier('workflowStatusUpdate')
            notifier.info(context, "workflows.reset_status.end",
                          notifier_info)

    def check_support_to_force_delete(self, context):
        """Check if the workflow driver supports force delete operation.

        :param context: running context
        """
        workflow_service = self.service.get_workflow_driver(context)
        return workflow_service.support_force_delete

    def _attach_device(self, context, workflow_device,
                       properties, is_snapshot=False):
        """Attach workflow device."""
        if not is_snapshot:
            return self._attach_volume(context, workflow_device, properties)
        else:
            volume = self.db.volume_get(context, workflow_device.volume_id)
            host = volume_utils.extract_host(volume['host'], 'backend')
            backend = self._get_volume_backend(host=host)
            rc = self._get_driver(backend)._attach_snapshot(
                context, workflow_device, properties)
            return rc

    def _attach_volume(self, context, volume, properties):
        """Attach a volume."""

        try:
            conn = self.volume_rpcapi.initialize_connection(context,
                                                            volume,
                                                            properties)
            return self._connect_device(conn)
        except Exception:
            with excutils.save_and_reraise_exception():
                try:
                    self.volume_rpcapi.terminate_connection(context, volume,
                                                            properties,
                                                            force=True)
                except Exception:
                    LOG.warning(_LW("Failed to terminate the connection "
                                    "of volume %(volume_id)s, but it is "
                                    "acceptable."),
                                {'volume_id', volume.id})

    def _connect_device(self, conn):
        """Establish connection to device."""
        use_multipath = CONF.use_multipath_for_image_xfer
        device_scan_attempts = CONF.num_volume_device_scan_tries
        protocol = conn['driver_volume_type']
        connector = utils.brick_get_connector(
            protocol,
            use_multipath=use_multipath,
            device_scan_attempts=device_scan_attempts,
            conn=conn)
        vol_handle = connector.connect_volume(conn['data'])

        return {'conn': conn, 'device': vol_handle, 'connector': connector}

    def _detach_device(self, context, attach_info, device,
                       properties, is_snapshot=False, force=False):
        """Disconnect the volume or snapshot from the host. """
        connector = attach_info['connector']
        connector.disconnect_volume(attach_info['conn']['data'],
                                    attach_info['device'])

        rpcapi = self.volume_rpcapi
        if not is_snapshot:
            rpcapi.terminate_connection(context, device, properties,
                                        force=force)
            rpcapi.remove_export(context, device)
        else:
            volume = self.db.volume_get(context, device.volume_id)
            host = volume_utils.extract_host(volume['host'], 'backend')
            backend = self._get_volume_backend(host=host)
            self._get_driver(backend)._detach_snapshot(
                context, attach_info, device, properties, force)


# TODO(dulek): This goes away immediately in Newton and is just present in
# Mitaka so that we can receive v1.x and v2.0 messages.
class _WorkflowV1Proxy(object):

    target = messaging.Target(version='1.3')

    def __init__(self, manager):
        self.manager = manager

    def create_workflow(self, context, workflow):
        return self.manager.create_workflow(context, workflow)

    def restore_workflow(self, context, workflow, volume_id):
        return self.manager.restore_workflow(context, workflow, volume_id)

    def delete_workflow(self, context, workflow):
        return self.manager.delete_workflow(context, workflow)

    def export_record(self, context, workflow):
        return self.manager.export_record(context, workflow)

    def import_record(self, context, workflow, workflow_service, workflow_url,
                      workflow_hosts):
        return self.manager.import_record(context, workflow, workflow_service,
                                          workflow_url, workflow_hosts)

    def reset_status(self, context, workflow, status):
        return self.manager.reset_status(context, workflow, status)

    def check_support_to_force_delete(self, context):
        return self.manager.check_support_to_force_delete(context)
