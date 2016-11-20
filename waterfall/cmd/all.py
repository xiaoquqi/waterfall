#!/usr/bin/env python
# Copyright 2011 OpenStack, LLC
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Starter script for All waterfall services.

This script attempts to start all the waterfall services in one process.  Each
service is started in its own greenthread.  Please note that exceptions and
sys.exit() on the starting of a service are logged and the script will
continue attempting to launch the rest of the services.

"""

import eventlet
eventlet.monkey_patch()

import sys

from oslo_config import cfg
from oslo_log import log as logging
from oslo_reports import guru_meditation_report as gmr
from oslo_reports import opts as gmr_opts

from waterfall import i18n
i18n.enable_lazy()

# Need to register global_opts
from waterfall.cmd import workflow as workflow_cmd
from waterfall.common import config   # noqa
from waterfall.db import api as session
from waterfall.i18n import _LE
from waterfall import objects
from waterfall import rpc
from waterfall import service
from waterfall import utils
from waterfall import version


CONF = cfg.CONF


# TODO(e0ne): get a rid of code duplication in waterfall.cmd module in Mitaka
def main():
    objects.register_all()
    gmr_opts.set_defaults(CONF)
    CONF(sys.argv[1:], project='waterfall',
         version=version.version_string())
    config.set_middleware_defaults()
    logging.setup(CONF, "waterfall")
    LOG = logging.getLogger('waterfall.all')

    utils.monkey_patch()

    gmr.TextGuruMeditation.setup_autorun(version, conf=CONF)

    rpc.init(CONF)

    launcher = service.process_launcher()
    # waterfall-api
    try:
        server = service.WSGIService('osapi_workflow')
        launcher.launch_service(server, workers=server.workers or 1)
    except (Exception, SystemExit):
        LOG.exception(_LE('Failed to load osapi_workflow'))

    for binary in ['waterfall-scheduler', 'waterfall-backup']:
        try:
            launcher.launch_service(service.Service.create(binary=binary))
        except (Exception, SystemExit):
            LOG.exception(_LE('Failed to load %s'), binary)

    # waterfall-workflow
    try:
        if CONF.enabled_backends:
            for backend in CONF.enabled_backends:
                CONF.register_opt(workflow_cmd.host_opt, group=backend)
                backend_host = getattr(CONF, backend).backend_host
                host = "%s@%s" % (backend_host or CONF.host, backend)
                server = service.Service.create(host=host,
                                                service_name=backend,
                                                binary='waterfall-workflow')
                # Dispose of the whole DB connection pool here before
                # starting another process.  Otherwise we run into cases
                # where child processes share DB connections which results
                # in errors.
                session.dispose_engine()
                launcher.launch_service(server)
        else:
            server = service.Service.create(binary='waterfall-workflow')
            launcher.launch_service(server)
    except (Exception, SystemExit):
        LOG.exception(_LE('Failed to load conder-workflow'))

    launcher.wait()
