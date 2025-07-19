from __future__ import annotations

"""
V00 of a Python Graph Editing Tool. 
Grant Hillebrand 

See https://isijingi.co.za/wp/category/higraph/ for related posts.

"""

import sys
import os
import copy
import math
import traceback  #for the Python window

#Debugging stuff

#import logging
#import gc
import weakref

from typing import List, Dict

from PySide6.QtWidgets import ( QApplication, QWidget, QMainWindow, QDialog,
            QGraphicsScene, QGraphicsView, QListWidget, QListWidgetItem,
            QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
            QLineEdit, QInputDialog, QMenu, QFileDialog, QStyleOptionGraphicsItem,
            QSlider, QLabel, QStatusBar,
            QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton)

from PySide6 import (QtCore, QtWidgets, QtGui )
from PySide6.QtGui import (QStandardItemModel, QStandardItem, QPolygonF,QPainter,
            QTransform, QFont, QFontMetrics, QAction, QCursor, QPen,QBrush,
            QPainterPath, QPainterPathStroker,
            QGuiApplication, QImage, QPixmap)
from PySide6.QtCore import (QLineF, QPointF,QPoint, QRect, QRectF, 
            QSize, QSizeF, Qt, Signal, Slot, QTimer, 
            QMimeData, QBuffer, QByteArray, QIODevice)
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from ui_form import Ui_MainWindow
#from dlgCredits import Ui_dlgCredits
from ui_Credits import Ui_dlgCredits
from Ui_HelpAbout import Ui_dlgAbout
#from dlgHelpAbout import Ui_dlgAbout 

# core Graph class:
from coreGraph import Graph

# XML serialiser/ file writing
#TODO: should this get folded in to some other object? Possibly `graphModel`
import yEdXfileOnly as yEd

#Helper & housekeeping functions

#Global constants. 
#TODO: Put these in a config file at some point
NODESIZE = 15
#Selection tolerance
HITSIZE = 5
#Offset to use when pasting nodes
PASTE_OFFSET = 20

APP_NAME = "qtPyGraphEdit V00"

# Indices for Qt Item metadata tags 
#index data: item Num from Graph
KEY_INDEX = Qt.UserRole + 1
#type date: item type 
KEY_ROLE = Qt.UserRole + 2

# To let Qt know what are nodes and what are edges
#TODO: Can ListWidgets take any type for roles? (Items can)
ROLE_NODE = QListWidgetItem.ItemType.UserType + 1
ROLE_EDGE = QListWidgetItem.ItemType.UserType + 2
#Control boxes for connecting/ moving
ROLE_CB = QListWidgetItem.ItemType.UserType + 3

class graphModel(QStandardItemModel):
    """ Hold the visual details for the nodes and edges of the graph (x,y, size)
        V0: Nodes: nodeID FK from Graph, x,y
            Edges: edgeID FK from Graph, sx, sy, ex, ey.
        V01: Edges as splines

        Will/ must! stay in sync with Graph, which will handle topology.
    """

    def __init__(self):
        super().__init__()
        #Setup the abstract graph
        self.Gr = Graph()
        #Read this from config/ on file load
        self.isDigraph = True #False  #Test with True, since removing stuff is normally easier

    def __repr__(self):
        rStr =""
        for row in range(self.rowCount()):
            #TODO: Columns not used here
            for col in range(self.columnCount()):
                item = self.item(row, col)
                rStr += f"({row}, {col}): idx ={item.data(KEY_INDEX)},{item.data(KEY_ROLE)} \n {item}\n\n"
        return rStr

    __str__ = __repr__

    def getModelItems(self):
        return [f"{self.item(i).text()}::{self.item(i).data(KEY_INDEX)} ({self.item(i).data(KEY_ROLE)})" \
            for i in range(self.rowCount())]

    def addGMNode(self,posn,nameP=""):
        """Make a Graph Model NODE item, return the item and the index number (item,n) """
        #TODO: name should be a param here
        #NB: The order in the lists (Gr, listView and model MUST BE MAINTAINED.

        # Make the coreGraph02 node
        n = self.Gr.addNode()
        #Default name is node number
        if not nameP:
            self.Gr.nodeD[n].metadata.update({'name': f"n{n}"})
        else:
            self.Gr.nodeD[n].metadata.update({'name': nameP})

        #TODO: How to have an item.dispText (dispName might be better?) at this level. Will need to sync onChange()
        #Make the Qt Item with text n
        item = QStandardItem(str(n))
        item.setData(n,KEY_INDEX)
        item.setData(ROLE_NODE,KEY_ROLE)

        self.appendRow(item)
        return item,n

    def getGMNodes(self):
        """ Returns all the Graph Model Nodes"""
        return [self.item(i).data(self.ROLE_NODE) for i in range(self.rowCount())]

    def addGMEdge(self,sItem, eItem, nameP=None):
        """Make a Graph Model EDGE item, return the item and the index number (item,n) 
           Note that either (but not both) of s & e may also be an edge (hypergraph)
        """
        start = sItem.nodeNum
        end = eItem.nodeNum
        e = self.Gr.addEdge(start,end)
        self.Gr.edgeD[e].metadata.update({'name':nameP })
        #Make the Qt Item with text e
        item = QStandardItem(str(e))
        item.setData(e,KEY_INDEX)
        item.setData(ROLE_EDGE,KEY_ROLE)
        #Add to the model
        self.appendRow(item)
        return item,e

    def findItemByIdx(self,idx):
        """takes a ROLE_INDEX value, and get the item out, or none """
        for row in range(self.rowCount()):
            item = self.item(row)
            if item.data(KEY_INDEX) == idx:
                return item
        return None

    def findRowByIdx(self,idx):
        """takes a ROLE_INDEX value, and returns the model row out, or none """
        for row in range(self.rowCount()):
            item = self.item(row)
            if item.data(KEY_INDEX) == idx:
                return row
        return None

    def itemName(self,itm)->str:
        """ Take a KEY_INDEX, returns the name from the graph"""
        iName = ""
        if itm.data(KEY_ROLE) == ROLE_NODE:
            iName = self.Gr.nodeD[int(itm.nodeNum)].metadata['name']
        elif itm.data(KEY_ROLE) == ROLE_EDGE:
            iName = self.Gr.edgeD[int(itm.edgeNum)].metadata['name']
        return(iName)

    def edgesAtNode(self,itm):
        """ Take a node's KEY_INDEX, returns a list of  attached graph edges (both ends), or None"""
        eList = []
        if itm.data(KEY_ROLE) == ROLE_NODE:
            eList = copy.deepcopy(self.Gr.nodeD[int(itm.nodeNum)].startsEdges)
            eList += copy.deepcopy(self.Gr.nodeD[int(itm.nodeNum)].endsEdges)
        return(eList)

    def delEdge(self, delIdx):
        """ Takes an internal index value,
         and deletes the edge from the abstract graph and the model.
         May evolve to manage all the deletions here, rather than scene
        """
        #Delete from Gr
        #print(f"Scene del Edge About to delete {delIdx =} from {self.Gr =}")
        self.Gr.delEdge(delIdx)
        # Models work by rows, not items
        self.removeRow(self.findRowByIdx(delIdx))

    def delNode(self, delIdx):
        """ Takes an internal index value,
         and deletes the node from the abstract graph and the model.
         May evolve to manage all the deletions here, rather than scene
        """
        #Delete from Gr
        #print(f"model delNode {delIdx =}")
        #print(f"{self.Gr =}")
        self.Gr.delNode(delIdx)
        # Models work by rows, not items
        self.removeRow(self.findRowByIdx(delIdx))

    def clear(self):
        """ Extend the base clear method to clear the abstract Graph too"""
        del self.Gr
        self.Gr = Graph()
        #Reset the global Gr id counter too
        Graph.nextID = 0
        super().clear()

