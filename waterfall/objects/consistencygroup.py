#    Copyright 2015 Yahoo Inc.
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

from waterfall import db
from waterfall import exception
from waterfall.i18n import _
from waterfall import objects
from waterfall.objects import base
from waterfall.objects import fields as c_fields
from oslo_versionedobjects import fields

OPTIONAL_FIELDS = ['cgsnapshots', 'workflows']


@base.WaterfallObjectRegistry.register
class ConsistencyGroup(base.WaterfallPersistentObject, base.WaterfallObject,
                       base.WaterfallObjectDictCompat):
    # Version 1.0: Initial version
    # Version 1.1: Added cgsnapshots and workflows relationships
    # Version 1.2: Changed 'status' field to use ConsistencyGroupStatusField
    VERSION = '1.2'

    fields = {
        'id': fields.UUIDField(),
        'user_id': fields.UUIDField(),
        'project_id': fields.UUIDField(),
        'host': fields.StringField(nullable=True),
        'availability_zone': fields.StringField(nullable=True),
        'name': fields.StringField(nullable=True),
        'description': fields.StringField(nullable=True),
        'workflow_type_id': fields.UUIDField(nullable=True),
        'status': c_fields.ConsistencyGroupStatusField(nullable=True),
        'cgsnapshot_id': fields.UUIDField(nullable=True),
        'source_cgid': fields.UUIDField(nullable=True),
        'cgsnapshots': fields.ObjectField('CGSnapshotList', nullable=True),
        'workflows': fields.ObjectField('WorkflowList', nullable=True),
    }

    @staticmethod
    def _from_db_object(context, consistencygroup, db_consistencygroup,
                        expected_attrs=None):
        if expected_attrs is None:
            expected_attrs = []
        for name, field in consistencygroup.fields.items():
            if name in OPTIONAL_FIELDS:
                continue
            value = db_consistencygroup.get(name)
            setattr(consistencygroup, name, value)

        if 'cgsnapshots' in expected_attrs:
            cgsnapshots = base.obj_make_list(
                context, objects.CGSnapshotsList(context),
                objects.CGSnapshot,
                db_consistencygroup['cgsnapshots'])
            consistencygroup.cgsnapshots = cgsnapshots

        if 'workflows' in expected_attrs:
            workflows = base.obj_make_list(
                context, objects.WorkflowList(context),
                objects.Workflow,
                db_consistencygroup['workflows'])
            consistencygroup.cgsnapshots = workflows

        consistencygroup._context = context
        consistencygroup.obj_reset_changes()
        return consistencygroup

    @base.remotable
    def create(self):
        if self.obj_attr_is_set('id'):
            raise exception.ObjectActionError(action='create',
                                              reason=_('already_created'))
        updates = self.waterfall_obj_get_changes()

        if 'cgsnapshots' in updates:
            raise exception.ObjectActionError(action='create',
                                              reason=_('cgsnapshots assigned'))

        if 'workflows' in updates:
            raise exception.ObjectActionError(action='create',
                                              reason=_('workflows assigned'))

        db_consistencygroups = db.consistencygroup_create(self._context,
                                                          updates)
        self._from_db_object(self._context, self, db_consistencygroups)

    def obj_load_attr(self, attrname):
        if attrname not in OPTIONAL_FIELDS:
            raise exception.ObjectActionError(
                action='obj_load_attr',
                reason=_('attribute %s not lazy-loadable') % attrname)
        if not self._context:
            raise exception.OrphanedObjectError(method='obj_load_attr',
                                                objtype=self.obj_name())

        if attrname == 'cgsnapshots':
            self.cgsnapshots = objects.CGSnapshotList.get_all_by_group(
                self._context, self.id)

        if attrname == 'workflows':
            self.workflows = objects.WorkflowList.get_all_by_group(self._context,
                                                               self.id)

        self.obj_reset_changes(fields=[attrname])

    @base.remotable
    def save(self):
        updates = self.waterfall_obj_get_changes()
        if updates:
            if 'cgsnapshots' in updates:
                raise exception.ObjectActionError(
                    action='save', reason=_('cgsnapshots changed'))
            if 'workflows' in updates:
                raise exception.ObjectActionError(
                    action='save', reason=_('workflows changed'))

            db.consistencygroup_update(self._context, self.id, updates)
            self.obj_reset_changes()

    @base.remotable
    def destroy(self):
        with self.obj_as_admin():
            db.consistencygroup_destroy(self._context, self.id)


@base.WaterfallObjectRegistry.register
class ConsistencyGroupList(base.ObjectListBase, base.WaterfallObject):
    # Version 1.0: Initial version
    # Version 1.1: Add pagination support to consistency group
    VERSION = '1.1'

    fields = {
        'objects': fields.ListOfObjectsField('ConsistencyGroup')
    }

    @base.remotable_classmethod
    def get_all(cls, context, filters=None, marker=None, limit=None,
                offset=None, sort_keys=None, sort_dirs=None):
        consistencygroups = db.consistencygroup_get_all(
            context, filters=filters, marker=marker, limit=limit,
            offset=offset, sort_keys=sort_keys, sort_dirs=sort_dirs)
        return base.obj_make_list(context, cls(context),
                                  objects.ConsistencyGroup,
                                  consistencygroups)

    @base.remotable_classmethod
    def get_all_by_project(cls, context, project_id, filters=None, marker=None,
                           limit=None, offset=None, sort_keys=None,
                           sort_dirs=None):
        consistencygroups = db.consistencygroup_get_all_by_project(
            context, project_id, filters=filters, marker=marker, limit=limit,
            offset=offset, sort_keys=sort_keys, sort_dirs=sort_dirs)
        return base.obj_make_list(context, cls(context),
                                  objects.ConsistencyGroup,
                                  consistencygroups)
