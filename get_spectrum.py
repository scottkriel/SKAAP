#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 25 22:49:16 2021

@author: Scott Kriel

Description: Script to fetch info on SDR device
"""
import SoapySDR
from SoapySDR import * #SOAPY_SDR_ constants  
import time 
import numpy as np #use numpy for buffers 
import sys
from simplespectral import zeros

def get_spectrum(f0=92e06, N=65536, gain=15.0, sampleRate=10e06, pol='0', avg=1):
    # f0: centre frequency, 
    # N: number of samples/bins
    # gain -> total receiver gain
    # pol -> SDR device ID string {'0','1'}
    # avg -> Number of spectra to average
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
    data = zeros(N, np.complex64)
    # Store start time
    start=time.time()
    # Read stream
    sr = sdr.readStream(rxStream, [buff], len(buff))
    if (sr.ret==N):
        #Save buffer to data upon success
        data=buff
    else:
        print(sr.ret)
       
    stop=time.time()
    sdr.deactivateStream(rxStream)
    sdr.closeStream(rxStream)
    return data, start, stop

def main():
    
    if len(sys.argv)<2:
        data, start, stop = get_samples()
    elif len(sys.argv)==2:
        data, start, stop = get_samples(float(sys.argv[1]))
    elif len(sys.argv)==3:
        data, start, stop = get_samples(float(sys.argv[1]),int(sys.argv[2]))
    elif len(sys.argv)==4:
        data, start, stop = get_samples(float(sys.argv[1]),int(sys.argv[2]),float(sys.argv[3]))
    
    np.save('data.npy',data)
    for mm  in data:
        print(mm)
        
    
if __name__ == '__main__':
    main()
