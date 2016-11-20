#    Copyright 2015 SimpliVity Corp.
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

from oslo_log import log as logging
from oslo_versionedobjects import fields

from waterfall import db
from waterfall import objects
from waterfall.objects import base

LOG = logging.getLogger(__name__)


@base.WaterfallObjectRegistry.register
class WorkflowAttachment(base.WaterfallPersistentObject, base.WaterfallObject,
                       base.WaterfallObjectDictCompat,
                       base.WaterfallComparableObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'id': fields.UUIDField(),
        'workflow_id': fields.UUIDField(),
        'instance_uuid': fields.UUIDField(nullable=True),
        'attached_host': fields.StringField(nullable=True),
        'mountpoint': fields.StringField(nullable=True),

        'attach_time': fields.DateTimeField(nullable=True),
        'detach_time': fields.DateTimeField(nullable=True),

        'attach_status': fields.StringField(nullable=True),
        'attach_mode': fields.StringField(nullable=True),
    }

    @staticmethod
    def _from_db_object(context, attachment, db_attachment):
        for name, field in attachment.fields.items():
            value = db_attachment.get(name)
            if isinstance(field, fields.IntegerField):
                value = value or 0
            attachment[name] = value

        attachment._context = context
        attachment.obj_reset_changes()
        return attachment

    @base.remotable
    def save(self):
        updates = self.waterfall_obj_get_changes()
        if updates:
            db.workflow_attachment_update(self._context, self.id, updates)
            self.obj_reset_changes()


@base.WaterfallObjectRegistry.register
class WorkflowAttachmentList(base.ObjectListBase, base.WaterfallObject):
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('WorkflowAttachment'),
    }

    @base.remotable_classmethod
    def get_all_by_workflow_id(cls, context, workflow_id):
        attachments = db.workflow_attachment_get_used_by_workflow_id(context,
                                                                 workflow_id)
        return base.obj_make_list(context, cls(context),
                                  objects.WorkflowAttachment, attachments)

    @base.remotable_classmethod
    def get_all_by_host(cls, context, workflow_id, host):
        attachments = db.workflow_attachment_get_by_host(context, workflow_id,
                                                       host)
        return base.obj_make_list(context, cls(context),
                                  objects.WorkflowAttachment, attachments)

    @base.remotable_classmethod
    def get_all_by_instance_uuid(cls, context, workflow_id, instance_uuid):
        attachments = db.workflow_attachment_get_by_instance_uuid(
            context, workflow_id, instance_uuid)
        return base.obj_make_list(context, cls(context),
                                  objects.WorkflowAttachment, attachments)
