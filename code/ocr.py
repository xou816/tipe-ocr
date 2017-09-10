# https://pillow.readthedocs.org/ pip install pillow
from PIL import Image

# Pour algorithmes
import math
import numpy as np
import random

# Pour sauvegardes dans des fichiers
import json
import io
import zipfile
import base64
import os


class ImageBinaire:

	"""Classe pour manipuler les images en noir et blanc"""

	def __init__(self, img):

		# On ne peut malheureusement pas hériter de la classe Image de PIL, il faut donc garder en mémoire une image PIL sur laquelle on travaille (voir également __getattr__)

		self._img = img

	def __getattr__(self, key):

		# Si une méthode n'est pas implémentée par ImageBinaire, on appelle cette méthode sur l'image interne PIL: cela évite d'avoir a réecrire toutes les méthodes d'image de PIL"""

		if key == "_img": raise AttributeError() # Evite les récursions infinies, à priori
		return getattr(self._img, key)

	def new(size, color = 0):

		"""Créer une nouvelle ImageBinaire"""

		return ImageBinaire(Image.new("1", size, color)) # Mode 1: noir+blanc

	def rotate(self, angle, resample = 0, expand = 0):

		"""Retourne une image d'un angle donné (modification en place)"""

		# Cette méthode gère correctement la rotation pour des angles non multiples de 90°, qui posent problème

		if angle%90 == 0: # Pas de problème de fond, on applique juste la rotation classique
			self._img = self._img.rotate(angle, resample, expand)
		else:
			# Voir http://stackoverflow.com/questions/5252170/specify-image-filling-color-when-rotating-in-python-with-pil-and-setting-expand
			rgba = self._img.convert("RGBA") # En RGBA, l'image sera retournée sur un fond transparent
			rot = rgba.rotate(angle, resample, expand)
			fond_blanc = Image.new("RGBA", rot.size, (255,)*4)
			finale = Image.composite(rot, fond_blanc, rot) # On colle notre image RGBA sur le fond blanc
			finale = finale.convert("1") # On repasse en noir+blanc
			self._img = finale

	def open(file, mode = "r", seuil = 128):

		"""Ouvre une image et la convertit en ImageBinaire si ce n'en est pas une"""

		img = Image.open(file, mode)
		if img.mode == "1": # Si le mode est déjà binaire, pas besoin de convertir
			return ImageBinaire(img)
		return ImageBinaire.depuis_image(img, seuil)

	def depuis_image(img, seuil = 128):

		"""Fonction convertissant l'image au format binaire (pixels noirs et blancs uniquement), avec un seuil de luminosité"""

		# Voir http://stackoverflow.com/questions/18777873/convert-rgb-to-black-or-white
		# Principe: la fonction point() applique une fonction à l'ensemble des pixels d'un canal (R, G, ou B). Ici, on commence par convertir l'image en nuance de gris (mode "L"), ainsi il n'y à plus qu'un canal et on peut directement appliquer point().

		if img.mode == "RGBA": # Les pixels transparents sont parfois interprétés comme pixels noirs... embêtant!
			img2 = Image.new("RGB", img.size, (255, 255, 255))
			img2.paste(img, mask = img.split()[3]) # On colle les pixels non transparents de l'image RGBA sur un fond blanc
			img = img2
		img = img.convert("L")
		img = img.point(lambda x: 0 if x < seuil else 255, "1")
		return ImageBinaire(img)

	def depuis_liste(liste):

		"""Fonction créant une image binaire à partir d'une liste de pixels noirs"""

		x = lambda coord: coord[0]
		y = lambda coord: coord[1]
		x0, y0, x1, y1 = (min(liste, key = x)[0], min(liste, key = y)[1], max(liste, key = x)[0], max(liste, key = y)[1]) # On récupère les coins
		w, h = x1-x0+1, y1-y0+1 # On calcule la taille de l'image

		img = ImageBinaire.new((w, h), 1)
		for x, y in liste:
			img.putpixel((x-x0, y-y0), 0) # On écrit nos pixels

		return img

	def enlever_parasites(self, seuil):

		"""Fonction filtrant les "parasites" (comme les lignes d'une feuille à carreaux) de taille inférieure ou égale à un seuil"""
		# Inspiré de http://stackoverflow.com/questions/11253899/removing-the-background-noise-of-a-captcha-image-by-replicating-the-chopping-fil

		self.enlever_parasites_verticalement(seuil)
		self.enlever_parasites_horizontalement(seuil)

	def enlever_parasites_verticalement(self, seuil):

		"""Fonction filtrant les parasites verticalement"""

		# Approche naïve et un peu lente...

		w, h = self.size
		pix = self.load()
		noir, blanc = 0, 1

		y = -1
		while y < h-1: # On parcoure selon y...
			y += 1
			x = -1
			while x < w-1: # ...et selon x
				x += 1
				if pix[x, y] == noir: # Si on trouve un pixel noir
					total = 0 # On compte le nombre de pixels noirs à la suite:
					for x2 in range(x, w):
						if pix[x2, y] == noir:
							total += 1
						else:
							break
					if total <= seuil: # Si le total est inférieur au seuil, on enlève ces pixels: résultat, les petits groupes de pixels sont enlevés
						for c in range(total):
							pix[x+c, y] = blanc
					x += total

	def enlever_parasites_horizontalement(self, seuil):

		"""Fonction filtrant les parasites horizontalement"""

		self.rotate(90)
		self.enlever_parasites_verticalement(seuil)
		self.rotate(-90)

	def decouper_verticalement(self):

		"""Découpe une image verticalement et renvoie une liste contenant ses "caractères" sous forme de liste de coordonnées des pixels noirs. Les caractères peuvent être reconstruits à l'aide de ImageBinaire.depuis_liste"""

		w, h = self.size
		pix = self.load()
		noir, blanc = 0, 1

		caracs = []
		carac = []
		pause = False
		col_0 = 0 # col_0 et col_1 délimitent des caractères

		for x in range(w): # On parcoure chaque colonne

			col_1 = x # col_1

			for y in range(h): # On regarde chaque pixel de la colonne
				p = pix[x, y]
				if p == noir:
					carac.append((x, y)) # Sil un pixel est noir on ajoute les coordonées du pixel au caractère
					if not pause: # Si on est en train de chercher l'autre extrêmité d'un caractère (pause == false), on indique qu'il faut continuer
						col_1 = None
					else: # Sinon, on se trouve dans un espace entre deux caractères: un pixel noir signifie que l'on parcourt un nouveau caractère, on modifie la borne gauche (col_0)
						pause = False
						col_0 = x

			if x == w-1: col_1 = x # Bug sinon à la dernière itération

			if col_1 is not None and not pause: # Si on cherche la borne droite d'un caractère (pause == false) et si on a pas trouvé de pixels noirs dans cette colonne, alors on a un caractère!
				pause = True
				if col_1 - col_0 > 5: # On ne garde que les caractères suffisamment larges (parasites ignorés)
					caracs.append(carac)
					carac = []

		return caracs

	def decouper_horizontalement(self):

		"""Découpe une image horizontalement et renvoie une liste contenant ses "caractères" sous forme de liste"""

		# On utilise ImageBinaire.decouper_verticalement pour pas dupliquer les algorithmes...

		# On découpe verticalement l'image tournée de 90 degrés
		self.rotate(90)
		caracs = self.decouper_verticalement()
		self.rotate(-90)

		# On rétablit les coordonnées renvoyées par le découpage vertical
		nouv_caracs = []
		for carac in caracs:
			nouv_carac = []
			h = max([p[1] for p in carac]) - min([p[1] for p in carac])
			for x, y in carac:
				nouv_carac.append((h-y, x))
			nouv_caracs.append(nouv_carac)

		return nouv_caracs

	def _cases_autour(self, ax, ay):

		"""Fonction interne (voir ImageBinaire.decouper)"""

		cases = []
		w, h = self.size
		if ax != 0:
			cases.append([ax-1, ay])
		if ax+1 != w:
			cases.append([ax+1, ay])
		if ay != 0:
			cases.append([ax, ay-1])
		if ay+1 != h:
			cases.append([ax, ay+1])

		return cases

	def decouper(self):

		"""Sépare les groupes de pixels d'une image"""

		w, h = self.size
		pix = self.load()
		noir, blanc = 0, 1

		caracs = []

		for x in range(w):
			for y in range(h):
				liste = None
				if pix[x, y] == noir:
					verif = True
					for c in caracs:
						if [x, y] in c:
							verif = False
					if verif == True:
						liste = [[x, y]]
						for ax, ay in liste:
							for bx, by in self._cases_autour(ax, ay):
								if [bx, by] not in liste:
									if pix[bx, by] == noir:
										liste.append([bx, by])
				if liste != None:
					caracs.append(liste)

		return caracs

	def decouper2(self):

		"""Sépare les groupes de pixels d'une image"""

		pix = self.load()
		w, h = self.size

		mini_groupes = [] # mini_groupes: liste de sets (ensemble) contenant les coordonnées d'un pixel noir, et des 4 pixels ajdacents
		for x in range(w):
			for y in range(h):
				if pix[x, y] == 0:
					mini_groupe = set()
					mini_groupe.add((x, y))
					for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
						x2, y2 = x + dx, y + dy
						if 0 <= x2 < w and 0 <= y2 < h and pix[x2, y2] == 0: # Problèmes de bords
							mini_groupe.add((x2, y2))
					mini_groupes.append(mini_groupe)

		groupes = [] # Groupes de pixels finaux
		a_enlever = []
		for mini_groupe in mini_groupes:
			for groupe in groupes:
				if len(mini_groupe & groupe): # Si il y a une intersection entre un groupe final et un mini_groupe (pixel noir + pixels voisins)
					mini_groupe = mini_groupe | groupe # On fait l'union
					a_enlever.append(groupe) # Et on marque ce groupe comme inutile (mini_groupe est plus grand à présent)
			for groupe in a_enlever:
				groupes.remove(groupe)
			a_enlever = []
			groupes.append(mini_groupe)

		return groupes

	def bounding_box(self):

		"""Renvoie les coordonnées de la plus petite boîte contenant les pixels noirs de l'image"""

		w, h = self.size
		pix = self.load()
		ax, ay, bx, by = w, h, 0, 0

		# On pourrait aussi utiliser min, max... mais on fait toutes les comparaisons dans une boucle, mieux?
		for x in range(w):
			for y in range(h):
				if pix[x, y] == 0:
					if x <= ax: ax = x
					if x >= bx: bx = x
					if y <= ay: ay = y
					if y >= by: by = y

		if ax > 0: ax -= 1
		if ay > 0: ay -= 1
		if bx < w: bx += 1
		if by < h: by += 1
		return (ax, ay, bx, by)

	def recentrer(self):

		"""Fonction pour "recentrer" l'image, ie la réduire à sa bounding_box (modification en place)"""

		self._img = self._img.crop(self.bounding_box())

	def proportions(self, grille = [3, 5]):

		"""Renvoie la proportion en pixels noirs de chaque case d'une grille de decoupe, le vecteur obtenu est ensuite normé"""

		w, h = self.size
		pix = self.load()
		gx, gy = grille # Taille de la "grille" de découpage
		tx, ty = math.ceil(w/gx), math.ceil(h/gy) # Taille de chaque carreau de la grille
		pourcentages = [0 for i in range(gx*gy)]
		noir, blanc = 0, 1

		for x in range(w):
			for y in range(h):
				if pix[x, y] == noir:
					cx, cy = x//tx, y//ty
					zone = cx%gx + cy*gx
					pourcentages[zone] += 1

		vecteur = [v/(tx*ty) for v in pourcentages]
		norme = np.linalg.norm(vecteur)
		return [e/norme for e in vecteur] # On pourrait renvoyer une array numpy... à voir, plusieurs modifications en amont


