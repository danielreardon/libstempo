from __future__ import division
import math, os
import numpy as N
import scipy.interpolate as interp
import libstempo

from libstempo import GWB

day = 24 * 3600
year = 365.25 * day
DMk = 4.15e3           # Units MHz^2 cm^3 pc sec

def add_gwb(psr,dist=1,ngw=1000,seed=None,flow=1e-8,fhigh=1e-5,gwAmp=1e-20,alpha=-0.66,logspacing=True):
    """Add a stochastic background from inspiraling binaries, using the tempo2
    code that underlies the GWbkgrd plugin.

    Here 'dist' is the pulsar distance [in kpc]; 'ngw' is the number of binaries,
    'seed' (a negative integer) reseeds the GWbkgrd pseudorandom-number-generator,
    'flow' and 'fhigh' [Hz] determine the background band, 'gwAmp' and 'alpha'
    determine its amplitude and exponent, and setting 'logspacing' to False
    will use linear spacing for the individual sources.

    It is also possible to create a background object with

    gwb = GWB(ngw,seed,flow,fhigh,gwAmp,alpha,logspacing)

    then call the method gwb.add_gwb(pulsar[i],dist) repeatedly to get a
    consistent background for multiple pulsars.

    Returns the GWB object
    """
    

    gwb = GWB(ngw,seed,flow,fhigh,gwAmp,alpha,logspacing)
    gwb.add_gwb(psr,dist)

    return gwb

def add_dipole_gwb(psr,dist=1,ngw=1000,seed=None,flow=1e-8,fhigh=1e-5,gwAmp=1e-20, alpha=-0.66, \
        logspacing=True, dipoleamps=None, dipoledir=None, dipolemag=None):
        
    """Add a stochastic background from inspiraling binaries distributed
    according to a pure dipole distribution, using the tempo2
    code that underlies the GWdipolebkgrd plugin.

    The basic use is identical to that of 'add_gwb':
    Here 'dist' is the pulsar distance [in kpc]; 'ngw' is the number of binaries,
    'seed' (a negative integer) reseeds the GWbkgrd pseudorandom-number-generator,
    'flow' and 'fhigh' [Hz] determine the background band, 'gwAmp' and 'alpha'
    determine its amplitude and exponent, and setting 'logspacing' to False
    will use linear spacing for the individual sources.

    Additionally, the dipole component can be specified by using one of two
    methods:
    1) Specify the dipole direction as three dipole amplitudes, in the vector
    dipoleamps
    2) Specify the direction of the dipole as a magnitude dipolemag, and a vector
    dipoledir=[dipolephi, dipoletheta]

    It is also possible to create a background object with
    
    gwb = GWB(ngw,seed,flow,fhigh,gwAmp,alpha,logspacing)

    then call the method gwb.add_gwb(pulsar[i],dist) repeatedly to get a
    consistent background for multiple pulsars.
    
    Returns the GWB object
    """

    gwb = GWB(ngw,seed,flow,fhigh,gwAmp,alpha,logspacing,dipoleamps,dipoledir,dipolemag)
    gwb.add_gwb(psr,dist)
    
    return gwb

def _geti(x,i):
    return x[i] if isinstance(x,(tuple,list,N.ndarray)) else x

def fakepulsar(parfile,obstimes,toaerr,freq=1440.0,observatory='AXIS',flags=''):
    """Returns a libstempo tempopulsar object corresponding to a noiseless set
    of observations for the pulsar specified in 'parfile', with observations
    happening at times (MJD) given in the array (or list) 'obstimes', with
    measurement errors given by toaerr (us).

    A new timfile can then be saved with pulsar.savetim(). Re the other parameters:
    - 'toaerr' needs to be either a common error, or a list of errors
       of the same length of 'obstimes';
    - 'freq' can be either a common observation frequency in MHz, or a list;
       it defaults to 1440;
    - 'observatory' can be either a common observatory name, or a list;
       it defaults to the IPTA MDC 'AXIS';
    - 'flags' can be a string (such as '-sys EFF.EBPP.1360') or a list of strings;
       it defaults to an empty string."""

    import tempfile
    outfile = tempfile.NamedTemporaryFile(delete=False)

    outfile.write('FORMAT 1\n')
    outfile.write('MODE 1\n')

    obsname = 'fake_' + os.path.basename(parfile)
    if obsname[-4:] == '.par':
        obsname = obsname[:-4]

    for i,t in enumerate(obstimes):
        outfile.write('{0} {1} {2} {3} {4} {5}\n'.format(
            obsname,_geti(freq,i),t,_geti(toaerr,i),_geti(observatory,i),_geti(flags,i)
        ))

    timfile = outfile.name
    outfile.close()

    pulsar = libstempo.tempopulsar(parfile,timfile,dofit=False)
    pulsar.stoas[:] -= pulsar.residuals(updatebats=False) / 86400.0

    os.remove(timfile)

    return pulsar

