# Interface
from tkinter import *
from tkinter import simpledialog, messagebox, ttk, filedialog
from PIL import Image, ImageTk # Dans le shell: "pip install pillow"

import os, sys, time, random, traceback, copy, json
from ocr import *

# Figures
import numpy
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt # Pour figure LaTeX

class LabelImage(Label):

	"""Affiche une miniature d'image"""

	def __init__(self, *args, **kwargs):

		self.thumbnail = (100, 100) # Taille de l'image
		if "thumbnail" in kwargs: # On regarde si l'utilisateur a spécifié "thumbnail": LabelImage(parent, thumbnail = ...)
			self.thumbnail = kwargs["thumbnail"]
			del kwargs["thumbnail"] # On enlève cette option, qui n'est pas reconnue par le Label de tkinter

		if "image" in kwargs: # Si il y a "image" dans les options, c'est une image PIL (normalement)
			self.image_reduite = kwargs["image"].copy() # ...que  l'on copie...
			self.image_reduite.thumbnail(self.thumbnail, Image.ANTIALIAS) # ... que l'on réduit à la taille spécifiée...
			self.image = ImageTk.PhotoImage(self.image_reduite) # ...que l'on convertit pour être affichée par tkinter...
			kwargs["image"] = self.image # On donne cette image transformée au constructeur de Label
		elif not "text" in kwargs: # Si y'a pas d'image, et que l'utilisateur n'a pas précisé de texte à afficher...
			kwargs["text"] = "(pas d'image)" # ... on demande au constructeur de Label d'écrire "(pas d'image)"

		Label.__init__(self, *args, **kwargs) # On passe tous les arguments au constructeur de Label (en ayant enlevé thumbnail notamment)

	def maj_image(self, image):

		"""Mets à jour l'image affichée, en la remplaçant par 'image'"""

		self.vraie_image = image
		self.image_reduite = image.copy() # Même opérations qu'avant, dans __init__
		self.image_reduite.thumbnail(self.thumbnail, Image.ANTIALIAS)
		self.image = ImageTk.PhotoImage(self.image_reduite)
		self.config(image = self.image, text = "")

	def get_image(self):

		"""Renvoie une copie de l'image PIL contenue"""

		return self.vraie_image.copy()


class PopupImage(Toplevel): # Un visionneur d'images très simple

	"""Classe pour gérer l'affichage d'images"""

	def __init__(self, **kw):

		"""Fonction appelée à la création d'un objet de type PopupImage"""
		
		if "lien" in kw or "image" in kw: # On exige que l'utilisateur fournisse un lien ou (exclusif) une image

			Toplevel.__init__(self)

			if "lien" in kw: # Si l'utilisateur a spécifié un lien
				try:
					self._image_originale = Image.open(kw["lien"]) # On ouvre l'image en tant qu'image PIL grâce à ce lien, on la stocke
					self.title("Image: "+kw["lien"]) # On modifie le titre de la fenêtre pour afficher le chemin d'accès de l'image = lien
				except Exception: # Si il y a une erreur (lien inexistant, image invalide... etc)
					messagebox.showerror("Erreur", "Une erreur est survenue lors de la lecture de l'image.")
			elif "image" in kw: # Si l'utilisateur a spécifié une image (sous entendu image PIL)
				self._image_originale = kw["image"] # C'est directement une image, on la stocke, pas besoin d'ouvrir
				self.title("Image locale")

			self.facteur = 1 # Facteur de zoom de l'image
			self.image = ImageTk.PhotoImage(self._image_originale) # L'image affichée est obtenue en convertissant l'image PIL pour tkinter
			self.affichage = ttk.Label(self, anchor = "center", image = self.image) # Un Label est capable d'afficher une image
			self.affichage.pack(fill = "both", expand = "yes")

			# Ce bout de code définit la taille minimale de la fenêtre comme étant la taille minimale requise une fois qu'on a affiché tous les widgets
			self.update_idletasks()
			self.minsize(self.winfo_width(), self.winfo_height())

			# On met en écoute les événements liés à l'utilisation de la molette, pour le zoom
			self.bind("<MouseWheel>", self.molette)
			# Pour Linux, il faut ajouter d'autres évenements: http://stackoverflow.com/questions/17355902/python-tkinter-binding-mousewheel-to-scrollbar
			self.bind("<Button-4>", self.molette) 
			self.bind("<Button-5>", self.molette)

	def molette(self, event):

		"""Change l'épaisseur de tracé et actualise le curseur s'il existe (appelé lors d'un défilement molette)"""
		
		# L'événement <MouseWheel> fourni un delta, qui vaut 120 ou -120, ce qui nous intéresse est essentiellement le signe de ce delta qui indique le sens de rotation de la molette
		delta = event.delta
		# Adaptations pour Linux: on regarde le numéro de l'événement car la molette est interprétée comme deux boutons supplémentaires de la souris (4 et 5)
		if event.num == 5:
			delta = -120
		elif event.num == 4:
			delta = 120

		facteur = 1-delta/1200
		self.zoom(facteur)


	def sauvegarder(self):

		"""Fonction appelée pour sauvegarder les images (non utilisée...)"""

		chemin = filedialog.asksaveasfilename() # Affiche un dialogue
		if chemin is not None:
			self._image_originale.save(chemin)


	def _maj_image(self):

		"""Met à jour l'image (par exemple, après modification du facteur de zoom)"""

		img = self._image_originale.copy() # On copie l'image PIL par sécurité avant d'y toucher
		w, h = img.size
		img = img.resize((int(w*self.facteur), int(h*self.facteur))) # On la redimensionne selon le facteur de zoom
		self.image = ImageTk.PhotoImage(img) # On la convertit pour tkinter...
		self.affichage.config(image = self.image)


	def zoom(self, facteur):

		"""Fonction appelée pour changer le facteur de zoom"""

		self.facteur *= facteur # On se content de modifier le facteur...
		self._maj_image() # ... puis on utilise notre fonction de mise à jour


