# Copyright (c) 2013 OpenStack Foundation
# All Rights Reserved.
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

from waterfall.api import extensions
from waterfall.api.openstack import wsgi
import waterfall.api.views.availability_zones
from waterfall.api import xmlutil
import waterfall.exception
import waterfall.workflow.api


def make_availability_zone(elem):
    elem.set('name', 'zoneName')
    zoneStateElem = xmlutil.SubTemplateElement(elem, 'zoneState',
                                               selector='zoneState')
    zoneStateElem.set('available')


class ListTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('availabilityZones')
        elem = xmlutil.SubTemplateElement(root, 'availabilityZone',
                                          selector='availabilityZoneInfo')
        make_availability_zone(elem)
        alias = Availability_zones.alias
        namespace = Availability_zones.namespace
        return xmlutil.MasterTemplate(root, 1, nsmap={alias: namespace})


class Controller(wsgi.Controller):

    _view_builder_class = waterfall.api.views.availability_zones.ViewBuilder

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)
        self.workflow_api = waterfall.workflow.api.API()

    @wsgi.serializers(xml=ListTemplate)
    def index(self, req):
        """Describe all known availability zones."""
        azs = self.workflow_api.list_availability_zones()
        return self._view_builder.list(req, azs)


class Availability_zones(extensions.ExtensionDescriptor):
    """Describe Availability Zones."""

    name = 'AvailabilityZones'
    alias = 'os-availability-zone'
    namespace = ('http://docs.openstack.org/workflow/ext/'
                 'os-availability-zone/api/v1')
    updated = '2013-06-27T00:00:00+00:00'

    def get_resources(self):
        controller = Controller()
        res = extensions.ResourceExtension(Availability_zones.alias,
                                           controller)
        return [res]
