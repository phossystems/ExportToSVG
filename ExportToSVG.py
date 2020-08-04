#Author-ortus
#Description-Exports Sketch and Model Geometry as SVG

import adsk.core, adsk.fusion, adsk.cam, traceback
import inspect
import os
import math


# Global set of event handlers to keep them referenced for the duration of the command
_handlers = []

COMMAND_ID = "exportToSVG"
COMMAND_NAME = "Export To SVG"
COMMAND_TOOLTIP = "Expoer bodies & sketch geometry to SVG file"

TOOLBAR_PANELS = ["SolidModifyPanel"]

SVG_UNIT_FACTOR = 72/2.54

script_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
script_dir = os.path.dirname(script_path)

currentSettings = []


# Fires when the CommandDefinition gets executed.
# Responsible for adding commandInputs to the command &
# registering the other command handlers.
class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Get the command that was created.
            cmd = adsk.core.Command.cast(args.command)

            # Registers the CommandDestryHandler
            onExecute = CommandExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)
            
            # Registers the CommandInputChangedHandler          
            onInputChanged = CommandInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            _handlers.append(onInputChanged)

                
            # Get the CommandInputs collection associated with the command.
            inputs = cmd.commandInputs

            tabSelection = inputs.addTabCommandInput("tabSelection", "Selection", "")
            tabSettings = inputs.addTabCommandInput("tabSettings", "Settings", "")

            global SVG_UNIT_FACTOR

            VIDPI = tabSelection.children.addValueInput("VIDPI", "DPI", "", adsk.core.ValueInput.createByReal(SVG_UNIT_FACTOR * 2.54))

            settingText = "red, 255, 0, 0, 1\nblack, 0, 0, 0, 1"

            # Tries to open settings.csv file
            try:
                global script_dir
                with open(os.path.join(script_dir, "settings.csv"), 'r') as file:
                    settingText = file.read()                
            except:
                print(traceback.format_exc())

            # Parses settings string
            settings = [i.split(",") for i in settingText.split("\n")]

            global currentSettings
            currentSettings = settings

            # Adds selection inputs
            for i, s in enumerate(settings):
                si = tabSelection.children.addSelectionInput(s[0], s[0], "")
                si.addSelectionFilter("SolidBodies")
                si.addSelectionFilter("SketchCurves")
                si.setSelectionLimits(0, 0)

            TBSettings = tabSettings.children.addTextBoxCommandInput("TBSettings", "", settingText, 10, False)
            TBSettings.isFullWidth = True

            TBInfo = tabSettings.children.addTextBoxCommandInput("TBInfo", "", "Color settings\nFormat:\nname, r, g, b, stroke-width\n\nClose command to apply.",5, True)
            TBInfo.isFullWidth = True

            BVReset = tabSettings.children.addBoolValueInput("BVReset", "    Reset Settings    ", False)
            BVReset.isFullWidth = True
            

           
        except:
            print(traceback.format_exc())




#Fires when the User executes the Command
#Responsible for doing the changes to the document
class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            root = adsk.core.Application.get().activeProduct.rootComponent
            app = adsk.core.Application.get()
            ui  = app.userInterface

            global currentSettings
            global SVG_UNIT_FACTOR
            
            # Getting selections now, as creating sketches clears em
            selections = []
            for i in currentSettings:
                _ = []

                for j in range(args.command.commandInputs.itemById(i[0]).selectionCount):
                    _.append(args.command.commandInputs.itemById(i[0]).selection(j).entity)

                selections.append(_)

            paths = []
            for i in selections:
                _ = []
                for s in i:
                    if(s.objectType == "adsk::fusion::BRepBody"):
                        sketch = root.sketches.add(root.xYConstructionPlane)
                        sketch.project(s)
                        _.append(sketchToSVGPaths(sketch))
                        sketch.deleteMe()
                    else:
                        sketch = root.sketches.add(root.xYConstructionPlane)
                        sketch.project(s)
                        _.append([curveToPathSegment(j, 1/SVG_UNIT_FACTOR, False, True) for j in sketch.sketchCurves])
                        sketch.deleteMe()
                paths.append(_)

            svg = buildSVGFromPaths(paths, currentSettings)


            fileDialog = ui.createFileDialog()
            fileDialog.isMultiSelectEnabled = False
            fileDialog.title = "Specify result filename"
            fileDialog.filter = 'SVG files (*.svg)'
            fileDialog.filterIndex = 0
            dialogResult = fileDialog.showSave()
            if dialogResult == adsk.core.DialogResults.DialogOK:
                filename = fileDialog.filename
                output = open(filename, 'w')
                output.writelines(svg)
                output.close()
        except:
            print(traceback.format_exc())



