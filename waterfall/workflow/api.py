from waterfall.db import base

class API(base.Base):
    """API for interacting with the recover manager."""

    def __init__(self, db_driver=None, image_service=None):
        super(API, self).__init__(db_driver)

    def workflow_get_all(self, context):
        return self.db.workflow_get_all(context)
