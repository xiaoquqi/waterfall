"""Drivers for workflow"""

from oslo_config import cfg
from oslo_log import log as logging


LOG = logging.getLogger(__name__)

workflow_opts = [
    cfg.StrOpt('workflow_backend_name',
               help='The backend name for a given driver implementation'),
]

CONF = cfg.CONF
CONF.register_opts(workflow_opts)

class WorkflowDriver(object):

    def apply(self):
        raise NotImplementedError()

    def is_approved(self):
        raise NotImplementedError()
