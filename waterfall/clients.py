# Copyright 2014
# The Cloudscaling Group, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cinderclient import client as cinderclient
from glanceclient import client as glanceclient
from keystoneauth1 import loading as ks_loading
from keystoneclient.auth.identity.generic import password as keystone_auth
from keystoneclient import client as keystoneclient
from keystoneclient import session as keystone_session
from neutronclient.v2_0 import client as neutronclient
from novaclient import api_versions as nova_api_versions
from novaclient import client as novaclient
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging

from waterfall.i18n import _, _LI, _LW

logger = logging.getLogger(__name__)

ec2_opts = [
    cfg.BoolOpt('ssl_insecure',
                default=False,
                deprecated_for_removal=True,
                deprecated_reason='code was switched to common section '
                                  '"keystone_authtoken"',
                deprecated_since='Newton',
                help="Verify HTTPS connections."),
    cfg.StrOpt('ssl_ca_file',
               deprecated_for_removal=True,
               deprecated_reason='code was switched to common section '
                                 '"keystone_authtoken"',
               deprecated_since='Newton',
               help="CA certificate file to use to verify "
                    "connecting clients"),
    cfg.StrOpt('nova_service_type',
               default='compute',
               help='Service type of Compute API, registered in Keystone '
                    'catalog. Should be v2.1 with microversion support. '
                    'If it is obsolete v2, a lot of useful EC2 compliant '
                    'instance properties will be unavailable.'),
    cfg.StrOpt('cinder_service_type',
               default='volumev2',
               help='Service type of Volume API, registered in Keystone '
                    'catalog.'),
    cfg.StrOpt('admin_user',
               deprecated_for_removal=True,
               deprecated_reason='code was switched to common section '
                                 '"keystone_authtoken"',
               deprecated_since='Newton',
               help=_("Admin user to access specific cloud resourses")),
    cfg.StrOpt('admin_password',
               deprecated_for_removal=True,
               deprecated_reason='code was switched to common section '
                                 '"keystone_authtoken"',
               deprecated_since='Newton',
               help=_("Admin password"),
               secret=True),
    cfg.StrOpt('admin_tenant_name',
               deprecated_for_removal=True,
               deprecated_reason='code was switched to common section '
                                 '"keystone_authtoken"',
               deprecated_since='Newton',
               help=_("Admin tenant name")),
]

CONF = cfg.CONF
CONF.register_opts(ec2_opts)

GROUP_AUTHTOKEN = 'keystone_authtoken'
ks_loading.register_session_conf_options(CONF, GROUP_AUTHTOKEN)
ks_loading.register_auth_conf_options(CONF, GROUP_AUTHTOKEN)


# Nova API version with microversions support
REQUIRED_NOVA_API_VERSION = '2.1'
REQUIRED_NOVA_API_VERSION_ID = 'v%s' % REQUIRED_NOVA_API_VERSION
LEGACY_NOVA_API_VERSION = '2'
# Nova API's 2.3 microversion provides additional EC2 compliant instance
# properties
# Nova API's 2.10 microversion provides admin access to users keypairs,
# which allows metadata service to expose openssh part of an instance key
REQUIRED_NOVA_API_MICROVERSION = '2.10'
_nova_api_version = None


def nova(context):
    global _nova_api_version
    if not _nova_api_version:
        _nova_api_version = _get_nova_api_version(context)
    clnt = novaclient.Client(_nova_api_version,
                             session=context.session,
                             service_type=CONF.nova_service_type)
    # NOTE(ft): workaround for LP #1494116 bug
    if not hasattr(clnt.client, 'last_request_id'):
        setattr(clnt.client, 'last_request_id', None)
    return clnt


def neutron(context):
    return neutronclient.Client(session=context.session,
                                service_type='network')


def glance(context):
    return glanceclient.Client('1', service_type='image',
                               session=context.session)


def cinder(context):
    url = context.session.get_endpoint(service_type=CONF.cinder_service_type)
    # TODO(jamielennox): This should be using proper version discovery from
    # the cinder service rather than just inspecting the URL for certain string
    # values.
    version = cinderclient.get_volume_api_from_url(url)
    return cinderclient.Client(version, session=context.session,
                               service_type=CONF.cinder_service_type)


def keystone(context):
    url = context.session.get_endpoint(service_type='identity')
    return keystoneclient.Client(auth_url=url,
                                 session=context.session)


def nova_cert(context):
    _cert_api = _rpcapi_CertAPI(context)
    return _cert_api