# Fires when CommandInputs are changed
# Responsible for dynamically updating other Command Inputs
class CommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global script_dir
            # Writes settings to file
            if args.input.id == "TBSettings":
                settingText = args.input.parentCommand.commandInputs.itemById("TBSettings").text

                with open(os.path.join(script_dir, 'settings.csv'), 'w') as file:
                    file.write(settingText)

            # Updates unit factor
            elif args.input.id == "VIDPI":
                global SVG_UNIT_FACTOR

                SVG_UNIT_FACTOR = args.input.parentCommand.commandInputs.itemById("VIDPI").value / 2.54

            # Resets the settings and writes them to file
            elif args.input.id == "BVReset":
                args.input.parentCommand.commandInputs.itemById("TBSettings").text = "red, 255, 0, 0, 1\nblack, 0, 0, 0, 1"


                with open(os.path.join(script_dir, 'settings.csv'), 'w') as file:
                    file.write("red, 255, 0, 0, 1\nblack, 0, 0, 0, 1")
                
        except:
            print(traceback.format_exc())



def buildSVGFromPaths(pathss, settings, width=50, height=25):
    """Constructs a full svg fle from paths

    Args:
        paths: (String[][]) SVG path data
        width: (float) Width ouf bounding rectangle
        height: (float) Height of bounding rectangle

    Returns:
        [string]: full svg

    """
    global SVG_UNIT_FACTOR

    rtn = ""


    rtn += r"<svg version='1.1' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {0} {1}' width='{0}px' height='{1}px'>\n".format(width*SVG_UNIT_FACTOR, height*SVG_UNIT_FACTOR)

    #rtn += r"<rect width='{}' height='{}' stroke='black' stroke-width='2' fill-opacity='0'/> ".format(width*SVG_UNIT_FACTOR, height*SVG_UNIT_FACTOR)
    for i, paths in enumerate(pathss):
        for j, p in enumerate(paths):
            for path in p:
                rtn += r"    <path d='{}' id='{}_{}' stroke='rgb({},{},{})' stroke-width='{}' fill='none' fill-opacity='0.5'/> ".format(path, settings[i][0],j, settings[i][1], settings[i][2], settings[i][3], settings[i][4])

    rtn += r"</svg>"

    return rtn


def getTransformsFromSVG(svg):
    """Imports SVG result from svgnest and extracts transform data

    Args:
        svg: (String) SVG data

    Returns:
        [zip]: zip of index and transform data (x, y, r)
    """

    global SVG_UNIT_FACTOR

    # Wraps svg data into single root node
    svg = "<g>{}</g>".format(svg)

    dom = minidom.parseString(svg)

    ids = []
    transforms = []

    p = re.compile(r'[\(\s]-?\d*\.{0,1}\d+')

    for sheetNumber, s in enumerate(dom.firstChild.childNodes):
        for e in s.getElementsByTagName('path'):
            if not(int(e.getAttribute('id')) in ids):
                ids.append(int(e.getAttribute('id')))
                
                # Gets the transform atributes as string
                transformTag = (e.parentNode.getAttribute('transform'))

                # Converts string to list of floats via regex
                # Adds sheet number to the end
                transforms.append([float(i[1:]) for i in p.findall(transformTag)] + [sheetNumber] )
            
    # X, Y, rotation, sheet number
    transformsScaled = [ [t[0]/SVG_UNIT_FACTOR, t[1]/SVG_UNIT_FACTOR, t[2], t[3]] for t in transforms]

    return zip(ids, transformsScaled)
    

