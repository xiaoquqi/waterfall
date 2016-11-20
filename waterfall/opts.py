
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools

from waterfall.api import common as waterfall_api_common
from waterfall.api.middleware import auth as waterfall_api_middleware_auth
from waterfall.api.middleware import sizelimit as waterfall_api_middleware_sizelimit
from waterfall.api.views import versions as waterfall_api_views_versions
from waterfall.backup import api as waterfall_backup_api
from waterfall.backup import chunkeddriver as waterfall_backup_chunkeddriver
from waterfall.backup import driver as waterfall_backup_driver
from waterfall.backup.drivers import ceph as waterfall_backup_drivers_ceph
from waterfall.backup.drivers import glusterfs as waterfall_backup_drivers_glusterfs
from waterfall.backup.drivers import google as waterfall_backup_drivers_google
from waterfall.backup.drivers import nfs as waterfall_backup_drivers_nfs
from waterfall.backup.drivers import posix as waterfall_backup_drivers_posix
from waterfall.backup.drivers import swift as waterfall_backup_drivers_swift
from waterfall.backup.drivers import tsm as waterfall_backup_drivers_tsm
from waterfall.backup import manager as waterfall_backup_manager
from waterfall.cmd import all as waterfall_cmd_all
from waterfall.cmd import workflow as waterfall_cmd_workflow
from waterfall.common import config as waterfall_common_config
import waterfall.compute
from waterfall.compute import nova as waterfall_compute_nova
from waterfall import context as waterfall_context
from waterfall import coordination as waterfall_coordination
from waterfall.db import api as waterfall_db_api
from waterfall.db import base as waterfall_db_base
from waterfall import exception as waterfall_exception
from waterfall.image import glance as waterfall_image_glance
from waterfall.image import image_utils as waterfall_image_imageutils
import waterfall.keymgr
from waterfall.keymgr import conf_key_mgr as waterfall_keymgr_confkeymgr
from waterfall.keymgr import key_mgr as waterfall_keymgr_keymgr
from waterfall import quota as waterfall_quota
from waterfall.scheduler import driver as waterfall_scheduler_driver
from waterfall.scheduler import host_manager as waterfall_scheduler_hostmanager
from waterfall.scheduler import manager as waterfall_scheduler_manager
from waterfall.scheduler import scheduler_options as \
    waterfall_scheduler_scheduleroptions
from waterfall.scheduler.weights import capacity as \
    waterfall_scheduler_weights_capacity
from waterfall.scheduler.weights import workflow_number as \
    waterfall_scheduler_weights_workflownumber
from waterfall import service as waterfall_service
from waterfall import ssh_utils as waterfall_sshutils
from waterfall.transfer import api as waterfall_transfer_api
from waterfall.workflow import api as waterfall_workflow_api
from waterfall.workflow import driver as waterfall_workflow_driver
from waterfall.workflow.drivers import block_device as \
    waterfall_workflow_drivers_blockdevice
from waterfall.workflow.drivers import blockbridge as \
    waterfall_workflow_drivers_blockbridge
from waterfall.workflow.drivers.cloudbyte import options as \
    waterfall_workflow_drivers_cloudbyte_options
from waterfall.workflow.drivers import coho as waterfall_workflow_drivers_coho
from waterfall.workflow.drivers import datera as waterfall_workflow_drivers_datera
from waterfall.workflow.drivers.dell import dell_storagecenter_common as \
    waterfall_workflow_drivers_dell_dellstoragecentercommon
from waterfall.workflow.drivers.disco import disco as \
    waterfall_workflow_drivers_disco_disco
from waterfall.workflow.drivers.dothill import dothill_common as \
    waterfall_workflow_drivers_dothill_dothillcommon
from waterfall.workflow.drivers import drbdmanagedrv as \
    waterfall_workflow_drivers_drbdmanagedrv
from waterfall.workflow.drivers.emc import emc_vmax_common as \
    waterfall_workflow_drivers_emc_emcvmaxcommon
from waterfall.workflow.drivers.emc import emc_vnx_cli as \
    waterfall_workflow_drivers_emc_emcvnxcli
from waterfall.workflow.drivers.emc import scaleio as \
    waterfall_workflow_drivers_emc_scaleio
from waterfall.workflow.drivers.emc import xtremio as \
    waterfall_workflow_drivers_emc_xtremio
from waterfall.workflow.drivers import eqlx as waterfall_workflow_drivers_eqlx
from waterfall.workflow.drivers.fujitsu import eternus_dx_common as \
    waterfall_workflow_drivers_fujitsu_eternusdxcommon
