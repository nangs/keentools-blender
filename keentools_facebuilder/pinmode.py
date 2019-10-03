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

import logging

import bpy

from . utils import manipulate, coords, cameras
from . config import Config, get_main_settings, ErrorType, BuilderType
from . fbdebug import FBDebug
from . fbloader import FBLoader
from . utils.other import FBStopTimer

import keentools_facebuilder.blender_independent_packages.pykeentools_loader as pkt


class OBJECT_OT_FBPinMode(bpy.types.Operator):
    """ On Screen Face Builder Draw Operator """
    bl_idname = Config.fb_pinmode_operator_idname
    bl_label = "FaceBuilder Pinmode"
    bl_description = "Operator for in-Viewport drawing"
    bl_options = {'REGISTER', 'UNDO'}  # {'REGISTER', 'UNDO'}

    headnum: bpy.props.IntProperty(default=0)
    camnum: bpy.props.IntProperty(default=0)

    def init_wireframer_colors(self, opacity):
        settings = get_main_settings()
        head = settings.heads[settings.current_headnum]
        headobj = head.headobj

        FBLoader.viewport().wireframer().init_geom_data(headobj)
        FBLoader.viewport().wireframer().init_edge_indices(headobj)

        FBLoader.viewport().wireframer().init_color_data(
            (*settings.wireframe_color, opacity * settings.wireframe_opacity))
        # Coloring special parts
        if settings.show_specials:
            special_indices = FBLoader.viewport().get_special_indices(
                FBLoader.get_builder_type())
            special_color = (*settings.wireframe_special_color,
                             opacity * settings.wireframe_opacity)
            FBLoader.viewport().wireframer().init_special_areas(
                headobj.data, special_indices, special_color)
        FBLoader.viewport().wireframer().create_batches()

    def on_left_mouse_press(self, context, mouse_x, mouse_y):
        settings = get_main_settings()
        # === Debug only ===
        FBDebug.add_event_to_queue(
            'DRAW_OPERATOR_PRESS_LEFTMOUSE',
            (mouse_x, mouse_y), coords.get_raw_camera_2d_data(context))
        # === Debug only ===

        if not coords.is_in_area(context, mouse_x, mouse_y):
            # Pass to interface interaction
            return {'PASS_THROUGH'}

        if coords.is_safe_region(context, mouse_x, mouse_y):
            # === Debug only ===
            FBDebug.add_event_to_queue(
                'CALL_MOVE_PIN_OPERATOR', mouse_x, mouse_y,
                coords.get_raw_camera_2d_data(context))
            # === Debug only ===

            # Registered Operator call
            op = getattr(
                bpy.ops.object, Config.fb_movepin_operator_callname)
            op('INVOKE_DEFAULT',
               headnum=settings.current_headnum,
               camnum=settings.current_camnum,
               pinx=mouse_x, piny=mouse_y)
            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def on_right_mouse_press(self, context, mouse_x, mouse_y):
        logger = logging.getLogger(__name__)
        # === Debug only ===
        FBDebug.add_event_to_queue(
            'IN_PINMODE_PRESS_RIGHTMOUSE', mouse_x, mouse_y,
            coords.get_raw_camera_2d_data(context))
        # === Debug only ===

        settings = get_main_settings()
        headnum = settings.current_headnum
        camnum = settings.current_camnum
        kid = cameras.keyframe_by_camnum(headnum, camnum)

        x, y = coords.get_image_space_coord(mouse_x, mouse_y, context)
        nearest, dist2 = coords.nearest_point(
            x, y, FBLoader.viewport().spins)
        if nearest >= 0 and \
                dist2 < FBLoader.viewport().tolerance_dist2():
            # Nearest pin found
            fb = FBLoader.get_builder()
            head = settings.heads[headnum]
            headobj = head.headobj
            # Delete pin
            fb.remove_pin(kid, nearest)
            del FBLoader.viewport().spins[nearest]
            # Setup Rigidity only for FaceBuilder
            if FBLoader.get_builder_type() == BuilderType.FaceBuilder:
                fb.set_auto_rigidity(settings.check_auto_rigidity)
                fb.set_rigidity(settings.rigidity)
            # Activate Focal Estimation
            fb.set_focal_length_estimation(head.auto_focal_estimation)

            try:
                # Solver
                fb.solve_for_current_pins(kid)
            except pkt.module().UnlicensedException:
                settings.force_out_pinmode = True
                settings.license_error = True
                FBLoader.out_pinmode(headnum, camnum)
                logger.error("PIN MODE LICENSE EXCEPTION")
                return {'FINISHED'}

            camobj = head.cameras[camnum].camobj

            kid = cameras.keyframe_by_camnum(headnum, camnum)
            # Camera update
            FBLoader.place_cameraobj(kid, camobj, headobj)

            # Head Mesh update
            coords.update_head_mesh(fb, headobj)
            # Update all cameras position
            FBLoader.update_cameras(headnum)
            # Save result
            FBLoader.fb_save(headnum, camnum)
            FBLoader.viewport().update_surface_points(fb, headobj, kid)
            # Shader update
            FBLoader.viewport().wireframer().init_geom_data(headobj)
            FBLoader.viewport().wireframer().init_edge_indices(headobj)
            FBLoader.viewport().wireframer().create_batches()

            # Indicators update
            FBLoader.update_pins_count(headnum, camnum)
            # Undo push
            head.need_update = True
            manipulate.force_undo_push('Pin Remove')
            head.need_update = False

        FBLoader.viewport().create_batch_2d(context)
        # out to prevent click events
        return {"RUNNING_MODAL"}

    def on_undo_detected(self, mouse_x, mouse_y):
        settings = get_main_settings()
        headnum = settings.current_headnum
        camnum = settings.current_camnum
        head = settings.heads[headnum]

        head.need_update = False
        # Reload pins
        FBLoader.load_all(headnum, camnum)
        kid = cameras.keyframe_by_camnum(headnum, camnum)
        FBLoader.viewport().update_surface_points(
            FBLoader.get_builder(), head.headobj, kid)

        FBLoader.viewport().wireframer().init_geom_data(head.headobj)
        FBLoader.viewport().wireframer().init_edge_indices(head.headobj)
        FBLoader.viewport().wireframer().create_batches()

        # === Debug only ===
        FBDebug.add_event_to_queue('UNDO_CALLED', mouse_x, mouse_y)
        FBDebug.add_event_to_queue('FORCE_SNAPSHOT', mouse_x, mouse_y)
        FBDebug.make_snapshot()
        # === Debug only ===

    def invoke(self, context, event):
        logger = logging.getLogger(__name__)
        args = (self, context)
        settings = get_main_settings()
        head = settings.heads[self.headnum]
        headobj = head.headobj

        logger.debug("PINMODE ENTER: CH{} CC{}".format(
            settings.current_headnum, settings.current_camnum))

        if settings.pinmode:
            # We had to finish last operation
            if settings.current_headnum >= 0 and settings.current_camnum >= 0:
                FBLoader.out_pinmode(
                    settings.current_headnum,
                    settings.current_camnum
                )
                logger.debug("PINMODE FORCE FINISH: H{} C{}".format(
                    settings.current_headnum, settings.current_camnum))
        else:
            FBLoader.builder().sync_version(head.mod_ver)
            head.mod_ver = FBLoader.get_builder_version()

        # Settings structure is broken
        if not settings.check_heads_and_cams():
            # Fix and Out
            heads_deleted, cams_deleted = settings.fix_heads()
            if heads_deleted > 0 or cams_deleted > 0:
                logger.warning("HEADS AND CAMERAS FIXED")
            if heads_deleted == 0:
                warn = getattr(bpy.ops.wm, Config.fb_warning_operator_callname)
                warn('INVOKE_DEFAULT', msg=ErrorType.SceneDamaged)
            return {'FINISHED'}

        # Current headnum & camnum in global settings object
        settings.current_headnum = self.headnum
        settings.current_camnum = self.camnum

        logger.debug("PINMODE START H{} C{}".format(
            settings.current_headnum, settings.current_camnum))
        # === Debug only ===
        FBDebug.add_event_to_queue(
            'PIN_MODE_START', self.headnum, self.camnum,
            coords.get_raw_camera_2d_data(context))
        # === Debug only ===

        FBLoader.load_all(self.headnum, self.camnum, False)

        # Hide geometry
        headobj.hide_set(True)
        cameras.hide_other_cameras(self.headnum, self.camnum)
        # Start our shader
        self.init_wireframer_colors(settings.overall_opacity)
        FBLoader.viewport().create_batch_2d(context)
        FBLoader.viewport().register_handlers(args, context)
        context.window_manager.modal_handler_add(self)

        kid = cameras.keyframe_by_camnum(self.headnum, self.camnum)
        # Load 3D pins
        FBLoader.viewport().update_surface_points(
            FBLoader.get_builder(), headobj, kid)

        # Can start much more times when not out from pinmode
        if not settings.pinmode:
            FBStopTimer.start()
            logger.debug("STOPPER START")
        settings.pinmode = True
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        logger = logging.getLogger(__name__)
        settings = get_main_settings()

        headnum = settings.current_headnum
        camnum = settings.current_camnum
        kid = cameras.keyframe_by_camnum(headnum, camnum)

        mouse_x = event.mouse_region_x
        mouse_y = event.mouse_region_y

        # Quit if Screen changed
        if context.area is None:  # Different operation Space
            FBLoader.out_pinmode(headnum, camnum)
            return {'FINISHED'}

        if headnum < 0:  # Head lost
            FBLoader.out_pinmode(headnum, camnum)
            logger.error("HEAD LOST")
            return {'FINISHED'}

        head = settings.heads[headnum]
        if not head.headobj.hide_get():
            head.headobj.hide_set(True)

        # Pixel size in relative coords
        FBLoader.viewport().update_pixel_size(context)

        # Screen Update request
        if context.area:
            context.area.tag_redraw()

        # Quit if PinMode out
        if settings.force_out_pinmode:  # Move Pin problem by ex.
            FBLoader.out_pinmode(headnum, camnum)
            settings.force_out_pinmode = False
            if settings.license_error:
                warn = getattr(bpy.ops.wm, Config.fb_warning_operator_callname)
                warn('INVOKE_DEFAULT', msg=ErrorType.NoLicense)
                settings.license_error = False
            logger.debug("FORCE OUT PINMODE")
            return {'FINISHED'}

        # Quit when camera rotated by user
        if context.space_data.region_3d.view_perspective != 'CAMERA':
            FBLoader.out_pinmode(headnum, camnum)
            return {'FINISHED'}

        # Quit by ESC pressed
        if event.type == 'ESC':
            FBLoader.out_pinmode(headnum, camnum)
            # --- PROFILING ---
            if FBLoader.viewport().profiling:
                pr = FBLoader.viewport().pr
                pr.dump_stats('facebuilder.pstat')
            # --- PROFILING ---
            return {'FINISHED'}

        if event.value == "PRESS" and event.type == 'TAB':
            if settings.overall_opacity > 0.5:
                settings.overall_opacity = 0.0
            else:
                settings.overall_opacity = 1.0
            logger.debug("OVERALL_OPACITY BY TAB {}".format(
                settings.overall_opacity))
            self.init_wireframer_colors(settings.overall_opacity)
            return {'RUNNING_MODAL'}

        if event.value == "PRESS" and event.type == "LEFTMOUSE":
            # Left mouse button pressed. Set Pin
            return self.on_left_mouse_press(context, mouse_x, mouse_y)

        if event.value == "PRESS" and event.type == "RIGHTMOUSE":
            # Right mouse button pressed - delete Pin
            return self.on_right_mouse_press(context, mouse_x, mouse_y)

        if head.need_update:
            # Undo was called so Model redraw is needed
            logger.debug("UNDO CALL DETECTED")
            self.on_undo_detected(mouse_x, mouse_y)

        # Catch if wireframer is off
        if not (FBLoader.viewport().wireframer().is_working()):
            FBLoader.out_pinmode(headnum, camnum)
            logger.debug("WIREFRAME IS OFF")
            return {'FINISHED'}

        FBLoader.viewport().create_batch_2d(context)
        FBLoader.viewport().update_residuals(
            FBLoader.get_builder(), context, head.headobj, kid)

        if FBLoader.viewport().current_pin:
            return {"RUNNING_MODAL"}
        else:
            return {"PASS_THROUGH"}