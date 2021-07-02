#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 29 22:12:59 2021

@author:        Scott Kriel
Description:    Spectrum scanning software based on https://github.com/xmikos/soapy_power/blob/master/soapypower/__main__.py 
                to handle long term measurements for the SKA Aperture Prototype (SKAAP)
    
"""

import os, sys, logging, argparse, re, shutil, textwrap

import numpy as np
import simplesoapy
from soapypower import writer
from soapypower.version import __version__
import json
import datetime
import time

logger = logging.getLogger(__name__)
re_float_with_multiplier = re.compile(r'(?P<num>[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)(?P<multi>[kMGT])?')
re_float_with_multiplier_negative = re.compile(r'^(?P<num>-(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)(?P<multi>[kMGT])?$')
multipliers = {'k': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12}


def float_with_multiplier(string):
    """Convert string with optional k, M, G, T multiplier to float"""
    match = re_float_with_multiplier.search(string)
    if not match or not match.group('num'):
        raise ValueError('String "{}" is not numeric!'.format(string))

    num = float(match.group('num'))
    multi = match.group('multi')
    if multi:
        try:
            num *= multipliers[multi]
        except KeyError:
            raise ValueError('Unknown multiplier: {}'.format(multi))
    return num


def freq_or_freq_range(string):
    """Convert string with freq. or freq. range to list of floats"""
    return [float_with_multiplier(f) for f in string.split(':')]


def specific_gains(string):
    """Convert string with gains of individual amplification elements to dict"""
    if not string:
        return {}

    gains = {}
    for gain in string.split(','):
        amp_name, value = gain.split('=')
        gains[amp_name.strip()] = float(value.strip())
    return gains


def device_settings(string):
    """Convert string with SoapySDR device settings to dict"""
    if not string:
        return {}

    settings = {}
    for setting in string.split(','):
        setting_name, value = setting.split('=')
        settings[setting_name.strip()] = value.strip()
    return settings


def wrap(text, indent='    '):
    """Wrap text to terminal width with default indentation"""
    wrapper = textwrap.TextWrapper(
        width=int(os.environ.get('COLUMNS', 80)),
        initial_indent=indent,
        subsequent_indent=indent
    )
    return '\n'.join(wrapper.wrap(text))


def detect_devices(soapy_args=''):
    """Returns detected SoapySDR devices"""
    devices = simplesoapy.detect_devices(soapy_args, as_string=True)
    text = []
    text.append('Detected SoapySDR devices:')
    if devices:
        for i, d in enumerate(devices):
            text.append('  {}'.format(d))
    else:
        text.append('  No devices found!')
    return (devices, '\n'.join(text))


def device_info(soapy_args=''):
    """Returns info about selected SoapySDR device"""
    text = []
    try:
        device = simplesoapy.SoapyDevice(soapy_args)
        text.append('Selected device: {}'.format(device.hardware))
        text.append('  Available RX channels:')
        text.append('    {}'.format(', '.join(str(x) for x in device.list_channels())))
        text.append('  Available antennas:')
        text.append('    {}'.format(', '.join(device.list_antennas())))
        text.append('  Available tunable elements:')
        text.append('    {}'.format(', '.join(device.list_frequencies())))
        text.append('  Available amplification elements:')
        text.append('    {}'.format(', '.join(device.list_gains())))
        text.append('  Available device settings:')
        for key, s in device.list_settings().items():
            text.append(wrap('{} ... {} - {} (default: {})'.format(key, s['name'], s['description'], s['value'])))
        text.append('  Available stream arguments:')
        for key, s in device.list_stream_args().items():
            text.append(wrap('{} ... {} - {} (default: {})'.format(key, s['name'], s['description'], s['value'])))
        text.append('  Allowed gain range [dB]:')
        text.append('    {:.2f} - {:.2f}'.format(*device.get_gain_range()))
        text.append('  Allowed frequency range [MHz]:')
        text.append('    {:.2f} - {:.2f}'.format(*[x / 1e6 for x in device.get_frequency_range()]))
        text.append('  Allowed sample rates [MHz]:')
        rates = []
        for r in device.list_sample_rates():
            if r[0] == r[1]:
                rates.append('{:.2f}'.format(r[0] / 1e6))
            else:
                rates.append('{:.2f} - {:.2f}'.format(r[0] / 1e6, r[1] / 1e6))
        text.append(wrap(', '.join(rates)))
        text.append('  Allowed bandwidths [MHz]:')
        bandwidths = []
        for b in device.list_bandwidths():
            if b[0] == b[1]:
                bandwidths.append('{:.2f}'.format(b[0] / 1e6))
            else:
                bandwidths.append('{:.2f} - {:.2f}'.format(b[0] / 1e6, b[1] / 1e6))
        if bandwidths:
            text.append(wrap(', '.join(bandwidths)))
        else:
            text.append('    N/A')
    except RuntimeError:
        device = None
        text.append('No devices found!')
    return (device, '\n'.join(text))


def setup_argument_parser():
    """Setup command line parser"""
    # Fix help formatter width
    if 'COLUMNS' not in os.environ:
        os.environ['COLUMNS'] = str(shutil.get_terminal_size().columns)

    parser = argparse.ArgumentParser(
        prog='soapy_power',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Obtain a power spectrum from SoapySDR devices',
        add_help=False
    )

    # Fix recognition of optional argements of type float_with_multiplier
    parser._negative_number_matcher = re_float_with_multiplier_negative

    main_title = parser.add_argument_group('Main options')
    main_title.add_argument('-h', '--help', action='help',
                            help='show this help message and exit')
    main_title.add_argument('-f', '--freq', metavar='Hz|Hz:Hz', type=freq_or_freq_range, default='1420405752',
                            help='center frequency or frequency range to scan, number '
                            'can be followed by a k, M or G multiplier (default: %(default)s)')

    # output_group = main_title.add_mutually_exclusive_group()
    # output_group.add_argument('-O', '--output', metavar='FILE', type=argparse.FileType('w'), default=sys.stdout,
    #                           help='output to file (incompatible with --output-fd, default is stdout)')
    # output_group.add_argument('--output-fd', metavar='NUM', type=int, default=None,
    #                           help='output to existing file descriptor (incompatible with -O)')

    main_title.add_argument('-F', '--format', choices=sorted(writer.formats.keys()), default='rtl_power_fftw',
                            help='output format (default: %(default)s)')
    main_title.add_argument('-q', '--quiet', action='store_true',
                            help='limit verbosity')
    main_title.add_argument('--debug', action='store_true',
                            help='detailed debugging messages')
    main_title.add_argument('--detect', action='store_true',
                            help='detect connected SoapySDR devices and exit')
    main_title.add_argument('--info', action='store_true',
                            help='show info about selected SoapySDR device and exit')
    main_title.add_argument('--version', action='version',
                            version='%(prog)s {}'.format(__version__))

    bins_title = parser.add_argument_group('FFT bins')
    bins_group = bins_title.add_mutually_exclusive_group()
    bins_group.add_argument('-b', '--bins', type=int, default=512,
                            help='number of FFT bins (incompatible with -B, default: %(default)s)')
    bins_group.add_argument('-B', '--bin-size', metavar='Hz', type=float_with_multiplier,
                            help='bin size in Hz (incompatible with -b)')

    spectra_title = parser.add_argument_group('Averaging')
    spectra_group = spectra_title.add_mutually_exclusive_group()
    spectra_group.add_argument('-n', '--repeats', type=int, default=1,
                               help='number of spectra to average (incompatible with -t and -T, default: %(default)s)')
    spectra_group.add_argument('-t', '--time', metavar='SECONDS', type=float,
                               help='integration time (incompatible with -T and -n)')
    spectra_group.add_argument('-T', '--total-time', metavar='SECONDS', type=float,
                               help='total integration time of all hops (incompatible with -t and -n)')

    runs_title = parser.add_argument_group('Measurements')
    runs_group = runs_title.add_mutually_exclusive_group()
    runs_group.add_argument('-c', '--continue', dest='endless', action='store_true',
                            help='repeat the measurement endlessly (incompatible with -u and -e)')
    runs_group.add_argument('-u', '--runs', type=int, default=1,
                            help='number of measurements (incompatible with -c and -e, default: %(default)s)')
    runs_group.add_argument('-e', '--elapsed', metavar='SECONDS', type=float,
                            help='scan session duration (time limit in seconds, incompatible with -c and -u)')

    device_title = parser.add_argument_group('Device settings')
    device_title.add_argument('-d', '--device', default='',
                              help='SoapySDR device to use')
    device_title.add_argument('-C', '--channel', type=int, default=0,
                              help='SoapySDR RX channel (default: %(default)s)')
    device_title.add_argument('-A', '--antenna', default='',
                              help='SoapySDR selected antenna')
    device_title.add_argument('-r', '--rate', metavar='Hz', type=float_with_multiplier, default=10e6,
                              help='sample rate (default: %(default)s)')
    device_title.add_argument('-w', '--bandwidth', metavar='Hz', type=float_with_multiplier, default=0,
                              help='filter bandwidth (default: %(default)s)')
    device_title.add_argument('-p', '--ppm', type=int, default=0,
                              help='frequency correction in ppm')

    gain_group = device_title.add_mutually_exclusive_group()
    gain_group.add_argument('-g', '--gain', metavar='dB', type=float, default=15.0,
                            help='total gain (incompatible with -G and -a, default: %(default)s)')
    gain_group.add_argument('-G', '--specific-gains', metavar='STRING', type=specific_gains, default='',
                            help='specific gains of individual amplification elements '
                                 '(incompatible with -g and -a, example: LNA=28,VGA=12,AMP=0')
    gain_group.add_argument('-a', '--agc', action='store_true',
                            help='enable Automatic Gain Control (incompatible with -g and -G)')

    device_title.add_argument('--lnb-lo', metavar='Hz', type=float_with_multiplier, default=0,
                              help='LNB LO frequency, negative for upconverters (default: %(default)s)')
    device_title.add_argument('--device-settings', metavar='STRING', type=device_settings, default='',
                              help='SoapySDR device settings (example: biastee=true)')
    device_title.add_argument('--force-rate', action='store_true',
                              help='ignore list of sample rates provided by device and allow any value')
    device_title.add_argument('--force-bandwidth', action='store_true',
                              help='ignore list of filter bandwidths provided by device and allow any value')
    device_title.add_argument('--tune-delay', metavar='SECONDS', type=float, default=0,
                              help='time to delay measurement after changing frequency (to avoid artifacts)')
    device_title.add_argument('--reset-stream', action='store_true',
                              help='reset streaming after changing frequency (to avoid artifacts)')

    crop_title = parser.add_argument_group('Crop')
    crop_group = crop_title.add_mutually_exclusive_group()
    crop_group.add_argument('-o', '--overlap', metavar='PERCENT', type=float, default=0,
                            help='percent of overlap when frequency hopping (incompatible with -k)')
    crop_group.add_argument('-k', '--crop', metavar='PERCENT', type=float, default=0,
                            help='percent of crop when frequency hopping (incompatible with -o)')

    perf_title = parser.add_argument_group('Performance options')
    perf_title.add_argument('-s', '--buffer-size', type=int, default=0,
                            help='base buffer size (number of samples, 0 = auto, default: %(default)s)')
    perf_title.add_argument('-S', '--max-buffer-size', type=int, default=0,
                            help='maximum buffer size (number of samples, -1 = unlimited, 0 = auto, default: %(default)s)')

    fft_rules_group = perf_title.add_mutually_exclusive_group()
    fft_rules_group.add_argument('--even', action='store_true',
                                 help='use only even numbers of FFT bins')
    fft_rules_group.add_argument('--pow2', action='store_true',
                                 help='use only powers of 2 as number of FFT bins')

    perf_title.add_argument('--max-threads', metavar='NUM', type=int, default=0,
                            help='maximum number of PSD threads (0 = auto, default: %(default)s)')
    perf_title.add_argument('--max-queue-size', metavar='NUM', type=int, default=0,
                            help='maximum size of PSD work queue (-1 = unlimited, 0 = auto, default: %(default)s)')
    perf_title.add_argument('--no-pyfftw', action='store_true',
                            help='don\'t use pyfftw library even if it is available (use scipy.fftpack or numpy.fft)')

    other_title = parser.add_argument_group('Other options')
    other_title.add_argument('-l', '--linear', action='store_true',
                             help='linear power values instead of logarithmic')
    other_title.add_argument('-R', '--remove-dc', action='store_true',
                             help='interpolate central point to cancel DC bias (useful only with boxcar window)')
    other_title.add_argument('-D', '--detrend', choices=['none', 'constant'], default='none',
                             help='remove mean value from data to cancel DC bias (default: %(default)s)')
    other_title.add_argument('--fft-window', choices=['boxcar', 'hann', 'hamming', 'blackman', 'bartlett', 'kaiser', 'tukey'],
                             default='hann', help='Welch\'s method window function (default: %(default)s)')
    other_title.add_argument('--fft-window-param', metavar='FLOAT', type=float, default=None,
                             help='shape parameter of window function (required for kaiser and tukey windows)')
    other_title.add_argument('--fft-overlap', metavar='PERCENT', type=float, default=50,
                             help='Welch\'s method overlap between segments (default: %(default)s)')

    return parser

# Start of classes/functions written by Scott Kriel
class JSONEncoder(json.JSONEncoder):
    """"Encodes dictionary structures to json-like format"""
    def default(self, obj):
        if isinstance(obj, type(sys.stdout)):
            return str(obj)
        if isinstance(obj, type(datetime.datetime.now())):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
     
