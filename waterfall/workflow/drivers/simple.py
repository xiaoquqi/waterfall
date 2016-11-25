from oslo_config import cfg
from oslo_log import log as logging

from waterfall import exception
from waterfall.workflow import driver

VERSION = '1.1.1'

LOG = logging.getLogger(__name__)

simple_opts = [
    cfg.StrOpt('simple_config',
               default='just for demo',
               help='How to add a opts'),
]

CONF = cfg.CONF
CONF.register_opts(simple_opts)


class SimpleDriver(driver.WorkflowDriver):

    def apply(self):
        LOG.debug("Simple Apply")

    def is_approved(self):
        pass