def _get_nova_api_version(context):
    client = novaclient.Client(REQUIRED_NOVA_API_VERSION,
                               session=context.session,
                               service_type=CONF.nova_service_type)

    required = nova_api_versions.APIVersion(REQUIRED_NOVA_API_MICROVERSION)
    current = client.versions.get_current()
    if not current:
        logger.warning(
            _LW('Could not check Nova API version because no version '
                'was found in Nova version list for url %(url)s of service '
                'type "%(service_type)s". '
                'Use v%(required_api_version)s Nova API.'),
            {'url': client.client.get_endpoint(),
             'service_type': CONF.nova_service_type,
             'required_api_version': REQUIRED_NOVA_API_MICROVERSION})
        return REQUIRED_NOVA_API_MICROVERSION
    if current.id != REQUIRED_NOVA_API_VERSION_ID:
        logger.warning(
            _LW('Specified "%s" Nova service type does not support v2.1 API. '
                'A lot of useful EC2 compliant instance properties '
                'will be unavailable.'),
            CONF.nova_service_type)
        return LEGACY_NOVA_API_VERSION
    if (nova_api_versions.APIVersion(current.version) < required):
        logger.warning(
            _LW('Nova support v%(nova_api_version)s, '
                'but v%(required_api_version)s is required. '
                'A lot of useful EC2 compliant instance properties '
                'will be unavailable.'),
            {'nova_api_version': current.version,
             'required_api_version': REQUIRED_NOVA_API_MICROVERSION})
        return current.version
    logger.info(_LI('Provided Nova API version is  v%(nova_api_version)s, '
                    'used one is v%(required_api_version)s'),
                {'nova_api_version': current.version,
                 'required_api_version': (
                        REQUIRED_NOVA_API_MICROVERSION)})
    return REQUIRED_NOVA_API_MICROVERSION


class _rpcapi_CertAPI(object):
    '''Client side of the cert rpc API.'''

    def __init__(self, context):
        super(_rpcapi_CertAPI, self).__init__()
        target = messaging.Target(topic=CONF.cert_topic, version='2.0')
        self.client = _rpc_get_client(target)
        self.context = context

    def decrypt_text(self, text):
        cctxt = self.client.prepare()
        return cctxt.call(self.context, 'decrypt_text',
                          project_id=self.context.project_id,
                          text=text)


_rpc_TRANSPORT = None


def _rpc_init(conf):
    global _rpc_TRANSPORT
    # NOTE(ft): set control_exchange parameter to use Nova cert topic
    messaging.set_transport_defaults('nova')
    _rpc_TRANSPORT = messaging.get_transport(conf)


def _rpc_get_client(target):
    if not _rpc_TRANSPORT:
        _rpc_init(CONF)
    assert _rpc_TRANSPORT is not None
    serializer = _rpc_RequestContextSerializer()
    return messaging.RPCClient(_rpc_TRANSPORT,
                               target,
                               serializer=serializer)


class _rpc_RequestContextSerializer(messaging.NoOpSerializer):

    def serialize_context(self, context):
        return context.to_dict()


_admin_session = None


def get_session_from_deprecated():
    auth = keystone_auth.Password(
        username=CONF.admin_user,
        password=CONF.admin_password,
        project_name=CONF.admin_tenant_name,
        tenant_name=CONF.admin_tenant_name,
        auth_url=CONF.keystone_url,
    )
    params = {'auth': auth}
    update_request_params_with_ssl(params)
    return keystone_session.Session(**params)


def get_os_admin_session():
    """Create a context to interact with OpenStack as an administrator."""
    # NOTE(ft): this is a singletone because keystone's session looks thread
    # safe for both regular and token renewal requests
    global _admin_session
    if not _admin_session:
        if not CONF[GROUP_AUTHTOKEN].auth_type:
            _admin_session = get_session_from_deprecated()
        else:
            auth_plugin = ks_loading.load_auth_from_conf_options(
                CONF, GROUP_AUTHTOKEN)
            _admin_session = ks_loading.load_session_from_conf_options(
                CONF, GROUP_AUTHTOKEN, auth=auth_plugin)

    return _admin_session


def update_request_params_with_ssl(params):
    if not CONF[GROUP_AUTHTOKEN].auth_type:
        verify = CONF.ssl_ca_file or not CONF.ssl_insecure
    else:
        verify = (CONF[GROUP_AUTHTOKEN].cafile or
                  not CONF[GROUP_AUTHTOKEN].insecure)
    if verify is not True:
        params['verify'] = verify