class VisNodeItem(QGraphicsItem):
    """ Create a new node - both Graph Model and Visual ("graphics") This connects visual Rect to model and list """

    def __init__(self,posn,model,listWidget, parent=None, nameP =""):
        #print(f"In VisNodeItem {posn =}")
        super().__init__(parent)
        self.suppressItemChange = True  # suppress itemChange (was protected, but scene needs to set it)
        
        self.model = model
        self.listWidget = listWidget
        #Store the lines that start/ end at this node
        self.startsEdges = []  
        self.endsEdges = []  

        #WHERE it must appear
        self.setPos(posn)
        
        #Create an abstract node, and keep the index as well
        self.node,self.nodeNum = self.model.addGMNode(posn,nameP=nameP)

        #add to the text list
        lWitem = QListWidgetItem(self.model.Gr.nodeD[self.nodeNum].metadata['name'])
        lWitem.setData(KEY_INDEX,self.nodeNum)
        lWitem.setData(KEY_ROLE,ROLE_NODE)
        self.listWidget.addItem(lWitem)

        # Create a text item to hold & show the ID number
        # Not needed with KEY_INDEX role
        #self.textItem = QGraphicsTextItem(f"{self.nodeNum}", self)
        #textRect = self.textItem.boundingRect()
        #self.textItem.setPos(-textRect.width()/2, -textRect.height()/2)
        #self.textItem.setFlag(QGraphicsItem.ItemIsSelectable, False)
        #self.textItem.setFlag(QGraphicsItem.ItemIsFocusable, False)

        self.dispText = self.model.Gr.nodeD[int(self.nodeNum)].metadata['name']

        #Non-display version, for referencing to model and listView
        self.setData(KEY_INDEX, self.nodeNum)
        self.setData(KEY_ROLE, ROLE_NODE)
        
        #The shape of the node- rectangle
        #1st 2 parms are origin, 2nd 2 are width & height
        #Rect shape
        #self.nodeShape = QGraphicsRectItem(-NODESIZE/2,-NODESIZE/2,NODESIZE,NODESIZE,self)
        #Circle Shape
        self.nodeShape = QGraphicsEllipseItem(-NODESIZE/2,-NODESIZE/2,NODESIZE,NODESIZE,self)
        self.nodeShape.my_parent_item = self #coPilot's suggestion to stop GC issues. Force a strong reference
        self.nodeShape.setPen(QPen(Qt.NoPen))
        #TODO: Set selectable False - see if that processes clicks better?
        self.nodeShape.setFlag(QGraphicsItem.ItemIsSelectable, False)

        #Make nodes appear in front of edges for painting & selection
        self.setZValue(1000)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlags(self.GraphicsItemFlag.ItemSendsScenePositionChanges)

        #self.setAcceptHoverEvents(True)
        self.hovered = False

        self.suppressItemChange = False  # enable itemChange normally

    def __repr__(self):
        return f"\n** VisNodeItem {super().__repr__()}\nIndex:{self.data(KEY_INDEX) }  Role:{self.data(KEY_ROLE) =} @ {self.pos() =}\n  \
                {self.startsEdges = }  ,  {self.endsEdges = }" #\n {self.nodeShape =})"
    __str__ = __repr__

    def boundingRect(self):

        #Calc text box. 
        #Hardcoding on top for now
        #self.dispText = self.model.Gr.nodeD[int(self.nodeNum)].metadata['name']
        #self.dispText += f"\n{int(self.pos().x())},{int(self.pos().y())}"
        tFont = QFont()
        metrics = QFontMetrics(tFont)
        textRect = metrics.boundingRect(self.dispText)
        #centre it
        textRect.adjust(-textRect.width()/2,-textRect.height()/2,-textRect.width()/2,-textRect.height()/2)

        nodeRect = QRectF(-NODESIZE/2,-NODESIZE/2,NODESIZE,NODESIZE)

        penWidth = 2
        bRect = nodeRect.united(textRect).adjusted(-penWidth,-penWidth,penWidth,penWidth)
        return bRect

    def paint(self, painter, option, widget=None):
        """ Draw a VisNode item"""
        #Debug: Show the centre of the node
        #painter.drawLine(-10,-10,10,10)
        #painter.drawLine(-10,10,10,-10)
        #painter.drawRect(self.boundingRect())
        
        #painter.setClipping(False)

        if self.isSelected():
            painter.setPen(QPen(Qt.blue,1,Qt.DashLine))
        else:
            painter.setPen(Qt.black)

        if self.hovered:
            brush = QBrush(Qt.lightGray)  # Light gray fill
        else:
            brush = QBrush(Qt.white)      # Normal fill
        painter.setBrush(brush)

        #TODO: Use the shape used in the constructor - will need a flag
        #painter.drawRect(self.nodeShape.rect())
        painter.drawEllipse(self.nodeShape.rect())

        # Pos on top (this can be generalised to left, bottom, right, etc)
        r = QRectF(0,-NODESIZE,0,0) 
        #update height & width
        r = painter.drawText(r,Qt.AlignCenter,self.dispText)
        painter.drawText(r, Qt.AlignCenter, self.dispText)

    def itemChange(self,change,value):
        """ in particular, deal with VisNode moving --> update VisEdges"""
        if not self.suppressItemChange:
            #TODO: figure out the differen `change` options
            self.dispText = self.model.Gr.nodeD[int(self.nodeNum)].metadata['name']
            
            for sEdge in self.startsEdges:
                sEdge.updateLine(self)
            for eEdge in self.endsEdges:
                eEdge.updateLine(self)

        #note the **return**
        return super().itemChange(change,value)

    #TODO: hoverEvents are not sent when there is an explicit mouseEVent handler. Handle in scene and delete here
    def xxhoverEnterEvent(self, event=None):
        self.hovered = True
        self.update()  # trigger repaint
        super().hoverEnterEvent(event)

    def xxhoverLeaveEvent(self, event):
        self.hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, mouseEvent):
        if (mouseEvent.button() == Qt.MouseButton.LeftButton):
            #TODO: check for <shift> & <ctrl> click to add, otherwise clear.
            #NOTE: Qt clears the selection elsewhere on mouseRelease 
            modifiers = mouseEvent.modifiers()
            if not (modifiers & Qt.ShiftModifier or modifiers & Qt.ControlModifier) \
                and not self.isSelected():
                self.scene().clearSelection()
            self.setSelected(True)
            #Highlight the list item as well
            lWItem = self.listWidget.findItemByIdx(self.data(KEY_INDEX))
            self.listWidget.setCurrentItem(lWItem)

        super().mousePressEvent(mouseEvent)

#Various support classes for edges.

class TransparentTextItem(QGraphicsTextItem):
    """ allows parent.shape() to select the text, rather than the textItem always grabbing the event  """
    def __init__(self, text:str, parent=None):
        if not parent:
            print(f"Error creating TransparentTextItem - no parent set")
        super().__init__(text,parent)
        # If you don’t need focus handling, remove focusable flag
        #self.setFlag(QGraphicsTextItem.ItemIsFocusable, False)

    def paint(self, painter, option, widget=None):
        super().paint(painter,option,widget)

    def mousePressEvent(self, event):
        # Forward to parent
        if self.parentItem():
            self.parentItem().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.parentItem():
            self.parentItem().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.parentItem():
            self.parentItem().mouseDoubleClickEvent(event)
        else:
            super().mouseDoubleClickEvent(event)

class controlBox(QGraphicsRectItem):
    """a little square to use as a handle for moving edge control points """

    def __init__(self,pos:QPointF, parent = None):
        #Parent should be calling edge
        super().__init__(-HITSIZE/2,-HITSIZE/2,HITSIZE,HITSIZE,parent)
        self.setPos(pos)
        self.setPen(QPen(Qt.red))
        self.setBrush(Qt.red)
        #Above selected Edges
        self.setZValue(3000)
        self.setData(KEY_ROLE, ROLE_CB)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlags(self.GraphicsItemFlag.ItemSendsScenePositionChanges)        
        #print(f"control box created {self}")

    def mousePressEvent(self,mouseEvent):
        #print(f"cBox clicked")
        super().mousePressEvent(mouseEvent)

class ArrowHeadItem(QGraphicsItem):
    """An arrowhead. 
        position updates are driven from the parent item
       chatGPT based code """

    def __init__(self, size=NODESIZE, parent=None):
        super().__init__(parent)
        self.size = size
        # Define arrowhead polygon pointing right (+X)
        self.polygon = QPolygonF([
            QPointF(0, 0),
            QPointF(-size, size / 2),
            QPointF(-size, -size / 2)
        ])
        #Transform by -NODESIZE/2 to not disappear under the node
        self.polygon.translate(QPointF(-NODESIZE/2,0))
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        #Hook in the parent p1 & p2 so that the painter can work out the angle
        if parent:
            self.setPos(parent._line.p2()) #TODO: This is not elegant for when edges are not lines
            self.start = parent._line.p1()

    def boundingRect(self):
        # Rectangle covering the polygon
        return QRectF(-self.size, -self.size/2, self.size, self.size)

    def paint(self, painter, option, widget):
        #print("Arrow Paint")

        #WHy is this needed? parent sel should propagate?
        #This code runs, but has no effect? What is overriding it?
        painter.save()
        if self.parentItem():
            if self.parentItem().isSelected():
                self.setSelected(True)
                #print("Setting arrow as selected")
                painter.setBrush(QBrush(Qt.blue))
                painter.setPen(QPen(Qt.blue,1,Qt.DashLine)) 

        if self.isSelected():
            #TODO: Arrow is never selected!
            #print("Arrow Paint SELECTED")
            painter.setBrush(QBrush(Qt.blue))
            painter.setPen(QPen(Qt.blue,1,Qt.DashLine)) 
        else:
            painter.setBrush(QBrush(Qt.black))
            painter.setPen(QPen(Qt.black))
        painter.drawPolygon(self.polygon)
        painter.restore()