class Dessin(Canvas):

	"""Classe pour gérer la zone de dessin (onglet échantillonage)"""

	def __init__(self, parent, taille, echelle, curseur = None):

		"""Fonction appelée à la création d'un Dessin"""

		Canvas.__init__(self, parent)
		self.config(bd = 0, highlightthickness = 0, width = taille, height = taille, bg = "white")
		
		self.echelle = echelle # Un tuple (min, max)
		self.curseur = curseur # Un widget "Scale" fourni éventuellement par l'utilisateur
		if curseur: # Si l'utilisateur a fourni un widget...
			curseur.config(command = self._epaisseur_scale, from_ = echelle[0], to = echelle[1]) # ...on s'occupe de régler son comportement pour qu'il corresponse au dessin

		self.dernier_xy = (0, 0) # On sauve en mémoire le dernier point ou l'utilisateur a cliqué (voir plus loin)
		self.taille = taille # Taille du dessin (côté)
		self.epaisseur = 10 # Épaisseur du tracé

		# On met en écoute les événements de la souris (= un clic, un mouvement, etc...)		
		# Les événements <Button-#> surviennent à chaque clic simple (relaché ou non après): on initialise le début du tracé
		# Les événements <B#-Motion> surviennent lorsque la souris se déplace tout en maintenant le bouton '#' enfoncé: on trace alors les pixels
		# Bouton 1 -> clic gauche (dessiner donc tracer en noir = #000000), bouton 3 -> clic droit (effacer donc tracer en blanc = #FFFFFF)
		self.bind("<Button-1>", lambda event: self.initialiser_clic(event, "#000000"))
		self.bind("<B1-Motion>", lambda event: self.dessiner(event, "#000000"))
		self.bind("<Button-3>", lambda event: self.initialiser_clic(event, "#FFFFFF"))
		self.bind("<B3-Motion>", lambda event: self.dessiner(event, "#FFFFFF"))

		# On met en écoute les événements liés à l'utilisation de la molette, ici pour changer l'épaisseur de tracé
		self.bind("<MouseWheel>", self._epaisseur_scroll)
		# Pour Linux, il faut ajouter d'autres évenements: http://stackoverflow.com/questions/17355902/python-tkinter-binding-mousewheel-to-scrollbar
		self.bind("<Button-4>", self._epaisseur_scroll) 
		self.bind("<Button-5>", self._epaisseur_scroll)

		self.pos_souris = (taille//2, taille//2) # On retient la position de la souris, par défaut au milieu du dessin
		self.bind("<Motion>", self.maj_viseur) # À chaque mouvement simple de la souris, on actualise l'affichage du viseur (le carré pour viser)
		self.viseur = self.create_rectangle(taille//2, taille//2, self.epaisseur, self.epaisseur, width = 0) # Le viseur est initialisé à la position de la souris, c'est un rectangle de longueur et de largeur correspondant à l'épaisseur

		self.effacer() # On efface le dessin au départ, cela sert en même temps à l'initialiser (voir effacer())

	def maj_viseur(self, event = None):

		"""Actualise le curseur (à appeler à chaque évenement susceptible de modifier l'épaisseur de tracé ou la position de la souris)"""

		# maj_viseur() est appelé soit par l'événement <Motion>, soit par le code pour signaler qu'il faut redessiner le viseur
		if event: # On a une variable event donc appel par <Motion>
			x, y = event.x, event.y # La variable event contient les coordonnées du lieu de l'événement
			self.pos_souris = (x, y) # On garde la position en mémoire pour les cas ou on appelle maj_viseur() sans événement (donc sans infos de position)
		else:
			x, y = self.pos_souris # On a pas d'événements donc on utilise la dernière position connue
		e = self.epaisseur
		self.itemconfig(self.viseur, width = 1) # On modifie le viseur: la largeur de son contour est mise à 1
		self.coords(self.viseur, x - e//2, y - e//2, x + e//2, y + e//2) # ... et on modifie ses coordonnées
		self.tag_raise(self.viseur) # On affiche le viseur sur le dessus du dessin par sécurité

	def changer_epaisseur(self, valeur, scale = False):

		from_, to = self.echelle
		self.epaisseur = valeur

		# On corrige les effets de bord
		if self.epaisseur > to:
			self.epaisseur = to
		elif self.epaisseur < from_:
			self.epaisseur = from_

		if self.curseur is not None and not scale: # Si on a un widget Scale, on le met à jour aussi! Sauf si c'est lui qui appelle 'changer_epaisseur' (scale = True)
			self.curseur.set(self.epaisseur)

		self.maj_viseur() # Enfin, on signale que le viseur doit être redessiné (il a changé d'épaisseur)
		
	def _epaisseur_scale(self, valeur):

		"""Change l'épaisseur de tracé, appelé par le curseur (widget Scale) s'il existe"""
		
		self.changer_epaisseur(int(float(valeur)), scale = True) # On signale que c'est le scale qui change l'épaisseur (sinon boucle infinie) 
		
	def _epaisseur_scroll(self, event = None):

		"""Change l'épaisseur de tracé et actualise le curseur s'il existe (appelé lors d'un défilement molette)"""
		
		# L'événement <MouseWheel> fourni un delta, qui vaut 120 ou -120, ce qui nous intéresse est essentiellement le signe de ce delta qui indique le sens de rotation de la molette
		delta = event.delta
		# Adaptations pour Linux: on regarde le numéro de l'événement car la molette est interprétée comme deux boutons supplémentaires de la souris (4 et 5)
		if event.num == 5:
			delta = -120
		elif event.num == 4:
			delta = 120

		from_, to = self.echelle
		self.changer_epaisseur(self.epaisseur + 1/2*delta//(from_-to)) # On modifie l'épaisseur

	def export(self, chemin):

		"""On enregistre le dessin au format 'format' (par défaut: PNG) dans le répertoire 'chemin'"""
		
		self.image.write(chemin, format = "png")

	def effacer(self):

		"""Efface le Dessin (appelée par le bouton 'Effacer' entre autres)"""

		self.image = PhotoImage(master = self, width = self.taille, height = self.taille)
		self.create_image((self.taille//2, self.taille//2), image = self.image, state = "normal") 

	# Méthodes de dessin inspirée de tkdocs.com

	def initialiser_clic(self, event, couleur):

		"""Fonction appelée lors d'un clic gauche sur le Dessin, définit un point de départ pour la tracé d'une ligne continue"""

		self.dernier_xy = x, y = (event.x, event.y) # Point de départ du tracé
		self.point(x, y, couleur) # On dessine un premier point

	def dessiner(self, event, couleur):

		"""Fonction appelée lors du maintien du clic gauche, permet de dessiner une ligne continue depuis 'dernier_xy'"""

		self.maj_viseur(event) # On met à jour le viseur à l'endroit où on dessine

		ox, oy = self.dernier_xy
		ex, ey = event.x, event.y
		self.dernier_xy = (ex, ey)
		e = int(self.epaisseur)

		# On trace les points entre le dernier point de passage enregistré (dernier_xy) et les coordonnées de l'événement car l'ordinateur n'arrive pas à capter tous les points de passage...
		dx, dy = (ex-ox)/e, (ey-oy)/e
		a_tracer = [(ex, ey)] # Liste de points (ex, ey) à tracer
		for i in range(e):
			ax, ay = (ox+i*dx, oy+i*dy)
			a_tracer.append((int(ax), int(ay)))

		for x, y in a_tracer:
			self.point(x, y, couleur) # On trace les points

	def point(self, x, y, couleur = "#000000"):

		"""Dessine un carré centré en (x, y) sur l'image du canvas"""

		e = int(self.epaisseur)
		try:
			self.image.put(couleur, to = (x-e//2, y-e//2, x+e//2, y+e//2))
		except Exception: # Quand on trace trop près des bords, des erreurs surviennent et ça semble beaucoup perturber tkinter, alors on le rassure en lui disant que c'est normal...
			pass


class Graphe():

	"""Un pseudo-widget pour faire rapidement un graphe Matplotlib"""

	def __init__(self, parent):

		self.figure = Figure(figsize = (5, 4), dpi = 100, facecolor = "white", linewidth = 0, frameon = False, edgecolor = "white") 
		self.plot = plot = self.figure.add_subplot(1, 1, 1)
		plot.autoscale_view(True, True, True)
		plot.margins(0.1, 0.1)
		self.courbes = [] # Objets courbe Matplotlib
		self.noms = []
		self.canvas = FigureCanvasTkAgg(self.figure, master = parent)
		self.canvas.show()

	def ajouter_point(self, courbe, x, y):

		"""Ajoute un point (x, y)"""

		courbe.set_xdata(numpy.append(courbe.get_xdata(), x))
		courbe.set_ydata(numpy.append(courbe.get_ydata(), y))
		
		self.plot.legend()
		self.plot.relim()
		self.plot.autoscale_view()
		self.plot.grid()
		self.canvas.draw()

	def export(self, fichier):

		"""Enregistre la figure dans un fichier"""

		self.figure.savefig(fichier)

	def donnees_brutes(self):

		liste = [(nom, courbe.get_xdata(), courbe.get_ydata()) for nom, courbe in zip(self.noms, self.courbes)]
		return liste

	def effacer(self):

		"""Effacer le tracé"""

		self.plot.clear()
		self.courbes = []
		self.noms = []

	def nouvelle_courbe(self, nom = ""):

		"""Créer une nouvelle courbe, les courbes précédentes restent affichées si non effacées"""

		courbe, = self.plot.plot([0], [0], label = nom)
		self.courbes.append(courbe)
		self.noms.append(nom)
		return courbe

	def widget(self):

		"""Renvoie le widget Tk associé au Graphe"""

		return self.canvas.get_tk_widget()

class Panneau(Frame):

	"""Un widget similaire à Frame, mais qui peut être affiché et caché alternativement. NÉCESSITE QUE LE PANNEAU SOIT AFFICHÉ DANS UNE GRILLE!!!"""

	def __init__(self, *args, **kwargs):

		Frame.__init__(self, *args, **kwargs)
		self.visible = True

	def toggle(self):

		if self.visible:
			self.visible = False
			self.grid_remove() # grid_remove() enlève l'élément de la grille mais retient les options passées à grid() au moment d'attacher le Panneau à l'interface
		else:
			self.visible = True
			self.grid() # grid() se souvient des options


class Application:

	"""L'application elle même!"""

	def __init__(self, root):

		"""Fonction appelée à la création de la fenêtre, on définit tout les onglets et autres""" 

		self.root = root
		self.style = ttk.Style()
		root.option_add("*tearOff", False) # Juste un p'tit réglage de l'affichage des menus
		root.protocol("WM_DELETE_WINDOW", self.quitter) # Comportement du bouton "fermer" de la fenêtre
		root.columnconfigure(1, weight = 1) # La colonne 1 de la fenêtre (celle du milieu) a le droit de s'étendre si il y a la place
		root.rowconfigure(0, weight = 1) # Idem pour la ligne 0 (chez nous, tous les éléments sont dans la première ligne)

		self.menus = [] # Menus clic droit

		# Les onglets pour entrer les échantillons sous forme de dessin ou photo, d'où le nom "methode" (ligne 0, colonne 0)
		self.methode = methode = ttk.Notebook(root) # Un navigateur par onglet
		methode.grid(column = 0, row = 0, sticky = W+E+N+S, padx = 10, pady = 10)
		methode.add(self.creer_zone_dessin(methode), text = "Dessin")
		methode.add(self.creer_zone_photo(methode), text = "Photo")

		self.onglets = [] # Liste des objets Onglet

		# La barre latérate (ligne 0, colonne 2)
		self.barre_laterale = self.creer_barre_laterale(root)

		self.chemin_fichier = None # Stocke le chemin complet vers le fichier actif
		self.modifie = False # Booléen donnant l'état du fichier courant: modifié ou non
		self.reseau_hist = [] # Liste de réseaux pour annuler les modifications
		self.nouveau() # Création d'un nouveau fichier

		# On crée les onglets (ligne 0, colonne 1, milieu)
		self.onglets_widgets = onglets = ttk.Notebook(root) # Attention: self.onglets_widgets != self.onglets
		onglets.grid(column = 1, row = 0, sticky = W+E+N+S, padx = 10, pady = 10)
		StructureReseau(onglets, self)
		Apprentissage(onglets, self)
		# Enlevé: EntrainementEnLigne(onglets, self)
		Reconnaissance(onglets, self)
		GrapheInterractif(onglets, self)

		root.bind("<Return>", self.action_principale_onglet) # On écoute l'événement "appui sur la touche entrée", liée à la fonction action_principale_onglet()

		# Ce bout de code définit la taille minimale de la fenêtre comme étant la taille minimale requise une fois qu'on a affiché tous les widgets
		root.update_idletasks()
		root.minsize(root.winfo_width(), root.winfo_height())

		self.creer_menu(root) # Création des menus 'Fichier', 'Édition', 'Affichage'...

		# On grid la barre latérale après, pour que la taille minimale ne la prenne pas en compte ;)
		self.barre_laterale.grid(column = 2, row = 0, sticky = W+E+N+S, padx = 5, pady = 5)

	def modif_style(self, *noms, **options):

		for nom in noms:
			self.style.configure(nom, **options)

	def ajout_menu_clic(self, widget):

		"""Création d'un menu clic droit pour un widget"""

		menu = Menu(root)
		self.menus.append(menu)
		id = len(self.menus)-1
		widget.bind("<Button-3>", lambda event, id = id: self.aff_menu_clic(event, id))
		widget.bind("<Button-1>", lambda event, id = id: self.menus[id].unpost())
		return menu

	def aff_menu_clic(self, event, id):

		"""Gère l'affichage menu clic droit"""

		self.menus[id].post(event.x_root, event.y_root)

	def action_principale_onglet(self, event):

		"""Identifie l'onglet actif et appelle action_principale() sur celui-ci"""

		nom = self.onglets_widgets.tab(self.onglets_widgets.select(), "text") # Renvoie le nom de l'onglet actif
		onglet = None
		for _onglet in self.onglets: # On parcoure les objets Onglet
			if _onglet.nom == nom: # On compare le nom avec celui obtenu plus haut
				onglet = _onglet
				break
		onglet.action_principale() # Enfin, on appelle action_principale(): on peut ainsi avoir un raccourci clavier identique en plusieurs points de l'interface, sans interférence

	def image(self):

		"""Renvoie un échantillon issu de l'onglet methode actif ('Dessin' ou 'Photo')"""

		nom = self.methode.tab(self.methode.select(), "text")

		if nom == "Dessin":

			self.dessin.export("dessin_tmp.png") # On a pas le choix, PhotoImage est trop limité, il faut créer un fichier temporaire
			image = ImageBinaire.open("dessin_tmp.png") # On ouvre ce dessin en tant qu'ImageBinaire, il n'y a pas de problème de seuil de luminosité puisque le dessin crée des images en noir et blanc
			if self.opt_epaisseur.get():
				self.dessin.changer_epaisseur(random.randint(*self.dessin.echelle))
			if self.opt_rotation.get(): 
				image.rotate(random.randint(-5, 5), expand = 1) # On applique une légère rotation
			image.recentrer() # On enlève les pixels inutiles
			return image

		elif nom == "Photo":

			return ImageBinaire.depuis_image(self.photo.get_image()) # Le seuil de luminosité n'importe pas car l'interface d'importation de photo ce charge de cela, on convertit une image déjà convertie...

	def creer_menu(self, parent):

		"""Création du menu 'Fichier', 'Édition', 'Affichage'..."""

		menu = Menu(parent)
		parent["menu"] = menu

		# Pour chacun des éléments, on définit une commande 'command' (action lors du clic), un 'accelerator' (indication visuelle du raccourci clavier) et on écoute les événements permettant de définir nos raccourcis clavier
		# <Control-lettre_en_minuscule> = Ctrl + lettre
		# <Control-lettre_en_majuscule> = Maj + Ctrl + lettre
		menu_fichier = Menu(menu)
		menu.add_cascade(menu = menu_fichier, label = "Fichier")
		menu_fichier.add_command(label = "Nouveau", command = self.nouveau, accelerator = "Ctrl + N")
		self.root.bind_all("<Control-n>", lambda event: self.nouveau())
		menu_fichier.add_command(label = "Ouvrir", command = self.ouvrir, accelerator = "Ctrl + O")
		self.root.bind_all("<Control-o>", lambda event: self.ouvrir())
		menu_fichier.add_command(label = "Enregistrer", command = self.sauvegarder, accelerator = "Ctrl + S")
		self.root.bind_all("<Control-s>", lambda event: self.sauvegarder())
		menu_fichier.add_command(label = "Enregistrer sous", command = lambda: self.sauvegarder(True), accelerator = "Maj + Ctrl + S")
		self.root.bind_all("<Control-S>", lambda event: self.sauvegarder(True))
		menu_fichier.add_command(label = "Quitter", command = self.quitter, accelerator = "Ctrl + Q")
		self.root.bind_all("<Control-q>", lambda event: self.quitter())

		self.menu_edition = menu_edition = Menu(menu)
		menu.add_cascade(menu = menu_edition, label = "Édition")
		menu_edition.add_command(label = "Annuler la dernière modification", command = self.annuler_modif, accelerator = "Ctrl + Z")
		self.root.bind_all("<Control-z>", lambda event: self.annuler_modif())

		menu_affichage = Menu(menu)
		menu.add_cascade(menu = menu_affichage, label = "Affichage")
		menu_affichage.add_checkbutton(label = "Barre latérale", command = self.barre_laterale.toggle, accelerator = "Ctrl + T")
		self.root.bind_all("<Control-t>", lambda event: self.barre_laterale.toggle())

		menu_onglets = Menu(menu_affichage)
		menu_affichage.add_cascade(menu = menu_onglets, label = "Onglets")
		for onglet in self.onglets:
			menu_onglets.add_checkbutton(label = onglet.nom, command = lambda *args, onglet = onglet: onglet.toggle())

		menu_theme = Menu(menu_affichage)
		menu_affichage.add_cascade(menu = menu_theme, label = "Thème Tkinter")
		for theme in self.style.theme_names():
			menu_theme.add_radiobutton(label = theme.title(), command = lambda *args, theme = theme: self.changer_theme(theme))
		menu_theme.add_radiobutton(label = "NE PAS CLIQUER", command = lambda *args: self.apocalypse())

	def apocalypse(self):

		messagebox.showwarning("NON!!", "POURQUOI AVOIR FAIT CA??")
		messagebox.showwarning("THIS IS TEH END", "Ouvrez le gestionnaire de tâche pour enrayer cette immonde opération, c'est votre seule chance!!!")
		self.changer_theme("custom")

	def theme_perso(self):

		"""Comic Sans FTW!"""

		self.modif_style(".", font = ("Comic Sans MS", 12, "bold italic"), background = "yellow", foreground = "green")
		self.modif_style("TButton", foreground = "white", background = "red")
		self.modif_style("TLabel", foreground = "blue")

	def changer_theme(self, theme):

		if theme == "custom":
			self.theme_perso()
		else:
			self.style.theme_use(theme)

	def reseau(self):

		"""Renvoie le réseau en cours de modification"""

		return self.reseau_hist[-1][0]

	def modif_reseau(self, reseau):

		"""Mets à jour le réseau actif, et conserve l'historique des modifications"""

		self.reseau_hist.append([reseau, self.modifie, self.nom_fichier, self.chemin_fichier])
		if len(self.reseau_hist) > 1:
			self.menu_edition.entryconfig(0, state = "normal")
		self.reseau_hist = self.reseau_hist[-5:] # On ne garde que 5 modifications en mémoire

	def annuler_modif(self):

		"""Annule la dernière modification"""

		if len(self.reseau_hist) > 1:
			self.reseau_hist.pop()
			reseau, modifie, nom_fichier, chemin_fichier = self.reseau_hist[-1]
			self.nom_fichier = nom_fichier
			self.chemin_fichier = chemin_fichier
			self.fichier_modifie(modifie)
		if len(self.reseau_hist) == 1:
			self.menu_edition.entryconfig(0, state = "disabled")

	def fichier_modifie(self, modifie = True):

		"""Marque le fichier actif comme étant modifié par défaut, ou comme n'étant pas modifié (modifie = False)"""

		self.modifie = modifie
		if modifie: 
			self.root.title(self.nom_fichier + "* - Réseaux de neurones artificiels") # On actualise le titre de la fenêtre en ajoutant une astérisque indiquant un changement
		else: 
			self.root.title(self.nom_fichier + " - Réseaux de neurones artificiels")
		self.maj_barre_laterale() # On actualise également la barre latérale qui décrit exactement l'état du fichier
		for onglet in self.onglets: 
			onglet.actualiser_fichier() # On signale à chaque onglet que le fichier a changé en appelant une méthode définie pour chaque Onglet (libre à lui d'utiliser cette information ou non)
			

	def test_modifie(self):

		"""Fonction à appeler à chaque fois que l'on souhaite changer de fichier, elle vérifie s'il y a des modifications à enregistrer et prévient l'utilisateur si c'est le cas"""

		if self.modifie: # N'a d'effet que si le fichier est effectivement modifié
			reponse = messagebox.askyesno("Enregistrer", "Le fichier '"+self.nom_fichier+"' a été modifié. Voulez-vous le sauvegarder?")
			if reponse:
				self.sauvegarder()


	def sauvegarder(self, sous = False):

		"""Sauvegarde le fichier actif, et affiche un dialogue de sauvegarde si le fichier n'est pas du tout enregistré. On peut forcer l'apparition de ce dialogue avec l'option 'sous'."""

		if self.chemin_fichier is not None and not sous: # Si un chemin vers le fichier existe et si on ne veut pas de dialogue "enregistrer sous"
			chemin = self.chemin_fichier
		else: # Sinon, on demande un endroit ou enregistrer
			chemin = filedialog.asksaveasfilename(filetypes = (("Réseaux (JSON)", "*.json"), ("Réseaux (ZIP)", "*.zip"), ("Tous les fichiers", "*.*")))
		if chemin is not None and chemin != "": # Pas de problème? On continue
			self.reseau().sauver(chemin)
			self.chemin_fichier = chemin
			self.nom_fichier = os.path.basename(chemin) # On garde le nom du fichier en mémoire
			self.fichier_modifie(False) # On signale qu'il n'y a PLUS de modifications (False)


	def quitter(self):

		"""Action à la fermeture de la fenêtre ou lors de l'utilisation de 'Quitter' depuis le menu 'Fichier'"""

		self.test_modifie() # On vérifie si il y a quelque chose à enregistrer...
		self.root.destroy() # Et on détruit la fenêtre sans états d'âme >:]
		exit()


	def ouvrir(self, fichier = None):

		"""Affiche un dialogue d'ouverture de fichier"""

		self.test_modifie() # On vérifie si il y a quelque chose à enregistrer

		if fichier is None:
			fichier = filedialog.askopenfilename(filetypes = (("Réseaux (JSON)", "*.json"), ("Réseaux (ZIP)", "*.zip"), ("Tous les fichiers", "*.*")))

		if fichier is not None and fichier != "" and os.path.exists(fichier): # Le fichier fourni est il valide? A t-on bien selectionné un fichier?

			self.nom_fichier = os.path.basename(fichier)
			self.chemin_fichier = fichier
			self.modif_reseau(ReseauOCR())
			self.reseau().ouvrir(fichier)
			self.fichier_modifie(False) # On indique qu'il n'y a plus de modifications en attente


	def nouveau(self):

		"""Création d'un nouveau fichier"""

		self.test_modifie()
		self.nom_fichier = "Sans titre"
		self.chemin_fichier = ""
		self.modif_reseau(ReseauOCR())
		self.fichier_modifie(False)


	def creer_zone_dessin(self, parent):

		"""Création du widget Dessin"""

		zone_dessin = ttk.Frame(parent)

		epaisseur = ttk.Scale(zone_dessin, orient = "horizontal") # Réglage de la taille du tracé, il est lié au Dessin et contrôlé par ce dernier (et vice-versa)
		self.dessin = Dessin(zone_dessin, 350, [5, 20], epaisseur)
		self.dessin.pack(padx = 5, pady = 5)
		epaisseur.pack(fill = "x", padx = 5, pady = 5)

		btn_eff = ttk.Button(zone_dessin, text = "Effacer le dessin", command = self.dessin.effacer)
		btn_eff.pack(padx = 5, pady = 5)

		# Option pour modifier l'épaisseur de tracé à chaque échantillon entré
		self.opt_epaisseur = BooleanVar()
		self.opt_epaisseur.set(False)
		check = ttk.Checkbutton(zone_dessin, text = "Épaisseur aléatoire", variable = self.opt_epaisseur)
		check.pack(padx = 5, pady = 5)

		# Option pour appliquer une légère rotation à chaque échantillon entré
		self.opt_rotation = BooleanVar()
		self.opt_rotation.set(False)
		check = ttk.Checkbutton(zone_dessin, text = "Rotation aléatoire", variable = self.opt_rotation)
		check.pack(padx = 5, pady = 5)

		return zone_dessin

	def creer_zone_photo(self, parent):

		"""Création du widget d'importation de Photo"""

		zone_photo = ttk.Frame(parent)

		self.photo_originale = None
		self.photo = photo = LabelImage(zone_photo, thumbnail = (350, 350), text = "(cliquer pour ouvrir une photo)")

		photo.bind("<Button-1>", self.ajouter_photo)
		photo.pack(padx = 5, pady = 5)

		f = ttk.Frame(zone_photo)
		f.pack(padx = 5, pady = 5, fill = "x")
		ttk.Label(f, text = "Luminosité: ").pack(padx = 5, side = "left")
		luminosite = ttk.Scale(f, orient = "horizontal", from_ = 0, to = 255, command = lambda valeur: self.maj_photo("couleur", valeur))
		luminosite.pack(fill = "x", expand = "yes", padx = 5, side = "left")

		# La flemme....
		# f = ttk.Frame(zone_photo)
		# f.pack(padx = 5, pady = 5, fill = "x")
		# ttk.Label(f, text = "Parasites:  ").pack(padx = 5, side = "left")
		# parasites = ttk.Scale(f, orient = "horizontal", from_ = 0, to = 10, command = lambda valeur: self.maj_photo("parasites", valeur))
		# parasites.pack(fill = "x", expand = "yes", padx = 5, side = "left")

		return zone_photo

	def ajouter_photo(self, *args):

		"""Affiche un dialogue pour ouvrir une photo dans l'application"""

		fichier = filedialog.askopenfilename()
		if fichier is not None and fichier != "":
			self.photo_originale = Image.open(fichier)
			self.photo.maj_image(self.photo_originale) # Voir LabelImage

	def maj_photo(self, type, valeur):

		"""Met à jour la photo, avec une modification du type 'type', de valeur 'valeur'"""

		if self.photo_originale is not None:
			valeur = int(float(valeur))
			if type == "couleur": # En fait, il s'agit de la modif du seuil de conversion en ImageBinaire
				photo_modif = ImageBinaire.depuis_image(self.photo_originale, valeur)
				# photo_modif.enlever_parasites(??) # La flemme...
			self.photo.maj_image(photo_modif)

	def creer_barre_laterale(self, parent):

		"""Création de la barre latérale"""

		barre_laterale = Panneau(root) # Voir Panneau

		self.explorateur = explorateur = ttk.Treeview(barre_laterale, columns = ("nb",)) # On ajoute nos colonnes spéciales
		for i in ["#0", "nb"]: # On configure les colonnes, #0 est la colonne par défaut toujours définie
			self.explorateur.column(i, width = 100, anchor = "center")
		self.explorateur.heading("#0", text = "Caractère")
		self.explorateur.heading("nb", text = "Échantillons")
		self.explorateur.bind("<<TreeviewSelect>>", self.explorateur_selection_changee) # On appelle la fonction 'explorateur_selection_changee' chaque fois que la sélection de l'explorateur, eh bien, change...
		explorateur.pack(fill = "both", expand = "yes", padx = 5, pady = 5)

		self.info_explorateur = ttk.Labelframe(barre_laterale, text = "Informations")
		self.info_explorateur.pack(fill = "both", expand = "yes", padx = 5, pady = 5)

		return barre_laterale

	def infos_reseau(self):

		"""Renvoie des infos sur le réseau pour la barre latérale"""

		reseau = self.reseau()
		return [("Réseau", reseau.architecture()), ("Type", reseau.type()), ("Codage", reseau.codage), ("Grille", reseau.grille)]


	def maj_barre_laterale(self):

		"""On met à jour la barre latérale"""

		reseau = self.reseau()

		for i in self.explorateur.get_children():
			self.explorateur.delete(i)

		# Chaque ligne du tableau reçoit un identifiant unique
		# Pour une ligne mère: l'identifiant est le nom de classe
		# Pour une ligne fille: nom de classe underscore numéro d'image (elles sont simplement numérotés dans l'ordre le lecture)
		for classe in sorted(reseau.classes):
			nb = len(reseau.echantillons[classe])
			self.explorateur.insert("", "end", classe, text = classe, values = (str(nb), ))
			for i in range(nb):
				self.explorateur.insert(classe, "end", classe+"_"+str(i), text = "Image "+str(i+1))

		for widget in self.info_explorateur.winfo_children(): widget.destroy() # On vide l'encart informations
		for (cle, valeur) in self.infos_reseau():
			label = ttk.Label(self.info_explorateur, text = cle+": "+str(valeur))
			label.pack()


	def explorateur_selection_changee(self, event):

		"""Appelée chaque fois que la sélection de l'explorateur, eh bien, change..."""

		reseau = self.reseau()
		selection = self.explorateur.focus()

		if "_" in selection: # C'est une fille! \o/
			classe, image = selection.split("_") # Voir maj_barre_laterale 
			image = int(image)
		else:
			classe = selection
			image = None
		
		# On remplit les infos
		for widget in self.info_explorateur.winfo_children(): widget.destroy() # On vide l'encart informations
		for (cle, valeur) in  self.infos_reseau() + [("Nom", classe), ("Vecteur", str(reseau.representation(classe))), ("Échantillons", len(reseau.echantillons[classe]))]:
			label = ttk.Label(self.info_explorateur, text = cle+": "+str(valeur))
			label.pack()

		# Si image == None, on a sélectionné une ligne mère, on affiche donc un bouton 'Supprimer' pour supprimer la classe
		if image is None:

			def supprimer(classe):
				reseau.enlever_classe(classe)
				self.fichier_modifie()

			ttk.Button(self.info_explorateur, text = "Supprimer", command = lambda *args, classe = classe: supprimer(classe)).pack(padx = 5, pady = 5)

		# Sinon, on affiche un bouton pour exporter l'image, et un pour supprimer l'image
		else:

			index = image
			image = reseau.image(classe, index)

			command = lambda *args, image = image: PopupImage(image = image, background = "white")
			label_image = LabelImage(self.info_explorateur, image = image)
			label_image.bind("<Button-1>", command)
			label_image.pack()

			def sauver(image):
				chemin = filedialog.asksaveasfilename()
				if chemin is not None and chemin != "":
					image.save(chemin)

			def supprimer(classe, index):
				reseau.enlever_echantillon(classe, index)
				self.fichier_modifie()

			ttk.Button(self.info_explorateur, text = "Exporter", command = lambda *args, image = image: sauver(image)).pack(padx = 5, pady = 5)

			ttk.Button(self.info_explorateur, text = "Supprimer échantillon", command = lambda *args, index = index, classe = classe: supprimer(classe, index)).pack(padx = 5, pady = 5)


class Onglet(ttk.Frame):

	"""Objet Onglet, c'est un widget avec quelques méthodes prédéfinies à réimplémenter éventuellement"""

	def __init__(self, parent, app, nom):

		self.app = app
		self.nom = nom
		self.root = self.app.root
		self.parent = parent
		self.reseau = self.app.reseau().copier()
		ttk.Frame.__init__(self, parent)
		parent.add(self, text = self.nom)
		self.visible = True
		app.onglets.append(self)

	def toggle(self):

		if not self.visible:
			self.parent.add(self, text = self.nom)
		else:
			self.parent.forget(self)
		self.visible = not self.visible

	def action_principale(self):

		"""Une action à activer au moment de l'appui sur la touche entrée"""

		pass

	def separation(self):

		"""Un petit raccourci pour afficher une barre horizontale de séparation"""

		ttk.Separator(self, orient = "horizontal").pack(fill = "x", padx = 15, pady = 15)

	def actualiser_fichier(self):

		"""Appelée lorsque le fichier est modifié. Pour exécuter une action à chaque changement, réimplémenter Onglet.changement_fichier"""

		self.reseau = self.app.reseau().copier()
		self.changement_fichier()

	def changement_fichier(self):

		"""Fonction à réécrire au besoin pour chaque onglet, elle est appelée chaque fois que le fichier change"""

		pass

	def fichier_modifie(self):

		"""Signale à l'application que l'on a modifié le réseau"""

		self.app.modif_reseau(self.reseau)
		self.app.fichier_modifie()


class OptionsEntrainement(ttk.LabelFrame):

	def __init__(self, parent, reset = True, taux_app = 0.1, inertie = 0.8):

		ttk.LabelFrame.__init__(self, parent, text = "Options")

		self.reset = BooleanVar()
		self.reset.set(reset)
		check = ttk.Checkbutton(self, text = "Réinitialiser les neurones", variable = self.reset)
		check.grid(column = 0, row = 0, columnspan = 2, padx = 5)

		self.validation = BooleanVar()
		self.validation.set(True)
		check = ttk.Checkbutton(self, text = "Utiliser validation", variable = self.validation)
		check.grid(column = 0, row = 1, columnspan = 2, padx = 5)

		l1 = ttk.Label(self, text = "Taux d'apprentissage:")
		l1.grid(column = 0, row = 2, padx = 5)
		l1.bind("<Button-1>", self.aide_taux_app)
		self.taux_app = DoubleVar()
		self.taux_app.set(taux_app)
		spinbox = Spinbox(self, from_ = 0.0, to = 1.0, increment = 0.01, width = 5, textvariable = self.taux_app)
		spinbox.grid(column = 1, row = 2, padx = 5)

		l2 = ttk.Label(self, text = "Inertie:")
		l2.grid(column = 0, row = 3, padx = 5)
		l2.bind("<Button-1>", self.aide_inertie)
		self.inertie = DoubleVar()
		self.inertie.set(inertie)
		spinbox = Spinbox(self, from_ = 0.0, to = 1.0, increment = 0.01, width = 5, textvariable = self.inertie)
		spinbox.grid(column = 1, row = 3, padx = 5)

	def aide_taux_app(self, event):

		messagebox.showinfo("Taux d'apprentissage", "Le taux d'apprentissage contrôle l'impact des corrections de l'algorithme d'entraînement. Plus le taux est important, plus les corrections apportées à un neurone seront importantes.")

	def aide_inertie(self, event):

		messagebox.showinfo("Inertie", "À chaque correction d'un neurone, la correction précédente est appliquée à nouveau à un facteur près, l'inertie. Une inertie égale à 1 applique intégralement la correction précédente. Une inertie nulle annule complètement l'effet d'inertie.")

	def get(self):

		return {
			"reset": self.reset.get(),
			"validation": self.validation.get(),
			"taux_app": self.taux_app.get(),
			"inertie": self.inertie.get(),
		}


class MethodeDecoupage(ttk.Frame):

	def __init__(self, parent, decoupage = "pas_decoupage"):

		# Les champs 'value' sont importants dans la suite, c'est la valeur renvoyée par self.decoupage.get()
		self.decoupage = StringVar()
		ttk.Frame.__init__(self, parent)
		ttk.Label(self, wraplength = "400", text = "Découpage:", anchor = "w").pack(padx = 5, side = "left")
		ttk.Radiobutton(self, text = "Aucun", variable = self.decoupage, value = "pas_decoupage").pack(padx = 5, side = "left")
		ttk.Radiobutton(self, text = "En colonnes", variable = self.decoupage, value = "colonne").pack(padx = 5, side = "left")
		ttk.Radiobutton(self, text = "Précis", variable = self.decoupage, value = "precis").pack(padx = 5, side = "left")
		self.decoupage.set(decoupage)

	def get(self):

		methode_decoupage = {
			"pas_decoupage": False,
			"colonne": ImageBinaire.decouper_verticalement,
			"precis": ImageBinaire.decouper2,
		}
		return methode_decoupage[self.decoupage.get()]


class StructureReseau(Onglet):

	def changement_fichier(self):

		x, y = self.reseau.grille
		self.grille_x.set(x)
		self.grille_y.set(y)

		s = ", ".join([str(len(c)) for c in self.reseau.couches_internes()])
		self.structure.set(s)

		s = ", ".join(sorted(self.reseau.classes))
		self.caracs.set(s)

		self.codage.set(self.reseau.codage)

	def __init__(self, parent, app):

		Onglet.__init__(self, parent, app, "Structure du réseau")

		ttk.Label(self, wraplength = "400", text = "Couche d'entrée", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)
		ttk.Label(self, wraplength = "400", text = "Définit la grille utilisée pour convertir les images entrées en vecteurs, par exemple, une grille (3, 5) convertit les images en vecteurs à 15 composantes.", anchor = "w").pack(padx = 5, pady = 5)

		f = ttk.Frame(self)
		f.pack(padx = 5, pady = 5)

		ttk.Label(f, text = "Grille:").pack(side = "left", padx = 5, pady = 5)

		self.grille_x = IntVar()
		self.grille_x.set(3.0)
		spinbox = Spinbox(f, from_ = 1.0, to = 10.0, width = 5, textvariable = self.grille_x)
		spinbox.pack(side = "left", padx = 5, pady = 5)

		self.grille_y = IntVar()
		self.grille_y.set(5.0)
		spinbox = Spinbox(f, from_ = 1.0, to = 10.0, width = 5, textvariable = self.grille_y)
		spinbox.pack(side = "left", padx = 5, pady = 5)

		ttk.Button(f, text = "OK", command = self.couche_entree).pack(padx = 5, pady = 5, side = "left")

		self.separation()

		ttk.Label(self, wraplength = "400", text = "Couches internes", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)
		ttk.Label(self, wraplength = "400", text = "Entrez la taille de chaque couche interne successive, séparées par des virgules, exemple: '3, 4, 5' va créer trois couches internes de tailles respectives 3, 4 et 5.", anchor = "w").pack(padx = 5, pady = 5)

		f = ttk.Frame(self)
		f.pack(padx = 5, pady = 5)
		self.structure = StringVar()
		entry = ttk.Entry(f, textvariable = self.structure)
		entry.pack(padx = 5, pady = 5, side = "left")
		ttk.Button(f, text = "OK", command = self.couches_internes).pack(padx = 5, pady = 5, side = "left")

		self.separation()

		ttk.Label(self, wraplength = "400", text = "Couche de sortie", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)
		ttk.Label(self, wraplength = "400", text = "Entrez une liste de caractères à reconnaître séparés par des virgules.", anchor = "w").pack(padx = 5, pady = 5)

		f = ttk.Frame(self)
		f.pack(padx = 5, pady = 5)

		self.caracs = StringVar()
		entry = ttk.Entry(f, textvariable = self.caracs)
		entry.grid(column = 0, row = 0, columnspan = 2, padx = 5, pady = 5, sticky = E+W)

		ttk.Label(f, text = "Codage:").grid(column = 0, row = 1, padx = 5, pady = 5)
		self.codage = StringVar()
		combo = ttk.Combobox(f, textvariable = self.codage)
		combo.grid(column = 1 , row = 1, padx = 5, pady = 5)
		combo["values"] = list(Reseau.codages.keys())

		ttk.Button(f, text = "OK", command = self.couche_sortie).grid(column = 2, row = 0, rowspan = 2, padx = 5, pady = 5)

		self.changement_fichier()


	def couche_entree(self):

		x, y = int(self.grille_x.get()), int(self.grille_y.get())
		self.reseau.grille = (x, y)
		self.reseau.initialiser((x, y))
		self.fichier_modifie()

	def couches_internes(self):

		# On enlève tout
		for couche in self.reseau.couches_internes():
			self.reseau.enlever_couche(couche)

		structure = self.structure.get()
		if structure is not "":
			for taille in structure.split(","):
				taille = int(taille.strip()) # strip() enlève les espaces, comme ça on peut lire aussi bien 'a,b,c' que 'a, b, c' ou encore 'a,b, c'
				self.reseau.ajout_couche(taille)

		# Il faut absolument réinitialiser après ce genre de modifications, puisque la taille des neurones est déterminée par la taille des couches précédentes
		self.reseau.initialiser(self.reseau.grille)
		self.fichier_modifie()

	def couche_sortie(self):

		self.reseau.utiliser_codage(self.codage.get())

		for classe in self.reseau.classes[:]:
			self.reseau.enlever_classe(classe)

		for classe in self.caracs.get().split(","):
			classe = classe.strip() # strip() enlève les espaces, comme ça on peut lire aussi bien 'a,b,c' que 'a, b, c' ou encore 'a,b, c'
			self.reseau.ajout_classe(classe)

		# Il faut absolument réinitialiser après ce genre de modifications, puisque la taille des neurones est déterminée par la taille des couches précédentes
		self.reseau.initialiser(self.reseau.grille)
		self.fichier_modifie()


class Apprentissage(Onglet):

	def __init__(self, parent, app):

		Onglet.__init__(self, parent, app, "Apprentissage")

		self.echantillons()
		self.separation()
		self.entrainement()

		self.time = 0
		self.delta = 0

		self.action_principale = self.ajout_echantillon

	def echantillons(self):

		ttk.Label(self, wraplength = "400", text = "Échantillons", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)

		ttk.Label(self, wraplength = "400", text = "Interpréter l'échantillon comme la chaîne suivante (si la chaîne comporte des caractères inexistants, les classes associées seront créées automatiquement):", anchor = "w").pack(padx = 5, pady = 5)

		f = ttk.Frame(self)
		f.pack(padx = 5, pady = 5)
		self.chaine = StringVar()
		self.entry = entry = ttk.Entry(f, textvariable = self.chaine)
		entry.pack(padx = 5, pady = 5, side = "left")
		ttk.Button(f, text = "OK", command = self.ajout_echantillon).pack(padx = 5, pady = 5, side = "left")

		# Les champs 'value' sont importants dans la suite, c'est la valeur renvoyée par self.decoupage.get()
		self.decoupage = MethodeDecoupage(self)
		self.decoupage.pack(padx = 5, pady = 5)


	def entrainement(self):

		frame = ttk.Frame(self)
		frame.pack(padx = 5, pady = 5, fill = "x")

		l = ttk.Label(frame, wraplength = "300", text = "Apprentissage", font = "TkDefaultFont 9 bold", anchor = "w")
		l.grid(columnspan = 3, column = 1, row = 0, padx = 5, pady = 5)
		ttk.Label(frame, wraplength = "300", text = "Entraîner les neurones sur l'ensemble des échantillons, jusqu'à ce qu'ils soient interprétés correctement.", anchor = "w").grid(columnspan = 3, column = 1, row = 1, padx = 5, pady = 5)

		lancer = ttk.Button(frame, text = "Commencer", command = self.entrainer)
		lancer.grid(column = 1, row = 2, padx = 5, pady = 5)

		l = ttk.Label(frame, text = "Max. cycles:")
		l.grid(column = 2, row = 2, padx = 5, pady = 5)
		self.max_cycles = IntVar()
		self.max_cycles.set(100)
		spinbox = Spinbox(frame, from_ = 1, to = 10000, increment = 1, width = 4, textvariable = self.max_cycles)
		spinbox.grid(column = 3, row = 2, padx = 5, pady = 5)

		stop = ttk.Button(frame, text = "Stopper l'apprentissage", command = self.stopper)
		stop.grid(column = 1, row = 3, padx = 5, pady = 5, columnspan = 3)

		self.options = OptionsEntrainement(frame)
		self.options.grid(column = 0, row = 0, rowspan = 5, padx = 5, pady = 5)

		self.graphe = Graphe(self)
		self.graphe.widget().pack(padx = 5, pady = 5, fill = "both", expand = "yes")

		menu = self.app.ajout_menu_clic(self.graphe.widget())
		menu.add_command(label = "Exporter graphe", command = self.texport)


	def texport(self):

		donnees = self.graphe.donnees_brutes()

		if len(donnees):

			chemin = filedialog.asksaveasfilename(filetypes = (("PDF", "*.pdf"), ("Données brutes", "*.json")))

			if chemin is not None:

				options = self.options.get()
				taux_app = float(options["taux_app"])
				inertie = float(options["inertie"])
				delta = round(self.delta, 1)
			
				if chemin.endswith(".pdf"):

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

						plt.savefig(chemin)

				elif chemin.endswith(".json"):

					donnees = [(nom, x.tolist(), y.tolist()) for (nom, x, y) in donnees]
					new_donnees = {
						"graphes": donnees,
						"taux_app": taux_app,
						"inertie": inertie,
						"delta": delta,
					}
					with open(chemin, "w+") as fichier:
						json.dump(new_donnees, fichier)


	def stopper(self): 

		self.stop = True

	def ajout_echantillon(self):

		chaine = self.chaine.get()

		if chaine != "": # Si l'utilisateur a rempli le champ échantillons

			image = self.app.image()
			decoupage = self.decoupage.get()
			liste = [image]
			if decoupage is not False:
				liste = [ImageBinaire.depuis_liste(carac) for carac in decoupage(image)]

			if len(liste) != len(chaine):

				messagebox.showerror("Erreur", "Le nombre de caractères ne semble pas correspondre.")

			else:

				for image, classe in zip(liste, chaine): # zip() colle les deux listes
					self.reseau.ajout_classe(classe) # Au cas où la classe n'existe pas!
					self.reseau.ajout_echantillon(classe, image) 

				self.fichier_modifie()
				self.app.dessin.effacer()

		else:

			messagebox.showerror("Erreur", "Chaîne vide.")


	def entrainer(self):

		self.stop = False

		try:

			options = self.options.get()
			taux_app = options["taux_app"]
			inertie = options["inertie"]
			validation = options["validation"]

			self.graphe.effacer()
			courbe1 = self.graphe.nouvelle_courbe("Erreur moyenne")
			if validation:
				courbe2 = self.graphe.nouvelle_courbe("Erreur de validation")

			if options["reset"]:
				self.reseau.initialiser(self.reseau.grille)

			exemples, resultats = self.reseau.charger_echantillons()

			self.fichier_modifie()

			self.time = time.time()

			for cycle, (err, err_val) in enumerate(self.reseau.entrainer_cycle(exemples, resultats, taux_app = taux_app, inertie = inertie, validation = validation)):
				self.graphe.ajouter_point(courbe1, cycle, err)
				if validation: self.graphe.ajouter_point(courbe2, cycle, err_val)
				self.root.update()
				if self.stop or cycle == int(self.max_cycles.get()):
					self.delta = time.time() - self.time
					self.fichier_modifie()
					break

			messagebox.showinfo("Terminé", "Apprentissage terminé!")


		except:


			messagebox.showerror("Erreur", "L'apprentissage a rencontré une erreur: {}".format(traceback.format_exc()))
			print(traceback.format_exc())



class Reconnaissance(Onglet):

	def __init__(self, parent, app):

		Onglet.__init__(self, parent, app, "Reconnaissance")

		ttk.Label(self, wraplength = "400", text = "Reconnaissance", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)
		ttk.Label(self, wraplength = "400", text = "Tenter une reconnaissance de texte, en utilisant la méthode de découpage sélectionnée. Le découpage en colonne nécessite des caractères séparés par au moins une colonne de pixels blancs. Si vous choisissez de ne pas utiliser de découpage, l'image sera interprétée comme un unique caractère!", anchor = "w").pack(padx = 5, pady = 5)

		self.decoupage = MethodeDecoupage(self)
		self.decoupage.pack(padx = 5, pady = 5)

		f = ttk.Frame(self)
		f.pack(padx = 5, pady = 5)
		l = ttk.Label(f, text = "Erreur maximale:")
		l.pack(side = "left", padx = 5)
		self.seuil = DoubleVar()
		self.seuil.set(1)
		spinbox = Spinbox(f, from_ = 0, to = 5, increment = 0.1, width = 5, textvariable = self.seuil)
		spinbox.pack(side = "left", padx = 5)

		f = ttk.Frame(self)
		f.pack(padx = 5, pady = 5)
		self.eff = BooleanVar()
		self.eff.set(True)
		ttk.Button(f, text = "Reconnaître", command = self.reconnaissance).pack(padx = 5, pady = 5, side = "left")
		ttk.Checkbutton(f, text = "Effacer dessin ensuite", variable = self.eff).pack(padx = 5, pady = 5, side = "left")

		self.separation()

		self.resultat = StringVar()
		self.resultat.set("...")

		ttk.Label(self, wraplength = "400", text = "Résultats", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)
		Label(self, wraplength = "300", textvariable = self.resultat, bg = "white", font = "TkDefaultFont 18 normal", anchor = "w").pack(padx = 20, pady = 20)


		self.action_principale = self.reconnaissance

	def reconnaissance(self):

		self.resultat.set("...")
		image = self.app.image()
		decoupage = self.decoupage.get()
		seuil = self.seuil.get()
		chaines = self.reseau.reconnaitre_chaine(image, decoupage, seuil)
		self.resultat.set(", ".join(chaines))

		if self.eff.get():
			self.app.dessin.effacer()


class DetailImage(Canvas):

	"""Affiche une image pour accompagner le GrapheReseau"""

	def __init__(self, parent):

		Canvas.__init__(self, parent)
		self.configure(highlightthickness = 0, width = 100, height = 0)
		self.bind("<Configure>", self.maj_taille)

		self._image = None
		self.image = None

	def maj_taille(self, event):

		self.config(height = event.height)

	def taille(self):

		return self.winfo_reqwidth(), self.winfo_reqheight()

	def afficher_image(self, image, grille):

		self.grille = grille
		
		wi, hi = image.size
		w, h = self.taille()
		ratio = min(w/wi, h/hi)
		image = image.resize((int(wi*ratio), int(hi*ratio)))
		wi, hi = image.size

		y0 = (h-hi)/2
		self._image = image
		self.image = ImageTk.PhotoImage(image)
		self.delete("image")
		self.create_image((0, y0), anchor = "nw", image = self.image, tags = "image", state = "hidden")

	def masquer_image(self):

		self.delete("image")
		self._image = None
		self.image = None

	def afficher_case(self, x, y):

		if self._image is not None:

			self.itemconfig("image", state = "normal")

			w, h = self.taille()
			wi, hi = self._image.size
			gx, gy = self.grille

			self.delete("detail")
			x0, y0 = 0 + x*wi/gx, (h-hi)/2 + y*hi/gy
			self.create_rectangle((x0, y0, x0 + wi/gx, y0 + hi/gy), outline = "red", tags = "detail")

	def masquer_case(self):

		self.delete("detail")
		self.itemconfig("image", state = "hidden")


class GrapheReseau(Canvas):

	"""Un graphe de représentation du réseau"""

	def __init__(self, parent, root):

		Canvas.__init__(self, parent)
		self.configure(highlightthickness = 0, width = 300, height = 300)
		self.bind("<Configure>", self.maj_taille)
		self.addtag_all("all")
		self.root = root

		w, h = self.taille = self.winfo_reqwidth(), self.winfo_reqheight()

		self.tag_bind("neurone", "<Enter>", self.neurone_actif) # On surveille le survol des neurones dessinés
		self.tag_bind("texte", "<Enter>", self.neurone_actif) # Ou de leur texte (dernière couche)
		self.tag_bind("neurone", "<Leave>", self.neurone_plus_actif)
		self.tag_bind("texte", "<Leave>", self.neurone_plus_actif)

		self.tag_bind("entree", "<Enter>", self.entree_actif)
		self.tag_bind("entree", "<Leave>", self.entree_plus_actif)

		# On met en écoute les événements liés à l'utilisation de la molette, pour le zoom
		self.bind("<MouseWheel>", self.zoom)
		# Pour Linux, il faut ajouter d'autres évenements: http://stackoverflow.com/questions/17355902/python-tkinter-binding-mousewheel-to-scrollbar
		self.bind("<Button-4>", self.zoom) 
		self.bind("<Button-5>", self.zoom)

		# Source: http://stackoverflow.com/questions/20645532/move-a-tkinter-canvas-with-mouse
		self.bind("<ButtonPress-1>", self.scroll_start)
		self.bind("<B1-Motion>", self.scroll_move)

		self.donnees = {}

	def scroll_start(self, event):

		self.scan_mark(event.x, event.y)

	def scroll_move(self, event):

		self.scan_dragto(event.x, event.y, gain = 1)

	def zoom(self, event):

		"""Change l'épaisseur de tracé et actualise le curseur s'il existe (appelé lors d'un défilement molette)"""
		
		# L'événement <MouseWheel> fourni un delta, qui vaut 120 ou -120, ce qui nous intéresse est essentiellement le signe de ce delta qui indique le sens de rotation de la molette
		delta = event.delta
		# Adaptations pour Linux: on regarde le numéro de l'événement car la molette est interprétée comme deux boutons supplémentaires de la souris (4 et 5)
		if event.num == 5:
			delta = -120
		elif event.num == 4:
			delta = 120

		sc = 1-delta/1200
		self.scale("all", event.x, event.y, sc, sc)

	# Adapté de http://stackoverflow.com/questions/22835289/how-to-get-tkinter-canvas-to-dynamically-resize-to-window-width
	def maj_taille(self, event):

		"""Adapte la taille du graphe à l'espace disponible, en conservant le ratio"""

		w, h = self.taille
		nw, nh = event.width, event.height

		n = min(nw, nh)
		sc = max(n/w, n/h)

		self.taille = event.width, event.height

		self.config(width = nw, height = nh)
		self.scale("all", 0, 0, sc, sc)

	def find_withtags(self, tags):

		"""Amélioration de Canvas.find_withtag, qui sélectionne les items ayant l'ensemble des 'tags'"""

		all = None
		for tag in tags:
			items = Canvas.find_withtag(self, tag)
			if all is None:
				all = set(items)
			else:
				all = set(items) & all # Intersection
		return tuple(all)

	def itemconfig(self, item, **kwargs):

		"""Petit hack pour les performances: on décale les appels de itemconfig (nombreux) d'une durée très courte"""

		self.root.after(5, lambda: Canvas.itemconfig(self, item, **kwargs))

	def center(self, item):

		"""Renvoie le milieu d'un objet"""

		x1, y1, x2, y2 = self.bbox(item)
		return ((x1+x2)/2, (y1+y2)/2)

	def add_datatag(self, item, **data):

		"""Ajouter des tags avec valeur numérique"""

		for key, value in data.items():
			value = float(value)
			tag = "data_{}_{}".format(key, value)
			self.addtag_withtag(tag, item)

	def get_data(self, item):

		"""Renvoie un dictionnaire avec clé: valeur numérique"""

		data = {}
		for tag in self.gettags(item):
			if tag.startswith("data_"):
				_, key, value = tag.split("_")
				data[key] = float(value)
		return data

	def get_datatags(self, item):

		"""Comme get_data mais sous forme de tags"""

		return self.as_tags(**self.get_data(item))

	def as_tags(self, **data):

		"""Convertit un ensemble clé: valeur numérique en datatags"""

		tags = []
		for key, value in data.items():
			value = float(value)
			tag = "data_{}_{}".format(key, value)
			tags.append(tag)
		return tags

	def neurone_actif(self, event):

		"""Appelé au survol d'un neurone"""

		item = self.find_withtag("current")
		data = self.get_datatags(item)

		# On met en rouge et on épaissit toutes les connexions
		lines = self.find_withtags(data + ["connexion"])
		for line in lines:
			self.itemconfig(line, fill = "red", width = 2)
			# self.tag_raise(line)

		# On affiche les valeurs des poids des connexions
		textes = self.find_withtags(data + ["poids"])
		for poids in textes:
			self.itemconfig(poids, state = "normal")
			self.tag_raise(poids) # On les mets au dessus aussi!


	def neurone_plus_actif(self, event):

		"""Appelé quand le survol d'un neurone cesse"""

		# On remet les connexions en gris
		lines = self.find_withtag("connexion")
		for line in lines:
			self.itemconfig(line, fill = "#AAA", width = 1)

		# On masque les textes
		textes = self.find_withtag("poids")
		for poids in textes:
			self.itemconfig(poids, state = "hidden")

	def visualiser(self, vecteur):

		"""Affiche les sorties de chaque neurone du réseau sur le graphe, pour l'entrée 'vecteur'"""

		self.delete("sortie") # On supprime les items taggés "sortie" (= la visualisation précédente)
		
		gx, gy = self.reseau.grille
		sorties = self.reseau.sortie(vecteur)
		entrees, sorties = sorties[0][:-1], sorties[1:]

		for i, entree in enumerate(entrees):

			x, y = i%gx, i//gx
			boite = self.find_withtags(self.as_tags(x = x, y = y) + ["entree"])
			entree = str(round(entree, 2)) # On réduit le nombre de décimales
			t = self.create_text(self.center(boite), text = entree, font = ("TkDefaultFont", 12), tags = ("sortie", "entree"))
			self.add_datatag(t, x = x, y = y)

		for c, couche in enumerate(sorties):

			if c != len(sorties)-1: 
				couche = couche[:-1]

			for n, sortie in enumerate(couche):

				neurone = self.find_withtags(self.as_tags(couche = c, num = n) + ["neurone"]) # On recupère l'item neurone correspondant à la sortie c,n
				color = "red" if (c == len(sorties)-1) and abs(sortie - max(couche)) < 0.01 and self.reseau.codage == "simple" else "black" # Coloration du texte
				sortie = str(round(sortie, 2)) # On réduit le nombre de décimales
				x, y = self.center(neurone) # Position du texte
				self.create_text((x + self.t_rond, y), anchor = "w", text = sortie, fill = color, font = ("TkDefaultFont", 12), tags = "sortie")

	def dessiner(self, reseau):

		"""Dessine un réseau sur le graphe"""

		self.delete("all") # On détruit tout >:)
		self.reseau = reseau # On le garde en mémoire
		tx, ty = reseau.grille
		w, h = self.taille # Taille du widget

		# Tailles relatives: tout est mis à l'échelle
		self.t_rond = t_rond = 15
		self.t_case = t_case = 15
		marge = 10
		espace_y = 5
		nbx, nby = self.format = len(reseau), max([len(couche) for couche in reseau] + [tx*ty]) # Nombres max de neurones verticalement et horizontalement
		
		h_d = t_rond*nby + espace_y*(nby-1) + 2*marge # Hauteur du dessin
		w_d = w*h_d/h # Largeur du dessin
		espace_x = min((w_d - (t_rond*nbx + 2*marge + t_case))/(nbx), 100)

		fleche_bbox = [] # Liste définie par récurrence, qui contient les coordonnées des attaches côté gauche pour les flèches entre deux couches

		# Dessin de la grille
		for y in range(ty):

			for x in range(tx):

				extra_y = h_d - (tx*ty*t_case + 2*marge)
				x0, y0 = marge, extra_y/2 + marge + x*t_case + y*tx*t_case
				bbox = (x0, y0, x0 + t_case, y0 + t_case)

				entree = self.create_rectangle(bbox, fill = "white", activefill = "grey", tags = "entree")
				self.add_datatag(entree, x = x, y = y)

				fleche_bbox.append((x0 + t_case, y0 + t_case/2))

		for c, couche in enumerate(reseau):

			new_fleche_bbox = [] # Future fleche_bbox
			extra_y = (h_d - (t_rond*len(couche)) - (espace_y*(len(couche)-1)) - 2*marge) # Espace supplémentaire vertical, couche par couche

			for n, neurone in enumerate(couche):

				x0, y0 = marge + t_case + (c+1)*espace_x + c*t_rond, marge + extra_y/2 + n*espace_y + n*t_rond # Position du coin inférieur gauche
				bbox = (x0, y0, x0 + t_rond, y0 + t_rond) # Boite qui contient le neurone tracé

				oval = self.create_oval(bbox, fill = "white", activefill = "grey", tags = "neurone") # Le neurone
				self.add_datatag(oval, couche = c, num = n)

				# Si c'est la dernière couche on écrit les sorties du réseau
				if c == len(reseau)-1 and reseau.codage == "simple":
					texte = self.create_text((x0 + t_rond/2, y0 + t_rond/2), text = reseau.classes[n], font = ("TkDefaultFont", 15), tags = "texte")
					self.add_datatag(texte, couche = c, num = n)

				# Tracé des flèches
				if len(fleche_bbox):

					for poids, (x, y) in zip(neurone, fleche_bbox):

						# On trace la ligne à partir des coordonnées précédentes dans fleche_bbox et des coordonnées du neurone de ce tour de boucle
						line = self.create_line((x, y, x0, y0 + t_rond/2), fill = "#AAA", width = "0.5", tags = "connexion")
						self.add_datatag(line, couche = c, num = n)
						
						# On écrit aussi les poids, mais cachés
						milieu = (x0 + x)/2, (y0 + t_rond/2 + y)/2
						poids = str(round(poids, 2))
						texte = self.create_text(milieu, text = poids, state = "hidden", font = ("TkDefaultFont", 15), tags = "poids")
						self.add_datatag(texte, couche = c, num = n)

				# On passe les coordonnées de nos neurones à la couche suivante!
				new_fleche_bbox.append((x0 + t_rond, y0 + t_rond/2))

			fleche_bbox = new_fleche_bbox

		# On fait croire à la fonction en charge de mettre à l'échelle (appelée par l'event <Configure>) que notre canvas est à la taille du dessin, et qu'il doit donc être réduit
		self.taille = w_d, h_d
		self.root.event_generate("<Configure>")

	def entree_actif(self, event):

		item = self.find_withtag("current")
		data = self.get_data(item)
		self.event_generate("<<EntreeActif>>", **data)

	def entree_plus_actif(self, event):

		self.event_generate("<<EntreePlusActif>>")


class GrapheInterractif(Onglet):

	def __init__(self, parent, app):

		Onglet.__init__(self, parent, app, "Graphe")

		ttk.Label(self, wraplength = "400", text = "Graphe", font = "TkDefaultFont 9 bold", anchor = "w").pack(padx = 5, pady = 5)
		ttk.Label(self, wraplength = "400", text = "Visualisation des connexions entre neuronnes et du fonctionnement du réseau. Risque de crash pour des réseaux trop grands!!", anchor = "w").pack(padx = 5, pady = 5)
		ttk.Button(self, text = "Tester", command = self.reconnaissance).pack(padx = 5, pady = 5)

		self.separation()

		f = ttk.Frame(self)
		f.pack(fill = "both", expand = "yes")

		self.graphe = GrapheReseau(f, self.root)
		self.graphe.pack(side = "left", fill = "both", expand = "yes")
		self.graphe.bind("<<EntreeActif>>", self.detail_afficher)
		self.graphe.bind("<<EntreePlusActif>>", self.detail_cacher)

		self.detail = DetailImage(f)
		self.detail.pack(side = "left", expand = "yes", fill = "both", padx = 20)

		self.action_principale = self.reconnaissance

	def detail_afficher(self, event):

		item = self.detail.afficher_case(event.x, event.y)

	def detail_cacher(self, event):

		self.detail.masquer_case()

	def reconnaissance(self):

		image = self.app.image()
		image.recentrer()
		vecteur = image.proportions(self.reseau.grille)

		self.detail.afficher_image(image, self.reseau.grille)
		self.graphe.visualiser(vecteur)

	def changement_fichier(self):

		self.graphe.dessiner(self.reseau)
		self.detail.masquer_image()

		
if __name__ == "__main__": # Si le script est exécuté, et non importé

	root = Tk()

	# Ajoute des arguments en ligne de commande, pour plus d'infos, exécuter les commandes suivantes dans Pyzo:
	# %cd /dossier/contenant/le/programme
	# %run ui.py --help
	import argparse
	parser = argparse.ArgumentParser(description = "Éditer des réseaux de neurones artificiels.")
	parser.add_argument("fichier", nargs = "?", default = None, help = "un fichier à ouvrir")
	parser.add_argument("-t", "--theme", choices = list(ttk.Style().theme_names())+["custom"], help = "thème Tkinter à utiliser")
	args = parser.parse_args()

	app = Application(root)
	if args.theme is not None: app.changer_theme(args.theme)
	if args.fichier is not None: app.ouvrir(args.fichier)
	root.mainloop()
	exit()
