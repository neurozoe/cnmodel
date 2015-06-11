from neuron import h

from .terminal import Terminal
from ..util import random

# utility class to create parameter lists... 
# create like: p = Params(abc=2.0, defg = 3.0, lunch='sandwich')
# reference like p.abc, p.defg, etc.
class Params(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class StochasticTerminal(Terminal):
    """
    Axon terminal with multi-site sctochastic release mechanism.
    """
    def __init__(self, pre_sec, target_cell, nzones=1, multisite=True, 
                 celltype='bushy', message=None, type='lognormal', identifier=0,
                 stochastic_pars=None, calcium_pars=None, delay=0, debug=False,
                 select=None, spike_source=None, dep_flag=1):
        """
        This routine creates a (potentially) multisite synapse with:
            A MultiSiteSynapse release mechanism that includes stochastic release, with a lognormal
                release latency distribution.
            A "cleft" mechanism (models diffusion of transmitter). Note that the cleft is inserted as part of the
                presynaptic section, but is not connected to the postsynaptic side yet.
        Inputs:
            pre_sec: the section where the synaptic mechanisms should be inserted.
            nzones: the number of activate zones to insert into the section.
            multisite: determines whether the terminal actually creates multiple 
                release zones (True) or just creates a single release zone that
                varies its amplitude based on the depression/facilitation state.
            celltype: bushy or (anything else), sets the duration and amplitude of the transmitter transient
                generated by these synapses
            message: a message to type out when instantiating (mostly for verification of code flow)
            type: 'lognormal' sets the release event latency distribution to use a lognormal function. Currently,
                no other function is supported.
            identifier: an identifier to associate with these release sites so we can find them later.
            stochastic_pars: A dictionary of parameters (Param class) used to specifiy the stochastic behavior of this site,
                including release latency, stdev, and lognormal distribution paramaters
            calcium_pars: A dictionary of parameters (Param class) to determine the calcium channels in this section.
                If None, then no calcium channels are inserted; otherwise, a P-type calcium conductance and a dynamic
                mechanism are inserted, and their conductance is set.
        Outputs: a list with 3 variables:
        terminal, relsite, cleft
            terminal: this is the pointer to the terminal section that was inserted (same as pre_sec if it was
                specified)
            relsite: a list of the nzones release sites that were created
            cleft: a list of the nzones cleft mechanisms that were created.
        """
        Terminal.__init__(self, pre_sec)
        
        
        # set parameter control for the stochastic release of vesicles...
        # this structure is passed to stochastic synapses, and replaces several variables 
        # that were previously defined in the call to that function.
        from .. import cells
            
        thresh = -30 # mV - AP detection on the presynaptic side.
        
        ANTerminals_Latency = 0.5 # latency 
        vPars = Params(LN_Flag=1, LN_t0=10.0, LN_A0=0.05, LN_tau=35, LN_std=0.05,
                    Lat_Flag=1, Lat_t0=10.0, Lat_A0=0.140, Lat_tau=21.5,
                    latency=ANTerminals_Latency)
        #NOTE: stochastic_pars must define parameters used by multisite, including:
            #.delay is the netcon delay between the presynaptic AP and the start of release events
            #.Latency is the latency to the mean release event... this could be confusing.
        
        if stochastic_pars is None:
            stochastic_pars = vPars
            
            
        mu = u'\u03bc'
        sigma = u'\u03c3'
        message='  >> creating terminal with %d release zones using lognormal release latencies (coh4)' % nzones
        if debug:
            print message
        terminal = pre_sec
        #terminal.push()
        if calcium_pars is not None:
            terminal.insert('cap') # insert calcium channel density
            terminal().cap.pcabar = calcium_pars.Ca_gbar
            terminal.insert('cad')
            
        # Create point process to simulate multiple independent release zones.
        relsite = h.MultiSiteSynapse(0.5, sec=terminal)
        relsite.nZones = nzones
        if multisite:
            relsite.multisite = 1
            relsite.rseed = random.current_seed()  # use global random seed
            relsite.latency = stochastic_pars.latency
            relsite.latstd = stochastic_pars.LN_std
            self.n_rzones = nzones
        else:
            relsite.multisite = 0
            self.release_rng = h.Random(random.current_seed())
            self.release_rng.uniform(0, 1)
            relsite.setUniformRNG(self.release_rng)
            self.n_rzones = 1
        
        relsite.Dep_Flag = dep_flag  # control synaptic dynamics
        if debug is True:
            relsite.debug = 1
        relsite.Identifier = identifier
        # if type == 'gamma':
        #     gd = gamma.rvs(2, size=10000)/2.0 # get a sample of 10000 events with a gamma dist of 2, set to mean of 1.0
        #     if relsite.latstd > 0.0:
        #         gds = relsite.latency+std*(gd-1.0)/gd.std() # scale standard deviation
        #     else:
        #         gds = relsite.latency*np.ones((10000,1))
        # if type == 'lognormal':
        #     if std > 0.0:
        #         gds = lognormal(mean=0, sigma=relsite.latstd, size=10000)
        #     else:
        #         gds = np.zeros((10000, 1))
        # use the variable latency mode of COH4. And, it is lognormal no matter what.
        # the parameters are defined in COH4.mod as follows
        #    Time course of latency shift in release during repetitive stimulation
        #   Lat_Flag = 0 (1) : 0 means fixed latency, 1 means lognormal distribution
        #   Lat_t0 = 0.0 (ms) : minimum time since simulation start before changes in latency are calculated
        #   Lat_A0 = 0.0 (ms) : size of latency shift from t0 to infinity
        #   Lat_tau = 100.0 (ms) : rate of change of latency shift (from fit of a+b(1-exp(-t/tau)))
        #   : Statistical control of log-normal release shape over time during repetive stimulation
        #   LN_Flag = 0 (1) : 0 means fixed values for all time
        #   LN_t0 = 0.0 (ms) : : minimum time since simulation start before changes in distribution are calculated
        #   LN_A0 = 0.0 (ms) : size of change in sigma from t0 to infinity
        #   LN_tau = 100.0 (ms) : rate of change of sigma over time (from fit of a+b*(1-exp(-t/tau)))

        relsite.LN_Flag = stochastic_pars.LN_Flag # enable use of lognormal release latency
        relsite.LN_t0 = stochastic_pars.LN_t0
        relsite.LN_A0 = stochastic_pars.LN_A0
        relsite.LN_tau = stochastic_pars.LN_tau
        relsite.Lat_Flag = stochastic_pars.Lat_Flag
        relsite.Lat_t0 = stochastic_pars.Lat_t0
        relsite.Lat_A0 = stochastic_pars.Lat_A0
        relsite.Lat_tau = stochastic_pars.Lat_tau
            #mpl.figure(2)
        if celltype in ['bushy', 'MNTB']:
            relsite.TDur = 0.10
            relsite.TAmp = 0.770
        else: # stellate
            relsite.TDur = 0.25
            relsite.TAmp = 1.56625
        h.pop_section()
        self.relsite = relsite

        if spike_source is None:
            spike_source = pre_sec(0.5)._ref_v
            
        pre_sec.push()
        self.netcon = h.NetCon(spike_source, relsite, thresh, delay, 1.0)
        self.netcon.weight[0] = 1
        self.netcon.threshold = -30.0
        h.pop_section()

        self.setPsdType(target_cell, select)

    def setPsdType(self, target_cell, select=None):
        # TODO: must resurrect this for inhibitory synapses.
        #elif psdtype.startswith('gly'):
            #self.setDF(target_cell, 'ipsc', select) # set the parameters for release
        self.setDF(target_cell, 'epsc') # set the parameters for release
        

    ################################################################################
    # The following routines set the synapse dynamics, based on measurements and fit
    # to the Dittman-Regehr model.
    ################################################################################

    def setDF(self, target_cell, synapsetype, select=None):
        """ set the parameters for the calyx release model ...
            These paramteres were obtained from an optimized fit of the Dittman-Regehr
            model to stimulus and recovery data for the synapses at 100, 200 and 300 Hz,
            for times out to about 0.5 - 1.0 second. Data from Ruili Xie and Yong Wang.
            Fitting by Paul Manis
        """
        from .. import cells
        if isinstance(target_cell, cells.Bushy):
            if synapsetype == 'epsc':
                self.bushy_epsc()
            if synapsetype == 'ipsc':
                if select is None:
                    self.bushy_ipsc_average()
                else:
                    self.bushy_ipsc_single(select=select)
        elif isinstance(target_cell, cells.TStellate):
            if synapsetype == 'epsc':
                self.stellate_epsc()
            if synapsetype == 'ipsc':
                self.stellate_ipsc()

    def bushy_epsc(self):
        """ data is average of 3 cells studied with recovery curves and individually fit """
        self.relsite.F = 0.29366
        self.relsite.k0 = 0.52313 / 1000.0
        self.relsite.kmax = 19.33805 / 1000.0
        self.relsite.taud = 15.16
        self.relsite.kd = 0.11283
        self.relsite.taus = 17912.2
        self.relsite.ks = 11.531
        self.relsite.kf = 17.78
        self.relsite.tauf = 9.75
        self.relsite.dD = 0.57771
        self.relsite.dF = 0.60364
        self.relsite.glu = 2.12827

    def stellate_epsc(self):
        """ data is average of 3 cells studied with recovery curves and individually fit """
        self.relsite.F = 0.43435
        self.relsite.k0 = 0.06717 / 1000.0
        self.relsite.kmax = 52.82713 / 1000.0
        self.relsite.taud = 3.98
        self.relsite.kd = 0.08209
        self.relsite.taus = 16917.120
        self.relsite.ks = 14.24460
        self.relsite.kf = 18.16292
        self.relsite.tauf = 11.38
        self.relsite.dD = 2.46535
        self.relsite.dF = 1.44543
        self.relsite.glu = 5.86564


    def stellate_ipsc(self):
        """ data is average of 3 cells studied with recovery curves and individually fit, 100 Hz """
        self.relsite.F = 0.23047
        self.relsite.k0 = 1.23636 #/ 1000.0
        self.relsite.kmax = 45.34474 #/ 1000.0
        self.relsite.taud = 98.09
        self.relsite.kd = 0.01183
        self.relsite.taus = 17614.50
        self.relsite.ks = 17.88618
        self.relsite.kf = 19.11424
        self.relsite.tauf = 32.28
        self.relsite.dD = 2.52072
        self.relsite.dF = 2.33317
        self.relsite.glu = 3.06948

    def bushy_ipsc_average(self):
        """average of 16 Bushy cells. Done differently than other averages.
        The individual fits were compiled, and an average computed for just the 100 Hz data
        across the individual fits. This average was then fit to the function of Dittman and Regeher
        (also in Xu-Friedman's papers). 
        The individual cells show a great deal of variability, from straight depression, to 
        depression/facilitaiton mixed, to facilation alone. This set of parameters generates
        a weak facilitaiton followed by depression back to baseline.
        """
        print "USING average kinetics for Bushy IPSCs"

        # average of 16cells for 100 Hz (to model); no recovery.
        self.relsite.F = 0.18521
        self.relsite.k0 = 2.29700
        self.relsite.kmax = 27.6667
        self.relsite.taud = 0.12366
        self.relsite.kd = 0.12272
        self.relsite.taus = 9.59624
        self.relsite.ks = 8.854469
        self.relsite.kf = 5.70771
        self.relsite.tauf = 0.37752
        self.relsite.dD = 4.00335
        self.relsite.dF = 0.72605
        self.relsite.glu = 5.61985

        # estimates for 400 Hz
        # self.relsite.F = 0.09
        # self.relsite.k0 = 1.2;
        # self.relsite.kmax = 30.;
        # self.relsite.taud = 0.01
        # self.relsite.kd = 0.75
        # self.relsite.taus = 0.015
        # self.relsite.ks = 1000.0
        # self.relsite.kf = 5.0
        # self.relsite.tauf = 0.3
        # self.relsite.dD = 1.0
        # self.relsite.dF = 0.025
        # self.relsite.glu = 4

        # self.relsite.F = 0.085426
        # self.relsite.k0 = 1.199372
        # self.relsite.kmax = 24.204277
        # self.relsite.taud = 0.300000
        # self.relsite.kd = 1.965292
        # self.relsite.taus = 2.596443
        # self.relsite.ks = 0.056385
        # self.relsite.kf = 0.721157
        # self.relsite.tauf = 0.034560
        # self.relsite.dD = 0.733980
        # self.relsite.dF = 0.025101
        # self.relsite.glu = 3.877192

        # average of 8 cells, all at 100 Hz with no recovery
        # self.relsite.F =    0.2450
        # self.relsite.k0 =   1.6206/1000.0
        # self.relsite.kmax = 26.0607/1000.0
        # self.relsite.taud = 0.0798
        # self.relsite.kd =   0.9679
        # self.relsite.taus = 9.3612
        # self.relsite.ks =   14.3474
        # self.relsite.kf =    4.2168
        # self.relsite.tauf =  0.1250
        # self.relsite.dD =    4.2715
        # self.relsite.dF =    0.6322
        # self.relsite.glu =   8.6160

        # average of 5 cells, mostly 100 Hz, but some 50, 200 and 400
        # self.relsite.F =    0.15573
        # self.relsite.k0 =   2.32272/1000.
        # self.relsite.kmax = 28.98878/1000.
        # self.relsite.taud = 0.16284
        # self.relsite.kd =   2.52092
        # self.relsite.taus = 17.97092
        # self.relsite.ks =   19.63906
        # self.relsite.kf =   7.44154
        # self.relsite.tauf = 0.10193
        # self.relsite.dD =   2.36659
        # self.relsite.dF =   0.38516
        # self.relsite.glu =  8.82600

        #original average - probably skewed.
        # self.relsite.F = 0.23382
        # self.relsite.k0 = 0.67554/1000.0
        # self.relsite.kmax = 52.93832/1000.0
        # self.relsite.taud = 8.195
        # self.relsite.kd = 0.28734
        # self.relsite.taus = 17.500
        # self.relsite.ks = 4.57098
        # self.relsite.kf = 16.21564
        # self.relsite.tauf = 123.36
        # self.relsite.dD = 2.21580
        # self.relsite.dF = 1.17146
        # self.relsite.glu = 1.90428


    def bushy_ipsc_single(self, select=None):
        """ data is from 31aug08b (single cell, clean dataset)"""
        print "Using bushy ipsc"

        if select is None or select > 4 or select <= 0:
            bushy_ipsc_average()
            return

        if select is 1: # 30aug08f
            print "using 30aug08f ipsc"
            self.relsite.F = 0.221818
            self.relsite.k0 = 0.003636364
            self.relsite.kmax = 0.077562107
            self.relsite.taud = 0.300000
            self.relsite.kd = 1.112554
            self.relsite.taus = 3.500000
            self.relsite.ks = 0.600000
            self.relsite.kf = 3.730452
            self.relsite.tauf = 0.592129
            self.relsite.dD = 0.755537
            self.relsite.dF = 2.931578
            self.relsite.glu = 1.000000

        if select is 2: #30aug08h
            print "using 30aug08H ipsc"
            self.relsite.F = 0.239404
            self.relsite.k0 = 3.636364 / 1000.
            self.relsite.kmax = 16.725479 / 1000.
            self.relsite.taud = 0.137832
            self.relsite.kd = 0.000900
            self.relsite.taus = 3.500000
            self.relsite.ks = 0.600000
            self.relsite.kf = 4.311995
            self.relsite.tauf = 0.014630
            self.relsite.dD = 3.326148
            self.relsite.dF = 0.725512
            self.relsite.glu = 1.000000

        if select is 3:
            print "using IPSC#3 "
            self.relsite.F = 0.29594
            self.relsite.k0 = 0.44388 / 1000.0
            self.relsite.kmax = 15.11385 / 1000.0
            self.relsite.taud = 0.00260
            self.relsite.kd = 0.00090
            self.relsite.taus = 11.40577
            self.relsite.ks = 27.98783
            self.relsite.kf = 30.00000
            self.relsite.tauf = 0.29853
            self.relsite.dD = 3.70000
            self.relsite.dF = 2.71163
            self.relsite.glu = 4.97494
