# AngleBased-EdgeTracer 1.0.0
# Copyright (C) 2020 Pouya Nakhaie Ahooie

# ######################## BEGIN GPL LICENSE BLOCK ########################
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ######################### END GPL LICENSE BLOCK #########################

bl_info = {
    "name": "AngleBased-EdgeTracer",
    "author": "Pouya Nakhaie Ahooie",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Select > Edge Tracer",
    "support": "COMMUNITY",
    "warning": "",
    "wiki_url": "",
    "description": "Select edge loops in non-quad messy geometries. An edge loop selection tool for edge cases.",
    "category": "Mesh"
}

import bpy
import bmesh
import numpy as np
from math import radians
from bpy.props import *

# ########### Global Variables ############
# Constants
EPSILON = 0.00001
DEFAULT_ANGLE_RANGE = 160.0
# Minimum angle difference allowed between edges
# 160.0 was suitable for most spheres and therefore selected as the default
angleRange = DEFAULT_ANGLE_RANGE
# An array to hold initially selected edges
selectedEdges = []
# Keymaps for shortcuts
addonKeymaps = []
# #########################################


def getAngleDegrees(a, b, c):
    """
        Gets 3 points in space
        Second parameter is the mid point
        Returns the angle between them
    """
    ba = a - b
    bc = c - b
    cosineAngle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    if cosineAngle < -1.0:
        cosineAngle = -1.0
    if cosineAngle > 1.0:
        cosineAngle = 1.0
    angle = np.arccos(cosineAngle)
    return np.degrees(angle)


def isInPath(e1, e2):
    """
        Gets 2 connected edges, compares the angle between them.
        Returns a dictionary containing the angle and a boolean determining if they qualify for selection.
    """
    points = []
    edgePoints = []

    # Adding all the verts to the points array
    points.append(np.array([e1.verts[0].co.x, e1.verts[0].co.y, e1.verts[0].co.z]))
    points.append(np.array([e1.verts[1].co.x, e1.verts[1].co.y, e1.verts[1].co.z]))
    points.append(np.array([e2.verts[0].co.x, e2.verts[0].co.y, e2.verts[0].co.z]))
    points.append(np.array([e2.verts[1].co.x, e2.verts[1].co.y, e2.verts[1].co.z]))

    # Find edge points and the mid point
    for point in points:
        if sum(np.array_equal(point, tempPoint) for tempPoint in points) > 1:
            midPoint = point
        else:
            edgePoints.append(point)

    # Get the angle between 3 points
    angle = getAngleDegrees(edgePoints[0], midPoint, edgePoints[1])

    # Construct the return value
    isInPath = (angle >= angleRange - EPSILON)
    result = {"isInPath": isInPath, "angle": angle}

    return result


# This is a recursive function. It manipulates the edges directly
# Gets an edge as a parameter, checks the linked edges and finds the best next edge/edges to complete the path
# Marks new edges in path as selected and calls itself with a new edge parameter to look for the next best fit
def selectNeighbours(selectedEdge):
    """
        This function finds the best edges to complete the path.
        Gets an edge as a parameter.
        Selects the desired edges.
    """
    # Checks all the connected edges to each vert
    for vert in selectedEdge.verts:

        skip = False
        possibleEdge = {"edge": None, "angle": 0.0}

        # Check if we reached a new edge which is not the original edge but is selected
        # Which most likely means we have selected an edge loop therefore we will skip this vert
        for edge in vert.link_edges:
            if (edge != selectedEdge) and edge.select:
                skip = True
                break
        if skip:
            continue

        # Check every linked edge except the selectedEdge to see if they can fit in our desired path
        # If they do, compare them to our current candidate which is stored in possibleEdge
        # Keep the edge with greater angle (Closer to 180)
        # If we have any possible edge / edges, select them and pass them to this function to find the next one in path
        for edge in vert.link_edges:
            if (edge != selectedEdge):
                currentEdge = isInPath(edge, selectedEdge)
                if currentEdge["isInPath"] and currentEdge["angle"] >= possibleEdge["angle"]:
                    possibleEdge["edge"] = edge
                    possibleEdge["angle"] = currentEdge["angle"]
        if possibleEdge["edge"]:
            possibleEdge["edge"].select = True
            selectNeighbours(possibleEdge["edge"])