def write_args_json(args, filepath):
    argsDict = vars(args) # Convert arg type to dictionary            
    #print(args)
    #print(argsDict) 
    with open(filepath, 'w') as fileID:
        fileID.write(json.dumps(argsDict, cls=JSONEncoder))   # Write config dict to json file using custom JSONencoder

def read_json(filepath):    
    # Read back the config file for error checking 
    fileID = open(filepath, "r")
    contents = fileID.read()
    dictIn = json.loads(contents)
    fileID.close()    
    return dictIn

def write_dict_json(argsDict, filepath):
    with open(filepath, 'w') as fileID:
        fileID.write(json.dumps(argsDict, cls=JSONEncoder))   # Write config dict to json file using custom JSONencoder

def isMonotonic(A):
    # Check if given array is Monotonic
    return (all(A[i] <= A[i + 1] for i in range(len(A) - 1)) or
            all(A[i] >= A[i + 1] for i in range(len(A) - 1)))

def lin10(dB):
    # Convert dB = 10*log10(A) to linear and return A
    return 10**(dB/10)
def dB10(A):
    """Returns dB = 10*log10(A)"""
    return 10*np.log10(A)

def main():
    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    # Define paths to campaign
    campaignPath = os.getcwd()+'/campaign/'
    # Overide necessary args to acheive required campaign behaviour
    args.output = open(campaignPath+'output.txt', "w", encoding="utf-8")
   
    # Setup logging
    if args.quiet:
        log_level = logging.WARNING
    elif args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s'
    )

    # Import soapypower.power module only after setting log level
    from soapypower import power

    # Detect SoapySDR devices
    if args.detect:
        devices, devices_text = detect_devices(args.device)
        print(devices_text)
        sys.exit(0 if devices else 1)
    # Show info about selected SoapySDR device
    if args.info:
        device, device_text = device_info(args.device)
        print(device_text)
        sys.exit(0 if device else 1)
    # Prepare arguments for SoapyPower
    if args.no_pyfftw:
        power.psd.simplespectral.use_pyfftw = False

    # Create SoapyPower instance
    try:
        sdr = power.SoapyPower(
            soapy_args=args.device, sample_rate=args.rate, bandwidth=args.bandwidth, corr=args.ppm,
            gain=args.specific_gains if args.specific_gains else args.gain, auto_gain=args.agc,
            channel=args.channel, antenna=args.antenna, settings=args.device_settings,
            force_sample_rate=args.force_rate, force_bandwidth=args.force_bandwidth,
            output=args.output,
            output_format=args.format
        )
        logger.info('Using device: {}'.format(sdr.device.hardware))
    except RuntimeError:
        parser.error('No devices found!')

    # Prepare arguments for SoapyPower.sweep()
    if len(args.freq) < 2:
        args.freq = [args.freq[0], args.freq[0]]

    if args.bin_size:
        args.bins = sdr.bin_size_to_bins(args.bin_size)
    args.bins = sdr.nearest_bins(args.bins, even=args.even, pow2=args.pow2)

    if args.crop:
        args.overlap = args.crop
        args.crop = True
    else:
        args.crop = False

    if args.overlap:
        args.overlap /= 100
        args.overlap = sdr.nearest_overlap(args.overlap, args.bins)

    if args.total_time:
        args.time = args.total_time / len(sdr.freq_plan(args.freq[0], args.freq[1], args.bins, args.overlap, quiet=True))
    if args.time:
        args.repeats = sdr.time_to_repeats(args.bins, args.time)

    if args.fft_window in ('kaiser', 'tukey'):
        if args.fft_window_param is None:
            parser.error('argument --fft-window: --fft-window-param is required when using kaiser or tukey windows')
        args.fft_window = (args.fft_window, args.fft_window_param)
    
    
    
    freq_fname = campaignPath+'freq.txt'
    magFull_fname = campaignPath+'magFull.txt'
    magMax_fname = campaignPath+'magMax.txt'
    magMean_fname = campaignPath+'magMean.txt'
    magMin_fname = campaignPath+'magMin.txt'
    time_fname = campaignPath+'time.txt'
    status_fname = campaignPath+'status.txt'
    ctrl_fname = campaignPath+'ctrl.txt'
    settings_fname = campaignPath+'settings.txt'
    # Log scan configuration to file 
    write_args_json(args, settings_fname)
    # Read config file back in (for debugging purposes only)  
    #settingsDictIn = read_json(campaignPath+'settings.txt')
    #print(settingsDictIn)

    statusDict = {'name'    : 'Unamed Campaign',
                  'running' : 1,
                  'paused'  : 0,
                  'extFlag' : -1,
                  'Nsweep' : 0,
                  'start_time'  : datetime.datetime.now(),
                  'curr_time'   : datetime.datetime.now() 
                    }
    write_dict_json(statusDict, status_fname)
    
    ctrlDict = {'run'   : 1,
                'pause' : 0
                }
    
    while (statusDict['Nsweep']<args.runs or args.endless) and ctrlDict['run']==1:
        args.output = open(args.output.name, "w", encoding="utf-8")
        # Create a new SoapyPower instance before each sweep (allows for variable SDR parameters)      
        try:
            sdr = power.SoapyPower(
                soapy_args=args.device, sample_rate=args.rate, bandwidth=args.bandwidth, corr=args.ppm,
                gain=args.specific_gains if args.specific_gains else args.gain, auto_gain=args.agc,
                channel=args.channel, antenna=args.antenna, settings=args.device_settings,
                force_sample_rate=args.force_rate, force_bandwidth=args.force_bandwidth,
                output=args.output,
                output_format=args.format
            )
            logger.info('Using device: {}'.format(sdr.device.hardware))
        except RuntimeError:
            parser.error('No devices found!')

        print('\nStarting sweep number %s' % (statusDict['Nsweep']+1)+' ...\n')
        scan_start_dtime = datetime.datetime.now()
        # Start frequency sweep
        sdr.sweep(
            args.freq[0], args.freq[1], args.bins, repeats=args.repeats,
            runs=1, overlap=args.overlap, crop=args.crop,
            fft_window=args.fft_window, fft_overlap=args.fft_overlap / 100, log_scale=not args.linear,
            remove_dc=args.remove_dc, detrend=args.detrend if args.detrend != 'none' else None,
            lnb_lo=args.lnb_lo, tune_delay=args.tune_delay, reset_stream=args.reset_stream,
            base_buffer_size=args.buffer_size, max_buffer_size=args.max_buffer_size,
            max_threads=args.max_threads, max_queue_size=args.max_queue_size
        )
        scan_end_dtime = datetime.datetime.now()
        scan_result = np.loadtxt(args.output.name, dtype=float, comments='#', delimiter=' ')
        freq = scan_result[:,0]
        mag_dB = scan_result[:,1]
        if statusDict['Nsweep']==0:    # Initialise output files if this is the first run
            if all(i > 0 for i in freq) and isMonotonic(freq):      # Check if freq array is positive monotonic
                freq_init = np.copy(freq) # make a copy and store as base freq vect
                magMax_dB = np.copy(mag_dB) # Max and min spectrums initialized
                magMin_dB = np.copy(mag_dB)
                magMean_lin = lin10(mag_dB) # Save mean as linear for averaging
                np.savetxt(freq_fname, freq.reshape(1,-1), fmt='%.3f') 
                np.savetxt(magFull_fname, mag_dB.reshape(1,-1), fmt='%.12f')
                np.savetxt(magMax_fname, mag_dB.reshape(1,-1), fmt='%.12f')
                np.savetxt(magMean_fname, mag_dB.reshape(1,-1), fmt='%.12f')
                np.savetxt(magMin_fname, mag_dB.reshape(1,-1), fmt='%.12f')
                with open(time_fname,'w') as fileID:
                    fileID.write('{}, {}\n'.format(scan_start_dtime,scan_end_dtime))
            else:
                raise ValueError('Initial scan frequency vector is invalid!')
        elif all(freq==freq_init):    # Check if current frequency vector is identical to initial
            # Calculate max, mean and min amplitudes
            magMean_lin=(magMean_lin+lin10(mag_dB))/(statusDict['Nsweep']+1)
            magMax_dB[np.where(mag_dB>magMax_dB)] = mag_dB[np.where(mag_dB>magMax_dB)]
            magMin_dB[np.where(mag_dB<magMin_dB)] = mag_dB[np.where(mag_dB<magMin_dB)]
            # Save to data files
            np.savetxt(magMax_fname, magMax_dB.reshape(1,-1), fmt='%.12f')
            np.savetxt(magMin_fname, mag_dB.reshape(1,-1), fmt='%.12f')
            np.savetxt(magMean_fname, dB10(magMean_lin.reshape(1,-1)), fmt='%.12f')
            with open(magFull_fname, "a") as fileID:    # Append scan to full magnitude data file
                np.savetxt(fileID, mag_dB.reshape(1,-1), fmt='%.12f')
            with open(time_fname,'a') as fileID:
                fileID.write('{}, {}\n'.format(scan_start_dtime,scan_end_dtime))
        else:
            raise ValueError('Scan ' + str(statusDict['Nsweep']) + ' frequency vector does not match initial!')
        
        # Update status
        statusDict['Nsweep']=statusDict['Nsweep']+1
        statusDict['curr_time']=datetime.datetime.now()
        print('\nSweep %s' % statusDict['Nsweep'] + ' complete.')
        write_dict_json(statusDict, status_fname)
        
        ctrlDict = read_json(ctrl_fname)
        
        if ctrlDict['pause']:
            statusDict['paused']=1
            write_dict_json(statusDict, status_fname)
            while ctrlDict['pause']:
                time.sleep(10)
                ctrlDict = read_json(ctrl_fname)
            statusDict['paused']=0
            write_dict_json(statusDict, status_fname)
            
        if ctrlDict['run']==0:
            statusDict['extFlag']=0
        elif not args.endless and statusDict['Nsweep']==args.runs:
            statusDict['extFlag']=statusDict['Nsweep']
            
        write_dict_json(statusDict, status_fname)
    
    statusDict['running']=0
    write_dict_json(statusDict, status_fname)
    
    

            


if __name__ == '__main__':
    main()
