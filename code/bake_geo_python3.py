'''
GW Alembic saver for Film production v1.3.6
Author: Marco Rossi 
Last modified 2024 OCT 01

Change Log
1.3.6 - Fixed for Pyton 3 (will rpobably not work on 2)
1.3.5 - Added "face sets"  and "color sets" to alembic output (17 May 2022)
1.3.4 - Check if plug-in AbcExport is loaded, and load it if needed.
1.3.3 - LOg file goes inside SET directory, not on top
1.3.2 - Minor UI changes for better interaction (2022 FEB 23)
1.3.1 - Added check if scene is saved. (2022 FEB 04)

NOTES
- Exports SETs from assets to alembic.
- SETs MUST be a selection of TRANSFORM nodes to export sucessfully. SHAPE nodes will fail.
- Maya DOEST NOT handle correctly Instances in Alembic, maya command WILL fail (same name for "leaf" nodes).
- Alembic also NEEDS all nodes have different names, DOES NOT like nodes with same name. Maya command will fail.
- The files will be written with the NAMESPACE as name, to allow multiple characters from same source file.
- NAMESPACE cannot be nested. Takes LAST namespace. So the set "train:wagon1:geo_cache_set" will be written as "train.abc"
- Defaults output to exports/abd of current project.

'''

import sys
import datetime
import getpass
import time
import os
import re
import shutil
import socket
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from PySide2 import QtCore
from PySide2.QtWidgets import QAbstractItemView
from PySide2 import QtWidgets
from maya import OpenMayaUI as omui
from shiboken2 import wrapInstance

software_version = 'Glassworks Sets Alembic Exporter 1.3.4'

def setFilterScript(name):
    """ Filter non outliner sets
    """
    # We first test for plug-in object sets.
    try:
        apiNodeType = cmds.nodeType(name, api=True)
    except RuntimeError:
        return False

    if apiNodeType == "kPluginObjectSet":
        return True

    # We do not need to test is the object is a set, since that test
    # has already been done by the outliner
    try:
        nodeType = cmds.nodeType(name)
    except RuntimeError:
        return False

    # We do not want any rendering sets
    if nodeType == "shadingEngine":
        return False

    # if the object is not a set, return false
    if not (nodeType == "objectSet" or
            nodeType == "textureBakeSet" or
            nodeType == "vertexBakeSet" or
            nodeType == "character"):
        return False

    # We also do not want any sets with restrictions
    restrictionAttrs = ["verticesOnlySet", "edgesOnlySet", "facetsOnlySet", "editPointsOnlySet", "renderableOnlySet"]
    if any(cmds.getAttr("{0}.{1}".format(name, attr)) for attr in restrictionAttrs):
        return False

    # Do not show layers
    if cmds.getAttr("{0}.isLayer".format(name)):
        return False

    # Do not show bookmarks
    annotation = cmds.getAttr("{0}.annotation".format(name))
    if annotation == "bookmarkAnimCurves":
        return False

    # Whew ... we can finally show it
    return True

def getOutlinerSets():
    return [name for name in cmds.ls(sets=True) if setFilterScript(name)]
################################################################################
def objectIsVisible(object):
    # if visibility is false. return false
    if cmds.attributeQuery("visibility", node = object, exists =True) == False:
        return False
    #if cmds.attributeQuery(node = object, exists ="intermediateObject") == False:
    #    return False
    visible = cmds.getAttr(object+".visibility")
    if visible == False:
        return False
    parent = cmds.listRelatives(object, parent=True, fullPath = True)
    if parent == None:
        return visible
    return objectIsVisible(parent[0])

################################################################################
def getFoldersFiles_abc(path):
    folderList = []
    fileList = []
    try:
        allData = os.listdir(path)
        folderList = [f for f in allData if os.path.isdir(os.path.join(path, f))]
        for file in allData:
            if file.endswith(".abc"):
                fileList.append(file)
        fileList.sort()
        fileList.reverse()
    except:
        pass
    return folderList, fileList

def getVersion_abc(saveLocationDir):
    if not os.path.exists(saveLocationDir):
        nextVersion = "1"
    else:
        allFiles = os.listdir(saveLocationDir)
        nextVersion = "1" # pre-setting this in case we don't get a match below
        if allFiles:
            versions = []
            for file in allFiles:
                if file.endswith(".abc"):
                    version_double = re.search(r'_v(\d\d)', file)
                    version_triple = re.search(r'_v(\d\d\d)', file)
                    if version_double:
                        versionNumber = str(int(version_double.group(1)))
                        versions.append(versionNumber)
                    if version_triple:
                        versionNumber = str(int(version_triple.group(1)))
                        versions.append(versionNumber)
            if versions:
                sortedVersions = sorted(versions, key=int)
                lastVersion = sortedVersions[-1]
                nextVersion = int(lastVersion) + 1
                nextVersion = str(nextVersion)
    nextVersion = "v" + nextVersion.zfill(3)
    return nextVersion