class Reseau(list): # On se base sur 'list' pour automatiquement avoir __iter__, len(), et ainsi de suite... bref, un comportement de liste!

	"""Un réseau de neurones artificiels généraliste, c'est une liste modifiée de listes de neurones (objets Neurone)"""

	def __str__(self):

		# Pas très "canonique" (voir doc Python), mais utile

		return "Reseau" + self.type().title() + "(" + self.architecture() + ")" # "truc".title() == "Truc"

	def __repr__(self): return self.__str__()

	def __init__(self, codage = "simple", classes = []):

		"""Créer un nouveau réseau en spécifiant ou non un ensemble de classes (liste de noms, exemple: ["a", "b", "c"]) à identifier et un type de codage"""

		self.codage = codage
		self.classes = []
		for classe in classes:
			self.ajout_classe(classe)

	def architecture(self):

		"""Renvoie l'architecture du réseau (string), par exemple: 10x5 signifie une couche interne de taille 10, et une couche de sortie de taille 5"""

		return "x".join([str(len(couche)) for couche in self])

	def type(self):

		"""Renvoie le type du réseau: multicouche ou monocouche"""

		return "multicouche" if len(self) > 1 else "monocouche"

	def _export(self):

		"""Renvoie un dictionnaire permettant de reconstituer le réseau"""

		donnees = {}
		donnees["codage"] = self.codage
		donnees["classes"] = self.classes
		donnees["structure"] = liste = []
		# On créé simplement une liste contenant des listes (couches) de liste de nombres (les neurones ~ liste de poids)
		for couche in self:
			tmp = []
			for neurone in couche:
				tmp.append([poids for poids in neurone])
			liste.append(tmp)
		return donnees

	def _import(self, donnees):

		"""Importe les données d'un autre réseau (obtenues avec _export) dans le dictionnaire courant"""

		# Note: on aurait pu implémenter ça sans 'self', de facon à renvoyer un nouveau réseau: nouv_res = Reseau._import(donnees)
		# Mais cette facon de faire permet à des réseaux particuliers (ReseauOCR) d'importer d'autres données.
		# Dans le cas contraire, un objet Reseau aurait ete créé, et non pas l'objet modifié qui hérite de Reseau (ReseauOCR).

		self.codage = donnees.get("codage", "simple")
		self.classes = donnees.get("classes", [])
		del self[:] # Brutal, mais efficace...
		for couche in donnees["structure"]:
			self.append([Neurone(poids_neurone) for poids_neurone in couche])

	def codage_simple(self, i):

		"""Appelée lorsque le réseau utilise un codage simple"""

		if len(self.classes) > 0:
			vec =  [0 for classe in self.classes]
			vec[i] = 1
			return vec
		else:
			return []

	def codage_binaire(self, i):

		"""Appelée lorsque le réseau utilise un codage binaire"""

		nb_classes = len(self.classes)
		if nb_classes > 0:
			nb = math.ceil(math.log(nb_classes, 2))
			vec =  [0 for k in range(nb)]
			binaire = bin(i)[2:] # On enlève "0b"
			for k, bit in enumerate(binaire[::-1]):
				if bit == "1":
					vec[-(k+1)] = 1
			return vec
		else:
			return []

	codages = {
		"simple": codage_simple,
		"binaire": codage_binaire,
	}

	def utiliser_codage(self, nom):

		"""Indique quel codage de la couche de sortie utiliser. Renvoie False si le codage est inconnu!"""

		if nom in Reseau.codages:
			self.codage = nom
			return True
		else:
			return False

	def representation(self, classe):

		"""Renvoie la représentation en sortie d'une classe (int ou string)"""

		try:
			return Reseau.codages[self.codage](self, classe)
		except Exception:
			return Reseau.codages[self.codage](self, self.classes.index(classe))

	def ajout_classe(self, nom):

		"""Ajoute une classe 'nom' au réseau"""

		if not nom in self.classes:
			self.classes.append(nom)
			vecteur = self.representation(0) # Codage d'un vecteur quelconque, ici le premier
			couche = [Neurone() for i in range(len(vecteur))] # La taille du vecteur donne le nombre de neurones de sortie
			if len(self) == 0:
				self.append(couche)
			else:
				self[-1] = couche

	def enlever_classe(self, nom):

		"""Enlève une classe 'nom' du réseau"""

		if nom in self.classes:
			self.classes.remove(nom)
			vecteur = self.representation(0) # Codage d'un vecteur quelconque, ici le premier
			couche = [Neurone() for i in range(len(vecteur))] # La taille du vecteur donne le nombre de neurones de sortie
			if len(self) == 0:
				self.append(couche)
			else:
				self[-1] = couche

	def initialiser(self, taille_entree):

		"""Initialise le réseau pour une entrée de taille 'taille_entree', c'est-à-dire que le réseau classera des vecteurs de taille 'taille_entree' et les classera parmi les classes définies plus haut.
		Il est ABSOLUMENT NÉCESSAIRE d'initialiser le réseau chaque fois que sa structure est modifiée (couches, classes...)"""

		# On initialise la taille des neurones par récurrence: la taille d'entrée du reseau définit la taille des vecteurs d'entrée de la première couche interne, la taille de cette dernière définit la taille d'entrée de la couche suivante... etc
		taille = taille_entree + 1
		for couche in self:
			for neurone in couche:
				neurone.initialiser(taille)
			taille = len(couche) + 1 # Taille + 1 pour les termes de biais

	def ajout_couche(self, couche):

		"""Ajoute une couche au réseau. Le paramètre 'couche' peut être indifféremment un entier (taille de la couche à ajouter) ou une liste de neurones déjà créés"""

		try: # On suppose que 'couche' est un entier
			couche = [Neurone()]*couche # On créé une couche de taille 'couche'
		except Exception: # Un problème? C'est donc déjà une liste
			pass
		self.insert(-1, couche) # On ajoute avant la couche de sortie géree par le réseau de manière interne

	def enlever_couche(self, couche):

		"""Enlève une couche du reseau. Le paramètre 'couche' peut être indifféremment un entier (taille de la couche à ajouter) ou une liste de neurones déjà créés"""

		try: # On suppose que 'couche' est un entier
			self.pop(couche)
		except Exception: # Un probleme? C'est donc une liste
			self.remove(couche)

	def couche_sortie(self): # Utilité discutable...

		"""Renvoie la couche de sortie"""

		return self[-1]

	def couches_internes(self): # Utilité discutable...

		"""Renvoie les couches internes du reseau"""

		return [couche for couche in self[:-1]]

	def sortie(self, vecteur):

		"""Calcule la sortie de chaque couche du réseau pour une entrée vectorielle"""

		sorties = [vecteur + [-1]] # On ajoute le terme de biais
		taille = len(self)
		for couche in self:
			# La sortie tout en haut de la liste (la dernière) est en fait l'entrée de la couche suivante
			sortie = [neurone.sortie(sorties[-1]) for neurone in couche] 
			if len(sorties) < taille:
				sortie += [-1] # On ajoute le terme de biais
			sorties.append(sortie)
		return sorties

	def classer(self, exemple, filtre = 1):

		"""Renvoie une liste de classes probables correspondant à l'exemple 'exemple', dans l'ordre décroissant de probabilité"""

		sortie = np.array(self.sortie(exemple)[-1])
		couples = []
		for classe in self.classes:
			rep = np.array(self.representation(classe))
			norme = 1/2*np.linalg.norm(rep - sortie)
			couples.append([classe, norme])
		couples.sort(key = lambda element: element[1]) # [plus probable, ..., moins probable]
		return [element[0] for element in couples if element[1] < filtre]

	def calc_erreur(self, sorties, resultat):

		"""Un générateur pour calculer les erreurs pour chaque neurone (voir explications TIPE), connaissant la sortie et le résultat attendu. Les erreurs calculées sont données en partant de la couche de sortie"""

		# Intérêt du générateur: les termes d'erreurs sont calculés au moment d'itérer (for _ in calc_erreur(*args)), ce qui permet un gain de temps. On ne peut mathématiquement les calculer qu'en partant de la fin néanmoins...

		erreur = [n.sortie_deriv(sorties[-2])*(t-y) for n, t, y in zip(self.couche_sortie(), resultat, sorties[-1])] # Première erreur: formule différente
		couche_suiv = self.couche_sortie()
		sorties.pop()
		yield erreur

		for couche in reversed(self.couches_internes()):
			retroprop = [sum(n[k]*e for n, e in zip(couche_suiv, erreur)) for k in range(len(couche))] # Terme de retropropagation
			erreur = [n.sortie_deriv(sorties[-2])*retroprop[k] for k, n in enumerate(couche)]
			couche_suiv = couche
			sorties.pop()
			yield erreur

	def entrainer(self, exemple, resultat, taux_app = 0.5, inertie = 0.5):

		"""Entraîne le réseau sur un exemple 'exemple' (vecteur) dont la sortie attendue est 'resultat'. Renvoie l'erreur quadratique commise par le réseau sur l'exemple avant correction"""

		sorties = self.sortie(exemple)
		gen_erreurs = self.calc_erreur(sorties, resultat)
		entrees = sorties[:-1]

		err = 1/2*sum((t - y)**2 for t, y in zip(resultat, sorties[-1]))

		for entree, erreurs, couche in zip(entrees[::-1], gen_erreurs, self[::-1]): # Il faut itérer à l'envers (voir Reseau.calc_erreur)
			for erreur, neurone in zip(erreurs, couche):
				delta = [erreur*i for i in entree]
				neurone.corriger(delta, inertie, taux_app)

		return err

	def entrainer_cycle(self, exemples, resultats, taux_app = 0.5, inertie = 0.5, validation = True):

		"""Entraîne le réseau sur un ensemble d'exemples dont les sorties attendues sont données dans 'resultats'. La fonction renvoie un itérateur (pouvant être arrêté par un 'break' par exemple), qui donne l'erreur moyenne et l'erreur de validation (ou 0 si cette dernière n'est pas disponible) à chaque cycle de correction"""

		liste = list(zip(exemples, resultats))
		random.shuffle(liste) # On mélange les exemples pour éviter au réseau de trop se focaliser sur une classe en particulier. On peut se permettre de ne mélanger qu'une fois en théorie, il y a peu de chances que le réseau se focalise sur le cycle
		liste_validation = [] # Couples de validation: ne sont pas utilisés pour l'entraînement, seulement pour tester l'évolution de l'erreur et s'assurer que le réseau ne se focalise pas trop sur les exemples d'entraînement

		if validation: # Si on veut l'erreur de validation aussi

			classes_vues = []
			for classe in resultats:
				if not classe in classes_vues: # On ne prend qu'un échantillon par classe
					classes_vues.append(classe)
					ex_classe = [] # On rassemble les couples ayant la même classe/même résultat
					for ex, res in liste:
						if res == classe:
							ex_classe.append((ex, res))
					if len(ex_classe) > 1:
						# liste_validation.append(random.choice(ex_classe))
						liste_validation.append(ex_classe[0])

			liste = [couple for couple in liste if couple not in liste_validation] # Couples gardés pour la validation

		while 1: # C'est normal, tout va bien

			err = 0
			for exemple, resultat in liste: # Pour chaque exemple
				err += self.entrainer(exemple, resultat, taux_app = taux_app, inertie = inertie)
			err = err/len(liste) # Moyenne algébrique des erreurs pour chaque exemple

			err_val = 0
			for exemple, resultat in liste_validation:
				sortie = self.sortie(exemple)[-1] # On calcule l'erreur pour les couples de validation
				err_val += 1/2*sum([(r - s)**2 for r, s in zip(resultat, sortie)])
			if len(liste_validation):
				err_val = err_val/len(liste_validation)

			yield err, err_val