def sketchToSVGPaths(sketch):
    """Converts a Sketch into a SVG Path date

    Args:
        sketch: (Sketch) Sketch to convert

    Returns:
        [str]: Array of SVG paths
    """

    rtn = ""

    sortedProfiles = sorted(sketch.profiles, key=lambda x: len(x.profileLoops), reverse=True)

    """for p in sketch.profiles:
        for pl in p.profileLoops:

            if(pl.isOuter):
                rtn.append(loopToSVGPath(pl))
                break
    """


    for pl in sortedProfiles[0].profileLoops:
        # Outer should be clockwise
        # Inner should be counterclockwise
        if(pl.isOuter != isLoopClockwise(pl)):
            rtn += loopToSVGPath(pl, True)
        else:
            rtn += loopToSVGPath(pl, False)

    return [rtn]


def loopToSVGPath(loop, reverse = False):
    """Converts a ProfileLoop into a SVG Path date

    Args:
        loop: (ProfileLoop) Loop to convert
        reverse: (Bool) Invert direction

    Returns:
        str: SVG Path data
    """
    
    global SVG_UNIT_FACTOR

    rtn = ""

    profileCurves = [i for i in loop.profileCurves]

    if(reverse):
        profileCurves.reverse()

    flip = getWhatCurvesToFlip(profileCurves)

    if(reverse and len(flip) == 1):
        flip = [not(i) for i in flip]


    for c, f in zip(profileCurves, flip):
        rtn += curveToPathSegment(
            c,
            1/SVG_UNIT_FACTOR,
            f,
            not rtn
        )
    return rtn


