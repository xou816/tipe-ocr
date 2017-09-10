import json
import matplotlib.pyplot as plt

chemin = input("Fichier: ")

with open(chemin, "r") as fichier:

	contenu = json.load(fichier)
	donnees = contenu["graphes"]
	taux_app = contenu["taux_app"]
	inertie = contenu["inertie"]
	delta = contenu["delta"]

	with plt.rc_context(rc = { "text.usetex": True, "font.family": "serif" }):

		plt.clf()

		lines = ["-", "--", "-.", ":"]
		if inertie > 0:
			titre = "Apprentissage ({}s) \n $\\alpha = {}, i = {}$".format(delta, taux_app, inertie)
		else:
			titre = "Apprentissage ({}s) \n $\\alpha = {}$".format(delta, taux_app)
		plt.title(titre, fontsize = 16)
		plt.xlabel("Cycle", fontsize = 16)
		plt.ylabel("Erreur $ E $", fontsize = 16)

		for i, courbe in enumerate(donnees):
			nom, x, y = courbe
			plt.plot(x, y, color = "black", linestyle = lines[i%4], label = nom)

		plt.grid()
		plt.legend()

		plt.savefig(chemin+".pdf")

		print("Fait!")