def heaviside(x):
	return 1 if x > 0 else 0

def heaviside_prime(x):
	return float("inf") if x == 0 else 0

def sigmoide(x):
	return 1/(1+math.exp(-x))

def sigmoide_prime(x):
	return sigmoide(x)*(1-sigmoide(x))

class Neurone(list):

	"""Un neurone pour les réseaux"""

	def __str__(self):

		return "Neurone({})".format(", ".join([str(i) for i in self]))

	def __repr__(self): return self.__str__()

	def __init__(self, poids = None):

		"""Créer un neurone, initialise aux poids 'poids' si fournis"""

		self.delta_prec = None
		# Fonction d'activation: un sigmoide + dérivée
		self.activation = sigmoide #interpolation(sigmoide, -5, 5, pts = 1000)
		self.activation_deriv = sigmoide_prime #interpolation(sigmoide_prime, -5, 5, pts = 1000)

		# Si on fournit des poids au moment de la création
		if poids is not None:
			self.initialiser(len(poids)) # On initialise à la bonne taille
			self.corriger(poids, inertie = 0, taux_app = 1) # Et on corrige (petite astuce pour éviter d'écrire "manuellement" les poids!)

	def corriger(self, delta, inertie = 0.5, taux_app = 0.5):

		"""Corrige les poids du neurone avec une liste de deltas à appliquer à chaque poids. L'inertie répète la dernière correction è un facteur près"""

		for i, poids in enumerate(self):
			self[i] = poids + taux_app*delta[i] + inertie*self.delta_prec[i]
		self.delta_prec = delta

	def sortie(self, vecteur):

		"""Sortie d'un neurone pour le vecteur 'vecteur'"""

		assert len(vecteur) == len(self)
		return self.activation(np.dot(vecteur, self)) # Produit scalaire des poids avec le vecteur, puis sigmoide

	def sortie_deriv(self, vecteur):

		"""Sortie derivée d'un neurone pour le vecteur 'vecteur'"""

		assert len(vecteur) == len(self)
		return self.activation_deriv(np.dot(vecteur, self))

	def initialiser(self, taille):

		"""Initialise le neurone à la taille 'taille' avec des valeurs aléatoires"""

		self.delta_prec = []
		del self[:]
		for i in range(taille):
			self.delta_prec.append(0)
			self.append(random.uniform(-0.5, 0.5)) # Initialisation avec de petites valeurs aleatoires