from waterfall.workflow.drivers import glusterfs as waterfall_workflow_drivers_glusterfs
from waterfall.workflow.drivers import hgst as waterfall_workflow_drivers_hgst
from waterfall.workflow.drivers.hitachi import hbsd_common as \
    waterfall_workflow_drivers_hitachi_hbsdcommon
from waterfall.workflow.drivers.hitachi import hbsd_fc as \
    waterfall_workflow_drivers_hitachi_hbsdfc
from waterfall.workflow.drivers.hitachi import hbsd_horcm as \
    waterfall_workflow_drivers_hitachi_hbsdhorcm
from waterfall.workflow.drivers.hitachi import hbsd_iscsi as \
    waterfall_workflow_drivers_hitachi_hbsdiscsi
from waterfall.workflow.drivers.hitachi import hnas_iscsi as \
    waterfall_workflow_drivers_hitachi_hnasiscsi
from waterfall.workflow.drivers.hitachi import hnas_nfs as \
    waterfall_workflow_drivers_hitachi_hnasnfs
from waterfall.workflow.drivers.hpe import hpe_3par_common as \
    waterfall_workflow_drivers_hpe_hpe3parcommon
from waterfall.workflow.drivers.hpe import hpe_lefthand_iscsi as \
    waterfall_workflow_drivers_hpe_hpelefthandiscsi
from waterfall.workflow.drivers.hpe import hpe_xp_opts as \
    waterfall_workflow_drivers_hpe_hpexpopts
from waterfall.workflow.drivers.huawei import huawei_driver as \
    waterfall_workflow_drivers_huawei_huaweidriver
from waterfall.workflow.drivers.ibm import flashsystem_common as \
    waterfall_workflow_drivers_ibm_flashsystemcommon
from waterfall.workflow.drivers.ibm import flashsystem_fc as \
    waterfall_workflow_drivers_ibm_flashsystemfc
from waterfall.workflow.drivers.ibm import flashsystem_iscsi as \
    waterfall_workflow_drivers_ibm_flashsystemiscsi
from waterfall.workflow.drivers.ibm import gpfs as waterfall_workflow_drivers_ibm_gpfs
from waterfall.workflow.drivers.ibm.storwize_svc import storwize_svc_common as \
    waterfall_workflow_drivers_ibm_storwize_svc_storwizesvccommon
from waterfall.workflow.drivers.ibm.storwize_svc import storwize_svc_fc as \
    waterfall_workflow_drivers_ibm_storwize_svc_storwizesvcfc
from waterfall.workflow.drivers.ibm.storwize_svc import storwize_svc_iscsi as \
    waterfall_workflow_drivers_ibm_storwize_svc_storwizesvciscsi
from waterfall.workflow.drivers.ibm import xiv_ds8k as \
    waterfall_workflow_drivers_ibm_xivds8k
from waterfall.workflow.drivers.infortrend.eonstor_ds_cli import common_cli as \
    waterfall_workflow_drivers_infortrend_eonstor_ds_cli_commoncli
from waterfall.workflow.drivers.lenovo import lenovo_common as \
    waterfall_workflow_drivers_lenovo_lenovocommon
from waterfall.workflow.drivers import lvm as waterfall_workflow_drivers_lvm
from waterfall.workflow.drivers.netapp import options as \
    waterfall_workflow_drivers_netapp_options
from waterfall.workflow.drivers.nexenta import options as \
    waterfall_workflow_drivers_nexenta_options
from waterfall.workflow.drivers import nfs as waterfall_workflow_drivers_nfs
from waterfall.workflow.drivers import nimble as waterfall_workflow_drivers_nimble
from waterfall.workflow.drivers.prophetstor import options as \
    waterfall_workflow_drivers_prophetstor_options
from waterfall.workflow.drivers import pure as waterfall_workflow_drivers_pure
from waterfall.workflow.drivers import quobyte as waterfall_workflow_drivers_quobyte
from waterfall.workflow.drivers import rbd as waterfall_workflow_drivers_rbd
from waterfall.workflow.drivers import remotefs as waterfall_workflow_drivers_remotefs
from waterfall.workflow.drivers.san.hp import hpmsa_common as \
    waterfall_workflow_drivers_san_hp_hpmsacommon
