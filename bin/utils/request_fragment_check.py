import os
import sys
import re 
import argparse
import textwrap
from datetime import datetime
sys.path.append('/afs/cern.ch/cms/PPD/PdmV/tools/McM/')
from rest import McM

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
            ------------------------------------------------ 
               This script currently checks for the following to give an OK, WARNING, or ERROR
               and does a patch for the MG5_aMC LO nthreads problem if needed. 
            
               WARNINGS:
                  * [WARNING] if time per event > 150 seconds
                  * [WARNING] if CMSSW version is not 10_2 and 9_3 and 7_1
                  * [WARNING] total number of events > 100000000
                  * [WARNING] powheg+pythia sample contains Pythia8PowhegEmissionVetoSettings 
                              - warning to check whether it is a loop induced process
                  * [WARNING] if CP5 tune is used but campaign is not Fall18 or Fall17
                  * [WARNING] if Fall18 campaing but no parton shower weights configuration in the fragment
                  * [WARNING] At least one of the MG5_aMC@NLO tmpdir patches is missing."
                  *                    --> Please check that you use:"
                  *                        >=  CMSSW_7_1_32_patch1 in 7_1_X or  
                  *                        >= CMSSW_9_3_9_patch1 in 9_3_X or
                  *                        >= 10_1_3 in 10_1_X or" 
                  *                        >= CMSSW_10_2_0_pre2 in 10_2_X.
                  *                        Your request uses version xxxxx :
                  *                         If you are not using a proper CMSSW version, please switch to that or
                  *                         re-create the gridpack using the updated genproductions area
		  * [WARNING] Filters in the fragment but filter efficiency = 1
                  * [WARNING] Matched sample but matching efficiency is 1!
                  * [WARNING] nJetMax is not equal to the number of jets specified in the proc card
                  * [WARNING] nJetMax(="+str(nJetMax)+") is not equal to the number of jets specified in the proc card(="+str(jet_count)+")."
                  *            Is it because this is an exclusive production with additional samples with higher multiplicity generated separately?"

               ERRORS:
                  * [ERROR] Memory is not 2300 or 4000 MB"
                  * [ERROR] Memory is 2300 MB while number of cores is XX but not = 1
                  * [ERROR] Memory is 4000 MB while number of cores is 1 but not = 2,4 or 8
                  * [ERROR] Gridpack should have used cvmfs path instead of eos path
                  * [ERROR] MG5_aMC@NLO multi-run patch missing in gridpack - please re-create a gridpack
                  *            using updated genproductions area
                  * [ERROR] May be wrong fragment: powheg/madgraph/mcatnlo in dataset name but settings in 
                            fragment not correct or vice versa"
                  * [ERROR] Fragment may be wrong: check "+word+" settings in the fragment"
                  *         if madgraph: You run MG5_aMC@NLO at LO but you have  Pythia8aMCatNLOSettings_cfi in fragment
                  *                --> please remove it from the fragment
                  * [ERROR] Tune configuration wrong in the fragment
                  * [ERROR] PS weights in config but CMSSW version is not 10_2_3 - please check!	
                  * [ERROR] Parton shower weight configuration not OK in the fragment
                  * [ERROR] You are using a loop induced process, [noborn=QCD].
                  *         Please remove all occurances of Pythia8aMCatNLOSettings from the fragment
                  * [ERROR] You are using a loop induced process, [noborn=QCD].
                  *         Please remove all TimeShower:nPartonsInBorn from the fragment 

               The script also checks if there is no fragment there is a hadronizer used.'''))
parser.add_argument('--prepid', type=str, help="check mcm requests using prepids", nargs='+')
parser.add_argument('--ticket', type=str, help="check mcm requests using ticket number", nargs=1)
parser.add_argument('--bypass_status', help="don't check request status in mcm", action='store_false')
parser.add_argument('--bypass_validation', help="proceed to next prepid even if there are errors", action='store_true')
parser.add_argument('--apply_many_threads_patch', help="apply the many threads MG5_aMC@NLO LO patch if necessary", action='store_true')
parser.add_argument('--dev', help="Run on DEV instance of McM", action='store_true')
parser.add_argument('--debug', help="Print debugging information", action='store_true')
args = parser.parse_args()

if args.prepid is not None:
    print "---> "+str(len(args.prepid))+" requests will be checked:"
    prepid = args.prepid
print " "


# Use no-id as identification mode in order not to use a SSO cookie
mcm = McM(id='no-id', dev=args.dev, debug=args.debug)


def get_request(prepid):
    result = mcm._McM__get('public/restapi/requests/get/%s' % (prepid))
    if not result:
        return {}

    result = result.get('results', {})
    return result


def get_range_of_requests(query):
    result = mcm._McM__put('public/restapi/requests/listwithfile', data={'contents': query})
    if not result:
        return {}

    result = result.get('results', {})
    return result


def get_ticket(prepid):
    result = mcm._McM__get('public/restapi/mccms/get/%s' % (prepid))
    if not result:
        return {}

    result = result.get('results', {})
    return result


if args.dev:
    print "Running on McM DEV!\n"


def root_requests_from_ticket(ticket_prepid, include_docs=False):
    """
    Return list of all root (first ones in the chain) requests of a ticket.
    By default function returns list of prepids.
    If include_docs is set to True, function will return whole documents
    """
    mccm = get_ticket(ticket_prepid)
    query = ''
    for root_request in mccm.get('requests',[]):
        if isinstance(root_request,str) or isinstance(root_request,unicode):
            query += '%s\n' % (root_request)
        elif isinstance(root_request,list):
             # List always contains two elements - start and end of a range
            query += '%s -> %s\n' % (root_request[0], root_request[1])
    requests = get_range_of_requests(query)
    if not include_docs:
        # Extract only prepids
        requests = [r['prepid'] for r in requests]
    return requests


if args.ticket is not None:
    ticket = args.ticket
    ticket = ticket[0]
    print "------------------------------------"
    print "--> Ticket = "+ticket
    print "------------------------------------"
#    print(root_requests_from_ticket(ticket))
    prepid = []
    for rr in root_requests_from_ticket(ticket):
        if 'GS' in rr or 'wmLHE' in rr or 'pLHE' in rr or 'FS' in rr:
            prepid.append(rr)


prepid = list(set(prepid)) #to avoid requests appearing x times if x chains have the same request 

print "Current date and time: %s" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
for x in prepid:
    print(x)

for num in range(0,len(prepid)):
    res = get_request(prepid[num])
    if len(res) == 0 :
        print "***********************************************************************************"
        print "Something's wrong - can not get the request parameters"
        print "***********************************************************************************"

    my_path =  '/tmp/'+os.environ['USER']+'/gridpacks/'
    print ""
    print "***********************************************************************************"

    # Create an array of one element so further for loop would not be removed and code re-indented
    res = [res]
    for r in res:
        pi = r['prepid']
        dn = r['dataset_name']
        te = r['time_event']
        totalevents = r['total_events']
        cmssw = r['cmssw_release']
        mem = r['memory']
        filter_eff = r['generator_parameters'][-1]['filter_efficiency']
        match_eff = r['generator_parameters'][-1]['match_efficiency']
        print pi+"    Status= "+r['status']
	print dn
        if args.bypass_status and r['status'] != "defined":
	    print "--> Skipping since the request is not in defined state"
	    print "--> Use --bypass_status option to look at all requests irrespective of state" 
	    continue
        check = []
        purepythiacheck = []
        powhegcheck = []
        tunecheck = []
        psweightscheck = [] #ps = parton shower
        MGpatch = []
        MGpatch2 = []
        ME = ["PowhegEmissionVeto","aMCatNLO"] # ME = matrix element
        MEname = ["powheg","madgraph","mcatnlo","jhugen"]
        tune = ["CP5","CUEP8M1","CP1","CP2","CP3","CP4","CP5TuneUp","CP5TuneDown"] 
        mcatnlo_flag = 0
        loop_flag = 0
        knd =  -1
	slha_flag = 0
        nPartonsInBorn_flag = 0
        matching = 10
        ickkw = 'del' # ickkw = matching parameter in madgraph
        nJetMax = 100
	jet_count_tmp = []
        nFinal = 100
        jet_count = 0
        bw = -1 
        error = 0
        warning = 0
        if "herwig" in dn.lower() or "comphep" in dn.lower() or "calchep" in dn.lower():
            print "* [WARNING] herwig or comphep or calchep sample. Please check manually"
            warning = warning + 1
            continue
        for item in te:
            timeperevent = float(item)
        if timeperevent > 150.0 :
            print "* [WARNING] Large time/event="+str(timeperevent)+" - please check"
            warning = warning + 1
        if '10_2' not in cmssw and '9_3' not in cmssw and '7_1' not in cmssw :
            print "* [WARNING] Are you sure you want to use "+cmssw+"release which is not standard"
            print "*           which may not have all the necessary GEN code."
            warning = warning + 1
        if totalevents >= 100000000 :
            print "* [WARNING] Is "+str(totalevents)+" events what you really wanted - please check!"
            warning = warning + 1
        os.popen('wget -q https://cms-pdmv.cern.ch/mcm/public/restapi/requests/get_fragment/'+pi+' -O '+pi).read()
        fsize = os.path.getsize(pi)
        f1 = open(pi,"r") 
        f2 = open(pi+"_tmp","w")
        data_f1 = f1.read()
        data_f2 = re.sub(r'(?m)^ *#.*\n?', '',data_f1)
        f1.close()
        f2.write(data_f2)
        f2.close()
        os.system('mkdir -p '+my_path+'/'+pi)
        os.system('mkdir -p '+my_path+'/eos/'+pi)
        os.system('mv '+pi+'_tmp '+pi)
        os.system('cp '+pi+' '+my_path+'/'+pi+'/.')
        os.system('wget -q https://cms-pdmv.cern.ch/mcm/public/restapi/requests/get_test/'+pi+' -O '+pi+'_get_test')
        gettest = os.popen('grep cff '+pi+'_get_test'+' | grep curl').read()
        if fsize == 0:
            print "* [WARNING] No fragment associated to this request"
            print "*           if this is the hadronizer you intended to use?: "+gettest
            warning = warning + 1
        ttxt = os.popen('grep nThreads '+pi+'_get_test').read()
        if int(os.popen('grep -c nThreads '+pi+'_get_test').read()) == 0 :
            nthreads = 1
        else :
            nthreads = int(re.search('nThreads(.*?) --',ttxt).group(1))
        if "HIN-HINPbPbAutumn18GSHIMix" not in pi and "HINPbPbAutumn18wmLHEGSHIMix" not in pi:    
            if mem != 2300 and mem != 4000:
                print "* [ERROR] Memory is not 2300 or 4000 MB"
                error = error + 1
            if mem == 2300 and nthreads != 1 :
                print "* [ERROR] Memory is "+str(mem)+" MB while number of cores is "+str(nthreads)+" but not = 1"
                error = error + 1
            if mem == 4000 and nthreads == 1 :
                print "* [ERROR] Memory is "+str(mem)+" MB while number of cores is "+str(nthreads)+" but not = 2,4 or 8"
                error = error + 1
        if "HIN-HINPbPbAutumn18GSHIMix" in pi and "HINPbPbAutumn18wmLHEGSHIMix" in pi:
            if mem != 14700 and mem != 5900 and mem != 4000 and mem != 2300:
                print "* [ERROR] HIN-HINPbPbAutumn18GSHIMix or HINPbPbAutumn18wmLHEGSHIMix campaign but Memory is not 14700, 5900, 400, or 2300 MB"
                error = error + 1
            if mem == 14700 and nthreads != 8 :
                print "* [ERROR] Memory is "+str(mem)+" MB while number of cores is "+str(nthreads)+" but not = 8"
                error = error + 1
            if mem == 5900 and nthreads != 4 :
                print "* [ERROR] Memory is "+str(mem)+" MB while number of cores is "+str(nthreads)+" but not = 4"
                error = error + 1
            if mem == 4000 and nthreads != 2 :
                print "* [ERROR] Memory is "+str(mem)+" MB while number of cores is "+str(nthreads)+" but not = 2"
                error = error + 1
            if mem == 2300 and nthreads != 1:
                print "* [ERROR] Memory is "+str(mem)+" MB while number of cores is "+str(nthreads)+" but not = 1"
                error = error + 1
#        os.system('wget -q https://cms-pdmv.cern.ch/mcm/public/restapi/requests/get_fragment/'+pi+' -O '+pi)
#        os.system('mkdir -p '+my_path+'/'+pi)
#        os.system('mkdir -p '+my_path+'/eos/'+pi)
        if int(os.popen('grep -c eos '+pi).read()) == 1 :
            print "* [ERROR] Gridpack should have used cvmfs path instead of eos path"
            error = error + 1
        if int(os.popen('grep -c nPartonsInBorn '+pi).read()) == 1:
            nPartonsInBorn_flag = 1
            print(os.popen('grep nPartonsInBorn '+pi).read())
        if int(os.popen('grep -c nJetMax '+pi).read()) == 1:  
            nJetMax = os.popen('grep nJetMax '+pi).read()
            nJetMax = re.findall('\d+',nJetMax)
            nJetMax = int(nJetMax[0])
        if int(os.popen('grep -c nFinal '+pi).read()) == 1:
            nFinal = os.popen('grep nFinal '+pi).read()
            nFinal =  re.findall('\d+',nFinal)
            nFinal = int(nFinal[0])
            print "nFinal="+str(nFinal)
        for ind, word in enumerate(MEname):
            if ind == 3:
                break
            if word in dn.lower() :
                if ind == 2 :
                    knd = 1 
                else :
                    knd = ind
                check.append(int(os.popen('grep -c pythia8'+ME[knd]+'Settings '+pi).read()))
                check.append(int(os.popen('grep -c "from Configuration.Generator.Pythia8'+ME[knd]+'Settings_cfi import *" '+pi).read()))
                check.append(int(os.popen('grep -c "pythia8'+ME[knd]+'SettingsBlock," '+pi).read()))
                if check[2] == 1:
                    mcatnlo_flag = 1
#                os.system('wget -q https://cms-pdmv.cern.ch/mcm/public/restapi/requests/get_fragment/'+pi+' -O '+my_path+'/'+pi+'/'+pi)   
                gridpack_cvmfs_path = os.popen('grep \/cvmfs '+my_path+'/'+pi+'/'+pi+'| grep -v \'#args\' ').read()
                gridpack_cvmfs_path = gridpack_cvmfs_path.split('\'')[1]
                gridpack_eos_path = gridpack_cvmfs_path.replace("/cvmfs/cms.cern.ch/phys_generator","/eos/cms/store/group/phys_generator/cvmfs")
                print gridpack_cvmfs_path
		print gridpack_eos_path
		if int(os.popen('grep -c slha '+pi).read()) != 0 or int(os.popen('grep -c \%i '+pi).read()) != 0 or int(os.popen('grep -c \%s '+pi).read()) != 0:
		    slha_flag = 1
                if slha_flag == 1:
                    if int(os.popen('grep -c \%i '+pi).read()) != 0:
                        gridpack_cvmfs_path = gridpack_cvmfs_path.replace("%i","*")
                    if int(os.popen('grep -c \%s '+pi).read()) != 0:    
                        gridpack_cvmfs_path = gridpack_cvmfs_path.replace("%s","*")
                    slha_all_path = os.path.dirname(gridpack_eos_path)    
                    gridpack_cvmfs_path = os.popen('ls '+ gridpack_cvmfs_path+' | head -1 | tr \'\n\' \' \'').read()
                    print "SLHA request - checking single gridpack:"
                    print gridpack_cvmfs_path  
                os.system('tar xf '+gridpack_cvmfs_path+' -C '+my_path+'/'+pi)	
                if ind == 0:
                    file_pwg_check =  my_path+'/'+pi+'/'+'pwhg_checklimits'
                    if os.path.isfile(file_pwg_check) is True :
                        print "grep from powheg pwhg_checklimits files"
#                        print(os.popen('grep emitter '+file_pwg_check+' | head -n 5').read())
                        nemit = os.popen('grep emitter '+file_pwg_check+' | head -n 1').read().replace('process','').replace('\n','').split(',')
                        nemitsplit = nemit[1].split()
                        print nemitsplit
                        nemitsplit = nemitsplit[2:]
                        nfinstatpar = len(nemitsplit)-nemitsplit.count('0')
                        if nfinstatpar == nFinal :
                            print "* [OK] nFinal(="+str(nFinal) + ") is equal to the number of final state particles before decays (="+str(nfinstatpar)+")"
                        if nfinstatpar != nFinal :
                            print "* [ERROR] nFinal(="+str(nFinal) + ") is NOT equal to the number of final state particles before decays (="+str(nfinstatpar)+")"
                            error = error + 1
                    with open(os.path.join(my_path, pi, "runcmsgrid.sh")) as f:
                        content = f.read()
                        match = re.search(r"""process=(["']?)([^"']*)\1""", content)
                    if match:
                        process = match.group(2)
                        if process == "gg_H_quark-mass-effects":
                            #for more information on this check, see
                            #https://its.cern.ch/jira/browse/CMSCOMPPR-4874

                            #this configuration is ok at 125 GeV, but causes trouble starting at around 170:
                            #  ncall1=50000, itmx1=5, ncall2=50000, itmx2=5, foldcsi=1, foldy=1, foldphi=1
                            #from mH=300 GeV to 3 TeV, this configuration seems to be fine:
                            #  ncall1=550000, itmx1=7, ncall2=75000, itmx2=5, foldcsi=2, foldy=5, foldphi=2

                            #I'm printing warnings here for anything less than the second configuration.
                            #Smaller numbers are probably fine at low mass
                            desiredvalues = {
                              "ncall1": 550000,
                              "itmx1": 7,
                              "ncall2": 75000,
                              "itmx2": 5,
                              "foldcsi": 2,
                              "foldy": 5,
                              "foldphi": 2,
                            }
                            with open(os.path.join(my_path, pi, "powheg.input")) as f:
                                content = f.read()
                                matches = dict((name, re.search(r"^"+name+" *([0-9]+)", content, flags=re.MULTILINE)) for name in desiredvalues)
                            bad = False
                            for name, match in matches.iteritems():
                                if match:
                                    actualvalue = int(match.group(1))
                                    if actualvalue < desiredvalues[name]:
                                        bad = True
                                        print "* [WARNING] {0} = {1}, should be at least {2} (may be ok if hmass < 150 GeV, please check!)".format(name, actualvalue, desiredvalues[name])
                                        warning = warning + 1
                                else:
                                    bad = True
                                    print "* [ERROR] didn't find "+name+" in powheg.input"
                                    error = error + 1
                            if not bad:
                                print "* [OK] integration grid setup looks ok for gg_H_quark-mass-effects"
                    else:
                        print "* [WARNING] Didn't find powheg process in runcmsgrid.sh"
                        warning = warning + 1

                if ind > 0:
                    filename = my_path+'/'+pi+'/'+'process/madevent/Cards/proc_card_mg5.dat'
                    fname_p2 = my_path+'/'+pi+'/'+'process/Cards/proc_card.dat'
                    fname_p3 = my_path+'/'+pi+'/'+'process/Cards/proc_card_mg5.dat'
                    if os.path.isfile(fname_p2) is True :
                        filename = fname_p2
                    if os.path.isfile(fname_p3) is True :
                        filename = fname_p3
                    print filename    
                    if os.path.isfile(filename) is True :
                        loop_flag = int(os.popen('more '+filename+' | grep -c "noborn=QCD"').read())
                        gen_line = os.popen('grep generate '+filename).read()
                        print(gen_line)
                        proc_line = os.popen('grep process '+filename).read()
                        print(proc_line)
                        if gen_line.count('@') < proc_line.count('@'):
                            nproc = proc_line.count('@')
                            nproc = '@'+str(nproc)
#                            proc_line = proc_line.split('\n')
			    proc_line = proc_line.split('add process')	
#                            jet_line = next((s for s in proc_line if nproc in s), None).replace('add process','')
			    jet_line = proc_line[len(proc_line)-1]
			    jet_line_arr = jet_line.split(',')	
			    for x in range(0,len(jet_line_arr)):
			        jet_count_tmp.append(jet_line_arr[x].count('j') + jet_line_arr[x].count('b') + jet_line_arr[x].count('c'))	 
		            jet_count = max(jet_count_tmp)
                        else :
                            jet_line = gen_line.replace('generate','')
                            jet_count = jet_line.count('j') + jet_line.count('b') + jet_line.count('c')
                        if nJetMax == jet_count:
                            print "* [OK] nJetMax(="+str(nJetMax) + ") is equal to the number of jets in the process(="+str(jet_count)+")"
                        if nJetMax != jet_count and str(jet_count)+"jet" not in dn.lower() and gen_line.count('@') != 0:
                            print "* [WARNING] nJetMax(="+str(nJetMax)+") is NOT equal to the number of jets specified in the proc card(="+str(jet_count)+")"
                            warning = warning + 1
                        if nJetMax != jet_count and str(jet_count)+"jet" in dn.lower():
                            print "* [WARNING] nJetMax(="+str(nJetMax)+") is not equal to the number of jets specified in the proc card(="+str(jet_count)+")."
                            print "*           Is it because this is an exclusive production with additional samples with higher multiplicity generated separately?"
                            warning = warning + 1                         
                    fname = my_path+'/'+pi+'/'+'process/madevent/Cards/run_card.dat'
                    fname2 = my_path+'/'+pi+'/'+'process/Cards/run_card.dat'
                    if os.path.isfile(fname) is True :
                       ickkw = os.popen('more '+fname+' | tr -s \' \' | grep "= ickkw"').read()
                       bw = os.popen('more '+fname+' | tr -s \' \' | grep "= bwcutoff"').read()
                    elif os.path.isfile(fname2) is True :    
                       ickkw = os.popen('more '+fname2+' | tr -s \' \' | grep "= ickkw"').read()
                       bw = os.popen('more '+fname2+' | tr -s \' \' | grep "= bwcutoff"').read()
                    else:
                        print "[ERROR] Although the name of the dataset has ~Madgraph, the gridpack doesn't seem to be a MG5_aMC one. Please check."
                        error = error + 1
                        break
                    test_bw = bw.split() 
                    if float(test_bw[0]) > 15.:
                        print " [WARNING] bwcutoff set to "+str(test_bw[0])+". Note that large bwcutoff values can cause problems in production."
                        warning = warning + 1
                    matching = int(re.search(r'\d+',ickkw).group())
                    ickkw = str(ickkw)  
                    if matching == 1 or matching == 2:
                        if match_eff == 1:
                            print "* [WARNING] Matched sample but matching efficiency is 1!"
                            warning = warning + 1
                    if ind < 2:
                        MGpatch.append(int(os.popen('more '+my_path+'/'+pi+'/'+'runcmsgrid.sh | grep -c "FORCE IT TO"').read()))
                        MGpatch.append(int(os.popen('grep -c _CONDOR_SCRATCH_DIR '+my_path+'/'+pi+'/'+'mgbasedir/Template/LO/SubProcesses/refine.sh').read()))
                        MGpatch.append(int(os.popen('grep -c _CONDOR_SCRATCH_DIR '+my_path+'/'+pi+'/'+'process/madevent/SubProcesses/refine.sh').read()))
                        if MGpatch[0] == 1 and MGpatch[1] == 1 and MGpatch[2] == 1:
                            print "* [OK] MG5_aMC@NLO leading order patches OK in gridpack"
                        if MGpatch[0] != 1:
                            print "* [ERROR] MG5_aMC@NLO multi-run patch missing in gridpack - please re-create a gridpack"
                            print "*            using updated genproductions area"
                            error = error + 1
                        if MGpatch[1] == 0 or MGpatch[2] == 0:
                            if '10_2' not in cmssw and '9_3' not in cmssw and '7_1' not in cmssw :
                                print "* [ERROR] At least one of the MG5_aMC@NLO tmpdir patches is missing."
                                print "* And the request is using a version "+str(cmssw)+" that does not contain the patch."
                                print "* Please use >= 7_1_32_patch1 or CMSSW_9_3_9_patch1 or 10_2_0_pre2"
                                error = error + 1 
                            elif '7_1' in cmssw:
                                test_version = cmssw.split('_')
                                if (len(test_version) == 4 and int(test_version[3]) < 33) or (len(test_version) == 5 and (int(test_version[3]) < 32 or (int(test_version[3]) == 32 and "patch1" not in cmssw))):
                                    print "* [ERROR] At least one of the MG5_aMC@NLO tmpdir patches is missing."
                                    print "* And the request is using a version "+str(cmssw)+" that does not contain the patch."
                                    print "* In this release, please at least use CMSSW_7_1_32_patch1"
                                    error = error + 1
                            elif '9_3' in cmssw:
                                test_version = cmssw.split('_')
                                if (len(test_version) == 4 and int(test_version[3]) < 10) or (len(test_version) == 5 and (int(test_version[3]) < 9 or (int(test_version[3]) == 9 and "patch1" not in cmssw))):
                                    print "* [ERROR] At least one of the MG5_aMC@NLO tmpdir patches is missing."
                                    print "* And the request is using a version "+str(cmssw)+" that does not contain the patch."
                                    print "* In this release, please at least use CMSSW_9_3_9_patch1"
                                    error = error + 1
                            elif '10_2' in cmssw:
                                test_version = cmssw.split('_')
                                if len(test_version) == 4 and int(test_version[3]) < 1:
                                    print "* [ERROR] At least one of the MG5_aMC@NLO tmpdir patches is missing."
                                    print "* And the request is using a version "+str(cmssw)+" that does not contain the patch."
                                    print "* In this release, please at least use CMSSW_10_2_0_pre2"
                                    error = error + 1
                        print "*"    
                        print "-------------------------MG5_aMC LO/MLM Many Threads Patch Check --------------------------------------"   
                        ppp_ind_range = 0
                        if slha_flag == 1:
                            slha_file_list =  os.listdir(slha_all_path)
                            ppp_ind_range = len(slha_file_list)
                        if slha_flag == 0:
                            ppp_ind_range = 1
                        for ppp in range(0,ppp_ind_range):
                            del MGpatch2[:]
                            if slha_flag == 1:
                                gridpack_cvmfs_path_tmp = slha_all_path+'/'+slha_file_list[ppp]
                                if "runmode0_TEST" in gridpack_cvmfs_path_tmp:
                                    continue
                                gridpack_cvmfs_path = gridpack_cvmfs_path_tmp
                                gridpack_eos_path = gridpack_cvmfs_path_tmp.replace("/cvmfs/cms.cern.ch/phys_generator","/eos/cms/store/group/phys_generator/cvmfs")
                            os.system('tar xf '+gridpack_eos_path+' -C '+my_path+'/eos/'+pi)
                            MGpatch2.append(int(os.popen('more '+my_path+'/'+pi+'/'+'runcmsgrid.sh | grep -c "To overcome problem of taking toomanythreads"').read()))
                            MGpatch2.append(int(os.popen('more '+my_path+'/eos/'+pi+'/'+'runcmsgrid.sh | grep -c "To overcome problem of taking toomanythreads"').read()))
                            if MGpatch2[1] == 1:
                                print "* [OK] MG5_aMC@NLO LO nthreads patch OK in EOS"
                            if MGpatch2[0] == 1:
                                print "* [OK] MG5_aMC@NLO LO nthreads patch OK in CVMFS"
                            if MGpatch2[0] == 0 and MGpatch2[1] == 1:
                                print "* [OK] MG5_aMC@NLO LO nthreads patch not made in CVMFS but done in EOS waiting for CVMFS-EOS synch"
                            if MGpatch2[1] == 0:
                                print "* [ERROR] MG5_aMC@NLO LO nthreads patch not made in EOS"
                                error = error + 1
                                if args.apply_many_threads_patch:
                                    print "Patching for nthreads problem... please be patient."
                                    if slha_flag == 0: 
                                        os.system('python ../../Utilities/scripts/update_gridpacks_mg242_thread.py --prepid '+pi)
                                    if slha_flag == 1:
                                        os.system('python ../../Utilities/scripts/update_gridpacks_mg242_thread.py --gridpack '+gridpack_cvmfs_path)
                            print "-------------------------EOF MG5_aMC LO/MLM Many Threads Patch Check ----------------------------------"
                            print "*"
                if matching >= 2 and check[0] == 2 and check[1] == 1 and check[2] == 1 :
                    print "* [OK] no known inconsistency in the fragment w.r.t. the name of the dataset "+word
                    if matching > 3 and os.path.isfile(file_pwg_check) is False :
                        print "* [WARNING] To check manually - This is a Powheg NLO sample. Please check 'nFinal' is"
                        print "*               set correctly as number of final state particles (BEFORE THE DECAYS)"
                        print "*                                   in the LHE other than emitted extra parton."
                        warning = warning + 1
                elif matching == 1 and check[0] == 0 and check[1] == 0 and check[2] == 0 :    
                    print "* [OK] no known inconsistency in the fragment w.r.t. the name of the dataset "+word
                    print "* [WARNING] To check manually - This is a MadGraph LO sample. Please check 'JetMatching:nJetMax' ="+str(nJetMax)+" is OK and"
                    print "*            correctly set as number of partons in born matrix element for highest multiplicity."
                    warning = warning + 1
                elif matching == 0 and word == "madgraph" and check[0] == 0 and check[1] == 0 and check[2] == 0 :
                    print "* [OK] no known inconsistency in the fragment w.r.t. the name of the dataset "+word
                elif matching == 0 and word == "mcatnlo" and check[0] == 2 and check[1] == 1 and check[2] == 1 and loop_flag != 1:
                    print "* [OK] no known inconsistency in the fragment w.r.t. the name of the dataset "+word
                    print "* [WARNING] Is this a MadGraph NLO sample without matching. Please check 'TimeShower:nPartonsInBorn'"
                    print "*                                                   is set correctly as number of coloured particles"
                    print "*                                                  (before resonance decays) in born matrix element."
		    warning = warning + 1	
                else:     
                    print "* [ERROR] Fragment may be wrong: check "+word+" settings in the fragment"
                    error = error + 1
                    if matching <= 1 and word == "madgraph":
                        print "*        You run MG5_aMC@NLO at LO but you have  Pythia8aMCatNLOSettings_cfi in fragment"
                        print "*           --> please remove it from the fragment"
                    if word == "powheg" :
                        print "* [WARNING] if this is a "+word+" but loop induced process such as gg->ZH," 
                        print "*           then fragment is OK (no need to have Pythia8PowhegEmissionVetoSettings)"
			warning = warning + 1
        if knd == 1 :
             powhegcheck.append(int(os.popen('grep -c -i PowhegEmission '+pi).read()))
             if powhegcheck[0] > 0 :
                 print "* [ERROR] Please remove POWHEG settings for MG requests."
                 error = error + 1
        if knd == -1 :
             purepythiacheck.append(int(os.popen('grep -c -i Pythia8aMCatNLOSettings '+pi).read()))
             purepythiacheck.append(int(os.popen('grep -c -i PowhegEmission '+pi).read()))
             if purepythiacheck[0] > 0 or purepythiacheck[1] >0 :
                 print "* [WARNING] Please remove aMCatNLO or POWHEG settings if this is a pure Pythia request."
                 print "*           If it's not a pure request, in the future, please include madgraph/powheg or amcatnlo"
                 print "*           in the name of the dataset"
                 warning = warning + 1
        if loop_flag == 1:
            if mcatnlo_flag == 1: 
                print "* [ERROR] You are using a loop induced process, [noborn=QCD]."
                print "*         Please remove all occurances of Pythia8aMCatNLOSettings from the fragment"
                error = error + 1
            if nPartonsInBorn_flag == 1:
                print "* [ERROR] You are using a loop induced process, [noborn=QCD]."
                print "*         Please remove all TimeShower:nPartonsInBorn from the fragment"       
                error = error + 1
        for kk in range (0, 8):   
            tunecheck.append(int(os.popen('grep -v "#" '+pi+' | grep -v "annotation" | grep -c -i '+tune[kk]).read()))
        if tunecheck[6] == 3 or tunecheck[7] == 3:
            if tunecheck[0] != 3:
                print "* [WARNING] Check if there is some extra tune setting"
                warning = warning + 1
        if 'sherpa' in dn.lower():
            print "* [WARNING] No automated check of Sherpa ps/tune parameters yet"
            warning = warning + 1
        if 3 not in tunecheck and 'sherpa' not in dn.lower():
            print "* [ERROR] Tune configuration may be wrong in the fragment"
 	    print "          or pythia8CUEP8M1Settings are overwritten by some other parameters as in CUETP8M2T4"
            error = error + 1
        elif 3 in tunecheck:
            print "* [OK] Tune configuration probably OK in the fragment"
            if tunecheck[0] > 2 :
                if 'Fall18' not in pi and 'Fall17' not in pi :
                    print "* [WARNING] Do you really want to have tune "+tune[0] +" in this campaign?"
                    warning = warning + 1
        if 'Fall18' in pi and fsize != 0:
            if int(os.popen('grep -c "from Configuration.Generator.PSweightsPythia.PythiaPSweightsSettings_cfi import *" '+pi).read()) != 1 :
                print "* [WARNING] No parton shower weights configuration in the fragment. In the Fall18 campaign, we recommend to include Parton Shower weights"
                warning = warning + 1
            if int(os.popen('grep -c "from Configuration.Generator.PSweightsPythia.PythiaPSweightsSettings_cfi import *" '+pi).read()) == 1 :
                cmssw_version    = int(re.search("_[0-9]?[0-9]_[0-9]?[0-9]_[0-9]?[0-9]",cmssw).group().replace('_',''))
                if cmssw_version < int('10_2_3'.replace('_','')) :
                    print "* [ERROR] PS weights in config but CMSSW version is < 10_2_3 - please check!"
                    error = error + 1
                psweightscheck.append(int(os.popen('grep -c "from Configuration.Generator.PSweightsPythia.PythiaPSweightsSettings_cfi import *" '+pi).read()))
                psweightscheck.append(int(os.popen('grep -c "pythia8PSweightsSettingsBlock," '+pi).read()))
                psweightscheck.append(int(os.popen('grep -c "pythia8PSweightsSettings" '+pi).read()))
                if psweightscheck[0] == 1 and psweightscheck[1] == 1 and psweightscheck[2] == 2 :
                    print "* [OK] Parton shower weight configuration probably OK in the fragment"
                else:
                    print "* [ERROR] Parton shower weight configuration not OK in the fragment" 
                    error = error + 1
        if int(os.popen('grep -c -i filter '+pi).read()) > 3 and filter_eff == 1:
            print "* [WARNING] Filters in the fragment but filter efficiency = 1"
            warning = warning + 1
        os.popen("rm -rf "+my_path+pi).read()  
        os.popen("rm -rf "+my_path+'eos/'+pi).read()
        print "***********************************************************************************"
        print "Number of warnings = "+ str(warning)
        print "Number of errors = "+ str(error)
        if error > 0:
            print "There is at least 1 error. Request won't proceed to VALIDATION"

# Valid range for exit codes is 0-255
        if error > 255 or error < 0:
            error = 255

# Exit with code, 0 - good, not 0 is bad
        if args.bypass_validation:
            continue
        else:    
            sys.exit(error)