# Protocoles de lecture et écriture de réseaux OCR

class ProtocoleJSON:

	"""Protocole pour le format JSON"""

	def __init__(self, chemin, mode):

		modes = { "r": "r", "w": "w+" } # Modes "r" ou "w" uniquement
		self.fichier = open(chemin, modes.get(mode, "r"))
		try: # On essaye de charger un fichier
			self.donnees = json.load(self.fichier)
		except Exception as e: # Si ça ne marche pas, on initialise le futur fichier
			self.donnees = { "echantillons": {} }

	def __enter__(self): # Appelé par le mot-clé "with"

		return self

	def __exit__(self, *args): # Appelé en sortant d'un bloc "with"

		self.fichier.close()

	def sauver(self, reseau):

		"""Sauve un réseau dans un fichier"""

		donnees = reseau._export() # On génère les données de base
		donnees["echantillons"] = {}

		# On convertit les images en texte, elles sont encodées en base 64
		for classe in reseau.classes:
			donnees["echantillons"][classe] = images_base64 = []
			for image in reseau.fichiers(classe):
				image_base64 = base64.b64encode(image.getvalue())
				images_base64.append(image_base64.decode("utf-8"))

		json.dump(donnees, self.fichier)

	def images(self):

		"""Itérateur sur les images contenues dans le fichier"""

		# Itérateur car le décodage peut être long

		for classe, images_base64 in self.donnees["echantillons"].items():
			for image_base64 in images_base64:
				image = io.BytesIO(base64.b64decode(image_base64)) # On décode chacune des images dans un fichier mémoire (BytesIO)
				image = ImageBinaire.open(image)
				yield classe, image

	def reseau(self):

		"""Renvoie les données brutes du réseau (pas d'échantillons)"""

		donnees = self.donnees.copy()
		del donnees["echantillons"]
		return donnees

