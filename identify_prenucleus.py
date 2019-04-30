#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[*conll2praat*] identifier un ensemble ordonné des *intervalles temporelles
étiquetées* aux *composants illocutoires (CI)* à chacun des *prénoyeaux* la
transcription reportée en tant que la *tire* **tx_new**.
"""

WARNING_EN = False
ERR_EN = False

# todo: solve issues with embedded prenucleus


def core_routine(sents, srcCol, pauseSign, dest, ref, num_sent_to_read=-1):
    # initialization
    tokens = []
    sentId = 0
    pauseId = 0
    cursor = 0
    err_num = 0
    dist_tot = 0

    for n, sent in enumerate(sents):
        # try a local search from cursor to end of time with by default thld.
        tokens = sent.split(' ')
        [begin, end, cursor_out, best_dist] = findTimes(tokens,
                                                        ref,
                                                        lowerbound=cursor,
                                                        upperbound=cursor + 50,
                                                        thld=0.10,
                                                        pauseSign=pauseSign)
        if cursor_out >= cursor:
            cursor = cursor_out
            deb_print("L{} local (begin,end) = ({:8.3f},{:8.3f})".format(
                n, begin, end))

            # écrire le contenu dans le tier de destination
            try:
                dest.add_interval(begin=begin, end=end, value=sent, check=True)
            except Exception as e:
                err_print("Line {} @ CoNLL : {}".format(n, e))
                err_num += 1

        else:
            # try a global search but with a more strict threshold for distance
            [begin, end, cursor_out,
             best_dist] = findTimes(tokens,
                                    ref,
                                    lowerbound=0,
                                    upperbound=-1,
                                    thld=0.05,
                                    pauseSign=pauseSign)
            if cursor_out >= 0:
                # écrire le contenu dans le tier de destination
                try:
                    dest.add_interval(begin=begin,
                                      end=end,
                                      value=sent,
                                      check=True)
                    deb_print("Line {} global (begin,end) = ({:8.3f},{:8.3f})".
                              format(n, begin, end))
                except Exception as e:
                    err_print("Line {} @ CoNLL : {}".format(n, e))
                    err_num += 1
            else:
                err_print("Search fails @ Line {} of the CoNLL".format(n))
                err_num += 1

        # early break if number of sentences to read is reached
        if sentId > num_sent_to_read and num_sent_to_read > 0: break

        # préparation à la prochaine phrase
        dist_tot += best_dist
        sentId += 1
        tokens = []

    return err_num, dist_tot


def core_routine_with_known_ref_tier(tg,
                                     sents,
                                     srcCol,
                                     pauseSign,
                                     valideRefTierName,
                                     num_sent_to_read=-1):
    # read the ref. tier
    refTier = tg.get_tier(valideRefTierName)
    # initilize the dest. tier
    testDestTier = tg.add_tier("test")
    # export the transcription from conll file
    err_num, dist = core_routine(sents, srcCol, pauseSign, testDestTier,
                                 refTier, num_sent_to_read)
    tg.remove_tier("test")

    # return error indicators
    return err_num, dist


def detect_ref_tier(tg,
                    sents,
                    srcCol,
                    pauseSign,
                    destTierName,
                    avaliableTierNames,
                    num_sent_to_read=10):
    warning_print(
        'Registered time reference tiers do not exist in TextGrid, launch auto-detection !'
    )

    err_by_tier = collections.Counter()
    dist_by_tier = collections.Counter()

    # try all tier as time referece tiers one by one
    for tierName in avaliableTierNames:
        info_print('try {}'.format(tierName))
        # try 10 sentences for each tier and collect their accumulated edit distance
        err_by_tier[tierName],dist_by_tier[tierName] = \
                core_routine_with_known_ref_tier(tg,sents,srcCol,pauseSign,tierName, num_sent_to_read)

    # use the best one to make final exporting
    best_ref_name, best_dist = dist_by_tier.most_common()[-1]
    return best_ref_name, best_dist
    """
    [begin, end, cursor_out, best_dist] = findTimes(tokens,
                                                    ref,
                                                    lowerbound=cursor,
                                                    upperbound=cursor + 50,
                                                    thld=0.10,
                                                    pauseSign=pauseSign)
    """


from exporter_lib import *

if __name__ == '__main__':

    file_path = 'export/ABJ_GWA_03_M_UPDATED.TextGrid'
    fileout_path = insert_to_basename(file_path, '_ADDED_PRENUCLEUS',
                                      'TextGrid')
    encoding = get_encoding(file_path)
    txTierName = 'tx_new'
    tg = TextGridPlus(file_path=file_path,
                      codec=encoding,
                      analorFileEn=javaobj_installed)
    tx = tg.get_tier(txTierName)
    avaliableTierNames = [
        t.name for t in tg.get_tiers()
        if t.name != 'tx' and t.name != txTierName
    ]
    tg.add_tier('prenucleus_ic_id')
    tg.add_tier('prenucleus_ic_value')
    prenucleus_ic_id = tg.get_tier('prenucleus_ic_id')
    prenucleus_ic_value = tg.get_tier('prenucleus_ic_value')

    sents = [interval[-1] for interval in tx.get_all_intervals()]
    all_IC_intervals = []

    best_ref_name, best_dist = detect_ref_tier(
        tg,
        sents,
        srcCol=2,
        pauseSign="#",
        destTierName=txTierName,
        avaliableTierNames=avaliableTierNames,
        num_sent_to_read=10)
    info_print('Set \'{}\' as time reference tier'.format(best_ref_name))

    refTier = tg.get_tier(best_ref_name)

    class subRefTier:
        def __init__(self, tier, tmin, tmax):
            all_intervals = tier.get_all_intervals()
            self.intervals = [
                interval for interval in all_intervals
                if interval[0] >= tmin and interval[1] <= tmax
            ]

        def get_all_intervals(self):
            return self.intervals

    for interval in tx.get_all_intervals():
        tmin_sent, tmax_sent, sent = interval
        if sent:
            # segment sentence in illocutionrary units
            IUs = sent.split('\\')
            for n, IU in enumerate(IUs):

                # identify prenucleus and extract illocutionrary compoents
                IC_intervals = []
                if ' < ' in IU:
                    # identify the temporal limits of IU
                    # inside the temporal limits of sentence
                    ref = subRefTier(refTier, tmin_sent, tmax_sent)
                    tokens = IU.split(' ')
                    [tmin_IU, tmax_IU, cursor_out,
                     best_dist] = findTimes(tokens=tokens,
                                            refTier=ref,
                                            lowerbound=0,
                                            upperbound=-1,
                                            thld=1000,
                                            pauseSign="#")
                    #print(tmin_IU, tmax_IU)
                    ICs = IU.split('<')[:-1]
                    cursor = 0
                    for IC in ICs:
                        ref = subRefTier(refTier, tmin_IU, tmax_IU)
                        tokens = IC.split(' ')
                        [tmin_IC, tmax_IC, cursor,
                         best_dist] = findTimes(tokens=tokens,
                                                refTier=ref,
                                                lowerbound=cursor,
                                                upperbound=-1,
                                                thld=1000,
                                                pauseSign="#")
                        IC_intervals.append((tmin_IC, tmax_IC, IC))

                if IC_intervals:
                    all_IC_intervals.append(IC_intervals)

    for k, ICs_of_IU in enumerate(all_IC_intervals):
        for n, IC_interval in enumerate(ICs_of_IU):
            tmin, tmax, IC = IC_interval
            print("{}.{}, ({},{}), '{}".format(k, n, tmin, tmax, IC))
            prenucleus_ic_id.add_interval(begin=tmin,
                                          end=tmax,
                                          value='{}:{}'.format(k, n),
                                          check=True)
            prenucleus_ic_value.add_interval(begin=tmin,
                                             end=tmax,
                                             value=IC,
                                             check=True)
    print('->{}'.format(fileout_path))
    tg.to_file(filepath=fileout_path, codec='utf-8', mode='binary')
