#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# exportateur Column @ CoNLL-U -> Tier @ Praat TextGrid
# prerequisite : pympi.Praat, python-magic, javaobj (optional)
#
# auteurs :
#     Sandy Duchemin
#     Luigi Liu

from exporter_lib import *

def core_routine(conll,srcCol,pauseSign,dest,ref, num_sent_to_read = -1):
          # initialization
          tokens = []
          sentId = 0
          pauseId = 0
          cursor = 0
          err_num = 0
          dist_tot = 0

          # boucle de lecture
          for n, row in enumerate(conll) :

          # les métadonnées
              if row and len(row) < 10 :
                  metadata = row[0]
                  continue

          # token dans une phrase
              if row :
                  token = row[srcCol - 1]
                  # récolte des tokens
                  if token.strip() != pauseSign :
                      tokens.append(token)
                  else :
                      pauseId += 1

          # saute de ligne à la frontière des phrases
              else :
                  sent = ' '.join(tokens)
                  deb_print("L{} sentence no.{} '{}'".format(n,sentId,sent))

                  # try a local search from cursor to end of time with by default thld.
                  [begin,end, cursor_out, best_dist] = findTimes(tokens,ref, lowerbound=cursor, upperbound=cursor+50,thld = 0.10, pauseSign=pauseSign)
                  if cursor_out >= cursor :
                        cursor = cursor_out
                        deb_print("L{} local (begin,end) = ({:8.3f},{:8.3f})".format(n,begin,end))

                        # écrire le contenu dans le tier de destination
                        try:
                              dest.add_interval(begin=begin, end=end, value=sent, check=True)
                        except Exception as e:
                              err_print("Line {} @ CoNLL : {}".format(n,e))
                              err_num+=1

                  else:
                        # try a global search but with a more strict threshold for distance
                        [begin,end, cursor_out, best_dist] = findTimes(tokens,ref, lowerbound=0, upperbound=-1, thld = 0.05, pauseSign=pauseSign)
                        if cursor_out >= 0 :
                              # écrire le contenu dans le tier de destination
                              try:
                                    dest.add_interval(begin=begin, end=end, value=sent, check=True)
                                    deb_print("Line {} global (begin,end) = ({:8.3f},{:8.3f})".format(n,begin,end))
                              except Exception as e:
                                    err_print("Line {} @ CoNLL : {}".format(n,e))
                                    err_num+=1
                        else:
                              err_print("Search fails @ Line {} of the CoNLL".format(n))
                              err_num+=1

     		  # early break if number of sentences to read is reached
                  if sentId > num_sent_to_read and num_sent_to_read > 0 : break

                  # préparation à la prochaine phrase
                  dist_tot += best_dist;
                  sentId += 1
                  tokens = []

          return err_num,dist_tot
          
          
def core_routine_with_known_ref_tier (tg,conll_path,srcCol,pauseSign,destTierName,valideRefTierName,num_sent_to_read=-1):
        # read the ref. tier
        refTier = tg.get_tier(valideRefTierName)
        # initilize the dest. tier
        tg.remove_tier(destTierName)
        destTier = tg.add_tier(destTierName)
        # export the transcription from conll file
        with open(conll_path, 'r') as f:
                    conllReader  = csv.reader(f, delimiter='\t', quotechar='\\')
                    err_num,dist=core_routine(conllReader,srcCol,pauseSign,destTier,refTier,num_sent_to_read)
        # return error indicators
        return err_num, dist
        
def detect_ref_tier(tg,conll_path,srcCol,pauseSign,destTierName,num_sent_to_read=10):
  warning_print('Registered time reference tiers do not exist in TextGrid, launch auto-detection !')

  err_by_tier = collections.Counter()
  dist_by_tier = collections.Counter()

  # try all tier as time referece tiers one by one
  for tierName in avaliableTierNames :
          info_print('try {}'.format(tierName))
          # try 10 sentences for each tier and collect their accumulated edit distance
          err_by_tier[tierName],dist_by_tier[tierName] = \
          core_routine_with_known_ref_tier(tg,conll_path,srcCol,pauseSign,destTierName,tierName, num_sent_to_read)
  
  # remove the detination generated during trail
  tg.remove_tier(destTierName)

  # use the best one to make final exporting
  best_ref_name, best_dist = dist_by_tier.most_common()[-1]
  return best_ref_name, best_dist

if __name__ == '__main__':

      # inform state for Analor file support
      if javaobj_installed:
             info_print('\'javaobj\' detected, Analor file support will be enabled')
      else :
             warning_print('\'javaobj\' not detected, Analor file (.or) support disabled')

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
      info_print("File(s) to process : ")
      list_of_file_pair_print(conll_tg_pairs_bak,reverse = False)
      out_rep     = args.praat_out
      if not os.path.exists(out_rep):
              os.makedirs(out_rep)
      refTierNames = ['mot','MOT','TokensAlign'] # set refTierNames if you want an auto-deteciton by default
      destTierName = 'tx_new'
      pauseSign    = '#'
      srcCol       = 2 # 'FORM' (CoNLL)

      # I/O handlers
      err = collections.Counter()
      enc = collections.defaultdict()
      conll_tg_pairs = conll_tg_pairs[::-1]
      while conll_tg_pairs:
          inconllFile,inTgfile = conll_tg_pairs.pop()
          conll_path = args.conll_in+'/'+inconllFile
          inTg_path = args.praat_in+'/'+inTgfile

          info_print('\t{:s} {:s}'.format('<-',conll_path))
          # detection of textgrid file encoding:utf-8, ascii, etc.
          enc[inTgfile] = get_encoding(inTg_path)
          info_print('\t{:s} {:s} [{}]'.format('<-',inTg_path, enc[inTgfile] if enc[inTgfile] else 'unknown'))
          outputTg_path = args.praat_out+'/'+insert_to_basename(inTgfile,'_UPDATED','TextGrid')
          info_print('\t{:s} {:s} [{}]'.format('->',outputTg_path, 'binary'))

          try:
            tg     = TextGridPlus(file_path=inTg_path, codec=enc[inTgfile], analorFileEn=javaobj_installed)
          except  Exception as e:
            err_print('TextGridPlus constructor fails : {}'.format(e))
            continue
            
          # handel diff. reference tier names
          avaliableTierNames = [t.name for  t in tg.get_tiers()]
          valideRefTierNames = list(set(avaliableTierNames) & set(refTierNames))
          # make exportaiton if a ref. tier is listed in registered in refTierNames
          if valideRefTierNames:
			        err_num,dist=core_routine_with_known_ref_tier(tg,conll_path,srcCol,pauseSign,destTierName,valideRefTierNames[0])
          # ortherwise lauche ref. tier detection
          else:
                          best_ref_name,best_dist=\
                          detect_ref_tier(tg,conll_path,srcCol,pauseSign,destTierName,num_sent_to_read=10)
                          info_print('Set \'{}\' as time reference tier'.format(best_ref_name))
                          err_num, dist = core_routine_with_known_ref_tier(tg,conll_path,srcCol,pauseSign,destTierName,best_ref_name)

          err[inconllFile]=err_num
          # remark: dy default, export TextGrid object in binaray format
          tg.to_file(outputTg_path, mode='binary', codec='utf-8')
          info_print("DONE.\n")

      info_print("Summaray of processed file(s): ")
      list_of_file_pair_print(conll_tg_pairs_bak, err_cnt = err, enc_dict = enc)
      #*****************************