class ProtocoleZIP:

	"""Protocole pour les fichiers ZIP"""

	def __init__(self, chemin, mode):

		modes = { "r": "r", "w": "w" }
		self.fichier = zipfile.ZipFile(io.StringIO(chemin).getvalue(), modes.get(mode, "r"))

	def __enter__(self):

		return self

	def __exit__(self, *args):

		self.fichier.close()

	def sauver(self, reseau):

		"""Sauve un réseau dans un fichier"""

		donnees = reseau._export()
		self.fichier.writestr("reseau.json", json.dumps(donnees)) # Les données textes sont sauvées dans un fichier JSON, placé dans le ZIP

		for classe in reseau.classes:
			for index, image in enumerate(reseau.fichiers(classe)): # Les images sont sauvées a part
				if classe == "/": classe = "__slash__" # On renomme l'éventuelle classe "/" qui va causer des bugs...
				self.fichier.writestr(classe+"/"+str(index)+".png", image.getvalue())

	def images(self):

		"""Itérateur sur les images contenues dans le fichier"""

		for nom in self.fichier.namelist(): # On itère sur les fichiers/dossiers, le ZIP contient des dossiers nommés selon les classes
			if "/" in nom and not nom.endswith("/"): # Le nom comporte "/" dans son nom, donc il est dans un dossier, et c'est bien un fichier car son nom ne termine pas par un "/"
				classe, vrai_nom = nom.split("/") # classe = nom du dossier, vrai_nom = nom du fichier
				if classe == "__slash__": classe = "/"
				image = self.fichier.read(nom)
				image = io.BytesIO(image) # Encore une fois, on ouvre en mémoire
				image = ImageBinaire.open(image) # Dernière étape: on créé une image binaire à partir du fichier mémoire!
				yield classe, image

	def reseau(self):

		"""Renvoie les données brutes du réseau (pas d'échantillons)"""

		donnees = self.fichier.open("reseau.json")
		donnees = io.TextIOWrapper(donnees) # On ouvre en mémoire
		donnees = json.load(donnees)
		return donnees