from waterfall.workflow.drivers.san import san as waterfall_workflow_drivers_san_san
from waterfall.workflow.drivers import scality as waterfall_workflow_drivers_scality
from waterfall.workflow.drivers import sheepdog as waterfall_workflow_drivers_sheepdog
from waterfall.workflow.drivers import smbfs as waterfall_workflow_drivers_smbfs
from waterfall.workflow.drivers import solidfire as waterfall_workflow_drivers_solidfire
from waterfall.workflow.drivers import tegile as waterfall_workflow_drivers_tegile
from waterfall.workflow.drivers import tintri as waterfall_workflow_drivers_tintri
from waterfall.workflow.drivers.violin import v7000_common as \
    waterfall_workflow_drivers_violin_v7000common
from waterfall.workflow.drivers.vmware import vmdk as \
    waterfall_workflow_drivers_vmware_vmdk
from waterfall.workflow.drivers import vzstorage as waterfall_workflow_drivers_vzstorage
from waterfall.workflow.drivers.windows import windows as \
    waterfall_workflow_drivers_windows_windows
from waterfall.workflow.drivers import xio as waterfall_workflow_drivers_xio
from waterfall.workflow.drivers.zfssa import zfssaiscsi as \
    waterfall_workflow_drivers_zfssa_zfssaiscsi
from waterfall.workflow.drivers.zfssa import zfssanfs as \
    waterfall_workflow_drivers_zfssa_zfssanfs
from waterfall.workflow import manager as waterfall_workflow_manager
from waterfall.wsgi import eventlet_server as waterfall_wsgi_eventletserver
from waterfall.zonemanager.drivers.brocade import brcd_fabric_opts as \
    waterfall_zonemanager_drivers_brocade_brcdfabricopts
from waterfall.zonemanager.drivers.brocade import brcd_fc_zone_driver as \
    waterfall_zonemanager_drivers_brocade_brcdfczonedriver
from waterfall.zonemanager.drivers.cisco import cisco_fabric_opts as \
    waterfall_zonemanager_drivers_cisco_ciscofabricopts
from waterfall.zonemanager.drivers.cisco import cisco_fc_zone_driver as \
    waterfall_zonemanager_drivers_cisco_ciscofczonedriver
from waterfall.zonemanager import fc_zone_manager as \
    waterfall_zonemanager_fczonemanager


