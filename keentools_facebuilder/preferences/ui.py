# ##### BEGIN GPL LICENSE BLOCK #####
# KeenTools for blender is a blender addon for using KeenTools in Blender.
# Copyright (C) 2019  KeenTools

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ##### END GPL LICENSE BLOCK #####

from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
import re
import keentools_facebuilder.preferences.operators as operators
import keentools_facebuilder.config
import keentools_facebuilder.blender_independent_packages.pykeentools_loader as pkt


class FBAddonPreferences(AddonPreferences):
    bl_idname = keentools_facebuilder.config.Config.addon_name

    license_id: StringProperty(
        name="license ID", default=""
    )

    license_server: StringProperty(
        name="license server host/IP", default="localhost"
    )

    license_server_port: IntProperty(
        name="license server port", default=7096, min=0, max=65535
    )

    license_server_lock: BoolProperty(
        name="Variables from ENV", default=False
    )

    license_server_auto: BoolProperty(
        name="Auto settings from Environment", default=True
    )

    hardware_id: StringProperty(
        name="hardware ID", default=""
    )

    lic_type: EnumProperty(
        name="Type",
        items=(
            ('ONLINE', "Online", "Online license management", 0),
            ('OFFLINE', "Offline", "Offline license management", 1),
            ('FLOATING', "Floating", "Floating license management", 2)),
        default='ONLINE')

    lic_status: StringProperty(
        name="license status", default=""
    )

    lic_online_status: StringProperty(
        name="online license status", default=""
    )

    lic_offline_status: StringProperty(
        name="offline license status", default=""
    )

    lic_floating_status: StringProperty(
        name="floating license status", default=""
    )

    lic_path: StringProperty(
            name="License file path",
            description="absolute path to license file",
            default="",
            subtype="FILE_PATH"
    )

    @classmethod
    def output_labels(cls, layout, txt):
        if txt is not None:
            arr = cls.split_by_br(txt)
            for a in arr:
                if len(a) > 0:
                    layout.label(text=a)

    @staticmethod
    def split_by_br(s):  # return list
        res = re.split("<br />|<br>|<br/>|\r\n|\n", s)
        return res

    def _draw_license_info(self, layout):
        from .licmanager import FBLicManager

        box = layout.box()
        box.label(text='License info:')

        FBLicManager.update_lic_status()

        self.output_labels(box, self.lic_status)

        row = box.row()
        row.prop(self, "lic_type", expand=True)

        if self.lic_type == 'ONLINE':
            self.output_labels(layout, self.lic_online_status)

            box = layout.box()
            row = box.row()
            row.prop(self, "license_id")
            row.operator(operators.OBJECT_OT_InstallLicenseOnline.bl_idname)

        elif self.lic_type == 'OFFLINE':
            # Get hardware ID
            if len(self.hardware_id) == 0:
                FBLicManager.update_hardware_id()

            # Start output
            self.output_labels(layout, self.lic_offline_status)

            layout.label(text="Generate license file at our site "
                              "and install it")
            row = layout.row()
            row.label(text="Visit our site: ")
            row.operator(operators.OBJECT_OT_OpenManualInstallPage.bl_idname)

            box = layout.box()
            row = box.row()
            row.prop(self, "hardware_id")
            row.operator(operators.OBJECT_OT_CopyHardwareId.bl_idname)

            row = box.row()
            row.prop(self, "lic_path")
            row.operator(operators.OBJECT_OT_InstallLicenseOffline.bl_idname)

        elif self.lic_type == 'FLOATING':
            FBLicManager.update_floating_params()
            self.output_labels(layout, self.lic_floating_status)

            box = layout.box()
            row = box.row()
            row.label(text="license server host/IP")
            if self.license_server_lock and self.license_server_auto:
                row.label(text=self.license_server)
            else:
                row.prop(self, "license_server", text="")

            row = box.row()
            row.label(text="license server port")
            if self.license_server_lock and self.license_server_auto:
                row.label(text=str(self.license_server_port))
            else:
                row.prop(self, "license_server_port", text="")

            if self.license_server_lock:
                box.prop(self, "license_server_auto",
                         text="Auto server/port settings")

            row.operator(operators.OBJECT_OT_FloatingConnect.bl_idname)

    def _draw_pkt_prefs(self, layout):
        box = layout.box()
        if pkt.is_installed():
            uninstall_row = box.row()
            uninstall_row.label(text="pykeentools is installed")
            uninstall_row.operator(operators.OBJECT_OT_UninstallPkt.bl_idname)
        else:
            install_row = box.row()
            install_row.label(text="pykeentools is not installed")
            install_row.operator(operators.OBJECT_OT_InstallPkt.bl_idname)

        if pkt.loaded():
            box.label(text="pykeentools loaded. Build info: {} {}".format(
                pkt.module().__version__,
                pkt.module().build_time))
            box.label(text="restart Blender to unload pykeentools")
        else:
            load_row = box.row()
            load_row.label(text="pykeentools is not loaded")
            load_row.operator(operators.OBJECT_OT_LoadPkt.bl_idname)

    def draw(self, context):
        layout = self.layout

        self._draw_pkt_prefs(layout)

        if pkt.loaded():
            self._draw_license_info(layout)
