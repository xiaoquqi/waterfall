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

from waterfall import exception
from waterfall.i18n import _
from waterfall import objects
from waterfall.objects import base
from waterfall.workflow import workflow_types

OPTIONAL_FIELDS = ['extra_specs', 'projects']
LOG = logging.getLogger(__name__)


@base.WaterfallObjectRegistry.register
class WorkflowType(base.WaterfallPersistentObject, base.WaterfallObject,
                 base.WaterfallObjectDictCompat, base.WaterfallComparableObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'id': fields.UUIDField(),
        'name': fields.StringField(nullable=True),
        'description': fields.StringField(nullable=True),
        'is_public': fields.BooleanField(default=True, nullable=True),
        'projects': fields.ListOfStringsField(nullable=True),
        'extra_specs': fields.DictOfStringsField(nullable=True),
    }

    @classmethod
    def _get_expected_attrs(cls, context):
        return 'extra_specs', 'projects'

    @staticmethod
    def _from_db_object(context, type, db_type, expected_attrs=None):
        if expected_attrs is None:
            expected_attrs = []
        for name, field in type.fields.items():
            if name in OPTIONAL_FIELDS:
                continue
            value = db_type[name]
            if isinstance(field, fields.IntegerField):
                value = value or 0
            type[name] = value

        # Get data from db_type object that was queried by joined query
        # from DB
        if 'extra_specs' in expected_attrs:
            type.extra_specs = {}
            specs = db_type.get('extra_specs')
            if specs and isinstance(specs, list):
                type.extra_specs = {item['key']: item['value']
                                    for item in specs}
            elif specs and isinstance(specs, dict):
                type.extra_specs = specs
        if 'projects' in expected_attrs:
            type.projects = db_type.get('projects', [])

        type._context = context
        type.obj_reset_changes()
        return type

    @base.remotable
    def create(self):
        if self.obj_attr_is_set('id'):
            raise exception.ObjectActionError(action='create',
                                              reason=_('already created'))
        db_workflow_type = workflow_types.create(self._context, self.name,
                                             self.extra_specs,
                                             self.is_public, self.projects,
                                             self.description)
        self._from_db_object(self._context, self, db_workflow_type)

    @base.remotable
    def save(self):
        updates = self.waterfall_obj_get_changes()
        if updates:
            workflow_types.update(self._context, self.id, self.name,
                                self.description)
            self.obj_reset_changes()

    @base.remotable
    def destroy(self):
        with self.obj_as_admin():
            workflow_types.destroy(self._context, self.id)


@base.WaterfallObjectRegistry.register
class WorkflowTypeList(base.ObjectListBase, base.WaterfallObject):
    # Version 1.0: Initial version
    # Version 1.1: Add pagination support to workflow type
    VERSION = '1.1'

    fields = {
        'objects': fields.ListOfObjectsField('WorkflowType'),
    }

    @base.remotable_classmethod
    def get_all(cls, context, inactive=0, filters=None, marker=None,
                limit=None, sort_keys=None, sort_dirs=None, offset=None):
        types = workflow_types.get_all_types(context, inactive, filters,
                                           marker=marker, limit=limit,
                                           sort_keys=sort_keys,
                                           sort_dirs=sort_dirs, offset=offset)
        expected_attrs = WorkflowType._get_expected_attrs(context)
        return base.obj_make_list(context, cls(context),
                                  objects.WorkflowType, types.values(),
                                  expected_attrs=expected_attrs)
