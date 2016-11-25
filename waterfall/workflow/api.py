from waterfall.db import base
from waterfall.workflow import rpcapi

class API(base.Base):
    """API for interacting with the recover manager."""

    def __init__(self, db_driver=None, image_service=None):
        super(API, self).__init__(db_driver)

    def workflow_get_all(self, context):
        return self.db.workflow_get_all(context)

    def workflow_create(self, context, resource_type, payload):
        workflow = self.db.workflow_create(context, resource_type, payload)
        workflow_rpcapi = rpcapi.WorkflowAPI()
        workflow_rpcapi.apply_workflow(context, workflow)

        return workflow

