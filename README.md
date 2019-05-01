# Interface syntaxe / prosodie (exporter.py) – Notice explicative du script

(S. Duchemin – 18/04/19)

![Example d'un fichier Praat TextGrid augmenté](https://github.com/vieenrose/conll2praat/blob/master/sample.png)

## Objectif

Ce script permet de récupérer les nouvelles annotations en macrosyntaxe présentes dans des
fichiers au format CoNLL10 pour mettre à jour la couche segmentée en phrases présente dans des
fichiers `.TextGrid`. Il ne supprime pas la couche existante mais en crée une nouvelle.

## Utilisation

Le script se lance en ligne de commande de la façon suivante :

```
python exporter.py fichier_conll10 fichier_textgrid répertoire_résultats
```
ou
```
python3 exporter.py fichier_conll10 fichier_textgrid répertoire_résultats
```

## Entrées

- Un fichier ou un répertoire contenant des fichiers [CoNLL-U](http://universaldependencies.org/format.html) `.conll`
- Un fichier ou un répertoire contenant des fichiers 
    - [format Praat](http://www.fon.hum.uva.nl/praat/manual/TextGrid_file_formats.html) 
        - TextGrid `.TextGrid`
        - Praat Binaire `.Collection`
    - [format Analor](http://www.lattice.cnrs.fr/Analor) `.or`

## Sortie

Pour chaque couple de fichiers `.textgrid` et `.conll[10]`, un nouveau fichier .textgrid portant le même
nom que le fichier original avec le suffixe `_UPDATED` est créé dans le répertoire de résultats passé en
argument lors du lancement du programme. Le répertoire sera crée s'il n'existe pas.

Dans chaque nouveau fichier textgrid, une nouvelle couche appelée `tx_new` est créée pour y
mettre les annotations mises à jour sans perdre d'informations en cas de problèmes.

## Fonctionnement

Dans un premier temps, le programme récupère les tokens de la première phrase dans le fichier
CoNLL (il s'appuie sur les sauts de ligne pour les délimiter) et les stocke en mémoire.

Il commence ensuite à lire la tire `mot`, la seule constante du fichier, en théorie, qui peut donc
servir de référence pour trouver les deux bornes temporelles initiales et finalles de la phrase.

Pour faire cela, le programme regarde la tire de référence via une fenêtre de dix intervalles et
repère les mots les plus proches du premier et du dernier token de la phrase récupérée dans le fichier
CoNLL en calculant des distances de Levenshtein, ce qui permet de prendre en compte des
éventuelles modifications orthographiques dans les fichiers CoNLL.

Le curseur de lecture de la tire `mot` est ensuite déplacé sur la fin de la phrase pour permettre une
lecture récursive.

Enfin, un intervalle contenant l'ensemble de la phrase récupérée sur le fichier tabulaire est créé en
utilisant les bornes temporelles récupérées précédemment et le programme passe à la phrase
suivante.


## Problèmes rencontrés

1. Tous les fichiers .textgrid n'utilisant pas le même nom pour la tire `mot`, le script ne parvenait
    pas à récupérer la tire en question. Pour l'instant, le script peut traiter les noms suivants :
    [“mot”, “MOT”, “TokensAlign”]. Il faudra mettre le script à jour dans le cas où d'autres noms
    seraient utilisés ([fa78fe](https://github.com/vieenrose/conll2praat/commit/fa78fe7e06a2bc61cbc5201d743cc110f7da53dd)).
2. Puisque l'alignement se fait progressivement et dépend du dérouler de la tire `mot` et du
    fichier CoNLL, il pourra y avoir des erreurs d'alignements si des phrases sont manquantes ou
    bien dans le désordre ([9c0103](https://github.com/vieenrose/conll2praat/commit/9c0103339cc1698411d473ae55f406aaffdc3374)).
3. Dans la première version du programme, il y avait parfois quelques erreurs d'alignement au
    début ou à la fin des phrases. Elles étaient dues à une mauvaise gestion des `#` et ont été
    corrigées. (voir rapport d'erreurs) ([f17282](https://github.com/vieenrose/conll2praat/commit/f172827012b6436c9b791354509ccb6f46a742be)).