def make_ideal(psr):
    """Adjust the TOAs so that the residuals to zero, then refit."""
    
    psr.stoas[:] -= psr.residuals() / 86400.0
    psr.fit()

def add_efac(psr,efac=1.0,seed=None):
    """Add nominal TOA errors, multiplied by `efac` factor.
    Optionally take a pseudorandom-number-generator seed."""
    
    if seed is not None:
        N.random.seed(seed)

    psr.stoas[:] += efac * psr.toaerrs * (1e-6 / day) * N.random.randn(psr.nobs)

def add_equad(psr,equad,seed=None):
    """Add quadrature noise of rms `equad` [s].
    Optionally take a pseudorandom-number-generator seed."""

    if seed is not None:
        N.random.seed(seed)
    
    psr.stoas[:] += (equad / day) * N.random.randn(psr.nobs)

def quantize(times,dt=1):
    bins    = N.arange(N.min(times),N.max(times)+dt,dt)
    indices = N.digitize(times,bins) # indices are labeled by "right edge"
    counts  = N.bincount(indices,minlength=len(bins)+1)

    bign, smalln = len(times), N.sum(counts > 0)

    t = N.zeros(smalln,'d')
    U = N.zeros((bign,smalln),'d')

    j = 0
    for i,c in enumerate(counts):
        if c > 0:
            U[indices == i,j] = 1
            t[j] = N.mean(times[indices == i])
            j = j + 1
    
    return t, U

def quantize_fast(times,dt=1):
    isort = N.argsort(times)
    
    bucket_ref = [times[isort[0]]]
    bucket_ind = [[isort[0]]]
    
    for i in isort[1:]:
        if times[i] - bucket_ref[-1] < dt:
            bucket_ind[-1].append(i)
        else:
            bucket_ref.append(times[i])
            bucket_ind.append([i])
    
    t = N.array([N.mean(times[l]) for l in bucket_ind],'d')
    
    U = N.zeros((len(times),len(bucket_ind)),'d')
    for i,l in enumerate(bucket_ind):
        U[l,i] = 1
    
    return t, U

# check that the two versions match
# t, U = quantize(N.array(psr.toas(),'d'),dt=1)
# t2, U2 = quantize_fast(N.array(psr.toas(),'d'),dt=1)
# print N.sum((t - t2)**2), N.all(U == U2)

def add_jitter(psr,equad,coarsegrain=0.1,seed=None):
    """Add correlated quadrature noise of rms `equad` [s],
    with coarse-graining time `coarsegrain` [days].
    Optionally take a pseudorandom-number-generator seed."""
    
    if seed is not None:
        N.random.seed(seed)

    t, U = quantize_fast(N.array(psr.toas(),'d'),0.1)
    psr.stoas[:] += (equad / day) * N.dot(U,N.random.randn(U.shape[1]))

def add_rednoise(psr,A,gamma,components=10,seed=None):
    """Add red noise with P(f) = A^2 / (12 pi^2) (f year)^-gamma,
    using `components` Fourier bases.
    Optionally take a pseudorandom-number-generator seed."""

    if seed is not None:
        N.random.seed(seed)
    
    t = psr.toas()
    minx, maxx = N.min(t), N.max(t)
    x = (t - minx) / (maxx - minx)
    T = (day/year) * (maxx - minx)

    size = 2*components
    F = N.zeros((psr.nobs,size),'d')
    f = N.zeros(size,'d')

    for i in range(components):
        F[:,2*i]   = N.cos(2*math.pi*(i+1)*x)
        F[:,2*i+1] = N.sin(2*math.pi*(i+1)*x)

        f[2*i] = f[2*i+1] = (i+1) / T

    norm = A**2 * year**2 / (12 * math.pi**2 * T)
    prior = norm * f**(-gamma)
    
    y = N.sqrt(prior) * N.random.randn(size)
    psr.stoas[:] += (1.0/day) * N.dot(F,y)

