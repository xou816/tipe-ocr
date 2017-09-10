import numpy as np
import matplotlib.pyplot as plt

def sigmoide(x):
	return 1/(1+np.exp(-x))

with plt.rc_context(rc = { "text.usetex": True, "font.family": "serif" }):
	x = np.linspace(-5, 5, 200)
	y = sigmoide(x)
	plt.plot(x, y, color = "black")
	plt.grid()
	plt.axes()
	plt.savefig("sigmoide.pdf")