def main(context, operator):

    selectedMesh = bpy.context.object.data
    selectedBMesh = bmesh.from_edit_mesh(selectedMesh)

    activeEdge = None

    global selectedEdges

    # Store and deselect all initially selected edges in global selectedEdges[] except active edge
    # Store the active edge in activeEdge variable
    for edge in selectedBMesh.edges:
        if (edge.select == True) and not(selectedBMesh.select_history.active == edge):
            selectedEdges.append(edge)
            edge.select = False
        elif (edge.select == True) and (selectedBMesh.select_history.active == edge):
            activeEdge = edge

    # Make sure we have an active edge
    if (activeEdge == None):
        print("Please select an edge!")
        operator.report({"ERROR"}, "Please select an edge.")
        return 0

    # Send The active edge to a recursive function to trace other edges around it
    selectNeighbours(activeEdge)

    # Restore Previously Selected Edges
    for edge in selectedEdges:
        for edgePrime in selectedBMesh.edges:
            if (edge == edgePrime):
                edgePrime.select = True
    # #################################

    bmesh.update_edit_mesh(selectedMesh)
    selectedMesh.update()

    return 0


def menuFunction(self, context):
    """Adding functionality to menu"""
    self.layout.separator()
    self.layout.operator("object.edgetraceroperator")


# Operator class for Edge Tracer
class EdgeTracerOperator(bpy.types.Operator):
    """"Edge Tracer Operator Class"""

    bl_idname = "object.edgetraceroperator"
    bl_label = "Edge Tracer"
    bl_options = {"REGISTER", "UNDO"}

    # Change the mode to manual if angle is not default
    def onAngleUpdate(self, context):
        if (self.angleInDegrees != DEFAULT_ANGLE_RANGE):
            self.mode = "Manual"

    # Create properties
    mode = EnumProperty(
        name="Mode",
        description="Angle value mode.",
        items=[
            ("Manual", "Manual Value", "Manual Value"),
            ("DefaultValue", "Default Value", "Default Value")
        ]
    )

    angleInDegrees = FloatProperty(
        name="Allowed Angle",
        description="Maximum angle between edges in degrees.",
        default=angleRange,
        min=0.0,
        max=180.0,
        update=onAngleUpdate
    )

    def execute(self, context):
        global selectedEdges

        # Make sure we are in edit mode
        print("MODE: ", bpy.context.mode)
        if (bpy.context.mode != "EDIT_MESH"):
            print("Please select an edge in edit mode")
            self.report({"ERROR"}, "Please select an edge in edit mode.")
            return {"CANCELLED"}

        # Make sure we are in edge select mode only
        if ((not bpy.context.tool_settings.mesh_select_mode[1])
                or (bpy.context.tool_settings.mesh_select_mode[0])
                or (bpy.context.tool_settings.mesh_select_mode[2])):
            print("Please select an edge in edit mode", bpy.context.tool_settings.mesh_select_mode[1])
            self.report({"ERROR"}, "Please select an edge in edge select mode.")
            return {"CANCELLED"}

        global DEFAULT_ANGLE_RANGE
        global angleRange

        if self.mode == "DefaultValue":
            self.angleInDegrees = DEFAULT_ANGLE_RANGE

        angleRange = self.angleInDegrees

        main(context, self)

        return {"FINISHED"}


def register():
    bpy.utils.register_class(EdgeTracerOperator)

    # Setting up shortcuts
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name="Mesh", space_type="EMPTY")
    kmi = km.keymap_items.new(EdgeTracerOperator.bl_idname, "T", "PRESS", shift=True)
    addonKeymaps.append(km)
    
    # Setting up menu
    bpy.types.VIEW3D_MT_select_edit_mesh.append(menuFunction)


def unregister():
    bpy.utils.unregister_class(EdgeTracerOperator)

    # Cleaning up shortcuts
    wm = bpy.context.window_manager
    for km in addonKeymaps:
        wm.keyconfigs.addon.keymaps.remove(km)
    del addonKeymaps[:]
    
    # Cleaning up menu
    bpy.types.VIEW3D_MT_select_edit_mesh.remove(menuFunction)


if __name__ == "__main__":
    register()
