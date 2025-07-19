# qtPyGraphEdit
A graphical node-edge graph editor, in Python and Qt (PySide6)

This is a prototype and learning project. My primary goal is to learn Qt/ Pyside, and to figure out the patterns needed to support model (repository) -based, multi-graphical view higraphs. I have some blog posts about the project [here](https://isijingi.co.za/wp/category/higraph/)

## V0 is a simple node-edge graph editor

Goal: Build a basic PySide6 framework for a model-viewController, with a truly independent Graph model
This is currently based on a simple [custom Graph library](https://github.com/ghillebrand/) , which will be extended to higraphs in V1. One could use `networkx` or an equivalent at this point, but it doesn't support higraphs, so the work will have to be done sooner or later.

V0.0
- Dictionary of nodes and edges with meta data. 
- Displayed in a text list and graphically
- Edit the graph - add, delete, edit text for nodes & edges, move nodes, reroute edges. 
- Save and load (Graphml with yED extensions). This uses code from [yEdExtended](https://github.com/cole-st-john/yEdExtended)
- Copy/ Paste as text, graphics and internally to duplicate items.
- A rudimentary Python shell that runs with (write!) access to the Graph, Scene and Model data.
- NOTE: This version uses the qtcreator `.ui` files, which places some constraints on what one can do. There are some workarounds to this in the code. As I understand Qt better, hopefully there will be fewer of these!

_Currently, V00 has a bug on deleting an edge, such that quite often, but not always, the edge is removed from the data structures, but the Qt Scene still draws it._

**TODO:**

V0.1
- Hermite splines for edges - based around [this code](https://github.com/vedantyadu/Hermite-cubic-spline)
- Multipoint edges

V0.2
- Hyperedges
            
V0.3
- Multiple tabs - editable views of different subsets of the master Graph model 
- Text display and edit for extended metadata

# Getting Started with editing
If you are totally new to Qt (or PySide, the Python version used here), this is a [good tutorial](www.pythonguis.com/tutorials/pyside6-qgraphics-vector-graphics/)

Otherwise, 
- create a folder, 
- create a virtual enviroment  `python -m venv C:\path\to\new\virtual\environment` (and make it active with `scripts\activate`)
- install PySide with `pip install PySide6`
- copy all the code from here (git clone https://github.com/ghillebrand/qtPyGraphEdit.git) or download the zip from the green `Code` button above.
- Run `python mainwindow.py`, or open `mainwindow.py` with you favourite editor. I use VSCodium: VSCode without the telemetry back to Microsoft.
- If you want to edit the dialogs, then you need the Qt designer `qtcreator` and to compile the `.ui` files to `.py`. The command is `pyside6-uic <file>.ui -o <file>.py`

The code comes with no guarantees at this point - not even that it will run! It certainly has rough edges and bugs. I do try to check that what's here runs, but this is still very much the beginning of a much longer journey.