def add_dm(psr,A,gamma,components=10,seed=None):
    """Add DM variations with P(f) = A^2 / (12 pi^2) (f year)^-gamma,
    using `components` Fourier bases.
    Optionally take a pseudorandom-number-generator seed."""

    if seed is not None:
        N.random.seed(seed)
    
    t = psr.toas()
    v = DMk / psr.freqs**2

    minx, maxx = N.min(t), N.max(t)
    x = (t - minx) / (maxx - minx)
    T = (day/year) * (maxx - minx)

    size = 2*components
    F = N.zeros((psr.nobs,size),'d')
    f = N.zeros(size,'d')

    for i in range(components):
        F[:,2*i]   = N.cos(2*math.pi*(i+1)*x)
        F[:,2*i+1] = N.sin(2*math.pi*(i+1)*x)

        f[2*i] = f[2*i+1] = (i+1) / T

    norm = A**2 * year**2 / (12 * math.pi**2 * T)
    prior = norm * f**(-gamma)
    
    y = N.sqrt(prior) * N.random.randn(size)
    psr.stoas[:] += (1.0/day) * v * N.dot(F,y)
    
def add_line(psr,f,A,offset=0.5):
    """Add a line of frequency `f` [Hz] and amplitude `A` [s],
    with origin at a fraction `offset` through the dataset."""
    
    t = psr.toas()
    t0 = offset * (N.max(t) - N.min(t))
    sine = A * N.cos(2 * math.pi * f * day * (t - t0))

    psr.stoas[:] += sine / day