class VisEdgeItem(QGraphicsItem):
    """ Create a new edge - both Graph Model and Visual ("graphics")
      This connects visual Rect to model and list 
    """
    #TODO: Look at refactoring with more of drawLineV2's structure
    #needs to be a graphics item of some sort (line)
    #HSplines will be a separate graphics class?

    def __init__(self,model,listWidget,sItem, eItem, parent=None, nameP=""):
        """ Create a visual edge, using the pos of the st and end 
        """
        super().__init__(parent)

        self.suppressItemChange = True  # suppress itemChange until all attribs set.

        self.model = model
        self.listWidget = listWidget

        #Note: Unlike a node which is a 1-click create,
        #   an edge can only be created once the start and end nodes are known. 
        #   Thus drawing must precede the creation of the abstract edge.
        #   This drawing has to be handled by the Scene mouse events, prior to construction.

        #SO code: track the VisNodes
        #TODO: update to startItem for hypergraphs
        #TODO: fold this into setStart & setEnd, for updates!
        self.startNode = sItem
        self.endNode = eItem

        #Create an abstract edge, and keep the index as well
        sName =self.model.Gr.nodeD[sItem.nodeNum].metadata['name'] 
        eName =self.model.Gr.nodeD[eItem.nodeNum].metadata['name'] 

        if not nameP:
            #TODO: Refactor edgeNum & nodeNum to itemNum for hyperedges
            self.edge,self.edgeNum = self.model.addGMEdge(sItem,eItem,nameP=f"{sName}->{eName}")
            #update the name with the edge ID, to help tracking
            #TODO: Find a more elegant wrapper for this!
            self.model.Gr.edgeD[self.edgeNum].metadata.update({'name':f"{self.edgeNum} {self.model.Gr.edgeD[self.edgeNum].metadata['name']}"})
        else:
            self.edge,self.edgeNum = self.model.addGMEdge(sItem,eItem,nameP=nameP)

        #add to the text list
        #TODO: Should this not be driven from the model?
        lWitem = QListWidgetItem(self.model.Gr.edgeD[self.edgeNum].metadata['name'])
        lWitem.setData(KEY_INDEX,self.edgeNum)
        lWitem.setData(KEY_ROLE,ROLE_EDGE)
        self.listWidget.addItem(lWitem)

        # Create a text item to hold & show the ID number
        #self.textItem = QGraphicsTextItem(f"{self.edgeNum}", self)
        #textRect = self.textItem.boundingRect()
        #self.textItem.setPos(-textRect.width()/2, -textRect.height()/2)
        
        #Non-display data, for referencing to model and listView
        noPen = QPen(Qt.NoPen)
        self.setData(KEY_INDEX, self.edgeNum)
        self.setData(KEY_ROLE, ROLE_EDGE)
        #Draw name in the middle
        #self.textItem = QGraphicsTextItem(self.model.Gr.edgeD[self.edgeNum].metadata['name'], parent=self)
        # chatGPT's suggestion to avoid shape() not selecting it - TransparentTextItem
        self.textItem = TransparentTextItem(self.model.Gr.edgeD[self.edgeNum].metadata['name'], parent=self)
        #Stop Python GC from mangling things on delete
        self.textItem.my_parent_item = self

        #TODO: choose one of textItem and dispText, and refactor
        self.dispText = self.model.Gr.edgeD[self.edgeNum].metadata['name']
        self.textItem.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.textItem.setFlag(QGraphicsItem.ItemIsFocusable, False)
        
        #Create the graphical line
        #SO uses _line , since Connection isA QGraphicsLineItem
        # create edgeLine to do that. Allows for replacing line type later.
        self._line = QtCore.QLineF(sItem.pos(), eItem.pos()) 
        self.edgeLine = QGraphicsLineItem(self._line,parent=self)
        #Stop Python GC from mangling things on delete
        self.edgeLine.my_parent_item = self
        self.edgeLine.setLine(self._line)
        self.edgeLine.setPen(noPen)
        self.edgeLine.setFlag(QGraphicsItem.ItemIsSelectable, False)
        #Add in the arrowhead for digraph
        if self.model.isDigraph:
            self.endShape = ArrowHeadItem(size=NODESIZE/2, parent=self)
        else:
            self.endShape = None

        self.bRect =self.edgeLine.boundingRect()

        #Link up the topology for the visual graph.
        #TODO: hypergraph - lines  can start xor end on an edge - 
        sItem.startsEdges.append(self)
        self.setStart(sItem)
        eItem.endsEdges.append(self)
        self.setEnd(eItem)

        #Selection and editing vars:
        #Control Boxes
        self.scB = None
        self.ecB = None

        self.setFlags(self.GraphicsItemFlag.ItemSendsScenePositionChanges)
        #V00: Set edges to only move via nodes.
        #TODO: Needs to be selectable to edit name/ show in list.
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, False) #Moving done via enditems
        #Checking if this was why there were ghosts
        #self.setCacheMode(QGraphicsItem.NoCache)
        
        #is this the only edge selected (used for rerouting)
        self.isOnlySelected = False
        #disable the guard
        self.suppressItemChange = False  # enable itemChange normally

    def __repr__(self):
        return f"\n>> VisEdgeItem {super().__repr__()}\n {self.textItem =}  {self.edgeLine =}\nID: {self.edgeNum} {self.dispText} s:({self.startNode.data(KEY_INDEX)})" + \
                        f" e:({self.endNode.data(KEY_INDEX)}) {self.startNode.nodeShape =} {self.endNode.nodeShape =}<<"

    def boundingRect(self):
        """ edges boundingRect """
        adjust = 2 # self.pen.width() / 2
        #self.bRect = self.edgeLine.boundingRect()
        #update the text pos on move as well (itemChange???)
        #return self.bRect.adjusted(-adjust, -adjust, adjust, adjust)
        return self.childrenBoundingRect().adjusted(-adjust, -adjust, adjust, adjust)

    def paint(self, painter, option, widget=None):
        #print(f" Paint {self.edgeNum =}")
        #painter.setPen(Qt.red)
        #painter.drawRect(self.bRect)
        #use the textBRect to adjust exact display position on the line (can be a [0,1] multiplier)

        textBRect = self.textItem.boundingRect()
        #To offset, `` from x
        self.textItem.setPos((self.startNode.pos().x()+self.endNode.pos().x())/2 - textBRect.width()/2, \
            (self.startNode.pos().y()+self.endNode.pos().y() - textBRect.height() )/2)
        
        #If you don't use .textItem, but .dispText (deprecate)
        tPos = QPointF((self.startNode.pos().x()+self.endNode.pos().x())/2 - textBRect.width()/2, \
            (self.startNode.pos().y()+self.endNode.pos().y())/2)

        #painter.drawRect(self.textItem.boundingRect())
       
        if self.isSelected():
            painter.setPen(QPen(Qt.blue,1,Qt.DashLine))
            self.textItem.setDefaultTextColor(Qt.blue)   
        else:
            painter.setPen(Qt.black)
            self.textItem.setDefaultTextColor(Qt.black)

        painter.drawLine(self._line)
        #painter.drawText(QPoint(0,0),self.textItem.toPlainText())
        #painter.drawText(tPos,self.dispText) #textItem.toPlainText())

        #Debug - draw the shape path
        #painter.drawPath(self.shape())

    def shape(self):
        """ Set a tight selection shape """
        path = QPainterPath()
        #Line
        path.moveTo(self.startNode.pos())
        path.lineTo(self.endNode.pos())
        
        #Text
        path.addRect(self.textItem.boundingRect().translated(self.textItem.pos()))

        outlinePath = QPainterPathStroker()
        outlinePath.setWidth(HITSIZE*2)
        return outlinePath.createStroke(path)

    def mousePressEvent(self, mouseEvent):
        if (mouseEvent.button() == Qt.MouseButton.LeftButton):

            modifiers = mouseEvent.modifiers()
            #TODO: Handle shift & ctrl click properly. 
            #TODO: Should this be here, or in Scene.mousePress???
            if not (modifiers & Qt.ShiftModifier or modifiers & Qt.ControlModifier) and \
                not self.isSelected():
                self.scene().clearSelection()
            self.setSelected(True)
            #Highlight the list item as well
            #print(f"\nSelected elt: {self.data(KEY_INDEX)}\n")
            lWItem = self.listWidget.findItemByIdx(self.data(KEY_INDEX))
            self.listWidget.setCurrentItem(lWItem)

    def itemChange(self, change, value):
        #print(f"edge item change {change},{value}")
        #guard clause to trap calls from __init__
        if not self.suppressItemChange:
            # Change the display text - what would the <change> be? Using ToolTip as the closest
            if change == QGraphicsItem.GraphicsItemChange.ItemToolTipChange:
                #Note: .dispText is simpler but .textItem is richer.
                self.dispText = self.model.Gr.edgeD[int(self.edgeNum)].metadata['name']
                self.textItem.setPlainText(self.model.Gr.edgeD[self.edgeNum].metadata['name'] )
        
        return super().itemChange(change, value)

    #From musicamente's SO post    
    def setP2(self, p2):
        #only used in the creation phase
        self._line.setP2(p2)
        self.edgeLine.setLine(self._line)
    
    def setStart(self, start):
        """ Set the startItem to start. Also update model, for edits"""
        #TODO: Add updateEdge() to Graph class, then include here
        self.startNode = start
        self.updateLine(start)

    def setEnd(self, end):
        #TODO: Add updateEdge() to Graph class, then include here
        self.endNode = end
        self._line.setP2(end.scenePos())
        self.updateLine(end)

    def updateLine(self, source):
        """ Tell Qt the ends have moved"""
        self.prepareGeometryChange()
        if source == self.startNode:
            #This is a built-in function
            self._line.setP1(source.scenePos())
        #TODO: For hypergraphs, this will need to change
        else: #endNode
            self._line.setP2(source.scenePos())
        self.edgeLine.setLine(self._line)
        if self.endShape:
            self.endShape.prepareGeometryChange()
            # Compute rotation angle
            dx = self._line.p2().x() - self._line.p1().x()
            dy = self._line.p2().y() - self._line.p1().y()
            angle_deg = math.degrees(math.atan2(dy, dx))
            self.endShape.setRotation(angle_deg)

            self.endShape.setPos(self._line.p2())
        self.update()

    #TODO: Move the end of an edge to another node

