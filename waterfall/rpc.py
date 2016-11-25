# Copyright 2013 Red Hat, Inc.
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

__all__ = [
    'init',
    'cleanup',
    'set_defaults',
    'add_extra_exmods',
    'clear_extra_exmods',
    'get_allowed_exmods',
    'RequestContextSerializer',
    'get_client',
    'get_server',
    'get_notifier',
    'TRANSPORT_ALIASES',
]

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_serialization import jsonutils
from oslo_utils import importutils
profiler = importutils.try_import('osprofiler.profiler')

import waterfall.context
import waterfall.exception
from waterfall.i18n import _LI
from waterfall import objects
from waterfall.objects import base

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
TRANSPORT = None
NOTIFIER = None

ALLOWED_EXMODS = [
    waterfall.exception.__name__,
]
EXTRA_EXMODS = []

# NOTE(flaper87): The waterfall.openstack.common.rpc entries are
# for backwards compat with Havana rpc_backend configuration
# values. The waterfall.rpc entries are for compat with Folsom values.
TRANSPORT_ALIASES = {
    'waterfall.openstack.common.rpc.impl_kombu': 'rabbit',
    'waterfall.openstack.common.rpc.impl_qpid': 'qpid',
    'waterfall.openstack.common.rpc.impl_zmq': 'zmq',
    'waterfall.rpc.impl_kombu': 'rabbit',
    'waterfall.rpc.impl_qpid': 'qpid',
    'waterfall.rpc.impl_zmq': 'zmq',
}


def init(conf):
    global TRANSPORT, NOTIFIER
    exmods = get_allowed_exmods()
    TRANSPORT = messaging.get_transport(conf,
                                        allowed_remote_exmods=exmods,
                                        aliases=TRANSPORT_ALIASES)

    serializer = RequestContextSerializer(JsonPayloadSerializer())
    NOTIFIER = messaging.Notifier(TRANSPORT, serializer=serializer)


def initialized():
    return None not in [TRANSPORT, NOTIFIER]


def cleanup():
    global TRANSPORT, NOTIFIER
    assert TRANSPORT is not None
    assert NOTIFIER is not None
    TRANSPORT.cleanup()
    TRANSPORT = NOTIFIER = None


def set_defaults(control_exchange):
    messaging.set_transport_defaults(control_exchange)


def add_extra_exmods(*args):
    EXTRA_EXMODS.extend(args)


def clear_extra_exmods():
    del EXTRA_EXMODS[:]


def get_allowed_exmods():
    return ALLOWED_EXMODS + EXTRA_EXMODS


class JsonPayloadSerializer(messaging.NoOpSerializer):
    @staticmethod
    def serialize_entity(context, entity):
        return jsonutils.to_primitive(entity, convert_instances=True)


class RequestContextSerializer(messaging.Serializer):

    def __init__(self, base):
        self._base = base

    def serialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.serialize_entity(context, entity)

    def deserialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.deserialize_entity(context, entity)

    def serialize_context(self, context):
        _context = context.to_dict()
        if profiler is not None:
            prof = profiler.get()
            if prof:
                trace_info = {
                    "hmac_key": prof.hmac_key,
                    "base_id": prof.get_base_id(),
                    "parent_id": prof.get_id()
                }
                _context.update({"trace_info": trace_info})
        return _context

    def deserialize_context(self, context):
        trace_info = context.pop("trace_info", None)
        if trace_info:
            if profiler is not None:
                profiler.init(**trace_info)

        return waterfall.context.RequestContext.from_dict(context)


def get_client(target, version_cap=None, serializer=None):
    assert TRANSPORT is not None
    serializer = RequestContextSerializer(serializer)
    return messaging.RPCClient(TRANSPORT,
                               target,
                               version_cap=version_cap,
                               serializer=serializer)


def get_server(target, endpoints, serializer=None):
    assert TRANSPORT is not None
    serializer = RequestContextSerializer(serializer)
    return messaging.get_rpc_server(TRANSPORT,
                                    target,
                                    endpoints,
                                    executor='eventlet',
                                    serializer=serializer)


def get_notifier(service=None, host=None, publisher_id=None):
    assert NOTIFIER is not None
    if not publisher_id:
        publisher_id = "%s.%s" % (service, host or CONF.host)
    return NOTIFIER.prepare(publisher_id=publisher_id)


LAST_RPC_VERSIONS = {}
LAST_OBJ_VERSIONS = {}


class RPCAPI(object):
    """Mixin class aggregating methods related to RPC API compatibility."""

    RPC_API_VERSION = '1.0'
    TOPIC = ''
    BINARY = ''

    def __init__(self):
        target = messaging.Target(topic=self.TOPIC,
                                  version=self.RPC_API_VERSION)
        #obj_version_cap = self._determine_obj_version_cap()
        #serializer = base.WaterfallObjectSerializer(obj_version_cap)

        #rpc_version_cap = self._determine_rpc_version_cap()
        #self.client = get_client(target, version_cap=rpc_version_cap,
        #                         serializer=serializer)

    def _determine_rpc_version_cap(self):
        global LAST_RPC_VERSIONS
        if self.BINARY in LAST_RPC_VERSIONS:
            return LAST_RPC_VERSIONS[self.BINARY]

        version_cap = objects.Service.get_minimum_rpc_version(
            waterfall.context.get_admin_context(), self.BINARY)
        if version_cap == 'liberty':
            # NOTE(dulek): This means that one of the services is Liberty,
            # we should cap to it's RPC version.
            version_cap = LIBERTY_RPC_VERSIONS[self.BINARY]
        elif not version_cap:
            # If there is no service we assume they will come up later and will
            # have the same version as we do.
            version_cap = self.RPC_API_VERSION
        LOG.info(_LI('Automatically selected %(binary)s RPC version '
                     '%(version)s as minimum service version.'),
                 {'binary': self.BINARY, 'version': version_cap})
        LAST_RPC_VERSIONS[self.BINARY] = version_cap
        return version_cap

    def _determine_obj_version_cap(self):
        global LAST_OBJ_VERSIONS
        if self.BINARY in LAST_OBJ_VERSIONS:
            return LAST_OBJ_VERSIONS[self.BINARY]

        version_cap = objects.Service.get_minimum_obj_version(
            waterfall.context.get_admin_context(), self.BINARY)
        # If there is no service we assume they will come up later and will
        # have the same version as we do.
        if not version_cap:
            version_cap = base.OBJ_VERSIONS.get_current()
        LOG.info(_LI('Automatically selected %(binary)s objects version '
                     '%(version)s as minimum service version.'),
                 {'binary': self.BINARY, 'version': version_cap})
        LAST_OBJ_VERSIONS[self.BINARY] = version_cap
        return version_cap


# FIXME(dulek): Liberty haven't reported its RPC versions, so we need to have
# them hardcoded. This dict may go away as soon as we drop compatibility with
# L, which should be in early N.
#
# This is the only time we need to have such dictionary. We don't need to add
# similar ones for any release following Liberty.
LIBERTY_RPC_VERSIONS = {
    'waterfall-workflow': '1.30',
    'waterfall-scheduler': '1.8',
    # NOTE(dulek) backup.manager had specified version '1.2', but backup.rpcapi
    # was really only sending messages up to '1.1'.
    'waterfall-backup': '1.1',
}
