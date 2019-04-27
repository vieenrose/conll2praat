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

if __name__ == '__main__':

      # filelists / tiernames / constants
      if javaobj_installed :
           warning_print('\'javaobj\' not detected, Analor file (.or) support disabled !')

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
      refTierNames = ['mot','MOT','TokensAlign']
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
            tg     = TextGridPlus(file_path=inTg_path, codec=enc[inTgfile])               #lecture du fichier textgrid (Praat)
          except  Exception as e:
            err_print(e)
            continue

          # handel diff. reference tier names
          ref = None
          for refTierName in refTierNames :
              try:
                  ref    = tg.get_tier(refTierName)  #tier de repères temporels ('mot')
                  break
              except IndexError:
                  pass
          if ref:
              dest   = tg.add_tier(destTierName) #tier de destination ('tx_new')
              with open(conll_path, 'r') as f:
                                   conllReader  = csv.reader(f, delimiter='\t', quotechar='\\')
                                   err_num,best_dist=core_routine(conllReader,srcCol,pauseSign,dest,ref)
          else:
                          warning_print('by defaut time reference tier fails, launch auto-detection !')
                          err_nums = collections.Counter()
                          dists = collections.Counter()

                          all_tier_names = [tier.name for tier in tg.get_tiers()]
                          for tierName in all_tier_names :
                                  tg.remove_tier(destTierName)
                                  dest = tg.add_tier(destTierName) #tier de destination ('tx_new')
                                  ref = tg.get_tier(tierName)
      	                          #lecture du fichier tabulaire (CoNLL-U)
                                  with open(conll_path, 'r') as f:
                                        conllReader  = csv.reader(f, delimiter='\t', quotechar='\\')
					# test for 10 sentences CoNLL to get an idea about the error rate of each tier
					# as time ref. tier
                                        err_nums[ref.name],dists[ref.name] = core_routine(conllReader,srcCol,pauseSign,dest,ref, num_sent_to_read=10)

                          if not err_nums or not dists:
                                        err_print('cannot find a good reference tier !')
                                        continue

                          # remove the output tier created during test
                          tg.remove_tier(destTierName)
                          dest   = tg.add_tier(destTierName) #tier de destination ('tx_new')
                          # get the best matched tier for time ref. use with least accumulated edit distance
                          best_ref_name, best_dist = dists.most_common()[-1]
                          debug_print('{(name of tier),(cost of tier as time ref.)}',dists) # debug
                          # final output based on the rigth ref. tier
                          info_print('detect \'{}\' as time reference tier'.format(best_ref_name))
                          ref = tg.get_tier(best_ref_name)  #tier de repères temporels ('mot')
                          with open(conll_path, 'r') as f:
                                        conllReader  = csv.reader(f, delimiter='\t', quotechar='\\')
                                        err_num,best_dist=core_routine(conllReader,srcCol,pauseSign,dest,ref)

          err[inconllFile]=err_num
          tg.to_file(outputTg_path, mode='binary', codec='utf-8')
          info_print("\n\nDONE.\n\n")

      info_print("Summaray of processed file(s): ")
      list_of_file_pair_print(conll_tg_pairs_bak, err_cnt = err, enc_dict = enc)
      #*****************************