def list_opts():
    return [
        ('FC-ZONE-MANAGER',
            itertools.chain(
                waterfall_zonemanager_fczonemanager.zone_manager_opts,
                waterfall_zonemanager_drivers_brocade_brcdfczonedriver.brcd_opts,
                waterfall_zonemanager_drivers_cisco_ciscofczonedriver.cisco_opts,
            )),
        ('KEYMGR',
            itertools.chain(
                waterfall_keymgr_keymgr.encryption_opts,
                waterfall.keymgr.keymgr_opts,
                waterfall_keymgr_confkeymgr.key_mgr_opts,
            )),
        ('DEFAULT',
            itertools.chain(
                waterfall_backup_driver.service_opts,
                waterfall_api_common.api_common_opts,
                waterfall_backup_drivers_ceph.service_opts,
                waterfall_workflow_drivers_smbfs.workflow_opts,
                waterfall_backup_chunkeddriver.chunkedbackup_service_opts,
                waterfall_workflow_drivers_san_san.san_opts,
                waterfall_workflow_drivers_hitachi_hnasnfs.NFS_OPTS,
                waterfall_wsgi_eventletserver.socket_opts,
                waterfall_sshutils.ssh_opts,
                waterfall_workflow_drivers_netapp_options.netapp_proxy_opts,
                waterfall_workflow_drivers_netapp_options.netapp_connection_opts,
                waterfall_workflow_drivers_netapp_options.netapp_transport_opts,
                waterfall_workflow_drivers_netapp_options.netapp_basicauth_opts,
                waterfall_workflow_drivers_netapp_options.netapp_cluster_opts,
                waterfall_workflow_drivers_netapp_options.netapp_7mode_opts,
                waterfall_workflow_drivers_netapp_options.netapp_provisioning_opts,
                waterfall_workflow_drivers_netapp_options.netapp_img_cache_opts,
                waterfall_workflow_drivers_netapp_options.netapp_eseries_opts,
                waterfall_workflow_drivers_netapp_options.netapp_nfs_extra_opts,
                waterfall_workflow_drivers_netapp_options.netapp_san_opts,
                waterfall_workflow_drivers_ibm_storwize_svc_storwizesvciscsi.
                storwize_svc_iscsi_opts,
                waterfall_backup_drivers_glusterfs.glusterfsbackup_service_opts,
                waterfall_backup_drivers_tsm.tsm_opts,
                waterfall_workflow_drivers_fujitsu_eternusdxcommon.
                FJ_ETERNUS_DX_OPT_opts,
                waterfall_workflow_drivers_ibm_gpfs.gpfs_opts,
                waterfall_workflow_drivers_violin_v7000common.violin_opts,
                waterfall_workflow_drivers_nexenta_options.NEXENTA_CONNECTION_OPTS,
                waterfall_workflow_drivers_nexenta_options.NEXENTA_ISCSI_OPTS,
                waterfall_workflow_drivers_nexenta_options.NEXENTA_DATASET_OPTS,
                waterfall_workflow_drivers_nexenta_options.NEXENTA_NFS_OPTS,
                waterfall_workflow_drivers_nexenta_options.NEXENTA_RRMGR_OPTS,
                waterfall_workflow_drivers_nexenta_options.NEXENTA_EDGE_OPTS,
                waterfall_exception.exc_log_opts,
                waterfall_common_config.global_opts,
                waterfall_scheduler_weights_capacity.capacity_weight_opts,
                waterfall_workflow_drivers_sheepdog.sheepdog_opts,
                [waterfall_api_middleware_sizelimit.max_request_body_size_opt],
                waterfall_workflow_drivers_solidfire.sf_opts,
                waterfall_backup_drivers_swift.swiftbackup_service_opts,
                waterfall_workflow_drivers_cloudbyte_options.
                cloudbyte_add_qosgroup_opts,
                waterfall_workflow_drivers_cloudbyte_options.
                cloudbyte_create_workflow_opts,
                waterfall_workflow_drivers_cloudbyte_options.
                cloudbyte_connection_opts,
                waterfall_workflow_drivers_cloudbyte_options.
                cloudbyte_update_workflow_opts,
                waterfall_service.service_opts,
                waterfall.compute.compute_opts,
                waterfall_workflow_drivers_drbdmanagedrv.drbd_opts,
                waterfall_workflow_drivers_dothill_dothillcommon.common_opts,
                waterfall_workflow_drivers_dothill_dothillcommon.iscsi_opts,
                waterfall_workflow_drivers_glusterfs.workflow_opts,
                waterfall_workflow_drivers_pure.PURE_OPTS,
                waterfall_context.context_opts,
                waterfall_scheduler_driver.scheduler_driver_opts,
                waterfall_workflow_drivers_scality.workflow_opts,
                waterfall_workflow_drivers_emc_emcvnxcli.loc_opts,
                waterfall_workflow_drivers_vmware_vmdk.vmdk_opts,
                waterfall_workflow_drivers_lenovo_lenovocommon.common_opts,
                waterfall_workflow_drivers_lenovo_lenovocommon.iscsi_opts,
                waterfall_backup_drivers_posix.posixbackup_service_opts,
                waterfall_workflow_drivers_emc_scaleio.scaleio_opts,
                [waterfall_db_base.db_driver_opt],
                waterfall_workflow_drivers_eqlx.eqlx_opts,
                waterfall_transfer_api.workflow_transfer_opts,
                waterfall_db_api.db_opts,
                waterfall_scheduler_weights_workflownumber.
                workflow_number_weight_opts,
                waterfall_workflow_drivers_coho.coho_opts,
                waterfall_workflow_drivers_xio.XIO_OPTS,
                waterfall_workflow_drivers_ibm_storwize_svc_storwizesvcfc.
                storwize_svc_fc_opts,
                waterfall_workflow_drivers_zfssa_zfssaiscsi.ZFSSA_OPTS,
                waterfall_workflow_driver.workflow_opts,
                waterfall_workflow_driver.iser_opts,
                waterfall_api_views_versions.versions_opts,
                waterfall_workflow_drivers_nimble.nimble_opts,
                waterfall_workflow_drivers_windows_windows.windows_opts,
                waterfall_workflow_drivers_san_hp_hpmsacommon.common_opts,
                waterfall_workflow_drivers_san_hp_hpmsacommon.iscsi_opts,
                waterfall_image_glance.glance_opts,
                waterfall_image_glance.glance_core_properties_opts,
                waterfall_workflow_drivers_hpe_hpelefthandiscsi.hpelefthand_opts,
                waterfall_workflow_drivers_lvm.workflow_opts,
                waterfall_workflow_drivers_emc_emcvmaxcommon.emc_opts,
                waterfall_workflow_drivers_remotefs.nas_opts,
                waterfall_workflow_drivers_remotefs.workflow_opts,
                waterfall_workflow_drivers_emc_xtremio.XTREMIO_OPTS,
                waterfall_backup_drivers_google.gcsbackup_service_opts,
                [waterfall_api_middleware_auth.use_forwarded_for_opt],
                waterfall_workflow_drivers_hitachi_hbsdcommon.workflow_opts,
                waterfall_workflow_drivers_infortrend_eonstor_ds_cli_commoncli.
                infortrend_esds_opts,
                waterfall_workflow_drivers_infortrend_eonstor_ds_cli_commoncli.
                infortrend_esds_extra_opts,
                waterfall_workflow_drivers_hitachi_hnasiscsi.iSCSI_OPTS,
                waterfall_workflow_drivers_rbd.rbd_opts,
                waterfall_workflow_drivers_tintri.tintri_opts,
                waterfall_backup_api.backup_api_opts,
                waterfall_workflow_drivers_hitachi_hbsdhorcm.workflow_opts,
                waterfall_backup_manager.backup_manager_opts,
                waterfall_workflow_drivers_ibm_storwize_svc_storwizesvccommon.
                storwize_svc_opts,
                waterfall_workflow_drivers_hitachi_hbsdfc.workflow_opts,
                waterfall_quota.quota_opts,
                waterfall_workflow_drivers_huawei_huaweidriver.huawei_opts,
                waterfall_workflow_drivers_dell_dellstoragecentercommon.
                common_opts,
                waterfall_scheduler_hostmanager.host_manager_opts,
                [waterfall_scheduler_manager.scheduler_driver_opt],
                waterfall_backup_drivers_nfs.nfsbackup_service_opts,
                waterfall_workflow_drivers_blockbridge.blockbridge_opts,
                [waterfall_scheduler_scheduleroptions.
                    scheduler_json_config_location_opt],
                waterfall_workflow_drivers_zfssa_zfssanfs.ZFSSA_OPTS,
                waterfall_workflow_drivers_disco_disco.disco_opts,
                waterfall_workflow_drivers_hgst.hgst_opts,
                waterfall_image_imageutils.image_helper_opts,
                waterfall_compute_nova.nova_opts,
                waterfall_workflow_drivers_ibm_flashsystemfc.flashsystem_fc_opts,
                waterfall_workflow_drivers_prophetstor_options.DPL_OPTS,
                waterfall_workflow_drivers_hpe_hpexpopts.FC_WORKFLOW_OPTS,
                waterfall_workflow_drivers_hpe_hpexpopts.COMMON_WORKFLOW_OPTS,
                waterfall_workflow_drivers_hpe_hpexpopts.HORCM_WORKFLOW_OPTS,
                waterfall_workflow_drivers_hitachi_hbsdiscsi.workflow_opts,
                waterfall_workflow_manager.workflow_manager_opts,
                waterfall_workflow_drivers_ibm_flashsystemiscsi.
                flashsystem_iscsi_opts,
                waterfall_workflow_drivers_tegile.tegile_opts,
                waterfall_workflow_drivers_ibm_flashsystemcommon.flashsystem_opts,
                [waterfall_workflow_api.allow_force_upload_opt],
                [waterfall_workflow_api.workflow_host_opt],
                [waterfall_workflow_api.workflow_same_az_opt],
                [waterfall_workflow_api.az_cache_time_opt],
                waterfall_workflow_drivers_ibm_xivds8k.xiv_ds8k_opts,
                waterfall_workflow_drivers_hpe_hpe3parcommon.hpe3par_opts,
                waterfall_workflow_drivers_datera.d_opts,
                waterfall_workflow_drivers_blockdevice.workflow_opts,
                waterfall_workflow_drivers_quobyte.workflow_opts,
                waterfall_workflow_drivers_vzstorage.vzstorage_opts,
                waterfall_workflow_drivers_nfs.nfs_opts,
            )),
        ('CISCO_FABRIC_EXAMPLE',
            itertools.chain(
                waterfall_zonemanager_drivers_cisco_ciscofabricopts.
                cisco_zone_opts,
            )),
        ('BRCD_FABRIC_EXAMPLE',
            itertools.chain(
                waterfall_zonemanager_drivers_brocade_brcdfabricopts.
                brcd_zone_opts,
            )),
        ('COORDINATION',
            itertools.chain(
                waterfall_coordination.coordination_opts,
            )),
        ('BACKEND',
            itertools.chain(
                [waterfall_cmd_workflow.host_opt],
                [waterfall_cmd_all.workflow_cmd.host_opt],
            )),
    ]