class grScene(QGraphicsScene):
    """ holds and extends all the drawing, connects to model using VisNodeItem and VisEdgeItem"""

    # See Hg QT6.gaphor `GrScene INSERT states` for analysis of states (StateMachine)

    #Mouse state enum
    # INSERTEDGE2CLICK for handling choice of item in ambiguous cases, which requires a click to choose, 
    # and thus the end is selected on a Press, not a release.
    INSERTNODE, INSERTEDGE, POINTER, INSERTEDGE2CLICK, MOVEEDGEEND = range(5)

    def __init__(self, model,listWidget):
        super().__init__()
        self.model = model
        self.listWidget = listWidget
        self.mouseMode = self.POINTER

        # Placeholders for nodes & edges between mouse states when creating an edge
        self.tmpEdgeSt = None #QGraphicsItem - temp start
        self.tmpEdgeEnd = None
        self.startPoint = None #QPoints, to draw the edge's sline
        self.endPoint = None
        self.rubberLine = None
        self.GrRubberLine =None

        #Handle hovering
        self.lastHovered = None #QGraphicsItem
        #Track single item selection (for edges)
        self.onlySelected = None

        #Add axes to help see how things move & debug graphical issues.
        #TODO: THere must be a better solution!
        #WHite to provide a auto-zoom anchor
        """
        VLine = QGraphicsLineItem(0,100,0,-100)
        self.addItem(VLine)
        VLine.setPen(QPen(Qt.white))
        HLine = QGraphicsLineItem(100,0,-100,0)
        HLine.setPen(QPen(Qt.white))
        self.addItem(HLine) 
        """

    def itemsHere(self, pos: QPointF, size: QSizeF, itemRoles: List[int]):
        """Return a list of the items who's roles match `itemRoles`, within `size` of `pos` """
        half_w = size.width() / 2
        half_h = size.height() / 2
        rect = QRectF(pos.x() - half_w, pos.y() - half_h, size.width(), size.height())
        raw = self.items(rect, Qt.IntersectsItemShape, Qt.DescendingOrder)
        filtered = []
        for itm in raw:
            #print(itm)
            if itm.data(KEY_ROLE) in itemRoles:
                filtered.append(itm)
                    #break
        #print(filtered)
        return filtered

    def pickItemAt(self, mouseEvent, size: QSizeF, itemRoles: List[int]):
        """ Return the user's choice of item at mouseEvent.scenePos() +- size, of type itemRoles, or None 
            TODO: This can be extended to return the <point> on the item, to allow for multiedges and blob 'control points'
        """
        #TODO: Change the param to pos, to make it more useful
        mPos = mouseEvent.scenePos()
        #TODO: Make the size a config param (at call time)
        items = self.itemsHere(mPos, size, itemRoles)
        #print(f"{items =}")
        pickedItem = None
        if len(items) == 1:
            pickedItem = items[0]
        elif len(items) > 1:
            #Since this will add a click, we go to a 2 click insert for edges
            if self.mouseMode == self.INSERTEDGE:
                self.mouseMode = self.INSERTEDGE2CLICK
            # standalone popup context menu
            menu = QMenu()
            actions = [] #menuActions equate to selectable items.
            
            for itm in items:
                if itm.data(KEY_ROLE) == ROLE_EDGE:
                    iType = "Edge"
                elif itm.data(KEY_ROLE) == ROLE_NODE:
                    iType = "Node"
                else:
                    iType = ""
                label = f"{iType}:{itm.data(KEY_INDEX)}>{itm.dispText}" 
                act = QAction(label, menu)
                menu.addAction(act)
                actions.append((act, itm))
            #Add None to the end of the list
            act = QAction("None", menu)
            menu.addAction(act)
            actions.append((act, None))

            # exec() returns the QAction that was triggered (or None) 
            chosen_action = menu.exec(mouseEvent.screenPos()) 
            if chosen_action:
                # find which item corresponds to that action
                for act, itm in actions:
                    if act is chosen_action:
                        pickedItem = itm

        return pickedItem

    def getSceneMousePos(self):
        """ return the current mouse position. Needed for multi-click inserts. Assumes only 1 view"""
        global_pos = QCursor.pos()
        #Assume only 1 view for now
        view = self.views()[0]
        view_pos = view.mapFromGlobal(global_pos)
        scene_pos = view.mapToScene(view_pos)
        return scene_pos
        
    #Code to handle the edge rubber banding during creation (QT handles edit changes)

    def startRubberLine(self, mPos):
        """ called from INSERTEDGE: mousePress. All vars are class global """
        #lock the start item in place so that it doesn't drag
        self.tmpEdgeSt.setFlag(self.tmpEdgeSt.GraphicsItemFlag.ItemIsMovable, False)
        
        #This will change when the whole boundary/ edge can be a connection point
        self.startPoint = self.tmpEdgeSt.pos()
        self.endPoint = self.getSceneMousePos()

        #Create the rubberBand line (actual edge is created on mouseRelease)
        self.rubberLine = QLineF(self.startPoint, self.endPoint)
        self.GrRubberLine = self.addLine(self.rubberLine)
        
    def stretchRubberLine(self,mPos):
        """ called from INSERTEDGE: mouseMove """
        self.endPoint = mPos # mouseEvent.scenePos()
        self.rubberLine.setP2(self.endPoint)
        self.GrRubberLine.setLine(self.rubberLine)
        
    def endRubberLine(self):
        """called on successful end item found for edge:
         from INSERTEDGE mouseRelease or INSERTEDGE2CLICK mousePress """

        #Create the actual edge
        edgeItem = VisEdgeItem(self.model,self.listWidget,self.tmpEdgeSt, self.tmpEdgeEnd, parent=None)
        #Add to *Scene*
        self.addItem(edgeItem)
        edgeItem.setFlag(QGraphicsItem.ItemIsSelectable, True) #can't select a node to move it due to drawing order
        edgeItem.setFlag(QGraphicsItem.ItemIsMovable, False)

    def resetRubberLine(self):
        """ Called whether or not an edge is created """
        if self.tmpEdgeSt:
            self.tmpEdgeSt.setFlag(self.tmpEdgeSt.GraphicsItemFlag.ItemIsMovable, True)
        if self.GrRubberLine:
            self.removeItem(self.GrRubberLine)
        self.tmpEdgeSt = None 
        self.tmpEdgeEnd = None
        self.startPoint = None 
        self.endPoint = None
        self.rubberLine = None
        self.GrRubberLine =None

    #Code to handle end terminator moving
    def startMovingEdgeEnd(self,edge, cBox):
        """ relink edge, using cBox as the floating end point
        similar to rubberLine, but we now have a line to work with"""
        #print(f"StartMovingEdge {edge}")
        self.cBox = cBox #Store the box for the Move/ Finish functions
        #is cBox at start or end?
        if self.cBox.pos() == edge.startNode.pos():
            # NOTE: Node relinking is only done on successful finish, so track the old Terminator item
            self.oldTermItem = edge.startNode
            self.EdgeEnd = "start"
            #link edge to CB to move
            edge.setStart(cBox)
        else:
            self.EdgeEnd = "end"
            # NOTE: Node relinking is only done on successful finish
            self.oldTermItem = edge.endNode
            edge.setEnd(cBox)

        cBox.setFlag(QGraphicsItem.ItemIsMovable, True)

    def MoveEdgeEnd(self,edge,mPos):
        """edge is a VisEdgeItem, that has been set up for moving (cBs in place) """
        self.cBox.setPos(mPos) 
        edge.updateLine(self.cBox)
        
    def finishMovingEdgeEnd(self,edge,mPos,mouseEvent):
        """ note pickItemAt needs the full mouseEvent (screenPos) """

        #Check that this is on a valid node/ Termination pt
        newTermItem = self.pickItemAt(mouseEvent, QSize(HITSIZE,HITSIZE),[ROLE_NODE])
        if newTermItem:
            #Unlink Edge from CB, link to newItem, if we have really moved:
            if self.EdgeEnd == "start" and newTermItem != self.oldTermItem:
                #edge.startNode = newTermItem
                edge.setStart(newTermItem)
                #relink self.oldTermItem in Gr
                # While clunky, these params will work with any item type
                self.model.Gr.updateEdge(edge.data(KEY_INDEX) ,self.oldTermItem.data(KEY_INDEX), "start", newTermItem.data(KEY_INDEX))
                #Move the reverse pointer from the oldTermItem to the new:
                self.oldTermItem.startsEdges.remove(edge)
                newTermItem.startsEdges.append(edge)
            elif newTermItem != self.oldTermItem:  #end
                #edge.endNode = newTermItem
                self.model.Gr.updateEdge(edge.data(KEY_INDEX) ,self.oldTermItem.data(KEY_INDEX), "end", newTermItem.data(KEY_INDEX))
                edge.setEnd(newTermItem)
                #Move the reverse pointer from the oldTermItem to the new:
                self.oldTermItem.endsEdges.remove(edge)
                newTermItem.endsEdges.append(edge)
        else: # link back to old
            #print("Missed (nothing found) on relink")
            self.cBox.setPos(self.oldTermItem.pos())
            #TODO: Check all the linkages ()
            if self.EdgeEnd == "start":
                edge.setStart(self.oldTermItem)
            else:  #end
                edge.setEnd(self.oldTermItem)

        self.cBox = None

    def clearEdgeOnly(self, edge):
        """ Remove the controlboxes from an edge and deselect."""
        #self.clearSelection()
        #For edges, was there only one selected? Clear.
        if edge.scB:
            edge.setZValue(0) #below nodes
            self.removeItem(edge.scB)
            edge.scB = None
        if edge.ecB:
            #TODO: edge -> scene 'loop'
            self.removeItem(edge.ecB)
            edge.ecB = None
        edge.isOnlySelected = None

    def mousePressEvent(self, mouseEvent):
        mPos = mouseEvent.scenePos()
        #print(f"Press {self.mouseMode =}")
        if (mouseEvent.button() == Qt.MouseButton.LeftButton):

            if self.mouseMode == self.INSERTNODE:
                self.clearSelection()
                #For edges, was there only one selected? Clear.
                if self.onlySelected:
                    self.clearEdgeOnly(self.onlySelected)

                #Items sizes should be relative to (0,0)
                mPos = mouseEvent.scenePos()
                #print(f"Insert node: {mPos =}, \n{mouseEvent =}")
                #VisNodeItem adds to the model and the  list
                item = VisNodeItem(mPos, self.model,self.listWidget)
                item.setPos(mPos)
                #Add to *Scene*
                self.addItem(item)

                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)

                #TODO: Should this be actionPointer, to update the toolbar, etc
                self.mouseMode = self.POINTER
                #TODO: Don't let Qt add a newly created item to the selection
                return
                
            elif self.mouseMode == self.INSERTEDGE:
                #print("Ins edge")
                self.clearSelection()
                #For edges, was there only one selected? Clear.
                if self.onlySelected:
                    self.clearEdgeOnly(self.onlySelected)

                itm = self.pickItemAt(mouseEvent,QSizeF(10,10),[ROLE_NODE]) #,ROLE_EDGE
                #print(f"{self.mouseMode =}")
                if itm:
                    self.tmpEdgeSt = itm
                    self.startRubberLine(mPos)
                else: #Miss
                    self.tmpEdgeSt = None

            #*This* click means END the rubberBanding, create the edge 
            elif self.mouseMode == self.INSERTEDGE2CLICK: 
                itm = self.pickItemAt(mouseEvent,QSizeF(10,10),[ROLE_NODE]) #,ROLE_EDGE
                if itm:
                    self.tmpEdgeEnd = itm 
                    self.endPoint = mPos
                    self.endRubberLine()
                self.resetRubberLine()
                self.mouseMode = self.POINTER
                return
    
            elif self.mouseMode == self.POINTER:
                # SCENE based selection - as much as possible is handled at the Qt Item level
                
                # Handle moving the end selected edge (rerouting)
                #Note: this design requires selecting, then moving on the next click

                #Only do this if we have exactly 1 edge selected
                #A click means start a new selection

                #TODO: Once pickItemAt() uses mPos, not the whole event, use it
                #selItem = self.pickItemAt(mouseEvent,HITSIZE,[ROLE_EDGE,ROLE_NODE])
                selItem = self.itemAt(mPos,self.views()[0].transform())

                if not selItem: #Nothing selected, clear
                    self.clearSelection()
                    #For edges, was there only one selected? Clear.
                    if self.onlySelected:
                        self.clearEdgeOnly(self.onlySelected) #onlySelected.isOnlySelected = False
                        self.onlySelected = None                    

                #Minor hack - leaves cB's until end of drag
                if selItem and selItem.data(KEY_ROLE) == ROLE_NODE:
                    if self.onlySelected: #Clear cBs
                        self.clearEdgeOnly(self.onlySelected)
                    #immediately hand off
                    super().mousePressEvent(mouseEvent)
                    return

                #clear cB  unless edge or cb, which we handle here #Is this not selecting a Node?
                #different edge selected
                clickedCB:bool = selItem and selItem.data(KEY_ROLE) == ROLE_CB 
                clickedDifferentEdge:bool = selItem and selItem.data(KEY_ROLE) == ROLE_EDGE and selItem != self.onlySelected                
                if not clickedCB and clickedDifferentEdge:
                    self.clearSelection()
                    #For edges, was there only one selected? Clear.
                    if self.onlySelected:
                        self.clearEdgeOnly(self.onlySelected)

                if selItem:
                    selItem.setSelected(True)
                selected_items = self.selectedItems()
                #len is 0 or 1
                #exactly 1 edge selected
                if len(selected_items) == 1 and selItem.data(KEY_ROLE) == ROLE_EDGE:
                    self.clearEdgeOnly(selItem)
                    item = selected_items[0]

                    if item.data(KEY_ROLE) == ROLE_EDGE:
                        item.isOnlySelected = True
                        #Let the scene remember, for unsetting
                        self.onlySelected = item
                        if not item.scB:
                            item.setZValue(2000) #above nodes
                            item.scB = controlBox(item.startNode.pos(), item)
                        if not item.ecB:
                            item.ecB = controlBox(item.endNode.pos(), item)  

                #Handle the connectionBox
                if selItem and selItem.data(KEY_ROLE) == ROLE_CB:
                    mouseEvent.accept()
                    self.mouseMode = self.MOVEEDGEEND
                    #Draw control boxes at either end, start move
                    self.startMovingEdgeEnd(selItem.parentItem(), selItem)
                    return #event handled

        if (mouseEvent.button() == Qt.MouseButton.RightButton):
            selItem = self.itemAt(mPos,self.views()[0].transform())
            if selItem:
                print(f"\n******************\nRC {selItem = }")
                if selItem.parentItem():
                    #TODO: Why does this remove selItem from the scene???
                    print(f"RC {selItem.parentItem() = }")
            else:
                # print everything
                MainWindow.action_DebugPrint(MainWin)

        #pass on
        super().mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        mPos = mouseEvent.scenePos()
        #print(f"M: {self.mouseMode} ",end="",flush=True)
        
        #Handle hovering

        if self.mouseMode == self.INSERTNODE:
            #print("moving at :",mouseEvent.scenePos())
            #print("n" , end ="")
            pass
        elif self.mouseMode == self.INSERTEDGE or self.mouseMode == self.INSERTEDGE2CLICK:
            #print("Ins edge move")
            #Rubber band the edge
            #print(f">",end="")
            if self.tmpEdgeSt:
                self.stretchRubberLine(mPos)
                mouseEvent.accept()
                #return #handled - don't show a select rectangle.
            
        elif self.mouseMode == self.POINTER:
            #Mostly handled by Qt
            #print("p" , end ="")
            pass
        elif self.mouseMode == self.MOVEEDGEEND:
            self.MoveEdgeEnd(self.onlySelected,mPos)
            mouseEvent.accept()
            #return #no rubberband -?? doesn't work?
        super().mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        mPos = mouseEvent.scenePos()
        #print(f"release {self.mouseMode =}")
        if self.mouseMode == self.INSERTNODE:
            #print("Node release at :",mouseEvent.scenePos())
            #print("up node")
            #TODO: Clear selection after adding a node (or before?)
            self.clearSelection()
            return # Or use the eventHandled method?
            
        elif self.mouseMode == self.INSERTEDGE:
            #print("up edge")
            #CreateEdge code 
            #TODO: Put this in its own function
            if self.tmpEdgeSt:
                itm = self.pickItemAt(mouseEvent,QSizeF(10,10),[ROLE_NODE]) # add ,ROLE_EDGE to the list for multigraphs
                if itm:
                    #For now, disallow self edges/ loops
                    if self.tmpEdgeSt != itm:
                        self.tmpEdgeEnd = itm 
                        self.endPoint = mPos
                        self.endRubberLine()

                #Clean up
                self.resetRubberLine()
                #Force a redraw
                self.update()
            self.mouseMode = self.POINTER
            self.clearSelection()
            #done processing - bail
            return

        elif self.mouseMode == self.POINTER:
            #print("up select at", mouseEvent.scenePos())
            pass
            #MainWindow.actionSceneSelectChange(MainWindow.Scene)
        elif self.mouseMode == self.MOVEEDGEEND:
            self.finishMovingEdgeEnd(self.onlySelected, mPos,mouseEvent)
            self.mouseMode = self.POINTER
            return
        super().mouseReleaseEvent(mouseEvent)  

    def WheelEvent(self, event):
        #print("wheelevent")
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
        if event.delta().y() > 0:
            self.scale(zoomInFactor, zoomInFactor)
        else:
            self.scale(zoomOutFactor, zoomOutFactor)

    def findItemByIdx(self,idx):
        """takes a ROLE_INDEX value, and return the item out, or none """
        for item in self.items():
            if item.data(KEY_INDEX) == idx:
                return item
        return None

    def deleteItemAndChildren(self,item):
        #TODO: Refactor to change name, removing 'AndChildren'
        item.suppressItemChange = True
        # Remove from scene
        #if its an edge, tell the nodes ends that the edge is gone
        if item.data(KEY_ROLE) == ROLE_EDGE:
            item.startNode.startsEdges.remove(item)
            #print(f"{item.endNode = }") #eItem
            item.endNode.endsEdges.remove(item)
            #print(f"{item.endNode.endsEdges =}")
        #print(f"{item =}")  
        #logging.debug("delItem&chld scene items, BEFORE remove")
        #for i in self.items():
        #    logging.debug(f"{i =}")        
        
        # Register a finalize callback to confirm deletion
        weakref.finalize(item, self._on_finalize, repr(item))

        self.removeItem(item)
        #logging.debug("delItem&chld scene items, AFTER remove")
        #for i in self.items():
        #    logging.debug(f"{i =}")
        #Item now belongs to Scene, del from memory
        #forcing the del will crash sooner. Otherwise, crashes on GC?
        del item

    def update(self):
        #print("scene updating")
        #logging.debug("Scene updating")
        super().update()

    #Part of tracking down the ghost lines - gc takes a while. forced gc crashes the whole thing.
    # Living with the ghost lines for now :/
    @staticmethod
    def _on_finalize(item_repr):
        print(f"[Finalize] {item_repr} has been garbage collected.")


