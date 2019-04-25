#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# exportateur Column @ CoNLL-U -> Tier @ Praat TextGrid
# prerequisite : pympi.Praat
#
# auteurs : 
#     Sandy Duchemin
#     Luigi Liu

import re, csv, os, sys, argparse, collections
from difflib import SequenceMatcher
import pympi.Praat as prt
from collections import deque
import sys, codecs, re, struct
DEBUG = False

# outils

# extend original TextGrid reader to support praat Collection
class TextGridPlus(prt.TextGrid):

      def from_file(self, ifile, codec='ascii'):
              """Read textgrid from stream.
              :param file ifile: Stream to read from.
              :param str codec: Text encoding for the input. Note that this will be
                  ignored for binary TextGrids.
              """
              if ifile.read(12) == b'ooBinaryFile':
                  def bin2str(ifile):
                      textlen = struct.unpack('>h', ifile.read(2))[0]
                      # Single byte characters
                      if textlen >= 0:
                          return ifile.read(textlen).decode('ascii')
                      # Multi byte characters have initial len -1 and then \xff bytes
                      elif textlen == -1:
                          textlen = struct.unpack('>h', ifile.read(2))[0]
                          data = ifile.read(textlen*2)
                          # Hack to go from number to unicode in python3 and python2
                          fun = unichr if 'unichr' in __builtins__.__dict__ else chr
                          charlist = (data[i:i+2] for i in range(0, len(data), 2))
                          return u''.join(
                              fun(struct.unpack('>h', i)[0]) for i in charlist)

		  # only difference is here :in the case of a Praat collection
		  # jump to the begining of the embedded TextGrid object
                  if ifile.read(ord(ifile.read(1))) == b'Collection': # skip oo type
                        self.jump2TextGridBin(ifile, codec)

                  self.xmin = struct.unpack('>d', ifile.read(8))[0]
                  self.xmax = struct.unpack('>d', ifile.read(8))[0]
                  ifile.read(1)  # skip <exists>
                  self.tier_num = struct.unpack('>i', ifile.read(4))[0]
                  for i in range(self.tier_num):
                      tier_type = ifile.read(ord(ifile.read(1))).decode('ascii')
                      name = bin2str(ifile)
                      tier = prt.Tier(0, 0, name=name, tier_type=tier_type)
                      self.tiers.append(tier)
                      tier.xmin = struct.unpack('>d', ifile.read(8))[0]
                      tier.xmax = struct.unpack('>d', ifile.read(8))[0]
                      nint = struct.unpack('>i', ifile.read(4))[0]
                      for i in range(nint):
                          x1 = struct.unpack('>d', ifile.read(8))[0]
                          if tier.tier_type == 'IntervalTier':
                              x2 = struct.unpack('>d', ifile.read(8))[0]
                          text = bin2str(ifile)
                          if tier.tier_type == 'IntervalTier':
                              tier.intervals.append((x1, x2, text))
                          elif tier.tier_type == 'TextTier':
                              tier.intervals.append((x1, text))
                          else:
                              raise Exception('Tiertype does not exist.')
              else:
                  def nn(ifile, pat):
                      line = next(ifile).decode(codec)
                      return pat.search(line).group(1)

                  regfloat = re.compile('([\d.]+)\s*$', flags=re.UNICODE)
                  regint = re.compile('([\d]+)\s*$', flags=re.UNICODE)
                  regstr = re.compile('"(.*)"\s*$', flags=re.UNICODE)
                  # Skip the Headers and empty line
                  next(ifile), next(ifile), next(ifile)
                  self.xmin = float(nn(ifile, regfloat))
                  self.xmax = float(nn(ifile, regfloat))
                  # Skip <exists>
                  line = next(ifile)
                  short = line.strip() == b'<exists>'
                  self.tier_num = int(nn(ifile, regint))
                  not short and next(ifile)
                  for i in range(self.tier_num):
                      not short and next(ifile)  # skip item[]: and item[\d]:
                      tier_type = nn(ifile, regstr)
                      name = nn(ifile, regstr)
                      tier = Tier(0, 0, name=name, tier_type=tier_type)
                      self.tiers.append(tier)
                      tier.xmin = float(nn(ifile, regfloat))
                      tier.xmax = float(nn(ifile, regfloat))
                      for i in range(int(nn(ifile, regint))):
                          not short and next(ifile)  # skip intervals [\d]
                          x1 = float(nn(ifile, regfloat))
                          if tier.tier_type == 'IntervalTier':
                              x2 = float(nn(ifile, regfloat))
                              t = nn(ifile, regstr)
                              tier.intervals.append((x1, x2, t))
                          elif tier.tier_type == 'TextTier':
                              t = nn(ifile, regstr)
                              tier.intervals.append((x1, t))

      def jump2TextGridBin(self, ifile, codec='ascii', keyword =  b'\x08TextGrid'):
            binstr = b''
            while ifile: 
                  binstr += ifile.read(1)
                  if len(binstr) > len(keyword): 
                        binstr = binstr[1:]
                  if binstr == keyword : 
                        break
            lg = struct.unpack('>h', ifile.read(2))[0]
            if lg == -1 : 
                  lg = lg.astype('>H')
            objname = ifile.read(lg).decode('ascii') # skip embeded oo name

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
      macrosyntax_signs = re.compile(r"[\#\&\(\)\[\]\/\|\+\s\<\>]") 
      s1 = re.sub(macrosyntax_signs, "", s1.lower())
      s2 = re.sub(macrosyntax_signs, "", s2.lower())
      dist =  edit_distance(s1, s2[:len(s1)])
      return dist
      
