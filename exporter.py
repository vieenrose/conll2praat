#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# exportateur Column @ CoNLL-U -> Tier @ Praat TextGrid
# prerequisite : pympi.Praat
#
# auteurs : 
#     Sandy Duchemin
#     Luigi Liu

import re, csv, os, sys, argparse
from difflib import SequenceMatcher
import pympi.Praat as prt
from collections import deque
DEBUG = False

# outils
def insert_to_basename(filename, inserted):
      basename, extension = os.path.splitext(filename)
      return basename + inserted + extension
      
def deb_print(x) : 
      if DEBUG : print(x)
      
# source : https://stackoverflow.com/questions/2460177/edit-distance-in-python
def edit_distance(s1, s2):
    m=len(s1)+1
    n=len(s2)+1

    tbl = {}
    for i in range(m): tbl[i,0]=i
    for j in range(n): tbl[0,j]=j
    for i in range(1, m):
        for j in range(1, n):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            tbl[i,j] = min(tbl[i, j-1]+1, tbl[i-1, j]+1, tbl[i-1, j-1]+cost)

    return tbl[i,j]
    
def distance(s1, s2) :

      # retirer des signes de marcro qui ne sont pas présentes dans le tier de ref.
      macrosyntax_signs = re.compile(r"[\&\(\)\[\]\/\|\+\s\<\>]") 
      s1 = re.sub(macrosyntax_signs, "", s1.lower())
      s2 = re.sub(macrosyntax_signs, "", s2.lower())
      dist =  edit_distance(s1, s2[:len(s1)])
      return dist
      
def findTimes (tokens, refTier, cursor) : 
      
    sent = ' '.join(tokens)
    intvs = refTier.get_all_intervals()
    ref_tokens = [intv[-1] for intv in intvs]
    best_dist = -1
    best_begin_n = -1
    best_end_n = -1
    ref_tokens_sampled = []
    best_begin_ref_sent = ''
    best_end_ref_sent = ''
    
    # détection du début temporel
    n_max = min(cursor + 10, len(ref_tokens))
    for n in range(cursor, n_max) : 
        if ref_tokens[n] == pauseSign or not(ref_tokens[n]) : continue # interdiction d'aligner le début de la phrase sur une pause ou un vide
        ref_tokens_sampled = list(zip(*zip(tokens, ref_tokens[n:])))[-1]
        ref_sent = ' '.join(ref_tokens_sampled)
        dist = distance(sent, ref_sent)
        if best_dist < 0 or dist < best_dist : 
            best_dist = dist
            best_begin_n = n
            best_begin_ref_sent = ref_sent
    #deb_print('\t@findTimes best distance: {}'.format(best_dist))
    #deb_print("\t@findTimes best begin sentence ({}) found   : '{}'".format(best_begin_n, best_begin_ref_sent))
      
    tmin = intvs[best_begin_n][0] # begining time of the starting interval
    
    # détection de la vraie fin temporelle
    best_dist = -1
    best_sent = ''
    width = 2 * len(tokens)
    while width :
        end_n = best_begin_n + width
        try: ref_sent = ' '.join(ref_tokens[best_begin_n:end_n])
        except IndexError: 
              if width > 0: 
                    width -= 1
                    continue
        dist = distance(sent[::-1], ref_sent[::-1])
        if best_dist < 0 or dist <= best_dist : 
            best_dist = dist
            best_end_n = end_n
            best_sent = ref_sent
        width -= 1
    tmax = intvs[best_end_n - 1][1] # end time of the last interval
    deb_print("\t@findTimes sent to match : '{}'".format(sent[-50:]))
    deb_print("\t@findTimes sent found    : '{}'".format(best_sent[-50:], tmin, tmax))
    
    #if 'look for' in sent : exit() #debug
    #if 'customer' in sent : exit() #debug
    
    cursor_out = best_end_n
          
    return [tmin, tmax, cursor_out]
    
def one_to_many_pairing (file1, files2, thld = 6):

      matched = ''
      maxlen = -1
      doublon = False
      
      for file2 in files2 :
            nonenone,nonenone,match_len = \
                SequenceMatcher(None, file1, file2).\
		    find_longest_match(0, len(file1), 0, len(file2))
            if match_len > max(thld , maxlen):
                  maxlen = match_len
                  matched = file2
                  doublon = False
            elif match_len == maxlen:
                  doublon = True

      # don't make a pair if at the end, a doublon remains
      if doublon : matched = ''

      return matched
      
def make_paires(files1, files2):
      # fine 1-to-1 file pair
      pairs = []
      for f1 in files1 :
          f2 = one_to_many_pairing(f1, files2)
          if f2 :
              if f1 == one_to_many_pairing(f2, files1) : 
                pairs.append((f1,f2))

      return pairs
      