def curveToPathSegment(curve, scale=1, invert=False, moveTo=False):
    """Converts a ProfileCurve into a SVG Path date segment

    Args:
        curve: (ProfileCurve) The curve object to be converted
        scale: (float) How many units are per SVG unit
        invert: (bool) Swaps curve's startPoint and endPoint
        moveTo: (bool) Moves to the startPoint before conversion

    Returns:
        str: Segment of SVG Path data.

    """

    rtn = ""


    if(curve.geometry.objectType == "adsk::core::Line3D"):
        if(not invert):
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    curve.geometry.startPoint.x / scale,
                    -curve.geometry.startPoint.y / scale
                )

            rtn += "L{0:.6f} {1:.6f} ".format(
                curve.geometry.endPoint.x / scale,
                -curve.geometry.endPoint.y / scale)

        else:
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    curve.geometry.endPoint.x / scale,
                    -curve.geometry.endPoint.y / scale
                )

            rtn += "L{0:.6f} {1:.6f} ".format(
                curve.geometry.startPoint.x / scale,
                -curve.geometry.startPoint.y / scale)
    
    elif(curve.geometry.objectType == "adsk::core::Arc3D"):
        if(not invert):
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    curve.geometry.startPoint.x / scale,
                    -curve.geometry.startPoint.y / scale
                )

            # rx ry rot large_af sweep_af x y
            rtn += "A {0:.6f} {0:.6f} 0 {1:.0f} {2:.0f} {3:.6f} {4:.6f}".format(
                curve.geometry.radius / scale,
                curve.geometry.endAngle-curve.geometry.startAngle > math.pi,
                0,
                curve.geometry.endPoint.x / scale,
                -curve.geometry.endPoint.y / scale
            )
        else:
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    curve.geometry.endPoint.x / scale,
                    -curve.geometry.endPoint.y / scale
                )

            # rx ry rot large_af sweep_af x y
            rtn += "A {0:.6f} {0:.6f} 0 {1:.0f} {2:.0f} {3:.6f} {4:.6f}".format(
                curve.geometry.radius / scale,
                curve.geometry.endAngle-curve.geometry.startAngle > math.pi,
                1,
                curve.geometry.startPoint.x / scale,
                -curve.geometry.startPoint.y / scale
            )
    
    elif(curve.geometry.objectType == "adsk::core::Circle3D"):
        sp = curve.geometry.center.copy()
        sp.translateBy(adsk.core.Vector3D.create(curve.geometry.radius, 0, 0))

        ep = curve.geometry.center.copy()
        ep.translateBy(adsk.core.Vector3D.create(0, curve.geometry.radius, 0))

        if(not invert):

            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    sp.x / scale,
                    -sp.y / scale
                )

            rtn += "A {0:.6f} {0:.6f} 0 {1:.0f} {2:.0f} {3:.6f} {4:.6f}".format(
                curve.geometry.radius / scale,
                1,
                1,
                ep.x / scale,
                -ep.y / scale
            )

            rtn += "A {0:.6f} {0:.6f} 0 {1:.0f} {2:.0f} {3:.6f} {4:.6f}".format(
                curve.geometry.radius / scale,
                0,
                1,
                sp.x / scale,
                -sp.y / scale
            )

        else:
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    sp.x / scale,
                    -sp.y / scale
                )

            rtn += "A {0:.6f} {0:.6f} 0 {1:.0f} {2:.0f} {3:.6f} {4:.6f}".format(
                curve.geometry.radius / scale,
                0,
                0,
                ep.x / scale,
                -ep.y / scale
            )

            rtn += "A {0:.6f} {0:.6f} 0 {1:.0f} {2:.0f} {3:.6f} {4:.6f}".format(
                curve.geometry.radius / scale,
                1,
                0,
                sp.x / scale,
                -sp.y / scale
            )

    
    elif(curve.geometry.objectType == "adsk::core::Ellipse3D"):
        sp = curve.geometry.center.copy()
        la = curve.geometry.majorAxis.copy()
        la.normalize()
        la.scaleBy(curve.geometry.majorRadius)
        sp.translateBy(la)

        ep = curve.geometry.center.copy()
        sa = adsk.core.Vector3D.crossProduct(curve.geometry.majorAxis, adsk.core.Vector3D.create(0,0,1))
        sa.normalize()
        sa.scaleBy(curve.geometry.minorRadius)
        ep.translateBy(sa)
        
        angle = -math.degrees(math.atan2(la.y, la.x))

        if(not invert):
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    sp.x / scale,
                    -sp.y / scale
                )

            # rx ry rot large_af sweep_af x y
            rtn += "A {0:.6f} {1:.6f} {2:.6f} {3:.0f} {4:.0f} {5:.6f} {6:.6f}".format(
                curve.geometry.majorRadius / scale,
                curve.geometry.minorRadius / scale,
                angle,
                1,
                0,
                ep.x / scale,
                -ep.y / scale
            )

            rtn += "A {0:.6f} {1:.6f} {2:.6f} {3:.0f} {4:.0f} {5:.6f} {6:.6f}".format(
                curve.geometry.majorRadius / scale,
                curve.geometry.minorRadius / scale,
                angle,
                0,
                0,
                sp.x / scale,
                -sp.y / scale
            )
        else:
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    sp.x / scale,
                    -sp.y / scale
                )

            # rx ry rot large_af sweep_af x y
            rtn += "A {0:.6f} {1:.6f} {2:.6f} {3:.0f} {4:.0f} {5:.6f} {6:.6f}".format(
                curve.geometry.majorRadius / scale,
                curve.geometry.minorRadius / scale,
                angle,
                0,
                1,
                ep.x / scale,
                -ep.y / scale
            )

            rtn += "A {0:.6f} {1:.6f} {2:.6f} {3:.0f} {4:.0f} {5:.6f} {6:.6f}".format(
                curve.geometry.majorRadius / scale,
                curve.geometry.minorRadius / scale,
                angle,
                1,
                1,
                sp.x / scale,
                -sp.y / scale
            )


    elif(curve.geometry.objectType == "adsk::core::EllipticalArc3D"):
        angle = -math.degrees(math.atan2(curve.geometry.majorAxis.y, curve.geometry.majorAxis.x))

        _, sp, ep = curve.geometry.evaluator.getEndPoints()

        if(not invert):
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    sp.x / scale,
                    -sp.y / scale
                )

            # rx ry rot large_af sweep_af x y
            rtn += "A {0:.6f} {1:.6f} {2:.6f} {3:.0f} {4:.0f} {5:.6f} {6:.6f}".format(
                curve.geometry.majorRadius / scale,
                curve.geometry.minorRadius / scale,
                angle,
                curve.geometry.endAngle-curve.geometry.startAngle > math.pi,
                0,
                ep.x / scale,
                -ep.y / scale
            )
        else:
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    ep.x / scale,
                    -ep.y / scale
                )

            # rx ry rot large_af sweep_af x y
            rtn += "A {0:.6f} {1:.6f} {2:.6f} {3:.0f} {4:.0f} {5:.6f} {6:.6f}".format(
                curve.geometry.majorRadius / scale,
                curve.geometry.minorRadius / scale,
                angle,
                curve.geometry.endAngle-curve.geometry.startAngle > math.pi,
                1,
                sp.x / scale,
                -sp.y / scale
            )

    elif(curve.geometry.objectType == "adsk::core::NurbsCurve3D"):
        # Aproximates nurbs with straight line segments

        ev = curve.geometry.evaluator
        _, sp, ep = ev.getParameterExtents()

        # List of segments, initially subdivided into two segments
        s = [sp, lerp(sp, ep, 0.5), ep]
        
        # Maxiumum angle two neighboring segments can have 
        maxAngle = math.radians(10)

        # Minimum length of segment
        minLength = 0.05

        i = 0
        while(i < len(s)-1):
            _, t = ev.getTangents(s)
            _, p = ev.getPointsAtParameters(s)

            # If the angle to the next segment is small enough, move one
            if( t[i].angleTo( t[i+1]) < maxAngle or p[i].distanceTo(p[i+1]) < minLength):
                i += 1
            # Otherwise subdivide the next segment into two
            else:
                s.insert(i+1, lerp( s[i], s[i+1], 0.5))

        if(not invert):
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    p[0].x / scale,
                    -p[0].y / scale
                )
            for i in p[1:]:
                rtn += "L{0:.6f} {1:.6f} ".format(
                    i.x / scale,
                    -i.y / scale
                )
        else:
            if(moveTo):
                rtn += "M{0:.6f} {1:.6f} ".format(
                    p[-1].x / scale,
                    -p[-1].y / scale
                )
            for i in reversed(p[:-1]):
                rtn += "L{0:.6f} {1:.6f} ".format(
                    i.x / scale,
                    -i.y / scale
                )

    else:
        print("Warning: Unsupported curve type, could not be converted: {}".format(curve.geometryType))
    return rtn


