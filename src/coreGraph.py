""" Core Graph Classes
V01:
This implements directed hyper multigraphs in a class Graph.
This is the "sort-of-pure maths" implementation. there are redundant links from
   nodes->edges as well as edges-> nodes, to make graphical editing & drawing a bit easier
The graphical representation for higraphs will be added later

Nodes as sets will be added later - inclusion is easier than n-ary edges.

"""

#from typing import ClassVar
import copy

class Graph:
    """ a set of nodes and edges"""
    
    #A graph-global ID. Allows for hyperedges (edges start XOR end on edges)
    nextID:int = 0
    
    # a container class of nodes. Mostly exists as a place to hold metadata, and some optimisations 
    class node():
      
        def __init__(self,metadata=None):
            self.nodeID = Graph.nextID
            Graph.nextID += 1
            self.metadata = metadata
            self.startsEdges = []  
            self.endsEdges = []


        def __repr__(self):
            return f"nodeID:{self.nodeID},metadata:{self.metadata},startsEdges:{self.startsEdges},endsEdges:{self.endsEdges}\n"

        __str__ = __repr__
        
        def addStarts(self,edge):
            """add that this node starts <edge>  """
            self.startsEdges.append(edge)
        
        def addEnds(self,edge):
            """add that this node ends <edge>  """
            self.endsEdges.append(edge)
        
            
    #-------------------------------------------------------------------------------------#
    
    class edge():
       
        def __init__(self,start:int,end:int,metadata:dict|None=None):
            """new edge, must have start = nodeID or tuple, end = nodeID, optional metadata   """
            #TODO: For re-creating from file/ paste, ID will need to be a param?
            self.edgeID = Graph.nextID
            Graph.nextID += 1
            self.metadata = metadata
            self.startNodes = [] 
            self.endNodes = []


        def __repr__(self):
            return f"edgeID:{self.edgeID},metadata:{self.metadata},startNodes:{self.startNodes},endNodes:{self.endNodes}\n"

        __str__ = __repr__
        
        def updateMeta(self,metadata:list[dict]):
            """ updates (overwriting) metadata of the edge. metadata must be list """
            for m in metadata:
                self.metadata.update(m)
                

    #-------------------------------------------------------------------------------------#
    
    # Parent Graph methods
        
    def __init__(self):
        #TODO: can this be one list, with a flag indicating the type?
        self.nodeD = {}  #Dictionary of nodes
        self.edgeD = {}  #Dictionary of edges

    def __repr__(self):
        return(f"nodes:\n{self.nodeD}\nedges:\n{self.edgeD}")
    
    __str__ = __repr__
    
    def addNode(self,name=None)->int:
        n = self.node({"name":name})
        self.nodeD.update({n.nodeID:n})
        return n.nodeID
        
    def addEdge(self,start,end,name=None)->int|None:

        #standard n-n edge
        if start in self.nodeD and end in self.nodeD:
            #create a new one
            e = self.edge(start,end,{"name":name})
            
            #Tell the nodes they have new edges
            #TODO: `nodeD` is a misnomer, since edges can be start/ end items too.
            self.nodeD[start].startsEdges.append(e.edgeID)
            self.nodeD[end].endsEdges.append(e.edgeID)
            
            #Store the nodes on the edge
            e.startNodes.append(start)
            e.endNodes.append(end)
            
            #Add to the graph's edge Dict
            self.edgeD.update({e.edgeID:e})
            return e.edgeID
        
        #check for a hyperedge create. NB: This is _not_ a new edge, just additional starts and ends
        #    and update metadata
        #In the editor, this will require adding an additional arc to the edge at (segment:proportion)
        #TODO: should this not be a separate method addToEdge(), since the edge itself already exists?
        
        # edge -> node
        if start in self.edgeD and end in self.nodeD:
            e = self.edgeD[start]
            if name:
                e.updateMeta([{'name':name}])
            e.endNodes.append(end)
            self.nodeD[end].endsEdges.append(e.edgeID)
            return e.edgeID

        #node -> edge
        if start in self.nodeD and end in self.edgeD:    
            e = self.edgeD[end]
            if name:
                e.updateMeta([{'name':name}])
            e.startNodes.append(start)
            self.nodeD[start].startsEdges.append(e.edgeID)     
            return e.edgeID
        
        #edge1 -> edge2 not allowed (requires merging 2 edges
        if start in self.edgeD and end in self.edgeD:
            print(f"***Error adding edge: edge->edge connections {start}->{end} require merging edges - not allowed")
            return None
        #else:
        print(f"***Error adding edge: No nodes found for edge {start}->{end}")
        return None
            
    def delNode(self,nodeID:int):
        """ Delete a node. If the node is the only start/ end for an edge, 
            the edge is deleted too
        """
        #print(nodeID)
        if nodeID in self.nodeD:
            n = self.nodeD[nodeID]
            #print(f"In coreGraph \n{self =}")
            #check for edges where this is a start/ end
            stEd = copy.deepcopy(n.startsEdges)
            for stEdge in stEd:
                if len(self.edgeD[stEdge].startNodes) == 1:
                    #This node is the *only* start, so delete the edge
                    self.delEdge(stEdge)
                else: #remove this node from the startlist
                    self.edgeD[stEdge].startNodes.remove(nodeID)
            
            enEd = copy.deepcopy(n.endsEdges)
            for endEdge in enEd:
                if len(self.edgeD[endEdge].endNodes) == 1:
                    #This is the *only* node ending edge
                    self.delEdge(endEdge)
                else: #remove from the endlist
                    self.edgeD[endEdge].endNodes.remove(nodeID)
            #delete the node
            self.nodeD.pop(nodeID)
        else:
            print(f"*** Error Can't delete {delNode =} - does not exist")
            return

    def delEdge(self,edgeID:int):
        """delete an Edge, inc updating all the reverse lists"""
        #Note - for graphics, check for additional sub arcs starting or ending at the edge to be deleted
        
        if edgeID in self.edgeD:
            e = self.edgeD[edgeID]
            #remove from nodeLists:
            for StNode in e.startNodes:
                self.nodeD[StNode].startsEdges.remove(edgeID)
            for EndNode in e.endNodes:
                self.nodeD[EndNode].endsEdges.remove(edgeID)
            
            self.edgeD.pop(edgeID)
        else:
            print(f"***Error deleting edge <{edgeID}> - does not exist")

    def updateEdge(self, edgeID:int ,oldID:int, end:str, newID:int):
        """ relinks `edgeID` from oldID to newID at end ("start" or "end" """
        if not end in ["start", "end"]:
            #TODO: make this an exception
            print(f"error - end must be 'start' or 'end' , not '{end}'")
            return None
        if edgeID in self.edgeD:
            e = self.edgeD[edgeID]
        else:
            print(f"***Error updating edge <{edgeID}> - does not exist")
            return None
        
        if oldID not in self.nodeD:
            print(f"***Error updating edge <{edgeID}> - node {oldID = } does not exist")
            return None            

        if newID not in self.nodeD:
            print(f"***Error updating edge <{edgeID}> - node {newID = } does not exist")
            return None
        
        if end == "start":
            #Unlink old node:
            self.nodeD[oldID].startsEdges.remove(edgeID)
            e.startNodes.remove(oldID)
            #Relink newnode:
            self.nodeD[newID].startsEdges.append(edgeID)
            e.startNodes.append(newID)
        else: #end
            #Unlink old node:
            self.nodeD[oldID].endsEdges.remove(edgeID)
            e.endNodes.remove(oldID)
            #Relink newnode:
            self.nodeD[newID].endsEdges.append(edgeID)
            e.endNodes.append(newID)
        return True
    
