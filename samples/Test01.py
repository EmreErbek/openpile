# import libraries
import matplotlib.pyplot as plt
from openpile.construct import create_pile, create_mesh
from openpile.analyses import simple_beam_analysis
from openpile.utils.graphics import connectivity_plot

# create pile
pile = create_pile(kind='Circular', 
                   material='Steel', 
                   top_elevation=0, 
                   pile_sections={'length':[40],'diameter':[2], 'wall thickness':[0.08]})
# create mesh
mesh = create_mesh(pile=pile, coarseness=5)

# create point load
# mesh.set_support(elevation=-10, )
mesh.set_support(elevation=-0, Tx = True, Ty =True)
mesh.set_support(elevation=-30, Ty = True)

mesh.set_pointload(elevation=-40,Py=200,Px=-100,Mz=-200)
results = simple_beam_analysis(mesh)

fig = connectivity_plot(mesh)


plt.show()