def isLoopClockwise(loop):
    """Determins if a ProfileLoop is clockwise

    Args:
        loop: (ProfileLoop) The loop to check

    Returns:
        bool: True if clockwise.
    """

    # If if it has only one segment it is clockwise by definition
    if(len(loop.profileCurves) == 1):
        return False;

    # https://stackoverflow.com/questions/1165647/how-to-determine-if-a-list-of-polygon-points-are-in-clockwise-order
    res = 0

    sp = [getStartPoint(i.geometry) for i in loop.profileCurves]
    ep = [getEndPoint(i.geometry) for i in loop.profileCurves]
    

    # range(len()) one of the deally sins of python
    for s, e in zip(sp, ep):
        res += (e.x - s.x) * (e.y + s.y)

    return res > 0


def getWhatCurvesToFlip(curves):
    """Determins which ProfileCurves need their startPoint and endPoint flipped to line up end to end

    Args:
        curves: (ProfileCurves) The List of points to check agains

    Returns:
        bool[]: List of bools of equal length to curves.
    """

    if(len(curves)==1):
        return [False]
    else:
        rtn = []

        for i in range(len(curves)):
            if(i==0):
                rtn.append(
                    isPointInList(
                        getStartPoint(curves[i].geometry),
                        [getStartPoint(curves[1].geometry), getEndPoint(curves[1].geometry)]
                    )
                )
            else:
                rtn.append(
                    not isPointInList(
                        getStartPoint(curves[i].geometry),
                        [getStartPoint(curves[i-1].geometry), getEndPoint(curves[i-1].geometry)]
                        )
                )
        return rtn