def debug_qgraphicsitem_refs():
    """ coPilot code to track gc issues. """
    #import gc
    print("debug_qgraphicsitem_refs()")
    gc.collect()
    print(f"gc stats {gc.get_stats()}")
    for obj in gc.get_objects():
        if isinstance(obj, QGraphicsItem):
            print("Alive QGraphicsItem:", obj)
            refs = gc.get_referrers(obj)
            print(f"There are {refs =} referrers")
            #print("  Referrers:")
            #for ref in refs:
            #    print("   ", ref)

######
# "monkey patch" QListWidget to create data() sorted lists
# can't properly extend QListWidget 'cos it's setup in the .ui file
# Courtesy of chatGPT

# Store original addItem method
_original_addItem = QListWidget.addItem

# Add sort_roles attribute to QListWidget instances
def _addItem_with_sort(self, item):
    _original_addItem(self, item)
    roles = getattr(self, "_sort_roles", None)
    if roles:
        _resort_items(self, roles)

def _resort_items(widget, roles):
    items = []
    while widget.count():
        items.append(widget.takeItem(0))
    #TODO: Make sort by name an option
    items.sort(key=lambda item: tuple(item.data(role) for role in roles))
    for item in items:
        _original_addItem(widget, item)

def set_sort_roles(self, roles):
    self._sort_roles = roles
    _resort_items(self, roles)
# Patch methods into QListWidget
QListWidget.addItem = _addItem_with_sort
QListWidget.setSortRoles = set_sort_roles

def findItemByIdx(self,idx):
    """another patch to LWid
      feed in a ROLE_INDEX value, and get the item out, or none """
    for row in range(self.count()):
        item = self.item(row)
        if item.data(KEY_INDEX) == idx:
            return item
    return None
QListWidget.findItemByIdx = findItemByIdx

def findItemRowByIdx(self,idx):
    """another patch to LWid
      feed in a ROLE_INDEX value, and get the item out, or none """
    for row in range(self.count()):
        item = self.item(row)
        if item.data(KEY_INDEX) == idx:
            return row
    return None
QListWidget.findItemRowByIdx = findItemRowByIdx


#end monkeypatch    


#Some global helper functions
class CodeExecDialog(QDialog):
    """Let the user run arbitrary Python code against the model """
    def __init__(self, parent=None, scene=None):
        super().__init__(parent)
        self.setWindowTitle("Python Code Executor - Experimenal - does not save!")
        self.resize(600, 400)
        self.setModal(False) 

        self.scene = scene  # Reference to the MainWindow's scene

        # Layouts
        mainLayout = QVBoxLayout()
        inputLabel = QLabel("Python Code ('S' is scene, 'M' is model, 'G' is Graph):")
        self.codeEdit = QTextEdit()
        self.codeEdit.setText("#Examples - No. of Scene items: \nresult = str(len(S.items()))\n" +
                                "#Directed or not:\nresult += f'\\n{M.isDigraph == False =}\\n' \n" +
                                "#Graph Model contents:\nresult += f'{M.getModelItems() =}\\n' \n"+
                                "#Abstract Graph G:\nresult += f'{G =}'")

        outputLabel = QLabel("Output:")
        self.outputEdit = QTextEdit()
        self.outputEdit.setReadOnly(True)

        buttonLayout = QHBoxLayout()
        runButton = QPushButton("Run")
        closeButton = QPushButton("Close")
        buttonLayout.addWidget(runButton)
        buttonLayout.addWidget(closeButton)

        mainLayout.addWidget(inputLabel)
        mainLayout.addWidget(self.codeEdit)
        mainLayout.addWidget(outputLabel)
        mainLayout.addWidget(self.outputEdit)
        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)

        # Connections
        runButton.clicked.connect(self.runCode)
        closeButton.clicked.connect(self.close)

    def runCode(self):
        """
        Execute the code entered in the text box.
        """
        code = self.codeEdit.toPlainText()
        output = ""

        # Prepare the local context
        localContext = {"S": self.scene, "G":self.scene.model.Gr, "M":self.scene.model}

        try:
            # Execute code
            exec(code, {}, localContext)

            # If they defined 'result', show it
            if "result" in localContext:
                output = str(localContext["result"])
            else:
                output = "Code executed successfully. (No 'result' defined.)"
        except Exception:
            output = "Exception:\n" + traceback.format_exc()

        self.outputEdit.setPlainText(output)


def zoomToFitWithMargin(view, margin=0.25):
    """ chatGpt. Pass in a QGraphicsView and a margin multiplier  """
    # Get bounding rect of all items
    sceneRect = view.scene().itemsBoundingRect()

    if sceneRect.isNull():
        # Nothing to fit
        return

    # Inflate by 25% on each side
    marginX = sceneRect.width() * margin
    marginY = sceneRect.height() * margin
    sceneRect.adjust(-marginX, -marginY, marginX, marginY)

    # Compute the transform to fit the rect
    viewportRect = view.viewport().rect()
    if viewportRect.isEmpty():
        return

    # Calculate scale factors
    xScale = viewportRect.width() / sceneRect.width()
    yScale = viewportRect.height() / sceneRect.height()
    scale = min(xScale, yScale)

    # Limit scaling to 100% max
    scale = min(scale, 1.0)

    # Build the target transform manually
    transform = QTransform()
    transform.translate(view.viewport().width() / 2, view.viewport().height() / 2)
    transform.scale(scale, scale)
    transform.translate(-sceneRect.center().x(), -sceneRect.center().y())

    view.setTransform(transform)