def add_cgw(psr, gwtheta, gwphi, mc, dist, fgw, phase0, psi, inc, pdist=1.0, \
                        pphase=None, psrTerm=True, evolve=True, \
                        phase_approx=False, tref=0):
    """
    Function to create GW incuced residuals from a SMBMB as 
    defined in Ellis et. al 2012,2013. Trys to be smart about it

    @param psr: pulsar object
    @param gwtheta: Polar angle of GW source in celestial coords [radians]
    @param gwphi: Azimuthal angle of GW source in celestial coords [radians]
    @param mc: Chirp mass of SMBMB [solar masses]
    @param dist: Luminosity distance to SMBMB [Mpc]
    @param fgw: Frequency of GW (twice the orbital frequency) [Hz]
    @param phase0: Initial Phase of GW source [radians]
    @param psi: Polarization of GW source [radians]
    @param inc: Inclination of GW source [radians]
    @param pdist: Pulsar distance to use other than those in psr [kpc]
    @param pphase: Use pulsar phase to determine distance [radian]
    @param psrTerm: Option to include pulsar term [boolean] 
    @param evolve: Option to exclude evolution [boolean]

    @return: Vector of induced residuals

    """

    # convert units
    mc *= 4.9e-6         # convert from solar masses to seconds
    dist *= 1.0267e14    # convert from Mpc to seconds

    # define initial orbital frequency 
    w0 = N.pi * fgw
    phase0 /= 2 # orbital phase
    w053 = w0**(-5/3)

    # define variable for later use
    cosgwtheta, cosgwphi = N.cos(gwtheta), N.cos(gwphi)
    singwtheta, singwphi = N.sin(gwtheta), N.sin(gwphi)
    sin2psi, cos2psi = N.sin(2*psi), N.cos(2*psi)
    incfac1, incfac2 = -0.5*(3+N.cos(2*inc)), 2*N.cos(inc)

    # unit vectors to GW source
    m = N.array([-singwphi, cosgwphi, 0.0])
    n = N.array([-cosgwtheta*cosgwphi, -cosgwtheta*singwphi, singwtheta])
    omhat = N.array([-singwtheta*cosgwphi, -singwtheta*singwphi, -cosgwtheta])

    # various factors invloving GW parameters
    fac1 = 256/5 * mc**(5/3) * w0**(8/3) 
    fac2 = 1/32/mc**(5/3)
    fac3 = mc**(5/3)/dist

    # pulsar location
    ptheta = N.pi/2 - psr['DECJ'].val
    pphi = psr['RAJ'].val

    # use definition from Sesana et al 2010 and Ellis et al 2012
    phat = N.array([N.sin(ptheta)*N.cos(pphi), N.sin(ptheta)*N.sin(pphi),\
            N.cos(ptheta)])

    fplus = 0.5 * (N.dot(m, phat)**2 - N.dot(n, phat)**2) / (1+N.dot(omhat, phat))
    fcross = (N.dot(m, phat)*N.dot(n, phat)) / (1 + N.dot(omhat, phat))
    cosMu = -N.dot(omhat, phat)


    # get values from pulsar object
    toas = psr.toas().copy()*86400 - tref
    if pphase is not None:
        pd = pphase/(2*N.pi*fgw*(1-cosMu)) / 1.0267e11
    else:
        pd = pdist
    

    # convert units
    pd *= 1.0267e11   # convert from kpc to seconds
    
    # get pulsar time
    tp = toas-pd*(1-cosMu)

    # evolution
    if evolve:

        # calculate time dependent frequency at earth and pulsar
        omega = w0 * (1 - fac1 * toas)**(-3/8)
        omega_p = w0 * (1 - fac1 * tp)**(-3/8)

        # calculate time dependent phase
        phase = phase0 + fac2 * (w053 - omega**(-5/3))
        phase_p = phase0 + fac2 * (w053 - omega_p**(-5/3))
    
    # use approximation that frequency does not evlolve over observation time
    elif phase_approx:
        
        # frequencies
        omega = w0
        omega_p = w0 * (1 + fac1 * pd*(1-cosMu))**(-3/8)
        
        # phases
        phase = phase0 + omega * toas
        phase_p = phase0 + fac2 * (w053 - omega_p**(-5/3)) + omega_p*toas
          
    # no evolution
    else: 
        
        # monochromatic
        omega = w0
        omega_p = omega
        
        # phases
        phase = phase0 + omega * toas
        phase_p = phase0 + omega * tp
        

    # define time dependent coefficients
    At = N.sin(2*phase) * incfac1
    Bt = N.cos(2*phase) * incfac2
    At_p = N.sin(2*phase_p) * incfac1
    Bt_p = N.cos(2*phase_p) * incfac2

    # now define time dependent amplitudes
    alpha = fac3 / omega**(1/3)
    alpha_p = fac3 / omega_p**(1/3)

    # define rplus and rcross
    rplus = alpha * (At*cos2psi - Bt*sin2psi)
    rcross = alpha * (At*sin2psi + Bt*cos2psi)
    rplus_p = alpha_p * (At_p*cos2psi - Bt_p*sin2psi)
    rcross_p = alpha_p * (At_p*sin2psi + Bt_p*cos2psi)

    # residuals
    if psrTerm:
        res = fplus*(rplus_p-rplus)+fcross*(rcross_p-rcross)
    else:
        res = -fplus*rplus - fcross*rcross

    psr.stoas[:] += res/86400