# filelists / tiernames / constants

# creattion of a frendly command-line interface using argparse
parser = argparse.ArgumentParser(description='conll2praat exporter')
parser.add_argument('conll_in', help = 'folder of conll files')
parser.add_argument('praat_in', help = 'folder of input praat files')
parser.add_argument('praat_out', help = 'folder for output praat files')
args = parser.parse_args()
# make conll - praat pairs
conllFiles   = os.listdir(args.conll_in)
conllFiles.sort()
inputTgFiles = os.listdir(args.praat_in)
conll_tg_pairs = make_paires(conllFiles, inputTgFiles)
conll_tg_pairs_bak = conll_tg_pairs
out_rep     = args.praat_out
if not os.path.exists(out_rep):
        os.makedirs(out_rep)
refTierNames = ['mot','MOT','TokensAlign']
destTierName = 'tx_new'
pauseSign    = '#'
srcCol       = 2 # 'FORM' (CoNLL)

# todo : ajout le soutien du TextGrid integré dans un fichier .Collection
# todo : recherche automatique du time reference tier
#for n,p in enumerate(conll_tg_pairs_bak): print('{}:\t{:5s}: {}\n\t{:5s}: {}\n'.format(n,'conll',p[0],'tg',p[1]))

# I/O handlers
conll_tg_pairs = conll_tg_pairs[::-1]
while conll_tg_pairs:
    inconllFile,inTgfile = conll_tg_pairs.pop()
    #print("\tFichier CONLL traité : {}".format(inconllFile))
    #print("\tFichier TG traité : {}\n".format(inTgfile))
    conll_path = args.conll_in+'/'+inconllFile
    inTg_path = args.praat_in+'/'+inTgfile
    
   
    conll  = csv.reader(open(conll_path, 'r'), delimiter='\t', quotechar='\\') #lecture du fichier tabulaire (CoNLL-U)
    try:
      tg     = prt.TextGrid(file_path=inTg_path, codec='utf-8')               #lecture du fichier textgrid (Praat)
      outputTg_path = args.praat_out+'/'+insert_to_basename(inTgfile,'_UPDATED')
    except:
      print('error: fail to read {}'.format(inTg_path))
      continue
      
    print('\t{:s} {:s}'.format('<-',conll_path))
    print('\t{:s} {:s}'.format('<-',inTg_path))
    print('\t{:s} {:s}'.format('->',outputTg_path))
    
    
    # handel diff. reference tier names
    for refTierName in refTierNames :
        try:
            ref    = tg.get_tier(refTierName)  #tier de repères temporels ('mot')
            break
        except IndexError:
            pass
            
    dest   = tg.add_tier(destTierName) #tier de destination ('tx')

    # initialization
    tokens = []
    sentId = 0
    pauseId = 0
    cursor = 0

    # boucle de lecture
    for n, row in enumerate(conll) :

    # les métadonnées 
        if row and len(row) < 10 : 
            metadata = row[0]
            #deb_print("L{} mdata[:50] '{}'".format(n,metadata[:50]))
            continue
    
    # token dans une phrase
        if row : 
            token = row[srcCol - 1]
            # récolte des tokens 
            if token.strip() != pauseSign : 
                tokens.append(token)
                #deb_print("L{} tokens[-5:-1] '{}'".format(n,tokens[-5:-1]))
            else :
                #deb_print("L{} pause no.{} '{}'".format(n,pauseId, token))
                pauseId += 1
                
    # saute de ligne à la frontière des phrases
        else :
            sent = ' '.join(tokens)
            deb_print("L{} sentence no.{} '... {}'".format(n,sentId,sent[-50:-1]))
            
            [begin,end, cursor_out] = findTimes(tokens,ref, cursor)
            if cursor_out >= cursor : 
                  cursor = cursor_out
                  deb_print("L{} (begin,end) = ({:8.3f},{:8.3f})".format(n,begin,end))
                
                  # écrire le contenu dans le tier de destination
                  dest.add_interval(begin=begin, end=end, value=sent, check=True)
            else:
                  deb_print("L{} (begin,end) = (????????,????????)".format(n))
            
            # préparation à la prochaine phrase
            sentId += 1
            tokens = []

    #path =  "./{}/{}".format(out_rep, outputTgFile)           
    tg.to_file(outputTg_path, mode='binary', codec='utf-8')
    print("\n\nDONE.\n\n")

print("Summaray of processed files: ")
for n,p in enumerate(conll_tg_pairs_bak): 
      print('{}:\t{:5s}: {}\n\t{:5s}: {}\n'.format(n,'conll',p[0],'tg',p[1]))
#*****************************
