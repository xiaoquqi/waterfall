# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# Copyright 2012 Red Hat, Inc.
# Copyright 2013 NTT corp.
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

"""Command-line flag library.

Emulates gflags by wrapping cfg.ConfigOpts.

The idea is to move fully to cfg eventually, and this wrapper is a
stepping stone.

"""

import socket

from oslo_config import cfg
from oslo_log import log as logging
from oslo_middleware import cors
from oslo_utils import netutils

from waterfall.i18n import _


CONF = cfg.CONF
logging.register_options(CONF)

core_opts = [
    cfg.StrOpt('state_path',
               default='/var/lib/waterfall',
               deprecated_name='pybasedir',
               help="Top-level directory for maintaining waterfall's state"), ]

debug_opts = [
]

CONF.register_cli_opts(core_opts)
CONF.register_cli_opts(debug_opts)

global_opts = [
    cfg.StrOpt('my_ip',
               default=netutils.get_my_ipv4(),
               help='IP address of this host'),
    cfg.StrOpt('glance_host',
               default='$my_ip',
               help='Default glance host name or IP'),
    cfg.IntOpt('glance_port',
               default=9292,
               min=1, max=65535,
               help='Default glance port'),
    cfg.ListOpt('glance_api_servers',
                default=['$glance_host:$glance_port'],
                help='A list of the URLs of glance API servers available to '
                     'waterfall ([http[s]://][hostname|ip]:port). If protocol '
                     'is not specified it defaults to http.'),
    cfg.IntOpt('glance_api_version',
               default=1,
               help='Version of the glance API to use'),
    cfg.IntOpt('glance_num_retries',
               default=0,
               help='Number retries when downloading an image from glance'),
    cfg.BoolOpt('glance_api_insecure',
                default=False,
                help='Allow to perform insecure SSL (https) requests to '
                     'glance'),
    cfg.BoolOpt('glance_api_ssl_compression',
                default=False,
                help='Enables or disables negotiation of SSL layer '
                     'compression. In some cases disabling compression '
                     'can improve data throughput, such as when high '
                     'network bandwidth is available and you use '
                     'compressed image formats like qcow2.'),
    cfg.StrOpt('glance_ca_certificates_file',
               help='Location of ca certificates file to use for glance '
                    'client requests.'),
    cfg.IntOpt('glance_request_timeout',
               help='http/https timeout value for glance operations. If no '
                    'value (None) is supplied here, the glanceclient default '
                    'value is used.'),
    cfg.StrOpt('scheduler_topic',
               default='waterfall-scheduler',
               help='The topic that scheduler nodes listen on'),
    cfg.StrOpt('workflow_topic',
               default='waterfall-workflow',
               help='The topic that workflow nodes listen on'),
    cfg.StrOpt('backup_topic',
               default='waterfall-backup',
               help='The topic that workflow backup nodes listen on'),
    cfg.BoolOpt('enable_v1_api',
                default=True,
                help=_("DEPRECATED: Deploy v1 of the Waterfall API.")),
    cfg.BoolOpt('enable_v2_api',
                default=True,
                help=_("DEPRECATED: Deploy v2 of the Waterfall API.")),
    cfg.BoolOpt('enable_v3_api',
                default=True,
                help=_("Deploy v3 of the Waterfall API.")),
    cfg.BoolOpt('api_rate_limit',
                default=True,
                help='Enables or disables rate limit of the API.'),
    cfg.ListOpt('osapi_workflow_ext_list',
                default=[],
                help='Specify list of extensions to load when using osapi_'
                     'workflow_extension option with waterfall.api.contrib.'
                     'select_extensions'),
    cfg.MultiStrOpt('osapi_workflow_extension',
                    default=['waterfall.api.contrib.standard_extensions'],
                    help='osapi workflow extension to load'),
    cfg.StrOpt('workflow_manager',
               default='waterfall.workflow.manager.WorkflowManager',
               help='Full class name for the Manager for workflow'),
    cfg.StrOpt('backup_manager',
               default='waterfall.backup.manager.BackupManager',
               help='Full class name for the Manager for workflow backup'),
    cfg.StrOpt('scheduler_manager',
               default='waterfall.scheduler.manager.SchedulerManager',
               help='Full class name for the Manager for scheduler'),
    cfg.StrOpt('host',
               default=socket.gethostname(),
               help='Name of this node.  This can be an opaque identifier. '
                    'It is not necessarily a host name, FQDN, or IP address.'),
    # NOTE(vish): default to nova for compatibility with nova installs
    cfg.StrOpt('storage_availability_zone',
               default='nova',
               help='Availability zone of this node'),
    cfg.StrOpt('default_availability_zone',
               help='Default availability zone for new workflows. If not set, '
                    'the storage_availability_zone option value is used as '
                    'the default for new workflows.'),
    cfg.BoolOpt('allow_availability_zone_fallback',
                default=False,
                help='If the requested Waterfall availability zone is '
                     'unavailable, fall back to the value of '
                     'default_availability_zone, then '
                     'storage_availability_zone, instead of failing.'),
    cfg.StrOpt('default_workflow_type',
               help='Default workflow type to use'),
    cfg.StrOpt('workflow_usage_audit_period',
               default='month',
               help='Time period for which to generate workflow usages. '
                    'The options are hour, day, month, or year.'),
    cfg.StrOpt('rootwrap_config',
               default='/etc/waterfall/rootwrap.conf',
               help='Path to the rootwrap configuration file to use for '
                    'running commands as root'),
    cfg.BoolOpt('monkey_patch',
                default=False,
                help='Enable monkey patching'),
    cfg.ListOpt('monkey_patch_modules',
                default=[],
                help='List of modules/decorators to monkey patch'),
    cfg.IntOpt('service_down_time',
               default=60,
               help='Maximum time since last check-in for a service to be '
                    'considered up'),
    cfg.StrOpt('workflow_api_class',
               default='waterfall.workflow.api.API',
               help='The full class name of the workflow API class to use'),
    cfg.StrOpt('backup_api_class',
               default='waterfall.backup.api.API',
               help='The full class name of the workflow backup API class'),
    cfg.StrOpt('auth_strategy',
               default='keystone',
               choices=['noauth', 'keystone'],
               help='The strategy to use for auth. Supports noauth or '
                    'keystone.'),
    cfg.ListOpt('enabled_backends',
                help='A list of backend names to use. These backend names '
                     'should be backed by a unique [CONFIG] group '
                     'with its options'),
    cfg.BoolOpt('no_snapshot_gb_quota',
                default=False,
                help='Whether snapshots count against gigabyte quota'),
    cfg.StrOpt('transfer_api_class',
               default='waterfall.transfer.api.API',
               help='The full class name of the workflow transfer API class'),
    cfg.StrOpt('replication_api_class',
               default='waterfall.replication.api.API',
               help='The full class name of the workflow replication API class'),
    cfg.StrOpt('consistencygroup_api_class',
               default='waterfall.consistencygroup.api.API',
               help='The full class name of the consistencygroup API class'),
    cfg.StrOpt('os_privileged_user_name',
               help='OpenStack privileged account username. Used for requests '
                    'to other services (such as Nova) that require an account '
                    'with special rights.'),
    cfg.StrOpt('os_privileged_user_password',
               help='Password associated with the OpenStack privileged '
                    'account.',
               secret=True),
    cfg.StrOpt('os_privileged_user_tenant',
               help='Tenant name associated with the OpenStack privileged '
                    'account.'),
    cfg.StrOpt('os_privileged_user_auth_url',
               help='Auth URL associated with the OpenStack privileged '
                    'account.'),
]

CONF.register_opts(global_opts)


def set_middleware_defaults():
    """Update default configuration options for oslo.middleware."""
    # CORS Defaults
    # TODO(krotscheck): Update with https://review.openstack.org/#/c/285368/
    cfg.set_defaults(cors.CORS_OPTS,
                     allow_headers=['X-Auth-Token',
                                    'X-Identity-Status',
                                    'X-Roles',
                                    'X-Service-Catalog',
                                    'X-User-Id',
                                    'X-Tenant-Id',
                                    'X-OpenStack-Request-ID',
                                    'X-Trace-Info',
                                    'X-Trace-HMAC',
                                    'OpenStack-API-Version'],
                     expose_headers=['X-Auth-Token',
                                     'X-Subject-Token',
                                     'X-Service-Token',
                                     'X-OpenStack-Request-ID',
                                     'OpenStack-API-Version'],
                     allow_methods=['GET',
                                    'PUT',
                                    'POST',
                                    'DELETE',
                                    'PATCH',
                                    'HEAD']
                     )
