#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 25 22:49:16 2021

@author: Scott Kriel

Description: Script to fetch info on SDR device
"""

import sys, logging, argparse, os, shutil, re
import numpy as np #use numpy for buffers 
from simplespectral import zeros
import SoapySDR
from SoapySDR import * #SOAPY_SDR_ constants  
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

def setup_argument_parser():
    """Setup command line parser"""
    # Fix help formatter width
    if 'COLUMNS' not in os.environ:
        os.environ['COLUMNS'] = str(shutil.get_terminal_size().columns)

    parser = argparse.ArgumentParser(
        #prog='soapy_power',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Obtain a power spectrum from SoapySDR devices',
        add_help=False
    )

    # Fix recognition of optional argements of type float_with_multiplier
    parser._negative_number_matcher = re_float_with_multiplier_negative

    main_title = parser.add_argument_group('Main options')
    main_title.add_argument('-h', '--help', action='help',
                            help='show this help message and exit')
    main_title.add_argument('-f', '--freq', metavar='Hz|Hz:Hz', type=freq_or_freq_range, default='92000000',
                            help='center frequency or frequency range to scan, number '
                            'can be followed by a k, M or G multiplier (default: %(default)s)')
    
    output_group = main_title.add_mutually_exclusive_group()
    output_group.add_argument('-O', '--output', metavar='FILE', type=argparse.FileType('w'), default=sys.stdout,
                              help='output to file (incompatible with --output-fd, default is stdout)')
    output_group.add_argument('--output-fd', metavar='NUM', type=int, default=None,
                              help='output to existing file descriptor (incompatible with -O)')
    
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
    
    device_title = parser.add_argument_group('Device settings')
    device_title.add_argument('-d', '--device', default='0',
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

    return parser

def get_samples(f0, N, gain, sampleRate, repeats, pol):
    # f0: centre frequency, 
    # N: number of samples per repeat
    # gain -> total receiver gain
    # pol -> SDR device ID string {'0','1'}
    # repeats -> Number of times to repeat measurement
    
    # Initialise SDR object with desired parameter
    args = dict(device_id=pol)
    sdr = SoapySDR.Device(args)
    sdr.setSampleRate(SOAPY_SDR_RX, 0, sampleRate)
    sdr.setFrequency(SOAPY_SDR_RX, 0, f0)
    # Set Auto Gain Control
    sdr.setGainMode(SOAPY_SDR_RX, 0,False)
    auto_gain=sdr.getGainMode(SOAPY_SDR_RX, 0)
    # Set overall gain and output gains of each element
    gain_types=sdr.listGains(SOAPY_SDR_RX, 0)
    sdr.setGain(SOAPY_SDR_RX,0,gain)
    # print(str(gain_types[0])+': '+str(sdr.getGain(SOAPY_SDR_RX,0,gain_types[0])))
    # print(str(gain_types[1])+': '+str(sdr.getGain(SOAPY_SDR_RX,0,gain_types[1])))
    # print(str(gain_types[2])+': '+str(sdr.getGain(SOAPY_SDR_RX,0,gain_types[2])))

    # Setup stream. Give it time to setup before activating
    rxStream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
    time.sleep(0.1)
    err = sdr.activateStream(rxStream)
    if err!=0:
        print(err)
    # Initialise buffer for reading
    buffer_size=sdr.getStreamMTU(rxStream)
    buff = zeros(N, np.complex64)
    #print('Buffer size: '+str(sys.getsizeof(buff)))
    data = zeros([N, repeats], np.complex64)
    # Store start time
    start=time.time()
    # Read stream
    n_repeat=0
    while(n_repeat<repeats):
        sr = sdr.readStream(rxStream, [buff], len(buff))
        print("Sample Number: %d" %n_repeat)
        if (sr.ret==N):
            print('Success')
            #Save raw IQ data
            data[:,n_repeat]=buff
            n_repeat=n_repeat+1
        else:
            print(sr.ret)
            #err=sdr.deactivateStream(rxStream)
            #if err==0:
            #    print('Stream Deactivated')
            #else:
                #print(err)
            #sdr.closeStream(rxStream)
            # Setup stream. Give it time to setup before activating
            #rxStream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
            #time.sleep(0.5)
            #err = sdr.activateStream(rxStream)
        
            #if err==0:
            #    print("Stream Activated.")
            #else:
            #    print(err)
       
    stop=time.time()
    sdr.deactivateStream(rxStream)
    sdr.closeStream(rxStream)
    return data, start, stop

def main():
    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    data, start, stop = get_samples(args.freq[0], args.bins, args.gain, args.rate, args.repeats, args.device)
    print(data, file=args.output)

        
    
if __name__ == '__main__':
    main()