class ReseauOCR(Reseau): # On se base sur Reseau

	"""Un réseau spécialisé dans l'OCR"""

	protocoles = {
		".zip": ProtocoleZIP,
		".json": ProtocoleJSON,
	}

	def get_protocole(fichier):

		"""Renvoie le protocole (probable) à utiliser selon le nom du fichier"""

		_, ext = os.path.splitext(fichier)
		return ReseauOCR.protocoles.get(ext, ProtocoleJSON) # dict.get(key) est similaire à dict[key] sauf qu'on peut préciser une valeur par défaut

	def __init__(self, *args, **kwargs):

		"""Créer un réseau spécialisé dans la reconnaissance de caractères"""

		Reseau.__init__(self, *args, **kwargs)
		self.grille = (3, 5) # La grille est juste une autre facon d'exprimer l'entrée du reseau
		self.echantillons = {} # Principale différence avec le réseau basique: stockage d'échantillons images

	def _export(self):

		"""Voir Reseau._export"""

		donnees = Reseau._export(self)
		donnees["grille"] = self.grille # On ajoute d'autres informations aux données, la gestion des images est à la charge des protocoles
		return donnees

	def _import(self, donnees):

		"""Voir Reseau._import"""

		Reseau._import(self, donnees) # Voir Reseau._import pour les explications concernant les choix d'implémentation
		self.grille = donnees.get("grille", (3, 5))

	def copier(self):

		"""Renvoie une copie du réseau (copy.deepcopy ne fonctionne pas)"""

		donnees = self._export()
		copie = ReseauOCR()
		copie._import(donnees)
		for classe in self.classes:
			for image in self.images(classe):
				copie.ajout_echantillon(classe, image)
		return copie

	def ouvrir(self, chemin, protocole = None):

		"""Ouvre un fichier dans le réseau, avec le protocole spécifié"""

		if protocole is None:
			protocole = ReseauOCR.get_protocole(chemin)
		with protocole(chemin, "r") as fichier:
			for classe, image in fichier.images():
				self.ajout_echantillon(classe, image)
			self._import(fichier.reseau())

	def sauver(self, chemin, protocole = None):

		"""Sauve le réseau dans un fichier, avec le protocole spécifié"""

		if protocole is None:
			protocole = ReseauOCR.get_protocole(chemin)
		with protocole(chemin, "w") as fichier:
			fichier.sauver(self)

	def initialiser(self, grille):

		"""Voir Reseau.initialiser. Seule différence: on initialise avec un tuple de deux valeurs pour la taille de l'entrée (ex: (3, 5) ==> 15)"""

		gx, gy = grille
		self.grille = tuple(grille)
		Reseau.initialiser(self, gx*gy)

	def ajout_classe(self, nom):

		"""Voir Reseau.ajout_classe"""

		Reseau.ajout_classe(self, nom)
		if not nom in self.echantillons:
			self.echantillons[nom] = []

	def ajout_echantillon(self, classe, image):

		"""Ajoute un échantillon au réseau. Cet echantillon est une image ou un chemin vers une image, associé à la classe 'classe'"""

		if not classe in self.echantillons:
			self.echantillons[classe] = []
		self.echantillons[classe].append(image)

	def enlever_echantillon(self, classe, index):

		"""Enlève un échantillon désigné pas son indice"""

		self.echantillons[classe].pop(index)

	def image(self, classe, i):

		"""Renvoie l'image d'indice 'i' associée à une classe"""

		try: # Cas ou l'échantillon est un chemin d'accès, on tente d'ouvir
			return ImageBinaire.open(self.echantillons[classe][i])
		except:
			return self.echantillons[classe][i] # Ca n'a pas marché, le fichier est déjà une image (objet ImageBinaire), il suffit de la renvoyer!

	def images(self, classe):

		"""Itère sur les images associées à une classe"""

		for i in range(len(self.echantillons[classe])):
			yield self.image(classe, i)

	def fichiers(self, classe):

		"""Itère sur les fichiers associés à une classe"""

		for image in self.images(classe):
			with io.BytesIO() as fichier_image: # On créé un fichier en mémoire
				image.save(fichier_image, "PNG") # PIL peut écrire sur notre BytesIO, pour lui, c'est un fichier comme un autre!
				yield fichier_image

	def charger_echantillons(self):

		"""Convertit les échantillons images en vecteurs, renvoie un tuple (exemples, resultats) directement exploitable par un entraînement hors ligne"""

		exemples = []
		resultats = []
		for classe in self.classes:
			for image in self.images(classe):
				image.recentrer()
				exemples.append(image.proportions(self.grille))
				resultats.append(self.representation(classe))
		return exemples, resultats

	def reconnaitre_caractere(self, image, filtre = 0.5):

		"""Similaire à Reseau.classer, mais avec une image ou un chemin vers une image"""

		try: image = ImageBinaire.open(image) # Cas ou l'échantillon est un chemin d'accès, on tente d'ouvrir
		except: pass # Ca n'a pas marché, le fichier est déjà une image
		image.recentrer()
		exemple = image.proportions(self.grille)
		return self.classer(exemple, filtre)

	def reconnaitre_chaine(self, image, decoupage = ImageBinaire.decouper, filtre = 0.5):

		"""Renvoie une liste de chaînes probables pour l'image fournie, de la plus probable à la moins probable. L'argument 'decoupage' permet de specifier un algorithme de découpage de caractères particulier (voir ImageBinaire)"""

		try: image = ImageBinaire.open(image) # Cas ou l'échantillon est un chemin d'accès, on tente d'ouvrir
		except: pass # Ca n'a pas marché, le fichier est déjà une image

		liste = [image]
		if decoupage is not False:
			liste = [ImageBinaire.depuis_liste(carac) for carac in decoupage(image)]

		chaines = ["", ]

		for image in liste:

			caracteres = self.reconnaitre_caractere(image, filtre)
			if not len(caracteres): caracteres.append("?")

			n_chaines = []
			for chaine in chaines:
				for c in caracteres:
					n_chaines.append(chaine + c)

			chaines = n_chaines[:]

		return chaines