def createGWB_clean(psr, Amp, gam, noCorr=False, seed=None, turnover=False, \
                    f0=1e-9, beta=1, power=1, npts=600, howml=10):
    """
    Function to create GW incuced residuals from a stochastic GWB as defined
    in Chamberlin, Creighton, Demorest et al. (2014)
    
    @param psr: pulsar object for single pulsar
    @param Amp: Amplitude of red noise in GW units
    @param gam: Red noise power law spectral index
    @param noCorr: Add red noise with no spatial correlations
    @param seed: Random number seed
    @param turnover: Produce spectrum with turnover at frequency f0
    @param f0: Frequency of spectrum turnover
    @param beta: Spectral index of power spectram for f << f0
    @param power: Fudge factor for flatness of spectrum turnover
    @param npts: Number of points used in interpolation
    @param howml: Lowest frequency is 1/(howml * T) 

    
    @return: list of residuals for each pulsar
    
    """

    if seed is not None:
        N.random.seed(seed)

    # number of pulsars
    Npulsars = len(psr)

    # gw start and end times for entire data set
    start = N.min([p.toas().min()*86400 for p in psr]) - 86400
    stop = N.max([p.toas().max()*86400 for p in psr]) + 86400
        
    # duration of the signal
    dur = stop - start
    
    # get maximum number of points
    if npts is None:
        # default to cadence of 2 weeks
        npts = dur/(86400*14)

    # make a vector of evenly sampled data points
    ut = N.linspace(start, stop, npts)

    # time resolution in days
    dt = dur/npts

    # compute the overlap reduction function
    if noCorr:
        ORF = N.diag(N.ones(Npulsars)*2)
    else:
        ORF = computeORFMatrix(psr)

    # Define frequencies spanning from DC to Nyquist. 
    # This is a vector spanning these frequencies in increments of 1/(dur*howml).
    f = N.arange(0, 1/(2*dt), 1/(dur*howml))
    f[0] = f[1] # avoid divide by 0 warning
    Nf = len(f)

    # Use Cholesky transform to take 'square root' of ORF
    M = N.linalg.cholesky(ORF)

    # Create random frequency series from zero mean, unit variance, Gaussian distributions
    w = N.zeros((Npulsars, Nf), complex)
    for ll in range(Npulsars):
        w[ll,:] = N.random.randn(Nf) + 1j*N.random.randn(Nf)

    # strain amplitude
    f1yr = 1/3.16e7
    alpha = -0.5 * (gam-3)
    hcf = Amp * (f/f1yr)**(alpha)
    if turnover:
        si = alpha - beta
        hcf /= (1+(f/f0)**(power*si))**(1/power)

    C = 1 / 96 / N.pi**2 * hcf**2 / f**3 * dur * howml

    ### injection residuals in the frequency domain
    Res_f = N.dot(M, w)
    for ll in range(Npulsars):
        Res_f[ll] = Res_f[ll] * C**(0.5)    # rescale by frequency dependent factor
        Res_f[ll,0] = 0			    # set DC bin to zero to avoid infinities
        Res_f[ll,-1] = 0		    # set Nyquist bin to zero also

    # Now fill in bins after Nyquist (for fft data packing) and take inverse FT
    Res_f2 = N.zeros((Npulsars, 2*Nf-2), complex)    
    Res_t = N.zeros((Npulsars, 2*Nf-2))
    Res_f2[:,0:Nf] = Res_f[:,0:Nf]
    Res_f2[:, Nf:(2*Nf-2)] = N.conj(Res_f[:,(Nf-2):0:-1])
    Res_t = N.real(N.fft.ifft(Res_f2)/dt)

    # shorten data and interpolate onto TOAs
    Res = N.zeros((Npulsars, npts))
    res_gw = []
    for ll in range(Npulsars):
        Res[ll,:] = Res_t[ll, 10:(npts+10)]
        f = interp.interp1d(ut, Res[ll,:], kind='linear')
        res_gw.append(f(psr[ll].toas()*86400))

    return res_gw

def computeORFMatrix(psr):
    """
    Compute ORF matrix.

    @param psr: List of pulsar object instances

    @return: Matrix that has the ORF values for every pulsar
             pair with 2 on the diagonals to account for the 
             pulsar term.

    """

    # begin loop over all pulsar pairs and calculate ORF
    npsr = len(psr)
    ORF = N.zeros((npsr, npsr))
    phati = N.zeros(3)
    phatj = N.zeros(3)
    ptheta = [N.pi/2 - p['DECJ'].val for p in psr]
    pphi = [p['RAJ'].val for p in psr]
    for ll in range(0, npsr):
        phati[0] = N.cos(pphi[ll]) * N.sin(ptheta[ll])
        phati[1] = N.sin(pphi[ll]) * N.sin(ptheta[ll])
        phati[2] = N.cos(ptheta[ll])

        for kk in range(0, npsr):
            phatj[0] = N.cos(pphi[kk]) * N.sin(ptheta[kk])
            phatj[1] = N.sin(pphi[kk]) * N.sin(ptheta[kk])
            phatj[2] = N.cos(ptheta[kk])
           
            if ll != kk:
                xip = (1.-N.sum(phati*phatj)) / 2.
                ORF[ll, kk] = 3.*( 1./3. + xip * ( N.log(xip) -1./6.) )
            else:
                ORF[ll, kk] = 2.0

    return ORF