def findTimes (tokens, refTier, lowerbound, upperbound = -1, thld = 0.1) : 
      
    sent = ' '.join(tokens)
    intvs = refTier.get_all_intervals()
    ref_tokens = [intv[-1] for intv in intvs]
    best_dist = -1
    best_begin_n = -1
    best_end_n = -1
    ref_tokens_sampled = []
    best_begin_ref_sent = ''
    best_end_ref_sent = ''
    width = 2 * len(tokens)
    
    # détection du début temporel
    if upperbound < 0: # interprete negative upper bound as unbounded case
          upperbound = len(ref_tokens)
    for n in range(lowerbound,upperbound)[::-1] :
        # check if n is correct
        try: ref_tokens[n]
        except IndexError: continue
        # adapt real width if necessary
        try : ref_tokens_sampled = ref_tokens[n:n+width]
        except IndexError: ref_tokens_sampled = ref_tokens[n:]
        # check if the current token represnts a pause 
        if ref_tokens[n] == pauseSign or not(ref_tokens[n]) : continue # interdiction d'aligner le début de la phrase sur une pause ou un vide
        
        # search the begining
        ref_sent = ' '.join(ref_tokens_sampled)
        dist = distance(sent, ref_sent)
        if best_dist < 0 or dist <= best_dist :
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
        ref_sent = ' '.join(ref_tokens[best_begin_n:end_n])
        dist = distance(sent[::-1], ref_sent[::-1])
        if best_dist < 0 or dist <= best_dist : 
            best_dist = dist
            best_end_n = end_n
            best_sent = ref_sent
        width -= 1
        
    # verify if dist < 10% of sentence length
    deb_print("\t@findTimes sent to match : '{}'".format(sent))
    if best_dist > thld * (len(sent)**1.1):
        tmin = -1; tmax = -1
        cursor_out = -1
        deb_print("\t@findTimes err : best dist. '{}' too large".format(best_dist))
    else :
        tmax = intvs[best_end_n - 1][1] # end time of the last interval
        cursor_out = best_end_n
        deb_print("\t@findTimes sent found    : '{}'".format(best_sent, tmin, tmax))

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

# todo : recherche automatique du time reference tier
#for n,p in enumerate(conll_tg_pairs_bak): print('{}:\t{:5s}: {}\n\t{:5s}: {}\n'.format(n,'conll',p[0],'tg',p[1]))

# I/O handlers
err = collections.Counter()
conll_tg_pairs = conll_tg_pairs[::-1]
while conll_tg_pairs:
    inconllFile,inTgfile = conll_tg_pairs.pop()
    #print("\tFichier CONLL traité : {}".format(inconllFile))
    #print("\tFichier TG traité : {}\n".format(inTgfile))
    conll_path = args.conll_in+'/'+inconllFile
    inTg_path = args.praat_in+'/'+inTgfile
    
   
    conll  = csv.reader(open(conll_path, 'r'), delimiter='\t', quotechar='\\') #lecture du fichier tabulaire (CoNLL-U)
    try:
      tg     = TextGridPlus(file_path=inTg_path, codec='utf-8')               #lecture du fichier textgrid (Praat)
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
            deb_print("L{} sentence no.{} '{}'".format(n,sentId,sent))
            
            # try a local search from cursor to end of time with by default thld.
            [begin,end, cursor_out] = findTimes(tokens,ref, lowerbound=cursor, upperbound=cursor+50,thld = 0.10)
            if cursor_out >= cursor : 
                  cursor = cursor_out
                  deb_print("L{} local (begin,end) = ({:8.3f},{:8.3f})".format(n,begin,end))
                
                  # écrire le contenu dans le tier de destination
                  dest.add_interval(begin=begin, end=end, value=sent, check=True)
            else:
                  # try a global search but with a more strict threshold for distance
                  [begin,end, cursor_out] = findTimes(tokens,ref, lowerbound=0, upperbound=-1, thld = 0.05)
                  if cursor_out >= 0 : 
                        #deb_print("L{} global (begin,end) = ({:8.3f},{:8.3f})".format(n,begin,end))
                  
                        # écrire le contenu dans le tier de destination
                        try:
                              dest.add_interval(begin=begin, end=end, value=sent, check=True)
                              deb_print("L{} global (begin,end) = ({:8.3f},{:8.3f})".format(n,begin,end))
                        except: 
                              print("L{} search fail (begin,end) = (????????,????????)".format(n))
                              err[inconllFile]+=1
                  else:
                        print("L{} search fail (begin,end) = (????????,????????)".format(n))
                        err[inconllFile]+=1
            
            # préparation à la prochaine phrase
            sentId += 1
            tokens = []

    #path =  "./{}/{}".format(out_rep, outputTgFile)           
    tg.to_file(outputTg_path, mode='binary', codec='utf-8')
    print("\n\nDONE.\n\n")

print("Summaray of processed files: ")
for n,p in enumerate(conll_tg_pairs_bak): 
      print('{}:\t{:5s}: {}\n\t{:5s}: {}'.format(n,'conll',p[0],'tg',p[1]))
      if p[0] in err.keys():
            num_err = err[p[0]] 
            if num_err: print('\tnumber of errors: {}'.format(num_err))
      print('')
#*****************************