def getStartPoint(curve):
    """Gets the start point of any Curve3D object

    Args:
        curves: (Curve3D) The curve

    Returns:
        Point3D: Start point of the curve
    """

    if(curve.objectType in ["adsk::core::Line3D", "adsk::core::Arc3D"]):
        return curve.startPoint

    elif(curve.objectType == "adsk::core::Circle3D"):
        sp = curve.center.copy()
        sp.translateBy(adsk.core.Vector3D.create(curve.radius, 0, 0))
        return sp

    elif(curve.objectType == "adsk::core::Ellipse3D"):
        sp = curve.center.copy()
        la = curve.majorAxis.copy()
        la.normalize()
        la.scaleBy(curve.majorRadius)
        sp.translateBy(la)
        return sp

    elif(curve.objectType in ["adsk::core::EllipticalArc3D", "adsk::core::NurbsCurve3D"]):
        _, sp, ep = curve.evaluator.getEndPoints()
        return sp


def getEndPoint(curve):
    """Gets the end point of any Curve3D object

    Args:
        curves: (Curve3D) The curve

    Returns:
        Point3D: End point of the curve
    """

    if(curve.objectType in ["adsk::core::Line3D", "adsk::core::Arc3D"]):
        return curve.endPoint

    elif(curve.objectType == "adsk::core::Circle3D"):
        ep = curve.center.copy()
        ep.translateBy(adsk.core.Vector3D.create(curve.radius, 0, 0))
        return ep

    elif(curve.objectType == "adsk::core::Ellipse3D"):
        ep = curve.center.copy()
        la = curve.majorAxis.copy()
        la.normalize()
        la.scaleBy(curve.majorRadius)
        ep.translateBy(la)
        return ep

    elif(curve.objectType in ["adsk::core::EllipticalArc3D", "adsk::core::NurbsCurve3D"]):
        _, sp, ep = curve.evaluator.getEndPoints()
        return ep


def isPointInList(point, pointList, tol=1e-4):
    """Determins if a Point3D is almost-equal to a Point3D in a list

    Args:
        point: (Point3D) The Point to be checked
        pointList: (Point3D[]) The List of points to check agains
        tol: (float) Tollerance for almost-equality

    Returns:
        bool: True if almost equal to any Point in list
    """

    for i in pointList:
        if(isPointEqual(point, i, tol)):
            return True
    return False


def isPointEqual(point1, point2, tol=1e-4):
    """Determins if a Point3D is almost-equal to a Point3D in a list

    Args:
        point1: (Point3D) The Point to be checked
        point2: (Point3D) The Points to check agains
        tol: (float) Tollerance for almost-equality

    Returns:
        bool: True if almost equal to point
    """
    return math.isclose(point1.x, point2.x, rel_tol=tol) and math.isclose(point1.y, point2.y, rel_tol=tol) and math.isclose(point1.z, point2.z, rel_tol=tol)


def lerp(a, b, i):
    """Linearly interpolates from a to b

    Args:
        a: (float) The value to interpolate from
        b: (float) The value to interpolate to
        i: (float) Interpolation factor

    Returns:
        float: Interpolation result
    """
    return a + (b-a)*i


def run(context):
    try:
        
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        commandDefinitions = ui.commandDefinitions
        #check the command exists or not
        cmdDef = commandDefinitions.itemById(COMMAND_ID)
        if not cmdDef:
            cmdDef = commandDefinitions.addButtonDefinition(COMMAND_ID, COMMAND_NAME,
                                                            COMMAND_TOOLTIP, 'resources')
        #Adds the commandDefinition to the toolbar
        for panel in TOOLBAR_PANELS:
            ui.allToolbarPanels.itemById(panel).controls.addCommand(cmdDef)
        
        onCommandCreated = CommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        _handlers.append(onCommandCreated)
    except:
        print(traceback.format_exc())


def stop(context):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        #Removes the commandDefinition from the toolbar
        for panel in TOOLBAR_PANELS:
            p = ui.allToolbarPanels.itemById(panel).controls.itemById(COMMAND_ID)
            if p:
                p.deleteMe()
        
        #Deletes the commandDefinition
        ui.commandDefinitions.itemById(COMMAND_ID).deleteMe()
            
            
            
    except:
        print(traceback.format_exc())