################################################################################


def getMayaMainWindow():
    mayaMainWindowPtr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(mayaMainWindowPtr), QtWidgets.QWidget)

class GW_alembic_saver(QtWidgets.QWidget):
    '''
    '''
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        mayaMainWindow =  getMayaMainWindow()
        # check for exiting window to avoid duplicates
        objectName = "GwAlembicWindow"
        if cmds.window("GwAlembicWindow", exists = True):
            cmds.deleteUI("GwAlembicWindow", wnd=True)
        self.setObjectName(objectName)
        #Parent widget under Maya main window
        self.setParent(mayaMainWindow)
        self.setWindowFlags(QtCore.Qt.Window)

        #create MAIN layout ####################################################
        self.main_Layout = QtWidgets.QVBoxLayout(self)
        self.setGeometry(1200, 800, 400, 340)
        self.move(600, 350)
        self.setWindowTitle(software_version)

        # Accessing pre existing variables from within Maya
        self.currentWorkspace = cmds.workspace(q=True, fn=True)
        self.currentMayaFile = cmds.file(q=True, sceneName=True).split('/')[-1]
        self.exportsSubdirectory = self.currentWorkspace+"/exports/abc"

        # GET the user created SETS in the scene
        maya_standar_sets = [(u'defaultLightSet'),(u'defaultObjectSet')]
        user_sets = getOutlinerSets()
        for non_wanted_set in maya_standar_sets:
            user_sets.remove(non_wanted_set)

        self.gwTitle = QtWidgets.QLabel(" GW Export Sets to Alembic")
        self.gwTitle.setStyleSheet("color: white;background-color:  rgb(37,42,57);")
        self.gwTitle.setFixedHeight(30)
        
        self.gwTitle2 = QtWidgets.QLabel(""" Exports selected character SETs to Alemibic
 Models must have the geometry in SETs
 
 IMPORTANT!
 - Alembic file name will be the NAMESPACE of the character.
 - It will be writen in the "exports/abc" folder unless 
   otherwise specified.
 - Also will output to CURRENT PROJECT.
 - Hidden geometry will NOT be exported by default.
 - Log file and back-Up will also be writen.

 HOW TO USE: 

   1) Select SETS to export 
   2) Add "notes" (optional)
   3) Push button "Save Alembic" to write to disk

 If you want to use other folder, check "Advanced Options"
 and use "Folder" button to select one.
""")
        self.gwTitle2.setStyleSheet("color: white;background-color:  rgb(57,42,37);")
        #self.gwTitle.setFixedHeight(30)

        self.setsNameLabel = QtWidgets.QLabel("Select sets to export:", self)
        self.setsList = QtWidgets.QListWidget(self)
        self.setsList.setFixedHeight(180) # SIZE
        for set in user_sets:
            self.setsList.addItem(set)
        self.setsList.setSelectionMode(QAbstractItemView.MultiSelection)
        self.setsList.itemSelectionChanged.connect(self.on_change_list)

        # NOTES FOR ALEMBIC FILE ##########################################
        self.notesLabel = QtWidgets.QLabel("Notes:", self)
        self.notes = QtWidgets.QTextEdit("", self)
        self.notes.setPlainText("")
        self.notes.setFixedHeight(40) # SIZE

        text = self.notes.toPlainText() # returns plain text

        self.toggleAdvancedOptions = QtWidgets.QCheckBox("Advanced Options")
        self.toggleAdvancedOptions.setChecked(False)
        self.toggleAdvancedOptions.stateChanged.connect(self.toggle_advanced_options)

        self.toggleOnlyVisible = QtWidgets.QCheckBox("Export only visible objects")
        self.toggleOnlyVisible.setChecked(True)
        self.toggleOnlyVisible.setEnabled(False)

        self.toggleNamespacesOnly = QtWidgets.QCheckBox("Use Namespace only")
        self.toggleNamespacesOnly.setChecked(True)
        self.toggleNamespacesOnly.setEnabled(False)

        self.BrowseAlembicFile = QtWidgets.QPushButton('Folder', self)
        self.BrowseAlembicFile.setFocusPolicy(QtCore.Qt.NoFocus)
        self.BrowseAlembicFile.setEnabled(False)
        self.connect(self.BrowseAlembicFile, QtCore.SIGNAL('clicked()'), self.browse_for_alembic)

        self.alembicFileName = QtWidgets.QLabel(self.exportsSubdirectory)
        self.alembicFileName.setStyleSheet("color: white;background-color: rgb(37,42,57);")
        self.alembicFileName.setFixedHeight(30)

        self.button = QtWidgets.QPushButton('Save Alembic', self)
        self.button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(self.button, QtCore.SIGNAL('clicked()'), self.saveAlembic)

        # BUILD LAYOUTS AND WIDGETS ############################################
        self.main_Layout.addWidget(self.gwTitle)
        self.main_Layout.addWidget(self.gwTitle2)
        self.main_Layout.addWidget(self.setsNameLabel)
        self.main_Layout.addWidget(self.setsList)
        self.main_Layout.addWidget(self.notesLabel)
        self.main_Layout.addWidget(self.notes)
        self.main_Layout.addWidget(self.toggleAdvancedOptions)
        self.main_Layout.addWidget(self.toggleOnlyVisible)
        self.main_Layout.addWidget(self.toggleNamespacesOnly)
        self.main_Layout.addWidget(self.BrowseAlembicFile)
        self.main_Layout.addWidget(self.alembicFileName)

        self.main_Layout.addWidget(self.button)

    def on_change_list(self):
        cmds.select(clear=True)
        for item in self.setsList.selectedItems():
            # print(item.text())
            cmds.select(item.text(),add=True )

    def browse_for_alembic(self):

        directory = cmds.fileDialog2(
            caption="Set Alembic folder",
            startingDirectory = self.currentWorkspace,
            fileFilter="*.abc",
            dialogStyle=2,
            fileMode = 3
        )
        if (directory != None):
            self.exportsSubdirectory = directory[0]
            self.alembicFileName.setText(self.exportsSubdirectory)
        # print self.exportsSubdirectory
        return

    def toggle_advanced_options(self):
        if self.toggleAdvancedOptions.isChecked():
            self.toggleOnlyVisible.setEnabled(True)
            self.toggleNamespacesOnly.setEnabled(True)
            self.BrowseAlembicFile.setEnabled(True)
        else:
            self.toggleOnlyVisible.setEnabled(False)
            self.toggleNamespacesOnly.setEnabled(False)
            self.BrowseAlembicFile.setEnabled(False)

    def selectSets(self):
        # select the content of the set
        currentSet=self.setsCombo.currentText()
        # print ("current set :"+currentSet+"\n")
        if (currentSet != "<Select set>"):
            cmds.select(currentSet,replace=True )

    def saveAlembic(self):
        # exports = self.exportsSubdirectory
        user = getpass.getuser()
        host = socket.gethostname()
        advanced_options = self.toggleAdvancedOptions.isChecked()
        Namespaces_only = self.toggleNamespacesOnly.isChecked()
        export_only_visible = self.toggleOnlyVisible.isChecked()

        # sets_to_export = self.setsList.selectedItems()
        sets_to_export = []
        sets_not_saved_to_alembic=[]
        for item in self.setsList.selectedItems():
            sets_to_export.append(item.text())
        if len(sets_to_export) == 0:
            msgBox = QtWidgets.QMessageBox()
            msgBox.critical(self,"Warning", "No SETS selected!\n\nPlease, select a Set to proceed")
            return
        notes = self.notes.toPlainText()
        notes = '\r\n'+notes.replace('\n', '\r\n')
        notes = ''.join([i if ord(i) < 128 else ' ' for i in notes])

        print("GW Alembic Saver ----------------------------------------------------------------\n")


        for currentSet in sets_to_export:
            # print sets_to_export
            # print currentSet
            cmds.select(currentSet,replace=True )
            selected_meshes = cmds.ls(selection=True, long=True)
            # if len(set(selected_meshes)) == len(selected_meshes):
            #     print("success")
            #     print selected_meshes
            # else:
            #     print("duplicate found")
            #     print selected_meshes
            # return
            #get selected AND visible objects
            if export_only_visible:
                selected_and_visible=[]
                for obj in selected_meshes:
                    if objectIsVisible(obj):
                        selected_and_visible.append(obj)
                selected_meshes  = selected_and_visible

            # ALEMBIC relevant data for Maya command
            start =int (cmds.playbackOptions( query=True, animationStartTime=True ))
            end = int(cmds.playbackOptions( query=True, animationEndTime=True ))
            frames_per_second =  cmds.currentUnit(query=True, time=True)
            print("start fame: ", start, " End frame: " , end , "fps: " , frames_per_second)
            print( "\n");
            # populate "root" varialble with selected geometry

            root_alembic = ""
            for element in selected_meshes:
                root_alembic = root_alembic + " -root " + element

            # print (root_alembic)
            if Namespaces_only:
                file_name=currentSet.split(":")[0]
            else:
                file_name=currentSet.replace(":","_") # convert : in NameSpace to _
            save_name = self.exportsSubdirectory+"/"+file_name+".abc"
            # export to alembic command
            command = "-frameRange " + str(start) + " " + str(end) +" -uvWrite -writeColorSets -writeFaceSets -worldSpace -writeUVSets -dataFormat ogawa " + root_alembic + " -file " + "\"" + save_name + "\""
            print (command+"\r\n")

            viewport_paused = cmds.ogs( query=True,pause = True ) # PAUSE VIEWPORT ############
            if (not viewport_paused): # TOGGLE VIEPORT
                cmds.ogs( pause = True )
                # print ("deactivating viewport\n")

            # print (command)
            alembic_saved = True #### SAVE ALEMBIC
            try:
                cmds.AbcExport ( j = command )
                print ("SAVED "+str(currentSet)+" to Alembic ")
            except:
                alembic_saved = False
                sets_not_saved_to_alembic.append(currentSet)
                error = str("Failed to save Alembic of :" +currentSet)
                cmds.warning( error )
                print (root_alembic)

            if (not viewport_paused): # TOGGLE VIEPORT
                cmds.ogs( pause = True )
                # print("Activating viewport\n")
            
            # Copy version to folder
            if alembic_saved:
                directory_of_alembics =self.exportsSubdirectory+"/"+file_name
                if not os.path.exists(directory_of_alembics):
                    os.makedirs(directory_of_alembics)
                    print("Created directory at: "+directory_of_alembics+"\n")
                version=getVersion_abc(directory_of_alembics)

                if  os.path.exists(directory_of_alembics):
                    print("COPY BACK-UP // Source: "+save_name+" --> Destination: "+directory_of_alembics+"/"+file_name+"_"+version+".abc"+"\n")
                    shutil.copyfile(save_name, directory_of_alembics+"/"+file_name+"_"+version+".abc")
                print ("                            ---->"+version)
            else:
                version="N/A"
            # write LOG info
            now = datetime.datetime.now()
            #?log_file = open(self.exportsSubdirectory+"/"+file_name+".log", "a+")
            log_file = open(directory_of_alembics+"/"+file_name+".log", "a+")
            log_file.write("------------------------------------------------------------------------------\r\n")
            log_file.write(str(now.strftime("%Y-%m-%d %H:%M"))+"\r\n")
            log_file.write("Set: "+currentSet+" Version:"+version+"\r\n")
            log_file.write("User name: "+user+" Machine: "+host+"\r\n")
            log_file.write("Maya build: "+cmds.about(installedVersion=True)+"\r\n")
            log_file.write("Starf frame: "+str(start)+" End frame: "+str(end)+" Frames per second: "+str(frames_per_second)+"\r\n")
            log_file.write("Project located at: "+self.currentWorkspace+"\r\n")
            log_file.write("original Maya file: "+self.currentMayaFile+"\r\n")
            log_file.write("Original Full path:"+cmds.file(q=True, sceneName=True)+"\r\n")
            if alembic_saved :
                log_file.write("Alembic Full path :"+save_name+"\r\n")
                log_file.write("BackUp file       :"+directory_of_alembics+"/"+file_name+"_"+version+".abc\r\n")
            else:
                log_file.write("WARNING : FAILED TO SAVE ALEMBIC FILE\r\n")
                log_file.write("TRYED Alembic Full path is:"+save_name+"\r\n")
                log_file.write("ALEMBIC Maya command options:"+command+"\r\n")
            log_file.write("\r\nNotes: "+notes+"\r\n")
            log_file.close()
        if len(sets_not_saved_to_alembic) > 0:
            msgBox = QtWidgets.QMessageBox()
            msgBox.critical(self,"Alembic failure", "Not all SETS saved!\n\nCheck script editor!!\n\nCHECK if all nodes to export have different names\nAlso instances are NOT supported by Maya alembic")
            print("GW Alembic Saver ----------------------------------------------------------------\n")
            for s in sets_not_saved_to_alembic:
                print ('WARNING: "'+str(s)+'" not saved in alembic!\n')
            pass
        else:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setWindowTitle("Info")
            msgBox.setText("Alembic saved!")
            msgBox.exec_()

        self.close()

# Check if Maya scne file exists, then proceed
maya_scene_name = cmds.file(query=True, sceneName=True, shortName=True) 
print (maya_scene_name)
if (maya_scene_name==""):
    cmds.confirmDialog( title='SCENE NOT SAVED', message='Cannot work with \"untitled\" Maya scene.\nPlease, save scene before proceed.', button=['OK'], defaultButton='Ok', dismissString='Ok' )
else: 
    if not cmds.pluginInfo('AbcExport',q=True,l=True):
		# Load Plugin
        try:
            cmds.loadPlugin('AbcExport')
        except: 
            raise Exception('Unable to load abcExport plugin!')
    dialog = GW_alembic_saver()
    dialog.show()