def paintItemAndChildren(item, painter):
    """
    chatGPT: Paint the item and all its children recursively.
    """
    # Default style option
    option = QStyleOptionGraphicsItem()

    # Save painter state
    painter.save()

    # Apply the item's transform
    painter.setTransform(item.sceneTransform(), combine=False)

    # Paint the item itself
    item.paint(painter, option, widget=None)

    # Paint the children
    for child in item.childItems():
        #print(child)
        paintItemAndChildren(child, painter)

    painter.restore()


basedir = os.path.dirname(__file__)

try:
    from ctypes import windll  # Only exists on Windows.
    myappid = "za.co.isijingi.qtpyGraphEdit.v00"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        #TODO: Put in the `isWindowModified()` code
        self.setWindowTitle(APP_NAME +"[*]")
        self.fileName = ""

        #Where the data lives
        self.model = graphModel()

        #Display List
        #self.ui.listWidget.setModel(self.model)
        #setup the list to sort by TYPE then ID (using patched function above)
        self.ui.listWidget.setSortRoles( (KEY_ROLE,KEY_INDEX) )
        self.ui.listWidget.itemChanged.connect(self.updateSceneText)
        self.ui.listWidget.itemClicked.connect(self.listClick)
        self.ui.listWidget.itemDoubleClicked.connect(self.listDblClicked)

        #Setup the graphicsView, linking model,scene and list
        self.Scene = grScene(self.model,self.ui.listWidget)
        self.Scene.selectionChanged.connect(self.actionSceneSelectChange(self.Scene))
        
        self.ui.graphicsView.setScene(self.Scene)
        self.ui.graphicsView.setRenderHint(QPainter.Antialiasing)
        self.ui.graphicsView.setDragMode(QGraphicsView.RubberBandDrag)
        self.ui.graphicsView.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.ui.graphicsView.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        # Create a status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Create a slider
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(10)     # 10%
        self.zoom_slider.setMaximum(400)    # 400%
        self.zoom_slider.setValue(100)      # Start at 100%
        self.zoom_slider.setTickInterval(10)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)

        # Label to show current zoom
        self.zoom_label = QLabel("Zoom: 100%")

        # Add slider and label to the status bar
        status_bar.addPermanentWidget(self.zoom_label)
        status_bar.addPermanentWidget(self.zoom_slider)

        # Connect the slider to the zoom handler
        self.zoom_slider.valueChanged.connect(self.setZoom)

        #deal with deletions not updating - doesn't help - issue is with object persistence
        #self.ui.graphicsView.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        #link UI to local code
        #Graph Tool bar tools
        self.ui.actionNewNode.triggered.connect(self.actionNewNode)
        self.ui.actionNewEdge.triggered.connect(self.actionNewEdge)
        self.ui.actionPointer.triggered.connect(self.actionPointer)

        #File
        self.ui.action_New.triggered.connect(self.action_FileNew)
        self.ui.action_Open.triggered.connect(self.action_FileOpen)
        self.ui.actionSave.triggered.connect(self.action_FileSave)
        self.ui.actionSave_As.triggered.connect(self.action_FileSaveAs)
        self.ui.actionClose.triggered.connect(self.action_FileClose)
        self.ui.actionExport.triggered.connect(self.action_FileExport)

        self.ui.actionPrint.triggered.connect(self.action_Print)
        #Edit
        self.ui.actionCopy.triggered.connect(self.action_EditCopy)
        self.ui.actionCut.triggered.connect(self.action_EditCut)
        self.ui.actionPaste.triggered.connect(self.action_EditPaste)
        self.ui.action_Delete.triggered.connect(self.action_EditDelete)
        self.ui.actionSelect_All.triggered.connect(self.action_EditSelectAll)
        self.ui.actionSelect_None.triggered.connect(self.action_EditSelectNone)
        self.ui.actionZoomIn.triggered.connect(self.action_EditZoomIn)
        self.ui.actionZoomOut.triggered.connect(self.action_EditZoomOut)

        #Tools & other 
        self.execCodeAction = QAction("Run Python Code", self)
        self.execCodeAction.triggered.connect(self.showCodeDialog)
        self.ui.menuTools.addAction(self.execCodeAction)

        #Help
        self.ui.action_About.triggered.connect(self.action_HelpAbout)
        self.ui.action_Credits.triggered.connect(self.action_HelpCredits)

    #GraphicsView/ scene handling
    def setZoom(self, value):
        """
        chatGPT
        Slot to set the zoom level of the QGraphicsView.
        """
        scale = value / 100.0  # Convert to 0.1 - 4.0
        self.ui.graphicsView.resetTransform()          # Reset any existing zoom
        self.ui.graphicsView.scale(scale, scale)       # Apply new zoom
        self.zoom_label.setText(f"Zoom: {value}%")

    #Action Code

    def showCodeDialog(self):
        #store self.codeDialog as an attribute to prevent it from being garbage-collected 
        self.codeDialog  = CodeExecDialog(self, scene=self.Scene)
        self.codeDialog.show()

    #Graph actions from the toolbar

    def actionNewNode(self):
        #Set the mouseMode to node
        self.Scene.mouseMode = grScene.INSERTNODE
        #self.actionPointer.setChecked(False)
        self.statusBar().showMessage("Insert Node",3000)

        """
        #TODO: Use this to properly set/ unset the toolbar buttons
        from DiagramScene:
        @Slot(QGraphicsPolygonItem)
        def item_inserted(self, item):
            print(f"Item inserted {item}")
            self._pointer_type_group.button(DiagramScene.MoveItem).setChecked(True)
            self.scene.set_mode(self._pointer_type_group.checkedId())
            self._button_group.button(item.diagram_type).setChecked(False)
        """

    def actionNewEdge(self):
        self.statusBar().showMessage("Insert Edge",3000)
        #print("Add an edge")
        self.Scene.mouseMode = grScene.INSERTEDGE

    def actionPointer(self):
        self.statusBar().showMessage("Select Mode",3000)
        self.Scene.mouseMode = grScene.POINTER

    def listClick(self,item):
        #print(f"listClick {item} , {item.text()}")
        #clear the selection
        self.Scene.clearSelection()
        #select the *graphics* view of the clicked item as well
        idx = item.data(KEY_INDEX)
        for sItem in self.Scene.items():
            if sItem.data(KEY_ROLE) in [ROLE_NODE, ROLE_EDGE]:
                if sItem.data(KEY_INDEX) == idx: # iNum:
                    sItem.setSelected(True)
                    #print(idx)
                    #break

    def listDblClicked(self,item):
        #print("listDblClicked", item.text(), item.index())
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.ui.listWidget.editItem(item)
        #print(f"Editing {item.text() =}, id = {item.data(KEY_INDEX)}")
        self.updateSceneText(item)

    def updateSceneText(self,item):
        """ Code for the listWidget to tell the scene that something has changed (name)"""
        #Maybe should be updateMODELText - scene updates via the model?

        #print("Update scene text")
        #print(f"updateSceneText id = {item.data(KEY_INDEX)} {item.text()}::{item.data(KEY_ROLE)}")

        iNum = item.data(KEY_INDEX)
        #print(f"{item.text()}::{item.data(KEY_INDEX)}>{item.data(KEY_ROLE)} {iNum =}")
        new_text = item.text()
        self.model.item(iNum).setText(new_text)
        #TODO: The list update should trigger some change flag/ be embedded 
        if item.data(KEY_ROLE) == ROLE_NODE:
            self.model.Gr.nodeD[iNum].metadata.update({'name':new_text})
        elif item.data(KEY_ROLE) == ROLE_EDGE:
            self.model.Gr.edgeD[iNum].metadata.update({'name':new_text})
        #Update of added attrib in the scene
        #TODO: Make this dataChanged.emit() work 
        #Find the index of the visEdge
        for sItem in self.Scene.items():
            if sItem.data(KEY_INDEX) == iNum:
                #TODO: How to get an index to pass?
                #sIDX = sItem.index()
                #Just call it directly, with a dummy change item
                sItem.itemChange(QGraphicsItem.GraphicsItemChange.ItemToolTipChange,0)
            #self.model.dataChanged.emit(sIDX, sIDX)

        self.Scene.update()
        self.ui.listWidget.repaint()

    def actionSceneSelectChange(self, scene):

        selected_items = scene.selectedItems()
        if selected_items:
            print("Selected items:")
            for item in selected_items:
                print("  ", item)
        #else:
        #    print("No items selected.")

    #Menu-like Actions
    def action_FileNew(self):
        #print("FileNew")
        #Tidy up where we are
        self.Scene.clearSelection()
        self.Scene.isOnlySelected = None
        
        #clear window vars
        self.setWindowTitle(APP_NAME +"[*]")
        self.fileName = ""

        #clear model
        self.model.clear()
        #clear ListW
        self.ui.listWidget.clear()
        #Clear Scene
        #TODO: Reset the temp vars for odd reloads
        # eg self.onlySelected
        self.Scene.clear()

    def action_FileOpen(self):
        #print("File Open")
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, 
            "Load File", dir="", filter ="graphml files(*.graphml);;All Files(*)", options = options)
        if fileName:  #dialog returns '' on <esc>
            #Clear the current graph
            self.action_FileNew()

            self.fileName = fileName
            #print(self.fileName)
            yGr = yEd.Graph()
            yGr = yGr.from_existing_graph(self.fileName)
            #Keep a dictionary of yGr id's <-> KEY_INDEX
            yGrID2Item = {}
            #print(f"{yGr.nodes = }\n{yGr.edges = }")
            # Read and set the Graph Digraph status
            self.model.isDigraph = yGr.directed == 'directed'

            #Add the nodes
            for yKey,yNode in yGr.nodes.items():
                #print(f"{yKey =}, {yNode.name =}, {yNode.geom["x"]=}, {yNode.geom["y"]=}")
                nPos = QPointF(float(yNode.geom["x"]),float(yNode.geom["y"]))
                #TODO: Read the additional items (URL, Description, Resources? custom_properties don't seem to be implemented)
                #Create and link in the Qt item:
                GItem = VisNodeItem(nPos, self.model,self.ui.listWidget,nameP=yNode.name.strip())
                yGrID2Item[yKey] = GItem.nodeNum
                self.Scene.addItem(GItem)
                GItem.setFlag(QGraphicsItem.ItemIsSelectable, True)
                GItem.setFlag(QGraphicsItem.ItemIsMovable, True)                

            #Add the edges
            for yKey,yEdge in yGr.edges.items():
                #print(f"{yKey = } {yEdge.node1.id =}, {yEdge.node2.id =} {yEdge.name =}")
                sNodeID = yGrID2Item[yEdge.node1.id.strip()]
                eNodeID = yGrID2Item[yEdge.node2.id.strip()]
                #print(f"{sNodeID =}, {eNodeID =}")
                sItem = self.Scene.findItemByIdx(sNodeID)
                eItem = self.Scene.findItemByIdx(eNodeID)
                edgeItem = VisEdgeItem(self.model,self.ui.listWidget,sItem, eItem, parent=None, nameP=yEdge.name)
                #Add to *Scene*
                self.Scene.addItem(edgeItem)
                edgeItem.setFlag(QGraphicsItem.ItemIsSelectable, True)
                edgeItem.setFlag(QGraphicsItem.ItemIsMovable, False)

            self.setWindowTitle(str(os.path.basename(self.fileName)) + " " + APP_NAME + "[*]")

            self.setZoom(100)
            zoomToFitWithMargin(self.ui.graphicsView, margin=0.2)
            
    def action_FileSave(self):
        #print("File Save")  
        if self.fileName:
            #NOTE: This code is basically duplicated in action_EditCopy, with changes to suit the clipboard.
            #Create the saveable yEd form of the graph
            yGr = yEd.Graph()

            #Include saving self.model.isDigraph
            #TODO: Consider adding a directed flag to the abstract Graph class's edges?
            if self.model.isDigraph:
                yGr.directed = 'directed'
            else:
                yGr.directed = 'undirected' #yEd semantics are a little different - each edge holds directed info.

            #track the yEd nodes and edges, since it runs its own IDs, and ID can't be overridden
            yGrNodes = {}
            yGrEdges = {}
            #nodes
            #TODO: Extend this to work for multiple scenes. yED will need work too
            #  useful for tabbed models later. (where each scene will be a subset of model)
            for sItem in self.Scene.items():
                if sItem.data(KEY_ROLE) == ROLE_NODE:
                    iID = sItem.data(KEY_INDEX)
                    iName = self.model.itemName(sItem)
                    iPosX = sItem.pos().x()
                    iPosY = sItem.pos().y()
                    #yGrNodes[iID] = yGr.add_node(id=str(iID),name=iName,x=str(iPosX),y=str(iPosY))
                    yGrNodes[iID] = yGr.add_node(name=iName,x=str(iPosX),y=str(iPosY))
            #edges
            for sItem in self.Scene.items():
                #print(sItem.data(KEY_INDEX),sItem.data(KEY_ROLE))
                if sItem.data(KEY_ROLE) == ROLE_EDGE:
                    #print(sItem)
                    iName = self.model.itemName(sItem)
                    #Get the s/e ID's.
                    startItem = yGrNodes[sItem.startNode.data(KEY_INDEX)]
                    endItem = yGrNodes[sItem.endNode.data(KEY_INDEX)]
                    #TODO: When we get to hyperedges,we'll need a dict for those too
                    #Note - yEdfile is ignoring this ID
                    yGr.add_edge(node1=startItem, node2=endItem, name=iName)
                    #yGr.add_edge(node1=startItem, node2=endItem)

            #print(f"{yGr.nodes =}\n{yGr.edges =}")
            #TODO: wrap this in a try
            yGr.persist_graph(self.fileName,overwrite=True)   
            #TODO: Clear the isModified flag  
            self.setWindowTitle(str(os.path.basename(self.fileName)) + " " + APP_NAME + "[*]")
        else:
            self.action_FileSaveAs()

    def action_FileSaveAs(self):
        #print("File SaveAs")  
        #TODO: Implement isWindowModified()
        #if not self.isWindowModified():
        #    return

        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self, 
            "Save File", dir=self.fileName, filter ="graphml files(*.graphml);;All Files(*)", options = options)
        if fileName:  #dialog returns '' on <esc>
            self.fileName = fileName
            self.action_FileSave()
                 
    def action_FileClose(self):
        print("File Close")  

    def action_Print(self):
        """
        chatGPT. Slot to print the entire QGraphicsScene.
        """
        printer = QPrinter(QPrinter.ScreenResolution)# HighResolution) 

        # Show print dialog
        printDialog = QPrintDialog(printer, self)
        if printDialog.exec() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            
            # Get the full scene rectangle
            sceneRect = self.Scene.sceneRect()
            #print(f"{sceneRect =}")

            # Compute scale to fit scene onto the page
            #TODO: Apply a human brain to this scaling - this gives weird results.
            pageRect = printer.pageRect(QPrinter.DevicePixel).toRect()
            #print(f"{pageRect =}")
            xScale = pageRect.width() / sceneRect.width()
            yScale = pageRect.height() / sceneRect.height()
            scale = min(xScale, yScale)
            #print(f"{scale =}")
            scale = scale/5 #needs tweaking

            # Center the scene on the page
            xOffset = (pageRect.width() - sceneRect.width() * scale) / 2
            yOffset = (pageRect.height() - sceneRect.height() * scale) / 2

            painter.translate(xOffset, yOffset)
            painter.scale(scale, scale)
        
            # Render the scene
            self.Scene.render(painter)

            painter.end()

    def action_DebugPrint(self):
            print("core Graph Model\n",self.model.Gr)
            print("model items \n",self.model.getModelItems())
            #print(f"{self.model =}")
            print("\nListView items:\n",
               "\n".join([self.ui.listWidget.item(x).text()+ \
                " ID:"+str(self.ui.listWidget.item(x).data(KEY_INDEX))+ \
                " type:"+str(self.ui.listWidget.item(x).data(KEY_ROLE)) \
                    for x in range(self.ui.listWidget.count())]))
            #graphics View ~= scene
            print("\nui.graphicsView items:\n","\n   ".join([str(itm) \
                for itm in self.ui.graphicsView.items()]))
            
            lstr = "core Graph Model\n"+ str(self.model.Gr)
            lstr += f"model items {self.model.getModelItems()} \n"
            lstr += "\nListView items:\n"
            lstr += "\n".join([self.ui.listWidget.item(x).text()+ " ID:"+str(self.ui.listWidget.item(x).data(KEY_INDEX))+ \
                " type:"+str(self.ui.listWidget.item(x).data(KEY_ROLE)) for x in range(self.ui.listWidget.count())])
            lstr += "\nui.graphicsView items:\n"
            lstr += "\n   ".join([str(itm) for itm in self.ui.graphicsView.items()])
            #logging.debug(lstr)

    def action_FileExport(self):
        # Fold this into FileSaveAs??
        #chatGPT code
        #print("File Export") 
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save SVG File",
            "",
            "Scalable Vector Graphics (*.svg)"
        )

        if not filePath:
            return  # User cancelled

        # Create SVG generator
        generator = QSvgGenerator()
        generator.setFileName(filePath)
        #TODO: bounding box still not snug, but workable.
        generator.setSize(self.Scene.sceneRect().size().toSize())  #itemsBoundingRect().size().toSize())

        #TODO: Why is there a lot of white space at the top left?
        generator.setTitle("(hi)graph V00Export")
        #generator.setDescription("An SVG export.")

        # Paint the scene into the generator
        painter = QPainter(generator)
        self.Scene.render(painter)
        painter.end()

    def action_EditCopy(self):
        """ chatGPT"""
        #print("Edit>Copy")
        selectedItems = self.Scene.selectedItems()
        if not selectedItems:
            return

        mimeData = QMimeData()

        #Simple Model Text
        ##################

        plainText = ""
        for sItem in selectedItems:
            if sItem.data(KEY_ROLE) == ROLE_NODE:
                plainText += str(self.model.Gr.nodeD[sItem.data(KEY_INDEX)])
            if sItem.data(KEY_ROLE) == ROLE_EDGE:
                plainText += str(self.model.Gr.edgeD[sItem.data(KEY_INDEX)])
        mimeData.setText(plainText)

        #graphml - pastable format
        #########################

        # Code copied from action_FileOpen. Use that as the "master" copy.
        #Positions only updated on PASTE

        yGr = yEd.Graph()

        #track the yEd nodes and edges, since it runs its own IDs, and ID can't be overridden
        yGrNodes = {}
        yGrEdges = {}
        #nodes
        for sItem in selectedItems: #self.Scene.items():
            if sItem.data(KEY_ROLE) == ROLE_NODE:
                iID = sItem.data(KEY_INDEX)
                iName = self.model.itemName(sItem)
                iPosX = sItem.pos().x()
                iPosY = sItem.pos().y()
                yGrNodes[iID] = yGr.add_node(name=iName,x=str(iPosX),y=str(iPosY))
        #edges
        for sItem in selectedItems: #self.Scene.items():
            #print(sItem.data(KEY_INDEX),sItem.data(KEY_ROLE))
            if sItem.data(KEY_ROLE) == ROLE_EDGE:
                #print(sItem)
                iName = self.model.itemName(sItem)
                #Get the s/e ID's.
                #Check that all end nodes are copied as well, even if not selected
                if sItem.startNode.data(KEY_INDEX) not in yGrNodes:
                    #Force the node in
                    nItem = sItem.startNode
                    iID = nItem.data(KEY_INDEX)
                    iName = self.model.itemName(nItem)
                    iPosX = nItem.pos().x()
                    iPosY = nItem.pos().y()
                    yGrNodes[iID] = yGr.add_node(name=iName,x=str(iPosX),y=str(iPosY))
                startItem = yGrNodes[sItem.startNode.data(KEY_INDEX)]
                
                if sItem.endNode.data(KEY_INDEX) not in yGrNodes:
                    #Force the node in
                    nItem = sItem.endNode
                    iID = nItem.data(KEY_INDEX)
                    iName = self.model.itemName(nItem)
                    iPosX = nItem.pos().x()
                    iPosY = nItem.pos().y()
                    yGrNodes[iID] = yGr.add_node(name=iName,x=str(iPosX),y=str(iPosY))
                endItem = yGrNodes[sItem.endNode.data(KEY_INDEX)]
                #TODO: When we get to hyperedges,we'll need a dict for those too
                yGr.add_edge(node1=startItem, node2=endItem, name=iName)

        #yGr now has the selected items - stringify, and paste
        graphmlData = yGr.stringify_graph()
        mimeData.setData("application/xml", graphmlData.encode("utf-8"))

        # Extract the yEdString->Graph code, and put in Edit>Paste(needing mods for new nodes)

        #Bitmap
        #######

        # Compute the bounding rect of all selected items
        boundingRect = selectedItems[0].sceneBoundingRect()
        for item in selectedItems[1:]:
            boundingRect = boundingRect.united(item.sceneBoundingRect())

        # Align to integers
        boundingRect = boundingRect.toAlignedRect()

        # Create the image
        image = QImage(boundingRect.size(), QImage.Format.Format_RGB16)
        image.fill(Qt.white)

        #Deselect to show in black, not blue!
        if len(selectedItems) == 1 and selectedItems[0].data(KEY_ROLE) == ROLE_EDGE:
            self.Scene.clearEdgeOnly(selectedItems[0])
        self.Scene.clearSelection()

        # Render the selected items
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)

        # Translate so that boundingRect.topLeft() is (0,0)
        #Only use this when calling item.paint(), not with Scene.render()
        #painter.translate(-boundingRect.topLeft())

        # Draw only selected items
        #"""
        # Temp - chop off at bounding rect
        self.Scene.render(painter, target=QRectF(), source=boundingRect) # item.sceneBoundingRect())
        #"""

        # Paint only the selected items (and the children of compound items)
        """
        painter.setPen(Qt.black)
        option = QStyleOptionGraphicsItem()
        #TODO: Get children items of NDOES to properly translate. 
        # This may be a deeper issue with structure of the objects
        painter.translate(-boundingRect.topLeft())
        for item in selectedItems:
            print(f"{item.data(KEY_INDEX) =} {item.pos() =}")
            #paintItemAndChildren(item,painter)
            item.paint(painter, option)
            
            for child in item.childItems():
                print(f"{child =}")
                painter.save()
                #Works for edges, not nodes:
                painter.translate(item.scenePos())
                painter.setTransform(child.sceneTransform(), True)
                
                child.paint(painter,option,widget=None)
                painter.restore()
        """

        """
        #Plan c: use a tempScene - this crashed everythong
        tempScene = QGraphicsScene()
        tempScene.setSceneRect(boundingRect)
        #clones = selectedItems  #copy.deepcopy(selectedItems) #VisNodeItem cannot be deepcopied :/
        for c in selectedItems:
            tempScene.addItem(c)
        tempScene.render(painter)
        """
        painter.end()

        #Reselect
        for item in selectedItems:
            item.setSelected(True)

        mimeData.setImageData(image)
        QGuiApplication.clipboard().setMimeData(mimeData)

        # Copy image to clipboard for MSFT :/ This gets hacky  (win32 calls)
        #TODO: figure out how to handle MSFT DIBs (Edit>CopyImage)
        #pixmap = QPixmap.fromImage(image)
        #QGuiApplication.clipboard().setPixmap(pixmap)

    def action_EditCut(self):
        print("Edit>Cut")

        #Edite->Copy
        #Delete selected?

    def action_EditPaste(self):
        #print("Edit>Paste")
        # Extract the yEdString->Graph code, and put in Edit>Paste(needing mods for new nodes)
        # The newly pasted items will be selected, to make them easy to move

        self.Scene.clearSelection()

        clipboard = QGuiApplication.clipboard()
        mimeData = clipboard.mimeData()

        # Check and extract XML if available
        if mimeData.hasFormat("application/xml"):
            xml_bytes = mimeData.data("application/xml")  # returns QByteArray
            xml_string = bytes(xml_bytes).decode("utf-8")
        else:
            return #Nothing readable on the clipboard

        #print(xml_string)
        #Now add the found items to the model. Based on File>Open
        yGrID2Item = {}
        yGr = yEd.Graph()
        yGr= yGr.from_XML_string(xml_string)
        for yKey,yNode in yGr.nodes.items():
            #print(f"{yKey =}, {yNode.name =}, {yNode.geom["x"]=}, {yNode.geom["y"]=}")
            nPos = QPointF(float(yNode.geom["x"]) + PASTE_OFFSET,float(yNode.geom["y"]) + PASTE_OFFSET)
            #TODO: Read the additional items (URL, Description, Resources? custom_properties don't seem to be implemented)
            #Create and link in the Qt item:
            GItem = VisNodeItem(nPos, self.model,self.ui.listWidget,nameP=yNode.name.strip())
            yGrID2Item[yKey] = GItem.nodeNum
            self.Scene.addItem(GItem)
            GItem.setFlag(QGraphicsItem.ItemIsSelectable, True)
            GItem.setFlag(QGraphicsItem.ItemIsMovable, True)  
            GItem.setSelected(True)  
        for yKey,yEdge in yGr.edges.items():
            #print(f"{yKey = } {yEdge.node1.id =}, {yEdge.node2.id =} {yEdge.name =}")
            sNodeID = yGrID2Item[yEdge.node1.id.strip()]
            eNodeID = yGrID2Item[yEdge.node2.id.strip()]
            #print(f"{sNodeID =}, {eNodeID =}")
            sItem = self.Scene.findItemByIdx(sNodeID)
            eItem = self.Scene.findItemByIdx(eNodeID)
            edgeItem = VisEdgeItem(self.model,self.ui.listWidget,sItem, eItem, parent=None, nameP=yEdge.name)
            #Add to *Scene*
            self.Scene.addItem(edgeItem)
            edgeItem.setFlag(QGraphicsItem.ItemIsSelectable, True)
            edgeItem.setFlag(QGraphicsItem.ItemIsMovable, False)
            GItem.setSelected(True)


        """
        #Debug helper
        selected_items = self.Scene.selectedItems()
        if selected_items:
            print("Selected items:")
            for item in selected_items:
                print("  ", item)
        else:
            print("No items selected.")
        """

    #Some helper functions for deletion

    def delEdge(self, delIdx):
        """ all the calls to delete an edge"""
        
        #delete from model
        ###
        self.model.delEdge(delIdx)
        #Delete from LWscene updat
        delRow = self.ui.listWidget.findItemRowByIdx(delIdx)
        delItem = self.ui.listWidget.takeItem(delRow)
        #del delItem
        #Delete from Scene
        delItem = self.Scene.findItemByIdx(delIdx)
        #remove CBs
        self.Scene.clearEdgeOnly(delItem)
        self.Scene.deleteItemAndChildren(delItem)

    def delNode(self, delIdx):
        """ all the calls to delete an node"""
        #Check for any edges attached
        #TODO: Pop a warning dialog when deleting the edges
        eList = self.model.edgesAtNode(self.Scene.findItemByIdx(delIdx))
        if eList:
            for e in eList:
                self.delEdge(e)
        #delete from model
        self.model.delNode(delIdx)
        #Delete from LW
        delRow = self.ui.listWidget.findItemRowByIdx(delIdx)
        delItem = self.ui.listWidget.takeItem(delRow)
        del delItem
        #Delete from Scene
        self.Scene.deleteItemAndChildren(self.Scene.findItemByIdx(delIdx))

    def action_EditDelete(self):
        #print("Edit>Delete")
        #Edge Delete (must delete edges 1st)
        selected_items = self.Scene.selectedItems()
        self.Scene.clearSelection()
        if selected_items:
            for item in selected_items:
                #print(self.model.itemName(item))
                if item.data(KEY_ROLE) == ROLE_EDGE:
                    delIdx = item.data(KEY_INDEX)
                    self.delEdge(delIdx)
            #Node delete - 1st del any connected edges - handled by GrScene
            for item in selected_items:
                if item.data(KEY_ROLE) == ROLE_NODE:
                    delIdx = item.data(KEY_INDEX)
                    self.delNode(delIdx)

        #logging.debug("about to update from action_EditDelete",stack_info=True  )
        #gc.collect() #This will crash the whole thing, with no traces
        #debug_qgraphicsitem_refs()  #More coPilot code ...

        #self.Scene.update()
        #Trying to get rid of the orphan lines - which go when the view changes so that scrollbars are added.
        self.Scene.invalidate(self.Scene.sceneRect(), QGraphicsScene.AllLayers)
        #GC takes some time (~100ms?) to finalise, so delay the repaint
        QTimer.singleShot(500, lambda: self.ui.graphicsView.viewport().repaint())
        #self.Scene.invalidate(self.Scene.sceneRect(), QGraphicsScene.AllLayers)
        self.ui.graphicsView.viewport().repaint()  #update()
        #self.Scene.invalidate()

    def action_EditSelectAll(self):
        #print("Edit>SelectAll")
        #TODO: For multiple scenes from 1 model, what to do? (select model, or scene?)
        #  Maybe select all needs to be context sensitive - scene, or list =model
        for item in self.Scene.items():
            if item.GraphicsItemFlag.ItemIsSelectable:
                item.setSelected(True)

    def action_EditSelectNone(self):
        #print("Edit>SelectNone")
        self.Scene.clearSelection()

    def action_EditZoomIn(self):
        #print("Edit>ZoomIn")
        pass

    def action_EditZoomOut(self):
        #print("Edit>ZoomOut")
        pass

    def action_HelpAbout(self):
        dlg = action_Aboutdlg(self)
        dlg.exec()

    def action_HelpCredits(self):
        dlg = action_CreditsDlg(self)
        dlg.exec()


#Dialogs called by mainwindow
class action_Aboutdlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.dlg = Ui_dlgAbout()
        self.dlg.setupUi(self)

class action_CreditsDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.uidlgCred = Ui_dlgCredits()
        self.uidlgCred.setupUi(self)

#--------------------------------------------
#import cProfile

if __name__ == "__main__":
    #print("="*100)
    #logger = logging.getLogger(__name__)
    #logging.basicConfig(filename='higraphDebug.log', 
    #                    encoding='utf-8', 
    #                    level=logging.DEBUG,
    #                    format='%(asctime)s %(message)s\nStk>%(stack_info)s')
    #logging.debug("\n\nStarting\n********\n")
    app = QApplication(sys.argv)
    #NOTE: also put `os.path.join(basedir,` into ui_form.py after generation
    app.setWindowIcon(QtGui.QIcon(os.path.join(basedir,'qtpyGraphEdit.ico')))
    MainWin = MainWindow()
    MainWin.resize(600, 400)
    MainWin.show()
    #cProfile.run('sys.exit(app.exec())')
    sys.exit(app.exec())